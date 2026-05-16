#!/usr/bin/env bash
# =============================================================================
# scripts/cleanup_repo.sh — Sylion project deep clean
#
# Removes patch artefacts, transient test DBs, bytecode caches, and
# tool-generated cache directories that must never appear in a release.
#
# USAGE:
#   ./scripts/cleanup_repo.sh          # dry-run (default, safe)
#   ./scripts/cleanup_repo.sh --apply  # actually delete files
#   DRY_RUN=0 ./scripts/cleanup_repo.sh   # same as --apply
#
# IDEMPOTENT: re-running produces no side-effects when nothing remains.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
DRY_RUN=1
for arg in "$@"; do
  case "$arg" in
    --apply) DRY_RUN=0 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# //'
      exit 0
      ;;
  esac
done

[[ "${DRY_RUN:-1}" == "0" ]] && DRY_RUN=0

if [[ "$DRY_RUN" -eq 1 ]]; then
  MODE_LABEL="DRY-RUN (pass --apply to delete)"
else
  MODE_LABEL="APPLY — files will be deleted"
fi

echo "======================================================"
echo " Sylion cleanup_repo.sh  |  ${MODE_LABEL}"
echo " Repo root: ${REPO_ROOT}"
echo "======================================================"
echo ""

REMOVED=0
SKIPPED=0

# ---------------------------------------------------------------------------
# Helper: remove a file or dir
# ---------------------------------------------------------------------------
_rm() {
  local target="$1"
  local reason="${2:-patch artefact}"
  if [[ -e "$target" || -L "$target" ]]; then
    echo "  REMOVE  ${target}  (${reason})"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      rm -rf -- "$target"
    fi
    (( REMOVED++ )) || true
  fi
}

# ---------------------------------------------------------------------------
# 1. Patch/editor artefacts
# ---------------------------------------------------------------------------
echo "--- 1. Patch / editor artefacts ---"
while IFS= read -r -d '' f; do
  _rm "$f" "patch artefact"
done < <(find "$REPO_ROOT" -type f \
  \( -name "*.orig" -o -name "*.rej" -o -name "*.fixed" \
     -o -name "*.bak"  -o -name "*~"   -o -name ".#*" \) \
  -not -path "*/.venv/*" \
  -not -path "*/.git/*" \
  -print0 2>/dev/null)

# ---------------------------------------------------------------------------
# 2. Transient test databases (not in tests/fixtures/)
# ---------------------------------------------------------------------------
echo ""
echo "--- 2. Transient test databases (not in tests/fixtures/) ---"
while IFS= read -r -d '' f; do
  # Skip anything already under tests/fixtures/
  if [[ "$f" == */tests/fixtures/* ]]; then
    echo "  KEEP    ${f}  (test fixture)"
    (( SKIPPED++ )) || true
    continue
  fi
  # test_*.db pattern = clearly a test database
  basename_f=$(basename "$f")
  if [[ "$basename_f" == test_*.db || "$basename_f" == test_*.db-* ]]; then
    _rm "$f" "transient test DB"
  fi
done < <(find "$REPO_ROOT" -type f -name "*.db" \
  -not -path "*/.venv/*" \
  -not -path "*/.git/*" \
  -print0 2>/dev/null)

# Large DBs (>100KB) not in fixtures — warn but don't auto-remove
echo ""
echo "--- 2b. Large DBs >100KB (not in fixtures/) — informational ---"
while IFS= read -r -d '' f; do
  if [[ "$f" != */tests/fixtures/* ]]; then
    size_kb=$(du -k "$f" 2>/dev/null | cut -f1)
    echo "  WARN    ${f}  (${size_kb} KB) — consider moving to tests/fixtures/ or .gitignore"
  fi
done < <(find "$REPO_ROOT" -type f -name "*.db" -size +100k \
  -not -path "*/.venv/*" \
  -not -path "*/.git/*" \
  -print0 2>/dev/null)

# ---------------------------------------------------------------------------
# 3. __pycache__ directories
# ---------------------------------------------------------------------------
echo ""
echo "--- 3. __pycache__ directories ---"
while IFS= read -r -d '' d; do
  _rm "$d" "__pycache__"
done < <(find "$REPO_ROOT" -type d -name "__pycache__" \
  -not -path "*/.venv/*" \
  -not -path "*/.git/*" \
  -print0 2>/dev/null)

# ---------------------------------------------------------------------------
# 4. Tool caches
# ---------------------------------------------------------------------------
echo ""
echo "--- 4. Tool caches ---"
for cache in ".pytest_cache" ".ruff_cache" ".mypy_cache"; do
  target="${REPO_ROOT}/${cache}"
  [[ -d "$target" ]] && _rm "$target" "tool cache"
done

# .hypothesis — keep the directory itself (has its own .gitignore written by
# hypothesis), but remove generated data subdirs
echo ""
echo "--- 4b. .hypothesis generated data ---"
for subdir in "constants" "unicode_data" "examples"; do
  target="${REPO_ROOT}/.hypothesis/${subdir}"
  [[ -d "$target" ]] && _rm "$target" ".hypothesis generated data"
done

# ---------------------------------------------------------------------------
# 5. Compiled Python bytecode (orphaned .pyc / .pyo outside __pycache__)
# ---------------------------------------------------------------------------
echo ""
echo "--- 5. Orphaned .pyc / .pyo files ---"
while IFS= read -r -d '' f; do
  _rm "$f" "compiled bytecode"
done < <(find "$REPO_ROOT" -type f \( -name "*.pyc" -o -name "*.pyo" \) \
  -not -path "*/__pycache__/*" \
  -not -path "*/.venv/*" \
  -not -path "*/.git/*" \
  -print0 2>/dev/null)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "======================================================"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo " DRY-RUN complete."
  echo " Would remove : ${REMOVED} item(s)"
  echo " Kept (fixture): ${SKIPPED} item(s)"
  echo " Run with --apply to perform actual deletion."
else
  echo " APPLY complete."
  echo " Removed : ${REMOVED} item(s)"
  echo " Kept    : ${SKIPPED} item(s)"
fi
echo "======================================================"
