from celery import Celery

from libs.core.config import get_settings


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "sentient-worker",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["apps.worker.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        beat_schedule={
            "strategy-tick": {
                "task": "worker.strategy.tick",
                "schedule": settings.strategy_tick_seconds,
            }
        },
    )
    return app


celery_app = make_celery()
