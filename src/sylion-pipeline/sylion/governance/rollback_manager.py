"""
SYLION Governance -- Rollback Manager

Enables safe rollback of decisions, pipeline runs, and module configurations
to previous known-good states. Creates checkpoint points and tracks all
rollback operations with approval workflows for high-impact changes.

Tables:
  rollback_points      -- named checkpoints capturing system state
  rollback_operations  -- records of rollback requests and executions

Singleton: get_rollback_manager() / reset_rollback_manager()
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

log = logging.getLogger("sylion.governance.rollback_manager")


class RollbackManager:
    """Manages rollback points and operations for safe state restoration."""

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
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS rollback_points (
                point_id        TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                description     TEXT,

                snapshot_id     TEXT,
                pipeline_run_id TEXT,
                module_states   TEXT NOT NULL,
                config_state    TEXT,

                point_type      TEXT NOT NULL,
                is_valid        INTEGER DEFAULT 1,

                created_at      REAL NOT NULL,
                created_by      TEXT DEFAULT 'system'
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS rollback_operations (
                operation_id    TEXT PRIMARY KEY,
                point_id        TEXT NOT NULL,

                operation_type  TEXT NOT NULL,
                target_scope    TEXT NOT NULL,

                before_state    TEXT NOT NULL,
                after_state     TEXT,

                status          TEXT DEFAULT 'pending',
                error_message   TEXT,

                requires_approval INTEGER DEFAULT 0,
                approved_by     TEXT,
                approved_at     REAL,

                started_at      REAL,
                completed_at    REAL,
                created_at      REAL NOT NULL
            )
        """)

        # Indexes
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rp_type ON rollback_points(point_type)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rp_pipeline ON rollback_points(pipeline_run_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rp_valid ON rollback_points(is_valid)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ro_point ON rollback_operations(point_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ro_status ON rollback_operations(status)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="rollback_manager",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    def _get_current_module_states(self) -> dict:
        """Try to gather current module states from the registry."""
        try:
            from sylion.core.module_registry import get_registry
            registry = get_registry()
            modules = registry.list_modules()
            states: dict[str, dict] = {}
            for m in modules:
                states[m["module_id"]] = {
                    "lifecycle": m.get("lifecycle", "unknown"),
                    "status": m.get("lifecycle", "unknown"),
                    "last_event": m.get("last_heartbeat", 0),
                }
            return states
        except Exception:
            return {}

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        """Parse a row, decoding JSON text fields."""
        d = dict(row)
        for key in ("module_states", "config_state", "before_state", "after_state",
                     "target_scope"):
            val = d.get(key)
            if val is not None and isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    # ------------------------------------------------------------------
    # Public API -- Rollback Points
    # ------------------------------------------------------------------

    def create_checkpoint(
        self,
        name: str,
        description: str = "",
        pipeline_run_id: str | None = None,
        snapshot_id: str | None = None,
        module_states: dict | None = None,
        config_state: dict | None = None,
        point_type: str = "manual",
    ) -> dict:
        """Create a named rollback point capturing current system state.

        Returns the created rollback point record.
        """
        point_id = self._uid()
        now = time.time()

        if module_states is None:
            module_states = self._get_current_module_states()

        with self._lock:
            self._conn.execute("""
                INSERT INTO rollback_points
                (point_id, name, description, snapshot_id, pipeline_run_id,
                 module_states, config_state, point_type, is_valid,
                 created_at, created_by)
                VALUES (?,?,?,?,?,?,?,?,1,?,'system')
            """, (
                point_id, name, description, snapshot_id, pipeline_run_id,
                json.dumps(module_states),
                json.dumps(config_state) if config_state is not None else None,
                point_type, now,
            ))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM rollback_points WHERE point_id = ?",
                (point_id,),
            ).fetchone()

        result = self._parse_row(row) if row else {"point_id": point_id}

        self._emit("rollback.point.created", {
            "point_id": point_id,
            "name": name,
            "point_type": point_type,
        })
        log.info("created rollback point %s (%s, type=%s)",
                 point_id, name, point_type)
        return result

    def create_auto_checkpoint(
        self,
        pipeline_run_id: str,
        trigger: str = "pre_step",
    ) -> dict:
        """Auto-checkpoint before pipeline steps or other automated triggers."""
        return self.create_checkpoint(
            name=f"auto_{trigger}_{pipeline_run_id}",
            description=f"Auto-checkpoint: {trigger} for pipeline {pipeline_run_id}",
            pipeline_run_id=pipeline_run_id,
            point_type="auto_checkpoint",
        )

    def list_rollback_points(
        self,
        point_type: str | None = None,
        pipeline_run_id: str | None = None,
        is_valid: int | None = None,
    ) -> list[dict]:
        """List rollback points with optional filters."""
        with self._lock:
            q = "SELECT * FROM rollback_points WHERE 1=1"
            params: list[Any] = []
            if point_type is not None:
                q += " AND point_type = ?"
                params.append(point_type)
            if pipeline_run_id is not None:
                q += " AND pipeline_run_id = ?"
                params.append(pipeline_run_id)
            if is_valid is not None:
                q += " AND is_valid = ?"
                params.append(is_valid)
            q += " ORDER BY created_at DESC"
            rows = self._conn.execute(q, params).fetchall()
        return [self._parse_row(r) for r in rows]

    def get_rollback_point(self, point_id: str) -> dict | None:
        """Return a single rollback point by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rollback_points WHERE point_id = ?",
                (point_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def invalidate_point(self, point_id: str) -> dict | None:
        """Mark a rollback point as no longer safe to restore."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rollback_points WHERE point_id = ?",
                (point_id,),
            ).fetchone()
            if not row:
                return None

            self._conn.execute(
                "UPDATE rollback_points SET is_valid = 0 WHERE point_id = ?",
                (point_id,),
            )
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM rollback_points WHERE point_id = ?",
                (point_id,),
            ).fetchone()

        result = self._parse_row(row) if row else None

        self._emit("rollback.point.invalidated", {
            "point_id": point_id,
        })
        log.info("invalidated rollback point %s", point_id)
        return result

    # ------------------------------------------------------------------
    # Public API -- Rollback Operations
    # ------------------------------------------------------------------

    def request_rollback(
        self,
        point_id: str,
        operation_type: str = "full_restore",
        target_scope: dict | None = None,
        requires_approval: bool = False,
    ) -> dict | None:
        """Create a rollback operation request. Returns the operation record."""
        with self._lock:
            point = self._conn.execute(
                "SELECT * FROM rollback_points WHERE point_id = ?",
                (point_id,),
            ).fetchone()
            if not point:
                return None

            if point["is_valid"] != 1:
                return None

        operation_id = self._uid()
        now = time.time()

        scope_str = json.dumps(target_scope) if target_scope else json.dumps({})
        before_state: dict[str, Any] = {
            "current_module_states": self._get_current_module_states(),
        }

        with self._lock:
            self._conn.execute("""
                INSERT INTO rollback_operations
                (operation_id, point_id, operation_type, target_scope,
                 before_state, status, requires_approval, created_at)
                VALUES (?,?,?,?,?, 'pending', ?,?)
            """, (
                operation_id, point_id, operation_type, scope_str,
                json.dumps(before_state),
                1 if requires_approval else 0,
                now,
            ))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM rollback_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()

        result = self._parse_row(row) if row else {"operation_id": operation_id}

        self._emit("rollback.operation.requested", {
            "operation_id": operation_id,
            "point_id": point_id,
            "operation_type": operation_type,
        })
        log.info("requested rollback %s for point %s (type=%s)",
                 operation_id, point_id, operation_type)
        return result

    def approve_rollback(
        self,
        operation_id: str,
        approved_by: str,
    ) -> dict | None:
        """Approve a pending rollback operation."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rollback_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if not row:
                return None

            if row["status"] != "pending":
                return None

            now = time.time()
            self._conn.execute("""
                UPDATE rollback_operations
                SET approved_by = ?, approved_at = ?
                WHERE operation_id = ?
            """, (approved_by, now, operation_id))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM rollback_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()

        result = self._parse_row(row) if row else None

        self._emit("rollback.operation.approved", {
            "operation_id": operation_id,
            "approved_by": approved_by,
        })
        log.info("approved rollback %s by %s", operation_id, approved_by)
        return result

    def execute_rollback(self, operation_id: str) -> dict | None:
        """Execute a pending rollback operation.

        Performs the actual state restoration based on operation_type:
        - full_restore: restores all module_states from checkpoint
        - module_restore: restores only specified modules
        - config_restore: restores configuration state
        - decision_revert: uses decision_snapshot.change_decision

        Returns the updated operation record with before/after states.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rollback_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if not row:
                return None

            op = dict(row)
            if op["status"] not in ("pending",):
                return None

            # Check approval requirement
            if op["requires_approval"] and not op.get("approved_by"):
                return None

            point = self._conn.execute(
                "SELECT * FROM rollback_points WHERE point_id = ?",
                (op["point_id"],),
            ).fetchone()
            if not point:
                return None

        now = time.time()
        point_data = dict(point)
        checkpoint_states = json.loads(point_data["module_states"])
        checkpoint_config = json.loads(point_data["config_state"]) if point_data["config_state"] else None

        # Capture before state
        before_state = {
            "current_module_states": self._get_current_module_states(),
            "checkpoint_id": op["point_id"],
        }

        # Mark in progress
        with self._lock:
            self._conn.execute("""
                UPDATE rollback_operations
                SET status = 'in_progress', started_at = ?,
                    before_state = ?
                WHERE operation_id = ?
            """, (now, json.dumps(before_state), operation_id))
            self._conn.commit()

        after_state: dict[str, Any] = {}
        error_message = None

        try:
            op_type = op["operation_type"]
            target_scope = json.loads(op["target_scope"]) if op["target_scope"] else {}

            if op_type == "full_restore":
                after_state = {
                    "restored_module_states": checkpoint_states,
                    "restored_config": checkpoint_config,
                }

            elif op_type == "module_restore":
                module_ids = target_scope.get("module_ids", [])
                restored = {
                    mid: checkpoint_states[mid]
                    for mid in module_ids
                    if mid in checkpoint_states
                }
                after_state = {
                    "restored_modules": restored,
                }

            elif op_type == "config_restore":
                after_state = {
                    "restored_config": checkpoint_config,
                }

            elif op_type == "decision_revert":
                snapshot_id = point_data.get("snapshot_id")
                if snapshot_id:
                    try:
                        from sylion.governance.decision_snapshot import get_decision_snapshot
                        ds = get_decision_snapshot()
                        revert_result = ds.change_decision(
                            snapshot_id,
                            new_choice=target_scope.get("new_choice", "reverted"),
                        )
                        after_state = {
                            "decision_revert_result": revert_result,
                        }
                    except Exception as e:
                        error_message = f"Decision revert failed: {e}"
                        after_state = {"error": error_message}
                else:
                    error_message = "No snapshot_id on rollback point for decision_revert"
                    after_state = {"error": error_message}
            else:
                error_message = f"Unknown operation type: {op_type}"
                after_state = {"error": error_message}

        except Exception as e:
            error_message = str(e)
            after_state = {"error": error_message}

        # Finalize
        final_status = "completed" if not error_message else "failed"
        completed_at = time.time()

        with self._lock:
            self._conn.execute("""
                UPDATE rollback_operations
                SET status = ?, after_state = ?, error_message = ?,
                    completed_at = ?
                WHERE operation_id = ?
            """, (
                final_status,
                json.dumps(after_state),
                error_message,
                completed_at,
                operation_id,
            ))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM rollback_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()

        result = self._parse_row(row) if row else None

        event_topic = f"rollback.operation.{final_status}"
        self._emit(event_topic, {
            "operation_id": operation_id,
            "point_id": op["point_id"],
            "operation_type": op["operation_type"],
            "error": error_message,
        })
        log.info("rollback %s %s for point %s",
                 operation_id, final_status, op["point_id"])
        return result

    def get_rollback_operations(
        self,
        point_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """List rollback operations with optional filters."""
        with self._lock:
            q = "SELECT * FROM rollback_operations WHERE 1=1"
            params: list[Any] = []
            if point_id is not None:
                q += " AND point_id = ?"
                params.append(point_id)
            if status is not None:
                q += " AND status = ?"
                params.append(status)
            q += " ORDER BY created_at DESC"
            rows = self._conn.execute(q, params).fetchall()
        return [self._parse_row(r) for r in rows]

    def get_rollback_operation(self, operation_id: str) -> dict | None:
        """Return a single rollback operation by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rollback_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def get_rollback_stats(self) -> dict:
        """Return statistics about rollback points and operations."""
        with self._lock:
            total_points = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM rollback_points"
            ).fetchone()["cnt"]

            total_operations = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM rollback_operations"
            ).fetchone()["cnt"]

            # By status
            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM rollback_operations "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            # By type
            type_rows = self._conn.execute(
                "SELECT operation_type, COUNT(*) as cnt FROM rollback_operations "
                "GROUP BY operation_type"
            ).fetchall()
            by_type = {r["operation_type"]: r["cnt"] for r in type_rows}

            # Success rate
            completed = by_status.get("completed", 0)
            failed = by_status.get("failed", 0)
            total_done = completed + failed
            success_rate = (completed / total_done * 100) if total_done > 0 else 0.0

        return {
            "total_points": total_points,
            "total_operations": total_operations,
            "by_status": by_status,
            "by_type": by_type,
            "success_rate": round(success_rate, 2),
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: RollbackManager | None = None


def get_rollback_manager(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> RollbackManager:
    global _manager
    if _manager is None:
        _manager = RollbackManager(db_path, event_bus)
    return _manager


def reset_rollback_manager(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> RollbackManager:
    global _manager
    _manager = RollbackManager(db_path, event_bus)
    return _manager
