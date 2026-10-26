"""FastAPI application factory."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import Status, StatusCode
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from .config import Settings, get_settings
from .db import make_engine, make_session_factory, run_migrations
from .flags import Flags
from .metrics import render_metrics
from .models import Base
from .routers import admin, auth, members, plan, recipes, shopping
from .security import RateLimiter
from .seed.loader import load_ingredients
from .seeding import ensure_probe, seed_recipes
from .telemetry import current_trace_ids, setup_logging, setup_tracing

log = logging.getLogger("pantry.http")
_telemetry_ready = False
SESSION_MAX_AGE = 14 * 24 * 3600


def create_app(settings: Settings | None = None) -> FastAPI:
    global _telemetry_ready
    settings = settings or get_settings()
    if not _telemetry_ready:
        setup_logging()
        setup_tracing(settings.service_name, settings.otlp_endpoint, settings.environment)
        _telemetry_ready = True

    engine = make_engine(settings.database_url)
    if settings.run_migrations:
        run_migrations(engine)
    else:
        Base.metadata.create_all(engine)
    factory = make_session_factory(engine)

    flags = Flags(factory)
    flags.ensure_defaults()
    with factory() as session:
        seed_recipes(session)
    ensure_probe(factory, settings)

    app = FastAPI(title="Pantry Plan", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = factory
    app.state.flags = flags
    app.state.limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.global_ingredients = load_ingredients()

    @app.middleware("http")
    async def observe(request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:  # unhandled error: log with trace ids, mark the span, answer 500
            span = trace.get_current_span()
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            log.exception("unhandled error", extra={"path": request.url.path, "method": request.method})
            response = JSONResponse({"detail": "Internal server error"}, status_code=500)
        trace_id, _ = current_trace_ids()
        if trace_id:
            response.headers["X-Trace-Id"] = trace_id
        path = request.url.path
        if path.startswith("/api") or path.startswith("/admin"):
            route = request.scope.get("route")
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "route": getattr(route, "path", path),
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
        return response

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        max_age=SESSION_MAX_AGE,
        same_site="lax",
        https_only=settings.cookie_secure,
        session_cookie="pantry_session",
    )

    for router in (auth.router, members.router, recipes.router, plan.router, shopping.router, admin.router):
        app.include_router(router)

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok", "version": settings.app_version}

    @app.get("/ready", include_in_schema=False)
    def ready():
        with factory() as s:
            s.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request):
        body, content_type = render_metrics("openmetrics" in request.headers.get("accept", ""))
        return Response(body, media_type=content_type)

    _mount_frontend(app, settings.static_dir)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,ready,metrics")
    return app


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve the built React app (single image, single origin). No-op when the build is absent."""
    index = static_dir / "index.html"
    if not index.is_file():
        return
    if (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "admin/")) or path in {"api", "admin"}:
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


def app_factory() -> FastAPI:  # for `uvicorn app.main:app_factory --factory`
    return create_app()
