"""GenerationJob ORM model."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(str):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=JobStatus.QUEUED,
        index=True,
    )

    # Certificate template metadata
    certificate_title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    issuer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Counters
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship
    certificates: Mapped[list["Certificate"]] = relationship(  # noqa: F821
        "Certificate", back_populates="job", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<GenerationJob id={self.id} status={self.status}>"
