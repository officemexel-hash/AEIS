"""
SYLION Security -- Phantom Wrapper

Ephemeral scoped session management with operation restrictions.
Provides time-limited sessions with scope-based access control.

Tables:
  phantom_sessions   -- ephemeral sessions with TTL and scope
  phantom_operations -- operation records within sessions

Thread-safe via threading.RLock(). Singleton via get_phantom_wrapper() /
reset_phantom_wrapper().  Emits events via EventBus.
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

log = logging.getLogger("sylion.security.phantom_wrapper")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TTL_SECONDS: int = 3600  # 1 hour


# ---------------------------------------------------------------------------
# PhantomWrapper
# ---------------------------------------------------------------------------


class PhantomWrapper:
    """Ephemeral scoped session manager with operation restrictions.

    Creates time-limited sessions tied to a user and scope.
    Each operation within a session is validated against the session's
    TTL and scope before being recorded.
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
            CREATE TABLE IF NOT EXISTS phantom_sessions (
                session_id  TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL DEFAULT '',
                scope       TEXT NOT NULL DEFAULT '',
                ttl_seconds INTEGER NOT NULL DEFAULT 3600,
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL DEFAULT 0.0,
                expires_at  REAL NOT NULL DEFAULT 0.0,
                revoked_at  REAL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS phantom_operations (
                op_id       TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL DEFAULT '',
                operation   TEXT NOT NULL DEFAULT '',
                resource    TEXT NOT NULL DEFAULT '',
                result      TEXT NOT NULL DEFAULT '',
                timestamp   REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pw_sessions_user ON phantom_sessions(user_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pw_sessions_active ON phantom_sessions(is_active)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pw_sessions_expires ON phantom_sessions(expires_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pw_ops_session ON phantom_operations(session_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pw_ops_ts ON phantom_operations(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.phantom_wrapper",
            ))

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def check(self, input_text: str, output_text: str,
              policies: list[str] | None = None) -> dict:
        """Run a lightweight phantom safety check on an input/output pair.

        Detects a small set of red-flags in the output that should not appear
        regardless of the input -- secrets-like patterns and obvious PII.
        Returns ``{passed, issues, input, output}``.

        Note: this is a deterministic check used as a safety smoke test in
        higher-level pipelines; it does not replace a full DLP layer.
        """
        import re

        issues: list[dict] = []
        out = output_text or ""

        patterns = [
            ("secret_pattern_sk",
             re.compile(r"sk-[A-Za-z0-9]{16,}"),
             "looks like an API token (sk-...)"),
            ("aws_access_key",
             re.compile(r"AKIA[0-9A-Z]{16}"),
             "looks like an AWS access key id"),
            ("private_key_block",
             re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
             "embeds a PEM private key block"),
            ("email_pii",
             re.compile(r"[\w\.-]+@[\w\.-]+\.[A-Za-z]{2,}"),
             "contains an email address"),
            ("ssn_us",
             re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
             "contains a US SSN-like pattern"),
        ]
        for code, rx, descr in patterns:
            if rx.search(out):
                issues.append({"code": code, "description": descr})

        # If the input explicitly forbids leaking, count any verbatim secret
        # leak from input -> output.
        if input_text and "DO NOT REVEAL" in input_text.upper():
            for token in input_text.split():
                if len(token) > 8 and token in out:
                    issues.append({
                        "code": "verbatim_leak",
                        "description": f"output verbatim contains input token '{token[:12]}...'",
                    })

        passed = not issues
        result = {
            "passed": passed,
            "issues": issues,
            "input": input_text,
            "output": output_text,
            "policies": policies or [],
        }
        self._emit("phantom.check", {
            "passed": passed, "issue_count": len(issues),
        })
        return result

    def create_session(self, user_id: str, scope: str = "",
                       ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict:
        """Create an ephemeral scoped session. Returns session dict."""
        session_id = uuid.uuid4().hex
        now = time.time()
        expires_at = now + ttl_seconds

        with self._lock:
            self._conn.execute("""
                INSERT INTO phantom_sessions
                    (session_id, user_id, scope, ttl_seconds, is_active, created_at, expires_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (session_id, user_id, scope, ttl_seconds, now, expires_at))
            self._conn.commit()

        self._emit("session_created", {
            "session_id": session_id,
            "user_id": user_id,
            "scope": scope,
            "expires_at": expires_at,
        })
        log.info("created phantom session %s for user %s (scope=%s, ttl=%ds)",
                 session_id[:12], user_id[:12], scope, ttl_seconds)
        return {
            "session_id": session_id,
            "user_id": user_id,
            "scope": scope,
            "ttl_seconds": ttl_seconds,
            "is_active": 1,
            "created_at": now,
            "expires_at": expires_at,
        }

    def validate_session(self, session_id: str,
                         operation: str = "") -> dict:
        """Validate a session for an operation.

        Checks: session exists, is active, has not expired (TTL),
        and operation is within scope.

        Returns dict with allowed (bool), reason, session data.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM phantom_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()

            if not row:
                return {"allowed": False, "reason": "session not found", "session": None}

            session = self._row_to_dict(row)

            if not session["is_active"]:
                return {"allowed": False, "reason": "session revoked", "session": session}

            now = time.time()
            if session["expires_at"] > 0 and session["expires_at"] < now:
                self._conn.execute(
                    "UPDATE phantom_sessions SET is_active = 0 WHERE session_id = ?",
                    (session_id,),
                )
                self._conn.commit()
                self._emit("session_expired", {"session_id": session_id})
                return {"allowed": False, "reason": "session expired", "session": session}

            # Scope check: if scope is defined, operation must match
            scope = session["scope"]
            if scope and operation:
                allowed_ops = [s.strip() for s in scope.split(",")]
                if operation not in allowed_ops:
                    return {
                        "allowed": False,
                        "reason": f"operation '{operation}' not in scope",
                        "session": session,
                    }

        return {"allowed": True, "reason": "valid", "session": session}

    def record_operation(self, session_id: str, operation: str,
                         resource: str = "", result: str = "") -> dict:
        """Record an operation within a session. Returns operation dict.

        Raises ValueError if session is not valid.
        """
        validation = self.validate_session(session_id, operation)
        if not validation["allowed"]:
            raise ValueError(f"Cannot record operation: {validation['reason']}")

        op_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO phantom_operations
                    (op_id, session_id, operation, resource, result, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (op_id, session_id, operation, resource, result, now))
            self._conn.commit()

        self._emit("operation_recorded", {
            "op_id": op_id,
            "session_id": session_id,
            "operation": operation,
        })
        log.info("recorded operation %s in session %s", operation, session_id[:12])
        return {
            "op_id": op_id,
            "session_id": session_id,
            "operation": operation,
            "resource": resource,
            "result": result,
            "timestamp": now,
        }

    def revoke_session(self, session_id: str) -> bool:
        """Revoke an active session. Returns True if revoked."""
        now = time.time()
        with self._lock:
            n = self._conn.execute(
                "UPDATE phantom_sessions SET is_active = 0, revoked_at = ? "
                "WHERE session_id = ? AND is_active = 1",
                (now, session_id),
            ).rowcount
            self._conn.commit()

        if n:
            self._emit("session_revoked", {"session_id": session_id})
            log.info("revoked phantom session %s", session_id[:12])
        return bool(n)

    def get_session(self, session_id: str) -> dict | None:
        """Get a session by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM phantom_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

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
                f"SELECT * FROM phantom_sessions {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_session_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM phantom_sessions"
            ).fetchone()["cnt"]
            active = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM phantom_sessions WHERE is_active = 1"
            ).fetchone()["cnt"]
            total_ops = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM phantom_operations"
            ).fetchone()["cnt"]

        return {
            "total_sessions": total,
            "active_sessions": active,
            "revoked_sessions": total - active,
            "total_operations": total_ops,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_wrapper: PhantomWrapper | None = None


def get_phantom_wrapper(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> PhantomWrapper:
    """Get or create the global PhantomWrapper singleton."""
    global _wrapper
    if _wrapper is None:
        _wrapper = PhantomWrapper(db_path, event_bus)
    return _wrapper


def reset_phantom_wrapper(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> PhantomWrapper:
    """Reset the global PhantomWrapper singleton (for testing)."""
    global _wrapper
    _wrapper = PhantomWrapper(db_path, event_bus)
    return _wrapper
