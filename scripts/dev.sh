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

PORT="${PORT:-8001}"

# Kill process on port (force fresh start)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -x "$SCRIPT_DIR/kill-port.sh" ]]; then
  "$SCRIPT_DIR/kill-port.sh" "$PORT" 2>/dev/null || true
elif command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
  PID=$(lsof -ti:"$PORT" 2>/dev/null) && kill -9 $PID 2>/dev/null || true
fi
sleep 2

# Clear Python cache (fix stale bytecode)
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo "Cache cleared. Starting API on port $PORT"

$PY -m uvicorn apps.api.app.main:app --reload --reload-dir apps --reload-dir libs --port "$PORT"

