#!/bin/sh
# dns_tunnel.sh — Konfiguracja DNS przez tunel WireGuard (OpenWrt/dnsmasq)
# SYLION v5.10 — ADR-0020
#
# Użycie:
#   dns_tunnel.sh enable  <vpn_dns_ip>   — skieruj DNS przez VPN
#   dns_tunnel.sh disable                — przywróć domyślny DNS ISP
#   dns_tunnel.sh status                 — pokaż aktualną konfigurację
#
# Schemat DNS:
#   Pixel → Mudi dnsmasq (127.0.0.1:53) → VPN DNS (np. 10.8.0.1 lub 1.1.1.1 przez wg0)
#
# Bez tej konfiguracji dnsmasq może wysyłać zapytania DNS przez WAN (ISP DNS) → DNS leak.
#
# WAŻNE: Po zmianie konfiguracji dnsmasq wymagany restart: /etc/init.d/dnsmasq restart

set -e

DEFAULT_VPN_DNS="10.8.0.1"
# Fallback DNS: Cloudflare przez tunel (jeśli VPN nie ma własnego DNS)
FALLBACK_VPN_DNS="1.1.1.1"

log() {
    logger -t sylion-dns "$*" 2>/dev/null || echo "[dns_tunnel] $*"
}

dns_enable() {
    local vpn_dns="${1:-$DEFAULT_VPN_DNS}"

    log "Konfiguracja DNS przez VPN: serwer=$vpn_dns"

    # 1. Wyczyść istniejące serwery DNS w dnsmasq
    # uci delete może zwrócić błąd jeśli lista jest pusta — ignoruj
    uci -q delete dhcp.@dnsmasq[0].server || true
    uci -q delete dhcp.@dnsmasq[0].noresolv || true

    # 2. Ustaw VPN DNS jako jedyny serwer upstream
    uci add_list dhcp.@dnsmasq[0].server="$vpn_dns"

    # 3. Opcjonalnie: dodaj Cloudflare przez tunel jako fallback
    if [ "$vpn_dns" != "$FALLBACK_VPN_DNS" ]; then
        uci add_list dhcp.@dnsmasq[0].server="$FALLBACK_VPN_DNS"
    fi

    # 4. Wyłącz /etc/resolv.conf jako źródło serwera DNS
    #    (blokuje użycie DNS od ISP przez DHCP WAN)
    uci set dhcp.@dnsmasq[0].noresolv="1"

    # 5. Wymuś nasłuchiwanie dnsmasq tylko na interfejsach LAN (nie WAN)
    uci set dhcp.@dnsmasq[0].interface="lan"

    # 6. Zapisz i przeładuj
    uci commit dhcp
    /etc/init.d/dnsmasq restart

    log "DNS przez VPN AKTYWNY: $vpn_dns"

    # 7. Weryfikacja — sprawdź czy dnsmasq słucha
    sleep 1
    if nslookup example.com 127.0.0.1 >/dev/null 2>&1; then
        log "DNS resolucja przez 127.0.0.1 OK"
        echo "OK: DNS przez VPN skonfigurowany ($vpn_dns)"
    else
        log "OSTRZEŻENIE: DNS resolucja przez 127.0.0.1 nieudana — sprawdź czy wg0 jest aktywny"
        echo "WARN: dnsmasq zrestartowany ale resolucja nieudana (czy wg0 jest UP?)"
    fi
}

dns_disable() {
    log "Przywracanie domyślnego DNS ISP"

    # Usuń konfigurację VPN DNS
    uci -q delete dhcp.@dnsmasq[0].server || true
    uci -q delete dhcp.@dnsmasq[0].noresolv || true
    uci -q delete dhcp.@dnsmasq[0].interface || true

    uci commit dhcp
    /etc/init.d/dnsmasq restart

    log "DNS przywrócony do domyślnego (ISP DHCP)"
    echo "OK: DNS przywrócony do domyślnego ISP"
}

dns_status() {
    echo "=== Konfiguracja dnsmasq (UCI) ==="
    uci show dhcp 2>/dev/null | grep -E "(server|noresolv|interface)" || echo "(brak konfiguracji DNS)"
    echo ""
    echo "=== /etc/resolv.conf ==="
    cat /etc/resolv.conf 2>/dev/null || echo "(brak pliku)"
    echo ""
    echo "=== Test resolucji przez 127.0.0.1 ==="
    if nslookup example.com 127.0.0.1 2>&1 | head -5; then
        echo ""
    else
        echo "(resolucja nieudana)"
    fi
}

case "$1" in
    enable)
        dns_enable "${2:-$DEFAULT_VPN_DNS}"
        ;;
    disable)
        dns_disable
        ;;
    status)
        dns_status
        ;;
    *)
        echo "Użycie: $0 {enable|disable|status} [vpn_dns_ip]"
        echo "  enable  [ip]  — skieruj DNS przez VPN (domyślnie $DEFAULT_VPN_DNS)"
        echo "  disable       — przywróć DNS ISP"
        echo "  status        — pokaż aktualną konfigurację DNS"
        exit 1
        ;;
esac
