from __future__ import annotations

import logging
from typing import Any

from app.services.task_queue import enqueue_task

logger = logging.getLogger("autorewier.analytics")


async def track_event(
    event_name: str,
    *,
    user_id: int | None = None,
    props: dict[str, Any] | None = None,
) -> None:
    payload = {"event": event_name, "user_id": user_id, "props": props or {}}
    queued = await enqueue_task("analytics_event", payload)
    if not queued:
        logger.info("analytics_event_fallback", extra={"event": event_name, "user_id": user_id})
