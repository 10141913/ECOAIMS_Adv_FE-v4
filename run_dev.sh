#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

HOST="${HOST:-127.0.0.1}"
BACKEND_PORT_BASE="${BACKEND_PORT_BASE:-8008}"
FRONTEND_PORT_BASE="${FRONTEND_PORT_BASE:-8050}"

PY="${PYTHON_BIN:-}"
if [[ -z "${PY}" ]]; then
  if [[ -x "$ROOT_DIR/ecoaims_frontend_env/bin/python" ]]; then
    PY="$ROOT_DIR/ecoaims_frontend_env/bin/python"
  else
    PY="$(command -v python3 || command -v python)"
  fi
fi

port_free() {
  "$PY" - "$HOST" "$1" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind((host, port))
except OSError:
    sys.exit(1)
finally:
    try:
        sock.close()
    except Exception:
        pass
sys.exit(0)
PY
}

find_port() {
  local p="$1"
  while ! port_free "$p"; do
    p=$((p + 1))
  done
  echo "$p"
}

BACKEND_PORT="$(find_port "$BACKEND_PORT_BASE")"
FRONTEND_PORT="$(find_port "$FRONTEND_PORT_BASE")"

BACKEND_URL="http://$HOST:$BACKEND_PORT"
FRONTEND_URL="http://$HOST:$FRONTEND_PORT"

mkdir -p "$ROOT_DIR/.run"
BACKEND_LOG="$ROOT_DIR/.run/backend.log"
FRONTEND_LOG="$ROOT_DIR/.run/frontend.log"
BACKEND_PID_FILE="$ROOT_DIR/.run/backend.pid"
FRONTEND_PID_FILE="$ROOT_DIR/.run/frontend.pid"

cleanup() {
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$PY" -m uvicorn ecoaims_backend.devtools.mock_fastapi_app:app --host "$HOST" --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID="$!"
echo "$BACKEND_PID" >"$BACKEND_PID_FILE"

for _ in $(seq 1 80); do
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1; then
      break
    fi
  else
    if "$PY" - "$BACKEND_URL" <<'PY' >/dev/null 2>&1; then
import sys
import urllib.request

url = sys.argv[1].rstrip("/") + "/health"
with urllib.request.urlopen(url, timeout=2) as r:
    sys.exit(0 if r.status == 200 else 1)
PY
      break
    fi
  fi
  sleep 0.2
done

export ECOAIMS_API_BASE_URL="$BACKEND_URL"
export ECOAIMS_FRONTEND_PORT="$FRONTEND_PORT"

"$PY" -m ecoaims_frontend.app >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID="$!"
echo "$FRONTEND_PID" >"$FRONTEND_PID_FILE"

echo "Mode: DEV STACK (mock backend devtools, NON-canonical)"
if [[ "$BACKEND_PORT" != "$BACKEND_PORT_BASE" ]]; then
  echo "Info: port backend $BACKEND_PORT_BASE sudah terpakai, pakai $BACKEND_PORT (ECOAIMS_API_BASE_URL ikut berubah)"
fi
if [[ "$FRONTEND_PORT" != "$FRONTEND_PORT_BASE" ]]; then
  echo "Info: port frontend $FRONTEND_PORT_BASE sudah terpakai, pakai $FRONTEND_PORT"
fi

echo "Backend (FastAPI): $BACKEND_URL"
echo "Frontend (Dash):   $FRONTEND_URL"
echo "Logs:"
echo "  $BACKEND_LOG"
echo "  $FRONTEND_LOG"
echo "PIDs:"
echo "  backend:  $BACKEND_PID (file: $BACKEND_PID_FILE)"
echo "  frontend: $FRONTEND_PID (file: $FRONTEND_PID_FILE)"
echo "Stop: Ctrl+C"

wait "$FRONTEND_PID"
