from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.services.task_queue import enqueue_task

logger = logging.getLogger("autorewier.analytics")


async def _send_to_posthog(event_name: str, user_id: int | None, props: dict[str, Any]) -> None:
    """Отправляет событие в PostHog (capture API). Без ключа — ничего не делает."""
    api_key = settings.posthog_api_key.strip()
    if not api_key:
        return
    host = settings.posthog_host.strip().rstrip("/") or "https://eu.i.posthog.com"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{host}/capture/",
                json={
                    "api_key": api_key,
                    "event": event_name,
                    "distinct_id": f"user_{user_id}" if user_id else "anonymous",
                    "properties": {**props, "source": "backend"},
                },
            )
    except Exception:
        # аналитика не должна влиять на основной поток
        pass


async def track_event(
    event_name: str,
    *,
    user_id: int | None = None,
    props: dict[str, Any] | None = None,
) -> None:
    props = props or {}
    await _send_to_posthog(event_name, user_id, props)
    payload = {"event": event_name, "user_id": user_id, "props": props}
    queued = await enqueue_task("analytics_event", payload)
    if not queued:
        logger.info("analytics_event_fallback", extra={"event": event_name, "user_id": user_id})
