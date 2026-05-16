"""
SYLION Execution -- Deployment Orchestrator

Orchestrates module deployments through lifecycle stages. Each deployment
tracks a module transitioning from one stage to another using a strategy
(blue_green, canary, rolling, recreate, shadow). Steps are auto-created
per strategy: prepare -> validate -> deploy -> verify -> complete.

Tables:
  deployments      -- deployment-level metadata + status
  deployment_steps -- individual steps inside a deployment

Singleton: get_deployment_orchestrator() / reset_deployment_orchestrator()
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

log = logging.getLogger("sylion.execution.deployment_orchestrator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STRATEGIES = ("blue_green", "canary", "rolling", "recreate", "shadow")
VALID_STATUSES = ("pending", "in_progress", "completed", "failed", "rolled_back")
VALID_STAGES = (
    "draft", "build", "validate", "shadow",
    "dual", "cutover", "stable", "deprecated",
)

# Steps auto-created for every deployment, in execution order.
DEFAULT_STEPS = ("prepare", "validate", "deploy", "verify", "complete")


# ---------------------------------------------------------------------------
# Deployment Orchestrator
# ---------------------------------------------------------------------------

class DeploymentOrchestrator:
    """Manages module deployment lifecycle with strategy-based step tracking.

    Thread-safe via RLock. SQLite-backed. Emits events through EventBus.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
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
            CREATE TABLE IF NOT EXISTS deployments (
                deployment_id  TEXT PRIMARY KEY,
                module_id      TEXT NOT NULL,
                from_stage     TEXT NOT NULL,
                to_stage       TEXT NOT NULL,
                strategy       TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'pending',
                started_at     REAL,
                completed_at   REAL,
                rollback_at    REAL,
                metadata       TEXT
            );

            CREATE TABLE IF NOT EXISTS deployment_steps (
                step_id       TEXT PRIMARY KEY,
                deployment_id TEXT NOT NULL,
                step_name     TEXT NOT NULL,
                step_order    INTEGER NOT NULL DEFAULT 0,
                status        TEXT NOT NULL DEFAULT 'pending',
                started_at    REAL,
                completed_at  REAL,
                output        TEXT,
                FOREIGN KEY (deployment_id) REFERENCES deployments(deployment_id)
            );
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deployments_module "
            "ON deployments(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deployments_status "
            "ON deployments(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deployments_strategy "
            "ON deployments(strategy)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_steps_deployment "
            "ON deployment_steps(deployment_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_steps_status "
            "ON deployment_steps(status)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _now() -> float:
        return time.time()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="execution.deployment_orchestrator",
            ))

    @staticmethod
    def _parse_metadata(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def _deployment_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["metadata"] = json.loads(d.get("metadata") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["metadata"] = {}
        return d

    @staticmethod
    def _step_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            if d.get("output") is not None:
                d["output"] = json.loads(d["output"])
        except (json.JSONDecodeError, TypeError):
            pass
        return d

    def _validate_strategy(self, strategy: str):
        if strategy not in VALID_STRATEGIES:
            raise ValueError(
                f"Invalid strategy '{strategy}', "
                f"must be one of {VALID_STRATEGIES}"
            )

    def _validate_status(self, status: str):
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}', "
                f"must be one of {VALID_STATUSES}"
            )

    def _validate_stage(self, stage: str):
        if stage not in VALID_STAGES:
            raise ValueError(
                f"Invalid stage '{stage}', "
                f"must be one of {VALID_STAGES}"
            )

    def _get_deployment_row(self, deployment_id: str) -> sqlite3.Row | None:
        """Fetch a deployment row; raises ValueError if not found."""
        row = self._conn.execute(
            "SELECT * FROM deployments WHERE deployment_id = ?",
            (deployment_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Deployment '{deployment_id}' not found")
        return row

    # ------------------------------------------------------------------
    # Deployment CRUD
    # ------------------------------------------------------------------

    def create_deployment(self, module_id: str, from_stage: str,
                          to_stage: str, strategy: str = "blue_green",
                          metadata: dict | None = None) -> dict:
        """Create a new deployment with auto-generated steps.

        Steps are created in order: prepare, validate, deploy, verify, complete.
        The deployment starts in 'pending' status and all steps are 'pending'.
        """
        self._validate_strategy(strategy)
        self._validate_stage(from_stage)
        self._validate_stage(to_stage)

        deployment_id = self._uid()
        now = self._now()
        metadata_json = json.dumps(metadata or {}, sort_keys=True, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO deployments
                    (deployment_id, module_id, from_stage, to_stage,
                     strategy, status, started_at, completed_at,
                     rollback_at, metadata)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL, NULL, ?)
            """, (deployment_id, module_id, from_stage, to_stage,
                  strategy, now, metadata_json))

            # Auto-create steps
            for idx, step_name in enumerate(DEFAULT_STEPS):
                step_id = self._uid()
                self._conn.execute("""
                    INSERT INTO deployment_steps
                        (step_id, deployment_id, step_name, step_order,
                         status, started_at, completed_at, output)
                    VALUES (?, ?, ?, ?, 'pending', NULL, NULL, NULL)
                """, (step_id, deployment_id, step_name, idx))

            self._conn.commit()

        result = {
            "deployment_id": deployment_id,
            "module_id": module_id,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "strategy": strategy,
            "status": "pending",
            "started_at": now,
            "completed_at": None,
            "rollback_at": None,
            "metadata": metadata or {},
        }

        self._emit("deployment.created", {
            "deployment_id": deployment_id,
            "module_id": module_id,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "strategy": strategy,
        })
        log.info("deployment created: %s for module %s (%s -> %s, %s)",
                 deployment_id[:12], module_id, from_stage, to_stage, strategy)
        return result

    def get_deployment(self, deployment_id: str) -> dict | None:
        """Get a single deployment by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM deployments WHERE deployment_id = ?",
                (deployment_id,),
            ).fetchone()
        if not row:
            return None
        return self._deployment_row(row)

    def list_deployments(self, module_id: str | None = None,
                         status: str | None = None,
                         limit: int = 100) -> list[dict]:
        """List deployments with optional filters."""
        if status is not None:
            self._validate_status(status)

        conds: list[str] = []
        params: list[Any] = []

        if module_id is not None:
            conds.append("module_id = ?")
            params.append(module_id)
        if status is not None:
            conds.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM deployments{where} "
                f"ORDER BY started_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._deployment_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def advance_step(self, deployment_id: str, step_name: str,
                     output: str = "") -> dict:
        """Advance a step by name within a deployment.

        Sets the step to 'in_progress' if it was 'pending', or marks it
        'completed' if it was 'in_progress'. The first advancement sets the
        deployment status to 'in_progress'.
        """
        now = self._now()
        output_val: str | None = output if output else None

        with self._lock:
            self._get_deployment_row(deployment_id)

            step_row = self._conn.execute(
                "SELECT * FROM deployment_steps "
                "WHERE deployment_id = ? AND step_name = ?",
                (deployment_id, step_name),
            ).fetchone()
            if not step_row:
                raise ValueError(
                    f"Step '{step_name}' not found in deployment '{deployment_id}'"
                )

            step = dict(step_row)

            if step["status"] == "pending":
                # Transition pending -> in_progress
                self._conn.execute("""
                    UPDATE deployment_steps
                    SET status = 'in_progress', started_at = ?, output = ?
                    WHERE step_id = ?
                """, (now, output_val, step["step_id"]))

                # Set deployment to in_progress if still pending
                self._conn.execute(
                    "UPDATE deployments SET status = 'in_progress' "
                    "WHERE deployment_id = ? AND status = 'pending'",
                    (deployment_id,),
                )
                new_status = "in_progress"

            elif step["status"] == "in_progress":
                # Transition in_progress -> completed
                self._conn.execute("""
                    UPDATE deployment_steps
                    SET status = 'completed', completed_at = ?, output = ?
                    WHERE step_id = ?
                """, (now, output_val, step["step_id"]))
                new_status = "completed"

            else:
                raise ValueError(
                    f"Cannot advance step '{step_name}' in status '{step['status']}'"
                )

            self._conn.commit()

        result = {
            "step_id": step["step_id"],
            "deployment_id": deployment_id,
            "step_name": step_name,
            "previous_status": step["status"],
            "new_status": new_status,
            "output": output or None,
        }
        log.info("step %s advanced: %s -> %s in deployment %s",
                 step_name, step["status"], new_status, deployment_id[:12])
        return result

    def get_steps(self, deployment_id: str) -> list[dict]:
        """List all steps for a deployment, ordered by step_order.

        Raises ValueError if the deployment does not exist.
        """
        with self._lock:
            self._get_deployment_row(deployment_id)
            rows = self._conn.execute(
                "SELECT * FROM deployment_steps "
                "WHERE deployment_id = ? ORDER BY step_order ASC",
                (deployment_id,),
            ).fetchall()
        return [self._step_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def complete_deployment(self, deployment_id: str) -> dict:
        """Mark a deployment as completed.

        All steps must be completed. Sets completed_at timestamp.
        """
        now = self._now()

        with self._lock:
            row = self._get_deployment_row(deployment_id)
            deployment = self._deployment_row(row)

            if deployment["status"] not in ("in_progress", "pending"):
                raise ValueError(
                    f"Cannot complete deployment in status '{deployment['status']}'"
                )

            # Verify all steps are completed
            incomplete = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM deployment_steps "
                "WHERE deployment_id = ? AND status != 'completed'",
                (deployment_id,),
            ).fetchone()

            if incomplete["cnt"] > 0:
                raise ValueError(
                    f"Cannot complete deployment: {incomplete['cnt']} step(s) not completed"
                )

            self._conn.execute("""
                UPDATE deployments
                SET status = 'completed', completed_at = ?
                WHERE deployment_id = ?
            """, (now, deployment_id))
            self._conn.commit()

        result = {
            "deployment_id": deployment_id,
            "status": "completed",
            "completed_at": now,
        }

        self._emit("deployment.completed", {
            "deployment_id": deployment_id,
            "module_id": deployment["module_id"],
            "from_stage": deployment["from_stage"],
            "to_stage": deployment["to_stage"],
        })
        log.info("deployment completed: %s", deployment_id[:12])
        return result

    def fail_deployment(self, deployment_id: str, reason: str = "") -> dict:
        """Mark a deployment as failed.

        Records the reason in metadata. Does not affect step statuses.
        """
        now = self._now()

        with self._lock:
            row = self._get_deployment_row(deployment_id)
            deployment = self._deployment_row(row)

            if deployment["status"] in ("completed", "rolled_back"):
                raise ValueError(
                    f"Cannot fail deployment in status '{deployment['status']}'"
                )

            # Merge failure reason into metadata
            meta = deployment.get("metadata") or {}
            meta["failure_reason"] = reason
            meta_json = json.dumps(meta, sort_keys=True, default=str)

            self._conn.execute("""
                UPDATE deployments
                SET status = 'failed', metadata = ?
                WHERE deployment_id = ?
            """, (meta_json, deployment_id))
            self._conn.commit()

        result = {
            "deployment_id": deployment_id,
            "status": "failed",
            "reason": reason,
        }

        self._emit("deployment.failed", {
            "deployment_id": deployment_id,
            "module_id": deployment["module_id"],
            "reason": reason,
        })
        log.info("deployment failed: %s (%s)", deployment_id[:12], reason)
        return result

    def rollback_deployment(self, deployment_id: str) -> dict:
        """Rollback a deployment to its from_stage.

        Only deployments in 'in_progress' or 'failed' status can be rolled back.
        Sets rollback_at timestamp and marks status as 'rolled_back'.
        """
        now = self._now()

        with self._lock:
            row = self._get_deployment_row(deployment_id)
            deployment = self._deployment_row(row)

            if deployment["status"] not in ("in_progress", "failed"):
                raise ValueError(
                    f"Cannot rollback deployment in status '{deployment['status']}'"
                )

            self._conn.execute("""
                UPDATE deployments
                SET status = 'rolled_back', rollback_at = ?
                WHERE deployment_id = ?
            """, (now, deployment_id))
            self._conn.commit()

        result = {
            "deployment_id": deployment_id,
            "status": "rolled_back",
            "rollback_at": now,
            "from_stage": deployment["from_stage"],
            "to_stage": deployment["to_stage"],
        }

        self._emit("deployment.rolled_back", {
            "deployment_id": deployment_id,
            "module_id": deployment["module_id"],
            "from_stage": deployment["from_stage"],
            "to_stage": deployment["to_stage"],
        })
        log.info("deployment rolled back: %s (to %s)",
                 deployment_id[:12], deployment["from_stage"])
        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return aggregate statistics: counts by status and strategy."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM deployments"
            ).fetchone()["cnt"]

            # By status
            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM deployments "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            # By strategy
            strat_rows = self._conn.execute(
                "SELECT strategy, COUNT(*) as cnt FROM deployments "
                "GROUP BY strategy"
            ).fetchall()
            by_strategy = {r["strategy"]: r["cnt"] for r in strat_rows}

        # Fill in zero-count statuses / strategies
        for s in VALID_STATUSES:
            by_status.setdefault(s, 0)
        for s in VALID_STRATEGIES:
            by_strategy.setdefault(s, 0)

        return {
            "total": total,
            "by_status": by_status,
            "by_strategy": by_strategy,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="execution.deployment_orchestrator",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_orchestrator: DeploymentOrchestrator | None = None


def get_deployment_orchestrator(db_path: str | Path | None = None,
                                event_bus: EventBus | None = None) -> DeploymentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = DeploymentOrchestrator(db_path, event_bus)
    return _orchestrator


def reset_deployment_orchestrator(db_path: str | Path | None = None,
                                  event_bus: EventBus | None = None) -> DeploymentOrchestrator:
    global _orchestrator
    _orchestrator = DeploymentOrchestrator(db_path, event_bus)
    return _orchestrator
