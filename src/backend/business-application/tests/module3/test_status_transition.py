import pytest
from src.models.course_model import CourseStatus
from src.models.course_model import CourseModel

async def test_teacher_course_status_transition_allows_edit_on_draft(client):
    """
    Teacher creates a course (status DRAFT).
    Can edit -> 200 OK
    """
    create_response = await client.post(
        "/api/teacher/courses",
        json={
            "title": "Draft Course",
            "field": "IT",
            "tags": ["python"],
            "description": "Test",
            "thumbnail_url": "http://img",
            "price": 100
        }
    )
    assert create_response.status_code == 201
    course_id = create_response.json()["id"]

    # Edit Draft
    put_response = await client.put(
        f"/api/teacher/courses/{course_id}",
        json={"title": "Draft Course Edited"}
    )
    assert put_response.status_code == 200
    assert put_response.json()["title"] == "Draft Course Edited"


async def test_teacher_course_status_transition_blocks_edit_on_pending(client):
    """
    Teacher has a course in PENDING_REVIEW state.
    Cannot edit -> 404 (because query filters by DRAFT/REJECTED)
    """
    create_response = await client.post(
        "/api/teacher/courses",
        json={
            "title": "Pending Course",
            "field": "IT",
            "tags": ["python"],
            "description": "Test",
            "thumbnail_url": "http://img",
            "price": 100
        }
    )
    assert create_response.status_code == 201
    course_id = create_response.json()["id"]

    # Submit for review (changes to PENDING_REVIEW)
    submit_response = await client.post(f"/api/teacher/courses/{course_id}/submit-review")
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == "PENDING_REVIEW"

    # Try to edit
    put_response = await client.put(
        f"/api/teacher/courses/{course_id}",
        json={"title": "Hacked Title"}
    )
    
    # Depending on implementation, it might be 404 or 409. 
    # update_course returns 409 INVALID_STATE
    assert put_response.status_code == 409
