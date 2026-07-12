"""Одноразовые коды обмена для OAuth-редиректа.

Зачем: раньше `oauth_callback` возвращал JWT прямо в query-строке
(`?token=...`). Такой токен утекает в историю браузера, логи прокси и заголовок
Referer (см. security-ревью 2026-07-10, находка #2). Вместо этого callback
кладёт JWT в короткоживущее серверное хранилище и отдаёт фронту одноразовый
`code`. Фронт меняет `code` на JWT одним POST-запросом (тело ответа, не URL).

Хранилище: Redis, если задан `REDIS_URL` (переживает несколько реплик), иначе
in-memory с TTL — согласуется с тем, что rate limiter в проекте тоже in-memory
при одном инстансе. Код одноразовый: при обмене удаляется.
"""
from __future__ import annotations

import secrets
import time

from app.services.cache import cache_enabled

# TTL кода: пользователь меняет его сразу после редиректа, держать долго незачем.
_CODE_TTL_SECONDS = 120
_KEY_PREFIX = "oauth_exchange:"

# Fallback-хранилище на случай, когда Redis не настроен.
# {code: (payload_dict, expires_at_monotonic)}
_memory_store: dict[str, tuple[dict, float]] = {}


def _prune_memory(now: float) -> None:
    expired = [c for c, (_, exp) in _memory_store.items() if exp <= now]
    for c in expired:
        _memory_store.pop(c, None)


async def _redis_client():
    from app.services.cache import _client  # локальный импорт: Redis опционален

    return await _client()


async def issue_exchange_code(*, token: str, user_id: int, email: str | None) -> str:
    """Сохраняет сессионные данные под одноразовым кодом, возвращает код."""
    code = secrets.token_urlsafe(24)
    payload = {"token": token, "uid": user_id, "email": email}

    if cache_enabled():
        client = None
        try:
            import json

            client = await _redis_client()
            await client.set(
                _KEY_PREFIX + code,
                json.dumps(payload, ensure_ascii=False),
                ex=_CODE_TTL_SECONDS,
            )
            return code
        except Exception:  # noqa: BLE001 — деградируем в in-memory
            pass
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception:  # noqa: BLE001
                    pass

    now = time.monotonic()
    _prune_memory(now)
    _memory_store[code] = (payload, now + _CODE_TTL_SECONDS)
    return code


async def redeem_exchange_code(code: str) -> dict | None:
    """Возвращает сохранённые данные по коду и удаляет код (одноразовость)."""
    if not code:
        return None

    if cache_enabled():
        client = None
        try:
            import json

            client = await _redis_client()
            key = _KEY_PREFIX + code
            raw = await client.get(key)
            await client.delete(key)
            if raw:
                return json.loads(raw)
        except Exception:  # noqa: BLE001
            pass
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception:  # noqa: BLE001
                    pass
        # Redis включён, но кода там нет — не проваливаемся в чужой in-memory.
        # Тем не менее проверим локальный стор ниже на случай смешанного режима.

    now = time.monotonic()
    _prune_memory(now)
    entry = _memory_store.pop(code, None)
    if entry is None:
        return None
    payload, exp = entry
    if exp <= now:
        return None
    return payload
