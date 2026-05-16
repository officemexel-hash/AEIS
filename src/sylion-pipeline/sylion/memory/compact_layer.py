"""
SYLION Memory -- Compact Layer

Context compaction with Canonical Fidelity Test (CFT).
Compresses text by removing whitespace, deduplicating lines, and extracting
key sentences while preserving semantic content.

Target: compression ratio >= 5x, fidelity score >= 0.99.
CFT = hash comparison on canonical form (sorted unique words).
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.memory.compact_layer")


@dataclass
class CompactionRecord:
    """Record of a single compaction operation."""
    record_id: str = ""
    original_hash: str = ""
    compact_hash: str = ""
    original_size: int = 0
    compact_size: int = 0
    ratio: float = 0.0
    fidelity_score: float = 0.0
    created_at: float = 0.0

    def __post_init__(self):
        if not self.record_id:
            self.record_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


def _canonical_form(text: str) -> str:
    """Canonical form: lowercase, sorted unique words."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return " ".join(sorted(set(words)))


def _canonical_hash(text: str) -> str:
    """SHA-256 hash of the canonical form of text."""
    canon = _canonical_form(text)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class CompactLayer:
    """Context compaction with Canonical Fidelity Test.

    Compresses text while measuring fidelity via word-overlap ratio.
    Thread-safe. SQLite-backed. Emits events.
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
            CREATE TABLE IF NOT EXISTS compaction_records (
                record_id      TEXT PRIMARY KEY,
                original_hash  TEXT NOT NULL DEFAULT '',
                compact_hash   TEXT NOT NULL DEFAULT '',
                original_size  INTEGER NOT NULL DEFAULT 0,
                compact_size   INTEGER NOT NULL DEFAULT 0,
                ratio          REAL NOT NULL DEFAULT 0.0,
                fidelity_score REAL NOT NULL DEFAULT 0.0,
                created_at     REAL NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_compact_ts ON compaction_records(created_at)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_compact_fidelity ON compaction_records(fidelity_score)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def compact(self, text: str) -> dict:
        """Compress text: remove excess whitespace, deduplicate lines, extract key sentences.

        Returns a dict with compacted text and metrics.
        """
        original_size = len(text)

        # Step 1: Normalize whitespace
        lines = text.splitlines()
        stripped = [line.strip() for line in lines if line.strip()]

        # Step 2: Deduplicate lines while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for line in stripped:
            key = line.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(line)

        # Step 3: Extract key sentences (first sentence of each line, up to
        # reasonable length). If a line has multiple sentences, keep the first.
        key_sentences: list[str] = []
        for line in deduped:
            # Split on sentence boundaries
            sentences = re.split(r'(?<=[.!?])\s+', line)
            if sentences:
                key_sentences.append(sentences[0])
            else:
                key_sentences.append(line)

        compacted = "\n".join(key_sentences)
        compact_size = len(compacted)

        ratio = original_size / compact_size if compact_size > 0 else 0.0
        fidelity = self.compute_fidelity(text, compacted)

        result = {
            "compacted": compacted,
            "original_size": original_size,
            "compact_size": compact_size,
            "ratio": round(ratio, 2),
            "fidelity_score": round(fidelity, 4),
        }

        self._emit("compact.compacted", result)
        return result

    # ------------------------------------------------------------------
    # Canonical Fidelity Test (CFT)
    # ------------------------------------------------------------------

    def compute_fidelity(self, original: str, compacted: str) -> float:
        """Compute word-overlap ratio between original and compacted text.

        fidelity = |words_intersection| / |words_union|
        Returns value in [0.0, 1.0].
        """
        orig_words = set(re.findall(r"[a-zA-Z0-9]+", original.lower()))
        comp_words = set(re.findall(r"[a-zA-Z0-9]+", compacted.lower()))

        if not orig_words:
            return 1.0 if not comp_words else 0.0

        intersection = orig_words & comp_words
        union = orig_words | comp_words

        if not union:
            return 1.0

        return len(intersection) / len(union)

    # ------------------------------------------------------------------
    # Record persistence
    # ------------------------------------------------------------------

    def record_compaction(self, original: str, compacted: str,
                          fidelity: float = 0.0) -> dict:
        """Record a compaction operation in the database.

        If fidelity is 0.0, it is computed automatically.
        """
        original_size = len(original)
        compact_size = len(compacted)
        ratio = original_size / compact_size if compact_size > 0 else 0.0

        if fidelity <= 0.0:
            fidelity = self.compute_fidelity(original, compacted)

        record = CompactionRecord(
            original_hash=_canonical_hash(original),
            compact_hash=_canonical_hash(compacted),
            original_size=original_size,
            compact_size=compact_size,
            ratio=round(ratio, 2),
            fidelity_score=round(fidelity, 4),
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO compaction_records
                (record_id, original_hash, compact_hash, original_size,
                 compact_size, ratio, fidelity_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.record_id, record.original_hash, record.compact_hash,
                record.original_size, record.compact_size, record.ratio,
                record.fidelity_score, record.created_at,
            ))
            self._conn.commit()

        self._emit("compact.recorded", {
            "record_id": record.record_id,
            "ratio": record.ratio,
            "fidelity_score": record.fidelity_score,
        })

        log.info("compaction recorded %s: ratio=%.2fx fidelity=%.4f",
                 record.record_id[:12], record.ratio, record.fidelity_score)
        return {
            "record_id": record.record_id,
            "ratio": record.ratio,
            "fidelity_score": record.fidelity_score,
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate compaction statistics: average ratio, min/max fidelity."""
        row = self._conn.execute("""
            SELECT
                COUNT(*) as total_records,
                AVG(ratio) as avg_ratio,
                MIN(fidelity_score) as min_fidelity,
                MAX(fidelity_score) as max_fidelity,
                AVG(fidelity_score) as avg_fidelity
            FROM compaction_records
        """).fetchone()

        if not row or row["total_records"] == 0:
            return {
                "total_records": 0,
                "avg_ratio": 0.0,
                "min_fidelity": 0.0,
                "max_fidelity": 0.0,
                "avg_fidelity": 0.0,
            }

        return {
            "total_records": row["total_records"],
            "avg_ratio": round(row["avg_ratio"], 2),
            "min_fidelity": round(row["min_fidelity"], 4),
            "max_fidelity": round(row["max_fidelity"], 4),
            "avg_fidelity": round(row["avg_fidelity"], 4),
        }

    def list_records(self, limit: int = 50) -> list[dict]:
        """List recent compaction records."""
        rows = self._conn.execute(
            "SELECT * FROM compaction_records ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="memory.compact_layer",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_compact: CompactLayer | None = None


def get_compact_layer(event_bus: EventBus | None = None,
                      db_path: str | Path | None = None) -> CompactLayer:
    global _compact
    if _compact is None:
        _compact = CompactLayer(event_bus, db_path)
    return _compact


def reset_compact_layer() -> None:
    global _compact
    _compact = None
