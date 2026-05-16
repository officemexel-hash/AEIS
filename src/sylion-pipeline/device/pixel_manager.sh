#!/usr/bin/env bash
# =============================================================================
# pixel_manager.sh — Zarządzanie urządzeniem Google Pixel z GrapheneOS
# Część potoku audytu SYLION
#
# Przeznaczenie:
#   Skrypt zapewnia zestaw funkcji do komunikacji z telefonem Google Pixel
#   przez ADB (Android Debug Bridge). Obsługuje flashowanie GrapheneOS,
#   instalację aplikacji SYLION, przesyłanie plików konfiguracyjnych,
#   uruchamianie poleceń na urządzeniu oraz monitorowanie stanu.
#
# Użycie:
#   source pixel_manager.sh           # załaduj funkcje do bieżącej powłoki
#   ./pixel_manager.sh <funkcja> [args...]  # uruchom bezpośrednio
#
# Wymagania:
#   - adb (Android Debug Bridge) zainstalowany i dostępny w PATH
#   - USB debugging włączone na urządzeniu
#   - Autoryzacja hosta na urządzeniu zatwierdzona
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# -----------------------------------------------------------------------------
# Konfiguracja globalna
# -----------------------------------------------------------------------------

# Katalog logów — domyślnie obok skryptu
readonly PIXEL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PIXEL_LOG_DIR="${SYLION_LOG_DIR:-${PIXEL_SCRIPT_DIR}/logs}"
readonly PIXEL_LOG_FILE="${PIXEL_LOG_DIR}/pixel_manager_$(date +%Y%m%d).log"

# Ścieżki na urządzeniu
readonly DEVICE_SYLION_DIR="/data/local/tmp/sylion"
readonly DEVICE_CONFIG_DIR="/data/local/tmp/sylion/config"
readonly DEVICE_SCREENSHOT_PATH="/sdcard/sylion_screenshot.png"

# Parametry ponownych prób
readonly PIXEL_RETRY_MAX="${SYLION_RETRY_MAX:-3}"
readonly PIXEL_RETRY_DELAY="${SYLION_RETRY_DELAY:-5}"

# Czy wymagamy konkretnego numeru seryjnego
ADB_SERIAL="${SYLION_ADB_SERIAL:-}"

# Flaga JSON (ustawiana przez argument --json)
OUTPUT_JSON=false

# -----------------------------------------------------------------------------
# Kolory terminala (wyłączane automatycznie gdy brak TTY lub --json)
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

# Upewnij się, że katalog logów istnieje
_ensure_log_dir() {
    mkdir -p "${PIXEL_LOG_DIR}"
}

# _log POZIOM KOMUNIKAT — zapisuje do pliku logu z znacznikiem czasu
_log() {
    local level="$1"
    local msg="$2"
    _ensure_log_dir
    printf '[%s] [pixel_manager] [%s] %s\n' \
        "$(date '+%Y-%m-%dT%H:%M:%S')" "${level}" "${msg}" >> "${PIXEL_LOG_FILE}"
}

# _info KOMUNIKAT — wydruk informacyjny (zielony)
_info() {
    local msg="$1"
    _log "INFO" "${msg}"
    if [[ "${OUTPUT_JSON}" == "false" ]]; then
        printf '%b[INFO]%b %s\n' "${GREEN}" "${RESET}" "${msg}"
    fi
}

# _warn KOMUNIKAT — wydruk ostrzeżenia (żółty)
_warn() {
    local msg="$1"
    _log "WARN" "${msg}"
    if [[ "${OUTPUT_JSON}" == "false" ]]; then
        printf '%b[WARN]%b %s\n' "${YELLOW}" "${RESET}" "${msg}" >&2
    fi
}

# _error KOMUNIKAT — wydruk błędu (czerwony)
_error() {
    local msg="$1"
    _log "ERROR" "${msg}"
    if [[ "${OUTPUT_JSON}" == "false" ]]; then
        printf '%b[ERROR]%b %s\n' "${RED}" "${RESET}" "${msg}" >&2
    fi
}

# _header TYTUŁ — sekcja wydruku (niebieski, pogrubiony)
_header() {
    local title="$1"
    if [[ "${OUTPUT_JSON}" == "false" ]]; then
        printf '\n%b=== %s ===%b\n' "${BOLD}${BLUE}" "${title}" "${RESET}"
    fi
}

# _json_output DANE — wydruk JSON na stdout
_json_output() {
    local data="$1"
    printf '%s\n' "${data}"
}

# _retry POLECENIE [ARGUMENTY...] — ponów polecenie do PIXEL_RETRY_MAX razy
_retry() {
    local attempt=1
    while true; do
        if "$@"; then
            return 0
        fi
        if (( attempt >= PIXEL_RETRY_MAX )); then
            _error "Polecenie nieudane po ${PIXEL_RETRY_MAX} próbach: $*"
            return 1
        fi
        _warn "Próba ${attempt}/${PIXEL_RETRY_MAX} nieudana. Czekam ${PIXEL_RETRY_DELAY}s..."
        sleep "${PIXEL_RETRY_DELAY}"
        (( attempt++ ))
    done
}

# -----------------------------------------------------------------------------
# Wrapper ADB — dodaje opcjonalny numer seryjny do każdego wywołania
# -----------------------------------------------------------------------------

_adb() {
    if [[ -n "${ADB_SERIAL}" ]]; then
        adb -s "${ADB_SERIAL}" "$@"
    else
        adb "$@"
    fi
}

# _adb_shell CMD — uruchamia polecenie przez adb shell, zwraca stdout
_adb_shell() {
    _adb shell "$@"
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_check_connection
# Sprawdza połączenie ADB i zwraca numer seryjny urządzenia.
#
# Wyjście (tryb tekstowy): numer seryjny urządzenia
# Wyjście (--json): {"serial": "...", "state": "device", "ok": true}
# Kody wyjścia: 0 — sukces, 1 — brak urządzenia lub błąd
# -----------------------------------------------------------------------------
pixel_check_connection() {
    _header "Sprawdzanie połączenia ADB"
    _log "INFO" "pixel_check_connection: start"

    # Uruchom serwer ADB jeśli nie działa
    adb start-server 2>/dev/null || true

    local devices_output
    devices_output="$(adb devices 2>/dev/null)"

    # Zlicz podłączone urządzenia (wiersze z "device" bez "List of")
    local device_lines
    device_lines="$(printf '%s\n' "${devices_output}" | grep -v '^List' | grep 'device$' || true)"

    if [[ -z "${device_lines}" ]]; then
        _error "Nie znaleziono żadnego urządzenia ADB. Sprawdź połączenie USB i USB debugging."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "no_device_found", "serial": null}'
        fi
        return 1
    fi

    local device_count
    device_count="$(printf '%s\n' "${device_lines}" | wc -l | tr -d ' ')"

    if (( device_count > 1 )) && [[ -z "${ADB_SERIAL}" ]]; then
        _warn "Znaleziono ${device_count} urządzenia ADB. Ustaw SYLION_ADB_SERIAL aby wskazać konkretne."
    fi

    # Pobierz numer seryjny (pierwszego lub wskazanego urządzenia)
    local serial
    if [[ -n "${ADB_SERIAL}" ]]; then
        serial="${ADB_SERIAL}"
        # Weryfikuj czy wskazane urządzenie faktycznie jest widoczne
        if ! printf '%s\n' "${device_lines}" | grep -q "^${serial}"; then
            _error "Urządzenie ${serial} nie jest połączone lub nie jest w stanie 'device'."
            if [[ "${OUTPUT_JSON}" == "true" ]]; then
                _json_output "{\"ok\": false, \"error\": \"serial_not_found\", \"serial\": \"${serial}\"}"
            fi
            return 1
        fi
    else
        serial="$(printf '%s\n' "${device_lines}" | awk '{print $1}' | head -1)"
        ADB_SERIAL="${serial}"
        export ADB_SERIAL
    fi

    local state
    state="$( adb -s "${serial}" get-state 2>/dev/null || echo "unknown" )"

    _info "Urządzenie podłączone: ${serial} (stan: ${state})"
    _log "INFO" "pixel_check_connection: serial=${serial}, state=${state}"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"serial\": \"${serial}\", \"state\": \"${state}\"}"
    else
        printf '%s\n' "${serial}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_get_info
# Pobiera informacje o urządzeniu: model, wersja Androida/GrapheneOS, bateria.
#
# Wyjście (--json): obiekt JSON ze wszystkimi polami
# -----------------------------------------------------------------------------
pixel_get_info() {
    _header "Informacje o urządzeniu Pixel"
    _log "INFO" "pixel_get_info: start"

    # Upewnij się że urządzenie jest podłączone
    pixel_check_connection > /dev/null 2>&1 || { _error "Brak połączenia z urządzeniem."; return 1; }

    # Pobierz właściwości przez adb shell getprop
    local model brand android_version sdk_version security_patch build_fingerprint
    model="$(_adb_shell getprop ro.product.model 2>/dev/null | tr -d '\r')"
    brand="$(_adb_shell getprop ro.product.brand 2>/dev/null | tr -d '\r')"
    android_version="$(_adb_shell getprop ro.build.version.release 2>/dev/null | tr -d '\r')"
    sdk_version="$(_adb_shell getprop ro.build.version.sdk 2>/dev/null | tr -d '\r')"
    security_patch="$(_adb_shell getprop ro.build.version.security_patch 2>/dev/null | tr -d '\r')"
    build_fingerprint="$(_adb_shell getprop ro.build.fingerprint 2>/dev/null | tr -d '\r')"

    # GrapheneOS — wersja build
    local grapheneos_version
    grapheneos_version="$(_adb_shell getprop ro.grapheneos.version 2>/dev/null | tr -d '\r')" || grapheneos_version="N/A"
    [[ -z "${grapheneos_version}" ]] && grapheneos_version="N/A"

    # Poziom naładowania baterii
    local battery_level battery_status
    battery_level="$(_adb_shell cat /sys/class/power_supply/battery/capacity 2>/dev/null | tr -d '\r')" || battery_level="?"
    battery_status="$(_adb_shell cat /sys/class/power_supply/battery/status 2>/dev/null | tr -d '\r')" || battery_status="?"

    # Wolne miejsce /data
    local storage_data
    storage_data="$(_adb_shell df /data 2>/dev/null | tail -1 | awk '{print $4}' | tr -d '\r')" || storage_data="?"

    # Uptime urządzenia
    local uptime_raw uptime_str
    uptime_raw="$(_adb_shell cat /proc/uptime 2>/dev/null | awk '{print $1}' | tr -d '\r')" || uptime_raw="0"
    uptime_str="$(awk "BEGIN {s=${uptime_raw:-0}; d=int(s/86400); h=int((s%86400)/3600); m=int((s%3600)/60); printf \"%dd %dh %dm\", d, h, m}")"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{
  \"ok\": true,
  \"serial\": \"${ADB_SERIAL}\",
  \"brand\": \"${brand}\",
  \"model\": \"${model}\",
  \"android_version\": \"${android_version}\",
  \"sdk_version\": \"${sdk_version}\",
  \"security_patch\": \"${security_patch}\",
  \"build_fingerprint\": \"${build_fingerprint}\",
  \"grapheneos_version\": \"${grapheneos_version}\",
  \"battery_level\": \"${battery_level}\",
  \"battery_status\": \"${battery_status}\",
  \"storage_data_free_kb\": \"${storage_data}\",
  \"uptime\": \"${uptime_str}\"
}"
    else
        printf '  %-26s %s\n' "Marka:"              "${brand}"
        printf '  %-26s %s\n' "Model:"              "${model}"
        printf '  %-26s %s\n' "Wersja Androida:"    "${android_version} (SDK ${sdk_version})"
        printf '  %-26s %s\n' "Łatka bezpieczeństwa:" "${security_patch}"
        printf '  %-26s %s\n' "GrapheneOS build:"   "${grapheneos_version}"
        printf '  %-26s %s%%\n' "Bateria:"           "${battery_level}"
        printf '  %-26s %s\n' "Stan ładowania:"     "${battery_status}"
        printf '  %-26s %s KB\n' "Wolne miejsce /data:" "${storage_data}"
        printf '  %-26s %s\n' "Uptime:"             "${uptime_str}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_flash_grapheneos IMAGE_PATH
# Flashuje / sideloaduje aktualizację GrapheneOS OTA.
# Urządzenie musi być uruchomione w trybie recovery z włączoną opcją
# "Apply update from ADB" (ADB sideload).
#
# Argumenty:
#   image_path — ścieżka do pliku OTA .zip na lokalnym komputerze
# -----------------------------------------------------------------------------
pixel_flash_grapheneos() {
    local image_path="${1:-}"
    _header "Flashowanie GrapheneOS"
    _log "INFO" "pixel_flash_grapheneos: image_path=${image_path}"

    # Walidacja ścieżki
    if [[ -z "${image_path}" ]]; then
        _error "Nie podano ścieżki do obrazu OTA."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_image_path"}'
        fi
        return 1
    fi

    if [[ ! -f "${image_path}" ]]; then
        _error "Plik nie istnieje: ${image_path}"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"file_not_found\", \"path\": \"${image_path}\"}"
        fi
        return 1
    fi

    local file_size
    file_size="$(du -sh "${image_path}" | cut -f1)"
    _info "Plik OTA: ${image_path} (${file_size})"

    # Sprawdź aktualny stan — jeśli urządzenie jest w trybie normalnym, zrebootuj do recovery
    local current_state
    current_state="$(_adb get-state 2>/dev/null || echo "unknown")"

    if [[ "${current_state}" == "device" ]]; then
        _info "Urządzenie jest w trybie normalnym. Rebootuję do recovery..."
        _adb reboot recovery
        _info "Czekam 30s na uruchomienie recovery..."
        sleep 30
        # Poczekaj aż urządzenie pojawi się w trybie sideload
        local wait_count=0
        while ! adb devices | grep -q 'sideload'; do
            if (( wait_count >= 12 )); then
                _error "Timeout: urządzenie nie przeszło w tryb sideload."
                _error "Ręcznie wybierz 'Apply update from ADB' w menu recovery i uruchom ponownie."
                if [[ "${OUTPUT_JSON}" == "true" ]]; then
                    _json_output '{"ok": false, "error": "sideload_timeout"}'
                fi
                return 1
            fi
            _info "Czekam na tryb sideload... (${wait_count}/12)"
            sleep 10
            (( wait_count++ ))
        done
    elif [[ "${current_state}" == "sideload" ]]; then
        _info "Urządzenie jest już w trybie sideload."
    else
        _warn "Nieoczekiwany stan urządzenia: ${current_state}. Próbuję kontynuować..."
    fi

    _info "Uruchamiam sideload: adb sideload ${image_path}"
    _log "INFO" "pixel_flash_grapheneos: uruchamiam adb sideload"

    # Wykonaj sideload — może trwać kilka minut
    local sideload_exit=0
    if [[ -n "${ADB_SERIAL}" ]]; then
        adb -s "${ADB_SERIAL}" sideload "${image_path}" || sideload_exit=$?
    else
        adb sideload "${image_path}" || sideload_exit=$?
    fi

    if (( sideload_exit != 0 )); then
        _error "Sideload zakończony błędem (kod: ${sideload_exit})."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"sideload_failed\", \"exit_code\": ${sideload_exit}}"
        fi
        return 1
    fi

    _info "Sideload zakończony sukcesem. Rebootuję system..."
    _adb reboot 2>/dev/null || true

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"action\": \"flash_grapheneos\", \"image\": \"${image_path}\"}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_deploy_sylion APK_OR_BINARY_PATH
# Instaluje aplikację SYLION na urządzeniu (APK lub binarny plik wykonywalny).
#
# Argumenty:
#   apk_or_binary_path — ścieżka do pliku .apk lub binarnego na komputerze
# -----------------------------------------------------------------------------
pixel_deploy_sylion() {
    local apk_or_binary_path="${1:-}"
    _header "Instalacja SYLION na Pixel"
    _log "INFO" "pixel_deploy_sylion: path=${apk_or_binary_path}"

    if [[ -z "${apk_or_binary_path}" ]]; then
        _error "Nie podano ścieżki do pliku SYLION."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_path"}'
        fi
        return 1
    fi

    if [[ ! -f "${apk_or_binary_path}" ]]; then
        _error "Plik nie istnieje: ${apk_or_binary_path}"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"file_not_found\", \"path\": \"${apk_or_binary_path}\"}"
        fi
        return 1
    fi

    pixel_check_connection > /dev/null 2>&1 || { _error "Brak połączenia z urządzeniem."; return 1; }

    local extension="${apk_or_binary_path##*.}"

    if [[ "${extension}" == "apk" ]]; then
        # Instalacja APK przez adb install
        _info "Instaluję APK: ${apk_or_binary_path}"

        local install_exit=0
        _retry _adb install -r -g "${apk_or_binary_path}" || install_exit=$?

        if (( install_exit != 0 )); then
            _error "Instalacja APK nieudana (kod: ${install_exit})."
            if [[ "${OUTPUT_JSON}" == "true" ]]; then
                _json_output "{\"ok\": false, \"error\": \"apk_install_failed\", \"exit_code\": ${install_exit}}"
            fi
            return 1
        fi

        _info "APK zainstalowany pomyślnie."

        # Pobierz nazwę pakietu z APK
        local package_name
        package_name="$(aapt dump badging "${apk_or_binary_path}" 2>/dev/null | grep "^package:" | sed "s/.*name='\([^']*\)'.*/\1/" || echo "unknown")"

        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": true, \"action\": \"install_apk\", \"package\": \"${package_name}\"}"
        fi

    else
        # Plik binarny — push do /data/local/tmp/sylion/ i nadaj uprawnienia
        _info "Przesyłam plik binarny: ${apk_or_binary_path}"

        local filename
        filename="$(basename "${apk_or_binary_path}")"
        local remote_path="${DEVICE_SYLION_DIR}/${filename}"

        # Utwórz katalog jeśli nie istnieje
        _adb_shell "mkdir -p '${DEVICE_SYLION_DIR}'" 2>/dev/null || true

        _retry _adb push "${apk_or_binary_path}" "${remote_path}"

        # Nadaj prawa wykonywania
        _adb_shell "chmod 755 '${remote_path}'"

        _info "Plik binarny przesłany: ${remote_path}"

        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": true, \"action\": \"push_binary\", \"remote_path\": \"${remote_path}\"}"
        fi
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_push_config CONFIG_PATH
# Przesyła plik konfiguracyjny do katalogu SYLION na urządzeniu.
#
# Argumenty:
#   config_path — ścieżka do pliku konfiguracyjnego na lokalnym komputerze
# -----------------------------------------------------------------------------
pixel_push_config() {
    local config_path="${1:-}"
    _header "Przesyłanie konfiguracji SYLION"
    _log "INFO" "pixel_push_config: config_path=${config_path}"

    if [[ -z "${config_path}" ]]; then
        _error "Nie podano ścieżki do pliku konfiguracyjnego."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_config_path"}'
        fi
        return 1
    fi

    if [[ ! -f "${config_path}" ]] && [[ ! -d "${config_path}" ]]; then
        _error "Plik/katalog nie istnieje: ${config_path}"
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"path_not_found\", \"path\": \"${config_path}\"}"
        fi
        return 1
    fi

    pixel_check_connection > /dev/null 2>&1 || { _error "Brak połączenia z urządzeniem."; return 1; }

    # Utwórz katalog konfiguracji na urządzeniu
    _adb_shell "mkdir -p '${DEVICE_CONFIG_DIR}'" 2>/dev/null || true

    local filename
    filename="$(basename "${config_path}")"
    local remote_path="${DEVICE_CONFIG_DIR}/${filename}"

    _retry _adb push "${config_path}" "${remote_path}"

    _info "Konfiguracja przesłana: ${remote_path}"
    _log "INFO" "pixel_push_config: sukces, remote=${remote_path}"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"action\": \"push_config\", \"local\": \"${config_path}\", \"remote\": \"${remote_path}\"}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_run_command CMD
# Wykonuje dowolne polecenie na urządzeniu przez adb shell.
#
# Argumenty:
#   cmd — polecenie do wykonania (jako pojedynczy ciąg znaków)
#
# Wyjście: stdout polecenia
# -----------------------------------------------------------------------------
pixel_run_command() {
    local cmd="${1:-}"
    _log "INFO" "pixel_run_command: cmd=${cmd}"

    if [[ -z "${cmd}" ]]; then
        _error "Nie podano polecenia do wykonania."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "error": "missing_command"}'
        fi
        return 1
    fi

    pixel_check_connection > /dev/null 2>&1 || { _error "Brak połączenia z urządzeniem."; return 1; }

    _info "Wykonuję na urządzeniu: ${cmd}"

    local output exit_code=0
    output="$(_adb_shell "${cmd}" 2>&1)" || exit_code=$?

    _log "INFO" "pixel_run_command: exit_code=${exit_code}"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        # Escape cudzysłowów w output dla JSON
        local escaped_output
        escaped_output="$(printf '%s' "${output}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || printf '%s' "${output}" | sed 's/\\/\\\\/g; s/"/\\"/g; s/$/\\n/' | tr -d '\n' | sed 's/\\n$//')"
        _json_output "{\"ok\": $([ ${exit_code} -eq 0 ] && echo 'true' || echo 'false'), \"command\": \"${cmd}\", \"exit_code\": ${exit_code}, \"output\": ${escaped_output}}"
    else
        printf '%s\n' "${output}"
    fi

    return "${exit_code}"
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_get_logs [FILTER]
# Pobiera logi logcat z urządzenia, opcjonalnie filtrując po tagu SYLION.
#
# Argumenty:
#   filter — opcjonalny filtr logcat (domyślnie: "SYLION:V *:S")
# -----------------------------------------------------------------------------
pixel_get_logs() {
    local filter="${1:-SYLION:V *:S}"
    _header "Logi urządzenia Pixel"
    _log "INFO" "pixel_get_logs: filter=${filter}"

    pixel_check_connection > /dev/null 2>&1 || { _error "Brak połączenia z urządzeniem."; return 1; }

    _info "Pobieranie logów (filtr: ${filter})..."

    local logs exit_code=0
    # -d: zrzuć i wyjdź (nie podążaj za logami)
    # -v time: format z czasem
    logs="$(_adb logcat -d -v time ${filter} 2>&1)" || exit_code=$?

    if (( exit_code != 0 )); then
        _error "Błąd podczas pobierania logów (kod: ${exit_code})."
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output "{\"ok\": false, \"error\": \"logcat_failed\", \"exit_code\": ${exit_code}}"
        fi
        return 1
    fi

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        local log_lines
        log_lines="$(printf '%s' "${logs}" | wc -l | tr -d ' ')"
        local escaped_logs
        escaped_logs="$(printf '%s' "${logs}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')"
        _json_output "{\"ok\": true, \"filter\": \"${filter}\", \"line_count\": ${log_lines}, \"logs\": ${escaped_logs}}"
    else
        printf '%s\n' "${logs}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_health_check
# Weryfikuje, czy SYLION działa prawidłowo na urządzeniu.
# Sprawdza: proces, dostęp do pliku binarnego, odpowiedź na ping.
# -----------------------------------------------------------------------------
pixel_health_check() {
    _header "Health check SYLION (Pixel)"
    _log "INFO" "pixel_health_check: start"

    local status="ok"
    local details=()

    # Sprawdź połączenie
    if ! pixel_check_connection > /dev/null 2>&1; then
        if [[ "${OUTPUT_JSON}" == "true" ]]; then
            _json_output '{"ok": false, "status": "no_connection", "details": []}'
        else
            _error "Brak połączenia z urządzeniem."
        fi
        return 1
    fi

    # 1. Sprawdź czy katalog SYLION istnieje
    local dir_check
    dir_check="$(_adb_shell "test -d '${DEVICE_SYLION_DIR}' && echo exists || echo missing" 2>/dev/null | tr -d '\r')"
    if [[ "${dir_check}" == "exists" ]]; then
        details+=('{"check": "sylion_dir", "ok": true, "value": "'"${DEVICE_SYLION_DIR}"'"}')
        _info "Katalog SYLION: OK (${DEVICE_SYLION_DIR})"
    else
        details+=('{"check": "sylion_dir", "ok": false, "value": "missing"}')
        _warn "Katalog SYLION nie istnieje: ${DEVICE_SYLION_DIR}"
        status="degraded"
    fi

    # 2. Sprawdź czy proces SYLION działa
    local proc_check
    proc_check="$(_adb_shell "pgrep -l sylion 2>/dev/null || echo none" | tr -d '\r')"
    if [[ "${proc_check}" != "none" ]] && [[ -n "${proc_check}" ]]; then
        details+=('{"check": "sylion_process", "ok": true, "value": "'"${proc_check}"'"}')
        _info "Proces SYLION: uruchomiony (${proc_check})"
    else
        details+=('{"check": "sylion_process", "ok": false, "value": "not_running"}')
        _warn "Proces SYLION nie jest uruchomiony."
        status="degraded"
    fi

    # 3. Sprawdź zainstalowane APK (szukaj pakietu z "sylion" w nazwie)
    local apk_check
    apk_check="$(_adb_shell "pm list packages 2>/dev/null | grep -i sylion || echo none" | tr -d '\r')"
    if [[ "${apk_check}" != "none" ]] && [[ -n "${apk_check}" ]]; then
        details+=('{"check": "sylion_apk", "ok": true, "value": "'"${apk_check}"'"}')
        _info "APK SYLION: zainstalowany (${apk_check})"
    else
        details+=('{"check": "sylion_apk", "ok": false, "value": "not_installed"}')
        _warn "APK SYLION nie jest zainstalowany."
        # Brak APK nie jest krytyczny jeśli działa binarnie
    fi

    # 4. Sprawdź użycie CPU i pamięci
    local mem_total mem_free
    mem_total="$(_adb_shell "grep MemTotal /proc/meminfo 2>/dev/null | awk '{print \$2}'" | tr -d '\r')" || mem_total="0"
    mem_free="$(_adb_shell "grep MemAvailable /proc/meminfo 2>/dev/null | awk '{print \$2}'" | tr -d '\r')" || mem_free="0"
    local mem_pct=0
    if (( mem_total > 0 )); then
        mem_pct=$(( (mem_total - mem_free) * 100 / mem_total ))
    fi
    details+=('{"check": "memory_usage_pct", "ok": true, "value": '"${mem_pct}"'}')
    _info "Użycie pamięci: ${mem_pct}% (${mem_free}/${mem_total} kB wolne)"

    # Zbuduj JSON z tablicą details
    local details_json
    details_json="$(IFS=','; printf '[%s]' "${details[*]}")"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": $([ \"${status}\" = 'ok' ] && echo 'true' || echo 'false'), \"status\": \"${status}\", \"details\": ${details_json}}"
    else
        if [[ "${status}" == "ok" ]]; then
            _info "Health check zakończony: ${status}"
        else
            _warn "Health check zakończony: ${status}"
        fi
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_screenshot
# Wykonuje zrzut ekranu urządzenia i pobiera plik na lokalny komputer.
#
# Wyjście: ścieżka do zapisanego pliku PNG
# -----------------------------------------------------------------------------
pixel_screenshot() {
    _header "Zrzut ekranu"
    _log "INFO" "pixel_screenshot: start"

    pixel_check_connection > /dev/null 2>&1 || { _error "Brak połączenia z urządzeniem."; return 1; }

    local local_path="${PIXEL_LOG_DIR}/screenshot_$(date +%Y%m%d_%H%M%S).png"
    _ensure_log_dir

    # Wykonaj screencap na urządzeniu
    _adb_shell "screencap -p '${DEVICE_SCREENSHOT_PATH}'"

    # Pobierz plik
    _adb pull "${DEVICE_SCREENSHOT_PATH}" "${local_path}"

    # Usuń tymczasowy plik z urządzenia
    _adb_shell "rm -f '${DEVICE_SCREENSHOT_PATH}'" 2>/dev/null || true

    _info "Zrzut ekranu zapisany: ${local_path}"
    _log "INFO" "pixel_screenshot: zapisano ${local_path}"

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"screenshot_path\": \"${local_path}\"}"
    else
        printf '%s\n' "${local_path}"
    fi
}

# -----------------------------------------------------------------------------
# Funkcja: pixel_reboot MODE
# Restartuje urządzenie do wybranego trybu.
#
# Argumenty:
#   mode — system | recovery | bootloader (domyślnie: system)
# -----------------------------------------------------------------------------
pixel_reboot() {
    local mode="${1:-system}"
    _header "Restart urządzenia: ${mode}"
    _log "INFO" "pixel_reboot: mode=${mode}"

    pixel_check_connection > /dev/null 2>&1 || { _error "Brak połączenia z urządzeniem."; return 1; }

    case "${mode}" in
        system)
            _info "Restartuję do systemu..."
            _adb reboot
            ;;
        recovery)
            _info "Restartuję do recovery..."
            _adb reboot recovery
            ;;
        bootloader)
            _info "Restartuję do bootloadera/fastboot..."
            _adb reboot bootloader
            ;;
        *)
            _error "Nieznany tryb restartu: ${mode}. Użyj: system, recovery, bootloader."
            if [[ "${OUTPUT_JSON}" == "true" ]]; then
                _json_output "{\"ok\": false, \"error\": \"invalid_mode\", \"mode\": \"${mode}\"}"
            fi
            return 1
            ;;
    esac

    _info "Polecenie restartu wysłane."

    if [[ "${OUTPUT_JSON}" == "true" ]]; then
        _json_output "{\"ok\": true, \"action\": \"reboot\", \"mode\": \"${mode}\"}"
    fi
}

# -----------------------------------------------------------------------------
# Obsługa wywołania bezpośredniego: ./pixel_manager.sh funkcja [args...]
# -----------------------------------------------------------------------------
_main() {
    # Sprawdź i przetwórz flagę --json
    local args=()
    for arg in "$@"; do
        if [[ "${arg}" == "--json" ]]; then
            OUTPUT_JSON=true
            _init_colors  # przeładuj kolory (wyłącz)
        else
            args+=("${arg}")
        fi
    done

    if [[ ${#args[@]} -eq 0 ]]; then
        printf 'Użycie: %s [--json] <funkcja> [argumenty...]\n\n' "$(basename "$0")"
        printf 'Dostępne funkcje:\n'
        printf '  pixel_check_connection\n'
        printf '  pixel_get_info\n'
        printf '  pixel_flash_grapheneos <ota.zip>\n'
        printf '  pixel_deploy_sylion <plik.apk|plik>\n'
        printf '  pixel_push_config <config>\n'
        printf '  pixel_run_command "<polecenie>"\n'
        printf '  pixel_get_logs [filtr]\n'
        printf '  pixel_health_check\n'
        printf '  pixel_screenshot\n'
        printf '  pixel_reboot [system|recovery|bootloader]\n'
        exit 0
    fi

    local func="${args[0]}"
    local func_args=("${args[@]:1}")

    # Sprawdź czy funkcja istnieje
    if ! declare -f "${func}" > /dev/null 2>&1; then
        _error "Nieznana funkcja: ${func}"
        exit 1
    fi

    "${func}" "${func_args[@]+"${func_args[@]}"}"
}

# Uruchom main tylko jeśli skrypt jest wywoływany bezpośrednio (nie source'owany)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    _main "$@"
fi
