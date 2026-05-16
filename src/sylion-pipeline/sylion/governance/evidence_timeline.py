"""
SYLION Governance -- Evidence Timeline

Builds timelines from evidence entries for decision auditing.
Each timeline is an ordered sequence of events (decisions, evidence
observations, actions, milestones, alerts) that provides a reconstructable
narrative for governance review.

Event types: decision, evidence, action, observation, milestone, alert

Tables:
  timelines         -- timeline metadata with aggregate counts
  timeline_events   -- individual events within a timeline

Singleton: get_evidence_timeline() / reset_evidence_timeline()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.governance.evidence_timeline")

VALID_EVENT_TYPES = ("decision", "evidence", "action", "observation", "milestone", "alert")


class EvidenceTimeline:
    """Manages evidence timelines for decision auditing.

    SQLite-backed with RLock for thread safety. Integrates with EventBus
    for cross-module notifications.
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS timelines (
                timeline_id  TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                updated_at   REAL NOT NULL DEFAULT 0.0,
                event_count  INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS timeline_events (
                event_id       TEXT PRIMARY KEY,
                timeline_id    TEXT NOT NULL,
                event_type     TEXT NOT NULL,
                title          TEXT NOT NULL,
                description    TEXT NOT NULL DEFAULT '',
                source_module  TEXT NOT NULL DEFAULT '',
                actor          TEXT NOT NULL DEFAULT '',
                timestamp      REAL NOT NULL,
                evidence_ref   TEXT NOT NULL DEFAULT '',
                metadata       TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (timeline_id) REFERENCES timelines(timeline_id)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_te_timeline
                ON timeline_events(timeline_id);
            CREATE INDEX IF NOT EXISTS idx_te_event_type
                ON timeline_events(event_type);
            CREATE INDEX IF NOT EXISTS idx_te_timestamp
                ON timeline_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_te_source
                ON timeline_events(source_module);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.evidence_timeline",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _json_dumps(value: Any) -> str:
        if value is None:
            return "{}"
        return json.dumps(value, sort_keys=True, default=str)

    @staticmethod
    def _json_loads(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    @staticmethod
    def _parse_event_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        if d.get("metadata") is not None:
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    def _increment_event_count(self, timeline_id: str, delta: int = 1):
        """Update event_count and updated_at for a timeline."""
        now = time.time()
        with self._lock:
            self._conn.execute("""
                UPDATE timelines
                SET event_count = event_count + ?,
                    updated_at = ?
                WHERE timeline_id = ?
            """, (delta, now, timeline_id))
            self._conn.commit()

    # ------------------------------------------------------------------
    # Timeline CRUD
    # ------------------------------------------------------------------

    def create_timeline(self, name: str, description: str = "") -> dict:
        """Create a new timeline and return its record."""
        timeline_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO timelines (timeline_id, name, description, created_at, updated_at, event_count)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (timeline_id, name, description, now, now))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM timelines WHERE timeline_id = ?", (timeline_id,)
            ).fetchone()

        result = dict(row)

        self._emit("timeline.created", {
            "timeline_id": timeline_id,
            "name": name,
        })

        log.info("timeline created: %s (%s)", timeline_id[:12], name)
        return result

    def get_timeline(self, timeline_id: str) -> dict | None:
        """Return a single timeline by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM timelines WHERE timeline_id = ?", (timeline_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_timelines(self, limit: int = 50) -> list[dict]:
        """List timelines ordered by most recently updated."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM timelines ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_timeline(self, timeline_id: str) -> bool:
        """Delete a timeline and all its events (cascade).

        Returns True if the timeline existed and was deleted, False otherwise.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT timeline_id FROM timelines WHERE timeline_id = ?",
                (timeline_id,)
            ).fetchone()
            if not row:
                return False

            self._conn.execute(
                "DELETE FROM timeline_events WHERE timeline_id = ?",
                (timeline_id,)
            )
            self._conn.execute(
                "DELETE FROM timelines WHERE timeline_id = ?",
                (timeline_id,)
            )
            self._conn.commit()

        log.info("timeline deleted: %s", timeline_id[:12])
        return True

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def add_event(
        self,
        timeline_id: str,
        event_type: str,
        title: str,
        description: str = "",
        source_module: str = "",
        actor: str = "",
        evidence_ref: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """Add an event to a timeline.

        Parameters
        ----------
        timeline_id : str
            Target timeline.
        event_type : str
            One of VALID_EVENT_TYPES.
        title : str
            Short human-readable title.
        description : str
            Extended description.
        source_module : str
            Module that produced this event.
        actor : str
            Who or what triggered the event.
        evidence_ref : str
            Reference to an evidence pack or spine entry.
        metadata : dict, optional
            Additional structured context.

        Returns
        -------
        dict
            The created event record.
        """
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid event_type: {event_type!r}. "
                f"Must be one of {VALID_EVENT_TYPES}"
            )

        with self._lock:
            tl = self._conn.execute(
                "SELECT timeline_id FROM timelines WHERE timeline_id = ?",
                (timeline_id,)
            ).fetchone()
            if not tl:
                raise ValueError(f"Timeline not found: {timeline_id}")

        event_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO timeline_events
                    (event_id, timeline_id, event_type, title, description,
                     source_module, actor, timestamp, evidence_ref, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, timeline_id, event_type, title, description,
                source_module, actor, now, evidence_ref,
                self._json_dumps(metadata),
            ))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM timeline_events WHERE event_id = ?",
                (event_id,)
            ).fetchone()

        self._increment_event_count(timeline_id, delta=1)

        result = self._parse_event_row(row)

        self._emit("timeline.event_added", {
            "event_id": event_id,
            "timeline_id": timeline_id,
            "event_type": event_type,
        })

        log.info("event added: %s to timeline %s (type=%s)",
                 event_id[:12], timeline_id[:12], event_type)
        return result

    def get_events(
        self,
        timeline_id: str,
        event_type: str | None = None,
        since: float | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """List events for a timeline ordered by timestamp ascending.

        Parameters
        ----------
        timeline_id : str
            Target timeline.
        event_type : str, optional
            Filter by event type.
        since : float, optional
            Only events at or after this unix timestamp.
        limit : int
            Maximum events to return (default 200).

        Returns
        -------
        list[dict]
            Ordered event records.
        """
        with self._lock:
            q = "SELECT * FROM timeline_events WHERE timeline_id = ?"
            params: list[Any] = [timeline_id]
            if event_type is not None:
                q += " AND event_type = ?"
                params.append(event_type)
            if since is not None:
                q += " AND timestamp >= ?"
                params.append(since)
            q += " ORDER BY timestamp ASC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(q, params).fetchall()

        return [self._parse_event_row(r) for r in rows]

    def get_event(self, event_id: str) -> dict | None:
        """Return a single event by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM timeline_events WHERE event_id = ?",
                (event_id,)
            ).fetchone()
        if not row:
            return None
        return self._parse_event_row(row)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics: timeline and event counts."""
        with self._lock:
            tl_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM timelines"
            ).fetchone()["cnt"]

            ev_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM timeline_events"
            ).fetchone()["cnt"]

            type_rows = self._conn.execute(
                "SELECT event_type, COUNT(*) as cnt "
                "FROM timeline_events GROUP BY event_type"
            ).fetchall()
            by_event_type = {r["event_type"]: r["cnt"] for r in type_rows}

        return {
            "timeline_count": tl_count,
            "event_count": ev_count,
            "by_event_type": by_event_type,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: EvidenceTimeline | None = None


def get_evidence_timeline(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> EvidenceTimeline:
    global _instance
    if _instance is None:
        _instance = EvidenceTimeline(db_path, event_bus)
    return _instance


def reset_evidence_timeline(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> EvidenceTimeline:
    global _instance
    _instance = EvidenceTimeline(db_path, event_bus)
    return _instance
