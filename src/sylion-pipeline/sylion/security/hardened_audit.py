"""
SYLION Security -- Hardened Audit Log (DEPRECATED)

DEPRECATED 2026-04-24 — use security.audit_trail_aggregator
Tamper-evident audit trail with blockchain-like SHA-256 hash chaining.
Each entry links to the previous via prev_hash for integrity verification.

Tables:
  hardened_audit_log -- append-only entries with hash chain
  audit_chains       -- named chain metadata for grouping entries

Thread-safe via threading.RLock(). Singleton via get_hardened_audit() /
reset_hardened_audit().  Emits events via EventBus.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
import warnings
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

warnings.warn(
    "hardened_audit is deprecated; use audit_trail_aggregator",
    DeprecationWarning,
    stacklevel=2,
)

log = logging.getLogger("sylion.security.hardened_audit")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENESIS_HASH = "0" * 64  # 64 hex zeros

VALID_SEVERITIES: tuple[str, ...] = ("debug", "info", "warning", "error", "critical")


# ---------------------------------------------------------------------------
# HardenedAuditLogger
# ---------------------------------------------------------------------------


class HardenedAuditLogger:
    """Immutable, tamper-evident audit log with hash chain integrity.

    Every entry stores a prev_hash linking it to the previous entry.
    The entry_hash is SHA-256 of (log_id + event_type + actor + action +
    resource + timestamp + prev_hash). Chain integrity can be verified
    at any time with verify_chain() or tamper_check().
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
            CREATE TABLE IF NOT EXISTS hardened_audit_log (
                log_id      TEXT PRIMARY KEY,
                event_type  TEXT NOT NULL DEFAULT '',
                actor       TEXT NOT NULL DEFAULT '',
                action      TEXT NOT NULL DEFAULT '',
                resource    TEXT NOT NULL DEFAULT '',
                details     TEXT NOT NULL DEFAULT '{}',
                severity    TEXT NOT NULL DEFAULT 'info',
                timestamp   REAL NOT NULL DEFAULT 0.0,
                prev_hash   TEXT NOT NULL DEFAULT '',
                entry_hash  TEXT NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_chains (
                chain_id    TEXT PRIMARY KEY,
                name        TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                head_hash   TEXT NOT NULL DEFAULT '',
                entry_count INTEGER NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL DEFAULT 0.0,
                updated_at  REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hal_event_type ON hardened_audit_log(event_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hal_actor ON hardened_audit_log(actor)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hal_severity ON hardened_audit_log(severity)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hal_ts ON hardened_audit_log(timestamp)"
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
                source_module="security.hardened_audit",
            ))

    def _compute_hash(self, log_id: str, event_type: str, actor: str,
                      action: str, resource: str, timestamp: float,
                      prev_hash: str) -> str:
        raw = f"{log_id}|{event_type}|{actor}|{action}|{resource}|{timestamp}|{prev_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _get_last_hash(self) -> str:
        row = self._conn.execute(
            "SELECT entry_hash FROM hardened_audit_log ORDER BY timestamp DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return row["entry_hash"] if row else GENESIS_HASH

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_event(self, event_type: str, actor: str, action: str,
                  resource: str = "", details_json: dict | str | None = None,
                  severity: str = "info") -> dict:
        """Record a tamper-evident audit event. Returns the event dict.

        Raises ValueError if severity is invalid.
        """
        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}'. Must be one of {VALID_SEVERITIES}"
            )

        log_id = uuid.uuid4().hex
        now = time.time()

        if isinstance(details_json, dict):
            details_str = json.dumps(details_json, default=str, sort_keys=True)
        elif isinstance(details_json, str):
            details_str = details_json
        else:
            details_str = "{}"

        with self._lock:
            prev_hash = self._get_last_hash()
            entry_hash = self._compute_hash(
                log_id, event_type, actor, action, resource, now, prev_hash,
            )
            self._conn.execute("""
                INSERT INTO hardened_audit_log
                    (log_id, event_type, actor, action, resource, details,
                     severity, timestamp, prev_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, event_type, actor, action, resource, details_str,
                  severity, now, prev_hash, entry_hash))
            self._conn.commit()

        self._emit("audit_logged", {
            "log_id": log_id,
            "event_type": event_type,
            "actor": actor,
            "entry_hash": entry_hash,
        })
        log.info("hardened audit: %s by %s [%s]", action, actor, event_type)
        return {
            "log_id": log_id,
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "resource": resource,
            "details": details_str,
            "severity": severity,
            "timestamp": now,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
        }

    # ------------------------------------------------------------------
    # Chain operations
    # ------------------------------------------------------------------

    def get_chain(self, chain_id: str) -> dict | None:
        """Get chain metadata by chain_id."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM audit_chains WHERE chain_id = ?",
                (chain_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def verify_chain(self, chain_id: str | None = None) -> dict:
        """Verify entire chain integrity.

        If chain_id is None, verifies the main audit log chain.
        Returns dict with valid (bool), total_entries, broken_at, errors.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hardened_audit_log ORDER BY timestamp ASC, rowid ASC"
            ).fetchall()

        errors: list[str] = []
        broken_at: list[int] = []
        expected_prev = GENESIS_HASH

        for idx, row in enumerate(rows):
            d = self._row_to_dict(row)
            # Check prev_hash linkage
            if d["prev_hash"] != expected_prev:
                errors.append(
                    f"Entry {idx} (log_id={d['log_id']}): prev_hash mismatch"
                )
                broken_at.append(idx)

            # Recompute and verify entry_hash
            recomputed = self._compute_hash(
                d["log_id"], d["event_type"], d["actor"],
                d["action"], d["resource"], d["timestamp"], d["prev_hash"],
            )
            if d["entry_hash"] != recomputed:
                errors.append(
                    f"Entry {idx} (log_id={d['log_id']}): entry_hash tampered"
                )
                broken_at.append(idx)

            expected_prev = d["entry_hash"]

        valid = len(errors) == 0

        if valid:
            self._emit("chain_verified", {
                "chain_id": chain_id,
                "total_entries": len(rows),
            })
        else:
            self._emit("tamper_detected", {
                "chain_id": chain_id,
                "broken_at": broken_at,
                "errors": errors,
            })

        return {
            "valid": valid,
            "total_entries": len(rows),
            "broken_at": broken_at,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_events(self, event_type: str | None = None,
                   actor: str | None = None,
                   limit: int = 100) -> list[dict]:
        """Get events with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if actor is not None:
            conditions.append("actor = ?")
            params.append(actor)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM hardened_audit_log {where} "
                f"ORDER BY timestamp DESC LIMIT ?",
                params + [limit],
            ).fetchall()

        results = []
        for r in rows:
            d = self._row_to_dict(r)
            try:
                d["details"] = json.loads(d.get("details", "{}"))
            except (json.JSONDecodeError, TypeError):
                d["details"] = {}
            results.append(d)
        return results

    def export_events(self, since: float | None = None) -> list[dict]:
        """Export events in chronological order, optionally since timestamp."""
        with self._lock:
            if since is not None:
                rows = self._conn.execute(
                    "SELECT * FROM hardened_audit_log WHERE timestamp >= ? "
                    "ORDER BY timestamp ASC, rowid ASC",
                    (since,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM hardened_audit_log ORDER BY timestamp ASC, rowid ASC",
                ).fetchall()

        results = []
        for r in rows:
            d = self._row_to_dict(r)
            try:
                d["details"] = json.loads(d.get("details", "{}"))
            except (json.JSONDecodeError, TypeError):
                d["details"] = {}
            results.append(d)
        return results

    def tamper_check(self) -> dict:
        """Run a full tamper check on the audit chain. Alias for verify_chain."""
        return self.verify_chain()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_logger: HardenedAuditLogger | None = None


def get_hardened_audit(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> HardenedAuditLogger:
    """Get or create the global HardenedAuditLogger singleton."""
    global _logger
    if _logger is None:
        _logger = HardenedAuditLogger(db_path, event_bus)
    return _logger


def reset_hardened_audit(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> HardenedAuditLogger:
    """Reset the global HardenedAuditLogger singleton (for testing)."""
    global _logger
    _logger = HardenedAuditLogger(db_path, event_bus)
    return _logger
