# Changeset: поиск детали по фото + слой загрузки ScrapingBee

> Готовый набор изменений для влития одной веткой/PR. Собрано ассистентом.
> Ветка: **`feat/photo-part-search`**. Дата: 29 июня 2026.
>
> Принцип «без конфликтов»: почти всё — **новые файлы**; правки существующих
> файлов — минимальные и аддитивные (импорт/регистрация/одна функция).

---

## 1. Что добавлено

**Фича «поиск б/у детали по фото».** Пользователь загружает фото детали (+ необязательная
подсказка) → нейросеть распознаёт деталь → сервис ищет похожие объявления на Авито со
ссылками. Честный дисклеймер о совместимости, демо-режим без ключей, мягкая деградация.
Экран в кабинете: `/app/parts`.

**Слой устойчивой загрузки `scraping.py`.** Переиспользуемая обёртка: есть `SCRAPINGBEE_API_KEY`
→ грузим через ScrapingBee (обход капчи Авито), нет → обычный httpx. Поиск запчастей
переведён на этот слой. Большой `parsers/avito_fetch.py` намеренно НЕ тронут.

---

## 2. Файлы

### Новые
- `app/services/part_finder.py` — ядро фичи (vision-распознавание + поиск по Авито).
- `app/api/part_finder_routes.py` — эндпоинт `POST /api/v1/parts/find-by-photo`.
- `tests/test_part_finder.py` — тесты фичи.
- `app/services/scraping.py` — слой загрузки HTML с опциональным ScrapingBee.
- `tests/test_scraping.py` — тесты слоя загрузки.
- `frontend/src/api/partFinderApi.js` — клиент фичи.
- `frontend/src/components/PartFinderPanel.vue` — UI-панель.
- `frontend/src/views/PartFinderView.vue` — экран `/app/parts`.
- `docs/SOURCE_OF_TRUTH.md`, `docs/CHANGESET_photo_part_search.md` — документация.

### Изменённые (минимально, аддитивно)
- `app/main.py` — +2 строки: импорт и регистрация роутера.
- `frontend/src/router/index.js` — +1 строка: маршрут `/app/parts`.
- `app/config.py` — настройки `SCRAPINGBEE_*` + свойство `scrapingbee_enabled`.
- `app/services/parts_prices.py` — `_fetch_html` теперь идёт через `scraping.fetch_html`.
- `.env.example` — блок переменных ScrapingBee.

---

## 3. Как влить (git)

```bash
git checkout -b feat/photo-part-search

git add \
  app/services/part_finder.py app/api/part_finder_routes.py tests/test_part_finder.py \
  app/services/scraping.py tests/test_scraping.py \
  frontend/src/api/partFinderApi.js frontend/src/components/PartFinderPanel.vue \
  frontend/src/views/PartFinderView.vue \
  app/main.py app/config.py app/services/parts_prices.py \
  frontend/src/router/index.js .env.example \
  docs/SOURCE_OF_TRUTH.md docs/CHANGESET_photo_part_search.md

git commit -m "feat: поиск б/у детали по фото + слой загрузки ScrapingBee"
git push -u origin feat/photo-part-search
```

Затем открыть PR в `main` (описание — в разделе 6).

---

## 4. Проверка перед PR

```bash
# Бэкенд-тесты новых модулей
pytest tests/test_part_finder.py tests/test_scraping.py -v

# (опционально) весь сьют как CI-гейт
pytest -m "not integration"

# Фронтенд: сборка + ручной просмотр экрана
cd frontend
npm install
npm run build           # или: npm run dev → открыть http://127.0.0.1:5173/app/parts
```

Чек-лист:
- [ ] `pytest tests/test_part_finder.py tests/test_scraping.py -v` — зелёный.
- [ ] `npm run build` проходит без ошибок.
- [ ] Экран `/app/parts` открывается под авторизацией.
- [ ] (если есть ключ OpenRouter) загрузка фото даёт распознанную деталь.
- [ ] (если есть ключ ScrapingBee) поиск возвращает реальные объявления.

---

## 5. Переменные окружения (опционально, для боевого режима)

```env
# Реальное ИИ-распознавание детали (иначе демо-режим)
OPENROUTER_API_KEY=...

# Устойчивый поиск по Авито в обход капчи (иначе прямой httpx)
SCRAPINGBEE_API_KEY=...
SCRAPINGBEE_PREMIUM_PROXY=true   # резидентные прокси РФ — для Авито
SCRAPINGBEE_COUNTRY_CODE=ru
SCRAPINGBEE_RENDER_JS=false
```

Без ключей всё работает в демо/прямом режиме — ничего не падает.

---

## 6. Описание для PR

**Заголовок:** feat: поиск б/у детали по фото + слой загрузки ScrapingBee

**Суть:** новая фича — поиск похожей б/у детали на Авито по фотографии (vision-распознавание
+ существующий поиск запчастей). Плюс переиспользуемый слой загрузки `scraping.py` с
опциональным ScrapingBee для устойчивости к капче; поиск запчастей переведён на него.

**Конфликт-риск:** низкий. Почти всё — новые файлы; правки существующих минимальны
(импорт/регистрация/одна функция/настройки). `parsers/avito_fetch.py` не тронут.

**Известное ограничение:** точную совместимость и OEM детали по фото определить нельзя —
позиционируется как «похожие детали», в ответ зашит дисклеймер.

**Дальше (отдельными задачами):** перенаправить основной парсер объявлений
`avito_fetch.py` на слой `scraping.py`; добавить кнопку на экран кабинета (`DashboardView.vue`).
