#!/bin/sh
# kill_switch.sh — WireGuard kill switch dla GL.iNet Mudi V2 (OpenWrt)
# SYLION v5.10 — ADR-0020
#
# Użycie:
#   kill_switch.sh up    — aktywuj kill switch (blokuj ruch poza wg0)
#   kill_switch.sh down  — dezaktywuj kill switch (przywróć routing)
#
# Wywoływany z PostUp/PostDown w wg0.conf.tmpl
#
# Schemat zabezpieczenia:
#   wlan0 (Pixel) → MARK 0xdead → FORWARD przez wg0 → ACCEPT
#                               → FORWARD przez !wg0 → DROP  (kill switch)
#   wlan0 → DNS: tylko przez 127.0.0.1:53 (dnsmasq → VPN DNS przez tunel)
#
# UWAGA: Ten skrypt zakłada, że LAN interface to wlan0.
#        Dostosuj WLAN_IF jeśli Mudi używa br-lan lub innej nazwy.

set -e

WLAN_IF="${WLAN_IF:-wlan0}"
WG_IF="${WG_IF:-wg0}"
MARK="0xdead"

log() {
    logger -t sylion-killswitch "$*" 2>/dev/null || echo "[kill_switch] $*"
}

ks_up() {
    log "Aktywacja kill switch: $WLAN_IF → tylko przez $WG_IF"

    # --- IPv4 kill switch ---

    # 1. Oznacz cały ruch wychodzący z wlan0 (od Pixela)
    iptables -t mangle -A PREROUTING -i "$WLAN_IF" -j MARK --set-mark "$MARK"

    # 2. Zezwól ruchowi oznaczonemu przejść przez wg0
    iptables -A FORWARD -i "$WLAN_IF" -o "$WG_IF" -j ACCEPT
    # 3. Zezwól odpowiedziom wrócić z tunelu do Pixela
    iptables -A FORWARD -i "$WG_IF" -o "$WLAN_IF" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    # 4. Blokuj WSZELKI ruch z wlan0 który NIE idzie przez wg0
    #    (reguła DROP tylko dla oznaczonego ruchu — przepuszcza ruch bez znaku, np. mDNS lokalny)
    iptables -A FORWARD -i "$WLAN_IF" ! -o "$WG_IF" -m mark --mark "$MARK" -j DROP

    # --- IPv6 kill switch — blokuj wszystko (VPN zakłada IPv4-only) ---
    ip6tables -A FORWARD -i "$WLAN_IF" -j DROP
    ip6tables -A OUTPUT -o "$WLAN_IF" -j DROP 2>/dev/null || true

    # --- Zablokuj wyciek DNS na WAN (nie przez tunel) ---
    # DNS przez dnsmasq lokalny (127.0.0.1:53) → kieruje zapytania przez VPN
    # Zablokuj bezpośredni DNS z routera na WAN port 53 (nie przez wg0)
    iptables -A OUTPUT -o eth0 -p udp --dport 53 ! -o "$WG_IF" -j DROP 2>/dev/null || \
    iptables -A OUTPUT -p udp --dport 53 ! -o "$WG_IF" -j DROP

    log "Kill switch AKTYWNY — ruch Pixela chroniony"
}

ks_down() {
    log "Dezaktywacja kill switch"

    # Usuń reguły IPv4 (ignoruj błędy jeśli reguły już nie istnieją)
    iptables -t mangle -D PREROUTING -i "$WLAN_IF" -j MARK --set-mark "$MARK" 2>/dev/null || true
    iptables -D FORWARD -i "$WLAN_IF" -o "$WG_IF" -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i "$WG_IF" -o "$WLAN_IF" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i "$WLAN_IF" ! -o "$WG_IF" -m mark --mark "$MARK" -j DROP 2>/dev/null || true

    # Usuń reguły IPv6
    ip6tables -D FORWARD -i "$WLAN_IF" -j DROP 2>/dev/null || true
    ip6tables -D OUTPUT -o "$WLAN_IF" -j DROP 2>/dev/null || true

    # Usuń blokadę DNS
    iptables -D OUTPUT -o eth0 -p udp --dport 53 ! -o "$WG_IF" -j DROP 2>/dev/null || true
    iptables -D OUTPUT -p udp --dport 53 ! -o "$WG_IF" -j DROP 2>/dev/null || true

    log "Kill switch DEZAKTYWOWANY"
}

ks_status() {
    echo "=== IPv4 FORWARD ==="
    iptables -L FORWARD -n -v 2>/dev/null || echo "iptables niedostępny"
    echo ""
    echo "=== IPv4 MANGLE PREROUTING ==="
    iptables -t mangle -L PREROUTING -n -v 2>/dev/null || true
    echo ""
    echo "=== IPv6 FORWARD ==="
    ip6tables -L FORWARD -n -v 2>/dev/null || echo "ip6tables niedostępny"
}

case "$1" in
    up)
        ks_up
        ;;
    down)
        ks_down
        ;;
    status)
        ks_status
        ;;
    *)
        echo "Użycie: $0 {up|down|status}"
        echo "  up     — aktywuj kill switch (WireGuard tunnel UP)"
        echo "  down   — dezaktywuj kill switch (WireGuard tunnel DOWN)"
        echo "  status — pokaż aktualny stan reguł"
        exit 1
        ;;
esac
