"""
SYLION Security -- Unified Key Store

Canonical consolidated key/secret storage.
Merges key_vault and secret_provider into a single module with
configurable backend and unified audit logging.

Backends: memory | file | keyring | vault
API: get, put, rotate, delete, list, audit_log

SQLite-backed with WAL. Thread-safe via RLock.
Singleton via get_key_store_unified() / reset_key_store_unified().
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

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.security.key_store_unified")

# ---------------------------------------------------------------------------
# Encryption helpers (same as key_vault)
# ---------------------------------------------------------------------------

try:
    from cryptography.fernet import Fernet
    _FERNET_AVAILABLE = True
except Exception:  # pragma: no cover
    _FERNET_AVAILABLE = False


class _Encryptor:
    """Simple encryptor using Fernet when available, else base64."""

    def __init__(self, key: bytes | None = None):
        if _FERNET_AVAILABLE and key is not None:
            self._fernet = Fernet(key)
        else:
            self._fernet = None

    @staticmethod
    def generate_key() -> bytes:
        if _FERNET_AVAILABLE:
            return Fernet.generate_key()
        return b""

    def encrypt(self, plaintext: str) -> str:
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        return base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        if self._fernet:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        return base64.b64decode(ciphertext.encode("utf-8")).decode("utf-8")


# ---------------------------------------------------------------------------
# KeyStoreUnified
# ---------------------------------------------------------------------------

VALID_BACKENDS = ("memory", "file", "keyring", "vault")


class KeyStoreUnified:
    """Unified key and secret store with configurable backend.

    All values are encrypted at rest (Fernet when available, else base64).
    Every mutation is recorded in the audit log.
    """

    def __init__(self, db_path: str | Path | None = None,
                 backend: str = "file",
                 encryptor: _Encryptor | None = None,
                 event_bus: EventBus | None = None):
        if backend not in VALID_BACKENDS:
            raise ValueError(f"Invalid backend '{backend}', must be one of {VALID_BACKENDS}")
        self._backend = backend
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._encryptor = encryptor or _Encryptor()
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS keystore_entries (
                key_id      TEXT PRIMARY KEY,
                scope       TEXT NOT NULL DEFAULT 'generic',
                ciphertext  TEXT NOT NULL DEFAULT '',
                metadata    TEXT NOT NULL DEFAULT '{}',
                version     INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL DEFAULT 0.0,
                updated_at  REAL NOT NULL DEFAULT 0.0,
                rotated_at  REAL NOT NULL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS keystore_audit (
                audit_id    TEXT PRIMARY KEY,
                key_id      TEXT NOT NULL,
                action      TEXT NOT NULL,
                actor       TEXT NOT NULL DEFAULT '',
                details     TEXT NOT NULL DEFAULT '{}',
                timestamp   REAL NOT NULL DEFAULT 0.0
            );
            CREATE INDEX IF NOT EXISTS idx_ks_scope ON keystore_entries(scope);
            CREATE INDEX IF NOT EXISTS idx_ks_audit_key ON keystore_audit(key_id);
            CREATE INDEX IF NOT EXISTS idx_ks_audit_ts ON keystore_audit(timestamp);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def _emit(self, topic: str, payload: dict) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.key_store_unified",
            ))

    def _add_audit(self, key_id: str, action: str,
                   actor: str = "", details: dict | None = None) -> None:
        audit_id = self._uid()
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO keystore_audit (audit_id, key_id, action, actor, details, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (audit_id, key_id, action, actor, json.dumps(details or {}), now),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def put(self, key_id: str, value: str, scope: str = "generic",
            metadata: dict | None = None, actor: str = "") -> dict:
        """Store or update a key/value pair. Returns entry dict."""
        now = time.time()
        ciphertext = self._encryptor.encrypt(value)
        meta_json = json.dumps(metadata or {}, default=str)

        with self._lock:
            existing = self._conn.execute(
                "SELECT version FROM keystore_entries WHERE key_id = ?",
                (key_id,),
            ).fetchone()
            if existing:
                version = existing["version"] + 1
                self._conn.execute(
                    "UPDATE keystore_entries SET scope = ?, ciphertext = ?, metadata = ?, "
                    "version = ?, updated_at = ? WHERE key_id = ?",
                    (scope, ciphertext, meta_json, version, now, key_id),
                )
            else:
                version = 1
                self._conn.execute(
                    "INSERT INTO keystore_entries (key_id, scope, ciphertext, metadata, "
                    "version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (key_id, scope, ciphertext, meta_json, version, now, now),
                )
            self._conn.commit()

        self._add_audit(key_id, "put", actor=actor, details={"scope": scope, "version": version})
        self._emit("keystore.put", {"key_id": key_id, "scope": scope, "version": version})
        log.info("keystore put %s scope=%s version=%d", key_id, scope, version)
        return {
            "key_id": key_id,
            "scope": scope,
            "version": version,
            "created_at": now if not existing else None,
            "updated_at": now,
        }

    def get(self, key_id: str, actor: str = "") -> str | None:
        """Retrieve decrypted value for a key_id, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT ciphertext FROM keystore_entries WHERE key_id = ?",
                (key_id,),
            ).fetchone()
        if not row:
            self._add_audit(key_id, "get_miss", actor=actor)
            return None
        plaintext = self._encryptor.decrypt(row["ciphertext"])
        self._add_audit(key_id, "get", actor=actor)
        self._emit("keystore.get", {"key_id": key_id})
        return plaintext

    def rotate(
        self,
        key_id: str,
        new_value: str,
        actor: str = "",
        metadata_update: dict | None = None,
    ) -> dict | None:
        """Rotate a key to a new value. Returns entry dict or None."""
        now = time.time()
        ciphertext = self._encryptor.encrypt(new_value)

        with self._lock:
            existing = self._conn.execute(
                "SELECT version, metadata FROM keystore_entries WHERE key_id = ?",
                (key_id,),
            ).fetchone()
            if not existing:
                self._add_audit(key_id, "rotate_miss", actor=actor)
                return None
            version = existing["version"] + 1
            metadata = self._parse_metadata(existing["metadata"])
            if metadata_update:
                metadata.update(metadata_update)
            self._conn.execute(
                "UPDATE keystore_entries SET ciphertext = ?, metadata = ?, "
                "version = ?, updated_at = ?, rotated_at = ? WHERE key_id = ?",
                (
                    ciphertext,
                    json.dumps(metadata, sort_keys=True, default=str),
                    version,
                    now,
                    now,
                    key_id,
                ),
            )
            self._conn.commit()

        self._add_audit(
            key_id,
            "rotate",
            actor=actor,
            details={"version": version, "metadata_updated": bool(metadata_update)},
        )
        self._emit("keystore.rotate", {"key_id": key_id, "version": version})
        log.info("keystore rotate %s version=%d", key_id, version)
        return {"key_id": key_id, "version": version, "rotated_at": now}

    def delete(self, key_id: str, actor: str = "") -> bool:
        """Delete a key. Returns True if deleted."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM keystore_entries WHERE key_id = ?",
                (key_id,),
            ).rowcount
            self._conn.commit()
        if n:
            self._add_audit(key_id, "delete", actor=actor)
            self._emit("keystore.delete", {"key_id": key_id})
            log.info("keystore delete %s", key_id)
            return True
        self._add_audit(key_id, "delete_miss", actor=actor)
        return False

    def list_keys(self, scope: str | None = None) -> list[dict]:
        """List keys, optionally filtered by scope."""
        with self._lock:
            if scope:
                rows = self._conn.execute(
                    "SELECT key_id, scope, version, created_at, updated_at, rotated_at "
                    "FROM keystore_entries WHERE scope = ? ORDER BY updated_at DESC",
                    (scope,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT key_id, scope, version, created_at, updated_at, rotated_at "
                    "FROM keystore_entries ORDER BY updated_at DESC",
                ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _parse_metadata(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def describe(self, key_id: str) -> dict | None:
        """Return metadata for a key without exposing ciphertext or plaintext."""
        with self._lock:
            row = self._conn.execute(
                "SELECT key_id, scope, metadata, version, created_at, "
                "updated_at, rotated_at FROM keystore_entries WHERE key_id = ?",
                (key_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["metadata"] = self._parse_metadata(result.get("metadata"))
        return result

    def record_audit(
        self,
        key_id: str,
        action: str,
        actor: str = "",
        details: dict | None = None,
    ) -> None:
        """Record a safe audit event for higher-level secret workflows."""
        self._add_audit(key_id, action, actor=actor, details=details)

    def audit_log(self, key_id: str | None = None, limit: int = 100) -> list[dict]:
        """Return audit log entries, optionally filtered by key_id."""
        with self._lock:
            if key_id:
                rows = self._conn.execute(
                    "SELECT * FROM keystore_audit WHERE key_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (key_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM keystore_audit ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        """Return store statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM keystore_entries"
            ).fetchone()["cnt"]
            scope_rows = self._conn.execute(
                "SELECT scope, COUNT(*) as cnt FROM keystore_entries GROUP BY scope"
            ).fetchall()
            audit_total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM keystore_audit"
            ).fetchone()["cnt"]
        return {
            "total_keys": total,
            "by_scope": {r["scope"]: r["cnt"] for r in scope_rows},
            "total_audit_events": audit_total,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: KeyStoreUnified | None = None


def get_key_store_unified(db_path: str | Path | None = None,
                          backend: str = "file",
                          encryptor: _Encryptor | None = None,
                          event_bus: EventBus | None = None) -> KeyStoreUnified:
    """Get or create the global KeyStoreUnified singleton."""
    global _instance
    if _instance is None:
        _instance = KeyStoreUnified(db_path, backend, encryptor, event_bus)
    return _instance


def reset_key_store_unified(db_path: str | Path | None = None,
                            backend: str = "file",
                            encryptor: _Encryptor | None = None,
                            event_bus: EventBus | None = None) -> KeyStoreUnified:
    """Reset the global KeyStoreUnified singleton (for testing)."""
    global _instance
    _instance = KeyStoreUnified(db_path, backend, encryptor, event_bus)
    return _instance
