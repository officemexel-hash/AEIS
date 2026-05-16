"""S3 — Masterplan + Team Scaling (RB-002).

execution_plan change → reconcile_worker_pool → no orphans, pool reflects
new plan exactly, project record's worker_pool matches the reconciliation
result.
"""
from __future__ import annotations


def test_execution_plan_change_rebuilds_worker_pool_no_orphans():
    from sylion.project_mode.store import get_project_mode_store

    store = get_project_mode_store()
    project_id = "S3-team-scaling"

    store.upsert_project({
        "project_id": project_id,
        "name": "S3 — initial team",
        "execution_plan": {"steps": [{"name": "design"}, {"name": "build"}, {"name": "test"}]},
        "worker_plan": {"roles": ["architect", "developer", "qa"]},
    })

    v1 = store.reconcile_worker_pool(project_id)
    v1_ids = {w["worker_entry_id"] for w in v1["workers"]}
    assert len(v1_ids) > 0

    store.upsert_project({
        "project_id": project_id,
        "name": "S3 — scaled-down team",
        "execution_plan": {"steps": [{"name": "ship"}]},
        "worker_plan": {"roles": ["releaser"]},
    })

    v2 = store.reconcile_worker_pool(project_id)
    v2_ids = {w["worker_entry_id"] for w in v2["workers"]}

    assert v2_ids != v1_ids
    project = store.get_project(project_id)
    pool_ids = {e["worker_entry_id"] for e in project["worker_pool"]}
    assert pool_ids == v2_ids
    assert pool_ids.intersection(set(v2.get("orphans", []))) == set()
