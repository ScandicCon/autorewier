"""Загрузка Avito: Playwright sync в отдельном потоке (Windows + uvicorn)."""

import asyncio
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from app.config import BASE_DIR, settings
from app.services.parsers.base import USER_AGENT

CACHE_DIR = BASE_DIR / "data" / "cache" / "avito"

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="avito_pw")
_pw_lock = threading.Lock()
_sync_playwright = None
_sync_context = None

BLOCK_MARKERS = (
    "captcha",
    "captchacheck",
    "подтвердите что вы человек",
    "firewall",
    "доступ ограничен",
    "доступ временно ограничен",
    "подтвердите, что вы не робот",
    "подтвердите что вы не робот",
    "проверка безопасности",
    "access denied",
    "cf-challenge",
    "hcaptcha",
    "g-recaptcha",
    "arkoselabs",
)

DEAD_BROWSER_MARKERS = (
    "has been closed",
    "target page, context or browser",
    "browser closed",
    "connection closed",
    "execution context was destroyed",
)

PROXY_AUTH_MARKERS = (
    "407",
    "proxy authentication",
    "proxy auth",
    "tunnel connection failed",
    "proxy connect error",
)

PROXY_CONNECT_MARKERS = (
    "proxyerror",
    "proxy error",
    "cannot connect to proxy",
    "failed to resolve proxy",
    "connection refused",
    "timed out",
    "temporary failure in name resolution",
    "name or service not known",
)

DEFAULT_WARMUP_URL = "https://www.avito.ru/"


class AvitoFetchStatus(str, Enum):
    success = "success"
    captcha = "captcha"
    blocked = "blocked"
    browser_missing = "browser_missing"
    invalid_html = "invalid_html"
    transient_error = "transient_error"
    failed = "failed"


@dataclass
class AvitoFetchResult:
    html: str | None
    status: AvitoFetchStatus
    user_message: str | None = None
    reason: str | None = None
    action_required: str | None = None
    source: str | None = None
    attempts: int = 0
    diagnostics: dict | None = None

    def legacy_error(self) -> str | None:
        """Backward-compatible error text for legacy tuple consumers."""
        if self.status == AvitoFetchStatus.success:
            return None
        if self.status == AvitoFetchStatus.captcha:
            return (
                "Avito показал captcha. В .env: AVITO_PLAYWRIGHT_HEADLESS=false — "
                "см. docs/AVITO.md"
            )
        return self.user_message or "Avito не загрузился. Введите данные вручную."

    def __iter__(self):
        """
        Backward compatibility with old `(html, error)` contract.
        Keep this until all legacy call sites are removed.
        """
        yield self.html
        yield self.legacy_error()


def _item_id(url: str) -> str | None:
    m = re.search(r"_(\d{6,})", url) or re.search(r"/(\d{6,})(?:\?|$)", url)
    return m.group(1) if m else None


def normalize_avito_url(url: str) -> str:
    url = url.strip()
    item_id = _item_id(url)
    if item_id and "avito.ru" in url.lower():
        return f"https://www.avito.ru/items/{item_id}"
    return url


def _cache_path(item_id: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{item_id}.html"


def _read_cache(item_id: str) -> str | None:
    if not settings.avito_cache_enabled:
        return None
    path = _cache_path(item_id)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > settings.avito_cache_ttl_sec:
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


def _write_cache(item_id: str, html: str) -> None:
    if settings.avito_cache_enabled and len(html) > 3000:
        _cache_path(item_id).write_text(html, encoding="utf-8")


def is_blocked_html(html: str) -> bool:
    status, _ = detect_block_state(html)
    return status in (AvitoFetchStatus.captcha, AvitoFetchStatus.blocked)


def detect_block_state(
    html: str | None,
    *,
    http_status: int | None = None,
) -> tuple[AvitoFetchStatus | None, str | None]:
    if http_status == 429:
        return AvitoFetchStatus.blocked, "rate_limited"
    if http_status == 403:
        return AvitoFetchStatus.blocked, "http_403"
    if not html:
        return None, None
    sample = html[:15000].lower()
    if any(x in sample for x in ("captcha", "hcaptcha", "g-recaptcha", "подтвердите")):
        return AvitoFetchStatus.captcha, "captcha_challenge"
    if any(m in sample for m in BLOCK_MARKERS):
        return AvitoFetchStatus.blocked, "blocked_page"
    return None, None


def is_valid_listing_html(html: str) -> bool:
    if len(html) < 8000:
        return False
    if is_blocked_html(html):
        return False
    low = html.lower()
    return (
        "item-view" in low
        or "itemprop=\"price\"" in low
        or 'data-marker="item-view' in low
        or ("avito" in low and re.search(r'"price"\s*:\s*\d{4,}', html))
    )


def _is_dead_browser_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(m in msg for m in DEAD_BROWSER_MARKERS)


@dataclass
class _ProxyConfig:
    configured: bool
    proxy_url: str | None
    playwright: dict | None
    issues: list[str]
    has_auth: bool
    endpoint: str | None


def _sanitize_proxy_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if not parsed.hostname or not parsed.port:
        return None
    netloc = f"{parsed.hostname}:{parsed.port}"
    if parsed.username:
        netloc = f"{parsed.username}:***@{netloc}"
    return urlunsplit((parsed.scheme or "http", netloc, "", "", ""))


def _normalize_proxy_url(raw: str) -> str:
    """
    Support both standard and provider-style proxy formats:
    - user:pass@host:port
    - host:port@user:pass
    - http://user:pass@host:port
    """
    value = raw.strip()
    if not value:
        return ""
    if "://" not in value:
        # Some providers return host:port@login:password.
        if "@" in value:
            left, right = value.rsplit("@", 1)
            if re.fullmatch(r"[^:@]+:\d+", left) and ":" in right:
                value = f"http://{right}@{left}"
            else:
                value = f"http://{value}"
        else:
            value = f"http://{value}"
    return value


def _build_proxy_config() -> _ProxyConfig:
    raw_proxy = _normalize_proxy_url(settings.avito_proxy)
    if not raw_proxy:
        return _ProxyConfig(
            configured=False,
            proxy_url=None,
            playwright=None,
            issues=[],
            has_auth=False,
            endpoint=None,
        )
    parsed = urlsplit(raw_proxy)
    issues: list[str] = []
    if parsed.scheme not in {"http", "https", "socks5", "socks5h"}:
        issues.append("proxy_scheme_not_supported")
    if not parsed.hostname or not parsed.port:
        issues.append("proxy_host_or_port_missing")

    username = settings.avito_proxy_username.strip() or (parsed.username or "")
    password = settings.avito_proxy_password.strip() or (parsed.password or "")
    has_auth = bool(username or password)
    if (username and not password) or (password and not username):
        issues.append("proxy_auth_incomplete")

    endpoint = None
    if parsed.hostname and parsed.port:
        endpoint = f"{parsed.hostname}:{parsed.port}"

    if issues:
        return _ProxyConfig(
            configured=True,
            proxy_url=None,
            playwright=None,
            issues=issues,
            has_auth=has_auth,
            endpoint=endpoint,
        )

    credentials = ""
    if username:
        credentials = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    proxy_url = urlunsplit(
        (
            parsed.scheme or "http",
            f"{credentials}{parsed.hostname}:{parsed.port}",
            "",
            "",
            "",
        )
    )
    playwright: dict[str, str] = {
        "server": f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port}"
    }
    if username:
        playwright["username"] = username
        playwright["password"] = password
    return _ProxyConfig(
        configured=True,
        proxy_url=proxy_url,
        playwright=playwright,
        issues=[],
        has_auth=has_auth,
        endpoint=endpoint,
    )


def get_proxy_diagnostics() -> dict:
    config = _build_proxy_config()
    return {
        "configured": config.configured,
        "endpoint": config.endpoint,
        "has_auth": config.has_auth,
        "issues": list(config.issues),
        "sanitized_proxy_url": _sanitize_proxy_url(config.proxy_url),
    }


def _proxy_playwright() -> dict | None:
    return _build_proxy_config().playwright


def _proxy_httpx() -> str | None:
    return _build_proxy_config().proxy_url


def _is_proxy_auth_error(detail: str) -> bool:
    sample = detail.lower()
    return any(marker in sample for marker in PROXY_AUTH_MARKERS)


def _is_proxy_connect_error(detail: str) -> bool:
    sample = detail.lower()
    return any(marker in sample for marker in PROXY_CONNECT_MARKERS)


def _profile_dir() -> Path:
    raw = settings.avito_user_data_dir.strip()
    path = Path(raw) if raw else BASE_DIR / "data" / "avito_browser_profile"
    if not path.is_absolute():
        path = BASE_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _launch_args() -> list[str]:
    return [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]


def _close_browser_unlocked() -> None:
    global _sync_playwright, _sync_context
    try:
        if _sync_context:
            _sync_context.close()
    except Exception:
        pass
    try:
        if _sync_playwright:
            _sync_playwright.stop()
    except Exception:
        pass
    _sync_context = _sync_playwright = None


def _open_persistent_context():
    from playwright.sync_api import sync_playwright

    global _sync_playwright, _sync_context
    _close_browser_unlocked()
    _sync_playwright = sync_playwright().start()
    _sync_context = _sync_playwright.chromium.launch_persistent_context(
        str(_profile_dir()),
        headless=settings.avito_playwright_headless,
        user_agent=USER_AGENT,
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        viewport={"width": 1440, "height": 900},
        proxy=_proxy_playwright(),
        args=_launch_args(),
    )
    _sync_context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )


def _expand_avito_description(page) -> None:
    """Раскрыть полное описание («Читать полностью») и прокрутить к блоку."""
    expand_selectors = (
        '[data-marker="item-view/item-description/expander"]',
        '[data-marker="description-preview/expander"]',
        'button:has-text("Читать")',
        'button:has-text("ещё")',
        'button:has-text("еще")',
    )
    for sel in expand_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=3000)
                page.wait_for_timeout(800)
                break
        except Exception:
            continue

    for sel in (
        '[data-marker="item-view/item-description"]',
        '[data-marker="item-view/item-description-text"]',
        '[data-marker="item-description/text"]',
    ):
        try:
            page.locator(sel).first.scroll_into_view_if_needed(timeout=5000)
            page.wait_for_timeout(500)
            break
        except Exception:
            continue


def _load_page(context, url: str) -> str:
    page = context.new_page()
    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=settings.avito_fetch_timeout_ms,
        )
        for sel in (
            'h1[data-marker="item-view/title-info"]',
            'h1[data-marker="item-title"]',
            "h1",
        ):
            try:
                page.wait_for_selector(sel, timeout=15000)
                break
            except Exception:
                continue
        for sel in (
            '[data-marker="item-view/item-description"]',
            '[data-marker="item-view/item-description-text"]',
            '[data-marker="item-description/text"]',
            'div[itemprop="description"]',
        ):
            try:
                page.wait_for_selector(sel, timeout=15000)
                break
            except Exception:
                continue
        _expand_avito_description(page)
        page.wait_for_timeout(1500)
        return page.content()
    finally:
        try:
            page.close()
        except Exception:
            pass


def _fetch_ephemeral_sync(url: str) -> str:
    """Новый браузер на каждый запрос — самый стабильный режим."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=settings.avito_playwright_headless,
            proxy=_proxy_playwright(),
            args=_launch_args(),
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1440, "height": 900},
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        try:
            return _load_page(context, url)
        finally:
            context.close()
            browser.close()


def _fetch_persistent_sync(url: str) -> str:
    global _sync_context
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with _pw_lock:
                if _sync_context is None:
                    _open_persistent_context()
                assert _sync_context is not None
                return _load_page(_sync_context, url)
        except Exception as e:
            last_err = e
            if _is_dead_browser_error(e) and attempt < 2:
                with _pw_lock:
                    _close_browser_unlocked()
                time.sleep(0.5)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("Не удалось открыть страницу Avito")


def _fetch_playwright_sync(url: str) -> str:
    if settings.avito_browser_per_request:
        return _fetch_ephemeral_sync(url)
    return _fetch_persistent_sync(url)


def _fetch_playwright_sync_mode(url: str, use_persistent: bool) -> str:
    if use_persistent:
        return _fetch_persistent_sync(url)
    return _fetch_ephemeral_sync(url)


async def _fetch_playwright(url: str, *, use_persistent: bool | None = None) -> str | None:
    loop = asyncio.get_running_loop()
    if use_persistent is None:
        return await loop.run_in_executor(_executor, _fetch_playwright_sync, url)
    return await loop.run_in_executor(
        _executor, _fetch_playwright_sync_mode, url, use_persistent
    )


async def _fetch_httpx(url: str) -> tuple[str | None, int | None, str | None]:
    timeout_sec = max(settings.avito_fetch_timeout_ms / 1000.0, 15.0)
    proxy = _proxy_httpx()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.avito.ru/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }
    last_error: str | None = None
    targets = [url]
    item_id = _item_id(url)
    if item_id:
        targets.append(f"https://m.avito.ru/items/{item_id}")
    for target in targets:
        try:
            client_kwargs: dict = {
                "follow_redirects": True,
                "timeout": timeout_sec,
                "headers": headers,
            }
            if proxy:
                client_kwargs["proxy"] = proxy
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(target)
                html = resp.text
                if resp.status_code == 200 and html and len(html) > 5000:
                    return html, resp.status_code, None
                if resp.status_code in (403, 429):
                    return html, resp.status_code, None
                last_error = f"status_{resp.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
    return None, None, last_error or "httpx_failed"


async def _fetch_scrapingbee(url: str, *, render_js: bool) -> str | None:
    """Загрузка через ScrapingBee (premium RU proxy) — последний эшелон.

    Зачем: на дата-центровом IP (Yandex Cloud) Playwright и httpx получают
    captcha/403 почти всегда. ScrapingBee ходит со своих резидентных прокси
    и снимает эту проблему без изменения логики разбора HTML.
    Кредиты учитываются в cost_tracking внутри слоя scraping.
    """
    from app.services.scraping import fetch_via_scrapingbee

    timeout_sec = max(settings.avito_fetch_timeout_ms / 1000.0, 15.0)
    return await fetch_via_scrapingbee(
        url,
        timeout=timeout_sec,
        render_js=render_js,
        premium_proxy=settings.scrapingbee_premium_proxy,
        country_code=settings.scrapingbee_country_code,
    )


def _coerce_httpx_result(
    raw_result: object,
) -> tuple[str | None, int | None, str | None]:
    """
    Normalize legacy monkeypatched HTTP fetch return shapes.
    Supported:
    - (html, status_code, http_error)  [current]
    - html string                       [legacy tests]
    - None                              [legacy tests]
    """
    if isinstance(raw_result, tuple):
        if len(raw_result) == 3:
            html, status_code, http_error = raw_result
            html_value = html if isinstance(html, str) or html is None else None
            status_value = status_code if isinstance(status_code, int) else None
            error_value = http_error if isinstance(http_error, str) else None
            return html_value, status_value, error_value
        if len(raw_result) == 2:
            html, http_error = raw_result
            html_value = html if isinstance(html, str) or html is None else None
            error_value = http_error if isinstance(http_error, str) else None
            return html_value, None, error_value
    if isinstance(raw_result, str):
        return raw_result, None, None
    if raw_result is None:
        return None, None, None
    return None, None, f"unsupported_httpx_result_type:{type(raw_result).__name__}"


async def _with_retry_pause(attempt: int) -> None:
    if attempt <= 0:
        return
    pause = max(settings.avito_fetch_retry_backoff_sec, 0.0) * attempt
    if pause > 0:
        await asyncio.sleep(min(pause, 5.0))


def _finalize_error_result(
    statuses: list[AvitoFetchStatus], details: list[str]
) -> AvitoFetchResult:
    joined = " ".join(details).lower()
    proxy_diag = get_proxy_diagnostics()
    if "time_budget_exceeded" in joined:
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.transient_error,
            reason="time_budget_exceeded",
            action_required="retry_later_or_proxy",
            user_message=(
                "Превышено время ожидания ответа Avito. Повторите запрос позже "
                "или проверьте прокси."
            ),
            diagnostics={"proxy": proxy_diag},
        )
    if "proxy_invalid_config" in joined:
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.transient_error,
            reason="proxy_invalid_config",
            action_required="check_proxy_settings",
            user_message=(
                "Прокси Avito настроен некорректно. Проверьте AVITO_PROXY и "
                "учетные данные прокси."
            ),
            diagnostics={"proxy": proxy_diag},
        )
    if _is_proxy_auth_error(joined):
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.transient_error,
            reason="proxy_auth_failed",
            action_required="check_proxy_credentials",
            user_message=(
                "Прокси отклонил авторизацию. Проверьте логин/пароль и доступ к прокси."
            ),
            diagnostics={"proxy": proxy_diag},
        )
    if _is_proxy_connect_error(joined):
        proxy_conf = _build_proxy_config()
        if proxy_conf.configured:
            msg = "Не удалось подключиться к прокси Avito. Проверьте адрес, порт и сеть."
        else:
            msg = "Avito временно недоступен или заблокировал запрос. Введите данные вручную."
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.transient_error,
            reason="proxy_connection_failed",
            action_required="check_proxy_settings",
            user_message=msg,
            diagnostics={"proxy": proxy_diag},
        )
    if "executable doesn't exist" in joined or "playwright install" in joined:
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.browser_missing,
            reason="playwright_browser_not_installed",
            action_required="install_playwright_browser",
            user_message=(
                "Установите браузер: .\\.venv\\Scripts\\playwright.exe install chromium "
                "или scripts\\setup_avito.ps1"
            ),
            diagnostics={"proxy": proxy_diag},
        )
    if AvitoFetchStatus.captcha in statuses:
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.captcha,
            reason="captcha_challenge",
            action_required="solve_captcha",
            user_message=(
                "Avito показал captcha. Откройте docs/AVITO.md: "
                "пройдите проверку один раз в non-headless режиме и повторите загрузку."
            ),
            diagnostics={"proxy": proxy_diag},
        )
    if AvitoFetchStatus.blocked in statuses:
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.blocked,
            reason="access_blocked",
            action_required="retry_later_or_proxy",
            user_message=(
                "Avito временно ограничил доступ. Повторите позже или настройте AVITO_PROXY."
            ),
            diagnostics={"proxy": proxy_diag},
        )
    if _is_dead_browser_error(Exception(joined)):
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.transient_error,
            reason="browser_context_restarted",
            action_required="retry_request",
            user_message=(
                "Браузер Avito перезапущен. Повторите загрузку. "
                "Если снова ошибка — закройте окна Chrome и перезапустите python run_api.py."
            ),
            diagnostics={"proxy": proxy_diag},
        )
    detail = details[-1] if details else "не удалось получить страницу"
    return AvitoFetchResult(
        html=None,
        status=AvitoFetchStatus.failed,
        reason="fetch_failed",
        action_required="fill_manual",
        user_message=f"Avito не загрузился ({detail}). Введите данные вручную.",
        diagnostics={"proxy": proxy_diag},
    )


def _shutdown_sync_browser() -> None:
    with _pw_lock:
        _close_browser_unlocked()


async def shutdown_avito_browser() -> None:
    if settings.avito_browser_per_request:
        return
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _shutdown_sync_browser)


async def fetch_avito_html(url: str) -> AvitoFetchResult:
    url = normalize_avito_url(url)
    item_id = _item_id(url)
    started_at = time.monotonic()
    budget_sec = max(10.0, float(settings.avito_fetch_time_budget_sec))

    if item_id:
        cached = _read_cache(item_id)
        if cached and is_valid_listing_html(cached):
            return AvitoFetchResult(
                html=cached,
                status=AvitoFetchStatus.success,
                source="cache",
                attempts=0,
            )

    mode = settings.avito_fetch_mode.lower()
    errors: list[str] = []
    statuses: list[AvitoFetchStatus] = []
    retry_attempts = max(1, int(settings.avito_fetch_retry_attempts))
    captcha_retry_attempts = max(0, int(settings.avito_captcha_retry_attempts))
    proxy_config = _build_proxy_config()
    if proxy_config.issues:
        statuses.append(AvitoFetchStatus.transient_error)
        errors.append(f"proxy_invalid_config:{','.join(proxy_config.issues)}")
        return _finalize_error_result(statuses, errors)

    urls = [url]
    if item_id:
        mobile = f"https://m.avito.ru/items/{item_id}"
        if mobile not in urls:
            urls.append(mobile)

    for target in urls:
        if mode in ("playwright", "auto"):
            last_status = AvitoFetchStatus.invalid_html
            for attempt in range(1, retry_attempts + 1):
                if time.monotonic() - started_at >= budget_sec:
                    statuses.append(AvitoFetchStatus.transient_error)
                    errors.append("time_budget_exceeded")
                    return _finalize_error_result(statuses, errors)
                try:
                    html = await _fetch_playwright(target)
                except Exception as exc:
                    errors.append(f"Playwright: {exc}")
                    statuses.append(AvitoFetchStatus.transient_error)
                    last_status = AvitoFetchStatus.transient_error
                    await _with_retry_pause(attempt)
                    continue
                if html and is_valid_listing_html(html):
                    if item_id:
                        _write_cache(item_id, html)
                    return AvitoFetchResult(
                        html=html,
                        status=AvitoFetchStatus.success,
                        source="playwright",
                        attempts=attempt,
                    )
                detected, reason = detect_block_state(html)
                if detected:
                    statuses.append(detected)
                    last_status = detected
                    errors.append(f"Playwright: {reason or detected.value}")
                    if (
                        detected == AvitoFetchStatus.captcha
                        and settings.avito_browser_per_request
                    ):
                        for profile_attempt in range(1, captcha_retry_attempts + 2):
                            if time.monotonic() - started_at >= budget_sec:
                                statuses.append(AvitoFetchStatus.transient_error)
                                errors.append("time_budget_exceeded")
                                return _finalize_error_result(statuses, errors)
                            try:
                                html_profile = await _fetch_playwright(
                                    target, use_persistent=True
                                )
                            except Exception as exc:
                                errors.append(f"Playwright(profile): {exc}")
                                statuses.append(AvitoFetchStatus.transient_error)
                                await _with_retry_pause(profile_attempt)
                                continue
                            if html_profile and is_valid_listing_html(html_profile):
                                if item_id:
                                    _write_cache(item_id, html_profile)
                                return AvitoFetchResult(
                                    html=html_profile,
                                    status=AvitoFetchStatus.success,
                                    source="playwright_profile",
                                    attempts=profile_attempt,
                                )
                            detected_profile, profile_reason = detect_block_state(
                                html_profile
                            )
                            if detected_profile:
                                statuses.append(detected_profile)
                                errors.append(
                                    f"Playwright(profile): {profile_reason or detected_profile.value}"
                                )
                        continue
                statuses.append(last_status)
                await _with_retry_pause(attempt)

        if mode in ("httpx", "auto"):
            for attempt in range(1, retry_attempts + 1):
                if time.monotonic() - started_at >= budget_sec:
                    statuses.append(AvitoFetchStatus.transient_error)
                    errors.append("time_budget_exceeded")
                    return _finalize_error_result(statuses, errors)
                raw_httpx_result = await _fetch_httpx(target)
                html, status_code, http_error = _coerce_httpx_result(raw_httpx_result)
                if http_error:
                    errors.append(f"HTTP: {http_error}")
                    statuses.append(AvitoFetchStatus.transient_error)
                    await _with_retry_pause(attempt)
                    continue
                if html and is_valid_listing_html(html):
                    if item_id:
                        _write_cache(item_id, html)
                    return AvitoFetchResult(
                        html=html,
                        status=AvitoFetchStatus.success,
                        source="httpx",
                        attempts=attempt,
                    )
                detected, reason = detect_block_state(html, http_status=status_code)
                if detected:
                    statuses.append(detected)
                    errors.append(f"HTTP({status_code}): {reason or detected.value}")
                else:
                    statuses.append(AvitoFetchStatus.invalid_html)
                    errors.append(f"HTTP({status_code}): invalid listing html")
                await _with_retry_pause(attempt)

    # Последний эшелон: ScrapingBee (если задан ключ). Идём по основному
    # desktop-URL; сначала без JS-рендера (дешевле по кредитам), при неудаче —
    # один раз с рендером. Все прямые источники к этому моменту исчерпаны.
    if settings.scrapingbee_enabled:
        render_modes = [bool(settings.scrapingbee_render_js)]
        if not settings.scrapingbee_render_js:
            render_modes.append(True)
        for render_js in render_modes:
            if time.monotonic() - started_at >= budget_sec:
                statuses.append(AvitoFetchStatus.transient_error)
                errors.append("time_budget_exceeded")
                return _finalize_error_result(statuses, errors)
            label = f"ScrapingBee(render_js={str(render_js).lower()})"
            try:
                html = await _fetch_scrapingbee(url, render_js=render_js)
            except Exception as exc:
                statuses.append(AvitoFetchStatus.transient_error)
                errors.append(f"{label}: {exc}")
                continue
            if html and is_valid_listing_html(html):
                if item_id:
                    _write_cache(item_id, html)
                return AvitoFetchResult(
                    html=html,
                    status=AvitoFetchStatus.success,
                    source="scrapingbee",
                    attempts=1,
                )
            detected, reason = detect_block_state(html)
            if detected:
                statuses.append(detected)
                errors.append(f"{label}: {reason or detected.value}")
            elif html:
                statuses.append(AvitoFetchStatus.invalid_html)
                errors.append(f"{label}: invalid listing html")
            else:
                statuses.append(AvitoFetchStatus.transient_error)
                errors.append(f"{label}: no_response")

    return _finalize_error_result(statuses, errors)


async def warmup_avito_session(url: str | None = None) -> AvitoFetchResult:
    target = normalize_avito_url(url or DEFAULT_WARMUP_URL)
    started_at = time.monotonic()
    budget_sec = max(10.0, float(settings.avito_fetch_time_budget_sec))
    retry_attempts = max(1, min(3, int(settings.avito_fetch_retry_attempts)))
    errors: list[str] = []
    statuses: list[AvitoFetchStatus] = []

    proxy_config = _build_proxy_config()
    if proxy_config.issues:
        statuses.append(AvitoFetchStatus.transient_error)
        errors.append(f"proxy_invalid_config:{','.join(proxy_config.issues)}")
        return _finalize_error_result(statuses, errors)

    for attempt in range(1, retry_attempts + 1):
        if time.monotonic() - started_at >= budget_sec:
            statuses.append(AvitoFetchStatus.transient_error)
            errors.append("time_budget_exceeded")
            return _finalize_error_result(statuses, errors)
        try:
            html = await _fetch_playwright(target, use_persistent=True)
        except Exception as exc:
            statuses.append(AvitoFetchStatus.transient_error)
            errors.append(f"Playwright(profile): {exc}")
            await _with_retry_pause(attempt)
            continue
        detected, reason = detect_block_state(html)
        if not detected:
            return AvitoFetchResult(
                html=None,
                status=AvitoFetchStatus.success,
                reason="warmup_ready",
                action_required=None,
                source="playwright_profile",
                attempts=attempt,
                user_message="Сессия Avito прогрета и готова к парсингу.",
                diagnostics={"proxy": get_proxy_diagnostics()},
            )
        statuses.append(detected)
        errors.append(f"Playwright(profile): {reason or detected.value}")
        if detected == AvitoFetchStatus.captcha:
            return _finalize_error_result(statuses, errors)
        await _with_retry_pause(attempt)

    return _finalize_error_result(statuses, errors)
