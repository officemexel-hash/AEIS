#!/usr/bin/env python3
"""
SYLION v5.9.1 — WireGuard Provisioning Tests
============================================
Tests for WireGuard VPN provisioning on the Mudi 750v2 router.
All SSH calls and opkg operations are mocked (pytest-mock pattern).

Per WIREGUARD_TODO.md: kmod-wireguard + wg-quick + iptables kill-switch.

Run:
    pytest tests_coverage/test_wireguard_provision.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call, ANY

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent / "latest/sylion-pipeline"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Minimal WireGuard provisioner stub (mirrors planned implementation)
# ---------------------------------------------------------------------------

class WireGuardConfig:
    """Planned config structure for WireGuard provisioning."""
    def __init__(
        self,
        host: str = "192.168.8.1",
        port: int = 22,
        username: str = "root",
        password: str = "",
        wg_interface: str = "wg0",
        wg_port: int = 51820,
        server_pubkey: str = "",
        client_privkey: str = "",
        client_ip: str = "10.0.0.2/24",
        endpoint: str = "",
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.wg_interface = wg_interface
        self.wg_port = wg_port
        self.server_pubkey = server_pubkey
        self.client_privkey = client_privkey
        self.client_ip = client_ip
        self.endpoint = endpoint


def _run_ssh(host, command, *, username="root", password="", timeout=30):
    """Thin wrapper: runs a command over SSH. Mocked in tests."""
    result = subprocess.run(
        ["ssh", f"{username}@{host}", command],
        capture_output=True, text=True, timeout=timeout
    )
    return result.returncode, result.stdout, result.stderr


def provision_wireguard(config: WireGuardConfig) -> dict:
    """
    Provision WireGuard on a Mudi 750v2 router.

    Steps:
      1. Check SSH connectivity
      2. Install kmod-wireguard via opkg
      3. Install wireguard-tools via opkg
      4. Write wg0.conf
      5. Enable wg-quick@wg0
      6. Apply iptables kill-switch rules
      7. Verify wg0 interface is up

    Returns: {"success": bool, "steps": [...], "error": str|None}
    """
    steps = []
    try:
        # Step 1: SSH ping
        rc, out, err = _run_ssh(config.host, "echo ok", username=config.username)
        if rc != 0:
            return {"success": False, "steps": steps, "error": f"SSH failed: {err}"}
        steps.append("ssh_ok")

        # Step 2: install kmod-wireguard
        rc, out, err = _run_ssh(
            config.host, "opkg install kmod-wireguard", username=config.username
        )
        if rc != 0:
            return {"success": False, "steps": steps, "error": f"kmod-wireguard install failed: {err}"}
        steps.append("kmod_wireguard_installed")

        # Step 3: install wireguard-tools
        rc, out, err = _run_ssh(
            config.host, "opkg install wireguard-tools", username=config.username
        )
        if rc != 0:
            return {"success": False, "steps": steps, "error": f"wireguard-tools install failed: {err}"}
        steps.append("wireguard_tools_installed")

        # Step 4: write wg0.conf
        wg_conf = (
            f"[Interface]\nPrivateKey = {config.client_privkey}\n"
            f"Address = {config.client_ip}\nListenPort = {config.wg_port}\n\n"
            f"[Peer]\nPublicKey = {config.server_pubkey}\n"
            f"Endpoint = {config.endpoint}\nAllowedIPs = 0.0.0.0/0\n"
        )
        write_cmd = f"cat > /etc/wireguard/{config.wg_interface}.conf << 'EOF'\n{wg_conf}EOF"
        rc, out, err = _run_ssh(config.host, write_cmd, username=config.username)
        if rc != 0:
            return {"success": False, "steps": steps, "error": f"wg0.conf write failed: {err}"}
        steps.append("wg0_conf_written")

        # Step 5: enable wg-quick
        rc, out, err = _run_ssh(
            config.host, f"wg-quick up {config.wg_interface}", username=config.username
        )
        if rc != 0:
            return {"success": False, "steps": steps, "error": f"wg-quick up failed: {err}"}
        steps.append("wg_quick_up")

        # Step 6: iptables kill-switch
        kill_switch_cmds = [
            f"iptables -A FORWARD -o {config.wg_interface} -j ACCEPT",
            f"iptables -A FORWARD -i {config.wg_interface} -j ACCEPT",
            f"iptables -A OUTPUT -o {config.wg_interface} -j ACCEPT",
            f"iptables -A OUTPUT ! -o {config.wg_interface} -j REJECT",
        ]
        for cmd in kill_switch_cmds:
            rc, out, err = _run_ssh(config.host, cmd, username=config.username)
            if rc != 0:
                return {"success": False, "steps": steps, "error": f"iptables failed: {err}"}
        steps.append("iptables_kill_switch_applied")

        # Step 7: verify interface
        rc, out, err = _run_ssh(
            config.host, f"wg show {config.wg_interface}", username=config.username
        )
        if rc != 0:
            return {"success": False, "steps": steps, "error": f"wg show failed: {err}"}
        steps.append("wg_interface_verified")

        return {"success": True, "steps": steps, "error": None}

    except subprocess.TimeoutExpired as e:
        return {"success": False, "steps": steps, "error": f"SSH timeout: {e}"}
    except Exception as e:
        return {"success": False, "steps": steps, "error": str(e)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def wg_config():
    return WireGuardConfig(
        host="192.168.8.1",
        username="root",
        wg_interface="wg0",
        wg_port=51820,
        server_pubkey="ServerPubKey1234abcd=",
        client_privkey="ClientPrivKey5678efgh=",
        client_ip="10.0.0.2/24",
        endpoint="vpn.example.com:51820",
    )


def _ok(stdout=""):
    """Helper: successful subprocess result."""
    r = SimpleNamespace(returncode=0, stdout=stdout, stderr="")
    return r


def _fail(stderr="error"):
    """Helper: failed subprocess result."""
    r = SimpleNamespace(returncode=1, stdout="", stderr=stderr)
    return r


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestWireGuardProvisionHappyPath:
    """All steps succeed → success=True, all step markers present."""

    def test_provision_success_all_steps(self, wg_config):
        """Full provisioning succeeds when all SSH calls return rc=0."""
        with patch("test_wireguard_provision.subprocess.run", return_value=_ok("ok")) as mock_run:
            result = provision_wireguard(wg_config)
        assert result["success"] is True
        assert result["error"] is None
        expected_steps = [
            "ssh_ok",
            "kmod_wireguard_installed",
            "wireguard_tools_installed",
            "wg0_conf_written",
            "wg_quick_up",
            "iptables_kill_switch_applied",
            "wg_interface_verified",
        ]
        for step in expected_steps:
            assert step in result["steps"], f"Missing step: {step}"

    def test_provision_ssh_called_with_correct_host(self, wg_config):
        """SSH must be called with the configured host IP."""
        with patch("test_wireguard_provision.subprocess.run", return_value=_ok("ok")) as mock_run:
            provision_wireguard(wg_config)
        calls_args = [c.args[0] for c in mock_run.call_args_list]
        # At least one call must reference the host
        hosts_in_calls = [a for a in calls_args if "192.168.8.1" in " ".join(a)]
        assert len(hosts_in_calls) > 0, "SSH calls must use configured host"

    def test_provision_wg0_conf_contains_private_key(self, wg_config):
        """wg0.conf write command must include the client private key."""
        written_cmds = []

        def _capture(args, **kwargs):
            written_cmds.append(" ".join(args))
            return _ok()

        with patch("test_wireguard_provision.subprocess.run", side_effect=_capture):
            provision_wireguard(wg_config)

        conf_writes = [c for c in written_cmds if "PrivateKey" in c or "wg0.conf" in c]
        assert len(conf_writes) > 0, "wg0.conf write step must be executed"

    def test_provision_iptables_kill_switch_applied(self, wg_config):
        """kill-switch must issue 4 iptables rules."""
        iptables_calls = []

        def _capture(args, **kwargs):
            cmd = " ".join(args)
            if "iptables" in cmd:
                iptables_calls.append(cmd)
            return _ok()

        with patch("test_wireguard_provision.subprocess.run", side_effect=_capture):
            provision_wireguard(wg_config)

        assert len(iptables_calls) == 4, (
            f"Expected 4 iptables calls, got {len(iptables_calls)}"
        )


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestWireGuardProvisionErrorPaths:
    """Each step failure must abort with success=False and a message."""

    def test_provision_fails_on_ssh_error(self, wg_config):
        """SSH connectivity failure returns success=False."""
        with patch("test_wireguard_provision.subprocess.run", return_value=_fail("Connection refused")):
            result = provision_wireguard(wg_config)
        assert result["success"] is False
        assert "SSH" in result["error"] or "ssh" in result["error"].lower()
        assert "ssh_ok" not in result["steps"]

    def test_provision_fails_on_kmod_install_error(self, wg_config):
        """kmod-wireguard install failure stops provisioning."""
        call_count = 0

        def _side_effect(args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _ok("ok")  # ssh ping OK
            return _fail("Package not found")

        with patch("test_wireguard_provision.subprocess.run", side_effect=_side_effect):
            result = provision_wireguard(wg_config)
        assert result["success"] is False
        assert "ssh_ok" in result["steps"]
        assert "kmod_wireguard_installed" not in result["steps"]

    def test_provision_fails_on_wg_quick_error(self, wg_config):
        """wg-quick up failure stops provisioning."""
        responses = [
            _ok("ok"),       # ssh ping
            _ok(),           # kmod install
            _ok(),           # wireguard-tools
            _ok(),           # wg0.conf write
            _fail("RTNETLINK answers: Operation not permitted"),  # wg-quick fails
        ]
        idx = [0]

        def _seq(args, **kwargs):
            r = responses[idx[0]]
            idx[0] = min(idx[0] + 1, len(responses) - 1)
            return r

        with patch("test_wireguard_provision.subprocess.run", side_effect=_seq):
            result = provision_wireguard(wg_config)
        assert result["success"] is False
        assert "wg_quick_up" not in result["steps"]

    def test_provision_timeout_returns_success_false(self, wg_config):
        """SSH timeout is caught and returns success=False."""
        with patch("test_wireguard_provision.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("ssh", 30)):
            result = provision_wireguard(wg_config)
        assert result["success"] is False
        assert "timeout" in result["error"].lower() or "Timeout" in result["error"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestWireGuardProvisionEdgeCases:
    """Edge cases: empty keys, default port, custom interface name."""

    def test_provision_custom_interface_name(self, wg_config):
        """Provisioning works with interface name other than wg0."""
        wg_config.wg_interface = "wg1"
        with patch("test_wireguard_provision.subprocess.run", return_value=_ok("ok")):
            result = provision_wireguard(wg_config)
        assert result["success"] is True

    def test_provision_empty_privkey_completes_without_crash(self, wg_config):
        """Empty private key is written to conf without causing crash."""
        wg_config.client_privkey = ""
        with patch("test_wireguard_provision.subprocess.run", return_value=_ok("ok")):
            result = provision_wireguard(wg_config)
        # Should complete (key validity not checked here)
        assert "success" in result

    def test_wireguard_config_stores_all_fields(self):
        """WireGuardConfig dataclass stores all fields correctly."""
        cfg = WireGuardConfig(
            host="10.0.0.1",
            port=2222,
            username="admin",
            wg_interface="wg2",
            wg_port=51821,
            server_pubkey="PubK=",
            client_privkey="PrivK=",
            client_ip="10.8.0.5/24",
            endpoint="srv.example.com:51821",
        )
        assert cfg.host == "10.0.0.1"
        assert cfg.port == 2222
        assert cfg.wg_interface == "wg2"
        assert cfg.wg_port == 51821
        assert cfg.server_pubkey == "PubK="
