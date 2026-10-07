"""Async SQLAlchemy engine and session factory."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


def _build_engine():  # type: ignore[return]
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


# Module-level engine created once; tests may patch get_settings()
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def async_session_factory() -> AsyncSession:  # type: ignore[return]
    """Return a new async session context manager."""
    factory = async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return factory()
