---
name: animated-ui-designer
description: Designs polished animated interfaces with strong visual hierarchy, smooth transitions, and production-safe motion. Use when building or refining React/Vue UI with emphasis on animation quality.
disable-model-invocation: true
---

# Animated UI Designer

Create visually strong UI with intentional motion, not random effects.

## When to Use

- New marketing pages, dashboards, landing pages
- UI refresh for better perceived quality
- React/Vue components needing transitions and micro-interactions

## Motion Principles

1. Animate purposefully: state change, focus, hierarchy, feedback.
2. Prefer subtle timing: 120-300ms for UI transitions.
3. Use easing that feels natural (`ease-out`, spring only where needed).
4. Keep performance safe (transform/opacity first, avoid layout thrashing).
5. Respect accessibility (`prefers-reduced-motion` fallback).

## Visual Quality Checklist

- Clear typography scale and spacing rhythm
- Strong primary/secondary contrast
- Hover/focus/pressed states for interactive elements
- Loading, empty, and error states are designed
- Mobile responsiveness and keyboard accessibility

## Framework Guidance

- React: use CSS transitions or Motion library for complex choreography.
- Vue: use `<Transition>` / `<TransitionGroup>` with reusable classes.
- Keep animation tokens centralized (duration, easing, delay scale).

## Output Format

- Aesthetic direction (1 short paragraph)
- Component/page structure
- Motion map (what animates and why)
- Implementation notes + accessibility fallback
