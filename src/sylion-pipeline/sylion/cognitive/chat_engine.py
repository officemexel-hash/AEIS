"""
SYLION Cognitive — Chat Engine

Thread-safe multi-model chat engine backed by SQLite.

Tables:
  chat_sessions     -- conversation sessions
  chat_messages     -- individual messages within sessions
  chat_attachments  -- file attachments linked to messages

Singleton: get_chat_engine() / reset_chat_engine()
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

log = logging.getLogger("sylion.cognitive.chat_engine")


class ChatEngine:
    """Thread-safe chat engine backed by SQLite.

    Manages chat sessions, messages, and attachments with full CRUD
    operations, search, statistics, and EventBus integration.
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
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id    TEXT PRIMARY KEY,
                title         TEXT NOT NULL DEFAULT '',
                model_id      TEXT NOT NULL DEFAULT '',
                system_prompt TEXT NOT NULL DEFAULT '',
                status        TEXT NOT NULL DEFAULT 'active',
                created_at    REAL NOT NULL,
                updated_at    REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                message_id  TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL DEFAULT '',
                model_id    TEXT NOT NULL DEFAULT '',
                metadata    TEXT,
                created_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_attachments (
                attachment_id TEXT PRIMARY KEY,
                message_id   TEXT NOT NULL,
                filename     TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_data    BLOB,
                size         INTEGER NOT NULL DEFAULT 0,
                created_at   REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_status
                ON chat_sessions(status);
            CREATE INDEX IF NOT EXISTS idx_sessions_updated
                ON chat_sessions(updated_at);
            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON chat_messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_created
                ON chat_messages(created_at);
            CREATE INDEX IF NOT EXISTS idx_attachments_message
                ON chat_attachments(message_id);
        """)
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
                source_module="cognitive.chat_engine",
            ))

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        if "metadata" in d and isinstance(d["metadata"], str):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def create_session(self, title: str, model_id: str = "",
                       system_prompt: str = "") -> dict:
        """Create a new chat session.

        Args:
            title: Human-readable session title.
            model_id: Default model identifier for the session.
            system_prompt: Optional system prompt for the session.

        Returns:
            The created session as a dict.
        """
        session_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO chat_sessions
                    (session_id, title, model_id, system_prompt,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
            """, (session_id, title, model_id, system_prompt, now, now))
            self._conn.commit()

        result = self.get_session(session_id)
        self._emit("chat.session.created", {
            "session_id": session_id,
            "title": title,
            "model_id": model_id,
        })
        log.info("session created: %s (%s)", session_id, title)
        return result

    def list_sessions(self, archived: bool = False, limit: int = 50,
                      offset: int = 0) -> list[dict]:
        """List sessions, optionally including archived ones.

        Args:
            archived: If True, include archived sessions. Otherwise only active.
            limit: Maximum number of sessions to return.
            offset: Number of sessions to skip.

        Returns:
            List of session dicts ordered by updated_at descending.
        """
        with self._lock:
            if archived:
                rows = self._conn.execute(
                    "SELECT * FROM chat_sessions "
                    "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM chat_sessions WHERE status = 'active' "
                    "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [self._parse_row(r) for r in rows]

    def get_session(self, session_id: str) -> dict | None:
        """Return a single session by ID, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def archive_session(self, session_id: str) -> dict | None:
        """Archive a session by setting its status to 'archived'.

        Args:
            session_id: The session to archive.

        Returns:
            The updated session dict, or None if not found.
        """
        now = time.time()
        with self._lock:
            existing = self._conn.execute(
                "SELECT session_id FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not existing:
                return None
            self._conn.execute(
                "UPDATE chat_sessions SET status = 'archived', updated_at = ? "
                "WHERE session_id = ?",
                (now, session_id),
            )
            self._conn.commit()
        result = self.get_session(session_id)
        self._emit("chat.session.archived", {
            "session_id": session_id,
        })
        log.info("session archived: %s", session_id)
        return result

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def send_message(self, session_id: str, role: str, content: str,
                     model_id: str | None = None,
                     metadata: dict | None = None) -> dict:
        """Send a message to a session.

        Creates the message record and emits a chat.message.sent event.

        Args:
            session_id: Target session.
            role: Message role (user, assistant, system).
            content: Message text content.
            model_id: Optional model that generated this message.
            metadata: Optional arbitrary metadata dict.

        Returns:
            The created message as a dict.
        """
        message_id = self._uid()
        now = time.time()
        metadata_json = (
            json.dumps(metadata, sort_keys=True, default=str)
            if metadata is not None else None
        )
        effective_model = model_id or ""

        with self._lock:
            self._conn.execute("""
                INSERT INTO chat_messages
                    (message_id, session_id, role, content,
                     model_id, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (message_id, session_id, role, content,
                  effective_model, metadata_json, now))
            # Touch session updated_at
            self._conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            self._conn.commit()

        result = self.get_message(message_id)
        self._emit("chat.message.sent", {
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
        })
        log.info("message sent: %s in session %s (role=%s)",
                 message_id, session_id, role)
        return result

    def list_messages(self, session_id: str, limit: int = 100,
                      offset: int = 0) -> list[dict]:
        """List messages for a session.

        Args:
            session_id: Target session.
            limit: Maximum messages to return.
            offset: Number of messages to skip.

        Returns:
            List of message dicts ordered by created_at ascending.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? "
                "ORDER BY created_at ASC LIMIT ? OFFSET ?",
                (session_id, limit, offset),
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    def get_message(self, message_id: str) -> dict | None:
        """Return a single message by ID, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM chat_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def delete_message(self, message_id: str) -> bool:
        """Delete a message by ID.

        Also deletes any attachments linked to the message.

        Args:
            message_id: The message to delete.

        Returns:
            True if a message was deleted, False otherwise.
        """
        with self._lock:
            existing = self._conn.execute(
                "SELECT message_id FROM chat_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if not existing:
                return False
            # Delete attachments first (FK-like cleanup)
            self._conn.execute(
                "DELETE FROM chat_attachments WHERE message_id = ?",
                (message_id,),
            )
            self._conn.execute(
                "DELETE FROM chat_messages WHERE message_id = ?",
                (message_id,),
            )
            self._conn.commit()
        log.info("message deleted: %s", message_id)
        return True

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    def upload_attachment(self, message_id: str, filename: str,
                          content_type: str, file_data: bytes) -> dict:
        """Upload a file attachment for a message.

        Args:
            message_id: Target message.
            filename: Original file name.
            content_type: MIME type of the file.
            file_data: Raw file bytes.

        Returns:
            The created attachment as a dict.
        """
        attachment_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO chat_attachments
                    (attachment_id, message_id, filename,
                     content_type, file_data, size, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (attachment_id, message_id, filename,
                  content_type, file_data, len(file_data), now))
            self._conn.commit()

        result = {
            "attachment_id": attachment_id,
            "message_id": message_id,
            "filename": filename,
            "content_type": content_type,
            "size": len(file_data),
            "created_at": now,
        }
        self._emit("chat.attachment.uploaded", {
            "attachment_id": attachment_id,
            "message_id": message_id,
            "filename": filename,
        })
        log.info("attachment uploaded: %s (%s, %d bytes)",
                 attachment_id, filename, len(file_data))
        return result

    def list_attachments(self, message_id: str) -> list[dict]:
        """List all attachments for a message.

        Returns attachment metadata without the binary file_data blob.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT attachment_id, message_id, filename, "
                "       content_type, size, created_at "
                "FROM chat_attachments WHERE message_id = ? "
                "ORDER BY created_at ASC",
                (message_id,),
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    def get_attachment(self, attachment_id: str) -> dict | None:
        """Return a single attachment by ID, including file_data.

        Returns None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM chat_attachments WHERE attachment_id = ?",
                (attachment_id,),
            ).fetchone()
        if not row:
            return None
        d = self._parse_row(row)
        # Convert blob to bytes if needed
        if isinstance(d.get("file_data"), memoryview):
            d["file_data"] = bytes(d["file_data"])
        return d

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_messages(self, query: str, session_id: str | None = None,
                        limit: int = 20) -> list[dict]:
        """Search messages by content using LIKE.

        Args:
            query: Search term (case-insensitive).
            session_id: Optional session to restrict search to.
            limit: Maximum results to return.

        Returns:
            List of matching message dicts ordered by created_at descending.
        """
        pattern = f"%{query}%"
        with self._lock:
            if session_id:
                rows = self._conn.execute(
                    "SELECT * FROM chat_messages "
                    "WHERE content LIKE ? AND session_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (pattern, session_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM chat_messages "
                    "WHERE content LIKE ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (pattern, limit),
                ).fetchall()
        return [self._parse_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_session_stats(self, session_id: str) -> dict:
        """Return aggregate statistics for a session.

        Returns:
            Dict with message counts by role, attachment count,
            first/last message timestamps, etc.
        """
        with self._lock:
            # Total messages
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM chat_messages "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            total_messages = total_row["cnt"] if total_row else 0

            # Messages by role
            role_rows = self._conn.execute(
                "SELECT role, COUNT(*) as cnt FROM chat_messages "
                "WHERE session_id = ? GROUP BY role",
                (session_id,),
            ).fetchall()
            messages_by_role = {r["role"]: r["cnt"] for r in role_rows}

            # Attachment count
            att_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM chat_attachments a "
                "INNER JOIN chat_messages m ON a.message_id = m.message_id "
                "WHERE m.session_id = ?",
                (session_id,),
            ).fetchone()
            attachment_count = att_row["cnt"] if att_row else 0

            # Total attachment size
            size_row = self._conn.execute(
                "SELECT COALESCE(SUM(a.size), 0) as total_size "
                "FROM chat_attachments a "
                "INNER JOIN chat_messages m ON a.message_id = m.message_id "
                "WHERE m.session_id = ?",
                (session_id,),
            ).fetchone()
            total_attachment_size = size_row["total_size"] if size_row else 0

            # First and last message timestamps
            first_row = self._conn.execute(
                "SELECT created_at FROM chat_messages "
                "WHERE session_id = ? ORDER BY created_at ASC LIMIT 1",
                (session_id,),
            ).fetchone()
            last_row = self._conn.execute(
                "SELECT created_at FROM chat_messages "
                "WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()

        return {
            "session_id": session_id,
            "total_messages": total_messages,
            "messages_by_role": messages_by_role,
            "attachment_count": attachment_count,
            "total_attachment_size": total_attachment_size,
            "first_message_at": first_row["created_at"] if first_row else None,
            "last_message_at": last_row["created_at"] if last_row else None,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: ChatEngine | None = None


def _audit_redirect(db_path: str | Path | None) -> str | Path | None:
    """Persist default chat state inside the active audit profile.

    Explicit ``:memory:`` stays in memory for unit tests. In audit mode a
    missing path becomes ``chat_engine.db`` so council/chat evidence survives
    backend restarts instead of living only in process RAM.
    """
    if db_path is not None and str(db_path) == ":memory:":
        return db_path
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path

    if not is_audit_mode():
        return db_path
    return resolve_db_path(Path(db_path) if db_path is not None else Path("chat_engine.db"))


def get_chat_engine(db_path: str | Path | None = None,
                    event_bus: EventBus | None = None) -> ChatEngine:
    global _engine
    if _engine is None:
        _engine = ChatEngine(_audit_redirect(db_path), event_bus)
    return _engine


def reset_chat_engine(db_path: str | Path | None = None,
                      event_bus: EventBus | None = None) -> ChatEngine:
    global _engine
    _engine = ChatEngine(_audit_redirect(db_path), event_bus)
    return _engine
