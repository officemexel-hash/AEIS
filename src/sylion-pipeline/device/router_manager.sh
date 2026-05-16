#!/usr/bin/env bash
# =============================================================================
# router_manager.sh — Zarządzanie routerem mobilnym z OpenWrt
# Część potoku audytu SYLION
#
# Przeznaczenie:
#   Skrypt zapewnia zestaw funkcji do komunikacji z routerem OpenWrt przez SSH.
#   Router jest podłączony przez USB (USB ethernet/RNDIS lub serial).
#   Obsługuje wdrożenie binarki SYLION relay, aktualizacje firmware,
#   zarządzanie pakietami opkg, konfigurację firewalla i monitorowanie.
#
# Użycie:
#   source router_manager.sh           # załaduj funkcje do bieżącej powłoki
#   ./router_manager.sh <funkcja> [args...]  # uruchom bezpośrednio
#
# Wymagania:
#   - ssh i scp dostępne w PATH
#   - Klucz SSH skonfigurowany dla routera (lub hasło przez sshpass)
#   - Router dostępny pod podanym adresem IP
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# -----------------------------------------------------------------------------
# Konfiguracja globalna
# -----------------------------------------------------------------------------

readonly ROUTER_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROUTER_LOG_DIR="${SYLION_LOG_DIR:-${ROUTER_SCRIPT_DIR}/logs}"
readonly ROUTER_LOG_FILE="${ROUTER_LOG_DIR}/router_manager_$(date +%Y%m%d).log"

# Domyślne wartości połączenia SSH
SSH_USER="${SYLION_ROUTER_USER:-root}"
SSH_PORT="${SYLION_ROUTER_PORT:-22}"
SSH_KEY="${SYLION_ROUTER_KEY:-}"
SSH_PASSWORD="${SYLION_ROUTER_PASSWORD:-}"

# Opcje SSH — wyłącz sprawdzanie host key dla USB (zaufana sieć lokalna)
SSH_OPTS=(
    -o StrictHostKeyChecking=no
    -o UserKnownHostsFile=/dev/null
    -o ConnectTimeout=10
    -o BatchMode=yes
    -p "${SSH_PORT}"
)
# Dodaj klucz SSH jeśli skonfigurowany
if [[ -n "${SSH_KEY}" ]]; then
    SSH_OPTS+=(-i "${SSH_KEY}")
fi

# Nazwa serwisu SYLION relay na routerze
SYLION_SERVICE="${SYLION_ROUTER_SERVICE:-sylion-relay}"

# Parametry ponownych prób
readonly ROUTER_RETRY_MAX="${SYLION_RETRY_MAX:-3}"
readonly ROUTER_RETRY_DELAY="${SYLION_RETRY_DELAY:-5}"

# Flaga JSON
OUTPUT_JSON=false

# -----------------------------------------------------------------------------
# Kolory terminala
# -----------------------------------------------------------------------------

_init_colors() {
    if [[ -t 1 ]] && [[ "${OUTPUT_JSON}" == "false" ]]; then
        RED='\033[0;31m'
        GREEN='\033[0;32m'
        YELLOW='\033[1;33m'
        BLUE='\033[0;34m'
        CYAN='\033[0;36m'
        BOLD='\033[1m'
        RESET='\033[0m'
    else
        RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' RESET=''
    fi
}
_init_colors

# -----------------------------------------------------------------------------
# Funkcje pomocnicze: logowanie i wyjście
# -----------------------------------------------------------------------------

_ensure_log_dir() {
    mkdir -p "${ROUTER_LOG_DIR}"
}

_log() {
    local level="$1"
    local msg="$2"
    _ensure_log_dir
    printf '[%s] [router_manager] [%s] %s\n' \
        "$(date '+%Y-%m-%dT%H:%M:%S')" "${level}" "${msg}" >> "${ROUTER_LOG_FILE}"
}

_info() {
    local msg="$1"
    _log "INFO" "${msg}"
    if [[ "${OUTPUT_JSON}" == "false" ]]; then
        printf '%b[INFO]%b %s\n' "${GREEN}" "${RESET}" "${msg}"
    fi
}

_warn() {
    local msg="$1"
    _log "WARN" "${msg}"
    if [[ "${OUTPUT_JSON}" == "false" ]]; then
        printf '%b[WARN]%b %s\n' "${YELLOW}" "${RESET}" "${msg}" >&2
    fi
}

_error() {
    local msg="$1"
    _log "ERROR" "${msg}"
    if [[ "${OUTPUT_JSON}" == "false" ]]; then
        printf '%b[ERROR]%b %s\n' "${RED}" "${RESET}" "${msg}" >&2
    fi
}

_header() {
    local title="$1"
    if [[ "${OUTPUT_JSON}" == "false" ]]; then
        printf '\n%b=== %s ===%b\n' "${BOLD}${BLUE}" "${title}" "${RESET}"
    fi
}

_json_output() {
    printf '%s\n' "$1"
}

_retry() {
    local attempt=1
    while true; do
        if "$@"; then
            return 0
        fi
        if (( attempt >= RETRY_MAX )); then
            _error "Polecenie nieudane po ${RETRY_MAX} próbach: $*"
            return 1
        fi
        _warn "Próba ${attempt}/${RETRY_MAX} nieudana. Czekam ${RETRY_DELAY}s..."
        sleep "${ROUTER_RETRY_DELAY}"
        (( attempt++ ))
    done
}

# -----------------------------------------------------------------------------
# ALLOWED_SSH_COMMANDS — komendy dozwolone przez SafeCommandRunner w Pythonie
# (device_harness.py). Ten skrypt bash może wywoływać wszystkie SSH. Poniższa
# lista to dokumentacja zmian v5.9.1 — odzwierciedla stan device_harness.py.
#
# Oryginalne 11 komend (v5.9.0):
#   scp, ls, chmod, start, kill, ps, cat, uptime, free, mkdir, rm, health
#
# Dodane w v5.9.1 (Fix 3):
#   wg             — status tunelu WireGuard
#   wg-quick       — uruchomienie/zatrzymanie wg0
#   iptables       — reguły kill-switch firewall
#   ip6tables      — reguły IPv6 kill-switch
#   ping           — test łączności WAN
#   ping6          — test łączności WAN (IPv6)
#   logread        — logi systemowe OpenWrt
#   opkg list-installed  — weryfikacja pakietów
#   nft            — zestaw reguł nftables
#   uci            — OpenWrt Unified Configuration Interface
#   /etc/init.d/*  — zarządzanie serwisami (pattern matching: initd w Pythonie)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Wrappery SSH i SCP
# Parametr IP jest przekazywany do każdej funkcji — brak globalnego stanu IP.
# -----------------------------------------------------------------------------

# _ssh IP CMD — wykonaj polecenie na routerze przez SSH
_ssh() {
    local ip="$1"
    shift
    if [[ -n "${SSH_PASSWORD}" ]] && command -v sshpass &>/dev/null; then
        sshpass -p "${SSH_PASSWORD}" ssh "${SSH_OPTS[@]}" "${SSH_USER}@${ip}" "$@"
    else
        ssh "${SSH_OPTS[@]}" "${SSH_USER}@${ip}" "$@"
    fi
}

# _scp_to IP LOCAL REMOTE — skopiuj plik na router
_scp_to() {
    local ip="$1"
    local local_path="$2"
    local remote_path="$3"
    local scp_opts=(
        -o StrictHostKeyChecking=no
        -o UserKnownHostsFile=/dev/null
        -o ConnectTimeout=10
        -P "${SSH_PORT}"
    )
    if [[ -n "${SSH_KEY}" ]]; then
        scp_opts+=(-i "${SSH_KEY}")
    fi
    if [[ -n "${SSH_PASSWORD}" ]] && command -v sshpass &>/dev/null; then
        sshpass -p "${SSH_PASSWORD}" scp "${scp_opts[@]}" "${local_path}" "${SSH_USER}@${ip}:${remote_path}"
    else
        scp "${scp_opts[@]}" "${local_path}" "${SSH_USER}@${ip}:${remote_path}"
    fi
}

# _scp_from IP REMOTE LOCAL — pobierz plik z routera
_scp_from() {
    local ip="$1"
    local remote_path="$2"
    local local_path="$3"
    local scp_opts=(
        -o StrictHostKeyChecking=no
        -o UserKnownHostsFile=/dev/null
        -o ConnectTimeout=10
        -P "${SSH_PORT}"
    )
    if [[ -n "${SSH_KEY}" ]]; then
        scp_opts+=(-i "${SSH_KEY}")
    fi
    if [[ -n "${SSH_PASSWORD}" ]] && command -v sshpass &>/dev/null; then
        sshpass -p "${SSH_PASSWORD}" scp "${scp_opts[@]}" "${SSH_USER}@${ip}:${remote_path}" "${local_path}"
    else
        scp "${scp_opts[@]}" "${SSH_USER}@${ip}:${remote_path}" "${local_path}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_check_connection IP
# Weryfikuje połączenie SSH z routerem.
#
# Argumenty:
#   ip — adres IP routera (np. 192.168.1.1)
#
# Wyjście (--json): {"ok": true/false, "ip": "...", "latency_ms": N}
# -----------------------------------------------------------------------------
router_check_connection() {
    local ip="${1:-}"
    _header "Sprawdzanie połączenia z routerem"
    _log "INFO" "router_check_connection: ip=${ip}"

    if [[ -z "${ip}" ]]; then
        _error "Nie podano adresu IP routera."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_ip"}'
        fi
        return 1
    fi

    # Ping — szybkie sprawdzenie dostępności sieciowej
    local ping_ok=false
    local latency_ms=0
    if ping -c 1 -W 3 "${ip}" &>/dev/null; then
        ping_ok=true
        # Zmierz latencję ping
        latency_ms="$(ping -c 1 -W 3 "${ip}" 2>/dev/null | grep 'time=' | sed 's/.*time=\([0-9.]*\).*/\1/' | head -1 || echo '0')"
    fi

    if [[ "${ping_ok}" == "false" ]]; then
        _warn "Brak odpowiedzi na ping dla ${ip}. Próbuję SSH bezpośrednio..."
    fi

    # Test SSH
    local ssh_ok=false
    local hostname=""
    local ssh_output
    ssh_output="$(_ssh "${ip}" "uname -n" 2>&1)" && {
        ssh_ok=true
        hostname="${ssh_output}"
        hostname="$(printf '%s' "${hostname}" | tr -d '\r\n')"
    } || true

    if [[ "${ssh_ok}" == "false" ]]; then
        _error "Nie można połączyć przez SSH z ${ip}."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"ip\": \"${ip}\", \"ping\": ${ping_ok}, \"ssh\": false}"
        fi
        return 1
    fi

    _info "Router dostępny: ${ip} (hostname: ${hostname}, ping: ${latency_ms}ms)"
    _log "INFO" "router_check_connection: ok, hostname=${hostname}"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"ip\": \"${ip}\", \"hostname\": \"${hostname}\", \"ping\": ${ping_ok}, \"ssh\": true, \"latency_ms\": ${latency_ms}}"
    else
        printf '%s\n' "${ip}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_get_info IP
# Pobiera informacje o routerze: wersja OpenWrt, uptime, pamięć, klienci.
# -----------------------------------------------------------------------------
router_get_info() {
    local ip="${1:-}"
    _header "Informacje o routerze OpenWrt"
    _log "INFO" "router_get_info: ip=${ip}"

    router_check_connection "${ip}" > /dev/null 2>&1 || { _error "Brak połączenia z routerem."; return 1; }

    # Wersja OpenWrt
    local openwrt_version
    openwrt_version="$(_ssh "${ip}" "cat /etc/openwrt_release 2>/dev/null | grep DISTRIB_DESCRIPTION | cut -d= -f2 | tr -d '\"'" | tr -d '\r')" || openwrt_version="N/A"

    # Wersja jądra
    local kernel_version
    kernel_version="$(_ssh "${ip}" "uname -r" | tr -d '\r')" || kernel_version="N/A"

    # Uptime
    local uptime_str
    uptime_str="$(_ssh "${ip}" "uptime" | tr -d '\r')" || uptime_str="N/A"

    # Pamięć
    local mem_total mem_free mem_used
    mem_total="$(_ssh "${ip}" "grep MemTotal /proc/meminfo | awk '{print \$2}'" | tr -d '\r')" || mem_total="0"
    mem_free="$(_ssh "${ip}" "grep MemFree /proc/meminfo | awk '{print \$2}'" | tr -d '\r')" || mem_free="0"
    mem_used=$(( mem_total - mem_free ))

    # Wolne miejsce /
    local disk_free
    disk_free="$(_ssh "${ip}" "df / | tail -1 | awk '{print \$4}'" | tr -d '\r')" || disk_free="N/A"

    # Liczba podłączonych klientów WiFi
    local wifi_clients
    wifi_clients="$(_ssh "${ip}" "iw dev 2>/dev/null | grep -c 'station' || echo 0" | tr -d '\r')" || wifi_clients="0"

    # Interfejsy sieciowe z IP
    local interfaces
    interfaces="$(_ssh "${ip}" "ip -br addr 2>/dev/null || ifconfig 2>/dev/null | grep -E '^[a-z]|inet '" | tr -d '\r')" || interfaces="N/A"

    # Adres MAC WAN
    local wan_mac
    wan_mac="$(_ssh "${ip}" "cat /sys/class/net/eth0/address 2>/dev/null || echo N/A" | tr -d '\r')" || wan_mac="N/A"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{
  \"ok\": true,
  \"ip\": \"${ip}\",
  \"openwrt_version\": \"${openwrt_version}\",
  \"kernel\": \"${kernel_version}\",
  \"uptime\": \"${uptime_str}\",
  \"memory_total_kb\": ${mem_total},
  \"memory_used_kb\": ${mem_used},
  \"memory_free_kb\": ${mem_free},
  \"disk_free_kb\": \"${disk_free}\",
  \"wifi_clients\": \"${wifi_clients}\",
  \"wan_mac\": \"${wan_mac}\"
}"
    else
        printf '  %-26s %s\n' "Router IP:"            "${ip}"
        printf '  %-26s %s\n' "OpenWrt:"              "${openwrt_version}"
        printf '  %-26s %s\n' "Jądro:"                "${kernel_version}"
        printf '  %-26s %s\n' "Uptime:"               "${uptime_str}"
        printf '  %-26s %d/%d kB\n' "Pamięć (użyta/całk.):" "${mem_used}" "${mem_total}"
        printf '  %-26s %s kB\n' "Wolne miejsce /:"   "${disk_free}"
        printf '  %-26s %s\n' "Klienci WiFi:"         "${wifi_clients}"
        printf '  %-26s %s\n' "MAC WAN:"              "${wan_mac}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_deploy_binary IP BINARY_PATH TARGET_PATH
# Kopiuje binarny plik SYLION relay na router przez SCP i restartuje serwis.
#
# Argumenty:
#   ip          — adres IP routera
#   binary_path — ścieżka do pliku binarnego na lokalnym komputerze
#   target_path — ścieżka docelowa na routerze (np. /usr/bin/sylion-relay)
# -----------------------------------------------------------------------------
router_deploy_binary() {
    local ip="${1:-}"
    local binary_path="${2:-}"
    local target_path="${3:-/usr/bin/sylion-relay}"
    _header "Wdrożenie binarki SYLION na router"
    _log "INFO" "router_deploy_binary: ip=${ip}, binary=${binary_path}, target=${target_path}"

    # Walidacja
    if [[ -z "${ip}" ]] || [[ -z "${binary_path}" ]]; then
        _error "Użycie: router_deploy_binary <ip> <binary_path> [target_path]"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_arguments"}'
        fi
        return 1
    fi

    if [[ ! -f "${binary_path}" ]]; then
        _error "Plik binarny nie istnieje: ${binary_path}"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"file_not_found\", \"path\": \"${binary_path}\"}"
        fi
        return 1
    fi

    router_check_connection "${ip}" > /dev/null 2>&1 || { _error "Brak połączenia z routerem."; return 1; }

    local file_size
    file_size="$(du -sh "${binary_path}" | cut -f1)"
    _info "Przesyłam binarke: ${binary_path} (${file_size}) -> ${ip}:${target_path}"

    # Zatrzymaj serwis przed wdrożeniem (jeśli działa)
    _info "Zatrzymuję serwis ${SYLION_SERVICE}..."
    _ssh "${ip}" "/etc/init.d/${SYLION_SERVICE} stop 2>/dev/null || true" 2>/dev/null || true

    # Utwórz katalog docelowy jeśli nie istnieje
    local target_dir
    target_dir="$(dirname "${target_path}")"
    _ssh "${ip}" "mkdir -p '${target_dir}'"

    # Skopiuj plik
    _retry _scp_to "${ip}" "${binary_path}" "${target_path}"

    # Nadaj prawa wykonywania
    _ssh "${ip}" "chmod 755 '${target_path}'"

    _info "Binarko wdrożona: ${target_path}"

    # Uruchom serwis ponownie
    _info "Uruchamiam serwis ${SYLION_SERVICE}..."
    local service_start_ok=true
    _ssh "${ip}" "/etc/init.d/${SYLION_SERVICE} start 2>/dev/null || ${target_path} --daemon 2>/dev/null || true" || service_start_ok=false

    if [[ "${service_start_ok}" == "true" ]]; then
        _info "Serwis ${SYLION_SERVICE} uruchomiony."
    else
        _warn "Nie udało się automatycznie uruchomić serwisu ${SYLION_SERVICE}."
    fi

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"action\": \"deploy_binary\", \"ip\": \"${ip}\", \"target\": \"${target_path}\", \"service_started\": ${service_start_ok}}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_update_config IP CONFIG_PATH
# Przesyła plik konfiguracyjny na router i aplikuje go (reload serwisu UCI).
#
# Argumenty:
#   ip          — adres IP routera
#   config_path — ścieżka do pliku konfiguracyjnego na komputerze
# -----------------------------------------------------------------------------
router_update_config() {
    local ip="${1:-}"
    local config_path="${2:-}"
    _header "Aktualizacja konfiguracji routera"
    _log "INFO" "router_update_config: ip=${ip}, config=${config_path}"

    if [[ -z "${ip}" ]] || [[ -z "${config_path}" ]]; then
        _error "Użycie: router_update_config <ip> <config_path>"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_arguments"}'
        fi
        return 1
    fi

    if [[ ! -f "${config_path}" ]]; then
        _error "Plik konfiguracyjny nie istnieje: ${config_path}"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"file_not_found\", \"path\": \"${config_path}\"}"
        fi
        return 1
    fi

    router_check_connection "${ip}" > /dev/null 2>&1 || { _error "Brak połączenia z routerem."; return 1; }

    local filename
    filename="$(basename "${config_path}")"

    # Zapisz kopię zapasową istniejącej konfiguracji
    _info "Wykonuję kopię zapasową istniejącej konfiguracji..."
    _ssh "${ip}" "cp '/etc/config/${filename}' '/etc/config/${filename}.bak.$(date +%Y%m%d%H%M%S)' 2>/dev/null || true" || true

    # Prześlij nową konfigurację
    _info "Przesyłam konfigurację: ${config_path} -> /etc/config/${filename}"
    _retry _scp_to "${ip}" "${config_path}" "/etc/config/${filename}"

    # Zastosuj konfigurację przez UCI reload
    _info "Aplikuję konfigurację (uci reload)..."
    _ssh "${ip}" "uci commit 2>/dev/null || true; /etc/init.d/network reload 2>/dev/null || true"

    # Zrestartuj serwis SYLION jeśli konfiguracja go dotyczy
    if printf '%s' "${filename}" | grep -qi "sylion"; then
        _info "Restartuję serwis ${SYLION_SERVICE}..."
        _ssh "${ip}" "/etc/init.d/${SYLION_SERVICE} restart 2>/dev/null || true" || true
    fi

    _info "Konfiguracja zaktualizowana: /etc/config/${filename}"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"action\": \"update_config\", \"ip\": \"${ip}\", \"remote\": \"/etc/config/${filename}\"}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_sysupgrade IP FIRMWARE_PATH
# Aktualizuje firmware OpenWrt z zachowaniem konfiguracji.
#
# Argumenty:
#   ip            — adres IP routera
#   firmware_path — ścieżka do pliku firmware .bin na komputerze
# -----------------------------------------------------------------------------
router_sysupgrade() {
    local ip="${1:-}"
    local firmware_path="${2:-}"
    _header "Aktualizacja firmware OpenWrt"
    _log "INFO" "router_sysupgrade: ip=${ip}, firmware=${firmware_path}"

    if [[ -z "${ip}" ]] || [[ -z "${firmware_path}" ]]; then
        _error "Użycie: router_sysupgrade <ip> <firmware_path>"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_arguments"}'
        fi
        return 1
    fi

    if [[ ! -f "${firmware_path}" ]]; then
        _error "Plik firmware nie istnieje: ${firmware_path}"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"file_not_found\", \"path\": \"${firmware_path}\"}"
        fi
        return 1
    fi

    router_check_connection "${ip}" > /dev/null 2>&1 || { _error "Brak połączenia z routerem."; return 1; }

    local file_size
    file_size="$(du -sh "${firmware_path}" | cut -f1)"
    _warn "UWAGA: Aktualizacja firmware jest operacją nieodwracalną!"
    _info "Plik firmware: ${firmware_path} (${file_size})"

    # Wykonaj kopię zapasową przed aktualizacją
    _info "Wykonuję kopię zapasową konfiguracji przed aktualizacją..."
    local backup_dir="${LOG_DIR}/router_backup_$(date +%Y%m%d_%H%M%S)"
    router_backup "${ip}" "${backup_dir}" || _warn "Kopia zapasowa nieudana, kontynuuję..."

    # Prześlij firmware na router
    _info "Przesyłam firmware na router: /tmp/firmware.bin"
    _scp_to "${ip}" "${firmware_path}" "/tmp/firmware.bin"

    # Weryfikacja MD5 (opcjonalna)
    local local_md5 remote_md5
    local_md5="$(md5sum "${firmware_path}" | awk '{print $1}')"
    remote_md5="$(_ssh "${ip}" "md5sum /tmp/firmware.bin | awk '{print \$1}'" | tr -d '\r')" || remote_md5=""

    if [[ -n "${remote_md5}" ]] && [[ "${local_md5}" != "${remote_md5}" ]]; then
        _error "Suma kontrolna MD5 nie zgadza się! Przerywam aktualizację."
        _ssh "${ip}" "rm -f /tmp/firmware.bin" || true
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"md5_mismatch\", \"local\": \"${local_md5}\", \"remote\": \"${remote_md5}\"}"
        fi
        return 1
    fi

    _info "MD5: ${local_md5} — OK"
    _info "Uruchamiam sysupgrade -n (zachowanie konfiguracji)..."

    # Uruchom sysupgrade — połączenie zostanie zerwane podczas restartu
    # Używamy nohup i & żeby polecenie nie zależało od sesji SSH
    _ssh "${ip}" "nohup sh -c 'sleep 2 && sysupgrade -v /tmp/firmware.bin' > /tmp/sysupgrade.log 2>&1 &"

    _info "Sysupgrade uruchomiony. Router zrestartuje się za chwilę."
    _info "Czekam 90 sekund na zakończenie aktualizacji i restart..."
    sleep 90

    # Sprawdź czy router wróci online
    local wait_count=0
    while ! router_check_connection "${ip}" > /dev/null 2>&1; do
        if (( wait_count >= 6 )); then
            _error "Router nie wrócił online po aktualizacji (timeout 2min)."
            if [[ "${OUTPUT_JSON}" == "true" ]]; then
                _json_output "{\"ok\": false, \"error\": \"router_not_online_after_upgrade\", \"ip\": \"${ip}\"}"
            fi
            return 1
        fi
        _info "Czekam na restart routera... (${wait_count}/6)"
        sleep 20
        (( wait_count++ ))
    done

    _info "Router wrócił online po aktualizacji!"

    # Pobierz nową wersję OpenWrt
    local new_version
    new_version="$(_ssh "${ip}" "cat /etc/openwrt_release | grep DISTRIB_DESCRIPTION | cut -d= -f2 | tr -d '\"'" | tr -d '\r')" || new_version="N/A"
    _info "Nowa wersja: ${new_version}"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"action\": \"sysupgrade\", \"ip\": \"${ip}\", \"new_version\": \"${new_version}\"}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_install_packages IP PACKAGES
# Instaluje pakiety przez opkg.
#
# Argumenty:
#   ip       — adres IP routera
#   packages — pakiety do zainstalowania (oddzielone spacjami)
# -----------------------------------------------------------------------------
router_install_packages() {
    local ip="${1:-}"
    local packages="${2:-}"
    _header "Instalacja pakietów OpenWrt"
    _log "INFO" "router_install_packages: ip=${ip}, packages=${packages}"

    if [[ -z "${ip}" ]] || [[ -z "${packages}" ]]; then
        _error "Użycie: router_install_packages <ip> <pakiet1 pakiet2 ...>"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_arguments"}'
        fi
        return 1
    fi

    router_check_connection "${ip}" > /dev/null 2>&1 || { _error "Brak połączenia z routerem."; return 1; }

    # Aktualizuj listę pakietów
    _info "Aktualizuję listę pakietów (opkg update)..."
    local update_exit=0
    _ssh "${ip}" "opkg update 2>&1" || update_exit=$?
    if (( update_exit != 0 )); then
        _warn "opkg update zwrócił kod ${update_exit}. Próbuję kontynuować instalację..."
    fi

    # Instaluj pakiety
    _info "Instaluję pakiety: ${packages}"
    local install_output install_exit=0
    install_output="$(_ssh "${ip}" "opkg install ${packages} 2>&1")" || install_exit=$?

    if (( install_exit != 0 )); then
        _error "Instalacja pakietów nieudana (kod: ${install_exit})."
        _error "Wyjście: ${install_output}"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"install_failed\", \"exit_code\": ${install_exit}}"
        fi
        return 1
    fi

    _info "Pakiety zainstalowane: ${packages}"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"action\": \"install_packages\", \"ip\": \"${ip}\", \"packages\": \"${packages}\"}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_get_logs IP [SERVICE]
# Pobiera logi z routera — syslog lub konkretnego serwisu.
#
# Argumenty:
#   ip      — adres IP routera
#   service — nazwa serwisu (domyślnie: sylion-relay)
# -----------------------------------------------------------------------------
router_get_logs() {
    local ip="${1:-}"
    local service="${2:-${SYLION_SERVICE}}"
    _header "Logi routera: ${service}"
    _log "INFO" "router_get_logs: ip=${ip}, service=${service}"

    if [[ -z "${ip}" ]]; then
        _error "Nie podano adresu IP routera."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_ip"}'
        fi
        return 1
    fi

    router_check_connection "${ip}" > /dev/null 2>&1 || { _error "Brak połączenia z routerem."; return 1; }

    local logs
    # Spróbuj logread z filtrem, potem fallback na /var/log/messages
    logs="$(_ssh "${ip}" "logread 2>/dev/null | grep -i '${service}' | tail -200 || grep -i '${service}' /var/log/messages 2>/dev/null | tail -200 || echo 'Brak logów dla: ${service}'" | tr -d '\r')" || logs="Błąd odczytu logów"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        local log_lines
        log_lines="$(printf '%s\n' "${logs}" | wc -l | tr -d ' ')"
        local escaped_logs
        escaped_logs="$(printf '%s' "${logs}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')"
        _json_output "{\"ok\": true, \"ip\": \"${ip}\", \"service\": \"${service}\", \"line_count\": ${log_lines}, \"logs\": ${escaped_logs}}"
    else
        printf '%s\n' "${logs}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_health_check IP
# Weryfikuje czy SYLION relay działa prawidłowo na routerze.
# -----------------------------------------------------------------------------
router_health_check() {
    local ip="${1:-}"
    _header "Health check SYLION Relay (router)"
    _log "INFO" "router_health_check: ip=${ip}"

    if [[ -z "${ip}" ]]; then
        _error "Nie podano adresu IP routera."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_ip"}'
        fi
        return 1
    fi

    local status="ok"
    local details=()

    # Sprawdź połączenie SSH
    if ! router_check_connection "${ip}" > /dev/null 2>&1; then
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"status\": \"no_connection\", \"ip\": \"${ip}\", \"details\": []}"
        else
            _error "Brak połączenia SSH z ${ip}."
        fi
        return 1
    fi
    details+=('{"check": "ssh_connection", "ok": true}')

    # Sprawdź czy plik binarny SYLION istnieje
    local binary_check
    binary_check="$(_ssh "${ip}" "test -f /usr/bin/sylion-relay && echo exists || echo missing" | tr -d '\r')" || binary_check="error"
    if [[ "${binary_check}" == "exists" ]]; then
        details+=('{"check": "sylion_binary", "ok": true, "path": "/usr/bin/sylion-relay"}')
        _info "Binarko SYLION relay: OK (/usr/bin/sylion-relay)"
    else
        details+=('{"check": "sylion_binary", "ok": false, "path": "/usr/bin/sylion-relay"}')
        _warn "Binarko SYLION relay nie znaleziono w /usr/bin/sylion-relay"
        status="degraded"
    fi

    # Sprawdź czy proces SYLION działa
    local proc_check
    proc_check="$(_ssh "${ip}" "pgrep -l sylion 2>/dev/null || echo none" | tr -d '\r')"
    if [[ "${proc_check}" != "none" ]] && [[ -n "${proc_check}" ]]; then
        details+=('{"check": "sylion_process", "ok": true, "pid_info": "'"${proc_check}"'"}')
        _info "Proces SYLION relay: uruchomiony (${proc_check})"
    else
        details+=('{"check": "sylion_process", "ok": false}')
        _warn "Proces SYLION relay nie jest uruchomiony."
        status="degraded"
    fi

    # Sprawdź serwis init.d
    local service_status
    service_status="$(_ssh "${ip}" "/etc/init.d/${SYLION_SERVICE} status 2>/dev/null || echo unknown" | tr -d '\r')" || service_status="unknown"
    local service_ok=true
    printf '%s' "${service_status}" | grep -qi "running" || service_ok=false
    details+=("{\"check\": \"init_service\", \"ok\": ${service_ok}, \"status\": \"${service_status}\"}")
    _info "Serwis init.d ${SYLION_SERVICE}: ${service_status}"

    # Sprawdź użycie pamięci
    local mem_total mem_free
    mem_total="$(_ssh "${ip}" "grep MemTotal /proc/meminfo | awk '{print \$2}'" | tr -d '\r')" || mem_total="0"
    mem_free="$(_ssh "${ip}" "grep MemFree /proc/meminfo | awk '{print \$2}'" | tr -d '\r')" || mem_free="0"
    local mem_pct=0
    if (( mem_total > 0 )); then
        mem_pct=$(( (mem_total - mem_free) * 100 / mem_total ))
    fi
    details+=("{\"check\": \"memory_usage_pct\", \"ok\": true, \"value\": ${mem_pct}}")
    _info "Użycie pamięci routera: ${mem_pct}% (${mem_free}/${mem_total} kB wolne)"

    # Sprawdź łączność WAN (ping 8.8.8.8)
    local wan_check
    wan_check="$(_ssh "${ip}" "ping -c 1 -W 3 8.8.8.8 &>/dev/null && echo ok || echo fail" | tr -d '\r')" || wan_check="fail"
    local wan_ok=false
    [[ "${wan_check}" == "ok" ]] && wan_ok=true
    details+=("{\"check\": \"wan_connectivity\", \"ok\": ${wan_ok}}")
    if [[ "${wan_ok}" == "true" ]]; then
        _info "Łączność WAN: OK"
    else
        _warn "Brak łączności WAN."
    fi

    local details_json
    details_json="$(IFS=','; printf '[%s]' "${details[*]}")"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": $([ \"${status}\" = 'ok' ] && echo 'true' || echo 'false'), \"status\": \"${status}\", \"ip\": \"${ip}\", \"details\": ${details_json}}"
    else
        if [[ "${status}" == "ok" ]]; then
            _info "Health check zakończony: ${status}"
        else
            _warn "Health check zakończony: ${status}"
        fi
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_firewall_rules IP
# Wyświetla aktualne reguły firewalla (iptables/nftables).
# -----------------------------------------------------------------------------
router_firewall_rules() {
    local ip="${1:-}"
    _header "Reguły firewalla routera"
    _log "INFO" "router_firewall_rules: ip=${ip}"

    if [[ -z "${ip}" ]]; then
        _error "Nie podano adresu IP routera."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_ip"}'
        fi
        return 1
    fi

    router_check_connection "${ip}" > /dev/null 2>&1 || { _error "Brak połączenia z routerem."; return 1; }

    # Pobierz reguły iptables lub nftables
    local iptables_rules nftables_rules uci_firewall
    iptables_rules="$(_ssh "${ip}" "iptables -L -n -v 2>/dev/null || echo 'iptables niedostępny'" | tr -d '\r')" || iptables_rules="błąd"
    nftables_rules="$(_ssh "${ip}" "nft list ruleset 2>/dev/null || echo 'nftables niedostępny'" | tr -d '\r')" || nftables_rules="błąd"
    uci_firewall="$(_ssh "${ip}" "uci show firewall 2>/dev/null | head -50 || echo 'brak konfiguracji UCI firewall'" | tr -d '\r')" || uci_firewall="błąd"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        local escaped_ipt escaped_nft escaped_uci
        escaped_ipt="$(printf '%s' "${iptables_rules}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')"
        escaped_nft="$(printf '%s' "${nftables_rules}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')"
        escaped_uci="$(printf '%s' "${uci_firewall}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')"
        _json_output "{\"ok\": true, \"ip\": \"${ip}\", \"iptables\": ${escaped_ipt}, \"nftables\": ${escaped_nft}, \"uci_firewall\": ${escaped_uci}}"
    else
        printf '%b--- iptables ---%b\n%s\n' "${CYAN}" "${RESET}" "${iptables_rules}"
        printf '%b--- nftables ---%b\n%s\n' "${CYAN}" "${RESET}" "${nftables_rules}"
        printf '%b--- UCI firewall ---%b\n%s\n' "${CYAN}" "${RESET}" "${uci_firewall}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_restart_service IP SERVICE
# Restartuje podany serwis na routerze przez init.d.
#
# Argumenty:
#   ip      — adres IP routera
#   service — nazwa serwisu (domyślnie: sylion-relay)
# -----------------------------------------------------------------------------
router_restart_service() {
    local ip="${1:-}"
    local service="${2:-${SYLION_SERVICE}}"
    _header "Restart serwisu: ${service}"
    _log "INFO" "router_restart_service: ip=${ip}, service=${service}"

    if [[ -z "${ip}" ]]; then
        _error "Nie podano adresu IP routera."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_ip"}'
        fi
        return 1
    fi

    router_check_connection "${ip}" > /dev/null 2>&1 || { _error "Brak połączenia z routerem."; return 1; }

    _info "Restartuję serwis ${service} na ${ip}..."
    local restart_output restart_exit=0
    restart_output="$(_ssh "${ip}" "/etc/init.d/${service} restart 2>&1")" || restart_exit=$?

    if (( restart_exit != 0 )); then
        _error "Restart serwisu ${service} nieudany (kod: ${restart_exit})."
        _error "Wyjście: ${restart_output}"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"restart_failed\", \"service\": \"${service}\", \"exit_code\": ${restart_exit}}"
        fi
        return 1
    fi

    _info "Serwis ${service} zrestartowany."

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"action\": \"restart_service\", \"ip\": \"${ip}\", \"service\": \"${service}\"}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: router_backup IP BACKUP_DIR
# Wykonuje kopię zapasową konfiguracji routera do lokalnego katalogu.
#
# Argumenty:
#   ip         — adres IP routera
#   backup_dir — lokalny katalog docelowy dla backupu
# -----------------------------------------------------------------------------
router_backup() {
    local ip="${1:-}"
    local backup_dir="${2:-${LOG_DIR}/router_backup_$(date +%Y%m%d_%H%M%S)}"
    _header "Backup konfiguracji routera"
    _log "INFO" "router_backup: ip=${ip}, backup_dir=${backup_dir}"

    if [[ -z "${ip}" ]]; then
        _error "Nie podano adresu IP routera."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_ip"}'
        fi
        return 1
    fi

    router_check_connection "${ip}" > /dev/null 2>&1 || { _error "Brak połączenia z routerem."; return 1; }

    mkdir -p "${backup_dir}"

    # Utwórz archiwum konfiguracji na routerze
    local remote_backup="/tmp/router_backup_$(date +%Y%m%d%H%M%S).tar.gz"
    _info "Tworzę archiwum konfiguracji na routerze: ${remote_backup}"
    _ssh "${ip}" "sysupgrade --create-backup '${remote_backup}' 2>/dev/null || tar -czf '${remote_backup}' /etc/config /etc/passwd /etc/shadow /etc/hosts 2>/dev/null"

    # Pobierz archiwum na lokalny komputer
    local local_backup="${backup_dir}/router_backup_${ip//./_}.tar.gz"
    _info "Pobieranie backupu do: ${local_backup}"
    _scp_from "${ip}" "${remote_backup}" "${local_backup}"

    # Usuń tymczasowy plik na routerze
    _ssh "${ip}" "rm -f '${remote_backup}'" || true

    local backup_size
    backup_size="$(du -sh "${local_backup}" | cut -f1)"
    _info "Backup zapisany: ${local_backup} (${backup_size})"
    _log "INFO" "router_backup: sukces, ${local_backup}"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"action\": \"backup\", \"ip\": \"${ip}\", \"backup_path\": \"${local_backup}\", \"size\": \"${backup_size}\"}"
    else
        printf '%s\n' "${local_backup}"
    fi
}

# -----------------------------------------------------------------------------
# Obsługa wywołania bezpośredniego
# -----------------------------------------------------------------------------
_main() {
    local args=()
    for arg in "$@"; do
        if [[ "${arg}" == "--json" ]]; then
            OUTPUT_JSON=true
            _init_colors
        else
            args+=("${arg}")
        fi
    done

    if [[ ${#args[@]} -eq 0 ]]; then
        printf 'Użycie: %s [--json] <funkcja> [argumenty...]\n\n' "$(basename "$0")"
        printf 'Dostępne funkcje:\n'
        printf '  router_check_connection <ip>\n'
        printf '  router_get_info <ip>\n'
        printf '  router_deploy_binary <ip> <binary_path> [target_path]\n'
        printf '  router_update_config <ip> <config_path>\n'
        printf '  router_sysupgrade <ip> <firmware_path>\n'
        printf '  router_install_packages <ip> "<pakiet1 pakiet2>"\n'
        printf '  router_get_logs <ip> [service]\n'
        printf '  router_health_check <ip>\n'
        printf '  router_firewall_rules <ip>\n'
        printf '  router_restart_service <ip> [service]\n'
        printf '  router_backup <ip> [backup_dir]\n'
        exit 0
    fi

    local func="${args[0]}"
    local func_args=("${args[@]:1}")

    if ! declare -f "${func}" > /dev/null 2>&1; then
        _error "Nieznana funkcja: ${func}"
        exit 1
    fi

    "${func}" "${func_args[@]+"${func_args[@]}"}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    _main "$@"
fi
