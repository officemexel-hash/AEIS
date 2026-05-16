from __future__ import annotations

from fastapi.testclient import TestClient

from sylion.api.app import app


client = TestClient(app)
BASE = "/api/v1/templates-setup"


def _apply_defaults(phase_id: str):
    response = client.post(f"{BASE}/{phase_id}/defaults/apply", json={"operator_id": "operator", "goal": "apps_internal"})
    assert response.status_code == 200
    return response.json()


def _accept(phase_id: str, phase: str):
    response = client.get(f"{BASE}/{phase_id}/acceptance-test")
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] is True
    assert data["hard_blocks"] == []
    assert data["audit_chain"][f"phase_{phase}_complete"] is True
    return data


def test_templates_setup_overview_and_edge_case_total(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "templates_overview.db"))

    response = client.get(BASE)

    assert response.status_code == 200
    data = response.json()
    assert len(data["phases"]) == 5
    assert data["group"]["edge_cases"] == 80
    assert {item["phase"] for item in data["phases"]} == {"11", "12", "13", "14", "15"}


def test_phase11_skills_bootstrap_registry_and_acceptance(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase11.db"))

    snapshot = client.get(f"{BASE}/skills").json()

    assert snapshot["phase"] == "11"
    assert len(snapshot["templates"]["artifacts"]) == 25
    assert len(snapshot["templates"]["edge_cases"]) == 20
    assert len(snapshot["templates"]["capabilities"]) == 5
    assert snapshot["acceptance"]["accepted"] is False

    applied = _apply_defaults("skills")
    assert applied["settings"]["flags"]["system_skills_available"] is True
    assert applied["settings"]["registry_stats"]["total_skills"] >= 25
    assert applied["settings"]["executor_stats"]["total_executions"] >= 1

    skills = client.get("/api/v1/skills/skills?lifecycle=PUBLISHED&limit=200")
    assert skills.status_code == 200
    assert len(skills.json()["skills"]) >= 25

    accepted = _accept("skills", "11")
    assert accepted["dod"]["passed_required"] == accepted["dod"]["required"]


def test_phase12_council_templates_custom_simulation_and_acceptance(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase12.db"))

    snapshot = client.get(f"{BASE}/council").json()

    assert snapshot["phase"] == "12"
    assert len(snapshot["templates"]["artifacts"]) == 8
    assert len(snapshot["templates"]["edge_cases"]) == 15

    _apply_defaults("council")

    custom = client.post(f"{BASE}/council/custom-artifacts", json={"name": "Polish accessibility council", "category": "accessibility"})
    assert custom.status_code == 200
    assert custom.json()["artifact"]["source"] == "custom"

    simulation = client.post(f"{BASE}/council/simulate", json={"project_type": "public_saas", "d_level": 4, "customer_specific": False})
    assert simulation.status_code == 200
    assert simulation.json()["simulation"]["recommendation"]["id"].startswith("ct_")

    accepted = _accept("council", "12")
    assert accepted["dod"]["passed_required"] == accepted["dod"]["required"]


def test_phase13_test_strategy_preserves_human_like_and_blocks_missing_baseline(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase13.db"))

    snapshot = client.get(f"{BASE}/test-strategy").json()

    assert snapshot["phase"] == "13"
    assert len(snapshot["templates"]["artifacts"]) == 5
    assert len(snapshot["templates"]["edge_cases"]) == 15
    assert all(any(str(level).startswith("L5") for level in item["levels"]) for item in snapshot["templates"]["artifacts"])

    _apply_defaults("test-strategy")
    accepted = _accept("test-strategy", "13")
    assert accepted["dod"]["passed_required"] == accepted["dod"]["required"]

    artifact_ids = [item["id"] for item in snapshot["templates"]["artifacts"]]
    reviewed = client.post(
        f"{BASE}/test-strategy/review",
        json={"accepted_artifact_ids": artifact_ids, "disabled_artifact_ids": artifact_ids[:1]},
    )
    assert reviewed.status_code == 200
    blocked = client.get(f"{BASE}/test-strategy/acceptance-test").json()
    assert blocked["accepted"] is False
    assert any(item["id"] == "baseline_missing" for item in blocked["hard_blocks"])


def test_phase14_deployment_templates_acceptance(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase14.db"))

    snapshot = client.get(f"{BASE}/deployment").json()

    assert snapshot["phase"] == "14"
    assert len(snapshot["templates"]["artifacts"]) == 6
    assert len(snapshot["templates"]["edge_cases"]) == 15
    assert any(item["id"] == "dt_canary" for item in snapshot["templates"]["artifacts"])

    _apply_defaults("deployment")
    simulation = client.post(f"{BASE}/deployment/simulate", json={"project_type": "customer_facing", "d_level": 4})
    assert simulation.status_code == 200
    assert simulation.json()["simulation"]["recommendation"]["id"] == "dt_canary"
    _accept("deployment", "14")


def test_phase15_cost_policies_customer_specific_acceptance(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase15.db"))

    snapshot = client.get(f"{BASE}/cost-policies").json()

    assert snapshot["phase"] == "15"
    assert len(snapshot["templates"]["artifacts"]) == 5
    assert len(snapshot["templates"]["edge_cases"]) == 15
    assert any(item["id"] == "cp_strict_customer" for item in snapshot["templates"]["artifacts"])

    applied = _apply_defaults("cost-policies")
    assert applied["settings"]["customer_policy"]["per_project_cap_eur"] == 500

    simulation = client.post(f"{BASE}/cost-policies/simulate", json={"project_type": "customer_funded", "d_level": 3, "customer_specific": True})
    assert simulation.status_code == 200
    assert simulation.json()["simulation"]["recommendation"]["id"] == "cp_strict_customer"
    _accept("cost-policies", "15")
