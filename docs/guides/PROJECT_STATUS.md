# AutoRewier / ПОДКАПОТ — Статус проекта (факт)

> Полный разбор проекта по факту на основе анализа кода, тестов и документации.
> Дата проверки: **18 июня 2026** (обновлено после правок: cookie consent, смена пароля, CI). Этот документ отражает реальное состояние репозитория, а не план.
> План см. `PROJECT_PLAN.md` и `LAUNCH_AND_PROFIT_PLAN.md`; аудит деплоя — `../deploy/DEPLOY_READINESS_AUDIT.md`.

---

## 0. Итог за 30 секунд

Проект **технически почти готов**. Бизнес-логика зрелая (~11 000 строк Python в `app/`), фронт на Vue 3 собран, бот работает, миграции есть, тесты по ключевым модулям **зелёные**. Локальный `.env` уже содержит реальные ключи (OpenRouter, SMTP, Autocode, ЮKassa). Sentry и PostHog заведены в коде.

Что осталось — это **не разработка, а вывод в прод**: прописать боевые переменные в Railway/Vercel, проверить сквозной деплой, платежи и почту в бою, закрыть юридическую часть и устойчивость парсинга. Главный финансовый риск — полные VIN-отчёты Autocode (держать платной опцией, не в безлимите).

Легенда: ✅ сделано · 🟡 частично / нужна проверка в бою · ⬜ не сделано

---

## 1. Что сделано ✅

### Бэкенд и бизнес-логика
- ✅ Ядро анализа (`services/analysis.py`): риски, нормы пробега РФ, расчёт ремонта, экономика перепродажи, вердикт.
- ✅ Парсеры Avito / Drom / Auto.ru (`services/parsers/`) на Playwright: капча, кэш, ретраи, прокси, профиль браузера.
- ✅ Цены запчастей (`parts_prices.py`): Avito со ссылками + магазины как ориентир.
- ✅ Autocode (VIN): интеграция B2B + демо-режим без ключей.
- ✅ Подписка Pro через ЮKassa (`security/yookassa.py`, `services/subscription.py`): вебхук, allowlist IP, идемпотентность.
- ✅ LLM-обогащение: текст, анализ фото (vision), транскрипция голоса (Whisper), генерация объявления, помощник в торге, сравнение с рынком.
- ✅ Мониторинг объявлений (`listing_monitor.py`) + Redis-воркер (`workers/worker.py`).
- ✅ PDF-отчёты (reportlab), чеклист осмотра.
- ✅ VIN-квоты и пакеты отчётов (миграция `20260612_04`), OAuth/соц-вход (миграция `20260612_05`).

### API
- ✅ REST: auth, inspections (CRUD + пост-осмотр), сравнение, VIN (sync/async), PDF, мониторинг, платежи, админ (`/health`, `/stats`).
- ✅ Три способа авторизации: cookie-сессия, JWT Bearer, Telegram-заголовки.

### Фронтенд (Vue 3 + Vite)
- ✅ Экраны: Landing, Login, Register, ForgotPassword, ResetPassword, VerifyEmail, Dashboard, NewInspection, InspectionDetail, OAuthCallback.
- ✅ **Юридические страницы созданы:** `OfertaView.vue`, `PrivacyView.vue`, `ContactsView.vue` (контент проверить — см. раздел 2).
- ✅ Прод-сборка в `frontend/dist`, `vercel.json` настроен (SPA-rewrites, Vite).

### Telegram-бот
- ✅ Полный сценарий проверки (URL → предпочтения → данные авто → дефекты → режим перекупа → целевая цена), чеклист, пост-осмотр.

### Инфраструктура и качество
- ✅ Конфиг через pydantic-settings (~80 параметров) + production-валидация.
- ✅ Rate limiting, JSON-логи, Prometheus `/metrics`, админ-API по токену.
- ✅ Docker (Dockerfile + миграции при старте), docker-compose (base + VPS-оверлей с Caddy/HTTPS).
- ✅ Alembic: 6 миграций, идемпотентные, под Supabase/asyncpg.
- ✅ Тесты: ранее «красные» модули (`negotiation`, `image_analysis_llm`, `market_comparison`, `pdf_report`, `password_confirm`) — **сейчас все зелёные (34 passed)**.

### Наблюдаемость (заведено в коде)
- ✅ **Sentry** — код подключён в `app/config.py`, `app/main.py`, `frontend/src/main.js` (включается при `SENTRY_DSN` / `VITE_SENTRY_DSN`).
- ✅ **PostHog** — код в `frontend/src/main.js`, `app/config.py`, `app/services/analytics.py`. Локальные `.env` настроены (этот разбор). Осталось прописать в проде — см. раздел 2.

### Ключи в локальном `.env` (dev)
- ✅ Заданы: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `WEB_SECRET_KEY`, `OPENROUTER_*`, `SMTP_*`, `AUTOCODE_*`, `YOOKASSA_*`, `POSTHOG_*`.

---

## 2. Что осталось 🔧

### 2.1. Критично — вывод в прод (без этого сайт не «живой»)

- ⬜ **Боевые переменные в Railway** (в локальном `.env` их нет — это нормально, они только для прода):
  `ENVIRONMENT=production`, `WEB_BASE_URL=https://…`, `ADMIN_API_TOKEN`, `CORS_EXTRA_ORIGINS=https://<vercel>`, `WEB_COOKIE_SECURE=true`, `WEB_COOKIE_SAMESITE=none`, `ALLOW_MOCK_SERVICES=false`, `ALLOW_DEV_PAYMENT_BYPASS=false`, `STRICT_PRODUCTION_CHECKS=true`, прод-`DATABASE_URL` (Postgres, не SQLite).
- 🟡 **PostHog в проде** (в работе): добавить `VITE_POSTHOG_KEY` + `VITE_POSTHOG_HOST` в Vercel (и сделать **Redeploy** — Vite вшивает при сборке), `POSTHOG_API_KEY` + `POSTHOG_HOST` в Railway. Проверить регион EU/US.
- 🟡 **Sentry в проде**: код готов, но `SENTRY_DSN` / `VITE_SENTRY_DSN` нигде не заданы — получить DSN и прописать в Railway + Vercel.
- ⬜ **Сквозной деплой end-to-end**: Railway (backend + Postgres) ↔ Vercel (frontend, Root = `frontend/`, `VITE_API_URL`) ↔ домен. Прогнать smoke-тест из `DEPLOY_READINESS_AUDIT.md` (раздел 4).
- ⬜ **Платежи в бою**: реальный платёж ЮKassa → вебхук → активация Pro; проверить allowlist IP, `YOOKASSA_RETURN_URL`, выключить dev-bypass.
- 🟡 **Email-верификация в бою**: ключи SMTP/Resend заданы локально, но нужно подтвердить домен (DKIM/SPF) и `REQUIRE_EMAIL_VERIFICATION=true` на проде.

### 2.2. Важно — стабильность ключевых фич

- ⬜ **Устойчивость парсинга Avito** — главный риск воронки. По плану: переход на скрейпинг-API (**ScrapingBee**) вместо своего Chromium + мониторинг доли успехов + graceful-фолбэк на ручной ввод.
- 🟡 **Autocode B2B** — ключи заданы; проверить реальное списание баланса, обработку пустых отчётов, лимиты на пользователя. Полный отчёт (~60₽) держать **платной опцией, не в безлимите Pro**.
- ⬜ **Воркер мониторинга в проде** — поднять как отдельный процесс на Railway (`TASK_QUEUE_ENABLED=true`, `REDIS_URL`), проверить доставку уведомлений (Telegram/email).
- ⬜ **Единый фронтенд** — решить судьбу двух UI (Vue SPA vs legacy Jinja-кабинет в `web/`), убрать дублирование.

### 2.3. Перед публичным запуском

- 🟡 **Юр-страницы** — файлы `OfertaView/PrivacyView/ContactsView` созданы; проверить содержание: оферта, политика конфиденциальности, согласие 152-ФЗ, дисклеймер «цены ориентировочные, не оферта».
- ✅ **Cookie consent для аналитики** — реализован: баннер `components/CookieConsent.vue`, PostHog инициализируется только после согласия (`main.js` → `initAnalytics`), выбор хранится в localStorage. Адаптирован под мобильные.
- ✅ **Смена пароля по старому паролю** (`/auth/password-change`) — реализована: схема `PasswordChangeRequest`, сервис `change_password`, эндпоинт + 4 теста (все зелёные).
- ⬜ **Бэкапы БД** и план восстановления.
- ✅ **CI/CD** — добавлен `.github/workflows/ci.yml`: pytest (166 тестов, изолированное окружение, таймаут на тест) + сборка фронта на push/PR в main. Браузерный тест помечен маркером `integration` и исключён из быстрого прогона.

### 2.4. Технический долг / улучшения (не блокеры)

- 🟡 Зелёный `pytest` как CI-гейт — частично: CI добавлен, маркер `integration` введён и применён к `test_playwright_smoke_e2e`. При полном локальном прогоне один тест может подвисать на реальном сетевом вызове (живые ключи в dev-`.env`) — в CI это закрыто `--timeout` + mock-окружением.
- ⬜ Чистка репозитория (крупные PNG, статусные `.md` в архив).
- ⬜ Перенос Vue-компонентов на TypeScript; дашборды Grafana поверх Prometheus.

---

## 3. Приоритетный порядок действий

1. **Прод-переменные в Railway + Vercel** (раздел 2.1) → поднять стейджинг.
2. **Сквозной деплой** Railway ↔ Vercel ↔ домен, smoke-тест: регистрация → проверка авто → PDF.
3. **Платежи и email в бою.**
4. **PostHog + Sentry** ключи в прод, проверить приём событий/ошибок.
5. **Устойчивость парсинга** (ScrapingBee) и Autocode-лимиты.
6. **Воркер мониторинга** + уведомления.
7. **Cookie consent + юр-страницы** (проверка контента) + бэкапы.
8. **CI/CD** (GitHub Actions) → публичный запуск.

---

## 4. Главные риски

1. **Парсинг Avito** (капча/блок на новом IP) — самая хрупкая точка. → ScrapingBee + мониторинг + фолбэк.
2. **Стоимость Autocode** (~60₽/полный отчёт) — драйвер убытка. → платная опция, лимиты.
3. **Реклама вперёд экономики** — не масштабировать до подтверждения себестоимости на живых данных.
4. **Два UI** (Vue + Jinja) — риск рассинхрона и двойной поддержки.
5. **Внешние зависимости** (OpenRouter, ЮKassa, Resend, ScrapingBee) — держать мягкую деградацию.
