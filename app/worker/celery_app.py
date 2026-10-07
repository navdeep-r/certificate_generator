"""Celery application factory.

Import this module to get the configured Celery app:
    from app.worker.celery_app import celery_app
"""
from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "bulk_certificate_generator",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Prevent tasks from being silently lost on ack failure
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Retry-related
    task_reject_on_worker_lost=True,
)
