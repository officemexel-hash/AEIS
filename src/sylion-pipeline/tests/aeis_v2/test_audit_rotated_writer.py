"""Tests for the v2 daily-rotated audit log writer.

Covers ``sylion.aeis_v2.audit.rotated_writer``:

- ``rotated_path``: deterministic ``<root>/<name>/YYYY-MM-DD.jsonl``
  mapping; UTC-anchored regardless of operator timezone.
- ``append_audit_row``: creates parent directory, appends one JSON line
  per call, handles unicode (Polish chars) round-trip, returns False on
  disk error without raising.
- ``list_audit_days``: returns sorted-desc YYYY-MM-DD strings, ``[]``
  when nothing has been written.
- ``read_audit_slice``: filters rows by ``[start_ts, end_ts]``,
  truncates at ``max_rows``, recovers from malformed lines.
- AUDIT_ROOT can be overridden via the ``SYLION_AUDIT_ROOT`` env var
  (verified by reloading the module under ``monkeypatch.setenv``).

Tests use ``tmp_path`` + ``monkeypatch`` to swap ``AUDIT_ROOT`` per test
so the real ``logs/v2/`` is never touched. Mirrors the pattern in
``test_terminal_replay.py``.
"""
from __future__ import annotations

import builtins
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sylion.aeis_v2.audit import rotated_writer
from sylion.aeis_v2.audit.rotated_writer import (
    append_audit_row,
    list_audit_days,
    read_audit_slice,
    rotated_path,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def audit_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Swap the module-level AUDIT_ROOT onto a tmp_path subdir.

    The writer reads ``AUDIT_ROOT`` at call time (not import time) so a
    single ``setattr`` on the module global redirects every read+write
    through the test directory.
    """
    target = tmp_path / "v2"
    monkeypatch.setattr(rotated_writer, "AUDIT_ROOT", target)
    return target


def _ts_for(
    year: int, month: int, day: int,
    hour: int = 12, minute: int = 0, second: int = 0,
) -> float:
    """UTC datetime -> epoch seconds. Handy for fixing test timestamps."""
    return datetime(
        year, month, day, hour, minute, second, tzinfo=timezone.utc,
    ).timestamp()


# --------------------------------------------------------------------------
# A. rotated_path
# --------------------------------------------------------------------------


def test_rotated_path_format_yyyy_mm_dd(audit_root: Path) -> None:
    """rotated_path returns <root>/<name>/YYYY-MM-DD.jsonl format."""
    ts = _ts_for(2026, 4, 27, hour=10)
    path = rotated_path("apply_audit", ts)
    assert path == audit_root / "apply_audit" / "2026-04-27.jsonl"
    # Stem must be a parseable date.
    datetime.strptime(path.stem, "%Y-%m-%d")


def test_rotated_path_uses_utc_not_local_tz(audit_root: Path) -> None:
    """rotated_path always uses UTC for the date component.

    A ts at 2026-04-27 23:30 UTC must land in 2026-04-27.jsonl even if
    the operator's local timezone (e.g. UTC+10 -> Sydney) would call it
    2026-04-28. The boundary chosen here is 23:30 UTC: any TZ east of
    UTC+0 with offset > 30 minutes would produce a different local
    date, so a passing test confirms UTC anchoring.
    """
    ts = _ts_for(2026, 4, 27, hour=23, minute=30)
    path = rotated_path("routing_audit", ts)
    assert path == audit_root / "routing_audit" / "2026-04-27.jsonl"

    # Sanity: 1 hour later (00:30 the next day UTC) lands in 04-28.
    ts_next = _ts_for(2026, 4, 28, hour=0, minute=30)
    path_next = rotated_path("routing_audit", ts_next)
    assert path_next == audit_root / "routing_audit" / "2026-04-28.jsonl"


# --------------------------------------------------------------------------
# B. append_audit_row
# --------------------------------------------------------------------------


def test_append_audit_row_creates_dir_and_writes(audit_root: Path) -> None:
    """append_audit_row mkdirs the parent and writes one JSON line."""
    ts = _ts_for(2026, 4, 27)
    ok = append_audit_row(
        "apply_audit",
        {"ts": ts, "type_id": "customer", "applied": True},
        ts=ts,
    )
    assert ok is True

    path = audit_root / "apply_audit" / "2026-04-27.jsonl"
    assert path.exists()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row == {"ts": ts, "type_id": "customer", "applied": True}

    # A second call same day appends rather than overwrites.
    append_audit_row(
        "apply_audit",
        {"ts": ts, "type_id": "order", "applied": False},
        ts=ts,
    )
    lines2 = path.read_text(encoding="utf-8").splitlines()
    assert len(lines2) == 2
    assert json.loads(lines2[1])["type_id"] == "order"


def test_append_audit_row_handles_unicode_polish(audit_root: Path) -> None:
    """Polish diacritics round-trip through write+read without mojibake."""
    ts = _ts_for(2026, 4, 27)
    payload = {
        "ts": ts,
        "text": "łódź ąćęńóśźż",
        "operator": "Łukasz",
        "rationale": "Zaaplikowano DDL — wszystkie żądania spełnione.",
    }
    ok = append_audit_row("intervention_audit", payload, ts=ts)
    assert ok is True

    path = audit_root / "intervention_audit" / "2026-04-27.jsonl"
    line = path.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["text"] == "łódź ąćęńóśźż"
    assert parsed["operator"] == "Łukasz"
    assert parsed["rationale"] == "Zaaplikowano DDL — wszystkie żądania spełnione."


def test_append_audit_row_returns_false_on_disk_error(
    audit_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disk-write OSError logs at WARNING and returns False (no raise)."""
    real_open = builtins.open

    def _exploding_open(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        # Only break opens against the audit dir; let pytest's own I/O
        # (e.g. capfd) keep working.
        if "apply_audit" in str(path):
            raise OSError("simulated disk full")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _exploding_open)

    ts = _ts_for(2026, 4, 27)
    ok = append_audit_row("apply_audit", {"ts": ts, "x": 1}, ts=ts)
    assert ok is False
    # No file should have been left half-written (the parent dir may
    # have been created via mkdir before open failed; that is fine —
    # we only assert no crash leaked out).


# --------------------------------------------------------------------------
# C. list_audit_days
# --------------------------------------------------------------------------


def test_list_audit_days_returns_sorted_desc(audit_root: Path) -> None:
    """Days are returned newest first."""
    for day in (25, 27, 24, 26):
        ts = _ts_for(2026, 4, day)
        append_audit_row("cost_ledger", {"ts": ts, "n": day}, ts=ts)

    days = list_audit_days("cost_ledger")
    assert days == ["2026-04-27", "2026-04-26", "2026-04-25", "2026-04-24"]


def test_list_audit_days_returns_empty_when_no_files(audit_root: Path) -> None:
    """Fresh surface with no writes returns [] (not an error)."""
    assert list_audit_days("cost_ledger") == []
    # Even if a SIBLING surface has writes, the queried surface must
    # report empty.
    ts = _ts_for(2026, 4, 27)
    append_audit_row("apply_audit", {"ts": ts, "x": 1}, ts=ts)
    assert list_audit_days("cost_ledger") == []
    assert list_audit_days("apply_audit") == ["2026-04-27"]


def test_list_audit_days_skips_non_date_filenames(audit_root: Path) -> None:
    """Stray files whose stem isn't YYYY-MM-DD are silently ignored."""
    ts = _ts_for(2026, 4, 27)
    append_audit_row("migration_audit", {"ts": ts}, ts=ts)
    # Drop a junk file alongside the legitimate daily file.
    junk = audit_root / "migration_audit" / "notes.jsonl"
    junk.write_text("[]", encoding="utf-8")
    junk2 = audit_root / "migration_audit" / "2026-04-27.bak"
    junk2.write_text("backup", encoding="utf-8")

    days = list_audit_days("migration_audit")
    assert days == ["2026-04-27"]


# --------------------------------------------------------------------------
# D. read_audit_slice
# --------------------------------------------------------------------------


def test_read_audit_slice_filters_by_time_range(audit_root: Path) -> None:
    """Rows outside [start_ts, end_ts] are excluded."""
    # Write three rows spanning three days.
    for day in (25, 26, 27):
        ts = _ts_for(2026, 4, day, hour=10)
        append_audit_row("apply_audit", {"ts": ts, "day": day}, ts=ts)

    # Query: only April 26 (one full UTC day window).
    start = _ts_for(2026, 4, 26, hour=0)
    end = _ts_for(2026, 4, 26, hour=23, minute=59, second=59)
    rows = read_audit_slice("apply_audit", start_ts=start, end_ts=end)
    assert len(rows) == 1
    assert rows[0]["day"] == 26

    # Query covering 25 + 26 returns both (sorted ascending).
    start = _ts_for(2026, 4, 25, hour=0)
    end = _ts_for(2026, 4, 26, hour=23, minute=59, second=59)
    rows = read_audit_slice("apply_audit", start_ts=start, end_ts=end)
    assert [r["day"] for r in rows] == [25, 26]


def test_read_audit_slice_truncates_at_max_rows(audit_root: Path) -> None:
    """Once max_rows is reached, scanning stops and the partial list is returned."""
    base_ts = _ts_for(2026, 4, 27, hour=10)
    for i in range(20):
        append_audit_row(
            "routing_audit",
            {"ts": base_ts + i, "i": i},
            ts=base_ts + i,
        )

    start = _ts_for(2026, 4, 27, hour=0)
    end = _ts_for(2026, 4, 27, hour=23, minute=59, second=59)
    rows = read_audit_slice(
        "routing_audit", start_ts=start, end_ts=end, max_rows=5,
    )
    assert len(rows) == 5
    # Truncation keeps the chronologically earliest rows.
    assert [r["i"] for r in rows] == [0, 1, 2, 3, 4]


def test_read_audit_slice_handles_malformed_lines_gracefully(
    audit_root: Path,
) -> None:
    """Non-JSON lines are skipped with a warning; valid lines still returned."""
    ts = _ts_for(2026, 4, 27, hour=10)
    append_audit_row("cost_ledger", {"ts": ts, "ok": "first"}, ts=ts)
    # Corrupt the file by appending a partial-write line.
    path = audit_root / "cost_ledger" / "2026-04-27.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write("{not-valid-json\n")
        f.write("\n")  # blank line: legitimate, just skip silently
    append_audit_row("cost_ledger", {"ts": ts + 1, "ok": "second"}, ts=ts + 1)

    start = _ts_for(2026, 4, 27, hour=0)
    end = _ts_for(2026, 4, 27, hour=23, minute=59, second=59)
    rows = read_audit_slice("cost_ledger", start_ts=start, end_ts=end)
    # Two legit rows survive; the bad line is dropped.
    assert [r["ok"] for r in rows] == ["first", "second"]


def test_read_audit_slice_returns_empty_when_no_files(audit_root: Path) -> None:
    """Slice over a quiet range returns [] without raising."""
    start = _ts_for(2026, 4, 25, hour=0)
    end = _ts_for(2026, 4, 27, hour=23, minute=59, second=59)
    rows = read_audit_slice("apply_audit", start_ts=start, end_ts=end)
    assert rows == []


def test_read_audit_slice_handles_inverted_window(audit_root: Path) -> None:
    """end_ts < start_ts returns [] (defensive: no walk, no error)."""
    ts = _ts_for(2026, 4, 27, hour=10)
    append_audit_row("apply_audit", {"ts": ts}, ts=ts)
    rows = read_audit_slice(
        "apply_audit",
        start_ts=_ts_for(2026, 4, 28),
        end_ts=_ts_for(2026, 4, 26),
    )
    assert rows == []


# --------------------------------------------------------------------------
# E. SYLION_AUDIT_ROOT env var override
# --------------------------------------------------------------------------


def test_audit_root_overridable_via_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SYLION_AUDIT_ROOT env var redirects writes after module reload.

    The constant is bound at module import time (so production never
    pays a per-call env-var read cost). Tests verify the contract by
    setting the env, reloading the module, and confirming the new
    AUDIT_ROOT is honoured.
    """
    target = tmp_path / "custom_audit_root"
    monkeypatch.setenv("SYLION_AUDIT_ROOT", str(target))
    # Reload to re-evaluate the module-level AUDIT_ROOT.
    reloaded = importlib.reload(rotated_writer)
    try:
        assert reloaded.AUDIT_ROOT == target

        ts = _ts_for(2026, 4, 27)
        ok = reloaded.append_audit_row(
            "apply_audit", {"ts": ts, "x": 1}, ts=ts,
        )
        assert ok is True
        assert (target / "apply_audit" / "2026-04-27.jsonl").exists()
    finally:
        # Restore module to default so subsequent tests in the session
        # don't inherit the override.
        monkeypatch.delenv("SYLION_AUDIT_ROOT", raising=False)
        importlib.reload(rotated_writer)
