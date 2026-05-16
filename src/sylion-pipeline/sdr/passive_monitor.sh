#!/usr/bin/env bash
# =============================================================================
# SYLION SDR — Pasywny monitoring IMEI/IMSI (HackRF One)
#
# Monitoruje sygnały GSM i przechwytuje IMEI/IMSI routera mobilnego.
# Używane do weryfikacji czy identyfikatory zmieniają się po aktualizacji firmware.
#
# WYMAGANIA: HackRF One, gr-gsm, gnuradio, tshark, python3
# =============================================================================

set -euo pipefail

# --- Konfiguracja ---
SYLION_SDR_DEVICE="${SYLION_SDR_DEVICE:-hackrf}"          # hackrf / rtlsdr / limesdr
SYLION_SDR_GAIN="${SYLION_SDR_GAIN:-40}"                   # Wzmocnienie LNA (dB)
SYLION_SDR_PPM="${SYLION_SDR_PPM:-0}"                      # Korekcja częstotliwości (ppm)
SYLION_GSM_BAND="${SYLION_GSM_BAND:-900}"                  # Pasmo GSM: 900/1800/850/1900
SYLION_CAPTURE_DURATION="${SYLION_CAPTURE_DURATION:-60}"   # Czas przechwytywania (sekundy)
SYLION_LOG_DIR="${SYLION_LOG_DIR:-./sdr_logs}"
SYLION_BASELINE_FILE="${SYLION_BASELINE_FILE:-./sdr_logs/baseline_identifiers.json}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${SYLION_LOG_DIR}/passive_${TIMESTAMP}.log"
JSON_OUTPUT="${SYLION_LOG_DIR}/capture_${TIMESTAMP}.json"

# --- Kolory (wyłączone dla --json lub pipe) ---
if [[ -t 1 ]] && [[ "${1:-}" != "--json" ]]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    BLUE='\033[0;34m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; NC=''
fi

_log() { echo -e "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
_info() { _log "${GREEN}[INFO]${NC} $*"; }
_warn() { _log "${YELLOW}[WARN]${NC} $*"; }
_error() { _log "${RED}[ERROR]${NC} $*"; }

mkdir -p "$SYLION_LOG_DIR"

# =============================================================================
# Sprawdzenie wymagań
# =============================================================================
check_dependencies() {
    _info "Sprawdzam zależności..."
    local missing=()

    for cmd in grgsm_scanner grgsm_livemon tshark python3 hackrf_info; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        _error "Brakujące narzędzia: ${missing[*]}"
        _info "Instalacja: sudo apt install gnuradio gr-gsm hackrf wireshark tshark"
        return 1
    fi

    # Sprawdź HackRF
    if [[ "$SYLION_SDR_DEVICE" == "hackrf" ]]; then
        if ! hackrf_info &>/dev/null; then
            _error "HackRF nie wykryty. Sprawdź połączenie USB."
            _info "Debug: lsusb | grep -i 'great scott'"
            return 1
        fi
        local serial
        serial=$(hackrf_info 2>/dev/null | grep "Serial number" | awk '{print $NF}')
        _info "HackRF wykryty: serial=$serial"
    fi

    _info "Wszystkie zależności OK"
}

# =============================================================================
# Skanowanie stacji bazowych
# =============================================================================
scan_base_stations() {
    _info "Skanuję stacje bazowe (pasmo GSM-${SYLION_GSM_BAND})..."

    local scan_file="${SYLION_LOG_DIR}/bts_scan_${TIMESTAMP}.txt"

    # grgsm_scanner skanuje i listuje stacje bazowe w zasięgu
    timeout 120 grgsm_scanner \
        --band "GSM${SYLION_GSM_BAND}" \
        --speed 4 \
        --ppm "$SYLION_SDR_PPM" \
        2>/dev/null | tee "$scan_file"

    local bts_count
    bts_count=$(grep -c "ARFCN" "$scan_file" 2>/dev/null || echo "0")

    if [[ "$bts_count" -eq 0 ]]; then
        _warn "Nie znaleziono stacji bazowych. Sprawdź antenę i pasmo."
        _info "Spróbuj inne pasmo: SYLION_GSM_BAND=1800 $0 scan"
        return 1
    fi

    _info "Znaleziono $bts_count stacji bazowych"

    # Parsuj do JSON
    python3 -c "
import sys, json, re

stations = []
with open('$scan_file') as f:
    for line in f:
        # Format: ARFCN: 975, Freq: 949.8M, CID: 12345, LAC: 678, MCC: 260, MNC: 02, Pwr: -45
        match = re.search(r'ARFCN:\s*(\d+).*Freq:\s*([\d.]+)M.*CID:\s*(\d+).*LAC:\s*(\d+).*MCC:\s*(\d+).*MNC:\s*(\d+).*Pwr:\s*([-\d.]+)', line)
        if match:
            stations.append({
                'arfcn': int(match.group(1)),
                'freq_mhz': float(match.group(2)),
                'cid': int(match.group(3)),
                'lac': int(match.group(4)),
                'mcc': match.group(5),
                'mnc': match.group(6),
                'power_dbm': float(match.group(7))
            })

# Sortuj po sile sygnału (najsilniejszy najpierw)
stations.sort(key=lambda x: x['power_dbm'], reverse=True)
print(json.dumps(stations, indent=2))
" > "${SYLION_LOG_DIR}/bts_stations_${TIMESTAMP}.json"

    _info "Stacje zapisane w: bts_stations_${TIMESTAMP}.json"
}

# =============================================================================
# Przechwytywanie IMSI/IMEI (pasywne)
# =============================================================================
capture_identifiers() {
    local freq="${1:-}"

    if [[ -z "$freq" ]]; then
        _error "Użycie: $0 capture <częstotliwość_MHz>"
        _info "Np.: $0 capture 949.8M"
        _info "Uruchom najpierw: $0 scan — żeby znaleźć aktywne częstotliwości"
        return 1
    fi

    _info "Przechwytuję identyfikatory na ${freq} przez ${SYLION_CAPTURE_DURATION}s..."

    local pcap_file="${SYLION_LOG_DIR}/gsm_capture_${TIMESTAMP}.pcap"
    local imsi_file="${SYLION_LOG_DIR}/imsi_${TIMESTAMP}.txt"

    # Uruchom grgsm_livemon w tle — przechwytuje GSM i wysyła do loopback
    grgsm_livemon \
        -f "$freq" \
        --ppm "$SYLION_SDR_PPM" \
        --gain "$SYLION_SDR_GAIN" \
        --speed 4 \
        &>/dev/null &
    local livemon_pid=$!

    # Daj chwilę na start
    sleep 2

    # Przechwyć pakiety z interfejsu loopback (port UDP 4729)
    timeout "$SYLION_CAPTURE_DURATION" tshark \
        -i lo \
        -f "udp port 4729" \
        -w "$pcap_file" \
        2>/dev/null &
    local tshark_pid=$!

    # Jednocześnie — wyciągaj IMSI w realtime
    timeout "$SYLION_CAPTURE_DURATION" tshark \
        -i lo \
        -f "udp port 4729" \
        -Y "gsm_a.dtap.msg_mm_type == 0x05 || e212.imsi" \
        -T fields \
        -e frame.time -e e212.imsi -e gsm_a.imei \
        -E separator=, \
        2>/dev/null | tee "$imsi_file" &

    # Czekaj na zakończenie przechwytywania
    _info "Przechwytywanie w toku... (${SYLION_CAPTURE_DURATION}s)"
    wait $tshark_pid 2>/dev/null || true

    # Zatrzymaj livemon
    kill $livemon_pid 2>/dev/null || true
    wait $livemon_pid 2>/dev/null || true

    # Parsuj wyniki
    _info "Analizuję przechwycone pakiety..."

    python3 -c "
import json, csv, sys
from collections import defaultdict

identifiers = defaultdict(lambda: {'imsi': set(), 'imei': set(), 'count': 0, 'first_seen': None, 'last_seen': None})

try:
    with open('$imsi_file') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                timestamp = parts[0].strip()
                imsi = parts[1].strip() if len(parts) > 1 else ''
                imei = parts[2].strip() if len(parts) > 2 else ''

                if imsi:
                    identifiers[imsi]['imsi'].add(imsi)
                    identifiers[imsi]['count'] += 1
                    if not identifiers[imsi]['first_seen']:
                        identifiers[imsi]['first_seen'] = timestamp
                    identifiers[imsi]['last_seen'] = timestamp
                if imei:
                    # Przypisz IMEI do najbliższego IMSI
                    for k in identifiers:
                        identifiers[k]['imei'].add(imei)
except FileNotFoundError:
    pass

results = []
for key, data in identifiers.items():
    results.append({
        'imsi': list(data['imsi']),
        'imei': list(data['imei']),
        'observations': data['count'],
        'first_seen': data['first_seen'],
        'last_seen': data['last_seen'],
        'mcc': key[:3] if len(key) >= 3 else '?',
        'mnc': key[3:5] if len(key) >= 5 else '?',
    })

output = {
    'timestamp': '$TIMESTAMP',
    'frequency': '$freq',
    'duration_seconds': $SYLION_CAPTURE_DURATION,
    'unique_imsi_count': len(results),
    'identifiers': results,
    'pcap_file': '$pcap_file'
}

print(json.dumps(output, indent=2))
" > "$JSON_OUTPUT"

    local imsi_count
    imsi_count=$(python3 -c "import json; print(json.load(open('$JSON_OUTPUT'))['unique_imsi_count'])" 2>/dev/null || echo "0")

    _info "Przechwycono $imsi_count unikalnych IMSI"
    _info "Wyniki: $JSON_OUTPUT"
    _info "PCAP:   $pcap_file"
}

# =============================================================================
# Zapisz baseline (przed aktualizacją firmware)
# =============================================================================
save_baseline() {
    local capture_file="${1:-$JSON_OUTPUT}"

    if [[ ! -f "$capture_file" ]]; then
        _error "Brak pliku capture. Uruchom najpierw: $0 capture <freq>"
        return 1
    fi

    cp "$capture_file" "$SYLION_BASELINE_FILE"
    _info "Baseline zapisany: $SYLION_BASELINE_FILE"

    python3 -c "
import json
data = json.load(open('$SYLION_BASELINE_FILE'))
print(f\"  IMSI: {[id['imsi'] for id in data['identifiers']]}\")
print(f\"  IMEI: {[id['imei'] for id in data['identifiers']]}\")
"
}

# =============================================================================
# Porównaj z baseline (po aktualizacji firmware)
# =============================================================================
compare_with_baseline() {
    local capture_file="${1:-$JSON_OUTPUT}"

    if [[ ! -f "$SYLION_BASELINE_FILE" ]]; then
        _error "Brak baseline. Uruchom najpierw: $0 baseline"
        return 1
    fi

    if [[ ! -f "$capture_file" ]]; then
        _error "Brak pliku capture do porównania."
        return 1
    fi

    _info "Porównuję z baseline..."

    python3 -c "
import json, sys

baseline = json.load(open('$SYLION_BASELINE_FILE'))
current = json.load(open('$capture_file'))

baseline_imsi = set()
baseline_imei = set()
for ident in baseline['identifiers']:
    baseline_imsi.update(ident['imsi'])
    baseline_imei.update(ident['imei'])

current_imsi = set()
current_imei = set()
for ident in current['identifiers']:
    current_imsi.update(ident['imsi'])
    current_imei.update(ident['imei'])

report = {
    'comparison_timestamp': '$TIMESTAMP',
    'baseline_file': '$SYLION_BASELINE_FILE',
    'current_file': '$capture_file',
    'imsi': {
        'baseline': sorted(baseline_imsi),
        'current': sorted(current_imsi),
        'added': sorted(current_imsi - baseline_imsi),
        'removed': sorted(baseline_imsi - current_imsi),
        'unchanged': sorted(baseline_imsi & current_imsi),
        'changed': len(current_imsi - baseline_imsi) > 0 or len(baseline_imsi - current_imsi) > 0,
    },
    'imei': {
        'baseline': sorted(baseline_imei),
        'current': sorted(current_imei),
        'added': sorted(current_imei - baseline_imei),
        'removed': sorted(baseline_imei - current_imei),
        'unchanged': sorted(baseline_imei & current_imei),
        'changed': len(current_imei - baseline_imei) > 0 or len(baseline_imei - current_imei) > 0,
    },
    'verdict': 'CHANGED' if (current_imsi != baseline_imsi or current_imei != baseline_imei) else 'UNCHANGED',
}

print(json.dumps(report, indent=2))

# Podsumowanie
print(f\"\\n--- PODSUMOWANIE ---\")
print(f\"IMSI: {'ZMIENIONY' if report['imsi']['changed'] else 'BEZ ZMIAN'}\")
if report['imsi']['added']:
    print(f\"  Nowe:    {report['imsi']['added']}\")
if report['imsi']['removed']:
    print(f\"  Usunięte: {report['imsi']['removed']}\")

print(f\"IMEI: {'ZMIENIONY' if report['imei']['changed'] else 'BEZ ZMIAN'}\")
if report['imei']['added']:
    print(f\"  Nowe:    {report['imei']['added']}\")
if report['imei']['removed']:
    print(f\"  Usunięte: {report['imei']['removed']}\")

print(f\"\\nWERDYKT: {report['verdict']}\")
" | tee "${SYLION_LOG_DIR}/comparison_${TIMESTAMP}.json"
}

# =============================================================================
# Pełny workflow: skan → capture → baseline/compare
# =============================================================================
full_workflow() {
    local mode="${1:-baseline}"  # baseline lub compare

    _info "═══ Pełny workflow: ${mode} ═══"

    # 1. Skanuj stacje bazowe
    scan_base_stations

    # 2. Wybierz najsilniejszą stację
    local best_freq
    best_freq=$(python3 -c "
import json
stations = json.load(open('${SYLION_LOG_DIR}/bts_stations_${TIMESTAMP}.json'))
if stations:
    print(f\"{stations[0]['freq_mhz']}M\")
" 2>/dev/null || echo "")

    if [[ -z "$best_freq" ]]; then
        _error "Nie znaleziono stacji bazowych"
        return 1
    fi

    _info "Najsilniejsza stacja: ${best_freq}"

    # 3. Przechwyć identyfikatory
    capture_identifiers "$best_freq"

    # 4. Baseline lub porównanie
    if [[ "$mode" == "baseline" ]]; then
        save_baseline "$JSON_OUTPUT"
        _info "Baseline zapisany. Teraz wgraj nowy firmware i uruchom: $0 full compare"
    else
        compare_with_baseline "$JSON_OUTPUT"
    fi
}

# =============================================================================
# Główna logika
# =============================================================================
main() {
    local command="${1:-help}"
    shift || true

    case "$command" in
        check)    check_dependencies ;;
        scan)     check_dependencies && scan_base_stations ;;
        capture)  check_dependencies && capture_identifiers "$@" ;;
        baseline) check_dependencies && save_baseline "$@" ;;
        compare)  check_dependencies && compare_with_baseline "$@" ;;
        full)     check_dependencies && full_workflow "$@" ;;
        help|--help|-h)
            echo "SYLION SDR — Pasywny monitoring IMEI/IMSI"
            echo ""
            echo "Użycie: $0 <komenda> [argumenty]"
            echo ""
            echo "Komendy:"
            echo "  check              Sprawdź zależności i HackRF"
            echo "  scan               Skanuj stacje bazowe"
            echo "  capture <freq>     Przechwyć IMSI/IMEI na danej częstotliwości"
            echo "  baseline [plik]    Zapisz baseline identyfikatorów"
            echo "  compare [plik]     Porównaj z baseline"
            echo "  full baseline      Pełny workflow: skan → capture → zapisz baseline"
            echo "  full compare       Pełny workflow: skan → capture → porównaj"
            echo ""
            echo "Zmienne środowiskowe:"
            echo "  SYLION_SDR_DEVICE          hackrf/rtlsdr/limesdr (domyślnie: hackrf)"
            echo "  SYLION_GSM_BAND            900/1800/850/1900 (domyślnie: 900)"
            echo "  SYLION_SDR_GAIN            Wzmocnienie dB (domyślnie: 40)"
            echo "  SYLION_CAPTURE_DURATION    Czas przechwytywania w sekundach (domyślnie: 60)"
            echo "  SYLION_LOG_DIR             Katalog logów (domyślnie: ./sdr_logs)"
            ;;
        *)
            _error "Nieznana komenda: $command"
            _info "Użyj: $0 help"
            return 1
            ;;
    esac
}

main "$@"
