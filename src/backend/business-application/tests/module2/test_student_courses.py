"""
Tests for Module 2 — Endpoint 4: GET /student/courses
                    Endpoint 5: GET /student/courses/{slug}/study

Both endpoints require authentication (STUDENT role).

Fixtures used:
  client        — get_current_user overridden → SEED_STUDENT (happy path)
  unauth_client — no override, no Bearer token → 401 (auth guard test)

Mock data reference (from course_service.py):
  _MOCK_ENROLLED_COURSES: 2 items
    {id=1, slug="nhap-mon-lap-trinh-python", progress_percent=65.0}
    {id=4, slug="co-so-du-lieu-sql",         progress_percent=20.0}

  _MOCK_STUDY_DATA["nhap-mon-lap-trinh-python"] — Section 0, Lesson layout:
    position=0 locked=False   (Lesson id=1)
    position=1 locked=False   (Lesson id=2)
    position=2 locked=True    (Lesson id=3)
    position=3 locked=True    (Lesson id=4)
  Q3 rule (mock only): first 2 lessons unlocked, rest locked — no sequential logic.
"""

from __future__ import annotations

import pytest

from tests.module2.conftest import UNKNOWN_SLUG

STUDY_SLUG = "nhap-mon-lap-trinh-python"


# ---------------------------------------------------------------------------
# Endpoint 4 — GET /student/courses
# ---------------------------------------------------------------------------

class TestGetEnrolledCourses:

    def test_get_enrolled_courses_returns_200_with_items(self, client):
        response = client.get("/api/student/courses")

        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert isinstance(body["items"], list)
        assert len(body["items"]) > 0

    def test_get_enrolled_courses_items_have_required_fields(self, client):
        response = client.get("/api/student/courses")

        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            for field in ("id", "slug", "title", "thumbnail_url", "progress_percent"):
                assert field in item, f"Missing field: {field}"

    def test_get_enrolled_courses_progress_percent_is_float(self, client):
        response = client.get("/api/student/courses")

        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            assert isinstance(item["progress_percent"], float)
            assert 0.0 <= item["progress_percent"] <= 100.0

    def test_get_enrolled_courses_returns_correct_progress(self, client):
        response = client.get("/api/student/courses")
        
        assert response.status_code == 200
        items = response.json()["items"]
        
        # In seed.py, student 1 is enrolled in python-fundamentals (free) and advanced-algorithms (paid)
        # free_course has 3 contents, all 3 are completed = 100.0%
        # paid_course has 1 content, 0 completed = 0.0%
        for item in items:
            if item["slug"] == "python-fundamentals":
                assert item["progress_percent"] == 100.0
            elif item["slug"] == "advanced-algorithms":
                assert item["progress_percent"] == 0.0

    def test_get_enrolled_courses_returns_empty_when_no_enrollments(self, unauth_client):
        # Create a new user override that has no enrollments
        def override_get_no_enrollments_user():
            return {"sub": 99999, "email": "empty@gmail.com", "roles": ["STUDENT"]}
            
        from src.app import app
        from src.middlewares.auth_middleware import get_current_user
        from tests.module2.conftest import override_get_async_db_session
        from src.db import get_async_db_session
        
        app.dependency_overrides[get_current_user] = override_get_no_enrollments_user
        app.dependency_overrides[get_async_db_session] = override_get_async_db_session
        
        response = unauth_client.get("/api/student/courses")
        
        assert response.status_code == 200
        assert response.json()["items"] == []
        
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_async_db_session, None)

    def test_get_enrolled_courses_returns_401_without_auth(self, unauth_client):
        response = unauth_client.get("/api/student/courses")

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Endpoint 5 — GET /student/courses/{slug}/study
# ---------------------------------------------------------------------------

class TestGetStudyContent:

    def test_get_study_content_returns_200_for_valid_slug(self, client):
        response = client.get(f"/api/student/courses/{STUDY_SLUG}/study")

        assert response.status_code == 200
        body = response.json()
        assert body["course_slug"] == STUDY_SLUG
        assert "sections" in body
        assert isinstance(body["sections"], list)
        assert len(body["sections"]) > 0

    def test_get_study_content_sections_have_required_fields(self, client):
        response = client.get(f"/api/student/courses/{STUDY_SLUG}/study")

        assert response.status_code == 200
        sections = response.json()["sections"]
        for section in sections:
            for field in ("id", "title", "position", "lessons"):
                assert field in section, f"Section missing field: {field}"

    def test_get_study_content_lessons_have_required_fields(self, client):
        response = client.get(f"/api/student/courses/{STUDY_SLUG}/study")

        assert response.status_code == 200
        sections = response.json()["sections"]
        first_section_lessons = sections[0]["lessons"]
        assert len(first_section_lessons) > 0
        for lesson in first_section_lessons:
            for field in ("id", "title", "position", "locked", "contents"):
                assert field in lesson, f"Lesson missing field: {field}"

    def test_get_study_content_lesson_locked_matches_mock_rule(self, client):
        # Asserts the exact mock values set in course_service.py _MOCK_STUDY_DATA:
        #   Section 0: lesson[0]=locked:False, lesson[1]=locked:False,
        #              lesson[2]=locked:True,  lesson[3]=locked:True
        # Q3 decision: fixed mock values, no sequential business logic.
        response = client.get(f"/api/student/courses/{STUDY_SLUG}/study")

        assert response.status_code == 200
        lessons = response.json()["sections"][0]["lessons"]

        # First lesson must be unlocked (accessible to any enrolled student)
        assert lessons[0]["locked"] is False, "Lesson 0 should be unlocked"
        # Second lesson also unlocked per mock rule
        assert lessons[1]["locked"] is False, "Lesson 1 should be unlocked"
        # Remaining lessons are locked
        assert lessons[2]["locked"] is True,  "Lesson 2 should be locked"
        assert lessons[3]["locked"] is True,  "Lesson 3 should be locked"

    def test_get_study_content_contents_have_required_fields(self, client):
        response = client.get(f"/api/student/courses/{STUDY_SLUG}/study")

        assert response.status_code == 200
        first_lesson = response.json()["sections"][0]["lessons"][0]
        assert len(first_lesson["contents"]) > 0
        for content in first_lesson["contents"]:
            for field in ("id", "content_type", "completed"):
                assert field in content, f"Content missing field: {field}"

    def test_get_study_content_returns_404_for_unknown_slug(self, client):
        response = client.get(f"/api/student/courses/{UNKNOWN_SLUG}/study")

        assert response.status_code == 404
        body = response.json()
        assert "message" in body
        assert "detail" in body
        assert body["code"] == 404

    def test_get_study_content_returns_401_without_auth(self, unauth_client):
        response = unauth_client.get(f"/api/student/courses/{STUDY_SLUG}/study")

        assert response.status_code == 401
