"""W14 TestingMemoryStore — lessons learned + cross-project pattern matching.

Per docs/CLAUDE_AEIS_W14_TESTING.md sec 29 (Cross-project pattern reuse).

Records:
  - lessons: per-project takeaways with anti-pattern tags
  - root_causes: classified causes from LoopReports
  - flaky_patterns: tests that flap and why
  - anti_patterns: catalog of known bad patterns ("ap_001", etc.)

Provides similarity lookup for new projects ("if you fail X you'll likely fail Y").
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.aeis.testing.memory")


class TestingMemoryStore:
    """Persisted store of W14 lessons + cross-project patterns."""

    __test__ = False  # pytest: do not collect (name starts with "Test")

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
                CREATE TABLE IF NOT EXISTS w14_lessons (
                    lesson_id    TEXT PRIMARY KEY,
                    project_id   TEXT NOT NULL,
                    release_id   TEXT NOT NULL DEFAULT '',
                    pattern_type TEXT NOT NULL,
                    context      TEXT NOT NULL DEFAULT '{}',
                    detection    TEXT NOT NULL DEFAULT '{}',
                    resolution   TEXT NOT NULL DEFAULT '{}',
                    generalization TEXT NOT NULL DEFAULT '{}',
                    created_at   REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS w14_root_causes (
                    cause_id     TEXT PRIMARY KEY,
                    finding_id   TEXT NOT NULL,
                    cause_class  TEXT NOT NULL,
                    description  TEXT NOT NULL DEFAULT '',
                    confidence   REAL NOT NULL DEFAULT 0.5,
                    created_at   REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS w14_flaky_patterns (
                    pattern_id   TEXT PRIMARY KEY,
                    test_id      TEXT NOT NULL,
                    fail_rate    REAL NOT NULL DEFAULT 0.0,
                    fail_modes   TEXT NOT NULL DEFAULT '[]',
                    runs_total   INTEGER NOT NULL DEFAULT 0,
                    runs_failed  INTEGER NOT NULL DEFAULT 0,
                    created_at   REAL NOT NULL,
                    updated_at   REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS w14_anti_patterns (
                    ap_id              TEXT PRIMARY KEY,
                    name               TEXT NOT NULL,
                    severity           TEXT NOT NULL DEFAULT 'D3',
                    detected_in_count  INTEGER NOT NULL DEFAULT 1,
                    detection_rule     TEXT NOT NULL DEFAULT '',
                    prevention         TEXT NOT NULL DEFAULT '',
                    created_at         REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_lessons_project ON w14_lessons(project_id);
                CREATE INDEX IF NOT EXISTS idx_lessons_pattern ON w14_lessons(pattern_type);
                CREATE INDEX IF NOT EXISTS idx_rc_finding     ON w14_root_causes(finding_id);
                CREATE INDEX IF NOT EXISTS idx_flaky_test     ON w14_flaky_patterns(test_id);
            """)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Lessons
    # ------------------------------------------------------------------

    def record_lesson(
        self, project_id: str, release_id: str,
        pattern_type: str, context: dict, detection: dict,
        resolution: dict, generalization: dict | None = None,
    ) -> str:
        lesson_id = f"lesson_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._conn.execute("""
                INSERT INTO w14_lessons
                  (lesson_id, project_id, release_id, pattern_type,
                   context, detection, resolution, generalization, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                lesson_id, project_id, release_id, pattern_type,
                json.dumps(context), json.dumps(detection),
                json.dumps(resolution),
                json.dumps(generalization or {}),
                time.time(),
            ))
            self._conn.commit()
        log.info("lesson recorded: %s (project=%s, pattern=%s)",
                 lesson_id[:12], project_id, pattern_type)
        return lesson_id

    def list_lessons(self, project_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM w14_lessons"
        params: tuple[Any, ...] = ()
        if project_id:
            sql += " WHERE project_id = ?"
            params = (project_id,)
        sql += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._lesson_row(r) for r in rows]

    def list_lessons_similar_to(
        self, project_type: str, limit: int = 10,
    ) -> list[dict]:
        """Find lessons from projects with matching pattern_type or context.

        Simple similarity by pattern_type prefix or context.project_type.
        SQLite LIKE wildcards `%` and `_` in user input are escaped
        (Kimi-class hardening) so a hostile project_type cannot turn
        the substring search into a wildcard scan over every row.
        """
        if not isinstance(project_type, str) or not project_type:
            return []
        if not isinstance(limit, int) or limit <= 0:
            limit = 10
        # Escape LIKE wildcards: %, _, and \ (the escape char itself).
        escaped = (
            project_type.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        like_pattern = f"%{escaped}%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM w14_lessons "
                "WHERE pattern_type LIKE ? ESCAPE '\\' "
                "   OR context LIKE ? ESCAPE '\\' "
                "ORDER BY created_at DESC LIMIT ?",
                (like_pattern, like_pattern, min(limit, 1000)),
            ).fetchall()
        return [self._lesson_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Root causes
    # ------------------------------------------------------------------

    def record_root_cause(
        self, finding_id: str, cause_class: str,
        description: str = "", confidence: float = 0.5,
    ) -> str:
        cause_id = f"rc_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._conn.execute("""
                INSERT INTO w14_root_causes
                  (cause_id, finding_id, cause_class, description,
                   confidence, created_at)
                VALUES (?,?,?,?,?,?)
            """, (cause_id, finding_id, cause_class, description,
                  confidence, time.time()))
            self._conn.commit()
        return cause_id

    def list_root_causes(self, finding_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM w14_root_causes"
        params: tuple[Any, ...] = ()
        if finding_id:
            sql += " WHERE finding_id = ?"
            params = (finding_id,)
        sql += " ORDER BY confidence DESC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Flaky patterns
    # ------------------------------------------------------------------

    def record_flaky(
        self, test_id: str, fail_modes: list[str],
        runs_total: int, runs_failed: int,
    ) -> str:
        pattern_id = f"flaky_{uuid.uuid4().hex[:12]}"
        rate = runs_failed / runs_total if runs_total else 0.0
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO w14_flaky_patterns
                  (pattern_id, test_id, fail_rate, fail_modes,
                   runs_total, runs_failed, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (pattern_id, test_id, rate, json.dumps(fail_modes),
                  runs_total, runs_failed, now, now))
            self._conn.commit()
        return pattern_id

    def list_flaky(self, min_fail_rate: float = 0.05) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM w14_flaky_patterns WHERE fail_rate >= ? "
                "ORDER BY fail_rate DESC",
                (min_fail_rate,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Anti-patterns catalog
    # ------------------------------------------------------------------

    def add_anti_pattern(
        self, name: str, severity: str = "D3",
        detection_rule: str = "", prevention: str = "",
    ) -> str:
        ap_id = f"ap_{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._conn.execute("""
                INSERT INTO w14_anti_patterns
                  (ap_id, name, severity, detected_in_count,
                   detection_rule, prevention, created_at)
                VALUES (?,?,?,1,?,?,?)
            """, (ap_id, name, severity, detection_rule, prevention, time.time()))
            self._conn.commit()
        return ap_id

    def increment_anti_pattern(self, name: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE w14_anti_patterns SET detected_in_count = detected_in_count + 1 "
                "WHERE name = ?",
                (name,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_anti_patterns(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM w14_anti_patterns ORDER BY detected_in_count DESC",
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> dict:
        with self._lock:
            counts = {}
            for table in ("w14_lessons", "w14_root_causes",
                          "w14_flaky_patterns", "w14_anti_patterns"):
                cnt = self._conn.execute(
                    f"SELECT COUNT(*) as c FROM {table}",
                ).fetchone()["c"]
                counts[table] = cnt
        return {"ok": True, "counts": counts, "ts": time.time()}

    @staticmethod
    def _lesson_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        for f in ("context", "detection", "resolution", "generalization"):
            try:
                d[f] = json.loads(d[f])
            except (json.JSONDecodeError, TypeError):
                pass
        return d


    # ------------------------------------------------------------------
    # C9 contract aliases — accept the 2/3-arg signatures from
    # docs/w14_workplan/W14_INTEGRATION_CONTRACTS.md while keeping the
    # richer internal record_* methods available to callers that need
    # the full payload split.
    # ------------------------------------------------------------------

    def record_lesson_c9(
        self, project_id: str, release_id: str, lesson: dict,
    ) -> str:
        """C9 surface: ``record_lesson(project_id, release_id, lesson)``.

        The lesson dict may contain ``pattern_type``, ``context``,
        ``detection``, ``resolution``, ``generalization``; any subset is
        accepted (sane defaults for missing parts).
        """
        if not isinstance(lesson, dict):
            raise ValueError("lesson must be a dict")
        return self.record_lesson(
            project_id=project_id,
            release_id=release_id,
            pattern_type=str(lesson.get("pattern_type", "general")),
            context=dict(lesson.get("context") or {}),
            detection=dict(lesson.get("detection") or {}),
            resolution=dict(lesson.get("resolution") or {}),
            generalization=dict(lesson.get("generalization") or {}),
        )

    def record_root_cause_c9(self, finding_id: str, root_cause: dict) -> str:
        """C9 surface: ``record_root_cause(finding_id, root_cause)``."""
        if not isinstance(root_cause, dict):
            raise ValueError("root_cause must be a dict")
        return self.record_root_cause(
            finding_id=finding_id,
            cause_class=str(root_cause.get("cause_class", "unknown")),
            description=str(root_cause.get("description", "")),
            confidence=float(root_cause.get("confidence", 0.5)),
        )

    def record_flaky_pattern(self, test_id: str, pattern: dict) -> str:
        """C9 surface: ``record_flaky_pattern(test_id, pattern)``."""
        if not isinstance(pattern, dict):
            raise ValueError("pattern must be a dict")
        return self.record_flaky(
            test_id=test_id,
            fail_modes=list(pattern.get("fail_modes") or []),
            runs_total=int(pattern.get("runs_total") or 0),
            runs_failed=int(pattern.get("runs_failed") or 0),
        )


__all__ = ["TestingMemoryStore"]
