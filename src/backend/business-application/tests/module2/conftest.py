"""
Shared pytest fixtures for Module 2: Student Course Directory & Study Mode.

WHY PYTEST (not unittest.IsolatedAsyncioTestCase):
  The existing test_lesson_comment_service.py uses unittest style because it
  tests the service layer directly with mocked AsyncSession — no HTTP involved.
  Module 2 tests hit the full HTTP stack (router → dependency → service) via
  TestClient, which integrates more naturally with pytest fixtures and
  dependency_overrides. Mixing styles is intentional: each module uses the
  approach that best fits its test boundary.

Seed account used across all Module 2 tests:
  email:    student@gmail.com
  password: student123  (not needed — only the decoded JWT payload matters)
  role:     STUDENT
  user_id:  1  (int, already cast by auth_middleware.py line 36)

Auth strategy: override get_current_user with a function returning SEED_STUDENT,
bypassing gRPC / JWT verification entirely in tests.

Leak prevention: dependency_overrides is populated at fixture setup and
removed in teardown (yield). This ensures Module 2 overrides never bleed into
tests/test_lesson_comment_service.py when `pytest` or `python -m unittest`
runs the full test suite in the same process.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

# Load .env FIRST so local machines can override DATABASE_URL (e.g. to use
# port 5433 on machines where native Postgres conflicts with Docker on 5432).
# python-dotenv's load_dotenv does NOT overwrite existing shell env vars, so
# CI/CD environments that set DATABASE_URL explicitly are still respected.
load_dotenv()

# Fallback values for any var not set by shell or .env — must use team-standard
# port 5432 here so this shared file does not break others' environments.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://lms:lms@localhost:5432/lms")
os.environ.setdefault("VERIFY_REGISTER_SECRET", "test-secret")
os.environ.setdefault("AUTH_PROVIDER_URL", "http://localhost:4001")
os.environ.setdefault("UPSTASH_REDIS_REST_URL", "http://localhost")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "test-token")

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.middlewares.auth_middleware import get_current_user

# ---------------------------------------------------------------------------
# Seed data — must mirror the payload shape returned by get_current_user:
#   {"sub": int, "email": str, "roles": list[str]}
# "sub" is an int because auth_middleware.py casts it: user_id = int(sub).
# ---------------------------------------------------------------------------

SEED_STUDENT = {
    "sub": 1,
    "email": "student@gmail.com",
    "roles": ["STUDENT"],
}

# Convenience constants used in test assertions
UNKNOWN_SLUG = "khoa-hoc-khong-ton-tai-xyz"
UNKNOWN_ID = 99999


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.db import get_async_db_session

test_engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
from sqlalchemy.ext.asyncio import AsyncSession

class RollbackSession(AsyncSession):
    async def commit(self):
        # Intercept commit to only flush, ensuring test data is never committed to DB
        await self.flush()

test_session_maker = async_sessionmaker(test_engine, class_=RollbackSession, expire_on_commit=False)

async def override_get_async_db_session():
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        
        async with test_session_maker(bind=conn) as session:
            try:
                yield session
            finally:
                await trans.rollback()

@pytest.fixture()
def client():
    """
    TestClient with get_current_user overridden to return SEED_STUDENT.
    Also overrides get_async_db_session to use NullPool, preventing InterfaceError 
    caused by connection pool sharing across multiple TestClient event loops.
    """
    def override_get_current_user():
        return SEED_STUDENT

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_async_db_session] = override_get_async_db_session
    with TestClient(app) as test_client:
        yield test_client
    # Teardown: remove exactly this override; other keys in the dict are untouched.
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_async_db_session, None)


@pytest.fixture()
def unauth_client():
    """
    TestClient with NO dependency override.

    get_current_user runs normally — no valid Bearer token → 401.
    Use this fixture to assert that auth-required endpoints reject unauthenticated requests.
    """
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
