from __future__ import annotations

from sylion.core.evidence_spine import EvidenceSpine
from sylion.worker.lifecycle import WorkerFleetLifecycle
from sylion.worker.registry import WorkerRegistry


def test_lifecycle_drill_records_register_heartbeat_rebalance_shutdown_evidence():
    registry = WorkerRegistry(":memory:")
    lifecycle = WorkerFleetLifecycle(
        registry=registry,
        evidence_spine=EvidenceSpine(":memory:"),
    )

    drill = lifecycle.run_lifecycle_drill(
        actor_id="pytest-operator",
        project_id="project_worker_lifecycle",
    )

    assert drill["status"] == "completed"
    assert drill["evidence_id"]
    payload = drill["payload"]
    assert len(payload["registrations"]) == 2
    assert all(item["last_heartbeat"] for item in payload["heartbeats"])
    assert payload["rebalance"]["moved"] == 1
    assert payload["shutdown"]["status"] == "completed"
    assert payload["shutdown"]["evidence_id"]

    shutdown_worker_id = payload["registrations"][0]["worker_id"]
    shutdown_worker = registry.get_worker(shutdown_worker_id)
    assert shutdown_worker["status"] == "offline"
    assert registry.list_assignments(worker_id=shutdown_worker_id) == []

    active_workers = registry.list_workers(status="active")
    assert len(active_workers) == 1
    active_assignments = registry.list_assignments(worker_id=active_workers[0]["worker_id"])
    assert {item["module_id"] for item in active_assignments} == {"module.api", "module.worker"}


def test_graceful_shutdown_blocks_assignment_when_no_target_capacity():
    registry = WorkerRegistry(":memory:")
    lifecycle = WorkerFleetLifecycle(
        registry=registry,
        evidence_spine=EvidenceSpine(":memory:"),
    )
    worker = registry.register_worker(name="solo", host="vps-a", capacity=1)
    assignment = registry.create_assignment(worker["worker_id"], "module.api")

    result = lifecycle.graceful_shutdown(worker["worker_id"], reason="solo_shutdown")

    assert result["status"] == "completed_with_blocked_assignments"
    assert result["blocked_assignments"][0]["assignment_id"] == assignment["assignment_id"]
    assert result["final_worker"]["status"] == "offline"
    blocked = registry.get_assignment(assignment["assignment_id"])
    assert blocked["status"] == "blocked"
    assert blocked["metadata"]["shutdown_reason"] == "solo_shutdown"
