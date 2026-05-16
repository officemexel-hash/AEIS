"""Integration tests for Section J — orchestration_config REST routes.

Uses FastAPI TestClient with in-process fallback store (no PG required).
"""
from __future__ import annotations

import pytest
from pathlib import Path

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from fastapi import FastAPI
    from sylion.api.orchestration_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_store(monkeypatch, tmp_path):
    """Use a per-test fallback store so runtime operator state cannot leak in."""
    from sylion.aeis.advisor.orchestration_config import service as svc_mod

    monkeypatch.setenv("SYLION_ORCHESTRATION_STORE", str(tmp_path / "orchestration_config_store.json"))
    svc_mod._STORE.clear()
    svc_mod._SERVICE = None
    svc_mod._ACTIVE_STORE_PATH = None
    svc_mod._PG_AVAILABLE = None
    yield
    svc_mod._STORE.clear()
    svc_mod._SERVICE = None
    svc_mod._ACTIVE_STORE_PATH = None
    svc_mod._PG_AVAILABLE = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/v1/orchestration/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestStopFixRestartGate:
    def test_scan_root_resolves_repo_from_package_cwd(self, monkeypatch):
        from sylion.api.orchestration_routes import _resolve_scan_root

        repo_root = next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "src" / "sylion-frontend").exists()
        )
        package_root = repo_root / "src" / "sylion-pipeline"
        monkeypatch.chdir(package_root)

        assert _resolve_scan_root() == repo_root


# ---------------------------------------------------------------------------
# J1 — LLM Judge Routing
# ---------------------------------------------------------------------------

class TestLLMJudgeRouting:
    def test_get_returns_default_matrix(self, client):
        r = client.get("/api/v1/orchestration/llm-judge-routing")
        assert r.status_code == 200
        data = r.json()
        assert "cells" in data
        assert len(data["cells"]) > 0
        assert data["preset"] == "balanced"

    def test_cells_have_required_fields(self, client):
        r = client.get("/api/v1/orchestration/llm-judge-routing")
        cell = r.json()["cells"][0]
        for field in ("recommendation_type", "risk_level", "model_id", "enabled"):
            assert field in cell

    def test_put_updates_routing(self, client):
        cells = [
            {"recommendation_type": "cost_optimization", "risk_level": "low",
             "model_id": "gpt-4o-mini", "enabled": True, "is_default": False}
        ]
        r = client.put("/api/v1/orchestration/llm-judge-routing",
                       json={"cells": cells, "preset": "cost-saving"})
        assert r.status_code == 200
        data = r.json()
        assert data["preset"] == "cost-saving"
        assert data["cells"][0]["model_id"] == "gpt-4o-mini"

    def test_apply_preset_cost_saving(self, client):
        r = client.post("/api/v1/orchestration/llm-judge-routing/preset/cost-saving")
        assert r.status_code == 200
        data = r.json()
        assert data["preset"] == "cost-saving"
        for cell in data["cells"]:
            assert cell["model_id"] == "claude-haiku-4-5-20251001"

    def test_apply_preset_invalid_raises_400(self, client):
        r = client.post("/api/v1/orchestration/llm-judge-routing/preset/nonexistent")
        assert r.status_code == 400

    def test_reset_cell(self, client):
        # First update a cell
        cells = [
            {"recommendation_type": "security", "risk_level": "critical",
             "model_id": "gpt-4o", "enabled": True, "is_default": False}
        ]
        client.put("/api/v1/orchestration/llm-judge-routing", json={"cells": cells})
        # Now reset
        r = client.post("/api/v1/orchestration/llm-judge-routing/reset-cell",
                        json={"recommendation_type": "security", "risk_level": "critical"})
        assert r.status_code == 200

    def test_reset_cell_missing_fields(self, client):
        r = client.post("/api/v1/orchestration/llm-judge-routing/reset-cell", json={})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# J2 — Council Rules
# ---------------------------------------------------------------------------

class TestCouncilRules:
    def test_get_returns_default_rules(self, client):
        r = client.get("/api/v1/orchestration/council-rules")
        assert r.status_code == 200
        data = r.json()
        assert "rank_weights" in data
        assert len(data["rank_weights"]) == 5
        assert data["critic_gate_enabled"] is True

    def test_put_updates_rules(self, client):
        r = client.get("/api/v1/orchestration/council-rules")
        default = r.json()
        default["quorum_min"] = 5
        r2 = client.put("/api/v1/orchestration/council-rules", json=default)
        assert r2.status_code == 200
        assert r2.json()["quorum_min"] == 5

    def test_simulate_vote_approved(self, client):
        votes = [
            {"rank": 5, "vote": "for"},
            {"rank": 4, "vote": "for"},
            {"rank": 3, "vote": "for"},
        ]
        r = client.post("/api/v1/orchestration/council-rules/simulate-vote",
                        json={"votes": votes})
        assert r.status_code == 200
        data = r.json()
        assert data["outcome"] == "approved"
        assert data["quorum_met"] is True

    def test_simulate_vote_rejected(self, client):
        votes = [
            {"rank": 1, "vote": "against"},
            {"rank": 2, "vote": "against"},
            {"rank": 3, "vote": "for"},
        ]
        r = client.post("/api/v1/orchestration/council-rules/simulate-vote",
                        json={"votes": votes})
        assert r.status_code == 200
        data = r.json()
        assert data["outcome"] == "rejected"

    def test_simulate_vote_empty_returns_400(self, client):
        r = client.post("/api/v1/orchestration/council-rules/simulate-vote",
                        json={"votes": []})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# J3 — Auditor Cadence
# ---------------------------------------------------------------------------

class TestAuditorCadence:
    def test_get_returns_defaults(self, client):
        r = client.get("/api/v1/orchestration/auditor-cadence")
        assert r.status_code == 200
        data = r.json()
        assert data["tick_frequency_seconds"] == 300
        assert len(data["enabled_dimensions"]) == 16

    def test_put_updates_frequency(self, client):
        r = client.get("/api/v1/orchestration/auditor-cadence")
        d = r.json()
        d["tick_frequency_seconds"] = 60
        r2 = client.put("/api/v1/orchestration/auditor-cadence", json=d)
        assert r2.status_code == 200
        assert r2.json()["tick_frequency_seconds"] == 60

    def test_trigger_audit_now(self, client):
        r = client.post("/api/v1/orchestration/auditor-cadence/trigger-now")
        assert r.status_code == 200
        data = r.json()
        assert "audit_id" in data
        assert data["status"] == "triggered"


# ---------------------------------------------------------------------------
# J4 — Fixer Protocol
# ---------------------------------------------------------------------------

class TestFixerProtocol:
    def test_get_returns_defaults(self, client):
        r = client.get("/api/v1/orchestration/fixer-protocol")
        assert r.status_code == 200
        data = r.json()
        assert "retry_budgets" in data
        agent_types = {b["agent_type"] for b in data["retry_budgets"]}
        assert "claude" in agent_types
        assert "codex" in agent_types

    def test_put_updates_retry_budget(self, client):
        r = client.get("/api/v1/orchestration/fixer-protocol")
        d = r.json()
        for b in d["retry_budgets"]:
            if b["agent_type"] == "claude":
                b["retry_limit"] = 5
        r2 = client.put("/api/v1/orchestration/fixer-protocol", json=d)
        assert r2.status_code == 200
        budgets = {b["agent_type"]: b for b in r2.json()["retry_budgets"]}
        assert budgets["claude"]["retry_limit"] == 5


# ---------------------------------------------------------------------------
# J5 — Dispatch Config
# ---------------------------------------------------------------------------

class TestDispatchConfig:
    def test_get_returns_defaults(self, client):
        r = client.get("/api/v1/orchestration/dispatch-config")
        assert r.status_code == 200
        data = r.json()
        assert data["parallelism_mode"] == "wide"
        assert len(data["stage_allocation_rules"]) == 4

    def test_put_switches_to_capped(self, client):
        r = client.get("/api/v1/orchestration/dispatch-config")
        d = r.json()
        d["parallelism_mode"] = "capped"
        d["max_simultaneous"] = 8
        r2 = client.put("/api/v1/orchestration/dispatch-config", json=d)
        assert r2.status_code == 200
        assert r2.json()["parallelism_mode"] == "capped"
        assert r2.json()["max_simultaneous"] == 8


# ---------------------------------------------------------------------------
# J6 — Test Catalog
# ---------------------------------------------------------------------------

class TestTestCatalog:
    def test_get_returns_entries(self, client):
        r = client.get("/api/v1/orchestration/test-catalog")
        assert r.status_code == 200
        assert "tests" in r.json()
        assert len(r.json()["tests"]) > 0

    def test_filter_by_module(self, client):
        r = client.get("/api/v1/orchestration/test-catalog?module=advisor.engine")
        assert r.status_code == 200
        for t in r.json()["tests"]:
            assert t["module"] == "advisor.engine"

    def test_get_runs_empty_initially(self, client):
        r = client.get("/api/v1/orchestration/test-catalog/runs")
        assert r.status_code == 200
        assert "runs" in r.json()

    def test_trigger_run(self, client):
        r = client.post("/api/v1/orchestration/test-catalog/run-now",
                        json={"suite": "golden"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "pass"
        assert "run_id" in data
        assert "Verified catalog check" in data["output"]
        assert data["completed_at"] is not None

    def test_trigger_run_respects_configured_council_quorum(self, client):
        r = client.get("/api/v1/orchestration/council-rules")
        rules = r.json()
        rules["quorum_min"] = 5
        updated = client.put("/api/v1/orchestration/council-rules", json=rules)
        assert updated.status_code == 200

        run = client.post("/api/v1/orchestration/test-catalog/run-now",
                          json={"suite": "golden"})
        assert run.status_code == 200
        data = run.json()
        assert data["status"] == "pass"
        assert "PASS test_advisor_council_0" in data["output"]


# ---------------------------------------------------------------------------
# J7 — Team Formation Rules
# ---------------------------------------------------------------------------

class TestTeamFormationRules:
    def test_get_returns_defaults(self, client):
        r = client.get("/api/v1/orchestration/team-formation-rules")
        assert r.status_code == 200
        data = r.json()
        assert "rules" in data
        assert "active_teams" in data
        assert len(data["rules"]) >= 2

    def test_add_rule(self, client):
        rule = {
            "trigger_pattern": r"^\[test\]",
            "agent_types": ["claude", "z_ai"],
            "lifetime": "ephemeral",
            "action": "spawn_audit_team",
            "enabled": True,
        }
        r = client.post("/api/v1/orchestration/team-formation-rules", json=rule)
        assert r.status_code == 200
        data = r.json()
        assert "rule_id" in data
        assert data["trigger_pattern"] == r"^\[test\]"

    def test_put_updates_rules(self, client):
        r = client.get("/api/v1/orchestration/team-formation-rules")
        rules = r.json()["rules"]
        for rule in rules:
            rule["enabled"] = False
        r2 = client.put("/api/v1/orchestration/team-formation-rules",
                        json={"rules": rules})
        assert r2.status_code == 200
        for rule in r2.json()["rules"]:
            assert rule["enabled"] is False

    def test_trigger_runtime_team_formation(self, client):
        rule = {
            "trigger_pattern": r"^\[r39-theater\]",
            "agent_types": ["z_ai", "claude"],
            "lifetime": "ephemeral",
            "action": "spawn_audit_team",
            "enabled": True,
        }
        created_rule = client.post(
            "/api/v1/orchestration/team-formation-rules",
            json=rule,
        )
        assert created_rule.status_code == 200

        r = client.post(
            "/api/v1/orchestration/team-formation-rules/trigger",
            json={
                "event_label": "[r39-theater] dashboard runtime check",
                "task": "manual dashboard runtime check",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["matched_rules"] == 1
        assert len(data["created_teams"]) == 1
        assert data["created_teams"][0]["agent_types"] == ["z_ai", "claude"]

        r2 = client.get("/api/v1/orchestration/team-formation-rules")
        assert r2.status_code == 200
        teams = r2.json()["active_teams"]
        assert any(
            team["agent_types"] == ["z_ai", "claude"]
            and team["current_task"] == "manual dashboard runtime check"
            for team in teams
        )


# ---------------------------------------------------------------------------
# J8 — Event Map
# ---------------------------------------------------------------------------

class TestEventMap:
    def test_get_returns_map(self, client):
        r = client.get("/api/v1/orchestration/event-map")
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data
        assert "edges" in data
        assert "generated_at" in data

    def test_filter_by_topic_prefix(self, client):
        r = client.get("/api/v1/orchestration/event-map?topic_prefix=aeis.advisor")
        assert r.status_code == 200
        for edge in r.json()["edges"]:
            assert edge["topic"].startswith("aeis.advisor")

    def test_event_map_reflects_runtime_events(self, client):
        from sylion.aeis.advisor.orchestration_config.service import get_orchestration_service

        service = get_orchestration_service()
        service.record_runtime_event("aeis.orchestration.team.formed", 2)
        r = client.get("/api/v1/orchestration/event-map?topic_prefix=aeis.orchestration")
        assert r.status_code == 200
        edges = r.json()["edges"]
        team_edge = next(edge for edge in edges if edge["topic"] == "aeis.orchestration.team.formed")
        assert team_edge["events_per_minute"] == 2.0
        assert team_edge["sample_payload"]["runtime_events"] == 2


# ---------------------------------------------------------------------------
# J9 — Inter-Model Conversation Settings
# ---------------------------------------------------------------------------

class TestInterModelConversation:
    def test_get_returns_defaults(self, client):
        r = client.get("/api/v1/orchestration/inter-model-conversation")
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is False
        assert data["max_turns"] == 4

    def test_put_enables_conversation(self, client):
        r = client.put("/api/v1/orchestration/inter-model-conversation",
                       json={"enabled": True, "max_turns": 6})
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is True
        assert data["max_turns"] == 6

    def test_settings_persist_across_get(self, client):
        client.put("/api/v1/orchestration/inter-model-conversation",
                   json={"enabled": True, "arbiter_model_id": "claude-opus-4-7"})
        r = client.get("/api/v1/orchestration/inter-model-conversation")
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is True
        assert data["arbiter_model_id"] == "claude-opus-4-7"

    def test_trigger_runtime_conversation_records_history(self, client):
        client.put("/api/v1/orchestration/inter-model-conversation",
                   json={"enabled": True, "max_turns": 3})
        r = client.post("/api/v1/orchestration/inter-model-conversation/trigger",
                        json={"topic": "manual dashboard runtime check"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["turns"] == 3
        assert len(data["transcript"]) == 3

        r2 = client.get("/api/v1/orchestration/inter-model-conversation")
        assert r2.status_code == 200
        recent = r2.json()["recent_conversations"]
        assert len(recent) == 1
        assert recent[0]["topic"] == "manual dashboard runtime check"
