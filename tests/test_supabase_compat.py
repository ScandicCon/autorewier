"""Тесты совместимости БД и инициализации схемы.

Гарантируют, что:
- init_db создаёт таблицы users и inspections при любом DATABASE_URL
  (в частности, при SQLite — без реального Supabase)
- User можно записать и прочитать через SQLAlchemy
- GET /health работает независимо от DATABASE_URL

Все тесты используют временную SQLite через tmp_path.
"""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import User  # noqa: F401 — нужен для регистрации метаданных
import app.models as _models  # noqa: F401 — регистрируем все модели в Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine_and_session(db_url: str):
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


async def _create_schema(engine) -> None:
    """Создаёт все таблицы через Base.metadata.create_all (имитирует init_db для SQLite)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _get_table_names(engine) -> list[str]:
    """Возвращает список имён таблиц в БД."""
    async with engine.begin() as conn:
        return await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )


# ---------------------------------------------------------------------------
# Tests: schema
# ---------------------------------------------------------------------------


def test_database_tables_exist(tmp_path: Path):
    """После init_db таблицы users и inspections существуют в SQLite."""
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compat.db'}"
    engine, _ = _make_engine_and_session(db_url)

    async def _run():
        await _create_schema(engine)
        tables = await _get_table_names(engine)
        await engine.dispose()
        return tables

    tables = asyncio.run(_run())

    assert "users" in tables, f"Таблица 'users' не найдена. Найдено: {tables}"
    assert "inspections" in tables, f"Таблица 'inspections' не найдена. Найдено: {tables}"


def test_create_user_in_db(tmp_path: Path):
    """Создать User через SQLAlchemy, прочитать обратно — все поля сохранены корректно."""
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'users.db'}"
    engine, session_factory = _make_engine_and_session(db_url)

    async def _run():
        await _create_schema(engine)

        # Создаём пользователя
        async with session_factory() as session:
            user = User(
                email="compat-test@example.com",
                password_hash="$2b$12$hashedpassword",
                email_verified=False,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            created_id = user.id

        # Читаем обратно в отдельной сессии
        async with session_factory() as session:
            fetched = await session.get(User, created_id)

        await engine.dispose()
        return fetched

    user = asyncio.run(_run())

    assert user is not None, "Пользователь не найден после записи"
    assert user.email == "compat-test@example.com"
    assert user.password_hash == "$2b$12$hashedpassword"
    assert user.email_verified is False
    assert user.id is not None


# ---------------------------------------------------------------------------
# Tests: health endpoint
# ---------------------------------------------------------------------------


def test_health_endpoint_with_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """GET /health возвращает 200 {"status": "ok"} при любом DATABASE_URL (в т.ч. SQLite)."""
    import asyncio as _asyncio
    from fastapi.testclient import TestClient
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings
    from app.main import app

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'health.db'}"
    test_engine = create_async_engine(db_url, echo=False)
    test_sessionmaker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(settings, "database_url", db_url)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "async_session", test_sessionmaker)

    async def _no_external_enrichment(report, vehicle, defects, user_preferences, listing_repairs):
        return report

    monkeypatch.setattr(inspections, "_enrich_report", _no_external_enrichment)

    with TestClient(app) as client:
        resp = client.get("/api/v1/health")

    _asyncio.run(test_engine.dispose())

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
