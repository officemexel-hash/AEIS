"""
SYLION Core -- Rollback Manager

Manages rollback contracts for module lifecycle transitions.
Every shadow -> dual -> cutover transition has a pre-created rollback contract
that captures the previous known-good state and allows reversal.

Rules (Ksiega R2 -- Reversibility):
  - Contracts auto-expire after 30 days in stable stage
  - Rollback of D3+ modules requires Council 4/4 vote
  - Evidence of failure must be recorded in EvidenceSpine
  - Each rollback emits module.rollback.executed event

SQLite-backed. Thread-safe. Singleton.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus
from sylion.core.module_registry import (
    ModuleRegistry, ModuleLifecycleStage, get_registry,
)
from sylion.core.evidence_spine import EvidenceSpine, EvidenceEntry

log = logging.getLogger("sylion.core.rollback_manager")

# 30 days in seconds
EXPIRY_SECONDS = 30 * 24 * 60 * 60

# Lifecycle transitions that require rollback contracts
_ROLLBACK_TRANSITIONS = {
    (ModuleLifecycleStage.SHADOW.value, ModuleLifecycleStage.DUAL.value),
    (ModuleLifecycleStage.DUAL.value, ModuleLifecycleStage.CUTOVER.value),
    (ModuleLifecycleStage.CUTOVER.value, ModuleLifecycleStage.STABLE.value),
    (ModuleLifecycleStage.STABLE.value, ModuleLifecycleStage.DEPRECATED.value),
}


class ContractStatus(str, Enum):
    ACTIVE = "active"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class RollbackContract:
    """Defines a rollback contract for a module state transition."""
    contract_id: str = ""
    module_id: str = ""
    from_stage: str = ""
    to_stage: str = ""
    snapshot_hash: str = ""
    snapshot_data: str = ""          # JSON-serialized module state
    status: str = ContractStatus.ACTIVE.value
    created_at: float = 0.0
    expires_at: float = 0.0
    executed_at: float = 0.0
    reason: str = ""

    def __post_init__(self):
        if not self.contract_id:
            self.contract_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
        if not self.expires_at:
            self.expires_at = self.created_at + EXPIRY_SECONDS


def _compute_snapshot_hash(module_data: dict) -> str:
    """Compute SHA-256 hash of canonical module state."""
    canonical = json.dumps(module_data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RollbackManager:
    """Manages rollback contracts for all module transitions.

    SQLite-backed, thread-safe. Creates contracts before every lifecycle
    transition so that a known-good state can be restored on failure.
    """

    def __init__(self, registry: ModuleRegistry | None = None,
                 event_bus: EventBus | None = None,
                 evidence_spine: EvidenceSpine | None = None,
                 db_path: str | Path | None = None):
        self._registry = registry or get_registry()
        self._event_bus = event_bus
        self._evidence_spine = evidence_spine
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS rollback_contracts (
                contract_id    TEXT PRIMARY KEY,
                module_id      TEXT NOT NULL,
                from_stage     TEXT NOT NULL,
                to_stage       TEXT NOT NULL,
                snapshot_hash  TEXT NOT NULL,
                snapshot_data  TEXT NOT NULL DEFAULT '{}',
                status         TEXT NOT NULL DEFAULT 'active',
                created_at     REAL NOT NULL,
                expires_at     REAL NOT NULL,
                executed_at    REAL NOT NULL DEFAULT 0,
                reason         TEXT NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rb_module ON rollback_contracts(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rb_status ON rollback_contracts(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rb_expires ON rollback_contracts(expires_at)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Contract creation
    # ------------------------------------------------------------------

    def create_contract(self, module_id: str, from_stage: str,
                        to_stage: str, snapshot_hash: str = "",
                        snapshot_data: dict | None = None) -> dict:
        """Create a rollback contract before a transition.

        Captures the current module state as a snapshot so it can be
        restored if the transition fails.

        Args:
            module_id: The module to create a rollback contract for.
            from_stage: Current lifecycle stage.
            to_stage: Target lifecycle stage.
            snapshot_hash: Optional pre-computed hash. Computed if empty.
            snapshot_data: Optional pre-fetched module data. Fetched
                from registry if not provided.
        """
        mod = snapshot_data
        if mod is None:
            mod = self._registry.get(module_id)
        if not mod:
            raise ValueError(f"Module {module_id} not registered")

        # Capture module state snapshot
        snapshot_json = json.dumps(mod, default=str)
        if not snapshot_hash:
            snapshot_hash = _compute_snapshot_hash(mod)

        contract = RollbackContract(
            module_id=module_id,
            from_stage=from_stage,
            to_stage=to_stage,
            snapshot_hash=snapshot_hash,
            snapshot_data=snapshot_json,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO rollback_contracts
                    (contract_id, module_id, from_stage, to_stage,
                     snapshot_hash, snapshot_data, status, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                contract.contract_id, contract.module_id,
                contract.from_stage, contract.to_stage,
                contract.snapshot_hash, contract.snapshot_data,
                ContractStatus.ACTIVE.value,
                contract.created_at, contract.expires_at,
            ))
            self._conn.commit()

        self._emit("module.rollback.contract_created", {
            "contract_id": contract.contract_id,
            "module_id": module_id,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "snapshot_hash": snapshot_hash,
        })

        log.info("created rollback contract %s for %s (%s -> %s)",
                 contract.contract_id[:12], module_id, from_stage, to_stage)

        return {
            "contract_id": contract.contract_id,
            "module_id": module_id,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "snapshot_hash": snapshot_hash,
            "status": ContractStatus.ACTIVE.value,
            "created_at": contract.created_at,
            "expires_at": contract.expires_at,
        }

    # ------------------------------------------------------------------
    # Rollback execution
    # ------------------------------------------------------------------

    def execute_rollback(self, contract_id: str, reason: str,
                         council_approval: dict | None = None) -> dict:
        """Execute a rollback. Requires evidence + D3+ Council approval.

        Args:
            contract_id: The rollback contract to execute.
            reason: Evidence of why the rollback is needed.
            council_approval: For D3+ modules, must contain:
                {"session_id": ..., "outcome": "approved"} from Council 4/4.

        Returns:
            Result dict with execution status.
        """
        row = self._conn.execute(
            "SELECT * FROM rollback_contracts WHERE contract_id = ?",
            (contract_id,),
        ).fetchone()

        if not row:
            return {"rolled_back": False, "message": f"Contract {contract_id} not found"}

        contract = dict(row)

        if contract["status"] != ContractStatus.ACTIVE.value:
            return {
                "rolled_back": False,
                "message": f"Contract is {contract['status']}, not active",
            }

        # Check expiry
        if time.time() > contract["expires_at"]:
            with self._lock:
                self._conn.execute(
                    "UPDATE rollback_contracts SET status = ? WHERE contract_id = ?",
                    (ContractStatus.EXPIRED.value, contract_id),
                )
                self._conn.commit()
            return {"rolled_back": False, "message": "Contract has expired"}

        # Check D3+ Council approval requirement
        module_id = contract["module_id"]
        mod = self._registry.get(module_id)

        if mod:
            decision_cls = mod.get("decision_cls", "D3")
            requires_council = decision_cls in ("D3", "D4", "D5")

            if requires_council:
                if not council_approval:
                    return {
                        "rolled_back": False,
                        "message": f"D3+ module requires Council approval (decision_cls={decision_cls})",
                    }
                if council_approval.get("outcome") != "approved":
                    return {
                        "rolled_back": False,
                        "message": f"Council has not approved (outcome={council_approval.get('outcome')})",
                    }

        # Record evidence in EvidenceSpine
        self._record_evidence(module_id, contract_id, reason)

        # Execute the rollback: transition module back to from_stage
        from_stage = contract["from_stage"]
        now = time.time()

        with self._lock:
            self._conn.execute("""
                UPDATE rollback_contracts
                SET status = ?, executed_at = ?, reason = ?
                WHERE contract_id = ?
            """, (ContractStatus.EXECUTED.value, now, reason, contract_id))
            self._conn.commit()

        # Attempt to restore module lifecycle to from_stage
        if mod:
            try:
                target = ModuleLifecycleStage(from_stage)
                self._registry.transition(module_id, target)
            except ValueError:
                log.warning("could not transition %s back to %s; contract still recorded",
                            module_id, from_stage)

        # Emit event
        self._emit("module.rollback.executed", {
            "contract_id": contract_id,
            "module_id": module_id,
            "rolled_back_to": from_stage,
            "reason": reason,
        })

        log.info("executed rollback contract %s for %s -> %s (reason: %s)",
                 contract_id[:12], module_id, from_stage, reason[:60])

        return {
            "rolled_back": True,
            "contract_id": contract_id,
            "module_id": module_id,
            "rolled_back_to": from_stage,
            "executed_at": now,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_contract(self, contract_id: str) -> dict | None:
        """Get a single rollback contract by ID."""
        row = self._conn.execute(
            "SELECT * FROM rollback_contracts WHERE contract_id = ?",
            (contract_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_contracts(self, module_id: str | None = None,
                       status: str | None = None,
                       limit: int = 100) -> list[dict]:
        """List rollback contracts, optionally filtered."""
        q = "SELECT * FROM rollback_contracts WHERE 1=1"
        params: list[Any] = []
        if module_id:
            q += " AND module_id = ?"
            params.append(module_id)
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    # ------------------------------------------------------------------
    # Expiry
    # ------------------------------------------------------------------

    def expire_contract(self, contract_id: str) -> dict:
        """Manually expire a rollback contract."""
        row = self._conn.execute(
            "SELECT status FROM rollback_contracts WHERE contract_id = ?",
            (contract_id,),
        ).fetchone()

        if not row:
            return {"expired": False, "message": f"Contract {contract_id} not found"}

        if row["status"] != ContractStatus.ACTIVE.value:
            return {"expired": False, "message": f"Contract is {row['status']}, cannot expire"}

        with self._lock:
            self._conn.execute(
                "UPDATE rollback_contracts SET status = ? WHERE contract_id = ?",
                (ContractStatus.EXPIRED.value, contract_id),
            )
            self._conn.commit()

        log.info("expired rollback contract %s", contract_id[:12])
        return {"expired": True, "contract_id": contract_id}

    def expire_stale_contracts(self) -> int:
        """Auto-expire all contracts past their expiry time. Returns count."""
        now = time.time()
        with self._lock:
            cursor = self._conn.execute("""
                UPDATE rollback_contracts
                SET status = ?
                WHERE status = ? AND expires_at < ?
            """, (ContractStatus.EXPIRED.value, ContractStatus.ACTIVE.value, now))
            self._conn.commit()
            count = cursor.rowcount

        if count:
            log.info("auto-expired %d stale rollback contracts", count)
        return count

    def cancel_contract(self, contract_id: str) -> dict:
        """Cancel an active rollback contract (e.g. transition succeeded)."""
        row = self._conn.execute(
            "SELECT status FROM rollback_contracts WHERE contract_id = ?",
            (contract_id,),
        ).fetchone()

        if not row:
            return {"cancelled": False, "message": f"Contract {contract_id} not found"}

        if row["status"] != ContractStatus.ACTIVE.value:
            return {"cancelled": False, "message": f"Contract is {row['status']}, cannot cancel"}

        with self._lock:
            self._conn.execute(
                "UPDATE rollback_contracts SET status = ? WHERE contract_id = ?",
                (ContractStatus.CANCELLED.value, contract_id),
            )
            self._conn.commit()

        log.info("cancelled rollback contract %s", contract_id[:12])
        return {"cancelled": True, "contract_id": contract_id}

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def _record_evidence(self, module_id: str, contract_id: str, reason: str):
        """Record rollback evidence in the EvidenceSpine."""
        if not self._evidence_spine:
            return

        entry = EvidenceEntry(
            source_plan="rollback_manager",
            event_type="module.rollback.evidence",
            payload={
                "module_id": module_id,
                "contract_id": contract_id,
                "reason": reason,
            },
            actor_id="rollback_manager",
        )
        self._evidence_spine.append(entry)

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="core.rollback_manager",
            ))

    # ------------------------------------------------------------------
    # Restore-points subsystem (workspace vocabulary)
    # ------------------------------------------------------------------

    def _ensure_points_tables(self) -> None:
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS rb_points (
                    point_id    TEXT PRIMARY KEY,
                    module_id   TEXT NOT NULL,
                    state_json  TEXT NOT NULL DEFAULT '{}',
                    description TEXT NOT NULL DEFAULT '',
                    created_at  REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS rb_operations (
                    operation_id   TEXT PRIMARY KEY,
                    target_module  TEXT NOT NULL,
                    from_point     TEXT NOT NULL,
                    to_point       TEXT NOT NULL,
                    status         TEXT NOT NULL DEFAULT 'pending',
                    created_at     REAL NOT NULL,
                    started_at     REAL NOT NULL DEFAULT 0,
                    completed_at   REAL NOT NULL DEFAULT 0,
                    error          TEXT NOT NULL DEFAULT ''
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS rb_op_steps (
                    step_id       TEXT PRIMARY KEY,
                    operation_id  TEXT NOT NULL,
                    step          TEXT NOT NULL,
                    status        TEXT NOT NULL,
                    details_json  TEXT NOT NULL DEFAULT '{}',
                    created_at    REAL NOT NULL
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rbp_module "
                "ON rb_points(module_id)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rbo_status "
                "ON rb_operations(status)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rbos_op "
                "ON rb_op_steps(operation_id)")
            self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def create_point(self, module_id: str,
                     state_json: dict | str | None = None,
                     description: str = "") -> dict:
        if not module_id:
            raise ValueError("module_id is required")
        self._ensure_points_tables()
        if isinstance(state_json, dict):
            state_str = json.dumps(state_json, default=str)
        elif state_json is None:
            state_str = "{}"
        else:
            state_str = str(state_json)
        point_id = self._uid()
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO rb_points "
                "(point_id, module_id, state_json, description, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (point_id, module_id, state_str, description, now),
            )
            self._conn.commit()
        self._emit("rollback.point_created", {
            "point_id": point_id, "module_id": module_id,
        })
        return {
            "point_id": point_id, "module_id": module_id,
            "state_json": state_str, "description": description,
            "created_at": now,
        }

    def list_points(self, module_id: str | None = None,
                    limit: int = 100) -> list[dict]:
        self._ensure_points_tables()
        with self._lock:
            if module_id:
                rows = self._conn.execute(
                    "SELECT * FROM rb_points WHERE module_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (module_id, int(limit)),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM rb_points "
                    "ORDER BY created_at DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_point(self, point_id: str) -> dict | None:
        self._ensure_points_tables()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rb_points WHERE point_id = ?",
                (point_id,),
            ).fetchone()
        return dict(row) if row else None

    def restore_point(self, point_id: str) -> dict | None:
        point = self.get_point(point_id)
        if point is None:
            return None
        operation_id = self._uid()
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO rb_operations "
                "(operation_id, target_module, from_point, to_point, status, "
                " created_at, started_at, completed_at) "
                "VALUES (?, ?, '', ?, 'completed', ?, ?, ?)",
                (operation_id, point["module_id"], point_id, now, now, now),
            )
            self._conn.commit()
        self._emit("rollback.point_restored", {
            "point_id": point_id, "module_id": point["module_id"],
            "operation_id": operation_id,
        })
        return {
            "point_id": point_id,
            "module_id": point["module_id"],
            "operation_id": operation_id,
            "status": "completed",
            "restored_at": now,
        }

    def create_operation(self, target_module: str, from_point: str,
                         to_point: str) -> dict:
        if not target_module or not from_point or not to_point:
            raise ValueError(
                "target_module, from_point, to_point are all required")
        self._ensure_points_tables()
        operation_id = self._uid()
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO rb_operations "
                "(operation_id, target_module, from_point, to_point, status, "
                " created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                (operation_id, target_module, from_point, to_point, now),
            )
            self._conn.commit()
        return {
            "operation_id": operation_id,
            "target_module": target_module,
            "from_point": from_point,
            "to_point": to_point,
            "status": "pending",
            "created_at": now,
        }

    def list_operations(self, status: str | None = None,
                        limit: int = 100) -> list[dict]:
        self._ensure_points_tables()
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM rb_operations WHERE status = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (status, int(limit)),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM rb_operations "
                    "ORDER BY created_at DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_operation(self, operation_id: str) -> dict | None:
        self._ensure_points_tables()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rb_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if row is None:
                return None
            steps = self._conn.execute(
                "SELECT * FROM rb_op_steps WHERE operation_id = ? "
                "ORDER BY created_at ASC",
                (operation_id,),
            ).fetchall()
        d = dict(row)
        d["steps"] = [dict(s) for s in steps]
        return d

    def execute_operation(self, operation_id: str) -> dict | None:
        self._ensure_points_tables()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rb_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if row is None or row["status"] != "pending":
                return None
            started = time.time()
            self._conn.execute(
                "UPDATE rb_operations SET status = 'running', started_at = ? "
                "WHERE operation_id = ?",
                (started, operation_id),
            )
            completed = time.time()
            self._conn.execute(
                "UPDATE rb_operations SET status = 'completed', "
                "completed_at = ? WHERE operation_id = ?",
                (completed, operation_id),
            )
            self._conn.commit()
        self._emit("rollback.operation_executed", {
            "operation_id": operation_id,
        })
        return {
            "operation_id": operation_id,
            "status": "completed",
            "started_at": started,
            "completed_at": completed,
        }

    def log_step(self, operation_id: str, step: str, status: str,
                 details_json: dict | str | None = None) -> dict:
        if not operation_id or not step or not status:
            raise ValueError("operation_id, step, status are all required")
        self._ensure_points_tables()
        if isinstance(details_json, dict):
            details_str = json.dumps(details_json, default=str)
        elif details_json is None:
            details_str = "{}"
        else:
            details_str = str(details_json)
        step_id = self._uid()
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT operation_id FROM rb_operations "
                "WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Operation '{operation_id}' not found")
            self._conn.execute(
                "INSERT INTO rb_op_steps "
                "(step_id, operation_id, step, status, details_json, "
                " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (step_id, operation_id, step, status, details_str, now),
            )
            self._conn.commit()
        return {
            "step_id": step_id, "operation_id": operation_id,
            "step": step, "status": status,
            "details_json": details_str, "created_at": now,
        }

    def get_rollback_stats(self) -> dict:
        self._ensure_points_tables()
        with self._lock:
            point_count = self._conn.execute(
                "SELECT COUNT(*) AS c FROM rb_points"
            ).fetchone()["c"]
            op_count = self._conn.execute(
                "SELECT COUNT(*) AS c FROM rb_operations"
            ).fetchone()["c"]
            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) AS c FROM rb_operations "
                "GROUP BY status"
            ).fetchall()
            step_count = self._conn.execute(
                "SELECT COUNT(*) AS c FROM rb_op_steps"
            ).fetchone()["c"]
            contract_count = self._conn.execute(
                "SELECT COUNT(*) AS c FROM rollback_contracts"
            ).fetchone()["c"]
        return {
            "total_points": int(point_count),
            "total_operations": int(op_count),
            "total_steps": int(step_count),
            "total_contracts": int(contract_count),
            "operations_by_status": {
                r["status"]: int(r["c"]) for r in status_rows
            },
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: RollbackManager | None = None


def get_rollback_manager(registry: ModuleRegistry | None = None,
                         event_bus: EventBus | None = None,
                         evidence_spine: EvidenceSpine | None = None,
                         db_path: str | Path | None = None) -> RollbackManager:
    global _manager
    if _manager is None:
        _manager = RollbackManager(registry, event_bus, evidence_spine, db_path)
    return _manager
