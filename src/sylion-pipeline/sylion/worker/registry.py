"""
SYLION Worker -- Registry & Assignment Store

Manages worker fleet, assignments, and build topology.
SQLite-backed. Thread-safe. Emits events via EventBus.
Scalable: designed for Postgres migration path (UUID keys, JSONB columns, WAL).

Tables:
  worker_registry      – fleet of build workers (local VMs, VPS, bare metal)
  worker_assignments   – module assignments per worker with lifecycle
  build_topology       – deployment topology configurations
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

log = logging.getLogger("sylion.worker.registry")

VALID_WORKER_STATES = ("active", "inactive", "offline", "draining")
VALID_ASSIGNMENT_STATES = (
    "pending", "assigned", "in_progress", "completed",
    "failed", "blocked", "rejected", "rollback",
)


class WorkerRegistry:
    """Thread-safe SQLite-backed registry for distributed build workers."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
    ):
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
            CREATE TABLE IF NOT EXISTS worker_registry (
                worker_id         TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                host              TEXT NOT NULL DEFAULT 'localhost',
                status            TEXT NOT NULL DEFAULT 'active',
                capacity          INTEGER NOT NULL DEFAULT 3,
                api_key_hash      TEXT NOT NULL DEFAULT '',
                budget_limit      REAL NOT NULL DEFAULT 0.0,
                budget_spent      REAL NOT NULL DEFAULT 0.0,
                token_usage       INTEGER NOT NULL DEFAULT 0,
                last_heartbeat    REAL,
                assigned_modules  TEXT NOT NULL DEFAULT '[]',
                tags              TEXT NOT NULL DEFAULT '[]',
                metadata_json     TEXT NOT NULL DEFAULT '{}',
                created_at        REAL NOT NULL,
                updated_at        REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_worker_status ON worker_registry(status);
            CREATE INDEX IF NOT EXISTS idx_worker_host   ON worker_registry(host);

            CREATE TABLE IF NOT EXISTS worker_assignments (
                assignment_id     TEXT PRIMARY KEY,
                worker_id         TEXT NOT NULL,
                module_id         TEXT NOT NULL,
                status            TEXT NOT NULL DEFAULT 'pending',
                priority          INTEGER NOT NULL DEFAULT 5,
                patch_proposal    TEXT,
                evidence_pack     TEXT,
                started_at        REAL,
                completed_at      REAL,
                error_log         TEXT,
                metadata_json     TEXT NOT NULL DEFAULT '{}',
                created_at        REAL NOT NULL,
                updated_at        REAL NOT NULL,
                FOREIGN KEY (worker_id) REFERENCES worker_registry(worker_id)
            );
            CREATE INDEX IF NOT EXISTS idx_asgn_worker   ON worker_assignments(worker_id);
            CREATE INDEX IF NOT EXISTS idx_asgn_module   ON worker_assignments(module_id);
            CREATE INDEX IF NOT EXISTS idx_asgn_status   ON worker_assignments(status);

            CREATE TABLE IF NOT EXISTS build_topology (
                topology_id       TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                description       TEXT NOT NULL DEFAULT '',
                config_json       TEXT NOT NULL DEFAULT '{}',
                status            TEXT NOT NULL DEFAULT 'draft',
                created_at        REAL NOT NULL,
                updated_at        REAL NOT NULL
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Emit helper
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict[str, Any]):
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(
                SylionEvent(
                    event_id="",
                    topic=topic,
                    payload=payload,
                    source_module="core.worker",
                )
            )
        except Exception as exc:
            log.warning("EventBus publish failed: %s", exc)

    # ------------------------------------------------------------------
    # Worker CRUD
    # ------------------------------------------------------------------

    def register_worker(
        self,
        name: str,
        host: str = "localhost",
        capacity: int = 3,
        api_key_hash: str = "",
        budget_limit: float = 0.0,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        worker_id = f"wk_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO worker_registry
                (worker_id, name, host, status, capacity, api_key_hash,
                 budget_limit, budget_spent, token_usage, last_heartbeat,
                 assigned_modules, tags, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    worker_id, name, host, "active", capacity, api_key_hash,
                    budget_limit, 0.0, 0, now,
                    json.dumps([]),
                    json.dumps(tags or []),
                    json.dumps(metadata or {}),
                    now, now,
                ),
            )
            self._conn.commit()
        self._emit(
            "worker.registered",
            {"worker_id": worker_id, "name": name, "host": host, "capacity": capacity},
        )
        return self.get_worker(worker_id)

    def get_worker(self, worker_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM worker_registry WHERE worker_id = ?", (worker_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_worker(row)

    def list_workers(
        self, status: str | None = None, host: str | None = None
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if host:
            where.append("host = ?")
            params.append(host)
        sql = "SELECT * FROM worker_registry"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_worker(r) for r in rows]

    def update_worker(
        self, worker_id: str, **fields: Any
    ) -> dict[str, Any] | None:
        allowed = {
            "name", "host", "status", "capacity", "api_key_hash",
            "budget_limit", "budget_spent", "token_usage",
            "assigned_modules", "tags", "metadata_json",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_worker(worker_id)
        updates["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [worker_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE worker_registry SET {cols} WHERE worker_id = ?", vals
            )
            self._conn.commit()
        self._emit("worker.updated", {"worker_id": worker_id, "fields": list(updates.keys())})
        return self.get_worker(worker_id)

    def unregister_worker(self, worker_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM worker_registry WHERE worker_id = ?", (worker_id,)
            )
            self._conn.commit()
        if cur.rowcount:
            self._emit("worker.unregistered", {"worker_id": worker_id})
            return True
        return False

    def unregister_orphaned(
        self,
        project_id: str,
        kept_worker_ids: list[str] | set[str],
    ) -> int:
        """Wave A4 (RB-002): unregister project workers no longer in plan.

        Walks the registry for workers whose `metadata.project_id` matches and
        whose `worker_id` is NOT in `kept_worker_ids`. Each such worker is
        unregistered (DELETE) and a `worker.unregistered` event is emitted.
        Returns the count of workers removed.

        Workers without a `metadata.project_id` (i.e. fleet-level / unassigned)
        are left alone — orphan detection is project-scoped.
        """
        kept = set(kept_worker_ids)
        with self._lock:
            rows = self._conn.execute(
                "SELECT worker_id, metadata_json FROM worker_registry"
            ).fetchall()
        removed = 0
        for row in rows:
            try:
                meta = json.loads(row["metadata_json"] or "{}")
            except (TypeError, ValueError):
                meta = {}
            if meta.get("project_id") != project_id:
                continue
            if row["worker_id"] in kept:
                continue
            if self.unregister_worker(row["worker_id"]):
                removed += 1
        return removed

    def heartbeat(self, worker_id: str, load: dict[str, Any] | None = None) -> bool:
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE worker_registry SET last_heartbeat = ?, updated_at = ? WHERE worker_id = ?",
                (now, now, worker_id),
            )
            self._conn.commit()
        if cur.rowcount:
            self._emit("worker.heartbeat", {"worker_id": worker_id, "timestamp": now, "load": load})
            return True
        return False

    # ------------------------------------------------------------------
    # Assignment CRUD
    # ------------------------------------------------------------------

    def create_assignment(
        self,
        worker_id: str,
        module_id: str,
        priority: int = 5,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assignment_id = f"asg_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO worker_assignments
                (assignment_id, worker_id, module_id, status, priority,
                 metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assignment_id, worker_id, module_id, "assigned", priority,
                    json.dumps(metadata or {}), now, now,
                ),
            )
            self._conn.commit()
            self._sync_assigned_modules(worker_id)
        self._emit(
            "assignment.created",
            {"assignment_id": assignment_id, "worker_id": worker_id, "module_id": module_id},
        )
        return self.get_assignment(assignment_id)

    def get_assignment(self, assignment_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM worker_assignments WHERE assignment_id = ?", (assignment_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_assignment(row)

    def list_assignments(
        self,
        worker_id: str | None = None,
        module_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if worker_id:
            where.append("worker_id = ?")
            params.append(worker_id)
        if module_id:
            where.append("module_id = ?")
            params.append(module_id)
        if status:
            where.append("status = ?")
            params.append(status)
        sql = "SELECT * FROM worker_assignments"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY priority ASC, created_at ASC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_assignment(r) for r in rows]

    def update_assignment(
        self, assignment_id: str, **fields: Any
    ) -> dict[str, Any] | None:
        allowed = {
            "status", "priority", "patch_proposal", "evidence_pack",
            "started_at", "completed_at", "error_log", "metadata_json",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_assignment(assignment_id)
        updates["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [assignment_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE worker_assignments SET {cols} WHERE assignment_id = ?", vals
            )
            self._conn.commit()
        asg = self.get_assignment(assignment_id)
        if asg:
            self._sync_assigned_modules(asg["worker_id"])
            self._emit("assignment.updated", {"assignment_id": assignment_id, "fields": list(updates.keys())})
        return asg

    def delete_assignment(self, assignment_id: str) -> bool:
        asg = self.get_assignment(assignment_id)
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM worker_assignments WHERE assignment_id = ?", (assignment_id,)
            )
            self._conn.commit()
        if cur.rowcount and asg:
            self._sync_assigned_modules(asg["worker_id"])
            self._emit("assignment.deleted", {"assignment_id": assignment_id})
            return True
        return False

    def submit_patch_proposal(
        self, assignment_id: str, patch_content: str, evidence_pack: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        now = time.time()
        return self.update_assignment(
            assignment_id,
            status="completed",
            patch_proposal=patch_content,
            evidence_pack=json.dumps(evidence_pack or {}),
            completed_at=now,
        )

    # ------------------------------------------------------------------
    # Topology CRUD
    # ------------------------------------------------------------------

    def create_topology(
        self, name: str, description: str = "", config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        topology_id = f"top_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO build_topology
                (topology_id, name, description, config_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (topology_id, name, description, json.dumps(config or {}), "draft", now, now),
            )
            self._conn.commit()
        self._emit("topology.created", {"topology_id": topology_id, "name": name})
        return self.get_topology(topology_id)

    def get_topology(self, topology_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM build_topology WHERE topology_id = ?", (topology_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_topology(row)

    def list_topologies(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM build_topology ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_topology(r) for r in rows]

    def update_topology(self, topology_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"name", "description", "config_json", "status"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_topology(topology_id)
        if "config_json" in updates and not isinstance(updates["config_json"], str):
            updates["config_json"] = json.dumps(updates["config_json"])
        updates["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [topology_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE build_topology SET {cols} WHERE topology_id = ?", vals
            )
            self._conn.commit()
        return self.get_topology(topology_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sync_assigned_modules(self, worker_id: str):
        with self._lock:
            rows = self._conn.execute(
                "SELECT module_id FROM worker_assignments WHERE worker_id = ? AND status IN ('assigned','in_progress')",
                (worker_id,),
            ).fetchall()
            modules = [r[0] for r in rows]
            self._conn.execute(
                "UPDATE worker_registry SET assigned_modules = ?, updated_at = ? WHERE worker_id = ?",
                (json.dumps(modules), time.time(), worker_id),
            )
            self._conn.commit()

    def _row_to_worker(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "worker_id": row["worker_id"],
            "name": row["name"],
            "host": row["host"],
            "status": row["status"],
            "capacity": row["capacity"],
            "api_key_hash": row["api_key_hash"],
            "budget_limit": row["budget_limit"],
            "budget_spent": row["budget_spent"],
            "token_usage": row["token_usage"],
            "last_heartbeat": row["last_heartbeat"],
            "assigned_modules": json.loads(row["assigned_modules"]),
            "tags": json.loads(row["tags"]),
            "metadata": json.loads(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_assignment(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "assignment_id": row["assignment_id"],
            "worker_id": row["worker_id"],
            "module_id": row["module_id"],
            "status": row["status"],
            "priority": row["priority"],
            "patch_proposal": row["patch_proposal"],
            "evidence_pack": json.loads(row["evidence_pack"]) if row["evidence_pack"] else None,
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "error_log": row["error_log"],
            "metadata": json.loads(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_topology(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "topology_id": row["topology_id"],
            "name": row["name"],
            "description": row["description"],
            "config": json.loads(row["config_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_registry_instance: WorkerRegistry | None = None


def get_worker_registry(db_path: str | Path | None = None, event_bus: EventBus | None = None) -> WorkerRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = WorkerRegistry(db_path, event_bus)
    return _registry_instance


def reset_worker_registry():
    global _registry_instance
    _registry_instance = None
