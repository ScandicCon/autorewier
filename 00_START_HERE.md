# 🚀 ПОДКАПОТ SPRINT: START HERE

**Sprint Duration:** June 8-28, 2026 (3 weeks)  
**Goal:** Launch MVP with Avito integration, risk scoring, full testing  
**Status:** READY TO BEGIN

---

## What is this?

You're looking at a **complete 3-week sprint plan** for the ПОДКАПОТ project. This document points you to the right information based on what you need.

---

## QUICK NAVIGATION

### "I just joined the team, what do I need to know?" (10 min)

Read in this order:

1. **SPRINT_SUMMARY.txt** (this explains everything at 30,000 feet)
2. **README_SPRINT.md** (this is the practical guide)
3. **DAILY_PRIORITIES.md** (this is your daily checklist)

**Total time:** 10-15 minutes to be fully oriented.

---

### "I'm a [Role] and want to know my tasks" (5 min)

Pick your role:

**Backend Developer**
- Go to: `README_SPRINT.md` → "By Roles" → Backend section
- Then: `DAILY_PRIORITIES.md` (find your first day)
- Deep dive: `ARCHITECTURE_DECISIONS.md` (parser, webhook, risk scoring)

**Frontend Developer**
- Go to: `README_SPRINT.md` → "By Roles" → Frontend section
- Then: `DAILY_PRIORITIES.md` (find your first day)
- Deep dive: `ARCHITECTURE_DECISIONS.md` (layout system, image upload)

**QA / Test Engineer**
- Go to: `README_SPRINT.md` → "By Roles" → QA section
- Then: `DAILY_PRIORITIES.md` (find your first day)
- Deep dive: `ARCHITECTURE_DECISIONS.md` (test architecture)

**DevOps / Infrastructure**
- Go to: `README_SPRINT.md` → "By Roles" → DevOps section
- Then: `DAILY_PRIORITIES.md` (find your first day)
- Deep dive: `docker-compose.yml` and `.env.example`

**Project Manager**
- Go to: `README_SPRINT.md` → "By Roles" → PM section
- Then: `DAILY_PRIORITIES.md` (find your first day)
- Deep dive: `SUCCESS_METRICS.md` (go/no-go gates)

---

### "What's the timeline?" (2 min)

See: **TIMELINE_VISUAL.txt**

Quick summary:
- **Week 1:** Avito parser, layout fixes, webhook, regression tests
- **Week 2:** Risk scoring, PDF reports, E2E tests, polish
- **Week 3:** Load testing, security, documentation, LAUNCH

---

### "What could go wrong?" (5 min)

See: **RISK_REGISTER.md** → "Top 3 Critical Risks"

Quick summary:
1. Avito parser rate limiting (mitigation: retry + captcha detection)
2. Database migration failure (mitigation: test locally + backup)
3. LLM costs overrun (mitigation: token counting + caching)

---

### "How do I know if we're succeeding?" (5 min)

See: **SUCCESS_METRICS.md** → "Go/No-Go Decision Gates"

Quick summary:
- Parser: ≥95% success rate
- Frontend: Lighthouse ≥85 (mobile)
- Tests: 100% pass, no flakes
- Ops: <0.5% error rate

---

### "How do I set up my environment?" (30 min)

See: **SETUP_CHECKLIST.md**

This covers:
- Python + venv setup
- Frontend npm setup
- Docker + database setup
- Slack/calendar communication setup
- First day tasks

---

## DOCUMENT MAP

```
00_START_HERE.md                    ← YOU ARE HERE (navigation hub)
│
├─ SPRINT_SUMMARY.txt               ← Executive summary (30,000 ft view)
│
├─ README_SPRINT.md                 ← Practical guide (how things work)
│
├─ DAILY_PRIORITIES.md              ← Daily checklist (PN-ПТ each week)
│                                      - Specific tasks per role
│                                      - Success criteria per day
│
├─ SPRINT_PLAN.md                   ← Full 3-week detailed plan
│                                      - Phases, priorities, metrics
│                                      - Checkpoints, dependencies
│
├─ ARCHITECTURE_DECISIONS.md        ← Technical deep-dives
│                                      - How to implement features
│                                      - Code patterns, examples
│
├─ RISK_REGISTER.md                 ← Risk management
│                                      - 12 identified risks
│                                      - Mitigation strategies
│                                      - Escalation procedures
│
├─ SUCCESS_METRICS.md               ← Performance metrics & go/no-go
│                                      - 18 metrics with targets
│                                      - Measurement methods
│                                      - Launch gates
│
├─ TIMELINE_VISUAL.txt              ← Visual schedule
│                                      - ASCII timeline
│                                      - Milestones per day
│                                      - Resource allocation
│
├─ SETUP_CHECKLIST.md               ← Pre-sprint setup
│                                      - Environment configuration
│                                      - Team communication
│                                      - First day readiness
│
└─ 00_START_HERE.md                 ← Navigation (this file)
```

---

## SPRINT AT A GLANCE

| Dimension | Value |
|-----------|-------|
| **Duration** | 3 weeks (8-28 June 2026) |
| **Team Size** | 5 people (1 backend, 1 frontend, 1 QA, 1 DevOps, 1 PM) |
| **Story Points** | 54 total (21 + 18 + 15 per week) |
| **Goal** | Launch MVP |
| **Critical Success** | All go/no-go gates pass |
| **If blocked** | Extend 1 week OR defer features to v1.1 |

---

## KEY DATES & DEADLINES

| Date | Event | Impact | Owner |
|------|-------|--------|-------|
| **Mon Jun 8** | Sprint kickoff | Must happen | PM |
| **Fri Jun 14** | Week 1 review | Foundation complete? | All |
| **Fri Jun 21** | Week 2 review | Integration complete? | All |
| **Fri Jun 28 10am** | Go/no-go decision | Can we launch? | PM + tech leads |
| **Fri Jun 28 6pm** | DEPLOY TO PRODUCTION | We launch! 🚀 | DevOps + backend |

---

## CRITICAL PATH (What blocks launch?)

```
┌─────────────────────┐
│ Parser (≥95%)       │
│ Risk Scoring (≥0.7) │ ──→ MVP READY ──→ Security audit ──→ LAUNCH
│ Tests (100%)        │     (Week 3)      (0 critical)     (Jun 28)
│ Lighthouse (≥85)    │
└─────────────────────┘
```

If ANY of these fails → Emergency escalation → Scope adjustment

---

## DAILY STANDUP (15 min, 9:00 UTC)

**Every weekday morning at 9:00 UTC:**
- What did I do yesterday?
- What will I do today?
- Am I blocked?

Attendance required: All 5 team members

---

## COMMUNICATION

**Main channel:** `#sprint-podkapot` on Slack

**Escalation:** `#critical` for emergencies

**Questions:** Ask in Slack thread, mention relevant lead

---

## METRICS SNAPSHOT

### Success Criteria (Friday Week 3)

✅ **Functionality**
- Parser: ≥95% success
- Risk scoring: ≥0.70 correlation
- Webhook: 99.9% delivery
- Image upload: working + fallback

✅ **Quality**
- Regression tests: 100% pass
- E2E tests: 100% pass, no flakes
- Security: 0 critical issues
- Coverage: ≥80% critical paths

✅ **Performance**
- Lighthouse: ≥85 (mobile)
- LCP: <2.5 seconds
- Bundle: <150KB gzip
- Load test: p95 <1s @ 10 concurrent

✅ **Operations**
- Monitoring: Configured
- Runbooks: Written
- Backups: Tested
- Team: Trained & confident

**All green = LAUNCH! 🚀**

---

## FIRST STEPS (DO THIS TODAY)

1. **Read** SPRINT_SUMMARY.txt (20 min)
2. **Read** README_SPRINT.md (15 min)
3. **Read** your role section in DAILY_PRIORITIES.md (10 min)
4. **Do** environment setup from SETUP_CHECKLIST.md (30 min)
5. **Attend** Monday 9am standup (confirm you're ready)

**Total prep time:** ~75 minutes

---

## QUESTIONS?

| If you want to know... | Read this... |
|------------------------|--------------|
| Big picture overview | SPRINT_SUMMARY.txt |
| How things work day-to-day | README_SPRINT.md |
| What I should do today | DAILY_PRIORITIES.md |
| How to implement a feature | ARCHITECTURE_DECISIONS.md |
| How to measure success | SUCCESS_METRICS.md |
| What could go wrong | RISK_REGISTER.md |
| Visual timeline | TIMELINE_VISUAL.txt |
| How to set up environment | SETUP_CHECKLIST.md |

---

## THE 30-SECOND VERSION

**We're launching a car inspection MVP in 3 weeks.**

**Week 1:** Build foundation (parser, layout, tests)  
**Week 2:** Add features (risk scoring, reports, E2E tests)  
**Week 3:** Polish & launch (performance, security, go-live)

**Success = All metrics green on Friday**

**If metrics aren't green by Friday = Extend sprint or defer features**

**Either way, we ship something good! 🚀**

---

## TEAM, YOU'RE READY!

Everything you need is in this folder:
- ✅ Full sprint plan (54 story points, 3 weeks)
- ✅ Architecture decisions (how to build it)
- ✅ Risk mitigation (what to watch for)
- ✅ Success metrics (how to measure it)
- ✅ Daily priorities (what to do today)
- ✅ Setup checklist (how to get ready)

**Now go make it happen!**

---

## MONDAY MORNING CHECKLIST (Before 9am standup)

- [ ] This entire document read
- [ ] Environment setup complete
- [ ] First day tasks identified
- [ ] Team member contact info saved
- [ ] Calendar events confirmed
- [ ] Slack notifications on
- [ ] Coffee ready ☕
- [ ] READY TO START! 🚀

---

**Sprint starts Monday 9:00 AM UTC**

**Questions? Ask in #sprint-podkapot**

**Let's launch this MVP! 🚀**

---

*Created: June 8, 2026*  
*Last updated: June 8, 2026*  
*Status: READY FOR EXECUTION*
