"""SYLION AEIS v2 — REST routes for cron-mode dashboard widget.

Phase 0 endpoint (prefix ``/api/v1/cron``):

    GET    /status                              — cron-mode metrics

Returns a small JSON payload powering the operator-overview widget
``CronModeMetrics``: total ``[v2 cron]`` commits, last 5 commit subjects,
and approximate disk usage of the ``docs/v2/_drafts`` tree (KB).

The endpoint is intentionally defensive — every shell call (``git log``)
and filesystem walk is wrapped so the widget renders gracefully on
machines without git on PATH (CI runners, frozen containers) or where
the drafts directory has been pruned.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from sylion.security.rbac import requires_role

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cron", tags=["cron_v2"])


def _git_log_lines(grep: str, limit: int | None = None) -> list[str]:
    """Run ``git log --oneline --grep <pattern>`` and return lines.

    Defensive: returns ``[]`` on any subprocess error (git missing,
    not a repo, timeout) — the caller treats that as zero commits.
    """
    cmd = ["git", "log", "--oneline", "--grep", grep]
    if limit is not None:
        cmd += ["-n", str(limit)]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=5)
    except Exception:
        return []
    return [line for line in out.strip().splitlines() if line]


def _drafts_size_kb(root: Path) -> int:
    """Sum of all regular file sizes under ``root`` in kilobytes.

    Returns 0 when the directory does not exist or any walk error
    surfaces (permission denied, broken symlinks, etc.).
    """
    try:
        if not root.exists() or not root.is_dir():
            return 0
        total = 0
        for f in root.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                continue
        return total // 1024
    except Exception:
        return 0


@router.get("/status", dependencies=[Depends(requires_role("operator"))])
def cron_status() -> dict[str, Any]:
    """Return cron-mode metrics for the operator-overview widget."""
    recent_lines = _git_log_lines("[v2 cron]", limit=10)
    recent_commits: list[dict[str, str]] = []
    for line in recent_lines:
        if " " not in line:
            continue
        h, subject = line.split(" ", 1)
        recent_commits.append({"hash": h, "subject": subject})

    total_count = len(_git_log_lines("[v2 cron]"))
    drafts_root = Path("docs/v2/_drafts")

    return {
        "total_commits": total_count,
        "recent_commits": recent_commits[:5],
        "drafts_size_kb": _drafts_size_kb(drafts_root),
    }
