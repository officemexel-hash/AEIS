"""
SYLION Operator Mobile -- device binding store.

Hook v1.0 (2026-04-25).
Changes: initial bridge-side device registry for operator mobile bindings.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class OperatorMobileStore:
    """SQLite-backed registry of operator mobile devices."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS operator_mobile_devices (
                device_id      TEXT PRIMARY KEY,
                operator_id    TEXT NOT NULL,
                device_token   TEXT NOT NULL UNIQUE,
                platform       TEXT NOT NULL,
                device_label   TEXT NOT NULL DEFAULT '',
                active         INTEGER NOT NULL DEFAULT 1,
                created_at     REAL NOT NULL,
                last_seen_at   REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_omd_operator
                ON operator_mobile_devices(operator_id);
            CREATE INDEX IF NOT EXISTS idx_omd_active
                ON operator_mobile_devices(active);
            """
        )
        self._conn.commit()

    @staticmethod
    def _now() -> float:
        return time.time()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def bind_device(
        self,
        operator_id: str,
        device_token: str,
        platform: str,
        device_label: str = "",
    ) -> dict[str, Any]:
        if not operator_id.strip():
            raise ValueError("operator_id is required")
        if not device_token.strip():
            raise ValueError("device_token is required")
        if not platform.strip():
            raise ValueError("platform is required")

        now = self._now()
        with self._lock:
            existing = self._conn.execute(
                """
                SELECT device_id
                  FROM operator_mobile_devices
                 WHERE device_token = ?
                """,
                (device_token,),
            ).fetchone()
            if existing:
                device_id = str(existing["device_id"])
                self._conn.execute(
                    """
                    UPDATE operator_mobile_devices
                       SET operator_id = ?,
                           platform = ?,
                           device_label = ?,
                           active = 1,
                           last_seen_at = ?
                     WHERE device_id = ?
                    """,
                    (operator_id, platform, device_label, now, device_id),
                )
            else:
                device_id = self._uid()
                self._conn.execute(
                    """
                    INSERT INTO operator_mobile_devices
                        (device_id, operator_id, device_token, platform,
                         device_label, active, created_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        device_id,
                        operator_id,
                        device_token,
                        platform,
                        device_label,
                        now,
                        now,
                    ),
                )
            self._conn.commit()
            row = self._conn.execute(
                """
                SELECT *
                  FROM operator_mobile_devices
                 WHERE device_id = ?
                """,
                (device_id,),
            ).fetchone()
        return self._to_dict(row) or {}

    def list_devices(self, operator_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT *
                  FROM operator_mobile_devices
                 WHERE operator_id = ? AND active = 1
                 ORDER BY created_at DESC
                """,
                (operator_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def unbind_device(self, device_id: str, operator_id: str | None = None) -> bool:
        with self._lock:
            if operator_id:
                result = self._conn.execute(
                    """
                    UPDATE operator_mobile_devices
                       SET active = 0,
                           last_seen_at = ?
                     WHERE device_id = ? AND operator_id = ? AND active = 1
                    """,
                    (self._now(), device_id, operator_id),
                )
            else:
                result = self._conn.execute(
                    """
                    UPDATE operator_mobile_devices
                       SET active = 0,
                           last_seen_at = ?
                     WHERE device_id = ? AND active = 1
                    """,
                    (self._now(), device_id),
                )
            self._conn.commit()
        return result.rowcount > 0


_store: OperatorMobileStore | None = None
_store_lock = threading.Lock()


def get_operator_mobile_store(
    db_path: str | Path | None = None,
) -> OperatorMobileStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = OperatorMobileStore(db_path=db_path)
        return _store


def reset_operator_mobile_store(
    db_path: str | Path | None = None,
) -> OperatorMobileStore:
    global _store
    with _store_lock:
        _store = OperatorMobileStore(db_path=db_path)
        return _store
