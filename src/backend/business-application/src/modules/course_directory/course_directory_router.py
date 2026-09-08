from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_async_db_session
from src.middlewares.auth_middleware import UserPayload, get_current_user
from src.models.base_model import Role
from src.modules.course_directory.course_directory_dto import (
    CourseDetailView,
    CourseFavoriteView,
    CourseListResponse,
    CourseReviewPatch,
    CourseReviewView,
    CourseReviewWrite,
    FavoriteListResponse,
    FavoriteRemovalView,
    InstructorDetailView,
    InstructorListResponse,
    MutationResponse,
    PriceType,
    ResourceResponse,
    ReviewListResponse,
)
from src.modules.course_directory.course_directory_service import CourseDirectoryService


router = APIRouter(tags=["Course Directory"])
optional_bearer = HTTPBearer(auto_error=False)


async def get_service(db: AsyncSession = Depends(get_async_db_session)) -> CourseDirectoryService:
    return CourseDirectoryService(db)


async def current_student(user: UserPayload = Depends(get_current_user)) -> UserPayload:
    if Role.STUDENT not in user.get("roles", []):
        raise HTTPException(403, "Student role required")
    return user

# Thuc hien chay ham get_current_user neu nhu co credential trong header, khong thi tra None de cho Depends pass qua 
async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
) -> UserPayload | None:
    return None if credentials is None else await get_current_user(credentials)


@router.get("/courses", response_model=CourseListResponse)
async def list_courses(
    q: str | None = None,
    field: str | None = None,
    tag: str | None = None,
    price_type: PriceType | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: CourseDirectoryService = Depends(get_service),
):
    return await service.list_courses(page, size, q, field, tag, price_type)


@router.get("/courses/{slug}", response_model=ResourceResponse[CourseDetailView])
async def get_course(
    slug: Annotated[str, Path(min_length=1)],
    user: UserPayload | None = Depends(optional_user),
    service: CourseDirectoryService = Depends(get_service),
):
    user_id = user["sub"] if user else None
    return {"data": await service.get_course(slug, user_id)}


@router.get("/instructors", response_model=InstructorListResponse)
async def list_instructors(
    q: str | None = None,
    field: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: CourseDirectoryService = Depends(get_service),
):
    return await service.list_instructors(page, size, q, field)


@router.get("/instructors/{user_id}", response_model=ResourceResponse[InstructorDetailView])
async def get_instructor(
    user_id: int,
    service: CourseDirectoryService = Depends(get_service),
):
    return {"data": await service.get_instructor(user_id)}


@router.get("/favorites", response_model=FavoriteListResponse)
async def list_favorites(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: UserPayload = Depends(current_student),
    service: CourseDirectoryService = Depends(get_service),
):
    return await service.list_favorites(user["sub"], page, size)


@router.put(
    "/courses/{course_id}/favorite",
    response_model=MutationResponse[CourseFavoriteView],
)
async def add_favorite(
    course_id: int,
    user: UserPayload = Depends(current_student),
    service: CourseDirectoryService = Depends(get_service),
):
    return {
        "data": await service.add_favorite(user["sub"], course_id),
        "message": "Course favorited",
    }


@router.delete(
    "/courses/{course_id}/favorite",
    response_model=MutationResponse[FavoriteRemovalView],
)
async def remove_favorite(
    course_id: int,
    user: UserPayload = Depends(current_student),
    service: CourseDirectoryService = Depends(get_service),
):
    return {
        "data": await service.remove_favorite(user["sub"], course_id),
        "message": "Favorite removed",
    }


@router.get("/courses/{course_id}/reviews", response_model=ReviewListResponse)
async def list_reviews(
    course_id: int,
    rating: int | None = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: CourseDirectoryService = Depends(get_service),
):
    return await service.list_reviews(course_id, rating, page, size)


@router.post(
    "/courses/{course_id}/reviews",
    response_model=MutationResponse[CourseReviewView],
)
async def add_review(
    course_id: int,
    payload: CourseReviewWrite,
    user: UserPayload = Depends(current_student),
    service: CourseDirectoryService = Depends(get_service),
):
    return {
        "data": await service.add_review(course_id, user["sub"], payload),
        "message": "Review saved",
    }


@router.patch(
    "/courses/{course_id}/reviews/{review_id}",
    response_model=MutationResponse[CourseReviewView],
)
async def update_review(
    course_id: int,
    review_id: int,
    payload: CourseReviewPatch,
    user: UserPayload = Depends(current_student),
    service: CourseDirectoryService = Depends(get_service),
):
    return {
        "data": await service.update_review(course_id, review_id, user["sub"], payload),
        "message": "Review updated",
    }
