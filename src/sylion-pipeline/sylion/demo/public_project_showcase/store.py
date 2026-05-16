"""SQLite store for portal."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from sylion.demo.public_project_showcase.models import (
    ProjectComment, PublicProject, Submission,
)


class PortalStore:
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
                CREATE TABLE IF NOT EXISTS portal_projects (
                    project_id    TEXT PRIMARY KEY,
                    owner_id      TEXT NOT NULL,
                    slug          TEXT UNIQUE NOT NULL,
                    title         TEXT NOT NULL,
                    description   TEXT NOT NULL DEFAULT '',
                    visibility    TEXT NOT NULL DEFAULT 'public',
                    metrics       TEXT NOT NULL DEFAULT '{}',
                    view_count    INTEGER NOT NULL DEFAULT 0,
                    created_at    REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portal_comments (
                    comment_id    TEXT PRIMARY KEY,
                    project_id    TEXT NOT NULL,
                    author_id     TEXT NOT NULL,
                    body          TEXT NOT NULL,
                    created_at    REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portal_submissions (
                    submission_id TEXT PRIMARY KEY,
                    project_id    TEXT,
                    submitter_email TEXT NOT NULL,
                    body          TEXT NOT NULL,
                    status        TEXT NOT NULL DEFAULT 'pending',
                    submitter_ip  TEXT NOT NULL DEFAULT '',
                    created_at    REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pp_owner ON portal_projects(owner_id);
                CREATE INDEX IF NOT EXISTS idx_pp_vis   ON portal_projects(visibility);
                CREATE INDEX IF NOT EXISTS idx_cm_proj  ON portal_comments(project_id);
                CREATE INDEX IF NOT EXISTS idx_sub_ip   ON portal_submissions(submitter_ip);
            """)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(self, p: PublicProject) -> PublicProject:
        with self._lock:
            self._conn.execute("""
                INSERT INTO portal_projects
                  (project_id, owner_id, slug, title, description,
                   visibility, metrics, view_count, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                p.project_id, p.owner_id, p.slug, p.title, p.description,
                p.visibility, json.dumps(p.metrics), p.view_count, p.created_at,
            ))
            self._conn.commit()
        return p

    def get_project(self, project_id: str) -> PublicProject | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM portal_projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return self._row_to_project(row) if row else None

    def get_by_slug(self, slug: str) -> PublicProject | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM portal_projects WHERE slug = ?", (slug,),
            ).fetchone()
        return self._row_to_project(row) if row else None

    def list_public(self, limit: int = 100) -> list[PublicProject]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM portal_projects WHERE visibility = 'public' "
                "ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def update_project(
        self, project_id: str, expected_owner: str, **fields: Any,
    ) -> PublicProject:
        """Update with ownership check (IDOR guard)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT owner_id FROM portal_projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"project not found: {project_id}")
            if row["owner_id"] != expected_owner:
                raise PermissionError(
                    f"IDOR attempt: project owned by {row['owner_id']}, "
                    f"not {expected_owner}"
                )
            allowed = ("title", "description", "visibility", "metrics")
            sets = []
            params = []
            for k, v in fields.items():
                if k not in allowed:
                    continue
                if k == "metrics":
                    v = json.dumps(v)
                sets.append(f"{k} = ?")
                params.append(v)
            if sets:
                params.append(project_id)
                self._conn.execute(
                    f"UPDATE portal_projects SET {', '.join(sets)} "
                    f"WHERE project_id = ?", params,
                )
                self._conn.commit()
        return self.get_project(project_id)

    def increment_view(self, project_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE portal_projects SET view_count = view_count + 1 "
                "WHERE project_id = ?", (project_id,),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def add_comment(self, c: ProjectComment) -> ProjectComment:
        with self._lock:
            self._conn.execute("""
                INSERT INTO portal_comments
                  (comment_id, project_id, author_id, body, created_at)
                VALUES (?,?,?,?,?)
            """, (c.comment_id, c.project_id, c.author_id,
                  c.body, c.created_at))
            self._conn.commit()
        return c

    def list_comments(self, project_id: str) -> list[ProjectComment]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM portal_comments WHERE project_id = ? "
                "ORDER BY created_at", (project_id,),
            ).fetchall()
        return [
            ProjectComment(
                comment_id=r["comment_id"],
                project_id=r["project_id"],
                author_id=r["author_id"],
                body=r["body"],
                created_at=r["created_at"],
            ) for r in rows
        ]

    # ------------------------------------------------------------------
    # Submissions (rate-limit support)
    # ------------------------------------------------------------------

    def add_submission(self, s: Submission) -> Submission:
        with self._lock:
            self._conn.execute("""
                INSERT INTO portal_submissions
                  (submission_id, project_id, submitter_email, body,
                   status, submitter_ip, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (s.submission_id, s.project_id, s.submitter_email, s.body,
                  s.status, s.submitter_ip, s.created_at))
            self._conn.commit()
        return s

    def count_submissions_from_ip(
        self, ip: str, since_ts: float,
    ) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM portal_submissions "
                "WHERE submitter_ip = ? AND created_at >= ?",
                (ip, since_ts),
            ).fetchone()
        return int(row["c"])

    # ------------------------------------------------------------------

    def health(self) -> dict:
        with self._lock:
            counts = {}
            for table in ("portal_projects", "portal_comments",
                          "portal_submissions"):
                counts[table] = self._conn.execute(
                    f"SELECT COUNT(*) AS c FROM {table}",
                ).fetchone()["c"]
        return {"ok": True, "counts": counts, "ts": time.time()}

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> PublicProject:
        return PublicProject(
            project_id=row["project_id"],
            owner_id=row["owner_id"],
            slug=row["slug"],
            title=row["title"],
            description=row["description"],
            visibility=row["visibility"],
            metrics=json.loads(row["metrics"]) if row["metrics"] else {},
            view_count=row["view_count"],
            created_at=row["created_at"],
        )


__all__ = ["PortalStore"]
