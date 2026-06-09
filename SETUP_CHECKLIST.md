# SETUP CHECKLIST: SPRINT LAUNCH (June 8, 2026)

**Выполнить ПЕРЕД первой встречей**

---

## DOCUMENTATION REVIEW (Everyone)

### Read in this order:

1. **SPRINT_SUMMARY.txt** (15 min)
   - [ ] Read executive summary
   - [ ] Understand critical blockers
   - [ ] Know success metrics

2. **README_SPRINT.md** (10 min)
   - [ ] Read "Quick Start"
   - [ ] Find your role section
   - [ ] Bookmark DAILY_PRIORITIES.md

3. **TIMELINE_VISUAL.txt** (5 min)
   - [ ] See the 3-week timeline
   - [ ] Note go/no-go decision points
   - [ ] Know risk hotspots

4. **By your role:**
   - [ ] **Backend:** Read ARCHITECTURE_DECISIONS.md (parser, webhook, risk scoring)
   - [ ] **Frontend:** Read ARCHITECTURE_DECISIONS.md (layout system, checkbox, image upload)
   - [ ] **QA:** Read ARCHITECTURE_DECISIONS.md (test architecture)
   - [ ] **DevOps:** Review docker-compose.yml and .env.example
   - [ ] **PM:** Read SUCCESS_METRICS.md (go/no-go gates)

5. **Skim these (optional but recommended):**
   - [ ] RISK_REGISTER.md (know top 3 risks)
   - [ ] SUCCESS_METRICS.md (understand what "done" looks like)

---

## ENVIRONMENT SETUP (Backend + QA + DevOps)

### Repository

- [ ] Clone repo: `git clone <url>`
- [ ] Create feature branch: `git checkout -b sprint/week1-foundation`
- [ ] Verify main branch: `git status`

### Python Environment

- [ ] Python 3.11+ installed: `python --version`
- [ ] Create venv: `python -m venv .venv`
- [ ] Activate: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Unix)
- [ ] Install deps: `pip install -r requirements.txt`
- [ ] Install dev deps: `pip install pytest pytest-cov black ruff`

### Database

- [ ] PostgreSQL 15+ running locally OR docker-compose
- [ ] Database created: `createdb podkapot` (or let docker handle it)
- [ ] Migrations run: `alembic upgrade head`
- [ ] Check schema: `psql podkapot -c "\dt"`

### Configuration

- [ ] Copy `.env.example` → `.env`
- [ ] Fill in required variables:
  - [ ] `WEB_SECRET_KEY` (generate random: `python -c "import secrets; print(secrets.token_hex(32))"`)
  - [ ] `TELEGRAM_BOT_TOKEN` (from @BotFather if needed)
  - [ ] `WEBHOOK_SECRET` (generate: `python -c "import secrets; print(secrets.token_hex(32))"`)
  - [ ] `OPENAI_API_KEY` (if doing LLM work Week 2+)
  - [ ] `DATABASE_URL` (if not localhost)

### Running Services

- [ ] Docker installed: `docker --version`
- [ ] Docker compose: `docker-compose --version`
- [ ] Start services: `docker-compose up -d` (or for dev: `docker-compose up api postgres redis`)
- [ ] Check health: `curl http://127.0.0.1:8000/api/v1/health`
- [ ] Logs clean: `docker-compose logs api | tail -20`

### Code Quality Tools

- [ ] Black formatter: `black --check app/`
- [ ] Ruff linter: `ruff check app/`
- [ ] Mypy type checker: `mypy app/` (optional)
- [ ] Pre-commit hooks: `pip install pre-commit && pre-commit install`

### Tests

- [ ] Run tests: `pytest tests/ -v`
- [ ] Check coverage: `pytest --cov=app --cov-report=html tests/`
- [ ] Expected: >70% coverage on main modules

---

## FRONTEND SETUP (Frontend + QA)

### Node.js

- [ ] Node.js 20+ installed: `node --version`
- [ ] npm 10+ installed: `npm --version`

### Dependencies

- [ ] Install: `cd frontend && npm install`
- [ ] Lock file exists: `package-lock.json` updated
- [ ] Audit vulnerabilities: `npm audit` (should be 0 critical)

### Development Server

- [ ] Start dev server: `npm run dev`
- [ ] Browser opens: http://127.0.0.1:5173
- [ ] Hot reload working (edit a file, see instant refresh)
- [ ] API proxy working: network tab shows `/api` calls going to backend

### Build & Production

- [ ] Build: `npm run build`
- [ ] Check dist folder: `dist/` exists with index.html
- [ ] Size check: `dist/assets/` should be <150KB total (after optimization)

### Linting & Formatting

- [ ] ESLint: `npm run lint` (if available)
- [ ] Prettier: `npm run format` (if available)
- [ ] No errors in terminal

---

## INFRASTRUCTURE SETUP (DevOps)

### Docker

- [ ] docker-compose.yml reviewed
- [ ] All services defined:
  - [ ] `api` (FastAPI)
  - [ ] `postgres` (database)
  - [ ] `redis` (cache + queue)
- [ ] Volumes created (data/, postgres_data/)
- [ ] Networks configured (default or custom)

### Health Checks

- [ ] API health: `curl http://127.0.0.1:8000/api/v1/health`
- [ ] Response: `{"status": "ok"}`
- [ ] Postgres health: `docker-compose exec postgres psql -U postgres -c "SELECT 1"`
- [ ] Redis health: `docker-compose exec redis redis-cli PING`

### Monitoring (Week 3, but verify now)

- [ ] Prometheus (if available): check scrape targets
- [ ] Logs: JSON format enabled in `app/observability.py`
- [ ] Metrics endpoint: `GET /metrics` exists

---

## TEAM COMMUNICATION SETUP

### Slack

- [ ] Channel created: `#sprint-podkapot`
- [ ] All team members added
- [ ] Notification settings: "Mention all" to desktop
- [ ] Pinned message: This SETUP_CHECKLIST.md

### Calendar

- [ ] Daily standup: Monday-Friday 9:00 UTC
  - [ ] Invite: all 5 team members
  - [ ] Duration: 15 minutes
  - [ ] Recurring: Week 1-3

- [ ] Friday demo: 4:00 PM UTC
  - [ ] Invite: all team + product owner + stakeholders
  - [ ] Duration: 15 minutes

- [ ] Friday retro: 4:30 PM UTC
  - [ ] Invite: all team (no stakeholders)
  - [ ] Duration: 30 minutes

### Documentation Sharing

- [ ] All sprint docs in repo (done ✓)
- [ ] Shared metrics spreadsheet created (Week 1 Friday)
- [ ] Daily report template ready (Slack bot or manual)

---

## TEAM ROLES CONFIRMATION

### Backend Developer
- [ ] Name: _______________________
- [ ] Slack: _______________________
- [ ] Email: _______________________
- [ ] Ready for: Week 1 parser work
- [ ] Tools: PyCharm/VSCode, Git, Docker

### Frontend Developer
- [ ] Name: _______________________
- [ ] Slack: _______________________
- [ ] Email: _______________________
- [ ] Ready for: Week 1 layout audit
- [ ] Tools: VSCode, Chrome DevTools, npm

### QA / Test Engineer
- [ ] Name: _______________________
- [ ] Slack: _______________________
- [ ] Email: _______________________
- [ ] Ready for: Fixtures + regression tests
- [ ] Tools: pytest, git, database viewer

### DevOps / Infrastructure
- [ ] Name: _______________________
- [ ] Slack: _______________________
- [ ] Email: _______________________
- [ ] Ready for: Docker, CI/CD, monitoring
- [ ] Tools: Docker, docker-compose, GitHub Actions

### Project Manager
- [ ] Name: _______________________
- [ ] Slack: _______________________
- [ ] Email: _______________________
- [ ] Ready for: Standups, blocking removal, scope
- [ ] Tools: Slack, calendar, spreadsheets

---

## KEY CONTACTS

| Role | Name | Slack | Email | Escalation |
|------|------|-------|-------|-----------|
| Backend Lead | _______ | @______ | ______ | Parser issues |
| Frontend Lead | _______ | @______ | ______ | Layout issues |
| QA Lead | _______ | @______ | ______ | Test failures |
| DevOps | _______ | @______ | ______ | Infra issues |
| PM | _______ | @______ | ______ | Blockers, scope |
| **Emergency** | _______ | **#critical** | ______ | All hands |

---

## FIRST DAY TASKS (Monday June 8)

### 30 min before standup (8:30 AM)

- [ ] Backend: `pytest tests/ -v` all passing locally
- [ ] Frontend: `npm run dev` server running on 5173
- [ ] QA: Database reset, empty inspection tables
- [ ] DevOps: `docker-compose ps` all healthy
- [ ] PM: Timer set for 9:00 AM standup

### During standup (9:00 AM, 15 min)

**Agenda:**
1. Quick intro (2 min)
2. Sprint overview from PM (3 min)
3. Today's tasks per role (5 min)
4. Blockers & questions (5 min)

**Expected decision:** "Go" to start tasks or "Hold" if environment broken

### After standup (9:15 AM+)

Start assigned tasks from DAILY_PRIORITIES.md (Jun 8 section):

**Backend:**
- [ ] Merge parser code
- [ ] Start retry logic
- [ ] Write smoke test

**Frontend:**
- [ ] CSS audit: find all text <14px
- [ ] Create design-system.css (start)
- [ ] Remove emoji from 1 view

**QA:**
- [ ] Setup conftest.py
- [ ] Create user factory
- [ ] Write first API test

**DevOps:**
- [ ] Verify Redis in compose
- [ ] .env.example has webhook_secret
- [ ] Health check endpoint working

**PM:**
- [ ] Send daily metric template to Slack
- [ ] Update DAILY_PRIORITIES.md with any changes
- [ ] Schedule Week 1 retro (Friday 4:30 PM)

---

## DAILY STANDUP CHECKLIST

### Before standup (9:00 AM)

- [ ] I've done something since yesterday standup
- [ ] I know 1 blocker or I'm clear
- [ ] I have 1 concrete task for today
- [ ] I've updated my status in shared doc

### During standup (9:00-9:15 AM)

- [ ] I shared what I did (30 sec)
- [ ] I shared blockers if any (15 sec)
- [ ] I shared today's goal (15 sec)
- [ ] I listened to others (3 min)
- [ ] I flagged cross-team dependencies

### After standup (9:15 AM+)

- [ ] My task is clear
- [ ] I know who to ask if blocked
- [ ] I have coffee/water ready
- [ ] I START WORKING! ⚡

---

## WEEKLY RHYTHM

### Every Monday
- [ ] Sprint kickoff standup (9:00 AM)
- [ ] Review week's goals
- [ ] Confirm no surprises from weekend

### Every Tue-Thu
- [ ] Daily standup (9:00 AM)
- [ ] Quick blocker check
- [ ] Sync if needed

### Every Friday
- [ ] Final standup (9:00 AM)
- [ ] Demo of week's work (4:00 PM)
- [ ] Team retrospective (4:30 PM)
- [ ] Plan next week

---

## RED FLAGS (Escalate immediately)

If you encounter ANY of these, escalate to PM + relevant lead:

- [ ] Parser success rate <80%
- [ ] Bundle size >200KB (gzip)
- [ ] Lighthouse score <70
- [ ] Test flakiness >20%
- [ ] Database migration fails
- [ ] Security vulnerability found
- [ ] 2+ people blocked on same issue
- [ ] Velocity <70% of planned

**Action:** Slack mention @backend-lead OR @frontend-lead + #critical

---

## SUCCESS CHECKLIST (Friday Week 1)

By end of Friday June 14, confirm ALL:

- [ ] Parser retry working (≥95% test success)
- [ ] Layout audit completed (all text ≥14px)
- [ ] Checkbox styled without emoji
- [ ] Placeholder images generating (<100ms)
- [ ] Webhook endpoint accepting POST requests
- [ ] API regression tests 100% pass
- [ ] CI/CD pipeline runs on commits
- [ ] No critical blockers outstanding
- [ ] All code changes reviewed + merged
- [ ] Team morale high (4+/5)

**If any unchecked:** Do NOT proceed to Week 2. Fix first.

---

## SETUP VERIFICATION (Do this now!)

### 5-minute check:

```bash
# Backend
python --version  # 3.11+
pytest --version  # installed
curl http://127.0.0.1:8000/api/v1/health  # 200 OK

# Frontend
node --version  # 20+
npm --version  # 10+
npm run dev  # http://127.0.0.1:5173 loads

# DevOps
docker --version
docker-compose ps  # all healthy

# Communication
# Slack: #sprint-podkapot exists, all members added
# Calendar: Daily standups scheduled
# Docs: All sprint files reviewed
```

**Result:** All checks ✓ → Ready to sprint! 🚀

---

## QUESTIONS BEFORE LAUNCH?

| Question | Answer Source |
|----------|--------|
| What do I do today? | DAILY_PRIORITIES.md (Jun 8 section) |
| How do I implement parser retry? | ARCHITECTURE_DECISIONS.md |
| How do I know if I'm done? | SUCCESS_METRICS.md |
| What if I'm blocked? | RISK_REGISTER.md (escalation) |
| Is this on track? | SPRINT_PLAN.md (weekly checkpoints) |

---

## FINAL SIGN-OFF

Team member confirmation:

| Role | Name | Date | Signature | Ready? |
|------|------|------|-----------|--------|
| Backend | _____________ | _____ | _____ | [ ] YES |
| Frontend | _____________ | _____ | _____ | [ ] YES |
| QA | _____________ | _____ | _____ | [ ] YES |
| DevOps | _____________ | _____ | _____ | [ ] YES |
| PM | _____________ | _____ | _____ | [ ] YES |

**All YES?** → SPRINT STARTS MONDAY 9:00 AM! 🚀

---

## SPRINT STARTS NOW

**Today's date:** June 8, 2026  
**Start time:** 9:00 AM UTC (Monday)  
**Duration:** 3 weeks  
**Goal:** LAUNCH MVP!

Go through this checklist with your team today. Fix any issues. 

**Monday morning:** First standup. Let's go! 🚀
