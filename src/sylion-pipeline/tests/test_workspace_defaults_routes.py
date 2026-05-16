from __future__ import annotations

from fastapi.testclient import TestClient

from sylion.api.app import app


client = TestClient(app)
BASE = "/api/v1/workspace-defaults"


def test_workspace_defaults_snapshot_covers_phase4_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase4.db"))

    response = client.get(BASE)

    assert response.status_code == 200
    data = response.json()
    assert data["phase"] == "4"
    assert len(data["wizard"]["steps"]) == 9
    assert len(data["settings"]["budget_templates"]) == 4
    assert len(data["templates"]["autonomy_presets"]) == 5
    assert len(data["templates"]["cleanup_defaults"]) == 10
    assert len(data["templates"]["edge_cases"]) == 25
    assert data["settings"]["test_strategy"]["human_like_required"] is True


def test_workspace_defaults_apply_and_acceptance(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase4.db"))

    apply_response = client.post(f"{BASE}/smart-defaults/apply")
    assert apply_response.status_code == 200

    step_response = client.post(f"{BASE}/wizard/step", json={"step": 2, "values": {"budget": "reviewed"}})
    assert step_response.status_code == 200
    assert 2 in step_response.json()["wizard"]["completed_steps"]

    acceptance = client.get(f"{BASE}/acceptance-test?goal=apps_internal")
    assert acceptance.status_code == 200
    data = acceptance.json()
    assert data["accepted"] is True
    assert data["audit_chain"]["phase_4_complete"] is True
    assert data["dod"]["common"]["passed"] == data["dod"]["common"]["required"]


def test_budget_estimation_and_custom_template(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase4.db"))
    client.post(f"{BASE}/smart-defaults/apply")

    custom = client.post(
        f"{BASE}/budgets/templates",
        json={
            "id": "customer_pilot",
            "name": "Customer pilot",
            "cap_usd": 150,
            "description": "One month customer pilot",
            "auto_apply_when": {"project_type": ["pilot"]},
            "typical_breakdown": {"llm_calls": 40, "cloud_resources": 40, "buffer": 20},
        },
    )
    assert custom.status_code == 200
    assert any(item["id"] == "customer_pilot" for item in custom.json()["budget_templates"])

    estimate = client.post(
        f"{BASE}/budgets/estimate",
        json={"project_type": "customer_facing_saas", "d_level": 4, "goal": "public_products", "build_phases": 18, "council_rounds": 3, "human_like_scenarios": 8},
    )
    assert estimate.status_code == 200
    data = estimate.json()
    assert data["suggested_template"] == "large"
    assert data["recommended_budget_usd"] > 0
    assert "build_orchestration" in data["breakdown"]


def test_notifications_mobile_and_goal_specific_acceptance(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase4.db"))
    client.post(f"{BASE}/smart-defaults/apply")

    mobile = client.post(
        f"{BASE}/mobile/pair",
        json={
            "pairing_code": "123456",
            "auth_method": "pin",
            "permissions": ["receive_notifications", "view_project_status", "approve_hard_gates", "approve_cost_overruns"],
        },
    )
    assert mobile.status_code == 200
    assert mobile.json()["mobile"]["paired"] is True
    assert mobile.json()["mobile"]["verified_push"] is True

    mapping = client.post(f"{BASE}/autonomy/mapping", json={"goal": "cybersecurity", "preset": "conservative"})
    assert mapping.status_code == 200

    acceptance = client.get(f"{BASE}/acceptance-test?goal=public_products")
    assert acceptance.status_code == 200
    data = acceptance.json()
    assert data["accepted"] is True
    check_ids = {item["id"] for item in data["checks"]}
    assert "public_production_budget" in check_ids
    assert "mobile_pairing_verified" in check_ids


def test_edge_cases_and_inheritance_preview(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase4.db"))
    client.post(f"{BASE}/smart-defaults/apply")

    cases = client.get(f"{BASE}/edge-cases")
    assert cases.status_code == 200
    assert cases.json()["count"] == 25
    assert {"configuration_conflicts", "mobile_companion", "wizard_setup", "smart_defaults", "recovery_integrity"} <= set(cases.json()["categories"])

    diagnosis = client.post(f"{BASE}/edge-cases/diagnose", json={"case_id": "EC-A2", "context": {"template": "small"}})
    assert diagnosis.status_code == 200
    assert diagnosis.json()["requires_operator_review"] is True

    preview = client.post(
        f"{BASE}/inheritance/preview",
        json={"goal": "public_products", "d_level": 4, "project_type": "customer_facing_saas"},
    )
    assert preview.status_code == 200
    data = preview.json()
    assert data["resolved"]["budget_template"] == "large"
    assert data["resolved"]["autonomy_preset"] == "production"
    assert "UX Designer" in data["resolved"]["council_roles"]
