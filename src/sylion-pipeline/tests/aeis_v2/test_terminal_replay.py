"""W18 G3 step 1 — replay-as-film backend tests.

Covers the storage + read side of the recorded-event log:

- ``record_event`` -> daily JSONL file under ``REPLAY_LOG_DIR`` with
  ``YYYY-MM-DD.jsonl`` rotation.
- ``_replay_log_path_for_ts`` -> deterministic path mapping for any UTC
  epoch timestamp.
- ``_iter_log_files_for_range`` -> walks daily files overlapping a
  query range, skipping non-existent days silently.
- ``get_replay_slice`` -> ordered, filtered, capped slice with a
  ``truncated`` flag.

Tests use ``tmp_path`` + ``monkeypatch`` to swap ``REPLAY_LOG_DIR`` per
test so the real ``logs/v2/terminal_replay/`` is never touched. Mirrors
the pattern in ``tests/aeis_v2/test_terminal_intervention.py`` (which
isolates ``SessionStore`` via the same monkeypatch shape).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sylion.aeis_v2.terminal import replay as replay_mod
from sylion.aeis_v2.terminal.replay import (
    MAX_REPLAY_SLICE_SIZE,
    ReplaySlice,
    _iter_log_files_for_range,
    _replay_log_path_for_ts,
    get_replay_slice,
    list_replay_days,
    record_event,
)
from sylion.aeis_v2.terminal.stream import TerminalEvent


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def replay_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Swap the module-level REPLAY_LOG_DIR onto a tmp_path subdir.

    The replay module reads ``REPLAY_LOG_DIR`` at call time (not at
    import time) so a single ``setattr`` on the module global is enough
    to redirect every read+write through the test directory.
    """
    target = tmp_path / "terminal_replay"
    monkeypatch.setattr(replay_mod, "REPLAY_LOG_DIR", target)
    return target


def _ts_for(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> float:
    """UTC datetime -> epoch seconds. Handy for fixing test timestamps."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp()


def _make_event(
    ts: float,
    *,
    layer: str = "W18",
    message: str = "msg",
    session_id: str = "",
) -> TerminalEvent:
    return TerminalEvent(
        ts=ts,
        layer=layer,
        message=message,
        session_id=session_id,
    )


# --------------------------------------------------------------------------
# A. record_event
# --------------------------------------------------------------------------


def test_record_event_writes_jsonl_to_daily_file(replay_dir: Path) -> None:
    """record_event must persist a JSON-serialised event to the day's file."""
    ts = _ts_for(2026, 4, 15, hour=10)
    evt = _make_event(ts, layer="W15", message="manifest applied")
    record_event(evt)

    expected = replay_dir / "2026-04-15.jsonl"
    assert expected.exists(), "daily JSONL should be created on first record"

    lines = expected.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    # All canonical TerminalEvent fields must be in the persisted dict
    # so the slice query later can filter on any of them.
    assert row["ts"] == ts
    assert row["layer"] == "W15"
    assert row["message"] == "manifest applied"
    assert "event_id" in row
    assert "extra" in row


def test_replay_log_path_uses_yyyy_mm_dd_format(replay_dir: Path) -> None:
    """The path helper must round-trip ts -> YYYY-MM-DD with UTC anchoring."""
    ts = _ts_for(2026, 1, 7)
    p = _replay_log_path_for_ts(ts)
    assert p.name == "2026-01-07.jsonl"
    assert p.parent == replay_dir

    # Boundary: midnight UTC sits on the new day, not the old one.
    midnight = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    p2 = _replay_log_path_for_ts(midnight)
    assert p2.name == "2026-06-01.jsonl"


# --------------------------------------------------------------------------
# B. get_replay_slice -- happy paths
# --------------------------------------------------------------------------


def test_get_replay_slice_returns_events_in_time_range(replay_dir: Path) -> None:
    """A slice query returns only events within [start_ts, end_ts]."""
    base = _ts_for(2026, 4, 20, hour=12)
    record_event(_make_event(base + 0, message="inside-1"))
    record_event(_make_event(base + 10, message="inside-2"))
    record_event(_make_event(base + 1000, message="outside-after"))

    slice_ = get_replay_slice(start_ts=base - 5, end_ts=base + 100)
    assert isinstance(slice_, ReplaySlice)
    assert slice_.total_count == 2
    assert slice_.truncated is False
    msgs = [e["message"] for e in slice_.events]
    assert msgs == ["inside-1", "inside-2"]
    # Chronological order is a hard contract -- replay is "what happened
    # in order", not "rows in some arbitrary on-disk order".
    tss = [e["ts"] for e in slice_.events]
    assert tss == sorted(tss)


def test_get_replay_slice_filters_by_session_id(replay_dir: Path) -> None:
    """session_id filter only returns events tagged with that session."""
    base = _ts_for(2026, 4, 21, hour=8)
    record_event(_make_event(base + 0, session_id="sess-A", message="A1"))
    record_event(_make_event(base + 1, session_id="sess-B", message="B1"))
    record_event(_make_event(base + 2, session_id="sess-A", message="A2"))
    record_event(_make_event(base + 3, session_id="", message="orphan"))

    slice_ = get_replay_slice(
        start_ts=base - 5, end_ts=base + 100, session_id="sess-A",
    )
    msgs = [e["message"] for e in slice_.events]
    assert msgs == ["A1", "A2"]
    assert slice_.filter_session_id == "sess-A"


def test_get_replay_slice_filters_by_layer(replay_dir: Path) -> None:
    """layer filter only returns events with that layer string."""
    base = _ts_for(2026, 4, 22, hour=14)
    record_event(_make_event(base + 0, layer="W15", message="m1"))
    record_event(_make_event(base + 1, layer="W18", message="t1"))
    record_event(_make_event(base + 2, layer="W15", message="m2"))

    slice_ = get_replay_slice(
        start_ts=base - 5, end_ts=base + 100, layer="W15",
    )
    msgs = [e["message"] for e in slice_.events]
    assert msgs == ["m1", "m2"]
    assert slice_.filter_layer == "W15"


# --------------------------------------------------------------------------
# C. get_replay_slice -- truncation + robustness
# --------------------------------------------------------------------------


def test_get_replay_slice_truncates_at_max_events(replay_dir: Path) -> None:
    """Slice rows beyond max_events must be cut and ``truncated`` flipped."""
    base = _ts_for(2026, 4, 23, hour=9)
    for i in range(15):
        record_event(_make_event(base + i, message=f"e{i:02d}"))

    slice_ = get_replay_slice(
        start_ts=base - 5, end_ts=base + 1000, max_events=5,
    )
    assert slice_.total_count == 5
    assert slice_.truncated is True
    assert len(slice_.events) == 5
    # Truncation must take the chronologically-earliest 5 -- the operator
    # cares about "what happened first" when zooming into an incident.
    msgs = [e["message"] for e in slice_.events]
    assert msgs == ["e00", "e01", "e02", "e03", "e04"]


def test_get_replay_slice_handles_missing_log_files_gracefully(
    replay_dir: Path,
) -> None:
    """A query against a range with zero log files must return empty slice.

    Critical for fresh deployments where ``logs/v2/terminal_replay/``
    does not even exist yet -- the route must NOT 500.
    """
    # Don't create any logs. Query a real range.
    base = _ts_for(2026, 4, 24, hour=12)
    slice_ = get_replay_slice(start_ts=base - 100, end_ts=base + 100)
    assert slice_.total_count == 0
    assert slice_.events == []
    assert slice_.truncated is False


def test_get_replay_slice_skips_malformed_lines(replay_dir: Path) -> None:
    """One bad JSON line must not poison the whole slice."""
    base = _ts_for(2026, 4, 25, hour=11)
    record_event(_make_event(base + 0, message="good-1"))
    # Corrupt the file with a half-line, then continue with another good one.
    path = replay_dir / "2026-04-25.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write("{partial-json,,,\n")
    record_event(_make_event(base + 2, message="good-2"))

    slice_ = get_replay_slice(start_ts=base - 5, end_ts=base + 100)
    assert slice_.total_count == 2
    msgs = [e["message"] for e in slice_.events]
    assert msgs == ["good-1", "good-2"]


# --------------------------------------------------------------------------
# D. _iter_log_files_for_range
# --------------------------------------------------------------------------


def test_iter_log_files_for_range_walks_multiple_days(replay_dir: Path) -> None:
    """A query spanning N calendar days yields up to N daily files."""
    # Three consecutive days, one event each.
    record_event(_make_event(_ts_for(2026, 5, 1, hour=10), message="d1"))
    record_event(_make_event(_ts_for(2026, 5, 2, hour=10), message="d2"))
    record_event(_make_event(_ts_for(2026, 5, 3, hour=10), message="d3"))

    start = _ts_for(2026, 5, 1, hour=0)
    end = _ts_for(2026, 5, 3, hour=23, minute=59)

    files = list(_iter_log_files_for_range(start, end))
    names = sorted(p.name for p in files)
    assert names == ["2026-05-01.jsonl", "2026-05-02.jsonl", "2026-05-03.jsonl"]

    # And the slice query stitches them together correctly, in order.
    slice_ = get_replay_slice(start_ts=start, end_ts=end)
    msgs = [e["message"] for e in slice_.events]
    assert msgs == ["d1", "d2", "d3"]


# --------------------------------------------------------------------------
# E. list_replay_days helper (used by /replay/days endpoint)
# --------------------------------------------------------------------------


def test_list_replay_days_returns_sorted_descending(replay_dir: Path) -> None:
    """list_replay_days enumerates known dates newest-first."""
    record_event(_make_event(_ts_for(2026, 5, 1), message="x"))
    record_event(_make_event(_ts_for(2026, 5, 3), message="y"))
    record_event(_make_event(_ts_for(2026, 5, 2), message="z"))

    days = list_replay_days()
    assert days == ["2026-05-03", "2026-05-02", "2026-05-01"]


def test_list_replay_days_returns_empty_when_dir_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No log dir at all -> ``[]``, never an exception."""
    target = tmp_path / "does-not-exist"
    monkeypatch.setattr(replay_mod, "REPLAY_LOG_DIR", target)
    assert list_replay_days() == []


def test_terminal_exec_records_command_and_result_to_replay(replay_dir: Path) -> None:
    """POST /terminal/exec path must feed W18 replay, not only frontend-local state."""
    from sylion.api.terminal_routes import ExecRequest, exec_command

    session_id = "sess-replay-exec"
    before = time.time() - 1
    response = exec_command(ExecRequest(line="/status", ctx={"session_id": session_id}))
    after = time.time() + 1

    assert response["kind"] == "text"
    slice_ = get_replay_slice(
        start_ts=before,
        end_ts=after,
        session_id=session_id,
        layer="W18",
    )
    messages = [row["message"] for row in slice_.events]
    assert "$ /status" in messages
    assert any("SYLION AEIS" in msg for msg in messages)


# --------------------------------------------------------------------------
# F. ReplaySlice dataclass + to_dict
# --------------------------------------------------------------------------


def test_replay_slice_to_dict_round_trip() -> None:
    """ReplaySlice.to_dict must surface every field the route returns."""
    s = ReplaySlice(
        events=[{"ts": 1.0, "layer": "W18", "message": "m"}],
        start_ts=0.0,
        end_ts=10.0,
        total_count=1,
        truncated=False,
        filter_session_id="abc",
        filter_layer="W18",
    )
    d = s.to_dict()
    assert d["events"] == [{"ts": 1.0, "layer": "W18", "message": "m"}]
    assert d["start_ts"] == 0.0
    assert d["end_ts"] == 10.0
    assert d["total_count"] == 1
    assert d["truncated"] is False
    assert d["filter_session_id"] == "abc"
    assert d["filter_layer"] == "W18"


def test_max_replay_slice_size_constant_is_10000() -> None:
    """Locked at 10k. Phase 0 cap; G3 step 3 lifts via pagination."""
    assert MAX_REPLAY_SLICE_SIZE == 10_000
