#!/usr/bin/env bash
set -e
echo "=== Final Audit v6.0.0 ==="
# 1. Hardcoded keys
if grep -rn "sk-ant-api03\|sk-proj-Jw\|pplx-o2ZY\|AQ\.Ab8RN" dashboard/ orchestrator.py budget_guard.py 2>/dev/null | grep -v "^#\|//\|_DEFAULT_API_KEYS.*\"\"\|test_"; then
  echo "FAIL: hardcoded keys found"; exit 1
fi
echo "[OK] No hardcoded keys"
# 2. .bak/.coverage
if find . -name "*.bak" -o -name ".coverage" -o -name ".ruff_cache" 2>/dev/null | grep -v ".venv\|__pycache__" | head -1 | grep -q .; then
  echo "FAIL: dev artifacts found"; exit 1
fi
echo "[OK] No dev artifacts"
# 3. SETUP_TOKEN.txt
if [ -f "dashboard/SETUP_TOKEN.txt" ]; then
  echo "FAIL: SETUP_TOKEN.txt exists"; exit 1
fi
echo "[OK] No SETUP_TOKEN.txt"
# 4. Version consistency
VERSION_FILE=$(cat VERSION 2>/dev/null)
if [ "$VERSION_FILE" != "6.0.0" ]; then
  echo "FAIL: VERSION file != 6.0.0"; exit 1
fi
echo "[OK] VERSION = 6.0.0"
echo "=== All checks passed ==="
