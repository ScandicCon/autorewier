# Настройка .env

## Бот или сайт?

**И то, и другое** — это два входа в один продукт:

```
                    ┌─────────────────┐
                    │  Общая база     │
                    │  и логика       │
                    │  (анализ, VIN,  │
                    │   запчасти)     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       run_api.py      run_bot.py     (в будущем
       Сайт + API      Telegram        мобильное)
```

| Что запускать | Команда | Для кого |
|---------------|---------|----------|
| **Сайт (кабинет)** | `python run_api.py` | Регистрация, большой отчёт, запчасти со ссылками Avito, подписка |
| **Telegram-бот** | `python run_bot.py` | Быстрые проверки с телефона, ссылка + фото-описание |
| **Оба** | Два терминала | Один backend — история общая только если один аккаунт (email в вебе ≠ telegram_id в боте, пока не связаны) |

**Для старта достаточно сайта:** заполните `WEB_SECRET_KEY` (уже сгенерирован в `.env`) и запустите `run_api.py`.

**Бот — опционально:** добавьте `TELEGRAM_BOT_TOKEN` и второй процесс `run_bot.py`.

---

## Минимальный .env (только сайт)

```env
WEB_SECRET_KEY=<уже в .env>
WEB_BASE_URL=http://127.0.0.1:8000
API_PORT=8000
```

Остальное можно оставить пустым.

---

## Telegram-бот

1. Откройте [@BotFather](https://t.me/BotFather)
2. `/newbot` → имя и username бота
3. Скопируйте токен вида `7123456789:AAH...` в:

```env
TELEGRAM_BOT_TOKEN=7123456789:AAH...
```

4. `python run_bot.py`

---

## Autocode (реальные отчёты по VIN)

1. Договор и доступ B2B: https://b2bapi.avtocod.ru
2. В личном кабинете: логин, пароль, домен, UID типа отчёта
3. В `.env`:

```env
AUTOCODE_USER=ваш_логин
AUTOCODE_PASSWORD=ваш_пароль
AUTOCODE_DOMAIN=ваш_домен
AUTOCODE_REPORT_TYPE_UID=тип_отчёта@ваш_домен
```

Без этого VIN работает в **демо-режиме** только при `ALLOW_MOCK_SERVICES=true` и не в production.

---

## ЮKassa (оплата Pro)

1. https://yookassa.ru → магазин → `shopId` и секретный ключ
2. В `.env`:

```env
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
YOOKASSA_RETURN_URL=https://ваш-домен.ru/cabinet/subscription?paid=1
```

3. В кабинете ЮKassa укажите webhook:  
   `https://ваш-домен.ru/api/v1/payments/webhook/yookassa`

**Локально без ЮKassa:** на странице подписки кнопка «Оплатить» включает Pro для теста только при `ALLOW_DEV_PAYMENT_BYPASS=true` и `ENVIRONMENT!=production`.

---

## OpenRouter (необязательно)

Доступ к разным моделям через один API: https://openrouter.ai/keys

```env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-4o-mini
# или, например: google/gemini-2.5-flash-preview, anthropic/claude-sonnet-4
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=https://ваш-сайт.ru
OPENROUTER_APP_NAME=AutoRewier
```

Дополняет риски в отчёте; без ключа анализ работает на правилах и парсерах.

---

## Проверка

```powershell
cd c:\Users\Даниил\Desktop\autorewier
.\.venv\Scripts\activate
python run_api.py
```

Откройте http://127.0.0.1:8000/cabinet/register
