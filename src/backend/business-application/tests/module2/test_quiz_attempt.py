import pytest
from httpx import AsyncClient
from sqlalchemy import select
from src.app import app
from src.models.quiz_model import QuizModel
from src.models.quiz_attempt_model import QuizAttemptModel
from src.models.base_model import QuizAttemptStatus

pytestmark = pytest.mark.asyncio

class TestCreateQuizAttempt:
    
    @pytest.fixture(autouse=True)
    async def setup_data(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        
        try:
            stmt = select(QuizModel.id).where(QuizModel.title.ilike("%Python%"))
            result = await async_db_session.execute(stmt)
            quiz_id = result.scalar()
            if not quiz_id:
                stmt2 = select(QuizModel.id).limit(1)
                quiz_id = (await async_db_session.execute(stmt2)).scalar()
            self.valid_quiz_id = quiz_id
        finally:
            pass
    async def test_create_attempt_happy_path(self):
        from tests.module2.conftest import override_get_async_db_session
        from src.modules.student_course_directory.course_service import CourseService
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        
        service = CourseService(db_session=async_db_session)
        student_id = 1
        
        # 1. Create first attempt
        attempt1 = await service.create_quiz_attempt(self.valid_quiz_id, student_id)
        assert attempt1.quiz_id == self.valid_quiz_id
        assert attempt1.attempt_no > 0
        assert attempt1.status == "IN_PROGRESS"
        
        # 2. Call again to test ABANDONED logic
        attempt2 = await service.create_quiz_attempt(self.valid_quiz_id, student_id)
        assert attempt2.attempt_no == attempt1.attempt_no + 1
        
        # Verify the first one was abandoned in the same transaction
        stmt = select(QuizAttemptModel.status).where(QuizAttemptModel.id == attempt1.id)
        status = (await async_db_session.execute(stmt)).scalar()
        assert status == QuizAttemptStatus.ABANDONED

    async def test_create_attempt_unenrolled(self, client):
        from src.middlewares.auth_middleware import get_current_user
        from src.app import app
        
        # Override to an unenrolled user
        def override_get_unenrolled_user():
            return {"sub": 99999, "email": "empty@gmail.com", "roles": ["STUDENT"]}
            
        app.dependency_overrides[get_current_user] = override_get_unenrolled_user
        
        response = client.post(f"/api/student/quizzes/{self.valid_quiz_id}/attempts")
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enrolled in this quiz"
        
        app.dependency_overrides.pop(get_current_user, None)

    async def test_create_attempt_max_limits(self):
        from tests.module2.conftest import override_get_async_db_session
        from src.modules.student_course_directory.course_service import CourseService
        from fastapi import HTTPException
        
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        service = CourseService(db_session=async_db_session)
        student_id = 1
        
        # Set quiz attempt limit to 1
        quiz = await async_db_session.get(QuizModel, self.valid_quiz_id)
        quiz.attempts = 1
        await async_db_session.flush()
        
        # Add a SUBMITTED attempt
        submitted_attempt = QuizAttemptModel(
            quiz_id=self.valid_quiz_id,
            student_id=student_id,
            attempt_no=999,
            status=QuizAttemptStatus.SUBMITTED,
        )
        async_db_session.add(submitted_attempt)
        await async_db_session.flush()
        
        # Now try to create a new attempt, it should fail
        with pytest.raises(HTTPException) as exc:
            await service.create_quiz_attempt(self.valid_quiz_id, student_id)
            
        assert exc.value.status_code == 400
        assert "Maximum attempts reached" in exc.value.detail

    async def test_get_attempt_happy_path(self):
        from tests.module2.conftest import override_get_async_db_session
        from src.modules.student_course_directory.course_service import CourseService
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        
        service = CourseService(db_session=async_db_session)
        student_id = 1
        
        # Create an attempt directly in DB first
        attempt = await service.create_quiz_attempt(self.valid_quiz_id, student_id)
        
        # GET it via service
        data = await service.get_quiz_attempt(self.valid_quiz_id, attempt.id, student_id)
        assert data.id == attempt.id
        assert data.quiz_id == self.valid_quiz_id
        assert data.questions is not None
        assert len(data.questions) > 0
        
        # In DTO, is_correct is dropped automatically. 
        # But we can verify by converting to dict (which simulates API response)
        data_dict = data.model_dump()
        assert "is_correct" not in data_dict["questions"][0]
        assert data_dict["status"] == "IN_PROGRESS"
        
    async def test_get_attempt_not_found(self):
        from tests.module2.conftest import override_get_async_db_session
        from src.modules.student_course_directory.course_service import CourseService
        from fastapi import HTTPException
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        
        service = CourseService(db_session=async_db_session)
        with pytest.raises(HTTPException) as exc:
            await service.get_quiz_attempt(self.valid_quiz_id, 999999, 1)
        assert exc.value.status_code == 404

class TestSubmitQuizAttempt:
    valid_quiz_id = 1
    
    async def test_submit_success_and_pass(self):
        from tests.module2.conftest import override_get_async_db_session
        from src.modules.student_course_directory.course_service import CourseService
        from src.modules.student_course_directory.course_dto import QuizSubmitRequest, QuizAttemptStatus
        from src.models.lesson_content_progress_model import LessonContentProgressModel
        from sqlalchemy import select
        
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        service = CourseService(db_session=async_db_session)
        student_id = 1
        
        attempt = await service.create_quiz_attempt(self.valid_quiz_id, student_id)
        attempt_details = await service.get_quiz_attempt(self.valid_quiz_id, attempt.id, student_id)
        
        # Build perfect answers
        answers = {}
        for q in attempt_details.questions:
            from src.models.quiz_question_model import QuizQuestionModel
            from sqlalchemy.orm import selectinload
            db_q = (await async_db_session.execute(select(QuizQuestionModel).options(selectinload(QuizQuestionModel.options)).where(QuizQuestionModel.id == q.id))).scalar_one()
            correct_opt = next(o for o in db_q.options if o.is_correct)
            answers[q.id] = correct_opt.id
            
        payload = QuizSubmitRequest(answers=answers)
        result = await service.submit_quiz_attempt(self.valid_quiz_id, attempt.id, payload, student_id)
        
        assert result.status == QuizAttemptStatus.SUBMITTED
        assert result.passed is True
        assert result.submission is not None
        assert result.submission.score == 100.0
        
        # Check side effect
        from src.models.enrollment_model import EnrollmentModel
        
        from src.models.lesson_content_model import LessonContentModel, LessonContentType
        from sqlalchemy.orm import selectinload
        from src.models.lesson_model import LessonModel
        from src.models.section_model import SectionModel
        content_stmt = select(LessonContentModel).options(selectinload(LessonContentModel.lesson).selectinload(LessonModel.section)).where(LessonContentModel.content_type == LessonContentType.QUIZ, LessonContentModel.content_id == attempt_details.quiz_id)
        lesson_content = (await async_db_session.execute(content_stmt)).scalar_one_or_none()
        course_id = lesson_content.lesson.section.course_id
        enroll_id = (await async_db_session.execute(select(EnrollmentModel.id).where(EnrollmentModel.student_id == student_id, EnrollmentModel.course_id == course_id))).scalar_one_or_none()
        progress = (await async_db_session.execute(select(LessonContentProgressModel).where(LessonContentProgressModel.enrollment_id == enroll_id))).scalars().all()
        assert any(p.completed for p in progress), "Progress should be marked completed"
        
    async def test_submit_success_and_fail(self):
        from tests.module2.conftest import override_get_async_db_session
        from src.modules.student_course_directory.course_service import CourseService
        from src.modules.student_course_directory.course_dto import QuizSubmitRequest, QuizAttemptStatus
        from sqlalchemy import select
        
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        service = CourseService(db_session=async_db_session)
        student_id = 1
        
        attempt = await service.create_quiz_attempt(self.valid_quiz_id, student_id)
        attempt_details = await service.get_quiz_attempt(self.valid_quiz_id, attempt.id, student_id)
        
        # Build wrong answers
        answers = {}
        for q in attempt_details.questions:
            from src.models.quiz_question_model import QuizQuestionModel
            from sqlalchemy.orm import selectinload
            db_q = (await async_db_session.execute(select(QuizQuestionModel).options(selectinload(QuizQuestionModel.options)).where(QuizQuestionModel.id == q.id))).scalar_one()
            wrong_opt = next(o for o in db_q.options if not o.is_correct)
            answers[q.id] = wrong_opt.id
            
        payload = QuizSubmitRequest(answers=answers)
        result = await service.submit_quiz_attempt(self.valid_quiz_id, attempt.id, payload, student_id)
        
        assert result.status == QuizAttemptStatus.SUBMITTED
        assert result.passed is False
        assert result.submission.score == 0.0

    async def test_submit_idempotent_already_submitted(self):
        from tests.module2.conftest import override_get_async_db_session
        from src.modules.student_course_directory.course_service import CourseService
        from src.modules.student_course_directory.course_dto import QuizSubmitRequest
        
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        service = CourseService(db_session=async_db_session)
        student_id = 1
        
        attempt = await service.create_quiz_attempt(self.valid_quiz_id, student_id)
        payload = QuizSubmitRequest(answers={})
        
        # Submit first time
        result1 = await service.submit_quiz_attempt(self.valid_quiz_id, attempt.id, payload, student_id)
        
        # Submit second time -> should just return old result
        result2 = await service.submit_quiz_attempt(self.valid_quiz_id, attempt.id, payload, student_id)
        
        assert result1.id == result2.id
        assert result1.submission.id == result2.submission.id

    async def test_submit_abandoned_raises_400(self):
        from tests.module2.conftest import override_get_async_db_session
        from src.modules.student_course_directory.course_service import CourseService
        from src.modules.student_course_directory.course_dto import QuizSubmitRequest
        from fastapi import HTTPException
        import pytest
        
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        service = CourseService(db_session=async_db_session)
        student_id = 1
        
        attempt1 = await service.create_quiz_attempt(self.valid_quiz_id, student_id)
        # Creating second attempt marks first as ABANDONED
        attempt2 = await service.create_quiz_attempt(self.valid_quiz_id, student_id)
        
        payload = QuizSubmitRequest(answers={})
        
        with pytest.raises(HTTPException) as exc:
            await service.submit_quiz_attempt(self.valid_quiz_id, attempt1.id, payload, student_id)
            
        assert exc.value.status_code == 400
        assert "abandoned" in exc.value.detail.lower()
