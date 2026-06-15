from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin_routes import router as admin_router, support_router
from app.api.auth_routes import router as auth_router
from app.api.payment_routes import router as payment_router
from app.api.routes import router as api_router
from app.config import BASE_DIR, settings
from app.database import init_db
from app.observability import configure_logging, install_observability

WEB_STATIC = BASE_DIR / "web" / "static"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    issues = settings.production_hardening_issues
    if issues:
        raise RuntimeError(
            "Production hardening checks failed: " + "; ".join(issues)
        )
    await init_db()
    yield
    try:
        from app.services.parsers.avito_fetch import shutdown_avito_browser

        await shutdown_avito_browser()
    except Exception:
        pass


# Sentry — мониторинг ошибок. Включается только при заданном SENTRY_DSN;
# без него ничего не импортируется и не инициализируется (мягкая деградация).
if settings.sentry_dsn.strip():
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn.strip(),
            environment=settings.environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,
            release=getattr(settings, "app_version", None) or None,
        )
    except Exception:
        pass


app = FastAPI(
    title="AutoRewier",
    description="Proверка автомобиля перед покупкой и перепродажей",
    version="0.2.0",
    lifespan=lifespan,
)
configure_logging()
install_observability(app)

_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    settings.web_base_url,
]
# CORS_EXTRA_ORIGINS comma-separated: e.g. https://autorewier.vercel.app
if settings.cors_extra_origins.strip():
    for _o in settings.cors_extra_origins.split(","):
        _o = _o.strip().rstrip("/")
        if _o and _o not in _cors_origins:
            _cors_origins.append(_o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if WEB_STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_STATIC)), name="static")

if FRONTEND_DIST.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="vue_frontend")

app.include_router(api_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(payment_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(support_router, prefix="/api/v1")
if settings.enable_server_rendered_web:
    from app.api.web_routes import router as web_router

    app.include_router(web_router)


@app.get("/", include_in_schema=False)
async def root_redirect():
    if FRONTEND_DIST.exists():
        return RedirectResponse(url="/app")
    return {"status": "ok", "service": "autorewier"}


@app.get("/app/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Catch-all for Vue Router history mode."""
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return RedirectResponse(url="/app")


def run_api():
    import os
    import uvicorn

    # Railway sets PORT; fall back to settings.api_port (default 8000)
    port = int(os.environ.get("PORT", settings.api_port))
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=port,
        reload=False,
    )
