"""Certificate download route.

GET /api/v1/certificates/{certificate_id}
    200 application/pdf  — completed certificate
    404                  — certificate not found
    409                  — certificate not ready (pending/processing/failed)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import ConflictError, NotFoundError
from app.models.certificate import CertificateStatus
from app.repositories.certificate_repository import CertificateRepository
from app.services.storage_service import StorageService

router = APIRouter()


@router.get(
    "/{certificate_id}",
    summary="Download a completed certificate PDF",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "Certificate not found"},
        409: {"description": "Certificate not ready or failed"},
    },
)
async def download_certificate(
    certificate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    repo = CertificateRepository(db)
    cert = await repo.get(certificate_id)

    if cert is None:
        raise NotFoundError(f"Certificate {certificate_id} not found.")

    if cert.status == CertificateStatus.FAILED:
        raise ConflictError(
            f"Certificate generation failed: [{cert.error_code}] {cert.error_message}"
        )

    if cert.status in (CertificateStatus.PENDING, CertificateStatus.PROCESSING):
        raise ConflictError(
            f"Certificate is not yet ready (current status: {cert.status})."
        )

    # COMPLETED — serve the PDF
    storage = StorageService()
    pdf_bytes = storage.read(cert.file_path)  # type: ignore[arg-type]

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{certificate_id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
