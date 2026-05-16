"""
SYLION Memory -- Knowledge Base Adapter

Adapter for external knowledge base access.
Manages KB source registration and provides a query interface
for external knowledge retrieval (stub implementation for Phase 1).
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
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.memory.kb_adapter")


@dataclass
class KBSource:
    """A registered knowledge base source."""
    source_id: str = ""
    name: str = ""
    source_type: str = "file"
    path: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    active: int = 1
    last_indexed: float = 0.0


@dataclass
class KBQuery:
    """A logged KB query for audit purposes."""
    query_id: str = ""
    source_id: str = ""
    query_text: str = ""
    results_count: int = 0
    latency_ms: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.query_id:
            self.query_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


class KBAdapter:
    """Knowledge base adapter for external KB access.

    Thread-safe. SQLite-backed. Emits events on source registration
    and queries.
    """

    def __init__(self, event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS kb_sources (
                source_id    TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                source_type  TEXT NOT NULL DEFAULT 'file',
                path         TEXT NOT NULL DEFAULT '',
                config       TEXT NOT NULL DEFAULT '{}',
                active       INTEGER NOT NULL DEFAULT 1,
                last_indexed REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS kb_queries (
                query_id      TEXT PRIMARY KEY,
                source_id     TEXT NOT NULL,
                query_text    TEXT NOT NULL DEFAULT '',
                results_count INTEGER NOT NULL DEFAULT 0,
                latency_ms    INTEGER NOT NULL DEFAULT 0,
                timestamp     REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kb_queries_source ON kb_queries(source_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kb_queries_ts ON kb_queries(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    def register_source(self, source_id: str, name: str,
                        source_type: str = "file", path: str = "",
                        config: dict | None = None) -> dict:
        """Register a new knowledge base source."""
        if config is None:
            config = {}

        source = KBSource(
            source_id=source_id,
            name=name,
            source_type=source_type,
            path=path,
            config=config,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO kb_sources
                (source_id, name, source_type, path, config, active, last_indexed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                source.source_id, source.name, source.source_type,
                source.path, json.dumps(source.config, default=str),
                source.active, source.last_indexed,
            ))
            self._conn.commit()

        self._emit("kb.source_registered", {
            "source_id": source_id,
            "name": name,
            "source_type": source_type,
        })

        log.info("registered KB source %s (%s, type=%s)",
                 source_id, name, source_type)
        return self._source_to_dict(source)

    def get_source(self, source_id: str) -> dict | None:
        """Retrieve a registered KB source by ID."""
        row = self._conn.execute(
            "SELECT * FROM kb_sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if not row:
            return None
        return self._source_row_to_dict(row)

    def list_sources(self, active_only: bool = True) -> list[dict]:
        """List all registered KB sources."""
        if active_only:
            rows = self._conn.execute(
                "SELECT * FROM kb_sources WHERE active = 1 ORDER BY name"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM kb_sources ORDER BY name"
            ).fetchall()
        return [self._source_row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Query (stub)
    # ------------------------------------------------------------------

    def query(self, source_id: str, query_text: str,
              limit: int = 10) -> list[dict]:
        """Query a knowledge base source (stub -- returns empty list).

        Logs the query for audit. Full implementation in Phase 2.
        """
        start = time.time()
        results: list[dict] = []
        elapsed_ms = int((time.time() - start) * 1000)

        logged_query = KBQuery(
            source_id=source_id,
            query_text=query_text,
            results_count=len(results),
            latency_ms=elapsed_ms,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO kb_queries
                (query_id, source_id, query_text, results_count, latency_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                logged_query.query_id, logged_query.source_id,
                logged_query.query_text, logged_query.results_count,
                logged_query.latency_ms, logged_query.timestamp,
            ))
            self._conn.commit()

        self._emit("kb.queried", {
            "query_id": logged_query.query_id,
            "source_id": source_id,
            "results_count": len(results),
        })

        log.info("queried KB source %s (results=%d, latency=%dms)",
                 source_id, len(results), elapsed_ms)
        return results

    # ------------------------------------------------------------------
    # Index (stub)
    # ------------------------------------------------------------------

    def index(self, source_id: str) -> dict | None:
        """Index a KB source (stub -- marks as indexed).

        Returns updated source dict or None if source not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM kb_sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if not row:
                log.warning("KB source %s not found for indexing", source_id)
                return None

            now = time.time()
            self._conn.execute(
                "UPDATE kb_sources SET last_indexed = ? WHERE source_id = ?",
                (now, source_id),
            )
            self._conn.commit()

        self._emit("kb.indexed", {
            "source_id": source_id,
            "timestamp": now,
        })

        log.info("indexed KB source %s", source_id)
        return self.get_source(source_id)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate KB adapter statistics."""
        source_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM kb_sources"
        ).fetchone()["cnt"]

        active_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM kb_sources WHERE active = 1"
        ).fetchone()["cnt"]

        query_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM kb_queries"
        ).fetchone()["cnt"]

        avg_latency_row = self._conn.execute(
            "SELECT AVG(latency_ms) as avg_lat FROM kb_queries"
        ).fetchone()
        avg_latency = avg_latency_row["avg_lat"] if avg_latency_row["avg_lat"] else 0.0

        return {
            "total_sources": source_count,
            "active_sources": active_count,
            "total_queries": query_count,
            "avg_latency_ms": round(avg_latency, 2),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _source_to_dict(source: KBSource) -> dict:
        return {
            "source_id": source.source_id,
            "name": source.name,
            "source_type": source.source_type,
            "path": source.path,
            "config": source.config,
            "active": source.active,
            "last_indexed": source.last_indexed,
        }

    @staticmethod
    def _source_row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["config"] = json.loads(d.get("config", "{}"))
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="memory.kb_adapter",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_adapter: KBAdapter | None = None


def get_kb_adapter(event_bus: EventBus | None = None,
                   db_path: str | Path | None = None) -> KBAdapter:
    global _adapter
    if _adapter is None:
        _adapter = KBAdapter(event_bus, db_path)
    return _adapter


def reset_kb_adapter() -> None:
    global _adapter
    _adapter = None
