"""FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.api.routes import health

logger = get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    application = FastAPI(
        title="Bulk Certificate Generator",
        description="Generate PDF certificates in bulk via an async Celery pipeline.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Global exception handlers ────────────────────────────────────────────
    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app_error | status=%d | code=%s | message=%s",
            exc.http_status,
            exc.error_code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error | %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error_code": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
        )

    # ── Routers ──────────────────────────────────────────────────────────────
    application.include_router(health.router, prefix="/health", tags=["Health"])

    logger.info(
        "app_startup | max_recipients=%d | batch_size=%d | storage=%s",
        settings.max_recipients_per_job,
        settings.batch_size,
        settings.storage_root,
    )

    return application


app = create_app()
