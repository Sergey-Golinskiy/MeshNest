"""Pytest fixtures.

Тесты ходят в реальный PostgreSQL (env: ``TEST_DATABASE_URL``).
В CI — через ``postgres`` service container.
Локально — поднять ``docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml up -d postgres``
и выставить ``TEST_DATABASE_URL=postgresql+asyncpg://meshnest:meshnest@localhost:5432/meshnest_test``
(плюс синхронный URL ``TEST_DATABASE_URL_SYNC`` для alembic).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# --- Override settings BEFORE importing app ---
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://meshnest:meshnest@localhost:5432/meshnest_test",
    ),
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    os.getenv(
        "TEST_DATABASE_URL_SYNC",
        "postgresql+psycopg2://meshnest:meshnest@localhost:5432/meshnest_test",
    ),
)
os.environ.setdefault("JWT_SECRET", "test-secret-only-do-not-use-in-prod-32bytes")
os.environ.setdefault("MESHNEST_STORAGE_DRIVER", "local")
os.environ.setdefault("MESHNEST_LOCAL_STORAGE_ROOT", "/tmp/meshnest-test-storage")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MEILISEARCH_URL", "http://localhost:7700")
os.environ.setdefault("MEILISEARCH_MASTER_KEY", "test-meili-key")

from app.config import settings  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    Session = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with Session() as s:
        yield s
        # Cleanup: TRUNCATE all tables (быстрее чем drop/create)
        await s.execute(text(
            "TRUNCATE TABLE refresh_tokens, model_tags, files, models, "
            "import_jobs, tags, categories, invites, users RESTART IDENTITY CASCADE"
        ))
        await s.commit()


@pytest_asyncio.fixture
async def client(session) -> AsyncIterator[AsyncClient]:
    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(session):
    from app.auth.passwords import hash_password
    from app.models import User
    from app.models._types import UserRole

    user = User(
        id=uuid.uuid4(),
        email="admin@test.local",
        password_hash=hash_password("test-password-123"),
        role=UserRole.admin,
        display_name="Admin",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user


@pytest_asyncio.fixture
async def admin_token(client, admin_user):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "test-password-123"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
