"""Runtime Truth endpoint for the operator dashboard.

This route answers one narrow question: which local AEIS runtime is the UI
really connected to right now? It intentionally returns only process metadata,
port status and masked paths. No secrets are read or exposed.
"""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/runtime", tags=["Runtime Truth"])


CHECK_PORTS: tuple[tuple[int, str], ...] = (
    (3001, "frontend Next.js"),
    (8000, "alternatywny backend FastAPI"),
    (8010, "aktywny backend AEIS"),
    (11434, "Ollama"),
)


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _git_value(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _existing_path(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(Path(value).expanduser().resolve())
    except Exception:
        return value


def _db_candidates(cwd: Path) -> list[str]:
    candidates: list[str] = []
    for key in ("SYLION_DB_PATH", "DATABASE_PATH", "AEIS_DB_PATH"):
        resolved = _existing_path(os.environ.get(key))
        if resolved:
            candidates.append(f"{key}={resolved}")
    for pattern in ("*.db", "*.sqlite", "*.sqlite3"):
        for path in cwd.glob(pattern):
            candidates.append(str(path.resolve()))
    return sorted(dict.fromkeys(candidates))[:12]


def _classify(current_port: int | None, port_rows: list[dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []
    busy = {int(row["port"]): bool(row["open"]) for row in port_rows}
    if not busy.get(3001):
        blockers.append("frontend_3001_unreachable")
    if current_port and current_port not in {8010, 8000}:
        warnings.append(f"unexpected_api_port_{current_port}")
    if current_port == 8010 and busy.get(8000):
        warnings.append("port_8000_busy_possible_duplicate_backend")
    if current_port == 8000 and busy.get(8010):
        warnings.append("port_8010_busy_possible_duplicate_backend")
    if not busy.get(8010) and not busy.get(8000):
        blockers.append("no_known_fastapi_port_open")
    if blockers:
        return "blocked", warnings, blockers
    if warnings:
        return "warning", warnings, blockers
    return "ok", warnings, blockers


@router.get("/truth")
def runtime_truth(request: Request) -> dict[str, Any]:
    cwd = Path.cwd().resolve()
    request_port = request.url.port
    port_rows = [
        {"port": port, "label": label, "open": _port_open(port)}
        for port, label in CHECK_PORTS
    ]
    status, warnings, blockers = _classify(request_port, port_rows)
    git_root = _git_value(["rev-parse", "--show-toplevel"], cwd)
    git_branch = _git_value(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    git_commit = _git_value(["rev-parse", "--short", "HEAD"], cwd)
    dirty = _git_value(["status", "--porcelain"], cwd)

    return {
        "status": status,
        "checked_at": time.time(),
        "api": {
            "pid": os.getpid(),
            "port": request_port,
            "url": str(request.base_url).rstrip("/"),
            "cwd": str(cwd),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "frontend": {
            "expected_url": "http://localhost:3001",
            "port_open": next((row["open"] for row in port_rows if row["port"] == 3001), False),
        },
        "database": {
            "mode": "postgres" if os.environ.get("SYLION_DB_URL") else "sqlite/local",
            "candidates": _db_candidates(cwd),
        },
        "git": {
            "root": git_root or str(cwd),
            "branch": git_branch or "unknown",
            "commit": git_commit or "unknown",
            "dirty": bool(dirty),
            "dirty_entries": len([line for line in dirty.splitlines() if line.strip()]),
        },
        "ports": port_rows,
        "warnings": warnings,
        "blockers": blockers,
        "evidence": {
            "source": "live_backend_process",
            "request_host": request.headers.get("host", ""),
            "x_forwarded_host": request.headers.get("x-forwarded-host", ""),
        },
    }
