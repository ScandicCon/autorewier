from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


class Base(DeclarativeBase):
    pass


_db_host = (urlparse(settings.database_url).hostname or "").lower()
_is_supabase_pooler = "pooler.supabase.com" in _db_host and "asyncpg" in settings.database_url
_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if _is_supabase_pooler:
    # Supabase pooler is more stable without SQLAlchemy connection pooling,
    # and asyncpg should avoid statement caching behind a pooler.
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs["connect_args"] = {"statement_cache_size": 0, "command_timeout": 60}

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def _migrate_sqlite(conn) -> None:
    """Добавляет колонки в существующую SQLite без Alembic."""
    migrations = [
        "ALTER TABLE users ADD COLUMN email VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN email_verification_code VARCHAR(16)",
        "ALTER TABLE users ADD COLUMN email_verification_expires_at DATETIME",
        "ALTER TABLE users ADD COLUMN phone_number VARCHAR(32)",
        "ALTER TABLE users ADD COLUMN phone_verified BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN session_token VARCHAR(64)",
        "ALTER TABLE users ADD COLUMN subscription_plan VARCHAR(16) DEFAULT 'free'",
        "ALTER TABLE users ADD COLUMN subscription_until DATETIME",
        "ALTER TABLE users ADD COLUMN inspections_this_month INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN month_reset_key VARCHAR(7)",
        "ALTER TABLE users ADD COLUMN session_issued_at DATETIME",
        "ALTER TABLE users ADD COLUMN session_expires_at DATETIME",
        "ALTER TABLE inspections ADD COLUMN parts_pricing JSON",
        "ALTER TABLE inspections ADD COLUMN user_preferences TEXT",
        "ALTER TABLE inspections ADD COLUMN listing_repairs TEXT",
        "ALTER TABLE inspections ADD COLUMN photos_metadata JSON",
        "ALTER TABLE inspections ADD COLUMN observed_defects JSON",
        "ALTER TABLE inspections ADD COLUMN final_recommendation VARCHAR(32)",
        # Added in v0.2 — email verification + password reset
        "ALTER TABLE users ADD COLUMN email_verification_sent_at DATETIME",
        "ALTER TABLE users ADD COLUMN password_reset_token VARCHAR(64)",
        "ALTER TABLE users ADD COLUMN password_reset_expires_at DATETIME",
        # Added in v0.2 — monitored listings
        """CREATE TABLE IF NOT EXISTS monitored_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            listing_url TEXT NOT NULL,
            listing_source VARCHAR(32),
            last_price_rub INTEGER,
            last_checked_at DATETIME,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS listing_change_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monitored_listing_id INTEGER NOT NULL REFERENCES monitored_listings(id),
            change_type VARCHAR(32),
            old_value TEXT,
            new_value TEXT,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
    ]
    for sql in migrations:
        try:
            await conn.execute(text(sql))
        except Exception:
            pass


async def init_db() -> None:
    from app import models  # noqa: F401

    if "postgresql" in settings.database_url:
        # For PostgreSQL/Supabase: tables are created via alembic migrations,
        # not at startup. Supabase Transaction pooler (port 6543) drops
        # connections before SQLAlchemy can run its init query — so we skip
        # create_all entirely and let alembic handle schema management.
        import logging as _logging
        _logging.getLogger(__name__).info(
            "PostgreSQL detected — skipping create_all. "
            "Run 'alembic upgrade head' to create/update tables."
        )
        return

    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    if db_path and not db_path.startswith(":"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in settings.database_url:
            await _migrate_sqlite(conn)
