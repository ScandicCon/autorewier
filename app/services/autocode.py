import asyncio
import base64
import hashlib
import time
from typing import Any

import httpx

from app.config import settings
from app.services.cache import cache_get_json, cache_set_json

# История по VIN меняется медленно — кэшируем готовый отчёт на 7 дней.
VIN_CACHE_TTL_SECONDS = 7 * 24 * 3600


def _make_auth_token() -> str:
    """Токен AR-REST по документации Autocode."""
    stamp = int(time.time())
    age = 999999999
    pass_hash = hashlib.md5(settings.autocode_password.encode()).hexdigest()
    salted = hashlib.sha256(
        f"{pass_hash}:{stamp}:{age}:{settings.autocode_user}".encode()
    ).digest()
    salted_b64 = base64.b64encode(salted).decode()
    raw = f"{settings.autocode_user}@{settings.autocode_domain}:{stamp}:{age}:{salted_b64}"
    token = base64.b64encode(raw.encode()).decode()
    return f"AR-REST {token}"


def _headers() -> dict[str, str]:
    return {
        "Authorization": _make_auth_token(),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def request_vin_report(vin: str) -> dict[str, Any]:
    if not settings.autocode_enabled:
        if settings.can_use_mock_services:
            return _mock_vin_report(vin)
        raise RuntimeError("Autocode is not configured")

    # Кэш: один и тот же VIN не оплачиваем у Autocode повторно в течение TTL.
    cache_key = f"vin:report:{vin.upper().strip()}"
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return cached

    uid = settings.autocode_report_type_uid
    if "@" not in uid:
        uid = f"{uid}@{settings.autocode_domain}"

    base = settings.autocode_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        make_resp = await client.post(
            f"{base}/user/reports/{uid}/_make",
            headers=_headers(),
            json={"queryType": "VIN", "query": vin.upper()},
        )
        make_resp.raise_for_status()
        make_data = make_resp.json()
        report_uid = (
            make_data.get("uid")
            or make_data.get("data", [{}])[0].get("uid")
            or (make_data.get("data") or {}).get("uid")
        )
        if not report_uid:
            report_uid = make_data.get("report_uid")

        if not report_uid:
            raise RuntimeError("Autocode не вернул uid отчёта")

        for _ in range(20):
            await asyncio.sleep(2)
            get_resp = await client.get(
                f"{base}/user/reports/{report_uid}",
                headers=_headers(),
            )
            get_resp.raise_for_status()
            report = get_resp.json()
            state = (
                report.get("state", {}).get("state")
                or report.get("data", {}).get("state")
                or report.get("progress_wait")
            )
            content = report.get("content") or report.get("data", {}).get("content")
            if content or state in ("ok", "success", None):
                result = {
                    "report_uid": report_uid,
                    "vin": vin.upper(),
                    "raw": report,
                    "summary": _extract_summary(report),
                }
                # Кэшируем только готовый отчёт (с контентом), демо/пустое не кэшируем.
                if content:
                    await cache_set_json(cache_key, result, VIN_CACHE_TTL_SECONDS)
                return result

    raise TimeoutError("Отчёт Autocode не готов за отведённое время")


def _extract_summary(report: dict) -> str:
    parts: list[str] = []
    content = report.get("content") or report.get("data") or report
    if isinstance(content, dict):
        tech = content.get("tech_data") or {}
        brand = (tech.get("brand") or {}).get("name", {}).get("normalized")
        model = (tech.get("model") or {}).get("name", {}).get("normalized")
        year = tech.get("year")
        if brand or model:
            parts.append(f"{' '.join(filter(None, [brand, model]))}")
        if year:
            parts.append(f"год {year}")
        owners = content.get("ownership") or content.get("owners")
        if owners:
            parts.append("есть данные по владельцам")
        restrictions = content.get("restrictions") or content.get("pledges")
        if restrictions:
            parts.append("проверьте ограничения/залоги в полном отчёте")
    if not parts:
        return "Отчёт получен — откройте детали в кабинете"
    return ". ".join(parts) + "."


def _mock_vin_report(vin: str) -> dict[str, Any]:
    return {
        "report_uid": f"demo-{vin[:8]}",
        "vin": vin.upper(),
        "raw": {
            "demo": True,
            "message": "Укажите AUTOCODE_* в .env для реальных отчётов",
        },
        "summary": (
            f"VIN {vin.upper()}: демо-режим. "
            "Подключите Autocode B2B API для истории, ДТП, залогов и ограничений."
        ),
    }
# end of autocode service
