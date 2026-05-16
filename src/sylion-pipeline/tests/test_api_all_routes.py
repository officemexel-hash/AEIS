"""
API integration tests: verify all route groups mount and respond correctly.
Uses FastAPI TestClient for end-to-end route testing.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.api.router import router


@pytest.fixture(scope="module")
def app():
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Route mounting verification
# ---------------------------------------------------------------------------

def test_all_routes_mounted(client):
    """Verify the app has all expected route groups."""
    routes = [r.path for r in client.app.routes]
    assert any("/api/v1/core" in r for r in routes)
    assert any("/api/v1/governance" in r for r in routes)
    assert any("/api/v1/cognitive" in r for r in routes)
    assert any("/api/v1/execution" in r for r in routes)
    assert any("/api/v1/security" in r for r in routes)
    assert any("/api/v1/aeis" in r for r in routes)
    assert any("/api/v1/skills" in r for r in routes)
    assert any("/api/v1/surface" in r for r in routes)


# ---------------------------------------------------------------------------
# Core routes
# ---------------------------------------------------------------------------

def test_core_modules_list(client):
    resp = client.get("/api/v1/core/modules")
    assert resp.status_code == 200


def test_core_contracts_list(client):
    resp = client.get("/api/v1/core/contracts")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Governance routes
# ---------------------------------------------------------------------------

def test_governance_proposals_list(client):
    resp = client.get("/api/v1/governance/proposals")
    assert resp.status_code == 200


def test_governance_council_sessions(client):
    resp = client.get("/api/v1/governance/council/sessions")
    assert resp.status_code == 200


def test_governance_evidence_packs(client):
    resp = client.get("/api/v1/governance/evidence-packs")
    assert resp.status_code == 200


def test_governance_policies(client):
    resp = client.get("/api/v1/governance/policies")
    assert resp.status_code == 200


def test_governance_gates(client):
    resp = client.get("/api/v1/governance/gates")
    assert resp.status_code == 200


def test_governance_roles(client):
    resp = client.get("/api/v1/governance/roles")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AEIS routes
# ---------------------------------------------------------------------------

def test_aeis_improvements_list(client):
    resp = client.get("/api/v1/aeis/improvements")
    assert resp.status_code == 200


def test_aeis_improvement_stats(client):
    resp = client.get("/api/v1/aeis/improvements/stats")
    assert resp.status_code == 200


def test_aeis_autonomy_stages(client):
    resp = client.get("/api/v1/aeis/autonomy/stages")
    assert resp.status_code == 200


def test_aeis_explanations_list(client):
    resp = client.get("/api/v1/aeis/explanations")
    assert resp.status_code == 200


def test_aeis_evolution_proposals(client):
    resp = client.get("/api/v1/aeis/evolution/proposals")
    assert resp.status_code == 200


def test_aeis_evolution_stats(client):
    resp = client.get("/api/v1/aeis/evolution/stats")
    assert resp.status_code == 200


def test_aeis_adaptation_feedback_list(client):
    resp = client.get("/api/v1/aeis/adaptation/feedback")
    assert resp.status_code == 200


def test_aeis_adaptation_adaptations(client):
    resp = client.get("/api/v1/aeis/adaptation/adaptations")
    assert resp.status_code == 200


def test_aeis_adaptation_rules(client):
    resp = client.get("/api/v1/aeis/adaptation/rules")
    assert resp.status_code == 200


def test_aeis_adaptation_stats(client):
    resp = client.get("/api/v1/aeis/adaptation/stats")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Skills routes
# ---------------------------------------------------------------------------

def test_skills_list(client):
    resp = client.get("/api/v1/skills/skills")
    assert resp.status_code == 200


def test_skills_registry_stats(client):
    resp = client.get("/api/v1/skills/skills-registry/stats")
    assert resp.status_code == 200


def test_skills_execution_stats(client):
    resp = client.get("/api/v1/skills/execution-stats")
    assert resp.status_code == 200


def test_skills_demand_signals(client):
    resp = client.get("/api/v1/skills/demand/signals")
    assert resp.status_code == 200


def test_skills_demand_stats(client):
    resp = client.get("/api/v1/skills/demand/stats")
    assert resp.status_code == 200


def test_skills_catalog_browse(client):
    resp = client.get("/api/v1/skills/catalog")
    assert resp.status_code == 200


def test_skills_catalog_stats(client):
    resp = client.get("/api/v1/skills/catalog-stats")
    assert resp.status_code == 200


def test_skills_catalog_recommend(client):
    resp = client.get("/api/v1/skills/catalog/recommend")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Skills CRUD flow
# ---------------------------------------------------------------------------

def test_skills_register_and_get(client):
    resp = client.post("/api/v1/skills/skills", params={
        "skill_id": "api-test-1",
        "name": "API Test Skill",
        "domain": "test",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["skill_id"] == "api-test-1"

    resp2 = client.get("/api/v1/skills/skills/api-test-1")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "API Test Skill"


def test_skills_execute(client):
    resp = client.post("/api/v1/skills/executions", params={
        "skill_id": "api-exec-1",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"

    resp2 = client.get(f"/api/v1/skills/executions/{data['exec_id']}")
    assert resp2.status_code == 200


def test_skills_lifecycle_long_run_endpoint(client):
    resp = client.post(
        "/api/v1/skills/lifecycle/long-run-test",
        json={
            "project_id": "proj_api_skill_lifecycle",
            "domain": "api-test",
            "owner_role": "pytest-operator",
            "cycles": 1,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["passed"] is True
    assert data["skill_ids"]
    assert set(data["final_lifecycle"].values()) == {"PUBLISHED"}
    stages = {item["stage"] for item in data["trace"]}
    assert {"demand_signal", "registered", "executed", "published", "demand_analyzed"}.issubset(stages)


def test_project_audit_emits_semantic_terminal_event():
    import time

    from sylion.api.project_start_routes import _append_audit
    from sylion.core.event_bus import get_event_bus

    since = time.time() - 1
    project = {"project_id": "proj_semantic_event_test", "state": "BUILDING"}
    entry = _append_audit(
        project,
        "semantic_terminal_probe",
        {
            "actor": "pytest",
            "phase": "W18",
            "environment_id": "local-test",
            "council_session_id": "council-test",
            "message": "semantic terminal probe",
        },
    )
    events = get_event_bus().query(topic="aeis.project.audit.semantic_terminal_probe", since=since, limit=10)
    assert any(event["idempotency_key"] == f"project_audit:{entry['event_id']}" for event in events)
    payloads = [event["payload"] for event in events]
    assert any("proj_semantic_event_test" in payload for payload in payloads)


def test_skills_catalog_add_and_browse(client):
    resp = client.post("/api/v1/skills/catalog", params={
        "skill_id": "cat-test-1",
        "name": "Catalog Test",
        "category": "test",
    })
    assert resp.status_code == 201

    resp2 = client.get("/api/v1/skills/catalog", params={"category": "test"})
    assert resp2.status_code == 200


def test_test_center_catalog_run_records_failed_finding(client):
    from sylion.api.test_center_routes import router as test_center_router

    app = FastAPI()
    app.include_router(test_center_router)
    test_center_client = TestClient(app)

    resp = test_center_client.post("/api/v1/test-center/catalog/run", params={
        "test_class": "T1",
        "project_id": "proj_test_center_api",
        "status": "failed",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["run"]["status"] == "failed"
    assert data["finding"]["severity"] == "P1"

    dashboard = test_center_client.get("/api/v1/test-center/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["findings"]["open_p0_p1"] >= 1


# ---------------------------------------------------------------------------
# AEIS CRUD flow
# ---------------------------------------------------------------------------

def test_aeis_improvement_crud(client):
    resp = client.post("/api/v1/aeis/improvements", params={
        "title": "Test Improvement",
        "category": "performance",
    })
    assert resp.status_code == 201

    resp2 = client.get("/api/v1/aeis/improvements")
    assert resp2.status_code == 200
    assert len(resp2.json()["improvements"]) >= 1


def test_aeis_evolution_propose(client):
    resp = client.post("/api/v1/aeis/evolution/propose", params={
        "target_module": "core.test",
        "mutation_type": "parameter_tune",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == "PROPOSED"

    pid = data["proposal_id"]
    resp2 = client.get(f"/api/v1/aeis/evolution/proposals/{pid}")
    assert resp2.status_code == 200


def test_aeis_adaptation_feedback(client):
    resp = client.post("/api/v1/aeis/adaptation/feedback", params={
        "source": "test",
        "metric": "cpu",
        "value": 0.95,
    })
    assert resp.status_code == 201
    assert "signal_id" in resp.json()


def test_aeis_adaptation_rule_crud(client):
    resp = client.post("/api/v1/aeis/adaptation/rules", params={
        "name": "Test Rule",
        "trigger_metric": "latency",
        "threshold": 100.0,
        "adaptation_type": "parameter_tune",
    })
    assert resp.status_code == 201

    resp2 = client.get("/api/v1/aeis/adaptation/rules")
    assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# Surface routes
# ---------------------------------------------------------------------------

def test_surface_console_endpoints(client):
    resp = client.get("/api/v1/surface/console/endpoints")
    assert resp.status_code == 200


def test_surface_console_stats(client):
    resp = client.get("/api/v1/surface/console/stats")
    assert resp.status_code == 200


def test_surface_ui_components(client):
    resp = client.get("/api/v1/surface/ui/components")
    assert resp.status_code == 200


def test_surface_ui_layouts(client):
    resp = client.get("/api/v1/surface/ui/layouts")
    assert resp.status_code == 200


def test_surface_ws_connections(client):
    resp = client.get("/api/v1/surface/ws/connections")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Execution routes
# ---------------------------------------------------------------------------

def test_execution_tools_list(client):
    resp = client.get("/api/v1/execution/tools")
    assert resp.status_code == 200


def test_execution_jobs_list(client):
    resp = client.get("/api/v1/execution/jobs")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Memory routes
# ---------------------------------------------------------------------------

def test_memory_kanon_sections(client):
    resp = client.get("/api/v1/memory/kanon/sections")
    assert resp.status_code == 200


def test_memory_compact_records(client):
    resp = client.get("/api/v1/memory/compact/records")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Rebuild routes
# ---------------------------------------------------------------------------

def test_rebuild_orchestrator_plans(client):
    resp = client.get("/api/v1/rebuild/orchestrator/plans")
    assert resp.status_code == 200


def test_rebuild_cutover_plans(client):
    resp = client.get("/api/v1/rebuild/cutover/plans")
    assert resp.status_code == 200


def test_rebuild_cft_suites(client):
    resp = client.get("/api/v1/rebuild/cft/suites")
    assert resp.status_code == 200
