"""
SYLION Execution -- Retry Orchestrator

Manages retry policies for failed operations with exponential backoff,
jitter, and dead letter queues. When an operation exhausts its retry
budget it is moved to the dead letter queue for manual review.

Thread-safe. SQLite-backed. Emits events to EventBus.
"""

from __future__ import annotations

import json
import logging
import random
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.execution.retry_orchestrator")

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RetryPolicy:
    """Retry policy configuration."""
    policy_id: str = ""
    name: str = ""
    description: str = ""
    max_retries: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 60000
    backoff_factor: float = 2.0
    jitter: float = 0.1
    retryable_errors: list[str] = field(default_factory=list)
    enabled: int = 1
    created_at: float = 0.0


@dataclass
class RetryAttempt:
    """A single retry attempt record."""
    attempt_id: str = ""
    policy_id: str = ""
    operation_type: str = ""
    operation_id: str = ""
    attempt_number: int = 0
    max_attempts: int = 0
    error_type: str = ""
    error_message: str = ""
    scheduled_at: float = 0.0
    executed_at: float = 0.0
    result: str = ""
    delay_ms: int = 0
    created_at: float = 0.0


@dataclass
class DeadLetterEntry:
    """An entry in the dead letter queue."""
    dlq_id: str = ""
    policy_id: str = ""
    operation_type: str = ""
    operation_id: str = ""
    original_error: str = ""
    last_error: str = ""
    total_attempts: int = 0
    payload: str = ""
    requires_manual_review: int = 0
    reviewed_by: str = ""
    reviewed_at: float = 0.0
    created_at: float = 0.0


# ---------------------------------------------------------------------------
# Retry Orchestrator
# ---------------------------------------------------------------------------

class RetryOrchestrator:
    """Retry policy manager with exponential backoff, jitter, and DLQ.

    Thread-safe. SQLite-backed. Emits events to EventBus.
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

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS retry_policies (
                policy_id        TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                description      TEXT,

                max_retries      INTEGER DEFAULT 3,
                base_delay_ms    INTEGER DEFAULT 1000,
                max_delay_ms     INTEGER DEFAULT 60000,
                backoff_factor   REAL DEFAULT 2.0,
                jitter           REAL DEFAULT 0.1,

                retryable_errors TEXT,

                enabled          INTEGER DEFAULT 1,
                created_at       REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS retry_attempts (
                attempt_id      TEXT PRIMARY KEY,
                policy_id       TEXT NOT NULL,

                operation_type  TEXT NOT NULL,
                operation_id    TEXT NOT NULL,

                attempt_number  INTEGER NOT NULL,
                max_attempts    INTEGER NOT NULL,

                error_type      TEXT,
                error_message   TEXT,

                scheduled_at    REAL NOT NULL,
                executed_at     REAL,
                result          TEXT,

                delay_ms        INTEGER,
                created_at      REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                dlq_id          TEXT PRIMARY KEY,
                policy_id       TEXT NOT NULL,

                operation_type  TEXT NOT NULL,
                operation_id    TEXT NOT NULL,

                original_error  TEXT,
                last_error      TEXT,
                total_attempts  INTEGER NOT NULL,

                payload         TEXT,
                requires_manual_review INTEGER DEFAULT 0,
                reviewed_by     TEXT,
                reviewed_at     REAL,

                created_at      REAL NOT NULL
            );
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ra_op ON retry_attempts(operation_type, operation_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ra_policy ON retry_attempts(policy_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ra_result ON retry_attempts(result)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dlq_op ON dead_letter_queue(operation_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dlq_reviewed ON dead_letter_queue(requires_manual_review)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def create_policy(self, name: str, max_retries: int = 3,
                      base_delay_ms: int = 1000, max_delay_ms: int = 60000,
                      backoff_factor: float = 2.0, jitter: float = 0.1,
                      retryable_errors: list[str] | None = None,
                      description: str = "") -> dict:
        """Create a new retry policy. Returns the policy dict."""
        policy_id = uuid.uuid4().hex
        created_at = time.time()
        errors_json = json.dumps(retryable_errors or [], default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO retry_policies
                    (policy_id, name, description, max_retries,
                     base_delay_ms, max_delay_ms, backoff_factor, jitter,
                     retryable_errors, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (policy_id, name, description, max_retries,
                  base_delay_ms, max_delay_ms, backoff_factor, jitter,
                  errors_json, created_at))
            self._conn.commit()

        result = {
            "policy_id": policy_id, "name": name, "description": description,
            "max_retries": max_retries, "base_delay_ms": base_delay_ms,
            "max_delay_ms": max_delay_ms, "backoff_factor": backoff_factor,
            "jitter": jitter, "retryable_errors": retryable_errors or [],
            "enabled": 1, "created_at": created_at,
        }

        self._emit("execution.retry.policy_created", {
            "policy_id": policy_id, "name": name,
        })
        log.info("created retry policy %s (%s)", policy_id[:12], name)
        return result

    def update_policy(self, policy_id: str, **kwargs: Any) -> dict | None:
        """Update one or more fields on an existing policy."""
        allowed = {
            "name", "description", "max_retries", "base_delay_ms",
            "max_delay_ms", "backoff_factor", "jitter", "retryable_errors",
            "enabled",
        }
        updates: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k not in allowed:
                raise ValueError(f"unknown field: {k}")
            if k == "retryable_errors":
                updates[k] = json.dumps(v, default=str)
            else:
                updates[k] = v

        if not updates:
            return self.get_policy(policy_id)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [policy_id]

        with self._lock:
            n = self._conn.execute(
                f"UPDATE retry_policies SET {set_clause} WHERE policy_id = ?",
                values,
            ).rowcount
            self._conn.commit()

        if not n:
            return None

        self._emit("execution.retry.policy_updated", {
            "policy_id": policy_id, "fields": list(updates.keys()),
        })
        log.info("updated retry policy %s", policy_id[:12])
        return self.get_policy(policy_id)

    def list_policies(self, enabled_only: bool = True) -> list[dict]:
        """List all policies, optionally filtering to enabled only."""
        with self._lock:
            if enabled_only:
                rows = self._conn.execute(
                    "SELECT * FROM retry_policies WHERE enabled = 1 ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM retry_policies ORDER BY created_at DESC"
                ).fetchall()
        return [self._policy_row(r) for r in rows]

    def get_policy(self, policy_id: str) -> dict | None:
        """Get a single policy by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM retry_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
        if not row:
            return None
        return self._policy_row(row)

    # ------------------------------------------------------------------
    # Attempt registration
    # ------------------------------------------------------------------

    def register_attempt(self, operation_type: str, operation_id: str,
                         policy_id: str | None = None,
                         error_type: str | None = None,
                         error_message: str | None = None,
                         payload: dict | None = None) -> dict:
        """Record a failed attempt and compute the next step.

        Returns dict with:
            attempt_id, attempt_number, next_delay_ms,
            should_retry, moved_to_dlq
        """
        # Resolve policy
        if policy_id is None:
            policy_id = self._find_default_policy()

        if policy_id:
            policy = self.get_policy(policy_id)
        else:
            policy = None

        max_retries = policy["max_retries"] if policy else 3
        base_delay_ms = policy["base_delay_ms"] if policy else 1000
        max_delay_ms = policy["max_delay_ms"] if policy else 60000
        backoff_factor = policy["backoff_factor"] if policy else 2.0
        jitter_frac = policy["jitter"] if policy else 0.1

        # Check retryable_errors filter
        if policy and policy.get("retryable_errors"):
            if error_type and error_type not in policy["retryable_errors"]:
                # Not a retryable error -- skip directly
                should_retry = False
                moved_to_dlq = True
                attempt_number = 1
                delay_ms = 0
                attempt_id = uuid.uuid4().hex
                now = time.time()

                with self._lock:
                    self._conn.execute("""
                        INSERT INTO retry_attempts
                            (attempt_id, policy_id, operation_type, operation_id,
                             attempt_number, max_attempts, error_type, error_message,
                             scheduled_at, executed_at, result, delay_ms, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'skipped', 0, ?)
                    """, (attempt_id, policy_id or "", operation_type, operation_id,
                          attempt_number, max_retries, error_type, error_message,
                          now, now, now))
                    self._conn.commit()

                self._move_to_dlq(
                    policy_id or "", operation_type, operation_id,
                    error_message or error_type or "", attempt_number,
                    payload,
                )
                return {
                    "attempt_id": attempt_id,
                    "attempt_number": attempt_number,
                    "next_delay_ms": 0,
                    "should_retry": False,
                    "moved_to_dlq": True,
                }

        # Count previous attempts for this operation
        with self._lock:
            count_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM retry_attempts "
                "WHERE operation_type = ? AND operation_id = ?",
                (operation_type, operation_id),
            ).fetchone()
            attempt_number = count_row["cnt"] + 1

        # Calculate delay
        delay_ms = self._calc_delay(
            base_delay_ms, backoff_factor, jitter_frac,
            max_delay_ms, attempt_number,
        )
        now = time.time()
        scheduled_at = now + delay_ms / 1000.0
        attempt_id = uuid.uuid4().hex

        should_retry = attempt_number < max_retries
        moved_to_dlq = False

        if should_retry:
            result_status = "failed"
        else:
            result_status = "failed"
            moved_to_dlq = True

        with self._lock:
            self._conn.execute("""
                INSERT INTO retry_attempts
                    (attempt_id, policy_id, operation_type, operation_id,
                     attempt_number, max_attempts, error_type, error_message,
                     scheduled_at, executed_at, result, delay_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (attempt_id, policy_id or "", operation_type, operation_id,
                  attempt_number, max_retries, error_type, error_message,
                  scheduled_at, now, result_status, delay_ms, now))
            self._conn.commit()

        if moved_to_dlq:
            self._move_to_dlq(
                policy_id or "", operation_type, operation_id,
                error_message or error_type or "", attempt_number,
                payload,
            )

        self._emit("execution.retry.attempt_registered", {
            "attempt_id": attempt_id,
            "operation_type": operation_type,
            "operation_id": operation_id,
            "attempt_number": attempt_number,
            "should_retry": should_retry,
            "moved_to_dlq": moved_to_dlq,
        })

        log.info("registered attempt %d for %s:%s (retry=%s, dlq=%s)",
                 attempt_number, operation_type, operation_id[:12],
                 should_retry, moved_to_dlq)

        return {
            "attempt_id": attempt_id,
            "attempt_number": attempt_number,
            "next_delay_ms": delay_ms,
            "should_retry": should_retry,
            "moved_to_dlq": moved_to_dlq,
        }

    def get_next_delay(self, policy_id: str, attempt_number: int) -> int:
        """Calculate the delay in ms for a given attempt without registering."""
        policy = self.get_policy(policy_id)
        if not policy:
            return 0
        return self._calc_delay(
            policy["base_delay_ms"],
            policy["backoff_factor"],
            policy["jitter"],
            policy["max_delay_ms"],
            attempt_number,
        )

    def record_success(self, operation_type: str, operation_id: str) -> bool:
        """Mark an operation as succeeded. Clears pending retry expectations."""
        now = time.time()
        attempt_id = uuid.uuid4().hex

        with self._lock:
            # Find the policy used by previous attempts for this operation
            prev = self._conn.execute(
                "SELECT policy_id, attempt_number FROM retry_attempts "
                "WHERE operation_type = ? AND operation_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (operation_type, operation_id),
            ).fetchone()

            policy_id = prev["policy_id"] if prev else ""
            next_attempt = (prev["attempt_number"] + 1) if prev else 1

            self._conn.execute("""
                INSERT INTO retry_attempts
                    (attempt_id, policy_id, operation_type, operation_id,
                     attempt_number, max_attempts, error_type, error_message,
                     scheduled_at, executed_at, result, delay_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, '', '', ?, ?, 'success', 0, ?)
            """, (attempt_id, policy_id, operation_type, operation_id,
                  next_attempt, 0, now, now, now))
            self._conn.commit()

        self._emit("execution.retry.success_recorded", {
            "operation_type": operation_type,
            "operation_id": operation_id,
        })
        return True

    def get_attempts(self, operation_type: str | None = None,
                     operation_id: str | None = None,
                     policy_id: str | None = None,
                     result: str | None = None,
                     limit: int = 100) -> list[dict]:
        """Query retry attempts with optional filters."""
        conds: list[str] = []
        params: list[Any] = []

        if operation_type is not None:
            conds.append("operation_type = ?")
            params.append(operation_type)
        if operation_id is not None:
            conds.append("operation_id = ?")
            params.append(operation_id)
        if policy_id is not None:
            conds.append("policy_id = ?")
            params.append(policy_id)
        if result is not None:
            conds.append("result = ?")
            params.append(result)

        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM retry_attempts{where} "
                f"ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Dead Letter Queue
    # ------------------------------------------------------------------

    def get_dlq_entries(self, reviewed: bool | None = None,
                        operation_type: str | None = None,
                        limit: int = 100) -> list[dict]:
        """Query dead letter queue entries."""
        conds: list[str] = []
        params: list[Any] = []

        if reviewed is not None:
            if reviewed:
                conds.append("reviewed_by IS NOT NULL AND reviewed_by != ''")
            else:
                conds.append("(reviewed_by IS NULL OR reviewed_by = '')")
        if operation_type is not None:
            conds.append("operation_type = ?")
            params.append(operation_type)

        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM dead_letter_queue{where} "
                f"ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._dlq_row(r) for r in rows]

    def review_dlq_entry(self, dlq_id: str, reviewed_by: str,
                         action: str = "discard") -> dict | None:
        """Mark a DLQ entry as reviewed. Action is informational ('discard' or 'retry')."""
        now = time.time()
        with self._lock:
            n = self._conn.execute("""
                UPDATE dead_letter_queue
                SET reviewed_by = ?, reviewed_at = ?
                WHERE dlq_id = ?
            """, (reviewed_by, now, dlq_id)).rowcount
            self._conn.commit()

        if not n:
            return None

        self._emit("execution.retry.dlq_reviewed", {
            "dlq_id": dlq_id, "reviewed_by": reviewed_by, "action": action,
        })
        log.info("DLQ entry %s reviewed by %s (action=%s)",
                 dlq_id[:12], reviewed_by, action)
        return {"dlq_id": dlq_id, "reviewed_by": reviewed_by, "action": action}

    def retry_dlq_entry(self, dlq_id: str) -> dict | None:
        """Move a DLQ entry back to the retry queue.

        Removes the DLQ entry and returns the original operation info
        so the caller can re-execute it.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM dead_letter_queue WHERE dlq_id = ?",
                (dlq_id,),
            ).fetchone()
            if not row:
                return None

            entry = self._dlq_row(row)

            # Delete previous attempts for this operation so it starts fresh
            self._conn.execute(
                "DELETE FROM retry_attempts "
                "WHERE operation_type = ? AND operation_id = ?",
                (entry["operation_type"], entry["operation_id"]),
            )

            # Remove from DLQ
            self._conn.execute(
                "DELETE FROM dead_letter_queue WHERE dlq_id = ?",
                (dlq_id,),
            )
            self._conn.commit()

        self._emit("execution.retry.dlq_retried", {
            "dlq_id": dlq_id,
            "operation_type": entry["operation_type"],
            "operation_id": entry["operation_id"],
        })
        log.info("DLQ entry %s moved back to retry queue", dlq_id[:12])
        return entry

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return aggregate statistics."""
        with self._lock:
            total_policies = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM retry_policies"
            ).fetchone()["cnt"]

            total_attempts = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM retry_attempts"
            ).fetchone()["cnt"]

            success_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM retry_attempts WHERE result = 'success'"
            ).fetchone()["cnt"]

            dlq_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM dead_letter_queue"
            ).fetchone()["cnt"]

            # By operation type
            op_rows = self._conn.execute(
                "SELECT operation_type, COUNT(*) as cnt FROM retry_attempts "
                "GROUP BY operation_type"
            ).fetchall()
            by_operation_type = {r["operation_type"]: r["cnt"] for r in op_rows}

            success_rate = (success_count / total_attempts * 100) if total_attempts else 0.0

        return {
            "total_policies": total_policies,
            "total_attempts": total_attempts,
            "success_rate": round(success_rate, 2),
            "dlq_count": dlq_count,
            "by_operation_type": by_operation_type,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calc_delay(self, base_delay_ms: int, backoff_factor: float,
                    jitter_frac: float, max_delay_ms: int,
                    attempt_number: int) -> int:
        """Compute exponential backoff delay with jitter.

        delay = min(base * factor^(attempt-1) * (1 + jitter * random()), max)
        """
        exponential = base_delay_ms * (backoff_factor ** (attempt_number - 1))
        jitter_mult = 1.0 + jitter_frac * random.random()
        raw_delay = exponential * jitter_mult
        return int(min(raw_delay, max_delay_ms))

    def _move_to_dlq(self, policy_id: str, operation_type: str,
                     operation_id: str, error: str, total_attempts: int,
                     payload: dict | None = None):
        """Move an operation to the dead letter queue."""
        dlq_id = uuid.uuid4().hex
        now = time.time()
        payload_json = json.dumps(payload or {}, default=str)

        with self._lock:
            # Check if already in DLQ
            existing = self._conn.execute(
                "SELECT dlq_id, original_error, total_attempts FROM dead_letter_queue "
                "WHERE operation_type = ? AND operation_id = ?",
                (operation_type, operation_id),
            ).fetchone()

            if existing:
                self._conn.execute("""
                    UPDATE dead_letter_queue
                    SET last_error = ?, total_attempts = ?,
                        payload = ?, requires_manual_review = 1,
                        reviewed_by = '', reviewed_at = NULL
                    WHERE dlq_id = ?
                """, (error, total_attempts, payload_json, existing["dlq_id"]))
                self._conn.commit()
                self._emit("execution.retry.dlq_updated", {
                    "dlq_id": existing["dlq_id"],
                })
            else:
                self._conn.execute("""
                    INSERT INTO dead_letter_queue
                        (dlq_id, policy_id, operation_type, operation_id,
                         original_error, last_error, total_attempts,
                         payload, requires_manual_review, reviewed_by,
                         reviewed_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, '', NULL, ?)
                """, (dlq_id, policy_id, operation_type, operation_id,
                      error, error, total_attempts, payload_json, now))
                self._conn.commit()
                self._emit("execution.retry.moved_to_dlq", {
                    "dlq_id": dlq_id,
                    "operation_type": operation_type,
                    "operation_id": operation_id,
                })

        log.warning("moved %s:%s to DLQ after %d attempts",
                    operation_type, operation_id[:12], total_attempts)

    def _find_default_policy(self) -> str | None:
        """Find the first enabled policy to use as default."""
        with self._lock:
            row = self._conn.execute(
                "SELECT policy_id FROM retry_policies WHERE enabled = 1 "
                "ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
        return row["policy_id"] if row else None

    @staticmethod
    def _policy_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["retryable_errors"] = json.loads(d.get("retryable_errors", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["retryable_errors"] = []
        return d

    @staticmethod
    def _dlq_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["payload"] = json.loads(d.get("payload", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["payload"] = {}
        return d

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="execution.retry_orchestrator",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_orchestrator: RetryOrchestrator | None = None


def get_retry_orchestrator(db_path: str | Path | None = None,
                           event_bus: EventBus | None = None) -> RetryOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = RetryOrchestrator(db_path, event_bus)
    return _orchestrator


def reset_retry_orchestrator() -> None:
    global _orchestrator
    _orchestrator = None
