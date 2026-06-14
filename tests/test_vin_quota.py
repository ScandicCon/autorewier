"""Тесты квоты VIN-отчётов (защита маржи).

Квота включается только при autocode_enabled (реальные ключи). В демо-режиме
ограничений нет. Порядок списания: квота Pro -> купленные кредиты пакетов.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.models import SubscriptionPlan
from app.services import subscription as sub


def _pro_user():
    return SimpleNamespace(
        subscription_plan=SubscriptionPlan.PRO,
        subscription_until=datetime.now() + timedelta(days=10),
        month_reset_key=sub.current_month_key(),
        inspections_this_month=0,
        vin_reports_this_month=0,
        report_credits=0,
    )


def _free_user():
    u = _pro_user()
    u.subscription_plan = SubscriptionPlan.FREE
    u.subscription_until = None
    return u


def _enable_autocode(monkeypatch, quota=3):
    # autocode_enabled — property из ключей; включаем через сами ключи
    monkeypatch.setattr(settings, "autocode_user", "u")
    monkeypatch.setattr(settings, "autocode_password", "p")
    monkeypatch.setattr(settings, "autocode_domain", "d")
    monkeypatch.setattr(settings, "autocode_report_type_uid", "uid")
    monkeypatch.setattr(settings, "pro_vin_reports_included", quota)
    assert settings.autocode_enabled is True


def test_demo_mode_no_limit(monkeypatch):
    # Autocode выключен -> без ограничений и без списания
    monkeypatch.setattr(settings, "autocode_user", "")
    user = _pro_user()
    for _ in range(100):
        ok, _msg = sub.can_use_vin_report(user)
        assert ok
        sub.consume_vin_report(user)
    assert user.vin_reports_this_month == 0
    assert user.report_credits == 0


def test_pro_quota_then_blocked(monkeypatch):
    _enable_autocode(monkeypatch, quota=3)
    user = _pro_user()
    # первые 3 — из квоты
    for i in range(3):
        ok, _ = sub.can_use_vin_report(user)
        assert ok, f"отчёт {i} должен быть в квоте"
        sub.consume_vin_report(user)
    assert user.vin_reports_this_month == 3
    # 4-й — заблокирован (квота исчерпана, кредитов нет)
    ok, msg = sub.can_use_vin_report(user)
    assert ok is False
    assert "квота" in msg.lower() or "пакет" in msg.lower()


def test_credits_used_after_quota(monkeypatch):
    _enable_autocode(monkeypatch, quota=2)
    user = _pro_user()
    user.report_credits = 2
    # 2 из квоты + 2 из кредитов = 4 успешных
    for _ in range(2):
        assert sub.can_use_vin_report(user)[0]
        sub.consume_vin_report(user)
    for _ in range(2):
        assert sub.can_use_vin_report(user)[0]
        sub.consume_vin_report(user)
    assert user.vin_reports_this_month == 2
    assert user.report_credits == 0
    # 5-й — заблокирован
    assert sub.can_use_vin_report(user)[0] is False


def test_free_user_blocked_when_autocode_on(monkeypatch):
    _enable_autocode(monkeypatch, quota=3)
    user = _free_user()
    ok, msg = sub.can_use_vin_report(user)
    assert ok is False
    assert "pro" in msg.lower() or "пакет" in msg.lower()


def test_add_report_credits(monkeypatch):
    user = _pro_user()
    sub.add_report_credits(user, 5)
    sub.add_report_credits(user, 3)
    assert user.report_credits == 8
