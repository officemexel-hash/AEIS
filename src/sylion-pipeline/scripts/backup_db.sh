#!/usr/bin/env bash
# =============================================================================
# backup_db.sh — SYLION AEIS Runtime SQLite Backup Script
# =============================================================================
# Wersja:  1.0.0
# Patch:   P8-BACKUP-SCRIPT (CP-6 WARN naprawa)
# Projekt: SYLION v5.9.3
#
# Opis:
#   Idempotentny skrypt backup bazy SQLite runtime AEIS.
#   Używa SQLite Online Backup API (sqlite3 .backup) — bezpieczne dla
#   działającej bazy (WAL-aware, nie blokuje writerów).
#
# Exit codes:
#   0 — sukces
#   1 — pre-flight fail (brak narzędzi, brak źródła, brak miejsca)
#   2 — backup fail (błąd sqlite3 .backup lub gzip)
#   3 — rotation fail (błąd usuwania starych plików)
#
# Zmienne środowiskowe (opcjonalne, mają wartości domyślne):
#   SYLION_DB_PATH     — ścieżka do SQLite DB
#                        (default: /var/lib/sylion/sylion_aeis.db)
#   SYLION_BACKUP_DIR  — katalog docelowy backup
#                        (default: /var/backups/sylion)
#   SYLION_BACKUP_KEEP_DAILY    — liczba codziennych (default: 7)
#   SYLION_BACKUP_KEEP_WEEKLY   — liczba tygodniowych (default: 4)
#   SYLION_BACKUP_KEEP_MONTHLY  — liczba miesięcznych (default: 6)
#
# Przykład użycia:
#   ./backup_db.sh
#   SYLION_DB_PATH=/srv/app/sylion_aeis.db ./backup_db.sh
#   SYLION_BACKUP_DIR=/mnt/nas/backups ./backup_db.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Konfiguracja
# ---------------------------------------------------------------------------
readonly SOURCE_DB="${SYLION_DB_PATH:-/var/lib/sylion/sylion_aeis.db}"
readonly BACKUP_BASE_DIR="${SYLION_BACKUP_DIR:-/var/backups/sylion}"
readonly BACKUP_DAILY_DIR="${BACKUP_BASE_DIR}/daily"
readonly BACKUP_WEEKLY_DIR="${BACKUP_BASE_DIR}/weekly"
readonly BACKUP_MONTHLY_DIR="${BACKUP_BASE_DIR}/monthly"

readonly KEEP_DAILY="${SYLION_BACKUP_KEEP_DAILY:-7}"
readonly KEEP_WEEKLY="${SYLION_BACKUP_KEEP_WEEKLY:-4}"
readonly KEEP_MONTHLY="${SYLION_BACKUP_KEEP_MONTHLY:-6}"

readonly TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
readonly BACKUP_FILENAME="sylion_aeis_${TIMESTAMP}.db.gz"

readonly SCRIPT_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
readonly T0="$(date +%s)"

# ---------------------------------------------------------------------------
# Funkcje pomocnicze
# ---------------------------------------------------------------------------

# log_json — emituje linię JSON do stdout (kompatybilne z journald)
log_json() {
    local level="$1"
    shift
    # Buduj pola klucz=wartość jako JSON
    local pairs=""
    local key val
    while [[ $# -ge 2 ]]; do
        key="$1"
        val="$2"
        shift 2
        # Escapuj cudzysłowy w wartości
        val="${val//\\/\\\\}"
        val="${val//\"/\\\"}"
        if [[ -z "$pairs" ]]; then
            pairs="\"${key}\":\"${val}\""
        else
            pairs="${pairs},\"${key}\":\"${val}\""
        fi
    done
    echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"level\":\"${level}\",${pairs}}"
}

# duration_s — oblicza sekundy od T0
duration_s() {
    echo $(( $(date +%s) - T0 ))
}

# preflight_fail — log + exit 1
preflight_fail() {
    log_json "ERROR" "event" "preflight_failed" "reason" "$1"
    exit 1
}

# backup_fail — log + exit 2
backup_fail() {
    log_json "ERROR" "event" "backup_failed" "reason" "$1" "duration_s" "$(duration_s)"
    exit 2
}

# rotation_fail — log + exit 3
rotation_fail() {
    log_json "ERROR" "event" "rotation_failed" "reason" "$1" "duration_s" "$(duration_s)"
    exit 3
}

# ---------------------------------------------------------------------------
# FAZA 1: Pre-flight checks (exit 1)
# ---------------------------------------------------------------------------
log_json "INFO" "event" "backup_start" "db" "${SOURCE_DB}" "backup_dir" "${BACKUP_BASE_DIR}" "ts_start" "${SCRIPT_START}"

# Sprawdź narzędzia
if ! command -v sqlite3 >/dev/null 2>&1; then
    preflight_fail "sqlite3 not found in PATH"
fi

if ! command -v gzip >/dev/null 2>&1; then
    preflight_fail "gzip not found in PATH"
fi

# Sprawdź istnienie źródłowej bazy
if [[ ! -f "${SOURCE_DB}" ]]; then
    preflight_fail "source DB not found: ${SOURCE_DB}"
fi

# Sprawdź czytelność
if [[ ! -r "${SOURCE_DB}" ]]; then
    preflight_fail "source DB not readable: ${SOURCE_DB}"
fi

# Sprawdź integralność bazy (szybka weryfikacja)
INTEGRITY_RESULT="$(sqlite3 "${SOURCE_DB}" "PRAGMA integrity_check;" 2>&1 || true)"
if [[ "${INTEGRITY_RESULT}" != "ok" ]]; then
    preflight_fail "source DB integrity_check failed: ${INTEGRITY_RESULT}"
fi

# Sprawdź dostępne miejsce (wymagane: min. 2× rozmiar DB dla temp + gzip)
DB_SIZE_KB="$(du -k "${SOURCE_DB}" | cut -f1)"
AVAIL_KB="$(df -k "${BACKUP_BASE_DIR%/*}" 2>/dev/null | awk 'NR==2{print $4}' || echo 999999)"
REQUIRED_KB=$(( DB_SIZE_KB * 2 + 1024 ))
if [[ "${AVAIL_KB}" -lt "${REQUIRED_KB}" ]]; then
    preflight_fail "insufficient disk space: available=${AVAIL_KB}KB required=${REQUIRED_KB}KB"
fi

# Utwórz katalogi backup (idempotentne)
mkdir -p "${BACKUP_DAILY_DIR}" "${BACKUP_WEEKLY_DIR}" "${BACKUP_MONTHLY_DIR}" || \
    preflight_fail "cannot create backup directories under ${BACKUP_BASE_DIR}"

log_json "INFO" "event" "preflight_ok" "db_size_kb" "${DB_SIZE_KB}" "avail_kb" "${AVAIL_KB}"

# ---------------------------------------------------------------------------
# FAZA 2: Backup (exit 2)
# ---------------------------------------------------------------------------

# Plik tymczasowy w tym samym systemie plików co docelowy (gwarantuje atomowe mv)
TMPFILE="$(mktemp "${BACKUP_DAILY_DIR}/backup_tmp_XXXXXX")"
# Cleanup trap — usuń TMPFILE przy błędzie/przerwaniu
trap 'rm -f "${TMPFILE}" "${TMPFILE}.gz" 2>/dev/null || true' EXIT

log_json "INFO" "event" "sqlite_backup_start" "tmpfile" "${TMPFILE}"

# sqlite3 .backup — Online Backup API: WAL-aware, nie blokuje writerów
if ! sqlite3 "${SOURCE_DB}" ".backup '${TMPFILE}'" 2>&1; then
    backup_fail "sqlite3 .backup command failed"
fi

# Sprawdź czy plik został faktycznie utworzony
if [[ ! -f "${TMPFILE}" ]]; then
    backup_fail "backup temp file missing after sqlite3 .backup"
fi

# Weryfikacja poprawności backup (quick check na kopii)
BACKUP_INTEGRITY="$(sqlite3 "${TMPFILE}" "PRAGMA integrity_check;" 2>&1 || true)"
if [[ "${BACKUP_INTEGRITY}" != "ok" ]]; then
    backup_fail "backup file integrity_check failed: ${BACKUP_INTEGRITY}"
fi

# Kompresja gzip -9
if ! gzip -9 "${TMPFILE}" 2>&1; then
    backup_fail "gzip compression failed for ${TMPFILE}"
fi

# Po gzip plik ma rozszerzenie .gz
if [[ ! -f "${TMPFILE}.gz" ]]; then
    backup_fail "compressed backup file missing after gzip"
fi

# Atomowy move do katalogu daily
FINAL_PATH="${BACKUP_DAILY_DIR}/${BACKUP_FILENAME}"
if ! mv "${TMPFILE}.gz" "${FINAL_PATH}"; then
    backup_fail "mv failed: ${TMPFILE}.gz -> ${FINAL_PATH}"
fi

# Reset trap — plik jest już na miejscu, nie usuwaj
trap - EXIT

FINAL_SIZE="$(du -k "${FINAL_PATH}" | cut -f1)"
log_json "INFO" "event" "backup_complete" \
    "file" "${BACKUP_FILENAME}" \
    "path" "${FINAL_PATH}" \
    "size_kb" "${FINAL_SIZE}" \
    "duration_s" "$(duration_s)"

# ---------------------------------------------------------------------------
# FAZA 3: Promocja do weekly / monthly (na podstawie daty)
# ---------------------------------------------------------------------------

DOW="$(date -u +%u)"      # 1=poniedziałek ... 7=niedziela
DOM="$(date -u +%d)"      # dzień miesiąca (01-31)

# Weekly: co niedzielę (DOW=7) — skopiuj najnowszy daily do weekly
if [[ "${DOW}" == "7" ]]; then
    WEEKLY_FILE="${BACKUP_WEEKLY_DIR}/${BACKUP_FILENAME}"
    if cp "${FINAL_PATH}" "${WEEKLY_FILE}" 2>/dev/null; then
        log_json "INFO" "event" "weekly_promoted" "file" "${BACKUP_FILENAME}"
    else
        log_json "WARN" "event" "weekly_promote_failed" "file" "${BACKUP_FILENAME}"
    fi
fi

# Monthly: pierwszego dnia miesiąca (DOM=01) — skopiuj do monthly
if [[ "${DOM}" == "01" ]]; then
    MONTHLY_FILE="${BACKUP_MONTHLY_DIR}/${BACKUP_FILENAME}"
    if cp "${FINAL_PATH}" "${MONTHLY_FILE}" 2>/dev/null; then
        log_json "INFO" "event" "monthly_promoted" "file" "${BACKUP_FILENAME}"
    else
        log_json "WARN" "event" "monthly_promote_failed" "file" "${BACKUP_FILENAME}"
    fi
fi

# ---------------------------------------------------------------------------
# FAZA 4: Rotacja (exit 3)
# ---------------------------------------------------------------------------

rotate_dir() {
    local dir="$1"
    local keep="$2"
    local label="$3"

    # Policz istniejące pliki backup (sortowane od najnowszego)
    local count
    count="$(find "${dir}" -maxdepth 1 -name "sylion_aeis_*.db.gz" 2>/dev/null | wc -l)"

    if [[ "${count}" -le "${keep}" ]]; then
        log_json "INFO" "event" "rotation_skip" "dir" "${label}" "count" "${count}" "keep" "${keep}"
        return 0
    fi

    # Usuń najstarsze (keep N najnowszych)
    local to_delete
    to_delete="$(find "${dir}" -maxdepth 1 -name "sylion_aeis_*.db.gz" \
        | sort \
        | head -n $(( count - keep )))"

    local deleted=0
    local failed=0
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        if rm -f "$f" 2>/dev/null; then
            (( deleted++ )) || true
            log_json "INFO" "event" "rotation_deleted" "dir" "${label}" "file" "$(basename "$f")"
        else
            (( failed++ )) || true
            log_json "WARN" "event" "rotation_delete_failed" "dir" "${label}" "file" "$(basename "$f")"
        fi
    done <<< "${to_delete}"

    if [[ "${failed}" -gt 0 ]]; then
        rotation_fail "failed to delete ${failed} file(s) in ${label}"
    fi

    log_json "INFO" "event" "rotation_done" "dir" "${label}" "deleted" "${deleted}" "remaining" "$(( count - deleted ))"
}

rotate_dir "${BACKUP_DAILY_DIR}"   "${KEEP_DAILY}"   "daily"   || rotation_fail "daily rotation error"
rotate_dir "${BACKUP_WEEKLY_DIR}"  "${KEEP_WEEKLY}"  "weekly"  || rotation_fail "weekly rotation error"
rotate_dir "${BACKUP_MONTHLY_DIR}" "${KEEP_MONTHLY}" "monthly" || rotation_fail "monthly rotation error"

# ---------------------------------------------------------------------------
# Sukces
# ---------------------------------------------------------------------------
log_json "INFO" "event" "backup_success" \
    "file" "${BACKUP_FILENAME}" \
    "keep_daily" "${KEEP_DAILY}" \
    "keep_weekly" "${KEEP_WEEKLY}" \
    "keep_monthly" "${KEEP_MONTHLY}" \
    "total_duration_s" "$(duration_s)"

exit 0
