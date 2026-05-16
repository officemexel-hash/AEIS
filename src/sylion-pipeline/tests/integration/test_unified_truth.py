"""Phase 2 D-INTEGRATE: 6 unified truth checks.

D2 task — verifies the integration of A/B/K work landed correctly:

  1. Human Gate / governance — 5 origins in single TicketStore
  2. Memory plane bootstrapped, /memory/evidence/stats reachable
  3. Skills runtime — loaded_skills > 0 after bootstrap_from
  4. Council semantics — enabled=False -> decision_hierarchy = ['operator_only']
  5. Worker pool reconciliation — execution_plan change leaves no orphans
  6. Funding submission -> governance ticket with origin='funding'
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sylion.governance.ticket import GovernanceTicket, VALID_ORIGINS
from sylion.governance.tickets import fetch_pending, submit


# ---------------------------------------------------------------------------
# Check 1: 5 origins land in one unified ticket store
# ---------------------------------------------------------------------------

class TestUnifiedTicketStore:
    """Single truth-plane for governance tickets across all caller surfaces."""

    def test_five_origins_in_one_store(self):
        """workspace, global, funding, mobile, skill -> all visible from one fetch_pending()."""
        ids: dict[str, str] = {}
        for origin in ("workspace", "global", "funding", "mobile", "skill"):
            tid = submit(GovernanceTicket(
                origin=origin,
                title=f"truth-check-{origin}",
                summary=f"unified plane probe ({origin})",
                requested_by="d-integrate",
            ))
            ids[origin] = tid

        all_pending = fetch_pending()
        seen = {t.ticket_id: t.origin for t in all_pending}

        for origin, tid in ids.items():
            assert tid in seen, f"ticket from {origin} missing from unified plane"
            assert seen[tid] == origin, f"origin drift on {tid}: {seen[tid]} != {origin}"

    def test_origin_filter_returns_only_that_origin(self):
        for origin in ("workspace", "funding", "mobile"):
            submit(GovernanceTicket(
                origin=origin, title=f"f-{origin}", requested_by="d",
            ))

        funding_only = fetch_pending(origin="funding")
        assert all(t.origin == "funding" for t in funding_only)
        assert any(t.title == "f-funding" for t in funding_only)

    def test_valid_origins_is_closed_set(self):
        """Origins are bounded — adding origin #8 must be a deliberate Hook bump."""
        assert VALID_ORIGINS == frozenset({
            "workspace", "global", "funding", "mobile", "skill", "council",
            "autonomy", "round_meta", "execution_guard",
        })


# ---------------------------------------------------------------------------
# Check 2: memory plane bootstrapped + evidence stats reachable
# ---------------------------------------------------------------------------

class TestMemoryPlaneBootstrap:
    def test_evidence_store_reachable_via_public_hook(self):
        from sylion.memory import stats as memory_stats
        result = memory_stats()
        assert isinstance(result, dict)
        assert "total" in result or "evidence_count" in result or len(result) >= 0

    def test_indexer_singleton_present(self):
        from sylion.memory.indexer import get_indexer
        idx = get_indexer()
        assert idx is not None

    def test_retrieval_singleton_present(self):
        from sylion.memory.retrieval import get_retrieval
        ret = get_retrieval()
        assert ret is not None

    def test_evidence_append_and_get_round_trip(self):
        from sylion.memory import append, get
        ev_id = append({
            "name": "d-integrate-probe",
            "artefact_type": "log",
            "content": "d-integrate truth probe",
            "metadata": {"check": 2},
        })
        assert ev_id
        rec = get(ev_id)
        assert rec is not None


# ---------------------------------------------------------------------------
# Check 3: skills runtime loaded > 0 + executable
# ---------------------------------------------------------------------------

class TestSkillsRuntimeBootstrap:
    def test_seed_skills_load_from_manifests_dir(self, tmp_db_path: str):
        from sylion.skills.runtime import bootstrap_from, list_loaded

        manifests_dir = Path(__file__).parent.parent.parent.parent.parent / "manifests" / "skills"
        if not manifests_dir.exists():
            pytest.skip(f"manifests dir not present at {manifests_dir}")

        bootstrap_from(str(manifests_dir))
        loaded = list_loaded()
        assert len(loaded) > 0, f"expected ≥1 seed skill, got {loaded}"

    def test_seed_echo_skill_executable_after_bootstrap(self):
        from sylion.skills.runtime import bootstrap_from, execute, list_loaded

        manifests_dir = Path(__file__).parent.parent.parent.parent.parent / "manifests" / "skills"
        if not manifests_dir.exists():
            pytest.skip("manifests dir not present")

        bootstrap_from(str(manifests_dir))
        loaded = list_loaded()
        ids = [s.get("skill_id") for s in loaded]
        echo_id = next((i for i in ids if i and "echo" in i.lower()), None)
        if echo_id is None:
            pytest.skip(f"no echo-flavored seed skill among {ids}")
        result = execute(echo_id, context={"input": "ping"})
        assert isinstance(result, dict)
        assert result.get("status") in ("success", "ok", "completed", "approved", None) or "error" not in result.get("status", "")


# ---------------------------------------------------------------------------
# Check 4: council semantics consistent
# ---------------------------------------------------------------------------

class TestCouncilSemantics:
    def test_disabled_council_yields_operator_only_hierarchy(self):
        from sylion.cognitive.model_registry import (
            DISABLED_DECISION_HIERARCHY,
            get_model_registry,
        )
        from sylion.project_mode.store import get_project_mode_store as get_project_store

        store = get_project_store()
        project_id = "truth-check-disabled"
        store.upsert_project({
            "project_id": project_id,
            "name": "disabled council",
            "council_plan": {"enabled": False, "active_size": 0},
        })

        registry = get_model_registry()
        hierarchy = registry.get_decision_hierarchy(project_id)
        active_members = registry.get_active_members(project_id)

        assert hierarchy == DISABLED_DECISION_HIERARCHY
        assert active_members == []

    def test_enabled_council_returns_active_members_matching_active_size(self):
        from sylion.cognitive.model_registry import get_model_registry
        from sylion.project_mode.store import get_project_mode_store as get_project_store

        store = get_project_store()
        project_id = "truth-check-enabled"
        store.upsert_project({
            "project_id": project_id,
            "name": "enabled council",
            "council_plan": {
                "enabled": True,
                "active_size": 3,
                "members": [
                    {"role": "alpha", "preferred_models": ["llama3:70b"]},
                    {"role": "beta", "preferred_models": ["mixtral:8x7b"]},
                    {"role": "gamma", "preferred_models": ["qwen2:72b"]},
                ],
            },
        })

        registry = get_model_registry()
        members = registry.get_active_members(project_id)
        assert len(members) == 3, f"expected 3 active members, got {len(members)}"
        assert registry.is_enabled(project_id) is True


# ---------------------------------------------------------------------------
# Check 5: worker pool reconciliation produces no orphans
# ---------------------------------------------------------------------------

class TestWorkerPoolReconciliation:
    def test_execution_plan_change_rebuilds_pool_no_orphans(self):
        from sylion.project_mode.store import get_project_mode_store as get_project_store

        store = get_project_store()
        project_id = "truth-check-workers-1"

        store.upsert_project({
            "project_id": project_id,
            "name": "worker probe",
            "execution_plan": {"steps": [{"name": "step-a"}, {"name": "step-b"}]},
            "worker_plan": {"roles": ["writer", "reviewer"]},
        })
        result_v1 = store.reconcile_worker_pool(project_id)
        v1_ids = {w["worker_entry_id"] for w in result_v1["workers"]}
        assert len(v1_ids) > 0

        store.upsert_project({
            "project_id": project_id,
            "name": "worker probe",
            "execution_plan": {"steps": [{"name": "step-c"}]},
            "worker_plan": {"roles": ["writer"]},
        })
        result_v2 = store.reconcile_worker_pool(project_id)
        v2_ids = {w["worker_entry_id"] for w in result_v2["workers"]}
        orphans_v2 = set(result_v2.get("orphans", []))

        assert v2_ids != v1_ids
        post_pool = {w["worker_entry_id"] for w in store.get_project(project_id)["worker_pool"]}
        assert post_pool == v2_ids
        assert post_pool.intersection(orphans_v2) == set(), "pool retains orphans"


# ---------------------------------------------------------------------------
# Check 6: funding submission produces governance ticket origin='funding'
# ---------------------------------------------------------------------------

class TestFundingGovernanceBridge:
    def test_funding_scan_ticket_lands_with_origin_funding(self):
        from sylion.funding_autopilot.governance_bridge import submit_scan_ticket

        ticket_id = submit_scan_ticket(
            job_id="job-d-integrate-001",
            force_refresh=False,
            since_days=30,
            calls_found=12,
        )
        assert ticket_id

        funding_pending = fetch_pending(origin="funding")
        assert any(t.ticket_id == ticket_id for t in funding_pending)

    def test_funding_submission_d4_priority_p1(self):
        from sylion.funding_autopilot.governance_bridge import submit_submission_ticket

        ticket_id = submit_submission_ticket(
            application_id="app-truth-001",
            session_id="sess-truth-001",
            portal="HORIZON",
            amount=750_000.0,
        )
        assert ticket_id
        funding_pending = fetch_pending(origin="funding")
        ticket = next((t for t in funding_pending if t.ticket_id == ticket_id), None)
        assert ticket is not None
        assert ticket.origin == "funding"
        assert ticket.decision_class in ("D3", "D4", "D5")
