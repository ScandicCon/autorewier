-- =============================================================================
-- AutoRewier — создание всех таблиц в Supabase
-- Вставь этот SQL в Supabase Dashboard → SQL Editor → New query → Run
-- =============================================================================

-- Enum types (IF NOT EXISTS не поддерживается для TYPE — используем DO блок)
DO $$ BEGIN
    CREATE TYPE subscriptionplan AS ENUM ('free', 'pro');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE paymentstatus AS ENUM ('pending', 'succeeded', 'canceled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE verdict AS ENUM ('worth_looking', 'caution', 'skip');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE inspectionstage AS ENUM ('draft', 'pre_inspection', 'post_inspection');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE listingstatus AS ENUM ('active', 'sold', 'removed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE changetype AS ENUM ('price_drop', 'price_rise', 'sold', 'removed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- users
CREATE TABLE IF NOT EXISTS users (
    id                            SERIAL PRIMARY KEY,
    telegram_id                   INTEGER UNIQUE,
    email                         VARCHAR(255) UNIQUE,
    email_verified                BOOLEAN DEFAULT FALSE NOT NULL,
    email_verification_code       VARCHAR(16),
    email_verification_expires_at TIMESTAMP,
    email_verification_sent_at    TIMESTAMP,
    password_reset_token          VARCHAR(64) UNIQUE,
    password_reset_expires_at     TIMESTAMP,
    phone_number                  VARCHAR(32) UNIQUE,
    phone_verified                BOOLEAN DEFAULT FALSE NOT NULL,
    password_hash                 VARCHAR(255),
    session_token                 VARCHAR(64) UNIQUE,
    session_issued_at             TIMESTAMP,
    session_expires_at            TIMESTAMP,
    subscription_plan             subscriptionplan DEFAULT 'free' NOT NULL,
    subscription_until            TIMESTAMP,
    inspections_this_month        INTEGER DEFAULT 0 NOT NULL,
    month_reset_key               VARCHAR(7),
    created_at                    TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id);
CREATE INDEX IF NOT EXISTS ix_users_email       ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_phone       ON users (phone_number);
CREATE INDEX IF NOT EXISTS ix_users_session     ON users (session_token);
CREATE INDEX IF NOT EXISTS ix_users_reset_token ON users (password_reset_token);

-- payments
CREATE TABLE IF NOT EXISTS payments (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    amount_rub          INTEGER NOT NULL,
    plan                subscriptionplan NOT NULL,
    status              paymentstatus DEFAULT 'pending' NOT NULL,
    yookassa_payment_id VARCHAR(64) UNIQUE,
    created_at          TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_payments_user_id ON payments (user_id);

-- processed_webhook_events
CREATE TABLE IF NOT EXISTS processed_webhook_events (
    id         SERIAL PRIMARY KEY,
    provider   VARCHAR(32) NOT NULL,
    event_key  VARCHAR(255) NOT NULL UNIQUE,
    payload    JSONB,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_webhook_provider  ON processed_webhook_events (provider);
CREATE INDEX IF NOT EXISTS ix_webhook_event_key ON processed_webhook_events (event_key);

-- inspections
CREATE TABLE IF NOT EXISTS inspections (
    id                   SERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL REFERENCES users(id),
    stage                inspectionstage DEFAULT 'draft' NOT NULL,
    listing_url          VARCHAR(1024),
    platform             VARCHAR(64),
    brand                VARCHAR(128),
    model                VARCHAR(128),
    year                 INTEGER,
    mileage_km           INTEGER,
    price_rub            INTEGER,
    engine               VARCHAR(256),
    transmission         VARCHAR(128),
    drive                VARCHAR(64),
    body_type            VARCHAR(64),
    color                VARCHAR(64),
    vin                  VARCHAR(32),
    description          TEXT,
    user_preferences     TEXT,
    listing_repairs      TEXT,
    pre_defects          TEXT,
    post_defects         TEXT,
    post_notes           TEXT,
    photo_paths          JSONB,
    photos_metadata      JSONB,
    observed_defects     JSONB,
    is_reseller          BOOLEAN DEFAULT FALSE NOT NULL,
    target_resale_price  INTEGER,
    final_recommendation VARCHAR(32),
    verdict              verdict,
    pre_report           JSONB,
    post_report          JSONB,
    parts_pricing        JSONB,
    repair_min_rub       INTEGER,
    repair_max_rub       INTEGER,
    created_at           TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at           TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_inspections_user_id ON inspections (user_id);

-- vin_checks
CREATE TABLE IF NOT EXISTS vin_checks (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    inspection_id INTEGER REFERENCES inspections(id),
    vin           VARCHAR(32) NOT NULL,
    report_uid    VARCHAR(128),
    summary       TEXT,
    report_data   JSONB,
    created_at    TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_vin_checks_user_id ON vin_checks (user_id);
CREATE INDEX IF NOT EXISTS ix_vin_checks_vin     ON vin_checks (vin);

-- monitored_listings
CREATE TABLE IF NOT EXISTS monitored_listings (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    inspection_id   INTEGER REFERENCES inspections(id),
    url             VARCHAR(1024) NOT NULL,
    platform        VARCHAR(64),
    last_price      INTEGER,
    last_status     listingstatus DEFAULT 'active' NOT NULL,
    last_checked_at TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW() NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_monitored_listings_user_id       ON monitored_listings (user_id);
CREATE INDEX IF NOT EXISTS ix_monitored_listings_inspection_id ON monitored_listings (inspection_id);

-- listing_change_events
CREATE TABLE IF NOT EXISTS listing_change_events (
    id                   SERIAL PRIMARY KEY,
    monitored_listing_id INTEGER NOT NULL REFERENCES monitored_listings(id),
    change_type          changetype NOT NULL,
    old_value            VARCHAR(256),
    new_value            VARCHAR(256),
    created_at           TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_listing_change_events_monitored_id ON listing_change_events (monitored_listing_id);

-- alembic version (чтобы alembic не пытался мигрировать с нуля)
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
