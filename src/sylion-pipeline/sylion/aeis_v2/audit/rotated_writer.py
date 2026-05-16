"""Daily-rotated JSONL audit log writer.

All v2 audit emitters should use this instead of hardcoded single-file
paths. The replay module (``sylion.aeis_v2.terminal.replay``) already
does per-day rotation; this module generalises the pattern so every
audit surface (``apply_audit``, ``routing_audit``, ``intervention_audit``,
``migration_audit``, ``cost_ledger``, …) shares one well-tested writer.

File layout
-----------
::

    <root>/<name>/YYYY-MM-DD.jsonl

- ``root``: ``logs/v2/`` (overridable via env ``SYLION_AUDIT_ROOT``).
- ``name``: stable per-surface identifier such as ``apply_audit``,
  ``routing_audit``, ``intervention_audit``, ``migration_audit``,
  ``cost_ledger``.
- The daily file rotates at UTC midnight (timestamps interpreted in UTC
  so a single ``ts`` always maps to one deterministic file regardless
  of operator timezone).

Best-effort semantics
---------------------

Failures (full disk, permission denied, race on directory creation)
log at WARNING level and never raise. This matches the behaviour of
the existing ``_emit_*_audit`` helpers — a missing audit row is always
preferable to a crashed apply / route / intervention.

Migration plan
--------------

The following five emit functions still write to single-file JSONL
paths and should be migrated to ``append_audit_row`` in a future cron
round (consumer migration is intentionally NOT done here — it is
surgical because each call site has its own row schema and existing
tests assert against the old single-file path):

1. ``sylion.aeis_v2.ontology.applier._emit_apply_audit``
   - current: ``logs/v2/apply_audit.jsonl``
   - target:  ``append_audit_row("apply_audit", row)``

2. ``sylion.aeis_v2.deployment.federation._emit_routing_audit``
   - current: ``logs/v2/routing_audit.jsonl``
   - target:  ``append_audit_row("routing_audit", row)``

3. ``sylion.api.terminal_routes._emit_intervention_audit``
   - current: ``logs/v2/intervention_audit.jsonl``
   - target:  ``append_audit_row("intervention_audit", row)``

4. ``sylion.aeis_v2.ontology.migration._emit_migration_audit``
   - current: ``logs/v2/migration_audit.jsonl``
   - target:  ``append_audit_row("migration_audit", row)``

5. ``sylion.aeis_v2.deployment.cost_ledger.emit_cost_record``
   - current: ``logs/v2/cost_ledger.jsonl``
   - target:  ``append_audit_row("cost_ledger", row)``

Each consumer should also update the ``read_audit`` helper(s) in its
test suite to walk daily files via :func:`read_audit_slice` instead of
reading a single file directly. The migration must keep at least one
test asserting the on-disk layout is ``<root>/<name>/<date>.jsonl`` so
no consumer regresses to the single-file pattern.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Storage location
# --------------------------------------------------------------------------
#
# ``AUDIT_ROOT`` is read from the env at IMPORT time so production
# deployments can move the log volume without code changes. Tests that
# need a different root can either:
#
#   1. Set ``SYLION_AUDIT_ROOT`` in the environment before importing
#      (``importlib.reload`` rebinds the module-level constant), or
#   2. Use ``monkeypatch.setattr(rotated_writer, "AUDIT_ROOT", tmp_path)``
#      which is the pattern already used by the replay tests.
#
# Both styles are exercised in ``tests/aeis_v2/test_audit_rotated_writer.py``.
AUDIT_ROOT: Path = Path(os.environ.get("SYLION_AUDIT_ROOT", "logs/v2"))

# Date format for daily rotation. UTC, matching the replay module so
# operators never have to translate between two different rotation
# anchors.
_DATE_FMT = "%Y-%m-%d"


# --------------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------------


def rotated_path(name: str, ts: float) -> Path:
    """Return ``<AUDIT_ROOT>/<name>/YYYY-MM-DD.jsonl`` for the given epoch ts.

    The date is computed in UTC so a single ``ts`` always maps to one
    deterministic file regardless of operator timezone. This is the
    single source of truth for "where does an audit row land?" — every
    other helper in this module composes from it.
    """
    date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime(_DATE_FMT)
    return AUDIT_ROOT / name / f"{date_str}.jsonl"


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------


def append_audit_row(
    name: str,
    row: dict[str, Any],
    *,
    ts: float | None = None,
) -> bool:
    """Append a row to today's ``<name>/YYYY-MM-DD.jsonl``.

    Args:
        name: stable surface identifier (e.g. ``"apply_audit"``). Used
            as the immediate subdirectory under ``AUDIT_ROOT``.
        row: JSON-serialisable dict — the audit row payload.
        ts: epoch seconds for date selection. When ``None``, the current
            UTC wallclock is used. Tests pass a fixed value to assert on
            the resulting path.

    Returns:
        ``True`` on successful flush to disk, ``False`` on any failure.

    Best-effort semantics: every failure mode (full disk, permission
    denied, race on directory creation, JSON serialisation error, broken
    OS file handle) logs at WARNING level and returns ``False`` rather
    than raising. Callers that must distinguish success from silent loss
    can branch on the return value; most just ignore it.
    """
    if ts is None:
        ts = datetime.now(timezone.utc).timestamp()
    try:
        path = rotated_path(name, ts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort, must not raise
        log.warning("audit %s: write failed (%s)", name, exc)
        return False


# --------------------------------------------------------------------------
# Day enumeration (for `/audit/<name>/days` endpoints)
# --------------------------------------------------------------------------


def list_audit_days(name: str) -> list[str]:
    """List ``YYYY-MM-DD`` files for an audit name. Returns sorted desc.

    Newest day first so the operator UI's date picker shows recent
    activity at the top. Returns ``[]`` when the audit directory
    doesn't exist (fresh deploy, never written) or has no daily files.

    Files whose stem isn't a valid ``YYYY-MM-DD`` are silently skipped —
    we don't want a stray ``.jsonl`` (e.g. one renamed during forensic
    analysis) to pollute the day list.
    """
    audit_dir = AUDIT_ROOT / name
    if not audit_dir.exists():
        return []
    days: list[str] = []
    for child in audit_dir.iterdir():
        if not child.is_file():
            continue
        if not child.name.endswith(".jsonl"):
            continue
        stem = child.stem
        try:
            datetime.strptime(stem, _DATE_FMT)
        except ValueError:
            continue
        days.append(stem)
    days.sort(reverse=True)
    return days


# --------------------------------------------------------------------------
# Slice query
# --------------------------------------------------------------------------


def read_audit_slice(
    name: str,
    *,
    start_ts: float,
    end_ts: float,
    max_rows: int = 10_000,
) -> list[dict[str, Any]]:
    """Walk daily files in ``[start_ts, end_ts]`` window, parse rows, return up to max_rows.

    Args:
        name: surface identifier (must match what ``append_audit_row``
            wrote with).
        start_ts: epoch seconds, inclusive lower bound.
        end_ts: epoch seconds, inclusive upper bound. ``end_ts <
            start_ts`` returns ``[]``.
        max_rows: hard cap; once reached, scanning stops and the partial
            list is returned. Defaults to 10k to match the replay
            module's MAX_REPLAY_SLICE_SIZE.

    Returns:
        List of row dicts whose ``ts`` falls in the requested window,
        sorted chronologically. Rows without a numeric ``ts`` field are
        silently skipped (defensive — the caller is responsible for
        always writing a ``ts`` but we don't crash on legacy data).

    Robustness:

    - Missing daily files in the range are silently skipped.
    - Malformed JSON lines are logged at WARNING and skipped — one bad
      line never poisons a whole slice.
    - File-open errors (permission denied, race) are logged and skipped.
    - The walk is hard-capped at 366 days to avoid pathologically huge
      ranges; a query spanning more than a year is almost certainly a
      bug.
    """
    if end_ts < start_ts:
        return []
    if max_rows <= 0:
        max_rows = 10_000

    out: list[dict[str, Any]] = []

    # Walk whole days from start to end, anchored on UTC midnight.
    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    cur = start_dt
    days_walked = 0
    max_days = 366

    truncated = False
    while cur <= end_dt and days_walked < max_days:
        if truncated:
            break
        path = AUDIT_ROOT / name / f"{cur.strftime(_DATE_FMT)}.jsonl"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            row = json.loads(stripped)
                        except json.JSONDecodeError as exc:
                            log.warning(
                                "audit %s: skipping malformed line in %s (%s)",
                                name, path, exc,
                            )
                            continue
                        row_ts = row.get("ts")
                        if not isinstance(row_ts, (int, float)):
                            continue
                        if row_ts < start_ts or row_ts > end_ts:
                            continue
                        if len(out) >= max_rows:
                            truncated = True
                            break
                        out.append(row)
            except FileNotFoundError:
                # Race: file vanished between exists() and open(). Treat
                # as a quiet day.
                pass
            except OSError as exc:
                log.warning("audit %s: failed to read %s (%s)", name, path, exc)
        cur = datetime.fromtimestamp(cur.timestamp() + 86400.0, tz=timezone.utc)
        days_walked += 1

    out.sort(key=lambda r: r.get("ts", 0.0))
    return out


__all__ = [
    "AUDIT_ROOT",
    "append_audit_row",
    "list_audit_days",
    "read_audit_slice",
    "rotated_path",
]
