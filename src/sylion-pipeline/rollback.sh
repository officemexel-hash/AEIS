#!/usr/bin/env bash
# =============================================================================
# SYLION — Rollback Script (WAL-integrity merge)
#
# Base:    snapshot_0052/rollback.sh (326 lines, v5.9.1 rewrite)
# Merged:  + LATEST features (version-based backup selection, pgrep stop)
#          + ADR-0017 requirements (pidfile guard, WAL checkpoint, exit codes)
#
# USAGE:
#   ./rollback.sh [OPTIONS]
#
# OPTIONS:
#   --dry-run           Print planned actions without executing; zero FS writes
#   --force             Override pidfile guard (dangerous; document your reason)
#   --version <ver>     Select backup for version <ver> (e.g. 5.9.0)
#   --backup-glob <g>   Override glob for finding DB backup
#   --prev-pkg <zip>    Path to previous-version package zip
#   --db-file <path>    Path to the live SQLite DB
#   --service-name <u>  systemd unit name to stop/start (default: sylion)
#   -h, --help          Show this help and exit
#
# EXIT CODES:
#   0  success
#   1  usage / pre-flight failure (missing backup, missing sqlite3, …)
#   2  live DB or backup DB corrupted (integrity_check failed on source)
#   3  integrity check on restored DB failed (live DB untouched)
#   4  pidfile held — another rollback is running (use --force to override)
#
# ADR-0017 compliance:
#   [A1] Pidfile guard    → Step 0 (line ~120)
#   [A2] WAL checkpoint   → Step 4b (line ~230)  — before safety snapshot
#   [A3] integrity_check  → Step 2  (line ~190)  — on backup before restore
#                        → Step 5  (line ~260)  — on restored tmp after cp
#   [A4] dry-run flag     → throughout (exec_cmd / exec_shell helpers)
#   [A5] Log file         → ~/sylion/logs/rollback_YYYYMMDD_HHMMSS.log
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults  (SNAPSHOT base + LATEST version arg)
# ---------------------------------------------------------------------------
DRY_RUN=0
FORCE=0
VERSION_ARG=""                                     # NEW (from LATEST)
BACKUP_GLOB="${BACKUP_GLOB:-}"                     # resolved below if empty
PREV_VERSION="5.8.8.1"
PREV_PKG="${PREV_PKG:-../sylion-v5.8.8.1.zip}"
VENV_DIR="${VENV_DIR:-.venv}"
DB_FILE="${DB_FILE:-}"
SERVICE_NAME="${SERVICE_NAME:-sylion}"
SYLION_PORT="${SYLION_PORT:-8421}"
HEALTH_URL="http://127.0.0.1:${SYLION_PORT}/api/health"
SYLION_HOME="${SYLION_HOME:-$HOME/sylion}"
PID_FILE="${SYLION_HOME}/sylion.pid"               # ADR-0017 [A1]
LOG_DIR="${SYLION_HOME}/logs"                      # ADR-0017 [A5]

# ---------------------------------------------------------------------------
# Argument parsing  (must run BEFORE any filesystem write — F-005)
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)        DRY_RUN=1; shift ;;
        --force)          FORCE=1; shift ;;
        --version)        VERSION_ARG="$2"; shift 2 ;;  # from LATEST
        --backup-glob)    BACKUP_GLOB="$2"; shift 2 ;;
        --prev-pkg)       PREV_PKG="$2"; shift 2 ;;
        --db-file)        DB_FILE="$2"; shift 2 ;;
        --service-name)   SERVICE_NAME="$2"; shift 2 ;;
        -h|--help)
            sed -n '1,34p' "$0"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# If --version was supplied (LATEST style), derive the backup glob from it.
if [[ -n "$VERSION_ARG" && -z "$BACKUP_GLOB" ]]; then
    BACKUP_GLOB="sylion.db.bak.v${VERSION_ARG}.*.sqlite3"
fi
# Fall back to snapshot default.
BACKUP_GLOB="${BACKUP_GLOB:-sylion.db.bak.v5.9.*.sqlite3}"

# ---------------------------------------------------------------------------
# Colour / logging helpers  (F-005: no file I/O in dry-run)
# ---------------------------------------------------------------------------
_RED='\033[0;31m'; _GRN='\033[0;32m'; _YEL='\033[1;33m'
_BLU='\033[0;34m'; _CYN='\033[0;36m'; _NC='\033[0m'

ROLLBACK_LOG=""
_log_to_file() {
    [[ -n "$ROLLBACK_LOG" ]] && echo "$*" >> "$ROLLBACK_LOG" 2>/dev/null || true
}

log_info()  { echo -e "${_BLU}[INFO]${_NC}  $*";    _log_to_file "[INFO]  $*"; }
log_ok()    { echo -e "${_GRN}[OK]${_NC}    $*";    _log_to_file "[OK]    $*"; }
log_warn()  { echo -e "${_YEL}[WARN]${_NC}  $*";    _log_to_file "[WARN]  $*"; }
log_error() { echo -e "${_RED}[ERROR]${_NC} $*" >&2; _log_to_file "[ERROR] $*"; }
log_dry()   { echo -e "${_CYN}[DRY-RUN]${_NC} $*"; }

# die_exit <code> <message>
die_exit() {
    local code="$1"; shift
    log_error "$*"
    exit "$code"
}

# exec_cmd: run unless dry-run.
exec_cmd() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_dry "$*"
    else
        "$@"
    fi
}

# exec_shell: pipeline-heavy one-liners only; trusted static strings.
exec_shell() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_dry "sh -c: $*"
    else
        bash -c "$*"
    fi
}

# ---------------------------------------------------------------------------
# Setup  (F-005: no writes until after dry-run guard)
# ---------------------------------------------------------------------------
cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ "$DRY_RUN" -eq 0 ]]; then
    mkdir -p "$LOG_DIR"
    ROLLBACK_LOG="${LOG_DIR}/rollback_$(date +%Y%m%d_%H%M%S).log"
    : > "$ROLLBACK_LOG"
fi

echo ""
echo "============================================================"
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  SYLION — Rollback [DRY RUN — zero filesystem writes]"
else
    echo "  SYLION — Rollback → v${PREV_VERSION}"
    echo "  Log: ${ROLLBACK_LOG}"
fi
echo "  Started: $(date --iso-8601=seconds)"
echo "============================================================"

# ---------------------------------------------------------------------------
# Step 0 — Pidfile guard  (ADR-0017 [A1])
# ---------------------------------------------------------------------------
log_info "STEP 0: Pidfile guard (ADR-0017 [A1])"

if [[ -f "$PID_FILE" ]]; then
    HELD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [[ "$FORCE" -eq 0 ]]; then
        log_error "Pidfile exists: $PID_FILE (pid=${HELD_PID:-unknown})"
        log_error "Another rollback may be in progress. Use --force to override."
        exit 4   # exit code 4 = pidfile held
    else
        log_warn "--force set; ignoring existing pidfile (pid=${HELD_PID:-unknown})"
    fi
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
    echo "$$" > "$PID_FILE"
    log_ok "Pidfile written: $PID_FILE (pid=$$)"
fi
# Ensure pidfile is cleaned up on exit (normal or error).
# shellcheck disable=SC2064
trap '[[ "$DRY_RUN" -eq 0 ]] && rm -f "$PID_FILE"' EXIT

# ---------------------------------------------------------------------------
# Step 1 — Pre-flight checks
# ---------------------------------------------------------------------------
log_info "STEP 1: Pre-flight checks"

command -v sqlite3 >/dev/null 2>&1 \
    || die_exit 1 "sqlite3 not found in PATH (required by ADR-0017)"

# Resolve DB_FILE if not given (F-004: known M-08 locations first).
if [[ -z "$DB_FILE" ]]; then
    for _cand in \
        "${SYLION_HOME}/sylion.db" \
        "${SYLION_HOME}/sylion_aeis.db" \
        "./sylion.db"
    do
        if [[ -f "$_cand" ]]; then
            DB_FILE="$_cand"
            break
        fi
    done
fi
[[ -n "$DB_FILE" && -f "$DB_FILE" ]] \
    || die_exit 1 "Live DB not found. Pass --db-file <path> explicitly."
log_info "DB file: $DB_FILE"

# ---------------------------------------------------------------------------
# Step 2 — Locate backup (F-004)
# ---------------------------------------------------------------------------
log_info "STEP 2: Locate backup (glob: $BACKUP_GLOB)"

BACKUP_FILE=""
for _sdir in "${SYLION_HOME}" "./backups" "." "/var/backups/sylion"; do
    [[ -d "$_sdir" ]] || continue
    # shellcheck disable=SC2012
    _cand=$(ls -1t "${_sdir}/"${BACKUP_GLOB} 2>/dev/null | head -n1 || true)
    if [[ -n "$_cand" && -f "$_cand" ]]; then
        BACKUP_FILE="$_cand"
        log_ok "Found backup: $BACKUP_FILE (in $_sdir)"
        break
    fi
done
[[ -n "$BACKUP_FILE" ]] \
    || die_exit 1 "No backup matching '$BACKUP_GLOB' found. Pass --backup-glob or --version to override."

# Quick integrity check on backup BEFORE touching anything (ADR-0017 [A3a]).
log_info "Verifying backup integrity (PRAGMA integrity_check) ..."
if sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -qx "ok"; then
    log_ok "Backup integrity: ok"
else
    die_exit 2 "Backup $BACKUP_FILE failed integrity_check. Aborting (no changes made)."
fi

# ---------------------------------------------------------------------------
# Step 3 — Stop service
# ---------------------------------------------------------------------------
log_info "STEP 3: Stop service '${SERVICE_NAME}'"

if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}.service"; then
    exec_cmd systemctl stop "$SERVICE_NAME" \
        || log_warn "systemctl stop returned non-zero (may already be stopped)"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        sleep 2
        if ss -ltnp 2>/dev/null | grep -q ":${SYLION_PORT}\b"; then
            log_warn "Port ${SYLION_PORT} still bound; attempting pkill uvicorn"
            pkill -f "uvicorn" 2>/dev/null || true
            sleep 2
        fi
    fi
else
    log_warn "systemd unit '$SERVICE_NAME' not found; trying pgrep fallback (from LATEST)"
    # LATEST: stop unified runtime process (pgrep-based)
    mapfile -t _DASH_PIDS < <(pgrep -f "python -m sylion.server" 2>/dev/null || true)
    if [[ "${#_DASH_PIDS[@]}" -gt 0 ]]; then
        log_info "Stopping unified runtime processes (pids=${_DASH_PIDS[*]})"
        for _pid in "${_DASH_PIDS[@]}"; do
            exec_cmd kill -TERM "$_pid" 2>/dev/null || true
        done
        if [[ "$DRY_RUN" -eq 0 ]]; then
            sleep 3
            for _pid in "${_DASH_PIDS[@]}"; do
                kill -9 "$_pid" 2>/dev/null || true
            done
        fi
    else
        exec_shell "pkill -f 'uvicorn.*dashboard' 2>/dev/null || true"
    fi
fi

# ---------------------------------------------------------------------------
# Step 4a — WAL checkpoint on the LIVE DB (ADR-0017 [A2])
# ---------------------------------------------------------------------------
log_info "STEP 4a: WAL checkpoint on live DB (ADR-0017 [A2])"

if [[ "$DRY_RUN" -eq 0 ]]; then
    _ckpt_out=$(sqlite3 "$DB_FILE" "PRAGMA wal_checkpoint(TRUNCATE);" 2>&1 || true)
    log_ok "WAL checkpoint result: ${_ckpt_out}"
else
    log_dry "sqlite3 $DB_FILE 'PRAGMA wal_checkpoint(TRUNCATE);'"
fi

# ---------------------------------------------------------------------------
# Step 4b — Safety snapshot of CURRENT state (rollback-of-rollback insurance)
# ---------------------------------------------------------------------------
SAFETY_TS=$(date +%Y%m%d_%H%M%S)
SAFETY_SNAPSHOT="${DB_FILE}.safety.pre-rollback.${SAFETY_TS}.sqlite3"
log_info "STEP 4b: Safety snapshot → $SAFETY_SNAPSHOT"

if [[ "$DRY_RUN" -eq 0 ]]; then
    sqlite3 "$DB_FILE" ".backup '${SAFETY_SNAPSHOT}'" \
        || die_exit 1 "Failed to create safety snapshot"
    log_ok "Safety snapshot created: $SAFETY_SNAPSHOT"
else
    log_dry "sqlite3 $DB_FILE .backup '$SAFETY_SNAPSHOT'"
fi

# ---------------------------------------------------------------------------
# Step 5 — Staged restore with PRAGMA integrity_check (ADR-0017 [A3b])
# ---------------------------------------------------------------------------
log_info "STEP 5: Staged restore → ${DB_FILE}.restore.tmp"

RESTORE_TMP="${DB_FILE}.restore.tmp"
if [[ "$DRY_RUN" -eq 0 ]]; then
    rm -f "$RESTORE_TMP" "${RESTORE_TMP}-wal" "${RESTORE_TMP}-shm"
    cp -a "$BACKUP_FILE" "$RESTORE_TMP"
    # Checkpoint tmp so it is self-contained before the atomic swap.
    sqlite3 "$RESTORE_TMP" "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null || true
    # Integrity check on the restored copy — abort if not "ok" (ADR-0017 [A3b]).
    if ! sqlite3 "$RESTORE_TMP" "PRAGMA integrity_check;" | grep -qx "ok"; then
        log_error "Restored DB failed integrity_check — live DB untouched."
        rm -f "$RESTORE_TMP" "${RESTORE_TMP}-wal" "${RESTORE_TMP}-shm"
        log_error "Safety snapshot preserved at: $SAFETY_SNAPSHOT"
        exit 3   # exit code 3 = integrity failed on restored DB
    fi
    log_ok "Restored DB passes integrity_check"
else
    log_dry "cp $BACKUP_FILE $RESTORE_TMP && sqlite3 wal_checkpoint + integrity_check"
fi

# ---------------------------------------------------------------------------
# Step 6 — Atomic swap + remove stale WAL/SHM
# ---------------------------------------------------------------------------
log_info "STEP 6: Atomic swap of $DB_FILE"

if [[ "$DRY_RUN" -eq 0 ]]; then
    # mv is atomic within same filesystem.
    mv -f "$RESTORE_TMP" "$DB_FILE"
    rm -f "${DB_FILE}-wal" "${DB_FILE}-shm"
    log_ok "DB swapped; stale WAL/SHM removed"
else
    log_dry "mv $RESTORE_TMP $DB_FILE && rm -f ${DB_FILE}-wal ${DB_FILE}-shm"
fi

# ---------------------------------------------------------------------------
# Step 7 — Restore code from previous package (optional)
# ---------------------------------------------------------------------------
log_info "STEP 7: Restore code from $PREV_PKG"

if [[ ! -f "$PREV_PKG" ]]; then
    log_warn "Previous package $PREV_PKG not found — code rollback skipped."
    log_warn "If only a DB rollback was needed, it is now complete."
else
    CODE_BACKUP="code.pre-rollback.${SAFETY_TS}.tar.gz"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        tar -czf "$CODE_BACKUP" \
            --exclude=".venv" --exclude="logs" --exclude="backups" \
            --exclude="*.sqlite3" --exclude="*.db" --exclude="*.db-*" \
            . || log_warn "Code backup tar returned non-zero"
        log_ok "Code backup: $CODE_BACKUP"
        _STAGE=$(mktemp -d)
        unzip -q "$PREV_PKG" -d "$_STAGE"
        _PKG_ROOT=$(find "$_STAGE" -maxdepth 2 -name VERSION -type f -printf '%h\n' | head -n1)
        [[ -n "$_PKG_ROOT" ]] || die_exit 1 "Could not locate VERSION inside $PREV_PKG"
        cp -a "${_PKG_ROOT}/." ./ 2>/dev/null || true
        rm -rf "$_STAGE"
        log_ok "Code restored from $PREV_PKG"
    else
        log_dry "tar backup current code → $CODE_BACKUP; unzip $PREV_PKG over tree"
    fi
fi

# ---------------------------------------------------------------------------
# Step 8 — Restart service and verify health
# ---------------------------------------------------------------------------
log_info "STEP 8: Restart service and verify health"

if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}.service"; then
    exec_cmd systemctl start "$SERVICE_NAME"
else
    log_warn "No systemd unit — restart manually (e.g. python -m sylion.server --host 127.0.0.1 --http-port ${SYLION_PORT})"
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
    _HEALTHY=0
    for _i in $(seq 1 30); do
        if curl -fsS -m 2 "$HEALTH_URL" >/dev/null 2>&1; then
            _HEALTHY=1
            break
        fi
        sleep 1
    done
    if [[ "$_HEALTHY" -eq 1 ]]; then
        log_ok "Service healthy at $HEALTH_URL"
    else
        log_error "Service did not become healthy within 30s."
        log_error "Safety snapshot of pre-rollback state: $SAFETY_SNAPSHOT"
        exit 3
    fi
else
    log_dry "curl -fsS $HEALTH_URL (with 30s retry)"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Rollback to v${PREV_VERSION} COMPLETE"
echo "  Safety snapshot (pre-rollback): $SAFETY_SNAPSHOT"
[[ -n "$ROLLBACK_LOG" ]] && echo "  Log: $ROLLBACK_LOG"
echo "  Finished: $(date --iso-8601=seconds)"
echo "============================================================"

exit 0
