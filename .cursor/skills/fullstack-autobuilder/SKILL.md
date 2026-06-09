---
name: fullstack-autobuilder
description: Implements end-to-end fullstack changes across backend, frontend/templates, and supporting services with balanced safety checks. Use when the user asks to add or modify features that touch APIs, business logic, UI/pages, schemas, data flow, or integration behavior.
---

# Fullstack Autobuilder

## Mission

Deliver production-usable fullstack changes quickly with balanced rigor:
- implement code end-to-end
- keep behavior coherent across layers
- run fast verification where available
- report concise outcomes and risks

## When To Apply

Apply this skill when requests include one or more of:
- "add feature", "implement", "wire up", "integrate"
- API plus UI/template changes
- schema/model changes affecting handlers/pages
- backend logic updates with visible product behavior changes

Do not apply this skill for pure brainstorming; use only when implementation is expected.

## Execution Style (Balanced)

1. Understand target behavior and likely touchpoints.
2. Make minimal, coherent edits across impacted layers.
3. Prefer existing project patterns over introducing new abstractions.
4. Add concise comments only for non-obvious logic.
5. Validate with quick checks (tests/lint/smoke) if available.
6. Return what changed, what was verified, and any residual risk.

## Fullstack Workflow

Copy and track this checklist during execution:

```text
Task Progress:
- [ ] Confirm expected user-visible behavior
- [ ] Locate backend and UI integration points
- [ ] Implement backend/domain changes
- [ ] Implement API/handler and serialization changes
- [ ] Implement UI/template changes
- [ ] Update tests or add focused coverage when practical
- [ ] Run fast verification commands
- [ ] Summarize changes and risks
```

## Layer Checklist

### Backend/domain
- Keep business logic in services/domain modules.
- Validate inputs and preserve error semantics.
- Reuse existing config/dependency patterns.

### API/transport
- Keep request/response contracts consistent.
- Update schemas and dependent callers together.
- Avoid silent contract breaks.

### UI/templates
- Reflect new states and errors explicitly.
- Keep naming and structure consistent with existing pages/components.
- Ensure backend payload assumptions match rendered fields.

### Data/models
- Update model, schema, and usage points in one pass.
- Preserve compatibility where possible; if not, note migration impact.

## Verification Rules

Run the fastest relevant checks first:
1. Targeted tests for changed modules.
2. Project lint/type checks if cheap.
3. Focused smoke path for the new/changed feature.

If checks cannot run, state exactly what was not run and why.

## Output Contract

Respond with:
1. What changed end-to-end (grouped by layer).
2. Commands/checks executed and key results.
3. Remaining risks, assumptions, or follow-up work.

Keep it concise and implementation-focused.

## Additional Resources

- Usage examples: [examples.md](examples.md)
