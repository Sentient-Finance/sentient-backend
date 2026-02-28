"""Celery task definitions.

Import celery_app here (not the other way around) to avoid circular imports.
"""
from apps.worker.celery_app import celery_app


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"
