# Performance Metrics & Monitoring

**Last Updated:** 2026-06-08

---

## 1. KEY METRICS DASHBOARD

### Uptime & Availability

```
Target: 99.5% uptime
Alert Threshold: <99.0%
Check Frequency: Every 5 minutes

Status Codes Tracking:
- 200-299: Success
- 400-499: Client error (monitored)
- 500-599: Server error (alert)
```

### API Response Times (SLA)

| Endpoint | p50 | p95 | p99 | Alert (>) |
|----------|-----|-----|-----|-----------|
| `POST /auth/register` | <100ms | <200ms | <300ms | 500ms |
| `POST /auth/login` | <80ms | <150ms | <250ms | 300ms |
| `GET /inspections` | <150ms | <300ms | <500ms | 800ms |
| `POST /inspections/create` | <200ms | <500ms | <1s | 1.5s |
| `POST /inspections/{id}/analyze` | <2s | <5s | <8s | 10s |
| `POST /inspections/{id}/report` | <1s | <3s | <5s | 6s |
| `GET /health` | <10ms | <20ms | <50ms | 100ms |

### Error Rate

```
Target: <0.5% errors across all requests
Alert: >1% error rate in 5-min window

Categorization:
- 4xx errors: User errors (validation)
- 5xx errors: Server errors (alert ops)
```

### Frontend Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Bundle Size (gzipped) | ❓ | <500KB |
| Lighthouse Performance | ❓ | >80 (mobile) |
| Largest Contentful Paint (LCP) | ❓ | <2.5s |
| First Input Delay (FID) | ❓ | <100ms |
| Cumulative Layout Shift (CLS) | ❓ | <0.1 |

### Test Coverage

```
Backend (app/): Target >70%
Frontend (frontend/src): Target >60%
Critical paths: Target 100%

Unit tests: pytest tests/ --cov=app
Frontend: npm run test -- --coverage
```

---

## 2. PROMETHEUS METRICS (if METRICS_ENABLED=true)

### Available Metrics

```bash
# Query endpoint: GET /metrics

# Request duration histogram
http_request_duration_seconds_bucket{endpoint="/api/v1/inspections/analyze"}
http_request_duration_seconds_sum{endpoint="/api/v1/inspections/analyze"}
http_request_duration_seconds_count{endpoint="/api/v1/inspections/analyze"}

# Request count by status
http_request_total{status="200"}
http_request_total{status="400"}
http_request_total{status="500"}

# Active connections
http_request_in_progress

# Custom: inspection analysis
inspection_analysis_duration_seconds_bucket
inspection_analysis_error_total{error="llm_timeout"}
inspection_analysis_error_total{error="avito_parser_failure"}
```

### Scrape Configuration (Prometheus)

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'autorewier-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

---

## 3. LOGGING & OBSERVABILITY

### Log Levels

```
DEBUG: verbose info (parser details, SQL queries)
INFO: important events (registration, analysis start/complete)
WARNING: unexpected but handled (avito timeout, parts_prices unavailable)
ERROR: failures (LLM error, PDF generation fail)
CRITICAL: system failures (DB connection lost, auth failure)
```

### Structured Logging (JSON)

Enable with `JSON_LOGS=true`:

```json
{
  "timestamp": "2026-06-08T12:34:56.789Z",
  "level": "INFO",
  "event": "inspection_analysis_complete",
  "inspection_id": "uuid-here",
  "vehicle": {
    "brand": "Toyota",
    "year": 2018
  },
  "risks_count": 5,
  "duration_ms": 2345,
  "user_id": "user-uuid"
}
```

### Log Aggregation

**Recommended:** ELK Stack (Elasticsearch, Logstash, Kibana) or Grafana Loki

```bash
# View real-time logs (Docker)
docker compose logs -f api | jq .

# Save logs to file
docker compose logs api > logs/api.log
tail -f logs/api.log | jq '.[] | select(.level == "ERROR")'
```

---

## 4. CRITICAL ALERTS

### Alert Rules (Prometheus)

```yaml
groups:
  - name: autorewier
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          (rate(http_request_total{status=~"5.."}[5m]) / rate(http_request_total[5m])) > 0.01
        for: 5m
        annotations:
          summary: "High error rate detected"
          severity: critical

      # Slow API response
      - alert: SlowAPIResponse
        expr: |
          histogram_quantile(0.95, http_request_duration_seconds_bucket) > 2
        for: 10m
        annotations:
          summary: "API response time exceeds SLA"
          severity: warning

      # Health check failing
      - alert: HealthCheckFailed
        expr: |
          up{job="autorewier-api"} == 0
        for: 1m
        annotations:
          summary: "API health check failed"
          severity: critical

      # LLM failures increasing
      - alert: HighLLMErrors
        expr: |
          rate(inspection_analysis_error_total{error="llm_timeout"}[5m]) > 0.1
        for: 5m
        annotations:
          summary: "OpenAI/OpenRouter API issues detected"
          severity: warning

      # Avito parser failures
      - alert: AvitoParserDown
        expr: |
          rate(inspection_analysis_error_total{error="avito_parser_failure"}[5m]) > 0.3
        for: 10m
        annotations:
          summary: "Avito parser failure rate >30%"
          severity: warning
```

### Notification Channels

```
Critical (immediate): Slack #incidents
Warning (batch): Email digest daily
Info (dashboard): Grafana panels only
```

---

## 5. BUNDLE SIZE ANALYSIS

### Frontend Optimization

```bash
# Check current size
cd frontend
npm run build

# Analyze bundle
npx bundle-report dist/

# Expected breakdown:
# - index.js: ~150-200KB (uncompressed, gzipped <80KB)
# - vendor.js: ~250-300KB (uncompressed, gzipped <100KB)
# - Total dist: ~400-500KB (uncompressed, gzipped <200KB)
```

### Size Limits

```javascript
// frontend/vitest.config.ts
const SIZE_LIMITS = {
  'dist/index.js': 250_000, // bytes (uncompressed)
  'dist/vendor.js': 350_000,
  'dist/': 600_000, // total
};

// CI will fail if exceeded
```

---

## 6. LIGHTHOUSE AUDIT

### How to Run

```bash
# Install
npm install -g lighthouse

# Mobile audit (recommended)
lighthouse https://your-domain.com/app --view --form-factor=mobile

# Desktop audit
lighthouse https://your-domain.com/app --view

# Batch run (CI)
npm install --save-dev @lhci/cli@0.11.0
lhci autorun --config=lighthouserc.json
```

### Target Scores

```
Mobile:
  ✓ Performance: >80
  ✓ Accessibility: >90
  ✓ Best Practices: >90
  ✓ SEO: >90
  ✓ PWA: N/A

Desktop:
  ✓ Performance: >85
  ✓ Accessibility: >90
  ✓ Best Practices: >90
  ✓ SEO: >90
```

### Config File (lighthouserc.json)

```json
{
  "ci": {
    "collect": {
      "url": ["http://localhost:8000/app"],
      "numberOfRuns": 3,
      "settings": {
        "configPath": "./lighthouse-config.js"
      }
    },
    "upload": {
      "target": "temporary-public-storage"
    },
    "assert": {
      "preset": "lighthouse:recommended",
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.8 }],
        "categories:accessibility": ["error", { "minScore": 0.9 }],
        "uses-http2": ["off"],
        "unused-css": ["off"]
      }
    }
  }
}
```

---

## 7. TESTING METRICS

### Test Execution Time

```
Target: Full test suite <15 min

Breakdown:
  - Backend unit tests: ~5 min
  - Backend E2E tests: ~5 min
  - Frontend unit tests: ~2 min
  - Frontend build check: ~1 min
  - Bundle size check: <1 min
```

### Coverage Goals

```
app/:
  - models/: 100% (critical)
  - services/: >80%
  - api/: >75%
  - bot/: >70%
Overall: >70%

frontend/src:
  - components/: >60%
  - views/: >50%
  - utils/: >80%
Overall: >60%
```

### Test Types Distribution

```
Unit tests: 60% (fast, isolated)
Integration tests: 25% (real DB, mocked external)
E2E tests: 15% (full flow, browser)

Speed ratio:
  Unit: <100ms per test
  Integration: <1s per test
  E2E: <10s per test
```

---

## 8. DATABASE PERFORMANCE

### Query Metrics

```
SELECT * FROM users: <10ms
SELECT * FROM inspections (paginated): <50ms
Complex JOIN (inspection + vehicle + risks): <100ms

Slow query threshold: >500ms
  -> Log and alert

Index usage:
  ✓ inspections.user_id
  ✓ inspections.created_at DESC
  ✓ risks.inspection_id
  ✓ users.email UNIQUE
```

### Connection Pool

```python
# app/database.py
pool_pre_ping = True  # Verify connection before use
pool_size = 20
max_overflow = 10
pool_recycle = 3600  # Recycle connections after 1 hour
```

---

## 9. AVITO PARSER RELIABILITY

### Success Rate Target

```
Overall: >95% (with graceful fallback)

Breakdown:
  - Successful parse: >85%
  - Graceful fallback: >10%
  - Hard failure (alert): <5%
```

### Monitoring

```python
# app/services/parsers/avito_fetch.py
logger.info("avito_parse_start", extra={"url": url})
logger.info("avito_parse_success", extra={
    "url": url,
    "vehicle": {...},
    "duration_ms": elapsed,
})
logger.warning("avito_parse_fallback", extra={
    "url": url,
    "reason": "captcha",
})
logger.error("avito_parse_failure", extra={
    "url": url,
    "error": str(e),
})
```

---

## 10. DASHBOARD EXAMPLES

### Grafana Dashboard JSON

```json
{
  "dashboard": {
    "title": "AutoRewier - ПОДКАПОТ",
    "panels": [
      {
        "title": "API Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)"
          }
        ],
        "thresholds": [
          {
            "value": 2,
            "color": "yellow"
          },
          {
            "value": 5,
            "color": "red"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_request_total{status=~'5..'}[5m])"
          }
        ]
      },
      {
        "title": "Inspection Analysis Success Rate",
        "targets": [
          {
            "expr": "100 - (rate(inspection_analysis_error_total[5m]) / rate(inspection_analysis_total[5m]) * 100)"
          }
        ]
      }
    ]
  }
}
```

---

## 11. SLO & SLI TARGETS

### Service Level Objectives

```
Availability: 99.5% (monthly downtime allowance: ~3.6 hours)
Latency: P95 < 2 seconds for user-facing endpoints
Error Budget: 0.5% of requests can fail (30 errors per 6000 requests)
```

### Service Level Indicators

```
Uptime % = (Total Requests - Failed Requests) / Total Requests
Latency p95 = histogram_quantile(0.95, duration)
Error Rate = Failed Requests / Total Requests
```

### Burn Rate

```
If 1-week burn rate > 5x, declare incident
If monthly burn rate > 1x, page on-call engineer

Formula:
  error_rate_actual / error_budget_rate = burn_rate
```

---

## 12. INCIDENT RESPONSE

### Escalation Path

1. **Alert triggered** (Prometheus)
   ↓
2. **Slack notification** (#incidents channel)
   ↓
3. **On-call engineer** checks dashboard
   ↓
4. **Manual investigation** if automated remediation fails
   ↓
5. **Post-mortem** within 24 hours

### Quick Diagnostics

```bash
# Check API health
curl -s http://localhost:8000/api/v1/health | jq .

# Check recent errors
docker compose logs api | grep ERROR | tail -20

# Database connectivity
docker compose exec api python -c "import app.database; print('DB OK')"

# Disk space
docker compose exec api df -h

# Memory usage
docker stats --no-stream
```

### Rollback Procedure

```bash
# If latest release breaks things:
docker compose down
git checkout previous-stable-tag
docker compose up --build -d
docker compose logs -f api
```

---

## 13. REPORTING

### Weekly Metrics Report

```
To: Tech Lead, Product Manager
Subject: AutoRewier Metrics - Week of June 2-8, 2026

Uptime: 99.8%
Error Rate: 0.3%
P95 API Latency: 1.2s
Bundle Size: 485KB (gzipped)
Test Coverage: 72%

Incidents: 0
Alerts triggered: 2 (both auto-resolved)

Week-over-week:
  + Faster /analyze endpoint (5s avg → 4.2s)
  - Slightly higher error rate (0.2% → 0.3%)
  ~ Bundle size stable

Action items:
  - Investigate Avito parser captcha rate (increasing trend)
  - Optimize image analysis step (currently slowest)
```

### Monthly Retrospective

```
Q2 Summary (June 1-30):
  ✓ SLO Achievement: 99.6% (target 99.5%)
  ✓ Bundle size maintained <500KB
  ✗ Avito fallback rate higher than target (15% vs 10%)
  ~ Test coverage: 70% → 72% (good trend)

Key improvements:
  1. Implemented graceful degradation for parts_prices API
  2. Added Avito proxy rotation (better than captcha fallback)
  3. Automated PDF generation optimization

Next month focus:
  1. Reduce Avito fallback rate <10%
  2. Improve /analyze latency <4s
  3. Increase test coverage to >75%
```

---

## Quick Reference

**Check these daily:**
```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/metrics | head -20
docker compose logs api --tail=50 | grep ERROR
```

**Check these weekly:**
```bash
pytest tests/test_api_regression.py -v
cd frontend && npm run test
npm run build && du -sh frontend/dist
```

**Check these monthly:**
```bash
lighthouse https://your-domain.com/app --view
# Review SLO dashboard in Grafana
# Review logs for emerging patterns
```

---

**Owner:** DevOps/QA Team  
**Last Review:** 2026-06-08  
**Next Review:** 2026-06-15
