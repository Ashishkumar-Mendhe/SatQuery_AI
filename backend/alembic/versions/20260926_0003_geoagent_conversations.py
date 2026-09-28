"""Persist bounded owner/scope-constrained GeoAgent conversation context.

Revision ID: 20260926_0003
Revises: 20260923_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260926_0003"
down_revision: str | None = "20260923_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "geoagent_conversations",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_scope", sa.String(160), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state_json", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "access_scope", "conversation_id"),
        sa.CheckConstraint("version >= 1", name="geoagent_conversation_version"),
    )


def downgrade() -> None:
    op.drop_table("geoagent_conversations")
