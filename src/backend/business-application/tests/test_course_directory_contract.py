from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import app
from src.middlewares.auth_middleware import get_current_user
from src.modules.course_directory.course_directory_dto import (
    CourseDetailView,
    CourseListResponse,
    CourseFavoriteView,
    CourseView,
    InstructorListResponse,
    ReviewSummary,
    TeacherProfileView,
)
from src.modules.course_directory.course_directory_router import get_service


@pytest.fixture
def service():
    return AsyncMock()


@pytest.fixture(autouse=True)
def overrides(service):
    async def override_service():
        return service

    async def override_user():
        return {"sub": 1, "roles": ["STUDENT"]}

    app.dependency_overrides[get_service] = override_service
    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        yield http_client


def course_view() -> CourseView:
    now = datetime.now(timezone.utc)
    return CourseView(
        id=1,
        teacher_id=2,
        title="Python",
        slug="python",
        rating=4.5,
        field="Programming",
        tags="python,basics",
        description="Course",
        thumbnail_url=None,
        price=Decimal("10.00"),
        price_type="paid",
        status="APPROVED",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_catalog_contract(client, service):
    service.list_courses.return_value = CourseListResponse(
        data=[course_view()], pagination={"page": 1, "size": 20, "total": 1}
    )
    response = await client.get("/api/courses", params={"field": "Programming", "tag": "python"})
    assert response.status_code == 200
    assert response.json()["data"][0]["price"] == "10.00"
    assert response.json()["data"][0]["currency"] == "USD"
    service.list_courses.assert_awaited_once_with(1, 20, None, "Programming", "python", None)


@pytest.mark.asyncio
async def test_anonymous_course_detail_omits_user_state(client, service):
    course = course_view()
    instructor = TeacherProfileView(
        user_id=2,
        full_name="Teacher",
        avatar_url=None,
        headline=None,
        expertise_tags=None,
        years_of_experience=None,
        education_entries=None,
        experience_entries=None,
        github_url=None,
        linkedin_url=None,
        website_url=None,
        email=None,
        phone=None,
        bio=None,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )
    service.get_course.return_value = CourseDetailView(
        **course.model_dump(),
        instructor=instructor,
        sections=[],
        review_summary=ReviewSummary(average_rating=0, total_reviews=0),
    )

    response = await client.get("/api/courses/python")

    assert response.status_code == 200
    assert "is_favorited" not in response.json()["data"]
    assert "is_enrolled" not in response.json()["data"]
    service.get_course.assert_awaited_once_with("python", None)


@pytest.mark.asyncio
async def test_instructor_contract(client, service):
    now = datetime.now(timezone.utc)
    instructor = TeacherProfileView(
        user_id=2,
        full_name="Teacher",
        avatar_url=None,
        headline="Python instructor",
        expertise_tags="Python",
        years_of_experience=5,
        education_entries=None,
        experience_entries=None,
        github_url=None,
        linkedin_url=None,
        website_url=None,
        email=None,
        phone=None,
        bio=None,
        created_at=now,
        updated_at=now,
    )
    service.list_instructors.return_value = InstructorListResponse(
        data=[instructor], pagination={"page": 1, "size": 20, "total": 1}
    )
    response = await client.get("/api/instructors?q=Teacher")
    assert response.status_code == 200
    assert response.json()["data"][0]["user_id"] == 2


@pytest.mark.asyncio
async def test_favorite_mutation_envelope(client, service):
    service.add_favorite.return_value = CourseFavoriteView(
        id=1,
        student_id=1,
        course_id=2,
        created_at=datetime.now(timezone.utc),
        is_favorited=True,
        course=None,
    )
    response = await client.put("/api/courses/2/favorite")
    assert response.status_code == 200
    assert response.json()["data"]["is_favorited"] is True
    assert response.json()["message"]


@pytest.mark.asyncio
async def test_non_student_cannot_mutate_favorite(client):
    async def teacher():
        return {"sub": 2, "roles": ["TEACHER"]}

    app.dependency_overrides[get_current_user] = teacher
    response = await client.put("/api/courses/1/favorite")
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_review_validation(client):
    response = await client.post("/api/courses/1/reviews", json={"rating": 6})
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_only_requested_course_directory_routes_are_registered():
    methods = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    expected = {
        ("GET", "/api/courses"),
        ("GET", "/api/courses/{slug}"),
        ("GET", "/api/instructors"),
        ("GET", "/api/instructors/{user_id}"),
        ("GET", "/api/favorites"),
        ("PUT", "/api/courses/{course_id}/favorite"),
        ("DELETE", "/api/courses/{course_id}/favorite"),
        ("GET", "/api/courses/{course_id}/reviews"),
        ("POST", "/api/courses/{course_id}/reviews"),
        ("PATCH", "/api/courses/{course_id}/reviews/{review_id}"),
    }
    assert expected <= methods
    assert not any(path.startswith("/api/payments") for _, path in methods)
