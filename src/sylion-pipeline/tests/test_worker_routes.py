from __future__ import annotations

from fastapi.testclient import TestClient

from sylion.api.app import app


client = TestClient(app)


def test_worker_topology_alias_does_not_resolve_as_worker_id():
    response = client.get("/api/v1/workers/topology")

    assert response.status_code == 200
    assert "topologies" in response.json()
    assert response.json() != {"detail": "Worker not found"}


def test_worker_topology_all_still_lists_topologies():
    response = client.get("/api/v1/workers/topology/all")

    assert response.status_code == 200
    assert "topologies" in response.json()
