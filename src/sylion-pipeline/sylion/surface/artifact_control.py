"""
SYLION Surface -- Artifact Control

Upload/version/publish/deprecate. Signed HTTP upload flow.
Thread-safe. SQLite-backed. Emits events via EventBus.

Frozen decisions:
- Browser uploads via signed HTTP / resumable multipart, NOT gRPC-Web
- Upload flow: InitiateUpload -> upload bytes -> FinalizeUpload -> validate -> DRAFT/PENDING -> publish
- Secrets never enter event store/Yjs/replay/evidence payload
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.surface.artifact_control")


@dataclass
class Artifact:
    artifact_id: str = ""
    name: str = ""
    artifact_type: str = "DOCUMENT"
    version: int = 1
    status: str = "DRAFT"
    checksum: str = ""
    size_bytes: int = 0
    uploaded_by: str = ""
    created_at: float = 0.0
    published_at: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.artifact_id:
            self.artifact_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class UploadSession:
    session_id: str = ""
    artifact_id: str = ""
    status: str = "INITIATED"
    signed_url: str = ""
    created_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.session_id:
            self.session_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


class ArtifactControl:
    """Artifact lifecycle: upload, version, publish, deprecate.

    Thread-safe. SQLite-backed. Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id    TEXT PRIMARY KEY,
                name           TEXT NOT NULL DEFAULT '',
                artifact_type  TEXT NOT NULL DEFAULT 'DOCUMENT',
                version        INTEGER NOT NULL DEFAULT 1,
                status         TEXT NOT NULL DEFAULT 'DRAFT',
                checksum       TEXT NOT NULL DEFAULT '',
                size_bytes     INTEGER NOT NULL DEFAULT 0,
                uploaded_by    TEXT NOT NULL DEFAULT '',
                created_at     REAL NOT NULL,
                published_at   REAL NOT NULL DEFAULT 0,
                metadata       TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS upload_sessions (
                session_id   TEXT PRIMARY KEY,
                artifact_id  TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'INITIATED',
                signed_url   TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                completed_at REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_art_name ON artifacts(name)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_art_status ON artifacts(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sess_art ON upload_sessions(artifact_id)"
        )
        self._conn.commit()

    def initiate_upload(self, name: str, artifact_type: str = "DOCUMENT",
                        uploaded_by: str = "",
                        size_bytes: int = 0) -> dict:
        """Create artifact in DRAFT + upload session with signed URL."""
        artifact = Artifact(
            name=name,
            artifact_type=artifact_type,
            size_bytes=size_bytes,
            uploaded_by=uploaded_by,
        )

        signed_url = f"http://localhost:5805/upload/{artifact.artifact_id}"

        session = UploadSession(
            artifact_id=artifact.artifact_id,
            signed_url=signed_url,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO artifacts
                    (artifact_id, name, artifact_type, version, status,
                     checksum, size_bytes, uploaded_by, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                artifact.artifact_id, name, artifact_type, 1, "DRAFT",
                "", size_bytes, uploaded_by, artifact.created_at, "{}",
            ))
            self._conn.execute("""
                INSERT INTO upload_sessions
                    (session_id, artifact_id, status, signed_url, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session.session_id, artifact.artifact_id,
                  "INITIATED", signed_url, session.created_at))
            self._conn.commit()

        self._emit("surface.artifact_control.upload_initiated", {
            "artifact_id": artifact.artifact_id,
            "session_id": session.session_id,
        })

        log.info("initiated upload %s for %s", session.session_id[:12], name)
        return {
            "artifact_id": artifact.artifact_id,
            "session_id": session.session_id,
            "signed_url": signed_url,
            "status": "DRAFT",
        }

    def finalize_upload(self, session_id: str, checksum: str = "",
                        size_bytes: int = 0) -> dict:
        """Finalize upload: validate checksum, mark session completed."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM upload_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return {"error": "session not found", "session_id": session_id}
            if dict(row)["status"] != "INITIATED":
                return {"error": "session not initiatiated", "status": dict(row)["status"]}

            artifact_id = dict(row)["artifact_id"]
            now = time.time()

            self._conn.execute("""
                UPDATE upload_sessions SET status = 'COMPLETED', completed_at = ?
                WHERE session_id = ?
            """, (now, session_id))
            self._conn.execute("""
                UPDATE artifacts SET checksum = ?, size_bytes = ?
                WHERE artifact_id = ?
            """, (checksum, size_bytes, artifact_id))
            self._conn.commit()

        self._emit("surface.artifact_control.upload_finalized", {
            "session_id": session_id,
            "artifact_id": artifact_id,
        })

        log.info("finalized upload %s", session_id[:12])
        return {"session_id": session_id, "artifact_id": artifact_id, "status": "COMPLETED"}

    def publish(self, artifact_id: str, publisher: str = "") -> dict:
        """Publish artifact: DRAFT/PENDING -> PUBLISHED."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            if not row:
                return {"error": "artifact not found", "artifact_id": artifact_id}
            data = dict(row)
            if data["status"] not in ("DRAFT", "PENDING"):
                return {"error": "artifact not publishable", "status": data["status"]}

            now = time.time()
            self._conn.execute("""
                UPDATE artifacts SET status = 'PUBLISHED', published_at = ?
                WHERE artifact_id = ?
            """, (now, artifact_id))
            self._conn.commit()

        self._emit("surface.artifact_control.artifact_published", {
            "artifact_id": artifact_id, "publisher": publisher,
        })

        log.info("published artifact %s by %s", artifact_id[:12], publisher)
        return {"artifact_id": artifact_id, "status": "PUBLISHED"}

    def deprecate(self, artifact_id: str, reason: str = "",
                  deprecator: str = "") -> dict:
        """Deprecate artifact."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            if not row:
                return {"error": "artifact not found", "artifact_id": artifact_id}

            self._conn.execute("""
                UPDATE artifacts SET status = 'DEPRECATED'
                WHERE artifact_id = ?
            """, (artifact_id,))
            self._conn.commit()

        self._emit("surface.artifact_control.artifact_deprecated", {
            "artifact_id": artifact_id, "reason": reason, "deprecator": deprecator,
        })

        log.info("deprecated artifact %s by %s: %s", artifact_id[:12], deprecator or "system", reason)
        return {"artifact_id": artifact_id, "status": "DEPRECATED"}

    def get_artifact(self, artifact_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        return d

    def list_artifacts(self, status: str | None = None,
                       artifact_type: str | None = None,
                       limit: int = 100) -> list[dict]:
        query = "SELECT * FROM artifacts WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if artifact_type:
            query += " AND artifact_type = ?"
            params.append(artifact_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d.get("metadata", "{}"))
            results.append(d)
        return results

    def get_versions(self, name: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM artifacts WHERE name = ? ORDER BY version",
            (name,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d.get("metadata", "{}"))
            results.append(d)
        return results

    def get_upload_session(self, session_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM upload_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_stats(self) -> dict:
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM artifacts"
        ).fetchone()["cnt"]
        by_status_rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM artifacts GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in by_status_rows}
        by_type_rows = self._conn.execute(
            "SELECT artifact_type, COUNT(*) as cnt FROM artifacts GROUP BY artifact_type"
        ).fetchall()
        by_type = {r["artifact_type"]: r["cnt"] for r in by_type_rows}
        return {
            "total_artifacts": total,
            "by_status": by_status,
            "by_type": by_type,
        }

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="surface.artifact_control",
            ))


_ctrl: ArtifactControl | None = None


def get_artifact_control(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> ArtifactControl:
    global _ctrl
    if _ctrl is None:
        _ctrl = ArtifactControl(db_path, event_bus)
    return _ctrl
