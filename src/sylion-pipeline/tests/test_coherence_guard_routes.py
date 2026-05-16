from __future__ import annotations

from fastapi.testclient import TestClient

from sylion.api.app import app


client = TestClient(app)
BASE = "/api/v1/coherence-guard"


def test_phase6_snapshot_covers_full_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase6.db"))

    response = client.get(BASE)

    assert response.status_code == 200
    data = response.json()
    assert data["phase"] == "6"
    assert len(data["templates"]["scope"]) == 4
    assert len(data["templates"]["cross_project_scope"]) == 5
    assert len(data["templates"]["severities"]) == 5
    assert len(data["templates"]["detection_tiers"]) == 2
    assert len(data["templates"]["baseline_checks"]) == 15
    assert len(data["templates"]["edge_cases"]) == 22
    assert len(data["templates"]["aggregated_guards"]) == 5
    assert data["acceptance"]["accepted"] is False


def test_apply_defaults_makes_phase6_acceptable(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase6.db"))

    applied = client.post(BASE + "/defaults/apply", json={"goal": "apps_internal", "autonomy_preset": "balanced"})

    assert applied.status_code == 200
    snapshot = applied.json()
    assert snapshot["settings"]["scope_configured"] is True
    assert snapshot["settings"]["triggers_configured"] is True
    assert snapshot["settings"]["severity_thresholds_reviewed"] is True
    assert snapshot["settings"]["baseline_checks_reviewed"] is True
    assert len(snapshot["settings"]["reviewed_check_ids"]) == 15

    acceptance = client.get(BASE + "/acceptance-test?goal=apps_internal")
    assert acceptance.status_code == 200
    data = acceptance.json()
    assert data["accepted"] is True
    assert data["audit_chain"]["phase_6_complete"] is True
    assert data["dod"]["common"]["passed"] == data["dod"]["common"]["required"]
    assert data["dod"]["performance"]["passed"] == data["dod"]["performance"]["required"]


def test_scope_triggers_custom_check_run_and_findings_panel(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase6.db"))
    client.post(BASE + "/defaults/apply", json={"goal": "apps_internal", "autonomy_preset": "balanced"})

    scope = client.post(
        BASE + "/scope",
        json={
            "scope": {"documents": True, "code": True, "tests": True, "deployment": True},
            "cross_project_enabled": False,
            "project_count": 1,
        },
    )
    assert scope.status_code == 200
    assert scope.json()["snapshot"]["settings"]["scope_configured"] is True

    triggers = client.post(
        BASE + "/triggers",
        json={
            "phase_boundaries": {"enabled": True, "critical_phases": [25, 28, 29, 35, 37, 39, 41]},
            "continuous": {"enabled": True, "throttle_per_file_seconds": 60, "batch_window_seconds": 5},
            "on_demand": {"enabled": True, "default_depth": "standard"},
        },
    )
    assert triggers.status_code == 200
    assert triggers.json()["triggers"]["continuous"]["batch_window_seconds"] == 5

    custom = client.post(
        BASE + "/custom-checks",
        json={
            "name": "Customer email before phone",
            "mechanism": "dsl",
            "definition": "FOR EACH form IN frontend.forms IF email BEFORE phone THEN flag",
            "severity": "WARNING",
            "tier": "tier1",
        },
    )
    assert custom.status_code == 200
    assert custom.json()["custom_check"]["source"] == "operator_custom"

    run = client.post(
        BASE + "/run",
        json={"depth": "standard", "scope": ["documents", "code", "tests", "deployment"], "project_id": "sample_project"},
    )
    assert run.status_code == 200
    run_data = run.json()
    assert run_data["run"]["findings_created"] >= 3
    assert run_data["aggregated_panel"]["total_active_findings"] >= 3
    assert run_data["aggregated_panel"]["conflicts"]

    findings = client.get(BASE + "/findings?status=active")
    assert findings.status_code == 200
    active = findings.json()["findings"]
    assert len(active) >= 3
    auto_fixable = next(item for item in active if item["can_auto_fix"])
    action = client.post(
        f"{BASE}/findings/{auto_fixable['id']}/action",
        json={"action": "apply_fix", "note": "safe deterministic locale coverage fix"},
    )
    assert action.status_code == 200
    assert action.json()["finding"]["status"] == "resolved"


def test_dashboard_run_does_not_emit_sample_findings(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase6.db"))
    client.post(BASE + "/defaults/apply", json={"goal": "apps_internal", "autonomy_preset": "balanced"})

    run = client.post(
        BASE + "/run",
        json={"depth": "standard", "scope": ["documents", "code", "tests", "deployment"], "project_id": "dashboard_current"},
    )
    assert run.status_code == 200
    findings = run.json()["findings"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "INFO"
    assert findings[0]["title"] == "Brak syntetycznych ustaleń w przebiegu dashboardu"
    assert "Frontend sample uses items" not in findings[0]["summary"]


def test_performance_autonomy_override_and_edge_diagnosis(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase6.db"))
    client.post(BASE + "/defaults/apply", json={"goal": "apps_internal", "autonomy_preset": "balanced"})

    performance = client.post(
        BASE + "/performance",
        json={
            "worker_enabled": True,
            "worker_status": "running",
            "cache_initialized": True,
            "cache_hit_rate_pct": 82,
            "monthly_budget_usd": 30,
            "used_monthly_usd": 12,
            "budget_cap_enabled": True,
            "budget_share_pct": 5,
            "incremental_diff": True,
        },
    )
    assert performance.status_code == 200
    assert performance.json()["performance"]["cache_hit_rate_pct"] == 82

    override = client.post(
        BASE + "/autonomy-override",
        json={
            "inherits_phase5": True,
            "preset": "production",
            "auto_fix_tier1": False,
            "auto_fix_tier2": False,
            "per_check_customization": True,
            "operator_note": "production-safe guard behavior",
        },
    )
    assert override.status_code == 200
    assert override.json()["autonomy_override"]["preset"] == "production"

    edge_cases = client.get(BASE + "/edge-cases")
    assert edge_cases.status_code == 200
    assert edge_cases.json()["count"] == 22
    assert {"false_positive", "performance", "custom_checks", "findings_handling", "recovery_migration"} <= set(edge_cases.json()["categories"])

    diagnosis = client.post(
        BASE + "/edge-cases/diagnose",
        json={"case_id": "EC-D3", "context": {"coherence": "API mismatch", "quality": "tests pass"}},
    )
    assert diagnosis.status_code == 200
    assert diagnosis.json()["requires_operator_review"] is True


def test_hard_blocks_prevent_phase6_completion(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase6.db"))
    client.post(BASE + "/defaults/apply", json={"goal": "apps_internal", "autonomy_preset": "balanced"})

    baseline = client.get(BASE).json()["templates"]["baseline_checks"]
    disabled_ids = [item["id"] for item in baseline]
    reviewed = client.post(
        BASE + "/checks/review",
        json={
            "reviewed_check_ids": disabled_ids,
            "disabled_check_ids": disabled_ids,
            "accepted_baseline": True,
            "custom_checks_not_needed": True,
        },
    )
    assert reviewed.status_code == 200

    acceptance = client.get(BASE + "/acceptance-test?goal=apps_internal")
    assert acceptance.status_code == 200
    data = acceptance.json()
    assert data["accepted"] is False
    assert any(item["id"] == "hard_all_baseline_disabled" for item in data["hard_blocks"])

    complete = client.post(BASE + "/complete?goal=apps_internal")
    assert complete.status_code == 400
