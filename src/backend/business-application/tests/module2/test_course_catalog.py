"""
Tests for Module 2 — Endpoint 1: GET /courses, Endpoint 2: GET /courses/{slug}.

Both endpoints are public (no auth required).
Using the shared `client` fixture (which has get_current_user overridden) is fine
here because auth override does not affect routes that never call get_current_user.

ErrorResponse shape (from app.py http_exception_handler):
    {"message": "Cloudian Notification", "code": int, "detail": str,
     "timestamp": str, "path": str}
"""

from __future__ import annotations

import pytest

from tests.module2.conftest import UNKNOWN_SLUG


# ---------------------------------------------------------------------------
# Endpoint 1 — GET /courses
# ---------------------------------------------------------------------------

class TestGetCourseCatalog:

    def test_get_course_catalog_returns_200_with_pagination_fields(self, client):
        response = client.get("/api/courses")

        assert response.status_code == 200
        body = response.json()
        assert "total_items" in body
        assert "total_pages" in body
        assert "current_page" in body
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_get_course_catalog_items_have_required_fields(self, client):
        response = client.get("/api/courses")

        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) > 0
        first = items[0]
        for field in ("id", "slug", "title", "thumbnail_url", "price",
                      "price_type", "field", "tags", "enrolled_count", "rating"):
            assert field in first, f"Missing field: {field}"

    def test_get_course_catalog_with_page_and_size_params(self, client):
        response = client.get("/api/courses", params={"page": 1, "size": 5})

        assert response.status_code == 200
        body = response.json()
        assert body["current_page"] == 1
        assert len(body["items"]) <= 5

    def test_get_course_catalog_filter_by_price_type_free(self, client):
        response = client.get("/api/courses", params={"price_type": "free"})

        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            assert item["price_type"] == "free"

    def test_get_course_catalog_filter_by_query_string(self, client):
        response = client.get("/api/courses", params={"q": "Python"})

        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) > 0
        for item in items:
            assert "python" in item["title"].lower()

    def test_get_course_catalog_unknown_query_returns_empty_items(self, client):
        response = client.get("/api/courses", params={"q": "xyzkhongtontai999"})

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total_items"] == 0


# ---------------------------------------------------------------------------
# Endpoint 2 — GET /courses/{slug}
# ---------------------------------------------------------------------------

class TestGetCourseDetail:

    def test_get_course_detail_returns_200_for_existing_slug(self, client):
        response = client.get("/api/courses/python-fundamentals")

        assert response.status_code == 200
        body = response.json()
        
        # Assert exact seed data values
        assert body["slug"] == "python-fundamentals"
        assert body["title"] == "Python Fundamentals"
        assert body["description"] == "A practical starter course for new Python learners."
        assert body["price"] == 0.0
        assert body["price_type"] == "free"
        assert body["field"] == "Programming"
        assert body["tags"] == ["python", "basics"]
        
        # We don't assert exact enrolled_count and rating because they depend on seed dynamically,
        # but we check their types.
        assert isinstance(body["enrolled_count"], int)
        assert isinstance(body["rating"], float)

        assert "sections" in body
        sections = body["sections"]
        assert isinstance(sections, list)
        assert len(sections) == 2
        
        # Section 0: Getting Started (has 2 lessons: Welcome, Quiz)
        assert sections[0]["title"] == "Getting Started"
        assert sections[0]["position"] == 0
        assert sections[0]["lesson_count"] == 2
        
        # Section 1: Practice (has 1 lesson: Two Sum)
        assert sections[1]["title"] == "Practice"
        assert sections[1]["position"] == 1
        assert sections[1]["lesson_count"] == 1

    def test_get_course_detail_response_has_all_required_fields(self, client):
        response = client.get("/api/courses/python-fundamentals")

        assert response.status_code == 200
        body = response.json()
        for field in ("id", "slug", "title", "description", "price",
                      "price_type", "field", "tags", "enrolled_count",
                      "rating", "sections"):
            assert field in body, f"Missing field: {field}"

    def test_get_course_detail_sections_have_required_fields(self, client):
        response = client.get("/api/courses/python-fundamentals")

        assert response.status_code == 200
        sections = response.json()["sections"]
        assert len(sections) > 0
        for section in sections:
            for field in ("id", "title", "position", "lesson_count"):
                assert field in section, f"Section missing field: {field}"

    def test_get_course_detail_returns_404_for_unknown_slug(self, client):
        response = client.get(f"/api/courses/{UNKNOWN_SLUG}")

        assert response.status_code == 404
        body = response.json()
        # ErrorResponse format from app.py http_exception_handler
        assert "message" in body
        assert "detail" in body
        assert body["code"] == 404
