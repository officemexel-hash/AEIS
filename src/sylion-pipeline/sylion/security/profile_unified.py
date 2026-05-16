"""
SYLION Security -- Profile Unified Manager

Canonical unified module for profile swap requests with approval workflow.
Consolidates profile swap logic into a single source of truth.

Tables:
  profile_swaps -- pending and completed swap requests
  swap_audit    -- audit trail for swap lifecycle events

Thread-safe via threading.RLock(). Singleton via get_profile_unified() /
reset_profile_unified().  Emits events via EventBus.
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

log = logging.getLogger("sylion.security.profile_unified")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES: tuple[str, ...] = (
    "pending", "approved", "executed", "rejected", "cancelled",
)


# ---------------------------------------------------------------------------
# ProfileSwapManager
# ---------------------------------------------------------------------------


class ProfileSwapManager:
    """Profile swap request lifecycle with approval workflow.

    SQLite-backed with RLock for thread safety.  Swaps transition through
    states: pending -> approved -> executed (or rejected/cancelled).
    Every state change is recorded in the swap_audit table.
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
            CREATE TABLE IF NOT EXISTS profile_swaps (
                swap_id       TEXT PRIMARY KEY,
                target_id     TEXT NOT NULL,
                from_profile  TEXT NOT NULL,
                to_profile    TEXT NOT NULL,
                reason        TEXT NOT NULL DEFAULT '',
                status        TEXT NOT NULL DEFAULT 'pending',
                approver      TEXT NOT NULL DEFAULT '',
                reject_reason TEXT NOT NULL DEFAULT '',
                requested_at  REAL NOT NULL DEFAULT 0.0,
                approved_at   REAL NOT NULL DEFAULT 0.0,
                executed_at   REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS swap_audit (
                audit_id  TEXT PRIMARY KEY,
                swap_id   TEXT NOT NULL,
                action    TEXT NOT NULL,
                actor     TEXT NOT NULL DEFAULT '',
                details   TEXT NOT NULL DEFAULT '{}',
                timestamp REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ps_swaps_status ON profile_swaps(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ps_swaps_target ON profile_swaps(target_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ps_audit_swap ON swap_audit(swap_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ps_audit_ts ON swap_audit(timestamp)"
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
                source_module="security.profile_unified",
            ))

    def _add_audit(self, swap_id: str, action: str,
                   actor: str = "", details: dict | None = None):
        """Insert an audit record for a swap event."""
        audit_id = uuid.uuid4().hex
        now = time.time()
        details_str = json.dumps(details or {}, default=str)
        self._conn.execute("""
            INSERT INTO swap_audit (audit_id, swap_id, action, actor, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (audit_id, swap_id, action, actor, details_str, now))
        self._conn.commit()

    # ------------------------------------------------------------------
    # Swap lifecycle
    # ------------------------------------------------------------------

    def request_swap(self, target_id: str, from_profile: str,
                     to_profile: str, reason: str = "") -> dict:
        """Request a profile swap. Returns swap dict.

        Raises ValueError if from_profile equals to_profile.
        """
        if from_profile == to_profile:
            raise ValueError(
                "from_profile and to_profile must be different"
            )

        swap_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO profile_swaps
                    (swap_id, target_id, from_profile, to_profile, reason,
                     status, requested_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """, (swap_id, target_id, from_profile, to_profile, reason, now))
            self._add_audit(swap_id, "requested", details={"reason": reason})
            self._conn.commit()

        self._emit("swap_requested", {
            "swap_id": swap_id,
            "target_id": target_id,
            "from_profile": from_profile,
            "to_profile": to_profile,
        })
        log.info("swap requested %s: %s -> %s for %s",
                 swap_id[:12], from_profile, to_profile, target_id[:12])
        return {
            "swap_id": swap_id,
            "target_id": target_id,
            "from_profile": from_profile,
            "to_profile": to_profile,
            "reason": reason,
            "status": "pending",
            "approver": "",
            "reject_reason": "",
            "requested_at": now,
            "approved_at": 0.0,
            "executed_at": 0.0,
        }

    def approve_swap(self, swap_id: str, approver: str) -> dict | None:
        """Approve a pending swap. Returns updated swap dict or None.

        Raises ValueError if swap is not in pending status.
        """
        swap = self.get_swap(swap_id)
        if swap is None:
            return None
        if swap["status"] != "pending":
            raise ValueError(
                f"Swap '{swap_id}' is not pending (status={swap['status']})"
            )

        now = time.time()
        with self._lock:
            n = self._conn.execute("""
                UPDATE profile_swaps
                SET status = 'approved', approver = ?, approved_at = ?
                WHERE swap_id = ? AND status = 'pending'
            """, (approver, now, swap_id)).rowcount
            self._add_audit(swap_id, "approved", actor=approver)
            self._conn.commit()

        if not n:
            return None

        self._emit("swap_approved", {
            "swap_id": swap_id,
            "approver": approver,
        })
        log.info("swap %s approved by %s", swap_id[:12], approver)
        return self.get_swap(swap_id)

    def reject_swap(self, swap_id: str, approver: str,
                    reason: str = "") -> dict | None:
        """Reject a pending swap. Returns updated swap dict or None.

        Raises ValueError if swap is not in pending status.
        """
        swap = self.get_swap(swap_id)
        if swap is None:
            return None
        if swap["status"] != "pending":
            raise ValueError(
                f"Swap '{swap_id}' is not pending (status={swap['status']})"
            )

        now = time.time()
        with self._lock:
            n = self._conn.execute("""
                UPDATE profile_swaps
                SET status = 'rejected', approver = ?, reject_reason = ?
                WHERE swap_id = ? AND status = 'pending'
            """, (approver, reason, swap_id)).rowcount
            self._add_audit(swap_id, "rejected", actor=approver,
                            details={"reason": reason})
            self._conn.commit()

        if not n:
            return None

        self._emit("swap_rejected", {
            "swap_id": swap_id,
            "approver": approver,
            "reason": reason,
        })
        log.info("swap %s rejected by %s", swap_id[:12], approver)
        return self.get_swap(swap_id)

    def execute_swap(self, swap_id: str) -> dict | None:
        """Execute an approved swap. Returns updated swap dict or None.

        Raises ValueError if swap is not in approved status.
        """
        swap = self.get_swap(swap_id)
        if swap is None:
            return None
        if swap["status"] != "approved":
            raise ValueError(
                f"Swap '{swap_id}' is not approved (status={swap['status']})"
            )

        now = time.time()
        with self._lock:
            n = self._conn.execute("""
                UPDATE profile_swaps
                SET status = 'executed', executed_at = ?
                WHERE swap_id = ? AND status = 'approved'
            """, (now, swap_id)).rowcount
            self._add_audit(swap_id, "executed")
            self._conn.commit()

        if not n:
            return None

        self._emit("swap_executed", {
            "swap_id": swap_id,
            "target_id": swap["target_id"],
            "from_profile": swap["from_profile"],
            "to_profile": swap["to_profile"],
        })
        log.info("swap %s executed", swap_id[:12])
        return self.get_swap(swap_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_swap(self, swap_id: str) -> dict | None:
        """Retrieve a swap by swap_id. Returns dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM profile_swaps WHERE swap_id = ?",
                (swap_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_swaps(self, status: str | None = None) -> list[dict]:
        """List swaps, optionally filtered by status."""
        conditions: list[str] = []
        params: list[Any] = []

        if status is not None:
            if status not in VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Must be one of {VALID_STATUSES}"
                )
            conditions.append("status = ?")
            params.append(status)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM profile_swaps {where} ORDER BY requested_at DESC",
                params,
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_swap_audit(self, swap_id: str) -> list[dict]:
        """Get audit trail for a swap."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM swap_audit WHERE swap_id = ? ORDER BY timestamp",
                (swap_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_swap_stats(self) -> dict:
        """Return aggregate statistics about swaps."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM profile_swaps"
            ).fetchone()[0]

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM profile_swaps GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

        return {
            "total_swaps": total,
            "by_status": by_status,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: ProfileSwapManager | None = None


def get_profile_unified(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> ProfileSwapManager:
    """Get or create the global ProfileSwapManager singleton."""
    global _manager
    if _manager is None:
        _manager = ProfileSwapManager(db_path, event_bus)
    return _manager


def reset_profile_unified(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> ProfileSwapManager:
    """Reset the global ProfileSwapManager singleton (for testing)."""
    global _manager
    _manager = ProfileSwapManager(db_path, event_bus)
    return _manager


# Backward-compatible aliases
get_profile_swap = get_profile_unified
reset_profile_swap = reset_profile_unified
