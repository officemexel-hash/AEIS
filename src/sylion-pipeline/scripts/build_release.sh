#!/usr/bin/env bash
# SYLION release guard for the unified AEIS runtime.
#
# Verifies that the source tree contains no runtime artifacts before packaging.

set -euo pipefail

ROOT="${SYLION_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT"

fail() { echo "BUILD GUARD FAIL: $*" >&2; exit 1; }
ok()   { echo "  ok: $*"; }

echo "[build_release] Guard checks in: $ROOT"

if find . \( -name ".venv" -o -name "__pycache__" -o -name ".git" -o -name "results" -o -name "workspace_uploads" \) -prune -o -name '*.db' -print 2>/dev/null | head -1 | grep -q .; then
  fail "found *.db in source tree (see above; add to .gitignore or remove)"
fi
ok "no DB files bundled"

if [[ ! -f VERSION ]]; then fail "VERSION file missing"; fi
VER=$(tr -d '[:space:]' < VERSION)
[[ -n "$VER" ]] || fail "VERSION file empty"
ok "VERSION = $VER"

if ! python3 -m py_compile sylion/server.py >/dev/null 2>&1; then
  fail "sylion/server.py does not compile"
fi
ok "unified runtime entrypoint compiles"

if grep -R --line-number --exclude-dir=.git --exclude-dir=.venv --exclude-dir=__pycache__ \
  -E 'dashboard[\\/](app|db|start)\.py|dashboard\.app|dashboard\.db|python dashboard[\\/]start' . 2>/dev/null | grep -v '^./scripts/build_release.sh:'; then
  fail "legacy dashboard runtime reference found"
fi
ok "no legacy dashboard runtime references"

echo "[build_release] ALL GUARDS PASSED for v$VER"
