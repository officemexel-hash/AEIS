"""W18 G3 replay-as-film -- server-side recording + slice query.

Phase 0 of G3:

- Record every ``TerminalEvent`` to a JSONL file per day (rotation:
  ``YYYY-MM-DD.jsonl``).
- Query API: ``get_replay_slice(start_ts, end_ts, *, session_id, layer)``
  returns an ordered event list.
- Limit query to ``MAX_REPLAY_SLICE_SIZE`` events per slice (Phase 0 --
  frontend pagination later). The slice is marked ``truncated=True`` if
  the underlying log set contained more rows than the cap.

G3 step 2 (frontend): SSE-replay endpoint that streams the slice with
client-controlled playback speed (1x/2x/4x/8x) and scrub-to-timestamp.
This module is the storage + read-side of that loop; step 2 will layer
a paced async generator on top of :func:`get_replay_slice` for the
``GET /api/v1/terminal/replay/stream`` endpoint.

Storage shape
-------------

One JSONL file per UTC date in ``logs/v2/terminal_replay/``. Each line is
the JSON-serialised ``TerminalEvent`` (via ``dataclasses.asdict``). The
day boundary is computed from the event's ``ts`` field interpreted as
UTC epoch seconds, so a single event always lands in exactly one daily
file regardless of operator timezone.

Recording is best-effort: any I/O failure (full disk, permissions, race
on directory creation) logs at WARNING level but never raises. A missing
audit row is preferable to a missed broadcast.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sylion.aeis_v2.terminal.stream import TerminalEvent

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Storage location + caps
# --------------------------------------------------------------------------
#
# ``REPLAY_LOG_DIR`` is module-level so tests can ``monkeypatch`` it onto
# a ``tmp_path``. Production override goes through env var
# ``SYLION_TERMINAL_REPLAY_DIR`` so an operator can move the log volume
# without a code change.
def _default_replay_log_dir() -> Path:
    override = os.environ.get("SYLION_TERMINAL_REPLAY_DIR")
    if override:
        return Path(override)
    return Path("logs/v2/terminal_replay")


REPLAY_LOG_DIR: Path = _default_replay_log_dir()

# Phase 0 cap. Frontend pagination (G3 step 3) will lift this.
MAX_REPLAY_SLICE_SIZE: int = 10_000

# Date format for daily rotation. UTC for consistency across operators.
_DATE_FMT = "%Y-%m-%d"


# --------------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------------


def _replay_log_path_for_ts(ts: float) -> Path:
    """Return ``logs/v2/terminal_replay/YYYY-MM-DD.jsonl`` for the given epoch ts.

    The date is computed in UTC so a single ``ts`` always maps to one
    deterministic file regardless of operator timezone.
    """
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return REPLAY_LOG_DIR / f"{dt.strftime(_DATE_FMT)}.jsonl"


def _date_str_for_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(_DATE_FMT)


def _iter_log_files_for_range(start_ts: float, end_ts: float) -> Iterable[Path]:
    """Yield daily log files overlapping the time range, in chronological order.

    Walks the calendar between ``start_ts`` and ``end_ts`` (UTC) one day
    at a time and yields the matching ``YYYY-MM-DD.jsonl`` path if it
    exists on disk. Non-existent days are silently skipped -- a slice
    query crossing a quiet day is normal, not an error.

    Bounded: ``end_ts < start_ts`` yields nothing. ``start_ts == end_ts``
    yields at most one file (the day they fall on).
    """
    if end_ts < start_ts:
        return
    # Anchor both ends on UTC midnight so we walk whole days.
    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    cur = start_dt
    # Safety guard: cap the walk at 365 days to avoid pathologically
    # huge ranges. A query spanning more than a year is almost certainly
    # a bug; it's better to truncate than to enumerate forever.
    max_days = 366
    days_walked = 0
    while cur <= end_dt and days_walked < max_days:
        path = REPLAY_LOG_DIR / f"{cur.strftime(_DATE_FMT)}.jsonl"
        if path.exists():
            yield path
        # Advance one day. Using timestamp arithmetic avoids the
        # ``timedelta`` import for a single use.
        cur = datetime.fromtimestamp(
            cur.timestamp() + 86400.0, tz=timezone.utc,
        )
        days_walked += 1


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------


def record_event(event: TerminalEvent) -> None:
    """Append the event to today's replay log. Best-effort.

    Failure modes that are silently logged at WARNING (never raised):

    - Disk full / quota exceeded
    - Permission denied on the log directory
    - Race on directory creation (handled by ``parents=True, exist_ok=True``)
    - JSON serialisation failure on a malformed ``extra`` payload (we
      fall back to ``str(extra)``)

    Production may flip ``stream.BROADCAST_RECORDS_REPLAY = False`` to
    disable recording entirely if the disk volume is filling up faster
    than the rotation can be drained.
    """
    try:
        REPLAY_LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = _replay_log_path_for_ts(event.ts)
        try:
            payload = asdict(event)
        except Exception:  # noqa: BLE001
            # Defensive: a non-serialisable ``extra`` value would break
            # asdict for the whole event. Reconstruct manually.
            payload = {
                "ts": event.ts,
                "layer": event.layer,
                "message": event.message,
                "module": event.module,
                "model": event.model,
                "host": event.host,
                "severity": event.severity,
                "session_id": event.session_id,
                "cost_usd": event.cost_usd,
                "event_id": event.event_id,
                "extra": str(event.extra),
            }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("replay: record failed (%s)", exc)


# --------------------------------------------------------------------------
# Slice query
# --------------------------------------------------------------------------


@dataclass
class ReplaySlice:
    """Result of a replay slice query.

    ``events`` is the chronologically-ordered list of recorded events
    matching the filters, capped at ``max_events`` rows. ``truncated`` is
    True iff at least one matching row was discarded due to the cap --
    the operator UI uses this to render a "more rows available, narrow
    your filter" banner.

    ``total_count`` is ``len(events)`` (the number of rows actually
    returned), NOT a count of all matching rows on disk. We deliberately
    do not pre-scan to count total matches: that would double the I/O
    for every slice request, and the truncation flag is enough signal
    for the operator UI in Phase 0.
    """

    events: list[dict]
    start_ts: float
    end_ts: float
    total_count: int
    truncated: bool
    filter_session_id: str | None
    filter_layer: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": list(self.events),
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "total_count": self.total_count,
            "truncated": self.truncated,
            "filter_session_id": self.filter_session_id,
            "filter_layer": self.filter_layer,
        }


def get_replay_slice(
    start_ts: float,
    end_ts: float,
    *,
    session_id: str | None = None,
    layer: str | None = None,
    max_events: int = MAX_REPLAY_SLICE_SIZE,
) -> ReplaySlice:
    """Read replay logs across the time window, filter, return slice.

    Walks every daily log file overlapping ``[start_ts, end_ts]``, reads
    line-by-line, parses JSON, and applies the optional ``session_id`` /
    ``layer`` filters. Stops as soon as ``max_events`` matching rows are
    accumulated, setting ``truncated=True`` on the returned slice.

    Robustness:

    - Missing daily files are silently skipped -- a slice across a quiet
      day returns whatever is available.
    - Malformed JSON lines (e.g. partial write at process kill) are
      logged at WARNING and skipped; one bad line never poisons the
      whole slice.
    - ``ts`` outside the requested window is filtered out even if a
      stale file is read (defensive: log rotation could leave a row
      from yesterday in today's file under clock drift).
    """
    if max_events <= 0:
        max_events = MAX_REPLAY_SLICE_SIZE

    events: list[dict] = []
    truncated = False

    for path in _iter_log_files_for_range(start_ts, end_ts):
        if truncated:
            break
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        log.warning(
                            "replay: skipping malformed line in %s (%s)",
                            path, exc,
                        )
                        continue
                    # Defensive ts-window filter -- see docstring.
                    row_ts = row.get("ts")
                    if not isinstance(row_ts, (int, float)):
                        continue
                    if row_ts < start_ts or row_ts > end_ts:
                        continue
                    if session_id is not None and row.get("session_id") != session_id:
                        continue
                    if layer is not None and row.get("layer") != layer:
                        continue
                    if len(events) >= max_events:
                        truncated = True
                        break
                    events.append(row)
        except FileNotFoundError:
            # Race: file existed when _iter yielded it but vanished
            # before we could open it. Treat as a quiet day.
            continue
        except OSError as exc:
            log.warning("replay: failed to read %s (%s)", path, exc)
            continue

    # Chronological order. The on-disk log is append-only by ts so each
    # file is already sorted; we sort the cross-file aggregate to be
    # safe (events arriving out of order across day boundaries due to
    # delayed clocks would otherwise interleave incorrectly).
    events.sort(key=lambda r: r.get("ts", 0.0))

    return ReplaySlice(
        events=events,
        start_ts=start_ts,
        end_ts=end_ts,
        total_count=len(events),
        truncated=truncated,
        filter_session_id=session_id,
        filter_layer=layer,
    )


# --------------------------------------------------------------------------
# Day enumeration (for /replay/days endpoint)
# --------------------------------------------------------------------------


def list_replay_days() -> list[str]:
    """Return YYYY-MM-DD strings for every daily log present, newest first.

    Used by ``GET /api/v1/terminal/replay/days`` so the operator UI can
    populate its date-picker without a separate stat call per day.
    Missing log dir (fresh deploy, never recorded) returns ``[]``.
    """
    if not REPLAY_LOG_DIR.exists():
        return []
    days: list[str] = []
    for child in REPLAY_LOG_DIR.iterdir():
        if not child.is_file():
            continue
        if not child.name.endswith(".jsonl"):
            continue
        stem = child.stem
        # Best-effort validate the stem looks like YYYY-MM-DD.
        try:
            datetime.strptime(stem, _DATE_FMT)
        except ValueError:
            continue
        days.append(stem)
    days.sort(reverse=True)
    return days


__all__ = [
    "REPLAY_LOG_DIR",
    "MAX_REPLAY_SLICE_SIZE",
    "ReplaySlice",
    "record_event",
    "get_replay_slice",
    "list_replay_days",
    "_replay_log_path_for_ts",
    "_iter_log_files_for_range",
]
