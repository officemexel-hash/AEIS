"""Wave A4 -- worker_pool reconciliation (RB-002).

DoD: a change to `execution_plan` deterministically rebuilds `worker_pool`,
drops orphaned slots, and surfaces the orphaned worker_entry_ids so that
runtime worker registry can prune them too. No cached pool ever survives a
plan change.
"""

from __future__ import annotations

import pytest

import sylion.project_mode.store as _store_mod
from sylion.worker.registry import WorkerRegistry, reset_worker_registry


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "store.sqlite"))
    if _store_mod._store is not None:
        _store_mod._store.close()
    _store_mod._store = None
    reset_worker_registry()
    yield
    if _store_mod._store is not None:
        _store_mod._store.close()
    _store_mod._store = None
    reset_worker_registry()


def _seed(
    project_id: str,
    local: int = 0,
    vps: int = 0,
    roles: list[str] | None = None,
) -> dict:
    project = {
        "project_id": project_id,
        "title": "t", "idea": "i", "constraints": "",
        "execution_plan": {
            "local_docker_workers": local,
            "vps_workers": vps,
        },
        "worker_plan": {"roles": roles or []},
    }
    return _store_mod.get_project_mode_store().upsert_project(project)


def _ids(pool: list[dict]) -> set[str]:
    return {entry["worker_entry_id"] for entry in pool}


class TestPoolDerivedFromPlan:

    def test_local_count_matches_plan(self):
        project = _seed("p", local=3, vps=0)
        assert len(project["worker_pool"]) == 3
        assert all(e["worker_type"] == "docker" for e in project["worker_pool"])

    def test_vps_count_matches_plan(self):
        project = _seed("p", local=0, vps=2)
        assert len(project["worker_pool"]) == 2
        assert all(e["worker_type"] == "vps" for e in project["worker_pool"])

    def test_combined_pool_size_matches_sum(self):
        project = _seed("p", local=3, vps=2)
        assert len(project["worker_pool"]) == 5
        types = sorted(e["worker_type"] for e in project["worker_pool"])
        assert types == ["docker", "docker", "docker", "vps", "vps"]

    def test_zero_zero_yields_empty_pool(self):
        project = _seed("p", local=0, vps=0)
        assert project["worker_pool"] == []

    def test_entry_ids_are_deterministic(self):
        project = _seed("proj_a", local=2, vps=1)
        ids = _ids(project["worker_pool"])
        assert ids == {
            "proj_a::local::0", "proj_a::local::1", "proj_a::vps::0",
        }


class TestPoolRebuildsOnPlanChange:
    """RB-002 core: changes to execution_plan must rebuild the pool."""

    def test_scale_down_drops_orphans(self):
        store = _store_mod.get_project_mode_store()
        _seed("p", local=3, vps=2)
        # Plan change: only 2 local, 0 vps remains -> 3 orphans.
        result = store.reconcile_worker_pool(
            "p", execution_plan={"local_docker_workers": 2, "vps_workers": 0},
        )
        assert len(result["workers"]) == 2
        assert sorted(result["orphans"]) == [
            "p::local::2", "p::vps::0", "p::vps::1",
        ]

    def test_scale_up_adds_slots_no_orphans(self):
        store = _store_mod.get_project_mode_store()
        _seed("p", local=2, vps=0)
        result = store.reconcile_worker_pool(
            "p", execution_plan={"local_docker_workers": 5, "vps_workers": 0},
        )
        assert len(result["workers"]) == 5
        assert result["orphans"] == []

    def test_replace_local_with_vps(self):
        store = _store_mod.get_project_mode_store()
        _seed("p", local=3, vps=0)
        result = store.reconcile_worker_pool(
            "p", execution_plan={"local_docker_workers": 0, "vps_workers": 3},
        )
        assert len(result["workers"]) == 3
        assert all(e["worker_type"] == "vps" for e in result["workers"])
        assert sorted(result["orphans"]) == [
            "p::local::0", "p::local::1", "p::local::2",
        ]

    def test_no_plan_change_yields_no_orphans(self):
        store = _store_mod.get_project_mode_store()
        _seed("p", local=2, vps=1)
        result = store.reconcile_worker_pool("p")
        assert len(result["workers"]) == 3
        assert result["orphans"] == []

    def test_three_consecutive_launches_no_orphans_remain(self):
        store = _store_mod.get_project_mode_store()
        _seed("p", local=1, vps=0)
        store.reconcile_worker_pool(
            "p", execution_plan={"local_docker_workers": 4, "vps_workers": 1},
        )
        store.reconcile_worker_pool(
            "p", execution_plan={"local_docker_workers": 2, "vps_workers": 2},
        )
        result = store.reconcile_worker_pool(
            "p", execution_plan={"local_docker_workers": 1, "vps_workers": 1},
        )
        # Final pool is exactly what the last plan asks for.
        assert len(result["workers"]) == 2
        # And the persisted DB matches this view.
        persisted = store.get_project("p")["worker_pool"]
        assert len(persisted) == 2

    def test_plan_change_does_not_drop_unrelated_metadata(self):
        store = _store_mod.get_project_mode_store()
        _seed("p", local=2, vps=0)
        # Operator labels worker 0 with a model_id.
        project = store.get_project("p")
        project["worker_pool"][0]["model_id"] = "ollama:llama3:latest"
        store.update_project_workers("p", project["worker_pool"])
        # Scale up; existing entries' model_id should be preserved.
        result = store.reconcile_worker_pool(
            "p", execution_plan={"local_docker_workers": 3, "vps_workers": 0},
        )
        assert len(result["workers"]) == 3
        first = next(e for e in result["workers"]
                     if e["worker_entry_id"] == "p::local::0")
        assert first["model_id"] == "ollama:llama3:latest"


class TestUpsertReplay:
    """Direct upsert with a different execution_plan must rebuild too."""

    def test_upsert_with_changed_plan_rebuilds_pool(self):
        store = _store_mod.get_project_mode_store()
        _seed("p", local=3, vps=2)
        project = store.get_project("p")
        project["execution_plan"] = {
            "local_docker_workers": 1, "vps_workers": 0,
        }
        result = store.upsert_project(project)
        # OLD bug returned cached 5 entries; correct behaviour: rebuild to 1.
        assert len(result["worker_pool"]) == 1
        assert result["worker_pool"][0]["worker_entry_id"] == "p::local::0"


class TestUnregisterOrphaned:
    """worker.registry.unregister_orphaned scoped by metadata.project_id."""

    def test_orphans_only_removed_for_named_project(self):
        registry = WorkerRegistry(":memory:")
        w_a1 = registry.register_worker(
            "a-1", host="h1", metadata={"project_id": "p_a"}
        )["worker_id"]
        w_a2 = registry.register_worker(
            "a-2", host="h2", metadata={"project_id": "p_a"}
        )["worker_id"]
        w_b1 = registry.register_worker(
            "b-1", host="h1", metadata={"project_id": "p_b"}
        )["worker_id"]
        w_global = registry.register_worker("global", host="h1")["worker_id"]

        # Keep only w_a1 for project p_a.
        removed = registry.unregister_orphaned("p_a", kept_worker_ids=[w_a1])
        assert removed == 1

        remaining = {w["worker_id"] for w in registry.list_workers()}
        assert w_a1 in remaining
        assert w_a2 not in remaining
        assert w_b1 in remaining
        assert w_global in remaining

    def test_no_workers_for_project_is_noop(self):
        registry = WorkerRegistry(":memory:")
        registry.register_worker("only-fleet", host="h1")
        removed = registry.unregister_orphaned("p_unknown", kept_worker_ids=[])
        assert removed == 0
        assert len(registry.list_workers()) == 1

    def test_all_kept_means_no_removals(self):
        registry = WorkerRegistry(":memory:")
        kept = []
        for i in range(3):
            w = registry.register_worker(
                f"p-{i}", metadata={"project_id": "p"}
            )
            kept.append(w["worker_id"])
        removed = registry.unregister_orphaned("p", kept_worker_ids=kept)
        assert removed == 0
        assert len(registry.list_workers()) == 3
