from enum import Enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from src.models.base_model import LessonContentType, QuizAttemptStatus


class PriceType(str, Enum):
    FREE = "free"
    PAID = "paid"


class EnrollStatus(str, Enum):
    ENROLLED = "enrolled"
    PENDING_PAYMENT = "pending_payment"


class CourseItemResponse(BaseModel):
    id: int
    slug: str
    title: str
    thumbnail_url: str
    price: float
    price_type: PriceType
    field: str
    tags: list[str]
    enrolled_count: int
    rating: float
    model_config = ConfigDict(from_attributes=True)


class CourseCatalogResponse(BaseModel):
    total_items: int
    total_pages: int
    current_page: int
    items: list[CourseItemResponse]
    model_config = ConfigDict(from_attributes=True)


class SectionOverviewResponse(BaseModel):
    id: int
    title: str
    position: int
    lesson_count: int
    model_config = ConfigDict(from_attributes=True)


class CourseDetailResponse(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    price: float
    price_type: PriceType
    field: str
    tags: list[str]
    enrolled_count: int
    rating: float
    sections: list[SectionOverviewResponse]
    model_config = ConfigDict(from_attributes=True)


class EnrollResponse(BaseModel):
    status: EnrollStatus
    checkout_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class UnenrollResponse(BaseModel):
    message: str
    model_config = ConfigDict(from_attributes=True)


class EnrolledCourseResponse(BaseModel):
    id: int
    slug: str
    title: str
    thumbnail_url: str
    progress_percent: float
    model_config = ConfigDict(from_attributes=True)


class StudentCoursesResponse(BaseModel):
    items: list[EnrolledCourseResponse]
    model_config = ConfigDict(from_attributes=True)



class LessonContentStudyResponse(BaseModel):
    id: int
    content_type: LessonContentType
    media_url: Optional[str] = None
    quiz_id: Optional[int] = None
    reading_content_id: Optional[int] = None
    completed: bool
    model_config = ConfigDict(from_attributes=True)
class LessonStudyResponse(BaseModel):
    id: int
    title: str
    position: int
    locked: bool
    contents: list[LessonContentStudyResponse]
    model_config = ConfigDict(from_attributes=True)


class SectionStudyResponse(BaseModel):
    id: int
    title: str
    position: int
    lessons: list[LessonStudyResponse]
    model_config = ConfigDict(from_attributes=True)


class StudyResponse(BaseModel):
    course_slug: str
    sections: list[SectionStudyResponse]
    model_config = ConfigDict(from_attributes=True)


class CompleteContentResponse(BaseModel):
    message: str
    completed_at: datetime
    model_config = ConfigDict(from_attributes=True)




class QuizOptionResponse(BaseModel):
    id: int
    text: str
    model_config = ConfigDict(from_attributes=True)


class QuizQuestionResponse(BaseModel):
    id: int
    question_text: str
    options: list[QuizOptionResponse]
    model_config = ConfigDict(from_attributes=True)


class QuizSubmissionView(BaseModel):
    id: int
    quiz_attempt_id: int
    score: float
    answers: dict[int, int]
    submitted_at: datetime
    model_config = ConfigDict(from_attributes=True)
    
    from pydantic import field_validator
    
    @field_validator("answers", mode="before")
    @classmethod
    def parse_answers(cls, v):
        if isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
            except Exception:
                return v
            res = {}
            if isinstance(parsed, dict):
                for k, val in parsed.items():
                    try:
                        res[int(k)] = int(val)
                    except (ValueError, TypeError):
                        pass
                return res
        elif isinstance(v, dict):
            res = {}
            for k, val in v.items():
                try:
                    res[int(k)] = int(val)
                except (ValueError, TypeError):
                    pass
            return res
        return v


class QuizOptionView(BaseModel):
    id: int
    question_id: int
    content: str
    model_config = ConfigDict(from_attributes=True)


class QuizQuestionView(BaseModel):
    id: int
    quiz_id: int
    title: Optional[str] = None
    content: str
    question_type: str
    points: float
    options: list[QuizOptionView]
    model_config = ConfigDict(from_attributes=True)


class QuizAttemptView(BaseModel):
    id: int
    quiz_id: int
    student_id: int
    attempt_no: int
    status: QuizAttemptStatus
    started_at: datetime
    submitted_at: Optional[datetime] = None
    passed: Optional[bool] = None
    attempts_left: Optional[int] = None
    expires_at: Optional[datetime] = None
    questions: Optional[list[QuizQuestionView]] = None
    submission: Optional[QuizSubmissionView] = None
    
    model_config = ConfigDict(from_attributes=True)


class QuizAttemptListResponse(BaseModel):
    data: list[QuizAttemptView]


class QuizSubmitRequest(BaseModel):
    answers: dict[int, int]
    model_config = ConfigDict(from_attributes=True)


class QuizResponse(BaseModel):
    id: int
    title: str
    passing_score: float
    questions: list[QuizQuestionResponse]
    model_config = ConfigDict(from_attributes=True)


class QuizSubmitResponse(BaseModel):
    submission_id: int
    score: float
    passed: bool
    correct_count: int
    total_count: int
    model_config = ConfigDict(from_attributes=True)
