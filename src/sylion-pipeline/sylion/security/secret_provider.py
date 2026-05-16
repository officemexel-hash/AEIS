"""
SYLION Security -- Secret Provider

Encrypted secret management with rotation and access auditing.
Secrets are stored as base64-encoded values in SQLite (dev-light profile).
Production will use proper encryption (e.g. Vault integration).

Tables:
  secrets            -- stored secrets with encrypted values
  secret_versions    -- version history for rotation tracking
  secret_access_log  -- audit trail of every access / rotate / delete

Singleton: get_secret_provider() / reset_secret_provider()
"""

from __future__ import annotations

import base64
import json
import logging
import sqlite3
import threading
import time
import uuid
import warnings
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

warnings.warn(
    "secret_provider is deprecated; use key_store_unified",
    DeprecationWarning,
    stacklevel=2,
)

log = logging.getLogger("sylion.security.secret_provider")


def _encode(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _decode(encoded: str) -> str:
    return base64.b64decode(encoded).decode("utf-8")


class SecretProvider:
    """Secret management with base64 encoding, rotation, and access auditing.

    Thread-safe.  SQLite-backed.  Emits events to EventBus.
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
            CREATE TABLE IF NOT EXISTS secrets (
                name            TEXT PRIMARY KEY,
                value_encrypted TEXT NOT NULL,
                scope           TEXT NOT NULL DEFAULT 'default',
                metadata_json   TEXT NOT NULL DEFAULT '{}',
                version         INTEGER NOT NULL DEFAULT 1,
                created_at      REAL NOT NULL,
                updated_at      REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS secret_versions (
                version_id   TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                version      INTEGER NOT NULL,
                value_encrypted TEXT NOT NULL,
                created_at   REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS secret_access_log (
                log_id     TEXT PRIMARY KEY,
                secret_name TEXT NOT NULL,
                accessor   TEXT NOT NULL DEFAULT '',
                action     TEXT NOT NULL,
                logged_at  REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_secrets_scope "
            "ON secrets(scope)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_versions_name "
            "ON secret_versions(name)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_access_name "
            "ON secret_access_log(secret_name)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_access_action "
            "ON secret_access_log(action)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="security.secret_provider",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _parse_json(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    # ------------------------------------------------------------------
    # Secret CRUD
    # ------------------------------------------------------------------

    def store(self, name: str, label: str = "", value: str = "",
              scope: str = "default") -> dict:
        """Friendly alias: store(name, label, value).

        Wraps ``store_secret`` for the simpler positional style used by
        callers that only need (name, label, value). Stores label as
        metadata.
        """
        return self.store_secret(
            name=name,
            value_encrypted=value,
            scope=scope,
            metadata_json={"label": label} if label else None,
        )

    def retrieve(self, name: str) -> str | None:
        """Friendly alias: returns the decoded raw value of a secret, or None."""
        rec = self.get_secret(name)
        if not rec:
            return None
        # get_secret already returns the decoded value under 'value'
        return rec.get("value")

    def store_secret(self, name: str, value_encrypted: str,
                     scope: str = "default",
                     metadata_json: dict | None = None) -> dict:
        """Store a new secret (or overwrite existing).

        The value is base64-encoded before writing to disk.
        A version history entry is created.
        """
        encoded = _encode(value_encrypted)
        now = time.time()
        meta = json.dumps(metadata_json or {}, default=str)

        with self._lock:
            existing = self._conn.execute(
                "SELECT version FROM secrets WHERE name = ?", (name,),
            ).fetchone()

            version = 1
            if existing:
                version = existing["version"] + 1
                self._conn.execute(
                    "UPDATE secrets SET value_encrypted = ?, scope = ?, "
                    "metadata_json = ?, version = ?, updated_at = ? "
                    "WHERE name = ?",
                    (encoded, scope, meta, version, now, name),
                )
            else:
                self._conn.execute("""
                    INSERT INTO secrets
                        (name, value_encrypted, scope, metadata_json,
                         version, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name, encoded, scope, meta, version, now, now))

            # Version history
            self._conn.execute("""
                INSERT INTO secret_versions
                    (version_id, name, version, value_encrypted, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (self._uid(), name, version, encoded, now))
            self._conn.commit()

        self._emit("secret_stored", {
            "name": name, "scope": scope, "version": version,
        })
        log.info("stored secret %s (scope=%s, v%d)", name, scope, version)
        return {"name": name, "scope": scope, "version": version}

    def get_secret(self, name: str) -> dict | None:
        """Retrieve a secret by name. Returns decoded value.

        Logs the access event.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM secrets WHERE name = ?", (name,),
            ).fetchone()
        if not row:
            return None

        result = dict(row)
        try:
            result["value"] = _decode(result["value_encrypted"])
        except Exception:
            result["value"] = None
        result["metadata_json"] = self._parse_json(
            result.get("metadata_json"), {})

        self.log_access(name, "", "read")
        self._emit("secret_accessed", {"name": name})
        return result

    def rotate_secret(self, name: str, new_value: str) -> dict | None:
        """Rotate a secret with a new value. Creates a new version."""
        encoded = _encode(new_value)
        now = time.time()

        with self._lock:
            existing = self._conn.execute(
                "SELECT version FROM secrets WHERE name = ?", (name,),
            ).fetchone()
            if not existing:
                return None

            version = existing["version"] + 1
            self._conn.execute(
                "UPDATE secrets SET value_encrypted = ?, version = ?, "
                "updated_at = ? WHERE name = ?",
                (encoded, version, now, name),
            )
            self._conn.execute("""
                INSERT INTO secret_versions
                    (version_id, name, version, value_encrypted, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (self._uid(), name, version, encoded, now))
            self._conn.commit()

        self.log_access(name, "", "rotate")
        self._emit("secret_rotated", {
            "name": name, "new_version": version,
        })
        log.info("rotated secret %s to v%d", name, version)
        return {"name": name, "version": version}

    def delete_secret(self, name: str) -> bool:
        """Delete a secret and its version history."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM secrets WHERE name = ?", (name,),
            ).rowcount
            if n:
                self._conn.execute(
                    "DELETE FROM secret_versions WHERE name = ?",
                    (name,),
                )
            self._conn.commit()

        if n:
            self.log_access(name, "", "delete")
            self._emit("secret_deleted", {"name": name})
            log.info("deleted secret %s", name)
        return bool(n)

    def list_secrets(self, scope: str | None = None) -> list[dict]:
        """List secrets (without values), optionally filtered by scope."""
        with self._lock:
            if scope:
                rows = self._conn.execute(
                    "SELECT name, scope, metadata_json, version, "
                    "created_at, updated_at FROM secrets "
                    "WHERE scope = ? ORDER BY name",
                    (scope,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT name, scope, metadata_json, version, "
                    "created_at, updated_at FROM secrets ORDER BY name"
                ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["metadata_json"] = self._parse_json(d.get("metadata_json"), {})
            results.append(d)
        return results

    def get_secret_history(self, name: str,
                           limit: int = 20) -> list[dict]:
        """Return version history for a secret."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM secret_versions "
                "WHERE name = ? ORDER BY version DESC LIMIT ?",
                (name, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Access logging
    # ------------------------------------------------------------------

    def log_access(self, secret_name: str, accessor: str,
                   action: str) -> dict:
        """Record an access event in the audit log."""
        log_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO secret_access_log
                    (log_id, secret_name, accessor, action, logged_at)
                VALUES (?, ?, ?, ?, ?)
            """, (log_id, secret_name, accessor, action, now))
            self._conn.commit()

        return {"log_id": log_id, "secret_name": secret_name,
                "accessor": accessor, "action": action}

    def get_access_log(self, limit: int = 100) -> list[dict]:
        """Return recent access log entries."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM secret_access_log "
                "ORDER BY logged_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_secret_stats(self) -> dict[str, Any]:
        """Aggregate secret statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as c FROM secrets"
            ).fetchone()["c"]

            by_scope_rows = self._conn.execute(
                "SELECT scope, COUNT(*) as c FROM secrets GROUP BY scope"
            ).fetchall()
            by_scope = {r["scope"]: r["c"] for r in by_scope_rows}

            total_versions = self._conn.execute(
                "SELECT COUNT(*) as c FROM secret_versions"
            ).fetchone()["c"]

            total_access = self._conn.execute(
                "SELECT COUNT(*) as c FROM secret_access_log"
            ).fetchone()["c"]

            by_action_rows = self._conn.execute(
                "SELECT action, COUNT(*) as c FROM secret_access_log "
                "GROUP BY action"
            ).fetchall()
            by_action = {r["action"]: r["c"] for r in by_action_rows}

        return {
            "total_secrets": total,
            "by_scope": by_scope,
            "total_versions": total_versions,
            "total_access_events": total_access,
            "by_action": by_action,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_provider: SecretProvider | None = None


def get_secret_provider(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> SecretProvider:
    global _provider
    if _provider is None:
        _provider = SecretProvider(db_path, event_bus)
    return _provider


def reset_secret_provider(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> SecretProvider:
    global _provider
    _provider = SecretProvider(db_path, event_bus)
    return _provider
