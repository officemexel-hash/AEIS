"""
SYLION Cognitive -- Knowledge Distiller

Manages distilled knowledge entries from AI interactions. Tracks entries,
sources, and cross-references between knowledge items.

Tables:
  knowledge_entries, knowledge_sources, knowledge_links

Singleton: get_knowledge_distiller() / reset_knowledge_distiller()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.cognitive.knowledge_distiller")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = ("fact", "procedure", "concept", "insight", "reference", "rule")


# ---------------------------------------------------------------------------
# Knowledge Distiller
# ---------------------------------------------------------------------------

class KnowledgeDistiller:
    """Manages distilled knowledge entries from AI interactions.

    Thread-safe. SQLite-backed. Emits events on entry mutations.
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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                entry_id    TEXT PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT '',
                content     TEXT NOT NULL DEFAULT '',
                category    TEXT NOT NULL DEFAULT 'fact',
                tags_json   TEXT NOT NULL DEFAULT '[]',
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge_sources (
                source_id       TEXT PRIMARY KEY,
                entry_id        TEXT NOT NULL,
                source_type     TEXT NOT NULL DEFAULT '',
                source_ref      TEXT NOT NULL DEFAULT '',
                relevance_score REAL NOT NULL DEFAULT 0.0,
                added_at        REAL NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES knowledge_entries(entry_id)
            );
            CREATE TABLE IF NOT EXISTS knowledge_links (
                link_id     TEXT PRIMARY KEY,
                from_id     TEXT NOT NULL,
                to_id       TEXT NOT NULL,
                link_type   TEXT NOT NULL DEFAULT 'related',
                created_at  REAL NOT NULL,
                FOREIGN KEY (from_id) REFERENCES knowledge_entries(entry_id),
                FOREIGN KEY (to_id) REFERENCES knowledge_entries(entry_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ke_category ON knowledge_entries(category);
            CREATE INDEX IF NOT EXISTS idx_ke_created ON knowledge_entries(created_at);
            CREATE INDEX IF NOT EXISTS idx_ks_entry ON knowledge_sources(entry_id);
            CREATE INDEX IF NOT EXISTS idx_kl_from ON knowledge_links(from_id);
            CREATE INDEX IF NOT EXISTS idx_kl_to ON knowledge_links(to_id);
        """)
        self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.knowledge_distiller",
            ))

    # ------------------------------------------------------------------
    # Entry CRUD
    # ------------------------------------------------------------------

    def create_entry(self, title: str, content: str, category: str = "fact",
                     tags_json: str = "[]") -> dict:
        """Create a new knowledge entry. Returns entry dict."""
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. "
                f"Must be one of {VALID_CATEGORIES}"
            )
        try:
            tags = json.loads(tags_json)
            if not isinstance(tags, list):
                raise ValueError("tags_json must be a JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid tags_json: {exc}") from exc

        entry_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute(
                "INSERT INTO knowledge_entries "
                "(entry_id, title, content, category, tags_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry_id, title, content, category, tags_json, now, now),
            )
            self._conn.commit()

        result = {
            "entry_id": entry_id, "title": title, "content": content,
            "category": category, "tags_json": tags_json,
            "created_at": now, "updated_at": now,
        }
        self._emit("entry_created", {"entry_id": entry_id, "category": category})
        log.info("create_entry %s [%s]", entry_id[:12], category)
        return result

    def update_entry(self, entry_id: str, **fields) -> dict | None:
        """Update mutable fields on an entry. Returns updated dict or None."""
        allowed = {"title", "content", "category", "tags_json"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_entry(entry_id)

        if "category" in updates and updates["category"] not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{updates['category']}'. "
                f"Must be one of {VALID_CATEGORIES}"
            )
        if "tags_json" in updates:
            try:
                tags = json.loads(updates["tags_json"])
                if not isinstance(tags, list):
                    raise ValueError("tags_json must be a JSON array")
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid tags_json: {exc}") from exc

        now = time.time()
        updates["updated_at"] = now

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM knowledge_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
            if not row:
                return None

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [entry_id]
            self._conn.execute(
                f"UPDATE knowledge_entries SET {set_clause} WHERE entry_id = ?",
                values,
            )
            self._conn.commit()

        result = dict(row)
        result.update(updates)
        self._emit("entry_updated", {"entry_id": entry_id, "fields": list(fields.keys())})
        log.info("update_entry %s", entry_id[:12])
        return result

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry and its associated sources/links. Returns True if deleted."""
        with self._lock:
            row = self._conn.execute(
                "SELECT entry_id FROM knowledge_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
            if not row:
                return False

            self._conn.execute(
                "DELETE FROM knowledge_sources WHERE entry_id = ?", (entry_id,),
            )
            self._conn.execute(
                "DELETE FROM knowledge_links WHERE from_id = ? OR to_id = ?",
                (entry_id, entry_id),
            )
            self._conn.execute(
                "DELETE FROM knowledge_entries WHERE entry_id = ?", (entry_id,),
            )
            self._conn.commit()

        log.info("delete_entry %s", entry_id[:12])
        return True

    def get_entry(self, entry_id: str) -> dict | None:
        """Retrieve a single entry by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM knowledge_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_entries(self, category: str | None = None,
                     tags: list[str] | None = None,
                     limit: int = 100) -> list[dict]:
        """List entries with optional filters."""
        with self._lock:
            clauses: list[str] = []
            params: list = []

            if category is not None:
                if category not in VALID_CATEGORIES:
                    raise ValueError(
                        f"Invalid category '{category}'. "
                        f"Must be one of {VALID_CATEGORIES}"
                    )
                clauses.append("category = ?")
                params.append(category)

            if tags:
                tag_clauses = []
                for tag in tags:
                    tag_clauses.append("tags_json LIKE ?")
                    params.append(f'%"{tag}"%')
                clauses.append(f"({' AND '.join(tag_clauses)})")

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = self._conn.execute(
                f"SELECT * FROM knowledge_entries{where} "
                f"ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()

        return [dict(r) for r in rows]

    def search_entries(self, query: str, limit: int = 50) -> list[dict]:
        """Full-text search on title and content."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM knowledge_entries "
                "WHERE title LIKE ? OR content LIKE ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def add_source(self, entry_id: str, source_type: str,
                   source_ref: str, relevance_score: float = 1.0) -> dict | None:
        """Add a source reference to an entry. Returns source dict or None."""
        relevance_score = max(0.0, min(1.0, relevance_score))
        source_id = self._uid()
        now = time.time()

        with self._lock:
            row = self._conn.execute(
                "SELECT entry_id FROM knowledge_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
            if not row:
                return None

            self._conn.execute(
                "INSERT INTO knowledge_sources "
                "(source_id, entry_id, source_type, source_ref, relevance_score, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source_id, entry_id, source_type, source_ref, relevance_score, now),
            )
            self._conn.commit()

        result = {
            "source_id": source_id, "entry_id": entry_id,
            "source_type": source_type, "source_ref": source_ref,
            "relevance_score": relevance_score, "added_at": now,
        }
        log.info("add_source %s -> %s", source_id[:12], entry_id[:12])
        return result

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------

    def link_entries(self, from_id: str, to_id: str,
                     link_type: str = "related") -> dict | None:
        """Create a link between two entries. Returns link dict."""
        if from_id == to_id:
            raise ValueError("Cannot link an entry to itself")

        link_id = self._uid()
        now = time.time()

        with self._lock:
            row_from = self._conn.execute(
                "SELECT entry_id FROM knowledge_entries WHERE entry_id = ?",
                (from_id,),
            ).fetchone()
            row_to = self._conn.execute(
                "SELECT entry_id FROM knowledge_entries WHERE entry_id = ?",
                (to_id,),
            ).fetchone()
            if not row_from or not row_to:
                return None

            self._conn.execute(
                "INSERT INTO knowledge_links "
                "(link_id, from_id, to_id, link_type, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (link_id, from_id, to_id, link_type, now),
            )
            self._conn.commit()

        result = {
            "link_id": link_id, "from_id": from_id, "to_id": to_id,
            "link_type": link_type, "created_at": now,
        }
        self._emit("entry_linked", {
            "link_id": link_id, "from_id": from_id,
            "to_id": to_id, "link_type": link_type,
        })
        log.info("link_entries %s -> %s [%s]", from_id[:12], to_id[:12], link_type)
        return result

    def get_linked(self, entry_id: str) -> list[dict]:
        """Get all entries linked to the given entry."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT l.link_id, l.from_id, l.to_id, l.link_type, l.created_at, "
                "e.entry_id, e.title, e.category "
                "FROM knowledge_links l "
                "JOIN knowledge_entries e ON "
                "  CASE WHEN l.from_id = ? THEN e.entry_id = l.to_id "
                "       ELSE e.entry_id = l.from_id END "
                "WHERE l.from_id = ? OR l.to_id = ? "
                "ORDER BY l.created_at DESC",
                (entry_id, entry_id, entry_id),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate knowledge distiller statistics."""
        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM knowledge_entries",
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            cat_rows = self._conn.execute(
                "SELECT category, COUNT(*) as cnt "
                "FROM knowledge_entries GROUP BY category",
            ).fetchall()
            by_category = {r["category"]: r["cnt"] for r in cat_rows}

            source_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM knowledge_sources",
            ).fetchone()["cnt"]

            link_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM knowledge_links",
            ).fetchone()["cnt"]

        return {
            "total_entries": total,
            "by_category": {c: by_category.get(c, 0) for c in VALID_CATEGORIES},
            "total_sources": source_count,
            "total_links": link_count,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_distiller: KnowledgeDistiller | None = None


def get_knowledge_distiller(db_path: str | Path | None = None,
                            event_bus: EventBus | None = None) -> KnowledgeDistiller:
    global _distiller
    if _distiller is None:
        _distiller = KnowledgeDistiller(db_path, event_bus)
    return _distiller


def reset_knowledge_distiller(db_path: str | Path | None = None,
                              event_bus: EventBus | None = None) -> KnowledgeDistiller:
    global _distiller
    _distiller = KnowledgeDistiller(db_path, event_bus)
    return _distiller
