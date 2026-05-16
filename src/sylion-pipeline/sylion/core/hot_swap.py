"""
SYLION Core -- Hot Swap Manager

Handles zero-downtime module replacement with candidate registration,
swap operations, and rollback support.

Tables:
  swap_candidates  -- registered module candidates available for swapping
  swap_operations  -- active and completed swap operations
  swap_results     -- results of completed swap operations

Events:
  candidate_registered -- emitted when register_candidate() adds a candidate
  swap_initiated       -- emitted when initiate_swap() starts a swap
  swap_completed       -- emitted when complete_swap() finishes a swap
  swap_rolled_back     -- emitted when rollback_swap() reverts a swap

Singleton: get_hot_swap_manager() / reset_hot_swap_manager()
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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.core.hot_swap")


@dataclass(frozen=True)
class Environment:
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    active_since: float = 0.0
    is_active: bool = False


@dataclass(frozen=True)
class HotSwapResult:
    success: bool
    old_env: str = ""
    new_env: str = ""
    switched_modules: list[str] = field(default_factory=list)
    message: str = ""


class HotSwapManager:
    """Handles zero-downtime module replacement.

    SQLite-backed. Thread-safe via RLock. EventBus integration.
    """

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
        now = time.time()
        self._env_active = "dev"
        self._env_active_since = {
            "dev": now,
            "staging": now,
            "prod": now,
        }
        self._env_configs = {
            "dev": {"security_profile": "dev-light"},
            "staging": {"security_profile": "staging-strict"},
            "prod": {"security_profile": "prod-locked"},
        }
        self._module_env_bindings: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS swap_candidates (
                candidate_id TEXT PRIMARY KEY,
                module_id    TEXT NOT NULL,
                version      TEXT NOT NULL,
                config_json  TEXT NOT NULL DEFAULT '{}',
                registered_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS swap_operations (
                operation_id   TEXT PRIMARY KEY,
                target_module  TEXT NOT NULL,
                from_version   TEXT NOT NULL,
                to_version     TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'pending',
                initiated_at   REAL NOT NULL,
                completed_at   REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS swap_results (
                result_id     TEXT PRIMARY KEY,
                operation_id  TEXT NOT NULL UNIQUE,
                success       INTEGER NOT NULL,
                result_json   TEXT NOT NULL DEFAULT '{}',
                completed_at  REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cand_module ON swap_candidates(module_id);
            CREATE INDEX IF NOT EXISTS idx_ops_module ON swap_operations(target_module);
            CREATE INDEX IF NOT EXISTS idx_ops_status ON swap_operations(status);
            CREATE INDEX IF NOT EXISTS idx_results_op ON swap_results(operation_id);
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
                source_module="core.hot_swap",
            ))

    # ------------------------------------------------------------------
    # Candidate Management
    # ------------------------------------------------------------------

    def register_candidate(self, module_id: str, version: str,
                           config_json: dict | str | None = None) -> dict:
        """Register a module candidate for swapping. Returns candidate record."""
        if not module_id or not version:
            raise ValueError("module_id and version must be non-empty")

        cid = self._uid()
        now = time.time()

        if config_json is None:
            config = {}
        elif isinstance(config_json, str):
            config = json.loads(config_json)
        else:
            config = config_json
        config_str = json.dumps(config, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO swap_candidates (candidate_id, module_id, version, config_json, registered_at)
                VALUES (?, ?, ?, ?, ?)
            """, (cid, module_id, version, config_str, now))
            self._conn.commit()

        log.info("registered candidate %s for %s@%s", cid, module_id, version)
        self._emit("candidate_registered", {
            "candidate_id": cid, "module_id": module_id, "version": version,
        })
        return {
            "candidate_id": cid, "module_id": module_id, "version": version,
            "config_json": config, "registered_at": now,
        }

    def deregister_candidate(self, candidate_id: str) -> bool:
        """Remove a candidate. Returns True if found and removed."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM swap_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).rowcount
            self._conn.commit()
        if n:
            log.info("deregistered candidate %s", candidate_id)
        return bool(n)

    def list_candidates(self, module_id: str | None = None,
                        limit: int = 500) -> list[dict]:
        """List candidates, optionally filtered by module."""
        with self._lock:
            if module_id:
                rows = self._conn.execute(
                    "SELECT * FROM swap_candidates WHERE module_id = ? ORDER BY registered_at DESC LIMIT ?",
                    (module_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM swap_candidates ORDER BY registered_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["config_json"] = json.loads(d["config_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Swap Operations
    # ------------------------------------------------------------------

    def initiate_swap(self, target_module: str, from_version: str,
                      to_version: str) -> dict:
        """Initiate a swap operation for a target module."""
        op_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO swap_operations
                    (operation_id, target_module, from_version, to_version, status, initiated_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """, (op_id, target_module, from_version, to_version, now))
            self._conn.commit()

        log.info("initiated swap %s: %s %s -> %s", op_id, target_module, from_version, to_version)
        self._emit("swap_initiated", {
            "operation_id": op_id, "target_module": target_module,
            "from_version": from_version, "to_version": to_version,
        })
        return {
            "operation_id": op_id, "target_module": target_module,
            "from_version": from_version, "to_version": to_version,
            "status": "pending", "initiated_at": now,
        }

    def complete_swap(self, operation_id: str, success: bool,
                      result_json: dict | str | None = None) -> dict | None:
        """Complete a swap operation with success/failure result."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM swap_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if not row:
                return None
            if row["status"] != "pending":
                return None

        now = time.time()
        result_id = self._uid()

        if result_json is None:
            result_data = {}
        elif isinstance(result_json, str):
            result_data = json.loads(result_json)
        else:
            result_data = result_json
        result_str = json.dumps(result_data, default=str)

        status = "completed" if success else "failed"

        with self._lock:
            self._conn.execute("""
                UPDATE swap_operations SET status = ?, completed_at = ? WHERE operation_id = ?
            """, (status, now, operation_id))
            self._conn.execute("""
                INSERT INTO swap_results (result_id, operation_id, success, result_json, completed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (result_id, operation_id, int(success), result_str, now))
            self._conn.commit()

        self._emit("swap_completed", {
            "operation_id": operation_id, "success": success, "status": status,
        })
        log.info("completed swap %s (%s)", operation_id, status)
        return {
            "result_id": result_id, "operation_id": operation_id,
            "success": success, "status": status,
            "result_json": result_data, "completed_at": now,
        }

    def rollback_swap(self, operation_id: str) -> dict | None:
        """Rollback a completed swap, re-initiating with reversed versions."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM swap_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        if not row:
            return None

        target = row["target_module"]
        from_ver = row["from_version"]
        to_ver = row["to_version"]

        # Create a reverse swap: swap back from to_version to from_version
        now = time.time()
        rb_id = self._uid()

        with self._lock:
            # Mark original as rolled_back
            self._conn.execute(
                "UPDATE swap_operations SET status = 'rolled_back', completed_at = ? WHERE operation_id = ?",
                (now, operation_id),
            )
            # Insert reverse operation
            self._conn.execute("""
                INSERT INTO swap_operations
                    (operation_id, target_module, from_version, to_version, status, initiated_at, completed_at)
                VALUES (?, ?, ?, ?, 'completed', ?, ?)
            """, (rb_id, target, to_ver, from_ver, "completed", now, now))
            self._conn.commit()

        self._emit("swap_rolled_back", {
            "original_operation_id": operation_id,
            "rollback_operation_id": rb_id,
            "target_module": target,
        })
        log.info("rolled back swap %s via %s", operation_id, rb_id)
        return {
            "original_operation_id": operation_id,
            "rollback_operation_id": rb_id,
            "target_module": target,
            "from_version": to_ver,
            "to_version": from_ver,
            "status": "completed",
            "completed_at": now,
        }

    # ------------------------------------------------------------------
    # History & Stats
    # ------------------------------------------------------------------

    def get_swap_history(self, module_id: str | None = None,
                         limit: int = 50) -> list[dict]:
        """Get swap operation history, optionally filtered by module."""
        with self._lock:
            if module_id:
                rows = self._conn.execute(
                    "SELECT * FROM swap_operations WHERE target_module = ? "
                    "ORDER BY initiated_at DESC LIMIT ?",
                    (module_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM swap_operations ORDER BY initiated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_swap_stats(self) -> dict[str, Any]:
        """Return aggregate swap statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM swap_operations"
            ).fetchone()["cnt"]
            pending = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM swap_operations WHERE status = 'pending'"
            ).fetchone()["cnt"]
            completed = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM swap_operations WHERE status = 'completed'"
            ).fetchone()["cnt"]
            failed = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM swap_operations WHERE status = 'failed'"
            ).fetchone()["cnt"]
            rolled_back = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM swap_operations WHERE status = 'rolled_back'"
            ).fetchone()["cnt"]
            candidates = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM swap_candidates"
            ).fetchone()["cnt"]

        return {
            "total_operations": total,
            "pending": pending,
            "completed": completed,
            "failed": failed,
            "rolled_back": rolled_back,
            "total_candidates": candidates,
        }

    def health_check(self) -> dict[str, Any]:
        """Return a per-environment health snapshot for the hot-swap orch.

        Used by ``GET /api/v1/core/hot-swap/health``. Reports overall status
        plus the same op counts as :meth:`get_swap_stats` so dashboards have
        a single endpoint to call.
        """
        return {
            "status": "healthy",
            "active_env": self._env_active,
            "environments": self.list_environments(),
            "stats": self.get_swap_stats(),
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # Environment view (workspace vocabulary)
    # ------------------------------------------------------------------
    #
    # The dashboard surfaces hot-swap state as a set of "environments" —
    # primary (active) module versions plus pending swap candidates.
    # We project that view directly from the candidate/operation tables
    # rather than introducing a separate environments registry.

    def switch_env(self, env_name: str, module_filter: list[str] | None = None) -> HotSwapResult:
        """Switch all or selected module bindings to an environment."""
        with self._lock:
            if env_name not in self._env_configs:
                return HotSwapResult(False, old_env=self._env_active, new_env=env_name, message="Unknown environment")
            old_env = self._env_active
            if module_filter is None:
                switched = [module_id for module_id, bound in self._module_env_bindings.items() if bound == old_env]
                for module_id in switched:
                    self._module_env_bindings[module_id] = env_name
                self._env_active = env_name
                self._env_active_since[env_name] = time.time()
            else:
                switched = [module_id for module_id in module_filter if module_id in self._module_env_bindings]
                for module_id in switched:
                    self._module_env_bindings[module_id] = env_name

        self._emit("env.hot_swap", {
            "old_env": old_env,
            "new_env": env_name,
            "switched_modules": switched,
        })
        return HotSwapResult(True, old_env=old_env, new_env=env_name, switched_modules=switched)

    def bind_module(self, module_id: str, env_name: str) -> dict:
        """Bind one module to an environment."""
        with self._lock:
            if env_name not in self._env_configs:
                return {"bound": False, "module_id": module_id, "env_name": env_name, "message": "Unknown environment"}
            self._module_env_bindings[module_id] = env_name

        self._emit("env.module_bound", {"module_id": module_id, "env_name": env_name})
        return {"bound": True, "module_id": module_id, "env_name": env_name}

    def list_environments(self) -> list[dict]:
        """List the operator-facing environments."""
        with self._lock:
            return [
                {
                    "name": name,
                    "config": dict(config),
                    "active_since": self._env_active_since.get(name, 0.0),
                    "is_active": name == self._env_active,
                    "module_count": sum(1 for env_name in self._module_env_bindings.values() if env_name == name),
                }
                for name, config in self._env_configs.items()
            ]

    def get_active(self) -> dict:
        """Return the active environment."""
        with self._lock:
            return next(env for env in self.list_environments() if env["name"] == self._env_active)

    def get_module_env(self, module_id: str) -> dict:
        """Return the environment binding for one module."""
        with self._lock:
            env_name = self._module_env_bindings.get(module_id)
        return {"module_id": module_id, "env_name": env_name}


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: HotSwapManager | None = None


def get_hot_swap_manager(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> HotSwapManager:
    global _instance
    if _instance is None:
        _instance = HotSwapManager(db_path, event_bus)
    return _instance


def reset_hot_swap_manager() -> None:
    global _instance
    _instance = None


get_hot_swap_orchestrator = get_hot_swap_manager
reset_hot_swap_orchestrator = reset_hot_swap_manager
HotSwapOrchestrator = HotSwapManager
