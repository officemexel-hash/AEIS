#!/usr/bin/env bash
# SYLION AEIS — Unified start script (Linux)
# Starts backend on :8010 and frontend on :8422
# The frontend proxies /api/v1/* to the backend via next.config.ts rewrites.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$(pwd)}"
BACKEND_DIR="$INSTALL_DIR/src/sylion-pipeline"
FRONTEND_DIR="$INSTALL_DIR/src/sylion-frontend"
VENV_DIR="$INSTALL_DIR/.venv"
ENV_FILE="$INSTALL_DIR/.env.generated"

BACKEND_PORT="${SYLION_BACKEND_PORT:-8010}"
FRONTEND_PORT="${SYLION_FRONTEND_PORT:-8422}"

echo "==> SYLION AEIS — starting services"
echo "    Backend:  http://127.0.0.1:$BACKEND_PORT"
echo "    Frontend: http://127.0.0.1:$FRONTEND_PORT"
echo ""

# --- Stop any previous instances ---
echo "[1/4] Cleaning up previous instances..."
pkill -f "sylion.server.*--http-port" 2>/dev/null || true
pkill -f "sylion.api.app:app" 2>/dev/null || true
pkill -f "next-server.*$FRONTEND_PORT" 2>/dev/null || true
sleep 1

# --- Start backend ---
echo "[2/4] Starting backend on :$BACKEND_PORT..."
if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  echo "ERROR: missing virtualenv at $VENV_DIR. Run ./scripts/install.sh first."
  exit 1
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export SYLION_USE_LEGACY_DB_PATH="0"
export SESSION_COOKIE_SECURE="0"
export SYLION_ENV="dev"
export SYLION_AEIS_ENV="dev"
export SYLION_RBAC_DISABLED="1"
export SYLION_RATE_LIMIT_DISABLED="1"
export SYLION_AUTH_BYPASS="1"
export SYLION_DB_PATH="${SYLION_DB_PATH:-$INSTALL_DIR/sylion_aeis.db}"
export PYTHONPATH="$BACKEND_DIR"
export LITELLM_LOCAL_MODEL_COST_MAP="True"
export LITELLM_DO_NOT_TRACK="True"

cd "$BACKEND_DIR"
python -m uvicorn sylion.api.app:app \
  --host 127.0.0.1 \
  --port "$BACKEND_PORT" \
  --timeout-graceful-shutdown 10 \
  &>/tmp/aeis_backend.log &
BACKEND_PID=$!
echo "    Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "    Waiting for backend to start..."
for i in $(seq 1 30); do
  if curl -s -m 1 "http://127.0.0.1:$BACKEND_PORT/api/v1/health" >/dev/null 2>&1; then
    echo "    Backend ready!"
    break
  fi
  sleep 1
done

# --- Start frontend ---
echo "[3/4] Starting frontend on :$FRONTEND_PORT..."
cd "$FRONTEND_DIR"

if [[ ! -d "node_modules" ]]; then
  echo "    Installing frontend dependencies..."
  npm install --silent 2>&1
fi

export NEXT_PUBLIC_API_URL=""
npx next dev --hostname 127.0.0.1 --port "$FRONTEND_PORT" \
  &>/tmp/aeis_frontend.log &
FRONTEND_PID=$!
echo "    Frontend PID: $FRONTEND_PID"

# Wait for frontend to be ready
echo "    Waiting for frontend to start..."
for i in $(seq 1 60); do
  if curl -s -m 1 "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null 2>&1; then
    echo "    Frontend ready!"
    break
  fi
  sleep 2
done

echo ""
echo "==> SYLION AEIS is running!"
echo "    Frontend:  http://127.0.0.1:$FRONTEND_PORT"
echo "    Backend:   http://127.0.0.1:$BACKEND_PORT"
echo "    API Docs:  http://127.0.0.1:$BACKEND_PORT/docs"
echo ""
echo "    Backend log:  tail -f /tmp/aeis_backend.log"
echo "    Frontend log: tail -f /tmp/aeis_frontend.log"
echo ""
echo "    To stop: kill $BACKEND_PID $FRONTEND_PID"
echo ""

# Save PIDs for later cleanup
echo "$BACKEND_PID" > /tmp/aeis_backend.pid
echo "$FRONTEND_PID" > /tmp/aeis_frontend.pid

# Keep script running so user can Ctrl+C to stop both
echo "Press Ctrl+C to stop all services..."
echo ""

# Trap Ctrl+C to kill both processes
cleanup() {
  echo ""
  echo "Stopping services..."
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
  rm -f /tmp/aeis_backend.pid /tmp/aeis_frontend.pid
  echo "Services stopped."
  exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for either process to exit
wait -n "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
echo "A service has stopped. Cleaning up..."
cleanup