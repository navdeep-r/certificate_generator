"""Pydantic schemas for Certificate API output."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CertificateResponse(BaseModel):
    certificate_id: uuid.UUID
    job_id: uuid.UUID
    sequence_number: int
    recipient_name: str
    recipient_email: Optional[str]
    status: str
    error_code: Optional[str]
    error_message: Optional[str]
    attempt_count: int
    created_at: datetime
    completed_at: Optional[datetime]


class CertificateListResponse(BaseModel):
    job_id: uuid.UUID
    total: int
    page: int
    page_size: int
    items: list[CertificateResponse]
