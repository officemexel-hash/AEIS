from __future__ import annotations

from sylion.api import advisor_routes as routes


def _passing_phase1_state(workspace_path: str) -> dict:
    return {
        "step": 8,
        "completed_steps": list(range(1, 9)),
        "values": {
            "operator_name": "Operator Test",
            "display_name": "Operator Test",
            "system_name": "operator.test",
            "operator_role": "solo",
            "timezone": "Europe/Warsaw",
            "timezone_confirmed": True,
            "email_skipped": True,
            "workspace_path": workspace_path,
            "storage_validation": {"ok": True, "errors": []},
            "security_mode": "low_security",
            "low_security_confirm": "ROZUMIEM",
            "goals": ["apps_internal"],
            "initial_autonomy_preset": "balanced",
            "tutorial_mode": "standard",
            "tutorial_project": "local_crm",
            "local_models": [{"name": "qwen2.5:7b-instruct", "status": "installed"}],
            "notification_channel": "in_app",
            "telemetry_consent": False,
        },
    }


def test_phase1_acceptance_recovers_exit_state_from_audit_chain(monkeypatch, tmp_path):
    chain_path = tmp_path / "onboarding.jsonl"
    workspace = tmp_path / "operator.test"
    for folder in routes._PHASE1_WORKSPACE_FOLDERS:
        (workspace / folder).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(routes, "resolve_audit_chain_path", lambda _name: chain_path)
    for step in range(1, 9):
        routes._emit_phase1_chain("operator", f"phase_1.step_{step}.complete", {"step": step})
    routes._emit_phase1_chain("operator", "phase_1.complete", {"workspace_path": str(workspace)})

    report = routes._phase1_acceptance_report("operator", _passing_phase1_state(str(workspace)))

    assert report["accepted"] is True
    exit_state = next(check for check in report["checks"] if check["key"] == "exit_state")
    assert exit_state["ok"] is True
    assert exit_state["detail"]["audit_completed"] is True
