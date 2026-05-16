"""
SYLION Core -- Version Manager

Tracks module versions with dependency graphs, changelogs, and comparison.

Tables:
  versions             -- module version records with spec and deprecation flag
  version_dependencies -- directed edges between versions (dep_type: requires|provides|conflicts)
  version_changelog    -- append-only changelog entries per version

Events:
  version_created      -- emitted when create_version() registers a new version
  version_deprecated   -- emitted when deprecate_version() marks a version deprecated
  dependency_added     -- emitted when add_dependency() links two versions

Singleton: get_version_manager() / reset_version_manager()
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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.core.version_manager")

VALID_DEP_TYPES = ("requires", "provides", "conflicts")


class VersionManager:
    """Tracks module versions with dependency graphs. SQLite-backed. Thread-safe."""

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS versions (
                version_id   TEXT PRIMARY KEY,
                module_id    TEXT NOT NULL,
                version      TEXT NOT NULL,
                spec_json    TEXT NOT NULL DEFAULT '{}',
                is_active    INTEGER NOT NULL DEFAULT 1,
                deprecated   INTEGER NOT NULL DEFAULT 0,
                created_at   REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS version_dependencies (
                dep_id                TEXT PRIMARY KEY,
                version_id            TEXT NOT NULL,
                depends_on_version_id TEXT NOT NULL,
                dep_type              TEXT NOT NULL DEFAULT 'requires',
                created_at            REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS version_changelog (
                changelog_id TEXT PRIMARY KEY,
                version_id   TEXT NOT NULL,
                message      TEXT NOT NULL,
                created_at   REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_versions_module ON versions(module_id);
            CREATE INDEX IF NOT EXISTS idx_versions_active ON versions(is_active);
            CREATE INDEX IF NOT EXISTS idx_versions_deprecated ON versions(deprecated);
            CREATE INDEX IF NOT EXISTS idx_vdep_version ON version_dependencies(version_id);
            CREATE INDEX IF NOT EXISTS idx_vdep_depends ON version_dependencies(depends_on_version_id);
            CREATE INDEX IF NOT EXISTS idx_vch_version ON version_changelog(version_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="core.version_manager",
            ))

    # ------------------------------------------------------------------
    # Version CRUD
    # ------------------------------------------------------------------

    def create_version(self, module_id: str, version: str,
                       spec_json: dict | str | None = None,
                       changelog: str | None = None) -> dict:
        """Register a new version for a module. Returns the version record."""
        if not module_id or not version:
            raise ValueError("module_id and version must be non-empty")

        vid = self._uid()
        now = time.time()

        if spec_json is None:
            spec = {}
        elif isinstance(spec_json, str):
            spec = json.loads(spec_json)
        else:
            spec = spec_json
        spec_str = json.dumps(spec, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO versions (version_id, module_id, version, spec_json, is_active, deprecated, created_at)
                VALUES (?, ?, ?, ?, 1, 0, ?)
            """, (vid, module_id, version, spec_str, now))

            if changelog:
                cid = self._uid()
                self._conn.execute("""
                    INSERT INTO version_changelog (changelog_id, version_id, message, created_at)
                    VALUES (?, ?, ?, ?)
                """, (cid, vid, changelog, now))

            self._conn.commit()

        log.info("created version %s for %s@%s", vid, module_id, version)
        self._emit("version_created", {
            "version_id": vid, "module_id": module_id, "version": version,
        })
        return {
            "version_id": vid, "module_id": module_id, "version": version,
            "spec_json": spec, "is_active": True, "deprecated": False,
            "created_at": now,
        }

    def get_version(self, version_id: str) -> dict | None:
        """Retrieve a version by ID. Returns dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM versions WHERE version_id = ?", (version_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["spec_json"] = json.loads(d["spec_json"])
        except (json.JSONDecodeError, TypeError):
            pass
        d["is_active"] = bool(d["is_active"])
        d["deprecated"] = bool(d["deprecated"])
        return d

    def list_versions(self, module_id: str | None = None,
                      active_only: bool = False,
                      limit: int = 500) -> list[dict]:
        """List versions with optional filters."""
        q = "SELECT * FROM versions WHERE 1=1"
        params: list[Any] = []
        if module_id:
            q += " AND module_id = ?"
            params.append(module_id)
        if active_only:
            q += " AND is_active = 1 AND deprecated = 0"
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            try:
                d["spec_json"] = json.loads(d["spec_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            d["is_active"] = bool(d["is_active"])
            d["deprecated"] = bool(d["deprecated"])
            results.append(d)
        return results

    def get_history(self, module_id: str | None = None,
                    change_type: str | None = None,
                    limit: int = 50) -> list[dict]:
        """Return a chronological change-log of version events.

        Each version row contributes a 'created' event; if deprecated=1
        it also contributes a 'deprecated' event. Optional filters:
        module_id (exact match), change_type ('created' or 'deprecated').

        Workspace-plane shim added 2026-04-25 (split-plane gap surfaced
        by Step 0c probe -- core_routes.py:361 called this method).
        """
        with self._lock:
            q = "SELECT * FROM versions"
            params: list[Any] = []
            if module_id:
                q += " WHERE module_id = ?"
                params.append(module_id)
            q += " ORDER BY created_at DESC"
            rows = self._conn.execute(q, params).fetchall()

        events: list[dict] = []
        for r in rows:
            d = dict(r)
            base = {
                "version_id": d["version_id"],
                "module_id": d["module_id"],
                "version": d["version"],
                "at": d["created_at"],
            }
            if change_type in (None, "created"):
                events.append({**base, "change_type": "created"})
            if d["deprecated"] and change_type in (None, "deprecated"):
                events.append({**base, "change_type": "deprecated"})

        events.sort(key=lambda e: e["at"], reverse=True)
        return events[:limit]

    def get_latest(self, module_id: str) -> dict | None:
        """Get the most recent active, non-deprecated version for a module."""
        with self._lock:
            row = self._conn.execute("""
                SELECT * FROM versions
                WHERE module_id = ? AND is_active = 1 AND deprecated = 0
                ORDER BY created_at DESC LIMIT 1
            """, (module_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["spec_json"] = json.loads(d["spec_json"])
        except (json.JSONDecodeError, TypeError):
            pass
        d["is_active"] = bool(d["is_active"])
        d["deprecated"] = bool(d["deprecated"])
        return d

    def get_current_version(self, module_id: str) -> dict | None:
        """Workspace alias for ``get_latest``."""
        return self.get_latest(module_id)

    def deprecate_version(self, version_id: str) -> bool:
        """Mark a version as deprecated. Returns True if found."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE versions SET deprecated = 1 WHERE version_id = ?",
                (version_id,),
            ).rowcount
            self._conn.commit()
        if n:
            log.info("deprecated version %s", version_id)
            self._emit("version_deprecated", {"version_id": version_id})
        return bool(n)

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def add_dependency(self, version_id: str, depends_on_version_id: str,
                       dep_type: str = "requires") -> dict:
        """Create a dependency edge between two versions."""
        if dep_type not in VALID_DEP_TYPES:
            raise ValueError(
                f"Invalid dep_type '{dep_type}'. Must be one of {VALID_DEP_TYPES}"
            )
        dep_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO version_dependencies
                    (dep_id, version_id, depends_on_version_id, dep_type, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (dep_id, version_id, depends_on_version_id, dep_type, now))
            self._conn.commit()

        log.info("added dependency %s -> %s (%s)", version_id, depends_on_version_id, dep_type)
        self._emit("dependency_added", {
            "dep_id": dep_id, "version_id": version_id,
            "depends_on_version_id": depends_on_version_id, "dep_type": dep_type,
        })
        return {
            "dep_id": dep_id, "version_id": version_id,
            "depends_on_version_id": depends_on_version_id,
            "dep_type": dep_type, "created_at": now,
        }

    def get_dependencies(self, version_id: str) -> list[dict]:
        """Get all dependencies for a given version."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM version_dependencies WHERE version_id = ? ORDER BY created_at",
                (version_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare_versions(self, v1_id: str, v2_id: str) -> dict:
        """Compare two versions. Returns differences and dependency overlaps."""
        v1 = self.get_version(v1_id)
        v2 = self.get_version(v2_id)
        if not v1 or not v2:
            return {"error": "One or both versions not found", "v1": v1, "v2": v2}

        v1_deps = {d["depends_on_version_id"]: d["dep_type"]
                   for d in self.get_dependencies(v1_id)}
        v2_deps = {d["depends_on_version_id"]: d["dep_type"]
                   for d in self.get_dependencies(v2_id)}

        common = set(v1_deps.keys()) & set(v2_deps.keys())
        only_v1 = set(v1_deps.keys()) - set(v2_deps.keys())
        only_v2 = set(v2_deps.keys()) - set(v1_deps.keys())

        same_module = v1["module_id"] == v2["module_id"]

        return {
            "same_module": same_module,
            "v1_module": v1["module_id"], "v1_version": v1["version"],
            "v2_module": v2["module_id"], "v2_version": v2["version"],
            "common_deps": sorted(common),
            "only_v1_deps": sorted(only_v1),
            "only_v2_deps": sorted(only_v2),
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_version_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM versions"
            ).fetchone()["cnt"]
            active = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM versions WHERE is_active = 1 AND deprecated = 0"
            ).fetchone()["cnt"]
            deprecated = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM versions WHERE deprecated = 1"
            ).fetchone()["cnt"]
            dep_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM version_dependencies"
            ).fetchone()["cnt"]
            changelog_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM version_changelog"
            ).fetchone()["cnt"]
            modules = self._conn.execute(
                "SELECT COUNT(DISTINCT module_id) as cnt FROM versions"
            ).fetchone()["cnt"]

        return {
            "total_versions": total,
            "active_versions": active,
            "deprecated_versions": deprecated,
            "total_dependencies": dep_count,
            "changelog_entries": changelog_count,
            "distinct_modules": modules,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: VersionManager | None = None


def get_version_manager(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> VersionManager:
    global _manager
    if _manager is None:
        _manager = VersionManager(db_path, event_bus)
    return _manager


def reset_version_manager() -> None:
    global _manager
    _manager = None
