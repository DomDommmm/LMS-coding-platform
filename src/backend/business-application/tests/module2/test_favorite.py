import pytest
from httpx import AsyncClient


class TestCourseFavorite:
    @pytest.fixture(autouse=True)
    async def setup_course_id(self, client: AsyncClient):
        # Fetch first course to get its ID
        res = client.get("/api/courses")
        items = res.json().get("items", [])
        if items:
            self.course_id = items[0]["id"]
        else:
            self.course_id = 1 # Fallback

    def test_add_favorite_returns_200_and_is_favorited(self, client: AsyncClient):
        # Fetch course
        res = client.get("/api/courses")
        course_id = res.json()["items"][0]["id"]

        # Add favorite
        put_res = client.put(f"/api/courses/{course_id}/favorite")
        assert put_res.status_code == 200
        
        data = put_res.json()
        assert data["course_id"] == course_id
        assert data["is_favorited"] is True
        assert "created_at" in data

    def test_add_favorite_idempotent(self, client: AsyncClient):
        res = client.get("/api/courses")
        course_id = res.json()["items"][0]["id"]

        # First add
        res1 = client.put(f"/api/courses/{course_id}/favorite")
        assert res1.status_code == 200
        created_at_1 = res1.json()["created_at"]

        # Second add
        res2 = client.put(f"/api/courses/{course_id}/favorite")
        assert res2.status_code == 200
        assert res2.json()["created_at"] == created_at_1

    def test_remove_favorite_returns_200_and_is_not_favorited(self, client: AsyncClient):
        res = client.get("/api/courses")
        course_id = res.json()["items"][0]["id"]

        # Ensure added first
        client.put(f"/api/courses/{course_id}/favorite")

        # Remove favorite
        del_res = client.delete(f"/api/courses/{course_id}/favorite")
        assert del_res.status_code == 200
        
        data = del_res.json()
        assert data["course_id"] == course_id
        assert data["is_favorited"] is False

    def test_get_favorites_returns_list(self, client: AsyncClient):
        res = client.get("/api/courses")
        course = res.json()["items"][0]
        course_id = course["id"]
        course_slug = course["slug"]

        # Ensure added
        client.put(f"/api/courses/{course_id}/favorite")

        # Get favorites
        fav_res = client.get("/api/favorites")
        assert fav_res.status_code == 200
        
        data = fav_res.json()
        assert data["total_items"] >= 1
        
        items = data["items"]
        assert len(items) >= 1
        
        fav_course = next((item for item in items if item["course_id"] == course_id), None)
        assert fav_course is not None
        assert fav_course["is_favorited"] is True
        assert "course" in fav_course
        assert fav_course["course"]["id"] == course_id
        assert fav_course["course"]["slug"] == course_slug

def test_add_favorite_returns_401_without_auth(unauth_client):
    res = unauth_client.put("/api/courses/1/favorite")
    assert res.status_code == 401

def test_get_favorites_returns_401_without_auth(unauth_client):
    res = unauth_client.get("/api/favorites")
    assert res.status_code == 401
