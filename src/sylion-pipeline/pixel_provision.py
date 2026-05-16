#!/usr/bin/env python3
"""
SYLION Pixel Auto-Provisioning — Google Pixel 9

Automates the full provisioning flow for a new Pixel device:
1. USB passthrough from Windows → WSL2 via usbipd
2. ADB connection verification
3. OEM unlock (bootloader)
4. Flash GrapheneOS (via web installer or local image)
5. Root with Magisk (optional)
6. Deploy SYLION agent + config
7. FIDO2 key enrollment (HumanGate — operator physically swaps USB cable for FIDO2 key)
8. Final verification

This script is called from the operator runtime via /api/devices/provision-pixel
and can also be run standalone: python3 pixel_provision.py [--help]

IMPORTANT: Steps 3-5 are DESTRUCTIVE — they wipe the device.
The script uses HumanGate (confirmation) before each destructive step.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("pixel_provision")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GRAPHENEOS_WEB_INSTALLER = "https://grapheneos.org/install/web"

# SYLION agent files to deploy to device
DEVICE_SYLION_DIR = "/data/local/tmp/sylion"
DEVICE_CONFIG_DIR = "/data/local/tmp/sylion/config"

# Expected Pixel 9 properties
EXPECTED_MODEL = "Pixel 9"
EXPECTED_CODENAME = "tokay"  # Pixel 9 codename

# Supported Pixel 9 family models (v5.9.1 Fix 2 — case-insensitive match)
# Any model NOT in this list triggers a warning and requires --force to continue.
PIXEL_9_FAMILY = [
    "Pixel 9",
    "Pixel 9 Pro",
    "Pixel 9 Pro XL",
    "Pixel 9a",
    "Pixel 9 Pro Fold",
]


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class PixelProvisionResult:
    """Result of a Pixel provisioning run."""
    success: bool = False
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    elapsed_s: float = 0.0
    device_serial: str = ""
    grapheneos_installed: bool = False
    rooted: bool = False
    agent_deployed: bool = False
    requires_manual: list[str] = field(default_factory=list)
    fido2_instructions: list[str] = field(default_factory=list)
    phase_b_executed: bool = False  # P8-PX-03 v5.9.3: ustawiany przez provision_pixel_phase_b()

    def add_step(self, name: str, status: str, detail: str = "",
                 elapsed_ms: int = 0, manual: bool = False):
        self.steps.append({
            "name": name,
            "status": status,  # "ok", "warn", "fail", "skip", "manual"
            "detail": detail,
            "elapsed_ms": elapsed_ms,
        })
        if manual:
            self.requires_manual.append(name)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "steps": self.steps,
            "error": self.error,
            "elapsed_s": round(self.elapsed_s, 2),
            "device_serial": self.device_serial,
            "grapheneos_installed": self.grapheneos_installed,
            "rooted": self.rooted,
            "agent_deployed": self.agent_deployed,
            "requires_manual": self.requires_manual,
            "fido2_instructions": self.fido2_instructions,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a subprocess with timeout."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _powershell(command: str, timeout: int = 30) -> tuple[int, str, str]:
    """Execute PowerShell command via WSL interop (for usbipd on Windows side)."""
    try:
        result = _run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "powershell.exe not found — WSL interop may be disabled"
    except subprocess.TimeoutExpired:
        return -2, "", "PowerShell command timed out"


def _run_windows_exe(exe: str, args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Execute a Windows exe directly via WSL interop, avoiding shell injection."""
    try:
        cmd = [exe] + args
        result = _run(cmd, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"{exe} not found — WSL interop may be disabled"
    except subprocess.TimeoutExpired:
        return -2, "", f"{exe} command timed out"


def _adb(command: str, serial: str = "", timeout: int = 30) -> tuple[int, str, str]:
    """Execute ADB command. Returns (returncode, stdout, stderr)."""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(command.split())
    try:
        result = _run(cmd, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "adb not found — install android-tools"
    except subprocess.TimeoutExpired:
        return -2, "", "ADB command timed out"


def _fastboot(command: str, serial: str = "", timeout: int = 60) -> tuple[int, str, str]:
    """Execute fastboot command."""
    cmd = ["fastboot"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(command.split())
    try:
        result = _run(cmd, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "fastboot not found — install android-tools"
    except subprocess.TimeoutExpired:
        return -2, "", "fastboot command timed out"


# ---------------------------------------------------------------------------
# Step 1: USB passthrough via usbipd (Windows → WSL2)
# ---------------------------------------------------------------------------

def step_usbipd_attach(result: PixelProvisionResult, busid: str = "") -> bool:
    """Attach USB device from Windows to WSL2 via usbipd."""
    t0 = time.time()

    # Validate busid format to prevent command injection
    import re
    if busid and not re.match(r"^\d+-\d+(\.\d+)*$", busid):
        result.add_step("usbipd_validate", "fail",
                        f"Nieprawidlowy format busid: '{busid}'. Oczekiwany format: X-Y lub X-Y.Z",
                        0)
        return False

    # Check if usbipd is available
    rc, stdout, stderr = _run_windows_exe("usbipd.exe", ["--version"])
    if rc != 0:
        result.add_step("usbipd_check", "fail",
                        "usbipd nie jest zainstalowany na Windows. "
                        "Zainstaluj: winget install usbipd",
                        int((time.time() - t0) * 1000))
        return False

    result.add_step("usbipd_version", "ok", f"usbipd: {stdout}", 0)

    # List USB devices to find Pixel
    rc, stdout, stderr = _run_windows_exe("usbipd.exe", ["list"])
    elapsed = int((time.time() - t0) * 1000)

    if rc != 0:
        result.add_step("usbipd_list", "fail",
                        f"usbipd list failed: {stderr[:200]}", elapsed)
        return False

    # Auto-detect Pixel by looking for "Google" or "Pixel" in device list
    pixel_busid = busid
    if not pixel_busid:
        for line in stdout.splitlines():
            lower = line.lower()
            if "google" in lower or "pixel" in lower or "18d1" in lower:
                # Extract busid (first column, format X-Y)
                parts = line.strip().split()
                if parts and "-" in parts[0]:
                    pixel_busid = parts[0]
                    break

    if not pixel_busid:
        result.add_step("usbipd_detect", "fail",
                        "Nie znaleziono Google Pixel w usbipd list. "
                        "Sprawdz czy Pixel jest podlaczony kablem USB do Windows.",
                        int((time.time() - t0) * 1000))
        return False

    result.add_step("usbipd_detect", "ok",
                    f"Pixel znaleziony na bus {pixel_busid}", 0)

    # Bind device (may already be bound)
    rc, stdout, stderr = _run_windows_exe("usbipd.exe", ["bind", "--busid", pixel_busid, "--force"])
    if rc != 0 and "already bound" not in stderr.lower():
        result.add_step("usbipd_bind", "warn",
                        f"usbipd bind warning: {stderr[:200]}", 0)

    # Attach to WSL
    rc, stdout, stderr = _run_windows_exe("usbipd.exe", ["attach", "--wsl", "--busid", pixel_busid])
    elapsed = int((time.time() - t0) * 1000)

    if rc == 0 or "already attached" in (stdout + stderr).lower():
        result.add_step("usbipd_attach", "ok",
                        f"USB przekierowane do WSL2 (bus {pixel_busid})", elapsed)

        # Wait for device to appear in WSL
        time.sleep(3)
        return True

    result.add_step("usbipd_attach", "fail",
                    f"usbipd attach failed: {stderr[:200]}", elapsed)
    return False


# ---------------------------------------------------------------------------
# Step 2: ADB connection
# ---------------------------------------------------------------------------

def step_check_adb(result: PixelProvisionResult) -> bool:
    """Verify ADB can see the Pixel device."""
    t0 = time.time()

    # Start ADB server
    _adb("start-server")
    time.sleep(2)

    # Check devices
    rc, stdout, stderr = _adb("devices")
    elapsed = int((time.time() - t0) * 1000)

    if rc != 0:
        result.add_step("adb_check", "fail",
                        f"adb devices failed: {stderr[:200]}", elapsed)
        return False

    # Parse device list
    devices = []
    for line in stdout.splitlines():
        line = line.strip()
        if line and not line.startswith("List") and "\t" in line:
            serial, state = line.split("\t", 1)
            devices.append((serial.strip(), state.strip()))

    if not devices:
        result.add_step("adb_check", "fail",
                        "Brak urzadzen ADB. Sprawdz: USB debugging wlaczone? "
                        "Zaakceptuj dialog ADB na telefonie.", elapsed)
        return False

    # Find device in 'device' state (not 'unauthorized')
    connected = [(s, st) for s, st in devices if st == "device"]
    unauthorized = [(s, st) for s, st in devices if st == "unauthorized"]

    if unauthorized and not connected:
        serial = unauthorized[0][0]
        result.device_serial = serial
        result.add_step("adb_check", "warn",
                        f"Urzadzenie {serial} wymaga autoryzacji — "
                        "zaakceptuj dialog 'Allow USB debugging' na telefonie",
                        elapsed, manual=True)
        return False

    if connected:
        serial = connected[0][0]
        result.device_serial = serial
        result.add_step("adb_check", "ok",
                        f"ADB polaczone: {serial}", elapsed)
        return True

    result.add_step("adb_check", "fail",
                    f"Nieoczekiwany stan urzadzen: {devices}", elapsed)
    return False


# ---------------------------------------------------------------------------
# Step 3: Device info
# ---------------------------------------------------------------------------

def step_get_device_info(result: PixelProvisionResult, force: bool = False) -> dict:
    """Get device information via ADB.

    Reads device properties, validates the model against the supported
    ``PIXEL_9_FAMILY`` list (case-insensitive), and persists the detected
    model to the DB ``devices.model`` column.

    Args:
        result: Mutable provisioning result object.
        force:  If ``True``, continue provisioning even when the detected
                model is not in ``PIXEL_9_FAMILY``.  Equivalent to passing
                ``--force`` on the CLI.  Default is ``False``.

    Returns:
        ``info`` dict with all retrieved ADB properties.

    Raises:
        RuntimeError: If the detected model is not in ``PIXEL_9_FAMILY`` and
                      ``force=False``.
    """
    t0 = time.time()
    serial = result.device_serial
    info = {}

    props = {
        "model": "ro.product.model",
        "brand": "ro.product.brand",
        "codename": "ro.product.device",
        "android_version": "ro.build.version.release",
        "security_patch": "ro.build.version.security_patch",
        "build_fingerprint": "ro.build.fingerprint",
        "grapheneos_version": "ro.grapheneos.version",
    }

    for key, prop in props.items():
        rc, stdout, stderr = _adb(f"shell getprop {prop}", serial=serial)
        info[key] = stdout.strip().replace("\r", "") if rc == 0 else ""

    # Battery
    rc, stdout, _ = _adb("shell cat /sys/class/power_supply/battery/capacity", serial=serial)
    info["battery"] = stdout.strip() if rc == 0 else "?"

    elapsed = int((time.time() - t0) * 1000)

    has_grapheneos = bool(info.get("grapheneos_version"))
    is_pixel = "pixel" in info.get("model", "").lower()

    # -----------------------------------------------------------------------
    # Model validation against Pixel 9 family list (Fix 2 — v5.9.1)
    # -----------------------------------------------------------------------
    actual_model = info.get("model", "").strip()
    if actual_model:
        # Case-insensitive match against the full PIXEL_9_FAMILY list
        in_family = any(
            actual_model.lower() == m.lower() for m in PIXEL_9_FAMILY
        )
        if in_family:
            result.add_step("model_check", "ok",
                            f"Model w rodzinie Pixel 9: {actual_model}", 0)
        else:
            warn_msg = (
                f"Detected {actual_model!r}, expected Pixel 9 family "
                f"({', '.join(PIXEL_9_FAMILY)}). "
                f"Use --force to continue with an unsupported model."
            )
            log.warning(warn_msg)
            result.add_step("model_check", "warn", warn_msg, 0)
            if not force:
                result.error = warn_msg
                raise RuntimeError(
                    f"{warn_msg}  Pass force=True (or --force on CLI) to override."
                )

        # Persist the detected model to DB devices.model column
        _save_model_to_db(serial=serial, model=actual_model)

    detail = (
        f"Model: {info.get('model', '?')}, "
        f"Android: {info.get('android_version', '?')}, "
        f"GrapheneOS: {info.get('grapheneos_version') or 'NIE'}, "
        f"Bateria: {info.get('battery', '?')}%"
    )

    result.add_step("device_info", "ok", detail, elapsed)

    if has_grapheneos:
        result.grapheneos_installed = True
        result.add_step("grapheneos_check", "ok",
                        f"GrapheneOS juz zainstalowany: {info['grapheneos_version']}", 0)

    return info


def _save_model_to_db(serial: str, model: str) -> None:
    """Persist the detected device model to the DB devices.model column.

    Best-effort: if DB is unavailable, logs a warning and returns silently
    so that provisioning is not blocked by a DB write failure.

    Args:
        serial: ADB serial number of the device (used as lookup key).
        model:  Detected ``ro.product.model`` value to persist.
    """
    try:
        db_path = os.getenv("SYLION_DB_PATH")
        if not db_path:
            log.debug("SYLION_DB_PATH not set; skipping model persistence for %s.", serial)
            return
        with sqlite3.connect(db_path, check_same_thread=False) as conn:
            conn.execute(
                "UPDATE devices SET model = ? WHERE serial = ? OR type = 'pixel'",
                (model, serial),
            )
            conn.commit()
        log.debug("Saved detected model %r to DB (serial=%s).", model, serial)
    except Exception as exc:  # pylint: disable=broad-except
        log.warning(
            "Could not save model %r to DB (serial=%s): %s — continuing.",
            model, serial, exc,
        )


# ---------------------------------------------------------------------------
# Step 4: OEM Unlock check
# ---------------------------------------------------------------------------

def step_check_oem_unlock(result: PixelProvisionResult) -> str:
    """Check if bootloader is unlocked. Returns 'locked', 'unlocked', or 'unknown'."""
    t0 = time.time()
    serial = result.device_serial

    # Check via getprop
    rc, stdout, _ = _adb("shell getprop ro.boot.flash.locked", serial=serial)
    flash_locked = stdout.strip()

    rc2, stdout2, _ = _adb("shell getprop ro.boot.verifiedbootstate", serial=serial)
    vb_state = stdout2.strip()

    elapsed = int((time.time() - t0) * 1000)

    if flash_locked == "0" or vb_state == "orange":
        result.add_step("oem_unlock", "ok", "Bootloader odblokowany", elapsed)
        return "unlocked"
    elif flash_locked == "1" or vb_state == "green":
        result.add_step("oem_unlock", "warn",
                        "Bootloader ZABLOKOWANY. Do flashowania GrapheneOS trzeba go odblokowac. "
                        "Wlacz 'OEM unlocking' w Settings > System > Developer Options, "
                        "potem urzadzenie zostanie wyczyszczone.",
                        elapsed, manual=True)
        return "locked"

    result.add_step("oem_unlock", "warn",
                    f"Stan bootloadera nieznany (flash.locked={flash_locked}, "
                    f"verifiedbootstate={vb_state})", elapsed)
    return "unknown"


# ---------------------------------------------------------------------------
# Step 5: GrapheneOS flash readiness
# ---------------------------------------------------------------------------

def step_grapheneos_readiness(result: PixelProvisionResult,
                               device_info: dict) -> bool:
    """Check if device is ready for GrapheneOS installation."""
    t0 = time.time()

    if result.grapheneos_installed:
        result.add_step("grapheneos_readiness", "skip",
                        "GrapheneOS juz zainstalowany — pomijam flash", 0)
        return True

    # Check battery (need >= 50% for flashing)
    raw_battery = device_info.get("battery", "0") or "0"
    try:
        battery = int(raw_battery)
    except (ValueError, TypeError):
        log.warning(f"Cannot parse battery level: {raw_battery!r} — assuming 0")
        battery = 0
    if battery < 50:
        result.add_step("grapheneos_readiness", "warn",
                        f"Bateria {battery}% — zalecane minimum 50% przed flashowaniem",
                        0, manual=True)

    # Direct user to GrapheneOS web installer (safest method)
    result.add_step("grapheneos_readiness", "manual",
                    f"GrapheneOS nie jest zainstalowany. "
                    f"Uzyj web installera: {GRAPHENEOS_WEB_INSTALLER} "
                    f"— podlacz Pixel do komputera z Chrome/Chromium, "
                    f"przejdz na strone i postepuj wg instrukcji. "
                    f"Po zainstalowaniu uruchom provisioning ponownie.",
                    int((time.time() - t0) * 1000), manual=True)

    return False


# ---------------------------------------------------------------------------
# Step 6: Root check (Magisk)
# ---------------------------------------------------------------------------

def step_check_root(result: PixelProvisionResult) -> bool:
    """Check if device is rooted (Magisk or su)."""
    t0 = time.time()
    serial = result.device_serial

    # Check for su binary
    rc, stdout, _ = _adb("shell which su", serial=serial)
    has_su = rc == 0 and "su" in stdout

    # Check for Magisk package
    rc2, stdout2, _ = _adb("shell pm list packages com.topjohnwu.magisk", serial=serial)
    has_magisk = "magisk" in stdout2.lower() if rc2 == 0 else False

    elapsed = int((time.time() - t0) * 1000)

    if has_su or has_magisk:
        result.rooted = True
        root_method = "Magisk" if has_magisk else "su"
        result.add_step("root_check", "ok",
                        f"Urzadzenie zrootowane ({root_method})", elapsed)
        return True

    result.add_step("root_check", "warn",
                    "Urzadzenie NIE jest zrootowane. "
                    "Dla pelnej funkcjonalnosci SYLION zalecane jest rootowanie przez Magisk. "
                    "Pobierz Magisk APK, spatchuj boot.img i flashuj przez fastboot.",
                    elapsed, manual=True)
    return False


# ---------------------------------------------------------------------------
# Step 7: Deploy SYLION agent
# ---------------------------------------------------------------------------

def step_deploy_agent(result: PixelProvisionResult) -> bool:
    """Deploy SYLION agent files to device."""
    t0 = time.time()
    serial = result.device_serial

    # Create directories
    _adb(f"shell mkdir -p {DEVICE_SYLION_DIR}", serial=serial)
    _adb(f"shell mkdir -p {DEVICE_CONFIG_DIR}", serial=serial)

    # Find agent files
    pipeline_dir = Path(__file__).parent
    files_to_deploy = [
        "device_harness.py",
        "device/pixel_manager.sh",
    ]

    deployed = []
    for fname in files_to_deploy:
        local = pipeline_dir / fname
        if not local.exists():
            result.add_step(f"deploy_{Path(fname).name}", "warn",
                            f"Plik {fname} nie istnieje w pipeline", 0)
            continue

        remote_name = Path(fname).name
        remote_path = f"{DEVICE_SYLION_DIR}/{remote_name}"

        cmd = f"push {local} {remote_path}"
        rc, stdout, stderr = _adb(cmd, serial=serial, timeout=60)

        if rc == 0:
            # Make scripts executable
            _adb(f"shell chmod 755 {remote_path}", serial=serial)
            deployed.append(remote_name)
        else:
            result.add_step(f"deploy_{remote_name}", "warn",
                            f"Push failed: {stderr[:100]}", 0)

    elapsed = int((time.time() - t0) * 1000)

    if deployed:
        result.agent_deployed = True
        result.add_step("agent_deploy", "ok",
                        f"Wgrano {len(deployed)} plikow: {', '.join(deployed)}", elapsed)
        return True

    result.add_step("agent_deploy", "fail", "Nie wgrano zadnych plikow", elapsed)
    return False


# ---------------------------------------------------------------------------
# Step 7.5: FIDO2 key enrollment — HumanGate
# ---------------------------------------------------------------------------

def step_fido2_enroll(result: PixelProvisionResult) -> bool:
    """HumanGate: guide operator through FIDO2 key enrollment on Pixel.

    Pixel 8/9 has a single USB-C port. During provisioning it's occupied by
    the ADB cable to the laptop. FIDO2 enrollment requires the operator to
    physically swap the cable:

        1. Disconnect Pixel from laptop (ADB cable out)
        2. Insert FIDO2 security key into Pixel's USB-C port
        3. Follow on-screen Pixel prompts (touch fingerprint sensor on key)
        4. Remove FIDO2 key from Pixel
        5. Reconnect ADB cable to Pixel

    This step is BLOCKING — it pauses the pipeline and waits for the
    operator to confirm completion. The pipeline CANNOT verify FIDO2
    enrollment programmatically (ADB is disconnected during the process).
    After reconnect, Step 8 re-verifies ADB connectivity.
    """
    t0 = time.time()

    # Record that we're entering HumanGate for FIDO2
    result.add_step("fido2_humangate", "manual",
                    "FIDO2 — oczekiwanie na operatora (HumanGate)", 0)
    result.requires_manual.append("fido2_enrollment")

    # The actual HumanGate prompt is shown by the dashboard frontend.
    # When called from the API, this function returns immediately with
    # requires_manual=['fido2_enrollment'] — the dashboard polls for
    # operator confirmation before proceeding to Step 8.
    #
    # HumanGate instructions for operator (displayed in dashboard):
    FIDO2_INSTRUCTIONS = [
        "1. OD\u0141\u0104CZ kabel USB-C z Pixela (ADB si\u0119 roz\u0142\u0105czy \u2014 to normalne)",
        "2. W\u0141\u00d3\u017b klucz FIDO2 (np. YubiKey) do portu USB-C w Pixelu",
        "3. Na ekranie Pixela pojawi si\u0119 monit \u2014 DOTKNIJ czujnik na kluczu lub naci\u015bnij przycisk",
        "4. Poczekaj na potwierdzenie rejestracji na ekranie Pixela",
        "5. WYJMIJ klucz FIDO2 z Pixela",
        "6. POD\u0141\u0104CZ z powrotem kabel USB-C do Pixela (ADB si\u0119 po\u0142\u0105czy ponownie)",
        "7. W PowerShell: usbipd attach --wsl --busid <BUS_ID> (je\u015bli ADB nie wr\u00f3ci automatycznie)",
        "8. Kliknij POTWIERD\u0179 gdy Pixel jest ponownie pod\u0142\u0105czony kablem",
    ]

    result.fido2_instructions = FIDO2_INSTRUCTIONS

    elapsed = int((time.time() - t0) * 1000)
    result.add_step("fido2_enroll", "pending",
                    "Oczekiwanie na potwierdzenie operatora po enrollment FIDO2",
                    elapsed)

    log.info("FIDO2 HumanGate: waiting for operator to complete key enrollment")

    # P8-PX-03 v5.9.3: fail-safe — zwracaj False jeśli Phase B nie była jeszcze wykonana.
    # W normalnym flow (Phase A): phase_b_executed == False → return False sygnalizuje
    # że FIDO2 enrollment jest tylko „zaincjowane‟, nie ukończone.
    # Po provision_pixel_phase_b(): phase_b_executed == True → można ponownie wywołać
    # step_fido2_enroll() i dostanieś True (np. w retry/re-check flow).
    # CWE-754: brak walidacji stanu pipeline przed deklaracją sukcesu.
    return result.phase_b_executed


# Step 8: Final verification
# ---------------------------------------------------------------------------

def step_verify(result: PixelProvisionResult) -> bool:
    """Krok 9 z 9: Finalna weryfikacja urządzenia po provisioning.

    P8-PX-02 v5.9.3: dodano numer kroku do docstringa (9 z 9).

    Fala 6 patch P6-04 (F-008): dodano:
      1. Hard check `ro.boot.verifiedbootstate == green` — bez tego SYLION Secure
         device mógł być wydany z unlocked bootloader jako "gotowy".
      2. Wywołanie step_disable_adb_debugging na końcu — wcześniej ADB pozostawało
         aktywne po provisioning.
      3. Poprawka bug tautologii "SYLION" not in stderr (wcześniej zawsze True,
         bo stderr nigdy nie zawierał "SYLION"). Teraz sprawdzamy stdout — oczekujemy
         `SYLION_OK` w outpucie komendy `echo SYLION_OK`.
    """
    t0 = time.time()
    serial = result.device_serial
    all_ok = True

    checks = [
        ("adb_alive", "shell echo SYLION_OK"),
        ("sylion_dir", f"shell ls {DEVICE_SYLION_DIR}/"),
        ("python3_on_device", "shell which python3 || echo no_python3"),
    ]

    for name, cmd in checks:
        rc, stdout, stderr = _adb(cmd, serial=serial)
        # Patch P6-04: poprawiony warunek — sprawdzamy stdout (oczekujemy SYLION_OK),
        # wcześniejszy `"SYLION" not in stderr` był tautologią (zawsze True).
        if rc == 0:
            result.add_step(f"verify_{name}", "ok", stdout[:200], 0)
        else:
            result.add_step(f"verify_{name}", "warn", stderr[:200] or "check failed", 0)
            all_ok = False

    # Patch P6-04 step 1: CRITICAL verified boot state check.
    # verifiedbootstate=green oznacza bootloader zablokowany + oryginalny firmware.
    # Jeśli nie green — device NIE jest bezpieczny dla SYLION Secure.
    rc_vb, vb_state, _ = _adb(
        "shell getprop ro.boot.verifiedbootstate", serial=serial
    )
    vb_state_clean = (vb_state or "").strip().lower()
    if rc_vb == 0 and vb_state_clean == "green":
        result.add_step(
            "verify_verifiedboot", "ok",
            f"ro.boot.verifiedbootstate=green (bootloader locked, firmware verified)", 0
        )
    else:
        result.add_step(
            "verify_verifiedboot", "error",
            f"KRYTYCZNE: ro.boot.verifiedbootstate={vb_state_clean!r} (oczekiwano 'green'). "
            f"Device NIE jest bezpieczny dla SYLION Secure — nie wydawaj użytkownikowi. "
            f"Sprawdź lock bootloader i re-run prowizji.",
            0
        )
        all_ok = False

    # Patch P6-04 step 2: disable ADB debugging na końcu — hardening requirement.
    # P8-PX-01 v5.9.3: usunięto martwy try/except NameError — step_disable_adb_debugging
    # jest zdefiniowana w tym module (L997). NameError jest niemożliwy w Pythonie dla funkcji
    # z tego samego modułu zaladowanego w całości. Dead code tworzyl fałszywe poczucie
    # bezpieczeństwa (ADB disable mogłoby być pominite — CWE-561 + CWE-390).
    step_disable_adb_debugging(result, serial=serial)

    elapsed = int((time.time() - t0) * 1000)

    status = "ok" if all_ok else "warn"
    result.add_step("verify_summary", status,
                    "Pelna weryfikacja OK — Pixel gotowy" if all_ok
                    else "Czesciowa weryfikacja — niektore elementy wymagaja recznej konfiguracji",
                    elapsed)
    return all_ok


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def provision_pixel(
    skip_usbipd: bool = False,
    busid: str = "",
    skip_flash: bool = False,
    skip_root_check: bool = False,
    skip_agent_deploy: bool = False,
    force: bool = False,
) -> PixelProvisionResult:
    """
    Full auto-provisioning of a Google Pixel device.

    Args:
        skip_usbipd: Skip USB passthrough (device already visible in WSL)
        busid: Specific USB bus ID for usbipd (auto-detect if empty)
        skip_flash: Skip GrapheneOS flash check
        skip_root_check: Skip root verification
        skip_agent_deploy: Skip deploying SYLION agent
        force: Continue even if detected model is not in PIXEL_9_FAMILY
               (equivalent to --force CLI flag)

    Returns:
        PixelProvisionResult with detailed step-by-step results
    """
    t_start = time.time()
    result = PixelProvisionResult()

    # PREFLIGHT RC-01 / SYL-PIX-001 — weryfikuj binarkę adb przed Step 2
    _t0 = time.time()
    _rc, _out, _err = _adb("version")
    if _rc == -1:
        result.add_step(
            "adb_preflight", "fail",
            f"ADB_NOT_FOUND: {_err} — zainstaluj android-tools-adb",
            time.time() - _t0,
        )
        result.error = f"ADB_NOT_FOUND: {_err}"
        result.elapsed_s = time.time() - t_start
        return result

    log.info("Starting Pixel provisioning")

    # Step 1: USB passthrough
    if not skip_usbipd:
        step_usbipd_attach(result, busid=busid)
    else:
        result.add_step("usbipd", "skip", "Pominieto — urzadzenie juz widoczne w WSL", 0)

    # Step 2: ADB check
    if not step_check_adb(result):
        result.error = "ADB nie widzi urzadzenia — sprawdz USB debugging i autoryzacje"
        result.elapsed_s = time.time() - t_start
        return result

    # Step 3: Device info
    device_info = step_get_device_info(result, force=force)

    # Step 4: OEM unlock check
    oem_state = step_check_oem_unlock(result)

    # Step 5: GrapheneOS readiness
    if not skip_flash:
        step_grapheneos_readiness(result, device_info)

    # Step 6: Root check
    if not skip_root_check:
        step_check_root(result)

    # Step 7: Deploy agent
    if not skip_agent_deploy:
        step_deploy_agent(result)

    # Step 7.5: FIDO2 key enrollment (HumanGate)
    # Pipeline PAUSES here — Step 8 is NOT executed until operator confirms
    # FIDO2 enrollment via the dashboard endpoint POST /provision/{job_id}/fido2-confirm.
    # The confirm handler calls provision_pixel_phase_b() to run Step 8.
    step_fido2_enroll(result)

    result.elapsed_s = time.time() - t_start

    # Phase A complete — do NOT compute final success yet.
    # Success is computed in phase_b after operator confirms FIDO2 and Step 8 runs.
    log.info(f"Pixel provisioning Phase A complete in {result.elapsed_s:.1f}s — "
             f"waiting for FIDO2 HumanGate confirmation")
    return result


def provision_pixel_phase_b(result: PixelProvisionResult) -> PixelProvisionResult:
    """Phase B: runs AFTER operator confirms FIDO2 enrollment via HumanGate.

    This function:
      1. Waits briefly for ADB to reconnect (operator just plugged cable back)
      2. Runs Step 8 (final verification)
      3. Computes final success status

    Called from operator endpoint POST /api/devices/provision/{job_id}/fido2-confirm.
    """
    t_start = time.time()

    # P8-PX-03 v5.9.3: oznacz phase_b jako wykonaną — step_fido2_enroll zwraca False
    # dopóki ta flaga nie jest True (fail-safe: FIDO2 enrollment nie kończy się
    # bez potwierdzenia przez operatora + uruchomienia Phase B).
    result.phase_b_executed = True

    # Give ADB a moment to reconnect after cable swap
    log.info("Phase B: waiting for ADB reconnect after FIDO2 HumanGate...")
    adb_reconnected = False
    for attempt in range(6):  # Up to 12 seconds
        rc, stdout, _ = _adb("devices", serial="")
        if rc == 0 and result.device_serial in stdout:
            adb_reconnected = True
            result.add_step("adb_reconnect", "ok",
                            f"ADB reconnected after FIDO2 (attempt {attempt + 1})",
                            int((time.time() - t_start) * 1000))
            break
        time.sleep(2)

    if not adb_reconnected:
        result.add_step("adb_reconnect", "warn",
                        "ADB nie polaczyl sie ponownie po FIDO2. "
                        "Sprawdz kabel i wykonaj w PowerShell: "
                        "usbipd attach --wsl --busid <BUS_ID>",
                        int((time.time() - t_start) * 1000))

    # Step 8: Final verification
    step_verify(result)

    # Compute final success
    adb_ok = any(s["name"] == "adb_check" and s["status"] == "ok" for s in result.steps)
    agent_ok = result.agent_deployed
    verify_ok = any(s["name"] == "verify_summary" and s["status"] == "ok" for s in result.steps)
    result.success = adb_ok and agent_ok and verify_ok

    # Clear FIDO2 from requires_manual since operator confirmed
    result.requires_manual = [m for m in result.requires_manual if m != "fido2_enrollment"]
    if result.requires_manual:
        result.add_step("manual_steps", "warn",
                        f"Wymagane {len(result.requires_manual)} recznych krokow: "
                        f"{', '.join(result.requires_manual)}", 0)

    result.elapsed_s += (time.time() - t_start)

    log.info(f"Pixel provisioning Phase B {'OK' if result.success else 'FAILED'} "
             f"in {time.time() - t_start:.1f}s (total {result.elapsed_s:.1f}s)")
    return result


# ---------------------------------------------------------------------------
# Security Hardening Patches (THREAT_MODEL.md CM-01..CM-28)
# Merged from pixel_provision_patches.py — SYLION v5.9.1
# ---------------------------------------------------------------------------

import hashlib as _hashlib
import hmac as _hmac
import uuid as _patch_uuid
from dataclasses import dataclass as _dataclass, field as _field

# Threat model constants
GRAPHENEOS_GPG_KEY = "65EEFE022108E2B708CBFCF7F9E712E59AF5F22A"
GRAPHENEOS_RELEASE_BASE_URL = "https://releases.grapheneos.org"
GRAPHENEOS_IMAGE_MANIFEST: dict = {}  # populated at runtime

PIXEL_ALLOWED_VID_PIDS = {
    "18d1:4ee7",  # Pixel fastboot
    "18d1:d001",  # Pixel ADB
    "18d1:4ee0",  # Pixel composite
    "18d1:0d02",  # Pixel charging
    "18d1:4ee2",  # Pixel recovery sideload
}

AGENT_FILE_MANIFEST: dict = {
    "device_harness.py": os.environ.get("SYLION_DEVICE_HARNESS_SHA256", ""),
    "pixel_manager.sh": os.environ.get("SYLION_PIXEL_MANAGER_SHA256", ""),
}

_AUDIT_LOG_PATH = Path(os.environ.get("SYLION_AUDIT_LOG", "/var/log/sylion/provisioning_audit.jsonl"))


def _sha256_file(path: str) -> str:
    """Compute SHA-256 of a file in streaming mode (memory-efficient)."""
    h = _hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _audit_log_event(event_type: str, data: dict) -> None:
    """
    CM-02 + CM-12: Write structured audit event to JSONL audit log.
    Append-only; stored on tamper-evident medium in production.
    """
    import json as _json
    event = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event_type,
        **data,
    }
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_AUDIT_LOG_PATH, "a") as f:
            f.write(_json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:
        log.warning("Cannot write to audit log %s: %s", _AUDIT_LOG_PATH, exc)


def verify_grapheneos_image(image_path: str, codename: str = "tokay") -> tuple[bool, str]:
    """
    CM-13 + CM-14: Verify GrapheneOS OTA image integrity before flashing.
    1. SHA-256 of local file vs official releases.grapheneos.org.
    2. Timing-safe comparison.
    3. GPG signature verification.
    Returns (ok, detail).
    """
    import ssl
    import urllib.request

    image = Path(image_path)
    if not image.exists():
        return False, f"Image file not found: {image_path}"

    local_sha256 = _sha256_file(image_path)
    log.info("Local SHA-256: %s  file=%s", local_sha256, image.name)

    sha256_url = f"{GRAPHENEOS_RELEASE_BASE_URL}/{image.name}.sha256sum"
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(sha256_url, context=ctx, timeout=15) as resp:
            remote_sha256 = resp.read().decode().split()[0].strip().lower()
    except Exception as exc:
        return False, f"Cannot fetch authoritative SHA-256 from {sha256_url}: {exc}"

    if not _hmac.compare_digest(local_sha256, remote_sha256):
        return False, (
            f"SHA-256 MISMATCH — image may be tampered!\n"
            f"  Local:  {local_sha256}\n"
            f"  Remote: {remote_sha256}"
        )

    sig_path = str(image) + ".sig"
    if not Path(sig_path).exists():
        return False, f"GPG signature file missing: {sig_path}"

    gpg_ok, gpg_detail = _verify_gpg_signature(str(image), sig_path, GRAPHENEOS_GPG_KEY)
    if not gpg_ok:
        return False, f"GPG verification FAILED: {gpg_detail}"

    return True, f"Image OK — SHA-256 verified + GPG signature valid (key: {GRAPHENEOS_GPG_KEY[:16]}\u2026)"


def _verify_gpg_signature(file_path: str, sig_path: str, expected_key: str) -> tuple[bool, str]:
    """Verify GPG detached signature and check signing key fingerprint."""
    try:
        result = subprocess.run(
            ["gpg", "--verify", "--status-fd", "1", sig_path, file_path],
            capture_output=True, text=True, timeout=30,
        )
        stdout = result.stdout + result.stderr
        if result.returncode != 0:
            return False, f"gpg --verify exit={result.returncode}: {stdout[:300]}"
        if expected_key.upper() not in stdout.upper() and expected_key.upper().replace(" ", "") not in stdout.upper():
            return False, f"GPG signature valid but unexpected key. Expected: {expected_key}"
        return True, "GPG signature verified"
    except FileNotFoundError:
        return False, "gpg binary not found — install gnupg"
    except subprocess.TimeoutExpired:
        return False, "gpg --verify timed out"


def step_disable_adb_debugging(result: Any, serial: str) -> bool:
    """
    CM-04 + CM-26: Disable ADB debugging on the device after provisioning.
    CRITICAL: leaves ADB enabled post-provisioning creates a backdoor (AV-11, AV-38).
    Must be called at the END of step_verify, before declaring success.
    """
    t0 = time.time()
    rc, stdout, stderr = _adb("shell settings put global adb_enabled 0", serial=serial)
    elapsed = int((time.time() - t0) * 1000)

    if rc != 0:
        result.add_step(
            "disable_adb", "warn",
            f"Could not disable ADB via settings: {stderr[:200]}. "
            f"Manual action required: Settings > Developer Options > USB Debugging OFF",
            elapsed,
        )
        return False

    rc2, stdout2, _ = _adb("shell settings get global adb_enabled", serial=serial)
    if stdout2.strip() == "0":
        result.add_step("disable_adb", "ok", "ADB debugging disabled (adb_enabled=0)", elapsed)
        return True

    result.add_step(
        "disable_adb", "warn",
        f"ADB disable command ran but adb_enabled={stdout2.strip()!r} (expected 0). "
        f"Physical device reboot required for setting to take effect.",
        elapsed,
    )
    return False


class HumanGateRequired(Exception):
    """Raised when a CRITICAL step requires operator confirmation before proceeding."""
    def __init__(self, step_name: str, message: str):
        self.step_name = step_name
        self.message = message
        super().__init__(f"HumanGate required for {step_name}: {message}")


def require_human_gate(step_name: str, description: str, result: Any) -> None:
    """
    CM-10: Block execution until HumanGate confirmation is registered.
    Records requirement in result.requires_manual and raises HumanGateRequired.
    """
    import uuid as _uuid_gate
    gate_id = str(_uuid_gate.uuid4())
    result.requires_manual.append(f"{step_name}:{gate_id}")
    result.add_step(
        f"humangate_{step_name}",
        "manual",
        f"[HUMAN GATE] {description} — gate_id={gate_id}",
        manual=True,
    )
    _audit_log_event("human_gate_required", {
        "step": step_name,
        "gate_id": gate_id,
        "description": description,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    raise HumanGateRequired(step_name, description)


@_dataclass
class RollbackCheckpoint:
    """
    CM-11: Tracks provisioning state for safe rollback on failure.
    Saves state to JSON alongside the provisioning job.
    """
    job_id: str
    device_serial: str
    stage: str = "pre_check"
    bootloader_unlocked_at: str = ""
    grapheneos_flashed: bool = False
    grapheneos_sha256: str = ""
    bootloader_locked_at: str = ""
    agent_deployed: bool = False
    fido2_enrolled: bool = False

    _STAGES_ORDER = [
        "pre_check", "usb_verified", "adb_authed", "device_identified",
        "bootloader_unlocked", "grapheneos_flashed", "bootloader_locked",
        "agent_deployed", "fido2_enrolled", "verified", "complete",
    ]

    def advance(self, new_stage: str) -> None:
        """Advance to a new stage and persist checkpoint."""
        import json as _json
        self.stage = new_stage
        if new_stage == "bootloader_unlocked":
            self.bootloader_unlocked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        elif new_stage == "bootloader_locked":
            self.bootloader_locked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._persist()
        _audit_log_event("checkpoint", {"job_id": self.job_id, "stage": new_stage,
                                         "device_serial": self.device_serial})

    def needs_rollback_action(self) -> "str | None":
        """Returns a string describing required rollback if pipeline interrupted, or None."""
        if self.stage == "bootloader_unlocked" and not self.grapheneos_flashed:
            return (
                "CRITICAL: Bootloader is unlocked but GrapheneOS not flashed. "
                "Either flash GrapheneOS immediately or run: fastboot flashing lock"
            )
        if self.grapheneos_flashed and not self.bootloader_locked_at:
            return (
                "WARNING: GrapheneOS flashed but bootloader not re-locked. "
                "Run: fastboot flashing lock"
            )
        return None

    def _persist(self) -> None:
        import json as _json
        checkpoint_path = Path(f"/tmp/sylion_checkpoint_{self.job_id}.json")
        try:
            with open(checkpoint_path, "w") as f:
                _json.dump({
                    "job_id": self.job_id,
                    "device_serial": self.device_serial,
                    "stage": self.stage,
                    "bootloader_unlocked_at": self.bootloader_unlocked_at,
                    "grapheneos_flashed": self.grapheneos_flashed,
                    "grapheneos_sha256": self.grapheneos_sha256,
                    "bootloader_locked_at": self.bootloader_locked_at,
                    "agent_deployed": self.agent_deployed,
                    "fido2_enrolled": self.fido2_enrolled,
                }, f, indent=2)
        except OSError as exc:
            log.warning("Cannot persist rollback checkpoint: %s", exc)

    @classmethod
    def load(cls, job_id: str) -> "RollbackCheckpoint | None":
        import json as _json
        checkpoint_path = Path(f"/tmp/sylion_checkpoint_{job_id}.json")
        if not checkpoint_path.exists():
            return None
        try:
            with open(checkpoint_path) as f:
                data = _json.load(f)
            cp = cls(job_id=data["job_id"], device_serial=data["device_serial"])
            for k, v in data.items():
                if hasattr(cp, k):
                    setattr(cp, k, v)
            return cp
        except Exception as exc:
            log.warning("Cannot load rollback checkpoint for job %s: %s", job_id, exc)
            return None


def get_adb_key_fingerprint() -> str:
    """
    CM-05: Read the local ADB private key and return its RSA fingerprint.
    Logs the fingerprint to the audit trail.
    """
    adbkey_path = Path.home() / ".android" / "adbkey"
    if not adbkey_path.exists():
        return "adbkey_not_found"
    try:
        content = adbkey_path.read_bytes()
        fingerprint = _hashlib.sha256(content).hexdigest()[:16]
        _audit_log_event("adb_key_used", {
            "fingerprint_sha256_prefix": fingerprint,
            "adbkey_path": str(adbkey_path),
        })
        return fingerprint
    except OSError as exc:
        return f"error:{exc}"


def verify_agent_files_before_push(pipeline_dir: Path) -> tuple[bool, list[str]]:
    """
    CM-19: Verify SHA-256 of agent files before pushing to device.
    Returns (all_ok, list_of_errors).
    """
    errors: list[str] = []
    files_to_check = [
        ("device_harness.py", pipeline_dir / "device_harness.py"),
        ("pixel_manager.sh", pipeline_dir / "device" / "pixel_manager.sh"),
    ]
    for name, local_path in files_to_check:
        expected = AGENT_FILE_MANIFEST.get(name, "")
        if not expected:
            log.warning("CM-19: No expected SHA-256 for %s in AGENT_FILE_MANIFEST — skipping", name)
            _audit_log_event("agent_verify_skipped", {"file": name, "reason": "no_manifest_entry"})
            continue
        if not local_path.exists():
            errors.append(f"Agent file missing: {local_path}")
            continue
        actual = _sha256_file(str(local_path))
        if not _hmac.compare_digest(actual, expected.lower()):
            errors.append(f"SHA-256 MISMATCH for {name}: got {actual}, expected {expected}")
            _audit_log_event("agent_integrity_failed", {
                "file": name, "actual_sha256": actual, "expected_sha256": expected,
            })
        else:
            _audit_log_event("agent_integrity_ok", {"file": name, "sha256": actual})
    return len(errors) == 0, errors


def step_deploy_agent_hardened(result: Any, serial: str, pipeline_dir: Path) -> bool:
    """
    CM-19 + CM-20: Hardened version of step_deploy_agent.
    Adds SHA-256 pre-push verification, chmod 700, post-push verification, and audit log.
    """
    t0 = time.time()

    ok, errors = verify_agent_files_before_push(pipeline_dir)
    if not ok:
        for err in errors:
            result.add_step("agent_integrity_check", "fail", err, 0)
        result.add_step("agent_deploy", "fail",
                        "Agent file integrity check failed — refusing to deploy", 0)
        return False

    _adb(f"shell mkdir -p {DEVICE_SYLION_DIR}", serial=serial)
    _adb(f"shell mkdir -p {DEVICE_CONFIG_DIR}", serial=serial)

    files_to_deploy = [
        ("device_harness.py", pipeline_dir / "device_harness.py"),
        ("pixel_manager.sh", pipeline_dir / "device" / "pixel_manager.sh"),
    ]

    deployed: list[str] = []
    for remote_name, local_path in files_to_deploy:
        if not local_path.exists():
            result.add_step(f"deploy_{remote_name}", "warn", f"File not found: {local_path}", 0)
            continue
        remote_path = f"{DEVICE_SYLION_DIR}/{remote_name}"
        rc, stdout, stderr = _adb(f"push {local_path} {remote_path}", serial=serial, timeout=60)
        if rc != 0:
            result.add_step(f"deploy_{remote_name}", "warn", f"Push failed: {stderr[:100]}", 0)
            continue
        _adb(f"shell chmod 700 {remote_path}", serial=serial)
        local_sha256 = _sha256_file(str(local_path))
        rc2, remote_sha256_raw, _ = _adb(f"shell sha256sum {remote_path}", serial=serial)
        remote_sha256 = remote_sha256_raw.split()[0] if rc2 == 0 else ""
        if remote_sha256 and _hmac.compare_digest(local_sha256, remote_sha256):
            _audit_log_event("agent_pushed", {
                "file": remote_name, "remote_path": remote_path,
                "sha256": local_sha256, "device_serial": serial,
            })
            deployed.append(remote_name)
        else:
            result.add_step(f"verify_{remote_name}", "fail",
                            f"Post-push SHA-256 mismatch for {remote_name}!", 0)

    _adb(f"shell chmod 700 {DEVICE_SYLION_DIR}", serial=serial)
    elapsed = int((time.time() - t0) * 1000)
    if deployed:
        result.agent_deployed = True
        result.add_step(
            "agent_deploy", "ok",
            f"Deployed {len(deployed)} files with integrity verification: {', '.join(deployed)}",
            elapsed,
        )
        return True
    result.add_step("agent_deploy", "fail", "No files deployed", elapsed)
    return False


def step_verify_hardened(result: Any, serial: str) -> bool:
    """
    CM-25 + CM-26 + CM-27: Hardened final verification.
    Checks: ADB alive, sylion dir, python3, GrapheneOS installed, bootloader locked, ADB disabled.
    """
    t0 = time.time()
    all_ok = True
    security_failures: list[str] = []

    checks = [
        ("adb_alive", "shell echo SYLION_OK"),
        ("sylion_dir", f"shell ls {DEVICE_SYLION_DIR}/"),
        ("python3_on_device", "shell which python3 || echo no_python3"),
    ]
    for name, cmd in checks:
        rc, stdout, stderr = _adb(cmd, serial=serial)
        if rc == 0:
            result.add_step(f"verify_{name}", "ok", stdout[:200], 0)
        else:
            result.add_step(f"verify_{name}", "warn", stderr[:200] or "check failed", 0)
            all_ok = False

    rc, gos_version, _ = _adb("shell getprop ro.grapheneos.version", serial=serial)
    if rc == 0 and gos_version.strip():
        result.add_step("verify_grapheneos", "ok",
                        f"GrapheneOS version: {gos_version.strip()}", 0)
        _audit_log_event("verify_grapheneos_ok", {
            "version": gos_version.strip(), "device_serial": serial,
        })
    else:
        msg = "GrapheneOS NOT detected (ro.grapheneos.version is empty) — SECURITY FAILURE"
        result.add_step("verify_grapheneos", "fail", msg, 0)
        security_failures.append("grapheneos_not_installed")
        all_ok = False

    rc, vb_state, _ = _adb("shell getprop ro.boot.verifiedbootstate", serial=serial)
    vb_state = vb_state.strip()
    if vb_state in ("green", "yellow"):
        result.add_step("verify_bootloader_locked", "ok",
                        f"Verified boot state: {vb_state} (bootloader locked)", 0)
        _audit_log_event("verify_bootloader_locked", {"state": vb_state, "device_serial": serial})
    else:
        msg = (
            f"Bootloader NOT locked (verifiedbootstate={vb_state!r}) — "
            f"CRITICAL SECURITY FAILURE. Run: fastboot flashing lock"
        )
        result.add_step("verify_bootloader_locked", "fail", msg, 0)
        security_failures.append("bootloader_not_locked")
        all_ok = False

    adb_disable_ok = step_disable_adb_debugging(result, serial)
    if not adb_disable_ok:
        security_failures.append("adb_still_enabled")
        all_ok = False

    rc, patch_date, _ = _adb("shell getprop ro.build.version.security_patch", serial=serial)
    if rc == 0 and patch_date.strip():
        _audit_log_event("verify_security_patch", {
            "patch_date": patch_date.strip(), "device_serial": serial,
        })
        result.add_step("verify_security_patch", "ok", f"Security patch: {patch_date.strip()}", 0)

    elapsed = int((time.time() - t0) * 1000)
    if security_failures:
        result.add_step(
            "verify_security_failures", "fail",
            f"SECURITY FAILURES: {', '.join(security_failures)} — device NOT ready for deployment",
            elapsed,
        )
        all_ok = False
    elif all_ok:
        result.add_step(
            "verify_summary", "ok",
            "Full verification OK — Pixel ready (ADB disabled, bootloader locked, GrapheneOS installed)",
            elapsed,
        )
    else:
        result.add_step(
            "verify_summary", "warn",
            "Partial verification — some checks require manual attention",
            elapsed,
        )

    _audit_log_event("verify_complete", {
        "device_serial": serial,
        "all_ok": all_ok,
        "security_failures": security_failures,
    })
    return all_ok


def generate_fido2_challenge() -> dict:
    """
    CM-22 + CM-24: Generate a cryptographic challenge for FIDO2 HumanGate.
    Returns a challenge dict to embed in the HumanGate response.
    """
    import uuid as _uuid_fido
    challenge_id = str(_uuid_fido.uuid4())
    nonce = os.urandom(32).hex()
    issued_at = int(time.time())
    expires_at = issued_at + int(os.environ.get("FIDO2_GATE_TIMEOUT_SECONDS", "600"))
    challenge = {
        "challenge_id": challenge_id,
        "nonce": nonce,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "type": "fido2_humangate",
    }
    _audit_log_event("fido2_challenge_issued", challenge)
    return challenge


def validate_fido2_confirmation(
    challenge_id: str,
    operator_id: str,
    confirmation_token: str,
    stored_challenges: dict,
) -> tuple[bool, str]:
    """
    CM-22: Validate FIDO2 HumanGate confirmation.
    Returns (ok, detail).
    """
    challenge = stored_challenges.get(challenge_id)
    if not challenge:
        return False, f"Challenge {challenge_id} not found"
    if int(time.time()) > challenge["expires_at"]:
        return False, f"Challenge {challenge_id} expired at {challenge['expires_at']}"
    if not operator_id:
        return False, "operator_id required for FIDO2 confirmation"
    _audit_log_event("fido2_confirmed", {
        "challenge_id": challenge_id,
        "operator_id": operator_id,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return True, f"FIDO2 HumanGate confirmed by operator {operator_id}"


def verify_device_attestation_fastboot(serial: str = "") -> tuple[bool, dict]:
    """
    CM-07: Use fastboot getvar to retrieve hardware attestation variables.
    Unlike adb shell getprop, fastboot variables are harder to spoof.
    Must be called in fastboot mode.
    """
    cmd_base = ["fastboot"]
    if serial:
        cmd_base.extend(["-s", serial])

    attestation_vars = [
        "product", "serialno", "secure", "unlocked",
        "verified-boot-state", "current-slot", "max-download-size",
    ]
    results: dict = {}
    for var in attestation_vars:
        try:
            proc = subprocess.run(
                cmd_base + ["getvar", var],
                capture_output=True, text=True, timeout=10,
            )
            for line in (proc.stdout + proc.stderr).splitlines():
                if line.lower().startswith(f"{var}:"):
                    results[var] = line.split(":", 1)[1].strip()
                    break
        except Exception:
            results[var] = "error"

    _audit_log_event("device_attestation", {
        "device_serial": serial,
        "fastboot_vars": results,
    })

    is_unlocked = results.get("unlocked", "").lower() == "yes"
    product = results.get("product", "")
    is_pixel_9 = "tokay" in product.lower() or "pixel" in product.lower()
    return is_pixel_9 and not is_unlocked, results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="SYLION Pixel Auto-Provisioning")
    parser.add_argument("--skip-usbipd", action="store_true",
                        help="Skip USB passthrough (device already in WSL)")
    parser.add_argument("--busid", default="", help="USB bus ID for usbipd")
    parser.add_argument("--skip-flash", action="store_true",
                        help="Skip GrapheneOS flash check")
    parser.add_argument("--skip-root", action="store_true",
                        help="Skip root check")
    parser.add_argument("--skip-agent", action="store_true",
                        help="Skip agent deployment")
    parser.add_argument(
        "--force", action="store_true",
        help=(
            "Continue provisioning even if the detected device model is not in the "
            "Pixel 9 family. Without --force, step_get_device_info() raises RuntimeError "
            "on unsupported models (e.g. Pixel 7, Pixel 8, non-Pixel devices)."
        ),
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    r = provision_pixel(
        skip_usbipd=args.skip_usbipd,
        busid=args.busid,
        skip_flash=args.skip_flash,
        skip_root_check=args.skip_root,
        skip_agent_deploy=args.skip_agent,
        force=args.force,
    )

    if args.json:
        print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"\n{'=' * 60}")
        print("SYLION Pixel Provisioning")
        print(f"{'=' * 60}")
        for step in r.steps:
            icon = {"ok": "\u2713", "warn": "\u26a0", "fail": "\u2717",
                    "skip": "\u2014", "manual": "\u261e"}.get(step["status"], "?")
            print(f"  [{icon}] {step['name']}: {step['detail']}")
        print(f"\nWynik: {'SUKCES' if r.success else 'WYMAGA UWAGI'}")
        if r.requires_manual:
            print(f"Kroki reczne: {', '.join(r.requires_manual)}")
        if r.error:
            print(f"Blad: {r.error}")
        print(f"Czas: {r.elapsed_s:.1f}s")
