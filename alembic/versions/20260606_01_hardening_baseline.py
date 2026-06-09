"""Hardening baseline for production.

Revision ID: 20260606_01
Revises:
Create Date: 2026-06-06 20:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260606_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_issued_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("session_expires_at", sa.DateTime(), nullable=True))
    op.create_table(
        "processed_webhook_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_processed_webhook_events_provider",
        "processed_webhook_events",
        ["provider"],
        unique=False,
    )
    op.create_index(
        "ix_processed_webhook_events_event_key",
        "processed_webhook_events",
        ["event_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_processed_webhook_events_event_key", table_name="processed_webhook_events")
    op.drop_index("ix_processed_webhook_events_provider", table_name="processed_webhook_events")
    op.drop_table("processed_webhook_events")
    op.drop_column("users", "session_expires_at")
    op.drop_column("users", "session_issued_at")
