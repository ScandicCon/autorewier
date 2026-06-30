"""Тесты поиска б/у детали по фото (POST /api/v1/parts/find-by-photo).

В тест-окружении ключ OpenRouter занулён (conftest), а ALLOW_MOCK_SERVICES=true,
поэтому эндпоинт работает в демо-режиме без сети и возвращает детерминированный
результат. Боевой путь (vision + поиск Авито) проверяется отдельным юнит-тестом
сервиса с замоканными зависимостями.
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app

# Минимальный валидный PNG 1x1.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    from app.config import settings

    db_file = tmp_path / "part_finder.db"
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
    return {"X-Telegram-Id": "900778"}


def test_find_part_demo_returns_offers(api_client: TestClient):
    resp = api_client.post(
        "/api/v1/parts/find-by-photo",
        headers=_auth_headers(),
        files=[("file", ("part.png", _PNG_1x1, "image/png"))],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["demo"] is True
    assert "identification" in data
    assert data["identification"]["part_name"]
    assert data["identification"]["search_query"]
    assert isinstance(data["offers"], list)
    assert len(data["offers"]) >= 1
    assert all(o["url"].startswith("http") for o in data["offers"])
    assert data["disclaimer"]


def test_find_part_with_hint(api_client: TestClient):
    resp = api_client.post(
        "/api/v1/parts/find-by-photo",
        headers=_auth_headers(),
        files=[("file", ("part.png", _PNG_1x1, "image/png"))],
        data={"hint": "Toyota Camry"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "Toyota Camry" in data["identification"]["search_query"]


def test_find_part_rejects_non_image(api_client: TestClient):
    resp = api_client.post(
        "/api/v1/parts/find-by-photo",
        headers=_auth_headers(),
        files=[("file", ("notes.txt", b"hello", "text/plain"))],
    )
    assert resp.status_code == 400


def test_find_part_requires_auth(api_client: TestClient):
    resp = api_client.post(
        "/api/v1/parts/find-by-photo",
        files=[("file", ("part.png", _PNG_1x1, "image/png"))],
    )
    assert resp.status_code in (401, 403)


def test_service_real_path_with_mocked_deps(monkeypatch: pytest.MonkeyPatch):
    """Боевой путь: vision распознал деталь → поиск вернул объявления."""
    from app.config import settings
    from app.schemas import AvitoPartOffer
    import app.services.part_finder as pf

    # Включаем «боевой» режим (llm_enabled зависит от наличия ключа).
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key", raising=False)

    async def fake_identify(photo_data_url, hint=None):
        return pf.PartIdentification(
            part_name="Зеркало боковое",
            category="Кузов",
            vehicle_hint="Kia Rio",
            search_query="зеркало боковое Kia Rio",
            keywords=["зеркало", "боковое"],
            confidence=82,
        )

    async def fake_search(query):
        return [
            AvitoPartOffer(title="Зеркало Kia Rio левое", price_rub=3200, url="https://www.avito.ru/x"),
            AvitoPartOffer(title="Зеркало Kia Rio правое", price_rub=3500, url="https://www.avito.ru/y"),
        ]

    monkeypatch.setattr(pf, "_identify_part", fake_identify)
    monkeypatch.setattr(pf, "search_avito_parts", fake_search)

    result = asyncio.run(pf.find_parts_by_photo("data:image/png;base64,xxx"))

    assert result.demo is False
    assert result.identification.part_name == "Зеркало боковое"
    assert result.identification.confidence == 82
    assert len(result.offers) == 2
    assert "avito.ru" in result.search_url


def test_service_search_failure_is_graceful(monkeypatch: pytest.MonkeyPatch):
    """Если поиск Авито упал — отдаём распознавание без объявлений, без падения."""
    from app.config import settings
    import app.services.part_finder as pf

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key", raising=False)

    async def fake_identify(photo_data_url, hint=None):
        return pf.PartIdentification(
            part_name="Бампер передний",
            search_query="бампер передний",
            confidence=70,
        )

    async def boom(query):
        raise RuntimeError("captcha")

    monkeypatch.setattr(pf, "_identify_part", fake_identify)
    monkeypatch.setattr(pf, "search_avito_parts", boom)

    result = asyncio.run(pf.find_parts_by_photo("data:image/png;base64,xxx"))
    assert result.offers == []
    assert result.identification.part_name == "Бампер передний"
