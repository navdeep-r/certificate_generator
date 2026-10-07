"""Shared pytest fixtures.

Integration tests that hit the FastAPI app use:
    - async_client: an httpx.AsyncClient backed by the FastAPI test app
    - db_session: an AsyncSession for direct DB assertions

The integration tests require a real PostgreSQL + Redis.
Unit tests (test_generator, test_validation) have no external dependencies.

To run only unit tests (no DB required):
    pytest tests/unit/
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Event-loop policy for Windows + asyncio
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# Integration DB setup (requires DATABASE_URL env var pointing at a test DB)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql+asyncpg://certuser:certpass@localhost:5432/certdb"),
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    from app.api.deps import get_db

    # Override get_db with a session that does NOT hit a real DB by default.
    # Integration tests that need a real DB should override this fixture.
    async def _override_get_db():
        # For unit-style API tests: caller must override if DB is needed
        from unittest.mock import AsyncMock
        mock_session = AsyncMock()
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Celery test mode
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=False)
def celery_eager(monkeypatch):
    """Force Celery tasks to execute synchronously in tests."""
    from app.worker.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
