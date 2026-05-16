from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from sylion.api.guard_suite_routes import router


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "guards.db"))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_list_guards_returns_catalog_and_panel(client: TestClient) -> None:
    response = client.get("/api/v1/guards")

    assert response.status_code == 200
    payload = response.json()
    guard_ids = {item["id"] for item in payload["guards"]}
    assert {"cost", "security", "quality", "provenance"}.issubset(guard_ids)
    assert len(payload["aggregated_panel"]["guards"]) >= 5


def test_apply_defaults_review_run_and_resolve_finding(client: TestClient) -> None:
    defaults = client.post(
        "/api/v1/guards/quality/defaults/apply",
        json={"goal": "apps_internal", "autonomy_preset": "balanced"},
    )
    assert defaults.status_code == 200
    snapshot = defaults.json()
    assert snapshot["guard_id"] == "quality"
    assert snapshot["settings"]["flags"]["baseline_reviewed"] is True

    checks = list(snapshot["settings"]["checks"])[:2]
    review = client.post(
        "/api/v1/guards/quality/review",
        json={"reviewed_check_ids": checks, "disabled_check_ids": [], "accepted_baseline": True},
    )
    assert review.status_code == 200
    assert review.json()["snapshot"]["guard_id"] == "quality"

    run = client.post(
        "/api/v1/guards/quality/run",
        json={"depth": "quick", "project_id": "coverage-baseline"},
    )
    assert run.status_code == 200
    run_payload = run.json()
    assert run_payload["run"]["findings_created"] >= 1
    finding_id = run_payload["findings"][0]["id"]

    listed = client.get("/api/v1/guards/quality/findings", params={"status": "active"})
    assert listed.status_code == 200
    assert any(item["id"] == finding_id for item in listed.json()["findings"])

    action = client.post(
        f"/api/v1/guards/quality/findings/{finding_id}/action",
        json={"action": "resolve", "note": "covered by R3.16 baseline repair"},
    )
    assert action.status_code == 200
    assert action.json()["finding"]["status"] == "resolved"


def test_guard_suite_rejects_invalid_inputs(client: TestClient) -> None:
    missing = client.get("/api/v1/guards/not-a-guard")
    assert missing.status_code == 404

    bad_preset = client.post(
        "/api/v1/guards/cost/defaults/apply",
        json={"goal": "apps_internal", "autonomy_preset": "reckless"},
    )
    assert bad_preset.status_code == 400

    bad_scope = client.post(
        "/api/v1/guards/cost/config",
        json={"scope": {"unknown_scope": True}, "flags": {}, "feature_overrides": {}},
    )
    assert bad_scope.status_code == 400


def test_edge_case_diagnosis_and_acceptance_contract(client: TestClient) -> None:
    edge_cases = client.get("/api/v1/guards/security/edge-cases")
    assert edge_cases.status_code == 200
    first_case = edge_cases.json()["edge_cases"][0]

    diagnosis = client.post(
        "/api/v1/guards/security/edge-cases/diagnose",
        json={"case_id": first_case["id"], "context": {"source": "coverage-baseline"}},
    )
    assert diagnosis.status_code == 200
    assert diagnosis.json()["case"]["id"] == first_case["id"]
    assert "write phase" in diagnosis.json()["action_plan"][-1]

    acceptance = client.get("/api/v1/guards/security/acceptance-test")
    assert acceptance.status_code == 200
    payload = acceptance.json()
    assert payload["guard_id"] == "security"
    assert "hard_blocks" in payload
