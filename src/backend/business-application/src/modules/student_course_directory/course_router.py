from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from src.middlewares.auth_middleware import UserPayload, get_current_user
from src.modules.student_course_directory.course_dependency import get_course_service
from src.modules.student_course_directory.course_dto import (
    CourseCatalogResponse,
    CourseDetailResponse,
    EnrollResponse,
    PriceType,
    UnenrollResponse,
)
from src.modules.student_course_directory.course_service import CourseService

router = APIRouter(
    prefix="/courses",
    tags=["Student Course Directory"],
)


# ---------------------------------------------------------------------------
# Endpoint 1 — GET /courses  (public, no auth)
# ---------------------------------------------------------------------------

@router.get("", response_model=CourseCatalogResponse, status_code=200)
async def get_course_catalog(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Annotated[str | None, Query()] = None,
    price_type: Annotated[PriceType | None, Query()] = None,
    service: CourseService = Depends(get_course_service),
) -> CourseCatalogResponse:
    return await service.get_course_catalog(page, size, q, price_type)


# ---------------------------------------------------------------------------
# Endpoint 2 — GET /courses/{slug}  (public, no auth)
# ---------------------------------------------------------------------------

@router.get("/{slug}", response_model=CourseDetailResponse, status_code=200)
async def get_course_detail(
    slug: Annotated[str, Path()],
    service: CourseService = Depends(get_course_service),
) -> CourseDetailResponse:
    return await service.get_course_detail(slug)


# ---------------------------------------------------------------------------
# Endpoint 3 — POST /courses/{slug}/enroll  (auth required → 201)
# ---------------------------------------------------------------------------

from fastapi.responses import JSONResponse

@router.post("/{slug}/enroll", response_model=EnrollResponse, status_code=201)
async def enroll_course(
    slug: Annotated[str, Path()],
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> EnrollResponse | JSONResponse:
    user_id: int | None = user.get("sub", None)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid user id in authorization token",
        )
    return await service.enroll_course(slug, user_id)


# ---------------------------------------------------------------------------
# Endpoint 9 — POST /courses/{slug}/unenroll  (auth required → 200)
# ---------------------------------------------------------------------------

@router.post("/{slug}/unenroll", response_model=UnenrollResponse, status_code=200)
async def unenroll_course(
    slug: Annotated[str, Path()],
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> UnenrollResponse:
    user_id: int | None = user.get("sub", None)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid user id in authorization token",
        )
    return await service.unenroll_course(slug, user_id)
