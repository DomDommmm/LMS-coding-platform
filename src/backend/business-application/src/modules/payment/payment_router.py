from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session
from src.middlewares.auth_middleware import UserPayload, get_current_user
from src.modules.payment.payment_dto import (
    CancelTransactionResponse,
    CreatePaymentRequest,
    CreatePaymentResponse,
    PayOSWebhookRequest,
    TransactionStatusResponse,
)
from src.modules.payment.payment_service import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


def get_payment_service(
    db: AsyncSession = Depends(get_db_session),
) -> PaymentService:
    return PaymentService(db)


# ---------------------------------------------------------------------------
# Endpoint 1: POST /payments/payos/create
# ---------------------------------------------------------------------------
@router.post(
    "/payos/create",
    response_model=CreatePaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Khởi tạo đơn thanh toán VietQR qua PayOS",
)
async def create_payos_payment(
    request: CreatePaymentRequest,
    user: UserPayload = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
) -> CreatePaymentResponse:
    return await service.create_payment(student_id=user["sub"], request=request)


# ---------------------------------------------------------------------------
# Endpoint 2: POST /payments/payos-webhook
# ---------------------------------------------------------------------------
@router.post(
    "/payos-webhook",
    status_code=status.HTTP_200_OK,
    summary="Xử lý webhook thanh toán từ PayOS (Public, verify bằng HMAC-SHA256)",
)
async def handle_payos_webhook(
    payload: PayOSWebhookRequest,
    service: PaymentService = Depends(get_payment_service),
) -> dict:
    return await service.process_webhook(payload)


# ---------------------------------------------------------------------------
# Endpoint 3: GET /payments/transactions/{transactionCode}/status
# ---------------------------------------------------------------------------
@router.get(
    "/transactions/{transactionCode}/status",
    response_model=TransactionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Kiểm tra trạng thái giao dịch (Frontend Polling)",
)
async def get_transaction_status(
    transactionCode: Annotated[str, Path(description="Mã giao dịch LMS, vd: TXN-123456")],
    service: PaymentService = Depends(get_payment_service),
) -> TransactionStatusResponse:
    return await service.get_transaction_status(transaction_code=transactionCode)


# ---------------------------------------------------------------------------
# Endpoint 4: POST /payments/transactions/{transactionCode}/cancel
# ---------------------------------------------------------------------------
@router.post(
    "/transactions/{transactionCode}/cancel",
    response_model=CancelTransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Hủy giao dịch thanh toán",
)
async def cancel_payment_transaction(
    transactionCode: Annotated[str, Path(description="Mã giao dịch LMS")],
    user: UserPayload = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
) -> CancelTransactionResponse:
    return await service.cancel_transaction(
        transaction_code=transactionCode, user_id=user["sub"]
    )
