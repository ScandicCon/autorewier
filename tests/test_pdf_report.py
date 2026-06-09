"""
Тесты для app.services.pdf_report.generate_inspection_pdf.

Ожидаемый контракт модуля:
    generate_inspection_pdf(report: AnalysisReport, car_label: str) -> bytes

Модуль ещё не создан — тесты написаны в TDD-стиле.
Если модуль отсутствует, тесты пропускаются с понятным сообщением.
"""
from __future__ import annotations

import importlib

import pytest

from app.schemas import (
    AnalysisReport,
    ChecklistItem,
    FinalRecommendationEnum,
    RepairLine,
    RiskItem,
    VerdictEnum,
)


# ---------------------------------------------------------------------------
# Условный импорт: пропускаем тест-набор если модуль ещё не реализован
# ---------------------------------------------------------------------------

pdf_report_module = None
try:
    pdf_report_module = importlib.import_module("app.services.pdf_report")
except ModuleNotFoundError:
    pass

skip_if_no_pdf_module = pytest.mark.skipif(
    pdf_report_module is None,
    reason="app.services.pdf_report не реализован — тесты ожидают создания модуля",
)


def _get_generate_fn():
    """Возвращает функцию generate_inspection_pdf или пропускает тест."""
    if pdf_report_module is None:
        pytest.skip("app.services.pdf_report не реализован")
    fn = getattr(pdf_report_module, "generate_inspection_pdf", None)
    if fn is None:
        pytest.skip("generate_inspection_pdf не найдена в app.services.pdf_report")
    return fn


# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------

def _minimal_report() -> AnalysisReport:
    """Минимальный AnalysisReport с заполнением только обязательных полей."""
    return AnalysisReport(
        verdict=VerdictEnum.worth_looking,
        final_recommendation=FinalRecommendationEnum.BUY_WITH_CONFIDENCE,
        verdict_label="Стоит смотреть",
        summary="Автомобиль в хорошем состоянии.",
        risks=[],
        checklist=[],
        repair_lines=[],
        repair_total_min=0,
        repair_total_max=0,
    )


def _rich_report() -> AnalysisReport:
    """AnalysisReport с рисками, ремонтом и чеклистом."""
    risk = RiskItem(
        title="Течь масла",
        severity="high",
        description="Видны следы масла под двигателем",
        estimated_cost_min=15_000,
        estimated_cost_max=40_000,
    )
    repair = RepairLine(
        category="Двигатель",
        description="Замена прокладки поддона",
        min_rub=15_000,
        max_rub=40_000,
    )
    checklist_item = ChecklistItem(
        zone="Двигатель",
        title="Проверить уровень масла",
        how_to_check="Вытащить щуп при заглушённом двигателе",
        tools=["Тряпка", "Фонарик"],
        red_flags=["Эмульсия на щупе", "Следы течи"],
    )
    return AnalysisReport(
        verdict=VerdictEnum.caution,
        final_recommendation=FinalRecommendationEnum.CAUTIOUS,
        verdict_label="Стоит смотреть с осторожностью",
        summary="Есть риски, требующие проверки.",
        risks=[risk],
        checklist=[checklist_item],
        repair_lines=[repair],
        repair_total_min=15_000,
        repair_total_max=40_000,
    )


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------

@skip_if_no_pdf_module
def test_pdf_generates_bytes():
    """generate_inspection_pdf(report, 'BMW 320i') → bytes, начинается с b'%PDF'."""
    generate_inspection_pdf = _get_generate_fn()
    report = _rich_report()
    result = generate_inspection_pdf(report, "BMW 320i")

    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF", (
        f"Ожидался PDF-заголовок %PDF, получено: {result[:20]!r}"
    )
    assert len(result) > 100, "PDF слишком маленький — возможно, пустой документ"


@skip_if_no_pdf_module
def test_pdf_contains_verdict():
    """PDF bytes содержат строку вердикта в читаемом тексте."""
    generate_inspection_pdf = _get_generate_fn()
    report = _rich_report()
    result = generate_inspection_pdf(report, "Toyota Camry 2015")

    assert isinstance(result, bytes)
    # Вердикт-метка должна присутствовать в PDF (как текст или закодированная строка)
    verdict_label = report.verdict_label.encode("utf-8")
    assert verdict_label in result or report.verdict.value.encode("utf-8") in result, (
        f"Вердикт '{report.verdict_label}' не найден в PDF"
    )


@skip_if_no_pdf_module
def test_pdf_no_crash_empty_report():
    """Минимальный AnalysisReport (только обязательные поля) → не кидает исключение."""
    generate_inspection_pdf = _get_generate_fn()
    report = _minimal_report()

    try:
        result = generate_inspection_pdf(report, "Неизвестный автомобиль")
    except Exception as exc:
        pytest.fail(
            f"generate_inspection_pdf упал на минимальном отчёте: {exc}"
        )

    assert isinstance(result, bytes)
    assert len(result) > 0


@skip_if_no_pdf_module
def test_pdf_car_label_present_in_output():
    """Метка автомобиля передаётся в PDF как заголовок или часть контента."""
    generate_inspection_pdf = _get_generate_fn()
    car_label = "Skoda Octavia 2019"
    report = _minimal_report()
    result = generate_inspection_pdf(report, car_label)

    assert isinstance(result, bytes)
    # Проверяем наличие хотя бы части метки (Skoda или Octavia)
    assert b"Skoda" in result or b"Octavia" in result or car_label.encode("utf-8") in result


@skip_if_no_pdf_module
def test_pdf_with_risks_contains_risk_info():
    """PDF с рисками содержит информацию о рисках."""
    generate_inspection_pdf = _get_generate_fn()
    report = _rich_report()
    result = generate_inspection_pdf(report, "BMW X5 2010")

    assert isinstance(result, bytes)
    # Название риска или часть его описания должны быть в документе
    risk_title = report.risks[0].title.encode("utf-8")
    assert risk_title in result, (
        f"Название риска '{report.risks[0].title}' не найдено в PDF"
    )
