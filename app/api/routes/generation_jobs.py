"""Generation job routes — thin HTTP adapter.

Routes: POST /api/v1/generation-jobs
        GET  /api/v1/generation-jobs/{job_id}
        GET  /api/v1/generation-jobs/{job_id}/certificates
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import NotFoundError
from app.repositories.certificate_repository import CertificateRepository
from app.repositories.generation_job_repository import GenerationJobRepository
from app.schemas.certificate import CertificateListResponse, CertificateResponse
from app.schemas.generation_job import (
    CreateGenerationJobRequest,
    CreateGenerationJobResponse,
    GenerationJobStatusResponse,
)
from app.services.generation_service import GenerationService

router = APIRouter()


@router.post(
    "",
    status_code=202,
    response_model=CreateGenerationJobResponse,
    summary="Create a bulk certificate generation job",
)
async def create_generation_job(
    request: CreateGenerationJobRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateGenerationJobResponse:
    service = GenerationService(db)
    job = await service.create_job(request)
    return CreateGenerationJobResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count,
        successful_count=job.successful_count,
        failed_count=job.failed_count,
        status_url=f"/api/v1/generation-jobs/{job.id}",
    )


@router.get(
    "/{job_id}",
    response_model=GenerationJobStatusResponse,
    summary="Get job status and progress",
)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> GenerationJobStatusResponse:
    repo = GenerationJobRepository(db)
    job = await repo.get(job_id)
    if job is None:
        raise NotFoundError(f"Generation job {job_id} not found.")

    processed = job.successful_count + job.failed_count
    pending = job.total_count - processed
    progress = (processed / job.total_count * 100) if job.total_count else 0.0

    return GenerationJobStatusResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count,
        successful_count=job.successful_count,
        failed_count=job.failed_count,
        pending_count=max(pending, 0),
        progress_percent=round(progress, 2),
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        results_url=f"/api/v1/generation-jobs/{job.id}/certificates",
    )


@router.get(
    "/{job_id}/certificates",
    response_model=CertificateListResponse,
    summary="List certificates for a job (paginated)",
)
async def list_job_certificates(
    job_id: uuid.UUID,
    status: Optional[str] = Query(default=None, description="Filter by certificate status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> CertificateListResponse:
    job_repo = GenerationJobRepository(db)
    job = await job_repo.get(job_id)
    if job is None:
        raise NotFoundError(f"Generation job {job_id} not found.")

    cert_repo = CertificateRepository(db)
    offset = (page - 1) * page_size
    items, total = await cert_repo.list_by_job(
        job_id, status=status, offset=offset, limit=page_size
    )

    return CertificateListResponse(
        job_id=job_id,
        total=total,
        page=page,
        page_size=page_size,
        items=[_cert_to_response(c) for c in items],
    )


def _cert_to_response(c) -> CertificateResponse:  # type: ignore[no-untyped-def]
    return CertificateResponse(
        certificate_id=c.id,
        job_id=c.job_id,
        sequence_number=c.sequence_number,
        recipient_name=c.recipient_name,
        recipient_email=c.recipient_email,
        status=c.status,
        error_code=c.error_code,
        error_message=c.error_message,
        attempt_count=c.attempt_count,
        created_at=c.created_at,
        completed_at=c.completed_at,
    )
