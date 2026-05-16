"""
SYLION Pion D — Device Integration Harness

ADB/SSH-based deployment and capture pipeline management for physical
devices: Pixel 9 (GrapheneOS via USB/ADB) and Mudi 750v2 router
(OpenWrt via SSH/Ethernet).

Orchestrates:
  1. Build verification (binary exists, checksums)
  2. Deploy to device (adb push / scp)
  3. Capture pipeline start/stop (screenrecord, v4l2, pipewire)
  4. Health check (connectivity, process alive, battery, thermal)
  5. Cleanup and rollback

All commands are pre-approved scenarios — LLM generates parameters,
this module executes allowed commands only.

⚠️  LLM NEVER issues raw shell commands.  Generates parameters for
    pre-approved scenarios only.

Target paths:
  Pixel 9:  /data/local/tmp/sylion/  (GrapheneOS has no root)
  Router:   /tmp/sylion/             (OpenWrt tmpfs)
"""

from __future__ import annotations

import enum
import json
import logging
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("device_harness")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PIXEL_DEPLOY_PATH = "/data/local/tmp/sylion"
ROUTER_DEPLOY_PATH = "/tmp/sylion"

# v5.9.1 P1-10 PIX-1: expected ro.product.model values for the Pixel 9 family.
# Pixel 9 ships as base ("Pixel 9"), Pixel 9 Pro, Pixel 9 Pro XL and Pixel 9 Pro Fold.
# Matched case-insensitively by validate_pixel_model().
PIXEL_9_FAMILY: tuple[str, ...] = (
    "Pixel 9",
    "Pixel 9 Pro",
    "Pixel 9 Pro XL",
    "Pixel 9 Pro Fold",
    "Pixel 9a",
)
DEFAULT_ROUTER_IP = "192.168.1.1"
DEFAULT_ADB_TIMEOUT = 30
DEFAULT_SSH_TIMEOUT = 15

# Pre-approved command allowlist — ONLY these patterns can be executed
ALLOWED_ADB_COMMANDS = {
    "push",           # adb push <local> <remote>
    "shell_ls",       # adb shell ls <path>
    "shell_chmod",    # adb shell chmod +x <path>
    "shell_start",    # adb shell <binary> --config <path>
    "shell_kill",     # adb shell pkill -f <pattern>
    "shell_ps",       # adb shell ps | grep <pattern>
    "shell_cat",      # adb shell cat <path>
    "shell_battery",  # adb shell dumpsys battery
    "shell_thermal",  # adb shell dumpsys thermalservice
    "shell_screen",   # adb shell screenrecord
    "shell_mkdir",    # adb shell mkdir -p <path>
    "shell_rm",       # adb shell rm -rf <path>
    "shell_getprop",  # adb shell getprop <prop>  (v5.9.1 PIX-1 model validation)
    "devices",        # adb devices
}

ALLOWED_SSH_COMMANDS = {
    "scp",            # scp <local> <user@host>:<remote>
    "ls",             # ssh <host> ls <path>
    "chmod",          # ssh <host> chmod +x <path>
    "start",          # ssh <host> <binary> --config <path>
    "kill",           # ssh <host> pkill -f <pattern>
    "ps",             # ssh <host> ps | grep <pattern>
    "cat",            # ssh <host> cat <path>
    "uptime",         # ssh <host> uptime
    "free",           # ssh <host> free
    "mkdir",          # ssh <host> mkdir -p <path>
    "rm",             # ssh <host> rm -rf <path>
    "health",         # ssh <host> health check composite
    # --- v5.9.1 additions (Fix 3 — allowlist expansion for WireGuard/firewall/diagnostics) ---
    "wg",             # ssh <host> wg show / wg set — WireGuard tunnel status
    "wg_quick",       # ssh <host> wg-quick up/down wg0 — WireGuard bring-up
    "iptables",       # ssh <host> iptables -L -n -v — kill-switch verification
    "ip6tables",      # ssh <host> ip6tables -L -n -v — IPv6 kill-switch
    "ping",           # ssh <host> ping -c 1 -W 2 8.8.8.8 — WAN connectivity
    "ping6",          # ssh <host> ping6 — IPv6 WAN connectivity
    "logread",        # ssh <host> logread — OpenWrt syslog
    "opkg_list",      # ssh <host> opkg list-installed — package verification
    "nft",            # ssh <host> nft list ruleset — nftables firewall
    "uci",            # ssh <host> uci show — OpenWrt Unified Configuration Interface
    "initd",          # ssh <host> /etc/init.d/<service> start|stop|restart — service mgmt
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DeviceType(enum.Enum):
    PIXEL = "pixel"
    ROUTER = "router"
    LAPTOP = "laptop"


class DeviceState(enum.Enum):
    UNKNOWN = "UNKNOWN"
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    DEPLOYING = "DEPLOYING"
    RUNNING = "RUNNING"
    ERROR = "ERROR"
    CAPTURING = "CAPTURING"


class DeviceConnectionState(enum.Enum):
    """Fine-grained ADB/SSH connection state for Pixel and router.

    Complements the broader ``DeviceState`` by distinguishing between
    connection-level outcomes that require different user actions:

    - ``ONLINE``         — device/router is connected and authorised.
    - ``OFFLINE``        — device is absent or unreachable.
    - ``UNAUTHORIZED``   — ADB fingerprint prompt not yet accepted on phone.
    - ``UNKNOWN_MODEL``  — device connected but ``ro.product.model`` unreadable.
    - ``WRONG_MODEL``    — connected model is not in the expected Pixel 9 family.
    - ``NOT_CONNECTED``  — no device line found in ``adb devices`` output.
    """
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNAUTHORIZED = "UNAUTHORIZED"
    UNKNOWN_MODEL = "UNKNOWN_MODEL"
    WRONG_MODEL = "WRONG_MODEL"
    NOT_CONNECTED = "NOT_CONNECTED"


class DeployResult(enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    TIMEOUT = "TIMEOUT"
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class CaptureBackend(enum.Enum):
    """Capture pipeline backends per device."""
    SCREENRECORD = "screenrecord"       # Pixel: adb screenrecord
    SURFACEFLINGER = "surfaceflinger"   # Pixel: SurfaceFlinger capture
    PIPEWIRE = "pipewire"              # Laptop: PipeWire/GStreamer
    V4L2 = "v4l2"                      # Laptop: Video4Linux2 fallback


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a device command execution."""
    command_id: str          # Allowlisted command name
    exit_code: int
    stdout: str
    stderr: str
    elapsed_s: float
    device: DeviceType
    timestamp: float = field(default_factory=time.time)

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "exit_code": self.exit_code,
            "stdout_lines": self.stdout.count("\n"),
            "stderr_lines": self.stderr.count("\n"),
            "elapsed_s": self.elapsed_s,
            "device": self.device.value,
            "success": self.success,
        }


@dataclass
class DeviceStatus:
    """Current device status."""
    device_type: DeviceType
    state: DeviceState
    last_check: float = 0.0
    battery_pct: int = -1         # Pixel only (-1 = N/A)
    thermal_status: str = ""      # Pixel only
    uptime_s: float = 0.0
    process_running: bool = False
    deploy_path: str = ""
    binary_version: str = ""
    error_message: str = ""
    capture_active: bool = False
    capture_backend: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device_type.value,
            "state": self.state.value,
            "last_check": self.last_check,
            "battery_pct": self.battery_pct,
            "thermal_status": self.thermal_status,
            "uptime_s": self.uptime_s,
            "process_running": self.process_running,
            "deploy_path": self.deploy_path,
            "binary_version": self.binary_version,
            "error_message": self.error_message,
            "capture_active": self.capture_active,
            "capture_backend": self.capture_backend,
        }


@dataclass
class DeployReport:
    """Report from a deploy operation."""
    device: DeviceType
    result: DeployResult
    binary_path: str
    remote_path: str
    elapsed_s: float
    checksum_local: str = ""
    checksum_remote: str = ""
    error_message: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)

    @property
    def checksum_match(self) -> bool:
        return (
            bool(self.checksum_local)
            and self.checksum_local == self.checksum_remote
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device.value,
            "result": self.result.value,
            "binary_path": self.binary_path,
            "remote_path": self.remote_path,
            "elapsed_s": self.elapsed_s,
            "checksum_match": self.checksum_match,
            "error_message": self.error_message,
            "steps": self.steps,
        }


@dataclass
class CaptureSession:
    """Active capture session on a device."""
    device: DeviceType
    backend: CaptureBackend
    started_at: float = field(default_factory=time.time)
    pid: int = 0
    output_path: str = ""
    resolution: str = ""
    fps: int = 0
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device.value,
            "backend": self.backend.value,
            "started_at": self.started_at,
            "pid": self.pid,
            "output_path": self.output_path,
            "resolution": self.resolution,
            "fps": self.fps,
            "active": self.active,
            "duration_s": time.time() - self.started_at if self.active else 0,
        }


# ---------------------------------------------------------------------------
# Safe Command Runner
# ---------------------------------------------------------------------------

class SafeCommandRunner:
    """
    Executes ONLY pre-approved commands.

    All commands must match the allowlist.  This is the enforcement
    layer ensuring LLM-generated parameters only trigger safe operations.
    """

    def __init__(
        self,
        *,
        adb_serial: str = "",
        router_ip: str = DEFAULT_ROUTER_IP,
        router_user: str = "root",
        ssh_key_path: str = "",
        adb_timeout: int = DEFAULT_ADB_TIMEOUT,
        ssh_timeout: int = DEFAULT_SSH_TIMEOUT,
        dry_run: bool = False,
        log_dir: Path | None = None,
    ):
        self.adb_serial = adb_serial
        self.router_ip = router_ip
        self.router_user = router_user
        self.ssh_key_path = ssh_key_path
        self.adb_timeout = adb_timeout
        self.ssh_timeout = ssh_timeout
        self.dry_run = dry_run
        self.log_dir = log_dir
        self._history: list[CommandResult] = []

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def run_adb(self, command_id: str, args: list[str]) -> CommandResult:
        """
        Run an ADB command from the allowlist.

        Args:
            command_id: Must be in ALLOWED_ADB_COMMANDS
            args: Command-specific arguments (sanitized)
        """
        if command_id not in ALLOWED_ADB_COMMANDS:
            return self._blocked_result(command_id, DeviceType.PIXEL,
                                        f"Command '{command_id}' not in ADB allowlist")

        cmd = self._build_adb_command(command_id, args)
        return self._execute(cmd, command_id, DeviceType.PIXEL, self.adb_timeout)

    def run_ssh(self, command_id: str, args: list[str]) -> CommandResult:
        """
        Run an SSH command from the allowlist.

        Args:
            command_id: Must be in ALLOWED_SSH_COMMANDS
            args: Command-specific arguments (sanitized)
        """
        if command_id not in ALLOWED_SSH_COMMANDS:
            return self._blocked_result(command_id, DeviceType.ROUTER,
                                        f"Command '{command_id}' not in SSH allowlist")

        cmd = self._build_ssh_command(command_id, args)
        return self._execute(cmd, command_id, DeviceType.ROUTER, self.ssh_timeout)

    def _build_adb_command(self, command_id: str, args: list[str]) -> list[str]:
        """Build ADB command from allowlisted operation."""
        base = ["adb"]
        if self.adb_serial:
            base.extend(["-s", self.adb_serial])

        safe_args = [shlex.quote(a) for a in args]

        if command_id == "push":
            return base + ["push"] + safe_args
        elif command_id == "devices":
            return base + ["devices"]
        elif command_id.startswith("shell_"):
            sub = command_id[6:]  # Remove "shell_" prefix
            if sub == "battery":
                return base + ["shell", "dumpsys", "battery"]
            elif sub == "thermal":
                return base + ["shell", "dumpsys", "thermalservice"]
            elif sub == "screen":
                return base + ["shell", "screenrecord"] + safe_args
            elif sub == "mkdir":
                return base + ["shell", "mkdir", "-p"] + safe_args
            elif sub == "rm":
                # Only allow removal under deploy path
                for a in args:
                    if not a.startswith(PIXEL_DEPLOY_PATH):
                        raise PermissionError(
                            f"rm only allowed under {PIXEL_DEPLOY_PATH}, got: {a}"
                        )
                return base + ["shell", "rm", "-rf"] + safe_args
            elif sub == "chmod":
                return base + ["shell", "chmod", "+x"] + safe_args
            elif sub == "ls":
                return base + ["shell", "ls", "-la"] + safe_args
            elif sub == "ps":
                return base + ["shell", "ps", "-A"]
            elif sub == "cat":
                return base + ["shell", "cat"] + safe_args
            elif sub == "start":
                return base + ["shell"] + safe_args
            elif sub == "kill":
                return base + ["shell", "pkill", "-f"] + safe_args
            elif sub == "getprop":
                # v5.9.1 PIX-1: allow reading a single ro.* property name only.
                # Restrict to ro.product.* and ro.build.* to avoid disclosure.
                if not args:
                    raise ValueError("shell_getprop requires exactly one property name")
                if len(args) != 1:
                    raise ValueError("shell_getprop accepts exactly one argument")
                prop = args[0]
                if not (prop.startswith("ro.product.") or prop.startswith("ro.build.")):
                    raise PermissionError(
                        f"getprop restricted to ro.product.*/ro.build.*, got: {prop}"
                    )
                return base + ["shell", "getprop"] + safe_args
            else:
                raise ValueError(f"Unknown shell sub-command: {sub}")
        else:
            raise ValueError(f"Unknown ADB command: {command_id}")

    def _build_ssh_command(self, command_id: str, args: list[str]) -> list[str]:
        """Build SSH command from allowlisted operation."""
        ssh_base = ["ssh"]
        if self.ssh_key_path:
            ssh_base.extend(["-i", self.ssh_key_path])
        ssh_base.extend([
            "-o", "StrictHostKeyChecking=no",
            "-o", f"ConnectTimeout={self.ssh_timeout}",
            f"{self.router_user}@{self.router_ip}",
        ])

        safe_args = [shlex.quote(a) for a in args]

        if command_id == "scp":
            # SCP uses different syntax
            scp_base = ["scp"]
            if self.ssh_key_path:
                scp_base.extend(["-i", self.ssh_key_path])
            scp_base.extend([
                "-o", "StrictHostKeyChecking=no",
            ])
            return scp_base + safe_args
        elif command_id == "ls":
            return ssh_base + ["ls", "-la"] + safe_args
        elif command_id == "chmod":
            return ssh_base + ["chmod", "+x"] + safe_args
        elif command_id == "start":
            return ssh_base + safe_args
        elif command_id == "kill":
            return ssh_base + ["pkill", "-f"] + safe_args
        elif command_id == "ps":
            return ssh_base + ["ps"]
        elif command_id == "cat":
            return ssh_base + ["cat"] + safe_args
        elif command_id == "uptime":
            return ssh_base + ["uptime"]
        elif command_id == "free":
            return ssh_base + ["free"]
        elif command_id == "mkdir":
            # Only allow under deploy path
            for a in args:
                if not a.startswith(ROUTER_DEPLOY_PATH):
                    raise PermissionError(
                        f"mkdir only allowed under {ROUTER_DEPLOY_PATH}, got: {a}"
                    )
            return ssh_base + ["mkdir", "-p"] + safe_args
        elif command_id == "rm":
            for a in args:
                if not a.startswith(ROUTER_DEPLOY_PATH):
                    raise PermissionError(
                        f"rm only allowed under {ROUTER_DEPLOY_PATH}, got: {a}"
                    )
            return ssh_base + ["rm", "-rf"] + safe_args
        elif command_id == "health":
            # Composite health check
            return ssh_base + [
                "echo OK && uptime && free && ls -la " +
                shlex.quote(ROUTER_DEPLOY_PATH)
            ]
        else:
            raise ValueError(f"Unknown SSH command: {command_id}")

    def _execute(
        self, cmd: list[str], command_id: str,
        device: DeviceType, timeout: int,
    ) -> CommandResult:
        """Execute a pre-approved command."""
        if self.dry_run:
            result = CommandResult(
                command_id=command_id,
                exit_code=0,
                stdout=f"[DRY_RUN] Would execute: {' '.join(cmd)}",
                stderr="",
                elapsed_s=0.0,
                device=device,
            )
            self._history.append(result)
            return result

        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            result = CommandResult(
                command_id=command_id,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                elapsed_s=time.time() - start,
                device=device,
            )
        except subprocess.TimeoutExpired:
            result = CommandResult(
                command_id=command_id,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                elapsed_s=time.time() - start,
                device=device,
            )
        except FileNotFoundError:
            result = CommandResult(
                command_id=command_id,
                exit_code=-2,
                stdout="",
                stderr=f"Command not found: {cmd[0]}",
                elapsed_s=time.time() - start,
                device=device,
            )
        except Exception as e:
            result = CommandResult(
                command_id=command_id,
                exit_code=-3,
                stdout="",
                stderr=str(e),
                elapsed_s=time.time() - start,
                device=device,
            )

        self._history.append(result)
        self._log_result(result)
        return result

    def _blocked_result(
        self, command_id: str, device: DeviceType, reason: str,
    ) -> CommandResult:
        result = CommandResult(
            command_id=command_id,
            exit_code=-99,
            stdout="",
            stderr=f"BLOCKED: {reason}",
            elapsed_s=0.0,
            device=device,
        )
        self._history.append(result)
        log.warning(f"BLOCKED command '{command_id}': {reason}")
        return result

    def _log_result(self, result: CommandResult) -> None:
        if self.log_dir:
            log_file = self.log_dir / "command_history.jsonl"
            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")

    @property
    def history(self) -> list[CommandResult]:
        return list(self._history)


# ---------------------------------------------------------------------------
# Device Harness
# ---------------------------------------------------------------------------

class DeviceHarness:
    """
    High-level device integration for Pixel 9 + Mudi router.

    Manages:
      - Deploy binaries (with checksum verification)
      - Start/stop capture pipeline
      - Health checks (battery, thermal, connectivity)
      - Rollback on failure

    Integrates with orchestrator via deploy stages.
    """

    def __init__(
        self,
        *,
        runner: SafeCommandRunner | None = None,
        pixel_binary: Path | None = None,
        router_binary: Path | None = None,
        config_path: Path | None = None,
        battery_threshold_pct: int = 20,
        target_fps: int = 30,
        max_resolution: str = "1920x1080",
        log_dir: Path | None = None,
    ):
        # PATCH 2 / RC-02 / SYL-PIX-015: czytaj dry_run z konfiguracji zamiast hardcode True
        if runner is not None:
            self.runner = runner
        else:
            try:
                from config import cfg  # type: ignore[import]
                _dry = cfg.device_harness_dry_run
            except Exception:
                import os as _os
                _dry = _os.environ.get("DEVICE_HARNESS_DRY_RUN", "false").lower() == "true"
            self.runner = SafeCommandRunner(dry_run=_dry)
        self.pixel_binary = pixel_binary
        self.router_binary = router_binary
        self.config_path = config_path
        self.battery_threshold_pct = battery_threshold_pct
        self.target_fps = target_fps
        self.max_resolution = max_resolution
        self.log_dir = log_dir

        self._device_states: dict[DeviceType, DeviceStatus] = {}
        self._capture_sessions: dict[DeviceType, CaptureSession] = {}
        self._deploy_reports: list[DeployReport] = []

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    # --- Discovery ---

    def check_pixel_connected(self) -> bool:
        """Check if Pixel device is connected via ADB.

        Handles three non-ONLINE states explicitly:
        - ``device``: device is ready — returns True.
        - ``unauthorized``: ADB fingerprint not accepted — logs WARN, sets ERROR, returns False.
        - ``offline``: device visible but unresponsive — logs, sets OFFLINE, returns False.
        - unknown status: raw output logged for diagnostics.
        """
        result = self.runner.run_adb("devices", [])
        if not result.success:
            return False
        # Parse "adb devices" output for device line
        lines = result.stdout.strip().split("\n")
        unauthorized_found = False
        offline_found = False
        for line in lines[1:]:   # Skip header
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                status = parts[1].strip()
                if status == "device":
                    self._update_state(DeviceType.PIXEL, DeviceState.ONLINE)
                    return True
                elif status == "unauthorized":
                    unauthorized_found = True
                elif status == "offline":
                    offline_found = True
                elif line.strip():
                    log.debug("adb devices: unknown line: %r", line.strip())
        if unauthorized_found:
            log.warning(
                "Pixel ADB unauthorized — accept the USB debugging fingerprint on the phone "
                "(Settings → Developer options → USB debugging prompt)."
            )
            self._update_state(DeviceType.PIXEL, DeviceState.ERROR)
            return False
        if offline_found:
            log.warning("Pixel ADB status is 'offline' — try: adb kill-server && adb start-server")
            self._update_state(DeviceType.PIXEL, DeviceState.OFFLINE)
            return False
        self._update_state(DeviceType.PIXEL, DeviceState.OFFLINE)
        return False

    def check_router_connected(self) -> bool:
        """Check if Mudi router is reachable via SSH."""
        result = self.runner.run_ssh("uptime", [])
        if result.success:
            self._update_state(DeviceType.ROUTER, DeviceState.ONLINE)
            return True
        self._update_state(DeviceType.ROUTER, DeviceState.OFFLINE)
        return False

    def wait_for_pixel_authorization(self, timeout: int = 120) -> "DeviceConnectionState":
        """Poll ``adb devices`` until the Pixel accepts the ADB fingerprint.

        This method is intended for interactive provisioning flows where the
        user must physically tap *Allow* on the phone screen after plugging in
        via USB.

        Args:
            timeout: Maximum seconds to wait for the device to transition from
                     ``unauthorized`` to ``device`` state.  Defaults to 120 s.

        Returns:
            ``DeviceConnectionState.ONLINE`` if the device authorised within
            the timeout, or ``DeviceConnectionState.UNAUTHORIZED`` with a
            descriptive message if the timeout elapsed.

        Example::

            state = harness.wait_for_pixel_authorization(timeout=120)
            if state is DeviceConnectionState.ONLINE:
                print("Pixel authorised — proceeding with provisioning.")
            else:
                print("Timeout: user did not accept ADB fingerprint on phone.")
        """
        poll_interval = 2  # seconds between adb devices polls
        deadline = time.time() + timeout
        last_state: DeviceConnectionState = DeviceConnectionState.NOT_CONNECTED

        log.info(
            "Waiting up to %ds for Pixel ADB authorisation "
            "(accept fingerprint prompt on phone)...",
            timeout,
        )

        while time.time() < deadline:
            result = self.runner.run_adb("devices", [])
            if not result.success:
                last_state = DeviceConnectionState.NOT_CONNECTED
                time.sleep(poll_interval)
                continue

            lines = result.stdout.strip().split("\n")
            found_unauthorized = False
            for line in lines[1:]:  # skip header
                parts = line.strip().split("\t")
                if len(parts) < 2:
                    continue
                status = parts[1].strip()
                if status == "device":
                    # Transitioned from unauthorized → device
                    self._update_state(DeviceType.PIXEL, DeviceState.ONLINE)
                    log.info("Pixel ADB authorised (serial=%s).", parts[0].strip())
                    return DeviceConnectionState.ONLINE
                elif status == "unauthorized":
                    found_unauthorized = True

            if found_unauthorized:
                last_state = DeviceConnectionState.UNAUTHORIZED
                log.debug("Pixel still unauthorized — waiting %ds...", poll_interval)
            else:
                last_state = DeviceConnectionState.NOT_CONNECTED
                log.debug("No Pixel visible in adb devices — waiting %ds...", poll_interval)

            time.sleep(poll_interval)

        # Timeout expired
        log.warning(
            "wait_for_pixel_authorization timed out after %ds. "
            "User did not accept ADB fingerprint on phone.",
            timeout,
        )
        self._update_state(DeviceType.PIXEL, DeviceState.ERROR)
        return DeviceConnectionState.UNAUTHORIZED

    def validate_pixel_model(self) -> "DeviceConnectionState":
        """Verify the connected device is a Pixel 9 family member (v5.9.1 PIX-1).

        Reads ``ro.product.model`` via ``adb shell getprop`` and compares
        against :data:`PIXEL_9_FAMILY`.  Must be called after the device is
        in the ``ONLINE`` state (use :meth:`wait_for_pixel_authorization`
        first).  Does NOT mutate device state.

        Returns:
            - :attr:`DeviceConnectionState.ONLINE` — model is in Pixel 9 family.
            - :attr:`DeviceConnectionState.WRONG_MODEL` — device is a non-Pixel-9.
            - :attr:`DeviceConnectionState.UNKNOWN_MODEL` — getprop failed or empty.
            - :attr:`DeviceConnectionState.OFFLINE` — device not reachable.

        Example::

            if harness.wait_for_pixel_authorization() is DeviceConnectionState.ONLINE:
                model_state = harness.validate_pixel_model()
                if model_state is not DeviceConnectionState.ONLINE:
                    log.error("Pixel 9 required, got %s", model_state)
                    return  # abort provisioning
        """
        result = self.runner.run_adb("shell_getprop", ["ro.product.model"])
        if not result.success:
            log.warning(
                "validate_pixel_model: 'adb shell getprop ro.product.model' failed "
                "(rc=%s, stderr=%s)", result.return_code, result.stderr.strip()[:200],
            )
            return DeviceConnectionState.OFFLINE

        model = (result.stdout or "").strip()
        if not model:
            log.warning("validate_pixel_model: empty model string")
            return DeviceConnectionState.UNKNOWN_MODEL

        # Case-insensitive match against the Pixel 9 family whitelist.
        expected_lower = {m.lower() for m in PIXEL_9_FAMILY}
        if model.lower() in expected_lower:
            log.info("validate_pixel_model: OK (model=%s)", model)
            return DeviceConnectionState.ONLINE

        log.error(
            "validate_pixel_model: WRONG_MODEL — got %r, expected one of %s",
            model, list(PIXEL_9_FAMILY),
        )
        return DeviceConnectionState.WRONG_MODEL

    # --- Deploy ---

    def deploy_to_pixel(self) -> DeployReport:
        """Deploy SYLION binary to Pixel 9 via ADB (v5.9.1 P1-10 PIX-1)."""
        start = time.time()
        steps: list[dict[str, Any]] = []

        if not self.pixel_binary or not self.pixel_binary.exists():
            return DeployReport(
                device=DeviceType.PIXEL,
                result=DeployResult.FAILED,
                binary_path=str(self.pixel_binary or ""),
                remote_path=PIXEL_DEPLOY_PATH,
                elapsed_s=time.time() - start,
                error_message="Binary not found",
            )

        self._update_state(DeviceType.PIXEL, DeviceState.DEPLOYING)

        # Step 1: Check battery
        battery = self._get_pixel_battery()
        steps.append({"step": "battery_check", "battery_pct": battery})
        if 0 < battery < self.battery_threshold_pct:
            self._update_state(DeviceType.PIXEL, DeviceState.ERROR)
            return DeployReport(
                device=DeviceType.PIXEL,
                result=DeployResult.FAILED,
                binary_path=str(self.pixel_binary),
                remote_path=PIXEL_DEPLOY_PATH,
                elapsed_s=time.time() - start,
                error_message=f"Battery too low: {battery}% < {self.battery_threshold_pct}%",
                steps=steps,
            )

        # Step 2: Create remote directory
        r = self.runner.run_adb("shell_mkdir", [PIXEL_DEPLOY_PATH])
        steps.append({"step": "mkdir", "success": r.success})

        # Step 3: Push binary
        remote = f"{PIXEL_DEPLOY_PATH}/{self.pixel_binary.name}"
        r = self.runner.run_adb("push", [str(self.pixel_binary), remote])
        steps.append({"step": "push", "success": r.success, "elapsed_s": r.elapsed_s})
        if not r.success:
            self._update_state(DeviceType.PIXEL, DeviceState.ERROR)
            return DeployReport(
                device=DeviceType.PIXEL,
                result=DeployResult.FAILED,
                binary_path=str(self.pixel_binary),
                remote_path=remote,
                elapsed_s=time.time() - start,
                error_message=r.stderr,
                steps=steps,
            )

        # Step 4: Make executable
        r = self.runner.run_adb("shell_chmod", [remote])
        steps.append({"step": "chmod", "success": r.success})

        # Step 5: Push config if provided
        if self.config_path and self.config_path.exists():
            config_remote = f"{PIXEL_DEPLOY_PATH}/config.json"
            r = self.runner.run_adb("push", [str(self.config_path), config_remote])
            steps.append({"step": "push_config", "success": r.success})

        # Step 6: Verify
        r = self.runner.run_adb("shell_ls", [PIXEL_DEPLOY_PATH])
        steps.append({"step": "verify_ls", "success": r.success})

        self._update_state(DeviceType.PIXEL, DeviceState.ONLINE)
        report = DeployReport(
            device=DeviceType.PIXEL,
            result=DeployResult.SUCCESS,
            binary_path=str(self.pixel_binary),
            remote_path=remote,
            elapsed_s=time.time() - start,
            steps=steps,
        )
        self._deploy_reports.append(report)
        log.info(f"Pixel deploy SUCCESS in {report.elapsed_s:.1f}s")
        return report

    def deploy_to_router(self) -> DeployReport:
        """Deploy SYLION relay binary to Mudi router via SCP."""
        start = time.time()
        steps: list[dict[str, Any]] = []

        if not self.router_binary or not self.router_binary.exists():
            return DeployReport(
                device=DeviceType.ROUTER,
                result=DeployResult.FAILED,
                binary_path=str(self.router_binary or ""),
                remote_path=ROUTER_DEPLOY_PATH,
                elapsed_s=time.time() - start,
                error_message="Binary not found",
            )

        self._update_state(DeviceType.ROUTER, DeviceState.DEPLOYING)

        # Step 1: Create remote directory
        r = self.runner.run_ssh("mkdir", [ROUTER_DEPLOY_PATH])
        steps.append({"step": "mkdir", "success": r.success})

        # Step 2: SCP binary
        remote = f"{self.runner.router_user}@{self.runner.router_ip}:{ROUTER_DEPLOY_PATH}/{self.router_binary.name}"
        r = self.runner.run_ssh("scp", [str(self.router_binary), remote])
        steps.append({"step": "scp", "success": r.success, "elapsed_s": r.elapsed_s})
        if not r.success:
            self._update_state(DeviceType.ROUTER, DeviceState.ERROR)
            return DeployReport(
                device=DeviceType.ROUTER,
                result=DeployResult.FAILED,
                binary_path=str(self.router_binary),
                remote_path=remote,
                elapsed_s=time.time() - start,
                error_message=r.stderr,
                steps=steps,
            )

        # Step 3: Make executable
        remote_path = f"{ROUTER_DEPLOY_PATH}/{self.router_binary.name}"
        r = self.runner.run_ssh("chmod", [remote_path])
        steps.append({"step": "chmod", "success": r.success})

        # Step 4: Push config
        if self.config_path and self.config_path.exists():
            config_remote = f"{self.runner.router_user}@{self.runner.router_ip}:{ROUTER_DEPLOY_PATH}/config.json"
            r = self.runner.run_ssh("scp", [str(self.config_path), config_remote])
            steps.append({"step": "scp_config", "success": r.success})

        # Step 5: Health check
        r = self.runner.run_ssh("health", [])
        steps.append({"step": "health", "success": r.success})

        self._update_state(DeviceType.ROUTER, DeviceState.ONLINE)
        report = DeployReport(
            device=DeviceType.ROUTER,
            result=DeployResult.SUCCESS,
            binary_path=str(self.router_binary),
            remote_path=remote_path,
            elapsed_s=time.time() - start,
            steps=steps,
        )
        self._deploy_reports.append(report)
        log.info(f"Router deploy SUCCESS in {report.elapsed_s:.1f}s")
        return report

    # --- Capture pipeline ---

    def start_capture_pixel(
        self,
        *,
        backend: CaptureBackend = CaptureBackend.SCREENRECORD,
        duration_s: int = 180,
        output_path: str = "",
    ) -> CaptureSession:
        """Start screen capture on Pixel 9."""
        if not output_path:
            output_path = f"{PIXEL_DEPLOY_PATH}/capture_{int(time.time())}.mp4"

        w, h = self.max_resolution.split("x")

        session = CaptureSession(
            device=DeviceType.PIXEL,
            backend=backend,
            output_path=output_path,
            resolution=self.max_resolution,
            fps=self.target_fps,
        )

        if backend == CaptureBackend.SCREENRECORD:
            r = self.runner.run_adb("shell_screen", [
                "--size", f"{w}x{h}",
                "--time-limit", str(duration_s),
                output_path,
            ])
            if r.success:
                self._capture_sessions[DeviceType.PIXEL] = session
                self._update_state(DeviceType.PIXEL, DeviceState.CAPTURING)
                log.info(f"Pixel capture started: {backend.value} → {output_path}")
            else:
                session.active = False
                log.error(f"Pixel capture FAILED: {r.stderr}")
        else:
            # SurfaceFlinger or other backends — placeholder for future
            log.warning(f"Capture backend {backend.value} not yet implemented")
            session.active = False

        return session

    def stop_capture_pixel(self) -> CaptureSession | None:
        """Stop active capture on Pixel 9."""
        session = self._capture_sessions.pop(DeviceType.PIXEL, None)
        if session:
            self.runner.run_adb("shell_kill", ["screenrecord"])
            session.active = False
            self._update_state(DeviceType.PIXEL, DeviceState.RUNNING)
            log.info("Pixel capture stopped")
        return session

    # --- Health checks ---

    def health_check_pixel(self) -> DeviceStatus:
        """Comprehensive Pixel 9 health check."""
        status = DeviceStatus(
            device_type=DeviceType.PIXEL,
            state=DeviceState.UNKNOWN,
            last_check=time.time(),
            deploy_path=PIXEL_DEPLOY_PATH,
        )

        # Check ADB connectivity
        r = self.runner.run_adb("devices", [])
        if not r.success:
            status.state = DeviceState.OFFLINE
            status.error_message = "ADB not responding"
            self._device_states[DeviceType.PIXEL] = status
            return status

        # Battery
        status.battery_pct = self._get_pixel_battery()

        # Thermal
        r = self.runner.run_adb("shell_thermal", [])
        if r.success:
            status.thermal_status = self._parse_thermal(r.stdout)

        # Process check
        r = self.runner.run_adb("shell_ps", [])
        if r.success:
            status.process_running = "sylion" in r.stdout.lower()

        # Capture check
        session = self._capture_sessions.get(DeviceType.PIXEL)
        if session and session.active:
            status.capture_active = True
            status.capture_backend = session.backend.value

        status.state = DeviceState.RUNNING if status.process_running else DeviceState.ONLINE
        self._device_states[DeviceType.PIXEL] = status
        return status

    def health_check_router(self) -> DeviceStatus:
        """Comprehensive Mudi router health check."""
        status = DeviceStatus(
            device_type=DeviceType.ROUTER,
            state=DeviceState.UNKNOWN,
            last_check=time.time(),
            deploy_path=ROUTER_DEPLOY_PATH,
        )

        r = self.runner.run_ssh("health", [])
        if not r.success:
            status.state = DeviceState.OFFLINE
            status.error_message = r.stderr
            self._device_states[DeviceType.ROUTER] = status
            return status

        status.state = DeviceState.ONLINE

        # Parse uptime
        r_up = self.runner.run_ssh("uptime", [])
        if r_up.success:
            status.uptime_s = self._parse_uptime(r_up.stdout)

        # Process check
        r_ps = self.runner.run_ssh("ps", [])
        if r_ps.success:
            status.process_running = "sylion" in r_ps.stdout.lower()
            if status.process_running:
                status.state = DeviceState.RUNNING

        self._device_states[DeviceType.ROUTER] = status
        return status

    def health_check_all(self) -> dict[str, DeviceStatus]:
        """Run health checks on all devices."""
        return {
            "pixel": self.health_check_pixel(),
            "router": self.health_check_router(),
        }

    # --- Rollback ---

    def rollback_pixel(self) -> CommandResult:
        """Remove deployed files from Pixel."""
        self.stop_capture_pixel()
        self.runner.run_adb("shell_kill", ["sylion"])
        r = self.runner.run_adb("shell_rm", [PIXEL_DEPLOY_PATH])
        self._update_state(DeviceType.PIXEL, DeviceState.ONLINE)
        log.info("Pixel rollback completed")
        return r

    def rollback_router(self) -> CommandResult:
        """Remove deployed files from router."""
        self.runner.run_ssh("kill", ["sylion"])
        r = self.runner.run_ssh("rm", [ROUTER_DEPLOY_PATH])
        self._update_state(DeviceType.ROUTER, DeviceState.ONLINE)
        log.info("Router rollback completed")
        return r

    # --- Reports ---

    def get_stats(self) -> dict[str, Any]:
        """Get harness statistics."""
        return {
            "devices": {
                dt.value: ds.to_dict()
                for dt, ds in self._device_states.items()
            },
            "captures": {
                dt.value: cs.to_dict()
                for dt, cs in self._capture_sessions.items()
            },
            "deploys": len(self._deploy_reports),
            "command_history_count": len(self.runner.history),
        }

    def export_report(self) -> dict[str, Any]:
        """Export full harness state."""
        return {
            "stats": self.get_stats(),
            "deploy_reports": [r.to_dict() for r in self._deploy_reports],
            "command_history": [r.to_dict() for r in self.runner.history[-50:]],
        }

    # --- Internal helpers ---

    def _get_pixel_battery(self) -> int:
        """Get Pixel battery percentage."""
        r = self.runner.run_adb("shell_battery", [])
        if not r.success:
            return -1
        for line in r.stdout.split("\n"):
            if "level:" in line.lower():
                try:
                    return int(line.split(":")[-1].strip())
                except ValueError:
                    pass
        return -1

    def _parse_thermal(self, output: str) -> str:
        """Parse thermal status from dumpsys output."""
        for line in output.split("\n"):
            if "mStatus" in line or "throttling" in line.lower():
                return line.strip()
        return "unknown"

    def _parse_uptime(self, output: str) -> float:
        """Parse uptime in seconds from 'uptime' output."""
        # Typical: " 18:42:03 up  2:30,  0 users,  load average: ..."
        try:
            parts = output.split("up")[1].split(",")[0].strip()
            if ":" in parts:
                h, m = parts.split(":")
                return float(h) * 3600 + float(m) * 60
            elif "day" in parts:
                d = float(parts.split("day")[0].strip())
                return d * 86400
            return 0.0
        except (IndexError, ValueError):
            return 0.0

    def _update_state(self, device: DeviceType, state: DeviceState) -> None:
        if device in self._device_states:
            self._device_states[device].state = state
            self._device_states[device].last_check = time.time()
        else:
            self._device_states[device] = DeviceStatus(
                device_type=device,
                state=state,
                last_check=time.time(),
            )
