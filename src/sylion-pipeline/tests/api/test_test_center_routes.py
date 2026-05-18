"""Smoke + contract tests for /api/v1/test-center/* aggregator routes.

Covers the E8/E9/E12 catch-up endpoints added so the Test Center UI
no longer depends on hardcoded JS constants:

  - personas      : full 15-persona catalog
  - scenarios     : full 50-scenario catalog (10 domains x 5)
  - dashboard     : charters/findings/runs roll-up
  - truth-alignment: matrix + summary
  - simulation    : sim_branch listing
  - auto-repair   : R0-R9 sessions + Loop Governor budget
  - release-gate  : 12+6 checklist + status
  - catalog       : T0-T19 with run counts

Plus a WS smoke test for /ws/agent-theater verifying the snapshot
shape and ping/pong round-trip.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from sylion.api.app import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Personas + scenarios catalog
# ---------------------------------------------------------------------------


def test_personas_returns_full_catalog(client):
    r = client.get("/api/v1/test-center/personas")
    assert r.status_code == 200
    body = r.json()
    assert body["total_canonical"] == 15
    assert body["starter_count"] == 4
    assert body["extended_count"] == 11
    # When the store is freshly initialized the starters auto-load.
    assert body["loaded_count"] == 15
    # Every loaded persona must carry the canonical fields the UI reads.
    for p in body["personas"]:
        assert "name" in p
        assert "capability_level" in p
        assert "error_proneness" in p
        assert p["capability_level"] in ("beginner", "intermediate", "expert")


def test_scenarios_full_catalog_is_50(client):
    r = client.get("/api/v1/test-center/scenarios")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 50
    # 10 canonical domains
    assert len(body["domains_canonical"]) == 10
    # Each scenario must reference a persona_*-prefixed id (or original
    # human-readable persona name accepted by the registry).
    for s in body["scenarios"]:
        assert "persona_id" in s
        assert "domain" in s
        assert s["domain"] in body["domains_canonical"]


def test_scenarios_filtered_by_domain(client):
    r = client.get("/api/v1/test-center/scenarios?domain=hmep")
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "hmep"
    assert body["total"] == 5
    assert all(s["domain"] == "hmep" for s in body["scenarios"])


def test_scenarios_rejects_unknown_domain(client):
    r = client.get("/api/v1/test-center/scenarios?domain=does_not_exist")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Dashboard / truth-alignment / simulation / auto-repair / catalog
# ---------------------------------------------------------------------------


def test_dashboard_returns_summary_shape(client):
    r = client.get("/api/v1/test-center/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert "charters" in body
    assert "findings" in body
    assert "recent_runs" in body
    assert {"total", "approved", "in_review"}.issubset(body["charters"])
    assert {"total", "by_severity", "by_status", "open_p0_p1"}.issubset(
        body["findings"]
    )


def test_no_mock_scan_endpoint_returns_release_safety_shape(client):
    r = client.get("/api/v1/test-center/no-mock-scan")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"PASS", "FAIL"}
    assert body["scanned_files"] > 0
    assert {"issue_count", "blocking_count", "issues", "rules"}.issubset(body)
    assert all("rule_id" in item for item in body["rules"])


def test_no_mock_scan_flags_empty_api_promise(tmp_path: Path):
    from sylion.aeis.testing.no_mock_scan import run_no_mock_scan

    target = tmp_path / "src" / "sylion-frontend" / "src" / "lib" / "api"
    target.mkdir(parents=True)
    (target / "client.ts").write_text(
        "export const api = { broken: () => Promise.resolve({ models: [] }) };",
        encoding="utf-8",
    )
    result = run_no_mock_scan(
        root=tmp_path,
        targets=("src/sylion-frontend/src/lib",),
    )
    assert result.status == "FAIL"
    assert result.blocking_count == 1
    assert result.issues[0].rule_id == "empty_promise_api"


def test_truth_alignment_normalizes_summary_keys(client):
    r = client.get("/api/v1/test-center/truth-alignment")
    assert r.status_code == 200
    body = r.json()
    assert len(body["layers"]) == 7
    summary = body["summary"]
    # UI expects these normalized aliases regardless of underlying impl.
    assert "aligned_count" in summary
    assert "drift_count" in summary
    assert "aligned_ratio" in summary


def test_simulation_lists_branches(client):
    r = client.get("/api/v1/test-center/simulation")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "active" in body
    assert "discarded" in body
    assert isinstance(body["branches"], list)


def test_auto_repair_exposes_loop_limits(client):
    r = client.get("/api/v1/test-center/auto-repair")
    assert r.status_code == 200
    body = r.json()
    assert "limits" in body
    # The canonical Loop Governor limits the spec mandates (sec 13).
    for k in (
        "max_auto_fix_attempts_per_finding",
        "max_total_no_go_iterations",
        "max_files_touched_no_hg",
        "max_diff_size_no_hg",
        "max_time_in_repair_loop_s",
        "max_new_p0_p1_introduced",
    ):
        assert k in body["limits"], f"missing limit {k}"
    assert isinstance(body["active_sessions"], list)
    assert isinstance(body["loop_reports_recent"], list)


def test_auto_repair_loop_guard_simulation_blocks_and_creates_hg(client):
    project_id = f"project_loop_guard_smoke_{int(time.time() * 1000)}"
    r = client.post(
        "/api/v1/test-center/auto-repair/loop-guard/simulate",
        json={
            "project_id": project_id,
            "actor": "pytest-operator",
            "rationale": "Controlled LoopGuard regression test.",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["project_id"] == project_id
    assert body["allowed"] is False
    assert body["reason"] == "max_auto_fix_attempts_per_finding"
    assert body["finding"]["r_status"] == "ESCALATED"
    assert body["finding"]["ticket_id"] == body["human_gate"]["request_id"]
    assert body["loop_report"]["required_decision"]["project_id"] == project_id
    assert body["loop_report"]["required_decision"]["status"] == "blocked_human_gate"
    assert body["loop_report"]["required_decision"]["human_gate_ref"] == body["human_gate"]["request_id"]
    assert "further_auto_patch" in body["blocked_actions"]

    status = client.get("/api/v1/test-center/auto-repair")
    assert status.status_code == 200
    status_body = status.json()
    assert any(
        item["report_id"] == body["loop_report"]["report_id"]
        for item in status_body["loop_reports_recent"]
    )


def test_auto_repair_scopes_and_archives_global_history(client):
    project_a = f"project_autorepair_scope_a_{int(time.time() * 1000)}"
    project_b = f"project_autorepair_scope_b_{int(time.time() * 1000)}"
    for project_id in (project_a, project_b):
        r = client.post(
            "/api/v1/test-center/auto-repair/loop-guard/simulate",
            json={
                "project_id": project_id,
                "actor": "pytest-operator",
                "rationale": "Project-scoped AutoRepair ledger test.",
            },
        )
        assert r.status_code == 200, r.text

    scoped = client.get(
        "/api/v1/test-center/auto-repair",
        params={"project_id": project_a},
    )
    assert scoped.status_code == 200
    scoped_body = scoped.json()
    assert scoped_body["project_id"] == project_a
    assert scoped_body["project_scope"] == "project"
    assert scoped_body["open_count"] >= 1
    assert all(project_a in item["title"] for item in scoped_body["active_sessions"])
    assert scoped_body["global_hidden_count"] >= 1

    archived = client.post(
        "/api/v1/test-center/auto-repair/archive-global",
        params={"project_id": project_a, "actor": "pytest-operator"},
    )
    assert archived.status_code == 200
    assert archived.json()["archived_count"] >= 1

    after = client.get(
        "/api/v1/test-center/auto-repair",
        params={"project_id": project_a},
    )
    assert after.status_code == 200
    assert after.json()["archived_global_count"] >= archived.json()["archived_count"]


def test_release_gate_requires_project_id(client):
    r = client.get("/api/v1/test-center/release-gate")
    assert r.status_code == 422  # FastAPI validation: missing query param


def test_release_gate_returns_checklist_for_project(client):
    r = client.get(
        "/api/v1/test-center/release-gate?project_id=proj_test_smoke",
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["rc_checklist"]) == 12
    assert len(body["prod_checklist"]) == 6
    assert body["no_mock_scan"]["status"] in {"PASS", "FAIL"}
    assert {"scanned_files", "issue_count", "blocking_count", "details_url"}.issubset(
        body["no_mock_scan"]
    )


def test_production_readiness_endpoint_blocks_false_ready_claims(client):
    r = client.get("/api/v1/test-center/production-readiness?project_id=proj_test_smoke")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"BLOCKED", "PROD_READY"}
    assert body["repair_protocol"]["command"] == "AEIS_PRODUCTION_REPAIR_LOOP"
    assert isinstance(body["results"], list)
    if body["status"] == "BLOCKED":
        assert body["can_mark_production_ready"] is False
        assert body["next_blocker"]["status"] == "FAIL"


def test_production_readiness_command_records_repair_loop(client):
    r = client.post(
        "/api/v1/test-center/production-readiness/command",
        json={
            "project_id": "proj_test_smoke",
            "actor": "pytest-operator",
            "action": "start",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["repair_protocol"]["command"] == "AEIS_PRODUCTION_REPAIR_LOOP"
    assert body["report_id"] == body["report"]["report_id"]
    assert body["allowed_to_continue"] == body["report"]["can_mark_production_ready"]


def test_release_gate_accepts_project_mode_ids(client):
    r = client.get(
        "/api/v1/test-center/release-gate?project_id=project_test_smoke",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["report"]["status"] == "blocked"
    assert "invalid_project_id" not in body["report"]["blockers"]


def test_release_gate_blocks_when_no_mock_scan_fails(client, monkeypatch):
    from sylion.aeis.testing import no_mock_scan as scan_mod
    from sylion.aeis.testing.release_rail import ReleaseRail
    from sylion.api.test_center_routes import _store
    from sylion.project_mode.store import get_project_mode_store

    class FakeScan:
        status = "FAIL"
        blocking_count = 1

    monkeypatch.setattr(
        scan_mod,
        "run_no_mock_scan",
        lambda limit=2000: FakeScan(),
    )

    project_id = f"project_no_mock_block_{int(time.time() * 1000)}"
    project_store = get_project_mode_store()
    project_store.upsert_project({
        "project_id": project_id,
        "title": "No mock release gate block smoke",
        "idea": "Valid project that must still be blocked by no-mock scan.",
        "canonical_book": "# Source of Truth",
        "masterplan": "# Masterplan",
        "canon_frozen_at": time.time(),
        "masterplan_frozen_at": time.time(),
        "canon_hash": "sha-canon",
        "masterplan_hash": "sha-masterplan",
        "approvals": {"book": True, "operating_model": True},
        "launch": {
            "artifact_path": "results/app.html",
            "artifact_sha256": "sha-artifact",
            "validation": {
                "success": True,
                "stages": {
                    "contract_tests": {"success": True},
                    "smoke_tests": {"success": True},
                },
            },
            "audit": {
                "results": [
                    {"status": "pass", "audit_type": "security_officer"},
                    {"status": "pass", "audit_type": "quality_perf_reviewer"},
                ],
            },
        },
    })
    for event_type in (
        "project.created",
        "project.canon.frozen",
        "project.masterplan.frozen",
        "project.build.completed",
        "project.validation.completed",
        "project.audit.completed",
        "project.execution.completed",
    ):
        project_store.add_event(project_id, event_type, {})

    r = client.get(f"/api/v1/test-center/release-gate?project_id={project_id}")
    assert r.status_code == 200
    report = r.json()["report"]
    assert report["checklist_results"]["no_mock_as_live"] is False
    assert "no_mock_as_live" in report["blockers"]

    direct = ReleaseRail(_store()).evaluate_for_project(
        project_id,
        overrides={"no_mock_as_live": True},
    )
    assert direct["checklist_results"]["no_mock_as_live"] is False


def test_testing_compat_release_gate_and_truth_alignment_routes(client):
    gate = client.get("/api/v1/testing/release-gate/project_test_smoke")
    assert gate.status_code == 200
    assert {"status", "checklist_results", "blockers"}.issubset(gate.json())
    assert "invalid_project_id" not in gate.json()["blockers"]

    truth = client.get("/api/v1/testing/truth-alignment")
    assert truth.status_code == 200
    assert isinstance(truth.json()["rows"], list)


def test_project_charter_can_be_proposed_and_approved_for_release_gate(client):
    project_id = f"proj_test_charter_smoke_{int(time.time() * 1000)}"
    proposed = client.post(
        f"/api/v1/test-center/charters/project/{project_id}/propose",
        json={
            "actor": "pytest-operator",
            "rationale": "Create project test catalog from audit fixture.",
        },
    )
    assert proposed.status_code == 201
    charter = proposed.json()["charter"]
    assert charter["project_id"] == project_id
    assert charter["status"] == "proposed"
    assert "T0" in charter["required_test_classes"]
    assert "T11" in charter["required_test_classes"]

    approved = client.post(
        f"/api/v1/test-center/charters/project/{project_id}/approve",
        json={
            "actor": "pytest-operator",
            "rationale": "HumanGate D3 approval for test catalog.",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["charter"]["status"] == "approved"
    from sylion.governance.tickets import fetch_by_id

    ticket_id = approved.json()["charter"]["hg_ticket_id"]
    ticket = fetch_by_id(ticket_id)
    assert ticket is not None
    assert ticket.state == "approved"
    assert ticket.origin == "council"

    gate = client.get(f"/api/v1/test-center/release-gate?project_id={project_id}")
    assert gate.status_code == 200
    body = gate.json()
    assert body["charter_summary"]["approved"] == 1
    assert body["report"]["checklist_results"]["test_charter_approved"] is True


def test_project_charter_rejects_synthetic_human_gate_id(client):
    project_id = f"proj_test_charter_fake_hg_{int(time.time() * 1000)}"
    proposed = client.post(
        f"/api/v1/test-center/charters/project/{project_id}/propose",
        json={"actor": "pytest-operator", "rationale": "Create test charter."},
    )
    assert proposed.status_code == 201

    approved = client.post(
        f"/api/v1/test-center/charters/project/{project_id}/approve",
        json={
            "actor": "pytest-operator",
            "rationale": "Attempt fake Human Gate id.",
            "hg_ticket_id": "hg_test_charter_fake",
        },
    )
    assert approved.status_code == 409


def test_production_release_gate_actions_make_project_production_ready(client):
    project_id = f"project_prod_gate_smoke_{int(time.time() * 1000)}"
    from sylion.project_mode.store import get_project_mode_store

    project_store = get_project_mode_store()
    project_store.upsert_project({
        "project_id": project_id,
        "title": "Production gate smoke",
        "idea": "Smoke project for production release gate.",
        "canonical_book": "# Source of Truth",
        "masterplan": "# Masterplan",
        "canon_frozen_at": time.time(),
        "masterplan_frozen_at": time.time(),
        "canon_hash": "sha-canon",
        "masterplan_hash": "sha-masterplan",
        "approvals": {"book": True, "operating_model": True},
        "launch": {
            "artifact_path": "results/app.html",
            "artifact_sha256": "sha-artifact",
            "validation": {
                "success": True,
                "stages": {
                    "contract_tests": {"success": True},
                    "smoke_tests": {"success": True},
                },
            },
            "audit": {
                "results": [
                    {"status": "pass", "audit_type": "security_officer"},
                    {"status": "pass", "audit_type": "quality_perf_reviewer"},
                ],
            },
        },
    })
    for event_type in (
        "project.created",
        "project.canon.frozen",
        "project.masterplan.frozen",
        "project.build.completed",
        "project.validation.completed",
        "project.audit.completed",
        "project.execution.completed",
    ):
        project_store.add_event(project_id, event_type, {})

    proposed = client.post(
        f"/api/v1/test-center/charters/project/{project_id}/propose",
        json={"actor": "pytest-operator", "rationale": "Create test charter."},
    )
    assert proposed.status_code == 201
    approved = client.post(
        f"/api/v1/test-center/charters/project/{project_id}/approve",
        json={"actor": "pytest-operator", "rationale": "Approve test charter."},
    )
    assert approved.status_code == 200
    for action in ("rehearse", "rollback-test", "council-sentinels", "final-sign"):
        response = client.post(
            f"/api/v1/test-center/production-release/project/{project_id}/{action}",
            json={"actor": "pytest-operator", "rationale": f"{action} evidence."},
        )
        assert response.status_code == 200, response.text
        if action == "final-sign":
            from sylion.governance.tickets import fetch_by_id

            ticket_id = response.json()["decision"]["hg_ticket_id"]
            ticket = fetch_by_id(ticket_id)
            assert ticket is not None
            assert ticket.state == "approved"
            assert ticket.gate_type == "production"

    gate = client.get(f"/api/v1/test-center/release-gate?project_id={project_id}")
    assert gate.status_code == 200
    checks = gate.json()["report"]["checklist_results"]
    for item in (
        "release_rehearsal_passed",
        "rollback_tested_within_7d",
        "council_completed_d4_d5",
        "sentinels_pass",
        "final_approval_signed",
        "operator_signed_final_gate",
    ):
        assert checks[item] is True


def test_catalog_returns_all_20_test_classes(client):
    r = client.get("/api/v1/test-center/catalog")
    assert r.status_code == 200
    body = r.json()
    assert len(body["classes"]) == 20
    codes = [c["code"] for c in body["classes"]]
    # Spot-check the ladder spans T0..T19
    assert "T0" in codes
    assert "T19" in codes
    for c in body["classes"]:
        assert {"code", "name", "description", "runs_total", "passed", "failed"}.issubset(c)


def test_health_lists_all_endpoints(client):
    r = client.get("/api/v1/test-center/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    expected = {
        "personas", "scenarios", "dashboard", "truth-alignment",
        "simulation", "auto-repair", "release-gate", "catalog",
        "theater",
    }
    assert expected.issubset(set(body["endpoints"]))


# ---------------------------------------------------------------------------
# WebSocket /ws/agent-theater
# ---------------------------------------------------------------------------


def test_agent_theater_ws_streams_snapshot_and_replies_to_ping(client):
    """Verify the WS endpoint pushes a snapshot then handles ping/pong."""
    with client.websocket_connect("/ws/agent-theater") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        assert "topology" in first
        assert isinstance(first["topology"]["actors"], list)
        # 13 guardians always reported (E5 catalog).
        assert len(first["guardians"]) == 13
        # Local models are registry-backed; an empty registry is valid.
        assert isinstance(first["locals"], list)

        ws.send_text(json.dumps({"type": "ping"}))
        pong = ws.receive_json()
        assert pong["type"] == "pong"


def test_agent_theater_ws_set_interval_updates_state(client):
    with client.websocket_connect("/ws/agent-theater") as ws:
        # consume the initial snapshot
        ws.receive_json()
        ws.send_text(json.dumps({"type": "set_interval", "seconds": 1.5}))
        ack = ws.receive_json()
        assert ack["type"] == "interval_set"
        assert abs(ack["seconds"] - 1.5) < 1e-6


def test_agent_theater_ws_rejects_invalid_json(client):
    with client.websocket_connect("/ws/agent-theater") as ws:
        ws.receive_json()  # initial snapshot
        ws.send_text("not json at all")
        err = ws.receive_json()
        assert err["type"] == "error"
        assert "invalid" in err["detail"].lower()


def test_agent_theater_ws_updates_alias_streams_snapshot(client):
    with client.websocket_connect("/ws/agent-theater/updates") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        assert "topology" in first
