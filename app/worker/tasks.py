"""Celery tasks — thin orchestration wrappers.

Tasks do NOT contain business logic.
They call services and handle task-level retry/error decisions.

Task graph:
    dispatch_job_batches(job_id, batch_size)
        └── process_certificate_batch(job_id, [cert_id, ...])
                └── (for each id) CertificateService.process_certificate(...)
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from celery import shared_task
from celery.utils.log import get_task_logger

from app.worker.celery_app import celery_app

logger = get_task_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_async(coro: Any) -> Any:
    """Run an async coroutine from synchronous Celery task context."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _new_loop_run(coro: Any) -> Any:
    """Create a fresh event loop — required when worker runs in a thread/process."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Task 1: Dispatcher ────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="tasks.dispatch_job_batches", max_retries=3)
def dispatch_job_batches(self, job_id: str, batch_size: int) -> None:  # type: ignore[misc]
    """Fetch all PENDING certificate IDs for the job and split them into batches.

    Each batch is sent to process_certificate_batch as a separate Celery task.
    This keeps individual tasks bounded and allows concurrent batch processing.
    """
    logger.info("batch_dispatcher_started | job_id=%s", job_id)
    try:
        _new_loop_run(_dispatch(job_id, batch_size))
    except Exception as exc:
        logger.exception("dispatch_failed | job_id=%s | error=%s", job_id, exc)
        raise self.retry(exc=exc, countdown=10)


async def _dispatch(job_id_str: str, batch_size: int) -> None:
    from app.db.session import async_session_factory  # noqa: PLC0415
    from app.models.generation_job import JobStatus  # noqa: PLC0415
    from app.repositories.certificate_repository import CertificateRepository  # noqa: PLC0415
    from app.repositories.generation_job_repository import GenerationJobRepository  # noqa: PLC0415

    job_id = uuid.UUID(job_id_str)

    async with async_session_factory() as session:
        job_repo = GenerationJobRepository(session)
        cert_repo = CertificateRepository(session)

        job = await job_repo.get(job_id)
        if job is None:
            logger.error("dispatch_job_not_found | job_id=%s", job_id_str)
            return

        # Mark job as PROCESSING
        await job_repo.update_status(
            job_id, JobStatus.PROCESSING, started_at=datetime.utcnow()
        )
        await session.commit()

        # Fetch all PENDING certificate IDs
        pending_ids = await cert_repo.get_pending_ids(job_id)

    if not pending_ids:
        logger.info("dispatch_no_pending | job_id=%s", job_id_str)
        await _finalize_job(job_id_str)
        return

    logger.info(
        "batch_dispatching | job_id=%s | pending=%d | batch_size=%d",
        job_id_str, len(pending_ids), batch_size,
    )

    # Split into bounded batches
    cert_id_strs = [str(cid) for cid in pending_ids]
    for i in range(0, len(cert_id_strs), batch_size):
        batch = cert_id_strs[i : i + batch_size]
        process_certificate_batch.delay(job_id_str, batch)

    logger.info(
        "batch_dispatched | job_id=%s | batches=%d",
        job_id_str, (len(pending_ids) + batch_size - 1) // batch_size,
    )


# ── Task 2: Batch processor ───────────────────────────────────────────────────

@celery_app.task(bind=True, name="tasks.process_certificate_batch", max_retries=3)
def process_certificate_batch(  # type: ignore[misc]
    self, job_id: str, certificate_ids: list[str]
) -> None:
    """Process one bounded batch of certificates.

    Failures are isolated per certificate — one bad PDF does not stop the batch.
    After the batch completes, job finalization is attempted.
    """
    logger.info(
        "batch_started | job_id=%s | count=%d", job_id, len(certificate_ids)
    )
    try:
        _new_loop_run(_process_batch(job_id, certificate_ids))
    except Exception as exc:
        logger.exception("batch_error | job_id=%s | error=%s", job_id, exc)
        raise self.retry(exc=exc, countdown=15)


async def _process_batch(job_id_str: str, certificate_id_strs: list[str]) -> None:
    from app.db.session import async_session_factory  # noqa: PLC0415
    from app.repositories.generation_job_repository import GenerationJobRepository  # noqa: PLC0415
    from app.services.certificate_service import CertificateService  # noqa: PLC0415

    job_id = uuid.UUID(job_id_str)

    async with async_session_factory() as session:
        job_repo = GenerationJobRepository(session)
        job = await job_repo.get(job_id)
        if job is None:
            logger.error("batch_job_not_found | job_id=%s", job_id_str)
            return

        cert_service = CertificateService(session)

        for cert_id_str in certificate_id_strs:
            cert_id = uuid.UUID(cert_id_str)
            try:
                await cert_service.process_certificate(job, cert_id)
            except Exception as exc:
                # Last-resort isolation: log and continue to next certificate
                logger.exception(
                    "certificate_unhandled_error | cert_id=%s | error=%s",
                    cert_id_str, exc,
                )

    logger.info("batch_completed | job_id=%s", job_id_str)

    # Attempt job finalization after each batch
    await _finalize_job(job_id_str)


# ── Job finalization ──────────────────────────────────────────────────────────

async def _finalize_job(job_id_str: str) -> None:
    """Check if the job is done and update its terminal status if so."""
    from app.db.session import async_session_factory  # noqa: PLC0415
    from app.models.generation_job import JobStatus  # noqa: PLC0415
    from app.repositories.generation_job_repository import GenerationJobRepository  # noqa: PLC0415

    job_id = uuid.UUID(job_id_str)

    async with async_session_factory() as session:
        job_repo = GenerationJobRepository(session)
        job = await job_repo.get(job_id)
        if job is None:
            return

        processed = job.successful_count + job.failed_count
        if processed < job.total_count:
            # Other batches still running
            return

        if job.failed_count == 0:
            final_status = JobStatus.COMPLETED
        else:
            final_status = JobStatus.COMPLETED_WITH_ERRORS

        await job_repo.update_status(
            job_id, final_status, completed_at=datetime.utcnow()
        )
        await session.commit()

        logger.info(
            "job_completed | job_id=%s | status=%s | success=%d | failed=%d",
            job_id_str, final_status, job.successful_count, job.failed_count,
        )
