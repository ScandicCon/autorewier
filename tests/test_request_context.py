from __future__ import annotations

from starlette.requests import Request

from app.security.request_context import get_client_ip


def _request(remote: str, xff: str | None = None) -> Request:
    headers = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (remote, 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
    }
    return Request(scope)


def test_ignores_forwarded_for_without_trusted_proxy(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8")
    request = _request("203.0.113.9", "198.51.100.20, 10.1.1.3")
    assert get_client_ip(request) == "203.0.113.9"


def test_uses_rightmost_forwarded_ip_with_hop_depth_one(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8")
    request = _request("10.1.1.3", "198.51.100.20, 10.1.1.3")
    assert get_client_ip(request) == "10.1.1.3"


def test_uses_hops_offset_for_multi_proxy_chain(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8,192.168.0.0/16")
    request = _request("192.168.10.5", "198.51.100.20, 10.1.1.3, 192.168.10.5")
    assert get_client_ip(request) == "10.1.1.3"


def test_falls_back_to_remote_when_header_chain_too_short(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8")
    request = _request("10.1.1.3", "198.51.100.20")
    assert get_client_ip(request) == "10.1.1.3"
