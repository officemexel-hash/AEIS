"""
SYLION Monitoring -- Circuit Breaker

Protects external service calls from cascading failures.  Each named breaker
tracks a consecutive failure counter and transitions through three states:

  closed   -- healthy, all calls pass through
  open     -- tripped, calls are rejected
  half_open -- probing, limited test calls to check recovery

State transitions:
  closed  -> open      : failure_count >= failure_threshold
  open    -> half_open : recovery_timeout elapsed since last failure
  half_open -> closed  : single successful call
  half_open -> open    : any failure immediately reopens

SQLite-backed with WAL mode.  Thread-safe via threading.RLock().
Singleton via get_circuit_breaker() / reset_circuit_breaker().
Emits events via EventBus.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.monitoring.circuit_breaker")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_CLOSED = "closed"
STATE_OPEN = "open"
STATE_HALF_OPEN = "half_open"

VALID_STATES = {STATE_CLOSED, STATE_OPEN, STATE_HALF_OPEN}


# ---------------------------------------------------------------------------
# CircuitBreakerManager
# ---------------------------------------------------------------------------

class CircuitBreakerManager:
    """Circuit breaker manager backed by SQLite.

    Each breaker tracks failure counts, recovery timeout, and state
    transitions.  Thread-safe via RLock.  Singleton-capable.
    EventBus-integrated.
    """

    def __init__(self, db_path: str = ":memory:",
                 event_bus: EventBus | None = None):
        self._db_path = db_path
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
            CREATE TABLE IF NOT EXISTS circuit_breakers (
                breaker_id        TEXT PRIMARY KEY,
                name              TEXT    NOT NULL,
                failure_threshold INTEGER NOT NULL DEFAULT 5,
                recovery_timeout  REAL    NOT NULL DEFAULT 60.0,
                half_open_max     INTEGER NOT NULL DEFAULT 3,
                state             TEXT    NOT NULL DEFAULT 'closed',
                failure_count     INTEGER NOT NULL DEFAULT 0,
                success_count     INTEGER NOT NULL DEFAULT 0,
                last_failure_at   REAL,
                last_success_at   REAL,
                total_calls       INTEGER NOT NULL DEFAULT 0,
                total_failures    INTEGER NOT NULL DEFAULT 0,
                total_successes   INTEGER NOT NULL DEFAULT 0,
                created_at        REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS breaker_events (
                event_id    TEXT PRIMARY KEY,
                breaker_id  TEXT    NOT NULL,
                event_type  TEXT    NOT NULL,
                old_state   TEXT,
                new_state   TEXT,
                details     TEXT,
                created_at  REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_be_breaker "
            "ON breaker_events(breaker_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_be_type "
            "ON breaker_events(event_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cb_state "
            "ON circuit_breakers(state)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="monitoring.circuit_breaker",
            ))

    def _insert_event(self, breaker_id: str, event_type: str,
                      old_state: str | None = None,
                      new_state: str | None = None,
                      details: str | None = None) -> None:
        """Insert a breaker event. Must be called under lock."""
        event_id = self._uid()
        now = time.time()
        self._conn.execute("""
            INSERT INTO breaker_events
                (event_id, breaker_id, event_type, old_state, new_state,
                 details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (event_id, breaker_id, event_type, old_state, new_state,
              details, now))

    def _resolve_state(self, row: sqlite3.Row) -> str:
        """Resolve the effective state (OPEN may become HALF_OPEN after timeout)."""
        stored = row["state"]
        if stored == STATE_OPEN and row["last_failure_at"] is not None:
            elapsed = time.time() - row["last_failure_at"]
            if elapsed >= row["recovery_timeout"]:
                return STATE_HALF_OPEN
        return stored

    def _row_to_dict(self, row: sqlite3.Row,
                     resolved_state: str | None = None) -> dict:
        state = resolved_state or self._resolve_state(row)
        return {
            "breaker_id": row["breaker_id"],
            "name": row["name"],
            "failure_threshold": row["failure_threshold"],
            "recovery_timeout": row["recovery_timeout"],
            "half_open_max": row["half_open_max"],
            "state": state,
            "failure_count": row["failure_count"],
            "success_count": row["success_count"],
            "last_failure_at": row["last_failure_at"],
            "last_success_at": row["last_success_at"],
            "total_calls": row["total_calls"],
            "total_failures": row["total_failures"],
            "total_successes": row["total_successes"],
            "created_at": row["created_at"],
        }

    # ------------------------------------------------------------------
    # Create / Get / List
    # ------------------------------------------------------------------

    def create_breaker(self, name: str, failure_threshold: int = 5,
                       recovery_timeout: float = 60.0,
                       half_open_max: int = 3) -> dict:
        """Create a new circuit breaker.

        Args:
            name: Human-readable breaker name.
            failure_threshold: Consecutive failures before tripping to OPEN.
            recovery_timeout: Seconds before transitioning OPEN -> HALF_OPEN.
            half_open_max: Consecutive successes in HALF_OPEN before closing.

        Returns:
            Dict with breaker_id and configuration.
        """
        breaker_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO circuit_breakers
                    (breaker_id, name, failure_threshold, recovery_timeout,
                     half_open_max, state, failure_count, success_count,
                     last_failure_at, last_success_at,
                     total_calls, total_failures, total_successes, created_at)
                VALUES (?, ?, ?, ?, ?, 'closed', 0, 0, NULL, NULL, 0, 0, 0, ?)
            """, (breaker_id, name, failure_threshold, recovery_timeout,
                  half_open_max, now))
            self._conn.commit()

        self._emit("breaker_created", {
            "breaker_id": breaker_id,
            "name": name,
            "failure_threshold": failure_threshold,
        })
        log.info("breaker created: %s (%s)", breaker_id[:12], name)
        return {
            "breaker_id": breaker_id,
            "name": name,
            "failure_threshold": failure_threshold,
            "recovery_timeout": recovery_timeout,
            "half_open_max": half_open_max,
            "state": STATE_CLOSED,
        }

    def get_breaker(self, breaker_id: str) -> dict | None:
        """Get a single breaker with full state info, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM circuit_breakers WHERE breaker_id = ?",
                (breaker_id,),
            ).fetchone()
        if row is None:
            return None
        resolved = self._resolve_state(row)
        return self._row_to_dict(row, resolved)

    def list_breakers(self, status: str | None = None) -> list[dict]:
        """List breakers, optionally filtered by status (state)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM circuit_breakers"
            ).fetchall()

        result = []
        for row in rows:
            resolved = self._resolve_state(row)
            if status is not None and resolved != status:
                continue
            result.append(self._row_to_dict(row, resolved))
        return result

    # ------------------------------------------------------------------
    # Record success / failure
    # ------------------------------------------------------------------

    def record_success(self, breaker_id: str) -> dict:
        """Record a successful call.

        CLOSED: resets failure count.
        HALF_OPEN: increments success counter; closes if >= half_open_max.
        OPEN: no state change (should not happen normally).

        Returns updated breaker dict.
        Raises ValueError if breaker not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM circuit_breakers WHERE breaker_id = ?",
                (breaker_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Breaker '{breaker_id}' not found")

            state = self._resolve_state(row)
            now = time.time()
            total_calls = row["total_calls"] + 1
            total_successes = row["total_successes"] + 1

            if state == STATE_CLOSED:
                self._conn.execute("""
                    UPDATE circuit_breakers
                    SET failure_count = 0, success_count = 0,
                        total_calls = ?, total_successes = ?,
                        last_success_at = ?
                    WHERE breaker_id = ?
                """, (total_calls, total_successes, now, breaker_id))

            elif state == STATE_HALF_OPEN:
                new_success = row["success_count"] + 1
                if new_success >= row["half_open_max"]:
                    old_state = state
                    state = STATE_CLOSED
                    self._conn.execute("""
                        UPDATE circuit_breakers
                        SET state = 'closed', failure_count = 0,
                            success_count = 0,
                            total_calls = ?, total_successes = ?,
                            last_success_at = ?
                        WHERE breaker_id = ?
                    """, (total_calls, total_successes, now, breaker_id))
                    self._insert_event(breaker_id, "state_change",
                                       old_state, STATE_CLOSED)
                    self._emit("breaker_closed", {
                        "breaker_id": breaker_id,
                    })
                else:
                    self._conn.execute("""
                        UPDATE circuit_breakers
                        SET success_count = ?,
                            total_calls = ?, total_successes = ?,
                            last_success_at = ?
                        WHERE breaker_id = ?
                    """, (new_success, total_calls, total_successes,
                          now, breaker_id))

            else:  # STATE_OPEN
                self._conn.execute("""
                    UPDATE circuit_breakers
                    SET total_calls = ?, total_successes = ?,
                        last_success_at = ?
                    WHERE breaker_id = ?
                """, (total_calls, total_successes, now, breaker_id))

            self._insert_event(breaker_id, "success",
                               details=f"state={state}")
            self._conn.commit()

        log.debug("success recorded on %s (state=%s)", breaker_id[:12], state)
        return self.get_breaker(breaker_id) or {}

    def record_failure(self, breaker_id: str) -> dict:
        """Record a failed call.

        CLOSED: increments failure count; trips to OPEN if threshold reached.
        HALF_OPEN: immediately reopens.
        OPEN: updates stats only.

        Returns updated breaker dict.
        Raises ValueError if breaker not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM circuit_breakers WHERE breaker_id = ?",
                (breaker_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Breaker '{breaker_id}' not found")

            state = self._resolve_state(row)
            now = time.time()
            total_calls = row["total_calls"] + 1
            total_failures = row["total_failures"] + 1

            if state == STATE_CLOSED:
                new_failures = row["failure_count"] + 1
                if new_failures >= row["failure_threshold"]:
                    old_state = state
                    state = STATE_OPEN
                    self._conn.execute("""
                        UPDATE circuit_breakers
                        SET state = 'open', failure_count = ?,
                            last_failure_at = ?,
                            total_calls = ?, total_failures = ?
                        WHERE breaker_id = ?
                    """, (new_failures, now, total_calls, total_failures,
                          breaker_id))
                    self._insert_event(breaker_id, "state_change",
                                       old_state, STATE_OPEN)
                    self._emit("breaker_opened", {
                        "breaker_id": breaker_id,
                    })
                else:
                    self._conn.execute("""
                        UPDATE circuit_breakers
                        SET failure_count = ?, last_failure_at = ?,
                            total_calls = ?, total_failures = ?
                        WHERE breaker_id = ?
                    """, (new_failures, now, total_calls, total_failures,
                          breaker_id))

            elif state == STATE_HALF_OPEN:
                old_state = state
                state = STATE_OPEN
                self._conn.execute("""
                    UPDATE circuit_breakers
                    SET state = 'open', failure_count = ?,
                        success_count = 0,
                        last_failure_at = ?,
                        total_calls = ?, total_failures = ?
                    WHERE breaker_id = ?
                """, (row["failure_count"] + 1, now,
                      total_calls, total_failures, breaker_id))
                self._insert_event(breaker_id, "state_change",
                                   old_state, STATE_OPEN)
                self._emit("breaker_opened", {
                    "breaker_id": breaker_id,
                })

            else:  # STATE_OPEN
                self._conn.execute("""
                    UPDATE circuit_breakers
                    SET last_failure_at = ?,
                        total_calls = ?, total_failures = ?
                    WHERE breaker_id = ?
                """, (now, total_calls, total_failures, breaker_id))

            self._insert_event(breaker_id, "failure",
                               details=f"state={state}")
            self._conn.commit()

        if state == STATE_OPEN:
            log.warning("breaker %s is OPEN", breaker_id[:12])
        return self.get_breaker(breaker_id) or {}

    # ------------------------------------------------------------------
    # Get state
    # ------------------------------------------------------------------

    def get_state(self, breaker_id: str) -> str | None:
        """Get the effective state of a breaker, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM circuit_breakers WHERE breaker_id = ?",
                (breaker_id,),
            ).fetchone()
        if row is None:
            return None
        return self._resolve_state(row)

    # ------------------------------------------------------------------
    # Force state transitions
    # ------------------------------------------------------------------

    def force_open(self, breaker_id: str) -> bool:
        """Manually force a breaker to OPEN state.

        Returns True if the breaker existed.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT state FROM circuit_breakers WHERE breaker_id = ?",
                (breaker_id,),
            ).fetchone()
            if row is None:
                return False

            now = time.time()
            self._conn.execute("""
                UPDATE circuit_breakers
                SET state = 'open', last_failure_at = ?,
                    success_count = 0
                WHERE breaker_id = ?
            """, (now, breaker_id))
            self._insert_event(breaker_id, "state_change",
                               row["state"], STATE_OPEN,
                               details="force_open")
            self._conn.commit()

        self._emit("breaker_opened", {
            "breaker_id": breaker_id,
            "reason": "force_open",
        })
        log.warning("breaker %s forced OPEN", breaker_id[:12])
        return True

    def force_close(self, breaker_id: str) -> bool:
        """Manually force a breaker to CLOSED state. Clears counters.

        Returns True if the breaker existed.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT state FROM circuit_breakers WHERE breaker_id = ?",
                (breaker_id,),
            ).fetchone()
            if row is None:
                return False

            now = time.time()
            self._conn.execute("""
                UPDATE circuit_breakers
                SET state = 'closed', failure_count = 0,
                    success_count = 0, last_failure_at = NULL,
                    last_success_at = ?
                WHERE breaker_id = ?
            """, (now, breaker_id))
            self._insert_event(breaker_id, "state_change",
                               row["state"], STATE_CLOSED,
                               details="force_close")
            self._conn.commit()

        self._emit("breaker_closed", {
            "breaker_id": breaker_id,
            "reason": "force_close",
        })
        log.info("breaker %s forced CLOSED", breaker_id[:12])
        return True

    # ------------------------------------------------------------------
    # Events / Stats
    # ------------------------------------------------------------------

    def get_events(self, breaker_id: str, limit: int = 100) -> list[dict]:
        """Get event history for a breaker, ordered newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM breaker_events WHERE breaker_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (breaker_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Aggregate statistics across all breakers."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM circuit_breakers"
            ).fetchall()

        by_state: dict[str, int] = {
            STATE_CLOSED: 0, STATE_OPEN: 0, STATE_HALF_OPEN: 0,
        }
        total_calls = 0
        total_failures = 0
        total_successes = 0

        for row in rows:
            resolved = self._resolve_state(row)
            by_state[resolved] = by_state.get(resolved, 0) + 1
            total_calls += row["total_calls"]
            total_failures += row["total_failures"]
            total_successes += row["total_successes"]

        return {
            "total_breakers": len(rows),
            "by_state": by_state,
            "total_calls": total_calls,
            "total_failures": total_failures,
            "total_successes": total_successes,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: CircuitBreakerManager | None = None


def get_circuit_breaker(db_path: str = ":memory:",
                        event_bus: EventBus | None = None) -> CircuitBreakerManager:
    """Get or create the global CircuitBreakerManager singleton."""
    global _instance
    if _instance is None:
        _instance = CircuitBreakerManager(db_path, event_bus)
    return _instance


def reset_circuit_breaker() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
