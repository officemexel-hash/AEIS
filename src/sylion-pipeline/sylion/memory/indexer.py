"""
SYLION Memory -- Indexer

TF-based text indexer for Ksiega sections and other content.
Tokenizes text, counts term frequencies, and stores them in SQLite
for efficient retrieval via term lookup.

Index structure:
  - text_index: (term, section_id, frequency) -- inverted index
  - index_metadata: (section_id, title, word_count, indexed_at)
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.memory.indexer")


def _invalidate_memory_search_cache() -> None:
    """Phase 3 W1.3 — drop every memory.search entry on indexer write.

    Lazy-import the cache so test fixtures that swap the indexer don't pay
    a circular-import cost. A failure here must not block a write — the
    next read will be a cache miss, never a wrong read.
    """
    try:
        from sylion.infra.cache import get_cache
        get_cache().invalidate("sylion:memory.search:*")
    except Exception:                              # noqa: BLE001
        log.warning("memory.search cache invalidation failed", exc_info=True)


# Minimum term length to index
MIN_TERM_LENGTH = 2

# Common English stop words to skip
STOP_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "be", "was", "are",
    "been", "have", "has", "had", "this", "that", "not", "no", "do",
    "if", "so", "up", "out", "about", "into", "over", "after", "all",
    "also", "can", "will", "just", "than", "then", "these", "those",
})


@dataclass
class IndexEntry:
    """A single term posting in the inverted index."""
    term: str = ""
    section_id: str = ""
    frequency: int = 0


@dataclass
class IndexMetadata:
    """Metadata about an indexed section."""
    section_id: str = ""
    title: str = ""
    content_preview: str = ""
    project_id: str = ""
    word_count: int = 0
    indexed_at: float = 0.0

    def __post_init__(self):
        if not self.indexed_at:
            self.indexed_at = time.time()


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, filtering stop words."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [w for w in words if len(w) >= MIN_TERM_LENGTH and w not in STOP_WORDS]


def _count_terms(tokens: list[str]) -> dict[str, int]:
    """Count term frequencies from a token list."""
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


class Indexer:
    """TF-based text indexer.

    Thread-safe. SQLite-backed. Emits events on index/remove.
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
            CREATE TABLE IF NOT EXISTS text_index (
                term       TEXT NOT NULL,
                section_id TEXT NOT NULL,
                frequency  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (term, section_id)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS index_metadata (
                section_id  TEXT PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT '',
                content_preview TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT '',
                word_count  INTEGER NOT NULL DEFAULT 0,
                indexed_at  REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ti_term ON text_index(term)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ti_sid ON text_index(section_id)")
        existing_cols = {
            row[1] for row in self._conn.execute("PRAGMA table_info(index_metadata)").fetchall()
        }
        if "content_preview" not in existing_cols:
            self._conn.execute(
                "ALTER TABLE index_metadata ADD COLUMN content_preview TEXT NOT NULL DEFAULT ''"
            )
        if "project_id" not in existing_cols:
            self._conn.execute(
                "ALTER TABLE index_metadata ADD COLUMN project_id TEXT NOT NULL DEFAULT ''"
            )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_im_project ON index_metadata(project_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_section(self, section_id: str, title: str, content: str,
                      project_id: str = "") -> dict:
        """Tokenize content, count term frequencies, store in inverted index.

        Removes any previous index for the section_id before re-indexing.
        Returns a summary with term count and total word count.

        Phase 3 W1.3: invalidates the ``memory.search`` cache after a write
        so subsequent reads re-rank against the new index.
        """
        tokens = _tokenize(f"{title} {content}")
        term_counts = _count_terms(tokens)
        word_count = len(tokens)
        indexed_at = time.time()
        preview = " ".join(content.split())[:240]

        with self._lock:
            # Remove old index entries for this section
            self._conn.execute(
                "DELETE FROM text_index WHERE section_id = ?", (section_id,)
            )
            self._conn.execute(
                "DELETE FROM index_metadata WHERE section_id = ?", (section_id,)
            )

            # Insert new term postings
            for term, freq in term_counts.items():
                self._conn.execute("""
                    INSERT INTO text_index (term, section_id, frequency)
                    VALUES (?, ?, ?)
                """, (term, section_id, freq))

            # Insert metadata
            self._conn.execute("""
                INSERT INTO index_metadata
                    (section_id, title, content_preview, project_id, word_count, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (section_id, title, preview, project_id or "", word_count, indexed_at))

            self._conn.commit()

        _invalidate_memory_search_cache()

        result = {
            "section_id": section_id,
            "project_id": project_id or "",
            "unique_terms": len(term_counts),
            "word_count": word_count,
        }

        self._emit("indexer.section_indexed", result)
        log.info("indexed section %s: %d terms, %d words",
                 section_id[:12], len(term_counts), word_count)
        return result

    def remove_section(self, section_id: str) -> bool:
        """Remove all index entries for a section.

        Phase 3 W1.3: invalidates the ``memory.search`` cache on success.
        """
        with self._lock:
            n_index = self._conn.execute(
                "DELETE FROM text_index WHERE section_id = ?", (section_id,)
            ).rowcount
            n_meta = self._conn.execute(
                "DELETE FROM index_metadata WHERE section_id = ?", (section_id,)
            ).rowcount
            self._conn.commit()

        if n_index > 0 or n_meta > 0:
            _invalidate_memory_search_cache()
            self._emit("indexer.section_removed", {"section_id": section_id})
            log.info("removed section %s from index (%d term postings)", section_id[:12], n_index)
        return n_index > 0 or n_meta > 0

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 10,
               project_id: str | None = None) -> list[dict]:
        """TF-ranked search. Tokenizes query, sums frequencies per section.

        Returns list of dicts with section_id, title, score, ordered by
        score descending.
        """
        query_terms = _tokenize(query)
        if not query_terms:
            return []

        # Build parameterized query for all terms at once
        placeholders = ",".join("?" for _ in query_terms)
        params: list[Any] = list(query_terms)
        project_filter = ""
        if project_id:
            project_filter = " AND im.project_id = ?"
            params.append(project_id)
        params.append(limit)

        rows = self._conn.execute(f"""
            SELECT
                ti.section_id,
                im.title,
                im.project_id,
                SUM(ti.frequency) as score
            FROM text_index ti
            JOIN index_metadata im ON ti.section_id = im.section_id
            WHERE ti.term IN ({placeholders})
            {project_filter}
            GROUP BY ti.section_id, im.title, im.project_id
            ORDER BY score DESC
            LIMIT ?
        """, params).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Index statistics: total terms, sections, average word count."""
        total_terms = self._conn.execute(
            "SELECT COUNT(DISTINCT term) as cnt FROM text_index"
        ).fetchone()["cnt"]

        total_postings = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM text_index"
        ).fetchone()["cnt"]

        section_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM index_metadata"
        ).fetchone()["cnt"]

        avg_words = self._conn.execute(
            "SELECT AVG(word_count) as avg FROM index_metadata"
        ).fetchone()["avg"]

        return {
            "unique_terms": total_terms,
            "total_postings": total_postings,
            "indexed_sections": section_count,
            "avg_word_count": round(avg_words, 1) if avg_words else 0.0,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="memory.indexer",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_indexer: Indexer | None = None


def get_indexer(event_bus: EventBus | None = None,
                db_path: str | Path | None = None) -> Indexer:
    global _indexer
    if _indexer is None:
        _indexer = Indexer(event_bus, db_path)
    return _indexer


def reset_indexer() -> None:
    global _indexer
    _indexer = None
