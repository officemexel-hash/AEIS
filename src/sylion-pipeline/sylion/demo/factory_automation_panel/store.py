"""SQLite store for factory automation."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from sylion.demo.factory_automation_panel.models import (
    Cabinet, EmergencyStop, IOMapping, ProgramUpload, SafetyInterlock,
)


class FactoryStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS factory_cabinets (
                    cabinet_id  TEXT PRIMARY KEY,
                    plant_id    TEXT NOT NULL,
                    name        TEXT NOT NULL,
                    plc_serial  TEXT NOT NULL,
                    firmware_version TEXT NOT NULL DEFAULT '',
                    last_backup_at   REAL,
                    last_estop_test_at REAL,
                    created_at  REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS factory_iomaps (
                    mapping_id  TEXT PRIMARY KEY,
                    cabinet_id  TEXT NOT NULL,
                    program_id  TEXT NOT NULL,
                    expected_plc_serial TEXT NOT NULL,
                    io_signature TEXT NOT NULL,
                    created_at  REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS factory_estops (
                    test_id     TEXT PRIMARY KEY,
                    cabinet_id  TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    passed      INTEGER NOT NULL,
                    response_time_ms REAL NOT NULL,
                    tested_at   REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS factory_uploads (
                    upload_id   TEXT PRIMARY KEY,
                    cabinet_id  TEXT NOT NULL,
                    mapping_id  TEXT NOT NULL,
                    program_sha256 TEXT NOT NULL,
                    status      TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    backup_id   TEXT,
                    estop_test_id TEXT,
                    dryrun_passed INTEGER,
                    council_session_id TEXT,
                    created_at  REAL NOT NULL,
                    uploaded_at REAL
                );
                CREATE TABLE IF NOT EXISTS factory_interlocks (
                    interlock_id TEXT PRIMARY KEY,
                    cabinet_id   TEXT NOT NULL,
                    name         TEXT NOT NULL,
                    active       INTEGER NOT NULL,
                    overridden   INTEGER NOT NULL DEFAULT 0,
                    override_council_session TEXT,
                    override_reason TEXT NOT NULL DEFAULT ''
                );
            """)
            self._conn.commit()

    # Cabinets
    def create_cabinet(self, c: Cabinet) -> Cabinet:
        with self._lock:
            self._conn.execute("""
                INSERT INTO factory_cabinets
                (cabinet_id, plant_id, name, plc_serial, firmware_version,
                 last_backup_at, last_estop_test_at, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (c.cabinet_id, c.plant_id, c.name, c.plc_serial,
                  c.firmware_version, c.last_backup_at,
                  c.last_estop_test_at, c.created_at))
            self._conn.commit()
        return c

    def get_cabinet(self, cabinet_id: str) -> Cabinet | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM factory_cabinets WHERE cabinet_id = ?",
                (cabinet_id,),
            ).fetchone()
        if not r:
            return None
        return Cabinet(
            cabinet_id=r["cabinet_id"], plant_id=r["plant_id"],
            name=r["name"], plc_serial=r["plc_serial"],
            firmware_version=r["firmware_version"],
            last_backup_at=r["last_backup_at"],
            last_estop_test_at=r["last_estop_test_at"],
            created_at=r["created_at"],
        )

    def update_cabinet_backup(self, cabinet_id: str, backup_at: float) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE factory_cabinets SET last_backup_at = ? "
                "WHERE cabinet_id = ?", (backup_at, cabinet_id),
            )
            self._conn.commit()

    # IO mappings
    def add_iomap(self, m: IOMapping) -> IOMapping:
        with self._lock:
            self._conn.execute("""
                INSERT INTO factory_iomaps
                (mapping_id, cabinet_id, program_id, expected_plc_serial,
                 io_signature, created_at)
                VALUES (?,?,?,?,?,?)
            """, (m.mapping_id, m.cabinet_id, m.program_id,
                  m.expected_plc_serial, m.io_signature, m.created_at))
            self._conn.commit()
        return m

    def get_iomap(self, mapping_id: str) -> IOMapping | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM factory_iomaps WHERE mapping_id = ?",
                (mapping_id,),
            ).fetchone()
        if not r:
            return None
        return IOMapping(
            mapping_id=r["mapping_id"], cabinet_id=r["cabinet_id"],
            program_id=r["program_id"],
            expected_plc_serial=r["expected_plc_serial"],
            io_signature=r["io_signature"], created_at=r["created_at"],
        )

    # E-stops
    def add_estop(self, e: EmergencyStop) -> EmergencyStop:
        with self._lock:
            self._conn.execute("""
                INSERT INTO factory_estops
                (test_id, cabinet_id, operator_id, passed,
                 response_time_ms, tested_at)
                VALUES (?,?,?,?,?,?)
            """, (e.test_id, e.cabinet_id, e.operator_id,
                  int(e.passed), e.response_time_ms, e.tested_at))
            self._conn.commit()
            self._conn.execute(
                "UPDATE factory_cabinets SET last_estop_test_at = ? "
                "WHERE cabinet_id = ?", (e.tested_at, e.cabinet_id),
            )
            self._conn.commit()
        return e

    # Uploads
    def add_upload(self, u: ProgramUpload) -> ProgramUpload:
        with self._lock:
            self._conn.execute("""
                INSERT INTO factory_uploads
                (upload_id, cabinet_id, mapping_id, program_sha256, status,
                 operator_id, backup_id, estop_test_id, dryrun_passed,
                 council_session_id, created_at, uploaded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (u.upload_id, u.cabinet_id, u.mapping_id,
                  u.program_sha256, u.status, u.operator_id,
                  u.backup_id, u.estop_test_id,
                  None if u.dryrun_passed is None else int(u.dryrun_passed),
                  u.council_session_id, u.created_at, u.uploaded_at))
            self._conn.commit()
        return u

    def update_upload_status(
        self, upload_id: str, status: str,
        uploaded_at: float | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE factory_uploads SET status = ?, uploaded_at = ? "
                "WHERE upload_id = ?",
                (status, uploaded_at, upload_id),
            )
            self._conn.commit()

    # Interlocks
    def add_interlock(self, i: SafetyInterlock) -> SafetyInterlock:
        with self._lock:
            self._conn.execute("""
                INSERT INTO factory_interlocks
                (interlock_id, cabinet_id, name, active, overridden,
                 override_council_session, override_reason)
                VALUES (?,?,?,?,?,?,?)
            """, (i.interlock_id, i.cabinet_id, i.name, int(i.active),
                  int(i.overridden), i.override_council_session,
                  i.override_reason))
            self._conn.commit()
        return i

    def health(self) -> dict:
        with self._lock:
            counts = {}
            for t in ("factory_cabinets", "factory_iomaps", "factory_estops",
                      "factory_uploads", "factory_interlocks"):
                counts[t] = self._conn.execute(
                    f"SELECT COUNT(*) AS c FROM {t}"
                ).fetchone()["c"]
        return {"ok": True, "counts": counts, "ts": time.time()}


__all__ = ["FactoryStore"]
