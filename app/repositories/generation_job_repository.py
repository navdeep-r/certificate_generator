"""Persistence operations for GenerationJob."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation_job import GenerationJob


class GenerationJobRepository:
    """All SQL that touches the generation_jobs table lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, job: GenerationJob) -> GenerationJob:
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, job_id: uuid.UUID) -> Optional[GenerationJob]:
        result = await self._session.execute(
            select(GenerationJob).where(GenerationJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        job_id: uuid.UUID,
        status: str,
        *,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        values: dict = {"status": status}
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        await self._session.execute(
            update(GenerationJob).where(GenerationJob.id == job_id).values(**values)
        )

    async def increment_counters(
        self,
        job_id: uuid.UUID,
        *,
        successful: int = 0,
        failed: int = 0,
    ) -> None:
        """Atomically increment job counters using SQL expressions."""
        from sqlalchemy import func  # noqa: PLC0415

        updates: dict = {}
        if successful:
            updates["successful_count"] = GenerationJob.successful_count + successful
        if failed:
            updates["failed_count"] = GenerationJob.failed_count + failed
        if updates:
            await self._session.execute(
                update(GenerationJob)
                .where(GenerationJob.id == job_id)
                .values(**updates)
            )
