---
name: subagent-planner
description: Plans multi-step work and delegates tasks across subagents with clear sequencing, dependencies, and checkpoints. Use when a request is large, cross-functional, or needs backend/frontend/test parallelization.
disable-model-invocation: true
---

# Subagent Planner

Use this skill to split complex work into executable chunks for subagents.

## When to Use

- End-to-end features across backend, frontend, and tests
- Requests with unclear scope or many dependencies
- Cases where parallel subagents can reduce delivery time

## Planning Rules

1. Define the user-visible outcome in one sentence.
2. Split into tracks: backend, frontend, tests, integration.
3. Mark dependencies between tracks (`blocked_by`).
4. Run independent tracks in parallel.
5. Add checkpoints after each track with quick validation.
6. Finish with synthesis: changed files, risks, next actions.

## Delegation Template

For each subagent task, specify:
- goal
- required skills
- inputs
- expected output
- done criteria

## Output Format

- Plan
- Parallel tasks
- Dependency notes
- Verification checklist
- Final merge/synthesis checklist
