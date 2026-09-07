"""
Tests for Module 2 — Endpoint 6:
  POST /student/progress/lesson-contents/{id}/complete  (-> 200)

Auth required (STUDENT role).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from tests.module2.conftest import UNKNOWN_ID
from src.models.lesson_content_model import LessonContentModel, LessonContentType
from src.models.course_model import CourseModel
from src.models.section_model import SectionModel
from src.models.lesson_model import LessonModel


# ---------------------------------------------------------------------------
# Endpoint 6 — POST /student/progress/lesson-contents/{id}/complete
# ---------------------------------------------------------------------------

class TestCompleteLessonContent:
    
    @pytest.fixture(autouse=True)
    async def setup_data(self):
        from tests.module2.conftest import override_get_async_db_session
        
        # Use an async generator to get the session
        session_gen = override_get_async_db_session()
        async_db_session = await anext(session_gen)
        
        try:
            # Find a valid reading content ID in the enrolled course (python-fundamentals)
            stmt = (
                select(LessonContentModel)
                .join(LessonModel, LessonContentModel.lesson_id == LessonModel.id)
                .join(SectionModel, LessonModel.section_id == SectionModel.id)
                .join(CourseModel, SectionModel.course_id == CourseModel.id)
                .where(CourseModel.slug == "python-fundamentals", LessonContentModel.content_type == LessonContentType.READING)
                .limit(1)
            )
            result = await async_db_session.execute(stmt)
            content = result.scalar_one_or_none()
            assert content is not None, "Seed data must contain at least one reading content in python-fundamentals"
            self.valid_reading_id = content.id
            
            # Find a valid quiz content ID in the enrolled course (python-fundamentals)
            stmt_quiz = (
                select(LessonContentModel)
                .join(LessonModel, LessonContentModel.lesson_id == LessonModel.id)
                .join(SectionModel, LessonModel.section_id == SectionModel.id)
                .join(CourseModel, SectionModel.course_id == CourseModel.id)
                .where(CourseModel.slug == "python-fundamentals", LessonContentModel.content_type == LessonContentType.QUIZ)
                .limit(1)
            )
            result = await async_db_session.execute(stmt_quiz)
            quiz_content = result.scalar_one_or_none()
            self.valid_quiz_id = quiz_content.id if quiz_content else None
            
            # Find a valid content ID in an UNENROLLED course (advanced-algorithms)
            stmt_un = (
                select(LessonContentModel)
                .join(LessonModel, LessonContentModel.lesson_id == LessonModel.id)
                .join(SectionModel, LessonModel.section_id == SectionModel.id)
                .join(CourseModel, SectionModel.course_id == CourseModel.id)
                .where(CourseModel.slug == "advanced-algorithms")
                .limit(1)
            )
            result = await async_db_session.execute(stmt_un)
            unenrolled_content = result.scalar_one_or_none()
            self.unenrolled_id = unenrolled_content.id if unenrolled_content else None
        finally:
            try:
                await anext(session_gen)
            except StopAsyncIteration:
                pass

    def test_complete_lesson_content_returns_200_for_valid_reading(self, client):
        response = client.post(
            f"/api/student/progress/lesson-contents/{self.valid_reading_id}/complete"
        )
        assert response.status_code == 200
        body = response.json()
        assert "message" in body
        assert "completed_at" in body

    def test_complete_lesson_content_returns_400_for_non_reading(self, client):
        if not self.valid_quiz_id:
            pytest.skip("No quiz content found in seed data")
        
        response = client.post(
            f"/api/student/progress/lesson-contents/{self.valid_quiz_id}/complete"
        )
        assert response.status_code == 400
        assert "Only READING content" in response.json()["detail"]

    def test_complete_lesson_content_returns_403_for_unenrolled_course(self, unauth_client):
        # User not enrolled in any course
        def override_get_no_enrollments_user():
            return {"sub": 99999, "email": "empty@gmail.com", "roles": ["STUDENT"]}
            
        from src.app import app
        from src.middlewares.auth_middleware import get_current_user
        
        app.dependency_overrides[get_current_user] = override_get_no_enrollments_user
        
        response = unauth_client.post(
            f"/api/student/progress/lesson-contents/{self.valid_reading_id}/complete"
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enrolled in this course"
        
        app.dependency_overrides.pop(get_current_user, None)

    def test_complete_lesson_content_is_idempotent(self, client):
        # Call first time
        response1 = client.post(
            f"/api/student/progress/lesson-contents/{self.valid_reading_id}/complete"
        )
        assert response1.status_code == 200
        
        # Call second time
        response2 = client.post(
            f"/api/student/progress/lesson-contents/{self.valid_reading_id}/complete"
        )
        assert response2.status_code == 200
        assert response2.json()["completed_at"] == response1.json()["completed_at"]

    def test_complete_lesson_content_returns_404_for_unknown_id(self, client):
        response = client.post(
            f"/api/student/progress/lesson-contents/{UNKNOWN_ID}/complete"
        )
        assert response.status_code == 404

    def test_complete_lesson_content_returns_401_without_auth(self, unauth_client):
        response = unauth_client.post(
            f"/api/student/progress/lesson-contents/{self.valid_reading_id}/complete"
        )
        assert response.status_code == 401
