# Стабильная загрузка Avito

Сервис открывает объявление **реальным браузером Chromium** (Playwright), а не простым HTTP-запросом.

## Установка (один раз)

```powershell
cd c:\Users\Даниил\Desktop\autorewier
.\scripts\setup_avito.ps1
```

Или вручную:

```powershell
.\.venv\Scripts\pip install playwright
.\.venv\Scripts\playwright install chromium
```

Перезапустите `python run_api.py` (на Windows **без** `--reload` — уже отключён в `run_api.py`).

## Настройки `.env`

```env
AVITO_FETCH_MODE=auto
AVITO_FETCH_TIMEOUT_MS=45000
AVITO_FETCH_RETRY_ATTEMPTS=2
AVITO_FETCH_RETRY_BACKOFF_SEC=1.2
AVITO_FETCH_TIME_BUDGET_SEC=90
AVITO_CAPTCHA_RETRY_ATTEMPTS=1
AVITO_PLAYWRIGHT_HEADLESS=true
AVITO_CACHE_ENABLED=true
AVITO_CACHE_TTL_SEC=3600
AVITO_PROXY_USERNAME=
AVITO_PROXY_PASSWORD=
```

| Переменная | Описание |
|------------|----------|
| `AVITO_FETCH_MODE` | `auto` — Playwright, потом httpx; `playwright` — только браузер |
| `AVITO_FETCH_RETRY_ATTEMPTS` | Количество повторных попыток на источник (Playwright/httpx), чтобы не падать от разовых сбоев |
| `AVITO_FETCH_RETRY_BACKOFF_SEC` | Пауза между ретраями (секунды), чтобы не попасть в быстрый цикл запросов |
| `AVITO_FETCH_TIME_BUDGET_SEC` | Общий лимит времени на одну загрузку (остановка попыток при превышении бюджета) |
| `AVITO_CAPTCHA_RETRY_ATTEMPTS` | Дополнительные попытки через persistent profile при captcha (re-use cookies) |
| `AVITO_CACHE_ENABLED` | Кэш HTML на 1 час (быстрее повторные проверки) |
| `AVITO_BROWSER_PER_REQUEST` | `true` — новый браузер на запрос (рекомендуется, нет «context closed») |
| `AVITO_USER_DATA_DIR` | Профиль Chrome с cookies, если `AVITO_BROWSER_PER_REQUEST=false` |
| `AVITO_PROXY` | Прокси, например `http://127.0.0.1:8080` |
| `AVITO_PROXY_USERNAME` / `AVITO_PROXY_PASSWORD` | Опциональные логин/пароль, если провайдер выдаёт отдельно от `AVITO_PROXY` |

## Ошибка «browser has been closed»

1. Закройте все окна Chromium/Chrome, запущенные Playwright.
2. Убедитесь в `.env`: `AVITO_BROWSER_PER_REQUEST=true`
3. Перезапустите: `python run_api.py`
4. Повторите загрузку объявления (подождите 15–40 сек).

## Если появляется captcha

1. В `.env` временно: `AVITO_PLAYWRIGHT_HEADLESS=false`
2. Перезапустите сервер, загрузите **любое** объявление Avito из кабинета
3. Откроется окно браузера — пройдите проверку Avito вручную один раз
4. Cookies сохранятся в `data/avito_browser_profile`
5. Верните `AVITO_PLAYWRIGHT_HEADLESS=true`

Теперь backend сам делает bounded retry и fallback:

- desktop URL + mobile URL (`m.avito.ru`)
- Playwright -> (при captcha) retry через persistent profile
- затем httpx fallback

Если все попытки исчерпаны, API возвращает безопасный статус (`parse_status`, `parse_reason`, `action_required`) без утечки внутреннего стека.

Для явного bootstrap persistent-профиля доступен endpoint:

```http
POST /api/v1/avito/warmup
```

Он запускает bounded warm-up и возвращает тот же контракт (`status`, `reason`, `action_required`) + безопасные diagnostics по прокси (без пароля).

## Описание продавца

При загрузке объявления сервис:

1. Ждёт блок описания в браузере и нажимает «Читать полностью», если текст свёрнут.
2. Извлекает полный текст из HTML, JSON в `<script>` и `application/ld+json`.
3. Показывает его в форме в поле **«Описание продавца с Avito»** и сохраняет в проверку.
4. Отдельно выделяет строки про замены/ТО для анализа рисков.

Если описание пустое — обновите кэш: удалите файл в `data/cache/avito/` для этого ID и загрузите ссылку снова (15–40 сек).

## ScrapingBee — последний эшелон (для прода)

Если задан `SCRAPINGBEE_API_KEY`, то после неудачи Playwright и httpx загрузка
объявления уходит в ScrapingBee (резидентные RU-прокси, `premium_proxy=true`):
сначала без JS-рендера (~10 кредитов), при неудаче — один раз с рендером (~25).
Кредиты пишутся в учёт себестоимости (`cost_tracking`). Без ключа поведение
не меняется. Порядок эшелонов на проде: свой `AVITO_PROXY` → httpx → ScrapingBee.

```env
SCRAPINGBEE_API_KEY=...
SCRAPINGBEE_PREMIUM_PROXY=true
SCRAPINGBEE_COUNTRY_CODE=ru
SCRAPINGBEE_RENDER_JS=false
```

## Производственный сервер

- Используйте резидентный прокси в `AVITO_PROXY`
- Не делайте десятки запросов в секунду — включён кэш по ID объявления
- Первый запрос к объявлению: 10–30 секунд — это нормально
