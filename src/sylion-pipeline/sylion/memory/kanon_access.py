"""
SYLION Memory -- Kanon Access

Read-only access to Ksiega (canon) text. Parses and stores structured sections
from the canonical reference document with SHA-256 content integrity hashes.

Sections are parsed from raw text using "---" separators or "# " headers.
Every section gets a content hash for tamper-evident integrity.
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

log = logging.getLogger("sylion.memory.kanon_access")


@dataclass
class KanonSection:
    """A single section of the Ksiega canon text."""
    section_id: str = ""
    title: str = ""
    content: str = ""
    chapter: str = ""
    section_number: int = 0
    hash: str = ""

    def __post_init__(self):
        if not self.section_id:
            self.section_id = uuid.uuid4().hex
        if not self.hash and self.content:
            self.hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class KanonAccess:
    """Read-only access to Ksiega (canon) text.

    Parses raw text into sections, stores them in SQLite with SHA-256
    integrity hashes. Thread-safe. Emits events on load.
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
            CREATE TABLE IF NOT EXISTS kanon_sections (
                section_id      TEXT PRIMARY KEY,
                title           TEXT NOT NULL DEFAULT '',
                content         TEXT NOT NULL DEFAULT '',
                chapter         TEXT NOT NULL DEFAULT '',
                section_number  INTEGER NOT NULL DEFAULT 0,
                hash            TEXT NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_kanon_chapter ON kanon_sections(chapter)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_kanon_hash ON kanon_sections(hash)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def load_text(self, raw_text: str) -> dict:
        """Parse raw text into sections and store them.

        Splits on "---" separators first; if none found, splits on "# " headers.
        Each resulting chunk becomes a KanonSection with a SHA-256 content hash.

        Returns a summary dict with count of sections loaded.
        """
        sections: list[KanonSection] = []

        # Try splitting on "---" separators
        chunks = re.split(r"\n---\n", raw_text)

        if len(chunks) <= 1:
            # Fall back to "# " header splitting
            chunks = re.split(r"\n(?=# )", raw_text)

        section_num = 0
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            section_num += 1

            # Extract title from first "# ..." line
            title = ""
            content_lines: list[str] = []
            for line in chunk.splitlines():
                if not title and line.startswith("# "):
                    title = line[2:].strip()
                else:
                    content_lines.append(line)

            content = "\n".join(content_lines).strip()
            if not content and not title:
                continue

            # Derive chapter from title or use generic
            chapter = ""
            if title:
                chapter = title.split(":")[0].split(".")[0].strip()

            section = KanonSection(
                title=title,
                content=content,
                chapter=chapter,
                section_number=section_num,
            )
            sections.append(section)

        # Store all parsed sections
        with self._lock:
            for section in sections:
                self._store_section_unlocked(section)

        result = {
            "sections_loaded": len(sections),
            "section_ids": [s.section_id for s in sections],
        }

        self._emit("kanon.loaded", result)
        log.info("loaded %d kanon sections", len(sections))
        return result

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def store_section(self, section: KanonSection) -> dict:
        """Store a single KanonSection."""
        with self._lock:
            self._store_section_unlocked(section)

        self._emit("kanon.section_stored", {
            "section_id": section.section_id,
            "title": section.title,
            "hash": section.hash,
        })
        return {"section_id": section.section_id, "hash": section.hash}

    def _store_section_unlocked(self, section: KanonSection):
        """Internal: store section without acquiring lock."""
        self._conn.execute("""
            INSERT OR REPLACE INTO kanon_sections
            (section_id, title, content, chapter, section_number, hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            section.section_id, section.title, section.content,
            section.chapter, section.section_number, section.hash,
        ))
        self._conn.commit()

    def get_section(self, section_id: str) -> dict | None:
        """Retrieve a single section by ID."""
        row = self._conn.execute(
            "SELECT * FROM kanon_sections WHERE section_id = ?", (section_id,)
        ).fetchone()
        return dict(row) if row else None

    def search(self, query_text: str, limit: int = 10) -> list[dict]:
        """LIKE search on section content and title."""
        pattern = f"%{query_text}%"
        rows = self._conn.execute("""
            SELECT * FROM kanon_sections
            WHERE content LIKE ? OR title LIKE ?
            ORDER BY section_number ASC
            LIMIT ?
        """, (pattern, pattern, limit)).fetchall()
        return [dict(r) for r in rows]

    def list_sections(self, chapter: str | None = None) -> list[dict]:
        """List all sections, optionally filtered by chapter."""
        if chapter:
            rows = self._conn.execute(
                "SELECT * FROM kanon_sections WHERE chapter = ? ORDER BY section_number ASC",
                (chapter,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM kanon_sections ORDER BY section_number ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_full_text(self) -> str:
        """Return the full canon text, assembled from sections in order."""
        rows = self._conn.execute(
            "SELECT title, content FROM kanon_sections ORDER BY section_number ASC"
        ).fetchall()
        parts: list[str] = []
        for row in rows:
            if row["title"]:
                parts.append(f"# {row['title']}")
            if row["content"]:
                parts.append(row["content"])
            parts.append("")  # blank line between sections
        return "\n".join(parts).strip()

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="memory.kanon_access",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_kanon: KanonAccess | None = None


def get_kanon_access(event_bus: EventBus | None = None,
                     db_path: str | Path | None = None) -> KanonAccess:
    global _kanon
    if _kanon is None:
        _kanon = KanonAccess(event_bus, db_path)
    return _kanon


def reset_kanon_access() -> None:
    global _kanon
    _kanon = None
