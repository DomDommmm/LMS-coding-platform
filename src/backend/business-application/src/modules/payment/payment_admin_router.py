from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session
from src.middlewares.auth_middleware import UserPayload
from src.middlewares.role_middleware import require_role
from src.models.base_model import PaymentStatus, Role
from src.modules.payment.payment_dto import (
    PaginatedPaymentTransactionView,
    PaginatedEnrollmentView
)
from src.modules.payment.payment_service import PaymentService

router = APIRouter(
    tags=["Admin Payments"],
)

def get_payment_service(db: AsyncSession = Depends(get_db_session)) -> PaymentService:
    return PaymentService(db)

@router.get(
    "/admin/payments",
    response_model=PaginatedPaymentTransactionView,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách giao dịch (Admin)",
)
async def get_admin_payments(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: PaymentStatus | None = Query(None, alias="status"),
    user: UserPayload = Depends(require_role(Role.ADMIN)),
    service: PaymentService = Depends(get_payment_service),
) -> PaginatedPaymentTransactionView:
    return await service.get_admin_payments(page=page, size=size, status=status_filter)

@router.get(
    "/admin/enrollments",
    response_model=PaginatedEnrollmentView,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách khóa học đã đăng ký (Admin)",
)
async def get_admin_enrollments(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: UserPayload = Depends(require_role(Role.ADMIN)),
    service: PaymentService = Depends(get_payment_service),
) -> PaginatedEnrollmentView:
    return await service.get_admin_enrollments(page=page, size=size)

