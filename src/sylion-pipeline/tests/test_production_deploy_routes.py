from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sylion.api.app import app
from sylion.governance.tickets import (
    clear_post_resolve_hooks,
    reset_ticket_store,
    resolve,
)
from sylion.ops.production_deploy_pipeline import reset_production_deploy_pipeline


ARTIFACT_SHA = "c" * 64
PREVIOUS_SHA = "d" * 64


@pytest.fixture(autouse=True)
def _reset_surface(tmp_path, monkeypatch):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "aeis.sqlite"))
    reset_ticket_store()
    clear_post_resolve_hooks()
    reset_production_deploy_pipeline(str(tmp_path / "aeis.sqlite"))
    yield
    reset_production_deploy_pipeline()
    reset_ticket_store()
    clear_post_resolve_hooks()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _payload(**overrides):
    data = {
        "project_id": "project_prod_route_smoke",
        "artifact_sha256": ARTIFACT_SHA,
        "previous_artifact_sha256": PREVIOUS_SHA,
        "release_version": "2026.05.18.1",
        "target_environment": "production",
        "scan_report": {
            "scanner": "trivy",
            "critical": 0,
            "high": 0,
        },
        "smoke_report": {
            "golden_tests_passed": True,
            "healthcheck_passed": True,
            "p99_ms": 160,
            "p99_target_ms": 500,
        },
        "operator_probe": {
            "healthcheck_passed": True,
            "operator_probe_passed": True,
            "error_rate": 0.0,
        },
    }
    data.update(overrides)
    return data


def _approve(ticket_id: str, reason: str) -> None:
    assert resolve(
        ticket_id,
        "approved",
        reason=reason,
        reviewer="operator@example.com",
    ) is True


def _approved_run(client: TestClient) -> dict:
    blocked = client.post("/api/v1/production-deploy/pipeline/run", json=_payload())
    assert blocked.status_code == 423
    ticket_id = blocked.json()["detail"]["governance_ticket_id"]
    _approve(ticket_id, "Approve production deploy pipeline.")

    created = client.post(
        "/api/v1/production-deploy/pipeline/run",
        json=_payload(approval_ticket_id=ticket_id),
    )
    assert created.status_code == 201, created.text
    return created.json()["run"]


def test_run_pipeline_requires_human_gate_and_then_records_full_run(client):
    run = _approved_run(client)

    assert run["status"] == "completed"
    assert len(run["stages"]) == 7
    assert run["rollbacks"][0]["details"]["drill"] is True
    assert run["current_live_sha256"] == ARTIFACT_SHA

    fetched = client.get(f"/api/v1/production-deploy/pipeline/{run['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["run"]["run_id"] == run["run_id"]

    listed = client.get("/api/v1/production-deploy/pipelines?project_id=project_prod_route_smoke")
    assert listed.status_code == 200
    assert listed.json()["runs"][0]["run_id"] == run["run_id"]


def test_actual_rollback_requires_human_gate_and_restores_previous_artifact(client):
    run = _approved_run(client)

    blocked = client.post(
        f"/api/v1/production-deploy/pipeline/{run['run_id']}/rollback",
        json={"reason": "operator rollback drill became real"},
    )
    assert blocked.status_code == 423
    ticket_id = blocked.json()["detail"]["governance_ticket_id"]
    _approve(ticket_id, "Approve production rollback.")

    rolled = client.post(
        f"/api/v1/production-deploy/pipeline/{run['run_id']}/rollback",
        json={
            "approval_ticket_id": ticket_id,
            "reason": "operator rollback drill became real",
        },
    )
    assert rolled.status_code == 200, rolled.text
    body = rolled.json()
    assert body["run"]["status"] == "rolled_back"
    assert body["run"]["current_live_sha256"] == PREVIOUS_SHA
    assert body["rollback"]["restored_artifact_sha256"] == PREVIOUS_SHA


def test_rollback_test_endpoint_adds_drill_without_changing_live_artifact(client):
    run = _approved_run(client)
    first_drill_count = len(run["rollbacks"])

    response = client.post(
        f"/api/v1/production-deploy/pipeline/{run['run_id']}/rollback-test",
        json={"reason": "repeat rollback drill"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rollback"]["details"]["drill"] is True
    assert body["run"]["current_live_sha256"] == ARTIFACT_SHA
    assert len(body["run"]["rollbacks"]) == first_drill_count + 1
