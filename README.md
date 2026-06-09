# AutoRewier

B2C-сервис на Python для проверки автомобиля перед покупкой или перепродажей.

## Возможности

- **Веб-кабинет** — регистрация, история, новая проверка, отчёт, подписка
- **Telegram-бот** — тот же сценарий для мобильных пользователей
- Парсинг объявлений: Avito, Auto.ru, Drom
- **Цены на запчасти**: поиск на Авито (со ссылками для пользователя) + ориентиры из магазинов Exist/Emex **без ссылок**
- **Autocode** — проверка VIN (история, ограничения; нужен B2B-доступ)
- **Подписка Pro** — ЮKassa, безлимит проверок
- Чеклист осмотра, риски, режим перекупщика
- REST API
- JSON-логи, базовые Prometheus-метрики, rate limiting

## Быстрый старт

```bash
cd autorewier
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Заполните `.env` (минимум `WEB_SECRET_KEY`, для бота — `TELEGRAM_BOT_TOKEN`).

## Docker

Базовый `docker-compose.yml` поднимает:
- `api` (FastAPI + Jinja + собранный Vue на `/app`)
- `bot` (Telegram-бот)

```bash
docker compose up --build -d
```

- Лендинг/Jinja: http://127.0.0.1:8000/
- Vue SPA: http://127.0.0.1:8000/app
- API docs: http://127.0.0.1:8000/docs

Перезапуск/релод после изменений:

```bash
docker compose up --build -d --force-recreate
docker compose logs -f api
docker compose logs -f bot
docker compose down
```

Если хотите запускать только API без бота:

```bash
docker compose up --build -d api
```

### Прод/VPS с доменом и HTTPS

Есть оверлей `docker-compose.vps.yml` + `deploy/Caddyfile`.

1) В `.env` заполните:

```env
APP_DOMAIN=example.com
WEB_SECRET_KEY=...
TELEGRAM_BOT_TOKEN=...
```

2) На VPS проверьте DNS: `A` запись домена указывает на IP сервера.

3) Запуск:

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml up --build -d
```

Caddy автоматически выпустит TLS-сертификат для `APP_DOMAIN`.

4) Проверка:

```bash
docker compose ps
docker compose logs -f caddy
docker compose logs -f api
```

Полный пошаговый гайд: `docs/VPS_DEPLOY.md`.

### Веб + API (один процесс)

```bash
python run_api.py
```

- Лендинг: http://127.0.0.1:8000/
- Кабинет: http://127.0.0.1:8000/cabinet
- API docs: http://127.0.0.1:8000/docs

### Vue Frontend (Vite)

Новый SPA-фронтенд находится в `frontend/` и не заменяет текущие Jinja-страницы.

Минимальная установка инструментов:

1. Установите Node.js LTS (рекомендуется 20.x): [nodejs.org](https://nodejs.org/)
2. Проверьте версии:

```bash
node -v
npm -v
```

```bash
cd frontend
npm install
npm run dev
```

- Dev режим: http://127.0.0.1:5173 (проксирует `/api` на backend)
- Прод-сборка: `npm run build`
- После сборки приложение отдается FastAPI по адресу: http://127.0.0.1:8000/app
- Основные Jinja-маршруты (`/`, `/cabinet`, `/cabinet/new` и т.д.) продолжают работать как прежде.

### Telegram-бот

```bash
python run_bot.py
```

## Веб-кабинет

1. Регистрация на `/cabinet/register`
2. **Новая проверка** — ссылка, VIN, дефекты
3. Отчёт: риски, чеклист, **блок запчастей** (кликабельные объявления только с Авито)
4. **VIN** — кнопка запроса отчёта Autocode
5. **После осмотра** — итоговый пересчёт
6. **Подписка** — Pro через ЮKassa (без ключей — dev-активация по кнопке)

## Цены на запчасти (правило ссылок)

| Источник | Для пользователя |
|----------|------------------|
| **Avito** | Цены + прямые ссылки на объявления |
| **Exist.ru, Emex.ru** | Только диапазон цен в тексте, **без ссылок** |

Сервис объединяет данные в оценку `estimate_min` / `estimate_max`.

## Autocode

В `.env`:

```
AUTOCODE_USER=
AUTOCODE_PASSWORD=
AUTOCODE_DOMAIN=
AUTOCODE_REPORT_TYPE_UID=тип_отчёта@домен
```

Документация: https://b2bapi.avtocod.ru/docs/

Без ключей работает **демо-режим** с пояснением в отчёте.

## ЮKassa

```
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
YOOKASSA_RETURN_URL=http://127.0.0.1:8000/cabinet/subscription?paid=1
```

Webhook для продакшена: `POST /api/v1/payments/webhook/yookassa`

Локально без ЮKassa dev-активация доступна только если `ALLOW_DEV_PAYMENT_BYPASS=true` и `ENVIRONMENT!=production`.

Webhook hardening:
- проверка IP-источника по allowlist (`YOOKASSA_WEBHOOK_ALLOWLIST`)
- сверка статуса платежа через API ЮKassa перед активацией подписки
- идемпотентная обработка повторных событий

## API

Авторизация (один из вариантов):

- Cookie `autorewier_session` (веб)
- `Authorization: Bearer <jwt>` после `/api/v1/auth/login`
- `X-Telegram-Id` + `X-Telegram-Secret` (только при `ENABLE_TELEGRAM_HEADER_AUTH=true`)

## Observability / Ops

- Метрики: `GET /metrics` (если `METRICS_ENABLED=true`)
- Админ API (защищено `X-Admin-Token`): `GET /api/v1/admin/health`, `GET /api/v1/admin/stats`
- JSON-логи запросов включаются при `JSON_LOGS=true`

## Workers (optional)

Есть минимальный Redis-worker для тяжёлых фоновых задач/событий:

```bash
python -m app.workers.worker
```

Нужно включить `TASK_QUEUE_ENABLED=true` и указать `REDIS_URL`.

```bash
# Регистрация
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@mail.ru","password":"secret12"}'

# Проверка VIN
curl -X POST http://127.0.0.1:8000/api/v1/vin/check \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vin":"XW8ZZZ61ZCG000000","inspection_id":1}'
```

## Структура

```
app/
  api/           # REST, auth, payments, web routes
  bot/
  services/
    parts_prices.py   # Avito + магазины
    autocode.py
    subscription.py
  web/templates/
  web/static/
```

## Avito (стабильная загрузка)

Объявления открываются через **Playwright + Chromium**. Установка:

```powershell
.\scripts\setup_avito.ps1
```

Подробно: [docs/AVITO.md](docs/AVITO.md) (captcha, профиль браузера, прокси).

## Ограничения

- Avito может показать captcha на новом IP — см. docs/AVITO.md
- Парсинг магазинов запчастей может блокироваться
- Autocode списывает баланс B2B-аккаунта
- Цены на запчасти ориентировочные, не оферта магазина

## Лицензия

MIT
