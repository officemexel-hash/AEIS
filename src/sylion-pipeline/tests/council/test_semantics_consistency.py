"""Wave A3 -- Council semantics consistency (RB-004).

DoD criterion: when council_plan.enabled is False, the decision_hierarchy
MUST NOT include 'planner_council', and active member count MUST be zero.
Verified across all combinations of enabled in {True, False} and
active_size in 0..5.
"""

from __future__ import annotations

import pytest

import sylion.project_mode.store as _store_mod
from sylion.cognitive.model_registry import (
    DEFAULT_DECISION_HIERARCHY,
    DISABLED_DECISION_HIERARCHY,
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


def _make_project(
    project_id: str = "proj_t1",
    enabled: bool | None = True,
    active_size: int = 3,
    plan_members: int = 5,
    decision_layers: list[str] | None = None,
) -> dict:
    plan: dict = {
        "active_size": active_size,
        "suggested_size": plan_members,
        "members": [
            {
                "role": f"role_{i}",
                "responsibility": f"resp_{i}",
                "preferred_models": [f"ollama:model_{i}:latest"],
            }
            for i in range(plan_members)
        ],
    }
    if enabled is not None:
        plan["enabled"] = enabled

    project = {
        "project_id": project_id,
        "title": "test project",
        "idea": "test idea",
        "constraints": "",
        "council_plan": plan,
    }
    if decision_layers is not None:
        project["governance_policy"] = {"decision_layers": decision_layers}
    store = _store_mod.get_project_mode_store()
    return store.upsert_project(project)


class TestEnabledDefault:

    def test_default_enabled_true_when_field_absent(self):
        _make_project(enabled=None, active_size=2, plan_members=3)
        assert get_model_registry().is_enabled("proj_t1") is True

    def test_explicit_enabled_true(self):
        _make_project(enabled=True, active_size=2)
        assert get_model_registry().is_enabled("proj_t1") is True

    def test_explicit_enabled_false(self):
        _make_project(enabled=False, active_size=2)
        assert get_model_registry().is_enabled("proj_t1") is False

    def test_unknown_project_defaults_enabled(self):
        # Graceful default for project that doesn't exist.
        assert get_model_registry().is_enabled("missing_project") is True


class TestDecisionHierarchyByEnabledFlag:

    def test_disabled_hierarchy_excludes_planner_council(self):
        _make_project(enabled=False, active_size=3)
        hierarchy = get_model_registry().get_decision_hierarchy("proj_t1")
        assert "planner_council" not in hierarchy
        assert hierarchy == ["operator_only"]
        assert hierarchy == DISABLED_DECISION_HIERARCHY

    def test_enabled_hierarchy_uses_configured_layers(self):
        _make_project(
            enabled=True, active_size=3,
            decision_layers=["operator", "planner_council", "engineer_council"],
        )
        hierarchy = get_model_registry().get_decision_hierarchy("proj_t1")
        assert hierarchy == ["operator", "planner_council", "engineer_council"]

    def test_enabled_no_layers_returns_default(self):
        _make_project(enabled=True, active_size=3, decision_layers=None)
        hierarchy = get_model_registry().get_decision_hierarchy("proj_t1")
        assert hierarchy == DEFAULT_DECISION_HIERARCHY


class TestEnabledFalseProducesEmptyMembers:

    @pytest.mark.parametrize("active_size", [0, 1, 2, 3, 5])
    def test_disabled_active_members_empty_regardless_of_active_size(self, active_size):
        _make_project(enabled=False, active_size=active_size, plan_members=5)
        members = get_model_registry().get_active_members("proj_t1")
        assert members == []


class TestEnabledTrueRespectsActiveSize:

    @pytest.mark.parametrize("active_size", [0, 1, 2, 3, 5])
    def test_enabled_active_count_matches_active_size(self, active_size):
        _make_project(enabled=True, active_size=active_size, plan_members=5)
        members = get_model_registry().get_active_members("proj_t1")
        assert len(members) == active_size


class TestSetCouncilEnabledTransitions:

    def test_disable_then_enable_round_trip(self):
        _make_project(enabled=True, active_size=3)
        store = _store_mod.get_project_mode_store()
        registry = get_model_registry()

        assert registry.is_enabled("proj_t1") is True
        assert len(registry.get_active_members("proj_t1")) == 3

        store.set_council_enabled("proj_t1", False)
        assert registry.is_enabled("proj_t1") is False
        assert registry.get_active_members("proj_t1") == []
        assert registry.get_decision_hierarchy("proj_t1") == ["operator_only"]

        store.set_council_enabled("proj_t1", True)
        assert registry.is_enabled("proj_t1") is True
        # Members got re-derived from the plan after re-enabling.
        assert len(registry.get_active_members("proj_t1")) == 3


class TestPersistedMembersHonorEnabled:

    def test_explicit_members_marked_inactive_when_disabled(self):
        # Even pre-supplied members must be marked inactive when the plan
        # gets a `enabled=False` flag.
        store = _store_mod.get_project_mode_store()
        store.upsert_project({
            "project_id": "proj_t2",
            "title": "x",
            "idea": "y",
            "constraints": "",
            "council_plan": {"enabled": False, "active_size": 2, "members": []},
            "council_members": [
                {"member_role": "r1", "model_id": "m1", "active": True},
                {"member_role": "r2", "model_id": "m2", "active": True},
            ],
        })
        council = store.get_project_council("proj_t2")
        for m in council["members"]:
            assert m["active"] is False
        assert get_model_registry().get_active_members("proj_t2") == []
