from datetime import datetime
from pydantic import BaseModel, Field
from src.models.base_model import PaymentStatus

class CreatePaymentRequest(BaseModel):
    course_id: int
    idempotency_key: str | None = Field(
        default=None,
        description="Khóa chống trùng lặp do client gửi lên"
    )

class CreatePaymentResponse(BaseModel):
    transaction_code: str = Field(
        ...,
        description="Mã giao dịch hệ thống LMS"
    )
    order_code: int = Field(
        ...,
        description="Mã đơn hàng PayOS"
    )
    payos_link: str = Field(
        ...,
        description="Link thanh toán PayOS"
    )
    qrcode: str | None = Field(
        default=None,
        description="Chuỗi VietQR raw để client tự render QR code nếu cần"
    )
    amount: int = Field(
        description="Số tiền thanh toán"
    )
    status: PaymentStatus = Field(
        default=PaymentStatus.PENDING,
        description="Trạng thái giao dịch ban đầu"
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Thời điểm hết hạn của link thanh toán"
    )

## PayOS Webhook
class PayOSWebhookData(BaseModel):
    orderCode: int
    amount: int
    description: str
    accountNumber: str
    reference: str
    transactionDateTime: str
    currency: str = "VND"
    paymentLinkId: str
    code: str
    desc: str
    counterAccountBankId: str | None = None # Mã ngân hàng của người chuyển tiền
    counterAccountBankName: str | None = None # Tên ngân hàng người chuyển
    counterAccountName: str | None = None # Tên người chuyển
    counterAccountNumber: str | None = None # Số tài khoản người chuyển
    virtualAccountName: str | None = None # Tên tài khoản ảo
    virtualAccountNumber: str | None = None # Số tài khoản ảo

class PayOSWebhookRequest(BaseModel):
    code: str = Field(..., description="Mã phản hồi từ PayOS")
    desc: str = Field(..., description="Mô tả trạng thái từ PayOS")
    data: PayOSWebhookData = Field(..., description="Dữ liệu chi tiết giao dịch ngân hàng")
    signature: str = Field(..., description="Chữ ký số HMAC-SHA256 để xác thực dữ liệu")

# Transaction Polling
class TransactionStatusResponse(BaseModel):
    transaction_code: str
    order_code: int
    course_id: int
    course_slug: str | None = None
    amount: float
    status: PaymentStatus
    completed_at: datetime | None = None

# Cancel Transaction
class CancelTransactionResponse(BaseModel):
    transaction_code: str
    status: PaymentStatus
    message: str
