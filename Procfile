web: uvicorn apps.api.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: celery -A apps.worker.celery_app worker --pool=prefork -l info -Q celery
worker-exec: celery -A apps.worker.celery_app worker --pool=prefork -l info -Q execution --concurrency=1
beat: celery -A apps.worker.celery_app beat -l info
