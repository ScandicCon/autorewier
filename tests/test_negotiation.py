"""Тесты для generate_negotiation_tips (app.services.negotiation)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas import AnalysisReport, FinalRecommendationEnum, RiskItem, VehicleInput, VerdictEnum
from app.services.negotiation import generate_negotiation_tips


# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------

def _make_vehicle(price_rub: int = 1_200_000) -> VehicleInput:
    return VehicleInput(
        brand="Toyota",
        model="Camry",
        year=2015,
        mileage_km=180_000,
        price_rub=price_rub,
    )


def _make_report(risks: list[RiskItem] | None = None) -> AnalysisReport:
    return AnalysisReport(
        verdict=VerdictEnum.caution,
        final_recommendation=FinalRecommendationEnum.CAUTIOUS,
        verdict_label="Стоит смотреть с осторожностью",
        summary="Тестовый отчёт",
        risks=risks or [],
        checklist=[],
        repair_lines=[],
        repair_total_min=50_000,
        repair_total_max=120_000,
    )


def _make_risk(severity: str = "high", cost_min: int | None = 20_000, cost_max: int | None = 50_000) -> RiskItem:
    return RiskItem(
        title="Стук в подвеске",
        severity=severity,  # type: ignore[arg-type]
        description="Слышен стук при езде по кочкам",
        estimated_cost_min=cost_min,
        estimated_cost_max=cost_max,
    )


def _fake_chat_completion(tips_json: str) -> MagicMock:
    """Создаёт mock-ответ OpenAI-совместимого клиента."""
    message = MagicMock()
    message.content = tips_json
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------

def test_generate_tips_returns_list(monkeypatch: pytest.MonkeyPatch):
    """Mock OpenRouter → generate_negotiation_tips возвращает list[str]."""
    expected_tips = [
        "Скажите продавцу: 'Стук в подвеске обойдётся в 50 000 ₽ — прошу скидку'",
        "Скажите продавцу: 'Течь масла требует замены прокладки — минус 20 000 ₽'",
        "Скажите продавцу: 'Пробег высокий, возможен ресурс двигателя'",
    ]
    fake_response = _fake_chat_completion('["' + '", "'.join(expected_tips) + '"]')

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_response)

    # llm_enabled должен быть True
    monkeypatch.setattr("app.services.negotiation.settings", MagicMock(
        llm_enabled=True,
        openrouter_model="openai/gpt-4o-mini",
    ))

    with patch("app.services.llm._openrouter_client", return_value=mock_client):
        report = _make_report(risks=[_make_risk()])
        vehicle = _make_vehicle()
        tips = asyncio.run(generate_negotiation_tips(report, vehicle))

    assert isinstance(tips, list)
    assert len(tips) == 3
    assert all(isinstance(t, str) for t in tips)
    assert tips[0] == expected_tips[0]


def test_generate_tips_empty_on_no_risks(monkeypatch: pytest.MonkeyPatch):
    """При пустых рисках и нулевом ремонте — возвращает [] или общие советы (не падает)."""
    fake_response = _fake_chat_completion("[]")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_response)

    monkeypatch.setattr("app.services.negotiation.settings", MagicMock(
        llm_enabled=True,
        openrouter_model="openai/gpt-4o-mini",
    ))

    with patch("app.services.llm._openrouter_client", return_value=mock_client):
        report = _make_report(risks=[])
        report.repair_total_min = 0
        report.repair_total_max = 0
        vehicle = _make_vehicle()
        tips = asyncio.run(generate_negotiation_tips(report, vehicle))

    assert isinstance(tips, list)
    # Допускаем как пустой список, так и общие советы
    assert all(isinstance(t, str) for t in tips)


def test_generate_tips_no_key(monkeypatch: pytest.MonkeyPatch):
    """Если llm_enabled=False — возвращает [], не кидает исключение."""
    monkeypatch.setattr("app.services.negotiation.settings", MagicMock(llm_enabled=False))

    report = _make_report(risks=[_make_risk()])
    vehicle = _make_vehicle()
    tips = asyncio.run(generate_negotiation_tips(report, vehicle))

    assert tips == []


def test_generate_tips_llm_exception_returns_empty(monkeypatch: pytest.MonkeyPatch):
    """Если LLM кидает исключение — возвращает [], не пробрасывает ошибку."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("network error"))

    monkeypatch.setattr("app.services.negotiation.settings", MagicMock(
        llm_enabled=True,
        openrouter_model="openai/gpt-4o-mini",
    ))

    with patch("app.services.llm._openrouter_client", return_value=mock_client):
        report = _make_report(risks=[_make_risk()])
        vehicle = _make_vehicle()
        tips = asyncio.run(generate_negotiation_tips(report, vehicle))

    assert tips == []


def test_generate_tips_malformed_json_returns_empty(monkeypatch: pytest.MonkeyPatch):
    """Если LLM возвращает некорректный JSON — возвращает [], не кидает исключение."""
    fake_response = _fake_chat_completion("не JSON ответ")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_response)

    monkeypatch.setattr("app.services.negotiation.settings", MagicMock(
        llm_enabled=True,
        openrouter_model="openai/gpt-4o-mini",
    ))

    with patch("app.services.llm._openrouter_client", return_value=mock_client):
        report = _make_report(risks=[_make_risk()])
        vehicle = _make_vehicle()
        tips = asyncio.run(generate_negotiation_tips(report, vehicle))

    assert tips == []
