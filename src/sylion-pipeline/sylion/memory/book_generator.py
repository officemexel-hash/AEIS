"""
SYLION Memory — Book Generator

Compiles conversations, council sessions, and other sources into structured
books with chapters.  Follows the evidence_spine pattern: SQLite + RLock +
singleton + EventBus _emit() helper.

Tables:
  generated_books  -- one row per book
  book_chapters    -- ordered chapters belonging to a book

Singleton: get_book_generator() / reset_book_generator()
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.memory.book_generator")

VALID_SOURCE_TYPES = ("chat", "council", "manual", "kanon", "pipeline")


class BookGenerator:
    """Compiles multi-source content into structured books with chapters."""

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
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_books (
                book_id       TEXT PRIMARY KEY,
                title         TEXT NOT NULL,
                description   TEXT,
                team_id       TEXT,
                project_id    TEXT,
                source_type   TEXT,
                source_id     TEXT,
                created_by    TEXT,
                chapter_count INTEGER NOT NULL DEFAULT 0,
                status        TEXT NOT NULL DEFAULT 'draft',
                created_at    REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS book_chapters (
                chapter_id      TEXT PRIMARY KEY,
                book_id         TEXT NOT NULL,
                title           TEXT NOT NULL,
                content         TEXT NOT NULL DEFAULT '',
                chapter_order   INTEGER NOT NULL DEFAULT 0,
                chapter_number  INTEGER NOT NULL DEFAULT 0,
                hash            TEXT,
                source_type     TEXT,
                source_id       TEXT,
                created_at      REAL NOT NULL,
                FOREIGN KEY (book_id) REFERENCES generated_books(book_id) ON DELETE CASCADE
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_books_source_type "
            "ON generated_books(source_type)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_books_status "
            "ON generated_books(status)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_books_team "
            "ON generated_books(team_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chapters_book_id "
            "ON book_chapters(book_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chapters_order "
            "ON book_chapters(book_id, chapter_order)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="memory.book_generator",
            ))

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        return dict(row)

    def _book_exists(self, book_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM generated_books WHERE book_id = ?",
            (book_id,),
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # Book CRUD
    # ------------------------------------------------------------------

    def create_book(
        self,
        title: str,
        description: str | None = None,
        team_id: str | None = None,
        project_id: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        created_by: str | None = None,
    ) -> dict:
        if source_type is not None and source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"Invalid source_type '{source_type}', "
                f"must be one of {VALID_SOURCE_TYPES}"
            )

        book_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO generated_books
                    (book_id, title, description, team_id, project_id,
                     source_type, source_id, created_by,
                     chapter_count, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'draft', ?)
            """, (
                book_id, title, description, team_id, project_id,
                source_type, source_id, created_by, now,
            ))
            self._conn.commit()

        result = {
            "book_id": book_id,
            "title": title,
            "description": description,
            "team_id": team_id,
            "project_id": project_id,
            "source_type": source_type,
            "source_id": source_id,
            "created_by": created_by,
            "chapter_count": 0,
            "status": "draft",
            "created_at": now,
        }

        self._emit("book.created", {"book_id": book_id, "title": title})
        log.info("book created: %s (%s)", book_id, title)
        return result

    def get_book(self, book_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM generated_books WHERE book_id = ?",
                (book_id,),
            ).fetchone()
            if not row:
                return None
            book = self._parse_row(row)
            ch_rows = self._conn.execute(
                "SELECT * FROM book_chapters WHERE book_id = ? "
                "ORDER BY chapter_number ASC, chapter_order ASC",
                (book_id,),
            ).fetchall()
            book["chapters"] = [self._parse_row(r) for r in ch_rows]
        return book

    def list_books(
        self,
        source_type: str | None = None,
        status: str | None = None,
        team_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        with self._lock:
            q = "SELECT * FROM generated_books WHERE 1=1"
            params: list[Any] = []
            if source_type is not None:
                q += " AND source_type = ?"
                params.append(source_type)
            if status is not None:
                q += " AND status = ?"
                params.append(status)
            if team_id is not None:
                q += " AND team_id = ?"
                params.append(team_id)
            q += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = self._conn.execute(q, params).fetchall()
        return [self._parse_row(r) for r in rows]

    def delete_book(self, book_id: str) -> bool:
        with self._lock:
            if not self._book_exists(book_id):
                return False
            self._conn.execute(
                "DELETE FROM book_chapters WHERE book_id = ?",
                (book_id,),
            )
            self._conn.execute(
                "DELETE FROM generated_books WHERE book_id = ?",
                (book_id,),
            )
            self._conn.commit()
        return True

    # ------------------------------------------------------------------
    # Chapter CRUD
    # ------------------------------------------------------------------

    def add_chapter(
        self,
        book_id: str,
        title: str,
        content: str,
        chapter_order: int | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> dict:
        chapter_id = self._uid()
        now = time.time()
        content_hash = hashlib.sha256(
            f"{book_id}:{title}:{content}:{now}".encode()
        ).hexdigest()[:12]

        with self._lock:
            if not self._book_exists(book_id):
                raise ValueError(f"Book '{book_id}' does not exist")

            # Get next chapter_number
            max_row = self._conn.execute(
                "SELECT MAX(chapter_number) as max_num "
                "FROM book_chapters WHERE book_id = ?",
                (book_id,),
            ).fetchone()
            chapter_number = (max_row["max_num"] or 0) + 1

            if chapter_order is None:
                chapter_order = chapter_number

            self._conn.execute("""
                INSERT INTO book_chapters
                    (chapter_id, book_id, title, content, chapter_order,
                     chapter_number, hash, source_type, source_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chapter_id, book_id, title, content, chapter_order,
                chapter_number, content_hash, source_type, source_id, now,
            ))
            self._conn.execute(
                "UPDATE generated_books SET chapter_count = chapter_count + 1 "
                "WHERE book_id = ?",
                (book_id,),
            )
            self._conn.commit()

        result = {
            "chapter_id": chapter_id,
            "book_id": book_id,
            "title": title,
            "content": content,
            "chapter_order": chapter_order,
            "chapter_number": chapter_number,
            "hash": content_hash,
            "source_type": source_type,
            "source_id": source_id,
            "created_at": now,
        }

        self._emit("book.chapter.added", {
            "chapter_id": chapter_id,
            "book_id": book_id,
        })
        log.info("chapter added: %s to book %s (num=%d)",
                 chapter_id, book_id, chapter_number)
        return result

    def update_chapter(self, chapter_id: str, **kwargs) -> dict | None:
        allowed = {"title", "content", "chapter_order", "source_type", "source_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_chapter(chapter_id)

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM book_chapters WHERE chapter_id = ?",
                (chapter_id,),
            ).fetchone()
            if not row:
                return None

            set_clauses = [f"{k} = ?" for k in updates]
            values = list(updates.values())
            values.append(chapter_id)
            self._conn.execute(
                f"UPDATE book_chapters SET {', '.join(set_clauses)} "
                f"WHERE chapter_id = ?",
                values,
            )
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM book_chapters WHERE chapter_id = ?",
                (chapter_id,),
            ).fetchone()

        return self._parse_row(row) if row else None

    def get_chapter(self, chapter_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM book_chapters WHERE chapter_id = ?",
                (chapter_id,),
            ).fetchone()
        return self._parse_row(row) if row else None

    def list_chapters(self, book_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM book_chapters WHERE book_id = ? "
                "ORDER BY chapter_order ASC, chapter_number ASC",
                (book_id,),
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    def get_chapters(self, book_id: str) -> list[dict]:
        return self.list_chapters(book_id)

    def delete_chapter(self, chapter_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT book_id FROM book_chapters WHERE chapter_id = ?",
                (chapter_id,),
            ).fetchone()
            if not row:
                return False
            book_id = row["book_id"]
            self._conn.execute(
                "DELETE FROM book_chapters WHERE chapter_id = ?",
                (chapter_id,),
            )
            self._conn.execute(
                "UPDATE generated_books SET chapter_count = chapter_count - 1 "
                "WHERE book_id = ?",
                (book_id,),
            )
            self._conn.commit()
        return True

    def reorder_chapters(self, book_id: str, chapter_ids: list[str]) -> dict:
        with self._lock:
            for idx, cid in enumerate(chapter_ids):
                self._conn.execute(
                    "UPDATE book_chapters SET chapter_order = ?, chapter_number = ? "
                    "WHERE chapter_id = ? AND book_id = ?",
                    (idx, idx + 1, cid, book_id),
                )
            self._conn.commit()
        return {"book_id": book_id, "reordered": len(chapter_ids)}

    # ------------------------------------------------------------------
    # Generation helpers
    # ------------------------------------------------------------------

    def generate_from_chat(
        self,
        book_id: str,
        session_ids: list[str] | str,
        chapter_count: int = 5,
    ) -> dict:
        if isinstance(session_ids, str):
            session_ids = [session_ids]

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM generated_books WHERE book_id = ?",
                (book_id,),
            ).fetchone()
            if not row:
                return {}
            self._conn.execute(
                "UPDATE generated_books SET status = 'generating' "
                "WHERE book_id = ?",
                (book_id,),
            )
            self._conn.commit()

        for idx, session_id in enumerate(session_ids):
            messages = [
                f"Message {i+1} from session {session_id}"
                for i in range(chapter_count)
            ]
            group_size = max(1, len(messages) // chapter_count)
            for ch_idx in range(chapter_count):
                start = ch_idx * group_size
                end = start + group_size if ch_idx < chapter_count - 1 else len(messages)
                group = messages[start:end]
                content = " ".join(group)
                self.add_chapter(
                    book_id,
                    f"Chapter {ch_idx + 1}",
                    content,
                    chapter_order=ch_idx,
                    source_type="chat",
                    source_id=session_id,
                )

        with self._lock:
            self._conn.execute(
                "UPDATE generated_books SET status = 'complete' "
                "WHERE book_id = ?",
                (book_id,),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM generated_books WHERE book_id = ?",
                (book_id,),
            ).fetchone()

        self._emit("book.generated", {
            "book_id": book_id, "source": "chat",
        })
        return self._parse_row(row) if row else {}

    def generate_from_council(
        self,
        book_id: str,
        council_session_ids: list[str] | str,
    ) -> dict:
        if isinstance(council_session_ids, str):
            council_session_ids = [council_session_ids]

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM generated_books WHERE book_id = ?",
                (book_id,),
            ).fetchone()
            if not row:
                return {}
            self._conn.execute(
                "UPDATE generated_books SET status = 'generating' "
                "WHERE book_id = ?",
                (book_id,),
            )
            self._conn.commit()

        for session_id in council_session_ids:
            chapter_templates = [
                ("Analyses", f"Council analyses for session {session_id}"),
                ("Discussion", f"Council discussion for session {session_id}"),
                ("Consolidated", f"Consolidated view for session {session_id}"),
                ("Recommendations", f"Recommendations from session {session_id}"),
            ]

            for title, content in chapter_templates:
                self.add_chapter(
                    book_id, title, content,
                    source_type="council",
                    source_id=session_id,
                )

        with self._lock:
            self._conn.execute(
                "UPDATE generated_books SET status = 'complete' "
                "WHERE book_id = ?",
                (book_id,),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM generated_books WHERE book_id = ?",
                (book_id,),
            ).fetchone()

        self._emit("book.generated", {
            "book_id": book_id, "source": "council",
        })
        return self._parse_row(row) if row else {}

    def generate_from_kanon(self, book_id: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM generated_books WHERE book_id = ?",
                (book_id,),
            ).fetchone()
            if not row:
                return {}
            self._conn.execute(
                "UPDATE generated_books SET status = 'generating' "
                "WHERE book_id = ?",
                (book_id,),
            )
            self._conn.commit()

        kanon_chapters = [
            ("Foundations", "Core principles and architecture foundations from the Kanon."),
            ("Patterns", "Established patterns and best practices documented in the Kanon."),
            ("Evolution", "Historical evolution of decisions and their outcomes."),
        ]
        for title, content in kanon_chapters:
            self.add_chapter(
                book_id, title, content,
                source_type="kanon",
            )

        with self._lock:
            self._conn.execute(
                "UPDATE generated_books SET status = 'complete' "
                "WHERE book_id = ?",
                (book_id,),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM generated_books WHERE book_id = ?",
                (book_id,),
            ).fetchone()

        self._emit("book.generated", {
            "book_id": book_id, "source": "kanon",
        })
        return self._parse_row(row) if row else {}

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_book(self, book_id: str, format: str = "markdown") -> str:
        book = self.get_book(book_id)
        if book is None:
            return ""

        if format == "json":
            result = json.dumps(book, indent=2, default=str)
            self._emit("book.exported", {
                "book_id": book_id, "format": "json",
            })
            return result

        parts = [f"# {book['title']}", ""]
        if book.get("description"):
            parts.append(book["description"])
            parts.append("")
        for ch in book.get("chapters", []):
            parts.append(f"## {ch['title']}")
            parts.append("")
            parts.append(ch.get("content", ""))
            parts.append("")

        self._emit("book.exported", {
            "book_id": book_id, "format": "markdown",
        })
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Stats & Search
    # ------------------------------------------------------------------

    def get_book_stats(self) -> dict:
        with self._lock:
            total_books = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM generated_books"
            ).fetchone()["cnt"]

            total_chapters = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM book_chapters"
            ).fetchone()["cnt"]

            rows = self._conn.execute(
                "SELECT source_type, COUNT(*) AS cnt FROM generated_books "
                "GROUP BY source_type"
            ).fetchall()
            by_source = {r["source_type"]: r["cnt"] for r in rows}

            avg_row = self._conn.execute(
                "SELECT AVG(chapter_count) AS avg FROM generated_books"
            ).fetchone()
            avg_chapters = round(avg_row["avg"], 2) if avg_row["avg"] else 0.0

        return {
            "total_books": total_books,
            "total_chapters": total_chapters,
            "by_source_type": by_source,
            "avg_chapters_per_book": avg_chapters,
        }

    def search_books(self, query: str) -> list[dict]:
        like = f"%{query}%"
        with self._lock:
            book_rows = self._conn.execute(
                "SELECT * FROM generated_books "
                "WHERE title LIKE ? OR description LIKE ? "
                "ORDER BY created_at DESC",
                (like, like),
            ).fetchall()
            books = [self._parse_row(r) for r in book_rows]

            ch_rows = self._conn.execute(
                "SELECT DISTINCT book_id FROM book_chapters "
                "WHERE title LIKE ? OR content LIKE ?",
                (like, like),
            ).fetchall()
            chapter_book_ids = {r["book_id"] for r in ch_rows}

        existing_ids = {b["book_id"] for b in books}
        for bid in chapter_book_ids:
            if bid not in existing_ids:
                book = self.get_book(bid)
                if book:
                    books.append(book)
                    existing_ids.add(bid)

        return books


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_gen: BookGenerator | None = None


def get_book_generator(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> BookGenerator:
    global _gen
    if _gen is None:
        _gen = BookGenerator(db_path, event_bus)
    return _gen


def reset_book_generator(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> BookGenerator:
    global _gen
    _gen = BookGenerator(db_path, event_bus)
    return _gen
