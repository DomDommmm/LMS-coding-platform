import pytest

async def test_teacher_basic_crud_happy_paths(client):
    """
    Test basic CRUD happy paths for sections, lessons, and content.
    """
    # 1. Create Course
    res = await client.post(
        "/api/teacher/courses",
        json={"title": "CRUD Test", "field": "IT", "tags": [], "description": "", "thumbnail_url": "", "price": 0}
    )
    assert res.status_code == 201
    course_id = res.json()["id"]

    # 2. Create Section
    res = await client.post(f"/api/teacher/courses/{course_id}/sections", json={"title": "S1"})
    assert res.status_code == 201
    section_id = res.json()["id"]
    
    # 3. Create Lesson
    res = await client.post(
        f"/api/teacher/sections/{section_id}/lessons", 
        json={"title": "L1", "summary": "Sum", "score": 100}
    )
    assert res.status_code == 201
    lesson_id = res.json()["id"]

    # 4. Create Reading Content
    res = await client.post(
        f"/api/teacher/lessons/{lesson_id}/readings",
        json={"title": "Read", "content": "Text"}
    )
    assert res.status_code == 201
    content_id = res.json()["lesson_content"]["id"]

    # 5. Delete Reading Content
    res = await client.delete(f"/api/teacher/lesson-contents/{content_id}")
    assert res.status_code == 200

    # 6. Delete Lesson
    res = await client.delete(f"/api/teacher/lessons/{lesson_id}")
    assert res.status_code == 200

    # 7. Delete Section
    res = await client.delete(f"/api/teacher/sections/{section_id}")
    assert res.status_code == 200
