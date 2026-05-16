#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$(pwd)}"
SRC_DIR="$INSTALL_DIR/src/sylion-pipeline"
VENV_DIR="$INSTALL_DIR/.venv"
ENV_FILE="$INSTALL_DIR/.env.generated"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  echo "ERROR: missing virtualenv at $VENV_DIR. Run ./scripts/install.sh first."
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "INFO: $ENV_FILE missing; starting in local-first mode without API keys."
fi

export SYLION_USE_LEGACY_DB_PATH="0"
export SESSION_COOKIE_SECURE="0"
export SYLION_ENV="dev"
export SYLION_AEIS_ENV="dev"
export SYLION_RBAC_DISABLED="1"
export SYLION_RATE_LIMIT_DISABLED="1"
export SYLION_AUTH_BYPASS="1"
export SYLION_DB_PATH="${SYLION_DB_PATH:-$INSTALL_DIR/sylion_aeis.db}"
export PYTHONPATH="$SRC_DIR"
export LITELLM_LOCAL_MODEL_COST_MAP="True"
export LITELLM_DO_NOT_TRACK="True"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
cd "$SRC_DIR"

echo
echo "SYLION AEIS API starts on http://127.0.0.1:8010"
echo "Stop with Ctrl+C"
echo

python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010 --timeout-graceful-shutdown 10
