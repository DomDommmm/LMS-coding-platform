import pytest

async def test_teacher_cannot_modify_other_teachers_course(client):
    """
    Teacher 2 creates a course.
    Then we switch auth to Teacher 3 and try to modify it.
    Expected: 404 Not Found (or 403)
    """
    # 1. Teacher 2 creates a course
    create_response = await client.post(
        "/api/teacher/courses",
        json={
            "title": "Course by Teacher 2",
            "field": "IT",
            "tags": ["python"],
            "description": "Test description",
            "thumbnail_url": "http://example.com/img.png",
            "price": 100
        }
    )
    assert create_response.status_code == 201, f"Failed to create course: {create_response.text}"
    course_id = create_response.json()["id"]

    # 2. Switch auth to Teacher 3
    from src.app import app
    from src.middlewares.auth_middleware import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"sub": 3, "email": "teacher3@gmail.com", "roles": ["TEACHER"]}

    # 3. Teacher 3 tries to modify Teacher 2's course
    try:
        put_response = await client.put(
            f"/api/teacher/courses/{course_id}",
            json={"title": "Hacked Title"}
        )
        assert put_response.status_code == 403, f"Expected 403, got {put_response.status_code}: {put_response.text}"
    finally:
        # Restore auth back to Teacher 2
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_current_user] = lambda: {"sub": 2, "email": "teacher@gmail.com", "roles": ["TEACHER"]}
