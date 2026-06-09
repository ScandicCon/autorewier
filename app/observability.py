from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.config import settings

REQUEST_COUNT = Counter(
    "autorewier_http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"],
)
REQUEST_DURATION = Histogram(
    "autorewier_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "route"],
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        for key in ("method", "route", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    if not settings.json_logs:
        return
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(JsonFormatter())
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def install_observability(app: FastAPI) -> None:
    logger = logging.getLogger("autorewier.http")

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.perf_counter()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        route = request.url.path

        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            route_tpl = (
                request.scope.get("route").path
                if request.scope.get("route") and hasattr(request.scope.get("route"), "path")
                else route
            )
            REQUEST_COUNT.labels(
                method=request.method,
                route=route_tpl,
                status=str(status_code),
            ).inc()
            REQUEST_DURATION.labels(method=request.method, route=route_tpl).observe(elapsed)

            logger.info(
                "request_handled",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": route_tpl,
                    "status_code": status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )
            if response is not None:
                response.headers["X-Request-Id"] = request_id

    if settings.metrics_enabled:

        @app.get(settings.metrics_path, include_in_schema=False)
        async def metrics() -> Response:
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
