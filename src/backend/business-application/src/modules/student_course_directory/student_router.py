from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from src.middlewares.auth_middleware import UserPayload, get_current_user
from src.modules.student_course_directory.course_dependency import get_course_service
from src.modules.student_course_directory.course_dto import (
    CompleteContentResponse,
    QuizResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    StudentCoursesResponse,
    StudyResponse,
    QuizAttemptView,
)
from src.modules.student_course_directory.course_service import CourseService

router = APIRouter(
    prefix="/student",
    tags=["Student Study Mode"],
)


def _extract_user_id(user: UserPayload) -> int:
    """Extract and validate user_id from get_current_user payload."""
    user_id: int | None = user.get("sub", None)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid user id in authorization token",
        )
    return user_id


# ---------------------------------------------------------------------------
# Endpoint 4 — GET /student/courses  (auth required)
# ---------------------------------------------------------------------------

@router.get("/courses", response_model=StudentCoursesResponse, status_code=200)
async def get_enrolled_courses(
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> StudentCoursesResponse:
    user_id = _extract_user_id(user)
    return await service.get_enrolled_courses(user_id)


# ---------------------------------------------------------------------------
# Endpoint 5 — GET /student/courses/{slug}/study  (auth required)
# ---------------------------------------------------------------------------

@router.get("/courses/{slug}/study", response_model=StudyResponse, status_code=200)
async def get_study_content(
    slug: Annotated[str, Path()],
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> StudyResponse:
    user_id = _extract_user_id(user)
    return await service.get_study_content(slug, user_id)


# ---------------------------------------------------------------------------
# Endpoint 6 — POST /student/progress/lesson-content/{id}/complete
#              path param is {id} per spec — Python alias: lesson_content_id
# ---------------------------------------------------------------------------

@router.post(
    "/progress/lesson-contents/{id}/complete",
    response_model=CompleteContentResponse,
    status_code=200,
)
async def complete_lesson_content(
    lesson_content_id: Annotated[int, Path(alias="id")],
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> CompleteContentResponse:
    user_id = _extract_user_id(user)
    return await service.complete_lesson_content(lesson_content_id, user_id)

@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=QuizAttemptView,
    status_code=201,
)
async def create_quiz_attempt(
    quiz_id: int,
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> QuizAttemptView:
    user_id = _extract_user_id(user)
    return await service.create_quiz_attempt(quiz_id, user_id)

@router.get(
    "/quizzes/{quiz_id}/attempts/{attempt_id}",
    response_model=QuizAttemptView,
    status_code=200,
)
async def get_quiz_attempt(
    quiz_id: int,
    attempt_id: int,
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> QuizAttemptView:
    user_id = _extract_user_id(user)
    return await service.get_quiz_attempt(quiz_id, attempt_id, user_id)

@router.post(
    "/quizzes/{quiz_id}/attempts/{attempt_id}/submit",
    response_model=QuizAttemptView,
    status_code=200,
)
async def submit_quiz_attempt(
    quiz_id: int,
    attempt_id: int,
    payload: QuizSubmitRequest,
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> QuizAttemptView:
    user_id = _extract_user_id(user)
    return await service.submit_quiz_attempt(quiz_id, attempt_id, payload, user_id)

# ---------------------------------------------------------------------------
# Endpoint 7 — GET /student/quizzes/{quizId}
#              path param is {quizId} per spec — Python alias: quiz_id
# ---------------------------------------------------------------------------

@router.get("/quizzes/{quizId}", response_model=QuizResponse, status_code=200)
async def get_quiz(
    quiz_id: Annotated[int, Path(alias="quizId")],
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> QuizResponse:
    user_id = _extract_user_id(user)
    return await service.get_quiz(quiz_id)


# ---------------------------------------------------------------------------
# Endpoint 8 — POST /student/quizzes/{quizId}/submit
#              path param is {quizId} per spec — Python alias: quiz_id
# ---------------------------------------------------------------------------

@router.post(
    "/quizzes/{quizId}/submit",
    response_model=QuizSubmitResponse,
    status_code=200,
)
async def submit_quiz(
    quiz_id: Annotated[int, Path(alias="quizId")],
    payload: QuizSubmitRequest,
    user: UserPayload = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> QuizSubmitResponse:
    user_id = _extract_user_id(user)
    return await service.submit_quiz(quiz_id, payload, user_id)
