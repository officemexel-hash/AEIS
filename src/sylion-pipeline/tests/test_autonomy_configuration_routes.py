from __future__ import annotations

from fastapi.testclient import TestClient

from sylion.api.app import app


client = TestClient(app)
BASE = "/api/v1/autonomy/configuration"


def test_phase5_snapshot_covers_full_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase5.db"))

    response = client.get(BASE)

    assert response.status_code == 200
    data = response.json()
    assert data["phase"] == "5"
    assert len(data["templates"]["dimensions"]) == 10
    assert len(data["templates"]["levels"]) == 6
    assert len(data["settings"]["hard_gates"]) == 18
    assert len(data["templates"]["edge_cases"]) == 22
    assert len(data["templates"]["override_scopes"]) == 6
    assert data["acceptance"]["accepted"] is False


def test_apply_phase4_preset_makes_phase5_acceptable(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase5.db"))

    applied = client.post(BASE + "/apply-preset", json={"goal": "apps_internal", "mode": "quick"})
    assert applied.status_code == 200
    snapshot = applied.json()
    assert snapshot["settings"]["selected_preset"] == "balanced"
    assert snapshot["settings"]["operator_understood_dimensions"] is True
    assert snapshot["settings"]["hard_gates_reviewed"] is True
    assert len(snapshot["settings"]["inheritance_traces"]) == 1

    acceptance = client.get(BASE + "/acceptance-test?goal=apps_internal")
    assert acceptance.status_code == 200
    data = acceptance.json()
    assert data["accepted"] is True
    assert data["audit_chain"]["phase_5_complete"] is True
    assert data["dod"]["common"]["passed"] == data["dod"]["common"]["required"]


def test_dimension_custom_gate_override_and_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase5.db"))
    client.post(BASE + "/apply-preset", json={"goal": "apps_internal", "mode": "quick"})

    dim = client.post(
        BASE + "/dimensions",
        json={
            "dimension_id": "cost_decisions",
            "level": "L4",
            "settings": {"requires_budget_cap": True, "budget_switch_threshold_pct": 60},
            "reason": "volume internal builds",
        },
    )
    assert dim.status_code == 200
    assert dim.json()["dimension"]["level"] == "L4"

    d_level = client.post(
        BASE + "/d-level-overrides",
        json={
            "dimension_id": "quality_verdicts",
            "enabled": True,
            "overrides": {"D1": "L4", "D2": "L3", "D3": "L2", "D4": "L1", "D5": "L0"},
        },
    )
    assert d_level.status_code == 200
    assert d_level.json()["dimension"]["d_level_adaptive"]["D5"] == "L0"

    custom = client.post(
        BASE + "/hard-gates/custom",
        json={
            "label": "Email blast over 100 customers",
            "condition": "email_recipients > 100",
            "dimension_lock": "cascade_re_evaluation",
        },
    )
    assert custom.status_code == 200
    assert custom.json()["gate"]["source"] == "operator_custom"

    override = client.post(
        BASE + "/overrides",
        json={
            "dimension_id": "cost_decisions",
            "level": "L4",
            "scope": "per_build",
            "reason": "cheaper model experiment",
            "project_id": "sample_project",
            "expires_in_hours": 5,
        },
    )
    assert override.status_code == 200
    assert override.json()["override"]["status"] == "active"

    trace = client.post(
        BASE + "/inheritance/trace",
        json={"dimension_id": "cost_decisions", "goal": "apps_internal", "d_level": "D3", "project_id": "sample_project"},
    )
    assert trace.status_code == 200
    data = trace.json()
    assert data["effective_level"] == "L4"
    assert [item["scope"] for item in data["trace"]][:2] == ["phase4_default", "phase5_workspace"]


def test_goal_specific_acceptance(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase5.db"))

    for goal, preset in [("public_products", "production"), ("cybersecurity", "conservative"), ("research", "research")]:
        applied = client.post(BASE + "/apply-preset", json={"goal": goal, "preset": preset, "mode": "quick"})
        assert applied.status_code == 200
        acceptance = client.get(f"{BASE}/acceptance-test?goal={goal}")
        assert acceptance.status_code == 200
        data = acceptance.json()
        assert data["accepted"] is True
        assert not data["hard_blocks"]


def test_edge_cases_and_gate_safety(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase5.db"))
    client.post(BASE + "/apply-preset", json={"goal": "public_products", "preset": "production", "mode": "quick"})

    cases = client.get(BASE + "/edge-cases")
    assert cases.status_code == 200
    assert cases.json()["count"] == 22
    assert {"hard_gate", "dimension_config", "wizard_setup", "recovery_migration"} <= set(cases.json()["categories"])

    diagnosis = client.post(BASE + "/edge-cases/diagnose", json={"case_id": "EC-C4", "context": {"dim3": "L0", "dim4": "L5"}})
    assert diagnosis.status_code == 200
    assert diagnosis.json()["requires_operator_review"] is True

    client.post(BASE + "/dimensions", json={"dimension_id": "deploy_authorization", "level": "L5"})
    blocked = client.post(BASE + "/hard-gates/deploy_production/toggle", json={"enabled": False, "reason": "debug"})
    assert blocked.status_code == 409
