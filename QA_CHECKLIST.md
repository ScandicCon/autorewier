# QA Checklist for ПОДКАПОТ v0.2.0

**Date:** 2026-06-08  
**QA Engineer:** [Your Name]  
**Status:** Ready for Testing  

---

## QUICK START

```bash
# 1. Install dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. Run smoke tests (2 min)
./run_quick_tests.sh smoke
# or PowerShell:
./run_qa_checks.ps1 -Mode smoke

# 3. Run regression tests (5 min)
./run_quick_tests.sh quick

# 4. Run critical flows (10 min)
pytest tests/test_e2e_critical_flows.py -v

# 5. Run full suite (15 min)
./run_quick_tests.sh full
```

---

## PHASE 1: SETUP VALIDATION (30 min)

### Environment Configuration

- [ ] `.env` file exists and contains:
  - [ ] `WEB_SECRET_KEY` set (min 32 chars)
  - [ ] `DATABASE_URL` configured (or SQLite default)
  - [ ] `OPENROUTER_API_KEY` or `OPENAI_API_KEY` set (for LLM tests)
  - [ ] `ALLOW_DEV_PAYMENT_BYPASS=true` (for local testing)
  - [ ] `ENVIRONMENT!=production` (prevents payment validation)

- [ ] Database initialized:
  ```bash
  python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
  ```

- [ ] Node.js v20.x+ installed:
  ```bash
  node -v  # Should be >=20.0.0
  npm -v   # Should be >=10.0.0
  ```

- [ ] Python 3.11+ installed:
  ```bash
  python --version
  python -m pip --version
  ```

### Dependency Installation

- [ ] Backend dependencies:
  ```bash
  pip install -r requirements.txt
  ```
  Expected: All packages installed without errors

- [ ] Frontend dependencies:
  ```bash
  cd frontend && npm install
  ```
  Expected: `node_modules` created, `package-lock.json` updated

- [ ] Playwright browser:
  ```bash
  playwright install
  ```
  Expected: Chromium downloaded (~400MB)

---

## PHASE 2: UNIT & REGRESSION TESTS (60 min)

### Backend Regression (pytest)

Run: `pytest tests/test_api_regression.py -v`

- [ ] **T001-T005: Views & UI Rendering**
  - Landing page loads without errors
  - All Jinja templates render (register, dashboard, new inspection)
  - Vue SPA initializes
  - No JavaScript console errors
  - Responsive on mobile (375px), tablet (768px), desktop (1440px)

- [ ] **T010-T015: Auth Flow**
  - [ ] Register new user (POST /auth/register)
    - Valid email + password → 201, user created
    - Duplicate email → 400
    - Weak password → 400
  - [ ] Email verification works
    - Token sent to email (mock OK)
    - Verify endpoint accepts token
    - email_verified flag set to True
  - [ ] Login successful (POST /auth/login)
    - Correct credentials → 200 + token/cookie
    - Wrong password → 401
    - Missing email field → 400
  - [ ] Password change (POST /auth/password-change)
    - Requires old_password
    - New password accepted
    - Login with new password works
  - [ ] Session handling
    - Cookie set with HttpOnly flag
    - Session expires after timeout (manual check)

### API Endpoints Regression

Run: `pytest tests/test_auth_payments_e2e.py -v`

- [ ] **Core Endpoints Respond**
  - [ ] GET /api/v1/health → 200 OK
  - [ ] GET /api/v1/docs → 200 (FastAPI docs)
  - [ ] GET /metrics → 200 (if METRICS_ENABLED)

Run: `pytest tests/test_cors_regression.py -v`

- [ ] **CORS Configuration**
  - [ ] Allowed origins configured correctly
  - [ ] Preflight requests (OPTIONS) → 200
  - [ ] Non-allowed origins rejected
  - [ ] Credentials header handled properly

### E2E Auth & Payments

Run: `pytest tests/test_auth_payments_e2e.py::test_* -v`

- [ ] **Payment Flow (if ЮKassa configured)**
  - [ ] Subscription creation → YooKassa redirect
  - [ ] Payment webhook received
  - [ ] Subscription status updated
  - [ ] Pro features unlocked

### Email Verification

Run: `pytest tests/test_email_verification.py -v`

- [ ] **Email Verification**
  - [ ] Token generated on registration
  - [ ] Email sent (check logs)
  - [ ] Token validation works
  - [ ] Resend token endpoint works

### Password Security

Run: `pytest tests/test_password_confirm.py -v`

- [ ] **Password Confirmation**
  - [ ] Old password required for change
  - [ ] New password validated
  - [ ] Hash updated in database

---

## PHASE 3: INSPECTION WORKFLOW (90 min)

### Manual Inspection Creation

Run: `pytest tests/test_vehicle_analysis_e2e.py -v`

- [ ] **T020: Create Inspection**
  - [ ] POST /inspections/create with manual vehicle input
    - Brand, model, year, mileage accepted
    - Defects array optional
    - inspection.id returned
    - Created timestamp set

- [ ] **T021: Add Defects**
  - [ ] PUT /inspections/{id}/defects
    - Multiple defect objects accepted
    - Each defect has: area, type, severity, location (optional)
    - Array updated in DB

- [ ] **T022: Analysis (LLM)**
  - [ ] POST /inspections/{id}/analyze
    - LLM called (OpenAI/OpenRouter)
    - Risks array populated
    - Each risk has: evidence[], rationale, confidence, priority
    - Response time <5s

- [ ] **T023: Report Generation**
  - [ ] POST /inspections/{id}/report
    - PDF binary returned
    - Content-Type: application/pdf
    - File size >1KB
    - Includes: vehicle info, checklist, risks, parts prices

- [ ] **T024: History & Pagination**
  - [ ] GET /inspections
    - Returns user's inspections
    - Pagination works (limit, offset)
    - Sorted by created_at DESC
    - Response time <300ms

### Avito Parser (with Fallback)

Run: `pytest tests/test_avito_captcha_resilience.py -v` (requires Chromium)

- [ ] **T030: Avito URL Parsing**
  - [ ] Valid URL recognized
  - [ ] Playwright fetches page
  - [ ] Vehicle data extracted (brand, model, year, mileage)
  - [ ] Parsing time <5s

- [ ] **T031: Captcha Handling**
  - [ ] Captcha detected → log warning
  - [ ] Fallback form shown to user
  - [ ] User can continue with manual input
  - [ ] No hard failure

- [ ] **T032: Invalid URL Rejection**
  - [ ] Non-Avito URL rejected with 400
  - [ ] Error message shown to user

- [ ] **T033: Manual Fallback**
  - [ ] Manual vehicle input form works
  - [ ] Same as T020 (create inspection)
  - [ ] Inspection created successfully

### Parser Regression

Run: `pytest tests/test_listing_parsers_regression.py -v`

- [ ] **Listing Parsers**
  - [ ] Avito parser returns ParsedListing
  - [ ] Auto.ru parser works (if implemented)
  - [ ] Drom parser works (if implemented)
  - [ ] Each parser handles errors gracefully

---

## PHASE 4: FRONTEND TESTS (30 min)

Run: `cd frontend && npm run test`

### Component Unit Tests

- [ ] **AuthModal** component
  - [ ] Renders login/register tabs
  - [ ] Form submission calls API
  - [ ] Error messages displayed

- [ ] **InspectionComposer** component
  - [ ] Vehicle form renders
  - [ ] Defects array manageable
  - [ ] Submit button enabled when valid

- [ ] **InspectionOverview** component
  - [ ] Inspection data displayed
  - [ ] Risks shown with priority badges
  - [ ] PDF download button visible

- [ ] **DashboardView** component
  - [ ] History panel shows inspections
  - [ ] Pagination works
  - [ ] Click inspection shows detail

- [ ] **NewInspectionView** component
  - [ ] URL input field present
  - [ ] Manual input tab works
  - [ ] Avito fallback message shown on error

### Vue Router Navigation

- [ ] Routes defined and working
- [ ] Authentication guard prevents unauthenticated access
- [ ] Redirects work (e.g., /app → login if not authenticated)

---

## PHASE 5: PERFORMANCE TESTS (30 min)

### Bundle Size Check

- [ ] Build frontend:
  ```bash
  cd frontend && npm run build
  ```

- [ ] Check size:
  ```bash
  du -sh frontend/dist  # Should be <600KB total
  du -sh frontend/dist/*.js  # Each file check
  ```

- [ ] **Targets:**
  - [ ] Total dist <500KB (gzipped: <200KB)
  - [ ] index.js <200KB
  - [ ] vendor.js <300KB
  - [ ] No unused dependencies

### API Response Time SLA

Run: `python scripts/perf_test.py` (or manual curl)

- [ ] **Register:** <500ms
  ```bash
  time curl -X POST http://localhost:8000/api/v1/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"perf@test.ru","password":"Test123!"}'
  ```

- [ ] **Login:** <300ms
- [ ] **Create Inspection:** <500ms
- [ ] **Analyze:** <5s (with LLM)
- [ ] **Generate Report:** <3s
- [ ] **Get Inspections:** <300ms
- [ ] **Health Check:** <20ms

### Lighthouse Audit

```bash
npm install -g lighthouse
npm run build
# Serve dist/ on localhost:8000 (or use docker-compose)
lighthouse http://localhost:8000/app --view
```

- [ ] **Mobile Scores:**
  - [ ] Performance: ≥80
  - [ ] Accessibility: ≥90
  - [ ] Best Practices: ≥90
  - [ ] SEO: ≥80

- [ ] **Key Metrics:**
  - [ ] LCP (Largest Contentful Paint): <2.5s
  - [ ] FID (First Input Delay): <100ms
  - [ ] CLS (Cumulative Layout Shift): <0.1

---

## PHASE 6: ERROR HANDLING & EDGE CASES (60 min)

### Critical Error Scenarios

- [ ] **E001: Invalid VIN**
  - [ ] Input: VIN too short
  - [ ] Expected: 400 error OR accepted with note
  - [ ] User sees message: "Проверьте VIN-код"

- [ ] **E002: LLM API Error**
  - [ ] Mock OpenAI timeout
  - [ ] Expected: 500 error with user message
  - [ ] Message: "Анализ временно недоступен"
  - [ ] User can retry

- [ ] **E003: PDF Generation Failure**
  - [ ] Mock reportlab crash
  - [ ] Expected: 500 error
  - [ ] Message: "Ошибка генерации отчета"
  - [ ] Contact support shown

- [ ] **E004: Backend Unavailable (503)**
  - [ ] Stop API service
  - [ ] Frontend shows: "Сервис недоступен"
  - [ ] Graceful error page

- [ ] **E005: Database Connection Fail**
  - [ ] API returns 500
  - [ ] Logs error
  - [ ] Alert sent (if monitoring)

- [ ] **E006: Parts Prices API Down**
  - [ ] parts_prices block shows "Цены недоступны"
  - [ ] Report still generated
  - [ ] No blank/empty block

- [ ] **E007: High Mileage Vehicle**
  - [ ] Mileage >300k km
  - [ ] Risk flagged: "Высокий пробег"
  - [ ] Evidence shown

### Rate Limiting

- [ ] **Rate Limit on Auth**
  - [ ] Rapid registrations rejected
  - [ ] HTTP 429 returned
  - [ ] X-RateLimit-* headers present

- [ ] **Rate Limit on Analysis**
  - [ ] Multiple /analyze calls throttled
  - [ ] Queue implemented (if Redis enabled)

### SQL Injection Prevention

- [ ] **VIN Input:**
  - [ ] Input: `'; DROP TABLE users; --`
  - [ ] Expected: Rejected or escaped safely
  - [ ] No SQL error in response

- [ ] **Pydantic Validation:**
  - [ ] VehicleInput schema enforced
  - [ ] Invalid types rejected
  - [ ] No unexpected fields accepted

---

## PHASE 7: SECURITY CHECKS (30 min)

### CORS & Headers

- [ ] **CORS Headers:**
  ```bash
  curl -i http://localhost:8000/api/v1/health
  # Check: Access-Control-Allow-Origin
  ```

- [ ] **Security Headers:**
  - [ ] X-Content-Type-Options: nosniff
  - [ ] X-Frame-Options: SAMEORIGIN (if needed)
  - [ ] Strict-Transport-Security (if HTTPS)

- [ ] **Session Cookie:**
  - [ ] HttpOnly flag set
  - [ ] Secure flag set (if HTTPS)
  - [ ] SameSite=Lax or Strict

### Authentication

- [ ] **JWT Token:**
  - [ ] Expires after timeout
  - [ ] Signature verified on each request
  - [ ] Cannot be tampered with

- [ ] **Password Hashing:**
  - [ ] Passwords hashed (bcrypt)
  - [ ] Plain text not in logs
  - [ ] Hash verified on login

### XSS Prevention

- [ ] **HTML Escaping:**
  - [ ] User input in parts_prices escaped
  - [ ] No <script> injection possible
  - [ ] Check: `curl http://localhost:8000/cabinet | grep '<script'`

---

## PHASE 8: DOCUMENTATION & LOGS (30 min)

### Documentation

- [ ] **README.md:**
  - [ ] Install instructions correct
  - [ ] Docker commands work
  - [ ] API examples provided
  - [ ] Environment variables documented

- [ ] **TESTING_PLAN_QA.md:**
  - [ ] Test scenarios documented
  - [ ] Runnable test commands
  - [ ] Expected results clear

- [ ] **docs/AVITO.md:**
  - [ ] Playwright setup documented
  - [ ] Captcha handling explained
  - [ ] Troubleshooting steps

- [ ] **docs/VPS_DEPLOY.md (if exists):**
  - [ ] Deployment steps clear
  - [ ] DNS/SSL setup documented

### Logging

- [ ] **Structured Logs:**
  - [ ] JSON logs enabled (`JSON_LOGS=true`)
  - [ ] Log level configurable
  - [ ] Important events logged

- [ ] **Error Logs:**
  - [ ] Errors captured with context
  - [ ] Stack traces present
  - [ ] No sensitive data (passwords, tokens)

---

## PHASE 9: PRODUCTION HARDENING (30 min)

### Configuration

- [ ] **Environment Check:**
  ```bash
  python -c "from app.config import settings; print(settings.production_hardening_issues)"
  ```
  - [ ] Should return empty list (or empty dict)
  - [ ] If issues: address them before deploy

- [ ] **Key Settings:**
  - [ ] `ENVIRONMENT` not set to "production" (local testing)
  - [ ] `DEBUG` = false
  - [ ] `RATE_LIMIT_ENABLED` = true (production)
  - [ ] `METRICS_ENABLED` = true (if monitoring setup)

### Database

- [ ] **Migrations:**
  ```bash
  alembic current  # Check current migration
  alembic upgrade head  # Apply pending migrations
  ```

- [ ] **Backups:**
  - [ ] Backup strategy documented
  - [ ] Restore procedure tested

### Monitoring

- [ ] **Health Endpoint:**
  ```bash
  curl http://localhost:8000/api/v1/health
  ```
  - [ ] Always returns 200
  - [ ] Can be checked every minute

- [ ] **Metrics Endpoint:**
  ```bash
  curl http://localhost:8000/metrics
  ```
  - [ ] Returns Prometheus format (if enabled)
  - [ ] Includes request counters, timers

- [ ] **Logs Setup:**
  - [ ] Logs written to file (not just stdout)
  - [ ] Log rotation configured
  - [ ] Error alerts implemented

---

## PHASE 10: FINAL SIGN-OFF (30 min)

### Test Summary

- [ ] Total tests run: ___
- [ ] Tests passed: ___
- [ ] Tests failed: ___
- [ ] Tests skipped: ___
- [ ] Coverage: ___%

### Known Issues

List any known issues that are NOT blockers:

| Issue | Severity | Owner | Target Fix |
|-------|----------|-------|-----------|
| | | | |

### Go/No-Go Decision

- [ ] **All critical tests PASS** (blocking issues resolved)
- [ ] **Performance SLA met** (bundle <500KB, API <2s)
- [ ] **Security hardening complete**
- [ ] **Documentation updated**
- [ ] **Monitoring configured**

**QA Sign-off:**

```
Name: ___________________________
Date: ___________________________
Status: GO / NO-GO

Notes:
_________________________________
_________________________________
_________________________________
```

---

## POST-DEPLOY CHECKS (within 24 hours)

- [ ] API health check passes
- [ ] User can register
- [ ] User can create inspection
- [ ] PDF reports generate
- [ ] No errors in logs
- [ ] Metrics normal
- [ ] Uptime monitoring active

---

## REGRESSION TEST SCHEDULE

- **Per commit:** `pytest tests/test_api_regression.py`
- **Daily:** Full test suite + Lighthouse
- **Weekly:** Manual E2E flow + security audit
- **Monthly:** Load test + performance analysis

---

## CONTACTS & ESCALATION

- **Backend issues:** Check `app/` logs → contact backend lead
- **Frontend issues:** Browser DevTools → contact frontend lead
- **Parser issues:** Check Avito docs → contact parser specialist
- **Payment issues:** Check YooKassa logs → contact payment engineer
- **Monitoring issues:** Check Prometheus/Grafana → contact DevOps

---

## APPENDIX: Command Reference

```bash
# Start API
python run_api.py

# Start frontend dev
cd frontend && npm run dev

# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_api_regression.py::TestAuthFlow::test_t010_register_new_user -v

# Build frontend
cd frontend && npm run build

# Check bundle size
du -sh frontend/dist

# Check API health
curl http://localhost:8000/api/v1/health

# Generate test coverage
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# View logs
docker compose logs -f api | jq .

# Run Lighthouse
lighthouse http://localhost:8000/app --view
```

---

**Version:** 1.0  
**Last Updated:** 2026-06-08  
**Next Review:** 2026-06-15
