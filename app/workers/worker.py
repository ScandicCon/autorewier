from __future__ import annotations

import asyncio
import json
import logging
import time

from app.config import settings
from app.database import async_session
from app.services.inspections import run_vin_check
from app.services.task_queue import set_task_status

logger = logging.getLogger("autorewier.worker")


async def _handle_vin_check(payload: dict) -> dict:
    user_id = int(payload["user_id"])
    vin = str(payload["vin"])
    inspection_id = payload.get("inspection_id")
    if inspection_id is not None:
        inspection_id = int(inspection_id)
    async with async_session() as session:
        check = await run_vin_check(session, user_id, vin, inspection_id)
    return {
        "vin_check_id": check.id,
        "vin": check.vin,
        "report_uid": check.report_uid,
        "summary": check.summary,
        "created_at": check.created_at.isoformat(),
        "inspection_id": check.inspection_id,
    }


async def run_worker() -> None:
    if not settings.redis_url.strip():
        raise RuntimeError("REDIS_URL is required for worker mode")

    import redis.asyncio as redis

    client = redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("worker_started")
    try:
        while True:
            item = await client.brpop(settings.task_queue_name, timeout=5)
            if not item:
                continue

            _, raw = item
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("worker_invalid_payload")
                continue

            task_id = str(body.get("task_id") or "")
            task_name = body.get("task")
            payload = body.get("payload") or {}
            if task_id:
                await set_task_status(task_id, "running")
            try:
                if task_name == "analytics_event":
                    logger.info("analytics_event_processed", extra={"event": payload.get("event")})
                    if task_id:
                        await set_task_status(task_id, "succeeded", result={"ok": True})
                elif task_name == "vin_check":
                    result = await _handle_vin_check(payload)
                    logger.info("vin_check_processed", extra={"task_id": task_id, "vin": result["vin"]})
                    if task_id:
                        await set_task_status(task_id, "succeeded", result=result)
                else:
                    logger.warning("worker_unknown_task", extra={"task": task_name})
                    if task_id:
                        await set_task_status(task_id, "failed", error=f"unknown_task:{task_name}")
            except Exception as exc:
                logger.exception("worker_task_failed", extra={"task": task_name, "task_id": task_id})
                if task_id:
                    await set_task_status(task_id, "failed", error=str(exc))
    finally:
        await client.aclose()


async def run_monitoring_scheduler() -> None:
    """Periodically runs listing monitoring cycle (once per hour by default)."""
    from app.services.listing_monitor import run_monitoring_cycle

    interval = max(60, settings.monitoring_cycle_interval_seconds)
    logger.info("monitoring_scheduler_started", extra={"interval_sec": interval})

    while True:
        try:
            await run_monitoring_cycle()
        except Exception:
            logger.exception("monitoring_scheduler_cycle_error")
        await asyncio.sleep(interval)


async def run_all() -> None:
    """Run task queue worker and monitoring scheduler concurrently."""
    await asyncio.gather(
        run_worker(),
        run_monitoring_scheduler(),
        return_exceptions=False,
    )


async def run_standalone_scheduler() -> None:
    """Run only the monitoring scheduler (no Redis required)."""
    await run_monitoring_scheduler()


def main() -> None:
    asyncio.run(run_worker())


def main_scheduler() -> None:
    """Entry point: run only the monitoring scheduler."""
    asyncio.run(run_standalone_scheduler())


if __name__ == "__main__":
    main()
