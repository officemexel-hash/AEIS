"""Wave A3 -- active_size === count(active members) (RB-004 part 2).

Verifies the determinism of council_plan.active_size in the derived
council_members list. After upsert/reconcile, exactly active_size members
are flagged active=True; remaining are active=False.
"""

from __future__ import annotations

import pytest

import sylion.project_mode.store as _store_mod
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


def _seed(project_id: str, active_size: int, plan_members: int = 5,
          enabled: bool = True) -> None:
    plan = {
        "enabled": enabled,
        "active_size": active_size,
        "suggested_size": plan_members,
        "members": [
            {"role": f"r{i}", "preferred_models": [f"m{i}"]}
            for i in range(plan_members)
        ],
    }
    store = _store_mod.get_project_mode_store()
    store.upsert_project({
        "project_id": project_id,
        "title": "t", "idea": "i", "constraints": "",
        "council_plan": plan,
    })


class TestExactActiveCount:

    @pytest.mark.parametrize("size", [0, 1, 2, 3, 4, 5])
    def test_count_active_members_equals_active_size(self, size):
        _seed("p", size)
        store = _store_mod.get_project_mode_store()
        members = store.get_project_council("p")["members"]
        active = [m for m in members if m["active"]]
        assert len(active) == size

    @pytest.mark.parametrize("size", [0, 1, 2, 3, 4, 5])
    def test_total_members_equals_plan_size(self, size):
        _seed("p", size, plan_members=5)
        store = _store_mod.get_project_mode_store()
        members = store.get_project_council("p")["members"]
        assert len(members) == 5  # all members persisted, only `active` differs

    @pytest.mark.parametrize("size", [0, 1, 2, 3, 4, 5])
    def test_registry_get_active_members_matches_size(self, size):
        _seed("p", size)
        active = get_model_registry().get_active_members("p")
        assert len(active) == size


class TestActiveSizeAfterReconcile:

    def test_reconcile_restores_consistency_after_external_drift(self):
        _seed("p", active_size=3, plan_members=5)
        store = _store_mod.get_project_mode_store()

        # Simulate drift: someone updates council_members directly so all 5
        # are active despite plan saying active_size=3.
        members = store.get_project_council("p")["members"]
        for m in members:
            m["active"] = True
        store.update_project_council("p", members)
        assert sum(1 for m in store.get_project_council("p")["members"]
                   if m["active"]) == 5

        # Reconcile: members get re-derived from the plan -> 3 active.
        refreshed = store.reconcile_council("p")
        active_count = sum(1 for m in refreshed["members"] if m["active"])
        assert active_count == 3


class TestActiveSizeBoundary:

    def test_active_size_larger_than_plan_members_caps_at_plan(self):
        # active_size=10 with only 5 plan members -> no IndexError, all 5 active.
        _seed("p", active_size=10, plan_members=5)
        active = get_model_registry().get_active_members("p")
        # All 5 plan members get active=True (idx < 10 for idx in 0..4).
        assert len(active) == 5

    def test_active_size_zero_yields_no_active_members(self):
        _seed("p", active_size=0, plan_members=5)
        active = get_model_registry().get_active_members("p")
        assert active == []
