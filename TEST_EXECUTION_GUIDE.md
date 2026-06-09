# Test Execution Guide - ПОДКАПОТ

**Quick Start for Running QA Tests**

---

## 30-SECOND QUICK START

```bash
# 1. Install dependencies (first time only)
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. Run smoke tests (2 minutes)
pytest tests/test_api_regression.py::TestAuthFlow::test_t010_register_new_user -v

# 3. Run critical flows (10 minutes)
pytest tests/test_e2e_critical_flows.py -v

# ✓ Done!
```

---

## DETAILED EXECUTION PATHS

### Path 1: SMOKE (2 min) - Verify basic functionality

**Use when:** You need a quick health check before deeper testing

```bash
# Option A: PowerShell
./run_qa_checks.ps1 -Mode smoke

# Option B: Bash/Git Bash
bash run_quick_tests.sh smoke

# Option C: Manual pytest
pytest tests/test_api_regression.py::TestAuthFlow::test_t010_register_new_user -v
pytest tests/test_auth_payments_e2e.py::test_t012_login_success -v
```

**What it checks:**
- API imports without errors
- Database initializes
- Frontend builds

**Expected output:**
```
test_t010_register_new_user PASSED
test_t012_login_success PASSED
✓ Smoke tests completed in 45s
```

---

### Path 2: QUICK (5 min) - Full regression suite

**Use when:** Before committing changes, or for daily verification

```bash
# Option A: PowerShell
./run_qa_checks.ps1 -Mode quick

# Option B: Bash/Git Bash
bash run_quick_tests.sh quick

# Option C: Manual pytest
pytest tests/test_api_regression.py -v
pytest tests/test_auth_payments_e2e.py -v
pytest tests/test_password_confirm.py -v
pytest tests/test_cors_regression.py -v
```

**What it checks:**
- All auth endpoints
- Core API endpoints
- CORS configuration
- Password security
- Session handling

**Expected output:**
```
test_api_regression.py: 15 passed
test_auth_payments_e2e.py: 8 passed
test_password_confirm.py: 3 passed
test_cors_regression.py: 4 passed
=============== 30 passed in 45s ===============
```

---

### Path 3: CRITICAL FLOWS (10 min) - E2E user scenarios

**Use when:** Testing complete user journeys and error handling

```bash
# Full critical flows test
pytest tests/test_e2e_critical_flows.py -v

# Or run specific scenario:
pytest tests/test_e2e_critical_flows.py::TestAuthFlow -v
pytest tests/test_e2e_critical_flows.py::TestInspectionWorkflow -v
pytest tests/test_e2e_critical_flows.py::TestAvitoFallback -v
pytest tests/test_e2e_critical_flows.py::TestErrorHandling -v

# With detailed output:
pytest tests/test_e2e_critical_flows.py -v -s
```

**Scenarios covered:**
1. **Registration → Verification → Login → Dashboard**
2. **New Inspection (manual) → Analysis → Report PDF**
3. **Avito Parser with Fallback**
4. **Error Handling & Graceful Degradation**
5. **Performance (SLA compliance)**

**Expected output:**
```
TestAuthFlow::test_t010_register_new_user PASSED
TestAuthFlow::test_t012_login_success PASSED
...
TestInspectionWorkflow::test_t022_analyze_generates_risks PASSED
TestInspectionWorkflow::test_t023_report_generates_pdf PASSED
TestAvitoFallback::test_t031_avito_unavailable_shows_fallback PASSED
TestErrorHandling::test_e001_invalid_vin_error PASSED
TestPerformance::test_registration_completes_within_sla PASSED
...
=============== 28 passed in 5m 34s ===============
```

---

### Path 4: FULL (15 min) - Everything including E2E and frontend

**Use when:** Before major releases or for comprehensive validation

```bash
# Option A: PowerShell
./run_qa_checks.ps1 -Mode full

# Option B: Bash/Git Bash
bash run_quick_tests.sh full

# Option C: Manual step-by-step
# Step 1: Backend regression
pytest tests/test_api_regression.py -v
pytest tests/test_auth_payments_e2e.py -v
pytest tests/test_vehicle_analysis_e2e.py -v
pytest tests/test_email_verification.py -v
pytest tests/test_listing_parsers_regression.py -v

# Step 2: Critical flows
pytest tests/test_e2e_critical_flows.py -v

# Step 3: Frontend
cd frontend
npm run test
npm run build
cd ..

# Step 4: Performance checks
du -sh frontend/dist
```

**All tests included:**
- All regression tests
- All E2E scenarios
- Frontend unit tests
- Performance checks

---

### Path 5: ADVANCED - Specific test files

**Use when:** Debugging specific functionality

#### Auth Tests Only
```bash
pytest tests/test_api_regression.py::TestAuthFlow -v
pytest tests/test_password_confirm.py -v
pytest tests/test_email_verification.py -v
```

#### Inspection Tests Only
```bash
pytest tests/test_vehicle_analysis_e2e.py -v
pytest tests/test_e2e_critical_flows.py::TestInspectionWorkflow -v
```

#### Parser Tests Only
```bash
pytest tests/test_listing_parsers_regression.py -v
pytest tests/test_drom_parser.py -v
pytest tests/test_avito_captcha_resilience.py -v
```

#### API Regression Only
```bash
pytest tests/test_api_regression.py -v
pytest tests/test_cors_regression.py -v
```

#### Frontend Only
```bash
cd frontend
npm run test -- --ui  # Interactive UI
npm run test -- --coverage  # With coverage report
```

---

## RUNNING TESTS WITH OPTIONS

### Verbose Output
```bash
# Show all print statements
pytest tests/test_e2e_critical_flows.py -v -s
```

### Show Failed Tests First
```bash
pytest tests/test_api_regression.py -v --lf
```

### Stop on First Failure
```bash
pytest tests/test_api_regression.py -v -x
```

### Run 3 Times (flakiness check)
```bash
pytest tests/test_e2e_critical_flows.py -v --count=3
```

### Show Coverage Report
```bash
pytest tests/ --cov=app --cov-report=html
# Open: htmlcov/index.html
```

### Run Specific Test by Name
```bash
pytest -k "test_t010_register_new_user" -v
pytest -k "auth" -v  # All tests with "auth" in name
```

### Generate JUnit XML (for CI/CD)
```bash
pytest tests/test_api_regression.py -v --junit-xml=report.xml
```

---

## INTERACTIVE TESTING (Development)

### Frontend Interactive Tests
```bash
cd frontend
npm run test -- --ui
# Opens browser with interactive test runner
```

### Watch Mode (re-run on file change)
```bash
cd frontend
npm run test -- --watch
```

### Debug Specific Test
```bash
# Terminal 1: Start backend
python run_api.py

# Terminal 2: Run single test with debug
pytest tests/test_e2e_critical_flows.py::TestInspectionWorkflow::test_t022_analyze_generates_risks -v -s --pdb
# --pdb opens debugger on failure
```

---

## BROWSER TESTING (Playwright)

### Run Playwright E2E Tests
```bash
# Enable Playwright tests
export RUN_PLAYWRIGHT_E2E=1  # or set in .env
pytest tests/test_playwright_smoke_e2e.py -v -s

# Or on Windows (PowerShell):
$env:RUN_PLAYWRIGHT_E2E=1
pytest tests/test_playwright_smoke_e2e.py -v -s
```

**What it does:**
- Starts real API server
- Opens browser
- Fills forms
- Navigates UI
- Takes screenshots

**Requirements:**
- Chromium installed via `playwright install`
- Sufficient disk space (screenshots stored)

---

## CI/CD INTEGRATION

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install deps
        run: |
          pip install -r requirements.txt
          playwright install
      
      - name: Run regression tests
        run: pytest tests/test_api_regression.py -v
      
      - name: Run critical flows
        run: pytest tests/test_e2e_critical_flows.py -v
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Frontend tests
        run: cd frontend && npm install && npm run test
```

---

## TROUBLESHOOTING

### Test Fails: "Database locked"
```bash
# Solution: Use fresh SQLite for each test
# Already handled in fixtures, but if stuck:
rm tests/e2e*.db
pytest tests/test_api_regression.py -v
```

### Test Fails: "No module named 'app'"
```bash
# Solution: Run from project root
cd /path/to/autorewier
pytest tests/test_api_regression.py -v
```

### Test Fails: "OPENROUTER_API_KEY missing"
```bash
# Solution: Set in .env or skip LLM tests
echo "OPENROUTER_API_KEY=sk-" >> .env
# Or mock it:
pytest tests/test_e2e_critical_flows.py -v -m "not llm"
```

### Frontend Test Fails: "vitest not found"
```bash
# Solution: Install frontend deps
cd frontend
npm install
npm run test
```

### Playwright Fails: "Chromium not installed"
```bash
# Solution: Install browsers
playwright install
```

### Tests Timeout
```bash
# Increase timeout
pytest tests/test_playwright_smoke_e2e.py --timeout=60
```

---

## PERFORMANCE TESTING

### Check API Response Time
```bash
# Manual timing test
time curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"perf@test.ru","password":"Test123!"}'

# Expected: <500ms
```

### Load Testing (optional, requires locust)
```bash
pip install locust

# Create locustfile.py with your scenarios
# Run:
locust -f locustfile.py --host=http://localhost:8000
# Open: http://localhost:8089
```

### Bundle Size Check
```bash
cd frontend
npm run build

# Check size
du -sh dist
# Expected: <600KB total

# Detailed breakdown
npm install --save-dev rollup-plugin-visualizer
# Review bundle analysis
```

### Lighthouse Audit
```bash
npm install -g lighthouse

# Build frontend first
cd frontend && npm run build && cd ..

# Start API
python run_api.py &

# Run audit
lighthouse http://localhost:8000/app --view
# Expected: Performance >80, Accessibility >90
```

---

## DOCUMENTATION

### Test Documentation Files
- **TESTING_PLAN_QA.md** - Complete test plan with all scenarios
- **PERFORMANCE_METRICS.md** - Monitoring and metrics
- **QA_CHECKLIST.md** - Comprehensive sign-off checklist
- **TEST_EXECUTION_GUIDE.md** - This file

### Test Code Documentation
- **tests/test_api_regression.py** - API regression tests
- **tests/test_e2e_critical_flows.py** - Critical user flows
- **tests/test_auth_payments_e2e.py** - Auth and payment tests
- **tests/test_vehicle_analysis_e2e.py** - Inspection analysis tests

---

## QUICK REFERENCE TABLE

| Test Type | Command | Time | When to Use |
|-----------|---------|------|------------|
| **Smoke** | `./run_qa_checks.ps1 -Mode smoke` | 2 min | Quick check |
| **Quick** | `./run_qa_checks.ps1 -Mode quick` | 5 min | Before commit |
| **Critical Flows** | `pytest tests/test_e2e_critical_flows.py -v` | 10 min | Before PR |
| **Full Suite** | `./run_qa_checks.ps1 -Mode full` | 15 min | Before release |
| **Performance** | `lighthouse http://localhost:8000/app --view` | 5 min | Weekly |
| **Specific Test** | `pytest -k "test_t010" -v` | <1 min | Debugging |

---

## EXAMPLE TEST SESSIONS

### Session 1: Quick Verification Before Commit
```bash
# Time: 5-10 min

# 1. Run quick tests
./run_quick_tests.sh quick

# 2. Check bundle size
cd frontend && npm run build && du -sh dist && cd ..

# 3. Manual smoke check
curl http://localhost:8000/api/v1/health

# Result: Green ✓ Ready to commit
```

### Session 2: Full Validation Before Release
```bash
# Time: 30 min

# 1. Full test suite
./run_qa_checks.ps1 -Mode full

# 2. Frontend build
cd frontend && npm run build && cd ..

# 3. Lighthouse audit
lighthouse http://localhost:8000/app --view

# 4. Manual E2E walkthrough
# Open http://localhost:8000/app in browser
# Register → Create inspection → Generate report

# 5. Check logs
docker compose logs api | grep ERROR

# Result: All green ✓ Ready for production
```

### Session 3: Debugging Specific Issue
```bash
# Time: 15-30 min

# 1. Identify failing test
pytest tests/test_e2e_critical_flows.py::TestInspectionWorkflow::test_t022_analyze_generates_risks -v

# 2. Run with debug
pytest tests/test_e2e_critical_flows.py::TestInspectionWorkflow::test_t022_analyze_generates_risks -v -s --pdb

# 3. Check logs
docker compose logs api | tail -50

# 4. Fix issue and rerun
pytest tests/test_e2e_critical_flows.py::TestInspectionWorkflow::test_t022_analyze_generates_risks -v

# Result: Issue resolved ✓
```

---

## KEY METRICS TO TRACK

After running tests, track these:

- **Test Pass Rate:** Should be 100%
- **Execution Time:** Smoke <2min, Quick <5min, Full <15min
- **Coverage:** Backend >70%, Frontend >60%
- **Bundle Size:** <500KB (gzipped <200KB)
- **API SLA:** Register <500ms, Login <300ms, Analyze <5s
- **Lighthouse Score:** Performance >80 on mobile

---

**Version:** 1.0  
**Last Updated:** 2026-06-08  
**Status:** Ready to Execute
