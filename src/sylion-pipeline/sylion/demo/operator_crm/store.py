"""CRM SQLite store + append-only audit."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from sylion.demo.operator_crm.models import (
    AuditEntry, Contact, ProjectLink,
)


class CrmStore:
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
                CREATE TABLE IF NOT EXISTS crm_contacts (
                    contact_id  TEXT PRIMARY KEY,
                    full_name   TEXT NOT NULL,
                    email       TEXT NOT NULL,
                    phone       TEXT NOT NULL DEFAULT '',
                    role        TEXT NOT NULL DEFAULT 'lead',
                    status      TEXT NOT NULL DEFAULT 'active',
                    notes       TEXT NOT NULL DEFAULT '',
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL,
                    deleted_at  REAL,
                    merged_into TEXT
                );
                CREATE TABLE IF NOT EXISTS crm_project_links (
                    link_id      TEXT PRIMARY KEY,
                    contact_id   TEXT NOT NULL,
                    aeis_project_id TEXT NOT NULL,
                    relationship TEXT NOT NULL DEFAULT 'owner',
                    created_at   REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS crm_audit_log (
                    entry_id      TEXT PRIMARY KEY,
                    actor_id      TEXT NOT NULL,
                    action        TEXT NOT NULL,
                    target_id     TEXT NOT NULL,
                    target_type   TEXT NOT NULL,
                    payload_redacted TEXT NOT NULL DEFAULT '{}',
                    created_at    REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_con_email ON crm_contacts(email);
                CREATE INDEX IF NOT EXISTS idx_con_status ON crm_contacts(status);
                CREATE INDEX IF NOT EXISTS idx_audit_target ON crm_audit_log(target_id);
            """)
            self._conn.commit()

    # Contacts
    def create_contact(self, c: Contact) -> Contact:
        with self._lock:
            self._conn.execute("""
                INSERT INTO crm_contacts
                (contact_id, full_name, email, phone, role, status,
                 notes, created_at, updated_at, deleted_at, merged_into)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (c.contact_id, c.full_name, c.email, c.phone,
                  c.role, c.status, c.notes,
                  c.created_at, c.updated_at, c.deleted_at, c.merged_into))
            self._conn.commit()
        return c

    def get_contact(self, contact_id: str) -> Contact | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM crm_contacts WHERE contact_id = ?",
                (contact_id,),
            ).fetchone()
        if not r:
            return None
        return self._row_to_contact(r)

    def list_contacts(
        self, status: str | None = None, limit: int = 100,
    ) -> list[Contact]:
        sql = "SELECT * FROM crm_contacts WHERE 1=1"
        params = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_contact(r) for r in rows]

    def find_by_email(self, email: str) -> Contact | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM crm_contacts WHERE email = ? "
                "AND status = 'active'", (email,),
            ).fetchone()
        return self._row_to_contact(r) if r else None

    def soft_delete_gdpr(self, contact_id: str) -> None:
        """GDPR right-to-be-forgotten: PII redacted but record preserved
        for audit retention."""
        with self._lock:
            self._conn.execute("""
                UPDATE crm_contacts
                SET full_name = '[GDPR_REDACTED]',
                    email = 'redacted@gdpr.local',
                    phone = '',
                    notes = '',
                    status = 'deleted_gdpr',
                    deleted_at = ?,
                    updated_at = ?
                WHERE contact_id = ?
            """, (time.time(), time.time(), contact_id))
            self._conn.commit()

    def mark_merged(self, contact_id: str, survivor_id: str) -> None:
        with self._lock:
            self._conn.execute("""
                UPDATE crm_contacts
                SET status = 'merged', merged_into = ?, updated_at = ?
                WHERE contact_id = ?
            """, (survivor_id, time.time(), contact_id))
            self._conn.commit()

    # Project links
    def add_link(self, link: ProjectLink) -> ProjectLink:
        with self._lock:
            self._conn.execute("""
                INSERT INTO crm_project_links
                (link_id, contact_id, aeis_project_id, relationship, created_at)
                VALUES (?,?,?,?,?)
            """, (link.link_id, link.contact_id, link.aeis_project_id,
                  link.relationship, link.created_at))
            self._conn.commit()
        return link

    def list_links(self, contact_id: str) -> list[ProjectLink]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM crm_project_links WHERE contact_id = ?",
                (contact_id,),
            ).fetchall()
        return [
            ProjectLink(
                link_id=r["link_id"], contact_id=r["contact_id"],
                aeis_project_id=r["aeis_project_id"],
                relationship=r["relationship"], created_at=r["created_at"],
            ) for r in rows
        ]

    # Audit (append-only)
    def append_audit(self, entry: AuditEntry) -> AuditEntry:
        with self._lock:
            self._conn.execute("""
                INSERT INTO crm_audit_log
                (entry_id, actor_id, action, target_id, target_type,
                 payload_redacted, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (entry.entry_id, entry.actor_id, entry.action,
                  entry.target_id, entry.target_type,
                  json.dumps(entry.payload_redacted), entry.created_at))
            self._conn.commit()
        return entry

    def list_audit_for_target(self, target_id: str) -> list[AuditEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM crm_audit_log WHERE target_id = ? "
                "ORDER BY created_at", (target_id,),
            ).fetchall()
        return [
            AuditEntry(
                entry_id=r["entry_id"], actor_id=r["actor_id"],
                action=r["action"], target_id=r["target_id"],
                target_type=r["target_type"],
                payload_redacted=json.loads(r["payload_redacted"]),
                created_at=r["created_at"],
            ) for r in rows
        ]

    def health(self) -> dict:
        with self._lock:
            counts = {}
            for t in ("crm_contacts", "crm_project_links", "crm_audit_log"):
                counts[t] = self._conn.execute(
                    f"SELECT COUNT(*) AS c FROM {t}",
                ).fetchone()["c"]
        return {"ok": True, "counts": counts, "ts": time.time()}

    @staticmethod
    def _row_to_contact(r: sqlite3.Row) -> Contact:
        # Bypass __post_init__ for "redacted" GDPR contacts
        c = Contact.__new__(Contact)
        c.contact_id = r["contact_id"]
        c.full_name = r["full_name"]
        c.email = r["email"]
        c.phone = r["phone"]
        c.role = r["role"]
        c.status = r["status"]
        c.notes = r["notes"]
        c.created_at = r["created_at"]
        c.updated_at = r["updated_at"]
        c.deleted_at = r["deleted_at"]
        c.merged_into = r["merged_into"]
        return c


__all__ = ["CrmStore"]
