import math
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.models.course_favorite_model import CourseFavoriteModel
from src.models.course_model import CourseModel
from src.modules.student_course_directory.course_dto import CourseItemResponse
from src.modules.student_course_directory.favorite_dto import (
    CourseFavoriteListResponse,
    CourseFavoriteView,
)

class FavoriteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_favorites(self, student_id: int, page: int, size: int) -> CourseFavoriteListResponse:
        # Count total
        count_stmt = select(func.count()).select_from(CourseFavoriteModel).where(
            CourseFavoriteModel.student_id == student_id
        )
        total_items = await self.db.scalar(count_stmt)
        total_items = total_items or 0
        total_pages = math.ceil(total_items / size) if size > 0 else 0

        from src.models.enrollment_model import EnrollmentModel
        from src.models.course_review_model import CourseReviewModel
        from src.modules.student_course_directory.course_dto import PriceType

        enrolled_count_sq = (
            select(func.count(EnrollmentModel.id))
            .where(EnrollmentModel.course_id == CourseModel.id)
            .scalar_subquery()
            .label("enrolled_count")
        )
        
        rating_sq = (
            select(func.coalesce(func.avg(CourseReviewModel.rating), 0.0))
            .where(CourseReviewModel.course_id == CourseModel.id)
            .scalar_subquery()
            .label("rating")
        )

        # Query favorites joined with course
        stmt = (
            select(CourseFavoriteModel, CourseModel, enrolled_count_sq, rating_sq)
            .join(CourseModel, CourseFavoriteModel.course_id == CourseModel.id)
            .where(CourseFavoriteModel.student_id == student_id)
            .order_by(CourseFavoriteModel.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        items = []
        for fav, course, enrolled_count, rating in rows:
            c_price = float(course.price)
            c_price_type = PriceType.FREE if c_price == 0 else PriceType.PAID
            tags_list = [tag.strip() for tag in course.tags.split(",")] if course.tags else []

            course_item = CourseItemResponse(
                id=course.id,
                slug=course.slug,
                title=course.title,
                thumbnail_url=course.thumbnail_url or "",
                price=c_price,
                price_type=c_price_type,
                field=course.field or "",
                tags=tags_list,
                enrolled_count=int(enrolled_count),
                rating=float(rating),
            )
            items.append(CourseFavoriteView(
                course_id=fav.course_id,
                is_favorited=True,
                created_at=fav.created_at,
                course=course_item
            ))

        return CourseFavoriteListResponse(
            items=items,
            total_items=total_items,
            total_pages=total_pages,
            current_page=page
        )

    async def add_favorite(self, student_id: int, course_id: int) -> CourseFavoriteView:
        # Verify course exists and is public
        course_stmt = select(CourseModel).where(CourseModel.id == course_id, CourseModel.status == "APPROVED")
        course = await self.db.scalar(course_stmt)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found or not approved")

        # Idempotent add
        try:
            fav = CourseFavoriteModel(student_id=student_id, course_id=course_id)
            self.db.add(fav)
            await self.db.commit()
            await self.db.refresh(fav)
            created_at = fav.created_at
        except IntegrityError:
            await self.db.rollback()
            # Already favorited, just fetch the existing one to return created_at
            existing_stmt = select(CourseFavoriteModel).where(
                CourseFavoriteModel.student_id == student_id,
                CourseFavoriteModel.course_id == course_id
            )
            existing_fav = await self.db.scalar(existing_stmt)
            created_at = existing_fav.created_at if existing_fav else None

        return CourseFavoriteView(
            course_id=course_id,
            is_favorited=True,
            created_at=created_at,
            course=None
        )

    async def remove_favorite(self, student_id: int, course_id: int) -> CourseFavoriteView:
        # Idempotent remove
        stmt = delete(CourseFavoriteModel).where(
            CourseFavoriteModel.student_id == student_id,
            CourseFavoriteModel.course_id == course_id
        )
        await self.db.execute(stmt)
        await self.db.commit()
        
        return CourseFavoriteView(
            course_id=course_id,
            is_favorited=False,
            created_at=None,
            course=None
        )
