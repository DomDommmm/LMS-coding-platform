"""
Tests for Module 2 — Endpoint 3: POST /courses/{slug}/enroll (→ 201)
                    Endpoint 9: POST /courses/{slug}/unenroll (→ 200)

Both endpoints require authentication (STUDENT role).

Fixtures used:
  client        — get_current_user overridden → SEED_STUDENT (happy path)
  unauth_client — no override, no Bearer token → 401 (auth guard test)

Mock slug reference (from course_service.py _MOCK_COURSES):
  FREE  slugs → ENROLLED,         checkout_url=None : nhap-mon-lap-trinh-python, co-so-du-lieu-sql
  PAID  slugs → PENDING_PAYMENT,  checkout_url set  : cau-truc-du-lieu-va-giai-thuat, lap-trinh-web-voi-fastapi

ErrorResponse shape (from app.py http_exception_handler):
    {"message": "Cloudian Notification", "code": int, "detail": str,
     "timestamp": str, "path": str}
"""

from __future__ import annotations

import pytest

from tests.module2.conftest import UNKNOWN_SLUG

FREE_SLUG = "python-fundamentals"
PAID_SLUG = "advanced-algorithms"


# ---------------------------------------------------------------------------
# Endpoint 3 — POST /courses/{slug}/enroll
# ---------------------------------------------------------------------------

class TestEnrollCourse:

    def test_enroll_course_checkout_url_is_null_when_enrolled(self, client):
        from src.app import app
        from src.middlewares.auth_middleware import get_current_user
        app.dependency_overrides[get_current_user] = lambda: {"sub": 2, "email": "teacher@gmail.com", "roles": ["student"]}

        # FREE course → status=enrolled, checkout_url must be absent or null
        response = client.post(f"/api/courses/{FREE_SLUG}/enroll")

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "enrolled"
        # checkout_url is Optional — either missing from payload or explicitly null
        assert body.get("checkout_url") is None

        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_current_user] = lambda: {"sub": 1, "email": "student@gmail.com", "roles": ["student"]}

    def test_enroll_course_checkout_url_present_when_pending_payment(self, client):
        from src.app import app
        from src.middlewares.auth_middleware import get_current_user
        app.dependency_overrides[get_current_user] = lambda: {"sub": 2, "email": "teacher@gmail.com", "roles": ["student"]}

        # PAID course → status=pending_payment, checkout_url must be a non-empty string
        response = client.post(f"/api/courses/{PAID_SLUG}/enroll")

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending_payment"
        assert isinstance(body.get("checkout_url"), str)
        
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_current_user] = lambda: {"sub": 1, "email": "student@gmail.com", "roles": ["student"]}
        assert len(body["checkout_url"]) > 0

    def test_enroll_course_returns_400_when_already_enrolled(self, client):
        # By default, client uses get_current_user = {"sub": 1}, which is already enrolled in seed data
        response = client.post(f"/api/courses/{FREE_SLUG}/enroll")

        assert response.status_code == 400
        body = response.json()
        assert body.get("error_code") == "ALREADY_ENROLLED"
        assert "details" in body
        assert any(d["field"] == "course_id" for d in body["details"])

    def test_enroll_course_returns_404_for_unknown_slug(self, client):
        response = client.post(f"/api/courses/{UNKNOWN_SLUG}/enroll")

        assert response.status_code == 404
        body = response.json()
        assert "message" in body
        assert "detail" in body
        assert body["code"] == 404

    def test_enroll_course_returns_401_without_auth(self, unauth_client):
        response = unauth_client.post(f"/api/courses/{FREE_SLUG}/enroll")

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Endpoint 9 — POST /courses/{slug}/unenroll
# ---------------------------------------------------------------------------

class TestUnenrollCourse:
    
    # We use actual seeded course slugs
    FREE_SLUG = "python-fundamentals"
    PAID_SLUG = "advanced-algorithms"
    UNKNOWN_SLUG = "khoa-hoc-khong-ton-tai"

    def test_unenroll_course_returns_200_for_existing_slug(self, client):
        # By default, client uses sub=1 (student) which is enrolled in python-fundamentals
        response = client.post(f"/api/courses/{self.FREE_SLUG}/unenroll")

        assert response.status_code == 200
        body = response.json()
        assert "message" in body
        assert isinstance(body["message"], str)
        assert len(body["message"]) > 0

    def test_unenroll_course_message_contains_course_title(self, client):
        response = client.post(f"/api/courses/{self.FREE_SLUG}/unenroll")

        assert response.status_code == 200
        assert "Successfully unenrolled" in response.json()["message"]
        assert "Python Fundamentals" in response.json()["message"]

    def test_unenroll_course_returns_404_for_unknown_slug(self, client):
        response = client.post(f"/api/courses/{self.UNKNOWN_SLUG}/unenroll")

        assert response.status_code == 404
        body = response.json()
        assert "message" in body
        assert "detail" in body
        assert body["code"] == 404

    def test_unenroll_course_returns_404_if_not_enrolled(self, client):
        from src.app import app
        from src.middlewares.auth_middleware import get_current_user
        
        # Override with teacher (id=2) who is NOT enrolled in the courses
        app.dependency_overrides[get_current_user] = lambda: {"sub": 2, "email": "teacher@gmail.com", "roles": ["student"]}
        
        response = client.post(f"/api/courses/{self.FREE_SLUG}/unenroll")
        
        # We expect a 404 because the enrollment doesn't exist
        assert response.status_code == 404
        assert "Enrollment not found" in response.json()["detail"]
        
        # Restore override
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_current_user] = lambda: {"sub": 1, "email": "student@gmail.com", "roles": ["student"]}

    def test_unenroll_course_returns_401_without_auth(self, unauth_client):
        response = unauth_client.post(f"/api/courses/{self.FREE_SLUG}/unenroll")

        assert response.status_code == 401
