#!/usr/bin/env bash
# =============================================================================
# monitor.sh — Ciągłe monitorowanie urządzeń SYLION
# Część potoku audytu SYLION
#
# Przeznaczenie:
#   Skrypt w pętli monitoruje router OpenWrt i Pixel z GrapheneOS.
#   Co N sekund odpytuje oba urządzenia, sprawdza:
#   - łączność (SSH / ADB)
#   - status procesu SYLION
#   - zasoby systemowe (CPU, RAM, bateria)
#   Wyniki są emitowane jako JSON, gotowe do spożycia przez agentów AI.
#
# Użycie:
#   ./monitor.sh [--json] [--interval N] [--router-ip IP]
#                [--once] [--output-file PLIK]
#
# Wyjście:
#   Jeden obiekt JSON na linię (NDJSON) — czytelny maszynowo dla agentów.
#   Przykład:
#     {"timestamp":"2024-01-15T12:00:00","router":{...},"pixel":{...},"ok":true}
#
# Zmienne środowiskowe:
#   SYLION_ROUTER_IP       — adres IP routera (domyślnie: 192.168.1.1)
#   SYLION_MONITOR_INTERVAL — interwał w sekundach (domyślnie: 30)
#   SYLION_ADB_SERIAL      — numer seryjny Pixela
#   SYLION_LOG_DIR         — katalog logów
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# -----------------------------------------------------------------------------
# Ścieżki i konfiguracja
# -----------------------------------------------------------------------------

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_DIR="${SYLION_LOG_DIR:-${SCRIPT_DIR}/logs}"
readonly LOG_FILE="${LOG_DIR}/monitor_$(date +%Y%m%d).log"

# Załaduj managery — dostęp do funkcji _ssh, _adb itd.
# shellcheck source=pixel_manager.sh
source "${SCRIPT_DIR}/pixel_manager.sh"
# shellcheck source=router_manager.sh
source "${SCRIPT_DIR}/router_manager.sh"

# Parametry monitora
ROUTER_IP="${SYLION_ROUTER_IP:-192.168.1.1}"
MONITOR_INTERVAL="${SYLION_MONITOR_INTERVAL:-30}"
OUTPUT_JSON=true     # monitor domyślnie wypisuje JSON
RUN_ONCE=false
OUTPUT_FILE=""
ITERATION=0

# PID file do kontroli procesu
PID_FILE="${LOG_DIR}/monitor.pid"

# -----------------------------------------------------------------------------
# Exponential backoff state (Fix 6 — v5.9.1)
# SSH failures cause the inter-poll delay to grow: 1s, 2s, 4s, 8s, capped 60s.
# Resets to 1s after any successful SSH connection.
# -----------------------------------------------------------------------------
_SSH_BACKOFF=1          # current backoff delay in seconds
_SSH_BACKOFF_MAX=60     # maximum backoff cap
_SSH_BACKOFF_LAST_OK=0  # epoch of last successful SSH

# Call on SSH success to reset backoff
_ssh_backoff_reset() {
    _SSH_BACKOFF=1
    _SSH_BACKOFF_LAST_OK="$(date +%s)"
}

# Call on SSH failure; sleeps for current backoff, then doubles for next time
_ssh_backoff_wait() {
    local delay="${_SSH_BACKOFF}"
    _stderr "SSH failure — backing off ${delay}s (cap ${_SSH_BACKOFF_MAX}s)..."
    sleep "${delay}"
    # Double for next failure, cap at max
    _SSH_BACKOFF=$(( _SSH_BACKOFF * 2 ))
    if (( _SSH_BACKOFF > _SSH_BACKOFF_MAX )); then
        _SSH_BACKOFF=${_SSH_BACKOFF_MAX}
    fi
}

# -----------------------------------------------------------------------------
# Kolory (tylko w trybie tekstowym)
# -----------------------------------------------------------------------------

_init_colors() {
    if [[ -t 2 ]] && [[ "${OUTPUT_JSON}" == "false" ]]; then
        RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
        BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
    else
        RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; BOLD=''; RESET=''
    fi
}
_init_colors

# -----------------------------------------------------------------------------
# Funkcje pomocnicze
# -----------------------------------------------------------------------------

_ensure_log_dir() { mkdir -p "${LOG_DIR}"; }

_log() {
    _ensure_log_dir
    printf '[%s] [monitor] [%s] %s\n' \
        "$(date '+%Y-%m-%dT%H:%M:%S')" "$1" "$2" >> "${LOG_FILE}"
}

_stderr() {
    # Wiadomości diagnostyczne idą na stderr, żeby nie zaśmiecać stdout (JSON)
    printf '[%s] [monitor] %s\n' "$(date '+%H:%M:%S')" "$1" >&2
}

_emit_json() {
    # Wyemituj JSON status na stdout
    local json="$1"
    printf '%s\n' "${json}"
    # Opcjonalnie zapisz do pliku
    if [[ -n "${OUTPUT_FILE}" ]]; then
        printf '%s\n' "${json}" >> "${OUTPUT_FILE}"
    fi
    _log "EMIT" "${json:0:200}..."
}

# Bezpieczna konwersja wartości do JSON string (escape)
_json_str() {
    local val="$1"
    printf '%s' "${val}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))' 2>/dev/null \
        || printf '"%s"' "${val//\"/\\\"}"
}

# Wrapper _adb_shell z timeout (zapobiega zawieszeniu)
_adb_shell_safe() {
    local timeout_sec="${1}"
    shift
    timeout "${timeout_sec}" bash -c "_adb shell $*" 2>/dev/null || true
}

# Wrapper _ssh z timeout
_ssh_safe() {
    local ip="$1"
    local timeout_sec="$2"
    shift 2
    timeout "${timeout_sec}" bash -c "_ssh '${ip}' $*" 2>/dev/null || true
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
            --no-json)
                OUTPUT_JSON=false
                _init_colors
                ;;
            --interval)
                MONITOR_INTERVAL="${2:?'--interval wymaga liczby sekund'}"
                shift
                ;;
            --router-ip)
                ROUTER_IP="${2:?'--router-ip wymaga adresu IP'}"
                shift
                ;;
            --once)
                RUN_ONCE=true
                ;;
            --output-file)
                OUTPUT_FILE="${2:?'--output-file wymaga ścieżki'}"
                shift
                ;;
            -h|--help)
                printf 'Użycie: %s [opcje]\n\n' "$(basename "$0")"
                printf 'Opcje:\n'
                printf '  --json              Wyjście JSON na stdout (domyślnie)\n'
                printf '  --no-json           Wyjście tekstowe (czytelne dla człowieka)\n'
                printf '  --interval N        Interwał odpytywania w sekundach (domyślnie: 30)\n'
                printf '  --router-ip IP      Adres IP routera (domyślnie: 192.168.1.1)\n'
                printf '  --once              Wykonaj jedno odpytanie i zakończ\n'
                printf '  --output-file PLIK  Dopisuj JSON do pliku\n'
                printf '  -h, --help          Ta pomoc\n'
                exit 0
                ;;
            *)
                printf '[WARN] Nieznany argument: %s\n' "$1" >&2
                ;;
        esac
        shift
    done
}

# -----------------------------------------------------------------------------
# Zbieranie danych z routera
# -----------------------------------------------------------------------------

_collect_router_status() {
    local ip="${1}"
    local ts_start ts_end latency

    ts_start="$(date +%s%N 2>/dev/null || date +%s)000"

    # Test połączenia SSH (timeout 8s)
    local ssh_ok=false
    local hostname=""
    if timeout 8 bash -c "_ssh '${ip}' 'echo ok'" &>/dev/null; then
        ssh_ok=true
        _ssh_backoff_reset  # reset exponential backoff on success
    fi

    ts_end="$(date +%s%N 2>/dev/null || date +%s)000"
    # Oblicz latencję w ms (bash arytmetyka)
    latency=$(( (ts_end - ts_start) / 1000000 )) 2>/dev/null || latency=0

    if [[ "${ssh_ok}" == "false" ]]; then
        printf '{"connected": false, "ip": "%s", "error": "ssh_timeout"}' "${ip}"
        _ssh_backoff_wait   # exponential backoff on SSH failure (1s→32s→cap 60s)
        return
    fi

    # Zbierz dane równolegle przez jedno połączenie SSH (oszczędność połączeń)
    local router_data
    router_data="$(_ssh "${ip}" '
        echo "HOSTNAME=$(uname -n)"
        echo "OPENWRT=$(grep DISTRIB_DESCRIPTION /etc/openwrt_release 2>/dev/null | cut -d= -f2 | tr -d "\"")"
        echo "UPTIME=$(cat /proc/uptime | awk "{print \$1}")"
        echo "MEM_TOTAL=$(grep MemTotal /proc/meminfo | awk "{print \$2}")"
        echo "MEM_FREE=$(grep MemFree /proc/meminfo | awk "{print \$2}")"
        echo "MEM_BUFFERS=$(grep Buffers /proc/meminfo | awk "{print \$2}")"
        echo "MEM_CACHED=$(grep "^Cached:" /proc/meminfo | awk "{print \$2}")"
        echo "LOAD=$(cat /proc/loadavg | awk "{print \$1}")"
        echo "SYLION_PROC=$(pgrep -l sylion 2>/dev/null | head -1 || echo none)"
        echo "SYLION_BIN=$(test -f /usr/bin/sylion-relay && echo ok || echo missing)"
        echo "WAN_PING=$(ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && echo ok || echo fail)"
        echo "DISK_FREE=$(df / | tail -1 | awk "{print \$4}")"
    ' 2>/dev/null | tr -d '\r')" || router_data=""

    # Parsuj zebrane dane
    local hostname openwrt uptime mem_total mem_free mem_buffers mem_cached
    local load sylion_proc sylion_bin wan_ping disk_free

    hostname="$(printf '%s' "${router_data}" | grep ^HOSTNAME= | cut -d= -f2)" ; hostname="${hostname:-unknown}"
    openwrt="$(printf '%s' "${router_data}" | grep ^OPENWRT= | cut -d= -f2)"   ; openwrt="${openwrt:-unknown}"
    uptime="$(printf '%s' "${router_data}" | grep ^UPTIME= | cut -d= -f2)"     ; uptime="${uptime:-0}"
    mem_total="$(printf '%s' "${router_data}" | grep ^MEM_TOTAL= | cut -d= -f2)"; mem_total="${mem_total:-0}"
    mem_free="$(printf '%s' "${router_data}" | grep ^MEM_FREE= | cut -d= -f2)" ; mem_free="${mem_free:-0}"
    mem_buffers="$(printf '%s' "${router_data}" | grep ^MEM_BUFFERS= | cut -d= -f2)"; mem_buffers="${mem_buffers:-0}"
    mem_cached="$(printf '%s' "${router_data}" | grep ^MEM_CACHED= | cut -d= -f2)";  mem_cached="${mem_cached:-0}"
    load="$(printf '%s' "${router_data}" | grep ^LOAD= | cut -d= -f2)"         ; load="${load:-0}"
    sylion_proc="$(printf '%s' "${router_data}" | grep ^SYLION_PROC= | cut -d= -f2)"; sylion_proc="${sylion_proc:-none}"
    sylion_bin="$(printf '%s' "${router_data}" | grep ^SYLION_BIN= | cut -d= -f2)"; sylion_bin="${sylion_bin:-missing}"
    wan_ping="$(printf '%s' "${router_data}" | grep ^WAN_PING= | cut -d= -f2)" ; wan_ping="${wan_ping:-fail}"
    disk_free="$(printf '%s' "${router_data}" | grep ^DISK_FREE= | cut -d= -f2)"; disk_free="${disk_free:-0}"

    # Oblicz użycie pamięci
    local mem_used_kb=0 mem_pct=0
    if (( mem_total > 0 )); then
        mem_used_kb=$(( mem_total - mem_free - mem_buffers - mem_cached ))
        mem_pct=$(( mem_used_kb * 100 / mem_total ))
    fi

    # Status procesu SYLION
    local sylion_running=false
    [[ "${sylion_proc}" != "none" ]] && [[ -n "${sylion_proc}" ]] && sylion_running=true

    # Status zdrowia
    local health="ok"
    [[ "${sylion_running}" == "false" ]] && health="degraded"
    [[ "${sylion_bin}" == "missing" ]] && health="critical"

    printf '{
    "connected": true,
    "ip": "%s",
    "hostname": "%s",
    "openwrt_version": "%s",
    "uptime_seconds": %s,
    "load_1m": %s,
    "memory": {
      "total_kb": %d,
      "used_kb": %d,
      "free_kb": %d,
      "usage_pct": %d
    },
    "disk_free_kb": %s,
    "wan_connectivity": %s,
    "sylion": {
      "running": %s,
      "binary_present": %s,
      "process_info": "%s"
    },
    "health": "%s",
    "latency_ms": %d
  }' \
        "${ip}" \
        "${hostname}" \
        "${openwrt}" \
        "${uptime:-0}" \
        "${load:-0}" \
        "${mem_total}" \
        "${mem_used_kb}" \
        "${mem_free}" \
        "${mem_pct}" \
        "${disk_free:-0}" \
        "$([ "${wan_ping}" = 'ok' ] && echo 'true' || echo 'false')" \
        "$([ "${sylion_running}" = 'true' ] && echo 'true' || echo 'false')" \
        "$([ "${sylion_bin}" = 'ok' ] && echo 'true' || echo 'false')" \
        "${sylion_proc}" \
        "${health}" \
        "${latency}"
}

# -----------------------------------------------------------------------------
# Zbieranie danych z Pixela
# -----------------------------------------------------------------------------

_collect_pixel_status() {
    # Upewnij się że ADB jest gotowe
    adb start-server 2>/dev/null || true

    # Sprawdź połączenie ADB
    local device_lines
    device_lines="$(adb devices 2>/dev/null | grep -v '^List' | grep 'device$' || true)"

    if [[ -z "${device_lines}" ]]; then
        printf '{"connected": false, "error": "no_adb_device"}'
        return
    fi

    # Pobierz serial
    local serial="${ADB_SERIAL:-}"
    if [[ -z "${serial}" ]]; then
        serial="$(printf '%s\n' "${device_lines}" | awk '{print $1}' | head -1)"
        ADB_SERIAL="${serial}"
        export ADB_SERIAL
    fi

    # Zbierz dane przez jedno połączenie ADB (oszczędność czasu)
    local pixel_data
    pixel_data="$(timeout 15 adb -s "${serial}" shell '
        echo "MODEL=$(getprop ro.product.model)"
        echo "ANDROID=$(getprop ro.build.version.release)"
        echo "GRAPHENEOS=$(getprop ro.grapheneos.version)"
        echo "BATTERY=$(cat /sys/class/power_supply/battery/capacity 2>/dev/null || echo -1)"
        echo "BAT_STATUS=$(cat /sys/class/power_supply/battery/status 2>/dev/null || echo unknown)"
        echo "MEM_TOTAL=$(grep MemTotal /proc/meminfo | awk "{print \$2}")"
        echo "MEM_FREE=$(grep MemAvailable /proc/meminfo | awk "{print \$2}")"
        echo "LOAD=$(cat /proc/loadavg | awk "{print \$1}")"
        echo "UPTIME=$(cat /proc/uptime | awk "{print \$1}")"
        echo "SYLION_APK=$(pm list packages 2>/dev/null | grep -i sylion | head -1 || echo none)"
        echo "SYLION_PROC=$(pgrep -l sylion 2>/dev/null | head -1 || echo none)"
        echo "SYLION_DIR=$(test -d /data/local/tmp/sylion && echo ok || echo missing)"
        echo "DISK_FREE=$(df /data 2>/dev/null | tail -1 | awk "{print \$4}")"
    ' 2>/dev/null | tr -d '\r')" || pixel_data=""

    # Parsuj zebrane dane
    local model android grapheneos battery bat_status mem_total mem_free
    local load uptime sylion_apk sylion_proc sylion_dir disk_free

    model="$(printf '%s' "${pixel_data}" | grep ^MODEL= | cut -d= -f2)"          ; model="${model:-unknown}"
    android="$(printf '%s' "${pixel_data}" | grep ^ANDROID= | cut -d= -f2)"      ; android="${android:-unknown}"
    grapheneos="$(printf '%s' "${pixel_data}" | grep ^GRAPHENEOS= | cut -d= -f2)"; grapheneos="${grapheneos:-N/A}"
    battery="$(printf '%s' "${pixel_data}" | grep ^BATTERY= | cut -d= -f2)"      ; battery="${battery:--1}"
    bat_status="$(printf '%s' "${pixel_data}" | grep ^BAT_STATUS= | cut -d= -f2)"; bat_status="${bat_status:-unknown}"
    mem_total="$(printf '%s' "${pixel_data}" | grep ^MEM_TOTAL= | cut -d= -f2)"  ; mem_total="${mem_total:-0}"
    mem_free="$(printf '%s' "${pixel_data}" | grep ^MEM_FREE= | cut -d= -f2)"    ; mem_free="${mem_free:-0}"
    load="$(printf '%s' "${pixel_data}" | grep ^LOAD= | cut -d= -f2)"            ; load="${load:-0}"
    uptime="$(printf '%s' "${pixel_data}" | grep ^UPTIME= | cut -d= -f2)"        ; uptime="${uptime:-0}"
    sylion_apk="$(printf '%s' "${pixel_data}" | grep ^SYLION_APK= | cut -d= -f2)"; sylion_apk="${sylion_apk:-none}"
    sylion_proc="$(printf '%s' "${pixel_data}" | grep ^SYLION_PROC= | cut -d= -f2)"; sylion_proc="${sylion_proc:-none}"
    sylion_dir="$(printf '%s' "${pixel_data}" | grep ^SYLION_DIR= | cut -d= -f2)"; sylion_dir="${sylion_dir:-missing}"
    disk_free="$(printf '%s' "${pixel_data}" | grep ^DISK_FREE= | cut -d= -f2)"  ; disk_free="${disk_free:-0}"

    # Oblicz użycie pamięci
    local mem_used_kb=0 mem_pct=0
    if (( mem_total > 0 )); then
        mem_used_kb=$(( mem_total - mem_free ))
        mem_pct=$(( mem_used_kb * 100 / mem_total ))
    fi

    # Status procesu SYLION
    local sylion_running=false
    [[ "${sylion_proc}" != "none" ]] && [[ -n "${sylion_proc}" ]] && sylion_running=true

    local sylion_installed=false
    [[ "${sylion_apk}" != "none" ]] && [[ -n "${sylion_apk}" ]] && sylion_installed=true

    # Status zdrowia
    local health="ok"
    [[ "${sylion_running}" == "false" ]] && [[ "${sylion_installed}" == "false" ]] && health="critical"
    [[ "${sylion_running}" == "false" ]] && [[ "${sylion_dir}" == "missing" ]] && health="critical"
    [[ "${sylion_running}" == "false" ]] && [[ "${sylion_dir}" != "missing" ]] && health="degraded"

    # Ostrzeżenie przy niskiej baterii
    local battery_int="${battery//-*/0}"
    if (( battery_int > 0 && battery_int < 20 )); then
        _log "WARN" "Niski poziom baterii Pixel: ${battery_int}%"
    fi

    printf '{
    "connected": true,
    "serial": "%s",
    "model": "%s",
    "android_version": "%s",
    "grapheneos_version": "%s",
    "battery": {
      "level_pct": %s,
      "status": "%s"
    },
    "uptime_seconds": %s,
    "load_1m": %s,
    "memory": {
      "total_kb": %d,
      "used_kb": %d,
      "free_kb": %d,
      "usage_pct": %d
    },
    "disk_free_data_kb": %s,
    "sylion": {
      "running": %s,
      "apk_installed": %s,
      "deploy_dir_exists": %s,
      "apk_package": "%s",
      "process_info": "%s"
    },
    "health": "%s"
  }' \
        "${serial}" \
        "${model}" \
        "${android}" \
        "${grapheneos}" \
        "${battery:-0}" \
        "${bat_status}" \
        "${uptime:-0}" \
        "${load:-0}" \
        "${mem_total}" \
        "${mem_used_kb}" \
        "${mem_free}" \
        "${mem_pct}" \
        "${disk_free:-0}" \
        "$([ "${sylion_running}" = 'true' ] && echo 'true' || echo 'false')" \
        "$([ "${sylion_installed}" = 'true' ] && echo 'true' || echo 'false')" \
        "$([ "${sylion_dir}" = 'ok' ] && echo 'true' || echo 'false')" \
        "${sylion_apk}" \
        "${sylion_proc}" \
        "${health}"
}

# -----------------------------------------------------------------------------
# Jedna iteracja monitorowania — zbierz dane z obu urządzeń
# -----------------------------------------------------------------------------

_run_once() {
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S')"
    local ts_epoch
    ts_epoch="$(date +%s)"

    _stderr "Odpytywanie urządzeń (iteracja #${ITERATION})..."

    # Zbierz dane z routera (z timeout)
    local router_json
    router_json="$( _collect_router_status "${ROUTER_IP}" 2>/dev/null )" \
        || router_json='{"connected": false, "error": "collection_error"}'

    # Zbierz dane z Pixela (z timeout)
    local pixel_json
    pixel_json="$( _collect_pixel_status 2>/dev/null )" \
        || pixel_json='{"connected": false, "error": "collection_error"}'

    # Oblicz ogólny status
    local router_health pixel_health overall_ok
    router_health="$(printf '%s' "${router_json}" | python3 -c \
        'import sys,json; d=json.load(sys.stdin); print(d.get("health","unknown"))' \
        2>/dev/null || echo "unknown")"
    pixel_health="$(printf '%s' "${pixel_json}" | python3 -c \
        'import sys,json; d=json.load(sys.stdin); print(d.get("health","unknown"))' \
        2>/dev/null || echo "unknown")"

    overall_ok="true"
    [[ "${router_health}" == "critical" ]] && overall_ok="false"
    [[ "${pixel_health}" == "critical" ]] && overall_ok="false"
    # Jeśli nie połączone — degraded ale nie critical
    local router_connected pixel_connected
    router_connected="$(printf '%s' "${router_json}" | python3 -c \
        'import sys,json; d=json.load(sys.stdin); print(str(d.get("connected",False)).lower())' \
        2>/dev/null || echo "false")"
    pixel_connected="$(printf '%s' "${pixel_json}" | python3 -c \
        'import sys,json; d=json.load(sys.stdin); print(str(d.get("connected",False)).lower())' \
        2>/dev/null || echo "false")"

    # Zbuduj finalny JSON statusu
    local final_json
    final_json="{
  \"timestamp\": \"${ts}\",
  \"epoch\": ${ts_epoch},
  \"iteration\": ${ITERATION},
  \"ok\": ${overall_ok},
  \"router\": ${router_json},
  \"pixel\": ${pixel_json},
  \"summary\": {
    \"router_connected\": ${router_connected},
    \"router_health\": \"${router_health}\",
    \"pixel_connected\": ${pixel_connected},
    \"pixel_health\": \"${pixel_health}\"
  }
}"

    # Waliduj JSON przed emisją (python3 jako parser)
    if python3 -c "import sys,json; json.loads(sys.stdin.read())" \
            <<< "${final_json}" 2>/dev/null; then
        _emit_json "${final_json}"
    else
        # Awaryjnie — wyemituj uproszczony JSON
        _log "WARN" "Wygenerowany JSON jest nieprawidłowy, emituję status awaryjny."
        _emit_json "{\"timestamp\": \"${ts}\", \"epoch\": ${ts_epoch}, \"ok\": false, \"error\": \"json_parse_error\", \"iteration\": ${ITERATION}}"
    fi

    # Zaloguj podsumowanie diagnostyczne na stderr
    _stderr "Router: connected=${router_connected}, health=${router_health} | Pixel: connected=${pixel_connected}, health=${pixel_health}"

    (( ITERATION++ ))
}

# -----------------------------------------------------------------------------
# Obsługa sygnałów — czysty shutdown
# -----------------------------------------------------------------------------

_cleanup() {
    _stderr "Monitor SYLION zatrzymany."
    rm -f "${PID_FILE}"
    exit 0
}
trap _cleanup SIGINT SIGTERM

# -----------------------------------------------------------------------------
# Główna pętla monitorowania
# -----------------------------------------------------------------------------

main() {
    _parse_args "$@"
    _ensure_log_dir

    # Zapisz PID
    printf '%d\n' "$$" > "${PID_FILE}"

    _stderr "=== Monitor SYLION uruchomiony ==="
    _stderr "Router IP:   ${ROUTER_IP}"
    _stderr "Pixel serial: ${ADB_SERIAL:-auto}"
    _stderr "Interwał:    ${MONITOR_INTERVAL}s"
    _stderr "Log:         ${LOG_FILE}"
    [[ -n "${OUTPUT_FILE}" ]] && _stderr "Output file: ${OUTPUT_FILE}"
    _stderr "PID:         $$"
    _stderr "Wciśnij Ctrl+C aby zatrzymać."
    _stderr ""

    if [[ "${RUN_ONCE}" == "true" ]]; then
        # Jednorazowe odpytanie
        _run_once
        rm -f "${PID_FILE}"
        return 0
    fi

    # Ciągła pętla monitorowania
    while true; do
        _run_once

        # Śpij z możliwością przerwania sygnałem
        sleep "${MONITOR_INTERVAL}" &
        local sleep_pid=$!
        wait "${sleep_pid}" 2>/dev/null || true
    done
}

main "$@"
