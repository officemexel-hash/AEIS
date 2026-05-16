"""
SYLION Security -- Audit Sink (DEPRECATED)

DEPRECATED 2026-04-24 — use security.audit_trail_aggregator
Routes audit events to external systems via subscriptions.
Each subscription defines a topic pattern, delivery type (webhook, file,
database), and configuration.  Events are delivered and tracked with
success/failure status and retry support.

SQLite-backed with WAL mode.  Thread-safe via threading.RLock().
Singleton via get_audit_sink() / reset_audit_sink().
Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
import warnings
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

warnings.warn(
    "audit_sink is deprecated; use audit_trail_aggregator",
    DeprecationWarning,
    stacklevel=2,
)

log = logging.getLogger("sylion.security.audit_sink")

# ---------------------------------------------------------------------------
# Valid delivery types
# ---------------------------------------------------------------------------

VALID_DELIVERY_TYPES = {"webhook", "file", "database"}


# ---------------------------------------------------------------------------
# AuditSink
# ---------------------------------------------------------------------------

class AuditSink:
    """Audit event routing engine backed by SQLite.

    Manages subscriptions that route audit events to external systems.
    Each delivery is tracked with status and retry count.
    Thread-safe via RLock.  Singleton-capable.
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
            CREATE TABLE IF NOT EXISTS sink_audit_log (
                entry_id      TEXT PRIMARY KEY,
                event_topic   TEXT NOT NULL,
                actor         TEXT NOT NULL DEFAULT '',
                action        TEXT NOT NULL DEFAULT '',
                resource      TEXT NOT NULL DEFAULT '',
                result        TEXT NOT NULL DEFAULT '',
                details_json  TEXT NOT NULL DEFAULT '{}',
                logged_at     REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sal_topic ON sink_audit_log(event_topic)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sal_actor ON sink_audit_log(actor)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sal_logged ON sink_audit_log(logged_at)"
        )
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sink_subscriptions (
                sub_id          TEXT PRIMARY KEY,
                name            TEXT    NOT NULL,
                topic_pattern   TEXT    NOT NULL,
                delivery_type   TEXT    NOT NULL,
                config_json     TEXT    NOT NULL DEFAULT '{}',
                enabled         INTEGER NOT NULL DEFAULT 1,
                created_at      REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sink_deliveries (
                delivery_id     TEXT PRIMARY KEY,
                sub_id          TEXT    NOT NULL,
                event_json      TEXT    NOT NULL,
                status          TEXT    NOT NULL DEFAULT 'pending',
                attempts        INTEGER NOT NULL DEFAULT 0,
                last_attempt_at REAL,
                error_message   TEXT,
                created_at      REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sd_sub "
            "ON sink_deliveries(sub_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sd_status "
            "ON sink_deliveries(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ss_topic "
            "ON sink_subscriptions(topic_pattern)"
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
                source_module="security.audit_sink",
            ))

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        return dict(row)

    # ------------------------------------------------------------------
    # Audit log -- direct append-only logging
    # ------------------------------------------------------------------

    def log(self, event_topic: str, *, actor: str = "", action: str = "",
            resource: str = "", result: str = "",
            details: dict | None = None) -> dict:
        """Append an audit entry to the sink log.

        Use this for direct security audit recording -- separate from the
        subscription/delivery plane. Returns the entry dict.
        """
        entry_id = self._uid()
        now = time.time()
        details_str = json.dumps(details or {}, default=str)
        with self._lock:
            self._conn.execute("""
                INSERT INTO sink_audit_log
                    (entry_id, event_topic, actor, action, resource,
                     result, details_json, logged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (entry_id, event_topic, actor, action, resource,
                  result, details_str, now))
            self._conn.commit()
        entry = {
            "entry_id": entry_id,
            "event_topic": event_topic,
            "actor": actor,
            "action": action,
            "resource": resource,
            "result": result,
            "details": details or {},
            "logged_at": now,
        }
        self._emit("audit.log_entry", {
            "entry_id": entry_id, "event_topic": event_topic,
            "actor": actor, "action": action, "result": result,
        })
        return entry

    def list_log_entries(self, event_topic: str | None = None,
                         actor: str | None = None,
                         limit: int = 100) -> list[dict]:
        """List audit log entries newest-first."""
        sql = "SELECT * FROM sink_audit_log WHERE 1=1"
        args: list[Any] = []
        if event_topic:
            sql += " AND event_topic = ?"
            args.append(event_topic)
        if actor:
            sql += " AND actor = ?"
            args.append(actor)
        sql += " ORDER BY logged_at DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, tuple(args)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["details"] = json.loads(d.pop("details_json", "{}") or "{}")
            except (json.JSONDecodeError, TypeError):
                d["details"] = {}
                d.pop("details_json", None)
            results.append(d)
        return results

    def query(self, event_type: str | None = None,
              actor: str | None = None,
              since: float | None = None,
              limit: int = 100) -> list[dict]:
        """Query audit entries with optional filters (route alias)."""
        sql = "SELECT * FROM sink_audit_log WHERE 1=1"
        args: list[Any] = []
        if event_type:
            sql += " AND event_topic = ?"
            args.append(event_type)
        if actor:
            sql += " AND actor = ?"
            args.append(actor)
        if since is not None:
            sql += " AND logged_at >= ?"
            args.append(float(since))
        sql += " ORDER BY logged_at DESC LIMIT ?"
        args.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, tuple(args)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["details"] = json.loads(d.pop("details_json", "{}") or "{}")
            except (json.JSONDecodeError, TypeError):
                d["details"] = {}
                d.pop("details_json", None)
            results.append(d)
        return results

    def export(self, since: float | None = None,
               limit: int = 10000) -> list[dict]:
        """Export audit entries (route alias for bulk read)."""
        return self.query(since=since, limit=limit)

    # ------------------------------------------------------------------
    # Subscription CRUD
    # ------------------------------------------------------------------

    def create_subscription(self, name: str, topic_pattern: str,
                            delivery_type: str,
                            config_json: dict | None = None) -> dict:
        """Create a new audit event subscription.

        Args:
            name: Human-readable subscription name.
            topic_pattern: Event topic pattern to match (e.g. 'security.*').
            delivery_type: One of 'webhook', 'file', 'database'.
            config_json: Delivery-specific configuration.

        Returns:
            Dict with sub_id and subscription details.

        Raises:
            ValueError: If delivery_type is invalid.
        """
        if delivery_type not in VALID_DELIVERY_TYPES:
            raise ValueError(
                f"Invalid delivery_type '{delivery_type}'. "
                f"Must be one of {VALID_DELIVERY_TYPES}"
            )

        sub_id = self._uid()
        now = time.time()
        cfg = json.dumps(config_json or {})

        with self._lock:
            self._conn.execute("""
                INSERT INTO sink_subscriptions
                    (sub_id, name, topic_pattern, delivery_type,
                     config_json, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (sub_id, name, topic_pattern, delivery_type, cfg, now))
            self._conn.commit()

        result = {
            "sub_id": sub_id,
            "name": name,
            "topic_pattern": topic_pattern,
            "delivery_type": delivery_type,
            "config_json": config_json or {},
            "enabled": True,
            "created_at": now,
        }

        self._emit("subscription_created", {
            "sub_id": sub_id, "name": name,
            "topic_pattern": topic_pattern,
            "delivery_type": delivery_type,
        })
        log.info("subscription created: %s (%s) -> %s",
                 name, sub_id[:12], delivery_type)
        return result

    def update_subscription(self, sub_id: str, *,
                            name: str | None = None,
                            topic_pattern: str | None = None,
                            delivery_type: str | None = None,
                            config_json: dict | None = None) -> dict | None:
        """Update an existing subscription.

        Returns updated subscription dict, or None if not found.
        """
        if delivery_type and delivery_type not in VALID_DELIVERY_TYPES:
            raise ValueError(
                f"Invalid delivery_type '{delivery_type}'. "
                f"Must be one of {VALID_DELIVERY_TYPES}"
            )

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sink_subscriptions WHERE sub_id = ?",
                (sub_id,),
            ).fetchone()
            if row is None:
                return None

            new_name = name if name is not None else row["name"]
            new_topic = topic_pattern if topic_pattern is not None else row["topic_pattern"]
            new_dtype = delivery_type if delivery_type is not None else row["delivery_type"]
            if config_json is not None:
                new_cfg = json.dumps(config_json)
            else:
                new_cfg = row["config_json"]

            self._conn.execute("""
                UPDATE sink_subscriptions
                SET name = ?, topic_pattern = ?, delivery_type = ?,
                    config_json = ?
                WHERE sub_id = ?
            """, (new_name, new_topic, new_dtype, new_cfg, sub_id))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM sink_subscriptions WHERE sub_id = ?",
                (sub_id,),
            ).fetchone()

        return self._row_to_dict(row)

    def delete_subscription(self, sub_id: str) -> bool:
        """Delete a subscription.

        Returns True if the subscription existed and was deleted.
        """
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM sink_subscriptions WHERE sub_id = ?",
                (sub_id,),
            ).rowcount
            self._conn.commit()
        return n > 0

    def list_subscriptions(self,
                           topic_pattern: str | None = None) -> list[dict]:
        """List subscriptions, optionally filtered by topic pattern."""
        with self._lock:
            if topic_pattern:
                rows = self._conn.execute(
                    "SELECT * FROM sink_subscriptions "
                    "WHERE topic_pattern = ? ORDER BY created_at",
                    (topic_pattern,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM sink_subscriptions ORDER BY created_at"
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Event delivery
    # ------------------------------------------------------------------

    def deliver_event(self, sub_id: str, event_json: dict) -> dict:
        """Deliver an event to a subscription.

        Creates a delivery record with pending status.
        Returns delivery dict with delivery_id.

        Raises:
            ValueError: If sub_id does not exist.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sink_subscriptions WHERE sub_id = ?",
                (sub_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Subscription '{sub_id}' not found")

        delivery_id = self._uid()
        now = time.time()
        event_str = json.dumps(event_json, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO sink_deliveries
                    (delivery_id, sub_id, event_json, status,
                     attempts, last_attempt_at, error_message, created_at)
                VALUES (?, ?, ?, 'pending', 0, NULL, NULL, ?)
            """, (delivery_id, sub_id, event_str, now))
            self._conn.commit()

        result = {
            "delivery_id": delivery_id,
            "sub_id": sub_id,
            "status": "pending",
            "attempts": 0,
            "created_at": now,
        }

        self._emit("event_delivered", {
            "delivery_id": delivery_id,
            "sub_id": sub_id,
        })
        log.info("event delivered: %s -> sub %s", delivery_id[:12], sub_id[:12])
        return result

    def list_deliveries(self, sub_id: str | None = None,
                        status: str | None = None,
                        limit: int = 100) -> list[dict]:
        """List deliveries with optional filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if sub_id is not None:
            clauses.append("sub_id = ?")
            params.append(sub_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (f"SELECT * FROM sink_deliveries{where} "
               f"ORDER BY created_at DESC LIMIT ?")
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def retry_delivery(self, delivery_id: str) -> dict | None:
        """Retry a failed delivery.

        Resets status to 'pending' and increments attempts.
        Returns updated delivery dict, or None if not found.
        """
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sink_deliveries WHERE delivery_id = ?",
                (delivery_id,),
            ).fetchone()
            if row is None:
                return None

            new_attempts = row["attempts"] + 1
            self._conn.execute("""
                UPDATE sink_deliveries
                SET status = 'pending', attempts = ?,
                    last_attempt_at = ?, error_message = NULL
                WHERE delivery_id = ?
            """, (new_attempts, now, delivery_id))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM sink_deliveries WHERE delivery_id = ?",
                (delivery_id,),
            ).fetchone()

        result = self._row_to_dict(row)
        self._emit("delivery_failed" if new_attempts > 3 else "event_delivered", {
            "delivery_id": delivery_id,
            "attempts": new_attempts,
        })
        return result

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_sink_stats(self) -> dict:
        """Aggregate statistics across all subscriptions and deliveries."""
        with self._lock:
            total_subs = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sink_subscriptions"
            ).fetchone()["cnt"]

            total_deliveries = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sink_deliveries"
            ).fetchone()["cnt"]

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM sink_deliveries "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            type_rows = self._conn.execute(
                "SELECT delivery_type, COUNT(*) as cnt FROM sink_subscriptions "
                "GROUP BY delivery_type"
            ).fetchall()
            by_type = {r["delivery_type"]: r["cnt"] for r in type_rows}

        return {
            "total_subscriptions": total_subs,
            "total_deliveries": total_deliveries,
            "deliveries_by_status": by_status,
            "subscriptions_by_type": by_type,
        }

    # Alias kept for ``sylion.api.security_routes.audit_stats`` which calls
    # ``sink.get_stats()`` directly.
    def get_stats(self) -> dict:
        return self.get_sink_stats()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: AuditSink | None = None


def get_audit_sink(db_path: str = ":memory:",
                   event_bus: EventBus | None = None) -> AuditSink:
    """Get or create the global AuditSink singleton."""
    global _instance
    if _instance is None:
        _instance = AuditSink(db_path, event_bus)
    return _instance


def reset_audit_sink() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
