"""Worker entrypoint.

Run via Makefile:   make worker
Or directly:        celery -A apps.worker.celery_app.celery_app worker --loglevel=info
"""
from apps.worker.celery_app import celery_app  # noqa: F401 — re-exported for celery CLI


def run() -> None:
    celery_app.start()


if __name__ == "__main__":
    run()
