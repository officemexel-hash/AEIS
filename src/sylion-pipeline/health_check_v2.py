from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import subprocess
import time
from contextlib import closing
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable


class Severity(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"
    NA = "n/a"


_COUNTS = {
    "PIX": 10,
    "MUD": 8,
    "WG": 5,
    "API": 12,
    "OLLAMA": 6,
    "UPL": 6,
    "SUB": 4,
    "KSIEGA": 4,
    "PHANTOM": 4,
    "PIPELINE": 5,
    "DB": 5,
    "CVE": 4,
    "RODO": 4,
    "CERT": 5,
    "CRED": 5,
}

CAT_CODES: dict[str, list[str]] = {
    category: [f"SYL-{category}-{index:03d}" for index in range(1, count + 1)]
    for category, count in _COUNTS.items()
}
CATEGORIES_META = [
    {"id": key.lower(), "label": key.title(), "prefix": f"SYL-{key}", "codes": value}
    for key, value in CAT_CODES.items()
]

_HISTORY_DB_PATH = Path(os.environ.get("SYLION_HEALTH_HISTORY_DB", "health_history.db"))


def _result(code: str, category: str, severity: str, message: str, suggestion_pl: str = "") -> dict[str, Any]:
    return {
        "code": code,
        "category": category,
        "severity": severity,
        "status": "pass" if severity == "ok" else severity,
        "message": message,
        "timestamp": time.time(),
        "suggestion_pl": suggestion_pl or "Zweryfikuj konfiguracje i uruchom ponownie check.",
    }


def _ok(code: str, category: str, message: str) -> dict[str, Any]:
    return _result(code, category, "ok", message)


def _warn(code: str, category: str, message: str) -> dict[str, Any]:
    return _result(code, category, "warn", message)


def _err(code: str, category: str, message: str) -> dict[str, Any]:
    return _result(code, category, "error", message)


def _crit(code: str, category: str, message: str) -> dict[str, Any]:
    return _result(code, category, "critical", message)


def _na(code: str, category: str, message: str = "N/A") -> dict[str, Any]:
    return _result(code, category, "n/a", message)


def _find_sylion_home() -> Path:
    return Path(os.environ.get("SYLION_HOME", Path.cwd()))


def _find_db() -> Path | None:
    explicit = os.environ.get("SYLION_DB_PATH")
    if explicit and Path(explicit).exists():
        return Path(explicit)
    for name in ("sylion_aeis.db", "advisor_engine.db"):
        path = _find_sylion_home() / name
        if path.exists():
            return path
    return None


def check_pixel() -> list[dict[str, Any]]:
    try:
        start = subprocess.run(["adb", "start-server"], capture_output=True, text=True)
    except FileNotFoundError:
        return [_err("SYL-PIX-001", "pixel", "ADB not installed")]
    if start.returncode != 0:
        return [_err("SYL-PIX-001", "pixel", "ADB start-server failed")]
    results = [_ok("SYL-PIX-001", "pixel", "ADB available")]
    devices = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    output = devices.stdout or ""
    if "unauthorized" in output.lower():
        results.append(_err("SYL-PIX-002", "pixel", "UNAUTHORIZED device"))
    elif "\tdevice" not in output:
        results.append(_warn("SYL-PIX-002", "pixel", "No device attached"))
        results.append(_na("SYL-PIX-003", "pixel", "No device attached"))
    else:
        results.append(_ok("SYL-PIX-002", "pixel", "Device authorized"))
        results.append(_ok("SYL-PIX-003", "pixel", "Device checks available"))
    return results


def check_mudi() -> list[dict[str, Any]]:
    try:
        ping = subprocess.run(["ping", "-n", "1", "192.168.8.1"], capture_output=True, text=True)
    except FileNotFoundError:
        return [_err("SYL-MUD-001", "mudi", "ping unavailable")]
    if ping.returncode != 0:
        return [_err("SYL-MUD-001", "mudi", "Mudi ping failed")]
    results = [_ok("SYL-MUD-001", "mudi", "Mudi ping ok")]
    ssh = subprocess.run(["ssh", "root@192.168.8.1", "echo SYLION_OK"], capture_output=True, text=True)
    if ssh.returncode != 0:
        results.append(_err("SYL-MUD-002", "mudi", "SSH failed"))
        return results
    results.append(_ok("SYL-MUD-002", "mudi", "SSH ok"))
    uptime = subprocess.run(["ssh", "root@192.168.8.1", "cat /proc/uptime"], capture_output=True, text=True)
    try:
        seconds = float((uptime.stdout or "0").split()[0])
    except (ValueError, IndexError):
        seconds = 0.0
    results.append(_warn("SYL-MUD-007", "mudi", "Fresh reboot") if seconds < 120 else _ok("SYL-MUD-007", "mudi", "Uptime ok"))
    return results


def check_wireguard() -> list[dict[str, Any]]:
    try:
        proc = subprocess.run(["wg", "show"], capture_output=True, text=True)
    except FileNotFoundError:
        return [_err("SYL-WG-001", "wireguard", "WireGuard not installed")]
    output = proc.stdout or ""
    if not output.strip():
        return [_err("SYL-WG-001", "wireguard", "WireGuard returned no output")]
    results = [_ok("SYL-WG-001", "wireguard", "WireGuard available")]
    if "peer:" not in output:
        results.append(_err("SYL-WG-003", "wireguard", "0 peers configured"))
        return results
    results.append(_ok("SYL-WG-003", "wireguard", "Peer configured"))
    if re.search(r"latest handshake: .*(hour|day)", output):
        results.append(_err("SYL-WG-002", "wireguard", "Handshake older than one hour"))
    else:
        results.append(_ok("SYL-WG-002", "wireguard", "Handshake fresh"))
    return results


def check_api_keys_live() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not openai_key:
        results.append(_err("SYL-API-001", "api", "OPENAI_API_KEY missing"))
    elif not openai_key.startswith("sk-"):
        results.append(_warn("SYL-API-002", "api", "OPENAI_API_KEY has unexpected prefix"))
    else:
        results.append(_ok("SYL-API-001", "api", "OPENAI_API_KEY present"))
        try:
            import httpx

            status = httpx.get("https://api.openai.com/v1/models", timeout=3).status_code
            if status == 401:
                results.append(_err("SYL-API-009", "api", "OpenAI returned 401"))
            elif status == 429:
                results.append(_warn("SYL-API-009", "api", "OpenAI returned 429"))
            else:
                results.append(_ok("SYL-API-009", "api", f"OpenAI returned {status}"))
        except Exception as exc:  # noqa: BLE001
            results.append(_warn("SYL-API-009", "api", f"OpenAI live check unavailable: {exc}"))
    if not anthropic_key:
        results.append(_err("SYL-API-003", "api", "ANTHROPIC_API_KEY missing"))
    return results


def check_ollama() -> list[dict[str, Any]]:
    try:
        import httpx

        version = httpx.get("http://127.0.0.1:11434/api/version", timeout=2)
        if version.status_code != 200:
            return [_err("SYL-OLLAMA-001", "ollama", "Ollama daemon unavailable")]
        results = [_ok("SYL-OLLAMA-001", "ollama", "Ollama daemon available")]
        httpx.get("http://127.0.0.1:11434/api/tags", timeout=2)
        httpx.get("http://127.0.0.1:11434/api/ps", timeout=2)
    except Exception as exc:  # noqa: BLE001
        return [_err("SYL-OLLAMA-001", "ollama", f"Ollama daemon down: {exc}")]
    if not os.environ.get("OLLAMA_MODEL"):
        results.append(_warn("SYL-OLLAMA-006", "ollama", "OLLAMA_MODEL not configured"))
    return results


def check_uploads() -> list[dict[str, Any]]:
    upload_dir = _find_sylion_home() / "sylion-pipeline" / "dashboard" / "workspace_uploads"
    if not upload_dir.exists():
        return [_err("SYL-UPL-001", "uploads", "Upload directory missing")]
    results = [_ok("SYL-UPL-001", "uploads", "Upload directory exists")]
    files = [p for p in upload_dir.rglob("*") if p.is_file()]
    traversal = next((p.name for p in files if ".." in p.name), None)
    dangerous = next((p.name for p in files if p.suffix.lower() in {".sh", ".bat", ".ps1", ".cmd", ".exe"}), None)
    results.append(_crit("SYL-UPL-005", "uploads", f"Path traversal-like filename: {traversal}") if traversal else _ok("SYL-UPL-005", "uploads", "No traversal filenames"))
    results.append(_warn("SYL-UPL-006", "uploads", f"Dangerous upload extension: {dangerous}") if dangerous else _ok("SYL-UPL-006", "uploads", "No dangerous extensions"))
    return results


def check_subagents() -> list[dict[str, Any]]:
    locks = list(_find_sylion_home().rglob("*.lock"))
    stale = [p for p in locks if time.time() - p.stat().st_mtime > 3600]
    return [_warn("SYL-SUB-001", "subagents", "Stale lock file") if stale else _ok("SYL-SUB-001", "subagents", "No stale locks")]


def check_ksiega() -> list[dict[str, Any]]:
    candidates = [_find_sylion_home() / "ksiega.json", Path.home() / "ksiega.json"]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return [_err("SYL-KSIEGA-001", "ksiega", "ksiega.json not found")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [_ok("SYL-KSIEGA-001", "ksiega", "ksiega.json found"), _err("SYL-KSIEGA-003", "ksiega", "Invalid JSON")]
    results = [_ok("SYL-KSIEGA-001", "ksiega", "ksiega.json found")]
    if str(payload.get("version")) != "3.4":
        results.append(_warn("SYL-KSIEGA-002", "ksiega", "Unexpected ksiega version"))
    return results


def check_phantom() -> list[dict[str, Any]]:
    path = _find_sylion_home() / "phantom.json"
    if not path.exists():
        return [_warn("SYL-PHANTOM-001", "phantom", "Phantom config missing")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [_err("SYL-PHANTOM-002", "phantom", "Invalid phantom config")]
    return [_warn("SYL-PHANTOM-002", "phantom", "Unexpected phantom version") if str(payload.get("version")) != "3" else _ok("SYL-PHANTOM-002", "phantom", "Phantom version ok")]


def check_pipeline() -> list[dict[str, Any]]:
    path = _find_db()
    if path is None:
        return [_na(f"SYL-PIPELINE-{index:03d}", "pipeline", "Database missing") for index in range(1, 5)]
    with closing(sqlite3.connect(path)) as conn:
        try:
            row = conn.execute("SELECT status FROM runs ORDER BY updated_at DESC LIMIT 1").fetchone()
        except sqlite3.Error:
            row = None
    status = row[0] if row else "unknown"
    return [_err("SYL-PIPELINE-001", "pipeline", "Latest run failed") if status == "failed" else _ok("SYL-PIPELINE-001", "pipeline", "Latest run not failed")]


def check_db_extended() -> list[dict[str, Any]]:
    path = _find_db()
    if path is None:
        return [_na(f"SYL-DB-{index:03d}", "db", "Database missing") for index in range(1, 6)]
    with closing(sqlite3.connect(path)) as conn:
        status = conn.execute("PRAGMA integrity_check").fetchone()[0]
    return [_ok("SYL-DB-006", "db", "SQLite integrity ok") if status == "ok" else _err("SYL-DB-006", "db", f"SQLite integrity failed: {status}")]


def check_cve() -> list[dict[str, Any]]:
    try:
        version = subprocess.run(["pip-audit", "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        return [_warn("SYL-CVE-001", "cve", "pip-audit not installed")]
    if version.returncode != 0:
        return [_warn("SYL-CVE-001", "cve", "pip-audit unavailable")]
    results = [_ok("SYL-CVE-001", "cve", "pip-audit available")]
    audit = subprocess.run(["pip-audit", "-f", "json"], capture_output=True, text=True)
    try:
        payload = json.loads(audit.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    vulns = payload.get("vulnerabilities") or []
    results.append(_ok("SYL-CVE-002", "cve", "No vulnerabilities") if not vulns else _crit("SYL-CVE-002", "cve", "Vulnerabilities found"))
    return results


def check_rodo() -> list[dict[str, Any]]:
    logs = _find_sylion_home() / "logs"
    results: list[dict[str, Any]] = []
    old = False
    pii = False
    if logs.exists():
        for path in logs.rglob("*"):
            if not path.is_file():
                continue
            old = old or (time.time() - path.stat().st_mtime > 90 * 86400)
            text = path.read_text(encoding="utf-8", errors="ignore")[:20000]
            pii = pii or bool(re.search(r"\b\d{11}\b|[\w.+-]+@[\w.-]+", text))
    results.append(_warn("SYL-RODO-003", "rodo", "Old logs found") if old else _ok("SYL-RODO-003", "rodo", "No stale logs"))
    results.append(_crit("SYL-RODO-004", "rodo", "PII found in logs") if pii else _ok("SYL-RODO-004", "rodo", "No PII in logs"))
    return results


def check_cert() -> list[dict[str, Any]]:
    try:
        subprocess.run(["systemctl", "is-active", "nginx"], capture_output=True, text=True)
        results = [_ok("SYL-CERT-001", "cert", "systemctl available")]
    except FileNotFoundError:
        results = [_na("SYL-CERT-001", "cert", "systemctl unavailable")]
    if not os.environ.get("SYLION_DOMAIN"):
        results.extend(_na(f"SYL-CERT-{index:03d}", "cert", "Domain not configured") for index in range(2, 6))
    return results


def check_cred() -> list[dict[str, Any]]:
    path = _find_db()
    if path is None:
        return [_na(f"SYL-CRED-{index:03d}", "cred", "Database missing") for index in range(1, 6)]
    results: list[dict[str, Any]] = []
    with closing(sqlite3.connect(path)) as conn:
        try:
            rows = conn.execute("SELECT role, totp_secret FROM users").fetchall()
        except sqlite3.Error:
            rows = []
    if any(row[0] is None for row in rows):
        results.append(_err("SYL-CRED-005", "cred", "User without role"))
    if any(row[1] is None for row in rows):
        results.append(_warn("SYL-CRED-003", "cred", "User without 2FA"))
    return results or [_ok("SYL-CRED-001", "cred", "Credentials table ok")]


RUNNERS: list[tuple[str, Callable[[], list[dict[str, Any]]]]] = [
    ("pixel", check_pixel),
    ("mudi", check_mudi),
    ("wireguard", check_wireguard),
    ("api", check_api_keys_live),
    ("ollama", check_ollama),
    ("uploads", check_uploads),
    ("subagents", check_subagents),
    ("ksiega", check_ksiega),
    ("phantom", check_phantom),
    ("pipeline", check_pipeline),
    ("db", check_db_extended),
    ("cve", check_cve),
    ("rodo", check_rodo),
    ("cert", check_cert),
    ("cred", check_cred),
]


def _worst_severity(checks: list[dict[str, Any]]) -> str:
    order = {"n/a": 0, "ok": 1, "warn": 2, "error": 3, "critical": 4}
    worst = "n/a"
    for check in checks:
        severity = str(check.get("severity", "n/a"))
        if order.get(severity, 0) > order.get(worst, 0):
            worst = severity
    return worst


def init_history_table(db_path: Path | None = None) -> None:
    path = Path(db_path or _HISTORY_DB_PATH)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at REAL NOT NULL,
                overall TEXT NOT NULL,
                elapsed_ms INTEGER NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hh_run_at ON health_history(run_at)")
        conn.commit()


def _save_history(payload: dict[str, Any]) -> None:
    init_history_table(_HISTORY_DB_PATH)
    with closing(sqlite3.connect(_HISTORY_DB_PATH)) as conn:
        conn.execute(
            "INSERT INTO health_history(run_at, overall, elapsed_ms, payload_json) VALUES (?, ?, ?, ?)",
            (time.time(), payload.get("overall", "unknown"), int(payload.get("elapsed_ms", 0)), json.dumps(payload, ensure_ascii=False, default=str)),
        )
        conn.commit()


def get_history(limit: int = 20) -> list[dict[str, Any]]:
    init_history_table(_HISTORY_DB_PATH)
    with closing(sqlite3.connect(_HISTORY_DB_PATH)) as conn:
        rows = conn.execute("SELECT overall, elapsed_ms, payload_json FROM health_history ORDER BY run_at DESC LIMIT ?", (limit,)).fetchall()
    history: list[dict[str, Any]] = []
    for overall, elapsed_ms, payload_json in rows:
        payload = json.loads(payload_json)
        payload.setdefault("overall", overall)
        payload.setdefault("elapsed_ms", elapsed_ms)
        history.append(payload)
    return history


def run_comprehensive_health(timeout: int = 30) -> dict[str, Any]:
    start = time.time()
    checks: list[dict[str, Any]] = []
    categories: dict[str, dict[str, Any]] = {}
    for category, runner in RUNNERS:
        try:
            results = runner()
        except Exception as exc:  # noqa: BLE001
            results = [_err(f"SYL-{category.upper()}-999", category, f"Runner failed: {exc}")]
        checks.extend(results)
        categories[category] = {"count": len(results), "worst": _worst_severity(results)}
    overall = _worst_severity(checks)
    stats = {
        "total": len(checks),
        "pass": sum(1 for item in checks if item["severity"] == "ok"),
        "warn": sum(1 for item in checks if item["severity"] == "warn"),
        "fail": sum(1 for item in checks if item["severity"] == "error"),
        "critical": sum(1 for item in checks if item["severity"] == "critical"),
    }
    payload = {
        "version": "v2",
        "overall": overall,
        "checks": checks,
        "categories": categories,
        "stats": stats,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_ms": int((time.time() - start) * 1000),
    }
    _save_history(payload)
    return payload


async def run_comprehensive_health_async(timeout: int = 30) -> dict[str, Any]:
    return await asyncio.to_thread(run_comprehensive_health, timeout)
