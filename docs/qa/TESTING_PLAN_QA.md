# ПЛАН ТЕСТИРОВАНИЯ ПОДКАПОТ - QA Strategy

**Дата:** 2026-06-08  
**Статус:** Active  
**Версия:** 0.2.0  

---

## 1. РЕГРЕССИОННЫЕ ТЕСТЫ (Baseline)

### 1.1 Views & UI Rendering

| Тест-кейс | Критерий | Инструмент | Метрика |
|-----------|----------|-----------|---------|
| **T001** Landing page загружается без ошибок | HTTP 200, нет console errors | Playwright | Response time <500ms |
| **T002** Cabinet Jinja-страницы рендерят (/, /cabinet, /cabinet/register, /cabinet/new) | No 404/500, header+footer видны | Playwright | Page render <1s |
| **T003** Vue SPA (/app) инициализируется без исключений | app:mounted event fired, no uncaught JS errors | Playwright + DevTools | Bundle injection <2s |
| **T004** Все компоненты (AuthModal, HeroSection, InspectionComposer, etc.) монтируются | DOM nodes present, props passed | Vitest (unit) | Jest coverage >80% |
| **T005** Responsive layout на mobile (375px), tablet (768px), desktop (1440px) | Нет overflow, кнопки кликабельны | Playwright via resize | Mobile Lighthouse >70 |

### 1.2 Auth Flow

| Тест-кейс | Сценарий | Ожидаемый результат | Статус |
|-----------|---------|-------------------|--------|
| **T010** Регистрация: email + пароль | POST /api/v1/auth/register | User created, session cookie set | ✓ (test_auth_payments_e2e.py) |
| **T011** Email verification: код отправлен на почту | GET /api/v1/auth/verify?token=... | email_verified=True | ✓ (test_email_verification.py) |
| **T012** Login: email + пароль вход в dashboard | POST /api/v1/auth/login → cookie | Редирект на /cabinet/dashboard | ✓ |
| **T013** Password confirm: старый пароль обязателен | POST /api/v1/auth/password-change | HTTP 400 if old_password missing | ✓ (test_password_confirm.py) |
| **T014** Session timeout: старая cookie инвалидна | Setcookie expires, переклик на protected route | Редирект на /cabinet/register | Manual |
| **T015** Logout: DELETE /api/v1/auth/logout | Session cleared, cookie deleted | HTTP 200, redirect to / | Manual |

### 1.3 Inspection Workflow

| Тест-кейс | Шаг | Проверяемое | Критерий успеха |
|-----------|-----|-----------|-----------------|
| **T020** Новая проверка: ввод VIN вручную | POST /api/v1/inspections/create + vehicle JSON | inspection.id created | ✓ (test_vehicle_analysis_e2e.py) |
| **T021** Дефекты: добавление через UI | PUT /api/v1/inspections/{id}/defects | defects array updated | ✓ |
| **T022** Анализ: вызов LLM для рисков | POST /api/v1/inspections/{id}/analyze | risks array populated (5+ элементов, каждый с evidence/rationale/confidence/priority) | ✓ (test_vehicle_analysis_e2e.py) |
| **T023** Отчет PDF: генерация | POST /api/v1/inspections/{id}/report | PDF binary returned, >100KB | ✓ (test_pdf_report.py) |
| **T024** История: список всех проверок | GET /api/v1/inspections | pagination, sort by created_at DESC | ✓ |

### 1.4 Avito Parser (с fallback)

| Тест-кейс | Входные данные | Ожидаемое поведение |
|-----------|----------------|-------------------|
| **T030** Avito URL парсится успешно | `https://www.avito.ru/...` | ParsedListing (title, price, year, mileage, defects если указаны) |
| **T031** Captcha на Avito → graceful error | Playwright exception поймана | User message: "Avito временно недоступна, введите данные вручную" |
| **T032** Invalid URL → rejection | `https://evil.com/...` | HTTP 400 "invalid listing URL" |
| **T033** Fallback to manual input | User выбрал "Ввести вручную" | POST с VehicleInput (brand, model, year, mileage) |

### 1.5 API Regression (Core Endpoints)

Запустить: `pytest tests/test_api_regression.py -v`

```python
# Покрытие:
- POST /api/v1/auth/register (duplicate email, weak password)
- POST /api/v1/auth/login (invalid credentials, missing fields)
- GET /api/v1/inspections (auth required, pagination)
- POST /api/v1/inspections/analyze (rate limiting, missing vehicle)
- GET /api/v1/metrics (if METRICS_ENABLED=true)
- GET /api/v1/health (always 200)
```

---

## 2. E2E СЦЕНАРИИ (End-to-End)

### 2.1 Playwright Suite: Registration → Inspection → Report

**Файл:** `tests/test_playwright_smoke_e2e.py` + **NEW:** `tests/test_e2e_full_journey.py`

**Prerequisite:** `RUN_PLAYWRIGHT_E2E=1 playwright install`

#### Сценарий 1: Новый пользователь → Первая проверка (Avito)

```gherkin
Scenario: New user journey with Avito listing
  Given User navigates to /cabinet/register
  When User enters email "test-user@example.com" and password "Secure123!"
  And User submits registration form
  Then User sees "Проверьте почту" message
  
  When User clicks verification link (mock или real email)
  Then email_verified = True
  
  When User navigates to /cabinet/new
  And User pastes Avito URL "https://www.avito.ru/..."
  And Playwright fetches listing via Chromium
  Then VehicleInput populated (brand, model, year, mileage from Avito)
  
  When User adds defects (scratches, dents from photos)
  And User clicks "Analyze"
  Then API calls LLM for risks (OpenAI/OpenRouter)
  And risks populated with evidence
  
  When User clicks "Generate Report"
  Then PDF downloaded successfully
  And Report contains: vehicle info + checklist + risks + parts prices
```

**Metrik:**
- Registration to first report: <3 min
- Avito parse latency: <5s (vs 10s threshold)
- PDF generation: <2s

#### Сценарий 2: Fallback - Avito недоступна

```gherkin
Scenario: User input fallback when Avito fails
  When User attempts Avito URL but captcha triggered
  Then Error message: "Avito временно недоступна"
  And User sees form to enter data manually
  
  When User enters: brand=Toyota, model=Camry, year=2018, mileage=150000
  And adds defects manually
  And clicks "Analyze"
  Then Report generated without Avito data
  And parts_prices block shows: "Цены примерные"
```

#### Сценарий 3: Сравнение двух авто

```gherkin
Scenario: Compare two inspections
  Given User has 2+ completed inspections in history
  When User selects "Inspection A" and "Inspection B"
  And User clicks "Compare"
  Then Split view shows:
    - Vehicle specs side-by-side
    - Risks comparison (Inspection A vs B)
    - Parts prices comparison
  
  When User clicks "Choose winner"
  Then Recommendation saved to DB
```

**Команда запуска:**
```bash
RUN_PLAYWRIGHT_E2E=1 pytest tests/test_playwright_smoke_e2e.py -v -s
```

### 2.2 API E2E (TestClient)

**Файл:** `tests/test_auth_payments_e2e.py`

Запустить:
```bash
pytest tests/test_auth_payments_e2e.py -v
```

**Цепочка:**
1. Register user
2. Login → get JWT token
3. Create inspection with VehicleInput
4. Add defects
5. Call /analyze → check risks structure
6. Generate PDF
7. Verify in history

---

## 3. PERFORMANCE ТЕСТЫ

### 3.1 Bundle Metrics

**Инструмент:** `npm run build` + bundlesize analyzer

```bash
cd frontend
npm run build
# Expected outputs:
# - index.js: <200KB (gzipped)
# - vendor.js: <300KB (gzipped)
# - Total dist: <500KB (gzipped)
```

**Автоматизация:**
```javascript
// frontend/vitest.config.ts - добавить
import { getSize } from 'rollup-plugin-visualizer';

test('bundle size under limit', () => {
  const size = fs.statSync('dist/index.js').size;
  expect(size).toBeLessThan(500 * 1024); // 500KB uncompressed
});
```

### 3.2 API Response Times

**Метрики по эндпоинту:**

| Endpoint | Target SLA | Alert Threshold |
|----------|-----------|-----------------|
| POST /api/v1/auth/register | <200ms | >500ms |
| POST /api/v1/auth/login | <150ms | >300ms |
| POST /api/v1/inspections/create | <500ms | >1s (parsing может быть долгим) |
| POST /api/v1/inspections/{id}/analyze | <5s (LLM call) | >10s |
| GET /api/v1/inspections | <300ms (with pagination) | >800ms |
| POST /api/v1/inspections/{id}/report | <3s (PDF gen) | >6s |

**Мониторинг:**
```bash
# В production (если METRICS_ENABLED=true):
curl http://localhost:8000/metrics | grep http_request_duration_seconds
```

### 3.3 Lighthouse (Mobile)

**Инструмент:** Lighthouse CLI / PageSpeed Insights

```bash
npm install -g lighthouse

# Dev mode (Vite)
npm run dev
# В другом терминале:
lighthouse http://127.0.0.1:5173 --view

# Prod build
npm run build
# Serve dist/ статически
lighthouse http://127.0.0.1:8000/app --view
```

**Целевые метрики:**
- Performance: >80 на mobile
- Accessibility: >90
- Best Practices: >90
- SEO: >80 (для лендинга)

---

## 4. КРИТИЧЕСКИЕ ОШИБКИ (Must Not Skip)

### 4.1 Error Handling & Graceful Degradation

| Сценарий | Текущая обработка | Требуемое поведение | Статус проверки |
|----------|------------------|-------------------|-----------------|
| **E001** Avito парсер crashes | ❓ | User-friendly message + fallback form | Тест: T031 |
| **E002** LLM API error (OpenAI rate limit) | ❓ | "Анализ временно недоступен, попробуйте позже" | Новый тест |
| **E003** PDF generation fails (reportlab crash) | ❓ | "Ошибка генерации отчета, контакт поддержку" | Новый тест |
| **E004** Backend недоступен (503) | ❓ | Offline page или "Сервис на техническом обслуживании" | Новый тест |
| **E005** Database connection fail | ❓ | 500 error + logs, alert ops team | Existing (health check) |
| **E006** Parts prices API blocks requests | ❓ | Show "Цены недоступны" block instead of blank | Новый тест |
| **E007** Авто с неправильным VIN | ❓ | "Проверьте VIN-код" message | Новый тест |

### 4.2 Секьюрность

| Сценарий | Проверка | Метод |
|----------|----------|--------|
| **SEC001** SQL injection в VIN | Pydantic validation | Grep: `VehicleInput` schema |
| **SEC002** CORS misconfiguration | CORS middleware check | Тест: test_cors_regression.py |
| **SEC003** Session hijacking | HttpOnly, Secure flags | Inspect Set-Cookie headers |
| **SEC004** XSS в части prices (если HTML) | HTML escaping | Manual review: parts_prices.py |
| **SEC005** Rate limiting on auth endpoints | X-RateLimit-* headers | Stress test: 100 reqs/sec |

Запустить security-review перед продакшеном:
```bash
# (требует GitHub Actions or manual)
pytest tests/ -m security -v
```

---

## 5. АВТОМАТИЗИРОВАННЫЕ ТЕСТЫ (RUN NOW)

### 5.1 Запуск всех тестов

```bash
# Установка зависимостей
pip install -r requirements.txt

# Backend unit + API regression
pytest tests/test_api_regression.py -v
pytest tests/test_auth_payments_e2e.py -v
pytest tests/test_vehicle_analysis_e2e.py -v
pytest tests/test_email_verification.py -v
pytest tests/test_password_confirm.py -v
pytest tests/test_cors_regression.py -v
pytest tests/test_pdf_report.py -v

# Avito-specific (может потребоваться Chromium)
pytest tests/test_avito_captcha_resilience.py -v

# Parser regression
pytest tests/test_listing_parsers_regression.py -v
pytest tests/test_drom_parser.py -v
```

**Итого:** ~15-20 мин на полный прогон

### 5.2 Frontend unit tests

```bash
cd frontend
npm install
npm run test

# Coverage report:
npm run test -- --coverage
```

### 5.3 Frontend + Backend integration (Vue + API)

```bash
# Terminal 1: Start backend
python run_api.py
# или docker:
docker compose up -d api

# Terminal 2: Start frontend dev
cd frontend
npm run dev

# Terminal 3: Run Playwright
RUN_PLAYWRIGHT_E2E=1 pytest tests/test_playwright_smoke_e2e.py::test_playwright_register_and_dashboard_smoke -v -s
```

### 5.4 Быстрая smoke-проверка (5 минут)

```bash
# 1. Фронтенд сборка
cd frontend && npm run build

# 2. API health
curl http://127.0.0.1:8000/api/v1/health

# 3. Регистрация
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.ru","password":"Test123!"}'

# 4. Вьюхи (Jinja)
curl -s http://127.0.0.1:8000/ | grep -q "AutoRewier" && echo "Landing OK"
curl -s http://127.0.0.1:8000/cabinet/register | grep -q "Регистрация" && echo "Register page OK"

# 5. Vue SPA
curl -s http://127.0.0.1:8000/app | grep -q "app" && echo "Vue app OK"
```

---

## 6. МЕТРИКИ & DASHBOARD

### 6.1 Ключевые метрики для мониторинга

| Метрика | Текущее | Целевое | Частота проверки |
|---------|---------|---------|------------------|
| **Uptime** | — | >99.5% | Hourly (Prometheus) |
| **API latency (p95)** | — | <1s | Real-time |
| **Error rate** | — | <0.5% | Real-time |
| **Bundle size (gzipped)** | ❓ | <500KB | Per build |
| **Lighthouse score (mobile)** | ❓ | >80 Performance | Per release |
| **Test coverage** | ❓ | >70% | Per commit |
| **Avito parse success rate** | ❓ | >95% (с fallback) | Daily |

### 6.2 Prometheus метрики (если `METRICS_ENABLED=true`)

```bash
# Доступно на GET /metrics
http_request_duration_seconds_bucket{endpoint="/api/v1/inspections/analyze"}
http_request_total{status="200"}
http_request_total{status="500"}
```

### 6.3 Custom observability

**Добавить логирование в критичные места:**

```python
# app/services/inspections.py
logger.info("analyze_inspection_start", extra={
    "inspection_id": id,
    "vehicle": vehicle,
})
# ... analysis ...
logger.info("analyze_inspection_complete", extra={
    "inspection_id": id,
    "risks_count": len(risks),
    "duration_ms": elapsed,
})

# Структурированные логи (JSON) если JSON_LOGS=true
```

Просмотр логов:
```bash
docker compose logs -f api | jq .  # если JSON логи
# или
tail -f /var/log/autorewier/api.log
```

---

## 7. REGRESSION TEST SUITE (Git CI/CD)

### 7.1 GitHub Actions (`.github/workflows/test.yml`)

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install backend deps
        run: |
          python -m pip install -r requirements.txt
          playwright install
      
      - name: Run API regression tests
        run: pytest tests/test_api_regression.py -v
      
      - name: Run E2E tests (auth + payments)
        run: pytest tests/test_auth_payments_e2e.py -v
      
      - name: Run vehicle analysis tests
        run: pytest tests/test_vehicle_analysis_e2e.py -v
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install frontend deps
        run: cd frontend && npm install
      
      - name: Run frontend tests
        run: cd frontend && npm run test
      
      - name: Build frontend
        run: cd frontend && npm run build
      
      - name: Check bundle size
        run: |
          SIZE=$(du -sb frontend/dist | cut -f1)
          if [ $SIZE -gt 524288 ]; then echo "Bundle >500KB!"; exit 1; fi
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/coverage.xml
```

### 7.2 Pre-commit hook (`.git/hooks/pre-commit`)

```bash
#!/bin/bash
# Быстрая smoke-проверка перед commit

echo "Running pre-commit tests..."

# Backend lint
python -m py_compile app/**/*.py || exit 1

# Frontend lint (if Node installed)
if command -v npm &> /dev/null; then
  cd frontend && npm run lint || exit 1
fi

echo "Pre-commit checks passed!"
```

---

## 8. ТЕСТОВЫЕ ДАННЫЕ & FIXTURES

### 8.1 Test User

```json
{
  "email": "qa-tester@podkapot.test",
  "password": "SecureTest123!",
  "phone": "+79991234567"
}
```

### 8.2 Sample Inspections

**Toyota Camry 2018:**
```json
{
  "vehicle": {
    "brand": "Toyota",
    "model": "Camry",
    "year": 2018,
    "mileage": 150000,
    "vin": "4T1BF1AK3CU123456"
  },
  "defects": [
    {"area": "body", "type": "rust", "severity": "medium", "location": "doors"},
    {"area": "interior", "type": "wear", "severity": "low", "location": "seat"}
  ]
}
```

### 8.3 Mock Avito Listings

```python
# tests/fixtures/avito_listings.py
AVITO_CAMRY = {
    "url": "https://www.avito.ru/sankt-peterburg/avtomobili/toyota_camry_2018_1234567890",
    "parsed": {
        "title": "Toyota Camry, 2018, 150000 км, белый",
        "price": 1250000,
        "year": 2018,
        "mileage": 150000,
        "body_type": "sedan",
    }
}
```

---

## 9. ЧЕКЛИСТ ПЕРЕД ПРОДАКШЕНОМ

- [ ] Все регрессионные тесты прошли (GREEN)
- [ ] E2E сценарии выполнены (регистрация → отчет)
- [ ] Lighthouse >80 на mobile
- [ ] Bundle size <500KB (gzipped)
- [ ] Avito fallback работает
- [ ] PDF генерируется <3s
- [ ] Все критичные errors обработаны gracefully
- [ ] CORS allow только нужные домены
- [ ] Rate limiting включен на /auth endpoints
- [ ] Логирование структурировано (JSON)
- [ ] Metrics доступны на /metrics (если enabled)
- [ ] Health check работает (/api/v1/health → 200)
- [ ] Docs актуальны (README, AVITO.md, VPS_DEPLOY.md)

---

## 10. КОНТАКТЫ & ESCALATION

- **Backend issues:** Check `app/` logs, DB queries
- **Frontend issues:** Browser DevTools, Vite dev mode
- **Parser issues:** `app/services/parsers/`, playwright logs
- **Avito captcha:** Documentend in `docs/AVITO.md`, may need proxy rotation
- **LLM errors:** Check OpenAI/OpenRouter API status, rate limits
- **Payment issues:** YooKassa webhook logs, check `app/api/payment_routes.py`

---

**Last Updated:** 2026-06-08  
**QA Lead:** [Your Name]  
**Status:** READY FOR EXECUTION
