"""Fix enum values to match Python model .value attributes.

Revision ID: 20260610_03
Revises: 20260607_01
Create Date: 2026-06-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260610_03"
down_revision = "20260607_01"
branch_labels = None
depends_on = None

_Q = lambda s: op.execute(sa.text(s))  # noqa: E731


def upgrade() -> None:
    # Drop tables that use the wrong enum types (DB is empty, no data loss)
    _Q("DROP TABLE IF EXISTS listing_change_events")
    _Q("DROP TABLE IF EXISTS monitored_listings")
    _Q("DROP TABLE IF EXISTS payments")

    # Drop the wrong enum types
    _Q("DROP TYPE IF EXISTS changetype")
    _Q("DROP TYPE IF EXISTS listingstatus")
    _Q("DROP TYPE IF EXISTS paymentstatus")

    # Recreate with correct values matching Python model .value
    _Q("CREATE TYPE paymentstatus AS ENUM ('pending', 'succeeded', 'canceled')")
    _Q("CREATE TYPE listingstatus AS ENUM ('active', 'sold', 'removed')")
    _Q("CREATE TYPE changetype AS ENUM ('price_drop', 'price_rise', 'sold', 'removed')")

    # Recreate payments
    _Q("""
CREATE TABLE payments (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES users(id),
    amount_rub            INTEGER NOT NULL,
    plan                  subscriptionplan NOT NULL,
    status                paymentstatus NOT NULL,
    yookassa_payment_id   VARCHAR(64),
    created_at            TIMESTAMP NOT NULL
)""")
    _Q("CREATE INDEX IF NOT EXISTS ix_payments_user_id ON payments (user_id)")
    _Q("CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_yookassa_payment_id ON payments (yookassa_payment_id)")

    # Recreate monitored_listings
    _Q("""
CREATE TABLE monitored_listings (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    inspection_id   INTEGER REFERENCES inspections(id),
    url             VARCHAR(1024) NOT NULL,
    platform        VARCHAR(64),
    last_price      INTEGER,
    last_status     listingstatus NOT NULL DEFAULT 'active',
    last_checked_at TIMESTAMP,
    created_at      TIMESTAMP NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT true
)""")
    _Q("CREATE INDEX IF NOT EXISTS ix_monitored_listings_user_id ON monitored_listings (user_id)")
    _Q("CREATE INDEX IF NOT EXISTS ix_monitored_listings_inspection_id ON monitored_listings (inspection_id)")

    # Recreate listing_change_events
    _Q("""
CREATE TABLE listing_change_events (
    id                    SERIAL PRIMARY KEY,
    monitored_listing_id  INTEGER NOT NULL REFERENCES monitored_listings(id),
    change_type           changetype NOT NULL,
    old_value             VARCHAR(256),
    new_value             VARCHAR(256),
    created_at            TIMESTAMP NOT NULL
)""")
    _Q("CREATE INDEX IF NOT EXISTS ix_listing_change_events_monitored_listing_id ON listing_change_events (monitored_listing_id)")


def downgrade() -> None:
    pass
