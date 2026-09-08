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
    PaymentTransactionView,
    EnrollmentView,
    PaginatedPaymentTransactionView,
    PaginatedEnrollmentView,
    PayOSWebhookRequest,
    TransactionStatusResponse,
)
from src.services.payos.payos_client import payos_client
from src.helpers.exchange_rate import get_usd_to_vnd_rate
from sqlalchemy import func

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payment(self, student_id: int, course_id: int, idempotency_key: str | None) -> PaymentTransactionView:
        course = await self.db.get(CourseModel, course_id)
        if not course or course.deleted_at is not None:
            raise HTTPException(status_code=404, detail={"message": "Không tìm thấy khóa học hoặc đã bị xóa", "error_code": "NOT_FOUND"})

        if course.status not in (CourseStatus.APPROVED, "PUBLISHED"):
            raise HTTPException(status_code=400, detail={"message": f"Trạng thái khóa học {course.status} không cho phép đăng ký", "error_code": "INVALID_STATE"})

        if course.price <= 0:
            raise HTTPException(status_code=400, detail={"message": "Khóa học này miễn phí, vui lòng sử dụng API đăng ký miễn phí", "error_code": "INVALID_REQUEST"})

        if course.teacher_id == student_id:
            raise HTTPException(status_code=403, detail={"message": "Bạn không thể mua khóa học của chính mình", "error_code": "FORBIDDEN"})

        enroll_stmt = select(EnrollmentModel).where(
            EnrollmentModel.student_id == student_id,
            EnrollmentModel.course_id == course.id,
        )
        enroll_res = await self.db.execute(enroll_stmt)
        if enroll_res.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail={"message": "Bạn đã đăng ký khóa học này rồi", "error_code": "DUPLICATE_RESOURCE"})
            
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
                return PaymentTransactionView(
                    transaction_code=existing_tx.transaction_code,
                    order_code=order_code,
                    checkout_url=existing_tx.payos_link or "",
                    qrcode=None,
                    amount=int(existing_tx.amount),
                    status=existing_tx.status,
                    expires_at=existing_tx.expires_at
                )
            existing_tx.status = PaymentStatus.FAILED
            await self.db.commit()
        
        order_code = int(time.time() * 1000) % 9000000000000 + random.randint(100, 999)
        transaction_code = f"TXN-{order_code}"
        idemp_key = idempotency_key or str(uuid.uuid4())

        return_url = f"{FE_URL}/payment-result/?status=success&courseId={course.slug}&orderCode={order_code}"
        cancel_url = f"{FE_URL}/payment-result/?status=cancelled&courseId={course.slug}&orderCode={order_code}"
        
        rate = await get_usd_to_vnd_rate()
        amount_vnd = int(float(course.price) * rate)
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
            idempotency_key=idemp_key,
            signature_verified=False,
            expires_at=expires_at,
        )
        self.db.add(new_tx)
        await self.db.commit()
        await self.db.refresh(new_tx)

        return PaymentTransactionView(
            transaction_code=new_tx.transaction_code,
            order_code=order_code,
            checkout_url=new_tx.payos_link or "",
            qrcode=payos_res.get("qrCode"),
            amount=new_tx.amount,
            status=new_tx.status,
            expires_at=new_tx.expires_at,
            course_id=new_tx.course_id,
            student_id=new_tx.student_id,
            created_at=new_tx.created_at,
            updated_at=new_tx.updated_at
        )

    async def process_webhook(self, payload: PayOSWebhookRequest) -> dict:
        """Xử lý webhook thanh toán thành công từ PayOS và fulfillment đơn hàng."""
        # 1. Xác thực chữ ký số HMAC-SHA256
        data_dict = payload.data.model_dump()
        is_valid = payos_client.verify_webhook_signature(data_dict, payload.signature)
        if not is_valid:
            logger.warning("PayOS Webhook Signature không hợp lệ: %s", payload.signature)
            raise HTTPException(status_code=400, detail={"message": "Chữ ký webhook không hợp lệ", "error_code": "INVALID_REQUEST"})
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
            raise HTTPException(status_code=404, detail={"message": "Không tìm thấy thông tin giao dịch", "error_code": "NOT_FOUND"})
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
                status="active",
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
                content=f"{student_name} vừa đăng ký khóa học '{course.title}'. Bạn nhận được {tx.amount:,.2f} USD.",
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
            raise HTTPException(status_code=404, detail={"message": "Không tìm thấy giao dịch", "error_code": "NOT_FOUND"})
        if tx.status == PaymentStatus.COMPLETED:
            raise HTTPException(
                status_code=400, detail={"message": "Không thể hủy giao dịch đã hoàn tất", "error_code": "INVALID_STATE"}
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

    async def get_admin_payments(self, page: int, size: int, status: PaymentStatus | None = None) -> PaginatedPaymentTransactionView:
        stmt = select(TransactionModel).order_by(TransactionModel.created_at.desc())
        if status:
            stmt = stmt.where(TransactionModel.status == status)
        
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(total_stmt)).scalar() or 0
        
        stmt = stmt.offset((page - 1) * size).limit(size)
        items = (await self.db.execute(stmt)).scalars().all()
        
        data = []
        for item in items:
            order_code = int(item.transaction_code.replace("TXN-", "")) if item.transaction_code.startswith("TXN-") else 0
            data.append(PaymentTransactionView(
                transaction_code=item.transaction_code,
                order_code=order_code,
                checkout_url=item.payos_link or "",
                qrcode=None,
                amount=item.amount,
                status=item.status,
                expires_at=item.expires_at,
                completed_at=item.completed_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
                course_id=item.course_id,
                student_id=item.student_id
            ))
            
        return PaginatedPaymentTransactionView(
            data=data,
            pagination={"page": page, "size": size, "total": total}
        )

    async def get_admin_enrollments(self, page: int, size: int) -> PaginatedEnrollmentView:
        stmt = select(EnrollmentModel).order_by(EnrollmentModel.enrolled_at.desc())
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(total_stmt)).scalar() or 0
        
        stmt = stmt.offset((page - 1) * size).limit(size)
        items = (await self.db.execute(stmt)).scalars().all()
        
        data = []
        for item in items:
            data.append(EnrollmentView(
                id=item.id,
                student_id=item.student_id,
                course_id=item.course_id,
                status=item.status,
                enrolled_at=item.enrolled_at,
                completed_at=None
            ))
            
        return PaginatedEnrollmentView(
            data=data,
            pagination={"page": page, "size": size, "total": total}
        )

