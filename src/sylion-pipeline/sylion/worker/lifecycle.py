"""Worker fleet lifecycle drill with evidence."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.evidence_spine import EvidenceSpine, get_evidence_spine
from sylion.worker.assignment import AssignmentOrchestrator
from sylion.worker.registry import WorkerRegistry, get_worker_registry


def _now() -> float:
    return time.time()


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


class WorkerFleetLifecycle:
    """Runs and records production worker fleet lifecycle operations."""

    def __init__(
        self,
        *,
        registry: WorkerRegistry | None = None,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
        evidence_spine: EvidenceSpine | None = None,
    ) -> None:
        self._registry = registry or get_worker_registry(event_bus=event_bus)
        self._orchestrator = AssignmentOrchestrator(
            worker_registry=self._registry,
            event_bus=event_bus,
        )
        self._event_bus = event_bus
        self._evidence_spine = evidence_spine or get_evidence_spine()
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS worker_fleet_lifecycle_drills (
                drill_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                evidence_id TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                completed_at REAL
            )
        """)
        self._conn.commit()

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if not self._event_bus:
            return
        event = SylionEvent(
            event_id="",
            topic=topic,
            payload=payload,
            source_module="worker.lifecycle",
        )
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(event)
            return
        emit = getattr(self._event_bus, "emit", None)
        if callable(emit):
            emit(event)

    def _evidence(self, payload: dict[str, Any], artifact_type: str) -> str:
        artifact = self._evidence_spine.register_json_artifact(
            payload,
            source="worker.lifecycle",
            artifact_type=artifact_type,
            retention_policy="worker-fleet-freeze",
            metadata={
                "drill_id": payload.get("drill_id", ""),
                "worker_id": payload.get("worker_id", ""),
            },
            actor_id=str(payload.get("actor_id") or "worker-fleet-lifecycle"),
        )
        return str(artifact["evidence_id"])

    def run_lifecycle_drill(
        self,
        *,
        actor_id: str = "operator-dashboard",
        project_id: str = "worker_fleet_drill",
    ) -> dict[str, Any]:
        """Run register -> heartbeat -> rebalance -> shutdown -> evidence."""
        drill_id = _uid("worker_drill")
        started = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO worker_fleet_lifecycle_drills "
                "(drill_id, status, payload_json, created_at, completed_at) "
                "VALUES (?, 'running', '{}', ?, NULL)",
                (drill_id, started),
            )
            self._conn.commit()

        primary = self._registry.register_worker(
            name="external-worker-a",
            host="vps-a.production.local",
            capacity=1,
            tags=["api", "worker-fleet"],
            metadata={
                "project_id": project_id,
                "environment": "production-equivalent",
                "drill_id": drill_id,
            },
        )
        secondary = self._registry.register_worker(
            name="external-worker-b",
            host="vps-b.production.local",
            capacity=3,
            tags=["api", "worker-fleet"],
            metadata={
                "project_id": project_id,
                "environment": "production-equivalent",
                "drill_id": drill_id,
            },
        )
        registrations = [primary, secondary]

        heartbeat_results = []
        for worker in registrations:
            self._registry.heartbeat(
                worker["worker_id"],
                load={"cpu": 0.25, "queue_depth": 0, "drill_id": drill_id},
            )
            heartbeat_results.append(self._registry.get_worker(worker["worker_id"]))

        first_assignment = self._registry.create_assignment(
            primary["worker_id"],
            "module.api",
            priority=1,
            metadata={"drill_id": drill_id},
        )
        second_assignment = self._registry.create_assignment(
            primary["worker_id"],
            "module.worker",
            priority=2,
            metadata={"drill_id": drill_id},
        )
        rebalance = self._orchestrator.rebalance()
        shutdown = self.graceful_shutdown(
            primary["worker_id"],
            reason="worker_fleet_lifecycle_drill",
            actor_id=actor_id,
            drill_id=drill_id,
        )

        payload = {
            "drill_id": drill_id,
            "actor_id": actor_id,
            "project_id": project_id,
            "registrations": registrations,
            "heartbeats": heartbeat_results,
            "initial_assignments": [first_assignment, second_assignment],
            "rebalance": rebalance,
            "shutdown": shutdown,
            "status": "completed",
        }
        evidence_id = self._evidence(payload, "worker_fleet_lifecycle_drill")
        completed = _now()
        with self._lock:
            self._conn.execute(
                "UPDATE worker_fleet_lifecycle_drills "
                "SET status = 'completed', evidence_id = ?, payload_json = ?, completed_at = ? "
                "WHERE drill_id = ?",
                (evidence_id, _canonical_json(payload), completed, drill_id),
            )
            self._conn.commit()
        self._emit("worker_fleet.lifecycle_drill_completed", {
            "drill_id": drill_id,
            "project_id": project_id,
            "evidence_id": evidence_id,
        })
        return self.get_drill(drill_id) or {}

    def graceful_shutdown(
        self,
        worker_id: str,
        *,
        reason: str = "operator_requested",
        actor_id: str = "operator-dashboard",
        drill_id: str = "",
    ) -> dict[str, Any]:
        worker = self._registry.get_worker(worker_id)
        if not worker:
            raise ValueError(f"worker not found: {worker_id}")

        self._registry.update_worker(worker_id, status="draining")
        active_assignments = [
            item for item in self._registry.list_assignments(worker_id=worker_id)
            if item["status"] in {"assigned", "in_progress"}
        ]
        moved: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for assignment in active_assignments:
            target = self._find_target_worker(exclude_worker_id=worker_id)
            if not target:
                metadata = dict(assignment.get("metadata") or {})
                metadata["shutdown_reason"] = reason
                updated = self._registry.update_assignment(
                    assignment["assignment_id"],
                    status="blocked",
                    metadata_json=json.dumps(metadata),
                    error_log="no target worker capacity during graceful shutdown",
                )
                blocked.append(updated or assignment)
                continue
            self._registry.delete_assignment(assignment["assignment_id"])
            replacement = self._registry.create_assignment(
                target["worker_id"],
                assignment["module_id"],
                priority=assignment.get("priority", 5),
                metadata={
                    **(assignment.get("metadata") or {}),
                    "moved_from_worker_id": worker_id,
                    "shutdown_reason": reason,
                },
            )
            moved.append({
                "from_assignment_id": assignment["assignment_id"],
                "to_assignment_id": replacement["assignment_id"],
                "module_id": assignment["module_id"],
                "target_worker_id": target["worker_id"],
            })

        self._registry.update_worker(worker_id, status="offline")
        final_worker = self._registry.get_worker(worker_id)
        payload = {
            "drill_id": drill_id,
            "worker_id": worker_id,
            "actor_id": actor_id,
            "reason": reason,
            "moved_assignments": moved,
            "blocked_assignments": blocked,
            "final_worker": final_worker,
            "status": "completed" if not blocked else "completed_with_blocked_assignments",
        }
        evidence_id = self._evidence(payload, "worker_graceful_shutdown")
        result = {**payload, "evidence_id": evidence_id}
        self._emit("worker_fleet.worker_graceful_shutdown", {
            "worker_id": worker_id,
            "moved": len(moved),
            "blocked": len(blocked),
            "evidence_id": evidence_id,
        })
        return result

    def _find_target_worker(self, *, exclude_worker_id: str) -> dict[str, Any] | None:
        candidates = []
        for worker in self._registry.list_workers(status="active"):
            if worker["worker_id"] == exclude_worker_id:
                continue
            load = len(worker.get("assigned_modules") or [])
            capacity = int(worker.get("capacity") or 1)
            if load < capacity:
                candidates.append((load / max(capacity, 1), worker))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def get_drill(self, drill_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM worker_fleet_lifecycle_drills WHERE drill_id = ?",
                (drill_id,),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload_json"] or "{}")
        return {
            "drill_id": row["drill_id"],
            "status": row["status"],
            "evidence_id": row["evidence_id"],
            "payload": payload,
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    def list_drills(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT drill_id FROM worker_fleet_lifecycle_drills "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get_drill(row["drill_id"]) for row in rows if row["drill_id"]]
