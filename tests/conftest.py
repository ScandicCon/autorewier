"""Глобальная изоляция тестов от внешних сервисов.

Зачем: при полном прогоне одним процессом тесты могут пытаться сделать реальный
сетевой вызов или запустить браузер Playwright. В окружении без быстрого fail-fast
по сети (или при наличии боевого .env рядом) это приводит к зависанию всего сьюта.

Эта фикстура делает тест-прогон детерминированным независимо от окружения:
- выставляет тест-флаги ещё до импорта приложения;
- зануляет ключи внешних интеграций (PostHog, Sentry, Redis, Autocode, LLM, почта),
  чтобы ни один тест случайно не пошёл во внешний сервис;
- запрещает реальный запуск Chromium в высокоуровневом парсере Avito.

Тесты, которые осознанно мокают свои внутренности (например, captcha-тесты,
вызывающие avito_fetch.fetch_avito_html напрямую), не затрагиваются: их
собственный monkeypatch применяется после этой autouse-фикстуры и переопределяет её.
"""

import os

import pytest

# Базовое тест-окружение должно быть выставлено до импорта app.config.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ALLOW_MOCK_SERVICES", "true")
os.environ.setdefault("STRICT_PRODUCTION_CHECKS", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("TASK_QUEUE_ENABLED", "false")

# Ключи, отвечающие за сетевые вызовы. Зануляем на время тестов.
_NETWORK_KEY_ATTRS = (
    "posthog_api_key",
    "sentry_dsn",
    "redis_url",
    "autocode_user",
    "autocode_password",
    "autocode_domain",
    "openrouter_api_key",
    "resend_api_key",
    "smtp_host",
    "smtp_user",
    "smtp_password",
)


@pytest.fixture(autouse=True)
def _isolate_external_services(monkeypatch):
    """Отключает внешние интеграции и запрещает запуск реального браузера."""
    from app.config import settings

    for attr in _NETWORK_KEY_ATTRS:
        if hasattr(settings, attr):
            monkeypatch.setattr(settings, attr, "", raising=False)

    if hasattr(settings, "task_queue_enabled"):
        monkeypatch.setattr(settings, "task_queue_enabled", False, raising=False)
    if hasattr(settings, "rate_limit_enabled"):
        monkeypatch.setattr(settings, "rate_limit_enabled", False, raising=False)

    # Никогда не запускаем реальный Chromium в высокоуровневом парсере Avito.
    # Возвращаем "fetch не удался" → парсер уходит в graceful-фолбэк на ручной ввод.
    try:
        import app.services.parsers.avito as avito
        from app.services.parsers.avito_fetch import (
            AvitoFetchResult,
            AvitoFetchStatus,
        )

        async def _stub_fetch(url: str) -> AvitoFetchResult:
            return AvitoFetchResult(
                html=None,
                status=AvitoFetchStatus.failed,
                reason="fetch_disabled_in_tests",
                action_required="manual_input",
            )

        monkeypatch.setattr(avito, "fetch_avito_html", _stub_fetch, raising=False)
    except Exception:
        # Если структура парсера изменится — не валим весь сьют из-за изоляции.
        pass

    yield
