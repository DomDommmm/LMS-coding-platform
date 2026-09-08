"""DTOs for the public course directory APIs."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.base_model import CourseStatus


T = TypeVar("T")


class ResourceResponse(BaseModel, Generic[T]):
    data: T


class MutationResponse(ResourceResponse[T], Generic[T]):
    message: str


class Pagination(BaseModel):
    page: int
    size: int
    total: int


class PriceType(str, Enum):
    FREE = "free"
    PAID = "paid"


class CourseView(BaseModel):
    id: int
    teacher_id: int
    title: str
    slug: str
    # rating: float - Sau khi thuc hien denormalize thi se tha 
    field: str | None
    tags: str | None
    description: str | None
    thumbnail_url: str | None
    price: Decimal  
    status: CourseStatus
    created_at: datetime
    updated_at: datetime


class CourseListResponse(BaseModel):
    data: list[CourseView]
    pagination: Pagination


class TeacherProfileView(BaseModel):
    user_id: int
    full_name: str
    avatar_url: str | None
    headline: str | None
    expertise_tags: str | None
    years_of_experience: int | None
    education_entries: str | None
    experience_entries: str | None
    github_url: str | None
    linkedin_url: str | None
    website_url: str | None
    email: str | None
    phone: str | None
    bio: str | None
    created_at: datetime
    updated_at: datetime


class InstructorListResponse(BaseModel):
    data: list[TeacherProfileView]
    pagination: Pagination


class InstructorDetailView(TeacherProfileView):
    courses: list[CourseView]


class SectionOverviewView(BaseModel):
    id: int
    course_id: int
    title: str
    position: int
    lesson_count: int


class ReviewSummary(BaseModel):
    average_rating: float
    total_reviews: int
    rating_distribution: dict[int, int] | None = None


class CourseDetailView(CourseView):
    instructor: TeacherProfileView
    sections: list[SectionOverviewView]
    is_favorited: bool | None = Field(default=None, exclude_if=lambda value: value is None)
    is_enrolled: bool | None = Field(default=None, exclude_if=lambda value: value is None)
    review_summary: ReviewSummary


class CourseFavoriteView(BaseModel):
    id: int
    student_id: int
    course_id: int
    created_at: datetime
    is_favorited: bool = True
    course: CourseView | None = None

    model_config = ConfigDict(from_attributes=True)


class FavoriteListResponse(BaseModel):
    data: list[CourseFavoriteView]
    pagination: Pagination


class FavoriteRemovalView(BaseModel):
    course_id: int
    is_favorited: Literal[False] = False


class CourseReviewWrite(BaseModel):
    rating: int = Field(ge=1, le=5)
    content: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class CourseReviewPatch(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    content: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if "rating" in self.model_fields_set and self.rating is None:
            raise ValueError("rating cannot be null")
        return self

    model_config = ConfigDict(extra="forbid")


class CourseReviewView(BaseModel):
    id: int
    course_id: int
    student_id: int
    rating: int
    content: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewListResponse(BaseModel):
    data: list[CourseReviewView]
    pagination: Pagination
    summary: ReviewSummary
