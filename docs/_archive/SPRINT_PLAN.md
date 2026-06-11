# СПРИНТ-ПЛАН ПОДКАПОТ (3 недели)

**Дата старта:** 2026-06-08  
**Цель:** Запустить MVP с базовой интеграцией Avito, фиксами UI/UX и регрессионным тестированием.

---

## ФАЗА 1: НЕДЕЛЯ 1 (8-14 июня) — ФУНДАМЕНТ

### Критичные блокеры и их решение

| Блокер | Решение | Статус |
|--------|---------|--------|
| Парсинг Avito требует ручного управления браузером | Finish Avito fetch module с retry-логикой + captcha detection | Priority 1 |
| Frontend layout сломан (emoji в forms, шрифт <12px) | Аудит CSS, стандартизация на 14px минимум | Priority 1 |
| Отсутствует API для синхронизации статуса анализа | Webhook endpoint для статуса, Redis queue для фоновых задач | Priority 2 |
| Тесты регрессии отсутствуют (только e2e) | Добавить view-тесты + API contract tests | Priority 2 |

### Backend (Приоритет 1-2)

#### 1.1 Доработка парсера Avito
**Файлы:** `app/services/parsers/avito.py`, `app/services/parsers/avito_fetch.py`, `app/services/parsers/avito_description.py`

- [x] Normalize URL parsing (убрать лишние параметры, canonical format)
- [ ] **Retry logic** с exponential backoff (3-5 попыток с задержкой 5-15 сек)
- [ ] **Captcha detection** через признаки HTML/JS-блокировки
- [ ] **Graceful degradation**: если Avito недоступна, возвращать частичные данные с warning
- [ ] **Timeout management** (максимум 30 сек на одно объявление)
- [ ] **Proxy rotation** (опционально, если указан AVITO_PROXY_LIST в .env)
- [ ] **Smoke-тест** успешного парсинга нескольких объявлений

**Метрика успеха:** 95% успешных парсов при первой попытке, <5% timeout'ов

---

#### 1.2 Генерация placeholder изображений
**Файлы:** `app/services/image_generation.py` (создать новый)

- [ ] Async генератор изображений (PIL/Pillow) для авто без фото
- [ ] Шаблоны по типам (sedan, suv, van, truck) с параметрами цвета/текста
- [ ] Кэширование на диск (`data/placeholders/`) с TTL
- [ ] Fallback на стандартный placeholder при ошибке
- [ ] Integration point: вызов в `InspectionComposer.vue` при upload fail

**Метрика успеха:** <100ms на генерацию, хранение на диск работает

---

#### 1.3 Webhook для синхронизации статуса анализа
**Файлы:** `app/api/routes.py` (добавить), `app/services/task_queue.py` (enhance)

- [ ] **POST /api/v1/inspection/{id}/status-webhook** — внешние сервисы отправляют статус
  - Payload: `{ status: "completed|failed", risk_score: float, error?: string }`
  - Валидация signature (HMAC-SHA256)
  - Идемпотентность (одна задача = один вебхук)
  
- [ ] **Redis background job** для обработки webhook'ов
  - Retry на 5 минут если БД недоступна
  - Log все попытки для audit

- [ ] **WebSocket** для real-time обновления UI (опционально, на неделю 2 перенести)

**Метрика успеха:** webhook обрабатывает в течение 2 сек, 100% доставка при retry

---

### Frontend (Приоритет 1)

#### 1.4 Фиксы Layout и Typography
**Файлы:** `frontend/src/**/*.vue`, `frontend/src/styles/` (create)

- [ ] **Global stylesheet** с переменными:
  ```css
  --font-size-body: 14px;
  --font-size-sm: 12px (min);
  --font-size-h1: 32px;
  --line-height: 1.5;
  --spacing-unit: 8px;
  ```

- [ ] **Audit всех компонентов** на соответствие:
  - AuthModal.vue, LoginView.vue, RegisterView.vue — минимум 14px
  - Убрать все emoji или заменить на текст/SVG иконки
  - Проверить контраст текста (WCAG AA)

- [ ] **Checkbox стилизация** в RegisterView
  - Custom checkbox без браузерного стиля
  - State: unchecked → checked (с animation)
  - Цвет согласно дизайн-гайду (primary brand color)

- [ ] **Мобильная оптимизация** (max-width, flex layout)
  - DashboardView, NewInspectionView на мобилке <320px width
  - Touch-friendly buttons (min 44x44 px)

**Метрика успеха:** все views корректны на 320px, 768px, 1920px viewports

---

#### 1.5 Автоматическая загрузка изображений в форму
**Файлы:** `frontend/src/components/InspectionComposer.vue`

- [ ] **Image upload handler**:
  - Drag & drop зона
  - File input `<input type="file" accept="image/*" multiple />`
  - Preview перед upload'ом (thumbnail)
  - Progress bar для каждого файла

- [ ] **Fallback на placeholder** если загрузка fail:
  - Показать generated image за несколько сек
  - User может переопубликовать или оставить placeholder

- [ ] **Integration с backend**:
  - POST `/api/v1/inspection/{id}/upload-image` — multipart
  - Валидация на server (MIME type, размер <5MB)
  - Сохранение в `data/images/{inspection_id}/` на диск или S3

**Метрика успеха:** upload работает для 3 типов файлов, fallback срабатывает <2 сек

---

### Тестирование (Неделя 1)

#### 1.6 Регрессионные тесты — Views
**Файлы:** `tests/test_api_regression.py` (enhance), создать новые fixtures

- [ ] **API Regression Suite**:
  - GET `/api/v1/health` → 200
  - POST `/api/v1/auth/register` с валидными данными → юзер создан
  - POST `/api/v1/auth/login` → JWT выдан
  - GET `/api/v1/inspection/{id}` с auth → inspection данные
  - GET `/api/v1/inspection/{id}` без auth → 401

- [ ] **Factory fixtures** для тестов (user, inspection, payment):
  ```python
  @pytest.fixture
  async def test_user(session: AsyncSession):
      return await register_user(session, "test@example.com", "password123")
  ```

- [ ] **Параметризованные тесты** для разных статусов inspection:
  - draft → pre_inspection → post_inspection
  - Каждый переход валидирует поля

**Метрика успеха:** 100% critical API endpoints покрыты, run <5 сек

---

### Checkpoints Неделя 1
- [ ] Avito parser работает с retry/captcha detection (тест на 5 объявлениях)
- [ ] Placeholder images генерируются за <100ms
- [ ] API regression тесты green (23/23)
- [ ] Frontend layout audit завершён, checkbox стилизован
- [ ] Webhook endpoint принимает POST запросы

---

---

## ФАЗА 2: НЕДЕЛЯ 2 (15-21 июня) — ИНТЕГРАЦИЯ И POLISH

### Backend (Приоритет 2-3)

#### 2.1 Risk Scoring Engine
**Файлы:** `app/services/analysis.py` (enhance), `app/schemas.py`

- [ ] **Алгоритм риск-скоринга** на основе:
  - Возраст авто (0-100 баллов)
  - Пробег (0-100)
  - История сервиса (если доступна)
  - Описание дефектов от пользователя (NLP sentiment)
  - VIN check результаты (если есть Autocode данные)
  
- [ ] **Формула**: `risk_score = (age_points + mileage_points + defects_points) / 3`
  - Output: 0-100, buckets: [0-30] safe, [31-60] caution, [61-100] skip

- [ ] **Чеклист по моделям** (model-specific checklist):
  - Загрузить JSON с known issues по маркам (Toyota, BMW, etc.)
  - Выводить рекомендуемые пункты осмотра для модели
  - Example: BMW X5 → проверить suspension, electronic modules

- [ ] **Webhook интеграция**: отправлять risk_score по webhook'у при completion

**Метрика успеха:** risk_score корреляция с user verdict >0.7 (A/B тест на 100 инспекций)

---

#### 2.2 PDF Report Generation (улучшение)
**Файлы:** `app/services/pdf_report.py`

- [ ] **Профессиональный шаблон**:
  - Header с логотипом и датой
  - Risk score visualisation (gauge chart или progress bar)
  - Таблица дефектов с severity colors
  - Blank pages для notes

- [ ] **Integration с risk_score** из 2.1:
  - Автоматическое резюме "Рекомендация: ..." вверху PDF

- [ ] **Асинхронная генерация** (фоновая task):
  - POST создание → immediate response с status_url
  - GET /api/v1/inspection/{id}/report-status → { status: "generating|ready|failed" }

**Метрика успеха:** PDF генерируется за <5 сек, файл <2MB

---

#### 2.3 Улучшение анализа LLM
**Файлы:** `app/services/llm.py` (enhance)

- [ ] **Prompt optimization** для risk assessment:
  - Убрать эмодзи из LLM output
  - Добавить structured JSON output с полями: risk_factors, recommendations, severity

- [ ] **Fallback на rule-based** если LLM fails:
  - Простые keyword-based хеурестики для common issues

- [ ] **Token counting**: логировать usage, мониторить затраты на OpenAI

**Метрика успеха:** LLM calls успешны >98%, costs <$0.05 per inspection

---

### Frontend (Приоритет 2)

#### 2.4 Professional Design Polish
**Файлы:** `frontend/src/**/*.vue`, дизайн-система

- [ ] **Убрать признаки ИИ**:
  - Заменить generic placeholder text на custom copy
  - Чистая, простая цветовая палитра (не gradient перегруз)
  - Professional typography (системные шрифты: -apple-system, Segoe UI)

- [ ] **Dark mode (опционально)** — toggle в header с persisting в localStorage

- [ ] **Loading states** с skeleton screens:
  - Inspection list loading → skeleton cards
  - Report generation → progress indicator

- [ ] **Error boundaries** для graceful fallback:
  - API error → user-friendly message (не 500 stack trace)
  - Network timeout → retry button

**Метрика успеха:** Figma audit passed, no ИИ-like artifacts

---

#### 2.5 Mobile Optimization (завершение)
**Файлы:** `frontend/src/**/*.vue`, media queries

- [ ] **Viewport meta tags**, responsive images
- [ ] **Touch interactions**: swipe для history, long-press для actions
- [ ] **Performance**: lazy loading компонентов, code splitting
- [ ] **Lighthouse score** >80 на mobile

**Метрика успеха:** Lighthouse mobile >80, Navigation <3s

---

### Тестирование (Неделя 2)

#### 2.6 E2E Flow Tests
**Файлы:** `tests/test_auth_payments_e2e.py` (enhance), `tests/test_vehicle_analysis_e2e.py`

- [ ] **Сценарий 1: Регистрация → Новая проверка → Отчёт**
  ```
  1. POST /register → юзер создан
  2. POST /inspection → inspection draft
  3. POST /inspection/{id}/analyze → analysis complete
  4. GET /inspection/{id}/report → PDF есть
  ```

- [ ] **Сценарий 2: Авторизация через JWT**
  ```
  1. POST /login → JWT
  2. GET /inspection с Bearer token → 200
  3. GET /inspection без token → 401
  ```

- [ ] **Сценарий 3: Webhook обработка**
  ```
  1. POST /webhook с signature → 202
  2. GET /inspection/{id} → статус updated
  ```

- [ ] **Playwright smoke** для UI (опционально):
  - Navigate to /app
  - Fill register form
  - Click "New inspection"
  - Upload image → видим preview

**Метрика успеха:** Все 3 сценария зелёные, <30 сек runtime

---

#### 2.7 Data Parsing Validation Tests
**Файлы:** `tests/test_listing_parsers_regression.py` (enhance)

- [ ] **Тестовые данные** (fixtures) для каждого парсера:
  - Avito: URL + ожидаемый parsed output (make, model, year, price)
  - Auto.ru: аналогично
  - Drom: аналогично

- [ ] **Regression на 20+ реальных объявлений**:
  - Mock HTML responses из файлов
  - Assert parsed == expected

- [ ] **Параметризованные тесты**:
  ```python
  @pytest.mark.parametrize("url,expected", [
      ("https://avito.ru/...", {"make": "Toyota", "model": "Camry"}),
  ])
  async def test_parser(url, expected):
      result = await parse_listing(url)
      assert result.make == expected["make"]
  ```

**Метрика успеха:** 100% test coverage на parsers, 0 regressions

---

### DevOps (Неделя 2)

#### 2.8 CI/CD Pipeline Setup
**Файлы:** `.github/workflows/` или `deploy/ci.yml` (create)

- [ ] **GitHub Actions** (или GitLab CI):
  ```yaml
  on: [push, pull_request]
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v3
        - uses: python-3.12
        - run: pip install -r requirements.txt
        - run: pytest tests/ -v
        - run: npm run test (frontend)
  ```

- [ ] **Pre-commit hooks** (`.pre-commit-config.yaml`):
  - black (code formatting)
  - ruff (linting)
  - mypy (type checking)

- [ ] **Deployment на test/staging**:
  - Docker build + push на registry
  - Deploy на staging VPS (если доступен)
  - Health check post-deploy

**Метрика успеха:** CI/CD fails на первую regress, deploy <5 мин

---

### Checkpoints Неделя 2
- [ ] Risk scoring алгоритм работает, корреляция >0.7
- [ ] PDF reports генерируются асинхронно
- [ ] E2E tests (3 сценария) зелёные
- [ ] Frontend дизайн professional (no ИИ artifacts)
- [ ] CI/CD pipeline running, все тесты pass
- [ ] Lighthouse mobile >80

---

---

## ФАЗА 3: НЕДЕЛЯ 3 (22-28 июня) — ПОЛИРОВКА И ЗАПУСК

### Backend (Приоритет 3)

#### 3.1 Observability & Monitoring
**Файлы:** `app/observability.py` (enhance), `prometheus.yml` (create)

- [ ] **Prometheus metrics**:
  - Request latency (histogram)
  - Error rate (counter)
  - Parsing success rate (gauge)
  - Queue depth (gauge)

- [ ] **Structured logging** (JSON):
  - Every request: method, path, status, latency, user_id
  - Every parser call: url, status, duration, success
  - Every webhook: payload, signature_valid, response_status

- [ ] **Error tracking**:
  - Sentry integration (optional) или file-based error log
  - Alert на parsing fails >10% за 5 мин

**Метрика успеха:** Prometheus dashboard готов, <0.5% parsing failure rate

---

#### 3.2 Documentation & Deployment Guides
**Файлы:** `docs/SPRINT_3_DEPLOY.md` (create)

- [ ] **Deployment checklist**:
  - [ ] Database migrations run (`alembic upgrade head`)
  - [ ] Environment variables set (use .env.prod template)
  - [ ] Healthcheck passes
  - [ ] Logs clean (no CRITICAL errors)

- [ ] **Runbook** для incident response:
  - What to do if parsing fails
  - How to manually trigger webhook
  - How to restart services

- [ ] **API Documentation** (Swagger/OpenAPI):
  - All endpoints documented
  - Request/response examples
  - Error codes listed

**Метрика успеха:** Новый девелопер может deploy за 30 мин по гайду

---

### Frontend (Приоритет 3)

#### 3.3 Performance Optimization
**Файлы:** `frontend/src/**/*.vue`, `vite.config.ts`

- [ ] **Bundle optimization**:
  - Code splitting на routes
  - Tree-shaking неиспользуемого кода
  - Lazy load heavy components (PDF viewer if needed)

- [ ] **Image optimization**:
  - WebP с fallback на JPG
  - Responsive images (srcset)
  - Placeholder blur while loading

- [ ] **Metrics**:
  - LCP <2.5s
  - FID <100ms
  - CLS <0.1

**Метрика успеха:** Production bundle <150KB (gzip), LCP <2.5s

---

#### 3.4 Accessibility (A11y)
**Файлы:** `frontend/src/**/*.vue`

- [ ] **WCAG 2.1 AA compliance**:
  - Keyboard navigation (tab, enter, escape)
  - ARIA labels на interactive elements
  - Color contrast ratio 4.5:1 для текста

- [ ] **Screen reader** support:
  - Form labels связаны с inputs
  - Error messages announced
  - Loading state communicated

**Метрика успеха:** axe DevTools audit <3 issues

---

### Тестирование (Неделя 3)

#### 3.5 Load & Stress Testing
**Файлы:** `tests/load_test.py` (create using locust/vegeta)

- [ ] **Locust smoke test**:
  - 10 concurrent users
  - Register, login, create inspection
  - Run for 2 minutes
  - Assert p95 latency <1s

- [ ] **Stress test** (опционально):
  - 100 concurrent requests
  - Identify bottlenecks

**Метрика успеха:** API handles 10 concurrent users, p95 <1s

---

#### 3.6 Security & Data Validation
**Файлы:** `tests/test_security.py` (create)

- [ ] **Input validation**:
  - SQL injection attempts → 400 Bad Request
  - XSS in inspection notes → sanitized
  - CSRF token present in forms

- [ ] **Authentication/Authorization**:
  - Юзер не может видеть чужие инспекции
  - JWT expiry enforced
  - Rate limiting prevents brute force

- [ ] **Data sanitization**:
  - LLM output escaping (XSS prevention)
  - Webhook signature validation

**Метрика успеха:** No OWASP Top 10 issues found

---

### QA & Release (Неделя 3)

#### 3.7 Full Regression Test Suite
**Файлы:** `tests/` (consolidate all)

- [ ] **Smoke test suite** (run before every deploy):
  - Health check
  - Core user flows (register, login, create inspection)
  - All parsers

- [ ] **Regression suite** (run nightly):
  - All API endpoints
  - All UI views
  - All edge cases

- [ ] **Checklist перед релизом**:
  - [ ] All tests green ✓
  - [ ] Code review complete ✓
  - [ ] Performance acceptable ✓
  - [ ] Security audit passed ✓
  - [ ] Documentation updated ✓
  - [ ] Changelog written ✓

**Метрика успеха:** 100% test pass, release checklist ✓

---

#### 3.8 Go-Live Preparation
**Файлы:** `docs/PRODUCTION_READINESS.md` (create)

- [ ] **Pre-launch checks**:
  - Database backups configured
  - Monitoring alerts set
  - Support documentation for users
  - Incident response plan

- [ ] **Launch day**:
  - [ ] Blue-green deployment (если есть 2 сервера)
  - [ ] или Canary rollout (5% → 25% → 100% traffic)
  - [ ] Monitor error rate & latency
  - [ ] Have rollback plan ready

- [ ] **Post-launch** (неделя после):
  - Monitor metrics 24/7
  - Respond to user feedback
  - Minor hotfixes as needed

**Метрика успеха:** 0 critical issues first week, <0.1% error rate

---

### Checkpoints Неделя 3
- [ ] Load test passes (10 concurrent, p95 <1s)
- [ ] Security audit 0 critical issues
- [ ] Full regression suite green
- [ ] Performance: LCP <2.5s, bundle <150KB
- [ ] Documentation complete
- [ ] Go-live checklist ready

---

---

## РИСК-ФАКТОРЫ И MITIGATION

| Риск | Вероятность | Влияние | Mitigation |
|------|------------|--------|-----------|
| Avito API rate limiting | HIGH | HIGH | Implement exponential backoff, proxy rotation, queue system |
| Парсинг Avito captcha | HIGH | HIGH | Detect captcha early, fallback на API или manual input |
| LLM costs > budget | MEDIUM | MEDIUM | Token counting, caching responses, rule-based fallback |
| Database migration fails in prod | LOW | CRITICAL | Test migrations locally first, have rollback script |
| Webhook delivery failures | MEDIUM | MEDIUM | Retry logic (5 попыток), DLQ for failed messages |
| Frontend mobile viewport bugs | MEDIUM | MEDIUM | Test on real devices (not just browser devtools) |
| E2E tests flaky | MEDIUM | MEDIUM | Add explicit waits, mock external services, use fixtures |

**Mitigation strategy:**
- Week 1: Focus on critical blockers (parser, layout)
- Week 2: Build safety nets (tests, monitoring)
- Week 3: Polish, document, prepare launch

---

## METRICS ДЛЯ УСПЕХА

### Backend
- [ ] Avito parser success rate: **>95%** (first attempt)
- [ ] Parsing latency p95: **<5 seconds**
- [ ] Risk score correlation with user verdict: **>0.7**
- [ ] Webhook delivery reliability: **99.9%** (with retries)
- [ ] API error rate: **<0.5%** in production

### Frontend
- [ ] Lighthouse mobile score: **>80**
- [ ] LCP (Largest Contentful Paint): **<2.5 seconds**
- [ ] Bundle size (gzip): **<150 KB**
- [ ] Mobile viewport coverage: **100%** (320px to 1920px)

### Testing
- [ ] Test coverage: **>80%** for critical paths
- [ ] E2E test runtime: **<30 seconds**
- [ ] Regression test suite: **100% pass rate**
- [ ] Security audit findings: **0 critical** issues

### DevOps
- [ ] CI/CD pipeline runtime: **<10 minutes**
- [ ] Deployment duration: **<5 minutes**
- [ ] Mean time to recovery: **<30 minutes** (rollback)
- [ ] Uptime: **99.5%** SLA

---

## TIMELINE SUMMARY

```
WEEK 1 (June 8-14)
├─ Mon: Parser retry logic, fixture setup
├─ Tue-Wed: Layout audit, checkbox styling, placeholder images
├─ Thu: Webhook endpoint, API regression tests
└─ Fri: Sprint review, risk scoring design

WEEK 2 (June 15-21)
├─ Mon-Tue: Risk scoring, PDF async, LLM polish
├─ Wed-Thu: E2E tests, frontend polish, mobile opt
├─ Fri: CI/CD setup, smoke tests, deployment guide draft

WEEK 3 (June 22-28)
├─ Mon-Tue: Load testing, security audit, monitoring setup
├─ Wed: Documentation, performance optimization
├─ Thu: Full regression, go-live checklist
└─ Fri: Launch! 🚀
```

---

## DEPENDENCIES & BLOCKERS

**Must have before Week 1:**
- [ ] .env configured (WEB_SECRET_KEY, TELEGRAM_BOT_TOKEN at minimum)
- [ ] Database migrations up to date
- [ ] Python 3.11+ environment
- [ ] Node.js 20.x for frontend

**Must have before Week 2:**
- [ ] Avito parser stable
- [ ] Frontend layout passed audit
- [ ] All Week 1 tests passing

**Must have before Week 3:**
- [ ] Risk scoring algorithm validated
- [ ] E2E tests reliable (no flakes)
- [ ] CI/CD pipeline working

---

## ROLES & RESPONSIBILITIES

| Role | Responsibilities |
|------|------------------|
| **Backend Lead** | Parser, risk scoring, webhook, observability |
| **Frontend Lead** | Layout fixes, polish, mobile optimization, A11y |
| **QA Lead** | Test suite setup, regression, security audit |
| **DevOps** | CI/CD, deployment, monitoring, runbooks |

---

## COMMUNICATION

- **Daily standup** (09:00 UTC): 15 min, blockers & progress
- **Code review SLA**: <4 hours
- **Slack channel**: #sprint-podkapot
- **Status dashboard**: Spreadsheet or Linear board

---

## SUCCESS CRITERIA (MVP Ready)

- [ ] **Functionality**: Avito parsing, analysis, PDF reports working
- [ ] **Quality**: 100% critical test pass, <0.5% error rate
- [ ] **Performance**: LCP <2.5s, parsing p95 <5s
- [ ] **UX**: Clean design, no ИИ artifacts, mobile-friendly
- [ ] **Ops**: Monitoring, logging, runbooks ready
- [ ] **Launch**: Go-live checklist complete, rollback plan ready

**Target:** Launch MVP by June 28, 2026
