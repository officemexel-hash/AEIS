"""Funding SQLite store."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from sylion.demo.funding_pipeline_tracker.models import (
    Attachment, GrantApplication, GrantSignature, SubmissionAttempt,
)


class FundingStore:
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
                CREATE TABLE IF NOT EXISTS funding_applications (
                    application_id TEXT PRIMARY KEY,
                    project_id     TEXT NOT NULL DEFAULT '',
                    grant_program  TEXT NOT NULL,
                    title          TEXT NOT NULL DEFAULT '',
                    submitter_id   TEXT NOT NULL,
                    deadline_ts    REAL NOT NULL,
                    requested_amount_eur REAL NOT NULL DEFAULT 0,
                    status         TEXT NOT NULL DEFAULT 'draft',
                    created_at     REAL NOT NULL,
                    submitted_at   REAL
                );
                CREATE TABLE IF NOT EXISTS funding_attachments (
                    attachment_id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    filename       TEXT NOT NULL,
                    sha256         TEXT NOT NULL,
                    size_bytes     INTEGER NOT NULL,
                    mime_type      TEXT NOT NULL,
                    uploaded_at    REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS funding_signatures (
                    signature_id   TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    signer_id      TEXT NOT NULL,
                    signer_role    TEXT NOT NULL,
                    cert_serial    TEXT NOT NULL,
                    signed_at      REAL NOT NULL,
                    expires_at     REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS funding_submissions (
                    attempt_id     TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    attempted_at   REAL NOT NULL,
                    success        INTEGER NOT NULL,
                    error          TEXT NOT NULL DEFAULT '',
                    portal_response_code INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_app_status
                  ON funding_applications(status);
                CREATE INDEX IF NOT EXISTS idx_att_app
                  ON funding_attachments(application_id);
                CREATE INDEX IF NOT EXISTS idx_sig_app
                  ON funding_signatures(application_id);
            """)
            self._conn.commit()

    # Applications
    def create_app(self, app: GrantApplication) -> GrantApplication:
        with self._lock:
            self._conn.execute("""
                INSERT INTO funding_applications
                (application_id, project_id, grant_program, title,
                 submitter_id, deadline_ts, requested_amount_eur,
                 status, created_at, submitted_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (app.application_id, app.project_id, app.grant_program,
                  app.title, app.submitter_id, app.deadline_ts,
                  app.requested_amount_eur, app.status,
                  app.created_at, app.submitted_at))
            self._conn.commit()
        return app

    def get_app(self, application_id: str) -> GrantApplication | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM funding_applications WHERE application_id = ?",
                (application_id,),
            ).fetchone()
        if not r:
            return None
        return GrantApplication(
            application_id=r["application_id"], project_id=r["project_id"],
            grant_program=r["grant_program"], title=r["title"],
            submitter_id=r["submitter_id"], deadline_ts=r["deadline_ts"],
            requested_amount_eur=r["requested_amount_eur"],
            status=r["status"], created_at=r["created_at"],
            submitted_at=r["submitted_at"],
        )

    def update_app_status(
        self, application_id: str, status: str,
        submitted_at: float | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE funding_applications SET status = ?, submitted_at = ? "
                "WHERE application_id = ?",
                (status, submitted_at, application_id),
            )
            self._conn.commit()

    # Attachments
    def add_attachment(self, a: Attachment) -> Attachment:
        with self._lock:
            self._conn.execute("""
                INSERT INTO funding_attachments
                (attachment_id, application_id, filename, sha256,
                 size_bytes, mime_type, uploaded_at)
                VALUES (?,?,?,?,?,?,?)
            """, (a.attachment_id, a.application_id, a.filename, a.sha256,
                  a.size_bytes, a.mime_type, a.uploaded_at))
            self._conn.commit()
        return a

    def list_attachments(
        self, application_id: str,
    ) -> list[Attachment]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM funding_attachments WHERE application_id = ?",
                (application_id,),
            ).fetchall()
        return [
            Attachment(
                attachment_id=r["attachment_id"],
                application_id=r["application_id"],
                filename=r["filename"], sha256=r["sha256"],
                size_bytes=r["size_bytes"], mime_type=r["mime_type"],
                uploaded_at=r["uploaded_at"],
            ) for r in rows
        ]

    def total_attachment_bytes(self, application_id: str) -> int:
        with self._lock:
            r = self._conn.execute(
                "SELECT COALESCE(SUM(size_bytes), 0) AS total "
                "FROM funding_attachments WHERE application_id = ?",
                (application_id,),
            ).fetchone()
        return int(r["total"])

    # Signatures
    def add_signature(self, s: GrantSignature) -> GrantSignature:
        with self._lock:
            self._conn.execute("""
                INSERT INTO funding_signatures
                (signature_id, application_id, signer_id, signer_role,
                 cert_serial, signed_at, expires_at)
                VALUES (?,?,?,?,?,?,?)
            """, (s.signature_id, s.application_id, s.signer_id,
                  s.signer_role, s.cert_serial, s.signed_at, s.expires_at))
            self._conn.commit()
        return s

    def list_signatures(self, application_id: str) -> list[GrantSignature]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM funding_signatures WHERE application_id = ?",
                (application_id,),
            ).fetchall()
        return [
            GrantSignature(
                signature_id=r["signature_id"],
                application_id=r["application_id"],
                signer_id=r["signer_id"], signer_role=r["signer_role"],
                cert_serial=r["cert_serial"], signed_at=r["signed_at"],
                expires_at=r["expires_at"],
            ) for r in rows
        ]

    # Submissions
    def add_attempt(self, a: SubmissionAttempt) -> SubmissionAttempt:
        with self._lock:
            self._conn.execute("""
                INSERT INTO funding_submissions
                (attempt_id, application_id, attempted_at, success,
                 error, portal_response_code)
                VALUES (?,?,?,?,?,?)
            """, (a.attempt_id, a.application_id, a.attempted_at,
                  int(a.success), a.error, a.portal_response_code))
            self._conn.commit()
        return a

    def health(self) -> dict:
        with self._lock:
            counts = {}
            for t in ("funding_applications", "funding_attachments",
                      "funding_signatures", "funding_submissions"):
                counts[t] = self._conn.execute(
                    f"SELECT COUNT(*) AS c FROM {t}",
                ).fetchone()["c"]
        return {"ok": True, "counts": counts, "ts": time.time()}


__all__ = ["FundingStore"]
