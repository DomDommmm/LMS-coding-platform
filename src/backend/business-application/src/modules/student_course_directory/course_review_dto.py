from datetime import datetime
from pydantic import BaseModel, Field


class CourseReviewWrite(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    content: str | None = Field(None, max_length=1000)


class CourseReviewPatch(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    content: str | None = Field(None, max_length=1000)


class CourseReviewView(BaseModel):
    id: int
    course_id: int
    student_id: int
    rating: int
    content: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CourseReviewSummary(BaseModel):
    average_rating: float
    total_reviews: int
    rating_distribution: dict[int, int]


class CourseReviewListResponse(BaseModel):
    total_items: int
    total_pages: int
    current_page: int
    summary: CourseReviewSummary
    items: list[CourseReviewView]
