"""Integration tests for the generation-jobs API.

These tests use the FastAPI test client with mocked service/repository layers
so they do not require a live database or Celery worker.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.exceptions import NotFoundError


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_PAYLOAD = {
    "certificate": {
        "title": "Certificate of Completion",
        "event_name": "Python Bootcamp 2026",
        "issuer_name": "Example Organization",
        "issue_date": "2026-10-07",
    },
    "recipients": [
        {"name": "Alice Johnson", "email": "alice@example.com"},
        {"name": "Bob Smith"},
    ],
}


def _mock_job(job_id: uuid.UUID | None = None) -> MagicMock:
    """Build a mock GenerationJob object."""
    job = MagicMock()
    job.id = job_id or uuid.uuid4()
    job.status = "queued"
    job.total_count = 2
    job.successful_count = 0
    job.failed_count = 0
    job.created_at = datetime(2026, 10, 7, 12, 0, 0)
    job.started_at = None
    job.completed_at = None
    return job


# ── POST /api/v1/generation-jobs ──────────────────────────────────────────────

class TestCreateGenerationJob:
    async def test_valid_request_returns_202(self, async_client: AsyncClient):
        mock_job = _mock_job()
        with patch(
            "app.api.routes.generation_jobs.GenerationService"
        ) as MockService:
            instance = MockService.return_value
            instance.create_job = AsyncMock(return_value=mock_job)
            resp = await async_client.post("/api/v1/generation-jobs", json=VALID_PAYLOAD)

        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "queued"
        assert body["total_count"] == 2
        assert "/api/v1/generation-jobs/" in body["status_url"]

    async def test_missing_certificate_field_returns_422(self, async_client: AsyncClient):
        payload = {"recipients": [{"name": "Alice"}]}
        resp = await async_client.post("/api/v1/generation-jobs", json=payload)
        assert resp.status_code == 422

    async def test_empty_recipients_returns_422(self, async_client: AsyncClient):
        payload = {**VALID_PAYLOAD, "recipients": []}
        resp = await async_client.post("/api/v1/generation-jobs", json=payload)
        assert resp.status_code == 422

    async def test_invalid_date_returns_422(self, async_client: AsyncClient):
        payload = dict(VALID_PAYLOAD)
        payload["certificate"] = {**VALID_PAYLOAD["certificate"], "issue_date": "not-a-date"}
        resp = await async_client.post("/api/v1/generation-jobs", json=payload)
        assert resp.status_code == 422

    async def test_too_many_recipients_returns_413(self, async_client: AsyncClient):
        from app.core.exceptions import RequestTooLargeError

        with patch(
            "app.api.routes.generation_jobs.GenerationService"
        ) as MockService:
            instance = MockService.return_value
            instance.create_job = AsyncMock(side_effect=RequestTooLargeError())
            payload = {**VALID_PAYLOAD, "recipients": [{"name": f"User{i}"} for i in range(501)]}
            resp = await async_client.post("/api/v1/generation-jobs", json=payload)

        assert resp.status_code == 413


# ── GET /api/v1/generation-jobs/{job_id} ─────────────────────────────────────

class TestGetJobStatus:
    async def test_existing_job_returns_200(self, async_client: AsyncClient):
        job_id = uuid.uuid4()
        mock_job = _mock_job(job_id)
        mock_job.status = "processing"
        mock_job.successful_count = 1
        mock_job.failed_count = 0
        mock_job.total_count = 2

        with patch(
            "app.api.routes.generation_jobs.GenerationJobRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.get = AsyncMock(return_value=mock_job)
            resp = await async_client.get(f"/api/v1/generation-jobs/{job_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == str(job_id)
        assert body["pending_count"] == 1
        assert body["progress_percent"] == 50.0

    async def test_unknown_job_returns_404(self, async_client: AsyncClient):
        job_id = uuid.uuid4()
        with patch(
            "app.api.routes.generation_jobs.GenerationJobRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.get = AsyncMock(return_value=None)
            resp = await async_client.get(f"/api/v1/generation-jobs/{job_id}")

        assert resp.status_code == 404

    async def test_progress_100_when_complete(self, async_client: AsyncClient):
        job_id = uuid.uuid4()
        mock_job = _mock_job(job_id)
        mock_job.status = "completed"
        mock_job.successful_count = 2
        mock_job.failed_count = 0
        mock_job.total_count = 2

        with patch(
            "app.api.routes.generation_jobs.GenerationJobRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.get = AsyncMock(return_value=mock_job)
            resp = await async_client.get(f"/api/v1/generation-jobs/{job_id}")

        assert resp.json()["progress_percent"] == 100.0


# ── GET /api/v1/generation-jobs/{job_id}/certificates ────────────────────────

class TestListCertificates:
    async def test_returns_paginated_list(self, async_client: AsyncClient):
        job_id = uuid.uuid4()
        mock_job = _mock_job(job_id)

        cert = MagicMock()
        cert.id = uuid.uuid4()
        cert.job_id = job_id
        cert.sequence_number = 1
        cert.recipient_name = "Alice Johnson"
        cert.recipient_email = "alice@example.com"
        cert.status = "completed"
        cert.error_code = None
        cert.error_message = None
        cert.attempt_count = 1
        cert.created_at = datetime(2026, 10, 7)
        cert.completed_at = datetime(2026, 10, 7)

        with (
            patch("app.api.routes.generation_jobs.GenerationJobRepository") as MockJobRepo,
            patch("app.api.routes.generation_jobs.CertificateRepository") as MockCertRepo,
        ):
            MockJobRepo.return_value.get = AsyncMock(return_value=mock_job)
            MockCertRepo.return_value.list_by_job = AsyncMock(return_value=([cert], 1))
            resp = await async_client.get(f"/api/v1/generation-jobs/{job_id}/certificates")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["recipient_name"] == "Alice Johnson"
