#!/usr/bin/env python3
"""Проверка готовности окружения к продакшену — AutoRewier / ПОДКАПОТ.

Что делает: загружает текущие настройки (из переменных окружения / .env) и
печатает понятный отчёт ✅/⬜ по тому, что нужно для боевого запуска:
жёсткие блокеры (production hardening), платежи, почта, VIN, БД, CORS, cookie,
аналитика и соц-вход.

Как запускать:
    # Локально против прод-значений (например, экспортнув переменные Railway):
    ENVIRONMENT=production STRICT_PRODUCTION_CHECKS=true \
    WEB_BASE_URL=https://example.com ADMIN_API_TOKEN=... \
    python scripts/check_prod_env.py

Код возврата: 0 — блокеров нет; 1 — есть жёсткие блокеры (прод не поднимется).
Опциональные интеграции в ⬜ не считаются блокерами — это просто «ещё не настроено».
"""

import os
import sys

# Корень репозитория в путь, чтобы скрипт работал из любой директории.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.config import settings
except Exception as exc:  # pragma: no cover
    print(f"Не удалось загрузить настройки: {exc}")
    sys.exit(2)


def mark(ok: bool) -> str:
    return "✅" if ok else "⬜"


def nonempty(*vals: str) -> bool:
    return all(bool((v or "").strip()) for v in vals)


def main() -> int:
    print("=" * 60)
    print("  Проверка готовности к продакшену — AutoRewier")
    print("=" * 60)
    print(f"ENVIRONMENT = {getattr(settings, 'environment', '?')}")
    print(f"is_production = {settings.is_production}")
    print()

    # 1. Жёсткие блокеры (встроенная валидация приложения).
    print("1. Жёсткие блокеры (production hardening)")
    issues = settings.production_hardening_issues
    if not settings.is_production:
        print("   ⚠️  ENVIRONMENT != production — hardening не проверяется.")
        print("       Запусти с ENVIRONMENT=production STRICT_PRODUCTION_CHECKS=true.")
    elif issues:
        for i in issues:
            print(f"   ❌ {i}")
    else:
        print("   ✅ блокеров нет")
    print()

    # 2. База данных.
    db = (settings.database_url or "")
    is_pg = "postgres" in db
    print("2. База данных")
    print(f"   {mark(is_pg)} DATABASE_URL = Postgres (сейчас: {'postgres' if is_pg else 'НЕ postgres — для прода нужен Postgres'})")
    print()

    # 3. Безопасность / доступ.
    print("3. Безопасность / доступ")
    print(f"   {mark(len((settings.web_secret_key or '').strip()) >= 24)} WEB_SECRET_KEY (>=24 симв.)")
    print(f"   {mark(nonempty(settings.admin_api_token))} ADMIN_API_TOKEN")
    print(f"   {mark(settings.web_base_url.startswith('https://'))} WEB_BASE_URL https")
    print(f"   {mark(getattr(settings, 'web_cookie_secure', False))} WEB_COOKIE_SECURE=true")
    samesite_ok = str(getattr(settings, 'web_cookie_samesite', '')).lower() == 'none'
    print(f"   {mark(samesite_ok)} WEB_COOKIE_SAMESITE=none (для Vercel↔Railway)")
    print(f"   {mark(not settings.allow_mock_services)} ALLOW_MOCK_SERVICES=false")
    print(f"   {mark(not settings.allow_dev_payment_bypass)} ALLOW_DEV_PAYMENT_BYPASS=false")
    print()

    # 4. Платежи (ЮKassa).
    print("4. Платежи (ЮKassa)")
    yk_ok = nonempty(getattr(settings, 'yookassa_shop_id', ''), getattr(settings, 'yookassa_secret_key', ''))
    print(f"   {mark(yk_ok)} YOOKASSA_SHOP_ID + YOOKASSA_SECRET_KEY")
    print()

    # 5. Почта (верификация email).
    print("5. Почта (верификация email)")
    mail_ok = nonempty(getattr(settings, 'resend_api_key', '')) or nonempty(getattr(settings, 'smtp_host', ''))
    print(f"   {mark(mail_ok)} RESEND_API_KEY или SMTP_HOST")
    print(f"   {mark(getattr(settings, 'require_email_verification', False))} REQUIRE_EMAIL_VERIFICATION (включать после подтверждения домена)")
    print()

    # 6. VIN (Autocode) — опционально, но без него VIN в демо.
    print("6. VIN (Autocode) — опционально")
    print(f"   {mark(settings.autocode_enabled)} AUTOCODE_* (иначе демо-режим)")
    print()

    # 7. Аналитика / мониторинг — опционально.
    print("7. Аналитика / мониторинг — опционально")
    print(f"   {mark(nonempty(getattr(settings, 'posthog_api_key', '')))} POSTHOG_API_KEY")
    print(f"   {mark(nonempty(getattr(settings, 'sentry_dsn', '')))} SENTRY_DSN")
    print()

    # 8. Соц-вход — опционально (по провайдерам).
    print("8. Соц-вход (OAuth) — опционально")
    for prov in ("yandex", "vk", "google"):
        cid = getattr(settings, f"{prov}_client_id", "")
        sec = getattr(settings, f"{prov}_client_secret", "")
        print(f"   {mark(nonempty(cid, sec))} {prov.upper()}_CLIENT_ID + SECRET")
    print()

    # Итог.
    print("=" * 60)
    if settings.is_production and issues:
        print("ИТОГ: ❌ есть жёсткие блокеры — прод не поднимется. Исправь раздел 1.")
        return 1
    print("ITOG: zhestkih blokerov net (hard-blockerov). Polya '[_]' -")
    print("optsionalnye integratsii, nastroy po docs/MASTER_PLAN.md (Etap 1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
