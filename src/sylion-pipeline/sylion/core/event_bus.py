"""
SYLION Core — Event Bus

Pub/sub event backbone for all modules. SQLite-backed (NATS JetStream later).

Event taxonomy: domain.event.action (e.g. decision.proposed, council.vote.cast)
Idempotency: UUIDv7 keys.

gRPC planned: PublishEvent, Subscribe, Ack, GetEventCatalog
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("sylion.core.event_bus")

# ---------------------------------------------------------------------------
# Event taxonomy
# ---------------------------------------------------------------------------

class EventDomain(str, Enum):
    MODULE    = "module"
    DECISION  = "decision"
    COUNCIL   = "council"
    EVIDENCE  = "evidence"
    GATE      = "gate"
    COGNITIVE = "cognitive"
    EXECUTION = "execution"
    MEMORY    = "memory"
    SECURITY  = "security"
    AEIS      = "aeis"
    SKILL     = "skill"
    SYSTEM    = "system"


@dataclass
class SylionEvent:
    """Canonical event structure."""
    event_id: str                            # UUIDv7
    topic: str                               # domain.action (e.g. "module.registered")
    payload: dict[str, Any] = field(default_factory=dict)
    source_module: str = ""                  # module_id that emitted
    timestamp: float = 0.0
    idempotency_key: str = ""                # dedup

    def __post_init__(self):
        if not self.event_id:
            self.event_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.idempotency_key:
            self.idempotency_key = self.event_id

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "topic": self.topic,
            "payload": self.payload,
            "source_module": self.source_module,
            "timestamp": self.timestamp,
            "idempotency_key": self.idempotency_key,
        }


# ---------------------------------------------------------------------------
# Subscriber callback type
# ---------------------------------------------------------------------------

EventHandler = Callable[[SylionEvent], None]

# ---------------------------------------------------------------------------
# Event Bus — SQLite-backed implementation
# ---------------------------------------------------------------------------

class EventBus:
    """Pub/sub event backbone.

    Phase 1: SQLite-backed with in-memory subscriber dispatch.
    Phase 2: NATS JetStream backend (same interface, config swap).
    """

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_subs: list[EventHandler] = []
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_events (
                event_id     TEXT PRIMARY KEY,
                topic        TEXT NOT NULL,
                payload      TEXT NOT NULL DEFAULT '{}',
                source_module TEXT NOT NULL DEFAULT '',
                timestamp    REAL NOT NULL,
                idempotency_key TEXT NOT NULL DEFAULT '',
                acked        INTEGER NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_topic ON sylion_events(topic)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON sylion_events(timestamp)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_idem ON sylion_events(idempotency_key)")
        self._conn.commit()

    # --- Publish ---

    def publish(self, event: SylionEvent) -> str:
        """Publish event. Returns event_id. Deduplicates by idempotency_key."""
        with self._lock:
            # Idempotency check
            existing = self._conn.execute(
                "SELECT event_id FROM sylion_events WHERE idempotency_key = ?",
                (event.idempotency_key,)
            ).fetchone()
            if existing:
                log.debug("dedup event %s (idem_key=%s)", event.event_id, event.idempotency_key)
                return existing["event_id"]

            self._conn.execute("""
                INSERT INTO sylion_events (event_id, topic, payload, source_module, timestamp, idempotency_key)
                VALUES (?,?,?,?,?,?)
            """, (
                event.event_id,
                event.topic,
                json.dumps(event.payload, default=str),
                event.source_module,
                event.timestamp,
                event.idempotency_key,
            ))
            self._conn.commit()

        # Dispatch to subscribers (outside lock)
        self._dispatch(event)
        return event.event_id

    def _dispatch(self, event: SylionEvent):
        # Exact topic subscribers
        for handler in self._subscribers.get(event.topic, []):
            try:
                handler(event)
            except Exception:
                log.exception("subscriber error for topic %s", event.topic)

        # Wildcard subscribers
        for handler in self._wildcard_subs:
            try:
                handler(event)
            except Exception:
                log.exception("wildcard subscriber error")

    # --- Subscribe ---

    def subscribe(self, topic: str, handler: EventHandler):
        """Subscribe to a topic. Use "*" for all events."""
        if topic == "*":
            self._wildcard_subs.append(handler)
        else:
            self._subscribers[topic].append(handler)
        log.debug("subscribed to %s", topic)

    # --- Ack ---

    def ack(self, event_id: str) -> bool:
        with self._lock:
            updated = self._conn.execute(
                "UPDATE sylion_events SET acked = 1 WHERE event_id = ?",
                (event_id,)
            ).rowcount
            self._conn.commit()
        return bool(updated)

    # --- Query ---

    def query(self, topic: str | None = None, since: float | None = None,
              limit: int = 100) -> list[dict]:
        q = "SELECT * FROM sylion_events WHERE 1=1"
        params: list[Any] = []
        if topic:
            q += " AND topic = ?"
            params.append(topic)
        if since:
            q += " AND timestamp >= ?"
            params.append(since)
        q += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    # --- Replay ---

    def replay(self, since: float | None = None, topic: str | None = None) -> int:
        """Replay events to subscribers. Returns count of replayed events."""
        events = self.query(topic=topic, since=since, limit=10000)
        count = 0
        for ev_dict in reversed(events):  # chronological order
            event = SylionEvent(
                event_id=ev_dict["event_id"],
                topic=ev_dict["topic"],
                payload=json.loads(ev_dict["payload"]),
                source_module=ev_dict["source_module"],
                timestamp=ev_dict["timestamp"],
            )
            self._dispatch(event)
            count += 1
        log.info("replayed %d events (since=%s, topic=%s)", count, since, topic)
        return count

    # --- Catalog ---

    def get_catalog(self) -> dict[str, int]:
        """Get event counts per topic."""
        rows = self._conn.execute(
            "SELECT topic, COUNT(*) as cnt FROM sylion_events GROUP BY topic ORDER BY topic"
        ).fetchall()
        return {r["topic"]: r["cnt"] for r in rows}


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_bus: EventBus | None = None

def get_event_bus(db_path: str | Path | None = None) -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus(db_path)
    return _bus
