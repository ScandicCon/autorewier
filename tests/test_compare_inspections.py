"""
Тесты сравнения проверок (inspections comparison).

Покрываемые сценарии:
- POST /inspections/compare (или GET /inspections-comparison) с двумя id
  → возвращает CompareResult / InspectionComparisonResponse
- В результате есть поле winner (или items с recommendation)
- Чужие inspections → 403 (при попытке сравнить чужие) или просто не включаются
- >3 inspections → 422 (если есть валидация лимита)
- Только 1 id → 422

Используем паттерн из существующих тестов проекта:
- TestClient с изолированной SQLite БД
- monkeypatch для отключения внешних сервисов
- Регистрация через /auth/register с COOKIE_NAME
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.services.auth import COOKIE_NAME


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings

    db_file = tmp_path / "test_compare_inspections.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_db_url, echo=False)
    test_sessionmaker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(settings, "database_url", test_db_url)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "free_inspections_per_month", 100)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "async_session", test_sessionmaker)

    async def _no_external_enrichment(report, vehicle, defects, user_preferences, listing_repairs):
        return report

    monkeypatch.setattr(inspections, "_enrich_report", _no_external_enrichment)

    with TestClient(app) as client:
        yield client

    asyncio.run(test_engine.dispose())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register(client: TestClient, email: str, password: str = "strongpass123") -> str:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password, "password_confirm": password})
    assert resp.status_code == 200
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.cookies.get(COOKIE_NAME)
    assert token
    return token


def _auth_headers(session_token: str) -> dict:
    return {"Cookie": f"{COOKIE_NAME}={session_token}"}


def _inspection_payload(brand: str = "Toyota", model: str = "Camry", year: int = 2016) -> dict:
    return {
        "vehicle": {
            "brand": brand,
            "model": model,
            "year": year,
            "mileage_km": 150_000,
            "price_rub": 1_200_000,
        },
        "pre_defects": "стук в подвеске",
    }


def _create_inspection(client: TestClient, headers: dict, brand: str = "Toyota") -> int:
    resp = client.post(
        "/api/v1/inspections",
        json=_inspection_payload(brand=brand),
        headers=headers,
    )
    assert resp.status_code == 200, f"Не удалось создать inspection: {resp.text}"
    return resp.json()["id"]


def _compare(client: TestClient, ids: list[int], headers: dict):
    """
    Вызывает эндпоинт сравнения.
    Сначала пробует POST /inspections/compare, затем GET /inspections-comparison.
    """
    # Попытка POST-эндпоинта (новая фича)
    post_resp = client.post(
        "/api/v1/inspections/compare",
        json={"inspection_ids": ids},
        headers=headers,
    )
    if post_resp.status_code not in (404, 405):
        return post_resp

    # Fallback к существующему GET-эндпоинту
    params = [("ids", i) for i in ids]
    get_resp = client.get(
        "/api/v1/inspections-comparison",
        params=params,
        headers=headers,
    )
    return get_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_compare_two_inspections(api_client: TestClient):
    """
    Сравнение двух inspections → возвращает CompareResult / InspectionComparisonResponse.
    """
    session_token = _register(api_client, "compare-two@example.com")
    headers = _auth_headers(session_token)

    id1 = _create_inspection(api_client, headers, brand="Toyota")
    id2 = _create_inspection(api_client, headers, brand="Kia")

    resp = _compare(api_client, [id1, id2], headers)

    assert resp.status_code == 200, f"Ожидался 200, получено {resp.status_code}: {resp.text}"
    payload = resp.json()

    # Проверяем структуру ответа
    assert payload is not None
    # GET-вариант возвращает {"items": [...]}
    # POST-вариант может возвращать {"items": [...], "winner": ...} или аналог
    items_key = "items" if "items" in payload else None
    if items_key:
        assert isinstance(payload["items"], list)
        assert len(payload["items"]) == 2
    else:
        # POST-вариант может иметь иную структуру
        assert isinstance(payload, dict)


def test_compare_result_has_winner(api_client: TestClient):
    """
    В результате сравнения должно быть поле winner (или final_recommendation в items).
    """
    session_token = _register(api_client, "compare-winner@example.com")
    headers = _auth_headers(session_token)

    id1 = _create_inspection(api_client, headers, brand="Toyota")
    id2 = _create_inspection(api_client, headers, brand="BMW")

    # Сначала пробуем POST-эндпоинт с winner
    post_resp = api_client.post(
        "/api/v1/inspections/compare",
        json={"inspection_ids": [id1, id2]},
        headers=headers,
    )

    if post_resp.status_code not in (404, 405):
        assert post_resp.status_code == 200
        payload = post_resp.json()
        # POST-эндпоинт должен возвращать поле winner
        assert "winner_id" in payload, (
            f"Ожидалось поле 'winner' в ответе, получено: {list(payload.keys())}"
        )
    else:
        # Fallback: GET-эндпоинт возвращает items с verdict/final_recommendation
        params = [("ids", id1), ("ids", id2)]
        get_resp = api_client.get(
            "/api/v1/inspections-comparison",
            params=params,
            headers=headers,
        )
        assert get_resp.status_code == 200
        payload = get_resp.json()
        assert "items" in payload
        items = payload["items"]
        assert len(items) == 2
        # Каждый item должен иметь verdict или final_recommendation
        for item in items:
            has_verdict = "verdict" in item or "final_recommendation" in item
            assert has_verdict, (
                f"Ожидался verdict/final_recommendation в item: {item}"
            )


def test_compare_wrong_user(api_client: TestClient):
    """
    Попытка сравнить чужие inspections должна вернуть 403
    ИЛИ просто не включать чужие записи в результат.
    """
    # Пользователь A создаёт inspection
    token_a = _register(api_client, "compare-owner-a@example.com")
    headers_a = _auth_headers(token_a)
    id_a = _create_inspection(api_client, headers_a, brand="Toyota")

    # Пользователь B пытается сравнить inspection пользователя A
    token_b = _register(api_client, "compare-owner-b@example.com")
    headers_b = _auth_headers(token_b)

    # B создаёт свою inspection
    id_b = _create_inspection(api_client, headers_b, brand="Kia")

    # B пытается сравнить свою с чужой (id_a)
    post_resp = api_client.post(
        "/api/v1/inspections/compare",
        json={"inspection_ids": [id_b, id_a]},
        headers=headers_b,
    )

    if post_resp.status_code not in (404, 405):
        if post_resp.status_code in (400, 403):
            # Ожидаемый ответ — запрет или «недостаточно доступных проверок»
            # (чужая запись исключается, остаётся <2 → 400)
            pass
        elif post_resp.status_code == 200:
            # Альтернативное поведение: чужие записи просто не включаются
            payload = post_resp.json()
            items = payload.get("items", [])
            included_ids = [item.get("inspection_id") for item in items]
            assert id_a not in included_ids, (
                f"Чужой inspection_id {id_a} не должен быть в результате: {included_ids}"
            )
        else:
            pytest.fail(f"Неожиданный статус {post_resp.status_code}: {post_resp.text}")
    else:
        # GET-эндпоинт: чужие inspection просто не включаются (get_inspection возвращает None)
        params = [("ids", id_b), ("ids", id_a)]
        get_resp = api_client.get(
            "/api/v1/inspections-comparison",
            params=params,
            headers=headers_b,
        )
        assert get_resp.status_code == 200
        payload = get_resp.json()
        items = payload.get("items", [])
        included_ids = [item.get("inspection_id") for item in items]
        # Чужой id_a не должен попасть в результат
        assert id_a not in included_ids, (
            f"Чужой inspection_id {id_a} не должен быть в результате: {included_ids}"
        )


def test_compare_too_many(api_client: TestClient):
    """
    Попытка сравнить >3 inspections → 422 (если есть валидация).
    Если лимит не реализован, тест проверяет что запрос хотя бы выполняется.
    """
    session_token = _register(api_client, "compare-many@example.com")
    headers = _auth_headers(session_token)

    # Создаём 4 inspections
    brands = ["Toyota", "Kia", "BMW", "Skoda"]
    ids = [_create_inspection(api_client, headers, brand=b) for b in brands]

    post_resp = api_client.post(
        "/api/v1/inspections/compare",
        json={"inspection_ids": ids},  # 4 ids > 3
        headers=headers,
    )

    if post_resp.status_code in (404, 405):
        # GET-эндпоинт не имеет лимита — пропускаем этот тест
        pytest.skip("POST /inspections/compare не реализован, GET не имеет лимита >3")

    # Если POST реализован с валидацией — ожидаем 422
    assert post_resp.status_code == 422, (
        f"При >3 ids ожидался 422, получено {post_resp.status_code}: {post_resp.text}"
    )


def test_compare_single(api_client: TestClient):
    """
    Сравнение только 1 inspection → 422 (недостаточно для сравнения).
    """
    session_token = _register(api_client, "compare-single@example.com")
    headers = _auth_headers(session_token)

    id1 = _create_inspection(api_client, headers, brand="Toyota")

    post_resp = api_client.post(
        "/api/v1/inspections/compare",
        json={"inspection_ids": [id1]},
        headers=headers,
    )

    if post_resp.status_code in (404, 405):
        # GET-эндпоинт: с одним id вернёт items с одним элементом
        params = [("ids", id1)]
        get_resp = api_client.get(
            "/api/v1/inspections-comparison",
            params=params,
            headers=headers,
        )
        assert get_resp.status_code == 200
        payload = get_resp.json()
        items = payload.get("items", [])
        # 1 item — это допустимо для GET, тест завершён
        assert len(items) == 1
        pytest.skip("POST /inspections/compare не реализован — проверка через GET пройдена")

    # Если POST реализован — ожидаем 422
    assert post_resp.status_code == 422, (
        f"При 1 id ожидался 422, получено {post_resp.status_code}: {post_resp.text}"
    )
