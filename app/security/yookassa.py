from __future__ import annotations

from ipaddress import ip_address, ip_network

from fastapi import HTTPException, Request

from app.config import settings
from app.security.request_context import get_client_ip


def _parse_allowlist() -> list:
    values = [value.strip() for value in settings.yookassa_webhook_allowlist.split(",")]
    return [ip_network(value) for value in values if value]


def verify_yookassa_source_ip(request: Request) -> str:
    client_ip = get_client_ip(request)
    if client_ip == "unknown" and not settings.is_production:
        return client_ip
    try:
        address = ip_address(client_ip)
    except ValueError as exc:
        if not settings.is_production:
            return client_ip
        raise HTTPException(status_code=403, detail="Webhook source IP is invalid") from exc

    for net in _parse_allowlist():
        if address in net:
            return client_ip

    raise HTTPException(status_code=403, detail="Webhook source is not trusted")
