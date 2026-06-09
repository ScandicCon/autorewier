---
name: sqlalchemy-orm-expert
description: Use when designing or optimizing SQLAlchemy 2.x ORM models, sessions, async queries, relationships, eager loading, and PostgreSQL-backed FastAPI integrations.
---

# SQLAlchemy ORM Expert

Practical guidance for SQLAlchemy 2.x ORM in production services.

## When to Use This Skill

- Creating or updating SQLAlchemy models and relationships
- Implementing async repository/data-access logic
- Fixing N+1 queries and slow ORM operations
- Designing session/transaction boundaries
- Preparing migrations and query-safe refactors

## Core Workflow

1. Map domain objects and relationship cardinality first.
2. Implement typed SQLAlchemy 2.x models with `Mapped[...]` and `mapped_column`.
3. Define session lifecycle per request/task; keep transactions explicit.
4. Build queries with `select(...)`; add eager loading where needed.
5. Validate performance with realistic data paths and indexing assumptions.
6. Add tests for CRUD, relationship integrity, and rollback behavior.

## ORM Guardrails

- Use `selectinload`/`joinedload` deliberately to avoid N+1.
- Keep transactions short; avoid long-lived sessions.
- Prefer explicit columns/filters; avoid accidental full-table scans.
- Handle integrity errors and map them to domain/API errors.
- Keep model constraints (unique, FK, indexes) aligned with app rules.

## Async + FastAPI Notes

- Use `AsyncSession` dependencies at request scope.
- Do not mix sync engine/session with async endpoints.
- Separate read-model queries from write flows when complexity grows.
