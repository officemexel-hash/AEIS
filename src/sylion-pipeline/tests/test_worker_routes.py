from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import sylion.api.worker_routes as worker_routes
from sylion.api.app import app
from sylion.worker.registry import reset_worker_registry


client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_worker_surface(tmp_path, monkeypatch):
    monkeypatch.setenv("SYLION_WORKER_DB_PATH", str(tmp_path / "workers.sqlite"))
    reset_worker_registry()
    worker_routes._wr = None
    worker_routes._orch = None
    worker_routes._compact = None
    worker_routes._lifecycle = None
    yield
    reset_worker_registry()
    worker_routes._wr = None
    worker_routes._orch = None
    worker_routes._compact = None
    worker_routes._lifecycle = None


def test_worker_topology_alias_does_not_resolve_as_worker_id():
    response = client.get("/api/v1/workers/topology")

    assert response.status_code == 200
    assert "topologies" in response.json()
    assert response.json() != {"detail": "Worker not found"}


def test_worker_topology_all_still_lists_topologies():
    response = client.get("/api/v1/workers/topology/all")

    assert response.status_code == 200
    assert "topologies" in response.json()


def test_worker_fleet_lifecycle_drill_route_runs_full_flow():
    response = client.post(
        "/api/v1/workers/fleet/lifecycle-drill",
        json={
            "actor_id": "pytest-operator",
            "project_id": "project_worker_route_lifecycle",
        },
    )

    assert response.status_code == 201, response.text
    drill = response.json()
    assert drill["status"] == "completed"
    assert drill["evidence_id"]
    assert drill["payload"]["rebalance"]["moved"] == 1
    assert drill["payload"]["shutdown"]["status"] == "completed"

    listed = client.get("/api/v1/workers/fleet/lifecycle-drills")
    assert listed.status_code == 200
    assert listed.json()["drills"][0]["drill_id"] == drill["drill_id"]

    fetched = client.get(f"/api/v1/workers/fleet/lifecycle-drills/{drill['drill_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["drill_id"] == drill["drill_id"]


def test_worker_graceful_shutdown_route_moves_assignment_to_active_worker():
    primary = client.post(
        "/api/v1/workers",
        json={"name": "primary", "host": "vps-a", "capacity": 1},
    ).json()
    secondary = client.post(
        "/api/v1/workers",
        json={"name": "secondary", "host": "vps-b", "capacity": 2},
    ).json()
    assignment = client.post(
        f"/api/v1/workers/{primary['worker_id']}/assignments",
        json={"module_id": "module.api", "priority": 1},
    )
    assert assignment.status_code == 201

    response = client.post(
        f"/api/v1/workers/{primary['worker_id']}/graceful-shutdown",
        json={"actor_id": "pytest-operator", "reason": "maintenance"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["final_worker"]["status"] == "offline"
    assert body["moved_assignments"][0]["target_worker_id"] == secondary["worker_id"]
    moved = client.get(f"/api/v1/workers/{secondary['worker_id']}/assignments")
    assert moved.status_code == 200
    assert moved.json()["assignments"][0]["module_id"] == "module.api"
