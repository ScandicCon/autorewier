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
    # --- Auth improvements ---
    # Cooldown timestamp for email verification resend
    op.add_column(
        "users",
        sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True),
    )
    # Password reset token fields
    op.add_column(
        "users",
        sa.Column("password_reset_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_users_password_reset_token",
        "users",
        ["password_reset_token"],
        unique=True,
    )

    # --- Monitored listings ---
    op.create_table(
        "monitored_listings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("inspection_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=True),
        sa.Column("last_price", sa.Integer(), nullable=True),
        sa.Column(
            "last_status",
            sa.Enum("active", "sold", "removed", name="listingstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitored_listings_user_id", "monitored_listings", ["user_id"])
    op.create_index(
        "ix_monitored_listings_inspection_id", "monitored_listings", ["inspection_id"]
    )

    # --- Listing change events ---
    op.create_table(
        "listing_change_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("monitored_listing_id", sa.Integer(), nullable=False),
        sa.Column(
            "change_type",
            sa.Enum("price_drop", "price_rise", "sold", "removed", name="changetype"),
            nullable=False,
        ),
        sa.Column("old_value", sa.String(length=256), nullable=True),
        sa.Column("new_value", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["monitored_listing_id"], ["monitored_listings.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_listing_change_events_monitored_listing_id",
        "listing_change_events",
        ["monitored_listing_id"],
    )


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
