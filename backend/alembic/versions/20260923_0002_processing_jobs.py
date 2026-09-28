"""Add the bounded preparation job and artifact persistence subset.

Revision ID: 20260923_0002
Revises: 20260907_0001
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260923_0002"
down_revision: str | None = "20260907_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_scope", sa.String(160), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False),
        sa.Column("operation_version", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("request_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_evidence_json", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("current_stage", sa.String(80), nullable=True),
        sa.Column("completed_units", sa.Integer(), nullable=True),
        sa.Column("total_units", sa.Integer(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(160), nullable=True),
        sa.Column("safe_error_message", sa.String(1000), nullable=True),
        sa.Column("quality_report_json", postgresql.JSONB(), nullable=True),
        sa.Column("manifest_json", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint(
            "state IN ('queued','running','cancelling','succeeded','failed','cancelled')",
            name="processing_jobs_state",
        ),
        sa.UniqueConstraint(
            "owner_id", "operation", "idempotency_key", name="uq_processing_job_idempotency"
        ),
    )
    op.create_index(
        "ix_processing_jobs_owner_submitted",
        "processing_jobs",
        ["owner_id", "submitted_at", "id"],
    )
    op.create_index(
        "ix_processing_jobs_cache",
        "processing_jobs",
        ["owner_id", "access_scope", "cache_key", "state"],
    )
    op.create_index("ix_processing_jobs_state", "processing_jobs", ["state", "submitted_at"])

    op.create_table(
        "processing_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("processing_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("media_type", sa.String(160), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('available','quarantined')", name="processing_artifacts_state"
        ),
    )
    op.create_index(
        "ix_processing_artifacts_owner_job",
        "processing_artifacts",
        ["owner_id", "job_id", "id"],
    )

    op.create_table(
        "processing_job_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("processing_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("stage", sa.String(80), nullable=True),
        sa.Column("details_json", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "sequence", name="uq_processing_job_event_sequence"),
    )


def downgrade() -> None:
    op.drop_table("processing_job_events")
    op.drop_index("ix_processing_artifacts_owner_job", table_name="processing_artifacts")
    op.drop_table("processing_artifacts")
    op.drop_index("ix_processing_jobs_state", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_cache", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_owner_submitted", table_name="processing_jobs")
    op.drop_table("processing_jobs")
