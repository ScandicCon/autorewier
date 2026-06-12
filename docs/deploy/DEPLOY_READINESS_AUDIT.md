# Аудит готовности к деплою — AutoRewier / ПОДКАПОТ

> Результат проверки `.env`, production-валидации и деплой-конфигов.
> Цель: довести до сквозного боевого деплоя Railway (backend) + Vercel (frontend).
> Составлено по итогам аудита. Дополняет существующие `deploy/DEPLOY_READY.md`, `ENV_SETUP.md`, `SETUP_CHECKLIST.md`.

---

## Краткий итог

Текущий `.env` — **dev-конфиг** (SQLite, `ENVIRONMENT` не задан, ЮKassa/Autocode пустые, локальные URL). Это нормально для разработки, но для прода нужен отдельный набор переменных. Код к проду готов: миграции запускаются при старте контейнера, порт берётся из `PORT` (Railway), CORS поддерживает credentials, фронт шлёт cookie с `credentials: include`.

Встроенная production-валидация (`STRICT_PRODUCTION_CHECKS`) на текущем `.env` в режиме `ENVIRONMENT=production` даёт **2 жёстких блокера**: `WEB_BASE_URL` без https и отсутствует `ADMIN_API_TOKEN`. Остальное — функциональные настройки (платежи, почта, БД, CORS, cookie).

**Хорошие новости:** `WEB_SECRET_KEY` уже 64 символа; в проде mock-сервисы и dev-обход платежей автоматически выключаются.

**Исправлено в ходе аудита (код):** во фронтенде `InspectionDetailView.vue` читал переменную `VITE_API_BASE`, тогда как остальной код — `VITE_API_URL`. В проде это сломало бы отправку пост-осмотра (запрос ушёл бы на домен Vercel вместо бэкенда). Унифицировано на `VITE_API_URL`.

---

## 1. Боевые переменные окружения (Railway → Variables)

Заполнить реальными значениями. Секреты — только в окружении Railway, не в репозитории.

### Критично — без этого прод не поднимется/не пройдёт валидацию

| Переменная | Значение для прода | Зачем |
|---|---|---|
| `ENVIRONMENT` | `production` | Включает hardening, выключает mock/dev-bypass |
| `WEB_SECRET_KEY` | случайные 64 симв. | Подпись сессий. **Уже задан валидный — перенести в прод** |
| `WEB_BASE_URL` | `https://<домен>` | Сейчас localhost → блокер валидации |
| `ADMIN_API_TOKEN` | случайная строка | Защита `/admin/*` → блокер валидации |
| `DATABASE_URL` | `postgresql+asyncpg://…` (Supabase/Railway PG) | Сейчас SQLite — для прода не годится |
| `CORS_EXTRA_ORIGINS` | `https://<vercel-домен>` | Иначе фронт получит CORS-ошибку |
| `WEB_COOKIE_SECURE` | `true` | Cookie только по HTTPS |
| `WEB_COOKIE_SAMESITE` | `none` | **Важно:** Vercel↔Railway — разные домены; при `lax` (дефолт) cookie не уйдёт |
| `ALLOW_MOCK_SERVICES` | `false` | Без демо-заглушек в проде |
| `ALLOW_DEV_PAYMENT_BYPASS` | `false` | Закрыть обход оплаты |
| `STRICT_PRODUCTION_CHECKS` | `true` | Чтобы прод падал при небезопасной конфигурации |

### Платежи (ЮKassa) — сейчас пусто, оплата не работает

| Переменная | Значение |
|---|---|
| `YOOKASSA_SHOP_ID` | из кабинета ЮKassa |
| `YOOKASSA_SECRET_KEY` | из кабинета ЮKassa |
| `YOOKASSA_RETURN_URL` | `https://<домен>/cabinet/subscription` (прод-URL) |
| `YOOKASSA_WEBHOOK_ALLOWLIST` | IP-диапазоны ЮKassa для вебхука |

### Почта (верификация email) — выбрать один канал

| Переменная | Значение |
|---|---|
| `RESEND_API_KEY` | ключ Resend (рекомендуется; SMTP был заблокирован) |
| либо `SMTP_HOST`/`SMTP_*` | если остаёшься на SMTP |
| `REQUIRE_EMAIL_VERIFICATION` | `true`, когда домен почты подтверждён (DKIM/SPF) |

> Напоминание: после фикса в коде в **production без рабочей почты** запрос верификации теперь возвращает явную ошибку 400, а не молчит. Это значит — домен в Resend должен быть подтверждён до включения `REQUIRE_EMAIL_VERIFICATION=true`.

### VIN (Autocode) — сейчас пусто, работает демо-режим

| Переменная | Значение |
|---|---|
| `AUTOCODE_USER` / `AUTOCODE_PASSWORD` | B2B-аккаунт Автокод |
| `AUTOCODE_DOMAIN` / `AUTOCODE_REPORT_TYPE_UID` | из договора Автокод |

Без них VIN-проверка отдаёт демо-данные (для запуска допустимо, но реальная ценность фичи — только с ключами). Помни про экономику: полный отчёт ~60 ₽ — держи его платной опцией (см. `guides/LAUNCH_AND_PROFIT_PLAN.md`).

### Масштабирование (опционально, можно позже)

| Переменная | Значение |
|---|---|
| `REDIS_URL` | `redis://…` (Railway Redis) |
| `TASK_QUEUE_ENABLED` | `true` — вынести парсинг/VIN в воркер |
| `RATE_LIMIT_STORAGE` | `redis`, если несколько инстансов API |

---

## 2. Frontend (Vercel)

- **Root Directory** проекта в Vercel = `frontend/` (там `package.json`; в корне репо его нет).
- Переменная сборки **`VITE_API_URL`** = `https://<railway-домен>` — фронт подставит её в адрес API. Без неё фронт будет ходить на свой же домен.
- `vercel.json` уже настроен: SPA-rewrites на `index.html`, `buildCommand: npm run build`, `outputDirectory: dist`.
- Cookie cross-site работает только в связке `WEB_COOKIE_SECURE=true` + `WEB_COOKIE_SAMESITE=none` на бэкенде (см. раздел 1).

---

## 3. Backend (Railway)

- `Dockerfile` собирает фронт + бэк, **запускает миграции при старте**: `alembic upgrade head && python run_api.py`. Отдельный шаг миграций не нужен.
- Порт берётся из `PORT` (Railway проставляет автоматически).
- **Внимание:** Dockerfile ставит Playwright + Chromium (тяжёлый, ~прожорлив по памяти). По плану выбран **Вариант B (ScrapingBee)** — после перехода на скрейпинг-API этот слой можно убрать из образа и облегчить контейнер/память.
- Поднять **Postgres** (Railway или Supabase) и прокинуть `DATABASE_URL` (asyncpg).

---

## 4. Сквозная проверка после деплоя (smoke-тест)

Пройти руками весь путь на проде:

1. Регистрация → письмо верификации дошло → вход.
2. Создать проверку (ручной ввод авто) → отчёт с рисками и вердиктом.
3. Скачать PDF-отчёт (`GET /inspections/{id}/pdf`).
4. Оплатить Pro через ЮKassa (тестовый платёж) → вебхук → подписка активна → лимит снят.
5. Проверить `/api/v1/health` (должен возвращать `status`) и `/admin/health` с `X-Admin-Token`.
6. Парсинг объявления (после интеграции ScrapingBee) — на реальной ссылке.

---

## 5. Чего НЕ хватает в коде (из ранее найденного) — бэклог перед публичным запуском

- Смена пароля по старому паролю (`/auth/password-change`) — не реализована (есть только reset через email).
- Отдельный шаг `/analyze` и обогащение рисков полями `evidence/confidence/priority` — анализ сейчас при создании.
- Юридические страницы (оферта, политика, согласие 152-ФЗ) — обязательны до рекламы.
- Sentry (мониторинг ошибок) и бэкапы БД.

---

## Порядок действий

1. Завести Postgres + Redis (опц.) на Railway.
2. Прописать боевые переменные из раздела 1 в Railway Variables.
3. Vercel: Root = `frontend/`, задать `VITE_API_URL`, задеплоить.
4. Прогнать smoke-тест из раздела 4.
5. Перейти на ScrapingBee для Avito и облегчить Docker-образ.
6. Юр-страницы + Sentry + бэкапы → публичный запуск.
