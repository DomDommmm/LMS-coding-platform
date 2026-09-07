import pytest
from httpx import AsyncClient

class TestCourseReview:
    @pytest.fixture(autouse=True)
    async def setup_course_ids(self, client: AsyncClient):
        # In seed data, student_id=1 is enrolled in course 1 (free) and course 2 (paid).
        # They have already reviewed course 1. They have not reviewed course 2.
        self.reviewed_course_id = 1
        self.unreviewed_course_id = 2

    def test_add_review_returns_200_and_creates_review(self, client: AsyncClient):
        # Use course 2, which student is enrolled in but hasn't reviewed yet.
        res = client.post(f"/api/courses/{self.unreviewed_course_id}/reviews", json={"rating": 5, "content": "Great course!"})
        assert res.status_code == 200
        data = res.json()
        assert data["course_id"] == self.unreviewed_course_id
        assert data["student_id"] == 1
        assert data["rating"] == 5
        assert data["content"] == "Great course!"
        assert "id" in data
        
    def test_add_review_returns_409_if_already_reviewed(self, client: AsyncClient):
        # Use course 1, which student has already reviewed in seed data.
        res = client.post(f"/api/courses/{self.reviewed_course_id}/reviews", json={"rating": 3})
        assert res.status_code == 409
        assert "DUPLICATE_RESOURCE" in res.json()["detail"]
        
    def test_patch_review_returns_200_and_updates(self, client: AsyncClient):
        # First, fetch the existing review for course 1 to get its ID
        res_get = client.get(f"/api/courses/{self.reviewed_course_id}/reviews")
        review_id = res_get.json()["items"][0]["id"]
        
        # Patch the review
        res = client.patch(f"/api/courses/{self.reviewed_course_id}/reviews/{review_id}", json={"rating": 4, "content": "Updated review content"})
        assert res.status_code == 200
        data = res.json()
        assert data["rating"] == 4
        assert data["content"] == "Updated review content"
        
    def test_get_reviews_returns_200_with_summary(self, client: AsyncClient):
        # Use course 1 which already has a review in seed data
        res = client.get(f"/api/courses/{self.reviewed_course_id}/reviews")
        assert res.status_code == 200
        data = res.json()
        
        assert "summary" in data
        # In seed data, the rating is 5.
        assert data["summary"]["average_rating"] == 5.0
        assert data["summary"]["total_reviews"] >= 1
        assert "5" in data["summary"]["rating_distribution"]
        
        assert len(data["items"]) >= 1


def test_add_review_returns_401_without_auth(unauth_client):
    res = unauth_client.post("/api/courses/1/reviews", json={"rating": 5})
    assert res.status_code == 401


def test_patch_review_returns_401_without_auth(unauth_client):
    res = unauth_client.patch("/api/courses/1/reviews/1", json={"rating": 5})
    assert res.status_code == 401
