#!/usr/bin/env bash
# Kill all processes listening on a given port (Windows + Unix)
set -euo pipefail

PORT="${1:-8000}"

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  # Windows: use netstat + taskkill (last column is PID)
  while read -r line; do
    pid=$(echo "$line" | awk '{print $NF}')
    if [[ -n "$pid" && "$pid" != "0" ]]; then
      taskkill //F //PID "$pid" 2>/dev/null && echo "Killed PID $pid" || true
    fi
  done < <(netstat -ano 2>/dev/null | grep ":$PORT" | grep LISTENING)
else
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null || true
  elif command -v lsof >/dev/null 2>&1; then
    PID=$(lsof -ti:"$PORT" 2>/dev/null) && kill -9 $PID 2>/dev/null || true
  else
    echo "No fuser/lsof. Install or kill manually." >&2
    exit 1
  fi
fi

echo "Port $PORT cleared."
