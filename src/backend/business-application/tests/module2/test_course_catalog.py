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
        assert "pagination" in body
        assert "total" in body["pagination"]
        assert "page" in body["pagination"]
        assert "data" in body
        assert isinstance(body["data"], list)

    def test_get_course_catalog_items_have_required_fields(self, client):
        response = client.get("/api/courses")

        assert response.status_code == 200
        items = response.json()["data"]
        assert len(items) > 0
        first = items[0]
        for field in ("id", "slug", "title", "thumbnail_url", "price",
                      "price_type", "field", "tags", "rating"):
            assert field in first, f"Missing field: {field}"

    def test_get_course_catalog_with_page_and_size_params(self, client):
        response = client.get("/api/courses", params={"page": 1, "size": 5})

        assert response.status_code == 200
        body = response.json()
        assert body["pagination"]["page"] == 1
        assert len(body["data"]) <= 5

    def test_get_course_catalog_filter_by_price_type_free(self, client):
        response = client.get("/api/courses", params={"price_type": "free"})

        assert response.status_code == 200
        items = response.json()["data"]
        for item in items:
            assert item["price_type"] == "free"

    def test_get_course_catalog_filter_by_query_string(self, client):
        response = client.get("/api/courses", params={"q": "Python"})

        assert response.status_code == 200
        items = response.json()["data"]
        assert len(items) > 0
        for item in items:
            assert "python" in item["title"].lower()

    def test_get_course_catalog_unknown_query_returns_empty_items(self, client):
        response = client.get("/api/courses", params={"q": "xyzkhongtontai999"})

        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["pagination"]["total"] == 0


# ---------------------------------------------------------------------------
# Endpoint 2 — GET /courses/{slug}
# ---------------------------------------------------------------------------

class TestGetCourseDetail:

    def test_get_course_detail_returns_200_for_existing_slug(self, client):
        response = client.get("/api/courses/python-fundamentals")

        assert response.status_code == 200
        body = response.json()["data"]
        
        # Assert exact seed data values
        assert body["slug"] == "python-fundamentals"
        assert body["title"] == "Python Fundamentals"
        assert body["description"] == "A practical starter course for new Python learners."
        assert body["price"] == "0.00"
        assert body["price_type"] == "free"
        assert body["field"] == "Programming"
        assert [tag.strip() for tag in body["tags"].split(",")] == ["python", "basics"]
        
        # Rating depends on seed data but remains a numeric projection.
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
        body = response.json()["data"]
        for field in ("id", "slug", "title", "description", "price",
                      "price_type", "field", "tags", "rating", "sections"):
            assert field in body, f"Missing field: {field}"

    def test_get_course_detail_sections_have_required_fields(self, client):
        response = client.get("/api/courses/python-fundamentals")

        assert response.status_code == 200
        sections = response.json()["data"]["sections"]
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
        assert "details" in body
        assert body["error_code"] == "NOT_FOUND"
