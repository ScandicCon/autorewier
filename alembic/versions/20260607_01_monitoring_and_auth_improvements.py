"""Add monitoring tables and auth improvements.

Revision ID: 20260607_01
Revises: 20260606_01
Create Date: 2026-06-07 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260607_01"
down_revision = "20260606_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: all columns and tables from this migration are already
    # included in the initial schema (20260601_00).
    pass


def downgrade() -> None:
    op.drop_index(
        "ix_listing_change_events_monitored_listing_id",
        table_name="listing_change_events",
    )
    op.drop_table("listing_change_events")

    op.drop_index("ix_monitored_listings_inspection_id", table_name="monitored_listings")
    op.drop_index("ix_monitored_listings_user_id", table_name="monitored_listings")
    op.drop_table("monitored_listings")

    # Drop enum types (PostgreSQL)
    try:
        op.execute("DROP TYPE IF EXISTS listingstatus")
        op.execute("DROP TYPE IF EXISTS changetype")
    except Exception:
        pass

    op.drop_index("ix_users_password_reset_token", table_name="users")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_token")
    op.drop_column("users", "email_verification_sent_at")
