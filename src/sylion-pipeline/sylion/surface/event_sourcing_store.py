"""
SYLION Surface -- Event Sourcing Store

Append-only stream, snapshots, replay, projection repair.
Thread-safe. SQLite-backed. Emits events via EventBus.

Frozen decisions:
- Event store is append-only (NEVER UPDATE/DELETE event history)
- event_sourcing_store = source of truth for operational action history
- Projections are rebuildable and disposable
- Full event sourcing, NOT just audit log
- Replay: event payload must be sufficient to rebuild state
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.surface.event_sourcing_store")


@dataclass
class StoredEvent:
    event_id: str = ""
    stream_id: str = ""
    event_type: str = ""
    version: int = 0
    payload: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.event_id:
            self.event_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class Snapshot:
    snapshot_id: str = ""
    stream_id: str = ""
    version: int = 0
    state: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.snapshot_id:
            self.snapshot_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


class EventSourcingStore:
    """Append-only event stream with snapshots and replay.

    Thread-safe. SQLite-backed. Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS event_stream (
                stream_id    TEXT PRIMARY KEY,
                stream_type  TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                last_version INTEGER NOT NULL DEFAULT 0
            )
        """)
        # APPEND-ONLY: never UPDATE or DELETE rows in event_log
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                event_id    TEXT PRIMARY KEY,
                stream_id   TEXT NOT NULL,
                event_type  TEXT NOT NULL DEFAULT '',
                version     INTEGER NOT NULL,
                payload     TEXT NOT NULL DEFAULT '{}',
                metadata    TEXT NOT NULL DEFAULT '{}',
                timestamp   REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                stream_id   TEXT NOT NULL,
                version     INTEGER NOT NULL,
                state       TEXT NOT NULL DEFAULT '{}',
                timestamp   REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_el_stream ON event_log(stream_id, version)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snap_stream ON snapshots(stream_id)"
        )
        self._conn.commit()

    def _ensure_stream(self, stream_id: str, stream_type: str = ""):
        row = self._conn.execute(
            "SELECT stream_id FROM event_stream WHERE stream_id = ?", (stream_id,),
        ).fetchone()
        if not row:
            self._conn.execute("""
                INSERT INTO event_stream (stream_id, stream_type, created_at, last_version)
                VALUES (?, ?, ?, 0)
            """, (stream_id, stream_type, time.time()))
            self._conn.commit()

    def append(self, stream_id: str, event_type: str,
               payload: dict | None = None,
               metadata: dict | None = None) -> dict:
        """Append event to stream. Auto-increments version."""
        event = StoredEvent(
            stream_id=stream_id,
            event_type=event_type,
            payload=payload or {},
            metadata=metadata or {},
        )

        with self._lock:
            self._ensure_stream(stream_id)
            row = self._conn.execute(
                "SELECT last_version FROM event_stream WHERE stream_id = ?",
                (stream_id,),
            ).fetchone()
            version = (row["last_version"] or 0) + 1
            event.version = version

            self._conn.execute("""
                INSERT INTO event_log
                    (event_id, stream_id, event_type, version,
                     payload, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.stream_id, event.event_type,
                event.version, json.dumps(event.payload),
                json.dumps(event.metadata), event.timestamp,
            ))
            self._conn.execute("""
                UPDATE event_stream SET last_version = ? WHERE stream_id = ?
            """, (version, stream_id))
            self._conn.commit()

        self._emit("surface.event_sourcing.event_appended", {
            "event_id": event.event_id,
            "stream_id": stream_id,
            "version": version,
            "event_type": event_type,
        })

        log.info("appended event %s v%d to stream %s",
                 event.event_id[:12], version, stream_id[:12])
        return {
            "event_id": event.event_id,
            "stream_id": stream_id,
            "version": version,
        }

    def get_events(self, stream_id: str, from_version: int = 0,
                   to_version: int | None = None) -> list[dict]:
        with self._lock:
            if to_version is not None:
                rows = self._conn.execute("""
                    SELECT * FROM event_log
                    WHERE stream_id = ? AND version >= ? AND version <= ?
                    ORDER BY version
                """, (stream_id, from_version, to_version)).fetchall()
            else:
                rows = self._conn.execute("""
                    SELECT * FROM event_log
                    WHERE stream_id = ? AND version >= ?
                    ORDER BY version
                """, (stream_id, from_version)).fetchall()

            results = []
            for r in rows:
                d = dict(r)
                d["payload"] = json.loads(d.get("payload", "{}"))
                d["metadata"] = json.loads(d.get("metadata", "{}"))
                results.append(d)
            return results

    def get_event(self, event_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM event_log WHERE event_id = ?", (event_id,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["payload"] = json.loads(d.get("payload", "{}"))
            d["metadata"] = json.loads(d.get("metadata", "{}"))
            return d

    def create_snapshot(self, stream_id: str) -> dict:
        """Create snapshot at current stream version."""
        with self._lock:
            events = self.get_events(stream_id)
            if not events:
                return {"error": "no events in stream", "stream_id": stream_id}

            state = {}
            for evt in events:
                state[f"v{evt['version']}"] = evt["payload"]

            version = events[-1]["version"]
            snap = Snapshot(
                stream_id=stream_id,
                version=version,
                state=state,
            )

            self._conn.execute("""
                INSERT INTO snapshots (snapshot_id, stream_id, version, state, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (snap.snapshot_id, stream_id, version,
                  json.dumps(snap.state), snap.timestamp))
            self._conn.commit()

        self._emit("surface.event_sourcing.snapshot_created", {
            "snapshot_id": snap.snapshot_id,
            "stream_id": stream_id,
            "version": version,
        })

        log.info("created snapshot %s for stream %s at v%d",
                 snap.snapshot_id[:12], stream_id[:12], version)
        return {
            "snapshot_id": snap.snapshot_id,
            "stream_id": stream_id,
            "version": version,
        }

    def get_latest_snapshot(self, stream_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM snapshots WHERE stream_id = ? ORDER BY version DESC LIMIT 1",
                (stream_id,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["state"] = json.loads(d.get("state", "{}"))
            return d

    def load_from_snapshot(self, stream_id: str) -> dict:
        """Load state from latest snapshot + remaining events."""
        snapshot = self.get_latest_snapshot(stream_id)
        if snapshot:
            from_v = snapshot["version"] + 1
            remaining = self.get_events(stream_id, from_version=from_v)
            state = snapshot["state"].copy()
            for evt in remaining:
                state[f"v{evt['version']}"] = evt["payload"]
            return {
                "stream_id": stream_id,
                "snapshot_version": snapshot["version"],
                "remaining_events": len(remaining),
                "state": state,
            }
        events = self.get_events(stream_id)
        state = {}
        for evt in events:
            state[f"v{evt['version']}"] = evt["payload"]
        return {
            "stream_id": stream_id,
            "snapshot_version": 0,
            "remaining_events": len(events),
            "state": state,
        }

    def replay_stream(self, stream_id: str,
                      handler: Callable[[dict], Any]) -> list[Any]:
        """Replay all events through handler function."""
        events = self.get_events(stream_id)
        results = []
        for evt in events:
            result = handler(evt)
            results.append(result)
        log.info("replayed %d events for stream %s", len(events), stream_id[:12])
        return results

    def list_streams(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM event_stream ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with self._lock:
            total_events = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM event_log"
            ).fetchone()["cnt"]
            total_streams = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM event_stream"
            ).fetchone()["cnt"]
            total_snapshots = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM snapshots"
            ).fetchone()["cnt"]
            return {
                "total_events": total_events,
                "total_streams": total_streams,
                "total_snapshots": total_snapshots,
            }

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="surface.event_sourcing_store",
            ))


_store: EventSourcingStore | None = None


def get_event_sourcing_store(db_path: str | Path | None = None,
                              event_bus: EventBus | None = None) -> EventSourcingStore:
    global _store
    if _store is None:
        _store = EventSourcingStore(db_path, event_bus)
    return _store
