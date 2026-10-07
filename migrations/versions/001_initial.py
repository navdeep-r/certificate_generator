"""Initial schema — generation_jobs and certificates tables.

Revision ID: 001
Revises:
Create Date: 2026-10-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("certificate_title", sa.String(200), nullable=False),
        sa.Column("event_name", sa.String(200), nullable=False),
        sa.Column("issuer_name", sa.String(200), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])

    op.create_table(
        "certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("recipient_name", sa.String(120), nullable=False),
        sa.Column("recipient_email", sa.String(254), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_certificates_job_id", "certificates", ["job_id"])
    op.create_index(
        "ix_certificates_job_id_status", "certificates", ["job_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_certificates_job_id_status", table_name="certificates")
    op.drop_index("ix_certificates_job_id", table_name="certificates")
    op.drop_table("certificates")
    op.drop_index("ix_generation_jobs_status", table_name="generation_jobs")
    op.drop_table("generation_jobs")
