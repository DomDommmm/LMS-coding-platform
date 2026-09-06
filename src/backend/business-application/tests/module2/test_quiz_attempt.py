import pytest
from src.modules.student_course_directory.course_service import CourseService
from src.modules.student_course_directory.course_dto import QuizSubmitRequest
from fastapi import HTTPException
from contextlib import aclosing

pytestmark = pytest.mark.asyncio

class TestQuizAttempt:

    # ==========================
    # CREATE ATTEMPT (3 tests)
    # ==========================

    async def test_create_attempt_happy_path(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            attempt1 = await service.create_quiz_attempt(1, 1)
            assert attempt1.quiz_id == 1
            assert attempt1.status == "IN_PROGRESS"
            
            # Idempotent / abandoned check (creating a second one abandons the first)
            attempt2 = await service.create_quiz_attempt(1, 1)
            assert attempt2.attempt_no == attempt1.attempt_no + 1
            
            # Verify attempt1 is abandoned
            from src.models.quiz_attempt_model import QuizAttemptModel
            att1 = await async_db_session.get(QuizAttemptModel, attempt1.id)
            assert att1.status == "ABANDONED"
        finally:
            await session_gen.aclose()

    async def test_create_attempt_unenrolled(self):
        from tests.module2.conftest import override_get_async_db_session
        from src.models.enrollment_model import EnrollmentModel
        from src.modules.student_course_directory.course_dto import EnrollStatus
        from src.models.course_model import CourseModel
        from sqlalchemy import select
        
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            # 1. Arrange: Create an explicit enrollment for student 2 (not seeded for this course)
            course_stmt = select(CourseModel).where(CourseModel.slug == "python-fundamentals")
            course = (await async_db_session.execute(course_stmt)).scalar_one()
            
            enrollment = EnrollmentModel(student_id=2, course_id=course.id, status=EnrollStatus.ENROLLED.value)
            async_db_session.add(enrollment)
            await async_db_session.commit()
            
            service = CourseService(db_session=async_db_session)
            
            # 2. Verify we can create an attempt for student 2
            attempt = await service.create_quiz_attempt(1, 2)
            assert attempt.id is not None
            
            # 3. Unenroll from course
            await service.unenroll_course("python-fundamentals", 2)
            
            # 4. Try to create another attempt -> should fail with 403
            with pytest.raises(HTTPException) as exc:
                await service.create_quiz_attempt(1, 2)
            assert exc.value.status_code == 403
            assert "Not enrolled" in exc.value.detail
        finally:
            await session_gen.aclose()

    async def test_create_attempt_max_limits(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            
            # Keep creating and submitting until we hit the limit
            # In seed.py, Quiz 1 has max_attempts = 3. 
            # There is already 1 SUBMITTED attempt from seed.py!
            # So creating and submitting 2 more should be fine, the 3rd new one will fail.
            payload = QuizSubmitRequest(answers={"1": 2, "2": 4})
            
            att2 = await service.create_quiz_attempt(1, 1)
            await service.submit_quiz_attempt(1, att2.id, payload, 1)
            
            att3 = await service.create_quiz_attempt(1, 1)
            await service.submit_quiz_attempt(1, att3.id, payload, 1)
            
            with pytest.raises(HTTPException) as exc:
                await service.create_quiz_attempt(1, 1)
            
            assert exc.value.status_code == 400
            assert "Maximum attempts reached" in exc.value.detail
        finally:
            await session_gen.aclose()

    # ==========================
    # GET ATTEMPT (2 tests)
    # ==========================

    async def test_get_attempt_happy_path(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            attempt = await service.create_quiz_attempt(1, 1)
            
            result = await service.get_quiz_attempt(1, attempt.id, 1)
            assert result.id == attempt.id
            assert result.quiz_id == 1
            assert result.status == "IN_PROGRESS"
            assert len(result.questions) > 0 # Should have questions
        finally:
            await session_gen.aclose()

    async def test_get_attempt_not_found(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            with pytest.raises(HTTPException) as exc:
                await service.get_quiz_attempt(1, 999999, 1) # Invalid attempt ID
            assert exc.value.status_code == 404
            assert "not found" in exc.value.detail.lower()
        finally:
            await session_gen.aclose()

    # ==========================
    # SUBMIT ATTEMPT (4 tests)
    # ==========================

    async def test_submit_success_and_pass(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            attempt = await service.create_quiz_attempt(1, 1)
            
            # Submit correct answers for Quiz 1
            # In seed.py: Option 2 is correct for Q1, Option 4 is correct for Q2
            payload = QuizSubmitRequest(answers={"1": 2, "2": 4})
            result = await service.submit_quiz_attempt(1, attempt.id, payload, 1)
            
            assert result.status == "SUBMITTED"
            assert result.passed == True
            assert result.submission.score == 100.0
        finally:
            await session_gen.aclose()

    async def test_submit_success_and_fail(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            attempt = await service.create_quiz_attempt(1, 1)
            
            # Submit WRONG answers for Quiz 1
            # Option 1 is wrong for Q1, Option 3 is wrong for Q2
            payload = QuizSubmitRequest(answers={"1": 1, "2": 3})
            result = await service.submit_quiz_attempt(1, attempt.id, payload, 1)
            
            assert result.status == "SUBMITTED"
            assert result.passed == False
            assert result.submission.score == 0.0
        finally:
            await session_gen.aclose()

    async def test_submit_idempotent_already_submitted(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            attempt = await service.create_quiz_attempt(1, 1)
            
            payload = QuizSubmitRequest(answers={"1": 2, "2": 4})
            # First submit
            result1 = await service.submit_quiz_attempt(1, attempt.id, payload, 1)
            assert result1.status == "SUBMITTED"
            
            # Second submit (idempotent, returns same result, does not raise error)
            result2 = await service.submit_quiz_attempt(1, attempt.id, payload, 1)
            assert result2.status == "SUBMITTED"
            assert result1.submission.id == result2.submission.id
        finally:
            await session_gen.aclose()

    async def test_submit_abandoned_raises_400(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            attempt1 = await service.create_quiz_attempt(1, 1)
            
            # Create a second attempt to abandon the first one
            attempt2 = await service.create_quiz_attempt(1, 1)
            
            # Try to submit the abandoned attempt
            payload = QuizSubmitRequest(answers={"1": 2, "2": 4})
            with pytest.raises(HTTPException) as exc:
                await service.submit_quiz_attempt(1, attempt1.id, payload, 1)
                
            assert exc.value.status_code == 400
            assert "abandoned" in exc.value.detail.lower()
        finally:
            await session_gen.aclose()

    # ==========================
    # LIST ATTEMPTS (3 tests)
    # ==========================

    async def test_list_attempts_happy_path(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            
            # List attempts for user 1, quiz 1 (seed.py already has 1, plus we might have created more if transactions aren't rolled back, but they are)
            result = await service.list_quiz_attempts(1, 1)
            assert hasattr(result, "data")
            assert len(result.data) >= 1
            assert result.data[0].quiz_id == 1
        finally:
            await session_gen.aclose()

    async def test_list_attempts_not_enrolled(self):
        from tests.module2.conftest import override_get_async_db_session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            service = CourseService(db_session=async_db_session)
            with pytest.raises(HTTPException) as exc:
                # 999 is invalid quiz ID
                await service.list_quiz_attempts(999, 1)
            assert exc.value.status_code in [403, 404]
        finally:
            await session_gen.aclose()

    async def test_list_attempts_empty_history(self):
        from tests.module2.conftest import override_get_async_db_session
        from sqlalchemy import text
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        try:
            # Manually delete seed data inside this isolated transaction
            await async_db_session.execute(text("DELETE FROM quiz_submission WHERE quiz_attempt_id IN (SELECT id FROM quiz_attempt WHERE quiz_id = 1 AND student_id = 1)"))
            await async_db_session.execute(text("DELETE FROM quiz_attempt WHERE quiz_id = 1 AND student_id = 1"))
            await async_db_session.commit()
            
            service = CourseService(db_session=async_db_session)
            result = await service.list_quiz_attempts(1, 1)
            assert hasattr(result, "data")
            assert len(result.data) == 0
        finally:
            await session_gen.aclose()
