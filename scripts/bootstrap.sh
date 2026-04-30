#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

docker compose -f docker-compose.yml up -d

if [[ ! -d .venv ]]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  elif command -v python >/dev/null 2>&1; then
    python -m venv .venv
  else
    echo "Python not found. Please install python3." >&2
    exit 1
  fi
fi

if [[ -f .venv/Scripts/python.exe ]]; then
  PY=.venv/Scripts/python.exe
else
  PY=.venv/bin/python
fi

$PY -m pip install -U pip
$PY -m pip install -e ".[dev]"

echo
echo "Next:"
echo "  source .venv/Scripts/activate  # Windows Git Bash"
echo "  source .venv/bin/activate      # Linux/macOS"
echo "  ./scripts/dev.sh"
