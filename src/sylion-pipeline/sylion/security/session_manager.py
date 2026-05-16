"""
SYLION Security -- Session Manager

User accounts, role-based sessions, and audit trail with SQLite-backed storage.
24-hour session expiry, token-based validation, and comprehensive audit logging.

Tables:
  user_accounts -- user identities with roles and credentials
  sessions      -- authenticated sessions with tokens and expiry
  audit_events  -- action audit trail for compliance

Thread-safe via threading.RLock(). Singleton via get_session_manager() /
reset_session_manager().  Emits events via EventBus.
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

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.security.session_manager")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ROLES: tuple[str, ...] = ("admin", "operator", "viewer", "service")

VALID_ACTIONS: tuple[str, ...] = (
    "login",
    "logout",
    "api_call",
    "config_change",
    "key_access",
    "data_export",
)

SESSION_TTL_SECONDS: int = 86400  # 24 hours


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------


class SessionManager:
    """User accounts, session lifecycle, and audit trail.

    SQLite-backed with RLock for thread safety.  Each session gets a unique
    token and expires after 24 hours by default.  Every significant action is
    recorded in the audit_events table.  Events are emitted on the EventBus
    for session lifecycle changes.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
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
            CREATE TABLE IF NOT EXISTS user_accounts (
                user_id       TEXT PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                email         TEXT NOT NULL DEFAULT '',
                role          TEXT NOT NULL DEFAULT 'viewer',
                password_hash TEXT NOT NULL DEFAULT '',
                created_at    REAL NOT NULL DEFAULT 0.0,
                last_login    REAL NOT NULL DEFAULT 0.0,
                is_active     INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id  TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL DEFAULT '',
                token       TEXT NOT NULL DEFAULT '',
                ip_address  TEXT NOT NULL DEFAULT '',
                user_agent  TEXT NOT NULL DEFAULT '',
                created_at  REAL NOT NULL DEFAULT 0.0,
                expires_at  REAL NOT NULL DEFAULT 0.0,
                is_active   INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id   TEXT PRIMARY KEY,
                session_id TEXT NOT NULL DEFAULT '',
                user_id    TEXT NOT NULL DEFAULT '',
                action     TEXT NOT NULL DEFAULT '',
                resource   TEXT NOT NULL DEFAULT '',
                ip_address TEXT NOT NULL DEFAULT '',
                timestamp  REAL NOT NULL DEFAULT 0.0,
                metadata   TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sm_users_username ON user_accounts(username)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sm_users_role ON user_accounts(role)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sm_sessions_user ON sessions(user_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sm_sessions_token ON sessions(token)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sm_sessions_active ON sessions(is_active)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sm_sessions_expires ON sessions(expires_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sm_audit_user ON audit_events(user_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sm_audit_action ON audit_events(action)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sm_audit_ts ON audit_events(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a plain dict."""
        return dict(row)

    def _parse_metadata(self, raw: str) -> dict:
        """Parse JSON metadata string, returning empty dict on failure."""
        try:
            return json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _emit(self, topic: str, payload: dict):
        """Publish an event if an EventBus is configured."""
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.session_manager",
            ))

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def create_user(self, username: str, email: str,
                    role: str = "viewer", password_hash: str = "") -> dict:
        """Create a new user account. Returns user dict.

        Raises ValueError if role is invalid.
        Raises sqlite3.IntegrityError (propagated) on duplicate username.
        """
        if role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of {VALID_ROLES}"
            )

        user_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO user_accounts
                    (user_id, username, email, role, password_hash,
                     created_at, last_login, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 0.0, 1)
            """, (user_id, username, email, role, password_hash, now))
            self._conn.commit()

        log.info("created user %s (role=%s)", username, role)
        return {
            "user_id": user_id,
            "username": username,
            "email": email,
            "role": role,
            "created_at": now,
            "last_login": 0.0,
            "is_active": 1,
        }

    def get_user(self, user_id: str) -> dict | None:
        """Retrieve a user by user_id. Returns dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM user_accounts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_users(self, role: str | None = None,
                   is_active: int | None = None) -> list[dict]:
        """List users, optionally filtered by role and/or active status."""
        conditions: list[str] = []
        params: list[Any] = []

        if role is not None:
            conditions.append("role = ?")
            params.append(role)
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM user_accounts {where} ORDER BY created_at",
                params,
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_user(self, user_id: str, email: str | None = None,
                    role: str | None = None,
                    is_active: int | None = None) -> dict | None:
        """Update user fields. Returns updated user dict or None if not found.

        Raises ValueError if role is invalid.
        """
        if role is not None and role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of {VALID_ROLES}"
            )

        sets: list[str] = []
        params: list[Any] = []

        if email is not None:
            sets.append("email = ?")
            params.append(email)
        if role is not None:
            sets.append("role = ?")
            params.append(role)
        if is_active is not None:
            sets.append("is_active = ?")
            params.append(is_active)

        if not sets:
            return self.get_user(user_id)

        params.append(user_id)

        with self._lock:
            n = self._conn.execute(
                f"UPDATE user_accounts SET {', '.join(sets)} WHERE user_id = ?",
                params,
            ).rowcount
            self._conn.commit()

        if not n:
            return None

        log.info("updated user %s", user_id[:12])
        return self.get_user(user_id)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, user_id: str, ip_address: str = "",
                       user_agent: str = "") -> dict:
        """Create a new session for a user with a random token and 24h expiry.

        Returns session dict.  Raises ValueError if user does not exist or
        is inactive.
        """
        user = self.get_user(user_id)
        if user is None:
            raise ValueError(f"User '{user_id}' does not exist")
        if not user["is_active"]:
            raise ValueError(f"User '{user_id}' is inactive")

        session_id = uuid.uuid4().hex
        token = uuid.uuid4().hex
        now = time.time()
        expires_at = now + SESSION_TTL_SECONDS

        with self._lock:
            self._conn.execute("""
                INSERT INTO sessions
                    (session_id, user_id, token, ip_address, user_agent,
                     created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (session_id, user_id, token, ip_address, user_agent,
                  now, expires_at))
            # Update last_login
            self._conn.execute(
                "UPDATE user_accounts SET last_login = ? WHERE user_id = ?",
                (now, user_id),
            )
            self._conn.commit()

        self._emit("session.created", {
            "session_id": session_id,
            "user_id": user_id,
        })
        log.info("created session %s for user %s", session_id[:12], user_id[:12])
        return {
            "session_id": session_id,
            "user_id": user_id,
            "token": token,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": now,
            "expires_at": expires_at,
            "is_active": 1,
        }

    def validate_session(self, token: str) -> dict | None:
        """Validate a token. Returns dict with session + user data or None.

        Checks that the session exists, is active, and has not expired.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE token = ?",
                (token,),
            ).fetchone()
            if not row:
                return None

            session = self._row_to_dict(row)

            # Check active flag
            if not session["is_active"]:
                return None

            # Check expiry
            now = time.time()
            if session["expires_at"] > 0 and session["expires_at"] < now:
                # Session expired -- deactivate and emit event
                self._conn.execute(
                    "UPDATE sessions SET is_active = 0 WHERE session_id = ?",
                    (session["session_id"],),
                )
                self._conn.commit()
                self._emit("session.expired", {
                    "session_id": session["session_id"],
                    "user_id": session["user_id"],
                })
                return None

        # Fetch user info
        user = self.get_user(session["user_id"])
        if user is None or not user["is_active"]:
            return None

        return {
            "session": session,
            "user": user,
        }

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session (soft delete). Returns True if revoked."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE sessions SET is_active = 0 WHERE session_id = ? AND is_active = 1",
                (session_id,),
            ).rowcount
            self._conn.commit()

        if n:
            self._emit("session.revoked", {"session_id": session_id})
            log.info("revoked session %s", session_id[:12])
        return bool(n)

    def list_sessions(self, user_id: str | None = None,
                      is_active: int | None = None) -> list[dict]:
        """List sessions, optionally filtered by user_id and/or active status."""
        conditions: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM sessions {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Audit events
    # ------------------------------------------------------------------

    def audit_event(self, session_id: str, action: str,
                    resource: str = "", ip_address: str = "",
                    metadata: dict | None = None) -> dict:
        """Record an audit event. Returns the event dict.

        Raises ValueError if action is not in VALID_ACTIONS.
        """
        if action not in VALID_ACTIONS:
            raise ValueError(
                f"Invalid action '{action}'. Must be one of {VALID_ACTIONS}"
            )

        event_id = uuid.uuid4().hex
        now = time.time()

        # Resolve user_id from session
        user_id = ""
        with self._lock:
            session_row = self._conn.execute(
                "SELECT user_id FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session_row:
                user_id = session_row["user_id"]

        meta_json = json.dumps(metadata, default=str) if metadata else "{}"

        with self._lock:
            self._conn.execute("""
                INSERT INTO audit_events
                    (event_id, session_id, user_id, action, resource,
                     ip_address, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_id, session_id, user_id, action, resource,
                  ip_address, now, meta_json))
            self._conn.commit()

        log.info("audit event %s: %s on %s", event_id[:12], action, resource)
        return {
            "event_id": event_id,
            "session_id": session_id,
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "ip_address": ip_address,
            "timestamp": now,
            "metadata": metadata or {},
        }

    def list_audit_events(self, user_id: str | None = None,
                          action: str | None = None,
                          limit: int = 100) -> list[dict]:
        """List audit events, optionally filtered by user_id and/or action."""
        conditions: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if action is not None:
            conditions.append("action = ?")
            params.append(action)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM audit_events {where} ORDER BY timestamp DESC LIMIT ?",
                params + [limit],
            ).fetchall()

        results = []
        for r in rows:
            d = self._row_to_dict(r)
            d["metadata"] = self._parse_metadata(d.get("metadata", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_expired(self) -> int:
        """Deactivate expired sessions. Returns count of sessions cleaned up."""
        now = time.time()
        expired_ids: list[str] = []

        with self._lock:
            rows = self._conn.execute(
                "SELECT session_id FROM sessions WHERE expires_at > 0 AND expires_at < ? AND is_active = 1",
                (now,),
            ).fetchall()
            expired_ids = [r["session_id"] for r in rows]

            if expired_ids:
                self._conn.execute(
                    "UPDATE sessions SET is_active = 0 WHERE expires_at > 0 AND expires_at < ? AND is_active = 1",
                    (now,),
                )
                self._conn.commit()

        for sid in expired_ids:
            self._emit("session.expired", {"session_id": sid})

        if expired_ids:
            log.info("cleaned up %d expired sessions", len(expired_ids))
        return len(expired_ids)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: SessionManager | None = None


def get_session_manager(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> SessionManager:
    """Get or create the global SessionManager singleton."""
    global _manager
    if _manager is None:
        _manager = SessionManager(db_path, event_bus)
    return _manager


def reset_session_manager(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> SessionManager:
    """Reset the global SessionManager singleton (for testing)."""
    global _manager
    _manager = SessionManager(db_path, event_bus)
    return _manager
