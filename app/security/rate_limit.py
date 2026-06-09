from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import settings
from app.security.request_context import get_client_ip


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds

        async with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


_memory_limiter = InMemoryRateLimiter()


async def enforce_rate_limit(
    request: Request,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
    identity: str | None = None,
) -> None:
    if not settings.rate_limit_enabled:
        return

    actor = identity or get_client_ip(request)
    key = f"{scope}:{actor}"
    allowed = await _memory_limiter.allow(key, limit=limit, window_seconds=window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests for {scope}, retry later.",
        )
