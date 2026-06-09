from __future__ import annotations

from ipaddress import ip_address, ip_network

from fastapi import Request

from app.config import settings


def _parse_ip(value: str | None):
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.startswith("[") and "]" in raw:
        raw = raw.split("]", 1)[0][1:]
    elif ":" in raw and raw.count(":") == 1:
        host, maybe_port = raw.rsplit(":", 1)
        if maybe_port.isdigit():
            raw = host
    try:
        return ip_address(raw)
    except ValueError:
        return None


def _trusted_proxy_networks() -> list:
    values = [value.strip() for value in settings.trusted_proxy_cidrs.split(",") if value.strip()]
    networks = []
    for value in values:
        try:
            networks.append(ip_network(value))
        except ValueError:
            continue
    return networks


def _is_trusted_proxy(client_ip) -> bool:
    networks = _trusted_proxy_networks()
    if client_ip is None:
        # Backward compatibility: in some test/proxy setups remote addr is unavailable.
        return not networks
    if networks:
        return any(client_ip in net for net in networks)
    return bool(client_ip.is_private or client_ip.is_loopback or client_ip.is_link_local)


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    client = _parse_ip(request.client.host if request.client else None)

    hops = max(0, settings.trusted_proxy_hops)
    if forwarded_for and hops > 0 and _is_trusted_proxy(client):
        chain = [_parse_ip(part.strip()) for part in forwarded_for.split(",")]
        chain = [addr for addr in chain if addr is not None]
        if len(chain) >= hops:
            # trusted_proxy_hops picks from the right side: 1 => rightmost, 2 => second rightmost.
            return str(chain[len(chain) - hops])

    return str(client) if client is not None else "unknown"
