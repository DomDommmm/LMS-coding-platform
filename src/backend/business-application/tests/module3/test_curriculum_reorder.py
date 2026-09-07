import pytest
from src.modules.teacher.teacher_curriculum.teacher_curriculum_dto import CurriculumItemType

async def test_teacher_curriculum_reorder(client):
    """
    Test reordering sections and lessons.
    Create a course -> 2 sections -> each has 1 lesson.
    Then reorder the sections.
    """
    # 1. Create Course
    res = await client.post(
        "/api/teacher/courses",
        json={"title": "Reorder Test", "field": "IT", "tags": [], "description": "", "thumbnail_url": "", "price": 0}
    )
    course_id = res.json()["id"]

    # 2. Create Section 1 (pos 0)
    res = await client.post(f"/api/teacher/courses/{course_id}/sections", json={"title": "S1"})
    s1_id = res.json()["id"]

    # 3. Create Section 2 (pos 1)
    res = await client.post(f"/api/teacher/courses/{course_id}/sections", json={"title": "S2"})
    s2_id = res.json()["id"]

    # 4. Reorder: Swap S1 and S2 positions
    res = await client.put(
        f"/api/teacher/courses/{course_id}/curriculum/reorder",
        json={
            "items": [
                {
                    "item_type": CurriculumItemType.SECTION.value,
                    "id": s1_id,
                    "parent_id": None,
                    "position": 1
                },
                {
                    "item_type": CurriculumItemType.SECTION.value,
                    "id": s2_id,
                    "parent_id": None,
                    "position": 0
                }
            ]
        }
    )
    
    assert res.status_code == 200, res.text
    data = res.json()
    sections = data["sections"]
    
    # Assert they are sorted by position in the response
    assert len(sections) == 2
    assert sections[0]["id"] == s2_id
    assert sections[0]["position"] == 0
    assert sections[1]["id"] == s1_id
    assert sections[1]["position"] == 1
