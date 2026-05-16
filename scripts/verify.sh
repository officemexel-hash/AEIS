#!/usr/bin/env bash
set -euo pipefail
BASE="${SYLION_BASE:-http://127.0.0.1:8422}"

echo "==> SYLION v6.2.0 verify @ $BASE"

pass=0; fail=0
check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "    [PASS] $name"; pass=$((pass+1))
  else
    echo "    [FAIL] $name"; fail=$((fail+1))
  fi
}

check "/api/health 200 + version=6.2.0"    bash -c "curl -sf $BASE/api/health | grep -q '6.2.0'"
check "/api/version == 6.2.0"              bash -c "curl -sf $BASE/api/version | grep -q '\"version\":\"6.2.0\"'"
check "/api/auth/setup-status (B-003)"     bash -c "curl -sf $BASE/api/auth/setup-status"
check "/api/human-gate/queue canonical"    bash -c "curl -s -o /dev/null -w '%{http_code}' $BASE/api/human-gate/queue | grep -qE '^(401|200|403)$'"
check "/api/human_gate/queue deprecated"   bash -c "curl -s -D - $BASE/api/human_gate/queue | grep -qi '^deprecation'"

echo
echo "Result: $pass PASS, $fail FAIL"
exit $fail
