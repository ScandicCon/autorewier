# RISK REGISTER & MITIGATION STRATEGIES

**Спринт:** ПОДКАПОТ MVP (3 недели, 8-28 июня 2026)  
**Дата создания:** 8 июня 2026  
**Собственник:** Project Lead  

---

## КРИТИЧЕСКИЕ РИСКИ (CRITICAL)

### 1. Avito Parser Rate Limiting / Blocking

**Описание:**  
Avito может заблокировать наш IP на новых адресах или при высокой частоте запросов. Это приводит к captcha или 403 Forbidden. На staging это могло работать, но на боевых данных (масштабирование) может прекратиться.

**Вероятность:** HIGH (80%)  
**Влияние:** HIGH (60%) — основной feature парсинга  
**Приоритет:** P0 (Critical)

**Метрики:**
- Parsing success rate падает ниже 80%
- Captcha hits >10% всех запросов
- User complaints о неработающих проверках

**Mitigation Strategy:**

| Шаг | Ответственный | Статус | Deadline |
|-----|---------------| -------|----------|
| Implement exponential backoff (2s→15s) | Backend | TODO | Jun 8 |
| Add captcha detection heuristics | Backend | TODO | Jun 8 |
| Setup proxy rotation (if available) | Backend/DevOps | TODO | Jun 10 |
| Monitor success rate daily | QA | TODO | Jun 8+ |
| Prepare fallback: manual URL input | Frontend | TODO | Jun 11 |
| Have offline mode for demo (cached data) | Backend | TODO | Jun 20 |

**Contingency Plan (if >3 days blocked):**
- Use Selenium + headless browser profile (slower but more reliable)
- Negotiate with Avito for API access (B2B route)
- Pivot to manual inspection creation (users paste data)

**Owner:** Backend Lead  
**Review:** Daily in standup

---

### 2. Database Migration Failure in Production

**Описание:**  
При деплое в продакшен может быть ошибка в Alembic миграции. Это приводит к downtime и потере данных (если не прокатится rollback).

**Вероятность:** MEDIUM (30%)  
**Влияние:** CRITICAL (100%) — полный downtime  
**Приоритет:** P0 (Critical)

**Метрики:**
- Миграция не применилась
- Данные inconsistent
- API возвращает 5xx

**Mitigation Strategy:**

| Шаг | Ответственный | Статус | Deadline |
|-----|---------------| -------|----------|
| Test migrations locally (dev → test DB) | Backend | TODO | Jun 20 |
| Write migration rollback script | DevOps | TODO | Jun 22 |
| Have backup before deploy | DevOps | TODO | Jun 26 |
| Dry-run migration on staging | DevOps | TODO | Jun 25 |
| Document migration SOP | DevOps | TODO | Jun 24 |
| Have DBA on-call during deploy | DevOps | TODO | Jun 26 |

**Contingency Plan (if migration fails):**
```bash
# Rollback script
alembic downgrade -1  # Undo last migration
# Or restore from backup
pg_restore -d podkapot /backups/podkapot-2026-06-26.sql
```

**Owner:** DevOps Lead  
**Review:** Daily in QA checklist

---

### 3. LLM API Costs Exceed Budget

**Описание:**  
OpenAI API могу потреблять больше токенов, чем ожидается. При масштабировании это может привести к $1000+ расходов в месяц.

**Вероятность:** MEDIUM (40%)  
**Влияние:** HIGH (30%) — финансовый удар  
**Приоритет:** P1 (High)

**Метрики:**
- Cost per inspection >$0.10 (target: $0.05)
- Token usage >50K/day

**Mitigation Strategy:**

| Шаг | Ответственный | Статус | Deadline |
|-----|---------------| -------|----------|
| Implement token counter | Backend | TODO | Jun 10 |
| Set spending alerts in OpenAI | DevOps | TODO | Jun 8 |
| Cache LLM responses (Redis) | Backend | TODO | Jun 15 |
| Fallback to rule-based analysis | Backend | TODO | Jun 17 |
| Monitor daily cost | QA | TODO | Jun 8+ |
| Set spending limit in OpenAI dashboard | DevOps | TODO | Jun 8 |

**Contingency Plan (if >$0.15/inspection):**
- Switch to cheaper model (gpt-3.5-turbo)
- Use cached responses for similar inspections
- Disable LLM for free tier users
- Manual analysis mode

**Owner:** Backend Lead  
**Review:** Weekly cost report

---

## ВЫСОКИЕ РИСКИ (HIGH)

### 4. Frontend Layout Bugs on Mobile

**Описание:**  
Оптимизация для мобильных устройств может быть неполной. Браузерные дев-тулс показывают OK, а на реальном телефоне — поломанный макет.

**Вероятность:** HIGH (60%)  
**Влияние:** MEDIUM (40%) — UX issues  
**Приоритет:** P1 (High)

**Метрики:**
- Lighthouse mobile <80
- LCP >3s на мобильной сети
- User complaints о неудобстве

**Mitigation Strategy:**

| Шаг | Ответственный | Статус | Deadline |
|-----|---------------| -------|----------|
| Test on real iPhone/Android devices | Frontend | TODO | Jun 10 |
| Set responsive breakpoints (320px, 480px, 768px) | Frontend | TODO | Jun 9 |
| Use mobile-first CSS approach | Frontend | TODO | Jun 9 |
| Run Lighthouse audit weekly | QA | TODO | Jun 9+ |
| Add touch-friendly button sizes (44x44px) | Frontend | TODO | Jun 10 |

**Contingency Plan:**
- Quick CSS fixes in hotfix branch
- Temporary mobile warning banner if severe

**Owner:** Frontend Lead  
**Review:** Every Friday Lighthouse score

---

### 5. E2E Tests are Flaky

**Описание:**  
Playwright тесты иногда падают из-за timing issues, network delays, или race conditions. Это снижает доверие к тестам.

**Вероятность:** HIGH (70%)  
**Влияние:** MEDIUM (30%) — DevOps overhead  
**Приоритет:** P1 (High)

**Метрики:**
- Test flakiness >10% (failed on first run, passed on retry)
- E2E run time unpredictable (10s-60s)

**Mitigation Strategy:**

| Шаг | Ответственный | Статус | Deadline |
|-----|---------------| -------|----------|
| Use explicit waits (not sleep) | QA | TODO | Jun 16 |
| Mock external services in E2E | QA | TODO | Jun 16 |
| Use database fixtures (reset before each test) | QA | TODO | Jun 16 |
| Add retry logic for flaky steps | QA | TODO | Jun 17 |
| Run E2E tests locally 3x to verify | QA | TODO | Jun 20 |

**Contingency Plan:**
- Skip E2E tests on non-critical branches
- Mark as "informational" (don't block merge)
- Run nightly instead of on every commit

**Owner:** QA Lead  
**Review:** After each E2E run

---

### 6. Webhook Delivery Failures

**Описание:**  
External сервис отправляет webhook, но он не обработается (network error, retry failed). Inspection stuck в "processing" state.

**Вероятность:** MEDIUM (50%)  
**Влияние:** MEDIUM (40%) — data inconsistency  
**Приоритет:** P1 (High)

**Метрики:**
- Webhook delivery success <99%
- Orphaned inspections (status not updated)

**Mitigation Strategy:**

| Шаг | Ответственный | Статус | Deadline |
|-----|---------------| -------|----------|
| Implement retry logic (5 attempts, exponential backoff) | Backend | TODO | Jun 11 |
| Store webhook history in database | Backend | TODO | Jun 11 |
| Add webhook signature verification | Backend | TODO | Jun 11 |
| Setup Dead Letter Queue (DLQ) for failed webhooks | Backend | TODO | Jun 18 |
| Monitor webhook success rate | DevOps | TODO | Jun 8+ |
| Daily check for orphaned inspections | QA | TODO | Jun 8+ |

**Contingency Plan:**
- Manual webhook replay from admin panel
- Timeout inspection after 24h processing
- Notify user to retry manually

**Owner:** Backend Lead  
**Review:** Weekly webhook metrics

---

### 7. Team Capacity Underestimated

**Описание:**  
3-недельный спринт с 4 приоритетами может быть слишком амбициозным. Может не хватить времени на тестирование и polish.

**Вероятность:** MEDIUM (50%)  
**Влияние:** HIGH (60%) — missed launch date  
**Приоритет:** P1 (High)

**Метрики:**
- Velocity <80% от planned
- Unfinished tasks >20% от sprint

**Mitigation Strategy:**

| Шаг | Ответственный | Статус | Deadline |
|-----|---------------| -------|----------|
| Daily standup (track velocity) | PM | TODO | Jun 8+ |
| Identify blockers early | All | TODO | Jun 8+ |
| Defer non-critical features | PM | TODO | Jun 10 |
| Add contingency buffer (25%) to estimates | PM | TODO | Jun 8 |
| Consider 2-week sprint extension (to Jun 30) | PM | TODO | Jun 15 |

**Contingency Plan (if running 2+ days behind):**
- Defer nice-to-haves (dark mode, animations)
- Reduce E2E coverage (keep critical flows)
- Skip non-essential features (model-specific checklists v2)
- Launch MVP with known limitations documented

**Owner:** PM/Project Lead  
**Review:** Every Friday retrospective

---

## СРЕДНИЕ РИСКИ (MEDIUM)

### 8. Image Generation Performance

**Описание:**  
PIL-based image generation может быть медленной для большого объёма. Или занимать слишком много памяти при кэшировании.

**Вероятность:** MEDIUM (40%)  
**Влияние:** LOW (20%) — graceful degradation exists  
**Приоритет:** P2 (Medium)

**Метрики:**
- Generation time >500ms
- Disk usage >1GB

**Mitigation Strategy:**
- Pre-generate common templates
- Use async generation (queue)
- Cache aggressively (30 days TTL)

---

### 9. Frontend Bundle Size Exceeds Limits

**Описание:**  
Vue components + libraries + CSS могут привести к большому JS bundle'у. На 3G сети loading долгий.

**Вероятность:** MEDIUM (40%)  
**Влияние:** MEDIUM (30%) — performance, UX  
**Приоритет:** P2 (Medium)

**Метрики:**
- Bundle size >200KB (gzip)
- LCP >3s on slow 3G

**Mitigation Strategy:**
- Code splitting by route
- Lazy load heavy components (PDF viewer)
- Tree-shaking unused code
- Monitor with webpack-bundle-analyzer

---

### 10. Autocode VIN API Unavailable

**Описание:**  
Autocode может быть недоступен во время спринта. API rate limits или отказ в доступе.

**Вероятность:** MEDIUM (30%)  
**Влияние:** MEDIUM (30%) — feature degradation  
**Приоритет:** P2 (Medium)

**Метрики:**
- Autocode API success <95%
- User complaints о VIN check

**Mitigation Strategy:**
- Graceful fallback (show "VIN service unavailable")
- Retry with backoff
- Cache Autocode results
- Document limitation in demo

---

## НИЗКИЕ РИСКИ (LOW)

### 11. Playwright Browser Installation

**Описание:**  
Playwright требует скачивания браузера. На staging может быть network issue.

**Вероятность:** LOW (20%)  
**Влияние:** LOW (10%) — easily fixed  
**Приоритет:** P3 (Low)

**Mitigation:** Cache browser in Docker image, pre-download

---

### 12. Timezone/Localization Issues

**Описание:**  
Даты могут быть некорректны из-за timezone mismatch между сервером и клиентом.

**Вероятность:** LOW (30%)  
**Влияние:** LOW (15%) — confusing UX  
**Приоритет:** P3 (Low)

**Mitigation:** Use UTC server-side, client-side render in local time

---

## RISK DASHBOARD

```
┌─────────────────────────────────────────────────────┐
│ CURRENT RISK STATUS (As of Sprint Start)           │
├─────────────────────────────────────────────────────┤
│ CRITICAL:                                           │
│  ✓ Avito Parser Blocking         [MITIGATING]      │
│  ✓ DB Migration Failures         [PREPARED]        │
│  ✓ LLM Cost Overrun              [MONITORING]      │
├─────────────────────────────────────────────────────┤
│ HIGH:                                               │
│  ✓ Mobile Layout Bugs            [IN PROGRESS]     │
│  ✓ E2E Test Flakiness            [IN PROGRESS]     │
│  ✓ Webhook Delivery              [IN PROGRESS]     │
│  ✓ Team Capacity                 [WATCHING]        │
├─────────────────────────────────────────────────────┤
│ MEDIUM:                                             │
│  ✓ Image Generation Performance  [MONITORING]      │
│  ✓ Bundle Size                   [MONITORING]      │
│  ✓ Autocode API Availability     [CONTINGENCY OK]  │
├─────────────────────────────────────────────────────┤
│ LOW:                                                │
│  ✓ Playwright Installation       [LOW PRIORITY]   │
│  ✓ Timezone Issues               [LOW PRIORITY]   │
└─────────────────────────────────────────────────────┘

Red Flags to Watch:
  🚩 Parser success rate drops below 80%
  🚩 Bundle size exceeds 200KB (gzip)
  🚩 Lighthouse mobile score <70
  🚩 Test flakiness >15%
  🚩 More than 2 people blocked
  🚩 Velocity <70% of planned
```

---

## ESCALATION PROCEDURES

**Level 1: Minor Issue (QA detects)**
- Slack thread in #sprint-podkapot
- Assign to responsible person
- Deadline: Same day resolution

**Level 2: Blocker (Multiple people affected)**
- Slack + mention @backend-lead / @frontend-lead
- Emergency 15min sync
- Document workaround
- Deadline: 2 hours

**Level 3: Critical (Project at risk)**
- Call emergency standup (all hands)
- PM decision on scope change
- Document decision + rationale
- Deadline: 30 min decision

**Example escalation (parser blocked):**
```
🚨 CRITICAL: Avito parser success rate 45% (target 95%)
@backend-lead investigate captcha detection
@qa manually test 5 listings
@pm: do we defer parser to week 2? or pivot to manual input?
Decision needed in 1 hour
```

---

## RISK ACCEPTANCE STATEMENT

**Sprint Constraints:**
- 3 weeks is tight for MVP + full test coverage
- Avito blocking is possible but managed with mitigations
- Some features may be deferred (dark mode, advanced analytics)

**We accept these risks because:**
- Market opportunity (MVP launch > perfect feature)
- Mitigation strategies in place
- Team is experienced with similar projects
- Go/no-go decision point is Friday of Week 2

**If risks materialize:**
- Defer Week 3 polish (still launch Week 3)
- Use beta tag (acknowledge limitations)
- Commit to hotfixes post-launch

---

## WEEKLY RISK REVIEW

**Every Friday 4pm (30 min):**

1. Review actual vs predicted risks
2. Update mitigation status
3. Escalate new risks
4. Adjust priorities if needed
5. Document lessons learned

**Risk Review Checklist:**
- [ ] Avito parser success rate ≥80%?
- [ ] Bundle size <150KB?
- [ ] Lighthouse mobile ≥70?
- [ ] Test flakiness <10%?
- [ ] No data loss incidents?
- [ ] Team velocity on track?
- [ ] No security issues?

---

## CONTINGENCY BUDGET

**Time reserve:** 3 days (included in Week 3)  
**Feature reserve:** 2-3 nice-to-haves that can be deferred  
**Resource reserve:** 1 senior dev for blockers

**Release gates (go/no-go decision):**
- [ ] Parser success rate ≥90%
- [ ] E2E tests 100% pass (not flaky)
- [ ] Security audit 0 critical
- [ ] Lighthouse mobile ≥80
- [ ] Team feels confident

**If any gate fails:** 1-week extension or defer feature to v1.1
