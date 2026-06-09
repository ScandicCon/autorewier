"""Initial schema — create all tables from scratch.

Revision ID: 20260601_00
Revises:
Create Date: 2026-06-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260601_00"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ENUMs
    subscription_plan = sa.Enum("free", "pro", name="subscriptionplan")
    subscription_plan.create(op.get_bind(), checkfirst=True)

    payment_status = sa.Enum("pending", "succeeded", "failed", "cancelled", name="paymentstatus")
    payment_status.create(op.get_bind(), checkfirst=True)

    inspection_stage = sa.Enum("draft", "pre_inspection", "post_inspection", name="inspectionstage")
    inspection_stage.create(op.get_bind(), checkfirst=True)

    verdict_enum = sa.Enum("worth_looking", "caution", "skip", name="verdict")
    verdict_enum.create(op.get_bind(), checkfirst=True)

    listing_status = sa.Enum("active", "sold", "deleted", "price_changed", name="listingstatus")
    listing_status.create(op.get_bind(), checkfirst=True)

    change_type = sa.Enum("price_drop", "price_increase", "status_change", "deleted", name="changetype")
    change_type.create(op.get_bind(), checkfirst=True)

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_verification_code", sa.String(16), nullable=True),
        sa.Column("email_verification_expires_at", sa.DateTime(), nullable=True),
        sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True),
        sa.Column("password_reset_token", sa.String(64), nullable=True),
        sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True),
        sa.Column("phone_number", sa.String(32), nullable=True),
        sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("session_token", sa.String(64), nullable=True),
        sa.Column("session_issued_at", sa.DateTime(), nullable=True),
        sa.Column("session_expires_at", sa.DateTime(), nullable=True),
        sa.Column("subscription_plan", sa.Enum("free", "pro", name="subscriptionplan"), nullable=False, server_default="free"),
        sa.Column("subscription_until", sa.DateTime(), nullable=True),
        sa.Column("inspections_this_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("month_reset_key", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_phone_number", "users", ["phone_number"], unique=True)
    op.create_index("ix_users_session_token", "users", ["session_token"], unique=True)
    op.create_index("ix_users_password_reset_token", "users", ["password_reset_token"], unique=True)

    # payments
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount_rub", sa.Integer(), nullable=False),
        sa.Column("plan", sa.Enum("free", "pro", name="subscriptionplan"), nullable=False),
        sa.Column("status", sa.Enum("pending", "succeeded", "failed", "cancelled", name="paymentstatus"), nullable=False),
        sa.Column("yookassa_payment_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_yookassa_payment_id", "payments", ["yookassa_payment_id"], unique=True)

    # processed_webhook_events
    op.create_table(
        "processed_webhook_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processed_webhook_events_provider", "processed_webhook_events", ["provider"])
    op.create_index("ix_processed_webhook_events_event_key", "processed_webhook_events", ["event_key"], unique=True)

    # vin_checks
    op.create_table(
        "vin_checks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("inspection_id", sa.Integer(), nullable=True),
        sa.Column("vin", sa.String(32), nullable=False),
        sa.Column("report_uid", sa.String(128), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("report_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vin_checks_user_id", "vin_checks", ["user_id"])
    op.create_index("ix_vin_checks_vin", "vin_checks", ["vin"])

    # inspections
    op.create_table(
        "inspections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stage", sa.Enum("draft", "pre_inspection", "post_inspection", name="inspectionstage"), nullable=False),
        sa.Column("listing_url", sa.String(1024), nullable=True),
        sa.Column("platform", sa.String(64), nullable=True),
        sa.Column("brand", sa.String(128), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("mileage_km", sa.Integer(), nullable=True),
        sa.Column("price_rub", sa.Integer(), nullable=True),
        sa.Column("engine", sa.String(256), nullable=True),
        sa.Column("transmission", sa.String(128), nullable=True),
        sa.Column("drive", sa.String(64), nullable=True),
        sa.Column("body_type", sa.String(64), nullable=True),
        sa.Column("color", sa.String(64), nullable=True),
        sa.Column("vin", sa.String(32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("user_preferences", sa.Text(), nullable=True),
        sa.Column("listing_repairs", sa.Text(), nullable=True),
        sa.Column("pre_defects", sa.Text(), nullable=True),
        sa.Column("post_defects", sa.Text(), nullable=True),
        sa.Column("post_notes", sa.Text(), nullable=True),
        sa.Column("photo_paths", sa.JSON(), nullable=True),
        sa.Column("photos_metadata", sa.JSON(), nullable=True),
        sa.Column("observed_defects", sa.JSON(), nullable=True),
        sa.Column("is_reseller", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("target_resale_price", sa.Integer(), nullable=True),
        sa.Column("final_recommendation", sa.String(32), nullable=True),
        sa.Column("verdict", sa.Enum("worth_looking", "caution", "skip", name="verdict"), nullable=True),
        sa.Column("pre_report", sa.JSON(), nullable=True),
        sa.Column("post_report", sa.JSON(), nullable=True),
        sa.Column("parts_pricing", sa.JSON(), nullable=True),
        sa.Column("repair_min_rub", sa.Integer(), nullable=True),
        sa.Column("repair_max_rub", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspections_user_id", "inspections", ["user_id"])

    # monitored_listings
    op.create_table(
        "monitored_listings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("inspection_id", sa.Integer(), sa.ForeignKey("inspections.id"), nullable=True),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("platform", sa.String(64), nullable=True),
        sa.Column("last_price", sa.Integer(), nullable=True),
        sa.Column("last_status", sa.Enum("active", "sold", "deleted", "price_changed", name="listingstatus"), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitored_listings_user_id", "monitored_listings", ["user_id"])
    op.create_index("ix_monitored_listings_inspection_id", "monitored_listings", ["inspection_id"])

    # listing_change_events
    op.create_table(
        "listing_change_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("monitored_listing_id", sa.Integer(), sa.ForeignKey("monitored_listings.id"), nullable=False),
        sa.Column("change_type", sa.Enum("price_drop", "price_increase", "status_change", "deleted", name="changetype"), nullable=False),
        sa.Column("old_value", sa.String(256), nullable=True),
        sa.Column("new_value", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_listing_change_events_monitored_listing_id", "listing_change_events", ["monitored_listing_id"])

    # Add FK for vin_checks.inspection_id now that inspections table exists
    op.create_foreign_key(None, "vin_checks", "inspections", ["inspection_id"], ["id"])


def downgrade() -> None:
    op.drop_table("listing_change_events")
    op.drop_table("monitored_listings")
    op.drop_table("inspections")
    op.drop_table("vin_checks")
    op.drop_table("processed_webhook_events")
    op.drop_table("payments")
    op.drop_table("users")
