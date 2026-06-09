---
name: fastapi-expert
description: Use when building high-performance async Python APIs with FastAPI and Pydantic v2, including endpoints, dependency injection, JWT auth, async SQLAlchemy, and OpenAPI docs.
---

# FastAPI Expert

Deep expertise in async Python, Pydantic v2, and production-grade API development with FastAPI.

## When to Use This Skill

- Building or refactoring REST APIs with FastAPI
- Implementing Pydantic v2 request/response schemas
- Adding async SQLAlchemy data access
- Implementing JWT authentication/authorization
- Designing dependencies and middleware
- Improving performance and API reliability

## Core Workflow

1. Clarify API contract: routes, payloads, auth requirements, and error model.
2. Define/adjust Pydantic v2 schemas first (`field_validator`, `model_validator`).
3. Implement async route handlers and dependency injection with `Annotated`.
4. Add persistence logic with async SQLAlchemy sessions and typed queries.
5. Add auth checks (JWT/OAuth2 flow) and explicit permission boundaries.
6. Verify by running tests and checking generated docs at `/docs`.

## Standards

- Prefer `X | None` over `Optional[X]`.
- Keep handlers thin; move logic to service/repository layers.
- Return explicit status codes and structured error responses.
- Never block event loop with sync DB/network calls.
- Do not expose secrets or internal fields in response models.

## Output Format

When implementing, provide:
1) schema updates, 2) router updates, 3) DB/service changes, 4) short verification checklist.
