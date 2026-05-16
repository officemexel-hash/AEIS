"""
SYLION Security -- Session Broker

Session management with configurable timeout and activity tracking.
SQLite-backed managed session storage with expiry, refresh, and cleanup.
Thread-safe. Emits events via EventBus.
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

log = logging.getLogger("sylion.security.session_broker")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ManagedSession:
    """A managed session with timeout tracking."""
    session_id: str = ""
    user_id: str = ""
    token: str = ""
    created_at: float = 0.0
    last_activity: float = 0.0
    timeout_seconds: int = 3600
    ip_address: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.session_id:
            self.session_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
        if not self.last_activity:
            self.last_activity = self.created_at


# ---------------------------------------------------------------------------
# SessionBroker
# ---------------------------------------------------------------------------

class SessionBroker:
    """Session management with timeout and activity tracking.

    Each session has a configurable timeout (default 3600s).
    Sessions are validated against last_activity + timeout_seconds.
    Expired sessions are cleaned up on validate() and cleanup_expired().
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
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
            CREATE TABLE IF NOT EXISTS managed_sessions (
                session_id       TEXT PRIMARY KEY,
                user_id          TEXT NOT NULL DEFAULT '',
                token            TEXT NOT NULL DEFAULT '',
                created_at       REAL NOT NULL DEFAULT 0.0,
                last_activity    REAL NOT NULL DEFAULT 0.0,
                timeout_seconds  INTEGER NOT NULL DEFAULT 3600,
                ip_address       TEXT NOT NULL DEFAULT '',
                metadata         TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ms_user ON managed_sessions(user_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ms_token ON managed_sessions(token)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ms_last ON managed_sessions(last_activity)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, session_id: str, user_id: str, token: str,
               timeout: int = 3600, ip_address: str = "",
               metadata: dict | None = None) -> dict:
        """Create a new managed session."""
        if not session_id:
            session_id = uuid.uuid4().hex
        if metadata is None:
            metadata = {}

        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO managed_sessions
                    (session_id, user_id, token, created_at, last_activity,
                     timeout_seconds, ip_address, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, user_id, token, now, now,
                timeout, ip_address, json.dumps(metadata, default=str),
            ))
            self._conn.commit()

        self._emit("security.session.created", {
            "session_id": session_id, "user_id": user_id, "timeout": timeout,
        })
        log.info("created session %s (user=%s, timeout=%ds)",
                 session_id[:12], user_id[:12], timeout)
        return {
            "session_id": session_id, "user_id": user_id,
            "token": token, "created_at": now, "last_activity": now,
            "timeout_seconds": timeout, "ip_address": ip_address,
        }

    def validate(self, session_id: str) -> dict | None:
        """Validate a session. Checks timeout. Returns session or None."""
        row = self._conn.execute(
            "SELECT * FROM managed_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return None

        result = dict(row)
        now = time.time()
        elapsed = now - result["last_activity"]
        if elapsed > result["timeout_seconds"]:
            # Session expired — remove it
            self.destroy(session_id)
            return None

        # Update last_activity (refresh on validate)
        with self._lock:
            self._conn.execute(
                "UPDATE managed_sessions SET last_activity = ? WHERE session_id = ?",
                (now, session_id),
            )
            self._conn.commit()

        result["last_activity"] = now
        return result

    def refresh(self, session_id: str) -> bool:
        """Refresh session activity timestamp."""
        now = time.time()
        with self._lock:
            n = self._conn.execute(
                "UPDATE managed_sessions SET last_activity = ? WHERE session_id = ?",
                (now, session_id),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def destroy(self, session_id: str) -> bool:
        """Destroy a session."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM managed_sessions WHERE session_id = ?",
                (session_id,),
            ).rowcount
            self._conn.commit()
        if n:
            self._emit("security.session.destroyed", {"session_id": session_id})
            log.info("destroyed session %s", session_id[:12])
        return bool(n)

    def list_sessions(self, user_id: str | None = None) -> list[dict]:
        """List sessions, optionally filtered by user_id."""
        if user_id:
            rows = self._conn.execute(
                "SELECT * FROM managed_sessions WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM managed_sessions ORDER BY created_at DESC"
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["metadata"] = json.loads(d.get("metadata", "{}"))
            except (json.JSONDecodeError, TypeError):
                d["metadata"] = {}
            results.append(d)
        return results

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count removed."""
        now = time.time()
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM managed_sessions WHERE (last_activity + timeout_seconds) < ?",
                (now,),
            ).rowcount
            self._conn.commit()
        if n:
            self._emit("security.session.cleanup", {"removed": n})
            log.info("cleaned up %d expired sessions", n)
        return n

    def get_stats(self) -> dict:
        """Get session statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM managed_sessions"
        ).fetchone()["cnt"]

        now = time.time()
        expired = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM managed_sessions WHERE (last_activity + timeout_seconds) < ?",
            (now,),
        ).fetchone()["cnt"]

        active = total - expired

        by_user_rows = self._conn.execute(
            "SELECT user_id, COUNT(*) as cnt FROM managed_sessions GROUP BY user_id"
        ).fetchall()
        by_user = {r["user_id"]: r["cnt"] for r in by_user_rows}

        return {
            "total_sessions": total,
            "active_sessions": active,
            "expired_sessions": expired,
            "by_user": by_user,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.session_broker",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_broker: SessionBroker | None = None


def get_session_broker(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> SessionBroker:
    global _broker
    if _broker is None:
        _broker = SessionBroker(db_path, event_bus)
    return _broker
