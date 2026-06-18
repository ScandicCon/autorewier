# Подключение PostHog — итоги и инструкция

> Документ собран по итогам разбора чата. Содержит: суть вопроса, что уже сделано в проекте, что осталось сделать, и точную инструкцию по ключу.

## 1. Исходный вопрос

В окне PostHog «Manual SDK setup» было непонятно:
- нужно ли выбирать/«брать» все SDK из списка (Next.js, React, Vue, Web, и т.д.);
- где взять ключ и что вообще делать.

Был озвучен project token: `phc_msaN2yDjCGbASKDgM5NJEQQ9AzyDai9u9xgfYwWK4FWB`

## 2. Ответы по существу

**Не нужно брать всё из окна SDK.** Список фреймворков в «Manual SDK setup» — это просто варианты сниппета под разный стек. Нужен один, под свой проект. У этого проекта фронтенд на **Vue (Vite)**, поэтому актуален вариант Vue / Web.

**Отдельно ключ нигде брать не надо.** `phc_...` — это и есть единственный нужный ключ (project / ingest key). Кнопка «Copy project token» уже скопировала его в буфер (на скрине было «Copied Project token to clipboard»).

**Это публичный ключ.** `phc_...` предназначен для вставки в клиентский код и виден посетителям сайта — это не секрет, паниковать не нужно. Настоящие секреты в PostHog — Personal API keys (`phx_...`), их показывать нельзя.

## 3. Что уже сделано в коде (проверено)

Интеграция PostHog **уже реализована** в репозитории — нужно только прописать переменные окружения.

| Где | Файл | Что читает |
|-----|------|------------|
| Фронтенд (Vue/Vite) | `frontend/src/main.js` | `VITE_POSTHOG_KEY`, `VITE_POSTHOG_HOST` (грузится лениво, только если ключ задан) |
| Бэкенд (FastAPI) | `app/config.py` | `posthog_api_key` (`POSTHOG_API_KEY`), `posthog_host` (`POSTHOG_HOST`, по умолчанию `https://eu.i.posthog.com`) |
| Сервис аналитики | `app/services/analytics.py` | использует настройки PostHog для серверных событий |

Логика «мягкой деградации»: без переменных окружения PostHog просто выключен, ошибок не будет.

## 4. Что осталось сделать

В `.env` / `.env.example` переменных PostHog пока **нет** — их надо добавить.

**Фронтенд** — файл `frontend/.env`:
```
VITE_POSTHOG_KEY=phc_msaN2yDjCGbASKDgM5NJEQQ9AzyDai9u9xgfYwWK4FWB
VITE_POSTHOG_HOST=https://eu.i.posthog.com
```

**Бэкенд** — корневой `.env`:
```
POSTHOG_API_KEY=phc_msaN2yDjCGbASKDgM5NJEQQ9AzyDai9u9xgfYwWK4FWB
POSTHOG_HOST=https://eu.i.posthog.com
```

Ключ один и тот же для фронта и бэка.

> ⚠️ **Проверить регион проекта.** В коде по умолчанию `eu.i.posthog.com`. Если проект в US — указать `https://us.i.posthog.com`, иначе события не дойдут. Регион виден в URL личного кабинета: `eu.posthog.com` или `us.posthog.com`.

## 5. Контекст из PRD (раздел 8.2)

PostHog по PRD отвечает за продуктовую аналитику: воронки, удержание, A/B-эксперименты, feature flags.

Ключевые события для трекинга:
- `signup`, `email_verified`, `login`
- `listing_parse_started`, `listing_parse_success`, `listing_parse_failed`
- `inspection_created`, `report_viewed`, `pdf_downloaded`
- `vin_check_requested`, `vin_check_completed`
- `subscription_checkout_started`, `subscription_activated`
- `monitoring_added`, `monitoring_alert_sent`

Главная воронка: регистрация → первая проверка → просмотр отчёта → оплата Pro.

Разграничение инструментов:
- **Sentry** — «что сломалось и почему» (ошибки).
- **PostHog** — «что делают пользователи и где отваливаются» (продукт).
- **Prometheus** — техническое здоровье инфраструктуры.

## 6. Чек-лист

- [ ] Уточнить регион проекта PostHog (EU / US)
- [ ] Добавить `VITE_POSTHOG_KEY` и `VITE_POSTHOG_HOST` в `frontend/.env`
- [ ] Добавить `POSTHOG_API_KEY` и `POSTHOG_HOST` в корневой `.env`
- [ ] Прописать те же переменные в проде (Vercel / VPS / docker-compose)
- [ ] Проверить, что события доходят (Activity / Live events в PostHog)
- [ ] Сверить список событий из PRD с реально отправляемыми
