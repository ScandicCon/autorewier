# Subagent Launch Templates

## 1) Code review subagent

Use this in chat:

```text
Запусти subagent типа generalPurpose.
Use skill project-reviewer, fastapi-expert, sqlalchemy-orm-expert.
Задача: проверь изменения и найди баги/регрессии/риски безопасности.
Верни отчет: Critical, High, Medium, Test gaps.
```

## 2) Backend implementation subagent

Use this in chat:

```text
Запусти subagent типа generalPurpose.
Use skill fastapi-expert and sqlalchemy-orm-expert.
Задача: реализовать <описание фичи> в FastAPI + SQLAlchemy.
Условия: не ломать API-контракт, добавить/обновить тесты.
```

## 3) Test automation subagent

Use this in chat:

```text
Запусти subagent типа generalPurpose.
Use skill playwright-cursor-rules.
Задача: написать/починить Playwright e2e для <сценарий>.
Условия: стабильные локаторы, без waitForTimeout, с понятными assertions.
```

## 4) Frontend subagent (React or Vue)

Use this in chat:

```text
Запусти subagent типа generalPurpose.
Use skill frontend-design.
Задача: реализовать фронтенд для <страница/фича> на React или Vue.
Условия: адаптивность, доступность, аккуратные состояния загрузки/ошибки, чистая структура компонентов.
```

## 5) Fullstack split with subagents

Use this in chat:

```text
Сделай фичу end-to-end и раздели работу между subagent-ами.
Backend subagent: use skills fastapi-expert, sqlalchemy-orm-expert.
Frontend subagent: use skill frontend-design (React/Vue).
Testing subagent: use skill playwright-cursor-rules.
Потом собери итог, проверь риски регрессии и покажи что изменилось.
```

## 6) Planner subagent

Use this in chat:

```text
Запусти subagent типа generalPurpose.
Use skill subagent-planner.
Задача: разложи фичу на backend/frontend/tests, выдели параллельные ветки, зависимости и чекпоинты.
Верни план + порядок выполнения + критерии готовности по каждому блоку.
```

## 7) Animated frontend subagent

Use this in chat:

```text
Запусти subagent типа generalPurpose.
Use skills frontend-design, animated-ui-designer.
Задача: сделать красивый анимированный интерфейс для <страница/фича> на React или Vue.
Условия: плавные переходы, доступность (prefers-reduced-motion), адаптивность, аккуратные состояния loading/error/empty.
```
