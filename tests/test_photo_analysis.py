"""Тесты эндпоинта загрузки и анализа фото авто (POST /photos/analyze).

Без боевого LLM-ключа vision уходит в keyword-фолбэк (см. analyze_photo_urls),
поэтому эндпоинт возвращает корректные ImageFinding и в тест-окружении.
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app

# Минимальный валидный PNG 1x1 (прозрачный).
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    from app.config import settings

    db_file = tmp_path / "photo_analysis.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_db_url, echo=False)
    test_sessionmaker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(settings, "database_url", test_db_url)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "async_session", test_sessionmaker)

    with TestClient(app) as client:
        yield client

    asyncio.run(test_engine.dispose())


def _auth_headers() -> dict[str, str]:
    return {"X-Telegram-Id": "900777"}


def test_analyze_photos_returns_findings(api_client: TestClient):
    resp = api_client.post(
        "/api/v1/photos/analyze",
        headers=_auth_headers(),
        files=[("files", ("front.png", _PNG_1x1, "image/png"))],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    finding = data[0]
    assert "issue" in finding
    assert "confidence" in finding
    assert "source" in finding


def test_analyze_photos_multiple(api_client: TestClient):
    resp = api_client.post(
        "/api/v1/photos/analyze",
        headers=_auth_headers(),
        files=[
            ("files", ("a.png", _PNG_1x1, "image/png")),
            ("files", ("b.png", _PNG_1x1, "image/png")),
        ],
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2


def test_analyze_photos_rejects_too_many(api_client: TestClient):
    files = [("files", (f"p{i}.png", _PNG_1x1, "image/png")) for i in range(6)]
    resp = api_client.post(
        "/api/v1/photos/analyze", headers=_auth_headers(), files=files
    )
    assert resp.status_code == 400


def test_analyze_photos_rejects_non_image(api_client: TestClient):
    resp = api_client.post(
        "/api/v1/photos/analyze",
        headers=_auth_headers(),
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert resp.status_code == 400


def test_analyze_photos_requires_auth(api_client: TestClient):
    resp = api_client.post(
        "/api/v1/photos/analyze",
        files=[("files", ("front.png", _PNG_1x1, "image/png"))],
    )
    assert resp.status_code in (401, 403)
