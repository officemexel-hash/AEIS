"""
SYLION Efficiency -- Circuit Breaker

Circuit breaker pattern for resilient external calls.
Tracks failure rates per circuit, transitions through
CLOSED -> OPEN -> HALF_OPEN states, and supports
configurable recovery probing.

States:
  CLOSED    -- healthy, calls pass through
  OPEN      -- tripped, calls rejected
  HALF_OPEN -- probing, limited calls allowed to test recovery

SQLite-backed with WAL mode. Thread-safe via threading.Lock.
Singleton via get_circuit_breaker(). Emits events via EventBus.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.efficiency.circuit_breaker")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_CLOSED = "closed"
STATE_OPEN = "open"
STATE_HALF_OPEN = "half_open"

VALID_STATES = {STATE_CLOSED, STATE_OPEN, STATE_HALF_OPEN}


class CircuitBreakerOpenError(Exception):
    """Raised when a call is attempted on an OPEN circuit."""
    pass


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Circuit breaker manager backed by SQLite.

    Each named circuit tracks its own failure count, state, and recovery
    parameters.  Thread-safe, singleton-capable, EventBus-integrated.

    Table ``sylion_circuits``:
        circuit_id       TEXT PRIMARY KEY
        state            TEXT NOT NULL DEFAULT 'closed'
        failure_count    INTEGER NOT NULL DEFAULT 0
        success_count    INTEGER NOT NULL DEFAULT 0  (half-open probe tracker)
        last_failure     REAL NOT NULL DEFAULT 0.0
        failure_threshold INTEGER NOT NULL DEFAULT 5
        recovery_timeout  REAL NOT NULL DEFAULT 60.0
        half_open_max     INTEGER NOT NULL DEFAULT 3
        total_calls       INTEGER NOT NULL DEFAULT 0
        total_failures    INTEGER NOT NULL DEFAULT 0
        total_successes   INTEGER NOT NULL DEFAULT 0
        created_at        REAL NOT NULL
        updated_at        REAL NOT NULL
    """

    def __init__(self, db_path: str = ":memory:",
                 event_bus: EventBus | None = None):
        self._db_path = db_path
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_table()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_circuits (
                circuit_id        TEXT PRIMARY KEY,
                state             TEXT    NOT NULL DEFAULT 'closed',
                failure_count     INTEGER NOT NULL DEFAULT 0,
                success_count     INTEGER NOT NULL DEFAULT 0,
                last_failure      REAL    NOT NULL DEFAULT 0.0,
                failure_threshold INTEGER NOT NULL DEFAULT 5,
                recovery_timeout  REAL    NOT NULL DEFAULT 60.0,
                half_open_max     INTEGER NOT NULL DEFAULT 3,
                total_calls       INTEGER NOT NULL DEFAULT 0,
                total_failures    INTEGER NOT NULL DEFAULT 0,
                total_successes   INTEGER NOT NULL DEFAULT 0,
                created_at        REAL    NOT NULL,
                updated_at        REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sc_state ON sylion_circuits(state)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    def register_circuit(self, circuit_id: str,
                         failure_threshold: int = 5,
                         recovery_timeout: float = 60.0,
                         half_open_max: int = 3) -> dict:
        """Register a new circuit or update an existing one.

        Returns dict with circuit_id and configuration.
        """
        now = time.time()
        with self._lock:
            existing = self._conn.execute(
                "SELECT circuit_id FROM sylion_circuits WHERE circuit_id = ?",
                (circuit_id,),
            ).fetchone()

            if existing:
                self._conn.execute("""
                    UPDATE sylion_circuits
                    SET failure_threshold = ?,
                        recovery_timeout  = ?,
                        half_open_max     = ?,
                        updated_at        = ?
                    WHERE circuit_id = ?
                """, (failure_threshold, recovery_timeout,
                      half_open_max, now, circuit_id))
            else:
                self._conn.execute("""
                    INSERT INTO sylion_circuits
                        (circuit_id, state, failure_count, success_count,
                         last_failure, failure_threshold, recovery_timeout,
                         half_open_max, total_calls, total_failures,
                         total_successes, created_at, updated_at)
                    VALUES (?, 'closed', 0, 0, 0, ?, ?, ?, 0, 0, 0, ?, ?)
                """, (circuit_id, failure_threshold, recovery_timeout,
                      half_open_max, now, now))
            self._conn.commit()

        self._emit("efficiency.circuit_breaker.registered", {
            "circuit_id": circuit_id,
            "failure_threshold": failure_threshold,
            "recovery_timeout": recovery_timeout,
            "half_open_max": half_open_max,
        })

        log.info("circuit registered: %s (threshold=%d, timeout=%.1fs, half_open_max=%d)",
                 circuit_id, failure_threshold, recovery_timeout, half_open_max)
        return {
            "circuit_id": circuit_id,
            "failure_threshold": failure_threshold,
            "recovery_timeout": recovery_timeout,
            "half_open_max": half_open_max,
        }

    # ------------------------------------------------------------------
    # Record success / failure
    # ------------------------------------------------------------------

    def record_success(self, circuit_id: str) -> dict:
        """Record a successful call on the circuit.

        In CLOSED state: resets consecutive failure count.
        In HALF_OPEN state: increments success probe count; if it reaches
        half_open_max, transitions to CLOSED.
        In OPEN state: no-op (should not happen, but safe).

        Returns the updated check_circuit dict.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_circuits WHERE circuit_id = ?",
                (circuit_id,),
            ).fetchone()

            if row is None:
                raise ValueError(f"Circuit '{circuit_id}' not registered")

            state = self._resolve_state(row)
            now = time.time()

            total_successes = row["total_successes"] + 1
            total_calls = row["total_calls"] + 1

            if state == STATE_CLOSED:
                self._conn.execute("""
                    UPDATE sylion_circuits
                    SET failure_count = 0,
                        success_count = 0,
                        total_calls = ?,
                        total_successes = ?,
                        updated_at = ?
                    WHERE circuit_id = ?
                """, (total_calls, total_successes, now, circuit_id))

            elif state == STATE_HALF_OPEN:
                new_success = row["success_count"] + 1
                if new_success >= row["half_open_max"]:
                    # Recovery successful -> CLOSED
                    self._conn.execute("""
                        UPDATE sylion_circuits
                        SET state = 'closed',
                            failure_count = 0,
                            success_count = 0,
                            total_calls = ?,
                            total_successes = ?,
                            updated_at = ?
                        WHERE circuit_id = ?
                    """, (total_calls, total_successes, now, circuit_id))
                    state = STATE_CLOSED
                else:
                    self._conn.execute("""
                        UPDATE sylion_circuits
                        SET success_count = ?,
                            total_calls = ?,
                            total_successes = ?,
                            updated_at = ?
                        WHERE circuit_id = ?
                    """, (new_success, total_calls, total_successes, now, circuit_id))

            elif state == STATE_OPEN:
                # Shouldn't normally happen, but record the stats anyway
                self._conn.execute("""
                    UPDATE sylion_circuits
                    SET total_calls = ?,
                        total_successes = ?,
                        updated_at = ?
                    WHERE circuit_id = ?
                """, (total_calls, total_successes, now, circuit_id))

            self._conn.commit()

        self._emit("efficiency.circuit_breaker.success", {
            "circuit_id": circuit_id,
            "state": state,
        })

        log.debug("success recorded on circuit %s (state=%s)", circuit_id, state)
        return self._read_circuit(circuit_id)

    def record_failure(self, circuit_id: str) -> dict:
        """Record a failed call on the circuit.

        In CLOSED state: increments failure count; if it reaches
        failure_threshold, trips to OPEN.
        In HALF_OPEN state: immediately reopens the circuit.
        In OPEN state: updates stats only.

        Returns the updated check_circuit dict.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_circuits WHERE circuit_id = ?",
                (circuit_id,),
            ).fetchone()

            if row is None:
                raise ValueError(f"Circuit '{circuit_id}' not registered")

            state = self._resolve_state(row)
            now = time.time()

            total_failures = row["total_failures"] + 1
            total_calls = row["total_calls"] + 1

            if state == STATE_CLOSED:
                new_failures = row["failure_count"] + 1
                if new_failures >= row["failure_threshold"]:
                    # Trip the circuit to OPEN
                    self._conn.execute("""
                        UPDATE sylion_circuits
                        SET state = 'open',
                            failure_count = ?,
                            last_failure = ?,
                            total_calls = ?,
                            total_failures = ?,
                            updated_at = ?
                        WHERE circuit_id = ?
                    """, (new_failures, now, total_calls, total_failures,
                          now, circuit_id))
                    state = STATE_OPEN
                else:
                    self._conn.execute("""
                        UPDATE sylion_circuits
                        SET failure_count = ?,
                            last_failure = ?,
                            total_calls = ?,
                            total_failures = ?,
                            updated_at = ?
                        WHERE circuit_id = ?
                    """, (new_failures, now, total_calls, total_failures,
                          now, circuit_id))

            elif state == STATE_HALF_OPEN:
                # Failed probe -> back to OPEN
                self._conn.execute("""
                    UPDATE sylion_circuits
                    SET state = 'open',
                        failure_count = ?,
                        last_failure = ?,
                        success_count = 0,
                        total_calls = ?,
                        total_failures = ?,
                        updated_at = ?
                    WHERE circuit_id = ?
                """, (row["failure_count"] + 1, now,
                      total_calls, total_failures, now, circuit_id))
                state = STATE_OPEN

            elif state == STATE_OPEN:
                self._conn.execute("""
                    UPDATE sylion_circuits
                    SET last_failure = ?,
                        total_calls = ?,
                        total_failures = ?,
                        updated_at = ?
                    WHERE circuit_id = ?
                """, (now, total_calls, total_failures, now, circuit_id))

            self._conn.commit()

        self._emit("efficiency.circuit_breaker.failure", {
            "circuit_id": circuit_id,
            "state": state,
        })

        if state == STATE_OPEN:
            log.warning("circuit %s is now OPEN (failure threshold reached)", circuit_id)
        else:
            log.debug("failure recorded on circuit %s (state=%s)", circuit_id, state)

        return self._read_circuit(circuit_id)

    # ------------------------------------------------------------------
    # Check circuit
    # ------------------------------------------------------------------

    def check_circuit(self, circuit_id: str) -> dict:
        """Check the current state of a circuit.

        Returns dict with keys:
            circuit_id, state, failures, last_failure,
            failure_threshold, recovery_timeout, half_open_max,
            total_calls, total_failures, total_successes.
        """
        row = self._conn.execute(
            "SELECT * FROM sylion_circuits WHERE circuit_id = ?",
            (circuit_id,),
        ).fetchone()

        if row is None:
            return {
                "circuit_id": circuit_id,
                "state": None,
                "failures": 0,
                "last_failure": 0.0,
            }

        state = self._resolve_state(row)

        return {
            "circuit_id": circuit_id,
            "state": state,
            "failures": row["failure_count"],
            "last_failure": row["last_failure"],
            "failure_threshold": row["failure_threshold"],
            "recovery_timeout": row["recovery_timeout"],
            "half_open_max": row["half_open_max"],
            "total_calls": row["total_calls"],
            "total_failures": row["total_failures"],
            "total_successes": row["total_successes"],
        }

    # ------------------------------------------------------------------
    # Half-open probe
    # ------------------------------------------------------------------

    def try_half_open(self, circuit_id: str) -> dict:
        """Attempt to transition an OPEN circuit to HALF_OPEN.

        Only succeeds if recovery_timeout has elapsed since last_failure.
        Resets the success probe counter.

        Returns the updated check_circuit dict.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_circuits WHERE circuit_id = ?",
                (circuit_id,),
            ).fetchone()

            if row is None:
                raise ValueError(f"Circuit '{circuit_id}' not registered")

            stored_state = row["state"]

            if stored_state != STATE_OPEN:
                # Not open (or already half_open in DB), nothing to do
                self._conn.commit()
                return self.check_circuit(circuit_id)

            # Check if recovery_timeout has elapsed
            now = time.time()
            if now - row["last_failure"] < row["recovery_timeout"]:
                # Too early
                self._conn.commit()
                return self.check_circuit(circuit_id)

            # Transition to HALF_OPEN
            self._conn.execute("""
                UPDATE sylion_circuits
                SET state = 'half_open',
                    success_count = 0,
                    updated_at = ?
                WHERE circuit_id = ?
            """, (now, circuit_id))
            self._conn.commit()

        self._emit("efficiency.circuit_breaker.half_open", {
            "circuit_id": circuit_id,
        })

        log.info("circuit %s transitioned to HALF_OPEN", circuit_id)
        return self.check_circuit(circuit_id)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset_circuit(self, circuit_id: str) -> bool:
        """Force reset a circuit to CLOSED state.

        Returns True if the circuit existed and was reset, False otherwise.
        """
        with self._lock:
            n = self._conn.execute("""
                UPDATE sylion_circuits
                SET state = 'closed',
                    failure_count = 0,
                    success_count = 0,
                    last_failure = 0.0,
                    updated_at = ?
                WHERE circuit_id = ?
            """, (time.time(), circuit_id)).rowcount
            self._conn.commit()

        if n:
            self._emit("efficiency.circuit_breaker.reset", {
                "circuit_id": circuit_id,
            })
            log.info("circuit %s force-reset to CLOSED", circuit_id)

        return bool(n)

    # ------------------------------------------------------------------
    # List circuits
    # ------------------------------------------------------------------

    def list_circuits(self) -> list[dict]:
        """List all registered circuits with their current state."""
        rows = self._conn.execute(
            "SELECT * FROM sylion_circuits ORDER BY circuit_id"
        ).fetchall()

        result = []
        for row in rows:
            state = self._resolve_state(row)
            result.append({
                "circuit_id": row["circuit_id"],
                "state": state,
                "failures": row["failure_count"],
                "last_failure": row["last_failure"],
                "failure_threshold": row["failure_threshold"],
                "recovery_timeout": row["recovery_timeout"],
                "half_open_max": row["half_open_max"],
                "total_calls": row["total_calls"],
                "total_failures": row["total_failures"],
                "total_successes": row["total_successes"],
            })
        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate statistics across all circuits.

        Returns dict with:
            total_circuits, closed_count, open_count, half_open_count,
            total_calls, total_failures, total_successes,
            overall_failure_rate.
        """
        rows = self._conn.execute(
            "SELECT * FROM sylion_circuits"
        ).fetchall()

        total = len(rows)
        closed_count = 0
        open_count = 0
        half_open_count = 0
        total_calls = 0
        total_failures = 0
        total_successes = 0

        for row in rows:
            state = self._resolve_state(row)
            if state == STATE_CLOSED:
                closed_count += 1
            elif state == STATE_OPEN:
                open_count += 1
            elif state == STATE_HALF_OPEN:
                half_open_count += 1
            total_calls += row["total_calls"]
            total_failures += row["total_failures"]
            total_successes += row["total_successes"]

        failure_rate = (total_failures / total_calls) if total_calls > 0 else 0.0

        return {
            "total_circuits": total,
            "closed_count": closed_count,
            "open_count": open_count,
            "half_open_count": half_open_count,
            "total_calls": total_calls,
            "total_failures": total_failures,
            "total_successes": total_successes,
            "overall_failure_rate": failure_rate,
        }

    # ------------------------------------------------------------------
    # Internal: read circuit under lock
    # ------------------------------------------------------------------

    def _read_circuit(self, circuit_id: str) -> dict:
        """Read circuit info under lock for thread-safety."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_circuits WHERE circuit_id = ?",
                (circuit_id,),
            ).fetchone()

        if row is None:
            return {
                "circuit_id": circuit_id,
                "state": None,
                "failures": 0,
                "last_failure": 0.0,
            }

        state = self._resolve_state(row)
        return {
            "circuit_id": circuit_id,
            "state": state,
            "failures": row["failure_count"],
            "last_failure": row["last_failure"],
            "failure_threshold": row["failure_threshold"],
            "recovery_timeout": row["recovery_timeout"],
            "half_open_max": row["half_open_max"],
            "total_calls": row["total_calls"],
            "total_failures": row["total_failures"],
            "total_successes": row["total_successes"],
        }

    # ------------------------------------------------------------------
    # Internal: resolve state (time-aware)
    # ------------------------------------------------------------------

    def _resolve_state(self, row: sqlite3.Row) -> str:
        """Resolve the effective state of a circuit.

        If the stored state is OPEN but recovery_timeout has elapsed,
        the effective state is HALF_OPEN (but we don't auto-transition
        here -- that is done by try_half_open). We only report it for
        check_circuit queries.
        """
        stored_state = row["state"]
        if stored_state == STATE_OPEN:
            elapsed = time.time() - row["last_failure"]
            if elapsed >= row["recovery_timeout"]:
                return STATE_HALF_OPEN
        return stored_state

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="efficiency.circuit_breaker",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: CircuitBreaker | None = None


def get_circuit_breaker(db_path: str = ":memory:",
                        event_bus: EventBus | None = None) -> CircuitBreaker:
    """Get or create the global CircuitBreaker singleton."""
    global _instance
    if _instance is None:
        _instance = CircuitBreaker(db_path, event_bus)
    return _instance
