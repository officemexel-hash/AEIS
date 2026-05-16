#!/usr/bin/env bash
# =============================================================================
# deploy_all.sh — Orkiestracja wdrożenia SYLION na wszystkie urządzenia
# Część potoku audytu SYLION
#
# Przeznaczenie:
#   Skrypt orkiestruje pełny cykl wdrożenia SYLION:
#   1. Buduje binarne artefakty (linux/amd64 dla routera, linux/arm64 dla Pixela)
#   2. Wdraża binarkę relay na router przez SSH
#   3. Wdraża aplikację SYLION na Pixel przez ADB
#   4. Uruchamia health check na obu urządzeniach
#   5. Raportuje status w formacie czytelnym dla agentów
#
# Użycie:
#   ./deploy_all.sh [--json] [--skip-build] [--skip-router] [--skip-pixel]
#                   [--router-ip <ip>] [--apk <ścieżka>] [--config <ścieżka>]
#
# Zmienne środowiskowe:
#   SYLION_ROUTER_IP    — adres IP routera (domyślnie: 192.168.1.1)
#   SYLION_SRC_DIR      — katalog źródłowy SYLION (domyślnie: ../.. od skryptu)
#   SYLION_APK_PATH     — ścieżka do APK SYLION (jeśli pre-skompilowany)
#   SYLION_CONFIG_PATH  — ścieżka do pliku konfiguracyjnego
#   SYLION_ADB_SERIAL   — numer seryjny Pixela (jeśli kilka urządzeń)
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# -----------------------------------------------------------------------------
# Tmpfs deploy-path warning (Fix 5 — v5.9.1)
# ROUTER_DEPLOY_PATH defaults to /tmp/sylion which is tmpfs on OpenWrt.
# All deployed files are lost on router reboot unless an alternate persistent
# path is provided via SYLION_ROUTER_DEPLOY_PATH.
# -----------------------------------------------------------------------------

echo "⚠  Router deploy path is /tmp/sylion (tmpfs) — data lost on router restart."
echo "   For persistent deploy, set SYLION_ROUTER_DEPLOY_PATH=/etc/sylion before running."

ROUTER_DEPLOY_PATH="${SYLION_ROUTER_DEPLOY_PATH:-/tmp/sylion}"
export ROUTER_DEPLOY_PATH

# -----------------------------------------------------------------------------
# Ścieżki i konfiguracja
# -----------------------------------------------------------------------------

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_DIR="${SYLION_LOG_DIR:-${SCRIPT_DIR}/logs}"
readonly LOG_FILE="${LOG_DIR}/deploy_all_$(date +%Y%m%d_%H%M%S).log"

# Załaduj managery urządzeń
# shellcheck source=pixel_manager.sh
source "${SCRIPT_DIR}/pixel_manager.sh"
# shellcheck source=router_manager.sh
source "${SCRIPT_DIR}/router_manager.sh"

# Parametry wdrożenia
ROUTER_IP="${SYLION_ROUTER_IP:-192.168.1.1}"
SRC_DIR="${SYLION_SRC_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
BINARY_DIR="${LOG_DIR}/build"
ROUTER_BINARY="${BINARY_DIR}/sylion-relay-linux-amd64"
PIXEL_BINARY="${BINARY_DIR}/sylion-linux-arm64"
APK_PATH="${SYLION_APK_PATH:-}"
CONFIG_PATH="${SYLION_CONFIG_PATH:-}"

# Flagi sterujące
OUTPUT_JSON=false
SKIP_BUILD=false
SKIP_ROUTER=false
SKIP_PIXEL=false

# Wyniki kroków (do raportu końcowego)
declare -A STEP_RESULTS
DEPLOY_START_TIME="$(date +%s)"

# -----------------------------------------------------------------------------
# Kolory (wyłączane przez --json)
# -----------------------------------------------------------------------------

_init_colors() {
    if [[ -t 1 ]] && [[ "${OUTPUT_JSON}" == "false" ]]; then
        RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
        BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
    else
        RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; BOLD=''; RESET=''
    fi
}
_init_colors

# -----------------------------------------------------------------------------
# Funkcje logowania (nadpisanie wariantów z managerów, bo oba managerów je
# definiują — tutaj redefiniujemy z prefiksem deploy_all)
# -----------------------------------------------------------------------------

_ensure_log_dir() { mkdir -p "${LOG_DIR}"; }

_log() {
    _ensure_log_dir
    printf '[%s] [deploy_all] [%s] %s\n' \
        "$(date '+%Y-%m-%dT%H:%M:%S')" "$1" "$2" >> "${LOG_FILE}"
}

_info() {
    _log "INFO" "$1"
    [[ "${OUTPUT_JSON}" == "false" ]] && printf '%b[INFO]%b %s\n' "${GREEN}" "${RESET}" "$1"
}

_warn() {
    _log "WARN" "$1"
    [[ "${OUTPUT_JSON}" == "false" ]] && printf '%b[WARN]%b %s\n' "${YELLOW}" "${RESET}" "$1" >&2
}

_error() {
    _log "ERROR" "$1"
    [[ "${OUTPUT_JSON}" == "false" ]] && printf '%b[ERROR]%b %s\n' "${RED}" "${RESET}" "$1" >&2
}

_header() {
    _log "INFO" "=== $1 ==="
    [[ "${OUTPUT_JSON}" == "false" ]] && printf '\n%b╔══ %s ══╗%b\n' "${BOLD}${BLUE}" "$1" "${RESET}"
}

_step() {
    local step_name="$1"
    _log "INFO" "KROK: ${step_name}"
    [[ "${OUTPUT_JSON}" == "false" ]] && printf '\n%b  ▶ %s%b\n' "${BOLD}${CYAN}" "${step_name}" "${RESET}"
}

_step_ok() {
    local step_name="$1"
    STEP_RESULTS["${step_name}"]="ok"
    _log "INFO" "KROK OK: ${step_name}"
    [[ "${OUTPUT_JSON}" == "false" ]] && printf '%b  ✔ %s%b\n' "${GREEN}" "${step_name}" "${RESET}"
}

_step_fail() {
    local step_name="$1"
    local reason="${2:-błąd}"
    STEP_RESULTS["${step_name}"]="failed: ${reason}"
    _log "ERROR" "KROK NIEUDANY: ${step_name}: ${reason}"
    [[ "${OUTPUT_JSON}" == "false" ]] && printf '%b  ✖ %s: %s%b\n' "${RED}" "${step_name}" "${reason}" "${RESET}"
}

_step_skip() {
    local step_name="$1"
    STEP_RESULTS["${step_name}"]="skipped"
    _log "INFO" "KROK POMINIĘTY: ${step_name}"
    [[ "${OUTPUT_JSON}" == "false" ]] && printf '%b  ⊘ %s (pominięty)%b\n' "${YELLOW}" "${step_name}" "${RESET}"
}

# -----------------------------------------------------------------------------
# Parsowanie argumentów CLI
# -----------------------------------------------------------------------------

_parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                OUTPUT_JSON=true
                _init_colors
                ;;
            --skip-build)
                SKIP_BUILD=true
                ;;
            --skip-router)
                SKIP_ROUTER=true
                ;;
            --skip-pixel)
                SKIP_PIXEL=true
                ;;
            --router-ip)
                ROUTER_IP="${2:?'--router-ip wymaga adresu IP'}"
                shift
                ;;
            --apk)
                APK_PATH="${2:?'--apk wymaga ścieżki do APK'}"
                shift
                ;;
            --config)
                CONFIG_PATH="${2:?'--config wymaga ścieżki do pliku konfiguracyjnego'}"
                shift
                ;;
            -h|--help)
                _print_usage
                exit 0
                ;;
            *)
                _error "Nieznany argument: $1"
                _print_usage
                exit 1
                ;;
        esac
        shift
    done
}

_print_usage() {
    printf 'Użycie: %s [opcje]\n\n' "$(basename "$0")"
    printf 'Opcje:\n'
    printf '  --json              Wyjście w formacie JSON\n'
    printf '  --skip-build        Pomiń krok budowania binarek\n'
    printf '  --skip-router       Pomiń wdrożenie na router\n'
    printf '  --skip-pixel        Pomiń wdrożenie na Pixel\n'
    printf '  --router-ip <ip>    Adres IP routera (domyślnie: 192.168.1.1)\n'
    printf '  --apk <ścieżka>     Ścieżka do pre-skompilowanego APK\n'
    printf '  --config <ścieżka>  Ścieżka do pliku konfiguracyjnego\n'
    printf '  -h, --help          Wyświetl tę pomoc\n'
}

# -----------------------------------------------------------------------------
# Krok 1: Budowanie binarek SYLION
# -----------------------------------------------------------------------------

step_build() {
    local step="build"
    _step "Budowanie binarek SYLION"

    if [[ "${SKIP_BUILD}" == "true" ]]; then
        _step_skip "${step}"
        return 0
    fi

    mkdir -p "${BINARY_DIR}"

    # Sprawdź czy istnieje plik go.mod (zakładamy projekt Go)
    if [[ ! -f "${SRC_DIR}/go.mod" ]] && [[ ! -f "${SRC_DIR}/Makefile" ]]; then
        _warn "Nie znaleziono go.mod ani Makefile w ${SRC_DIR}."
        _warn "Sprawdzam czy są pre-skompilowane binarne..."

        # Sprawdź czy binarne już istnieją (np. z poprzedniego builda)
        if [[ -f "${ROUTER_BINARY}" ]] && [[ -f "${PIXEL_BINARY}" ]]; then
            _info "Znaleziono istniejące binarne — pomijam build."
            _step_ok "${step}"
            return 0
        fi

        _step_fail "${step}" "brak źródeł i brak binarek"
        return 1
    fi

    # Buduj dla routera: linux/amd64
    _info "Budowanie sylion-relay dla linux/amd64 (router)..."
    local build_router_exit=0
    if [[ -f "${SRC_DIR}/Makefile" ]]; then
        (cd "${SRC_DIR}" && GOOS=linux GOARCH=amd64 make build-relay \
            OUTPUT="${ROUTER_BINARY}" 2>>"${LOG_FILE}") || build_router_exit=$?
    elif [[ -f "${SRC_DIR}/go.mod" ]]; then
        (cd "${SRC_DIR}" && GOOS=linux GOARCH=amd64 go build \
            -ldflags="-s -w -X main.version=$(git describe --tags 2>/dev/null || echo 'dev')" \
            -o "${ROUTER_BINARY}" \
            ./cmd/relay/... 2>>"${LOG_FILE}") || build_router_exit=$?
    fi

    if (( build_router_exit != 0 )); then
        _step_fail "${step}" "build router (exit ${build_router_exit})"
        return 1
    fi
    _info "Build router OK: ${ROUTER_BINARY}"

    # Buduj dla Pixela: linux/arm64
    _info "Budowanie sylion dla linux/arm64 (Pixel)..."
    local build_pixel_exit=0
    if [[ -f "${SRC_DIR}/Makefile" ]]; then
        (cd "${SRC_DIR}" && GOOS=linux GOARCH=arm64 make build \
            OUTPUT="${PIXEL_BINARY}" 2>>"${LOG_FILE}") || build_pixel_exit=$?
    elif [[ -f "${SRC_DIR}/go.mod" ]]; then
        (cd "${SRC_DIR}" && GOOS=linux GOARCH=arm64 go build \
            -ldflags="-s -w -X main.version=$(git describe --tags 2>/dev/null || echo 'dev')" \
            -o "${PIXEL_BINARY}" \
            ./cmd/sylion/... 2>>"${LOG_FILE}") || build_pixel_exit=$?
    fi

    if (( build_pixel_exit != 0 )); then
        _step_fail "${step}" "build pixel (exit ${build_pixel_exit})"
        return 1
    fi
    _info "Build Pixel OK: ${PIXEL_BINARY}"

    # Wyświetl rozmiary binarek
    if [[ -f "${ROUTER_BINARY}" ]]; then
        _info "Rozmiar sylion-relay (amd64): $(du -sh "${ROUTER_BINARY}" | cut -f1)"
    fi
    if [[ -f "${PIXEL_BINARY}" ]]; then
        _info "Rozmiar sylion (arm64): $(du -sh "${PIXEL_BINARY}" | cut -f1)"
    fi

    _step_ok "${step}"
}

# -----------------------------------------------------------------------------
# Krok 2: Wdrożenie na router
# -----------------------------------------------------------------------------

step_deploy_router() {
    local step="deploy_router"
    _step "Wdrożenie SYLION Relay na router (${ROUTER_IP})"

    if [[ "${SKIP_ROUTER}" == "true" ]]; then
        _step_skip "${step}"
        return 0
    fi

    # Sprawdź czy binarko istnieje
    if [[ ! -f "${ROUTER_BINARY}" ]]; then
        _step_fail "${step}" "brak binarki: ${ROUTER_BINARY}"
        return 1
    fi

    # Sprawdź połączenie z routerem
    if ! router_check_connection "${ROUTER_IP}" > /dev/null 2>&1; then
        _step_fail "${step}" "brak połączenia SSH z ${ROUTER_IP}"
        return 1
    fi

    # Wdróż binarko relay
    local deploy_exit=0
    router_deploy_binary "${ROUTER_IP}" "${ROUTER_BINARY}" "/usr/bin/sylion-relay" \
        || deploy_exit=$?

    if (( deploy_exit != 0 )); then
        _step_fail "${step}" "deploy_binary exit ${deploy_exit}"
        return 1
    fi

    # Wdróż konfigurację jeśli podana
    if [[ -n "${CONFIG_PATH}" ]] && [[ -f "${CONFIG_PATH}" ]]; then
        _info "Wdrażam konfigurację na router..."
        router_update_config "${ROUTER_IP}" "${CONFIG_PATH}" || \
            _warn "Konfiguracja nieudana — kontynuuję."
    fi

    # Zainstaluj wymagane pakiety systemowe (jeśli potrzebne)
    _info "Sprawdzam wymagane pakiety na routerze..."

    # OPKG_REQUIRED packages — add here as deployment matures
    OPKG_REQUIRED=(
        "kmod-tun"          # TUN/TAP kernel module (required for VPN tunnels)
        # v5.10: uncomment when WG support lands:
        # "kmod-wireguard-all-modules"  # WireGuard kernel modules
        # "wireguard-tools"              # wg, wg-quick CLI tools
    )

    for pkg in "${OPKG_REQUIRED[@]}"; do
        [[ "${pkg}" == \#* ]] && continue  # skip commented entries
        router_install_packages "${ROUTER_IP}" "${pkg}" 2>/dev/null || \
            _warn "Instalacja pakietu ${pkg} nieudana — być może już zainstalowany."
    done

    _step_ok "${step}"
}

# -----------------------------------------------------------------------------
# Krok 3: Wdrożenie na Pixel
# -----------------------------------------------------------------------------

step_deploy_pixel() {
    local step="deploy_pixel"
    _step "Wdrożenie SYLION na Pixel"

    if [[ "${SKIP_PIXEL}" == "true" ]]; then
        _step_skip "${step}"
        return 0
    fi

    # Sprawdź połączenie ADB
    if ! pixel_check_connection > /dev/null 2>&1; then
        _step_fail "${step}" "brak połączenia ADB"
        return 1
    fi

    # Wdróż APK jeśli podany, w przeciwnym razie wdróż binarko ARM64
    if [[ -n "${APK_PATH}" ]] && [[ -f "${APK_PATH}" ]]; then
        _info "Wdrażam APK SYLION: ${APK_PATH}"
        local apk_exit=0
        pixel_deploy_sylion "${APK_PATH}" || apk_exit=$?
        if (( apk_exit != 0 )); then
            _step_fail "${step}" "install APK exit ${apk_exit}"
            return 1
        fi
    elif [[ -f "${PIXEL_BINARY}" ]]; then
        _info "Wdrażam binarko SYLION arm64: ${PIXEL_BINARY}"
        local bin_exit=0
        pixel_deploy_sylion "${PIXEL_BINARY}" || bin_exit=$?
        if (( bin_exit != 0 )); then
            _step_fail "${step}" "push binary exit ${bin_exit}"
            return 1
        fi
    else
        _step_fail "${step}" "brak APK ani binarki arm64"
        return 1
    fi

    # Wdróż konfigurację jeśli podana
    if [[ -n "${CONFIG_PATH}" ]] && [[ -f "${CONFIG_PATH}" ]]; then
        _info "Wdrażam konfigurację na Pixel..."
        pixel_push_config "${CONFIG_PATH}" || \
            _warn "Konfiguracja nieudana — kontynuuję."
    fi

    _step_ok "${step}"
}

# -----------------------------------------------------------------------------
# Krok 4: Health check router
# -----------------------------------------------------------------------------

step_health_router() {
    local step="health_router"
    _step "Health check router (${ROUTER_IP})"

    if [[ "${SKIP_ROUTER}" == "true" ]]; then
        _step_skip "${step}"
        return 0
    fi

    local health_exit=0
    router_health_check "${ROUTER_IP}" || health_exit=$?

    if (( health_exit != 0 )); then
        _step_fail "${step}" "health check nieudany"
        return 1
    fi

    _step_ok "${step}"
}

# -----------------------------------------------------------------------------
# Krok 5: Health check Pixel
# -----------------------------------------------------------------------------

step_health_pixel() {
    local step="health_pixel"
    _step "Health check Pixel"

    if [[ "${SKIP_PIXEL}" == "true" ]]; then
        _step_skip "${step}"
        return 0
    fi

    local health_exit=0
    pixel_health_check || health_exit=$?

    if (( health_exit != 0 )); then
        _step_fail "${step}" "health check nieudany"
        return 1
    fi

    _step_ok "${step}"
}

# -----------------------------------------------------------------------------
# Raport końcowy
# -----------------------------------------------------------------------------

_print_report() {
    local deploy_end_time="$(date +%s)"
    local elapsed=$(( deploy_end_time - DEPLOY_START_TIME ))
    local timestamp="$(date '+%Y-%m-%dT%H:%M:%S')"

    # Oblicz ogólny status
    local overall_ok=true
    local failed_steps=()
    for step in "${!STEP_RESULTS[@]}"; do
        if [[ "${STEP_RESULTS[${step}]}" != "ok" ]] && \
           [[ "${STEP_RESULTS[${step}]}" != "skipped" ]]; then
            overall_ok=false
            failed_steps+=("${step}")
        fi
    done

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        # Zbuduj JSON z wynikami kroków
        local steps_json="{"
        local first=true
        for step in build deploy_router deploy_pixel health_router health_pixel; do
            local result="${STEP_RESULTS[${step}]:-not_run}"
            if [[ "${first}" == "false" ]]; then steps_json+=","; fi
            steps_json+="\"${step}\": \"${result}\""
            first=false
        done
        steps_json+="}"

        local failed_json
        failed_json="$(printf '"%s",' "${failed_steps[@]+"${failed_steps[@]}"}" | sed 's/,$//')"
        printf '{
  "ok": %s,
  "timestamp": "%s",
  "elapsed_seconds": %d,
  "router_ip": "%s",
  "pixel_serial": "%s",
  "steps": %s,
  "failed_steps": [%s],
  "log_file": "%s"
}\n' \
            "$([ "${overall_ok}" == "true" ] && echo 'true' || echo 'false')" \
            "${timestamp}" \
            "${elapsed}" \
            "${ROUTER_IP}" \
            "${ADB_SERIAL:-unknown}" \
            "${steps_json}" \
            "${failed_json}" \
            "${LOG_FILE}"
    else
        printf '\n%b╔══════════════════════════════════╗%b\n' "${BOLD}${BLUE}" "${RESET}"
        printf '%b║       RAPORT WDROŻENIA SYLION    ║%b\n' "${BOLD}${BLUE}" "${RESET}"
        printf '%b╚══════════════════════════════════╝%b\n' "${BOLD}${BLUE}" "${RESET}"
        printf '  Czas:          %s\n' "${timestamp}"
        printf '  Czas trwania:  %ds\n' "${elapsed}"
        printf '  Router IP:     %s\n' "${ROUTER_IP}"
        printf '  Pixel serial:  %s\n' "${ADB_SERIAL:-nieznany}"
        printf '  Log:           %s\n' "${LOG_FILE}"
        printf '\n  Kroki:\n'
        for step in build deploy_router deploy_pixel health_router health_pixel; do
            local result="${STEP_RESULTS[${step}]:-not_run}"
            local color="${GREEN}"
            [[ "${result}" == "skipped" ]]  && color="${YELLOW}"
            [[ "${result}" == "not_run" ]]  && color="${YELLOW}"
            [[ "${result}" == failed* ]]    && color="${RED}"
            printf '    %b%-20s%b %s\n' "${color}" "${step}:" "${RESET}" "${result}"
        done
        printf '\n  Status ogólny: '
        if [[ "${overall_ok}" == "true" ]]; then
            printf '%bSUKCES%b\n' "${GREEN}${BOLD}" "${RESET}"
        else
            printf '%bNIEUDANY%b (kroki: %s)\n' "${RED}${BOLD}" "${RESET}" \
                "${failed_steps[*]+"${failed_steps[*]}"}"
        fi
        printf '\n'
    fi

    # Zapisz raport JSON do pliku niezależnie od trybu wyjścia
    local report_file="${LOG_DIR}/deploy_report_$(date +%Y%m%d_%H%M%S).json"
    _ensure_log_dir
    cat > "${report_file}" << REPORT_EOF
{
  "ok": $([ "${overall_ok}" == "true" ] && echo 'true' || echo 'false'),
  "timestamp": "${timestamp}",
  "elapsed_seconds": ${elapsed},
  "router_ip": "${ROUTER_IP}",
  "pixel_serial": "${ADB_SERIAL:-unknown}",
  "log_file": "${LOG_FILE}"
}
REPORT_EOF
    _log "INFO" "Raport zapisany: ${report_file}"

    [[ "${overall_ok}" == "true" ]]
}

# -----------------------------------------------------------------------------
# Główna funkcja orkiestracji
# -----------------------------------------------------------------------------

main() {
    _parse_args "$@"

    _header "SYLION DEPLOY ALL — $(date '+%Y-%m-%d %H:%M:%S')"
    _info "Router IP: ${ROUTER_IP}"
    _info "Katalog źródeł: ${SRC_DIR}"
    _info "Katalog binarek: ${BINARY_DIR}"
    [[ -n "${APK_PATH}" ]] && _info "APK: ${APK_PATH}"
    [[ -n "${CONFIG_PATH}" ]] && _info "Konfiguracja: ${CONFIG_PATH}"

    mkdir -p "${BINARY_DIR}"

    # Wykonaj kroki wdrożenia sekwencyjnie
    # Każdy krok loguje wynik, błąd nie przerywa całości (|| true)
    step_build          || true
    step_deploy_router  || true
    step_deploy_pixel   || true
    step_health_router  || true
    step_health_pixel   || true

    # Wydrukuj raport i zwróć odpowiedni kod wyjścia
    _print_report
}

main "$@"
