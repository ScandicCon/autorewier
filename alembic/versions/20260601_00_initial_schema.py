"""Initial schema — create all tables from scratch.

Revision ID: 20260601_00
Revises:
Create Date: 2026-06-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260601_00"
down_revision = None
branch_labels = None
depends_on = None

_Q = lambda s: op.execute(sa.text(s))  # noqa: E731


def upgrade() -> None:
    # ── Enum types (fully idempotent via DO/EXCEPTION) ────────────────────
    _Q("""DO $$ BEGIN CREATE TYPE subscriptionplan AS ENUM ('free','pro');
EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    _Q("""DO $$ BEGIN CREATE TYPE paymentstatus AS ENUM ('pending','succeeded','failed','cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    _Q("""DO $$ BEGIN CREATE TYPE inspectionstage AS ENUM ('draft','pre_inspection','post_inspection');
EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    _Q("""DO $$ BEGIN CREATE TYPE verdict AS ENUM ('worth_looking','caution','skip');
EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    _Q("""DO $$ BEGIN CREATE TYPE listingstatus AS ENUM ('active','sold','deleted','price_changed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    _Q("""DO $$ BEGIN CREATE TYPE changetype AS ENUM ('price_drop','price_increase','status_change','deleted');
EXCEPTION WHEN duplicate_object THEN NULL; END $$""")

    # ── users ─────────────────────────────────────────────────────────────
    _Q("""
CREATE TABLE IF NOT EXISTS users (
    id                              SERIAL PRIMARY KEY,
    telegram_id                     INTEGER,
    email                           VARCHAR(255),
    email_verified                  BOOLEAN NOT NULL DEFAULT false,
    email_verification_code         VARCHAR(16),
    email_verification_expires_at   TIMESTAMP,
    email_verification_sent_at      TIMESTAMP,
    password_reset_token            VARCHAR(64),
    password_reset_expires_at       TIMESTAMP,
    phone_number                    VARCHAR(32),
    phone_verified                  BOOLEAN NOT NULL DEFAULT false,
    password_hash                   VARCHAR(255),
    session_token                   VARCHAR(64),
    session_issued_at               TIMESTAMP,
    session_expires_at              TIMESTAMP,
    subscription_plan               subscriptionplan NOT NULL DEFAULT 'free',
    subscription_until              TIMESTAMP,
    inspections_this_month          INTEGER NOT NULL DEFAULT 0,
    month_reset_key                 VARCHAR(7),
    created_at                      TIMESTAMP NOT NULL
)""")
    _Q("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id)")
    _Q("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
    _Q("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone_number ON users (phone_number)")
    _Q("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_session_token ON users (session_token)")
    _Q("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_password_reset_token ON users (password_reset_token)")

    # ── payments ──────────────────────────────────────────────────────────
    _Q("""
CREATE TABLE IF NOT EXISTS payments (
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

    # ── processed_webhook_events ──────────────────────────────────────────
    _Q("""
CREATE TABLE IF NOT EXISTS processed_webhook_events (
    id          SERIAL PRIMARY KEY,
    provider    VARCHAR(32) NOT NULL,
    event_key   VARCHAR(255) NOT NULL,
    payload     JSON,
    created_at  TIMESTAMP NOT NULL
)""")
    _Q("CREATE INDEX IF NOT EXISTS ix_processed_webhook_events_provider ON processed_webhook_events (provider)")
    _Q("CREATE UNIQUE INDEX IF NOT EXISTS ix_processed_webhook_events_event_key ON processed_webhook_events (event_key)")

    # ── vin_checks ────────────────────────────────────────────────────────
    _Q("""
CREATE TABLE IF NOT EXISTS vin_checks (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    inspection_id INTEGER,
    vin           VARCHAR(32) NOT NULL,
    report_uid    VARCHAR(128),
    summary       TEXT,
    report_data   JSON,
    created_at    TIMESTAMP NOT NULL
)""")
    _Q("CREATE INDEX IF NOT EXISTS ix_vin_checks_user_id ON vin_checks (user_id)")
    _Q("CREATE INDEX IF NOT EXISTS ix_vin_checks_vin ON vin_checks (vin)")

    # ── inspections ───────────────────────────────────────────────────────
    _Q("""
CREATE TABLE IF NOT EXISTS inspections (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES users(id),
    stage                 inspectionstage NOT NULL,
    listing_url           VARCHAR(1024),
    platform              VARCHAR(64),
    brand                 VARCHAR(128),
    model                 VARCHAR(128),
    year                  INTEGER,
    mileage_km            INTEGER,
    price_rub             INTEGER,
    engine                VARCHAR(256),
    transmission          VARCHAR(128),
    drive                 VARCHAR(64),
    body_type             VARCHAR(64),
    color                 VARCHAR(64),
    vin                   VARCHAR(32),
    description           TEXT,
    user_preferences      TEXT,
    listing_repairs       TEXT,
    pre_defects           TEXT,
    post_defects          TEXT,
    post_notes            TEXT,
    photo_paths           JSON,
    photos_metadata       JSON,
    observed_defects      JSON,
    is_reseller           BOOLEAN NOT NULL DEFAULT false,
    target_resale_price   INTEGER,
    final_recommendation  VARCHAR(32),
    verdict               verdict,
    pre_report            JSON,
    post_report           JSON,
    parts_pricing         JSON,
    repair_min_rub        INTEGER,
    repair_max_rub        INTEGER,
    created_at            TIMESTAMP NOT NULL,
    updated_at            TIMESTAMP NOT NULL
)""")
    _Q("CREATE INDEX IF NOT EXISTS ix_inspections_user_id ON inspections (user_id)")

    # FK from vin_checks → inspections (added after inspections exists)
    _Q("""DO $$ BEGIN
ALTER TABLE vin_checks ADD CONSTRAINT fk_vin_checks_inspection
    FOREIGN KEY (inspection_id) REFERENCES inspections(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$""")

    # ── monitored_listings ────────────────────────────────────────────────
    _Q("""
CREATE TABLE IF NOT EXISTS monitored_listings (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    inspection_id   INTEGER REFERENCES inspections(id),
    url             VARCHAR(1024) NOT NULL,
    platform        VARCHAR(64),
    last_price      INTEGER,
    last_status     listingstatus NOT NULL,
    last_checked_at TIMESTAMP,
    created_at      TIMESTAMP NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT true
)""")
    _Q("CREATE INDEX IF NOT EXISTS ix_monitored_listings_user_id ON monitored_listings (user_id)")
    _Q("CREATE INDEX IF NOT EXISTS ix_monitored_listings_inspection_id ON monitored_listings (inspection_id)")

    # ── listing_change_events ─────────────────────────────────────────────
    _Q("""
CREATE TABLE IF NOT EXISTS listing_change_events (
    id                    SERIAL PRIMARY KEY,
    monitored_listing_id  INTEGER NOT NULL REFERENCES monitored_listings(id),
    change_type           changetype NOT NULL,
    old_value             VARCHAR(256),
    new_value             VARCHAR(256),
    created_at            TIMESTAMP NOT NULL
)""")
    _Q("CREATE INDEX IF NOT EXISTS ix_listing_change_events_monitored_listing_id ON listing_change_events (monitored_listing_id)")


def downgrade() -> None:
    _Q("DROP TABLE IF EXISTS listing_change_events")
    _Q("DROP TABLE IF EXISTS monitored_listings")
    _Q("DROP TABLE IF EXISTS inspections")
    _Q("DROP TABLE IF EXISTS vin_checks")
    _Q("DROP TABLE IF EXISTS processed_webhook_events")
    _Q("DROP TABLE IF EXISTS payments")
    _Q("DROP TABLE IF EXISTS users")
    _Q("DROP TYPE IF EXISTS changetype")
    _Q("DROP TYPE IF EXISTS listingstatus")
    _Q("DROP TYPE IF EXISTS verdict")
    _Q("DROP TYPE IF EXISTS inspectionstage")
    _Q("DROP TYPE IF EXISTS paymentstatus")
    _Q("DROP TYPE IF EXISTS subscriptionplan")
