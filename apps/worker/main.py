"""Worker module — re-exports celery_app for the celery CLI.

Run via Makefile:   make worker
Or directly:        celery -A apps.worker.celery_app worker -l info
"""

from apps.worker.celery_app import celery_app  # noqa: F401 — re-exported for celery CLI
