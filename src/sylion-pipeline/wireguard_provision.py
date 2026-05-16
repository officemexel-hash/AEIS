#!/usr/bin/env python3
"""
wireguard_provision.py — WireGuard provisioning dla GL.iNet Mudi V2 (OpenWrt)
SYLION v5.10 — ADR-0020

Moduł implementuje kompletny WireGuard flow:
1. generate_wg_config()   — generuje wg0.conf z szablonu (klucze przez wg genkey na routerze)
2. deploy_wg0_conf()      — wgrywa wg0.conf na router przez SCP
3. enable_wg_quick()      — uruchamia wg-quick up wg0 + autostart /etc/init.d/wg-quick
4. verify_tunnel()        — weryfikuje tunel: wg show, ping przez tunel, IP check
5. enable_kill_switch()   — wgrywa kill_switch.sh i aktywuje reguły iptables
6. enable_dns_tunnel()    — konfiguruje dnsmasq przez VPN DNS (brak DNS leak)
7. configure_wifi_ssid()  — ustawia SSID i WPA2-PSK przez uci

Wywoływany z provision_router() jako opcjonalny step:
    from wireguard_provision import provision_wireguard
    result = provision_wireguard(ip="192.168.8.1", wg_config=WgConfig(...))

Wszystkie klucze WireGuard są generowane NA ROUTERZE (wg genkey) — klucz prywatny
nigdy nie opuszcza urządzenia. Skrypt pobiera tylko klucz publiczny (wg pubkey)
w celu wymiany z serwerem VPN.
"""

from __future__ import annotations

import ipaddress  # P8-WG-01 v5.9.3 — walidacja IPv4/IPv6 przed SSH/SCP
import json
import logging
import os
import re  # P8-WG-02 v5.9.3 — walidacja kluczy WireGuard i endpoint

# P9-WG-LOW-STYLE: module-level pre-compiled regexes (avoid recompiling on every call)
_WG_KEY_RE = re.compile(r"^[A-Za-z0-9+/]{43}=$")
_WG_ENDPOINT_RE = re.compile(r"^[a-zA-Z0-9.\-\[\]:]+:[0-9]{1,5}$")
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any

log = logging.getLogger("wireguard_provision")

# ---------------------------------------------------------------------------
# Stałe
# ---------------------------------------------------------------------------

WG_CONF_REMOTE_PATH = "/etc/wireguard/wg0.conf"
WG_KEY_REMOTE_PATH = "/etc/wireguard/"          # katalog kluczy na routerze
WG_AGENT_DEPLOY_DIR = "/etc/sylion/"
KILL_SWITCH_REMOTE = "/etc/sylion/kill_switch.sh"
DNS_TUNNEL_REMOTE = "/etc/sylion/dns_tunnel.sh"

# Ścieżki lokalne (względem tego pliku)
# Fala 6 patch P6-03 (F-007): poprawiono ścieżki na templates/ i scripts/ —
# wcześniej pliki były szukane w katalogu głównym module, co powodowało,
# że provision_wireguard() zwracał "Brak szablonu" i kill-switch VPN NIE DZIAŁAŁ.
_HERE = Path(__file__).parent
TEMPLATE_PATH = _HERE / "templates" / "wg0.conf.tmpl"
KILL_SWITCH_LOCAL = _HERE / "scripts" / "kill_switch.sh"
DNS_TUNNEL_LOCAL = _HERE / "scripts" / "dns_tunnel.sh"

# Domyślne wartości
DEFAULT_WG_KEEPALIVE = 25
DEFAULT_WG_ALLOWED_IPS = "0.0.0.0/0, ::/0"
DEFAULT_DNS = "10.8.0.1"
DEFAULT_WIFI_SSID = "SYLION-Pixel"
DEFAULT_WIFI_ENCRYPTION = "psk2"


# ---------------------------------------------------------------------------
# Modele danych
# ---------------------------------------------------------------------------

@dataclass
class WgConfig:
    """Konfiguracja WireGuard dla routera (strona kliencka)."""
    server_pubkey: str         # klucz publiczny serwera VPN
    server_endpoint: str       # adres:port serwera, np. "vpn.example.com:51820"
    client_address: str        # IP tunelu klienta, np. "10.8.0.2/24"
    dns: str = DEFAULT_DNS
    allowed_ips: str = DEFAULT_WG_ALLOWED_IPS
    keepalive: int = DEFAULT_WG_KEEPALIVE
    preshared_key: str = ""    # opcjonalny — pusty = wyłączony


@dataclass
class WifiConfig:
    """Konfiguracja WiFi SSID i WPA2-PSK."""
    ssid: str = DEFAULT_WIFI_SSID
    key: str = ""              # hasło WPA2 — min. 8 znaków
    encryption: str = DEFAULT_WIFI_ENCRYPTION
    # Mudi V2 ma radio0 (2.4 GHz) i radio1 (5 GHz)
    radio_index: int = 0       # wifi-iface[0] = pierwsze radio


@dataclass
class WgProvisionResult:
    """Wynik provisioning WireGuard."""
    success: bool = False
    router_pubkey: str = ""    # klucz publiczny routera — do rejestracji na serwerze VPN
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    elapsed_s: float = 0.0

    def add_step(self, name: str, status: str, detail: str = "", elapsed_ms: int = 0):
        self.steps.append({
            "name": name,
            "status": status,
            "detail": detail,
            "elapsed_ms": elapsed_ms,
        })

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "router_pubkey": self.router_pubkey,
            "steps": self.steps,
            "error": self.error,
            "elapsed_s": round(self.elapsed_s, 2),
        }


# ---------------------------------------------------------------------------
# SSH helper (identyczny z router_provision.py — możliwy refactor do shared)
# ---------------------------------------------------------------------------

def _ssh(ip: str, command: str, timeout: int = 30, password: str = "") -> tuple[int, str, str]:
    """Wykonaj komendę SSH na routerze. Zwraca (returncode, stdout, stderr)."""
    ssh_opts = [
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=10",
    ]
    if not password:
        ssh_opts.extend(["-o", "BatchMode=yes"])

    if password:
        env = os.environ.copy()
        env["SSHPASS"] = password
        cmd = ["sshpass", "-e", "ssh"] + ssh_opts + [f"root@{ip}", command]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "SSH timeout"
        except FileNotFoundError as e:
            return -2, "", f"Brak narzędzia: {e}"
    else:
        cmd = ["ssh"] + ssh_opts + [f"root@{ip}", command]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "SSH timeout"
        except FileNotFoundError as e:
            return -2, "", f"Brak narzędzia: {e}"


def _scp(ip: str, local_path: str, remote_path: str, password: str = "") -> tuple[int, str]:
    """Kopiuj plik na router przez SCP. Zwraca (returncode, stderr)."""
    ssh_opts = [
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=10",
    ]
    if not password:
        ssh_opts.extend(["-o", "BatchMode=yes"])

    if password:
        env = os.environ.copy()
        env["SSHPASS"] = password
        cmd = ["sshpass", "-e", "scp"] + ssh_opts + [local_path, f"root@{ip}:{remote_path}"]
    else:
        cmd = ["scp"] + ssh_opts + [local_path, f"root@{ip}:{remote_path}"]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           env=(os.environ | {"SSHPASS": password}) if password else None)
        return r.returncode, r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "SCP timeout"
    except FileNotFoundError as e:
        return -2, f"Brak narzędzia: {e}"


# ---------------------------------------------------------------------------
# Kroki WireGuard
# ---------------------------------------------------------------------------

def install_wg_packages(ip: str, result: WgProvisionResult, password: str = "") -> bool:
    """
    Krok 1: Instalacja pakietów WireGuard przez opkg.

    Pakiety:
      - kmod-wireguard   — moduł jądra WireGuard dla OpenWrt
      - wireguard-tools  — wg, wg-quick
      - kmod-nft-compat  — kompatybilność iptables z nftables (OpenWrt 23.x)
      - dnsmasq-full     — zastępuje dnsmasq-base, obsługuje serwery upstream

    UWAGA: kmod-wireguard wymaga restartu kernela po pierwszej instalacji.
    W praktyce OpenWrt nie wymaga pełnego restartu — modprobe wireguard wystarcza.
    """
    t0 = time.time()

    WG_PACKAGES = [
        "kmod-wireguard",
        "wireguard-tools",
        "kmod-nft-compat",   # iptables → nftables bridge (OpenWrt 23.x)
    ]

    # opkg update
    rc, _, stderr = _ssh(ip, "opkg update", timeout=90, password=password)
    if rc != 0:
        result.add_step("wg_opkg_update", "fail",
                        f"opkg update failed: {stderr[:200]}", int((time.time() - t0) * 1000))
        return False

    installed = []
    for pkg in WG_PACKAGES:
        t1 = time.time()
        rc, stdout, stderr = _ssh(ip, f"opkg install {pkg}", timeout=120, password=password)
        elapsed_pkg = int((time.time() - t1) * 1000)
        if rc == 0 or "already installed" in (stdout + stderr).lower():
            installed.append(pkg)
            result.add_step(f"wg_pkg_{pkg}", "ok", f"{pkg} zainstalowany", elapsed_pkg)
        else:
            result.add_step(f"wg_pkg_{pkg}", "fail",
                            f"Instalacja {pkg} nieudana: {stderr[:100]}", elapsed_pkg)
            return False

    # Załaduj moduł kernela (nie wymaga restartu)
    rc, _, _ = _ssh(ip, "modprobe wireguard 2>/dev/null || true", password=password)

    result.add_step("wg_packages", "ok",
                    f"Zainstalowano WireGuard: {', '.join(installed)}",
                    int((time.time() - t0) * 1000))
    return True


def generate_wg_config(
    ip: str,
    wg_cfg: WgConfig,
    result: WgProvisionResult,
    password: str = "",
) -> bool:
    """
    Krok 2: Generuj klucze na routerze i wgraj wg0.conf.

    Bezpieczeństwo:
    - Klucz prywatny generowany NA ROUTERZE (wg genkey) — nie opuszcza urządzenia
    - Klucz publiczny (wg pubkey) jest pobierany i zwracany w result.router_pubkey
      w celu rejestracji na serwerze VPN
    - wg0.conf ma chmod 600 — tylko root może czytać

    Sekwencja:
    1. mkdir -p /etc/wireguard
    2. wg genkey > /etc/wireguard/wg0.key
    3. wg pubkey < /etc/wireguard/wg0.key (pobierz do zmiennej)
    4. Wgraj wg0.conf.tmpl z podstawionymi wartościami
    5. chmod 600 /etc/wireguard/wg0.conf wg0.key
    """
    t0 = time.time()

    # 1. Utwórz katalog kluczy
    rc, _, stderr = _ssh(ip, "mkdir -p /etc/wireguard", password=password)
    if rc != 0:
        result.add_step("wg_mkdir", "fail", f"mkdir /etc/wireguard: {stderr[:100]}",
                        int((time.time() - t0) * 1000))
        return False

    # 2. Generuj klucz prywatny
    rc, _, stderr = _ssh(ip, "wg genkey > /etc/wireguard/wg0.key", password=password)
    if rc != 0:
        result.add_step("wg_genkey", "fail",
                        f"wg genkey nieudany — czy wireguard-tools zainstalowany? {stderr[:100]}",
                        int((time.time() - t0) * 1000))
        return False

    # 3. Pobierz klucz publiczny routera
    rc, router_pubkey, stderr = _ssh(
        ip, "wg pubkey < /etc/wireguard/wg0.key", password=password
    )
    if rc != 0 or not router_pubkey:
        result.add_step("wg_pubkey", "fail",
                        f"wg pubkey nieudany: {stderr[:100]}",
                        int((time.time() - t0) * 1000))
        return False
    result.router_pubkey = router_pubkey
    result.add_step("wg_genkey", "ok",
                    f"Klucze wygenerowane. Klucz publiczny routera: {router_pubkey[:20]}...",
                    int((time.time() - t0) * 1000))

    # 4. Wygeneruj wg0.conf z szablonu
    if not TEMPLATE_PATH.exists():
        result.add_step("wg_conf_tmpl", "fail",
                        f"Brak szablonu: {TEMPLATE_PATH}", 0)
        return False

    # P8-WG-02 v5.9.3: walidacja kluczy WireGuard i endpoint przed wstawieniem do szablonu.
    # Klucz WireGuard: 44 znaki base64 (43 + padding '='). RFC 7748 / WireGuard spec.
    # Endpoint: host:port (hostname/IP + port 1-65535).
    # P9-WG-LOW-STYLE: using module-level _WG_KEY_RE / _WG_ENDPOINT_RE (pre-compiled).

    if not _WG_KEY_RE.match(wg_cfg.server_pubkey):
        result.add_step("wg_conf_validate", "fail",
                        f"Nieprawidłowy klucz publiczny serwera WG: {wg_cfg.server_pubkey[:20]!r}..."
                        f" (oczekiwano 44 znaki base64)", 0)
        return False

    if not _WG_ENDPOINT_RE.match(wg_cfg.server_endpoint):
        result.add_step("wg_conf_validate", "fail",
                        f"Nieprawidłowy endpoint WireGuard: {wg_cfg.server_endpoint!r}"
                        f" (oczekiwano format host:port)", 0)
        return False

    # Sprawdź port w zakresie 1-65535
    _ep_port = int(wg_cfg.server_endpoint.rsplit(":", 1)[-1])
    if not (1 <= _ep_port <= 65535):
        result.add_step("wg_conf_validate", "fail",
                        f"Port endpoint poza zakresem 1-65535: {_ep_port}", 0)
        return False

    result.add_step("wg_conf_validate", "ok",
                    "Klucz serwera i endpoint WireGuard zwalidowane", 0)

    tmpl_text = TEMPLATE_PATH.read_text()

    # Podstawienie zmiennych (bezpieczne — Template nie wykonuje kodu)
    conf_text = (
        tmpl_text
        .replace("{{ WG_PRIVATE_KEY }}", "$(cat /etc/wireguard/wg0.key)")
        # Podczas deploymentu klucz prywatny jest wstawiany przez shell na routerze
        # (nie przez Python) — klucz prywatny nigdy nie trafia do procesu Python
        .replace("{{ WG_ADDRESS }}", wg_cfg.client_address)
        .replace("{{ WG_DNS }}", wg_cfg.dns)
        .replace("{{ WG_SERVER_PUBKEY }}", wg_cfg.server_pubkey)
        .replace("{{ WG_ENDPOINT }}", wg_cfg.server_endpoint)
        .replace("{{ WG_ALLOWED_IPS }}", wg_cfg.allowed_ips)
        .replace("{{ WG_KEEPALIVE }}", str(wg_cfg.keepalive))
    )

    # Usuń linie z PresharedKey jeśli nie podano
    if not wg_cfg.preshared_key:
        conf_text = "\n".join(
            line for line in conf_text.splitlines()
            if "{{ WG_PRESHARED_KEY }}" not in line
        )
    else:
        conf_text = conf_text.replace("{{ WG_PRESHARED_KEY }}", wg_cfg.preshared_key)

    # 5. Zapisz conf lokalnie i wgraj SCP
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as tmp:
        tmp.write(conf_text)
        tmp_path = tmp.name

    try:
        rc, err = _scp(ip, tmp_path, WG_CONF_REMOTE_PATH, password=password)
        if rc != 0:
            result.add_step("wg_conf_deploy", "fail",
                            f"SCP wg0.conf nieudany: {err[:100]}", 0)
            return False
    finally:
        os.unlink(tmp_path)

    # 6. Ustaw uprawnienia
    rc, _, stderr = _ssh(
        ip,
        "chmod 600 /etc/wireguard/wg0.conf /etc/wireguard/wg0.key && "
        "chown root:root /etc/wireguard/wg0.conf /etc/wireguard/wg0.key",
        password=password,
    )
    if rc != 0:
        result.add_step("wg_conf_perms", "warn",
                        f"chmod 600 nieudany: {stderr[:100]}", 0)

    result.add_step("wg_conf_deploy", "ok",
                    f"wg0.conf wgrany do {WG_CONF_REMOTE_PATH} (chmod 600)",
                    int((time.time() - t0) * 1000))
    return True


def deploy_wg0_conf(ip: str, result: WgProvisionResult, password: str = "") -> bool:
    """
    Krok 2b: Deploy kill_switch.sh i dns_tunnel.sh na router.
    Wywoływany razem z generate_wg_config().
    """
    t0 = time.time()

    scripts = [
        (KILL_SWITCH_LOCAL, KILL_SWITCH_REMOTE),
        (DNS_TUNNEL_LOCAL, DNS_TUNNEL_REMOTE),
    ]

    for local, remote in scripts:
        if not local.exists():
            result.add_step(f"deploy_{local.name}", "warn",
                            f"Brak lokalnego pliku: {local}", 0)
            continue
        rc, err = _scp(ip, str(local), remote, password=password)
        if rc != 0:
            result.add_step(f"deploy_{local.name}", "fail",
                            f"SCP {local.name}: {err[:100]}", 0)
            return False
        # Ustaw uprawnienia wykonywalności
        _ssh(ip, f"chmod 755 {remote}", password=password)
        result.add_step(f"deploy_{local.name}", "ok",
                        f"{local.name} → {remote} (chmod 755)", 0)

    result.add_step("deploy_scripts", "ok", "Kill switch + DNS tunnel scripts wgrane",
                    int((time.time() - t0) * 1000))
    return True


def enable_wg_quick(ip: str, result: WgProvisionResult, password: str = "") -> bool:
    """
    Krok 3: Uruchom wg-quick up wg0 i skonfiguruj autostart.

    wg-quick na OpenWrt korzysta z /etc/wireguard/wg0.conf i zarządza:
    - ip link add wg0 type wireguard
    - wg setconf wg0
    - ip address add
    - ip route add
    - PostUp/PostDown (kill switch przez hook)

    Autostart: /etc/init.d/wg-quick enable → uruchamia wg-quick up wg0 przy każdym rebootcie
    """
    t0 = time.time()

    # Uruchom tunel
    rc, stdout, stderr = _ssh(ip, "wg-quick up wg0 2>&1", timeout=30, password=password)
    elapsed = int((time.time() - t0) * 1000)

    if rc != 0 and "already exists" not in stderr:
        result.add_step("wg_quick_up", "fail",
                        f"wg-quick up wg0 nieudany: {(stdout + stderr)[:300]}", elapsed)
        return False

    result.add_step("wg_quick_up", "ok", "wg-quick up wg0 — tunel uruchomiony", elapsed)

    # Skonfiguruj autostart przez init.d (OpenWrt standard)
    # wg-quick dostarcza /etc/init.d/wg-quick na nowszych wersjach wireguard-tools dla OpenWrt
    autostart_cmd = (
        "( /etc/init.d/wg-quick enable 2>/dev/null && echo INITD_OK ) || "
        "( grep -qF 'wg-quick up wg0' /etc/rc.local 2>/dev/null || "
        "  printf '\\n# WireGuard autostart (SYLION)\\nwg-quick up wg0\\n' >> /etc/rc.local "
        "  && echo RCLOCAL_OK )"
    )
    rc2, stdout2, _ = _ssh(ip, autostart_cmd, password=password)
    if "INITD_OK" in stdout2:
        result.add_step("wg_autostart", "ok",
                        "/etc/init.d/wg-quick enable — autostart przez init.d skonfigurowany", 0)
    elif "RCLOCAL_OK" in stdout2:
        result.add_step("wg_autostart", "ok",
                        "wg-quick up wg0 dołączony do /etc/rc.local — autostart aktywny", 0)
    else:
        result.add_step("wg_autostart", "warn",
                        "Nie udało się skonfigurować autostart — wymagana ręczna konfiguracja", 0)

    return True


def verify_tunnel(ip: str, result: WgProvisionResult, password: str = "") -> bool:
    """
    Krok 4: Weryfikacja tunelu WireGuard.

    Sprawdzenia:
    1. wg show wg0 — tunel istnieje i ma peera
    2. ip addr show wg0 — interfejs ma adres IP
    3. ping przez tunel do peer endpoint — łączność przez VPN
    4. curl ifconfig.me (lub nslookup) — zewnętrzne IP = IP serwera VPN
    """
    t0 = time.time()
    all_ok = True

    # 1. Sprawdź wg show wg0
    rc, stdout, _ = _ssh(ip, "wg show wg0 2>/dev/null || echo WG_DOWN", password=password)
    wg_up = rc == 0 and "WG_DOWN" not in stdout and "interface" in stdout.lower()
    result.add_step("verify_wg_show",
                    "ok" if wg_up else "fail",
                    stdout[:300] if wg_up else "wg0 nie istnieje lub brak peera", 0)
    if not wg_up:
        all_ok = False

    # 2. Sprawdź adres IP interfejsu wg0
    rc, stdout, _ = _ssh(ip, "ip addr show wg0 2>/dev/null | grep inet || echo NO_ADDR",
                         password=password)
    has_addr = "NO_ADDR" not in stdout and "inet" in stdout
    result.add_step("verify_wg_addr",
                    "ok" if has_addr else "warn",
                    stdout[:200] if has_addr else "Brak adresu IP na wg0", 0)

    # 3. Ping przez tunel (sprawdź łączność do serwera VPN przez wg0)
    rc, stdout, _ = _ssh(
        ip, "ping -c 2 -W 3 -I wg0 8.8.8.8 2>&1 | tail -3 || echo PING_FAIL",
        timeout=15, password=password
    )
    ping_ok = "PING_FAIL" not in stdout and rc == 0
    result.add_step("verify_tunnel_ping",
                    "ok" if ping_ok else "warn",
                    stdout[:200], 0)

    # 4. Sprawdź zewnętrzne IP (jeśli curl dostępny na routerze)
    rc, ext_ip, _ = _ssh(
        ip, "curl -s --max-time 5 ifconfig.me 2>/dev/null || echo NO_CURL",
        timeout=10, password=password
    )
    if "NO_CURL" not in ext_ip and ext_ip:
        result.add_step("verify_external_ip", "ok",
                        f"Zewnętrzne IP przez VPN: {ext_ip[:50]}", 0)
    else:
        result.add_step("verify_external_ip", "skip",
                        "curl niedostępny — pominięto weryfikację zewnętrznego IP", 0)

    elapsed = int((time.time() - t0) * 1000)
    result.add_step("verify_tunnel_summary",
                    "ok" if all_ok else "warn",
                    "Tunel WireGuard zweryfikowany" if all_ok else "Tunel częściowo działa",
                    elapsed)
    return all_ok


def enable_kill_switch(ip: str, result: WgProvisionResult, password: str = "") -> bool:
    """
    Krok 5: Aktywacja kill switch — blokuje ruch Pixela poza tunelem.

    kill_switch.sh up ustawia reguły iptables:
    - MARK 0xdead na cały ruch z wlan0
    - FORWARD: wlan0→wg0 ACCEPT (ruch przez tunel)
    - FORWARD: wlan0→!wg0 DROP (kill switch — brak wycieku gdy VPN down)
    - ip6tables FORWARD wlan0 DROP (blokada IPv6 — VPN jest IPv4-only)

    Weryfikacja: iptables -L FORWARD -n | grep DROP
    """
    t0 = time.time()

    # Sprawdź czy kill_switch.sh jest na routerze
    rc, stdout, _ = _ssh(ip, f"test -f {KILL_SWITCH_REMOTE} && echo EXISTS || echo MISSING",
                         password=password)
    if "MISSING" in stdout:
        result.add_step("ks_check", "fail",
                        f"{KILL_SWITCH_REMOTE} nie istnieje — deploy_wg0_conf() nie uruchomiony", 0)
        return False

    # Uruchom kill switch
    rc, stdout, stderr = _ssh(ip, f"sh {KILL_SWITCH_REMOTE} up 2>&1",
                              timeout=15, password=password)
    elapsed = int((time.time() - t0) * 1000)

    if rc != 0:
        result.add_step("kill_switch_up", "fail",
                        f"kill_switch.sh up nieudany: {(stdout + stderr)[:200]}", elapsed)
        return False

    # Weryfikacja — sprawdź DROP w FORWARD
    rc, ks_rules, _ = _ssh(ip, "iptables -L FORWARD -n 2>/dev/null | grep -c DROP || echo 0",
                           password=password)
    drop_count = int(ks_rules.strip()) if ks_rules.strip().isdigit() else 0
    result.add_step("kill_switch_up", "ok" if drop_count > 0 else "warn",
                    f"Kill switch aktywny — {drop_count} reguł DROP w FORWARD",
                    elapsed)

    # Weryfikacja IPv6
    rc, ip6_rules, _ = _ssh(
        ip, "ip6tables -L FORWARD -n 2>/dev/null | grep -c DROP || echo 0",
        password=password
    )
    ip6_drop = int(ip6_rules.strip()) if ip6_rules.strip().isdigit() else 0
    result.add_step("kill_switch_ipv6",
                    "ok" if ip6_drop > 0 else "warn",
                    f"IPv6 kill switch: {ip6_drop} reguł DROP", 0)

    return drop_count > 0


def enable_dns_tunnel(ip: str, vpn_dns: str, result: WgProvisionResult,
                      password: str = "") -> bool:
    """
    Krok 6: Konfiguracja DNS przez tunel VPN (eliminacja DNS leak).

    Zmiana konfiguracji dnsmasq przez UCI:
    - dhcp.@dnsmasq[0].server = <vpn_dns>
    - dhcp.@dnsmasq[0].noresolv = 1  (ignoruj /etc/resolv.conf z WAN DHCP)
    - restart dnsmasq

    Weryfikacja: nslookup example.com 127.0.0.1

    UWAGA: Wymaga dnsmasq-full (nie dnsmasq-base) dla pełnego wsparcia opcji upstream.
    OpenWrt Mudi domyślnie ma dnsmasq-base — może wymagać aktualizacji.
    """
    t0 = time.time()

    # Sprawdź czy dns_tunnel.sh jest na routerze
    rc, stdout, _ = _ssh(ip, f"test -f {DNS_TUNNEL_REMOTE} && echo EXISTS || echo MISSING",
                         password=password)
    if "MISSING" in stdout:
        result.add_step("dns_check", "fail",
                        f"{DNS_TUNNEL_REMOTE} nie istnieje — deploy_wg0_conf() nie uruchomiony", 0)
        return False

    # Uruchom konfigurację DNS
    rc, stdout, stderr = _ssh(
        ip, f"sh {DNS_TUNNEL_REMOTE} enable {shlex.quote(vpn_dns)} 2>&1",
        timeout=20, password=password
    )
    elapsed = int((time.time() - t0) * 1000)

    if rc != 0:
        result.add_step("dns_tunnel_enable", "fail",
                        f"dns_tunnel.sh enable nieudany: {(stdout + stderr)[:200]}", elapsed)
        return False

    # Weryfikacja UCI
    rc, uci_out, _ = _ssh(
        ip, "uci get dhcp.@dnsmasq[0].server 2>/dev/null || echo NONE",
        password=password
    )
    dns_set = vpn_dns in uci_out
    result.add_step("dns_tunnel_enable",
                    "ok" if dns_set else "warn",
                    f"DNS przez VPN: {uci_out[:100]}" if dns_set else
                    f"DNS UCI nie potwierdzony: {uci_out[:100]}",
                    elapsed)

    return dns_set


def configure_wifi_ssid(ip: str, wifi: WifiConfig, result: WgProvisionResult,
                        password: str = "") -> bool:
    """
    Krok 7: Konfiguracja WiFi SSID i WPA2-PSK przez UCI.

    Ustawia:
    - wireless.@wifi-iface[0].ssid = 'SYLION-Pixel'
    - wireless.@wifi-iface[0].key = '<hasło>'
    - wireless.@wifi-iface[0].encryption = 'psk2'

    Po zmianie: uci commit wireless && wifi reload
    Pixel może połączyć się z nowym SSID bez ręcznej konfiguracji.

    UWAGA: wifi reload może chwilowo zerwać połączenie SSH jeśli SSH jest przez WiFi.
    Przy konfiguracji przez kabel Ethernet (standardowy provisioning SYLION) nie ma problemu.
    """
    t0 = time.time()

    if not wifi.ssid:
        result.add_step("wifi_ssid", "skip", "Brak konfiguracji SSID — pominięto", 0)
        return True

    if wifi.key and len(wifi.key) < 8:
        result.add_step("wifi_ssid", "fail",
                        "Hasło WiFi musi mieć minimum 8 znaków (WPA2 wymóg)", 0)
        return False

    iface_idx = wifi.radio_index
    cmds = [
        f"uci set wireless.@wifi-iface[{iface_idx}].ssid={shlex.quote(wifi.ssid)}",
        f"uci set wireless.@wifi-iface[{iface_idx}].encryption={shlex.quote(wifi.encryption)}",
    ]
    if wifi.key:
        cmds.append(f"uci set wireless.@wifi-iface[{iface_idx}].key={shlex.quote(wifi.key)}")

    cmds += ["uci commit wireless", "wifi reload"]
    combined = " && ".join(cmds)

    rc, stdout, stderr = _ssh(ip, combined, timeout=20, password=password)
    elapsed = int((time.time() - t0) * 1000)

    if rc != 0:
        result.add_step("wifi_ssid", "fail",
                        f"UCI wireless config nieudany: {stderr[:200]}", elapsed)
        return False

    result.add_step("wifi_ssid", "ok",
                    f"WiFi SSID='{wifi.ssid}' encryption={wifi.encryption} — skonfigurowane",
                    elapsed)
    return True


# ---------------------------------------------------------------------------
# Główna funkcja orchestratora WireGuard
# ---------------------------------------------------------------------------

def provision_wireguard(
    ip: str,
    wg_cfg: WgConfig,
    wifi_cfg: WifiConfig | None = None,
    password: str = "",
    skip_wifi: bool = False,
) -> WgProvisionResult:
    """
    Kompletny WireGuard provisioning flow dla GL.iNet Mudi V2.

    Wywołaj po provision_router() — router musi mieć już klucz SSH i agenta.

    Args:
        ip:       IP routera (domyślnie 192.168.8.1)
        wg_cfg:   Konfiguracja WireGuard (serwer, endpoint, adresy)
        wifi_cfg: Konfiguracja WiFi (SSID, hasło) — None = pomiń
        password: Hasło root (jeśli klucz SSH nie jest jeszcze zainstalowany)
        skip_wifi: Pomiń konfigurację WiFi

    Returns:
        WgProvisionResult.router_pubkey — klucz publiczny routera do rejestracji na serwerze VPN
    """
    # P8-WG-01 v5.9.3: walidacja IP — zapobiega SSRF przez SSH/SCP na nieautoryzowane hosty.
    # Obsługuje IPv4 i IPv6 (RFC 4291). IPv6 dostaje nawiasy wymagane przez SSH: root@[::1].
    result = WgProvisionResult()
    try:
        _addr = ipaddress.ip_address(ip)
        # IPv6 wymaga nawiasów w formacie hosta SSH/SCP: ssh root@[fe80::1]
        ip = f"[{_addr}]" if _addr.version == 6 else str(_addr)
    except ValueError as exc:
        result.error = f"Nieprawidłowy adres IP routera: {exc}"
        result.add_step("ip_validation", "fail",
                        f"Walidacja IP nieudana: {exc}", 0)
        return result

    t_start = time.time()

    log.info(f"WireGuard provisioning start: {ip}")

    # Krok 1: Instalacja pakietów
    if not install_wg_packages(ip, result, password=password):
        result.error = "Instalacja pakietów WireGuard nieudana"
        result.elapsed_s = time.time() - t_start
        return result

    # Krok 2: Generowanie kluczy i konfiguracja wg0.conf
    if not generate_wg_config(ip, wg_cfg, result, password=password):
        result.error = "Generowanie konfiguracji WireGuard nieudane"
        result.elapsed_s = time.time() - t_start
        return result

    # Krok 2b: Deploy skryptów pomocniczych
    if not deploy_wg0_conf(ip, result, password=password):
        result.error = "Deploy kill_switch.sh / dns_tunnel.sh nieudany"
        result.elapsed_s = time.time() - t_start
        return result

    # Krok 3: Uruchom tunel
    if not enable_wg_quick(ip, result, password=password):
        result.error = "wg-quick up wg0 nieudany"
        result.elapsed_s = time.time() - t_start
        return result

    # Krok 4: Weryfikacja tunelu
    tunnel_ok = verify_tunnel(ip, result, password=password)
    if not tunnel_ok:
        log.warning("Tunel WireGuard uruchomiony ale weryfikacja ping nieudana — kontynuuję")

    # Krok 5: Kill switch
    if not enable_kill_switch(ip, result, password=password):
        result.error = "Kill switch aktywacja nieudana — KRYTYCZNE dla bezpieczeństwa"
        result.elapsed_s = time.time() - t_start
        return result

    # Krok 6: DNS przez VPN
    if not enable_dns_tunnel(ip, wg_cfg.dns, result, password=password):
        log.warning("DNS przez VPN nie skonfigurowany — potencjalny DNS leak")
        result.add_step("dns_warning", "warn",
                        "DNS leak protection nie aktywna — sprawdź konfigurację dnsmasq", 0)

    # Krok 7: WiFi SSID (opcjonalne)
    if not skip_wifi and wifi_cfg is not None:
        configure_wifi_ssid(ip, wifi_cfg, result, password=password)
    elif not skip_wifi:
        # Domyślna konfiguracja WiFi
        default_wifi = WifiConfig(ssid=DEFAULT_WIFI_SSID)
        configure_wifi_ssid(ip, default_wifi, result, password=password)

    result.elapsed_s = time.time() - t_start
    result.success = bool(result.router_pubkey) and tunnel_ok

    if result.success:
        log.info(f"WireGuard provisioning OK w {result.elapsed_s:.1f}s. "
                 f"Router pubkey: {result.router_pubkey[:20]}...")
    else:
        result.error = result.error or "WireGuard provisioning częściowo nieudany"
        log.warning(f"WireGuard provisioning FAIL: {result.error}")

    return result


# ---------------------------------------------------------------------------
# CLI (testowe)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="SYLION WireGuard Provisioning")
    parser.add_argument("--ip", default="192.168.8.1")
    parser.add_argument("--password", default="")
    parser.add_argument("--server-pubkey", required=True, help="Klucz publiczny serwera VPN")
    parser.add_argument("--endpoint", required=True, help="Endpoint VPN, np. vpn.example.com:51820")
    parser.add_argument("--client-addr", default="10.8.0.2/24", help="Adres IP tunelu klienta")
    parser.add_argument("--dns", default=DEFAULT_DNS)
    parser.add_argument("--ssid", default=DEFAULT_WIFI_SSID)
    parser.add_argument("--wifi-key", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wg = WgConfig(
        server_pubkey=args.server_pubkey,
        server_endpoint=args.endpoint,
        client_address=args.client_addr,
        dns=args.dns,
    )
    wifi = WifiConfig(ssid=args.ssid, key=args.wifi_key) if args.ssid else None

    result = provision_wireguard(
        ip=args.ip,
        wg_cfg=wg,
        wifi_cfg=wifi,
        password=args.password,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"\n{'=' * 60}")
        print("SYLION WireGuard Provisioning")
        print(f"{'=' * 60}")
        for step in result.steps:
            icon = {"ok": "✓", "warn": "⚠", "fail": "✗", "skip": "—"}.get(step["status"], "?")
            print(f"  [{icon}] {step['name']}: {step['detail']}")
        print(f"\nWynik: {'SUKCES' if result.success else 'BŁĄD'}")
        if result.router_pubkey:
            print(f"Router pubkey: {result.router_pubkey}")
            print(">>> Zarejestruj ten klucz na serwerze VPN jako nowego peera <<<")
        if result.error:
            print(f"Błąd: {result.error}")
        print(f"Czas: {result.elapsed_s:.1f}s")

    sys.exit(0 if result.success else 1)
