#!/usr/bin/env bash
# ============================================================================
# SYLION AEIS — Master CI Check
#
# Runs all validation checks in sequence:
#   1. pytest (backend tests)
#   2. check_contracts.py (contract freeze validator)
#   3. check_imports.py (cross-module boundary checker, if exists)
#   4. check_golden_sets.py (golden set conformance)
#
# Exit code 0 only if ALL checks pass.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
SKIPPED_COUNT=0

# ---------------------------------------------------------------------------
# Helper: run a check and record result
# ---------------------------------------------------------------------------
run_check() {
    local name="$1"
    shift

    echo ""
    echo "================================================================"
    echo "CHECK: $name"
    echo "================================================================"

    if "$@"; then
        echo -e "${GREEN}PASS${NC}: $name"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo -e "${RED}FAIL${NC}: $name"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

run_check_optional() {
    local name="$1"
    shift

    echo ""
    echo "================================================================"
    echo "CHECK (optional): $name"
    echo "================================================================"

    if "$@"; then
        echo -e "${GREEN}PASS${NC}: $name"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo -e "${YELLOW}SKIP/FAIL${NC}: $name (optional — not blocking)"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    fi
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo "================================================================"
echo " SYLION AEIS — Master CI Check"
echo " Project: $PROJECT_ROOT"
echo " Date:    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "================================================================"

cd "$PROJECT_ROOT"

# --- 1. pytest (backend tests) ---
run_check "pytest (backend tests)" python -m pytest tests/ -x -q --tb=short 2>/dev/null \
    || run_check "pytest (backend tests, any location)" python -m pytest -x -q --tb=short

# --- 2. Contract freeze validator ---
run_check "Contract Freeze Validator" python scripts/check_contracts.py

# --- 3. check_imports.py (if exists) ---
if [ -f "scripts/check_imports.py" ]; then
    run_check "Import Boundary Checker" python scripts/check_imports.py
else
    echo ""
    echo "================================================================"
    echo "CHECK: Import Boundary Checker"
    echo "================================================================"
    echo -e "${YELLOW}SKIP${NC}: scripts/check_imports.py not found"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
fi

# --- 4. Golden set runner ---
run_check "Golden Set Runner" python scripts/check_golden_sets.py

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "================================================================"
echo " MASTER CI CHECK — SUMMARY"
echo "================================================================"
echo -e "  Passed:   ${GREEN}${PASS_COUNT}${NC}"
echo -e "  Failed:   ${RED}${FAIL_COUNT}${NC}"
echo -e "  Skipped:  ${YELLOW}${SKIPPED_COUNT}${NC}"
echo "================================================================"

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "${RED}OVERALL: FAIL${NC} — ${FAIL_COUNT} check(s) failed"
    exit 1
else
    echo -e "${GREEN}OVERALL: PASS${NC} — all checks succeeded"
    exit 0
fi
