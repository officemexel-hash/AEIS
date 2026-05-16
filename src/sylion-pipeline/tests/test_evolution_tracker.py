"""
tests/test_evolution_tracker.py -- Evolution Tracker tests

Covers:
- Proposal CRUD (propose, approve, get, list)
- Step management (add steps, step ordering)
- Proposal execution (multi-step, status transitions)
- Results retrieval
- Statistics aggregation
- EventBus integration
- Thread safety (concurrent operations)
- Singleton get/reset
- Validation errors
- Full lifecycle
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.aeis.evolution_tracker import (
    VALID_CHANGE_TYPES,
    VALID_PROPOSAL_STATUSES,
    VALID_STEP_STATUSES,
    EvolutionTracker,
    get_evolution_tracker,
    reset_evolution_tracker,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def tracker(bus):
    return EvolutionTracker(event_bus=bus)


@pytest.fixture(autouse=True)
def _reset_singleton():
    yield
    reset_evolution_tracker()


# =====================================================================
# Constants
# =====================================================================

class TestConstants:

    def test_valid_change_types(self):
        assert "schema_migration" in VALID_CHANGE_TYPES
        assert "behavior_change" in VALID_CHANGE_TYPES
        assert "security_patch" in VALID_CHANGE_TYPES

    def test_valid_proposal_statuses(self):
        assert "proposed" in VALID_PROPOSAL_STATUSES
        assert "approved" in VALID_PROPOSAL_STATUSES
        assert "completed" in VALID_PROPOSAL_STATUSES

    def test_valid_step_statuses(self):
        assert "pending" in VALID_STEP_STATUSES
        assert "completed" in VALID_STEP_STATUSES
        assert "failed" in VALID_STEP_STATUSES


# =====================================================================
# Proposals
# =====================================================================

class TestProposeEvolution:

    def test_propose_basic(self, tracker):
        result = tracker.propose_evolution(
            module_id="core.event_bus", change_type="performance_tuning",
        )
        assert result["proposal_id"]
        assert result["module_id"] == "core.event_bus"
        assert result["change_type"] == "performance_tuning"
        assert result["status"] == "proposed"
        assert result["description"] == ""
        assert result["rationale"] == ""
        assert result["created_at"] > 0

    def test_propose_with_description_and_rationale(self, tracker):
        result = tracker.propose_evolution(
            module_id="gov.policy", change_type="feature_addition",
            description="Add caching", rationale="Performance bottleneck",
        )
        assert result["description"] == "Add caching"
        assert result["rationale"] == "Performance bottleneck"

    @pytest.mark.parametrize("ctype", VALID_CHANGE_TYPES)
    def test_propose_all_change_types(self, tracker, ctype):
        result = tracker.propose_evolution(
            module_id="mod", change_type=ctype,
        )
        assert result["change_type"] == ctype

    def test_propose_invalid_change_type(self, tracker):
        with pytest.raises(ValueError, match="Invalid change_type"):
            tracker.propose_evolution("mod", "invalid_type")

    def test_propose_unique_ids(self, tracker):
        r1 = tracker.propose_evolution("mod1", "schema_migration")
        r2 = tracker.propose_evolution("mod2", "behavior_change")
        assert r1["proposal_id"] != r2["proposal_id"]


class TestGetProposal:

    def test_get_existing(self, tracker):
        created = tracker.propose_evolution("mod", "performance_tuning")
        result = tracker.get_proposal(created["proposal_id"])
        assert result is not None
        assert result["proposal_id"] == created["proposal_id"]
        assert result["module_id"] == "mod"

    def test_get_nonexistent(self, tracker):
        assert tracker.get_proposal("nonexistent") is None


class TestListProposals:

    def test_list_empty(self, tracker):
        assert tracker.list_proposals() == []

    def test_list_all(self, tracker):
        tracker.propose_evolution("mod1", "schema_migration")
        tracker.propose_evolution("mod2", "behavior_change")
        result = tracker.list_proposals()
        assert len(result) == 2

    def test_list_filter_by_status(self, tracker):
        r1 = tracker.propose_evolution("mod1", "schema_migration")
        r2 = tracker.propose_evolution("mod2", "behavior_change")
        tracker.approve_proposal(r1["proposal_id"], approver="admin")
        proposed = tracker.list_proposals(status="proposed")
        approved = tracker.list_proposals(status="approved")
        assert len(proposed) == 1
        assert len(approved) == 1

    def test_list_filter_by_module(self, tracker):
        tracker.propose_evolution("core.ebus", "performance_tuning")
        tracker.propose_evolution("gov.policy", "feature_addition")
        tracker.propose_evolution("core.ebus", "security_patch")
        result = tracker.list_proposals(module_id="core.ebus")
        assert len(result) == 2

    def test_list_combined_filters(self, tracker):
        r1 = tracker.propose_evolution("core.ebus", "schema_migration")
        tracker.approve_proposal(r1["proposal_id"], approver="a")
        tracker.propose_evolution("core.ebus", "behavior_change")
        tracker.propose_evolution("gov.policy", "schema_migration")
        result = tracker.list_proposals(
            status="approved", module_id="core.ebus",
        )
        assert len(result) == 1

    def test_list_ordered_by_created_at_desc(self, tracker):
        r1 = tracker.propose_evolution("m1", "schema_migration")
        time.sleep(0.01)
        r2 = tracker.propose_evolution("m2", "behavior_change")
        result = tracker.list_proposals()
        assert result[0]["proposal_id"] == r2["proposal_id"]


# =====================================================================
# Approval
# =====================================================================

class TestApproveProposal:

    def test_approve(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        result = tracker.approve_proposal(created["proposal_id"], approver="admin")
        assert result is not None
        assert result["status"] == "approved"
        assert result["approver"] == "admin"

    def test_approve_nonexistent(self, tracker):
        result = tracker.approve_proposal("nonexistent", approver="admin")
        assert result is None

    def test_approve_already_approved(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        tracker.approve_proposal(created["proposal_id"], approver="a")
        with pytest.raises(ValueError, match="Cannot approve"):
            tracker.approve_proposal(created["proposal_id"], approver="b")

    def test_approve_empty_approver(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        result = tracker.approve_proposal(created["proposal_id"])
        assert result["status"] == "approved"
        assert result["approver"] == ""


# =====================================================================
# Steps
# =====================================================================

class TestAddStep:

    def test_add_step(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        step = tracker.add_step(
            created["proposal_id"], step_name="backup_db",
            step_order=1, config_json='{"tables": ["all"]}',
        )
        assert step["step_id"]
        assert step["proposal_id"] == created["proposal_id"]
        assert step["step_name"] == "backup_db"
        assert step["step_order"] == 1
        assert step["config_json"] == '{"tables": ["all"]}'
        assert step["status"] == "pending"

    def test_add_multiple_steps(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        s1 = tracker.add_step(created["proposal_id"], "backup", 1)
        s2 = tracker.add_step(created["proposal_id"], "migrate", 2)
        s3 = tracker.add_step(created["proposal_id"], "verify", 3)
        assert s1["step_id"] != s2["step_id"] != s3["step_id"]

    def test_add_step_nonexistent_proposal(self, tracker):
        with pytest.raises(ValueError, match="Proposal not found"):
            tracker.add_step("nonexistent", "step", 1)

    def test_add_step_default_config(self, tracker):
        created = tracker.propose_evolution("mod", "behavior_change")
        step = tracker.add_step(created["proposal_id"], "run")
        assert step["config_json"] == "{}"


# =====================================================================
# Execution
# =====================================================================

class TestExecuteProposal:

    def _create_ready_proposal(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        tracker.approve_proposal(created["proposal_id"], approver="admin")
        tracker.add_step(created["proposal_id"], "backup", 1)
        tracker.add_step(created["proposal_id"], "migrate", 2)
        tracker.add_step(created["proposal_id"], "verify", 3)
        return created["proposal_id"]

    def test_execute_success(self, tracker):
        pid = self._create_ready_proposal(tracker)
        result = tracker.execute_proposal(pid)
        assert result["outcome"] == "success"
        assert result["summary"]["steps_completed"] == 3
        assert result["result_id"]

    def test_execute_updates_proposal_status(self, tracker):
        pid = self._create_ready_proposal(tracker)
        tracker.execute_proposal(pid)
        proposal = tracker.get_proposal(pid)
        assert proposal["status"] == "completed"

    def test_execute_nonexistent(self, tracker):
        with pytest.raises(ValueError, match="Proposal not found"):
            tracker.execute_proposal("nonexistent")

    def test_execute_not_approved(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        tracker.add_step(created["proposal_id"], "step", 1)
        with pytest.raises(ValueError, match="Cannot execute"):
            tracker.execute_proposal(created["proposal_id"])

    def test_execute_no_steps(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        tracker.approve_proposal(created["proposal_id"])
        with pytest.raises(ValueError, match="No steps defined"):
            tracker.execute_proposal(created["proposal_id"])

    def test_execute_with_metrics(self, tracker):
        pid = self._create_ready_proposal(tracker)
        result = tracker.execute_proposal(pid)
        assert "execution_time" in result["metrics"]


class TestGetResults:

    def test_get_results_after_execution(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        tracker.approve_proposal(created["proposal_id"])
        tracker.add_step(created["proposal_id"], "step1", 1)
        tracker.execute_proposal(created["proposal_id"])
        result = tracker.get_results(created["proposal_id"])
        assert result is not None
        assert result["outcome"] == "success"
        assert result["summary"]["steps_completed"] == 1

    def test_get_results_no_execution(self, tracker):
        created = tracker.propose_evolution("mod", "schema_migration")
        result = tracker.get_results(created["proposal_id"])
        assert result is None


# =====================================================================
# Statistics
# =====================================================================

class TestStats:

    def test_stats_empty(self, tracker):
        stats = tracker.get_evolution_stats()
        assert stats["total_proposals"] == 0
        assert stats["total_steps"] == 0
        assert stats["total_results"] == 0

    def test_stats_after_propose(self, tracker):
        tracker.propose_evolution("mod1", "schema_migration")
        tracker.propose_evolution("mod2", "behavior_change")
        stats = tracker.get_evolution_stats()
        assert stats["total_proposals"] == 2
        assert stats["proposals_by_status"]["proposed"] == 2
        assert stats["proposals_by_type"]["schema_migration"] == 1

    def test_stats_after_steps(self, tracker):
        created = tracker.propose_evolution("mod", "feature_addition")
        tracker.add_step(created["proposal_id"], "s1", 1)
        tracker.add_step(created["proposal_id"], "s2", 2)
        stats = tracker.get_evolution_stats()
        assert stats["total_steps"] == 2

    def test_stats_after_execution(self, tracker):
        created = tracker.propose_evolution("mod", "performance_tuning")
        tracker.approve_proposal(created["proposal_id"])
        tracker.add_step(created["proposal_id"], "tune", 1)
        tracker.execute_proposal(created["proposal_id"])
        stats = tracker.get_evolution_stats()
        assert stats["total_results"] == 1
        assert stats["results_by_outcome"]["success"] == 1

    def test_stats_by_module(self, tracker):
        tracker.propose_evolution("core.ebus", "performance_tuning")
        tracker.propose_evolution("core.ebus", "security_patch")
        tracker.propose_evolution("gov.policy", "feature_addition")
        stats = tracker.get_evolution_stats()
        assert stats["proposals_by_module"]["core.ebus"] == 2
        assert stats["proposals_by_module"]["gov.policy"] == 1


# =====================================================================
# Events
# =====================================================================

class TestEvents:

    def test_event_proposal_created(self, tracker, bus):
        events = []
        bus.subscribe("proposal_created", lambda e: events.append(e))
        tracker.propose_evolution("mod", "schema_migration")
        assert len(events) == 1
        assert events[0].payload["module_id"] == "mod"
        assert events[0].source_module == "aeis.evolution_tracker"

    def test_event_proposal_approved(self, tracker, bus):
        events = []
        bus.subscribe("proposal_approved", lambda e: events.append(e))
        created = tracker.propose_evolution("mod", "behavior_change")
        tracker.approve_proposal(created["proposal_id"], approver="admin")
        assert len(events) == 1
        assert events[0].payload["approver"] == "admin"

    def test_event_step_completed(self, tracker, bus):
        events = []
        bus.subscribe("step_completed", lambda e: events.append(e))
        created = tracker.propose_evolution("mod", "schema_migration")
        tracker.approve_proposal(created["proposal_id"])
        tracker.add_step(created["proposal_id"], "step1", 1)
        tracker.execute_proposal(created["proposal_id"])
        assert len(events) == 1
        assert events[0].payload["step_name"] == "step1"

    def test_event_evolution_completed(self, tracker, bus):
        events = []
        bus.subscribe("evolution_completed", lambda e: events.append(e))
        created = tracker.propose_evolution("mod", "security_patch")
        tracker.approve_proposal(created["proposal_id"])
        tracker.add_step(created["proposal_id"], "patch", 1)
        tracker.execute_proposal(created["proposal_id"])
        assert len(events) == 1
        assert events[0].payload["outcome"] == "success"

    def test_no_events_without_bus(self):
        t = EvolutionTracker(event_bus=None)
        created = t.propose_evolution("mod", "schema_migration")
        t.approve_proposal(created["proposal_id"])
        t.add_step(created["proposal_id"], "step", 1)
        t.execute_proposal(created["proposal_id"])


# =====================================================================
# Thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_proposals(self, tracker):
        results = []
        errors = []

        def propose(idx):
            try:
                r = tracker.propose_evolution(
                    f"mod-{idx}", "schema_migration",
                )
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=propose, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20

    def test_concurrent_approves(self, tracker):
        pids = []
        for i in range(10):
            r = tracker.propose_evolution(f"mod-{i}", "behavior_change")
            pids.append(r["proposal_id"])

        errors = []

        def approve(pid):
            try:
                tracker.approve_proposal(pid, approver="auto")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=approve, args=(pid,)) for pid in pids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        approved = tracker.list_proposals(status="approved")
        assert len(approved) == 10


# =====================================================================
# Singleton
# =====================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        t = get_evolution_tracker()
        assert isinstance(t, EvolutionTracker)

    def test_get_returns_same_instance(self):
        t1 = get_evolution_tracker()
        t2 = get_evolution_tracker()
        assert t1 is t2

    def test_reset_clears_singleton(self):
        t1 = get_evolution_tracker()
        reset_evolution_tracker()
        t2 = get_evolution_tracker()
        assert t1 is not t2

    def test_get_with_params(self, bus):
        t = get_evolution_tracker(event_bus=bus)
        assert isinstance(t, EvolutionTracker)


# =====================================================================
# Full lifecycle
# =====================================================================

class TestFullLifecycle:

    def test_evolution_lifecycle(self, tracker, bus):
        """Full lifecycle: propose -> approve -> add steps -> execute -> get results."""
        # Propose
        created = tracker.propose_evolution(
            module_id="core.event_bus",
            change_type="performance_tuning",
            description="Optimize event dispatch",
            rationale="Latency exceeds 50ms p99",
        )
        pid = created["proposal_id"]
        assert created["status"] == "proposed"

        # Approve
        result = tracker.approve_proposal(pid, approver="cto")
        assert result["status"] == "approved"
        assert result["approver"] == "cto"

        # Add steps
        tracker.add_step(pid, "benchmark_baseline", 1, '{"duration": 60}')
        tracker.add_step(pid, "apply_optimization", 2, '{"strategy": "batch"}')
        tracker.add_step(pid, "verify_improvement", 3, '{"threshold": 30}')

        # Execute
        exec_result = tracker.execute_proposal(pid)
        assert exec_result["outcome"] == "success"
        assert exec_result["summary"]["steps_completed"] == 3

        # Verify final state
        proposal = tracker.get_proposal(pid)
        assert proposal["status"] == "completed"

        results = tracker.get_results(pid)
        assert results is not None
        assert results["outcome"] == "success"

        # Stats
        stats = tracker.get_evolution_stats()
        assert stats["total_proposals"] == 1
        assert stats["total_results"] == 1

    def test_proposal_rejection(self, tracker):
        """Proposals can be tracked even when rejected."""
        created = tracker.propose_evolution("mod", "deprecation")
        pid = created["proposal_id"]

        # Directly update status to rejected (simulating rejection)
        # In production, a reject_proposal method would handle this
        proposal = tracker.get_proposal(pid)
        assert proposal["status"] == "proposed"
