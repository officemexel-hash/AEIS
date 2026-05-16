"""SQLite-backed store for inspections, photos, signatures, queue."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sylion.demo.mobile_field_inspector.models import (
    FieldInspection, OfflineQueueEntry, PhotoEvidence, SignatureEvidence,
)

log = logging.getLogger("sylion.demo.mobile_field_inspector.store")


class InspectorStore:
    """Thread-safe SQLite store for inspector domain."""

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
                CREATE TABLE IF NOT EXISTS field_inspections (
                    inspection_id   TEXT PRIMARY KEY,
                    project_id      TEXT NOT NULL DEFAULT '',
                    inspector_id    TEXT NOT NULL,
                    location_label  TEXT NOT NULL DEFAULT '',
                    notes           TEXT NOT NULL DEFAULT '',
                    gps_json        TEXT,
                    status          TEXT NOT NULL DEFAULT 'draft',
                    revision        INTEGER NOT NULL DEFAULT 0,
                    created_at      REAL NOT NULL,
                    updated_at      REAL NOT NULL,
                    synced_at       REAL
                );
                CREATE TABLE IF NOT EXISTS field_photos (
                    photo_id        TEXT PRIMARY KEY,
                    inspection_id   TEXT NOT NULL,
                    sha256          TEXT NOT NULL,
                    size_bytes      INTEGER NOT NULL,
                    mime_type       TEXT NOT NULL DEFAULT 'image/jpeg',
                    captured_at     REAL NOT NULL,
                    FOREIGN KEY (inspection_id) REFERENCES field_inspections(inspection_id)
                );
                CREATE TABLE IF NOT EXISTS field_signatures (
                    signature_id    TEXT PRIMARY KEY,
                    inspection_id   TEXT NOT NULL,
                    signer_id       TEXT NOT NULL,
                    signature_data_b64 TEXT NOT NULL,
                    signed_at       REAL NOT NULL,
                    FOREIGN KEY (inspection_id) REFERENCES field_inspections(inspection_id)
                );
                CREATE TABLE IF NOT EXISTS field_offline_queue (
                    queue_id        TEXT PRIMARY KEY,
                    inspection_id   TEXT NOT NULL,
                    queued_at       REAL NOT NULL,
                    attempt_count   INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at REAL,
                    last_error      TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_insp_inspector
                  ON field_inspections(inspector_id);
                CREATE INDEX IF NOT EXISTS idx_insp_status
                  ON field_inspections(status);
                CREATE INDEX IF NOT EXISTS idx_photo_insp
                  ON field_photos(inspection_id);
                CREATE INDEX IF NOT EXISTS idx_sig_insp
                  ON field_signatures(inspection_id);
                CREATE INDEX IF NOT EXISTS idx_queue_insp
                  ON field_offline_queue(inspection_id);
            """)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Inspections
    # ------------------------------------------------------------------

    def create_inspection(self, insp: FieldInspection) -> FieldInspection:
        gps_json = json.dumps(asdict(insp.gps)) if insp.gps else None
        with self._lock:
            self._conn.execute("""
                INSERT INTO field_inspections
                  (inspection_id, project_id, inspector_id, location_label,
                   notes, gps_json, status, revision, created_at, updated_at, synced_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                insp.inspection_id, insp.project_id, insp.inspector_id,
                insp.location_label, insp.notes, gps_json,
                insp.status, insp.revision,
                insp.created_at, insp.updated_at, insp.synced_at,
            ))
            self._conn.commit()
        return insp

    def get_inspection(self, inspection_id: str) -> FieldInspection | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM field_inspections WHERE inspection_id = ?",
                (inspection_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_inspection(row)

    def list_inspections(
        self, inspector_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[FieldInspection]:
        sql = "SELECT * FROM field_inspections WHERE 1=1"
        params: list[Any] = []
        if inspector_id:
            sql += " AND inspector_id = ?"
            params.append(inspector_id)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_inspection(r) for r in rows]

    def update_inspection(
        self, inspection_id: str, expected_revision: int,
        **fields: Any,
    ) -> FieldInspection:
        """Update with optimistic concurrency (multi-tab confusion guard).

        Raises RuntimeError if expected_revision mismatch.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT revision FROM field_inspections WHERE inspection_id = ?",
                (inspection_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"inspection not found: {inspection_id}")
            current_rev = row["revision"]
            if current_rev != expected_revision:
                raise RuntimeError(
                    f"revision conflict: client={expected_revision}, "
                    f"server={current_rev}"
                )

            allowed = ("status", "notes", "location_label", "synced_at")
            sets: list[str] = ["revision = ?", "updated_at = ?"]
            params: list[Any] = [current_rev + 1, time.time()]
            for k, v in fields.items():
                if k not in allowed:
                    continue
                sets.append(f"{k} = ?")
                params.append(v)
            params.append(inspection_id)
            self._conn.execute(
                f"UPDATE field_inspections SET {', '.join(sets)} "
                f"WHERE inspection_id = ?",
                params,
            )
            self._conn.commit()
        return self.get_inspection(inspection_id)

    # ------------------------------------------------------------------
    # Photos
    # ------------------------------------------------------------------

    def add_photo(self, photo: PhotoEvidence) -> PhotoEvidence:
        with self._lock:
            self._conn.execute("""
                INSERT INTO field_photos
                  (photo_id, inspection_id, sha256, size_bytes,
                   mime_type, captured_at)
                VALUES (?,?,?,?,?,?)
            """, (
                photo.photo_id, photo.inspection_id, photo.sha256,
                photo.size_bytes, photo.mime_type, photo.captured_at,
            ))
            self._conn.commit()
        return photo

    def list_photos(self, inspection_id: str) -> list[PhotoEvidence]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM field_photos WHERE inspection_id = ? "
                "ORDER BY captured_at",
                (inspection_id,),
            ).fetchall()
        return [
            PhotoEvidence(
                photo_id=r["photo_id"],
                inspection_id=r["inspection_id"],
                sha256=r["sha256"],
                size_bytes=r["size_bytes"],
                mime_type=r["mime_type"],
                captured_at=r["captured_at"],
            ) for r in rows
        ]

    # ------------------------------------------------------------------
    # Signatures
    # ------------------------------------------------------------------

    def add_signature(self, sig: SignatureEvidence) -> SignatureEvidence:
        with self._lock:
            self._conn.execute("""
                INSERT INTO field_signatures
                  (signature_id, inspection_id, signer_id,
                   signature_data_b64, signed_at)
                VALUES (?,?,?,?,?)
            """, (
                sig.signature_id, sig.inspection_id, sig.signer_id,
                sig.signature_data_b64, sig.signed_at,
            ))
            self._conn.commit()
        return sig

    def list_signatures(self, inspection_id: str) -> list[SignatureEvidence]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM field_signatures WHERE inspection_id = ? "
                "ORDER BY signed_at",
                (inspection_id,),
            ).fetchall()
        return [
            SignatureEvidence(
                signature_id=r["signature_id"],
                inspection_id=r["inspection_id"],
                signer_id=r["signer_id"],
                signature_data_b64=r["signature_data_b64"],
                signed_at=r["signed_at"],
            ) for r in rows
        ]

    # ------------------------------------------------------------------
    # Offline queue
    # ------------------------------------------------------------------

    def enqueue(self, entry: OfflineQueueEntry) -> OfflineQueueEntry:
        with self._lock:
            self._conn.execute("""
                INSERT INTO field_offline_queue
                  (queue_id, inspection_id, queued_at,
                   attempt_count, last_attempt_at, last_error)
                VALUES (?,?,?,?,?,?)
            """, (
                entry.queue_id, entry.inspection_id, entry.queued_at,
                entry.attempt_count, entry.last_attempt_at, entry.last_error,
            ))
            self._conn.commit()
        return entry

    def list_queue(self) -> list[OfflineQueueEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM field_offline_queue ORDER BY queued_at",
            ).fetchall()
        return [
            OfflineQueueEntry(
                queue_id=r["queue_id"],
                inspection_id=r["inspection_id"],
                queued_at=r["queued_at"],
                attempt_count=r["attempt_count"],
                last_attempt_at=r["last_attempt_at"],
                last_error=r["last_error"],
            ) for r in rows
        ]

    def mark_queue_attempt(
        self, queue_id: str, success: bool, error: str | None = None,
    ) -> None:
        with self._lock:
            if success:
                self._conn.execute(
                    "DELETE FROM field_offline_queue WHERE queue_id = ?",
                    (queue_id,),
                )
            else:
                self._conn.execute("""
                    UPDATE field_offline_queue
                    SET attempt_count = attempt_count + 1,
                        last_attempt_at = ?,
                        last_error = ?
                    WHERE queue_id = ?
                """, (time.time(), error or "", queue_id))
            self._conn.commit()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> dict:
        with self._lock:
            counts = {}
            for table in ("field_inspections", "field_photos",
                          "field_signatures", "field_offline_queue"):
                cnt = self._conn.execute(
                    f"SELECT COUNT(*) as c FROM {table}",
                ).fetchone()["c"]
                counts[table] = cnt
        return {"ok": True, "counts": counts, "ts": time.time()}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_inspection(row: sqlite3.Row) -> FieldInspection:
        from sylion.demo.mobile_field_inspector.models import GpsCoord
        gps_obj = None
        if row["gps_json"]:
            try:
                d = json.loads(row["gps_json"])
                gps_obj = GpsCoord(**d)
            except (json.JSONDecodeError, ValueError, TypeError):
                gps_obj = None
        return FieldInspection(
            inspection_id=row["inspection_id"],
            project_id=row["project_id"],
            inspector_id=row["inspector_id"],
            location_label=row["location_label"],
            notes=row["notes"],
            gps=gps_obj,
            status=row["status"],
            revision=row["revision"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            synced_at=row["synced_at"],
        )


__all__ = ["InspectorStore"]
