from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.modules.student_course_directory.course_dto import CourseItemResponse


class CourseFavoriteView(BaseModel):
    course_id: int
    is_favorited: bool
    created_at: Optional[datetime] = None
    course: Optional[CourseItemResponse] = None

    model_config = ConfigDict(from_attributes=True)


class CourseFavoriteListResponse(BaseModel):
    items: list[CourseFavoriteView]
    total_items: int
    total_pages: int
    current_page: int
    model_config = ConfigDict(from_attributes=True)
