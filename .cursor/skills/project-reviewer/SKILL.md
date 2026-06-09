---
name: project-reviewer
description: Reviews FastAPI, SQLAlchemy, and Playwright changes for bugs, regressions, security issues, and missing tests. Use when analyzing diffs, PRs, incidents, or CI failures in this project.
disable-model-invocation: true
---

# Project Reviewer

Use this skill for focused technical review in this repository.

## Scope

- Backend API behavior (FastAPI handlers, auth, validation, errors)
- Data layer correctness and performance (SQLAlchemy models and queries)
- E2E reliability (Playwright selectors, waits, assertions, flake risks)
- Risk assessment for regressions and production impact

## Review Workflow

1. Read changed files and identify user-visible behavior changes.
2. Prioritize correctness and security over style.
3. Look for broken contracts, missing validation, and unsafe assumptions.
4. Check data consistency: transactions, constraints, query load patterns.
5. Check test gaps and propose concrete additions.

## Output Format

- Critical: must-fix issues with impact and fix direction
- High: likely bugs or strong regression risks
- Medium: maintainability or reliability concerns
- Test gaps: missing test cases that should be added

For each finding include:
- where it occurs,
- why it is risky,
- how to fix it succinctly.
