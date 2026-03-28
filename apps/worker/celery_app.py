from celery import Celery  # type: ignore[import-untyped]

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
        # Route execution tasks to a dedicated single-concurrency queue
        # so all performUpkeep calls are sequential → no nonce collision.
        task_routes={
            "worker.execution.enqueue": {"queue": "execution"},
        },
        beat_schedule={
            "strategy-tick": {
                "task": "worker.strategy.tick",
                "schedule": settings.strategy_tick_seconds,
            },
            "risk-guard-tick": {
                "task": "worker.risk_guard.tick",
                "schedule": settings.risk_tick_seconds,
            },
            "indexer-tick": {
                "task": "worker.indexer.tick",
                "schedule": settings.indexer_tick_seconds,
            },
        },
    )
    return app


celery_app = make_celery()
