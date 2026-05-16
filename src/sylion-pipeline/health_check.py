#!/usr/bin/env python3
"""
SYLION Health Check & Auto-Diagnostics Module (v5.8.8.1)

Performs deep system health checks, generates structured error reports,
and attempts automatic fixes for common problems.

Error code format: SYL-{CATEGORY}-{NUMBER}
Categories:
    ENV  = Environment / Python / dependencies
    DB   = Database (SQLite)
    KEY  = API keys configuration
    NET  = Network / ports / connectivity
    CFG  = Configuration files
    FS   = Filesystem / permissions
    PIPE = Pipeline / orchestrator
    RUN  = Runtime
    DEV  = Devices (Pixel, Router)
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.health")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    OK = "ok"
    WARN = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AutoFixResult(str, Enum):
    FIXED = "fixed"
    ATTEMPTED = "attempted"
    SKIPPED = "skipped"
    FAILED = "failed"
    NOT_APPLICABLE = "n/a"


@dataclass
class CheckResult:
    """Single health check result."""
    code: str                             # e.g. "SYL-ENV-001"
    name: str                             # Human-readable name
    severity: Severity = Severity.OK
    message: str = ""                     # Detail message
    auto_fix: AutoFixResult = AutoFixResult.NOT_APPLICABLE
    fix_description: str = ""             # What was fixed / attempted
    suggestion: str = ""                  # Manual fix suggestion for user
    elapsed_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.severity == Severity.OK

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["auto_fix"] = self.auto_fix.value
        return d


@dataclass
class HealthReport:
    """Complete health report for the whole system."""
    timestamp: float = field(default_factory=time.time)
    overall: Severity = Severity.OK
    checks: list[CheckResult] = field(default_factory=list)
    summary: str = ""
    fixed_count: int = 0
    error_count: int = 0
    warning_count: int = 0

    def add(self, result: CheckResult):
        self.checks.append(result)
        if result.severity == Severity.CRITICAL:
            self.overall = Severity.CRITICAL
        elif result.severity == Severity.ERROR and self.overall != Severity.CRITICAL:
            self.overall = Severity.ERROR
        elif result.severity == Severity.WARN and self.overall == Severity.OK:
            self.overall = Severity.WARN
        if result.auto_fix == AutoFixResult.FIXED:
            self.fixed_count += 1
        if result.severity in (Severity.ERROR, Severity.CRITICAL):
            self.error_count += 1
        elif result.severity == Severity.WARN:
            self.warning_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall": self.overall.value,
            "summary": self.summary,
            "stats": {
                "total": len(self.checks),
                "ok": sum(1 for c in self.checks if c.ok),
                "warnings": self.warning_count,
                "errors": self.error_count,
                "auto_fixed": self.fixed_count,
            },
            "checks": [c.to_dict() for c in self.checks],
        }

    def save(self, path: Path):
        """Save report as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Health report saved to %s", path)

    def generate_summary(self) -> str:
        lines = []
        if self.overall == Severity.OK:
            lines.append("System OK — all checks passed.")
        else:
            lines.append(f"System status: {self.overall.value.upper()}")
        lines.append(f"  Checks: {len(self.checks)} total, "
                      f"{sum(1 for c in self.checks if c.ok)} OK, "
                      f"{self.warning_count} warnings, {self.error_count} errors")
        if self.fixed_count:
            lines.append(f"  Auto-fixed: {self.fixed_count}")

        # List problems
        for c in self.checks:
            if not c.ok:
                icon = "⚠" if c.severity == Severity.WARN else "✗"
                lines.append(f"  {icon} [{c.code}] {c.name}: {c.message}")
                if c.auto_fix == AutoFixResult.FIXED:
                    lines.append(f"    → AUTO-FIXED: {c.fix_description}")
                elif c.suggestion:
                    lines.append(f"    → Suggestion: {c.suggestion}")
        self.summary = "\n".join(lines)
        return self.summary


# ---------------------------------------------------------------------------
# Utility: find SYLION home
# ---------------------------------------------------------------------------

def _find_sylion_home() -> Path:
    """Find the SYLION installation root."""
    # Check env var first
    env = os.environ.get("SYLION_HOME")
    if env:
        return Path(env)
    # Try common locations
    candidates = [
        Path.home() / "sylion",
        Path(__file__).resolve().parent.parent,  # sylion-installer -> sylion
        Path.cwd(),
    ]
    for c in candidates:
        if (c / "launcher.py").exists() or (c / "sylion-pipeline").exists():
            return c
    return Path.home() / "sylion"


def _find_runtime_db() -> Path | None:
    home = _find_sylion_home()
    candidates = [
        Path(os.getenv("SYLION_DB_PATH", "")),
        home / "sylion_aeis.db",
        home / "sylion-pipeline" / "sylion_aeis.db",
        Path(__file__).resolve().parent / "sylion_aeis.db",
    ]
    for p in candidates:
        if str(p) and p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_python_version() -> CheckResult:
    """SYL-ENV-001: Python version >= 3.10"""
    t0 = time.monotonic()
    v = sys.version_info
    result = CheckResult(code="SYL-ENV-001", name="Python version")
    if v >= (3, 10):
        result.message = f"Python {v.major}.{v.minor}.{v.micro}"
    elif v >= (3, 9):
        result.severity = Severity.WARN
        result.message = f"Python {v.major}.{v.minor} — recommended >=3.10"
        result.suggestion = "Upgrade to Python 3.10+ for full asyncio support"
    else:
        result.severity = Severity.ERROR
        result.message = f"Python {v.major}.{v.minor} — requires >=3.10"
        result.suggestion = "Install Python 3.10 or newer"
    result.elapsed_ms = (time.monotonic() - t0) * 1000
    return result


def check_dependencies() -> list[CheckResult]:
    """SYL-ENV-002..N: Check required Python packages."""
    required = {
        "fastapi": ("SYL-ENV-002", "FastAPI"),
        "uvicorn": ("SYL-ENV-003", "Uvicorn"),
        "dotenv": ("SYL-ENV-004", "python-dotenv", "python-dotenv"),
        "argon2": ("SYL-ENV-005", "argon2-cffi", "argon2-cffi"),
        "aiofiles": ("SYL-ENV-006", "aiofiles"),
        "pydantic": ("SYL-ENV-007", "Pydantic"),
        "yaml": ("SYL-ENV-008", "PyYAML", "pyyaml"),
        "litellm": ("SYL-ENV-009", "LiteLLM"),
        "rich": ("SYL-ENV-010", "Rich"),
        "httpx": ("SYL-ENV-011", "HTTPX"),
        "pypdf": ("SYL-ENV-012", "pypdf"),
        "docx": ("SYL-ENV-013", "python-docx", "python-docx"),
        "multipart": ("SYL-ENV-014", "python-multipart", "python-multipart"),
    }
    results = []
    for import_name, info in required.items():
        code = info[0]
        label = info[1]
        pip_name = info[2] if len(info) > 2 else label.lower()
        t0 = time.monotonic()
        r = CheckResult(code=code, name=f"Dependency: {label}")
        try:
            mod = importlib.import_module(import_name)
            ver = getattr(mod, "__version__", getattr(mod, "VERSION", "?"))
            r.message = f"{label} {ver}"
        except ImportError:
            r.severity = Severity.ERROR
            r.message = f"{label} not installed"
            r.suggestion = f"pip install {pip_name}"
            # Attempt auto-fix (subprocess.run to avoid PIPE deadlock — Council v5.8.7)
            try:
                pip_result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pip_name, "-q"],
                    capture_output=True, text=True, timeout=180,  # Council v5.8.7: 180s for heavy deps
                )
                if pip_result.returncode != 0:
                    r.auto_fix = AutoFixResult.FAILED
                    err_tail = (pip_result.stderr or "").strip()[-500:]
                    r.fix_description = f"pip exit {pip_result.returncode}: {err_tail}"
                else:
                    # Verify import actually works after install (Council v5.8.7)
                    importlib.invalidate_caches()
                    try:
                        importlib.import_module(import_name)
                        r.auto_fix = AutoFixResult.FIXED
                        r.fix_description = f"Auto-installed {pip_name}"
                        r.severity = Severity.WARN  # Downgrade — fixed but note it
                        r.message = f"{label} was missing — auto-installed"
                    except ImportError:
                        r.auto_fix = AutoFixResult.FAILED
                        r.fix_description = f"{pip_name} installed but still not importable"
            except Exception as exc:
                r.auto_fix = AutoFixResult.FAILED
                r.fix_description = f"pip install failed: {exc}"
        r.elapsed_ms = (time.monotonic() - t0) * 1000
        results.append(r)
    return results


def check_database() -> CheckResult:
    """SYL-DB-001: Runtime database exists and is accessible."""
    t0 = time.monotonic()
    r = CheckResult(code="SYL-DB-001", name="AEIS runtime database")
    db_path = _find_runtime_db()
    if not db_path:
        r.severity = Severity.WARN
        r.message = "Runtime database file not found (set SYLION_DB_PATH or start AEIS backend)"
        r.elapsed_ms = (time.monotonic() - t0) * 1000
        return r
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        # Check critical tables exist
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        required_tables = []
        missing = [t for t in required_tables if t not in tables]
        if missing:
            r.severity = Severity.ERROR
            r.message = f"Missing tables: {', '.join(missing)}"
            r.suggestion = "Run AEIS backend once to initialize DB, or set SYLION_DB_PATH to the active database"
        else:
            r.message = f"OK — {len(tables)} tables, size {db_path.stat().st_size / 1024:.0f} KB"
        conn.close()
    except Exception as exc:
        r.severity = Severity.ERROR
        r.message = f"Database error: {exc}"
        r.suggestion = "Check file permissions or delete and recreate the database"
    r.elapsed_ms = (time.monotonic() - t0) * 1000
    return r


def check_api_keys() -> list[CheckResult]:
    """SYL-KEY-001..N: Check API keys are configured."""
    keys_info = {
        "ANTHROPIC_API_KEY": ("SYL-KEY-001", "Anthropic (Claude)", "sk-ant-", True),
        "OPENAI_API_KEY": ("SYL-KEY-002", "OpenAI (GPT)", "sk-", True),
        "GOOGLE_API_KEY": ("SYL-KEY-003", "Google (Gemini)", "AIza", True),
        "DEEPSEEK_API_KEY": ("SYL-KEY-004", "DeepSeek", "sk-", False),
        "XAI_API_KEY": ("SYL-KEY-005", "xAI (Grok)", "xai-", False),
        "PERPLEXITY_API_KEY": ("SYL-KEY-006", "Perplexity (Sonar)", "pplx-", False),
    }
    results = []
    for env_var, (code, label, prefix, critical) in keys_info.items():
        t0 = time.monotonic()
        r = CheckResult(code=code, name=f"API Key: {label}")
        value = os.getenv(env_var, "")

        # Fallback to env var
        if not value:
            value = os.environ.get(env_var, "")

        if value:
            if value.startswith(prefix) or prefix == "AIza":
                r.message = f"Configured ({value[:6]}...{value[-4:]})"
            else:
                r.severity = Severity.WARN
                r.message = f"Set but unexpected prefix (expected '{prefix}*')"
                r.suggestion = f"Verify the {label} key is correct"
        else:
            if critical:
                r.severity = Severity.ERROR
                r.message = "Not configured — pipeline cannot use this provider"
                r.suggestion = f"Set {env_var} in .env or process environment"
            else:
                r.severity = Severity.WARN
                r.message = "Not configured (optional provider)"
                r.suggestion = f"Set {env_var} in .env if you want to use {label}"
        r.elapsed_ms = (time.monotonic() - t0) * 1000
        results.append(r)
    return results


def check_port(port: int = 8421) -> CheckResult:
    """SYL-NET-001: Runtime port availability."""
    t0 = time.monotonic()
    r = CheckResult(code="SYL-NET-001", name=f"Runtime port {port}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        if result == 0:
            r.message = f"Port {port} is LISTENING (runtime is running)"
        else:
            r.severity = Severity.WARN
            r.message = f"Port {port} is not listening (runtime not running)"
    except Exception as exc:
        r.severity = Severity.WARN
        r.message = f"Could not check port: {exc}"
    r.elapsed_ms = (time.monotonic() - t0) * 1000
    return r


def check_runtime_alive(port: int = 8421) -> CheckResult:
    """SYL-RUN-001: Runtime responds to health endpoint."""
    t0 = time.monotonic()
    r = CheckResult(code="SYL-RUN-001", name="Runtime health endpoint")
    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get("status") == "ok":
                r.message = "Runtime responding OK"
            else:
                r.severity = Severity.WARN
                r.message = f"Runtime responded but status={data.get('status')}"
    except Exception as exc:
        r.severity = Severity.WARN
        r.message = f"Runtime not responding: {exc}"
        r.suggestion = "Start AEIS runtime: python -m sylion.server --host 127.0.0.1"
    r.elapsed_ms = (time.monotonic() - t0) * 1000
    return r


def check_config_files() -> list[CheckResult]:
    """SYL-CFG-001..N: Check critical config files."""
    home = _find_sylion_home()
    pipeline_dir = home / "sylion-pipeline"
    if not pipeline_dir.exists():
        pipeline_dir = home

    files = {
        "SYL-CFG-001": ("agents.yaml", pipeline_dir / "agents.yaml", True),
        "SYL-CFG-002": (".env", home / ".env", True),
        "SYL-CFG-003": ("config.py", pipeline_dir / "config.py", True),
        "SYL-CFG-004": ("orchestrator.py", pipeline_dir / "orchestrator.py", True),
        "SYL-CFG-005": ("launcher.py", home / "launcher.py", True),
        "SYL-CFG-006": ("devices.json", home / "devices.json", False),
    }
    results = []
    for code, (name, path, required) in files.items():
        t0 = time.monotonic()
        r = CheckResult(code=code, name=f"Config: {name}")
        if path.exists():
            size = path.stat().st_size
            r.message = f"Found ({size} bytes)"
            # Validate YAML / JSON if applicable
            if name.endswith(".yaml"):
                try:
                    import yaml
                    with open(path) as f:
                        yaml.safe_load(f)
                    r.message += " — valid YAML"
                except Exception as exc:
                    r.severity = Severity.ERROR
                    r.message += f" — YAML parse error: {exc}"
            elif name.endswith(".json"):
                try:
                    json.loads(path.read_text())
                    r.message += " — valid JSON"
                except Exception as exc:
                    r.severity = Severity.ERROR
                    r.message += f" — JSON parse error: {exc}"
            elif name == ".env":
                content = path.read_text(encoding="utf-8", errors="replace")
                key_count = sum(1 for line in content.splitlines()
                                if line.strip() and not line.startswith("#") and "=" in line)
                r.message += f" — {key_count} entries"
        else:
            if required:
                r.severity = Severity.ERROR
                r.message = f"Not found at {path}"
                r.suggestion = f"File {name} is required — reinstall or copy from template"
            else:
                r.severity = Severity.WARN
                r.message = f"Not found (optional)"
        r.elapsed_ms = (time.monotonic() - t0) * 1000
        results.append(r)
    return results


def check_filesystem_permissions() -> list[CheckResult]:
    """SYL-FS-001..N: Check write permissions on critical directories."""
    home = _find_sylion_home()
    dirs = {
        "SYL-FS-001": ("Logs directory", home / "logs"),
        "SYL-FS-002": ("Runtime DB directory", home / "sylion-pipeline"),
        "SYL-FS-003": ("Workspace uploads", home / "sylion-pipeline" / "workspace_uploads"),
    }
    results = []
    for code, (name, path) in dirs.items():
        t0 = time.monotonic()
        r = CheckResult(code=code, name=f"Filesystem: {name}")
        if path.exists():
            if os.access(path, os.W_OK):
                r.message = f"Writable — {path}"
            else:
                r.severity = Severity.ERROR
                r.message = f"Not writable — {path}"
                r.suggestion = f"Fix permissions: chmod 755 {path}"
                # Attempt fix
                try:
                    path.chmod(0o755)
                    r.auto_fix = AutoFixResult.FIXED
                    r.fix_description = "Applied chmod 755"
                    r.severity = Severity.WARN
                except Exception:
                    r.auto_fix = AutoFixResult.FAILED
        else:
            try:
                path.mkdir(parents=True, exist_ok=True)
                r.message = f"Created — {path}"
                r.auto_fix = AutoFixResult.FIXED
                r.fix_description = f"Created missing directory {path}"
            except Exception as exc:
                r.severity = Severity.ERROR
                r.message = f"Cannot create: {exc}"
                r.suggestion = f"Create manually: mkdir -p {path}"
        r.elapsed_ms = (time.monotonic() - t0) * 1000
        results.append(r)
    return results


def check_venv() -> CheckResult:
    """SYL-ENV-020: Check if running inside a virtual environment."""
    t0 = time.monotonic()
    r = CheckResult(code="SYL-ENV-020", name="Virtual environment")
    if sys.prefix != sys.base_prefix:
        r.message = f"Active venv: {sys.prefix}"
    else:
        r.severity = Severity.WARN
        r.message = "Not running in a virtual environment"
        r.suggestion = "Recommended: python -m venv .venv && source .venv/bin/activate"
    r.elapsed_ms = (time.monotonic() - t0) * 1000
    return r


# ---------------------------------------------------------------------------
# Auto-fix: common pipeline crash patterns
# ---------------------------------------------------------------------------

_KNOWN_CRASH_PATTERNS: list[tuple[str, str, str]] = [
    # (regex pattern in traceback, error code, fix description)
    (
        r"'SignalingServer'.*'_max_rooms'",
        "SYL-PIPE-001",
        "AttributeError: _max_rooms → max_rooms (fixed in v5.8)"
    ),
    (
        r"ModuleNotFoundError.*No module named '(\w+)'",
        "SYL-PIPE-002",
        "Missing Python module — auto-install attempted"
    ),
    (
        r"OperationalError.*no such table: (\w+)",
        "SYL-PIPE-003",
        "Missing database table - runtime may need re-initialization"
    ),
    (
        r"Address already in use.*:(\d+)",
        "SYL-PIPE-004",
        "Port already in use — attempt to kill stale process"
    ),
    (
        r"SQLITE_BUSY|database is locked",
        "SYL-PIPE-005",
        "SQLite busy — concurrent access conflict"
    ),
    (
        r"litellm\..*enterprise",
        "SYL-PIPE-006",
        "LiteLLM enterprise module error — stub installed"
    ),
    (
        r"Brak klucza API.*ustaw (\w+)",
        "SYL-PIPE-007",
        "Missing API key for provider"
    ),
    # --- v5.8.1: Extended TypeError / AttributeError diagnostics ---
    (
        r"TypeError: ([\w.]+)\.__init__\(\) got an unexpected keyword argument '(\w+)'",
        "SYL-PIPE-010",
        "Constructor called with wrong keyword argument"
    ),
    (
        r"TypeError: ([\w.]+)\(\) got an unexpected keyword argument '(\w+)'",
        "SYL-PIPE-011",
        "Function called with wrong keyword argument"
    ),
    (
        r"TypeError: ([\w.]+)\(\) missing (\d+) required positional argument",
        "SYL-PIPE-012",
        "Function missing required arguments"
    ),
    (
        r"TypeError: ([\w.]+)\(\) takes (\d+) positional arguments? but (\d+) (?:was|were) given",
        "SYL-PIPE-013",
        "Function received too many positional arguments"
    ),
    (
        r"TypeError: cannot unpack non-(?:iterable|sequence) (\w+)(?: object)?",
        "SYL-PIPE-014",
        "Unpacking error — return value shape mismatch"
    ),
    (
        r"TypeError: '(\w+)' object is not (subscriptable|iterable|callable)",
        "SYL-PIPE-015",
        "Type mismatch — object used incorrectly"
    ),
    (
        r"AttributeError: '(\w+)' object has no attribute '(\w+)'",
        "SYL-PIPE-020",
        "Missing attribute on object — API mismatch or outdated code"
    ),
    (
        r"AttributeError: module '([\w.]+)' has no attribute '(\w+)'",
        "SYL-PIPE-021",
        "Missing module attribute — version mismatch or wrong import"
    ),
    (
        r"KeyError: '?([^'\n]+)'?",
        "SYL-PIPE-030",
        "Missing dictionary key — schema or config mismatch"
    ),
    (
        r"ValueError: (.*?)(?:\n|$)",
        "SYL-PIPE-031",
        "Invalid value encountered"
    ),
    (
        r"OperationalError.*no such column: (\w+)",
        "SYL-PIPE-032",
        "Missing database column — schema out of date"
    ),
    (
        r"ImportError: cannot import name '(\w+)' from '([\w.]+)'",
        "SYL-PIPE-033",
        "Cannot import symbol — version mismatch between modules"
    ),
    (
        r"ConnectionRefusedError.*localhost:(\d+)",
        "SYL-PIPE-040",
        "Connection refused — target service not running"
    ),
    (
        r"FileNotFoundError.*No such file.*'([^']+)'",
        "SYL-PIPE-041",
        "Missing file or directory"
    ),
    (
        r"PermissionError.*'([^']+)'",
        "SYL-PIPE-042",
        "Permission denied on file or directory"
    ),
    (
        r"RuntimeError: (?:asyncio\.run|This event loop|cannot be called from)",
        "SYL-PIPE-050",
        "Asyncio event loop conflict — nested run() or wrong thread"
    ),
    (
        r"RecursionError: maximum recursion depth exceeded",
        "SYL-PIPE-051",
        "Infinite recursion detected"
    ),
    (
        r"MemoryError",
        "SYL-PIPE-052",
        "Out of memory — reduce batch size or increase RAM"
    ),
    # --- v5.8.1: LLM-specific crash patterns ---
    # 060-069: reserved for LLM / API integration errors
    (
        r"(?:pydantic[._])?ValidationError[:\s]",
        "SYL-PIPE-060",
        "Pydantic validation error — likely malformed LLM response"
    ),
    (
        r"(?:json\.decoder\.)?JSONDecodeError",
        "SYL-PIPE-061",
        "JSON decode error — malformed response from LLM or API"
    ),
    (
        r"(?:httpx\.)?(?:ConnectTimeout|ReadTimeout|TimeoutError|ConnectError)",
        "SYL-PIPE-062",
        "Network timeout / connection error to external API"
    ),
]


def _extract_crash_location(log_text: str) -> str:
    """Extract the file:line from the last traceback frame before the error."""
    # Look for:  File "/path/to/file.py", line 42, in function_name
    # Also match 'in <module>' (top-level crashes)
    frames = re.findall(
        r'File "([^"]+)", line (\d+), in ([^\r\n]+)',
        log_text,
    )
    if frames:
        path, line, func = frames[-1]  # Last frame is the crash site
        # Normalize both Unix and Windows path separators
        normalized = path.replace("\\", "/")
        parts = normalized.rsplit("/", 2)
        short_path = parts[-2:] if len(parts) >= 2 else parts
        return f"{'/'.join(short_path)}:{line} in {func.strip()}()"
    return ""


def _build_suggestion_for_type_error(
    code: str, match: re.Match, log_text: str
) -> tuple[str, str]:
    """Build (suggestion, message) for TypeError patterns.

    Returns targeted fix instructions based on the specific error variant.
    """
    location = _extract_crash_location(log_text)
    loc_hint = f" [{location}]" if location else ""

    if code == "SYL-PIPE-010":
        cls_name = match.group(1)
        kwarg = match.group(2)
        short_cls = cls_name.rsplit('.', 1)[-1]
        suggestion = (
            f"Klasa {cls_name}.__init__() nie przyjmuje parametru '{kwarg}'.\n"
            f"    Sprawdź sygnaturę konstruktora: grep -rn 'class {short_cls}' *.py\n"
            f"    Może '{kwarg}' należy do podrzędnego obiektu (np. Store, Engine) "
            f"a nie do {cls_name} bezpośrednio."
        )
        message = f"TypeError: {cls_name}() got unexpected kwarg '{kwarg}'{loc_hint}"
        return suggestion, message

    elif code == "SYL-PIPE-011":
        func_name = match.group(1)
        kwarg = match.group(2)
        suggestion = (
            f"Funkcja {func_name}() nie przyjmuje parametru '{kwarg}'.\n"
            f"    Sprawdź sygnaturę: grep -n 'def {func_name}' *.py\n"
            f"    Może parametr zmienił nazwę lub został przeniesiony."
        )
        message = f"TypeError: {func_name}() got unexpected kwarg '{kwarg}'{loc_hint}"
        return suggestion, message

    elif code == "SYL-PIPE-012":
        func_name = match.group(1)
        n_missing = match.group(2)
        suggestion = (
            f"Funkcja {func_name}() wymaga {n_missing} argumentów, których nie podano.\n"
            f"    Sprawdź wywołanie i sygnaturę: grep -n '{func_name}(' *.py"
        )
        message = f"TypeError: {func_name}() missing {n_missing} required arg(s){loc_hint}"
        return suggestion, message

    elif code == "SYL-PIPE-013":
        func_name = match.group(1)
        expected = match.group(2)
        got = match.group(3)
        suggestion = (
            f"Funkcja {func_name}() przyjmuje {expected} argumentów, a dostała {got}.\n"
            f"    Sprawdź wywołanie — prawdopodobnie trzeba użyć keyword args."
        )
        message = f"TypeError: {func_name}() takes {expected} args but {got} given{loc_hint}"
        return suggestion, message

    elif code == "SYL-PIPE-015":
        obj_type = match.group(1)
        action = match.group(2)
        suggestion = (
            f"Obiekt typu '{obj_type}' nie jest {action}.\n"
            f"    Sprawdź co zwraca funkcja — może None zamiast listy/dict."
        )
        message = f"TypeError: '{obj_type}' object is not {action}{loc_hint}"
        return suggestion, message

    log.warning("_build_suggestion_for_type_error: unhandled code %s", code)
    return ("", "")


# ---------------------------------------------------------------------------
# Crash handler functions (dispatch-based architecture)
# ---------------------------------------------------------------------------

_BUILTIN_TYPES = frozenset({
    "NoneType", "int", "str", "float", "list",
    "dict", "tuple", "set", "bool", "bytes",
})


def _handle_missing_module(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-002: Auto-install missing Python module."""
    module_name = match.group(1)
    r.suggestion = f"pip install {module_name}"
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", module_name, "-q"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=60,
        )
        r.auto_fix = AutoFixResult.FIXED
        r.fix_description = f"Auto-installed {module_name}"
    except Exception:
        r.auto_fix = AutoFixResult.FAILED


def _handle_missing_table(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-003: Re-initialize database."""
    table_name = match.group(1)
    r.suggestion = "Restart AEIS backend to re-initialize DB, or point SYLION_DB_PATH at a clean runtime DB"
    try:
        from db import init_db
        init_db()
        r.auto_fix = AutoFixResult.FIXED
        r.fix_description = f"Re-initialized database (missing table: {table_name})"
    except Exception:
        r.auto_fix = AutoFixResult.ATTEMPTED
        r.fix_description = "Could not auto-initialize DB"


def _handle_port_in_use(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-004: Port already in use."""
    port_str = match.group(1)
    r.suggestion = f"Kill process on port {port_str}: fuser -k {port_str}/tcp"


def _handle_missing_api_key(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-007: Missing API key."""
    env_var = match.group(1)
    r.suggestion = f"Set {env_var} in .env or process environment"


def _handle_type_error(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-010..015: TypeError variants."""
    suggestion, message = _build_suggestion_for_type_error(
        r.code, match, log_text
    )
    if suggestion:
        r.suggestion = suggestion
    if message:
        r.message = message


def _handle_unpack_error(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-014: Cannot unpack non-iterable."""
    obj_type = match.group(1)
    location = _extract_crash_location(log_text)
    r.suggestion = (
        f"Nie można rozpakować obiektu typu '{obj_type}'.\n"
        f"    Sprawdź co zwraca funkcja — może tuple zamiast dict."
    )
    if location:
        r.message = f"Unpacking error on {obj_type} [{location}]"


def _handle_attr_error_object(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-020: Missing attribute on object."""
    obj_type = match.group(1)
    attr_name = match.group(2)
    location = _extract_crash_location(log_text)
    if obj_type in _BUILTIN_TYPES:
        r.suggestion = (
            f"Obiekt typu '{obj_type}' nie ma atrybutu '{attr_name}'.\n"
            f"    Sprawdź czy zmienna nie jest None/pusta przed użyciem atrybutu.\n"
            f"    Szukaj: grep -rn '.{attr_name}' *.py"
        )
    else:
        r.suggestion = (
            f"Obiekt '{obj_type}' nie ma atrybutu '{attr_name}'.\n"
            f"    Sprawdź definicję klasy: grep -rn 'class {obj_type}' *.py\n"
            f"    Może atrybut zmienił nazwę w nowszej wersji."
        )
    if location:
        r.message = f"'{obj_type}' has no attribute '{attr_name}' [{location}]"


def _handle_attr_error_module(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-021: Missing module attribute."""
    module_name = match.group(1)
    attr_name = match.group(2)
    r.suggestion = (
        f"Moduł '{module_name}' nie eksportuje '{attr_name}'.\n"
        f"    Może trzeba zaktualizować pakiet: pip install --upgrade {module_name.split('.')[0]}\n"
        f"    Lub nazwa zmieniła się w nowej wersji."
    )


def _handle_key_error(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-030: Missing dictionary key."""
    key_name = match.group(1).strip("'\" ")
    location = _extract_crash_location(log_text)
    r.suggestion = (
        f"Brakujący klucz '{key_name}' w słowniku.\n"
        f"    Sprawdź źródło danych — może schemat DB lub odpowiedź API zmieniła się.\n"
        f"    Użyj dict.get('{key_name}', default) zamiast dict['{key_name}']."
    )
    if location:
        r.message = f"KeyError: '{key_name}' [{location}]"


def _handle_value_error(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-031: Invalid value."""
    detail = match.group(1)[:100]
    location = _extract_crash_location(log_text)
    r.suggestion = (
        f"Nieprawidłowa wartość: {detail}\n"
        f"    Sprawdź dane wejściowe i walidację w tym miejscu."
    )
    if location:
        r.message = f"ValueError: {detail} [{location}]"


def _handle_missing_column(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-032: Missing database column."""
    col_name = match.group(1)
    r.suggestion = (
        f"Kolumna '{col_name}' nie istnieje w tabeli.\n"
        f"    Wskaz czysta runtime DB przez SYLION_DB_PATH i uruchom ponownie (auto-migracja),\n"
        f"    lub dodaj ręcznie: ALTER TABLE <table> ADD COLUMN {col_name} TEXT DEFAULT '';"
    )


def _handle_import_error(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-033: Cannot import symbol."""
    symbol = match.group(1)
    module = match.group(2)
    r.suggestion = (
        f"Symbol '{symbol}' nie istnieje w module '{module}'.\n"
        f"    Sprawdź wersję pakietu: pip show {module.split('.')[0]}\n"
        f"    Może trzeba zaktualizować albo poprawić import."
    )


def _handle_conn_refused(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-040: Connection refused."""
    port_str = match.group(1)
    r.suggestion = (
        f"Połączenie odrzucone na localhost:{port_str}.\n"
        f"    Sprawdź czy usługa na tym porcie jest uruchomiona.\n"
        f"    Jeżeli to Ollama: ollama serve\n"
        f"    Jezeli to AEIS runtime: python -m sylion.server --host 127.0.0.1"
    )


def _handle_file_not_found(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-041: Missing file."""
    filepath = match.group(1)
    r.suggestion = (
        f"Nie znaleziono pliku: {filepath}\n"
        f"    Sprawdź ścieżkę i uprawnienia."
    )


def _handle_permission_error(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-042: Permission denied."""
    filepath = match.group(1)
    r.suggestion = (
        f"Brak uprawnień do: {filepath}\n"
        f"    chmod 755 {filepath}  lub  chown $(whoami) {filepath}"
    )


def _handle_asyncio_conflict(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-050: Asyncio event loop conflict."""
    r.suggestion = (
        "Konflikt asyncio event loop — prawdopodobnie podwójne asyncio.run().\n"
        "    Użyj 'await' zamiast asyncio.run() wewnątrz istniejącego loop."
    )


def _handle_recursion(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-051: Infinite recursion."""
    location = _extract_crash_location(log_text)
    base = ("Nieskończona rekurencja.\n"
            "    Sprawdź warunki stopu w funkcji rekurencyjnej.")
    r.suggestion = base + (f"\n    Lokalizacja: {location}" if location else "")


def _handle_memory_error(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-052: Out of memory."""
    r.severity = Severity.CRITICAL
    r.suggestion = (
        "Brak pamięci (MemoryError).\n"
        "    Zmniejsz rozmiar batcha, zamknij inne procesy,\n"
        "    lub zwiększ RAM/swap."
    )


def _handle_validation_error(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-060: Pydantic ValidationError — LLM response parsing."""
    location = _extract_crash_location(log_text)
    r.suggestion = (
        "Błąd walidacji Pydantic — prawdopodobnie LLM zwrócił niepoprawny format.\n"
        "    Sprawdź schemat modelu Pydantic i format odpowiedzi LLM.\n"
        "    Dodaj retry z promptem naprawczym lub fallback na surowy tekst."
    )
    if location:
        r.message = f"ValidationError [{location}]"


def _handle_json_decode_error(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-061: JSON decode error — malformed LLM/API response."""
    location = _extract_crash_location(log_text)
    r.suggestion = (
        "Błąd dekodowania JSON — odpowiedź API/LLM nie jest poprawnym JSON-em.\n"
        "    Sprawdź surową odpowiedź (logi debug).\n"
        "    Dodaj walidację json.loads() z try/except i retry."
    )
    if location:
        r.message = f"JSONDecodeError [{location}]"


def _handle_network_timeout(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """SYL-PIPE-062: Network timeout to external API."""
    r.suggestion = (
        "Timeout połączenia z zewnętrznym API.\n"
        "    Sprawdź połączenie sieciowe i dostępność usługi.\n"
        "    Zwiększ timeout w konfiguracji (httpx/litellm).\n"
        "    Jeżeli to Ollama lokalne: sprawdź czy ollama serve działa."
    )


def _handle_default(
    r: CheckResult, match: re.Match, log_text: str
) -> None:
    """Default handler for patterns without specific logic."""
    r.suggestion = "Sprawdź dokumentację SYLION lub zgłoś problem."


# Handler registry: maps error codes to handler functions
_CRASH_HANDLERS: dict[str, Any] = {
    "SYL-PIPE-002": _handle_missing_module,
    "SYL-PIPE-003": _handle_missing_table,
    "SYL-PIPE-004": _handle_port_in_use,
    "SYL-PIPE-007": _handle_missing_api_key,
    "SYL-PIPE-010": _handle_type_error,
    "SYL-PIPE-011": _handle_type_error,
    "SYL-PIPE-012": _handle_type_error,
    "SYL-PIPE-013": _handle_type_error,
    "SYL-PIPE-014": _handle_unpack_error,
    "SYL-PIPE-015": _handle_type_error,
    "SYL-PIPE-020": _handle_attr_error_object,
    "SYL-PIPE-021": _handle_attr_error_module,
    "SYL-PIPE-030": _handle_key_error,
    "SYL-PIPE-031": _handle_value_error,
    "SYL-PIPE-032": _handle_missing_column,
    "SYL-PIPE-033": _handle_import_error,
    "SYL-PIPE-040": _handle_conn_refused,
    "SYL-PIPE-041": _handle_file_not_found,
    "SYL-PIPE-042": _handle_permission_error,
    "SYL-PIPE-050": _handle_asyncio_conflict,
    "SYL-PIPE-051": _handle_recursion,
    "SYL-PIPE-052": _handle_memory_error,
    "SYL-PIPE-060": _handle_validation_error,
    "SYL-PIPE-061": _handle_json_decode_error,
    "SYL-PIPE-062": _handle_network_timeout,
}

# Family mapping: specific codes block overlapping generic fallbacks
_FAMILY_BLOCKS: dict[str, set[str]] = {
    "SYL-PIPE-001": {"SYL-PIPE-020"},  # Specific AttributeError blocks generic
    "SYL-PIPE-010": {"SYL-PIPE-011"},  # __init__() kwarg blocks generic func kwarg
}


def diagnose_crash(log_text: str) -> list[CheckResult]:
    """Analyze crash log and return diagnosed issues with auto-fix attempts.

    Recognizes 25 crash patterns including TypeError, AttributeError,
    KeyError, ImportError, OperationalError, runtime errors, and
    LLM-specific errors (Pydantic, JSON, network timeouts).
    Extracts crash location (file:line) from traceback for targeted advice.
    Uses priority-based matching: specific patterns block overlapping generic ones.
    Uses dispatch-based handler architecture for scalability.
    """
    results = []
    blocked_codes: set[str] = set()

    for pattern, code, description in _KNOWN_CRASH_PATTERNS:
        # Skip if a more specific pattern already blocked this code
        if code in blocked_codes:
            continue

        match = re.search(pattern, log_text, re.IGNORECASE)
        if not match:
            continue

        # Register blocks: if this code blocks others, mark them
        blocks = _FAMILY_BLOCKS.get(code)
        if blocks:
            blocked_codes.update(blocks)

        r = CheckResult(
            code=code,
            name=description,
            severity=Severity.ERROR,
            message=f"Detected: {match.group(0)[:200]}",
        )

        # Dispatch to handler
        handler = _CRASH_HANDLERS.get(code, _handle_default)
        handler(r, match, log_text)

        results.append(r)

    return results


# ---------------------------------------------------------------------------
# Device checks (SYL-DEV)
# ---------------------------------------------------------------------------

def check_adb_available() -> CheckResult:
    """SYL-DEV-001: Check if ADB is installed and accessible."""
    t0 = time.monotonic()
    r = CheckResult(code="SYL-DEV-001", name="ADB binary")
    try:
        proc = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            ver_line = proc.stdout.strip().split('\n')[0] if proc.stdout else "unknown"
            r.message = f"Available — {ver_line}"
        else:
            r.severity = Severity.WARN
            r.message = "ADB found but returned error"
            r.suggestion = "Reinstall android-tools: sudo apt install adb"
    except FileNotFoundError:
        r.severity = Severity.WARN
        r.message = "ADB not installed"
        r.suggestion = (
            "Windows: pobierz Platform Tools ze https://developer.android.com/tools/releases/platform-tools "
            "i dodaj folder do PATH. Linux: sudo apt install android-tools-adb"
        )
    except subprocess.TimeoutExpired:
        r.severity = Severity.WARN
        r.message = "ADB timed out"
    except Exception as exc:
        r.severity = Severity.WARN
        r.message = f"ADB check failed: {exc}"
    r.elapsed_ms = (time.monotonic() - t0) * 1000
    return r


def check_pixel_connected() -> CheckResult:
    """SYL-DEV-002: Check if Pixel device is connected via USB/ADB."""
    t0 = time.monotonic()
    r = CheckResult(code="SYL-DEV-002", name="Pixel 9 (USB/ADB)")
    # PATCH 4 / RC-08 / SYL-PIX-005: import PIXEL_9_FAMILY for model validation
    try:
        from pixel_provision import PIXEL_9_FAMILY as _PIX9  # type: ignore[import]
        _PIX9_LOWER = {m.lower().strip() for m in _PIX9}
    except Exception:
        _PIX9_LOWER = set()
    try:
        proc = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            r.severity = Severity.WARN
            r.message = "ADB daemon not responding"
            r.suggestion = "Run: adb start-server"
            r.elapsed_ms = (time.monotonic() - t0) * 1000
            return r
        lines = proc.stdout.strip().split('\n')
        devices = []
        for line in lines[1:]:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                devices.append((parts[0], parts[1]))
        connected = [d for d in devices if d[1] == "device"]
        unauthorized = [d for d in devices if d[1] == "unauthorized"]
        if connected:
            serial = connected[0][0]
            # Try to get device model
            model = "unknown"
            try:
                m = subprocess.run(
                    ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
                    capture_output=True, text=True, timeout=10
                )
                if m.returncode == 0 and m.stdout.strip():
                    model = m.stdout.strip()
            except Exception:
                pass
            # PATCH 4 / RC-08 / SYL-PIX-005: walidacja modelu w PIXEL_9_FAMILY
            if _PIX9_LOWER and model.lower().strip() not in _PIX9_LOWER:
                r.severity = Severity.WARN
                r.message = (
                    f"WRONG_MODEL: podłączono '{model}' (serial: {serial}) — "
                    "oczekiwano Pixel 9 family"
                )
                r.suggestion = (
                    "Odłącz i podłącz Pixel 9 / 9 Pro / 9 Pro XL / 9 Pro Fold / 9a"
                )
            else:
                r.message = f"Connected — {model} (serial: {serial})"
        elif unauthorized:
            r.severity = Severity.WARN
            r.message = f"Device found but UNAUTHORIZED (serial: {unauthorized[0][0]})"
            r.suggestion = "Accept USB debugging prompt on the phone"
        else:
            r.severity = Severity.WARN
            r.message = "No device connected"
            r.suggestion = "Connect Pixel via USB, enable USB debugging. In WSL2: use usbipd to attach USB"
    except FileNotFoundError:
        r.severity = Severity.WARN
        r.message = "ADB not installed — cannot check"
    except Exception as exc:
        r.severity = Severity.WARN
        r.message = f"Check failed: {exc}"
    r.elapsed_ms = (time.monotonic() - t0) * 1000
    return r


def check_router_connected() -> CheckResult:
    """SYL-DEV-003: Check if GL.iNet Mudi V2 router is reachable."""
    t0 = time.monotonic()
    r = CheckResult(code="SYL-DEV-003", name="Router GL.iNet Mudi V2 (SSH)")
    # Read router IP from devices.json or use default
    router_ip = "192.168.8.1"
    home = _find_sylion_home()
    devices_json = home / "devices.json"
    if devices_json.exists():
        try:
            cfg = json.loads(devices_json.read_text(encoding="utf-8"))
            for dev in cfg.get("devices", []):
                if dev.get("type") == "router":
                    router_ip = dev.get("ip", router_ip)
                    break
        except Exception:
            pass

    # Step 1: ping check (fast)
    _ping_cmd = (
        ["ping", "-n", "1", "-w", "3000", router_ip]
        if sys.platform == "win32"
        else ["ping", "-c", "1", "-W", "3", router_ip]
    )
    try:
        proc = subprocess.run(
            _ping_cmd,
            capture_output=True, text=True, timeout=5
        )
        if proc.returncode != 0:
            r.severity = Severity.WARN
            r.message = f"Router {router_ip} not reachable (ping failed)"
            r.suggestion = f"Check Ethernet/WiFi connection to router at {router_ip}"
            r.elapsed_ms = (time.monotonic() - t0) * 1000
            return r
    except Exception:
        pass  # ping may not be available, try SSH directly

    # Step 2: SSH check
    try:
        proc = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-o", "BatchMode=yes", f"root@{router_ip}", "echo", "SYLION_OK"],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0 and "SYLION_OK" in proc.stdout:
            r.message = f"Connected — root@{router_ip} (SSH OK)"
        elif proc.returncode == 255:
            r.severity = Severity.WARN
            r.message = f"Router {router_ip} reachable but SSH failed"
            r.suggestion = "Check SSH keys or password auth on router"
        else:
            r.severity = Severity.WARN
            r.message = f"Router {router_ip} — SSH returned code {proc.returncode}"
    except FileNotFoundError:
        r.severity = Severity.WARN
        r.message = "SSH not available"
    except subprocess.TimeoutExpired:
        r.severity = Severity.WARN
        r.message = f"SSH to {router_ip} timed out"
    except Exception as exc:
        r.severity = Severity.WARN
        r.message = f"Router check failed: {exc}"
    r.elapsed_ms = (time.monotonic() - t0) * 1000
    return r


def check_pipeline_files() -> list[CheckResult]:
    """SYL-PIPE-001..N: Check pipeline module files exist."""
    home = _find_sylion_home()
    pipeline_dir = home / "sylion-pipeline"
    if not pipeline_dir.exists():
        pipeline_dir = home

    files = {
        "SYL-PIPE-001": ("orchestrator.py", pipeline_dir / "orchestrator.py"),
        "SYL-PIPE-002": ("config.py", pipeline_dir / "config.py"),
        "SYL-PIPE-003": ("agents.yaml", pipeline_dir / "agents.yaml"),
    }
    results = []
    for code, (name, path) in files.items():
        t0 = time.monotonic()
        r = CheckResult(code=code, name=f"Pipeline file: {name}")
        if path.exists():
            size = path.stat().st_size
            r.message = f"Found ({size} bytes)"
        else:
            r.severity = Severity.WARN
            r.message = f"Not found at {path}"
            r.suggestion = f"Ensure {name} exists in the pipeline directory"
        r.elapsed_ms = (time.monotonic() - t0) * 1000
        results.append(r)
    return results


def check_fido2_key() -> CheckResult:
    """SYL-DEV-004: Check FIDO2/U2F security key readiness.

    Pixel 8/9 has ONE USB-C port. During normal operation it's occupied by
    the ADB cable to the laptop. FIDO2 enrollment happens via HumanGate
    during the provisioning pipeline (Step 7.5):

        1. Pipeline pauses and asks operator to disconnect ADB cable
        2. Operator inserts FIDO2 key into Pixel's USB-C port
        3. Operator touches fingerprint sensor on key
        4. Operator removes FIDO2 key and reconnects ADB cable

    This health check only verifies that a FIDO2 key is physically present
    somewhere (plugged into laptop USB) as a readiness indicator.
    Actual enrollment is handled by pixel_provision.step_fido2_enroll().
    """
    t0 = time.monotonic()
    r = CheckResult(code="SYL-DEV-004", name="FIDO2 Security Key")

    fido_usb_found = False
    key_info = ""

    # Check local USB for FIDO2 keys connected to laptop
    # NOTE: 18d1 (Google) excluded — Pixel ADB uses the same vendor ID.
    # Google Titan keys have specific PIDs (503c, 5283) but filtering by
    # PID is fragile. Better to not false-positive on Pixel ADB.
    fido_vendors = {
        "1050": "Yubico (YubiKey)",
        "1209": "SoloKeys",
        "096e": "Feitian",
        "1ea8": "Thetis",
        "2581": "HyperFIDO",
        "20a0": "Nitrokey",
    }
    try:
        proc = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            for line in proc.stdout.strip().split('\n'):
                for vid, name in fido_vendors.items():
                    if f" {vid}:" in line.lower() or f"id {vid}:" in line.lower():
                        fido_usb_found = True
                        key_info = f"{name} (USB w laptopie) — {line.strip()}"
                        break
                if fido_usb_found:
                    break
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if fido_usb_found:
        r.message = f"Wykryty w USB laptopa \u2014 {key_info}"
        r.suggestion = (
            "Klucz FIDO2 wykryty. Podczas provisioningu pipeline poprosi Cie "
            "o wyjecie klucza z laptopa i wlozenie do Pixela (HumanGate Step 7.5)."
        )
    else:
        # NOT a warning — key doesn't need to be plugged in yet.
        # It just needs to be physically available when pipeline asks.
        r.message = "Klucz FIDO2 nie wpi\u0119ty w USB laptopa \u2014 OK, pipeline poprosi w odpowiednim momencie"
        r.suggestion = (
            "Upewnij si\u0119, \u017ce masz klucz FIDO2 (np. YubiKey) fizycznie pod r\u0119k\u0105. "
            "Pipeline poprosi o wlo\u017cenie go do Pixela w HumanGate Step 7.5. "
            "Klucz nie musi by\u0107 wpi\u0119ty teraz."
        )

    r.elapsed_ms = (time.monotonic() - t0) * 1000
    return r


# ---------------------------------------------------------------------------
# Full system health check
# ---------------------------------------------------------------------------

def run_full_check(port: int = 8421) -> HealthReport:
    """Run all health checks and return a complete report."""
    report = HealthReport()

    # Environment
    report.add(check_python_version())
    report.add(check_venv())
    for r in check_dependencies():
        report.add(r)

    # Database
    report.add(check_database())

    # API Keys
    for r in check_api_keys():
        report.add(r)

    # Config files
    for r in check_config_files():
        report.add(r)

    # Filesystem
    for r in check_filesystem_permissions():
        report.add(r)

    # Network
    report.add(check_port(port))
    report.add(check_runtime_alive(port))

    # Devices
    report.add(check_adb_available())
    report.add(check_pixel_connected())
    report.add(check_router_connected())
    report.add(check_fido2_key())

    report.generate_summary()
    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("SYLION Health Check\n" + "=" * 40)
    report = run_full_check()
    print(report.summary)
    print()

    # Save report
    home = _find_sylion_home()
    report_path = home / "logs" / "health_report.json"
    try:
        report.save(report_path)
        print(f"Report saved to: {report_path}")
    except Exception as exc:
        print(f"Could not save report: {exc}")

    # Exit code
    if report.overall in (Severity.ERROR, Severity.CRITICAL):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
