"""
SYLION Skills -- Registry with Lifecycle Management

Manages skill definitions with lifecycle states:
DRAFT -> VALIDATED -> PUBLISHED -> DEPRECATED -> RETIRED.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.skills.registry")


# ---------------------------------------------------------------------------
# Lifecycle states
# ---------------------------------------------------------------------------

VALID_LIFECYCLE_STATES = ("DRAFT", "VALIDATED", "PUBLISHED", "DEPRECATED", "RETIRED")

# Valid forward transitions
LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"VALIDATED"},
    "VALIDATED": {"PUBLISHED"},
    "PUBLISHED": {"DEPRECATED"},
    "DEPRECATED": {"RETIRED"},
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """A registered skill definition."""

    skill_id: str = ""
    name: str = ""
    domain: str = ""
    version: str = "1.0.0"
    owner_role: str = ""
    inputs: list[Any] = field(default_factory=list)
    outputs: list[Any] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)
    cost_profile: str = "zero-cost"
    lifecycle: str = "DRAFT"
    description: str = ""
    runtime_spec: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.skill_id:
            self.skill_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at


# ---------------------------------------------------------------------------
# Skills Registry
# ---------------------------------------------------------------------------

class SkillsRegistry:
    """Skills registry with lifecycle management."""

    def __init__(self, db_path: str | Path | None = None, event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                skill_id      TEXT PRIMARY KEY,
                name          TEXT    NOT NULL,
                domain        TEXT    NOT NULL DEFAULT '',
                version       TEXT    NOT NULL DEFAULT '1.0.0',
                owner_role    TEXT    NOT NULL DEFAULT '',
                inputs        TEXT    NOT NULL DEFAULT '[]',
                outputs       TEXT    NOT NULL DEFAULT '[]',
                quality_gates TEXT    NOT NULL DEFAULT '[]',
                cost_profile  TEXT    NOT NULL DEFAULT 'zero-cost',
                lifecycle     TEXT    NOT NULL DEFAULT 'DRAFT',
                description   TEXT    NOT NULL DEFAULT '',
                runtime_spec  TEXT    NOT NULL DEFAULT '{}',
                created_at    REAL    NOT NULL,
                updated_at    REAL    NOT NULL DEFAULT 0
            )
        """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_domain ON skills(domain)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_lifecycle ON skills(lifecycle)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_name ON skills(name)")

        existing_cols = {row[1] for row in self._conn.execute("PRAGMA table_info(skills)").fetchall()}
        column_defs = {
            "version": "TEXT NOT NULL DEFAULT '1.0.0'",
            "owner_role": "TEXT NOT NULL DEFAULT ''",
            "inputs": "TEXT NOT NULL DEFAULT '[]'",
            "outputs": "TEXT NOT NULL DEFAULT '[]'",
            "quality_gates": "TEXT NOT NULL DEFAULT '[]'",
            "cost_profile": "TEXT NOT NULL DEFAULT 'zero-cost'",
            "description": "TEXT NOT NULL DEFAULT ''",
            "runtime_spec": "TEXT NOT NULL DEFAULT '{}'",
            "created_at": "REAL NOT NULL DEFAULT 0",
            "updated_at": "REAL NOT NULL DEFAULT 0",
        }
        for col, ddl in column_defs.items():
            if col not in existing_cols:
                self._conn.execute(f"ALTER TABLE skills ADD COLUMN {col} {ddl}")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    def _build_runtime_spec(self, payload: dict[str, Any]) -> dict[str, Any]:
        runtime_spec = dict(payload.get("runtime_spec") or {})
        skill_id = payload.get("skill_id") or payload.get("name", "")
        name = payload.get("name") or skill_id

        runtime_spec.setdefault("skill_id", skill_id)
        runtime_spec.setdefault("name", name)
        runtime_spec.setdefault("description", payload.get("description", ""))
        runtime_spec.setdefault("version", payload.get("version", "1.0.0"))
        runtime_spec.setdefault("domain", payload.get("domain", ""))
        runtime_spec.setdefault("owner_role", payload.get("owner_role", ""))
        runtime_spec.setdefault("lifecycle", payload.get("lifecycle", "DRAFT"))
        runtime_spec.setdefault("parallel_safe", True)
        runtime_spec.setdefault("idempotent", True)
        runtime_spec.setdefault("requires_hg", False)
        runtime_spec.setdefault("inputs", payload.get("inputs", []))
        runtime_spec.setdefault("outputs", payload.get("outputs", []))
        runtime_spec.setdefault(
            "steps",
            [
                f"Load metadata for {skill_id}.",
                f"Execute {skill_id} with the provided context.",
            ],
        )
        runtime_spec.setdefault(
            "safety_rules",
            [
                "No filesystem writes unless the handler explicitly implements them.",
                "No network calls unless the handler explicitly implements them.",
            ],
        )
        return runtime_spec

    def _bootstrap_runtime(self, payload: dict[str, Any]) -> bool:
        from sylion.skills.runtime import get_skills_runtime

        runtime = get_skills_runtime(db_path=self._db_path, event_bus=self._event_bus)
        loaded = runtime.bootstrap_one(payload.get("runtime_spec", {}))
        return loaded is not None

    def register(
        self,
        skill_id: str,
        name: str,
        domain: str = "",
        owner_role: str = "",
        description: str = "",
        runtime_spec: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register a new skill in DRAFT state and sync it with runtime."""

        return self.register_skill(
            {
                "skill_id": skill_id,
                "name": name,
                "domain": domain,
                "owner_role": owner_role,
                "description": description,
                "runtime_spec": runtime_spec or {},
            },
            persist=True,
        )

    def register_skill(self, skill: Skill | dict[str, Any], persist: bool = True) -> dict[str, Any]:
        """Register a skill and immediately bootstrap it into the runtime."""

        payload = asdict(skill) if isinstance(skill, Skill) else dict(skill)
        skill_id = payload.get("skill_id") or payload.get("name")
        name = payload.get("name") or skill_id
        if not skill_id or not name:
            raise ValueError("skill_id and name required")

        now = time.time()
        skill_record = Skill(
            skill_id=skill_id,
            name=name,
            domain=payload.get("domain", ""),
            version=payload.get("version", "1.0.0"),
            owner_role=payload.get("owner_role", ""),
            inputs=list(payload.get("inputs", [])),
            outputs=list(payload.get("outputs", [])),
            quality_gates=list(payload.get("quality_gates", [])),
            cost_profile=payload.get("cost_profile", "zero-cost"),
            lifecycle=payload.get("lifecycle", "DRAFT"),
            description=payload.get("description", ""),
            runtime_spec=self._build_runtime_spec(payload),
            created_at=payload.get("created_at", now) or now,
            updated_at=payload.get("updated_at", now) or now,
        )

        if persist:
            with self._lock:
                self._conn.execute(
                    """
                    INSERT INTO skills
                        (skill_id, name, domain, version, owner_role,
                         inputs, outputs, quality_gates, cost_profile,
                         lifecycle, description, runtime_spec, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        skill_record.skill_id,
                        skill_record.name,
                        skill_record.domain,
                        skill_record.version,
                        skill_record.owner_role,
                        json.dumps(skill_record.inputs),
                        json.dumps(skill_record.outputs),
                        json.dumps(skill_record.quality_gates),
                        skill_record.cost_profile,
                        skill_record.lifecycle,
                        skill_record.description,
                        json.dumps(skill_record.runtime_spec),
                        skill_record.created_at,
                        skill_record.updated_at,
                    ),
                )
                self._conn.commit()

        try:
            loaded = self._bootstrap_runtime(asdict(skill_record))
        except Exception:
            if persist:
                with self._lock:
                    self._conn.execute("DELETE FROM skills WHERE skill_id = ?", (skill_id,))
                    self._conn.commit()
            raise

        self._emit(
            "skill.registry.registered",
            {"skill_id": skill_id, "name": name, "lifecycle": skill_record.lifecycle},
        )

        log.info("registered skill %s: %s", skill_id, name)
        return {
            "skill_id": skill_id,
            "name": name,
            "lifecycle": skill_record.lifecycle,
            "loaded_in_runtime": loaded,
        }

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def publish(self, skill_id: str) -> dict[str, Any]:
        """Transition skill: DRAFT -> VALIDATED -> PUBLISHED."""
        with self._lock:
            row = self._conn.execute("SELECT lifecycle FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()
            if not row:
                raise ValueError(f"Skill {skill_id} not found")

            current = row["lifecycle"]
            while current != "PUBLISHED":
                allowed = LIFECYCLE_TRANSITIONS.get(current, set())
                if not allowed:
                    raise ValueError(f"Cannot publish skill {skill_id} from state {current}")
                next_state = next(iter(allowed))
                now = time.time()
                self._conn.execute(
                    "UPDATE skills SET lifecycle = ?, updated_at = ? WHERE skill_id = ?",
                    (next_state, now, skill_id),
                )
                current = next_state
            self._conn.commit()

        self._emit("skill.lifecycle.changed", {"skill_id": skill_id, "lifecycle": "PUBLISHED"})
        log.info("published skill %s", skill_id)
        return {"skill_id": skill_id, "lifecycle": "PUBLISHED"}

    def deprecate(self, skill_id: str) -> dict[str, Any]:
        """Transition skill to DEPRECATED."""
        with self._lock:
            row = self._conn.execute("SELECT lifecycle FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()
            if not row:
                raise ValueError(f"Skill {skill_id} not found")

            current = row["lifecycle"]
            allowed = LIFECYCLE_TRANSITIONS.get(current, set())
            if "DEPRECATED" not in allowed:
                raise ValueError(f"Cannot deprecate skill {skill_id} from state {current}")

            now = time.time()
            self._conn.execute(
                "UPDATE skills SET lifecycle = ?, updated_at = ? WHERE skill_id = ?",
                ("DEPRECATED", now, skill_id),
            )
            self._conn.commit()

        self._emit("skill.lifecycle.changed", {"skill_id": skill_id, "lifecycle": "DEPRECATED"})
        log.info("deprecated skill %s", skill_id)
        return {"skill_id": skill_id, "lifecycle": "DEPRECATED"}

    def retire(self, skill_id: str) -> dict[str, Any]:
        """Transition skill to RETIRED."""
        with self._lock:
            row = self._conn.execute("SELECT lifecycle FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()
            if not row:
                raise ValueError(f"Skill {skill_id} not found")

            current = row["lifecycle"]
            allowed = LIFECYCLE_TRANSITIONS.get(current, set())
            if "RETIRED" not in allowed:
                raise ValueError(f"Cannot retire skill {skill_id} from state {current}")

            now = time.time()
            self._conn.execute(
                "UPDATE skills SET lifecycle = ?, updated_at = ? WHERE skill_id = ?",
                ("RETIRED", now, skill_id),
            )
            self._conn.commit()

        self._emit("skill.lifecycle.changed", {"skill_id": skill_id, "lifecycle": "RETIRED"})
        log.info("retired skill %s", skill_id)
        return {"skill_id": skill_id, "lifecycle": "RETIRED"}

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["inputs"] = json.loads(data.get("inputs", "[]"))
        data["outputs"] = json.loads(data.get("outputs", "[]"))
        data["quality_gates"] = json.loads(data.get("quality_gates", "[]"))
        data["runtime_spec"] = json.loads(data.get("runtime_spec", "{}"))
        return data

    def get(self, skill_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def list_skills(
        self,
        domain: str | None = None,
        lifecycle: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM skills WHERE 1=1"
        params: list[Any] = []
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if lifecycle:
            query += " AND lifecycle = ?"
            params.append(lifecycle)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        rows = self._conn.execute(
            "SELECT * FROM skills WHERE name LIKE ? OR description LIKE ? ORDER BY created_at DESC LIMIT ?",
            (pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_stats(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) as cnt FROM skills").fetchone()["cnt"]
        by_lifecycle_rows = self._conn.execute(
            "SELECT lifecycle, COUNT(*) as cnt FROM skills GROUP BY lifecycle"
        ).fetchall()
        by_lifecycle = {row["lifecycle"]: row["cnt"] for row in by_lifecycle_rows}
        by_domain_rows = self._conn.execute("SELECT domain, COUNT(*) as cnt FROM skills GROUP BY domain").fetchall()
        by_domain = {row["domain"]: row["cnt"] for row in by_domain_rows}
        return {
            "total_skills": total,
            "by_lifecycle": by_lifecycle,
            "by_domain": by_domain,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict[str, Any]):
        if self._event_bus:
            self._event_bus.publish(
                SylionEvent(
                    event_id="",
                    topic=topic,
                    payload=payload,
                    source_module="skills.registry",
                )
            )


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_registry: SkillsRegistry | None = None


def get_skills_registry(db_path: str | Path | None = None, event_bus: EventBus | None = None) -> SkillsRegistry:
    global _registry
    if _registry is None:
        _registry = SkillsRegistry(db_path, event_bus)
    elif db_path is not None and str(db_path) != _registry._db_path:
        _registry = SkillsRegistry(db_path, event_bus)
    return _registry


def reset_skills_registry(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> SkillsRegistry:
    global _registry
    _registry = SkillsRegistry(db_path, event_bus)
    return _registry
