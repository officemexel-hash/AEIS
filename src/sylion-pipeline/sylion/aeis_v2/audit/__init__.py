"""SYLION AEIS v2 — daily-rotated audit log abstraction.

This package provides a single shared writer for every v2 JSONL audit
surface. Each consumer picks a stable ``name`` (e.g. ``"apply_audit"``,
``"routing_audit"``) and the writer takes care of UTC-anchored daily
rotation under ``logs/v2/<name>/YYYY-MM-DD.jsonl``.

Mirrors the per-day rotation pattern already shipped by
``sylion.aeis_v2.terminal.replay`` (W18 G3) — this module generalises it
so every v2 audit surface can stop accumulating in a single ever-growing
file.

Public API:

    from sylion.aeis_v2.audit import (
        append_audit_row,
        list_audit_days,
        read_audit_slice,
        rotated_path,
        AUDIT_ROOT,
    )

See ``rotated_writer.py`` for full docstrings + the migration plan
listing the five existing v2 audit emitters that should switch to this
abstraction in a follow-up cron round.
"""
from __future__ import annotations

from sylion.aeis_v2.audit.rotated_writer import (
    AUDIT_ROOT,
    append_audit_row,
    list_audit_days,
    read_audit_slice,
    rotated_path,
)

__all__ = [
    "AUDIT_ROOT",
    "append_audit_row",
    "list_audit_days",
    "read_audit_slice",
    "rotated_path",
]
