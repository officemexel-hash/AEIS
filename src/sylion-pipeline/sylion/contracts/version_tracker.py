"""
SYLION Contracts -- Version Tracker

Tracks module version history with semver compatibility checks and breaking
change detection.  SQLite-backed, thread-safe, singleton pattern.

Event emissions:
  - contracts.version.registered  -- new version registered
  - contracts.version.breaking    -- breaking version detected on register
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from typing import Any

log = logging.getLogger("sylion.contracts.version_tracker")

# ---------------------------------------------------------------------------
# Semver parsing helpers
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-[A-Za-z0-9.]+)?(?:\+[A-Za-z0-9.]+)?$"
)


def parse_semver(version: str) -> tuple[int, int, int] | None:
    """Parse a semver string into (major, minor, patch).  Returns None on failure."""
    m = _SEMVER_RE.match(version.strip())
    if m is None:
        return None
    return (int(m.group("major")), int(m.group("minor")), int(m.group("patch")))


# ---------------------------------------------------------------------------
# VersionTracker
# ---------------------------------------------------------------------------

class VersionTracker:
    """Tracks module versions, history, breaking changes, and semver compatibility.

    All state lives in a SQLite table ``sylion_versions``.
    Thread-safe via a single ``threading.Lock``.
    """

    def __init__(self, db_path: str = ":memory:", event_bus: Any = None):
        self._db_path = str(db_path)
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sylion_versions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id       TEXT    NOT NULL,
                version         TEXT    NOT NULL,
                changelog       TEXT    NOT NULL DEFAULT '',
                breaking        INTEGER NOT NULL DEFAULT 0,
                registered_at   REAL    NOT NULL DEFAULT 0,
                UNIQUE(module_id, version)
            );
            CREATE INDEX IF NOT EXISTS idx_ver_module
                ON sylion_versions(module_id);
            CREATE INDEX IF NOT EXISTS idx_ver_breaking
                ON sylion_versions(module_id, breaking);
        """)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict[str, Any]):
        """Emit an event through the EventBus if available."""
        if self._event_bus is not None:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="contracts.version_tracker",
            ))

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "module_id": row["module_id"],
            "version": row["version"],
            "changelog": row["changelog"],
            "breaking": bool(row["breaking"]),
            "registered_at": row["registered_at"],
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_version(
        self,
        module_id: str,
        version: str,
        changelog: str = "",
        breaking: bool = False,
    ) -> dict[str, Any]:
        """Register a new version for *module_id*.

        Returns the registered version dict.
        Raises ``ValueError`` if the version string is not valid semver or if
        the (module_id, version) pair already exists.
        """
        parsed = parse_semver(version)
        if parsed is None:
            raise ValueError(f"Invalid semver: {version!r}")

        now = time.time()
        with self._lock:
            # Check duplicate
            existing = self._conn.execute(
                "SELECT id FROM sylion_versions WHERE module_id=? AND version=?",
                (module_id, version),
            ).fetchone()
            if existing is not None:
                raise ValueError(
                    f"Version {version!r} already registered for module {module_id!r}"
                )

            self._conn.execute(
                """INSERT INTO sylion_versions
                   (module_id, version, changelog, breaking, registered_at)
                   VALUES (?, ?, ?, ?, ?)
                """,
                (module_id, version, changelog, int(breaking), now),
            )
            self._conn.commit()

        result = {
            "module_id": module_id,
            "version": version,
            "changelog": changelog,
            "breaking": breaking,
            "registered_at": now,
        }

        self._emit("contracts.version.registered", result)
        if breaking:
            self._emit("contracts.version.breaking", result)

        return result

    def get_current_version(self, module_id: str) -> dict[str, Any] | None:
        """Return the latest registered version for *module_id*, or None."""
        with self._lock:
            row = self._conn.execute(
                """SELECT * FROM sylion_versions
                   WHERE module_id=?
                   ORDER BY registered_at DESC, id DESC
                   LIMIT 1
                """,
                (module_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_dict(row)

    def get_version_history(
        self, module_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return version history for *module_id*, most recent first."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM sylion_versions
                   WHERE module_id=?
                   ORDER BY registered_at DESC, id DESC
                   LIMIT ?
                """,
                (module_id, limit),
            ).fetchall()

        return [self._row_to_dict(r) for r in rows]

    def compare_versions(
        self, module_id: str, v1: str, v2: str
    ) -> dict[str, Any]:
        """Compare two versions of the same module.

        Returns a dict with:
          - ``v1`` and ``v2`` version strings
          - ``v1_parsed`` / ``v2_parsed`` as (major, minor, patch)
          - ``relationship``: "newer", "older", "equal", "incomparable"
          - ``major_diff``, ``minor_diff``, ``patch_diff``
        """
        p1 = parse_semver(v1)
        p2 = parse_semver(v2)

        if p1 is None or p2 is None:
            return {
                "v1": v1,
                "v2": v2,
                "v1_parsed": p1,
                "v2_parsed": p2,
                "relationship": "incomparable",
                "major_diff": None,
                "minor_diff": None,
                "patch_diff": None,
            }

        maj_d = p2[0] - p1[0]
        min_d = p2[1] - p1[1]
        pat_d = p2[2] - p1[2]

        if maj_d == 0 and min_d == 0 and pat_d == 0:
            relationship = "equal"
        elif (maj_d > 0) or (maj_d == 0 and min_d > 0) or (maj_d == 0 and min_d == 0 and pat_d > 0):
            relationship = "newer"
        else:
            relationship = "older"

        return {
            "v1": v1,
            "v2": v2,
            "v1_parsed": p1,
            "v2_parsed": p2,
            "relationship": relationship,
            "major_diff": maj_d,
            "minor_diff": min_d,
            "patch_diff": pat_d,
        }

    def is_compatible(
        self, module_id: str, from_version: str, to_version: str
    ) -> bool:
        """Check semver compatibility: compatible when major version is the same.

        Two versions are compatible when their major components are identical.
        Pre-release tags are ignored.
        """
        p_from = parse_semver(from_version)
        p_to = parse_semver(to_version)

        if p_from is None or p_to is None:
            return False

        return p_from[0] == p_to[0]

    def list_breaking_changes(
        self, module_id: str
    ) -> list[dict[str, Any]]:
        """Return all breaking version entries for *module_id*."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM sylion_versions
                   WHERE module_id=? AND breaking=1
                   ORDER BY registered_at DESC, id DESC
                """,
                (module_id,),
            ).fetchall()

        return [self._row_to_dict(r) for r in rows]

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about tracked versions."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sylion_versions"
            ).fetchone()["cnt"]

            breaking_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sylion_versions WHERE breaking=1"
            ).fetchone()["cnt"]

            by_module_rows = self._conn.execute(
                "SELECT module_id, COUNT(*) as cnt FROM sylion_versions GROUP BY module_id ORDER BY module_id"
            ).fetchall()

            breaking_by_module_rows = self._conn.execute(
                "SELECT module_id, COUNT(*) as cnt FROM sylion_versions WHERE breaking=1 GROUP BY module_id ORDER BY module_id"
            ).fetchall()

            last_registered = self._conn.execute(
                "SELECT MAX(registered_at) as t FROM sylion_versions"
            ).fetchone()["t"]

        by_module = {r["module_id"]: r["cnt"] for r in by_module_rows}
        breaking_by_module = {r["module_id"]: r["cnt"] for r in breaking_by_module_rows}

        return {
            "total_versions": total,
            "by_module": by_module,
            "breaking_change_count": breaking_count,
            "breaking_by_module": breaking_by_module,
            "last_registered_time": last_registered,
        }

    def close(self):
        """Close the database connection."""
        self._conn.close()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_tracker: VersionTracker | None = None


def get_version_tracker(
    db_path: str = ":memory:", event_bus: Any = None
) -> VersionTracker:
    """Return the global VersionTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = VersionTracker(db_path=db_path, event_bus=event_bus)
    return _tracker
