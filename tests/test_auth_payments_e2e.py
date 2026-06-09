import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import routes as api_routes
from app.main import app
from app.models import Payment, PaymentStatus, SubscriptionPlan, User
from app.schemas import ParseListingRequest, VehicleInput
from app.services.auth import COOKIE_NAME


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings

    db_file = tmp_path / "e2e_auth_payments.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_db_url, echo=False)
    test_sessionmaker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(settings, "database_url", test_db_url)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "async_session", test_sessionmaker)

    async def _no_external_enrichment(
        report,
        vehicle,
        defects,
        user_preferences,
        listing_repairs,
    ):
        return report

    monkeypatch.setattr(inspections, "_enrich_report", _no_external_enrichment)

    with TestClient(app) as client:
        yield client

    asyncio.run(test_engine.dispose())


def _run(coro):
    return asyncio.run(coro)


def _inspection_payload() -> dict:
    return {
        "vehicle": {
            "brand": "Toyota",
            "model": "Corolla",
            "year": 2016,
            "mileage_km": 150000,
            "price_rub": 900000,
        },
        "pre_defects": "скрип в подвеске",
    }


def _cookie_headers(session_token: str) -> dict[str, str]:
    return {"Cookie": f"{COOKIE_NAME}={session_token}"}


def _register(client: TestClient, email: str, password: str = "strongpass123") -> tuple[str, str]:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200
    session_token = resp.cookies.get(COOKIE_NAME)
    assert session_token
    jwt_token = resp.json()["token"]
    assert jwt_token
    return session_token, jwt_token


async def _load_user(email: str) -> User:
    import app.database as database

    async with database.async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        assert user is not None
        return user


async def _create_payment_for_user(
    user_id: int, yookassa_payment_id: str, status: PaymentStatus = PaymentStatus.PENDING
) -> int:
    import app.database as database

    async with database.async_session() as session:
        payment = Payment(
            user_id=user_id,
            amount_rub=990,
            plan=SubscriptionPlan.PRO,
            status=status,
            yookassa_payment_id=yookassa_payment_id,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment.id


async def _load_payment(payment_id: int) -> Payment:
    import app.database as database

    async with database.async_session() as session:
        payment = await session.get(Payment, payment_id)
        assert payment is not None
        return payment


def test_auth_session_cookie_rotation_and_bearer_fallback(api_client: TestClient):
    email = "auth-flow@example.com"
    password = "strongpass123"

    initial_cookie, _ = _register(api_client, email=email, password=password)
    me_resp = api_client.get("/api/v1/auth/me", headers=_cookie_headers(initial_cookie))
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    rotated_cookie = login_resp.cookies.get(COOKIE_NAME)
    assert rotated_cookie
    assert rotated_cookie != initial_cookie
    bearer = login_resp.json()["token"]

    old_cookie_resp = api_client.get("/api/v1/auth/me", headers=_cookie_headers(initial_cookie))
    assert old_cookie_resp.status_code == 401

    new_cookie_resp = api_client.get("/api/v1/auth/me", headers=_cookie_headers(rotated_cookie))
    assert new_cookie_resp.status_code == 200
    assert new_cookie_resp.json()["email"] == email

    api_client.cookies.clear()
    bearer_resp = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert bearer_resp.status_code == 200
    assert bearer_resp.json()["email"] == email


def test_auth_rejects_invalid_session_and_bearer(api_client: TestClient):
    resp = api_client.get(
        "/api/v1/auth/me",
        headers=_cookie_headers("invalid-session-token")
        | {"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp.status_code == 401
    assert "Требуется авторизация" in resp.json()["detail"]


def test_email_verification_dev_fallback_returns_test_code(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.config import settings

    session_cookie, _ = _register(api_client, email="verify-dev@example.com")
    headers = {"Cookie": f"{COOKIE_NAME}={session_cookie}"}
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_sender_email", "")

    resp = api_client.post(
        "/api/v1/auth/verification/request",
        json={"channel": "email"},
        headers=headers,
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["channel"] == "email"
    assert "fallback" in payload["message"].lower() or "код" in payload["message"].lower()


def test_email_verification_production_requires_smtp(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from app.config import settings

    session_cookie, _ = _register(api_client, email="verify-prod@example.com")
    headers = {"Cookie": f"{COOKIE_NAME}={session_cookie}"}
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_sender_email", "")

    resp = api_client.post(
        "/api/v1/auth/verification/request",
        json={"channel": "email"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "production" in resp.json()["detail"].lower()


def test_payment_webhook_is_idempotent_and_ignores_unknown_or_wrong_events(
    api_client: TestClient,
):
    email = "billing-security@example.com"
    _register(api_client, email=email)
    user = _run(_load_user(email))
    payment_id = _run(_create_payment_for_user(user.id, yookassa_payment_id="yk-known-1"))

    ignored_event = api_client.post(
        "/api/v1/payments/webhook/yookassa",
        json={"event": "payment.canceled", "object": {"id": "yk-known-1"}},
    )
    assert ignored_event.status_code == 200

    payment_after_ignored = _run(_load_payment(payment_id))
    user_after_ignored = _run(_load_user(email))
    assert payment_after_ignored.status == PaymentStatus.PENDING
    assert user_after_ignored.subscription_plan == SubscriptionPlan.FREE
    assert user_after_ignored.subscription_until is None

    unknown_payment = api_client.post(
        "/api/v1/payments/webhook/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "yk-unknown"}},
    )
    assert unknown_payment.status_code == 200

    payment_after_unknown = _run(_load_payment(payment_id))
    user_after_unknown = _run(_load_user(email))
    assert payment_after_unknown.status == PaymentStatus.PENDING
    assert user_after_unknown.subscription_plan == SubscriptionPlan.FREE
    assert user_after_unknown.subscription_until is None

    valid_payment = api_client.post(
        "/api/v1/payments/webhook/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "yk-known-1"}},
    )
    assert valid_payment.status_code == 200

    payment_after_success = _run(_load_payment(payment_id))
    user_after_success = _run(_load_user(email))
    assert payment_after_success.status == PaymentStatus.SUCCEEDED
    assert user_after_success.subscription_plan == SubscriptionPlan.PRO
    assert user_after_success.subscription_until is not None
    first_expiration = user_after_success.subscription_until

    replayed_notification = api_client.post(
        "/api/v1/payments/webhook/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "yk-known-1"}},
    )
    assert replayed_notification.status_code == 200

    payment_after_replay = _run(_load_payment(payment_id))
    user_after_replay = _run(_load_user(email))
    assert payment_after_replay.status == PaymentStatus.SUCCEEDED
    assert user_after_replay.subscription_plan == SubscriptionPlan.PRO
    assert user_after_replay.subscription_until is not None
    assert user_after_replay.subscription_until == first_expiration


def test_payment_webhook_rejects_untrusted_source_in_production(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    resp = api_client.post(
        "/api/v1/payments/webhook/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "forged"}},
    )
    assert resp.status_code == 403


def test_payment_webhook_uses_forwarded_ip_allowlist_in_production(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    monkeypatch.setattr(settings, "yookassa_webhook_allowlist", "203.0.113.0/24")

    trusted_chain_resp = api_client.post(
        "/api/v1/payments/webhook/yookassa",
        headers={"X-Forwarded-For": "203.0.113.5"},
        json={"event": "payment.succeeded", "object": {"id": "yk-forwarded-ok"}},
    )
    assert trusted_chain_resp.status_code == 200

    rejected_chain_resp = api_client.post(
        "/api/v1/payments/webhook/yookassa",
        headers={"X-Forwarded-For": "198.51.100.10"},
        json={"event": "payment.succeeded", "object": {"id": "yk-forwarded-bad"}},
    )
    assert rejected_chain_resp.status_code == 403
    assert "not trusted" in rejected_chain_resp.json()["detail"]


def test_admin_health_and_stats_require_token_and_show_operational_counts(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_api_token", "ops-token")
    monkeypatch.setattr(settings, "task_queue_enabled", True)

    no_token = api_client.get("/api/v1/admin/health")
    assert no_token.status_code == 403

    owner_cookie, _ = _register(api_client, email="ops-owner@example.com")
    _register(api_client, email="ops-second@example.com")
    create_resp = api_client.post(
        "/api/v1/inspections",
        json=_inspection_payload(),
        headers={"Cookie": f"{COOKIE_NAME}={owner_cookie}"},
    )
    assert create_resp.status_code == 200

    owner = _run(_load_user("ops-owner@example.com"))
    _run(
        _create_payment_for_user(
            owner.id,
            yookassa_payment_id="ops-payment-1",
            status=PaymentStatus.SUCCEEDED,
        )
    )

    admin_headers = {"X-Admin-Token": "ops-token"}
    health = api_client.get("/api/v1/admin/health", headers=admin_headers)
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert health.json()["queue_enabled"] is True

    stats = api_client.get("/api/v1/admin/stats", headers=admin_headers)
    assert stats.status_code == 200
    payload = stats.json()
    assert payload["users_total"] == 2
    assert payload["inspections_total"] == 1
    assert payload["payments_total"] == 1
    assert payload["succeeded_payments"] == 1


def test_admin_health_returns_503_when_token_not_configured(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_api_token", "")
    resp = api_client.get("/api/v1/admin/health", headers={"X-Admin-Token": "anything"})
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"]


def test_parse_listing_exposes_support_friendly_proxy_context(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.config import settings
    from app.services.parsers.base import ParsedListing

    session_cookie, _ = _register(api_client, email="support-flow@example.com")
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    async def _fake_parse_listing(_url: str) -> ParsedListing:
        return ParsedListing(
            platform="avito",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error="proxy auth failed",
            parse_status="transient_error",
            parse_reason="proxy_auth_failed",
            action_required="check_proxy_credentials",
            listing_repairs=[],
        )

    monkeypatch.setattr(api_routes, "parse_listing_url", _fake_parse_listing)
    response = api_client.post(
        "/api/v1/parse-listing",
        json=ParseListingRequest(url="https://www.avito.ru/items/42").model_dump(mode="json"),
        headers={"Cookie": f"{COOKIE_NAME}={session_cookie}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["parse_ok"] is False
    assert data["parse_status"] == "transient_error"
    assert data["parse_reason"] == "proxy_auth_failed"
    assert data["action_required"] == "check_proxy_credentials"


def test_register_initializes_email_verification_as_pending(api_client: TestClient):
    email = "verify-pending@example.com"
    _register(api_client, email=email)
    user = _run(_load_user(email))
    assert user.email_verified is False
    assert user.email_verification_code is None
    assert user.email_verification_expires_at is None


def test_parse_listing_requires_authenticated_session(api_client: TestClient):
    unauthorized = api_client.post(
        "/api/v1/parse-listing",
        json={"url": "https://auto.drom.ru/some-car"},
    )
    assert unauthorized.status_code == 401


def test_tasks_endpoint_hides_foreign_task_ids(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.api.routes as routes_api

    session_cookie, _ = _register(api_client, email="task-owner@example.com")
    headers = {"Cookie": f"{COOKIE_NAME}={session_cookie}"}

    async def _fake_status(_task_id: str):
        return {
            "task_id": "task-foreign",
            "task": "vin_check",
            "status": "queued",
            "owner_id": 999,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "result": None,
            "error": None,
        }

    monkeypatch.setattr(routes_api, "get_task_status", _fake_status)
    resp = api_client.get("/api/v1/tasks/task-foreign", headers=headers)
    assert resp.status_code == 404


def test_free_plan_limit_blocks_excess_inspections(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.config import settings

    monkeypatch.setattr(settings, "free_inspections_per_month", 1)
    session_cookie, _ = _register(api_client, email="limit-check@example.com")
    headers = {"Cookie": f"{COOKIE_NAME}={session_cookie}"}

    first = api_client.post("/api/v1/inspections", json=_inspection_payload(), headers=headers)
    assert first.status_code == 200

    second = api_client.post("/api/v1/inspections", json=_inspection_payload(), headers=headers)
    assert second.status_code == 402
    assert "Лимит бесплатного тарифа" in second.json()["detail"]

    me = api_client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["inspections_this_month"] == 1


def test_user_cannot_access_another_users_inspection(api_client: TestClient):
    user_a_cookie, _ = _register(api_client, email="owner-a@example.com")
    user_b_cookie, _ = _register(api_client, email="owner-b@example.com")

    create_resp = api_client.post(
        "/api/v1/inspections",
        json=_inspection_payload(),
        headers={"Cookie": f"{COOKIE_NAME}={user_a_cookie}"},
    )
    assert create_resp.status_code == 200
    inspection_id = create_resp.json()["id"]

    forbidden = api_client.get(
        f"/api/v1/inspections/{inspection_id}",
        headers={"Cookie": f"{COOKIE_NAME}={user_b_cookie}"},
    )
    assert forbidden.status_code == 404


def test_api_smoke_health_auth_and_inspection_checklist(api_client: TestClient):
    health = api_client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    session_cookie, _ = _register(api_client, email="smoke-api@example.com")
    headers = {"Cookie": f"{COOKIE_NAME}={session_cookie}"}

    created = api_client.post("/api/v1/inspections", json=_inspection_payload(), headers=headers)
    assert created.status_code == 200
    inspection_id = created.json()["id"]

    checklist = api_client.get(f"/api/v1/inspections/{inspection_id}/checklist", headers=headers)
    assert checklist.status_code == 200
    assert isinstance(checklist.json()["checklist"], list)
    assert checklist.json()["checklist"]


def test_vin_check_async_returns_task_and_status(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.api.routes as routes_api

    session_cookie, _ = _register(api_client, email="vin-async@example.com")
    headers = {"Cookie": f"{COOKIE_NAME}={session_cookie}"}

    async def _fake_enqueue(task_name: str, payload: dict, *, owner_id: int | None = None):
        assert task_name == "vin_check"
        assert payload["vin"] == "XTA12345678901234"
        assert owner_id is not None
        return "task-123"

    async def _fake_status(task_id: str):
        assert task_id == "task-123"
        return {
            "task_id": "task-123",
            "task": "vin_check",
            "status": "queued",
            "owner_id": 1,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "result": None,
            "error": None,
        }

    monkeypatch.setattr(routes_api, "enqueue_tracked_task", _fake_enqueue)
    monkeypatch.setattr(routes_api, "get_task_status", _fake_status)

    queued = api_client.post(
        "/api/v1/vin/check/async",
        json={"vin": "XTA12345678901234"},
        headers=headers,
    )
    assert queued.status_code == 202
    assert queued.json()["task_id"] == "task-123"
    assert queued.json()["status"] == "queued"

    status = api_client.get("/api/v1/tasks/task-123", headers=headers)
    assert status.status_code == 200
    assert status.json()["task"] == "vin_check"


def test_email_verification_flow(api_client: TestClient):
    session_cookie, _ = _register(api_client, email="verify-flow@example.com")
    headers = {"Cookie": f"{COOKIE_NAME}={session_cookie}"}

    request_resp = api_client.post(
        "/api/v1/auth/verification/request",
        json={"channel": "email"},
        headers=headers,
    )
    assert request_resp.status_code == 200
    assert request_resp.json()["ok"] is True

    user = _run(_load_user("verify-flow@example.com"))
    assert user.email_verification_code

    confirm_resp = api_client.post(
        "/api/v1/auth/verification/confirm",
        json={"channel": "email", "code": user.email_verification_code},
        headers=headers,
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["email_verified"] is True


def test_admin_support_status_contract(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_api_token", "test-admin-token")
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8,192.168.0.0/16")

    denied = api_client.get("/api/v1/admin/support-status")
    assert denied.status_code == 403

    ok = api_client.get(
        "/api/v1/admin/support-status",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["trusted_proxy_hops"] == 2
    assert payload["trusted_proxy_cidrs"] == ["10.0.0.0/8", "192.168.0.0/16"]
    assert "queue_enabled" in payload
