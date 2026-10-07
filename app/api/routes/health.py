"""Liveness and readiness health checks."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("", summary="Health status")
async def health_check() -> JSONResponse:
    """Return 200 when service is running."""
    return JSONResponse(content={"status": "ok"})


@router.get("/live", summary="Liveness probe")
async def liveness() -> JSONResponse:
    """Return 200 when the process is alive."""
    return JSONResponse(content={"status": "ok"})


@router.get("/ready", summary="Readiness probe")
async def readiness() -> JSONResponse:
    """Return 200 when the application is ready to serve traffic.

    Readiness check currently validates that the process started correctly.
    Database connectivity is checked lazily on first request to avoid blocking
    startup when migrations are still running.
    """
    return JSONResponse(content={"status": "ok"})
