"""Wave A3 -- registry and workspace council never disagree (RB-012).

DoD: ModelRegistry.get_active_members(project_id) MUST return the same
truth as project_mode_store.get_project_council(project_id) when filtered
to active members. No split-brain -- one truth plane.

Also exercises the /api/v1/council/{project_id}/state endpoint.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.project_mode.store as _store_mod
from sylion.api.council_routes import router as council_router
from sylion.cognitive.model_registry import (
    get_model_registry,
    reset_model_registry,
)


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "store.sqlite"))
    if _store_mod._store is not None:
        _store_mod._store.close()
    _store_mod._store = None
    reset_model_registry(":memory:")
    yield
    if _store_mod._store is not None:
        _store_mod._store.close()
    _store_mod._store = None
    reset_model_registry(":memory:")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(council_router)
    return TestClient(app)


def _seed(
    project_id: str,
    active_size: int,
    enabled: bool = True,
    plan_members: int = 5,
    decision_layers: list[str] | None = None,
) -> None:
    project = {
        "project_id": project_id,
        "title": "t", "idea": "i", "constraints": "",
        "council_plan": {
            "enabled": enabled,
            "active_size": active_size,
            "suggested_size": plan_members,
            "members": [
                {"role": f"r{i}", "preferred_models": [f"ollama:m{i}"]}
                for i in range(plan_members)
            ],
        },
    }
    if decision_layers is not None:
        project["governance_policy"] = {"decision_layers": decision_layers}
    _store_mod.get_project_mode_store().upsert_project(project)


class TestRegistryStoreParity:

    @pytest.mark.parametrize("active_size", [0, 1, 3, 5])
    def test_active_member_ids_match(self, active_size):
        _seed("p", active_size=active_size, plan_members=5)
        store = _store_mod.get_project_mode_store()
        store_ids = {
            m["council_member_id"]
            for m in store.get_project_council("p")["members"]
            if m["active"]
        }
        registry_ids = {
            m.member_id for m in get_model_registry().get_active_members("p")
        }
        assert store_ids == registry_ids

    def test_disabled_council_yields_zero_in_both_views(self):
        _seed("p", active_size=3, enabled=False)
        store = _store_mod.get_project_mode_store()
        registry = get_model_registry()
        store_active = [m for m in store.get_project_council("p")["members"]
                        if m["active"]]
        assert store_active == []
        assert registry.get_active_members("p") == []

    def test_member_role_propagates_through_registry(self):
        _seed("p", active_size=2)
        registry = get_model_registry()
        roles = {m.member_role for m in registry.get_active_members("p")}
        # First two roles are r0, r1.
        assert roles == {"r0", "r1"}


class TestCouncilStateEndpoint:

    def test_endpoint_returns_consistent_state(self, client):
        _seed(
            "p_alpha", active_size=2, enabled=True,
            decision_layers=["operator", "planner_council", "engineer_council"],
        )
        r = client.get("/api/v1/council/p_alpha/state")
        assert r.status_code == 200
        body = r.json()
        assert body["project_id"] == "p_alpha"
        assert body["enabled"] is True
        assert body["active_size"] == 2
        assert len(body["members"]) == 2
        assert body["decision_hierarchy"] == [
            "operator", "planner_council", "engineer_council",
        ]

    def test_disabled_council_state(self, client):
        _seed("p_beta", active_size=3, enabled=False)
        r = client.get("/api/v1/council/p_beta/state")
        assert r.status_code == 200
        body = r.json()
        assert body["enabled"] is False
        assert body["active_size"] == 0
        assert body["members"] == []
        assert "planner_council" not in body["decision_hierarchy"]
        assert body["decision_hierarchy"] == ["operator_only"]

    def test_unknown_project_returns_404(self, client):
        r = client.get("/api/v1/council/missing/state")
        assert r.status_code == 404


class TestReconcileEndpoint:

    def test_reconcile_restores_consistency(self, client):
        _seed("p_gamma", active_size=2, plan_members=5)
        # Drift: mark all members active externally.
        store = _store_mod.get_project_mode_store()
        members = store.get_project_council("p_gamma")["members"]
        for m in members:
            m["active"] = True
        store.update_project_council("p_gamma", members)

        r = client.post("/api/v1/council/p_gamma/reconcile")
        assert r.status_code == 200
        body = r.json()
        assert body["active_size"] == 2
        assert len(body["members"]) == 2  # only active members surface
        # Underlying store also re-aligned: 2 active out of 5.
        active_after = [m for m in
                        store.get_project_council("p_gamma")["members"]
                        if m["active"]]
        assert len(active_after) == 2


class TestEnableEndpoint:

    def test_enable_endpoint_toggles_state(self, client):
        _seed("p_delta", active_size=3, enabled=True)
        r = client.post("/api/v1/council/p_delta/enable", json={"enabled": False})
        assert r.status_code == 200
        body = r.json()
        assert body["enabled"] is False
        assert body["members"] == []
        assert body["decision_hierarchy"] == ["operator_only"]

        # Re-enable.
        r2 = client.post("/api/v1/council/p_delta/enable", json={"enabled": True})
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["enabled"] is True
        # After re-enable + re-derive, members come from the plan again.
        assert len(body2["members"]) == 3


class TestRegistryWithoutProjectId:

    def test_global_get_active_members_returns_registered_models(self):
        registry = get_model_registry()
        registry.register_model("m1", "ollama", "Llama 3", "{}")
        registry.register_model("m2", "openai", "GPT-4", "{}")
        members = registry.get_active_members(None)
        assert len(members) == 2
        assert {m.model_id for m in members} == {"m1", "m2"}
        assert all(m.project_id is None for m in members)
