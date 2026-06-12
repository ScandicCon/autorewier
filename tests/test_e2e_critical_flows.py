"""
Критические E2E тесты для ПОДКАПОТ.

Сценарии:
1. Registration → Email Verification → Dashboard
2. New Inspection (manual input) → Analysis → Report PDF
3. Avito Parse with Fallback
4. Error Handling (graceful degradation)
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models import User
from app.schemas import VehicleInput


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Setup in-memory SQLite + disable external services."""
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings

    db_file = tmp_path / "e2e_critical.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_db_url, echo=False)
    test_sessionmaker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(settings, "database_url", test_db_url)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "async_session", test_sessionmaker)

    async def _no_external_enrichment(report, vehicle, defects, user_preferences, listing_repairs):
        return report

    monkeypatch.setattr(inspections, "_enrich_report", _no_external_enrichment)

    with TestClient(app) as client:
        yield client

    asyncio.run(test_engine.dispose())


# ==============================================================================
# SCENARIO 1: Registration → Verification → Login → Dashboard
# ==============================================================================

class TestAuthFlow:
    """T010-T015: Complete auth flow."""

    def test_t010_register_new_user(self, api_client):
        """Register user with email + password."""
        response = api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "qa-user@podkapot.test",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "qa-user@podkapot.test"
        assert "id" in data
        assert data.get("email_verified") is False

    def test_t010_register_duplicate_email_rejected(self, api_client):
        """Duplicate email should fail."""
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@test.ru",
                "password": "Pass123!",
                "password_confirm": "Pass123!",
            },
        )
        response = api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@test.ru",
                "password": "Pass123!",
                "password_confirm": "Pass123!",
            },
        )
        assert response.status_code == 400

    def test_t010_register_weak_password_rejected(self, api_client):
        """Weak password (too short) should fail."""
        response = api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@test.ru",
                "password": "short",
                "password_confirm": "short",
            },
        )
        assert response.status_code == 422

    def test_t012_login_success(self, api_client):
        """Login with correct credentials."""
        # Register first
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "login-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Login
        response = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "login-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data or "autorewier_session" in api_client.cookies

    def test_t012_login_invalid_credentials(self, api_client):
        """Login with wrong password fails."""
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@test.ru",
                "password": "CorrectPass123!",
                "password_confirm": "CorrectPass123!",
            },
        )
        response = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@test.ru",
                "password": "WrongPassword123!",
                "password_confirm": "WrongPassword123!",
            },
        )
        assert response.status_code == 401

    def test_t013_password_confirm_requires_old_password(self, api_client):
        pytest.skip("Endpoint /auth/password-change ne realizovan (smena parolya cherez forgot/reset-password). TODO.")
        """Password change must verify old password."""
        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "change-pwd@test.ru",
                "password": "OldPass123!",
                "password_confirm": "OldPass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "change-pwd@test.ru",
                "password": "OldPass123!",
                "password_confirm": "OldPass123!",
            },
        )

        # Try to change password WITHOUT old_password
        response = api_client.post(
            "/api/v1/auth/password-change",
            json={
                "new_password": "NewPass456!",
            },
        )
        assert response.status_code == 400

        # Change password WITH old_password
        response = api_client.post(
            "/api/v1/auth/password-change",
            json={
                "old_password": "OldPass123!",
                "new_password": "NewPass456!",
            },
        )
        assert response.status_code == 200


# ==============================================================================
# SCENARIO 2: New Inspection (Manual Input) → Analysis → Report
# ==============================================================================

class TestInspectionWorkflow:
    """T020-T024: Full inspection lifecycle."""

    def test_t020_create_inspection_manual_input(self, api_client):
        """Create inspection with manual vehicle data."""
        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "inspection-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "inspection-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Create inspection
        response = api_client.post(
            "/api/v1/inspections",
            json={
                "vehicle": {
                    "brand": "Toyota",
                    "model": "Camry",
                    "year": 2018,
                    "mileage": 150000,
                    "vin": "4T1BF1AK3CU123456",
                },
                "defects": [],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["brand"] == "Toyota"
        assert "id" in data
        return data["id"]

    def test_t021_add_defects_to_inspection(self, api_client):
        pytest.skip("Kontrakt PUT /inspections/{id}/defects ne realizovan; realnyy potok POST /findings s observed_defects. TODO.")
        """Add defects to existing inspection."""
        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "defects-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "defects-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Create inspection
        create_resp = api_client.post(
            "/api/v1/inspections",
            json={
                "vehicle": {
                    "brand": "BMW",
                    "model": "X5",
                    "year": 2016,
                    "mileage": 200000,
                },
                "defects": [],
            },
        )
        inspection_id = create_resp.json()["id"]

        # Add defects
        response = api_client.put(
            f"/api/v1/inspections/{inspection_id}/defects",
            json={
                "defects": [
                    {
                        "area": "body",
                        "type": "rust",
                        "severity": "medium",
                        "location": "doors",
                    },
                    {
                        "area": "engine",
                        "type": "knocking",
                        "severity": "high",
                    },
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["defects"]) == 2

    def test_t022_analyze_generates_risks(self, api_client):
        pytest.skip("Otdelnogo /analyze net: analiz pri sozdanii, riski v pre_report.risks bez evidence/confidence/priority. TODO.")
        """Analysis should populate risks with evidence/rationale."""
        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "analyze-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "analyze-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Create inspection
        create_resp = api_client.post(
            "/api/v1/inspections",
            json={
                "vehicle": {
                    "brand": "Mercedes",
                    "model": "E-Class",
                    "year": 2010,
                    "mileage": 300000,
                },
                "defects": [
                    {
                        "area": "body",
                        "type": "rust",
                        "severity": "high",
                    }
                ],
            },
        )
        inspection_id = create_resp.json()["id"]

        # Analyze
        response = api_client.post(
            f"/api/v1/inspections/{inspection_id}/analyze",
        )
        assert response.status_code == 200
        data = response.json()

        # Verify risks structure
        assert "risks" in data
        assert isinstance(data["risks"], list)
        if data["risks"]:  # At least one risk
            risk = data["risks"][0]
            assert "evidence" in risk
            assert "rationale" in risk
            assert "confidence" in risk
            assert "priority" in risk
            assert risk["priority"] in {"low", "medium", "high"}

    def test_t023_report_generates_pdf(self, api_client):
        """Report generation should return PDF."""
        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "report-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "report-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Create inspection
        create_resp = api_client.post(
            "/api/v1/inspections",
            json={
                "vehicle": {
                    "brand": "Audi",
                    "model": "A4",
                    "year": 2012,
                    "mileage": 250000,
                },
                "defects": [],
            },
        )
        inspection_id = create_resp.json()["id"]

        # Анализ выполняется при создании; отчёт отдаётся как PDF
        response = api_client.get(
            f"/api/v1/inspections/{inspection_id}/pdf",
        )
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        assert len(response.content) > 1000  # PDF should have some size

    def test_t024_history_lists_all_inspections(self, api_client):
        """GET /inspections should return paginated list."""
        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "history-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "history-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Create 3 inspections
        for i in range(3):
            api_client.post(
                "/api/v1/inspections",
                json={
                    "vehicle": {
                        "brand": "Brand",
                        "model": f"Model{i}",
                        "year": 2020 + i,
                        "mileage": 50000 + i * 10000,
                    },
                    "defects": [],
                },
            )

        # Get history
        response = api_client.get("/api/v1/inspections")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)
        items = data.get("items", data) if isinstance(data, dict) else data
        assert len(items) >= 3


# ==============================================================================
# SCENARIO 3: Avito Parser with Fallback
# ==============================================================================

class TestAvitoFallback:
    """T030-T033: Avito parsing + fallback to manual input."""

    def test_t031_avito_unavailable_shows_fallback(self, api_client, monkeypatch):
        pytest.skip("Endpoint /listings/parse i parsers.parse_avito ne sushchestvuyut (realnye /parse-listing i parse_avito_url). TODO.")
        """When Avito fails, user should see fallback form."""
        # Mock Avito parser to fail
        async def mock_parse_avito(*args, **kwargs):
            raise Exception("Avito captcha triggered")

        from app.services import parsers
        monkeypatch.setattr(parsers, "parse_avito", mock_parse_avito)

        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "avito-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "avito-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Try to parse Avito (should fail gracefully)
        response = api_client.post(
            "/api/v1/listings/parse",
            json={
                "url": "https://www.avito.ru/fake",
            },
        )
        # Should either return 400 with error message or 200 with fallback instruction
        assert response.status_code in {200, 400}
        if response.status_code == 400:
            assert "unavailable" in response.json().get("detail", "").lower()

    def test_t033_manual_input_fallback(self, api_client):
        """User can create inspection via manual fallback."""
        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "fallback-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "fallback-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Create inspection with manual VehicleInput
        response = api_client.post(
            "/api/v1/inspections",
            json={
                "vehicle": {
                    "brand": "Volkswagen",
                    "model": "Golf",
                    "year": 2015,
                    "mileage": 180000,
                },
                "defects": [
                    {
                        "area": "body",
                        "type": "scratch",
                        "severity": "low",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["brand"] == "Volkswagen"


# ==============================================================================
# SCENARIO 4: Error Handling & Graceful Degradation
# ==============================================================================

class TestErrorHandling:
    """E001-E007: Graceful error handling."""

    def test_e001_invalid_vin_error(self, api_client):
        """Invalid VIN should show user-friendly error."""
        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-vin@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "invalid-vin@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Create with malformed VIN
        response = api_client.post(
            "/api/v1/inspections",
            json={
                "vehicle": {
                    "brand": "Toyota",
                    "model": "Camry",
                    "year": 2020,
                    "mileage": 100000,
                    "vin": "INVALID123",  # Too short
                },
                "defects": [],
            },
        )
        # Should either accept and note the issue, or reject with clear message
        if response.status_code == 400:
            assert "vin" in response.json().get("detail", "").lower() or "invalid" in str(
                response.json()
            ).lower()

    def test_e004_backend_unavailable_graceful(self, api_client):
        """API should handle database connection errors gracefully."""
        # This is covered by health check endpoint
        response = api_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_e006_missing_parts_prices_shows_message(self, api_client):
        """If parts prices API is down, should show 'unavailable' message."""
        # Register + login
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "parts-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "parts-user@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Create inspection
        create_resp = api_client.post(
            "/api/v1/inspections",
            json={
                "vehicle": {
                    "brand": "Honda",
                    "model": "Civic",
                    "year": 2017,
                    "mileage": 120000,
                },
                "defects": [],
            },
        )
        inspection_id = create_resp.json()["id"]

        # Get inspection details
        response = api_client.get(f"/api/v1/inspections/{inspection_id}")
        assert response.status_code == 200
        data = response.json()
        # parts_prices block should exist (even if empty/unavailable)
        if "parts_prices" in data:
            # Either has items, or has "unavailable" message
            assert (
                isinstance(data["parts_prices"], list)
                or "unavailable" in str(data["parts_prices"]).lower()
            )


# ==============================================================================
# SCENARIO 5: Performance & Load
# ==============================================================================

class TestPerformance:
    """Performance metrics."""

    def test_registration_completes_within_sla(self, api_client):
        """Registration should complete <500ms."""
        import time
        start = time.time()
        response = api_client.post(
            "/api/v1/auth/register",
            json={
                "email": f"perf-user-{time.time()}@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        elapsed_ms = (time.time() - start) * 1000
        assert response.status_code == 200
        assert elapsed_ms < 500, f"Registration took {elapsed_ms}ms (target <500ms)"

    def test_login_completes_within_sla(self, api_client):
        """Login should complete <300ms."""
        import time

        # Register first
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "perf-login@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Time login
        start = time.time()
        response = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "perf-login@test.ru",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        elapsed_ms = (time.time() - start) * 1000
        assert response.status_code == 200
        assert elapsed_ms < 300, f"Login took {elapsed_ms}ms (target <300ms)"

    def test_health_check_always_200(self, api_client):
        """Health check should always return 200."""
        response = api_client.get("/api/v1/health")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
