"""Pydantic schemas for GenerationJob API input/output."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Input ────────────────────────────────────────────────────────────────────

class CertificateMetadataIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    event_name: str = Field(..., min_length=1, max_length=200)
    issuer_name: str = Field(..., min_length=1, max_length=200)
    issue_date: date

    @field_validator("title", "event_name", "issuer_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class RecipientIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: Optional[EmailStr] = Field(default=None, max_length=254)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class CreateGenerationJobRequest(BaseModel):
    certificate: CertificateMetadataIn
    recipients: list[RecipientIn] = Field(..., min_length=1)


# ── Output ───────────────────────────────────────────────────────────────────

class CreateGenerationJobResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    total_count: int
    successful_count: int
    failed_count: int
    status_url: str


class GenerationJobStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    total_count: int
    successful_count: int
    failed_count: int
    pending_count: int
    progress_percent: float
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    results_url: str
