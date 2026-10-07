"""GenerationService — use-case orchestrator for job creation.

Responsibilities:
    1. Validate the request-level constraints (max recipients).
    2. Run per-recipient validation.
    3. Create the GenerationJob row.
    4. Bulk-insert Certificate rows (valid → PENDING, invalid → FAILED).
    5. Commit the transaction.
    6. Dispatch background processing via Celery.
    7. Return the new job.

No PDF drawing. No HTTP details. No Celery internals.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import RequestTooLargeError
from app.core.logging import get_logger
from app.models.certificate import Certificate, CertificateStatus
from app.models.generation_job import GenerationJob, JobStatus
from app.repositories.certificate_repository import CertificateRepository
from app.repositories.generation_job_repository import GenerationJobRepository
from app.schemas.generation_job import CreateGenerationJobRequest
from app.services.validation_service import (
    FailedRecipient,
    ValidatedRecipient,
    validate_recipients,
)

logger = get_logger(__name__)


class GenerationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._job_repo = GenerationJobRepository(session)
        self._cert_repo = CertificateRepository(session)
        self._settings = get_settings()

    async def create_job(self, request: CreateGenerationJobRequest) -> GenerationJob:
        """Validate, persist, and enqueue a new generation job.

        Returns the created GenerationJob (before background processing begins).
        Raises RequestTooLargeError if recipient count exceeds the configured limit.
        """
        # ── Request-level limit ───────────────────────────────────────────────
        if len(request.recipients) > self._settings.max_recipients_per_job:
            raise RequestTooLargeError(
                f"Request contains {len(request.recipients)} recipients; "
                f"maximum is {self._settings.max_recipients_per_job}."
            )

        # ── Validate each recipient independently ─────────────────────────────
        valid_recipients, failed_recipients = validate_recipients(request.recipients)
        total = len(request.recipients)

        # ── Create job ────────────────────────────────────────────────────────
        job = GenerationJob(
            id=uuid.uuid4(),
            status=JobStatus.QUEUED,
            certificate_title=request.certificate.title,
            event_name=request.certificate.event_name,
            issuer_name=request.certificate.issuer_name,
            issue_date=request.certificate.issue_date,
            total_count=total,
            successful_count=0,
            failed_count=len(failed_recipients),
            created_at=datetime.utcnow(),
        )
        await self._job_repo.create(job)

        # ── Bulk-insert certificates ──────────────────────────────────────────
        cert_rows = _build_certificate_rows(job.id, valid_recipients, failed_recipients)
        await self._cert_repo.bulk_create(cert_rows)

        await self._session.commit()

        logger.info(
            "job_created | job_id=%s | total=%d | valid=%d | pre_failed=%d",
            job.id, total, len(valid_recipients), len(failed_recipients),
        )

        # ── Dispatch background work (import here to avoid circular import) ───
        if valid_recipients:
            _dispatch_job(str(job.id), self._settings.batch_size)
            logger.info("job_dispatched | job_id=%s", job.id)

        # If there are zero valid recipients the job is already terminal
        if not valid_recipients:
            await self._job_repo.update_status(
                job.id,
                JobStatus.COMPLETED_WITH_ERRORS,
                completed_at=datetime.utcnow(),
            )
            await self._session.commit()

        return job


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_certificate_rows(
    job_id: uuid.UUID,
    valid: list[ValidatedRecipient],
    failed: list[FailedRecipient],
) -> list[Certificate]:
    rows: list[Certificate] = []

    for v in valid:
        rows.append(
            Certificate(
                id=uuid.uuid4(),
                job_id=job_id,
                sequence_number=v.sequence_number,
                recipient_name=v.name,
                recipient_email=v.email,
                status=CertificateStatus.PENDING,
                attempt_count=0,
                created_at=datetime.utcnow(),
            )
        )

    for f in failed:
        rows.append(
            Certificate(
                id=uuid.uuid4(),
                job_id=job_id,
                sequence_number=f.sequence_number,
                recipient_name=f.name or "(invalid)",
                recipient_email=f.email,
                status=CertificateStatus.FAILED,
                error_code=f.error_code,
                error_message=f.error_message,
                attempt_count=0,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
        )

    return rows


def _dispatch_job(job_id: str, batch_size: int) -> None:
    """Import and call the Celery task.

    Late import prevents a circular dependency between services and worker.
    """
    from app.worker.tasks import dispatch_job_batches  # noqa: PLC0415
    dispatch_job_batches.delay(job_id, batch_size)
