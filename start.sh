#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
VENV_DIR="${ECOAIMS_VENV_DIR:-$ROOT_DIR/ecoaims_frontend_env}"
PID_FILE="$RUN_DIR/frontend-server.pid"
LOG_FILE="$RUN_DIR/frontend-server.log"
REQ_FILE="$ROOT_DIR/ecoaims_frontend/requirements.txt"

mkdir -p "$RUN_DIR"

resolve_system_python() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  echo "Error: python3/python tidak ditemukan. Install Python 3 terlebih dahulu." >&2
  return 127
}

ensure_venv() {
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    return 0
  fi
  local sys_py
  sys_py="$(resolve_system_python)"
  "$sys_py" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel >/dev/null
}

install_deps() {
  ensure_venv
  if [[ ! -f "$REQ_FILE" ]]; then
    echo "Error: requirements.txt tidak ditemukan di: $REQ_FILE" >&2
    return 2
  fi
  "$VENV_DIR/bin/python" -m pip install -r "$REQ_FILE"
}

frontend_env() {
  export ECOAIMS_API_BASE_URL="${ECOAIMS_API_BASE_URL:-http://127.0.0.1:8008}"
  export ECOAIMS_AUTH_ENABLED="${ECOAIMS_AUTH_ENABLED:-true}"
  export ECOAIMS_AUTH_MODE="${ECOAIMS_AUTH_MODE:-proxy}"
  export ECOAIMS_AUTH_BACKEND_BASE_URL="${ECOAIMS_AUTH_BACKEND_BASE_URL:-$ECOAIMS_API_BASE_URL}"
  export ECOAIMS_FORCE_HTTPS="${ECOAIMS_FORCE_HTTPS:-false}"
  export ECOAIMS_SESSION_COOKIE_SECURE="${ECOAIMS_SESSION_COOKIE_SECURE:-false}"
  export ECOAIMS_FRONTEND_HOST="${ECOAIMS_FRONTEND_HOST:-}"
  export ECOAIMS_FRONTEND_PORT="${ECOAIMS_FRONTEND_PORT:-8050}"
  export ECOAIMS_DASH_DEBUG="${ECOAIMS_DASH_DEBUG:-false}"
  export ECOAIMS_DASH_USE_RELOADER="${ECOAIMS_DASH_USE_RELOADER:-false}"
}

is_running() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

start_foreground() {
  ensure_venv
  frontend_env
  if [[ -z "${ECOAIMS_FRONTEND_HOST:-}" ]]; then
    export ECOAIMS_FRONTEND_HOST="127.0.0.1"
  fi
  cd "$ROOT_DIR"
  exec "$VENV_DIR/bin/python" -m ecoaims_frontend.app
}

start_daemon() {
  install_deps
  frontend_env
  if [[ -z "${ECOAIMS_FRONTEND_HOST:-}" ]]; then
    export ECOAIMS_FRONTEND_HOST="0.0.0.0"
  fi

  if is_running; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    echo "Frontend sudah berjalan (pid=$pid)."
    return 0
  fi

  cd "$ROOT_DIR"
  nohup "$VENV_DIR/bin/python" -m ecoaims_frontend.app >"$LOG_FILE" 2>&1 &
  echo "$!" >"$PID_FILE"
  echo "Frontend started (pid=$(cat "$PID_FILE"))."
  echo "URL: http://${ECOAIMS_FRONTEND_HOST}:${ECOAIMS_FRONTEND_PORT}/"
  echo "Logs: $LOG_FILE"
}

stop_daemon() {
  if ! [[ -f "$PID_FILE" ]]; then
    echo "Frontend tidak sedang berjalan (pid file tidak ada)."
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE" 2>/dev/null || true
  echo "Stopped (if running)."
}

status() {
  if is_running; then
    echo "running (pid=$(cat "$PID_FILE"))"
  else
    echo "stopped"
  fi
}

logs() {
  if [[ -f "$LOG_FILE" ]]; then
    tail -n 200 "$LOG_FILE"
  else
    echo "Log file belum ada: $LOG_FILE"
  fi
}

usage() {
  cat <<'TXT'
Usage:
  ./start.sh install
  ./start.sh start        (foreground)
  ./start.sh daemon       (background + pid/log)
  ./start.sh stop
  ./start.sh restart
  ./start.sh status
  ./start.sh logs

Env:
  ECOAIMS_API_BASE_URL      default: http://127.0.0.1:8008
  ECOAIMS_AUTH_ENABLED      default: true
  ECOAIMS_AUTH_MODE         default: proxy
  ECOAIMS_AUTH_BACKEND_BASE_URL default: same as ECOAIMS_API_BASE_URL
  ECOAIMS_FORCE_HTTPS       default: false
  ECOAIMS_SESSION_COOKIE_SECURE default: false
  ECOAIMS_FRONTEND_HOST     default: 127.0.0.1 (daemon akan override ke 0.0.0.0 jika tidak diset)
  ECOAIMS_FRONTEND_PORT     default: 8050
  ECOAIMS_DASH_DEBUG        default: false
  ECOAIMS_DASH_USE_RELOADER default: false
  ECOAIMS_VENV_DIR          default: ./ecoaims_frontend_env
TXT
}

cmd="${1:-start}"
case "$cmd" in
  install)
    install_deps
    ;;
  start)
    start_foreground
    ;;
  daemon)
    start_daemon
    ;;
  stop)
    stop_daemon
    ;;
  restart)
    stop_daemon
    start_daemon
    ;;
  status)
    status
    ;;
  logs)
    logs
    ;;
  *)
    usage
    exit 2
    ;;
esac
