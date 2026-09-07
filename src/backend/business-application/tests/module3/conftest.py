"""
Shared pytest fixtures for Module 3: Instructor Course Management.

Seed account used across all Module 3 tests:
  email:    teacher@gmail.com
  password: teacher123  (not needed — only the decoded JWT payload matters)
  role:     TEACHER
  user_id:  2  (int, already cast by auth_middleware.py line 36)
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://lms:lms@localhost:5432/lms")
os.environ.setdefault("VERIFY_REGISTER_SECRET", "test-secret")
os.environ.setdefault("AUTH_PROVIDER_URL", "http://localhost:4001")
os.environ.setdefault("UPSTASH_REDIS_REST_URL", "http://localhost")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "test-token")

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from src.app import app
from src.middlewares.auth_middleware import get_current_user
from src.grpc.client import AuthGrpcClient
from src.jwk_service import PublicKeyService
from src.services.rabbitmq.rabbitmq_manager import RabbitMQManager

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_TEACHER = {
    "sub": 2,
    "email": "teacher@gmail.com",
    "roles": ["TEACHER"],
}

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
        await self.flush()

test_session_maker = async_sessionmaker(test_engine, class_=RollbackSession, expire_on_commit=False)

@pytest.fixture(scope="function")
async def test_db_session():
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        
        async with test_session_maker(bind=conn) as session:
            try:
                from src.models.teacher_profile_model import TeacherProfileModel
                from sqlalchemy import select
                existing = await session.scalar(select(TeacherProfileModel).where(TeacherProfileModel.user_id == 2))
                if not existing:
                    profile = TeacherProfileModel(user_id=2)
                    session.add(profile)
                    await session.flush()
                yield session
            finally:
                await trans.rollback()

@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    monkeypatch.setattr("src.app.AuthGrpcClient.close", AsyncMock())
    monkeypatch.setattr("src.app.PublicKeyService.load", AsyncMock())
    monkeypatch.setattr("src.app.RabbitMQManager.connect", AsyncMock())
    monkeypatch.setattr("src.app.RabbitMQManager.consume", AsyncMock())
    monkeypatch.setattr("src.app.RabbitMQManager.close", AsyncMock())
    
    # Mock MinioHandler to avoid real S3 operations failing due to missing buckets in test environment
    from unittest.mock import MagicMock
    mock_minio = MagicMock()
    mock_minio.put_object.return_value = {
        'bucket_name': 'lms',
        'file_name': 'mocked_file_name.txt',
        'url': 'http://localhost:9000/lms/mocked_file_name.txt'
    }
    monkeypatch.setattr("src.services.minio.minio_handler.MinioHandler.put_object", mock_minio.put_object)
    
    yield

from httpx import AsyncClient, ASGITransport

@pytest.fixture()
async def client(test_db_session):
    def override_get_current_user():
        return SEED_TEACHER

    async def override_get_async_db_session():
        yield test_db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_async_db_session] = override_get_async_db_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
        
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_async_db_session, None)


@pytest.fixture()
def unauth_client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
