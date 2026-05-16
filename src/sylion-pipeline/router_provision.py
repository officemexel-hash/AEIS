#!/usr/bin/env python3
"""
SYLION Router Auto-Provisioning — GL.iNet Mudi V2 (OpenWrt)

Automates the FULL first-boot setup of a new router (zero manual steps):
1. Detect router on default IP (192.168.8.1) or custom IP
2. Auto-complete GL.iNet first-boot wizard (language EN + admin password)
3. SSH is automatically available after wizard completion
4. Generate + deploy SSH keypair for passwordless access
5. Install required OpenWrt packages (opkg)
6. Deploy SYLION agent to /etc/sylion/ with autostart
7. Verify full connectivity

This script is called from the dashboard via /api/devices/provision
and can also be run standalone: python3 router_provision.py [--ip 192.168.8.1]
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("router_provision")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_ROUTER_IP = "192.168.8.1"
SSH_KEY_PATH = Path.home() / ".ssh" / "id_ed25519"
SSH_KEY_COMMENT = "sylion-pipeline-auto"

# Required OpenWrt packages for SYLION pipeline
OPKG_REQUIRED = [
    "python3-light",
    "coreutils-sha256sum",
    # --- v5.10: WireGuard stack ---
    "kmod-wireguard",      # Moduł jądra WireGuard (OpenWrt kernel module)
    "wireguard-tools",     # wg, wg-quick CLI tools
    "kmod-nft-compat",     # iptables→nftables bridge (OpenWrt 23.x)
    # --- v5.10: DNS leak protection ---
    # dnsmasq-full zastępuje dnsmasq-base — musi być instalowany osobno jeśli obecny
    # (konflikt pakietów; obsłużone w step_install_opkg_packages)
]

# Optional but recommended packages
OPKG_OPTIONAL = [
    "tcpdump",
    "iptables-nft",
    "curl",
    "openssh-sftp-server",
    "dnsmasq-full",        # pełny dnsmasq dla opcji upstream DNS przez VPN
]

# Agent files to deploy to router
AGENT_DEPLOY_DIR = "/etc/sylion/"
AGENT_FILES = [
    "device_harness.py",
    # v5.10: WireGuard helper scripts
    "wireguard_provision.py",
]

# GL.iNet firmware 4.x JSON-RPC API
GLINET_RPC_URL = "/rpc"

# Language for wizard
DEFAULT_WIZARD_LANG = "en"


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class ProvisionResult:
    """Result of a provisioning run."""
    router_ip: str = DEFAULT_ROUTER_IP
    success: bool = False
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    elapsed_s: float = 0.0
    ssh_key_deployed: bool = False
    packages_installed: list[str] = field(default_factory=list)
    agent_deployed: bool = False

    def add_step(self, name: str, status: str, detail: str = "", elapsed_ms: int = 0):
        self.steps.append({
            "name": name,
            "status": status,  # "ok", "warn", "fail", "skip"
            "detail": detail,
            "elapsed_ms": elapsed_ms,
        })

    def to_dict(self) -> dict:
        return {
            "router_ip": self.router_ip,
            "success": self.success,
            "steps": self.steps,
            "error": self.error,
            "elapsed_s": round(self.elapsed_s, 2),
            "ssh_key_deployed": self.ssh_key_deployed,
            "packages_installed": self.packages_installed,
            "agent_deployed": self.agent_deployed,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 30, check: bool = False,
         capture: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess with timeout."""
    return subprocess.run(
        cmd, capture_output=capture, text=True, timeout=timeout, check=check,
    )


def _ssh(ip: str, command: str, timeout: int = 30, password: str = "") -> tuple[int, str, str]:
    """Execute SSH command on router. Returns (returncode, stdout, stderr)."""
    ssh_opts = [
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=10",
    ]
    if not password:
        ssh_opts.extend(["-o", "BatchMode=yes"])

    if password:
        # Use sshpass with env var to avoid exposing password in ps/proc
        env = os.environ.copy()
        env["SSHPASS"] = password
        cmd = ["sshpass", "-e", "ssh"] + ssh_opts + [f"root@{ip}", command]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "SSH timeout"
        except FileNotFoundError as e:
            return -2, "", f"Missing tool: {e}"
    else:
        cmd = ["ssh"] + ssh_opts + [f"root@{ip}", command]

    try:
        result = _run(cmd, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "SSH timeout"
    except FileNotFoundError as e:
        return -2, "", f"Missing tool: {e}"


def _scp(ip: str, local_path: str, remote_path: str,
          password: str = "") -> tuple[int, str]:
    """SCP file to router."""
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
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
            return result.returncode, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "SCP timeout"
        except FileNotFoundError as e:
            return -2, f"Missing tool: {e}"
    else:
        cmd = ["scp"] + ssh_opts + [local_path, f"root@{ip}:{remote_path}"]

    try:
        result = _run(cmd, timeout=60)
        return result.returncode, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "SCP timeout"
    except FileNotFoundError as e:
        return -2, f"Missing tool: {e}"


# ---------------------------------------------------------------------------
# GL.iNet API helpers
# ---------------------------------------------------------------------------

def _glinet_rpc(ip: str, method: str, params: list | None = None,
                timeout: int = 10) -> dict:
    """Call GL.iNet JSON-RPC API. Returns parsed response or raises."""
    import urllib.request
    import urllib.error
    url = f"http://{ip}{GLINET_RPC_URL}"
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "call",
        "params": params or [],
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "glinet": "1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _glinet_check_initialized(ip: str) -> bool | None:
    """Check if router has completed first-boot wizard.
    
    Returns:
        True  — wizard completed, router is initialized
        False — wizard NOT completed, needs init
        None  — could not determine (network error, timeout, etc.)
    """
    try:
        resp = _glinet_rpc(ip, "call", ["", "ui", "check_initialized", {}])
        result_data = resp.get("result", [])
        # Result is [code, data] — code 0 = success
        if isinstance(result_data, list) and len(result_data) >= 2:
            return result_data[1].get("initialized", False)
        return False
    except Exception:
        return None


def _glinet_run_wizard(ip: str, password: str, lang: str = "en") -> tuple[bool, str]:
    """Automatically complete the first-boot wizard via JSON-RPC.
    
    On fresh GL.iNet firmware 4.x, SSH is available without password
    before wizard completion. We SSH in and call the local RPC to
    initialize the device (set language + admin password).
    
    After wizard completion, the admin password also becomes the SSH root password.
    """
    try:
        # Method 1: Direct JSON-RPC (works on firmware 4.x)
        resp = _glinet_rpc(ip, "call", [
            "", "ui", "init",
            {"lang": lang, "username": "root", "password": password, "security_rule": 0}
        ])
        result_data = resp.get("result", [])
        if isinstance(result_data, list) and len(result_data) >= 1:
            if result_data[0] == 0:
                return True, "Wizard zakonczony przez JSON-RPC API"
        return False, f"API zwrocilo: {result_data}"
    except Exception as e:
        # Method 2: SSH fallback (before wizard, SSH has no password on GL.iNet)
        # Build JSON payload safely — no shell interpolation of user input
        try:
            payload = json.dumps({
                "jsonrpc": "2.0", "id": 5, "method": "call",
                "params": ["", "ui", "init", {
                    "lang": lang, "username": "root",
                    "password": password, "security_rule": 0,
                }],
            })
            # shlex.quote ensures payload is a single safe shell argument
            ssh_cmd = (
                f'curl -s -k http://127.0.0.1/rpc '
                f'-H "glinet: 1" -d {shlex.quote(payload)}'
            )
            rc, stdout, stderr = _ssh(ip, ssh_cmd, timeout=15)
            if rc == 0 and '"code":0' in stdout:
                return True, "Wizard zakonczony przez SSH + local RPC"
            return False, f"SSH curl failed: rc={rc}, {stderr[:200]}"
        except Exception as e2:
            return False, f"Oba sposoby zawiodly: API={e}, SSH={e2}"


# ---------------------------------------------------------------------------
# Provisioning steps
# ---------------------------------------------------------------------------

def step_check_reachability(result: ProvisionResult) -> bool:
    """Step 1: Check if router is reachable via ping."""
    t0 = time.time()
    _ping_cmd = (
        ["ping", "-n", "3", "-w", "2000", result.router_ip]
        if sys.platform == "win32"
        else ["ping", "-c", "3", "-W", "2", result.router_ip]
    )
    try:
        proc = _run(_ping_cmd, timeout=15)
        elapsed = int((time.time() - t0) * 1000)
        if proc.returncode == 0:
            result.add_step("ping", "ok", f"Router {result.router_ip} odpowiada na ping", elapsed)
            return True
        result.add_step("ping", "fail",
                        f"Router {result.router_ip} nie odpowiada. Sprawdz kabel Ethernet.", elapsed)
        return False
    except Exception as e:
        result.add_step("ping", "fail", str(e), int((time.time() - t0) * 1000))
        return False


def step_check_ssh_available(result: ProvisionResult, password: str = "") -> bool:
    """Step 2: Check if SSH is enabled and accessible."""
    t0 = time.time()
    rc, stdout, stderr = _ssh(result.router_ip, "echo SYLION_SSH_OK", password=password)
    elapsed = int((time.time() - t0) * 1000)

    if rc == 0 and "SYLION_SSH_OK" in stdout:
        result.add_step("ssh_check", "ok", "SSH dostepne — polaczenie OK", elapsed)
        return True

    if "Permission denied" in stderr or "password" in stderr.lower():
        result.add_step("ssh_check", "warn",
                        "SSH aktywne, ale brak klucza/hasla. Wymagane haslo root.", elapsed)
        return False  # SSH is on but needs auth setup

    result.add_step("ssh_check", "fail",
                    f"SSH niedostepne: {stderr[:200]}. "
                    f"Otworz http://{result.router_ip} > System > Administration > SSH > Enable.", elapsed)
    return False


def step_generate_ssh_key(result: ProvisionResult) -> bool:
    """Step 3: Generate SSH keypair if not exists."""
    t0 = time.time()
    if SSH_KEY_PATH.exists():
        result.add_step("ssh_keygen", "skip",
                        f"Klucz SSH juz istnieje: {SSH_KEY_PATH}", 0)
        return True

    try:
        SSH_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        proc = _run([
            "ssh-keygen", "-t", "ed25519", "-f", str(SSH_KEY_PATH),
            "-N", "",  # No passphrase
            "-C", SSH_KEY_COMMENT,
        ], timeout=30)
        elapsed = int((time.time() - t0) * 1000)

        if proc.returncode == 0 and SSH_KEY_PATH.exists():
            result.add_step("ssh_keygen", "ok",
                            f"Wygenerowano klucz SSH: {SSH_KEY_PATH}", elapsed)
            return True
        result.add_step("ssh_keygen", "fail",
                        f"ssh-keygen failed: {proc.stderr[:200]}", elapsed)
        return False
    except Exception as e:
        result.add_step("ssh_keygen", "fail", str(e), int((time.time() - t0) * 1000))
        return False


def step_deploy_ssh_key(result: ProvisionResult, password: str) -> bool:
    """Step 4: Deploy SSH public key to router (ssh-copy-id equivalent)."""
    t0 = time.time()
    pub_key_path = Path(str(SSH_KEY_PATH) + ".pub")
    if not pub_key_path.exists():
        result.add_step("ssh_key_deploy", "fail", "Brak klucza publicznego", 0)
        return False

    pub_key = pub_key_path.read_text().strip()

    # Deploy via SSH with password — append to authorized_keys
    commands = [
        "mkdir -p /etc/dropbear",
        f"grep -qF '{pub_key}' /etc/dropbear/authorized_keys 2>/dev/null || "
        f"echo '{pub_key}' >> /etc/dropbear/authorized_keys",
        "chmod 600 /etc/dropbear/authorized_keys",
    ]
    combined_cmd = " && ".join(commands)

    rc, stdout, stderr = _ssh(result.router_ip, combined_cmd, password=password)
    elapsed = int((time.time() - t0) * 1000)

    if rc == 0:
        # Verify passwordless access works
        rc2, out2, _ = _ssh(result.router_ip, "echo KEY_OK")
        if rc2 == 0 and "KEY_OK" in out2:
            result.ssh_key_deployed = True
            result.add_step("ssh_key_deploy", "ok",
                            "Klucz SSH wgrany — bezhaslowy dostep aktywny", elapsed)
            return True
        result.add_step("ssh_key_deploy", "warn",
                        "Klucz skopiowany, ale weryfikacja bezhaslowa zawiodla — "
                        "moze byc problem z prawami /etc/dropbear/", elapsed)
        return False

    result.add_step("ssh_key_deploy", "fail",
                    f"Nie udalo sie wgrac klucza: {stderr[:200]}", elapsed)
    return False


def step_install_opkg_packages(result: ProvisionResult,
                               password: str = "",
                               include_optional: bool = False) -> bool:
    """Step 5: Install required OpenWrt packages."""
    t0 = time.time()

    # Update package list
    rc, stdout, stderr = _ssh(result.router_ip, "opkg update", timeout=60, password=password)
    if rc != 0:
        result.add_step("opkg_update", "fail",
                        f"opkg update failed: {stderr[:200]}. "
                        "Router musi miec dostep do internetu (WAN).",
                        int((time.time() - t0) * 1000))
        return False

    result.add_step("opkg_update", "ok", "opkg update OK", int((time.time() - t0) * 1000))

    # Install packages
    packages = list(OPKG_REQUIRED)
    if include_optional:
        packages.extend(OPKG_OPTIONAL)

    installed = []
    failed = []
    for pkg in packages:
        t1 = time.time()
        rc, stdout, stderr = _ssh(
            result.router_ip, f"opkg install {pkg}", timeout=120, password=password
        )
        elapsed_pkg = int((time.time() - t1) * 1000)

        if rc == 0 or "already installed" in (stdout + stderr).lower():
            installed.append(pkg)
            result.add_step(f"opkg_{pkg}", "ok",
                            f"Pakiet {pkg} zainstalowany", elapsed_pkg)
        else:
            failed.append(pkg)
            is_optional = pkg in OPKG_OPTIONAL
            result.add_step(f"opkg_{pkg}",
                            "warn" if is_optional else "fail",
                            f"Pakiet {pkg}: {stderr[:100]}",
                            elapsed_pkg)

    result.packages_installed = installed
    elapsed = int((time.time() - t0) * 1000)

    if failed and any(p in OPKG_REQUIRED for p in failed):
        result.add_step("opkg_summary", "warn",
                        f"Zainstalowano {len(installed)}/{len(packages)} pakietow. "
                        f"Brakuje: {', '.join(failed)}", elapsed)
        return False

    result.add_step("opkg_summary", "ok",
                    f"Wszystkie wymagane pakiety zainstalowane ({len(installed)})", elapsed)
    return True


def step_configure_wifi(result: ProvisionResult, ssid: str = "SYLION-Pixel",
                        wifi_key: str = "", password: str = "") -> bool:
    """
    Krok 5b: Konfiguracja WiFi SSID i WPA2-PSK przez UCI.
    [WG-001 / WIFI-001] — automatyczna konfiguracja zamiast ręcznej.
    """
    t0 = time.time()
    if not ssid:
        result.add_step("wifi_config", "skip", "Brak SSID — konfiguracja WiFi pominięta", 0)
        return True
    cmds = [
        f"uci set wireless.@wifi-iface[0].ssid={shlex.quote(ssid)}",
        f"uci set wireless.@wifi-iface[0].encryption=psk2",
    ]
    if wifi_key:
        if len(wifi_key) < 8:
            result.add_step("wifi_config", "fail",
                            "Hasło WiFi musi mieć minimum 8 znaków", 0)
            return False
        cmds.append(f"uci set wireless.@wifi-iface[0].key={shlex.quote(wifi_key)}")
    cmds += ["uci commit wireless", "wifi reload"]
    rc, _, stderr = _ssh(result.router_ip, " && ".join(cmds),
                         timeout=20, password=password)
    elapsed = int((time.time() - t0) * 1000)
    if rc != 0:
        result.add_step("wifi_config", "fail",
                        f"UCI wireless nieudany: {stderr[:200]}", elapsed)
        return False
    result.add_step("wifi_config", "ok",
                    f"WiFi SSID='{ssid}' (WPA2-PSK) skonfigurowany przez UCI", elapsed)
    return True


def step_deploy_agent(result: ProvisionResult, password: str = "") -> bool:
    """Step 6: Deploy SYLION agent files to router."""
    t0 = time.time()

    # Create remote directory
    rc, _, stderr = _ssh(result.router_ip, f"mkdir -p {AGENT_DEPLOY_DIR}", password=password)
    if rc != 0:
        result.add_step("agent_deploy", "fail",
                        f"mkdir failed: {stderr[:200]}", int((time.time() - t0) * 1000))
        return False

    # Find agent files relative to this script
    pipeline_dir = Path(__file__).parent
    deployed = []
    failed = []

    for fname in AGENT_FILES:
        local = pipeline_dir / fname
        if not local.exists():
            failed.append(fname)
            result.add_step(f"deploy_{fname}", "warn",
                            f"Plik {fname} nie istnieje w pipeline", 0)
            continue

        rc, err = _scp(result.router_ip, str(local), AGENT_DEPLOY_DIR + fname, password=password)
        if rc == 0:
            deployed.append(fname)
        else:
            failed.append(fname)
            result.add_step(f"deploy_{fname}", "fail",
                            f"SCP failed: {err[:100]}", 0)

    elapsed = int((time.time() - t0) * 1000)
    if deployed:
        result.agent_deployed = True
        result.add_step("agent_deploy", "ok",
                        f"Wgrano {len(deployed)} plikow do {AGENT_DEPLOY_DIR}", elapsed)
        return True

    result.add_step("agent_deploy", "fail", "Nie wgrano zadnych plikow", elapsed)
    return False


def step_configure_autostart(result: ProvisionResult, password: str = "") -> bool:
    """Step 6b: Configure agent autostart via rc.local."""
    t0 = time.time()
    # Add to rc.local if not already present
    # Step 1: Check if already configured
    rc_grep, stdout_grep, _ = _ssh(result.router_ip,
        "grep -qF 'sylion' /etc/rc.local 2>/dev/null && echo PRESENT || echo ABSENT",
        password=password)
    if rc_grep == 0 and "PRESENT" in stdout_grep:
        elapsed = int((time.time() - t0) * 1000)
        result.add_step("autostart", "ok", "Autostart juz skonfigurowany w rc.local", elapsed)
        return True

    # Step 2: Insert autostart BEFORE 'exit 0' using awk (BusyBox-safe, no \n issues)
    # awk handles newlines correctly on both BusyBox and GNU
    awk_cmd = (
        "awk '/^exit 0/ && !done "
        "{print \"# SYLION agent autostart\"; "
        "print \"python3 /etc/sylion/device_harness.py &\"; "
        "done=1} {print}' /etc/rc.local > /tmp/rc.local.tmp "
        "&& mv /tmp/rc.local.tmp /etc/rc.local "
        "&& chmod +x /etc/rc.local"
    )
    rc_awk, _, stderr_awk = _ssh(result.router_ip, awk_cmd, password=password)

    # Step 3: Verify the change — check for actual command, not just 'sylion'
    rc_verify, stdout_verify, _ = _ssh(result.router_ip,
        "grep -qF 'device_harness.py' /etc/rc.local 2>/dev/null && echo OK || echo MISSING",
        password=password)
    elapsed = int((time.time() - t0) * 1000)

    if rc_verify == 0 and "OK" in stdout_verify:
        result.add_step("autostart", "ok", "Autostart agenta skonfigurowany w rc.local", elapsed)
        return True

    # Fallback: append directly if awk failed (no 'exit 0' in rc.local or empty file)
    rc_append, _, stderr_append = _ssh(result.router_ip,
        "printf '\\n# SYLION agent autostart\\npython3 /etc/sylion/device_harness.py &\\n' >> /etc/rc.local",
        password=password)

    # Verify fallback append
    rc_verify2, stdout_verify2, _ = _ssh(result.router_ip,
        "grep -qF 'device_harness.py' /etc/rc.local 2>/dev/null && echo OK || echo MISSING",
        password=password)
    elapsed = int((time.time() - t0) * 1000)

    if rc_verify2 == 0 and "OK" in stdout_verify2:
        result.add_step("autostart", "ok",
                        "Autostart agenta dopisany do rc.local (fallback append)", elapsed)
        return True

    result.add_step("autostart", "warn",
                    f"Nie udalo sie skonfigurowac autostart: awk={stderr_awk[:100]}, "
                    f"append={stderr_append[:100]}", elapsed)
    return False


def step_verify_full(result: ProvisionResult) -> bool:
    """Step 7: Full verification — SSH, python3, agent, uname."""
    t0 = time.time()
    checks = [
        ("uname", "uname -a"),
        ("python3", "python3 --version"),
        ("agent_check", f"ls -la {AGENT_DEPLOY_DIR}"),
        ("sha256sum", "sha256sum --version 2>&1 | head -1"),
    ]

    all_ok = True
    for name, cmd in checks:
        rc, stdout, stderr = _ssh(result.router_ip, cmd)
        if rc == 0:
            result.add_step(f"verify_{name}", "ok", stdout[:200], 0)
        else:
            result.add_step(f"verify_{name}", "fail", stderr[:200], 0)
            all_ok = False

    elapsed = int((time.time() - t0) * 1000)
    if all_ok:
        result.add_step("verify_summary", "ok",
                        "Pelna weryfikacja OK — router gotowy do pracy z SYLION", elapsed)
    else:
        result.add_step("verify_summary", "warn",
                        "Czesciowa weryfikacja — niektore komponenty niedostepne", elapsed)

    return all_ok


# ---------------------------------------------------------------------------
# Main provisioning orchestrator
# ---------------------------------------------------------------------------

def provision_router(ip: str = DEFAULT_ROUTER_IP,
                     password: str = "",
                     include_optional_pkgs: bool = False,
                     skip_agent_deploy: bool = False,
                     wifi_ssid: str = "SYLION-Pixel",
                     wifi_key: str = "",
                     skip_wifi: bool = False) -> ProvisionResult:
    """
    Full auto-provisioning of a new GL.iNet router.

    Args:
        ip: Router IP address (default 192.168.8.1)
        password: Root password set during first-boot wizard.
                  Required for first-time SSH key deployment.
        include_optional_pkgs: Also install optional packages (tcpdump, etc.)
        skip_agent_deploy: Skip deploying SYLION agent files

    Returns:
        ProvisionResult with detailed step-by-step results
    """
    t_start = time.time()
    result = ProvisionResult(router_ip=ip)

    import ipaddress as _ipaddress
    try:
        _ipaddress.ip_address(ip)
    except ValueError:
        result.error = f"Nieprawidlowy adres IP: {ip}"
        result.add_step("ip_validate", "fail", f"'{ip}' nie jest prawidlowym adresem IPv4/IPv6", 0)
        return result

    if password and not shutil.which("sshpass"):
        result.add_step("preflight_sshpass", "fail",
                        "sshpass nie jest zainstalowany. Zainstaluj: sudo apt install sshpass", 0)
        result.error = "Brak wymaganego narzedzia: sshpass"
        result.elapsed_s = time.time() - t_start
        return result

    log.info(f"Starting router provisioning for {ip}")

    # Step 1: Reachability
    if not step_check_reachability(result):
        result.error = "Router nieosiagalny — sprawdz kabel Ethernet"
        result.elapsed_s = time.time() - t_start
        return result

    # Step 1.5: Auto-complete first-boot wizard (GL.iNet firmware 4.x)
    t_wiz = time.time()
    if not password:
        result.error = "Haslo admina routera jest wymagane — podaj w formularzu provisioningu"
        result.add_step("password_check", "fail",
                        "Brak hasla: operator musi podac haslo admina routera", 0)
        result.elapsed_s = time.time() - t_start
        return result
    wizard_password = password
    init_status = _glinet_check_initialized(ip)
    if init_status is True:
        result.add_step("wizard_check", "ok",
                        "Router juz zainicjalizowany — pomijam wizard", 0)
    elif init_status is None:
        result.add_step("wizard_check", "warn",
                        "Nie mozna sprawdzic stanu wizard — blad polaczenia. "
                        "Probuje uruchomic wizard na wszelki wypadek...", 0)
        log.info("Router init status unknown — attempting auto-wizard")
    else:
        log.info("Router not initialized — running auto-wizard")
        result.add_step("wizard_check", "ok",
                        "Router niezainicjalizowany — uruchamiam auto-wizard", 0)
    if init_status is not True:
        ok, detail = _glinet_run_wizard(ip, wizard_password, DEFAULT_WIZARD_LANG)
        elapsed_wiz = int((time.time() - t_wiz) * 1000)
        if ok:
            result.add_step("wizard_init", "ok",
                            f"Wizard zakonczony: jezyk={DEFAULT_WIZARD_LANG}, "
                            f"haslo ustawione. {detail}", elapsed_wiz)
            # After wizard, the password we set becomes the SSH root password
            # Give the router a moment to restart services after init
            time.sleep(3)
        else:
            result.add_step("wizard_init", "warn",
                            f"Auto-wizard nie powiodl sie: {detail}. "
                            f"Moze byc wymagane reczne przejscie wizarda.", elapsed_wiz)
    else:
        result.add_step("wizard_check", "skip",
                        "Router juz zainicjalizowany — pomijam wizard",
                        int((time.time() - t_wiz) * 1000))

    # Step 2: Check SSH
    ssh_ok = step_check_ssh_available(result, password=password)

    # Step 3: Generate SSH key if needed
    step_generate_ssh_key(result)

    # Step 4: Deploy SSH key (needs password for first time)
    if password:
        step_deploy_ssh_key(result, password)
    elif not ssh_ok:
        result.add_step("ssh_key_deploy", "warn",
                        "Brak hasla root — nie mozna wgrac klucza SSH. "
                        "Podaj haslo root ustawione w wizardzie routera.", 0)

    # Step 5: Install packages
    # Use password if key not yet deployed
    auth_pass = password if not result.ssh_key_deployed else ""
    step_install_opkg_packages(result, password=auth_pass,
                               include_optional=include_optional_pkgs)

    # Step 6: Deploy agent
    if not skip_agent_deploy:
        step_deploy_agent(result, password=auth_pass)

    # Step 6b: Autostart
    if not skip_agent_deploy and result.agent_deployed:
        step_configure_autostart(result, password=auth_pass)

    # Krok 5b: WiFi SSID (v5.10 — WIFI-001)
    if not skip_wifi:
        step_configure_wifi(result, ssid=wifi_ssid, wifi_key=wifi_key, password=auth_pass)

    # Step 7: Verify
    step_verify_full(result)

    result.elapsed_s = time.time() - t_start

    # Strict success: ping + SSH + required packages + agent (if not skipped)
    ping_ok = any(s["name"] == "ping" and s["status"] == "ok" for s in result.steps)
    ssh_ok_final = result.ssh_key_deployed or ssh_ok
    pkgs_ok = any(s["name"] == "opkg_summary" and s["status"] == "ok" for s in result.steps)
    agent_ok = skip_agent_deploy or result.agent_deployed
    verify_ok = any(s["name"] == "verify_summary" and s["status"] == "ok" for s in result.steps)
    critical_ok = ping_ok and ssh_ok_final and pkgs_ok and agent_ok and verify_ok

    result.success = critical_ok
    if not result.success and not result.error:
        result.error = "Provisioning niekompletny — sprawdz szczegoly krokow"

    log.info(f"Provisioning {'OK' if result.success else 'FAILED'} in {result.elapsed_s:.1f}s")
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="SYLION Router Auto-Provisioning")
    parser.add_argument("--ip", default=DEFAULT_ROUTER_IP, help="Router IP address")
    parser.add_argument("--password", default="", help="Root password from first-boot wizard")
    parser.add_argument("--optional-pkgs", action="store_true", help="Install optional packages")
    parser.add_argument("--skip-agent", action="store_true", help="Skip agent deployment")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    args = parser.parse_args()

    result = provision_router(
        ip=args.ip,
        password=args.password,
        include_optional_pkgs=args.optional_pkgs,
        skip_agent_deploy=args.skip_agent,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"\n{'=' * 60}")
        print(f"SYLION Router Provisioning — {result.router_ip}")
        print(f"{'=' * 60}")
        for step in result.steps:
            icon = {"ok": "✓", "warn": "⚠", "fail": "✗", "skip": "—"}.get(step["status"], "?")
            print(f"  [{icon}] {step['name']}: {step['detail']}")
        print(f"\nWynik: {'SUKCES' if result.success else 'BLAD'}")
        if result.error:
            print(f"Blad: {result.error}")
        print(f"Czas: {result.elapsed_s:.1f}s")

    sys.exit(0 if result.success else 1)
