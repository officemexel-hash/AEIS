"""
SYLION Cognitive -- Reasoner

Reasoning with canon context. Records reasoning chains with confidence
scores, supporting query-based retrieval and chain-of-thought tracking.

Thread-safe. SQLite-backed. Emits events on reasoning operations.
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

log = logging.getLogger("sylion.cognitive.reasoner")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReasoningChain:
    """A single reasoning chain record."""
    chain_id: str = ""
    query: str = ""
    conclusion: str = ""
    steps: str = "[]"
    confidence: float = 0.0
    source: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.chain_id:
            self.chain_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Reasoner
# ---------------------------------------------------------------------------

class Reasoner:
    """Reasoning with canon context.

    Thread-safe. SQLite-backed. Emits events on reasoning operations.
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
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS reasoning_chains (
                chain_id   TEXT PRIMARY KEY,
                query      TEXT NOT NULL DEFAULT '',
                conclusion TEXT NOT NULL DEFAULT '',
                steps      TEXT NOT NULL DEFAULT '[]',
                confidence REAL NOT NULL DEFAULT 0.0,
                source     TEXT NOT NULL DEFAULT '',
                timestamp  REAL NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_reason_query ON reasoning_chains(query)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_reason_conf ON reasoning_chains(confidence)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_reason_ts ON reasoning_chains(timestamp)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Reasoning operations
    # ------------------------------------------------------------------

    def reason(self, query: str, context: str = "", conclusion: str = "",
               steps: list | None = None, confidence: float = 0.0,
               source: str = "") -> dict:
        """Record a reasoning chain. Returns chain dict."""
        if steps is None:
            steps = []

        chain = ReasoningChain(
            query=query,
            conclusion=conclusion,
            steps=json.dumps(steps, default=str),
            confidence=confidence,
            source=source,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO reasoning_chains
                (chain_id, query, conclusion, steps, confidence, source, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                chain.chain_id, chain.query, chain.conclusion, chain.steps,
                chain.confidence, chain.source, chain.timestamp,
            ))
            self._conn.commit()

        self._emit("reasoning.recorded", {
            "chain_id": chain.chain_id,
            "query": query,
            "confidence": confidence,
        })
        log.info("recorded reasoning chain %s: confidence=%.2f",
                 chain.chain_id[:12], confidence)
        return {
            "chain_id": chain.chain_id,
            "query": query,
            "conclusion": conclusion,
            "confidence": confidence,
            "timestamp": chain.timestamp,
        }

    def get_chain(self, chain_id: str) -> dict | None:
        """Retrieve a single reasoning chain by ID."""
        row = self._conn.execute(
            "SELECT * FROM reasoning_chains WHERE chain_id = ?",
            (chain_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["steps"] = json.loads(result.get("steps", "[]"))
        return result

    def query_chains(self, query_text: str, limit: int = 10) -> list[dict]:
        """Search reasoning chains by query text (LIKE match)."""
        pattern = f"%{query_text}%"
        rows = self._conn.execute("""
            SELECT * FROM reasoning_chains
            WHERE query LIKE ? OR conclusion LIKE ?
            ORDER BY confidence DESC, timestamp DESC
            LIMIT ?
        """, (pattern, pattern, limit)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["steps"] = json.loads(d.get("steps", "[]"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Aggregate reasoning statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM reasoning_chains"
        ).fetchone()["cnt"]

        avg_conf = self._conn.execute(
            "SELECT AVG(confidence) as avg FROM reasoning_chains"
        ).fetchone()["avg"]

        by_source_rows = self._conn.execute(
            "SELECT source, COUNT(*) as cnt FROM reasoning_chains GROUP BY source"
        ).fetchall()
        by_source = {r["source"]: r["cnt"] for r in by_source_rows}

        return {
            "total_chains": total,
            "avg_confidence": round(avg_conf or 0.0, 4),
            "by_source": by_source,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.reasoner",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_reasoner: Reasoner | None = None


def get_reasoner(event_bus: EventBus | None = None,
                 db_path: str | Path | None = None) -> Reasoner:
    global _reasoner
    if _reasoner is None:
        _reasoner = Reasoner(event_bus, db_path)
    return _reasoner
