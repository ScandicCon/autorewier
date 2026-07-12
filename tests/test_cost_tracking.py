"""Тесты учёта себестоимости проверки (app.services.cost_tracking)."""
from app.config import settings
from app.services import cost_tracking as ct


def test_records_within_context(monkeypatch):
    monkeypatch.setattr(settings, "cost_llm_rub_per_1k_prompt", 0.02)
    monkeypatch.setattr(settings, "cost_llm_rub_per_1k_completion", 0.08)
    monkeypatch.setattr(settings, "cost_scrapingbee_rub_per_credit", 0.02)
    with ct.cost_context() as acc:
        ct.record_llm(1000, 500)
        ct.record_llm(0, 500)
        ct.record_scrapingbee(25)
        snap = ct.snapshot(acc)
    assert snap["llm_calls"] == 2
    assert snap["llm_prompt_tokens"] == 1000
    assert snap["llm_completion_tokens"] == 1000
    assert snap["scrapingbee_requests"] == 1
    assert snap["scrapingbee_credits"] == 25
    # 1000/1000*0.02 + 1000/1000*0.08 + 25*0.02 = 0.02 + 0.08 + 0.5 = 0.6
    assert snap["cost_rub"] == 0.6


def test_no_context_is_noop():
    # Вне контекста запись не должна падать и ничего не накапливает.
    ct.record_llm(100, 100)
    ct.record_scrapingbee(10)
    snap = ct.snapshot_current()  # нулевой снимок
    assert snap["llm_calls"] == 0
    assert snap["scrapingbee_credits"] == 0
    assert snap["cost_rub"] == 0.0


def test_context_isolation():
    with ct.cost_context() as acc:
        ct.record_llm(500, 0)
        assert acc["llm_prompt_tokens"] == 500
    # После выхода контекст сброшен.
    assert ct.snapshot_current()["llm_prompt_tokens"] == 0
