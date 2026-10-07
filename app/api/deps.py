"""FastAPI dependency providers shared across routes."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session and close it when done."""
    async with async_session_factory() as session:
        yield session
