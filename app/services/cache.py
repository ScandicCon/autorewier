"""Лёгкий кэш на Redis с мягкой деградацией.

Назначение: не дёргать дорогие внешние сервисы (Autocode, парсинг) повторно за
одни и те же данные. Снижает нагрузку и стоимость при росте числа пользователей.

Поведение:
- Если `REDIS_URL` не задан — кэш выключен: get отдаёт None, set ничего не делает.
- Любая ошибка Redis не ломает основной поток (логируется, возвращается None).
"""

import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger("autorewier.cache")


def cache_enabled() -> bool:
    return bool((settings.redis_url or "").strip())


async def _client():
    import redis.asyncio as redis

    return redis.from_url(settings.redis_url, decode_responses=True)


async def cache_get_json(key: str) -> Any | None:
    """Возвращает закэшированное значение (dict/list) или None."""
    if not cache_enabled():
        return None
    client = None
    try:
        client = await _client()
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — кэш не должен ронять основной поток
        logger.warning("cache_get_failed key=%s err=%s", key, exc)
        return None
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    """Сохраняет значение в кэш с TTL. Тихо игнорирует ошибки."""
    if not cache_enabled():
        return
    client = None
    try:
        client = await _client()
        await client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache_set_failed key=%s err=%s", key, exc)
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass
