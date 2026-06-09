"""Hardening baseline for production.

Revision ID: 20260606_01
Revises:
Create Date: 2026-06-06 20:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260606_01"
down_revision = "20260601_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # All columns and tables already created in initial schema (20260601_00)
    pass


def downgrade() -> None:
    op.drop_index("ix_processed_webhook_events_event_key", table_name="processed_webhook_events")
    op.drop_index("ix_processed_webhook_events_provider", table_name="processed_webhook_events")
    op.drop_table("processed_webhook_events")
    op.drop_column("users", "session_expires_at")
    op.drop_column("users", "session_issued_at")
