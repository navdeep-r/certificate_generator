"""Integration tests for certificate download route.

Uses mocked repository and storage layers.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.certificate import CertificateStatus


def _mock_cert(status: str = CertificateStatus.COMPLETED) -> MagicMock:
    cert = MagicMock()
    cert.id = uuid.uuid4()
    cert.job_id = uuid.uuid4()
    cert.status = status
    cert.file_path = f"storage/{cert.job_id}/{cert.id}.pdf"
    cert.error_code = None
    cert.error_message = None
    return cert


class TestDownloadCertificate:
    async def test_completed_cert_returns_pdf(self, async_client: AsyncClient):
        cert = _mock_cert(CertificateStatus.COMPLETED)
        fake_pdf = b"%PDF-1.4 fake pdf content for testing"

        with (
            patch("app.api.routes.certificates.CertificateRepository") as MockRepo,
            patch("app.api.routes.certificates.StorageService") as MockStorage,
        ):
            MockRepo.return_value.get = AsyncMock(return_value=cert)
            MockStorage.return_value.read = MagicMock(return_value=fake_pdf)

            resp = await async_client.get(f"/api/v1/certificates/{cert.id}")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == fake_pdf

    async def test_pending_cert_returns_409(self, async_client: AsyncClient):
        cert = _mock_cert(CertificateStatus.PENDING)

        with patch("app.api.routes.certificates.CertificateRepository") as MockRepo:
            MockRepo.return_value.get = AsyncMock(return_value=cert)
            resp = await async_client.get(f"/api/v1/certificates/{cert.id}")

        assert resp.status_code == 409

    async def test_processing_cert_returns_409(self, async_client: AsyncClient):
        cert = _mock_cert(CertificateStatus.PROCESSING)

        with patch("app.api.routes.certificates.CertificateRepository") as MockRepo:
            MockRepo.return_value.get = AsyncMock(return_value=cert)
            resp = await async_client.get(f"/api/v1/certificates/{cert.id}")

        assert resp.status_code == 409

    async def test_failed_cert_returns_409_with_error(self, async_client: AsyncClient):
        cert = _mock_cert(CertificateStatus.FAILED)
        cert.error_code = "CERTIFICATE_GENERATION_FAILED"
        cert.error_message = "PDF generation error."

        with patch("app.api.routes.certificates.CertificateRepository") as MockRepo:
            MockRepo.return_value.get = AsyncMock(return_value=cert)
            resp = await async_client.get(f"/api/v1/certificates/{cert.id}")

        assert resp.status_code == 409
        body = resp.json()
        assert "CERTIFICATE_GENERATION_FAILED" in body["message"]

    async def test_unknown_cert_returns_404(self, async_client: AsyncClient):
        cert_id = uuid.uuid4()

        with patch("app.api.routes.certificates.CertificateRepository") as MockRepo:
            MockRepo.return_value.get = AsyncMock(return_value=None)
            resp = await async_client.get(f"/api/v1/certificates/{cert_id}")

        assert resp.status_code == 404
