# SUCCESS METRICS & KPIs (SPRINT COMPLETION CRITERIA)

**Спринт:** ПОДКАПОТ MVP  
**Период:** 8-28 июня 2026 (3 недели)  
**Дата создания:** 8 июня 2026

---

## ТИРИНГИРОВАНИЕ УСПЕХА

Спринт считается **УСПЕШНЫМ** если выполнены все **GREEN-LEVEL** критерии.  
Спринт считается **ХОРОШИМ** если выполнены все **GREEN** + 80% **AMBER**.  
Спринт считается **ТРЕБУЕТ РЕФЛЕКСИИ** если не выполнены **GREEN** критерии.

---

## BACKEND METRICS

### 1. Parser Success Rate (CRITICAL)

**Определение:** % успешных парсов объявлений с первой попытки

| Метрика | Target | Warning | Critical Fail |
|---------|--------|---------|---------------|
| Overall success rate | ≥95% | 85-94% | <85% |
| Avito success rate | ≥95% | 80-94% | <80% |
| Auto.ru success rate | ≥90% | 75-89% | <75% |
| Drom success rate | ≥85% | 70-84% | <70% |
| Captcha detection rate | ≥99% | 95-98% | <95% |

**Как измерять:**
```python
# Daily metrics report
total_parses = db.query(ParseAttempt).filter(
    ParseAttempt.created_at > yesterday
).count()

success_count = db.query(ParseAttempt).filter(
    ParseAttempt.created_at > yesterday,
    ParseAttempt.success == True
).count()

success_rate = (success_count / total_parses) * 100
print(f"Parser success rate: {success_rate:.1f}%")
```

**Green Status (Week 1):** ≥95% on test set (50+ URLs)  
**Green Status (Week 2):** ≥95% on production URLs (100+ daily)  
**Green Status (Week 3):** ≥95% sustained through launch

**Escalation:** If <90%, trigger emergency standup

---

### 2. Parsing Latency (PERFORMANCE)

**Определение:** Time to parse single listing (wall clock time)

| Percentile | Target | Warning | Fail |
|-----------|--------|---------|------|
| p50 | <2s | 2-3s | >3s |
| p90 | <4s | 4-5s | >5s |
| p95 | <5s | 5-7s | >7s |
| p99 | <10s | 10-15s | >15s |
| Max | <30s (timeout) | - | - |

**Как измерять:**
```python
import statistics

latencies = [2.1, 2.5, 3.2, 1.8, 4.5, 2.2, 3.1, 2.9]  # seconds

stats = {
    'p50': statistics.median(latencies),
    'p90': statistics.quantiles(latencies, n=10)[8],
    'p95': statistics.quantiles(latencies, n=20)[18],
    'p99': statistics.quantiles(latencies, n=100)[98]
}
```

**Green Status:** p95 <5s (typical case)  
**Escalation:** If p99 >15s consistently

---

### 3. Risk Scoring Accuracy (ALGORITHM QUALITY)

**Определение:** Correlation между risk_score и user verdict (worth_looking | caution | skip)

| Metric | Target | Method |
|--------|--------|--------|
| Spearman correlation | >0.7 | Compare 50+ user verdicts with generated scores |
| User satisfaction | ≥4.0/5 | Post-inspection survey: "Was score accurate?" |
| False positive rate | <10% | % of SKIP verdicts that user found acceptable |
| False negative rate | <15% | % of WORTH_LOOKING that had hidden issues |

**Как измерять:**
```python
from scipy.stats import spearmanr

user_verdicts = [3, 1, 2, 3, 2, 1, 3, ...]  # 1=skip, 2=caution, 3=worth_looking
risk_scores = [78, 25, 55, 82, 60, 15, 90, ...]  # 0-100

correlation, p_value = spearmanr(user_verdicts, risk_scores)
print(f"Correlation: {correlation:.2f}")  # Target: >0.7
```

**Green Status (Week 2):** ≥0.65 correlation on 20 test cases  
**Green Status (Week 3):** ≥0.70 correlation on 50+ real cases  
**Nice-to-have:** User survey avg ≥4.0/5

---

### 4. Error Rate (STABILITY)

**Определение:** % API requests returning 5xx errors

| Metric | Target | Warning | Fail |
|--------|--------|---------|------|
| Overall error rate | <0.5% | 0.5-1% | >1% |
| Parser errors | <1% | 1-2% | >2% |
| Database errors | <0.1% | 0.1-0.5% | >0.5% |
| LLM API errors | <2% | 2-5% | >5% |

**Как измерять:**
```python
# From Prometheus or logs
total_requests = 10000
error_requests = 45
error_rate = (error_requests / total_requests) * 100
# Result: 0.45% ✓ (target: <0.5%)
```

**Green Status:** <0.5% in staging  
**Green Status:** <0.5% in production (24h monitoring)

---

### 5. Webhook Delivery Reliability

**Определение:** % webhook'ов, успешно обработанных или переданных в retry queue

| Metric | Target | Method |
|--------|--------|--------|
| First-attempt success | ≥95% | Successful HTTP 202 response |
| Total delivery (with retries) | ≥99.9% | Message in queue or processed within 24h |
| Processing latency (p95) | <2s | Time from webhook receive to DB update |
| Idempotency check | 100% | No duplicate processing |

**Green Status (Week 2):** 100% of test webhooks processed  
**Green Status (Week 3):** 99.9% delivery on 100+ prod webhooks

---

### 6. Database Health

**Определение:** Query performance, replication lag, data consistency

| Metric | Target | Warning | Fail |
|--------|--------|---------|------|
| Query p95 latency | <100ms | 100-200ms | >200ms |
| Replication lag | <100ms | 100-500ms | >500ms |
| Constraint violations | 0 | - | >0 |
| Orphaned records | 0 | - | >0 |

**Green Status:** All constraints pass daily integrity check

---

---

## FRONTEND METRICS

### 7. Lighthouse Score (MOBILE)

**Определение:** Google Lighthouse mobile score

| Category | Target | Warning | Fail |
|----------|--------|---------|------|
| Overall | ≥85 | 75-84 | <75 |
| Performance | ≥85 | 75-84 | <75 |
| Accessibility | ≥85 | 75-84 | <75 |
| Best Practices | ≥90 | 80-89 | <80 |
| SEO | ≥90 | 80-89 | <80 |

**Как измерять:**
```bash
npm run build  # Production build
npm run lighthouse  # Run Lighthouse

# Results:
# Performance: 88
# Accessibility: 87
# Best Practices: 92
# SEO: 90
```

**Green Status (Week 1):** ≥75 on initial audit  
**Green Status (Week 2):** ≥80 on all categories  
**Green Status (Week 3):** ≥85 on performance + accessibility

---

### 8. Core Web Vitals

**Определение:** Google's core metrics for page performance

| Metric | Target | Warning | Fail |
|--------|--------|---------|------|
| LCP (Largest Contentful Paint) | <2.5s | 2.5-3.5s | >3.5s |
| FID (First Input Delay) | <100ms | 100-300ms | >300ms |
| CLS (Cumulative Layout Shift) | <0.1 | 0.1-0.25 | >0.25 |

**Как измерять:**
```javascript
// In browser console or performance monitoring
const lcpEntries = performance.getEntriesByName('largest-contentful-paint');
const lcp = lcpEntries[lcpEntries.length - 1]?.renderTime || 0;
console.log(`LCP: ${lcp}ms`);  // Target: <2500ms
```

**Green Status (Week 2):** LCP <3.0s on 3G simulation  
**Green Status (Week 3):** LCP <2.5s on real network

---

### 9. Bundle Size (OPTIMIZATION)

**Определение:** Gzipped size of frontend JavaScript + CSS

| Package | Target | Warning | Fail |
|---------|--------|---------|------|
| Main JS | <100KB | 100-150KB | >150KB |
| CSS | <30KB | 30-50KB | >50KB |
| **Total (gzip)** | **<120KB** | 120-180KB | >180KB |

**Как измерять:**
```bash
npm run build
ls -lh dist/assets/
# Or use webpack-bundle-analyzer
```

**Green Status (Week 2):** <150KB total  
**Green Status (Week 3):** <120KB total

---

### 10. Mobile Viewport Coverage

**Определение:** % of views that render correctly on different screen sizes

| Viewport | Target | Method |
|----------|--------|--------|
| 320px (iPhone SE) | 100% | Manual test + browser devtools |
| 480px (small phone) | 100% | Manual test |
| 768px (tablet) | 100% | Manual test |
| 1024px (desktop) | 100% | Manual test |
| 1920px (large desktop) | 100% | Manual test |

**Views to test:**
- [ ] LoginView
- [ ] RegisterView
- [ ] DashboardView
- [ ] NewInspectionView
- [ ] InspectionDetailView
- [ ] LandingView

**Green Status:** All views on all 5 viewports show no broken layout, no horizontal scroll

---

### 11. Component Accessibility (A11y)

**Определение:** WCAG 2.1 AA compliance

| Check | Target | Tool |
|-------|--------|------|
| Color contrast | ≥4.5:1 | axe DevTools |
| Keyboard navigation | 100% usable | Manual testing |
| ARIA labels | All interactive | Manual audit |
| Heading hierarchy | Correct | axe DevTools |
| Screen reader | Working | NVDA/JAWS test |

**Green Status:** axe DevTools audit shows <3 issues (minor only)

---

---

## TESTING METRICS

### 12. Test Coverage (CODE QUALITY)

**Определение:** % of critical code paths tested

| Layer | Target | Tool |
|-------|--------|------|
| Backend Unit | ≥80% | pytest-cov |
| Backend Integration | ≥70% | pytest |
| Frontend Unit | ≥70% | vitest |
| E2E (critical flows) | 100% | playwright |

**Как измерять:**
```bash
pytest --cov=app --cov-report=html tests/
# Results: 82% coverage ✓

npm run test -- --coverage
# Results: 75% coverage ✓
```

**Green Status:** ≥80% for critical paths (auth, parsing, risk scoring)

---

### 13. Test Success Rate

**Определение:** % of tests passing on CI

| Suite | Target | Duration |
|-------|--------|----------|
| Unit tests | 100% | <2min |
| Integration tests | 100% | <5min |
| E2E tests | 100% (no flakes) | <10min |
| Regression suite | 100% | <15min |

**Как измерять:**
```bash
pytest tests/ -v  # Must show: passed X, failed 0
npm run test  # Must show: passed X, failed 0
```

**Green Status (Week 1):** ≥95% pass (allow 1-2 flakes)  
**Green Status (Week 2):** 100% pass (no flakes)  
**Green Status (Week 3):** 100% pass sustained

---

### 14. E2E Test Reliability

**Определение:** % of E2E tests passing consistently (no flakes)

| Scenario | Target | Runs |
|----------|--------|------|
| Register → Create Inspection → Report | 100% | 10x |
| Login with JWT | 100% | 10x |
| Webhook status update | 100% | 10x |

**Green Status:** Run each scenario 10x, 100% pass every time

---

### 15. Performance Testing (Load)

**Определение:** API performance under load

| Metric | Target | Concurrency |
|--------|--------|-------------|
| Latency p95 | <1s | 10 concurrent users |
| Latency p99 | <3s | 10 concurrent users |
| Error rate | <1% | 10 concurrent users |
| Throughput | >10 req/s | 10 concurrent users |

**Как измерять (locust):**
```python
# tests/load_test.py
from locust import HttpUser, task

class PodkapoUser(HttpUser):
    @task
    def register(self):
        self.client.post("/api/v1/auth/register", json={...})

# Run: locust -f tests/load_test.py --headless -u 10 -r 5 -t 2m
```

**Green Status (Week 3):** p95 <1s at 10 concurrent

---

---

## OPERATIONS METRICS

### 16. Deployment Success Rate

**Определение:** % of deployments that complete without rollback

| Stage | Target | Rollback time |
|-------|--------|---------------|
| Staging | 100% | N/A |
| Production | 100% | <2min |

**Green Status:** 3/3 deployments successful (no rollbacks)

---

### 17. Monitoring & Alerting

**Определение:** All critical metrics are monitored

| Alert | Target | Escalation |
|-------|--------|------------|
| Error rate >1% | ✓ | Immediate |
| Parser success <90% | ✓ | 5 min |
| Latency p95 >2s | ✓ | 10 min |
| Database query >500ms | ✓ | 15 min |
| Disk usage >80% | ✓ | 30 min |

**Green Status:** All alerts configured, tested, and active

---

### 18. Documentation Completeness

**Определение:** % of deliverables documented

| Document | Status | Owner |
|----------|--------|-------|
| API Docs (Swagger) | ✓ | Backend |
| Deployment Guide | ✓ | DevOps |
| Incident Runbook | ✓ | DevOps |
| Architecture Decisions | ✓ | Backend |
| Frontend Component Docs | ✓ | Frontend |
| Database Schema Docs | ✓ | Backend |

**Green Status:** All 6 documents complete and reviewed

---

---

## GO/NO-GO DECISION GATES (Friday Week 3)

**Release can proceed ONLY IF all GREEN gates pass:**

### Functional Completeness
- [ ] Avito parser: success rate ≥95%
- [ ] Risk scoring: correlation ≥0.70
- [ ] Webhook: 99.9% delivery
- [ ] PDF reports: generated in <5s
- [ ] Image upload: works with fallback

### Quality Assurance
- [ ] Regression tests: 100% pass
- [ ] E2E tests: 100% pass (no flakes)
- [ ] Security audit: 0 critical issues
- [ ] Code coverage: ≥80% for critical paths
- [ ] Performance: LCP <2.5s, bundle <150KB

### Performance & Scale
- [ ] Lighthouse mobile: ≥85
- [ ] Load test: p95 <1s @ 10 concurrent
- [ ] Error rate: <0.5%
- [ ] No data loss in testing

### Operations Readiness
- [ ] Monitoring configured: all alerts active
- [ ] Runbooks written: 3+ procedures documented
- [ ] Backups tested: restore succeeds
- [ ] Team trained: all know their roles

### Business & Stakeholders
- [ ] Product owner: approved launch
- [ ] Legal: terms/privacy reviewed (if needed)
- [ ] Finance: costs within budget
- [ ] Support: ready to handle users

---

## SUCCESS CRITERIA BY WEEK

### WEEK 1 COMPLETION (June 14)
**Minimum viable features + foundation:**

- [x] Parser retry logic: ≥95% success
- [x] Frontend layout: all text ≥14px
- [x] Checkbox: styled without emoji
- [x] Placeholder images: <100ms generation
- [x] Webhook endpoint: accepts POST
- [x] API regression tests: ≥90% pass
- [x] No critical blockers

**Decision:** Proceed to Week 2?  
✓ YES if 6/7 items complete  
✗ NO if <5/7 (negotiate pivot/delay)

---

### WEEK 2 COMPLETION (June 21)
**Integration + full feature set:**

- [x] Risk scoring: ≥0.65 correlation
- [x] PDF async: <5s generation
- [x] Image upload: fallback working
- [x] E2E tests: 3 scenarios, 100% pass
- [x] Frontend polish: Lighthouse ≥75
- [x] CI/CD pipeline: green on all commits
- [x] No critical security issues

**Decision:** Proceed to Week 3?  
✓ YES if 6/7 items complete  
✗ NO if <5/7 (extend sprint or defer features)

---

### WEEK 3 COMPLETION (June 28)
**Launch readiness:**

- [x] All Week 1-2 items complete
- [x] Load test: p95 <1s @ 10 concurrent
- [x] Security audit: 0 critical
- [x] Documentation: all docs complete
- [x] Monitoring: all alerts active
- [x] Team confidence: ≥4/5 ready
- [x] Stakeholder approval: product owner +1

**Decision:** LAUNCH or DELAY?  
✓ LAUNCH if 7/7 items + green gates  
✗ DELAY if <7/7 (push to Week 4 or v1.1)

---

## MEASUREMENT & REPORTING

### Daily Metrics Report (morning standup)

**Format:** Slack message with key metrics

```
🎯 SPRINT METRICS (Day 3)

Parser:
  Success rate: 94.2% (target: ≥95%) ⚠️
  Avg latency: 2.3s (target: <2s) ✓
  Captcha hits: 2.1% (target: <5%) ✓

Frontend:
  Lighthouse: 76/100 (target: ≥85) ⚠️
  Bundle: 128KB gzip (target: <150KB) ✓

Tests:
  Unit: 12/12 ✓
  Integration: 8/8 ✓
  E2E: 2/3 flaky ⚠️

Blockers:
  1. Parser captcha detection needs tuning
  2. E2E tests flaky on auth flow

Next 24h:
  - Tune captcha detection
  - Fix E2E auth flakiness
```

### Weekly Retrospective (Friday 4pm)

**Metrics covered:**
- Velocity (story points)
- Test coverage trend
- Performance trend
- Risk status
- Blockers & resolutions

**Outputs:**
- Update Success_Metrics.md
- Adjust Week 2/3 priorities if needed
- Document lessons learned

---

## REFERENCE: TYPICAL SUCCESS PROFILE

**"Healthy sprint" looks like:**
```
Parser success: 95-99% ✓
API error rate: 0.2-0.5% ✓
Lighthouse: 82-90 ✓
LCP: 1.8-2.3s ✓
Test coverage: 82% ✓
E2E pass rate: 100% (no flakes) ✓
Deployment: 100% success ✓
Team: 4-5/5 confidence ✓
```

**"Unhealthy sprint" looks like:**
```
Parser success: <85% ✗
API error rate: >1% ✗
Lighthouse: <70 ✗
LCP: >3.5s ✗
Test coverage: <70% ✗
E2E flakiness: >20% ✗
Deployment: 1+ rollbacks ✗
Team: 2-3/5 confidence ✗
→ ESCALATE & ADJUST SCOPE
```

---

## FINAL SCORECARD (Post-Launch)

**After Week 3, fill this out:**

| Area | Target | Achieved | Status |
|------|--------|----------|--------|
| **Backend** | - | - | - |
| Parser success rate | ≥95% | ___ % | ✓/✗ |
| Risk score correlation | ≥0.70 | 0.___ | ✓/✗ |
| API error rate | <0.5% | ___% | ✓/✗ |
| **Frontend** | - | - | - |
| Lighthouse mobile | ≥85 | ___ | ✓/✗ |
| LCP | <2.5s | ___s | ✓/✗ |
| Bundle size | <150KB | ___KB | ✓/✗ |
| **Quality** | - | - | - |
| Test coverage | ≥80% | ___% | ✓/✗ |
| E2E pass rate | 100% | ___% | ✓/✗ |
| Security issues | 0 critical | ___ | ✓/✗ |
| **Ops** | - | - | - |
| Deployment success | 100% | ___% | ✓/✗ |
| Uptime | ≥99% | ___% | ✓/✗ |
| **Overall** | **GREEN** | ? | ? |

**Launch Status:** ✓ GO / ✗ NO-GO
