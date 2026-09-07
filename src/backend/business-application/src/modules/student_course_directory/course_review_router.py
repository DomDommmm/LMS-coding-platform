from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_async_db_session
from src.middlewares.role_middleware import require_role
from src.models.base_model import Role
from src.modules.student_course_directory.course_review_dto import (
    CourseReviewListResponse,
    CourseReviewPatch,
    CourseReviewView,
    CourseReviewWrite,
)
from src.modules.student_course_directory.course_review_service import CourseReviewService


router = APIRouter(tags=["Course Review"])

def get_course_review_service(db: AsyncSession = Depends(get_async_db_session)) -> CourseReviewService:
    return CourseReviewService(db)

def get_current_student_id(user: dict = Depends(require_role(Role.STUDENT))) -> int:
    return int(user["sub"])


@router.get("/courses/{course_id}/reviews", response_model=CourseReviewListResponse)
async def get_reviews(
    course_id: int,
    rating: int | None = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    service: CourseReviewService = Depends(get_course_review_service)
):
    return await service.get_reviews(course_id, rating, page, size)


@router.post("/courses/{course_id}/reviews", response_model=CourseReviewView)
async def add_review(
    course_id: int,
    data: CourseReviewWrite,
    student_id: int = Depends(get_current_student_id),
    service: CourseReviewService = Depends(get_course_review_service)
):
    return await service.add_review(course_id, student_id, data)


@router.patch("/courses/{course_id}/reviews/{review_id}", response_model=CourseReviewView)
async def update_review(
    course_id: int,
    review_id: int,
    data: CourseReviewPatch,
    student_id: int = Depends(get_current_student_id),
    service: CourseReviewService = Depends(get_course_review_service)
):
    return await service.update_review(course_id, review_id, student_id, data)
