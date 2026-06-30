from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = ""
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'autorewier.db'}"
    environment: str = "development"
    app_version: str = "0.2.0"
    app_revision: str = ""
    app_forwarded_for_depth: int = 1
    # OpenRouter (https://openrouter.ai) — OpenAI-совместимый API
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = ""
    openrouter_app_name: str = "AutoRewier"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    web_secret_key: str = "change-me-in-production"
    web_base_url: str = "http://127.0.0.1:8000"
    web_session_ttl_seconds: int = 30 * 24 * 3600
    web_cookie_secure: bool = False
    web_cookie_samesite: str = "lax"
    web_cookie_domain: str = ""
    enable_server_rendered_web: bool = False
    enforce_verified_accounts: bool = False
    require_email_verification: bool = False
    verification_code_ttl_minutes: int = 15
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_sender_email: str = ""
    smtp_sender_name: str = "ПОДКАПОТ"
    smtp_use_tls: bool = True

    # Autocode B2B API
    autocode_user: str = ""
    autocode_password: str = ""
    autocode_domain: str = ""
    autocode_report_type_uid: str = ""
    autocode_base_url: str = "https://b2bapi.avtocod.ru/b2b/api/v1"

    # YooKassa
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    yookassa_return_url: str = "http://127.0.0.1:8000/cabinet/subscription?paid=1"
    yookassa_webhook_allowlist: str = (
        "185.71.76.0/27,185.71.77.0/27,77.75.153.0/25,77.75.154.128/25,"
        "77.75.156.11/32,77.75.156.35/32,2a02:5180::/32"
    )

    subscription_pro_price_rub: int = 990
    free_inspections_per_month: int = 3
    pro_vin_reports_included: int = 10  # включённых VIN-отчётов в Pro/мес (защита маржи)
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    posthog_api_key: str = ""
    posthog_host: str = "https://eu.i.posthog.com"
    # OAuth (вход через соцсети). Провайдер активен только при заданных client_id/secret.
    oauth_redirect_base: str = ""   # публичный URL бэкенда, напр. https://autorewier-production.up.railway.app
    oauth_success_redirect: str = ""  # фронт-URL приёма токена; по умолчанию web_base_url + /oauth-callback
    yandex_client_id: str = ""
    yandex_client_secret: str = ""
    vk_client_id: str = ""
    vk_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    allow_dev_payment_bypass: bool = False
    allow_mock_services: bool = False
    enable_telegram_header_auth: bool = True
    telegram_header_secret: str = ""
    admin_api_token: str = ""
    trusted_proxy_hops: int = 0
    trusted_proxy_cidrs: str = ""
    strict_production_checks: bool = True
    run_alembic_on_startup: bool = False

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_storage: str = "memory"  # memory | redis
    rate_limit_login_limit: int = 10
    rate_limit_login_window_seconds: int = 60
    rate_limit_register_limit: int = 10
    rate_limit_register_window_seconds: int = 60
    rate_limit_payment_limit: int = 20
    rate_limit_payment_window_seconds: int = 60
    rate_limit_webhook_limit: int = 120
    rate_limit_webhook_window_seconds: int = 60
    rate_limit_vin_limit: int = 30
    rate_limit_vin_window_seconds: int = 60

    # CORS — comma-separated extra origins (e.g. Vercel frontend URL in production)
    # Example: CORS_EXTRA_ORIGINS=https://autorewier.vercel.app
    cors_extra_origins: str = ""

    # Observability
    json_logs: bool = True
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"

    # Redis / workers
    redis_url: str = ""
    task_queue_enabled: bool = False
    task_queue_name: str = "autorewier:tasks"

    # Whisper transcription (через OpenRouter)
    whisper_model: str = "openai/whisper-1"

    # Monitoring cycle interval in seconds (default 1 hour)
    monitoring_cycle_interval_seconds: int = 3600

    # Avito: playwright | httpx | auto (сначала Playwright, затем httpx)
    avito_fetch_mode: str = "auto"
    avito_fetch_timeout_ms: int = 45000
    avito_fetch_retry_attempts: int = 2
    avito_fetch_retry_backoff_sec: float = 1.2
    avito_fetch_time_budget_sec: float = 90.0
    avito_captcha_retry_attempts: int = 1
    avito_playwright_headless: bool = True
    avito_cache_enabled: bool = True
    avito_cache_ttl_sec: int = 3600
    avito_user_data_dir: str = ""  # путь к профилю Chrome — сохраняет cookies Avito
    avito_proxy: str = ""  # например http://user:pass@host:port
    avito_proxy_username: str = ""  # опционально, если провайдер выдает логин отдельно
    avito_proxy_password: str = ""  # опционально, если провайдер выдает пароль отдельно
    # True = новый Chromium на каждый запрос (стабильнее, без «context closed»)
    avito_browser_per_request: bool = True

    # ScrapingBee (внешний скрейпинг-API для обхода антибота Avito).
    # Без ключа всё работает на прямом httpx (мягкая деградация).
    scrapingbee_api_key: str = ""
    scrapingbee_render_js: bool = False
    scrapingbee_premium_proxy: bool = True  # резидентные прокси (нужны для Avito)
    scrapingbee_country_code: str = "ru"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str:
        raw = str(value or "").strip()
        if not raw:
            return raw
        if raw.startswith("DATABASE_URL="):
            raw = raw.split("=", 1)[1].strip()
        if (raw.startswith('"') and raw.endswith('"')) or (
            raw.startswith("'") and raw.endswith("'")
        ):
            raw = raw[1:-1]
        # Railway/Heroku give plain postgresql:// — convert to asyncpg driver
        if raw.startswith('postgres://'):
            raw = 'postgresql+asyncpg://' + raw[len('postgres://'):]
        elif raw.startswith('postgresql://') and '+' not in raw.split('://')[0]:
            raw = 'postgresql+asyncpg://' + raw[len('postgresql://'):]

        # Common copy-paste mistake: password wrapped in [] in postgres URL.
        raw = re.sub(
            r"^(postgresql(?:\+asyncpg)?://[^:/?#]+):\[([^\]]+)\]@",
            r"\1:\2@",
            raw,
        )
        # Supabase pooler + asyncpg is more stable with SSL required and
        # disabled statement cache (pgbouncer compatibility).
        try:
            parsed = urlparse(raw)
            host = (parsed.hostname or "").lower()
            if "pooler.supabase.com" in host and "+asyncpg" in raw:
                query_items = parse_qsl(parsed.query, keep_blank_values=True)
                filtered_items = [
                    (k, v)
                    for (k, v) in query_items
                    if k not in {"statement_cache_size", "command_timeout"}
                ]
                q = dict(filtered_items)
                q.setdefault("ssl", "require")
                raw = urlunparse(parsed._replace(query=urlencode(q)))
        except Exception:
            pass
        return raw

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openrouter_api_key.strip())

    @property
    def scrapingbee_enabled(self) -> bool:
        return bool(self.scrapingbee_api_key.strip())

    @property
    def autocode_enabled(self) -> bool:
        return all(
            [
                self.autocode_user.strip(),
                self.autocode_password.strip(),
                self.autocode_domain.strip(),
                self.autocode_report_type_uid.strip(),
            ]
        )

    @property
    def yookassa_enabled(self) -> bool:
        return bool(self.yookassa_shop_id.strip() and self.yookassa_secret_key.strip())

    @property
    def is_production(self) -> bool:
        return self.environment.lower().strip() in {"prod", "production"}

    @property
    def effective_cookie_secure(self) -> bool:
        return bool(self.web_cookie_secure or self.is_production)

    @property
    def effective_cookie_samesite(self) -> str:
        value = (self.web_cookie_samesite or "lax").lower().strip()
        if value not in {"lax", "strict", "none"}:
            return "lax"
        return value

    @property
    def can_use_dev_payment_bypass(self) -> bool:
        return bool(self.allow_dev_payment_bypass and not self.is_production)

    @property
    def can_use_mock_services(self) -> bool:
        return bool(self.allow_mock_services and not self.is_production)

    @property
    def production_hardening_issues(self) -> list[str]:
        if not self.is_production or not self.strict_production_checks:
            return []
        issues: list[str] = []
        if len((self.web_secret_key or "").strip()) < 24 or "change-me" in self.web_secret_key:
            issues.append("WEB_SECRET_KEY is weak")
        if not self.web_base_url.startswith("https://"):
            issues.append("WEB_BASE_URL must use https")
        if self.allow_dev_payment_bypass:
            issues.append("ALLOW_DEV_PAYMENT_BYPASS must be false")
        if self.allow_mock_services:
            issues.append("ALLOW_MOCK_SERVICES must be false")
        if not self.admin_api_token.strip():
            issues.append("ADMIN_API_TOKEN is required")
        return issues


settings = Settings()
