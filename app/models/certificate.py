"""Certificate ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CertificateStatus(str):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        Index("ix_certificates_job_id", "job_id"),
        Index("ix_certificates_job_id_status", "job_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Recipient data (input at creation time — never used as filesystem paths)
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    recipient_email: Mapped[str | None] = mapped_column(String(254), nullable=True)

    # State
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CertificateStatus.PENDING
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Error tracking
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship
    job: Mapped["GenerationJob"] = relationship(  # noqa: F821
        "GenerationJob", back_populates="certificates"
    )

    def __repr__(self) -> str:
        return f"<Certificate id={self.id} status={self.status}>"
