from __future__ import annotations

import json
import logging
from datetime import datetime, timezone as _tz
UTC = _tz.utc
from typing import Any
from uuid import uuid4

from app.config import settings

logger = logging.getLogger("autorewier.queue")
_TASK_STATUS_TTL_SECONDS = 24 * 3600


def _task_status_key(task_id: str) -> str:
    return f"{settings.task_queue_name}:status:{task_id}"


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _queue_ready() -> bool:
    return bool(settings.task_queue_enabled and settings.redis_url.strip())


async def _get_redis_client():
    import redis.asyncio as redis

    return redis.from_url(settings.redis_url, decode_responses=True)


async def enqueue_task(task_name: str, payload: dict[str, Any]) -> bool:
    if not _queue_ready():
        return False

    try:
        task_id = await enqueue_tracked_task(task_name, payload)
        return bool(task_id)
    except Exception:
        logger.warning("redis_client_unavailable")
        return False


async def enqueue_tracked_task(
    task_name: str,
    payload: dict[str, Any],
    *,
    owner_id: int | None = None,
) -> str | None:
    if not _queue_ready():
        return None

    task_id = uuid4().hex
    now = _now_iso()
    body = {"task_id": task_id, "task": task_name, "payload": payload}
    status_mapping = {
        "task_id": task_id,
        "task": task_name,
        "status": "queued",
        "owner_id": str(owner_id) if owner_id is not None else "",
        "created_at": now,
        "updated_at": now,
        "result": "",
        "error": "",
    }
    client = await _get_redis_client()
    try:
        key = _task_status_key(task_id)
        await client.hset(key, mapping=status_mapping)
        await client.expire(key, _TASK_STATUS_TTL_SECONDS)
        await client.lpush(settings.task_queue_name, json.dumps(body, ensure_ascii=False))
        return task_id
    except Exception:
        logger.exception("queue_enqueue_failed")
        return None
    finally:
        await client.aclose()


async def set_task_status(
    task_id: str,
    status: str,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    if not _queue_ready() or not task_id:
        return
    client = await _get_redis_client()
    key = _task_status_key(task_id)
    try:
        mapping = {
            "status": status,
            "updated_at": _now_iso(),
        }
        if result is not None:
            mapping["result"] = json.dumps(result, ensure_ascii=False)
            mapping["error"] = ""
        if error:
            mapping["error"] = error
            mapping["result"] = ""
        await client.hset(key, mapping=mapping)
        await client.expire(key, _TASK_STATUS_TTL_SECONDS)
    except Exception:
        logger.exception("queue_status_update_failed", extra={"task_id": task_id, "status": status})
    finally:
        await client.aclose()


async def get_task_status(task_id: str) -> dict[str, Any] | None:
    if not _queue_ready() or not task_id:
        return None
    client = await _get_redis_client()
    try:
        raw = await client.hgetall(_task_status_key(task_id))
        if not raw:
            return None
        owner_id: int | None = None
        if raw.get("owner_id"):
            try:
                owner_id = int(raw["owner_id"])
            except ValueError:
                owner_id = None
        parsed_result: dict[str, Any] | None = None
        if raw.get("result"):
            try:
                parsed_result = json.loads(raw["result"])
            except json.JSONDecodeError:
                parsed_result = {"raw": raw["result"]}
        return {
            "task_id": raw.get("task_id", task_id),
            "task": raw.get("task", ""),
            "status": raw.get("status", "unknown"),
            "owner_id": owner_id,
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("updated_at"),
            "result": parsed_result,
            "error": raw.get("error") or None,
        }
    finally:
        await client.aclose()


async def get_queue_depth() -> int | None:
    if not _queue_ready():
        return None
    client = await _get_redis_client()
    try:
        return int(await client.llen(settings.task_queue_name))
    except Exception:
        logger.exception("queue_depth_failed")
        return None
    finally:
        await client.aclose()
