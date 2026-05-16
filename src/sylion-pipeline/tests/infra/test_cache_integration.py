"""Phase 3 W1.3 — integration tests proving every cache namespace is wired.

For each of the six canonical namespaces (council.decision, memory.search,
workspace.project, funding.programs, observability.metrics, audit.events)
we assert two contracts:

  1. **Hot path is cached.** The second call hits the cache (stats hit
     counter increments) and avoids the underlying SQL/disk path.
  2. **Writes invalidate.** A subsequent write (vote/index/upsert/scan/
     record) drops the namespace so the next read reflects fresh state.

The test uses the in-memory backend so it works without Redis. Each test
is fully isolated via the autouse ``_clean_cache`` fixture.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from sylion.infra.cache import get_cache, reset_cache


@pytest.fixture(autouse=True)
def _clean_cache(monkeypatch):
    monkeypatch.setenv("SYLION_CACHE_URL", "memory")
    reset_cache()
    yield
    reset_cache()


# ---------------------------------------------------------------- memory.search

class TestMemorySearchCache:
    def test_retrieve_caches_then_invalidates_on_write(self, tmp_path, monkeypatch):
        from sylion.memory.indexer import Indexer
        from sylion.memory.retrieval import Retrieval

        db_path = tmp_path / "mem.db"
        indexer = Indexer(db_path=db_path)
        indexer.index_section("s1", "Council guidelines", "approve quorum vote council")
        retrieval = Retrieval(indexer=indexer)

        cache = get_cache()
        before = cache.stats()
        # First call: miss -> populates cache.
        first = retrieval.retrieve("council quorum", limit=5)
        # Second call: should be a hit.
        second = retrieval.retrieve("council quorum", limit=5)
        after = cache.stats()

        assert first == second
        assert after["hits"] >= before["hits"] + 1, (
            "second retrieve() did not hit the cache"
        )

        # Write should invalidate the namespace.
        indexer.index_section("s2", "Funding rules", "horizon eu grant programme")
        post_write_stats = cache.stats()
        # Cached entry should be gone — third read is a miss again.
        retrieval.retrieve("council quorum", limit=5)
        post_third = cache.stats()
        assert post_third["misses"] > post_write_stats["misses"], (
            "indexer.index_section did not invalidate memory.search cache"
        )


# ---------------------------------------------------------------- workspace.project

class TestWorkspaceProjectCache:
    def test_get_project_caches_then_invalidates_on_upsert(self, tmp_path):
        from sylion.project_mode.store import ProjectModeStore

        db_path = tmp_path / "proj.db"
        store = ProjectModeStore(db_path=str(db_path))
        store.upsert_project({
            "project_id": "proj1",
            "title": "Test",
            "idea": "x",
            "owner_id": "u1",
        })

        cache = get_cache()
        before = cache.stats()
        a = store.get_project("proj1")
        b = store.get_project("proj1")
        after = cache.stats()

        assert a is not None and b is not None and a == b
        assert after["hits"] >= before["hits"] + 1
        assert a["title"] == "Test"

        # upsert must invalidate so the next read sees the new title.
        # (upsert internally calls get_project at the end which warms the
        # cache — but with the *new* state, so no miss is observable here.
        # Correct semantics: the cached value reflects the post-write state.)
        store.upsert_project({
            "project_id": "proj1",
            "title": "Updated",
            "idea": "x",
            "owner_id": "u1",
        })
        c = store.get_project("proj1")
        assert c["title"] == "Updated", (
            "post-upsert read returned stale cached value"
        )

    def test_add_event_invalidates(self, tmp_path):
        from sylion.project_mode.store import ProjectModeStore

        db_path = tmp_path / "proj_evt.db"
        store = ProjectModeStore(db_path=str(db_path))
        store.upsert_project({"project_id": "p2", "title": "t", "idea": "i", "owner_id": "u"})

        store.get_project("p2")        # populate
        store.get_project("p2")        # cache hit
        cache = get_cache()
        pre = cache.stats()

        store.add_event("p2", "stage_advanced", {"to": "canon"})
        store.get_project("p2")        # should miss
        post = cache.stats()
        assert post["misses"] > pre["misses"]


# ---------------------------------------------------------------- council.decision

class TestCouncilDecisionCache:
    def test_tally_caches_then_invalidates_on_vote(self, tmp_path):
        from sylion.governance.council_workflow import (
            CouncilWorkflow,
            SessionStatus,
            Vote,
            VoteValue,
        )
        from sylion.core.decision_gate_engine import DecisionClass

        db_path = tmp_path / "council.db"
        wf = CouncilWorkflow(db_path=str(db_path))
        # Open a D3 session manually
        from sylion.governance.council_workflow import CouncilSession

        session = CouncilSession(
            session_id="sess1",
            proposal_id="prop1",
            decision_class=DecisionClass.D3,
            opened_at=0.0,
            required_quorum=3,
            status=SessionStatus.OPEN,
        )
        wf.open_session(session)

        cache = get_cache()
        first = wf.tally("sess1")
        before = cache.stats()
        second = wf.tally("sess1")
        after = cache.stats()
        assert first == second
        assert after["hits"] >= before["hits"] + 1

        # Cast a vote -> invalidates tally cache.
        wf.cast_vote(Vote(
            vote_id="v1", session_id="sess1", member_id="m1",
            value=VoteValue.APPROVE, rationale="lgtm", timestamp=1.0,
        ))
        wf.tally("sess1")
        post_vote = cache.stats()
        assert post_vote["misses"] > after["misses"]


# ---------------------------------------------------------------- funding.programs

class TestFundingProgramsCache:
    def test_list_calls_caches_then_invalidates_on_create(self, tmp_path, monkeypatch):
        from sylion.funding_autopilot.store import FundingAutopilotStore

        db_path = tmp_path / "funding.db"
        store = FundingAutopilotStore(db_path=str(db_path))
        store.create_programme({
            "programme_id": "prog1", "name": "Test", "country": "PL",
        })

        cache = get_cache()
        a = store.list_calls()
        before = cache.stats()
        b = store.list_calls()
        after = cache.stats()
        assert a == b == []
        assert after["hits"] >= before["hits"] + 1

        # Insert a call -> invalidates.
        store.create_call({
            "call_id": "call1", "programme_id": "prog1",
            "title": "First call", "code": "FIRST",
        })
        store.list_calls()
        post = cache.stats()
        assert post["misses"] > after["misses"]


# ---------------------------------------------------------------- audit.events

class TestAuditEventsCache:
    def test_query_caches_then_invalidates_on_record(self, tmp_path):
        from sylion.security.audit_trail_aggregator import (
            AuditTrailAggregator,
        )

        db_path = tmp_path / "audit.db"
        agg = AuditTrailAggregator(db_path=str(db_path))
        agg.record(
            source="api", action="x", actor="alice",
            resource="r1", outcome="success",
        )

        cache = get_cache()
        a = agg.query(source="api", limit=10)
        before = cache.stats()
        b = agg.query(source="api", limit=10)
        after = cache.stats()
        assert a == b
        assert after["hits"] >= before["hits"] + 1

        # New record invalidates query cache.
        agg.record(
            source="api", action="y", actor="bob",
            resource="r2", outcome="success",
        )
        agg.query(source="api", limit=10)
        post = cache.stats()
        assert post["misses"] > after["misses"]


# ---------------------------------------------------------------- observability.metrics

class TestObservabilityMetricsCache:
    def test_list_metrics_decorator_active(self):
        # Confirms the existing @cached decorator on list_metrics is still
        # wired after this scope-fill pass — guards against regression.
        from sylion.api.observability_routes import list_metrics

        cache = get_cache()
        list_metrics()                  # warm
        before = cache.stats()
        list_metrics()                  # hit
        after = cache.stats()
        assert after["hits"] >= before["hits"] + 1


# ---------------------------------------------------------------- coverage manifest

def test_all_six_namespaces_have_default_ttl():
    """Sanity: every namespace declared in the W1.3 docstring has a TTL."""
    from sylion.infra.cache import _NAMESPACES
    expected = {
        "council.decision",
        "memory.search",
        "workspace.project",
        "funding.programs",
        "observability.metrics",
        "audit.events",
    }
    assert expected.issubset(set(_NAMESPACES.keys()))
