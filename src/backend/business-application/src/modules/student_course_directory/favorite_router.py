from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_async_db_session
from src.middlewares.role_middleware import require_role
from src.models.base_model import Role
from src.modules.student_course_directory.favorite_dto import (
    CourseFavoriteListResponse,
    CourseFavoriteView,
)
from src.modules.student_course_directory.favorite_service import FavoriteService

router = APIRouter(tags=["Course Favorite"])

def get_favorite_service(db: AsyncSession = Depends(get_async_db_session)) -> FavoriteService:
    return FavoriteService(db)

def get_current_student_id(user: dict = Depends(require_role(Role.STUDENT))) -> int:
    return int(user["sub"])

@router.get("/favorites", response_model=CourseFavoriteListResponse)
async def get_favorites(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    student_id: int = Depends(get_current_student_id),
    service: FavoriteService = Depends(get_favorite_service)
):
    return await service.get_favorites(student_id, page, size)

@router.put("/courses/{course_id}/favorite", response_model=CourseFavoriteView)
async def add_favorite(
    course_id: int,
    student_id: int = Depends(get_current_student_id),
    service: FavoriteService = Depends(get_favorite_service)
):
    return await service.add_favorite(student_id, course_id)

@router.delete("/courses/{course_id}/favorite", response_model=CourseFavoriteView)
async def remove_favorite(
    course_id: int,
    student_id: int = Depends(get_current_student_id),
    service: FavoriteService = Depends(get_favorite_service)
):
    return await service.remove_favorite(student_id, course_id)
