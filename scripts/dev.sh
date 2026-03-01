#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .venv/Scripts/python.exe ]]; then
  PY=.venv/Scripts/python.exe
else
  PY=.venv/bin/python
fi

if [[ ! -x "$PY" ]]; then
  echo "Missing .venv. Run ./scripts/bootstrap.sh first." >&2
  exit 2
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

PORT="${PORT:-8000}"
$PY -m uvicorn apps.api.app.main:app --reload --port "$PORT"

