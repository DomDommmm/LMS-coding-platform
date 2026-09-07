import pytest
import io

async def test_teacher_problem_testcase_upload_uses_minio(client):
    """
    Test that uploading testcase files uses MinIO and inserts into TestcaseModel properly.
    """
    # 1. Create a Problem
    res = await client.post(
        "/api/teacher/problems",
        json={
            "title": "A Problem",
            "slug": "a-problem",
            "statement": "Solve it",
            "input_description": "None",
            "output_description": "None",
            "constraints": "None",
            "sample_input": "1",
            "sample_output": "1",
            "explanation": "None",
            "difficulty": "EASY",
            "passing_score": 100,
            "public": True,
            "tag_ids": [],
            "configs": []
        }
    )
    assert res.status_code == 201, res.text
    problem_id = res.json()["id"]

    # 2. Upload testcase
    # Must use multipart/form-data with files and form fields
    params = {
        "score": "10",
        "is_hidden": "true"
    }
    
    files = {
        "input": ("inp01.txt", io.BytesIO(b"input data"), "text/plain"),
        "output": ("out01.txt", io.BytesIO(b"output data"), "text/plain")
    }

    res = await client.post(
        f"/api/teacher/problems/{problem_id}/testcases/upload",
        params=params,
        files=files
    )
    
    assert res.status_code == 201, res.text
    # The response should return the updated testcases list (authorized TestcaseView)
    # Check that the testcase was created with the mock bucket name
    data = res.json()
    testcases = data["testcases"]
    assert len(testcases) > 0
    
    testcase = testcases[-1]
    assert testcase["score"] == 10
    assert testcase["is_hidden"] is True
    
    # Assert Minio response properties based on mock
    assert testcase["input_file"] == "mocked_file_name.txt"
    assert testcase["output_file"] == "mocked_file_name.txt"
