"""CertificateService — per-certificate processing pipeline.

Responsibilities:
    1. Claim a PENDING certificate (idempotency guard).
    2. Build CertificateData from DB row + job context.
    3. Call the PDF generator.
    4. Save the PDF via StorageService.
    5. Mark the certificate COMPLETED or FAILED.
    6. Update job counters.

No HTTP, no Celery task details.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.certificate.generator import CertificateData, CertificateGenerationError, generate_certificate_pdf
from app.core.exceptions import StorageError
from app.core.logging import get_logger
from app.models.generation_job import GenerationJob
from app.repositories.certificate_repository import CertificateRepository
from app.repositories.generation_job_repository import GenerationJobRepository
from app.services.storage_service import StorageService

logger = get_logger(__name__)

EC_GENERATION_FAILED = "CERTIFICATE_GENERATION_FAILED"
EC_STORAGE_ERROR = "STORAGE_ERROR"


class CertificateService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageService | None = None,
    ) -> None:
        self._session = session
        self._cert_repo = CertificateRepository(session)
        self._job_repo = GenerationJobRepository(session)
        self._storage = storage or StorageService()

    async def process_certificate(
        self,
        job: GenerationJob,
        certificate_id: uuid.UUID,
    ) -> None:
        """Attempt to process a single certificate.

        Idempotent: if the certificate is already COMPLETED or FAILED it is skipped.
        If another worker already claimed it (PROCESSING), we also skip.
        """
        start = datetime.utcnow()

        # ── Claim ─────────────────────────────────────────────────────────────
        claimed = await self._cert_repo.claim_for_processing(certificate_id)
        if not claimed:
            logger.info(
                "certificate_already_claimed | cert_id=%s | job_id=%s",
                certificate_id, job.id,
            )
            return

        cert = await self._cert_repo.get(certificate_id)
        if cert is None:
            logger.error("certificate_not_found | cert_id=%s", certificate_id)
            return

        logger.info(
            "certificate_started | cert_id=%s | job_id=%s | seq=%d",
            certificate_id, job.id, cert.sequence_number,
        )

        # ── Generate ──────────────────────────────────────────────────────────
        try:
            pdf_data = generate_certificate_pdf(
                CertificateData(
                    recipient_name=cert.recipient_name,
                    certificate_title=job.certificate_title,
                    event_name=job.event_name,
                    issuer_name=job.issuer_name,
                    issue_date=job.issue_date,
                )
            )
        except CertificateGenerationError as exc:
            await self._record_failure(
                certificate_id, job.id, EC_GENERATION_FAILED,
                "Certificate PDF could not be generated.",
            )
            return

        # ── Store ─────────────────────────────────────────────────────────────
        try:
            file_path = self._storage.save(job.id, certificate_id, pdf_data)
        except StorageError as exc:
            await self._record_failure(
                certificate_id, job.id, EC_STORAGE_ERROR,
                "Certificate file could not be stored.",
            )
            return

        # ── Complete ──────────────────────────────────────────────────────────
        await self._cert_repo.mark_completed(certificate_id, file_path)
        await self._job_repo.increment_counters(job.id, successful=1)
        await self._session.commit()

        duration = (datetime.utcnow() - start).total_seconds()
        logger.info(
            "certificate_completed | cert_id=%s | job_id=%s | duration_s=%.2f",
            certificate_id, job.id, duration,
        )

    async def _record_failure(
        self,
        certificate_id: uuid.UUID,
        job_id: uuid.UUID,
        error_code: str,
        error_message: str,
    ) -> None:
        await self._cert_repo.mark_failed(certificate_id, error_code, error_message)
        await self._job_repo.increment_counters(job_id, failed=1)
        await self._session.commit()
        logger.warning(
            "certificate_failed | cert_id=%s | job_id=%s | code=%s",
            certificate_id, job_id, error_code,
        )
