#!/usr/bin/env bash
# =============================================================================
# SYLION v5.9.2 â€” Linux/macOS Installer
# Audit: 2026-07-11 | R3.13: unified runtime entrypoint
#
# USAGE:
#   ./install_v592.sh                          # normal install
#   ./install_v592.sh --dry-run                # simulate â€” no writes
#   ./install_v592.sh --reinstall              # wipe venv+DB, fresh start
#   PYTHON_BIN=python3.12 ./install_v592.sh    # override interpreter
#   SYLION_PORT=8422      ./install_v592.sh    # override port
#   SYLION_DIR=/opt/sylion ./install_v592.sh   # override install root
#
# IDEMPOTENT: Safe to re-run; skips steps already complete.
# ROLLBACK:   On failure, venv is removed and DB is rolled back (.bak kept).
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Script-level constants
# ---------------------------------------------------------------------------
SCRIPT_VERSION="6.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${HOME}/sylion"
LOG_FILE="${LOG_DIR}/install.log"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# ---------------------------------------------------------------------------
# Runtime flags (set via CLI args below)
# ---------------------------------------------------------------------------
DRY_RUN=false
REINSTALL=false

# ---------------------------------------------------------------------------
# Configuration (override via environment variables)
# ---------------------------------------------------------------------------
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
REQ_FILE="${REQ_FILE:-requirements-lock.txt}"
AGENTS_YAML="${AGENTS_YAML:-agents.yaml}"
SYLION_PORT="${SYLION_PORT:-8421}"
HEALTH_URL="http://127.0.0.1:${SYLION_PORT}/health"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=11
MIN_DISK_MB=500
SETUP_TOKEN_FILE="SETUP_TOKEN.txt"

# ---------------------------------------------------------------------------
# Parse CLI arguments
# ---------------------------------------------------------------------------
parse_args() {
    for arg in "$@"; do
        case "$arg" in
            --dry-run)   DRY_RUN=true ;;
            --reinstall) REINSTALL=true ;;
            --help|-h)
                echo "Usage: $0 [--dry-run] [--reinstall] [--help]"
                echo ""
                echo "  --dry-run    Simulate all steps; no filesystem changes."
                echo "  --reinstall  Wipe venv + backup DB, then reinstall from scratch."
                exit 0
                ;;
            *)
                die "Unknown argument: $arg. Use --help for usage."
                ;;
        esac
    done
}

# ---------------------------------------------------------------------------
# Color output helpers (auto-disable if not a terminal)
# ---------------------------------------------------------------------------
if [[ -t 1 ]] && [[ "${TERM:-}" != "dumb" ]]; then
    _RED='\033[0;31m'
    _GRN='\033[0;32m'
    _YEL='\033[1;33m'
    _BLU='\033[0;34m'
    _MAG='\033[0;35m'
    _NC='\033[0m'
else
    _RED='' _GRN='' _YEL='' _BLU='' _MAG='' _NC=''
fi

# ---------------------------------------------------------------------------
# Logging: console + file
# ---------------------------------------------------------------------------
_setup_log() {
    if [[ "$DRY_RUN" == "false" ]]; then
        mkdir -p "${LOG_DIR}"
        # Tee all stdout+stderr into log file from this point forward
        exec > >(tee -a "${LOG_FILE}") 2>&1
    fi
}

log_info()  { echo -e "${_BLU}[INFO]${_NC}  $*"; }
log_ok()    { echo -e "${_GRN}[OK]${_NC}    $*"; }
log_warn()  { echo -e "${_YEL}[WARN]${_NC}  $*"; }
log_error() { echo -e "${_RED}[ERROR]${_NC} $*" >&2; }
log_dry()   { echo -e "${_MAG}[DRY]${_NC}   $*"; }
die()       { log_error "$*"; exit 1; }

# Wraps a command: in dry-run, just prints it; otherwise executes it.
run() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would run: $*"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Rollback handler (registered via trap)
# ---------------------------------------------------------------------------
_ROLLBACK_VENV=false
_ROLLBACK_DB_BAK=""

_rollback() {
    local rc=$?
    if [[ $rc -ne 0 ]]; then
        log_error "Installation failed (exit code ${rc}). Running rollback..."
        if [[ "$_ROLLBACK_VENV" == "true" && -d "${VENV_DIR}" ]]; then
            log_warn "Removing partially created venv: ${VENV_DIR}"
            rm -rf "${VENV_DIR}"
        fi
        if [[ -n "$_ROLLBACK_DB_BAK" && -f "${_ROLLBACK_DB_BAK}" ]]; then
            log_warn "Restoring DB from backup: ${_ROLLBACK_DB_BAK}"
            cp "${_ROLLBACK_DB_BAK}" "dashboard/sylion.db" 2>/dev/null || true
        fi
        log_error "Rollback complete. Check ${LOG_FILE} for details."
    fi
}
trap '_rollback' EXIT

# ---------------------------------------------------------------------------
# Preflight: Python version check
# ---------------------------------------------------------------------------
preflight_python() {
    log_info "Preflight: checking Python interpreter..."

    local found_bin=""
    for candidate in "$PYTHON_BIN" python3.12 python3.11 python3; do
        if command -v "$candidate" &>/dev/null; then
            found_bin="$candidate"
            break
        fi
    done

    [[ -z "$found_bin" ]] && die "No Python interpreter found. Install Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+."

    PYTHON_BIN="$found_bin"

    local version_str major minor
    version_str=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    major=$(echo "$version_str" | cut -d. -f1)
    minor=$(echo "$version_str" | cut -d. -f2)

    if [[ "$major" -lt "$MIN_PYTHON_MAJOR" ]] || \
       [[ "$major" -eq "$MIN_PYTHON_MAJOR" && "$minor" -lt "$MIN_PYTHON_MINOR" ]]; then
        die "Python ${version_str} < ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}. Install a newer Python."
    fi

    log_ok "Python ${version_str} at $(command -v "$PYTHON_BIN")"
}

# ---------------------------------------------------------------------------
# Preflight: pip availability
# ---------------------------------------------------------------------------
preflight_pip() {
    log_info "Preflight: checking pip availability..."
    "$PYTHON_BIN" -m pip --version &>/dev/null \
        || die "pip not available for $PYTHON_BIN. Run: $PYTHON_BIN -m ensurepip"
    log_ok "pip is available."
}

# ---------------------------------------------------------------------------
# Preflight: disk space (>=500 MB free)
# ---------------------------------------------------------------------------
preflight_disk() {
    log_info "Preflight: checking disk space (>=${MIN_DISK_MB} MB required)..."
    local free_kb
    free_kb=$(df -k "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    local free_mb=$(( free_kb / 1024 ))
    if [[ "$free_mb" -lt "$MIN_DISK_MB" ]]; then
        die "Insufficient disk space: ${free_mb} MB free, need ${MIN_DISK_MB} MB."
    fi
    log_ok "Disk space OK: ${free_mb} MB free."
}

# ---------------------------------------------------------------------------
# --reinstall: wipe venv and backup existing DB
# ---------------------------------------------------------------------------
handle_reinstall() {
    if [[ "$REINSTALL" == "false" ]]; then return 0; fi

    log_warn "--reinstall: removing existing venv (${VENV_DIR})..."
    run rm -rf "${VENV_DIR}"

    local db_path="dashboard/sylion.db"
    if [[ -f "$db_path" ]]; then
        local bak_path="dashboard/sylion.db.bak.v${SCRIPT_VERSION}_${TIMESTAMP}"
        log_warn "--reinstall: backing up DB to ${bak_path}"
        run cp "$db_path" "$bak_path"
        _ROLLBACK_DB_BAK="$bak_path"
        run rm -f "$db_path"
        log_ok "DB backed up to: ${bak_path}"
    fi
}

# ---------------------------------------------------------------------------
# Step 1: Create virtual environment (idempotent)
# ---------------------------------------------------------------------------
create_venv() {
    log_info "Setting up virtual environment at: ${VENV_DIR}"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would create venv at ${VENV_DIR} with $PYTHON_BIN"
        return 0
    fi

    if [[ -d "${VENV_DIR}" ]]; then
        if "${VENV_DIR}/bin/python" -c "import sys" &>/dev/null; then
            log_ok "Venv already exists and is functional â€” skipping."
            return 0
        else
            log_warn "Existing venv appears broken. Recreating..."
            rm -rf "${VENV_DIR}"
        fi
    fi

    _ROLLBACK_VENV=true
    "$PYTHON_BIN" -m venv "${VENV_DIR}"
    _ROLLBACK_VENV=false  # Venv created OK; keep it even on later failure
    log_ok "Virtual environment created."
}

# ---------------------------------------------------------------------------
# Step 2: Install dependencies from requirements-lock.txt (hash-verified)
# ---------------------------------------------------------------------------
install_deps() {
    log_info "Installing dependencies from ${REQ_FILE}..."

    [[ -f "${REQ_FILE}" ]] || die "Requirements file not found: ${REQ_FILE}"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would run: pip install --require-hashes -r ${REQ_FILE}"
        return 0
    fi

    # Upgrade pip silently
    "${VENV_DIR}/bin/pip" install --quiet --upgrade pip

    # Prefer hash-verified install; fall back if lockfile has no hashes
    if grep -q "sha256:" "${REQ_FILE}" 2>/dev/null; then
        log_info "Hash verification mode (--require-hashes) enabled."
        "${VENV_DIR}/bin/pip" install \
            --quiet \
            --require-hashes \
            --no-cache-dir \
            -r "${REQ_FILE}" \
            || die "Dependency installation failed (hash mismatch or network error)."
    else
        log_warn "No sha256 hashes found in ${REQ_FILE} â€” installing without hash verification."
        log_warn "Run pip-compile --generate-hashes to add hashes for security."
        "${VENV_DIR}/bin/pip" install \
            --quiet \
            --no-cache-dir \
            -r "${REQ_FILE}" \
            || die "Dependency installation failed."
    fi

    log_ok "Dependencies installed."
}

# ---------------------------------------------------------------------------
# Step 3: Initialize runtime database placeholder (idempotent)
# ---------------------------------------------------------------------------
init_database() {
    log_info "Preparing unified runtime database path..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would prepare ${SYLION_DB_PATH:-${HOME}/sylion/sylion_aeis.db}"
        return 0
    fi

    local db_path="${SYLION_DB_PATH:-${HOME}/sylion/sylion_aeis.db}"
    mkdir -p "$(dirname "${db_path}")"
    touch "${db_path}" || die "Database path preparation failed: ${db_path}"
    export SYLION_DB_PATH="${db_path}"

    log_ok "Runtime database path ready: ${SYLION_DB_PATH}"
}

# ---------------------------------------------------------------------------
# Step 4: (v6.0.0 T-01) No setup token generated â€” Create First Account flow
# ---------------------------------------------------------------------------
generate_setup_token() {
    # v6.0.0 T-01: SETUP_TOKEN.txt is no longer generated by the installer.
    # The first account is created directly via the browser UI at /.
    # Remove any stale SETUP_TOKEN.txt from a previous v5.x installation.
    if [[ -f "${SETUP_TOKEN_FILE}" ]]; then
        log_info "Removing stale SETUP_TOKEN.txt from previous installation (v6.0.0 T-01)..."
        if [[ "$DRY_RUN" != "true" ]]; then
            rm -f "${SETUP_TOKEN_FILE}"
            log_ok "Stale SETUP_TOKEN.txt removed."
        else
            log_dry "Would remove ${SETUP_TOKEN_FILE}"
        fi
    fi
    log_ok "v6.0.0: No setup token needed. Open http://127.0.0.1:${SYLION_PORT}/ to create the first account."
}

# ---------------------------------------------------------------------------
# Step 5: Seed agents from agents.yaml (idempotent via upsert)
# ---------------------------------------------------------------------------
seed_agents() {
    log_info "Seeding agents from ${AGENTS_YAML}..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would skip legacy dashboard agent seeding"
        return 0
    fi

    if [[ ! -f "${AGENTS_YAML}" ]]; then
        log_warn "agents.yaml not found â€” skipping agent seeding."
        return 0
    fi

    log_warn "Legacy dashboard agent seeding removed in R3.13; unified runtime bootstraps agents separately."
}

# ---------------------------------------------------------------------------
# Step 6: Healthcheck (non-fatal; server may be started separately)
# ---------------------------------------------------------------------------
healthcheck() {
    log_info "Healthcheck: ${HEALTH_URL} (5 attempts, 3s apart)..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would poll: ${HEALTH_URL}"
        return 0
    fi

    if ! command -v curl &>/dev/null; then
        log_warn "curl not found â€” skipping healthcheck. Verify: ${HEALTH_URL}"
        return 0
    fi

    local i=0 retries=5 delay=3
    while [[ $i -lt $retries ]]; do
        local http_code
        http_code=$(curl -sf -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || true)
        if [[ "$http_code" == "200" ]]; then
            log_ok "Healthcheck passed (HTTP 200)."
            return 0
        fi
        i=$(( i + 1 ))
        log_warn "Attempt ${i}/${retries}: HTTP ${http_code:-no response}. Retrying in ${delay}s..."
        sleep "$delay"
    done

    log_warn "Healthcheck not passed â€” server may not be running yet."
    log_warn "Start server: source ${VENV_DIR}/bin/activate && python -m sylion.server --host 127.0.0.1 --http-port ${SYLION_PORT}"
}

# ---------------------------------------------------------------------------
# Print next-steps banner
# ---------------------------------------------------------------------------
print_next_steps() {
    # v6.0.0 T-01: no setup token hint needed â€” Create First Account via UI
    echo ""
    echo "============================================================"
    log_ok "SYLION v${SCRIPT_VERSION} installation complete."
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "  ${_MAG}[DRY-RUN] No changes were made.${_NC}"
    fi
    echo ""
    echo "  NEXT STEPS:"
    echo "  1. Activate environment:  source ${VENV_DIR}/bin/activate"
    echo "  2. Start server:          python -m sylion.server --host 127.0.0.1 --http-port ${SYLION_PORT}"
    echo "  3. Open in browser:       http://127.0.0.1:${SYLION_PORT}/"
    echo "  4. Create first account:  Enter username + password (no token needed)"
    echo "  5. Health URL:            ${HEALTH_URL}"
    echo ""
    echo "  Log file: ${LOG_FILE}"
    echo "============================================================"
    echo ""
}

# ---------------------------------------------------------------------------
# DEFECT-B06 fix: _setup_nohup â€” start server in background with correct dir
# ---------------------------------------------------------------------------
_setup_nohup() {
    local install_dir="${1:-${SCRIPT_DIR}}"
    local port="${2:-${SYLION_PORT}}"
    local log_out="${LOG_DIR}/sylion-server.log"
    mkdir -p "${LOG_DIR}"
    log_info "Starting SYLION server via nohup (DEFECT-B06 fix: cd to install dir first)..."
    # DEFECT-B06: must cd to install dir so module resolution uses project root.
    (
        cd "${install_dir}" || { log_warn "Cannot cd to ${install_dir}"; return 1; }
        source "${VENV_DIR}/bin/activate"
        nohup python -m sylion.server --host 127.0.0.1 --http-port "${port}" >> "${log_out}" 2>&1 &
        echo $! > "${LOG_DIR}/sylion.pid"
        log_ok "Server started (PID $!). Log: ${log_out}"
    )
}

# ---------------------------------------------------------------------------
# PATCH 3 / RC-03 / SYL-PIX-002: Install udev rules for Google Pixel (VID=18d1)
# ---------------------------------------------------------------------------
install_udev_rules() {
    local RULES_SRC="$(dirname "$0")/templates/51-android.rules"
    local RULES_DST="/etc/udev/rules.d/51-android.rules"
    if [ ! -f "$RULES_DST" ]; then
        echo "[INSTALL] Kopiowanie udev rules dla Google Pixel (VID=18d1)"
        sudo cp "$RULES_SRC" "$RULES_DST"
        sudo chmod 644 "$RULES_DST"
        sudo udevadm control --reload-rules && sudo udevadm trigger
        sudo usermod -aG plugdev "$USER"
        echo "[INSTALL] Wyloguj i zaloguj ponownie (zmiana grupy plugdev)"
    fi
}

# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"
    _setup_log

    echo ""
    echo "============================================================"
    echo "  SYLION v${SCRIPT_VERSION} â€” Installer (Linux/macOS)"
    if [[ "$DRY_RUN" == "true" ]];   then echo "  MODE: DRY-RUN (no changes will be made)"; fi
    if [[ "$REINSTALL" == "true" ]]; then echo "  MODE: REINSTALL (wipe + fresh install)"; fi
    echo "  Log: ${LOG_FILE}"
    echo "============================================================"
    echo ""

    cd "${SCRIPT_DIR}"

    # Preflight checks
    preflight_python
    preflight_pip
    preflight_disk

    # Reinstall prep
    handle_reinstall

    # Install steps
    install_udev_rules
    create_venv
    install_deps
    init_database
    generate_setup_token
    seed_agents
    healthcheck

    print_next_steps
}

main "$@"
