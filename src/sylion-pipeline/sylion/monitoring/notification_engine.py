"""
SYLION Monitoring -- Notification Engine

Manages notification channels (email, webhook, in-app) and rules that map
trigger conditions to channel delivery.  Notifications are created when rules
fire, tracked for read status, and logged for auditing.

Tables:
  notification_channels  -- delivery endpoints
  notification_rules     -- condition -> channel mappings
  notifications          -- individual notification records
  notification_log       -- delivery audit trail

SQLite-backed with WAL mode.  Thread-safe via threading.RLock().
Singleton via get_notification_engine() / reset_notification_engine().
Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.monitoring.notification_engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CHANNEL_TYPES = ("email", "webhook", "in_app", "slack")
VALID_SEVERITIES = ("info", "warning", "urgent", "critical")


# ---------------------------------------------------------------------------
# NotificationEngine
# ---------------------------------------------------------------------------

class NotificationEngine:
    """Channel-aware notification system with rules engine.

    Thread-safe.  SQLite-backed.  Emits events on channel creation,
    notification send, and read.
    """

    def __init__(self, db_path: str | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS notification_channels (
                channel_id   TEXT PRIMARY KEY,
                name         TEXT    NOT NULL,
                channel_type TEXT    NOT NULL,
                config       TEXT,
                enabled      INTEGER NOT NULL DEFAULT 1,
                created_at   REAL    NOT NULL,
                updated_at   REAL
            );
            CREATE TABLE IF NOT EXISTS notification_rules (
                rule_id            TEXT PRIMARY KEY,
                name               TEXT    NOT NULL,
                channel_id         TEXT    NOT NULL,
                trigger_condition  TEXT,
                severity_filter    TEXT,
                enabled            INTEGER NOT NULL DEFAULT 1,
                created_at         REAL    NOT NULL,
                updated_at         REAL
            );
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id TEXT PRIMARY KEY,
                rule_id         TEXT,
                channel_id      TEXT,
                title           TEXT    NOT NULL,
                message         TEXT    NOT NULL,
                severity        TEXT    NOT NULL DEFAULT 'info',
                metadata        TEXT,
                status          TEXT    NOT NULL DEFAULT 'unread',
                created_at      REAL    NOT NULL,
                read_at         REAL
            );
            CREATE TABLE IF NOT EXISTS notification_log (
                log_id      TEXT PRIMARY KEY,
                notification_id TEXT NOT NULL,
                channel_id  TEXT    NOT NULL,
                status      TEXT    NOT NULL,
                error       TEXT,
                created_at  REAL    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notification_preferences (
                pref_id    TEXT PRIMARY KEY,
                user_id    TEXT    NOT NULL,
                category   TEXT    NOT NULL,
                channel    TEXT    NOT NULL DEFAULT 'in_app',
                enabled    INTEGER NOT NULL DEFAULT 1,
                updated_at REAL    NOT NULL,
                UNIQUE(user_id, category)
            );
            CREATE TABLE IF NOT EXISTS notification_user_channels (
                user_channel_id TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                channel_type    TEXT NOT NULL,
                config          TEXT,
                created_at      REAL NOT NULL,
                UNIQUE(user_id, channel_type)
            );
            CREATE INDEX IF NOT EXISTS idx_nc_type
                ON notification_channels(channel_type);
            CREATE INDEX IF NOT EXISTS idx_nr_channel
                ON notification_rules(channel_id);
            CREATE INDEX IF NOT EXISTS idx_notif_status
                ON notifications(status);
            CREATE INDEX IF NOT EXISTS idx_notif_severity
                ON notifications(severity);
            CREATE INDEX IF NOT EXISTS idx_notif_created
                ON notifications(created_at);
            CREATE INDEX IF NOT EXISTS idx_nl_notif
                ON notification_log(notification_id);
            CREATE INDEX IF NOT EXISTS idx_npref_user
                ON notification_preferences(user_id);
            CREATE INDEX IF NOT EXISTS idx_nuc_user
                ON notification_user_channels(user_id);
        """)
        # Lazy migration: add user_id / category / priority to notifications.
        existing_cols = {row["name"] for row in self._conn.execute(
            "PRAGMA table_info(notifications)").fetchall()}
        if "user_id" not in existing_cols:
            self._conn.execute(
                "ALTER TABLE notifications ADD COLUMN user_id TEXT")
        if "category" not in existing_cols:
            self._conn.execute(
                "ALTER TABLE notifications ADD COLUMN category TEXT")
        if "priority" not in existing_cols:
            self._conn.execute(
                "ALTER TABLE notifications ADD COLUMN priority TEXT")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_notif_user "
            "ON notifications(user_id)")
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
                source_module="monitoring.notification_engine",
            ))

    # ------------------------------------------------------------------
    # Channel CRUD
    # ------------------------------------------------------------------

    def create_channel(self, name: str, channel_type: str,
                       config_json: str | dict | None = None) -> dict:
        """Create a new notification channel.

        Args:
            name: Human-readable channel name.
            channel_type: One of email, webhook, in_app, slack.
            config_json: Optional JSON string or dict with channel config.

        Returns:
            Dict with channel_id, name, channel_type, created_at.
        """
        if channel_type not in VALID_CHANNEL_TYPES:
            raise ValueError(
                f"Invalid channel_type '{channel_type}'. "
                f"Must be one of {VALID_CHANNEL_TYPES}"
            )

        channel_id = self._uid()
        now = time.time()
        config_str = (json.dumps(config_json) if isinstance(config_json, dict)
                      else config_json)

        with self._lock:
            self._conn.execute("""
                INSERT INTO notification_channels
                    (channel_id, name, channel_type, config, enabled, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (channel_id, name, channel_type, config_str, now))
            self._conn.commit()

        self._emit("channel_created", {
            "channel_id": channel_id,
            "name": name,
            "channel_type": channel_type,
        })
        log.info("channel created: %s (%s)", channel_id[:12], channel_type)
        return {
            "channel_id": channel_id,
            "name": name,
            "channel_type": channel_type,
            "config": config_str,
            "enabled": True,
            "created_at": now,
        }

    def update_channel(self, channel_id: str, *, name: str | None = None,
                       channel_type: str | None = None,
                       config_json: str | dict | None = None,
                       enabled: bool | None = None) -> dict | None:
        """Update a notification channel. Returns updated dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM notification_channels WHERE channel_id = ?",
                (channel_id,),
            ).fetchone()
            if row is None:
                return None

            updates: list[str] = []
            params: list[Any] = []

            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if channel_type is not None:
                if channel_type not in VALID_CHANNEL_TYPES:
                    raise ValueError(f"Invalid channel_type '{channel_type}'")
                updates.append("channel_type = ?")
                params.append(channel_type)
            if config_json is not None:
                config_str = (json.dumps(config_json)
                              if isinstance(config_json, dict)
                              else config_json)
                updates.append("config = ?")
                params.append(config_str)
            if enabled is not None:
                updates.append("enabled = ?")
                params.append(int(enabled))

            if updates:
                updates.append("updated_at = ?")
                params.append(time.time())
                params.append(channel_id)
                self._conn.execute(
                    f"UPDATE notification_channels SET {', '.join(updates)} "
                    f"WHERE channel_id = ?",
                    params,
                )
                self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM notification_channels WHERE channel_id = ?",
                (channel_id,),
            ).fetchone()

        return dict(row) if row else None

    def delete_channel(self, channel_id: str) -> bool:
        """Delete a channel. Returns True if it existed."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM notification_channels WHERE channel_id = ?",
                (channel_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def list_channels(self, channel_type: str | None = None) -> list[dict]:
        """List channels, optionally filtered by type."""
        with self._lock:
            if channel_type:
                rows = self._conn.execute(
                    "SELECT * FROM notification_channels "
                    "WHERE channel_type = ? ORDER BY created_at DESC",
                    (channel_type,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM notification_channels "
                    "ORDER BY created_at DESC",
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Rule CRUD
    # ------------------------------------------------------------------

    def create_rule(self, name: str, channel_id: str,
                    trigger_condition_json: str | dict | None = None,
                    severity_filter: str | None = None) -> dict:
        """Create a notification rule linking conditions to a channel.

        Args:
            name: Human-readable rule name.
            channel_id: Target channel for notifications from this rule.
            trigger_condition_json: JSON condition expression.
            severity_filter: Only fire for notifications >= this severity.

        Returns:
            Dict with rule_id, name, channel_id, created_at.
        """
        rule_id = self._uid()
        now = time.time()
        cond_str = (json.dumps(trigger_condition_json)
                    if isinstance(trigger_condition_json, dict)
                    else trigger_condition_json)

        with self._lock:
            self._conn.execute("""
                INSERT INTO notification_rules
                    (rule_id, name, channel_id, trigger_condition,
                     severity_filter, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (rule_id, name, channel_id, cond_str,
                  severity_filter, now))
            self._conn.commit()

        log.info("rule created: %s -> channel %s", rule_id[:12],
                 channel_id[:12])
        return {
            "rule_id": rule_id,
            "name": name,
            "channel_id": channel_id,
            "trigger_condition": cond_str,
            "severity_filter": severity_filter,
            "enabled": True,
            "created_at": now,
        }

    def update_rule(self, rule_id: str, *, name: str | None = None,
                    channel_id: str | None = None,
                    trigger_condition_json: str | dict | None = None,
                    severity_filter: str | None = None,
                    enabled: bool | None = None) -> dict | None:
        """Update a notification rule. Returns updated dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM notification_rules WHERE rule_id = ?",
                (rule_id,),
            ).fetchone()
            if row is None:
                return None

            updates: list[str] = []
            params: list[Any] = []

            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if channel_id is not None:
                updates.append("channel_id = ?")
                params.append(channel_id)
            if trigger_condition_json is not None:
                cond_str = (json.dumps(trigger_condition_json)
                            if isinstance(trigger_condition_json, dict)
                            else trigger_condition_json)
                updates.append("trigger_condition = ?")
                params.append(cond_str)
            if severity_filter is not None:
                updates.append("severity_filter = ?")
                params.append(severity_filter)
            if enabled is not None:
                updates.append("enabled = ?")
                params.append(int(enabled))

            if updates:
                updates.append("updated_at = ?")
                params.append(time.time())
                params.append(rule_id)
                self._conn.execute(
                    f"UPDATE notification_rules SET {', '.join(updates)} "
                    f"WHERE rule_id = ?",
                    params,
                )
                self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM notification_rules WHERE rule_id = ?",
                (rule_id,),
            ).fetchone()

        return dict(row) if row else None

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule. Returns True if it existed."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM notification_rules WHERE rule_id = ?",
                (rule_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def list_rules(self, channel_id: str | None = None) -> list[dict]:
        """List rules, optionally filtered by channel_id."""
        with self._lock:
            if channel_id:
                rows = self._conn.execute(
                    "SELECT * FROM notification_rules "
                    "WHERE channel_id = ? ORDER BY created_at DESC",
                    (channel_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM notification_rules "
                    "ORDER BY created_at DESC",
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Send / read notifications
    # ------------------------------------------------------------------

    def send_notification(self, rule_id: str, title: str, message: str,
                          severity: str = "info",
                          metadata_json: str | dict | None = None) -> dict:
        """Create and deliver a notification through the rule's channel.

        Evaluates the rule's severity filter before sending.  Logs the
        delivery attempt in notification_log.

        Args:
            rule_id: The rule whose channel will receive the notification.
            title: Short notification title.
            message: Full notification body.
            severity: info | warning | urgent | critical.
            metadata_json: Optional JSON string or dict with extra data.

        Returns:
            Dict with notification_id and details.

        Raises:
            ValueError: If the rule does not exist or severity is invalid.
        """
        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}'. "
                f"Must be one of {VALID_SEVERITIES}"
            )

        with self._lock:
            rule = self._conn.execute(
                "SELECT * FROM notification_rules WHERE rule_id = ?",
                (rule_id,),
            ).fetchone()

        if rule is None:
            raise ValueError(f"Rule '{rule_id}' not found")

        if not rule["enabled"]:
            raise ValueError(f"Rule '{rule_id}' is disabled")

        # Check severity filter
        sev_filter = rule["severity_filter"]
        if sev_filter is not None and sev_filter:
            sev_order = {"info": 0, "warning": 1, "urgent": 2, "critical": 3}
            if sev_order.get(severity, 0) < sev_order.get(sev_filter, 0):
                return {
                    "notification_id": None,
                    "status": "filtered",
                    "reason": f"severity '{severity}' below filter "
                              f"'{sev_filter}'",
                }

        notification_id = self._uid()
        now = time.time()
        meta_str = (json.dumps(metadata_json)
                    if isinstance(metadata_json, dict)
                    else metadata_json)

        with self._lock:
            self._conn.execute("""
                INSERT INTO notifications
                    (notification_id, rule_id, channel_id, title, message,
                     severity, metadata, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'unread', ?)
            """, (notification_id, rule_id, rule["channel_id"],
                  title, message, severity, meta_str, now))

            log_id = self._uid()
            self._conn.execute("""
                INSERT INTO notification_log
                    (log_id, notification_id, channel_id, status, created_at)
                VALUES (?, ?, ?, 'delivered', ?)
            """, (log_id, notification_id, rule["channel_id"], now))
            self._conn.commit()

        self._emit("notification_sent", {
            "notification_id": notification_id,
            "rule_id": rule_id,
            "channel_id": rule["channel_id"],
            "severity": severity,
        })
        log.info("notification sent: %s via rule %s", notification_id[:12],
                 rule_id[:12])
        return {
            "notification_id": notification_id,
            "rule_id": rule_id,
            "channel_id": rule["channel_id"],
            "title": title,
            "message": message,
            "severity": severity,
            "status": "unread",
            "created_at": now,
        }

    def get_notifications(self, status: str | None = None,
                          limit: int = 100) -> list[dict]:
        """List notifications, optionally filtered by status."""
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM notifications WHERE status = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM notifications "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def mark_read(self, notification_id: str) -> dict | None:
        """Mark a notification as read. Returns updated dict or None."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT notification_id FROM notifications "
                "WHERE notification_id = ? AND status = 'unread'",
                (notification_id,),
            ).fetchone()
            if not row:
                return None
            self._conn.execute(
                "UPDATE notifications SET status = 'read', read_at = ? "
                "WHERE notification_id = ?",
                (now, notification_id),
            )
            self._conn.commit()

        self._emit("notification_read", {
            "notification_id": notification_id,
        })
        return {
            "notification_id": notification_id,
            "status": "read",
            "read_at": now,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate notification statistics."""
        with self._lock:
            total_channels = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM notification_channels"
            ).fetchone()["cnt"]

            total_rules = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM notification_rules"
            ).fetchone()["cnt"]

            total_notifications = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM notifications"
            ).fetchone()["cnt"]

            sev_rows = self._conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM notifications "
                "GROUP BY severity"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in sev_rows}

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM notifications "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            type_rows = self._conn.execute(
                "SELECT channel_type, COUNT(*) as cnt "
                "FROM notification_channels GROUP BY channel_type"
            ).fetchall()
            by_channel_type = {r["channel_type"]: r["cnt"] for r in type_rows}

            log_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM notification_log"
            ).fetchone()["cnt"]

        return {
            "total_channels": total_channels,
            "total_rules": total_rules,
            "total_notifications": total_notifications,
            "total_log_entries": log_count,
            "by_severity": by_severity,
            "by_status": by_status,
            "by_channel_type": by_channel_type,
        }

    def get_notification_stats(self, user_id: str | None = None) -> dict:
        """Alias for ``sylion.api.monitoring_routes`` /notifications/stats which
        passes ``user_id`` for per-user counts. The base table is not user-keyed
        so when ``user_id`` is provided we report the same totals plus a
        ``user_id`` echo so the response shape stays stable."""
        base = self.get_stats()
        if user_id:
            base = {**base, "user_id": user_id}
        return base

    # ------------------------------------------------------------------
    # Workspace-vocabulary methods (user-keyed notifications)
    # ------------------------------------------------------------------

    def get_unread_count(self, user_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM notifications "
                "WHERE user_id = ? AND status = 'unread'",
                (user_id,),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def list_notifications(self, user_id: str | None = None,
                           category: str | None = None,
                           priority: str | None = None,
                           unread_only: bool = False,
                           limit: int = 50) -> list[dict]:
        clauses: list[str] = []
        params: list[Any] = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if priority is not None:
            clauses.append("priority = ?")
            params.append(priority)
        if unread_only:
            clauses.append("status = 'unread'")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM notifications {where} "
                "ORDER BY created_at DESC LIMIT ?",
                tuple(params),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_notification(self, notification_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM notifications WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
        return dict(row) if row else None

    def mark_all_read(self, user_id: str) -> int:
        now = time.time()
        with self._lock:
            n = self._conn.execute(
                "UPDATE notifications SET status = 'read', read_at = ? "
                "WHERE user_id = ? AND status = 'unread'",
                (now, user_id),
            ).rowcount
            self._conn.commit()
        return int(n or 0)

    def delete_notification(self, notification_id: str) -> bool:
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM notifications WHERE notification_id = ?",
                (notification_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def get_preferences(self, user_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM notification_preferences WHERE user_id = ? "
                "ORDER BY category ASC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_preference(self, user_id: str, category: str,
                       channel: str = "in_app", enabled: bool = True) -> dict:
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT pref_id FROM notification_preferences "
                "WHERE user_id = ? AND category = ?",
                (user_id, category),
            ).fetchone()
            if row:
                self._conn.execute(
                    "UPDATE notification_preferences SET channel = ?, "
                    "enabled = ?, updated_at = ? WHERE pref_id = ?",
                    (channel, int(enabled), now, row["pref_id"]),
                )
                pref_id = row["pref_id"]
            else:
                pref_id = self._uid()
                self._conn.execute(
                    "INSERT INTO notification_preferences "
                    "(pref_id, user_id, category, channel, enabled, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (pref_id, user_id, category, channel, int(enabled), now),
                )
            self._conn.commit()
        return {
            "pref_id": pref_id,
            "user_id": user_id,
            "category": category,
            "channel": channel,
            "enabled": bool(enabled),
            "updated_at": now,
        }

    def get_channels(self, user_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM notification_user_channels WHERE user_id = ? "
                "ORDER BY created_at ASC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def register_channel(self, user_id: str, channel_type: str,
                         config: dict | None = None) -> dict:
        now = time.time()
        cfg_str = json.dumps(config) if config else None
        with self._lock:
            row = self._conn.execute(
                "SELECT user_channel_id FROM notification_user_channels "
                "WHERE user_id = ? AND channel_type = ?",
                (user_id, channel_type),
            ).fetchone()
            if row:
                user_channel_id = row["user_channel_id"]
                self._conn.execute(
                    "UPDATE notification_user_channels SET config = ? "
                    "WHERE user_channel_id = ?",
                    (cfg_str, user_channel_id),
                )
            else:
                user_channel_id = self._uid()
                self._conn.execute(
                    "INSERT INTO notification_user_channels "
                    "(user_channel_id, user_id, channel_type, config, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_channel_id, user_id, channel_type, cfg_str, now),
                )
            self._conn.commit()
        return {
            "user_channel_id": user_channel_id,
            "user_id": user_id,
            "channel_type": channel_type,
            "config": cfg_str,
            "created_at": now,
        }

    def bulk_notify(self, user_ids: list[str], title: str, message: str,
                    category: str = "system",
                    priority: str = "info") -> list[dict]:
        out: list[dict] = []
        now = time.time()
        with self._lock:
            for uid in user_ids:
                nid = self._uid()
                self._conn.execute(
                    "INSERT INTO notifications "
                    "(notification_id, rule_id, channel_id, title, message, "
                    " severity, status, created_at, user_id, category, priority) "
                    "VALUES (?, NULL, NULL, ?, ?, ?, 'unread', ?, ?, ?, ?)",
                    (nid, title, message, priority, now, uid, category,
                     priority),
                )
                out.append({
                    "notification_id": nid, "user_id": uid,
                    "title": title, "category": category,
                    "priority": priority, "status": "unread",
                    "created_at": now,
                })
            self._conn.commit()
        return out

    def cleanup_read(self, older_than_days: int = 30) -> int:
        cutoff = time.time() - (older_than_days * 86400.0)
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM notifications WHERE status = 'read' "
                "AND read_at IS NOT NULL AND read_at < ?",
                (cutoff,),
            ).rowcount
            self._conn.commit()
        return int(n or 0)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: NotificationEngine | None = None


def get_notification_engine(db_path: str | None = None,
                            event_bus: EventBus | None = None) -> NotificationEngine:
    """Get or create the global NotificationEngine singleton."""
    global _instance
    if _instance is None:
        _instance = NotificationEngine(db_path, event_bus)
    return _instance


def reset_notification_engine() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
