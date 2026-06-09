# СПРИНТ-ПЛАН ПОДКАПОТ: ПОЛНОЕ РАСПЛАНИРОВАНИЕ

**Дата подготовки:** 8 июня 2026  
**Проект:** ПОДКАПОТ (B2C сервис проверки авто)  
**Период спринта:** 8-28 июня 2026 (3 недели)  
**Статус:** ✅ ПОЛНОСТЬЮ ПОДГОТОВЛЕНО К ВЫПОЛНЕНИЮ

---

## ДОСТАВЛЕННЫЕ ДОКУМЕНТЫ

### 🎯 Основной Пакет (8 документов)

| # | Документ | Размер | Назначение | Аудитория |
|---|----------|--------|-----------|-----------|
| 1 | **00_START_HERE.md** | 5 pages | Навигация + ориентация | Все |
| 2 | **SPRINT_SUMMARY.txt** | 7 pages | Резюме спринта | Все |
| 3 | **README_SPRINT.md** | 5 pages | Практический гайд | Все |
| 4 | **DAILY_PRIORITIES.md** | 12 pages | День-за-днём checklist | Все |
| 5 | **SPRINT_PLAN.md** | 15 pages | Полный детальный план | Tech leads + PM |
| 6 | **ARCHITECTURE_DECISIONS.md** | 12 pages | Технические решения | Backend + Frontend + QA |
| 7 | **RISK_REGISTER.md** | 13 pages | Управление рисками | Tech leads + PM |
| 8 | **SUCCESS_METRICS.md** | 20 pages | Метрики успеха & go/no-go | QA + PM |

### 🎨 Вспомогательные документы (2 документа)

| # | Документ | Размер | Назначение |
|---|----------|--------|-----------|
| 9 | **TIMELINE_VISUAL.txt** | 3 pages | ASCII визуальный график |
| 10 | **SETUP_CHECKLIST.md** | 8 pages | Подготовка окружения |
| 11 | **DOCUMENTS_INDEX.txt** | 5 pages | Индекс и навигация |

**Всего:** 98+ страниц подробной документации

---

## ОХВАТЫВАЕМЫЕ ОБЛАСТИ

### 1. Бизнес-планирование
- [x] 3-недельный roadmap с фазами
- [x] 54 story points, разбор по неделям
- [x] Критичные блокеры и их решения
- [x] Метрики успеха для каждого этапа
- [x] Риск-факторы и mitigation strategies

### 2. Backend Приоритеты
- [x] Интеграция с Avito API (парсинг + retry logic)
- [x] Автогенерация placeholder изображений
- [x] Улучшение анализа (risk scoring, чеклисты)
- [x] Webhook для синхронизации статуса
- [x] Архитектурные решения с примерами кода

### 3. Frontend Приоритеты
- [x] Фиксы layout (auth-forms, no emoji, min 14px font)
- [x] Стилизованный checkbox (без emoji)
- [x] Автоматическая загрузка изображений
- [x] Оптимизация мобильного вида
- [x] Профессиональный дизайн (без видимого ИИ)

### 4. Тестирование
- [x] Регрессия-тесты на все views
- [x] E2E для критичных flows (register → check → report)
- [x] Валидация парсинга данных
- [x] Load testing (p95 <1s @ 10 concurrent)
- [x] Security audit (0 critical issues)

### 5. DevOps/QA
- [x] CI/CD пайплайн (тесты перед деплоем)
- [x] Мониторинг ошибок парсинга
- [x] Deployment procedures
- [x] Runbooks для инцидентов
- [x] Go-live checklist

---

## СТРУКТУРА ПЛАНА

### 📊 ФАЗА 1: Неделя 1 (ФУНДАМЕНТ)
```
Цель: Установить базис, решить критичные блокеры
Backend: Parser retry, placeholders, webhook, API tests
Frontend: Layout audit, CSS vars, checkbox, mobile test
QA: Fixtures, regression tests, smoke tests
Success: ≥95% parser, no layout bugs, webhook working
```

### 🔧 ФАЗА 2: Неделя 2 (ИНТЕГРАЦИЯ)
```
Цель: Добавить основные функции, интегрировать компоненты
Backend: Risk scoring, async PDF, LLM optimization
Frontend: Design polish, image upload, Lighthouse optimization
QA: E2E tests (3 scenarios), data validation, CI/CD
Success: Risk correlation >0.65, image upload works, Lighthouse ≥75
```

### 🚀 ФАЗА 3: Неделя 3 (ЗАПУСК)
```
Цель: Финализировать, подготовить production, запустить
Backend: Observability, documentation, security audit
Frontend: Performance optimization, A11y compliance
QA: Load testing, full regression, go-live verification
Success: Load test p95 <1s, security 0 critical, LAUNCH!
```

---

## КЛЮЧЕВЫЕ КОМПОНЕНТЫ ПЛАНА

### 1. Управление Рисками
**12 идентифицированных рисков** с:
- Вероятностью и влиянием
- Стратегиями mitigation
- Contingency plans
- Процедурами escalation

**Top 3 Critical:**
1. Avito parser blocking (HIGH probability, HIGH impact)
2. Database migration failure (MEDIUM probability, CRITICAL impact)
3. LLM cost overrun (MEDIUM probability, MEDIUM impact)

### 2. Метрики Успеха
**18 метрик** с целевыми значениями:
- **Backend:** Parser 95%, latency p95 <5s, risk correlation >0.7, error rate <0.5%
- **Frontend:** Lighthouse ≥85, LCP <2.5s, bundle <150KB, mobile coverage 100%
- **QA:** Coverage ≥80%, E2E 100% pass (no flakes), security 0 critical
- **Ops:** Deployment 100% success, monitoring configured, docs complete

### 3. Go/No-Go Gates
**Friday неделя 3 (10:00am)** - финальное решение о запуске
- Все GREEN метрики должны пройти
- Если не пройти → Option: Beta launch, extend sprint, или defer features

### 4. Daily Standup Format
**15 минут, 9:00am UTC, каждый день (ПН-ПТ)**
- Status: Done yesterday, blockers, today's goal
- Risk check: Anything emerging?
- Demo: Show progress
- Decisions: What needs approval?
- Assignments: Who owns what?

---

## ПРИМЕРЫ РЕАЛИЗАЦИИ

### Avito Parser с Retry Logic
```python
# Exponential backoff, captcha detection, graceful degradation
async def parse_avito_with_retry(url: str) -> ParsedListing | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            html = await fetch_avito_html(url, timeout=30)
            if is_blocked_html(html):  # captcha detection
                if attempt < MAX_RETRIES:
                    delay = min(15, 2 * (1.5 ** attempt))  # backoff
                    await asyncio.sleep(delay)
                    continue
            return _parse_listing_html(html)
        except TimeoutError:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 * attempt)
                continue
    return None  # Graceful degradation
```

### Webhook с Signature Verification
```python
# HMAC-SHA256 signature, idempotency, retry queue
@router.post("/inspection/{id}/status-webhook")
async def receive_webhook(body: dict, request: Request):
    # Verify signature
    if not await service.verify_signature(body, request.headers):
        raise HTTPException(401, "Invalid signature")
    
    # Check idempotency
    if await service.is_processed(id, webhook_id=body.get("id")):
        return {"status": "already_processed"}
    
    # Queue for processing
    await redis.rpush("queue:webhook:analysis", json.dumps({...}))
    return {"status": "accepted"}
```

### CSS Design System
```css
:root {
  --font-family-base: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-size-base: 14px;  /* Min 14px everywhere */
  --spacing-unit: 8px;
  --color-primary: #2563eb;
}

/* Mobile-first responsive approach */
@media (max-width: 640px) {
  --font-size-base: 16px;  /* Increase on mobile */
  --spacing-md: 12px;
}
```

---

## КОМАНДА & РОЛИ

### Backend Developer (1 dev)
- **Week 1:** Parser retry + placeholders + webhook + API tests
- **Week 2:** Risk scoring + async PDF + LLM optimization
- **Week 3:** Observability + docs + security audit
- **Files to focus:** `app/services/parsers/avito.py`, `app/api/routes.py`, `app/services/analysis.py`

### Frontend Developer (1 dev)
- **Week 1:** Layout audit + CSS vars + checkbox + mobile testing
- **Week 2:** Design polish + image upload + Lighthouse optimization
- **Week 3:** Performance + A11y + bundle optimization
- **Files to focus:** `frontend/src/styles/design-system.css`, `frontend/src/components/`

### QA / Test Engineer (1 dev)
- **Week 1:** Fixtures + regression tests (23 endpoints) + smoke tests
- **Week 2:** E2E tests (3 scenarios) + data validation + CI/CD
- **Week 3:** Load testing + security audit + full regression
- **Files to focus:** `tests/conftest.py`, `tests/test_*_regression.py`, `tests/test_*_e2e.py`

### DevOps / Infrastructure (1 dev)
- **Week 1:** Docker + .env + health checks
- **Week 2:** GitHub Actions + pre-commit hooks + staging
- **Week 3:** Monitoring + deployment runbook + go-live prep
- **Files to focus:** `docker-compose.yml`, `.github/workflows/`, `deploy/`

### Project Manager (1 person)
- **Daily:** Standups (9:00am), blockers removal, velocity tracking
- **Weekly:** Demo (Friday 4pm), retro (4:30pm), metrics reporting
- **Week 3:** Go-live decision, launch coordination, post-launch support

---

## КРИТИЧНЫЕ СРОКИ

| Дата | Событие | Владелец | Влияние |
|------|---------|----------|---------|
| Пн 8 июня, 9am | Standup kickoff | PM | Спринт начинается |
| Пт 14 июня, 4pm | Week 1 demo | All | Foundation complete? |
| Пт 14 июня, 4:30pm | Week 1 retro | All | Lessons learned |
| Пт 21 июня, 4pm | Week 2 demo | All | Features working? |
| Пт 28 июня, 10am | **Go/No-Go** | PM + Tech leads | **МОЖНО ЛИ ЗАПУСКАТЬ?** |
| Пт 28 июня, 6pm | **DEPLOY** | DevOps | **MVP LIVE!** |

---

## УСПЕХ vs НЕУДАЧА

### ✅ Успех (All Green)
```
Parser: 95-99%              ✓
API errors: <0.5%           ✓
Lighthouse: 85-90           ✓
LCP: 1.8-2.3s              ✓
E2E: 100% pass (no flakes) ✓
Test coverage: 82%         ✓
Security: 0 critical       ✓
Deployment: 100% success   ✓
Team confidence: 4-5/5     ✓

→ DEPLOY & CELEBRATE! 🎉
```

### ❌ Неудача (Red Flags)
```
Parser: <85%                ✗
API errors: >1%             ✗
Lighthouse: <70             ✗
LCP: >3.5s                 ✗
E2E flakiness: >20%        ✗
Coverage: <70%             ✗
Security: 1+ critical      ✗
Team confidence: 2-3/5     ✗

→ ESCALATE & ADJUST SCOPE
   Option A: Beta launch (known issues)
   Option B: Extend sprint
   Option C: Defer to v1.1
```

---

## БЫСТРАЯ СПРАВКА ДЛЯ ЕЖЕДНЕВНОГО ИСПОЛЬЗОВАНИЯ

### Каждое утро (5 min)
1. Открыть `DAILY_PRIORITIES.md` (сегодняшний день)
2. Выполнить список задач для своей роли
3. Подготовить 1-2 sentence для standup'а

### На standup'е (9:00am, 15 min)
1. Статус: Что сделал вчера? Blockers? Что делаю сегодня?
2. Риски: Что может пойти не так?
3. Demo: Показать прогресс
4. Решения: Что нужно одобрение?

### Каждую пятницу (4pm + 4:30pm)
1. 4:00pm: Demo (показать неделю)
2. 4:30pm: Retro (что выучили?)
3. Обновить SUCCESS_METRICS.md с актуальными метриками

### Каждую неделю (проверка)
- Parser success rate ≥80% (week 1-2) или ≥95% (week 3)
- Lighthouse score trend (should improve each week)
- Test pass rate 100% (no flakes)
- No unresolved critical issues

---

## CONTINGENCY & FLEX

### Если отстаем (velocity <70%)

**Option 1: Defer features**
- Dark mode (nice-to-have, defer to v1.1)
- Advanced analytics (nice-to-have, defer to v1.1)
- Model-specific checklists v2 (enhancement, defer to v1.1)

**Option 2: Reduce scope**
- Reduce E2E test coverage (keep critical flows)
- Skip non-essential optimizations
- Defer nice-to-haves to post-launch

**Option 3: Extend sprint**
- Add 3-7 days to Week 3
- Communicate to stakeholders
- Adjust launch date

### Contingency time budget
- **Time reserve:** 3 дня (included in Week 3)
- **Feature reserve:** 3 nice-to-haves that can be deferred
- **Team buffer:** 1 senior dev for blockers

---

## ЧТО ПОДГОТОВЛЕНО

### ✅ Доставлены все документы
- [x] 11 полных документов (98+ страниц)
- [x] Структурированный roadmap (3 недели)
- [x] Архитектурные решения с примерами
- [x] 12 рисков с mitigation strategies
- [x] 18 метрик успеха с целевыми значениями
- [x] Day-by-day checklist для каждой роли
- [x] Standup template & procedures
- [x] Go-live gates & decision process

### ✅ Готовые к использованию
- [x] Все документы в проекте (git-committed)
- [x] Индекс документов для навигации
- [x] Quick reference cards
- [x] Role-based task assignments
- [x] Timeline & milestones

### ✅ Процессы задокументированы
- [x] Daily standup (15 min, структура)
- [x] Weekly demo (15 min)
- [x] Weekly retro (30 min)
- [x] Risk escalation (3 levels)
- [x] Go/no-go decision (Friday 10am)

---

## КАК ИСПОЛЬЗОВАТЬ ЭТОТ ПЛАН

### День 1 (Понедельник)

1. **Все** читают:
   - 00_START_HERE.md (5 min)
   - SPRINT_SUMMARY.txt (15 min)
   - README_SPRINT.md (10 min)

2. **По ролям** читают:
   - Свою роль в README_SPRINT.md
   - Свои первые дни в DAILY_PRIORITIES.md

3. **Выполняют** SETUP_CHECKLIST.md (environment setup)

4. **Присутствуют** на kickoff standup'е (9:00am)

### Недели 1-3

1. **Каждое утро** (5 min):
   - Check DAILY_PRIORITIES.md для сегодня
   - Prepare 1-liner for standup

2. **Каждый день** (9:00am):
   - Attend standup (15 min)
   - Update metrics

3. **Каждую пятницу** (4:00pm + 4:30pm):
   - Demo (15 min)
   - Retro (30 min)

4. **При блокировке**:
   - Check RISK_REGISTER.md (escalation)
   - Escalate в Slack (level 1-3)
   - Follow procedure

### Неделя 3 (Запуск)

1. **Пятница 10:00am**:
   - Go/no-go decision meeting
   - Check SUCCESS_METRICS.md (all gates?)
   - Final approval

2. **Пятница 6:00pm**:
   - DEPLOY TO PRODUCTION 🚀

3. **Суббота onwards**:
   - Monitor (24/7 on-call team)
   - Handle incidents
   - Support users

---

## ВЫВОДЫ

### ✅ Что мы подготовили

Полный, структурированный план запуска MVP на 3 недели с:
- Детальным roadmap'ом (фаза за фазой)
- Четкой архитектурой (как реализовать)
- Управлением рисками (что может пойти не так)
- Метриками успеха (как измерить)
- Ежедневными приоритетами (что делать сегодня)
- Процедурами escalation (как справиться с проблемами)
- Go-live gates (когда можно запускать)

### 🎯 Результат (если следовать плану)

**Friday June 28, 2026:**
- MVP готов к production
- Все метрики в зелени
- Команда confident
- Stakeholders approved
- DEPLOY! 🚀

**By July 15, 2026:**
- 100+ real inspections in production
- Users happy (4+ star reviews)
- MVP success! 🎉

### 📞 Поддержка

Если команда потеряется:
1. Check DOCUMENTS_INDEX.txt (найти нужный документ)
2. Scroll to "REFERENCE BY QUESTION" section
3. Ask in #sprint-podkapot Slack
4. Escalate to PM if stuck

---

## ФИНАЛЬНЫЙ CHECKLIST

Перед стартом спринта убедитесь:

- [ ] Все 11 документов прочитаны (или заскип'ли)
- [ ] Environment setup complete (SETUP_CHECKLIST.md)
- [ ] Все коммунікационные каналы настроены (#sprint-podkapot, calendar)
- [ ] Каждый знает свою роль и первые 3 дня
- [ ] Никаких вопросов (или они задают в Slack)
- [ ] READY FOR KICKOFF! ✓

---

**Спринт официально начинается**
**Понедельник, 8 июня 2026, 9:00 AM UTC**

**ДАВАЙТЕ ЗАПУСТИМ ЭТОТ MVP! 🚀**

---

*Подготовлено:* Архитектор проекта  
*Дата:* 8 июня 2026  
*Статус:* ✅ ПОЛНОСТЬЮ ГОТОВО К ВЫПОЛНЕНИЮ
