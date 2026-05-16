#!/usr/bin/env bash
# =============================================================================
# SYLION — regenerate_checksums.sh
# Regeneruje CHECKSUMS.sha256 dla wszystkich śledzonych plików projektu.
#
# Śledzony zbiór: *.py *.md *.sh *.yml *.yaml *.bat *.json *.txt
# Wykluczenia: .venv/, __pycache__/, .hypothesis/, .pytest_cache/,
#              .ruff_cache/, workspace_uploads/, .git/, benchmark_results/
#
# Użycie:
#   cd /path/to/sylion-pipeline
#   chmod +x scripts/regenerate_checksums.sh
#   ./scripts/regenerate_checksums.sh
#
# Opcje:
#   --dry-run      Wyświetl co zostałoby zapisane (bez zapisu)
#   --verify       Tylko weryfikuj istniejący CHECKSUMS.sha256 (bez regeneracji)
#   --strict       Zakończ z exit code 1 jeśli są niespójności (używaj w CI)
#   --output FILE  Zapisz do wskazanego pliku (domyślnie: CHECKSUMS.sha256)
#
# Wymaga: sha256sum (Linux) lub shasum -a 256 (macOS)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Stałe i wartości domyślne
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Projekt root = katalog nadrzędny względem scripts/
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_FILE="${PROJECT_ROOT}/CHECKSUMS.sha256"
DRY_RUN=false
VERIFY_ONLY=false
STRICT=false
VERBOSE=false

# Kolory terminala (wyłącz jeśli nie TTY)
if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  NC='\033[0m'
else
  RED=''
  GREEN=''
  YELLOW=''
  BLUE=''
  NC=''
fi

# ---------------------------------------------------------------------------
# Parsowanie argumentów
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --verify)
      VERIFY_ONLY=true
      shift
      ;;
    --strict)
      STRICT=true
      shift
      ;;
    --verbose|-v)
      VERBOSE=true
      shift
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# //' | sed 's/^#//'
      exit 0
      ;;
    *)
      echo "Nieznany argument: $1" >&2
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Wybór narzędzia sha256sum (Linux vs macOS)
# ---------------------------------------------------------------------------

if command -v sha256sum &>/dev/null; then
  SHA256_CMD="sha256sum"
  SHA256_CHECK_CMD="sha256sum --check --ignore-missing"
elif command -v shasum &>/dev/null; then
  SHA256_CMD="shasum -a 256"
  SHA256_CHECK_CMD="shasum -a 256 --check --ignore-missing"
else
  echo -e "${RED}BŁĄD: Nie znaleziono sha256sum ani shasum. Zainstaluj coreutils.${NC}" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Funkcja: znajdź śledzony zbiór plików
# ---------------------------------------------------------------------------

find_tracked_files() {
  local root="$1"

  find "${root}" \
    \( \
      -name "*.py" \
      -o -name "*.md" \
      -o -name "*.sh" \
      -o -name "*.yml" \
      -o -name "*.yaml" \
      -o -name "*.bat" \
      -o -name "*.json" \
      -o -name "*.txt" \
    \) \
    ! -path "*/.venv/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.hypothesis/*" \
    ! -path "*/.pytest_cache/*" \
    ! -path "*/.ruff_cache/*" \
    ! -path "*/workspace_uploads/*" \
    ! -path "*/.git/*" \
    ! -path "*/benchmark_results/*" \
    ! -path "*/node_modules/*" \
    2>/dev/null \
  | sort
}

# ---------------------------------------------------------------------------
# Tryb: --verify
# ---------------------------------------------------------------------------

if [ "${VERIFY_ONLY}" = true ]; then
  echo -e "${BLUE}[SYLION CHECKSUMS] Tryb weryfikacji: ${OUTPUT_FILE}${NC}"

  if [ ! -f "${OUTPUT_FILE}" ]; then
    echo -e "${RED}BŁĄD: Plik ${OUTPUT_FILE} nie istnieje.${NC}" >&2
    exit 1
  fi

  cd "${PROJECT_ROOT}"
  FAILED=0
  PASSED=0

  while IFS= read -r line; do
    [[ "$line" =~ ^# ]] && continue
    [[ -z "$line" ]] && continue

    expected_hash="${line%% *}"
    filepath="${line#* }"
    filepath="${filepath#./}"

    if [ ! -f "${filepath}" ]; then
      echo -e "${RED}MISSING: ${filepath}${NC}"
      FAILED=$((FAILED + 1))
      continue
    fi

    actual_hash=$(${SHA256_CMD} "${filepath}" 2>/dev/null | awk '{print $1}')
    if [ "${actual_hash}" = "${expected_hash}" ]; then
      [ "${VERBOSE}" = true ] && echo -e "${GREEN}OK: ${filepath}${NC}"
      PASSED=$((PASSED + 1))
    else
      echo -e "${RED}FAILED: ${filepath}${NC}"
      [ "${VERBOSE}" = true ] && echo -e "  Expected: ${expected_hash}"
      [ "${VERBOSE}" = true ] && echo -e "  Actual:   ${actual_hash}"
      FAILED=$((FAILED + 1))
    fi
  done < "${OUTPUT_FILE}"

  echo ""
  echo -e "${GREEN}OK: ${PASSED}${NC} | ${RED}FAILED/MISSING: ${FAILED}${NC}"

  if [ "${FAILED}" -gt 0 ] && [ "${STRICT}" = true ]; then
    echo -e "${RED}[STRICT] Weryfikacja nieudana — ${FAILED} pliki niezgodne.${NC}" >&2
    exit 1
  fi

  exit 0
fi

# ---------------------------------------------------------------------------
# Tryb: generowanie CHECKSUMS.sha256
# ---------------------------------------------------------------------------

echo -e "${BLUE}[SYLION CHECKSUMS] Regeneracja CHECKSUMS.sha256${NC}"
echo -e "  Projekt: ${PROJECT_ROOT}"
echo -e "  Wyjście: ${OUTPUT_FILE}"
echo ""

cd "${PROJECT_ROOT}"

# Zbierz pliki
TRACKED_FILES="$(find_tracked_files "${PROJECT_ROOT}")"
FILE_COUNT=$(echo "${TRACKED_FILES}" | wc -l | tr -d ' ')

echo -e "Znaleziono ${BLUE}${FILE_COUNT}${NC} plików do zahashowania..."

# Buduj zawartość CHECKSUMS
{
  echo "# SYLION CHECKSUMS.sha256"
  echo "# Wygenerowano: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "# Wersja: $(cat "${PROJECT_ROOT}/VERSION" 2>/dev/null || echo 'unknown')"
  echo "# Narzędzie: ${SHA256_CMD}"
  echo "# Śledzone rozszerzenia: .py .md .sh .yml .yaml .bat .json .txt"
  echo "# Aby zweryfikować: sha256sum --check CHECKSUMS.sha256"
  echo "#"
  echo ""

  while IFS= read -r filepath; do
    # Konwertuj ścieżkę bezwzględną na względną od roota projektu
    rel_path="./${filepath#${PROJECT_ROOT}/}"

    if [ "${VERBOSE}" = true ]; then
      echo "  Hashowanie: ${rel_path}" >&2
    fi

    ${SHA256_CMD} "${filepath}" 2>/dev/null | \
      awk -v rp="${rel_path}" '{print $1 "  " rp}'

  done <<< "${TRACKED_FILES}"

} > /tmp/sylion_checksums_tmp.sha256

LINES=$(grep -c '  \.' /tmp/sylion_checksums_tmp.sha256 2>/dev/null || true)
echo -e "Zahashowano ${GREEN}${LINES}${NC} plików."

# Podsumowanie zmian (jeśli stary plik istnieje)
if [ -f "${OUTPUT_FILE}" ]; then
  OLD_COUNT=$(grep -c '  \.' "${OUTPUT_FILE}" 2>/dev/null || echo 0)
  NEW_COUNT=${LINES}
  DIFF=$((NEW_COUNT - OLD_COUNT))

  echo ""
  echo -e "Poprzedni: ${OLD_COUNT} wpisów → Nowy: ${NEW_COUNT} wpisów (${DIFF:+${DIFF}})"

  # Pokaż pliki które się zmieniły
  CHANGED=0
  while IFS= read -r line; do
    [[ "$line" =~ ^# ]] && continue
    [[ -z "$line" ]] && continue
    if ! grep -qF "$line" "${OUTPUT_FILE}" 2>/dev/null; then
      filepath="${line#* }"
      echo -e "  ${YELLOW}CHANGED:${NC} ${filepath}"
      CHANGED=$((CHANGED + 1))
    fi
  done < /tmp/sylion_checksums_tmp.sha256

  if [ "${CHANGED}" -eq 0 ]; then
    echo -e "${GREEN}Wszystkie pliki niezmienione — CHECKSUMS już aktualny.${NC}"
    rm /tmp/sylion_checksums_tmp.sha256
    exit 0
  else
    echo -e "${YELLOW}${CHANGED} plików ze zmienioną zawartością.${NC}"
  fi
fi

# Zapisz lub wyświetl
if [ "${DRY_RUN}" = true ]; then
  echo ""
  echo -e "${YELLOW}[DRY-RUN] Poniżej zostałoby zapisane do ${OUTPUT_FILE}:${NC}"
  echo "---"
  cat /tmp/sylion_checksums_tmp.sha256
  echo "---"
  rm /tmp/sylion_checksums_tmp.sha256
  echo -e "${YELLOW}[DRY-RUN] Plik NIE został zapisany.${NC}"
else
  mv /tmp/sylion_checksums_tmp.sha256 "${OUTPUT_FILE}"
  echo ""
  echo -e "${GREEN}✓ Zapisano: ${OUTPUT_FILE}${NC}"

  # Natychmiastowa weryfikacja
  echo -e "${BLUE}Weryfikacja...${NC}"
  FAIL_COUNT=$(${SHA256_CHECK_CMD} "${OUTPUT_FILE}" 2>&1 | grep -c 'FAILED' || true)

  if [ "${FAIL_COUNT}" -eq 0 ]; then
    echo -e "${GREEN}✓ Weryfikacja OK — wszystkie ${LINES} pliki zgodne.${NC}"
  else
    echo -e "${RED}BŁĄD: ${FAIL_COUNT} pliki niezgodne po regeneracji!${NC}" >&2
    if [ "${STRICT}" = true ]; then
      exit 1
    fi
  fi
fi

echo ""
echo -e "${BLUE}[SYLION] CHECKSUMS regeneracja zakończona.${NC}"
