#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID_FILE="$ROOT_DIR/.run/backend.pid"
FRONTEND_PID_FILE="$ROOT_DIR/.run/frontend.pid"

kill_if_running() {
  local pid="$1"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
}

if [[ -f "$FRONTEND_PID_FILE" ]]; then
  FRONTEND_PID="$(cat "$FRONTEND_PID_FILE" || true)"
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill_if_running "$FRONTEND_PID"
  fi
  rm -f "$FRONTEND_PID_FILE" 2>/dev/null || true
fi

if [[ -f "$BACKEND_PID_FILE" ]]; then
  BACKEND_PID="$(cat "$BACKEND_PID_FILE" || true)"
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill_if_running "$BACKEND_PID"
  fi
  rm -f "$BACKEND_PID_FILE" 2>/dev/null || true
fi

echo "Stopped (if running)."
