"""Skills Marketplace SQLite store."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from sylion.demo.skills_marketplace.models import (
    Skill, SkillDependency, SkillReview, SkillScanResult,
)


class MarketplaceStore:
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
                CREATE TABLE IF NOT EXISTS marketplace_skills (
                    skill_id      TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    version       TEXT NOT NULL,
                    author_id     TEXT NOT NULL,
                    description   TEXT NOT NULL DEFAULT '',
                    sha256        TEXT NOT NULL,
                    signature_pubkey TEXT NOT NULL,
                    status        TEXT NOT NULL,
                    cost_budget_usd REAL NOT NULL,
                    council_session_id TEXT,
                    created_at    REAL NOT NULL,
                    approved_at   REAL,
                    UNIQUE(name, version)
                );
                CREATE TABLE IF NOT EXISTS marketplace_dependencies (
                    dep_id      TEXT PRIMARY KEY,
                    skill_id    TEXT NOT NULL,
                    dep_name    TEXT NOT NULL,
                    dep_version_pin TEXT NOT NULL,
                    dep_sha256  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS marketplace_scans (
                    scan_id     TEXT PRIMARY KEY,
                    skill_id    TEXT NOT NULL,
                    findings    TEXT NOT NULL DEFAULT '[]',
                    severity_max TEXT NOT NULL,
                    scanner_version TEXT NOT NULL DEFAULT '1.0',
                    scanned_at  REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS marketplace_reviews (
                    review_id   TEXT PRIMARY KEY,
                    skill_id    TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    decision    TEXT NOT NULL,
                    rationale   TEXT NOT NULL DEFAULT '',
                    reviewed_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_skill_name
                  ON marketplace_skills(name);
                CREATE INDEX IF NOT EXISTS idx_skill_status
                  ON marketplace_skills(status);
            """)
            self._conn.commit()

    def create_skill(self, s: Skill) -> Skill:
        with self._lock:
            self._conn.execute("""
                INSERT INTO marketplace_skills
                (skill_id, name, version, author_id, description, sha256,
                 signature_pubkey, status, cost_budget_usd,
                 council_session_id, created_at, approved_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (s.skill_id, s.name, s.version, s.author_id,
                  s.description, s.sha256, s.signature_pubkey,
                  s.status, s.cost_budget_usd, s.council_session_id,
                  s.created_at, s.approved_at))
            self._conn.commit()
        return s

    def get_skill(self, skill_id: str) -> Skill | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM marketplace_skills WHERE skill_id = ?",
                (skill_id,),
            ).fetchone()
        if not r:
            return None
        return self._row_to_skill(r)

    def find_by_name(self, name: str) -> list[Skill]:
        """Exact name match (anti-typosquat)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM marketplace_skills WHERE name = ?",
                (name,),
            ).fetchall()
        return [self._row_to_skill(r) for r in rows]

    def update_skill_status(
        self, skill_id: str, status: str,
        council_session_id: str | None = None,
        approved_at: float | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE marketplace_skills SET status = ?, "
                "council_session_id = COALESCE(?, council_session_id), "
                "approved_at = COALESCE(?, approved_at) "
                "WHERE skill_id = ?",
                (status, council_session_id, approved_at, skill_id),
            )
            self._conn.commit()

    # Dependencies
    def add_dependency(self, d: SkillDependency) -> SkillDependency:
        with self._lock:
            self._conn.execute("""
                INSERT INTO marketplace_dependencies
                (dep_id, skill_id, dep_name, dep_version_pin, dep_sha256)
                VALUES (?,?,?,?,?)
            """, (d.dep_id, d.skill_id, d.dep_name,
                  d.dep_version_pin, d.dep_sha256))
            self._conn.commit()
        return d

    def list_dependencies(self, skill_id: str) -> list[SkillDependency]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM marketplace_dependencies WHERE skill_id = ?",
                (skill_id,),
            ).fetchall()
        return [
            SkillDependency(
                dep_id=r["dep_id"], skill_id=r["skill_id"],
                dep_name=r["dep_name"], dep_version_pin=r["dep_version_pin"],
                dep_sha256=r["dep_sha256"],
            ) for r in rows
        ]

    # Scans
    def add_scan(self, s: SkillScanResult) -> SkillScanResult:
        with self._lock:
            self._conn.execute("""
                INSERT INTO marketplace_scans
                (scan_id, skill_id, findings, severity_max,
                 scanner_version, scanned_at)
                VALUES (?,?,?,?,?,?)
            """, (s.scan_id, s.skill_id, json.dumps(s.findings),
                  s.severity_max, s.scanner_version, s.scanned_at))
            self._conn.commit()
        return s

    def get_latest_scan(self, skill_id: str) -> SkillScanResult | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM marketplace_scans WHERE skill_id = ? "
                "ORDER BY scanned_at DESC LIMIT 1",
                (skill_id,),
            ).fetchone()
        if not r:
            return None
        return SkillScanResult(
            scan_id=r["scan_id"], skill_id=r["skill_id"],
            findings=json.loads(r["findings"]),
            severity_max=r["severity_max"],
            scanner_version=r["scanner_version"],
            scanned_at=r["scanned_at"],
        )

    # Reviews
    def add_review(self, r: SkillReview) -> SkillReview:
        with self._lock:
            self._conn.execute("""
                INSERT INTO marketplace_reviews
                (review_id, skill_id, reviewer_id, decision,
                 rationale, reviewed_at)
                VALUES (?,?,?,?,?,?)
            """, (r.review_id, r.skill_id, r.reviewer_id,
                  r.decision, r.rationale, r.reviewed_at))
            self._conn.commit()
        return r

    def health(self) -> dict:
        with self._lock:
            counts = {}
            for t in ("marketplace_skills", "marketplace_dependencies",
                      "marketplace_scans", "marketplace_reviews"):
                counts[t] = self._conn.execute(
                    f"SELECT COUNT(*) AS c FROM {t}",
                ).fetchone()["c"]
        return {"ok": True, "counts": counts, "ts": time.time()}

    @staticmethod
    def _row_to_skill(r: sqlite3.Row) -> Skill:
        return Skill(
            skill_id=r["skill_id"], name=r["name"], version=r["version"],
            author_id=r["author_id"], description=r["description"],
            sha256=r["sha256"], signature_pubkey=r["signature_pubkey"],
            status=r["status"], cost_budget_usd=r["cost_budget_usd"],
            council_session_id=r["council_session_id"],
            created_at=r["created_at"], approved_at=r["approved_at"],
        )


__all__ = ["MarketplaceStore"]
