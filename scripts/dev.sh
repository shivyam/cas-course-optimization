#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/src/backend"
FRONTEND_DIR="$ROOT_DIR/src/frontend"
BACKEND_PYTHON="$BACKEND_DIR/.venv/bin/python"

if [[ ! -x "$BACKEND_PYTHON" ]]; then
  echo "Backend virtual environment not found at $BACKEND_DIR/.venv"
  echo "Create it and install the backend first:"
  echo "  cd src/backend && python -m venv .venv && .venv/bin/pip install -e \".[dev]\""
  exit 1
fi

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

(
  cd "$BACKEND_DIR" || exit
  echo "Starting backend at http://127.0.0.1:8000"
  exec "$BACKEND_PYTHON" -m uvicorn app.main:app --reload
) &
BACKEND_PID=$!

(
  cd "$FRONTEND_DIR" || exit
  echo "Starting frontend at http://localhost:5173"
  exec npm run dev
) &
FRONTEND_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
