def test_list_instructors_returns_only_approved_profiles(client):
    response = client.get("/api/instructors")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    assert all(item["user_id"] != 1 for item in body["data"])


def test_list_instructors_supports_search_and_field(client):
    response = client.get(
        "/api/instructors", params={"q": "Cloudian Teacher", "field": "Python"}
    )
    assert response.status_code == 200
    assert response.json()["data"]


def test_instructor_detail_contains_public_courses(client):
    instructor_id = client.get("/api/instructors").json()["data"][0]["user_id"]
    response = client.get(f"/api/instructors/{instructor_id}")
    assert response.status_code == 200
    assert all(course["status"] == "APPROVED" for course in response.json()["data"]["courses"])


def test_pending_application_is_not_public_instructor(client):
    response = client.get("/api/instructors/1")
    assert response.status_code == 404
