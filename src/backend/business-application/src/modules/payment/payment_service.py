import logging
import random
import time
import uuid
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.cores.settings import FE_URL
from src.models.base_model import (
    CourseStatus,
    Currency,
    NotificationType,
    PaymentStatus,
    utc_now,
)
from src.models.course_model import CourseModel
from src.models.enrollment_model import EnrollmentModel
from src.models.notification_model import NotificationModel
from src.models.transaction_model import TransactionModel
from src.models.user_model import UserModel
from src.models.wallet_model import WalletLedgerModel, WalletModel
from src.modules.payment.payment_dto import (
    CancelTransactionResponse,
    CreatePaymentRequest,
    CreatePaymentResponse,
    PayOSWebhookRequest,
    TransactionStatusResponse,
)
from src.services.payos.payos_client import payos_client
logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payment(self, student_id: int, request: CreatePaymentRequest) -> CreatePaymentResponse:
        course = await self.db.get(CourseModel, request.course_id)
        if not course or course.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Course not found or deleted")

        if course.status not in (CourseStatus.APPROVED, "PUBLISHED"):
            raise HTTPException(status_code=400, detail=f"Course status {course.status} not allow to enroll")

        if course.price <= 0:
            raise HTTPException(status_code=400, detail="You can enroll this course for free. Please use the /enroll/free endpoint instead")

        if course.teacher_id == student_id:
            raise HTTPException(status_code=400, detail="You cannot buy your own course")

        enroll_stmt = select(EnrollmentModel).where(
            EnrollmentModel.student_id == student_id,
            EnrollmentModel.course_id == course.id,
        )
        enroll_res = await self.db.execute(enroll_stmt)
        if enroll_res.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="You are already enrolled in this course")
            
        pending_stmt = select(TransactionModel).where(
            TransactionModel.student_id == student_id,
            TransactionModel.course_id == course.id,
            TransactionModel.status == PaymentStatus.PENDING,
        )
        pending_res = await self.db.execute(pending_stmt)
        existing_tx = pending_res.scalar_one_or_none()

        now = utc_now()
        if existing_tx:
            if existing_tx.expires_at and existing_tx.expires_at > now:
                order_code = int(existing_tx.transaction_code.replace("TXN-", ""))
                return CreatePaymentResponse(
                    transaction_code=existing_tx.transaction_code,
                    order_code=order_code,
                    payos_link=existing_tx.payos_link or "",
                    qrcode=None,
                    amount=int(existing_tx.amount),
                    status=existing_tx.status,
                    expires_at=existing_tx.expires_at
                )
            existing_tx.status = PaymentStatus.FAILED
            await self.db.commit()
        
        order_code = int(time.time() * 1000) % 9000000000000 + random.randint(100, 999)
        transaction_code = f"TXN-{order_code}"
        idempotency_key = request.idempotency_key or str(uuid.uuid4())

        return_url = f"{FE_URL}/payment-result/?status=success&courseId={course.slug}&orderCode={order_code}"
        cancel_url = f"{FE_URL}/payment-result/?status=cancelled&courseId={course.slug}&orderCode={order_code}"
        amount_vnd = int(course.price)
        description = f"LMS {order_code}"[:25]

        try:
            payos_res = await payos_client.create_payment_link(
                order_code=order_code,
                amount=amount_vnd,
                description=description,
                return_url=return_url,
                cancel_url=cancel_url
            )
        except Exception as e:
            logger.error("Cannot create payment link on PayOS: %s", e)
            raise HTTPException(status_code=502, detail=f"PayOS is unavailable: {e}") from e
        
        expires_at = now + timedelta(minutes=15)
        new_tx = TransactionModel(
            student_id=student_id,
            course_id=course.id,
            amount=course.price,
            status=PaymentStatus.PENDING,
            transaction_code=transaction_code,
            payos_code=payos_res.get("paymentLinkId"),
            payos_link=payos_res.get("checkoutUrl"),
            idempotency_key=idempotency_key,
            signature_verified=False,
            expires_at=expires_at,
        )
        self.db.add(new_tx)
        await self.db.commit()
        await self.db.refresh(new_tx)

        return CreatePaymentResponse(
            transaction_code=new_tx.transaction_code,
            order_code=order_code,
            payos_link=new_tx.payos_link or "",
            qrcode=payos_res.get("qrCode"),
            amount=int(new_tx.amount),
            status=new_tx.status,
            expires_at=new_tx.expires_at,
        )

    async def process_webhook(self, payload: PayOSWebhookRequest) -> dict:
        """Xử lý webhook thanh toán thành công từ PayOS và fulfillment đơn hàng."""
        # 1. Xác thực chữ ký số HMAC-SHA256
        data_dict = payload.data.model_dump()
        is_valid = payos_client.verify_webhook_signature(data_dict, payload.signature)
        if not is_valid:
            logger.warning("PayOS Webhook Signature không hợp lệ: %s", payload.signature)
            raise HTTPException(status_code=400, detail="Chữ ký webhook không hợp lệ")
        # 2. Tìm Transaction theo order_code
        order_code = payload.data.orderCode
        transaction_code = f"TXN-{order_code}"
        stmt = select(TransactionModel).where(
            TransactionModel.transaction_code == transaction_code
        )
        res = await self.db.execute(stmt)
        tx = res.scalar_one_or_none()
        if not tx:
            logger.error("Không tìm thấy transaction với mã: %s", transaction_code)
            raise HTTPException(status_code=404, detail="Không tìm thấy thông tin giao dịch")
        # 3. Idempotency check: Tránh thực thi lại nếu webhook gửi lặp lại
        if tx.status == PaymentStatus.COMPLETED:
            return {"status": "ok", "message": "Giao dịch đã được xử lý trước đó"}
        # 4. Kiểm tra mã trạng thái từ PayOS
        if payload.code != "00" or payload.data.code != "00":
            tx.status = PaymentStatus.FAILED
            await self.db.commit()
            return {"status": "ok", "message": "Giao dịch thanh toán thất bại"}
        # 5. Atomic Fulfillment trong cùng 1 Transaction DB
        now = utc_now()
        # A. Cập nhật Transaction
        tx.status = PaymentStatus.COMPLETED
        tx.signature_verified = True
        tx.completed_at = now
        tx.payos_code = payload.data.paymentLinkId
        # B. Tạo Enrollment cho học viên (nếu chưa có)
        enroll_stmt = select(EnrollmentModel).where(
            EnrollmentModel.student_id == tx.student_id,
            EnrollmentModel.course_id == tx.course_id,
        )
        existing_enroll = (await self.db.execute(enroll_stmt)).scalar_one_or_none()
        if not existing_enroll:
            enrollment = EnrollmentModel(
                student_id=tx.student_id,
                course_id=tx.course_id,
                status="ACTIVE",
                enrolled_at=now,
            )
            self.db.add(enrollment)
        # C. Cộng tiền ví giảng viên & Ghi sổ cái bất biến (Wallet Ledger)
        course = await self.db.get(CourseModel, tx.course_id)
        if course:
            wallet_stmt = select(WalletModel).where(
                WalletModel.teacher_id == course.teacher_id
            )
            wallet = (await self.db.execute(wallet_stmt)).scalar_one_or_none()
            if not wallet:
                wallet = WalletModel(
                    teacher_id=course.teacher_id,
                    available_balance=0,
                    pending_balance=0,
                    currency=Currency.USD,
                )
                self.db.add(wallet)
                await self.db.flush()
            wallet.available_balance = int(wallet.available_balance) + int(tx.amount)
            ledger = WalletLedgerModel(
                wallet_id=wallet.id,
                transaction_id=tx.id,
                entry_type="REVENUE",
                amount=tx.amount,
                currency=Currency.USD,
                created_at=now,
            )
            self.db.add(ledger)
            # D. Tạo thông báo cho học viên và giảng viên
            student = await self.db.get(UserModel, tx.student_id)
            student_name = student.full_name if student else "Học viên"
            notify_student = NotificationModel(
                user_id=tx.student_id,
                type=NotificationType.PAYMENT_SUCCESS,
                content=f"Thanh toán thành công khóa học '{course.title}'. Bạn có thể bắt đầu học ngay bây giờ!",
                created_at=now,
            )
            notify_teacher = NotificationModel(
                user_id=course.teacher_id,
                type=NotificationType.PAYMENT_SUCCESS,
                content=f"{student_name} vừa đăng ký khóa học '{course.title}'. Bạn nhận được {tx.amount:,.0f} VND.",
                created_at=now,
            )
            self.db.add_all([notify_student, notify_teacher])
        # Commit toàn bộ thay đổi an toàn
        await self.db.commit()
        return {"status": "ok", "message": "Xử lý webhook và kích hoạt khóa học thành công"}

    async def get_transaction_status(
        self, transaction_code: str
    ) -> TransactionStatusResponse:
        """Lấy trạng thái giao dịch phục vụ polling từ phía frontend."""
        stmt = select(TransactionModel).where(
            TransactionModel.transaction_code == transaction_code
        )
        res = await self.db.execute(stmt)
        tx = res.scalar_one_or_none()
        if not tx:
            raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")
        course = await self.db.get(CourseModel, tx.course_id)
        order_code = int(tx.transaction_code.replace("TXN-", ""))
        return TransactionStatusResponse(
            transaction_code=tx.transaction_code,
            order_code=order_code,
            course_id=tx.course_id,
            course_slug=course.slug if course else None,
            amount=int(tx.amount),
            status=tx.status,
            completed_at=tx.completed_at,
        )
    async def cancel_transaction(
        self, transaction_code: str, user_id: int
    ) -> CancelTransactionResponse:
        """Hủy giao dịch thanh toán khi người dùng nhấn Hủy."""
        stmt = select(TransactionModel).where(
            TransactionModel.transaction_code == transaction_code,
            TransactionModel.student_id == user_id,
        )
        res = await self.db.execute(stmt)
        tx = res.scalar_one_or_none()
        if not tx:
            raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")
        if tx.status == PaymentStatus.COMPLETED:
            raise HTTPException(
                status_code=400, detail="Không thể hủy giao dịch đã hoàn tất"
            )

        # Gọi PayOS để hủy link trên cổng thanh toán
        order_code = int(tx.transaction_code.replace("TXN-", ""))
        try:
            await payos_client.cancel_payment_link(
                order_code_or_id=order_code,
                cancellation_reason="Người dùng hủy giao dịch trên LMS",
            )
        except Exception as e:
            logger.warning("Không thể hủy link trên PayOS: %s", e)

        tx.status = PaymentStatus.FAILED
        await self.db.commit()
        return CancelTransactionResponse(
            transaction_code=tx.transaction_code,
            status=tx.status,
            message="Đã hủy giao dịch thanh toán",
        )

