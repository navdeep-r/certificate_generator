"""Persistence operations for Certificate."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.certificate import Certificate, CertificateStatus


class CertificateRepository:
    """All SQL that touches the certificates table lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(self, certificates: list[Certificate]) -> None:
        """Bulk-insert certificate rows in one round-trip."""
        self._session.add_all(certificates)
        await self._session.flush()

    async def get(self, certificate_id: uuid.UUID) -> Optional[Certificate]:
        result = await self._session.execute(
            select(Certificate).where(Certificate.id == certificate_id)
        )
        return result.scalar_one_or_none()

    async def list_by_job(
        self,
        job_id: uuid.UUID,
        *,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Certificate], int]:
        """Return (items, total_count) for a job, with optional status filter."""
        from sqlalchemy import func  # noqa: PLC0415

        conditions = [Certificate.job_id == job_id]
        if status:
            conditions.append(Certificate.status == status)

        count_stmt = select(func.count()).select_from(Certificate).where(and_(*conditions))
        total = (await self._session.execute(count_stmt)).scalar_one()

        rows_stmt = (
            select(Certificate)
            .where(and_(*conditions))
            .order_by(Certificate.sequence_number)
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(rows_stmt)).scalars().all()
        return list(rows), total

    async def claim_for_processing(self, certificate_id: uuid.UUID) -> bool:
        """Atomically transition PENDING → PROCESSING.

        Returns True if the claim succeeded (this worker owns the item).
        Returns False if the item was already claimed or is in a terminal state.
        """
        result = await self._session.execute(
            update(Certificate)
            .where(
                and_(
                    Certificate.id == certificate_id,
                    Certificate.status == CertificateStatus.PENDING,
                )
            )
            .values(
                status=CertificateStatus.PROCESSING,
                processing_started_at=datetime.utcnow(),
                attempt_count=Certificate.attempt_count + 1,
            )
            .returning(Certificate.id)
        )
        return result.scalar_one_or_none() is not None

    async def mark_completed(self, certificate_id: uuid.UUID, file_path: str) -> None:
        await self._session.execute(
            update(Certificate)
            .where(Certificate.id == certificate_id)
            .values(
                status=CertificateStatus.COMPLETED,
                file_path=file_path,
                completed_at=datetime.utcnow(),
                error_code=None,
                error_message=None,
            )
        )

    async def mark_failed(
        self,
        certificate_id: uuid.UUID,
        error_code: str,
        error_message: str,
    ) -> None:
        await self._session.execute(
            update(Certificate)
            .where(Certificate.id == certificate_id)
            .values(
                status=CertificateStatus.FAILED,
                error_code=error_code,
                error_message=error_message,
                completed_at=datetime.utcnow(),
            )
        )

    async def get_pending_ids(self, job_id: uuid.UUID) -> list[uuid.UUID]:
        """Return IDs of PENDING certificates for a job (used by batch dispatcher)."""
        result = await self._session.execute(
            select(Certificate.id)
            .where(
                and_(
                    Certificate.job_id == job_id,
                    Certificate.status == CertificateStatus.PENDING,
                )
            )
            .order_by(Certificate.sequence_number)
        )
        return list(result.scalars().all())
