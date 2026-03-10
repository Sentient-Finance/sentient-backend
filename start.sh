#!/bin/sh
# Run indexer in background
python -m apps.indexer.main --loop &

# Run API in foreground (keeps container alive)
exec uvicorn apps.api.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
