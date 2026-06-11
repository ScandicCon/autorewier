# ЕЖЕДНЕВНЫЕ ПРИОРИТЕТЫ СПРИНТА (3 недели)

## НЕДЕЛЯ 1: ФУНДАМЕНТ (8-14 июня)

### ПН 8 июня — Parser & Retry Logic

**Backend (Критичный)**
- [ ] Merge Avito parser into single module (`app/services/parsers/avito.py`)
- [ ] Implement retry logic with exponential backoff (3-5 attempts)
- [ ] Add captcha detection heuristics
- [ ] Write retry tests (5 fixtures with real/mock HTML)
- [ ] **Success metric:** 95% first-time pass rate on test set

**Frontend**
- [ ] Audit CSS: all text sizes ≥14px (except system labels)
- [ ] Remove all emoji from UI (RegisterView, AuthModal)
- [ ] Create `frontend/src/styles/design-system.css` with variables

**QA**
- [ ] Set up pytest fixtures (conftest.py, factories)
- [ ] Run existing tests to ensure no regressions

---

### ВТ-СР 9-10 июня — Layout & Placeholder Images

**Frontend (Критичный)**
- [ ] Apply design-system CSS to all views
- [ ] Implement custom Checkbox component (no emoji)
- [ ] Test on 320px, 768px, 1920px viewports
- [ ] **Success metric:** All views render correctly on mobile

**Backend**
- [ ] Create `app/services/image_generation.py`
- [ ] Implement placeholder image generator (PIL-based)
- [ ] Add caching to disk (`data/placeholders/`)
- [ ] **Success metric:** <100ms generation, <2MB disk usage

**QA**
- [ ] Create image generation tests
- [ ] Regression test all 5 main views (DashboardView, LoginView, etc.)

---

### ЧТ 11 июня — Webhook & Tests

**Backend**
- [ ] Implement `POST /api/v1/inspection/{id}/status-webhook`
- [ ] Add signature verification (HMAC-SHA256)
- [ ] Create webhook service with idempotency check
- [ ] **Success metric:** Webhook endpoint accepts and queues messages

**QA**
- [ ] Write API regression tests (18-20 endpoints)
- [ ] Create test database fixtures
- [ ] Run full regression suite
- [ ] **Success metric:** 100% tests pass in <5 seconds

**DevOps**
- [ ] Ensure Redis is available in docker-compose
- [ ] Document .env template for webhook_secret

---

### ПТ 12 июня — Sprint Review & Fixes

**All**
- [ ] Daily standup: demo parser, layout, tests
- [ ] Fix any blockers discovered
- [ ] Code review all PRs (SLA <4 hours)
- [ ] Prepare Week 2 tasks

**Checkpoints:**
- [x] Avito parser handles retry + captcha
- [x] Frontend layout audit passed
- [x] Checkbox styled without emoji
- [x] Placeholder images generated
- [x] Webhook endpoint works
- [x] API regression tests green

---

---

## НЕДЕЛЯ 2: ИНТЕГРАЦИЯ (15-21 июня)

### ПН 15 июня — Risk Scoring

**Backend (Приоритет 2)**
- [ ] Design risk scoring algorithm (formula, buckets)
- [ ] Implement `app/services/analysis.py` enhancements
- [ ] Create model-specific checklist (JSON file in `data/checklists/`)
- [ ] Integrate with webhook (send risk_score in response)
- [ ] **Success metric:** risk_score generated for 10 test inspections

**Frontend**
- [ ] Design professional color palette (no emoji, clean look)
- [ ] Implement dark mode toggle (optional but nice)
- [ ] Add loading skeletons to DashboardView

**QA**
- [ ] Write unit tests for risk scoring algorithm
- [ ] Create fixtures for different car types

---

### ВТ-СР 16-17 июня — PDF Reports & Async Tasks

**Backend**
- [ ] Enhance `app/services/pdf_report.py` with risk_score visualization
- [ ] Implement async report generation (Redis background job)
- [ ] Add `GET /api/v1/inspection/{id}/report-status` endpoint
- [ ] **Success metric:** PDF generates in <5 seconds

**Frontend**
- [ ] Implement image upload component (drag & drop, fallback)
- [ ] Add progress bar for upload
- [ ] Test image fallback (placeholder generation)
- [ ] **Success metric:** Upload works, fallback triggers on error

**QA**
- [ ] Test image upload with various file types
- [ ] Test PDF generation at scale (10 concurrent)

---

### ЧТ 18 июня — E2E & Polish

**QA (Критичный)**
- [ ] Write 3 E2E scenarios:
  - Register → Create Inspection → Get Report
  - Login with JWT
  - Webhook status update
- [ ] Run Playwright smoke tests (optional)
- [ ] **Success metric:** All scenarios <30s runtime, 100% pass

**Frontend**
- [ ] Professional design polish (Figma audit)
- [ ] Mobile optimization (Lighthouse >80)
- [ ] Remove all "AI-like" artifacts

**Backend**
- [ ] LLM prompt optimization (no emoji, structured output)
- [ ] Add token counting for OpenAI

---

### ПТ 19 июня — CI/CD & Runbooks

**DevOps**
- [ ] Set up GitHub Actions workflow (or equivalent)
- [ ] Configure pre-commit hooks (black, ruff, mypy)
- [ ] Create deployment runbook (Week 3 launch)
- [ ] **Success metric:** CI passes on all commits

**All**
- [ ] Code review sprint
- [ ] Demo: risk scoring, PDF reports, E2E tests

**Checkpoints:**
- [x] Risk scoring algorithm works
- [x] PDF async generation implemented
- [x] Image upload with fallback working
- [x] E2E tests green (3 scenarios)
- [x] Frontend design professional
- [x] CI/CD pipeline running
- [x] Lighthouse mobile >80

---

---

## НЕДЕЛЯ 3: LAUNCH PREP (22-28 июня)

### ПН 22 июня — Load Testing & Monitoring

**DevOps (Критичный)**
- [ ] Set up Prometheus metrics (API, parsers, queue)
- [ ] Write locust load test (10 concurrent users, 2 min)
- [ ] **Success metric:** p95 latency <1s, 0 timeouts
- [ ] Configure error alerts (>5% failure rate)

**Backend**
- [ ] Verify all logs are JSON-formatted
- [ ] Check error handling (no stack traces to user)
- [ ] Document rate limiting config

**QA**
- [ ] Run stress test (50 concurrent connections)
- [ ] Monitor memory/CPU usage

---

### ВТ-СР 23-24 июня — Security & Documentation

**Backend**
- [ ] Security audit (SQL injection, XSS, CSRF)
- [ ] Verify JWT expiry enforcement
- [ ] Test input validation on all endpoints
- [ ] **Success metric:** 0 critical OWASP issues

**Documentation**
- [ ] Complete API docs (Swagger)
- [ ] Write deployment guide (PRODUCTION_READINESS.md)
- [ ] Create incident response runbook
- [ ] **Success metric:** New dev can deploy in 30 min

**DevOps**
- [ ] Prepare blue-green or canary deployment
- [ ] Write rollback script

---

### ЧТ 25 июня — Full Regression & Launch Checklist

**QA**
- [ ] Run full regression suite (all tests):
  - Unit tests (parsers, analysis)
  - Integration tests (API contracts)
  - E2E tests (user flows)
- [ ] Check code coverage (>80% for critical paths)
- [ ] **Success metric:** 100% tests pass

**All**
- [ ] Go-live checklist review:
  - [ ] Database backups configured
  - [ ] Monitoring alerts active
  - [ ] Support docs ready
  - [ ] Team trained on runbooks

---

### ПТ 26 июня — Launch Day! 🚀

**Pre-launch (Morning)**
- [ ] Final health check on staging
- [ ] Verify all integrations (Avito, payment, email)
- [ ] Team standup (10 min, roles assigned)

**Launch (Afternoon)**
- [ ] Deploy to production
- [ ] Monitor error rate, latency, logs
- [ ] Check key user flows (register, create inspection)

**Post-launch (First 24h)**
- [ ] Monitor metrics 24/7 (shifts if needed)
- [ ] Respond to critical user issues
- [ ] Keep changelog updated

**Checkpoints:**
- [x] Load test passes (p95 <1s)
- [x] Security audit 0 critical
- [x] Full regression suite green
- [x] Documentation complete
- [x] Team trained
- [x] Production live!

---

---

## DAILY STANDUP TEMPLATE (15 min)

**Participant:** 1 Backend, 1 Frontend, 1 QA, 1 DevOps

**Format:**
```
1. Status (2 min):
   - What was done yesterday? (blockers?)
   - What's today's goal?
   - Any help needed?

2. Blockers (2 min):
   - Is anything blocking you?
   - Do we need to escalate?

3. Risk Check (1 min):
   - Any risks emerging?
   - Timeline still on track?

4. Decisions (2 min):
   - Any decisions needed?
   - Who owns what?

5. Demo (5 min):
   - Show progress (even if incomplete)
   - Get feedback early
```

**Example (Day 1):**
```
Backend: "Finished parser retry logic, need code review today"
Frontend: "Layout audit done, all text ≥14px. Starting design-system CSS"
QA: "Set up pytest fixtures, running first regression tests"
DevOps: "Verified Redis in docker-compose, ready for webhook integration"

Blockers: None
Risks: Avito captcha might slow down testing (but have workaround)
Next: All Week 1 tasks should be mergeable by Friday
```

---

## WEEKLY DEMO FORMAT (Friday, 15 min)

**Show:**
1. Parser improvements (real Avito listing parsing + retry demo)
2. Frontend changes (layout side-by-side before/after on phone)
3. Test coverage (regression suite, E2E scenarios)
4. Metrics (success rate, latency, uptime)

**Ask:**
- Any feedback on design/UX?
- Should we adjust priorities?
- Are we on track for launch?

---

## SPRINT VELOCITY TRACKING

**Expected story points per week (T-shirt sizing):**
- Week 1: 21 points (foundation, must have)
- Week 2: 18 points (integration, quality)
- Week 3: 15 points (polish, launch)

**If running behind:**
1. Defer nice-to-haves (dark mode, advanced optimizations)
2. Reduce E2E test coverage (keep critical flows)
3. Extend sprint by 3 days (if possible)

---

## RED FLAGS (Escalate immediately)

- [ ] CI/CD pipeline fails on main branch
- [ ] Database migrations broken
- [ ] Any critical security issue found
- [ ] Performance degrades >20% from baseline
- [ ] Avito parser success rate <80%
- [ ] More than 2 team members blocked
- [ ] Risk scoring not converging to user verdict

**Escalation:** Slack + manager + emergency standup (if needed)

---

## SUCCESS METRICS (End of Sprint)

**Backend:**
- Avito parser: 95%+ success, p95 <5s
- Risk scoring: >0.7 correlation with users
- Webhook: 99.9% delivery with retries
- API error rate: <0.5%

**Frontend:**
- Lighthouse mobile: >80
- LCP: <2.5 seconds
- Mobile viewport: 100% (320px-1920px)
- Bundle size: <150KB gzip

**Quality:**
- Test coverage: >80% critical paths
- Regression suite: 100% pass
- Security: 0 critical OWASP issues
- Load test: 10 concurrent, p95 <1s

**Ops:**
- Deployment time: <5 minutes
- Rollback available: <2 minutes
- Monitoring: All alerts configured
- Documentation: Complete & up-to-date

**All green = Launch is GO! 🚀**
