# СПРИНТ-ПЛАН ПОДКАПОТ: КРАТКАЯ СПРАВКА

**Проект:** ПОДКАПОТ (проверка авто перед покупкой)  
**Период:** 8-28 июня 2026 (3 недели)  
**Цель:** Запустить MVP с интеграцией Avito, риск-скорингом и полной регрессией  
**Статус:** НАЧАЛО СПРИНТА

---

## СТРУКТУРА ДОКУМЕНТОВ

```
README_SPRINT.md                    ← ВЫ ЗДЕСЬ (краткая справка)
│
├─ SPRINT_PLAN.md                   ← ОСНОВНОЙ ПЛАН (3 недели подробно)
│  └─ Фазы, приоритеты, метрики успеха
│
├─ DAILY_PRIORITIES.md              ← ДЕНЬ-ЗА-ДНЁМ (ПН-ПТ каждой недели)
│  └─ Конкретные задачи, checklist, стендапы
│
├─ ARCHITECTURE_DECISIONS.md        ← ТЕХНИЧЕСКИЕ РЕШЕНИЯ
│  └─ Parser retry logic, webhook pattern, test architecture
│
├─ RISK_REGISTER.md                 ← УПРАВЛЕНИЕ РИСКАМИ
│  └─ 12 рисков с mitigation'ом и escalation procedures
│
└─ SUCCESS_METRICS.md               ← GO/NO-GO КРИТЕРИИ
   └─ 18 метрик с целевыми значениями и способом измерения
```

**Где искать информацию:**
- "Что делать сегодня?" → `DAILY_PRIORITIES.md`
- "Как реализовать функцию?" → `ARCHITECTURE_DECISIONS.md`
- "Какой должен быть результат?" → `SUCCESS_METRICS.md`
- "Что может пойти не так?" → `RISK_REGISTER.md`
- "Полная картина спринта?" → `SPRINT_PLAN.md` или этот файл

---

## БЫСТРЫЙ СТАРТ (5 мин чтение)

### The Big Picture

**Неделя 1:** Фундамент (parser, layout, placeholder images, webhook, tests)  
**Неделя 2:** Интеграция (risk scoring, PDF reports, E2E tests, polish)  
**Неделя 3:** Запуск (load test, security audit, documentation, LAUNCH)

### Critical Blockers (Решить в первый день)

| Блокер | Решение | Deadline |
|--------|---------|----------|
| Avito parser может быть заблокирован | Implement retry + captcha detection | Jun 8 |
| Frontend layout сломан (emoji, шрифт <14px) | Layout audit + CSS variables | Jun 10 |
| Нет регрессионных тестов | Create fixtures + API contract tests | Jun 11 |
| Webhook синхронизация не работает | Implement webhook endpoint + queue | Jun 11 |

### Success = All Green Metrics

| Category | Target | Measured By |
|----------|--------|-------------|
| Parser | ≥95% success rate | Daily test |
| Frontend | Lighthouse ≥85 mobile | Weekly audit |
| Tests | 100% E2E pass (no flakes) | Every CI run |
| Ops | <0.5% error rate | Production monitoring |

---

## ПО РОЛЯМ

### Backend Developer

**Week 1:**
- Avito parser: retry logic + captcha detection
- Placeholder image generation (async, cached)
- Webhook endpoint (signature verification + idempotency)
- API regression tests

**Week 2:**
- Risk scoring algorithm (correlation >0.7)
- Async PDF generation
- LLM prompt optimization
- Token counting + cost monitoring

**Week 3:**
- Observability (Prometheus + JSON logs)
- Documentation (API docs, runbooks)
- Security audit (OWASP)
- Load testing (p95 <1s @ 10 concurrent)

**Key Files:**
- `app/services/parsers/avito.py` — parser retry
- `app/services/image_generation.py` — placeholders (create)
- `app/api/routes.py` — webhook endpoint
- `app/services/analysis.py` — risk scoring
- `tests/test_*_regression.py` — regression suite

**Daily Checklist:**
- [ ] 1 PR reviewed/merged
- [ ] Tests pass locally
- [ ] Metrics tracked (Slack report 9am)
- [ ] Standup attended

---

### Frontend Developer

**Week 1:**
- CSS audit: all text ≥14px, no emoji
- Design system variables (typography, spacing, colors)
- Custom checkbox (no emoji)
- Mobile viewport testing (320px, 768px, 1920px)

**Week 2:**
- Professional design polish (no AI artifacts)
- Image upload component (drag & drop, fallback)
- Loading skeletons
- Mobile optimization (Lighthouse >80)

**Week 3:**
- Performance optimization (bundle <150KB, LCP <2.5s)
- Accessibility (WCAG AA, axe audit)
- Dark mode (optional)
- Error boundaries

**Key Files:**
- `frontend/src/styles/design-system.css` — CSS vars (create)
- `frontend/src/components/Checkbox.vue` — custom checkbox (create)
- `frontend/src/components/ImageUpload.vue` — image upload (create)
- `frontend/src/views/*.vue` — layout fixes

**Daily Checklist:**
- [ ] 1 PR reviewed/merged
- [ ] Tests pass locally
- [ ] Responsive testing on real device
- [ ] Standup attended

---

### QA / Test Engineer

**Week 1:**
- Create test fixtures (conftest, factories)
- API regression suite (18-20 endpoints)
- Parser validation tests (5+ URLs per platform)
- Success rate: ≥95%

**Week 2:**
- E2E tests (3 critical scenarios)
- Data parsing validation (20+ fixtures)
- Risk scoring unit tests
- Success rate: 100% no flakes

**Week 3:**
- Load testing (10 concurrent, p95 <1s)
- Security testing (OWASP Top 10)
- Full regression suite
- Smoke tests pre-deploy

**Key Files:**
- `tests/conftest.py` — shared fixtures
- `tests/test_api_regression.py` — API tests
- `tests/test_*_e2e.py` — end-to-end scenarios
- `tests/load_test.py` — load testing (create)

**Daily Checklist:**
- [ ] 1 new test written
- [ ] All tests passing
- [ ] Coverage tracked
- [ ] Standup attended

---

### DevOps / Infrastructure

**Week 1:**
- Ensure Redis in docker-compose
- Verify .env template has webhook_secret
- Health check endpoint working

**Week 2:**
- GitHub Actions workflow (test on push)
- Pre-commit hooks (black, ruff, mypy)
- Staging deployment ready

**Week 3:**
- Prometheus monitoring configured
- Alerting rules set
- Deployment runbook (blue-green or canary)
- Production readiness checklist

**Key Files:**
- `docker-compose.yml` — services
- `.github/workflows/test.yml` — CI/CD (create)
- `deploy/Caddyfile` — reverse proxy
- `docs/PRODUCTION_READINESS.md` — runbook (create)

**Daily Checklist:**
- [ ] All services healthy (docker-compose ps)
- [ ] CI/CD passing
- [ ] Logs reviewed (no errors)
- [ ] Standup attended

---

### Project Manager / Product Owner

**Week 1:**
- Kickoff standup Monday 9am
- Track daily velocity
- Identify blockers
- Keep DAILY_PRIORITIES.md updated

**Week 2:**
- Mid-sprint review (Wed 3pm)
- Confirm no scope creep
- Demo to stakeholders (optional)

**Week 3:**
- Go/no-go decision Friday 10am
- Prepare launch plan
- Post-launch support

**Key Activities:**
- Daily standup (15 min, 9am)
- Friday demo (15 min, 4pm)
- Weekly retro (Friday 4:30pm)
- Risk review (Friday 4pm)

---

## METRICS AT A GLANCE

### Daily Tracking (Print & Post)

```
PARSER SUCCESS RATE
Target: 95% | Current: ___ % | Trend: ⬆️ ⬇️ →

FRONTEND LIGHTHOUSE
Target: 85 | Current: ___ | Trend: ⬆️ ⬇️ →

TEST PASS RATE
Unit: __/__ | Integration: __/__ | E2E: __/__ 
Flakes: ___% | Trend: ⬆️ ⬇️ →

BLOCKERS
[ ] None | [ ] 1 (describe) | [ ] 2+ (escalate)

TEAM MORALE
1 2 3 4 5 (5=confident we'll launch)
```

### Weekly Review (Friday 4pm)

**Questions to answer:**
1. Are we on track for launch? (YES / AT RISK / NO)
2. What's blocking us? (risk register)
3. What should we defer? (scope management)
4. Do we need help? (escalation)
5. What did we learn? (retrospective)

---

## DECISION GATES

### Go/No-Go Friday Week 3 (10am)

**Can we launch if:**

✓ All GREEN metrics pass
✓ No critical security issues
✓ E2E tests 100% pass (no flakes)
✓ Team confidence ≥4/5
✓ Product owner approved

**If any gate fails:**
- Option 1: Launch with known limitations (beta tag)
- Option 2: Extend 1 week (push to July 5)
- Option 3: Defer features to v1.1 (post-launch)

---

## ESCALATION PATHS

**Minor Issue** (1 person affected)
- Slack thread in #sprint-podkapot
- Owner: responsible dev
- SLA: Same day fix

**Blocker** (2+ people affected)
- Slack mention + 15min sync
- Owner: team lead
- SLA: 2 hours fix

**Critical** (project at risk)
- Emergency all-hands
- Decision: PM + tech lead
- SLA: 30 min decision

**Example:** "Parser success <80% for 2 hours"
→ Escalate to backend lead + PM → Emergency decision

---

## DAILY STANDUP

**Time:** 9:00 UTC (adjustable)  
**Duration:** 15 minutes  
**Format:**
1. Status: What was done? Blockers?
2. Today's goal: What will be done?
3. Risk check: Anything emerging?
4. Demo: Show progress (even if incomplete)

**Attendees:** 1 Backend, 1 Frontend, 1 QA, 1 DevOps, 1 PM

**Slack report (if async standup):**
```
🔄 STANDUP (Jun 8)

@backend: Parser retry logic 80% done, blocked on captcha detection heuristics
  → Need design input from @frontend (if visual feedback needed?)
  
@frontend: CSS audit 100%, all text ≥14px ✓
  → Today: design-system.css + checkbox component
  
@qa: Fixtures created, regression tests 5/23 ✓
  → Today: finish regression suite
  
@devops: docker-compose verified, Redis ready ✓
  → Today: webhook_secret in .env template

@pm: All on track, no scope creep
  → Friday demo: show parser + layout + tests
```

---

## WEEKLY DEMO (Friday 4pm)

**Show:**
1. Parser improvements (live demo with real URL)
2. Frontend changes (mobile before/after)
3. Test coverage (regression suite results)
4. Metrics dashboard (success rates)

**Ask feedback:**
- Anything we should adjust?
- Are we on track?
- Do we need help?

**Time:** 15 minutes, then drinks! 🍺

---

## QUICK REFERENCE: WHAT TO DO TODAY

### Monday Jun 8 (Day 1)

**Backend:**
- [ ] Merge existing parser code
- [ ] Add retry logic (3 attempts)
- [ ] Design captcha detection
- [ ] Smoke test 5 listings

**Frontend:**
- [ ] Audit all CSS for font sizes
- [ ] Create design-system.css
- [ ] Remove emoji from views
- [ ] Test on phone (devtools 320px)

**QA:**
- [ ] Set up pytest conftest.py
- [ ] Create user + inspection factories
- [ ] Write 5 API regression tests

**DevOps:**
- [ ] Verify docker-compose works
- [ ] Add webhook_secret to .env.example
- [ ] Health check endpoint ready

**PM:**
- [ ] Daily standup 9am
- [ ] Update DAILY_PRIORITIES.md with today's progress
- [ ] Check Slack for blockers

---

## RESOURCES & LINKS

**Internal Docs:**
- Code: `git clone <repo>`
- API: `http://127.0.0.1:8000/docs`
- Tests: `pytest tests/`
- Frontend Dev: `cd frontend && npm run dev`

**External Tools:**
- Monitoring: Prometheus (setup Week 3)
- Logs: JSON logs in `app/observability.py`
- Load testing: `pip install locust`
- Browser testing: Playwright (pre-installed)

**Communication:**
- Slack: #sprint-podkapot
- Standup: Every weekday 9am
- Demo: Every Friday 4pm
- Retro: Every Friday 4:30pm

---

## WHAT SUCCESS LOOKS LIKE

**By Friday of Week 3 (June 28), you'll see:**

✓ Parser works on real Avito listings (≥95% success)  
✓ Frontend looks professional (no emoji, clean design)  
✓ Tests pass 100% (no flakes, good coverage)  
✓ Metrics dashboard shows <0.5% error rate  
✓ Team is confident to launch  
✓ Go-live checklist complete  

**Launch day morning: DEPLOY TO PRODUCTION** 🚀

---

## WHAT FAILURE LOOKS LIKE (Escalate!)

✗ Parser success <80%  
✗ Lighthouse mobile <70  
✗ E2E tests >20% flaky  
✗ Security audit finds critical issue  
✗ 2+ team members blocked  
✗ Velocity <70% of planned  

**If ANY of these happen:** Emergency standup + scope adjustment

---

## FINAL CHECKLIST (Friday Week 3 GO/NO-GO)

**Functionality:**
- [ ] Avito parser ≥95% success
- [ ] Risk scoring ≥0.70 correlation
- [ ] Webhook 99.9% delivery
- [ ] PDF <5s generation
- [ ] Image upload + fallback

**Quality:**
- [ ] All regression tests pass
- [ ] E2E 3 scenarios, no flakes
- [ ] Security 0 critical issues
- [ ] Coverage ≥80%

**Performance:**
- [ ] Lighthouse ≥85 mobile
- [ ] LCP <2.5s
- [ ] Bundle <150KB
- [ ] Load test p95 <1s

**Ops:**
- [ ] Monitoring configured
- [ ] Runbooks written
- [ ] Backups tested
- [ ] Team trained

**If ALL checked:** DEPLOY! 🎉

---

## WHO TO CONTACT

| Issue | Who | Slack |
|-------|-----|-------|
| Parser problems | @backend-lead | #sprint-podkapot |
| Layout/design | @frontend-lead | #sprint-podkapot |
| Tests failing | @qa-lead | #sprint-podkapot |
| Deploy/infra | @devops | #sprint-podkapot |
| Scope/timeline | @pm | #sprint-podkapot |
| Emergency | @all | #critical |

---

## NEXT STEPS

1. **Read** `SPRINT_PLAN.md` (full plan)
2. **Review** `DAILY_PRIORITIES.md` (today's tasks)
3. **Check** `ARCHITECTURE_DECISIONS.md` (how to implement)
4. **Scan** `RISK_REGISTER.md` (what can go wrong)
5. **Understand** `SUCCESS_METRICS.md` (how to measure)
6. **Attend** Monday 9am standup
7. **Start** your first task

---

**Good luck! Let's ship this MVP! 🚀**

Questions? Slack → #sprint-podkapot
