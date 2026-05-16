#!/usr/bin/env bash
# SYLION v5.9.1 — regenerate requirements-lock.txt from requirements.in.
# Uses pip-compile (pip-tools) with hash-sealed lock for reproducibility.
#
# Usage:
#   bash scripts/regen-lock.sh         # regen from scratch
#   bash scripts/regen-lock.sh upgrade # allow upgrades of pinned deps

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! python -m pip show pip-tools >/dev/null 2>&1; then
  echo "[SYLION] installing pip-tools..."
  python -m pip install -q pip-tools
fi

MODE="${1:-freeze}"
EXTRA_ARGS=()
if [[ "$MODE" == "upgrade" ]]; then
  EXTRA_ARGS+=(--upgrade)
fi

echo "[SYLION] compiling requirements.in -> requirements-lock.txt (hashes)"
python -m piptools compile \
  --generate-hashes \
  --output-file requirements-lock.txt \
  "${EXTRA_ARGS[@]}" \
  requirements.in

echo "[SYLION] done. Review diff before committing."
