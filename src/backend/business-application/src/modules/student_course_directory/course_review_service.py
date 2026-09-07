import math
from fastapi import HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.course_review_model import CourseReviewModel
from src.models.enrollment_model import EnrollmentModel
from src.modules.student_course_directory.course_review_dto import (
    CourseReviewListResponse,
    CourseReviewPatch,
    CourseReviewSummary,
    CourseReviewView,
    CourseReviewWrite,
)


class CourseReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_reviews(self, course_id: int, rating: int | None, page: int, size: int) -> CourseReviewListResponse:
        # Check rating param
        if rating is not None and not (1 <= rating <= 5):
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

        # 1. Summary: average rating and total count
        summary_stmt = select(
            func.coalesce(func.avg(CourseReviewModel.rating), 0.0),
            func.count(CourseReviewModel.id),
        ).where(CourseReviewModel.course_id == course_id)
        
        summary_res = await self.db.execute(summary_stmt)
        avg_rating, total_reviews = summary_res.first() or (0.0, 0)
        
        # 2. Rating distribution
        dist_stmt = select(
            CourseReviewModel.rating,
            func.count(CourseReviewModel.id)
        ).where(CourseReviewModel.course_id == course_id).group_by(CourseReviewModel.rating)
        
        dist_res = await self.db.execute(dist_stmt)
        dist = {r: 0 for r in range(1, 6)}
        for row in dist_res:
            dist[int(row.rating)] = row[1]

        # 3. List filter
        base_query = select(CourseReviewModel).where(CourseReviewModel.course_id == course_id)
        if rating is not None:
            base_query = base_query.where(CourseReviewModel.rating == rating)
            
        # Count filtered
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_items = await self.db.scalar(count_stmt) or 0
        total_pages = math.ceil(total_items / size) if size > 0 else 0
        
        # Get items
        stmt = base_query.order_by(CourseReviewModel.created_at.desc()).offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        
        items = [CourseReviewView.model_validate(r) for r in rows]
        
        return CourseReviewListResponse(
            total_items=total_items,
            total_pages=total_pages,
            current_page=page,
            summary=CourseReviewSummary(
                average_rating=float(avg_rating),
                total_reviews=total_reviews,
                rating_distribution=dist
            ),
            items=items
        )

    async def add_review(self, course_id: int, student_id: int, data: CourseReviewWrite) -> CourseReviewView:
        # Check enrollment
        enrollment = await self.db.scalar(
            select(EnrollmentModel).where(
                EnrollmentModel.course_id == course_id,
                EnrollmentModel.student_id == student_id
            )
        )
        if not enrollment:
            raise HTTPException(status_code=403, detail="Must be enrolled to review this course")
            
        new_review = CourseReviewModel(
            course_id=course_id,
            student_id=student_id,
            rating=data.rating,
            content=data.content
        )
        self.db.add(new_review)
        
        try:
            await self.db.commit()
            await self.db.refresh(new_review)
            return CourseReviewView.model_validate(new_review)
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=409, detail="DUPLICATE_RESOURCE: You have already reviewed this course")

    async def update_review(self, course_id: int, review_id: int, student_id: int, data: CourseReviewPatch) -> CourseReviewView:
        # Note: Spec says still require enrollment, but technically if they own the review, they were enrolled.
        # But we can verify enrollment just to be safe.
        enrollment = await self.db.scalar(
            select(EnrollmentModel).where(
                EnrollmentModel.course_id == course_id,
                EnrollmentModel.student_id == student_id
            )
        )
        if not enrollment:
            raise HTTPException(status_code=403, detail="Must be enrolled to update review")
            
        review = await self.db.scalar(
            select(CourseReviewModel).where(
                CourseReviewModel.id == review_id,
                CourseReviewModel.course_id == course_id,
                CourseReviewModel.student_id == student_id
            )
        )
        if not review:
            raise HTTPException(status_code=404, detail="Review not found or does not belong to you")
            
        if data.rating is not None:
            review.rating = data.rating
        if data.content is not None:
            review.content = data.content
            
        await self.db.commit()
        await self.db.refresh(review)
        return CourseReviewView.model_validate(review)
