"""
SYLION Security -- Bootstrap Initialization

Dev-light bootstrap for security subsystem.
Creates default admin and viewer users if none exist.
Tracks bootstrap state in SQLite for idempotency.
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

log = logging.getLogger("sylion.security.bootstrap_init")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class BootstrapState:
    """Bootstrap state entry."""
    key: str = ""
    value: str = ""
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = time.time()


# ---------------------------------------------------------------------------
# BootstrapInit
# ---------------------------------------------------------------------------

class BootstrapInit:
    """Bootstrap initialization for dev-light security.

    Creates default users and system session on first run.
    Uses bootstrap_state table to track what has been initialized.
    """

    def __init__(self, auth_provider: Any = None,
                 event_bus: EventBus | None = None):
        self._auth_provider = auth_provider
        self._event_bus = event_bus
        self._db_path = ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS bootstrap_state (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL DEFAULT '',
                updated_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def bootstrap(self) -> dict:
        """Run bootstrap: create default users and system session if needed.

        Creates:
        - admin user (role=admin) if no users exist
        - viewer user (role=viewer) if no users exist
        - system session if no sessions exist

        Returns bootstrap status.
        """
        created_users: list[str] = []
        created_session: bool = False

        if self._auth_provider is None:
            log.warning("bootstrap called without auth_provider; skipping")
            return {"status": "skipped", "reason": "no auth_provider"}

        existing_users = self._auth_provider.list_users(active_only=False)

        if not existing_users:
            # Create default admin user
            self._auth_provider.create_user(
                user_id="admin", username="admin",
                password_hash="admin", role="admin",
            )
            created_users.append("admin")

            # Create default viewer user
            self._auth_provider.create_user(
                user_id="viewer", username="viewer",
                password_hash="viewer", role="viewer",
            )
            created_users.append("viewer")

            log.info("bootstrap created default users: %s", created_users)
        else:
            log.info("bootstrap: %d users already exist, skipping user creation",
                     len(existing_users))

        # Create system session if auth_provider supports sessions
        existing_sessions = []
        try:
            # Check if any sessions exist by trying to create one
            rows = self._auth_provider._conn.execute(
                "SELECT COUNT(*) as cnt FROM sessions"
            ).fetchone()
            existing_sessions_count = rows["cnt"] if rows else 0
        except Exception:
            existing_sessions_count = 0

        if existing_sessions_count == 0:
            self._auth_provider.create_session(
                user_id="admin", token="system-bootstrap-token",
                expires_at=time.time() + 86400 * 365,  # 1 year
            )
            created_session = True
            log.info("bootstrap created system session")

        # Record bootstrap state
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO bootstrap_state (key, value, updated_at)
                VALUES (?, ?, ?)
            """, ("bootstrapped", json.dumps({
                "created_users": created_users,
                "created_session": created_session,
                "timestamp": now,
            }), now))
            self._conn.commit()

        self._emit("security.bootstrap.completed", {
            "created_users": created_users,
            "created_session": created_session,
        })

        return {
            "status": "completed",
            "created_users": created_users,
            "created_session": created_session,
        }

    def get_status(self) -> dict:
        """Get current bootstrap state."""
        row = self._conn.execute(
            "SELECT * FROM bootstrap_state WHERE key = 'bootstrapped'"
        ).fetchone()
        if not row:
            return {"status": "not_bootstrapped"}
        result = dict(row)
        try:
            result["value"] = json.loads(result["value"])
        except (json.JSONDecodeError, TypeError):
            pass
        return result

    def reset(self) -> bool:
        """Clear bootstrap state, allowing re-bootstrap."""
        with self._lock:
            self._conn.execute("DELETE FROM bootstrap_state")
            self._conn.commit()
        self._emit("security.bootstrap.reset", {})
        log.info("bootstrap state reset")
        return True

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.bootstrap_init",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_init: BootstrapInit | None = None


def get_bootstrap_init(auth_provider: Any = None,
                       event_bus: EventBus | None = None) -> BootstrapInit:
    global _init
    if _init is None:
        _init = BootstrapInit(auth_provider, event_bus)
    return _init
