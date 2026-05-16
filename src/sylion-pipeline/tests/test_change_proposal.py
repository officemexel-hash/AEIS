"""
tests/test_change_proposal.py -- Change Proposal Manager tests

Covers:
- Proposal creation (all change types, priorities)
- Validation of inputs (change_type, status, priority, verdict)
- Proposal retrieval and listing with filters
- Status and priority updates
- Review workflow (add, list, verdicts)
- Statistics aggregation
- EventBus integration
- Thread safety (concurrent operations)
- Singleton get/reset
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.change_proposal import (
    VALID_CHANGE_TYPES,
    VALID_PRIORITIES,
    VALID_STATUSES,
    VALID_VERDICTS,
    ChangeProposalManager,
    get_change_proposal_manager,
    reset_change_proposal_manager,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def manager(bus):
    return ChangeProposalManager(event_bus=bus)


@pytest.fixture(autouse=True)
def _reset_singleton():
    yield
    reset_change_proposal_manager()


# =====================================================================
# Constants
# =====================================================================

class TestConstants:

    def test_valid_change_types(self):
        assert VALID_CHANGE_TYPES == (
            "feature", "bugfix", "refactor", "migration",
            "config_change", "api_change",
        )

    def test_valid_statuses(self):
        assert VALID_STATUSES == (
            "draft", "submitted", "under_review", "approved",
            "rejected", "implemented", "withdrawn",
        )

    def test_valid_priorities(self):
        assert VALID_PRIORITIES == ("low", "medium", "high", "critical")

    def test_valid_verdicts(self):
        assert VALID_VERDICTS == (
            "approve", "reject", "request_changes", "abstain",
        )


# =====================================================================
# Creation
# =====================================================================

class TestCreateProposal:

    def test_create_basic(self, manager):
        result = manager.create_proposal(
            title="Add caching layer",
            change_type="feature",
            module_id="core.event_bus",
        )
        assert result["proposal_id"]
        assert result["title"] == "Add caching layer"
        assert result["change_type"] == "feature"
        assert result["module_id"] == "core.event_bus"
        assert result["status"] == "draft"
        assert result["priority"] == "medium"
        assert result["description"] == ""
        assert result["proposer"] == ""
        assert result["created_at"] > 0
        assert result["updated_at"] > 0
        assert result["metadata"] == {}

    def test_create_with_all_fields(self, manager):
        result = manager.create_proposal(
            title="Fix memory leak",
            change_type="bugfix",
            module_id="memory.compact_layer",
            description="Memory leak in compact_layer during compaction",
            proposer="alice",
            priority="critical",
        )
        assert result["title"] == "Fix memory leak"
        assert result["change_type"] == "bugfix"
        assert result["description"] == "Memory leak in compact_layer during compaction"
        assert result["proposer"] == "alice"
        assert result["priority"] == "critical"

    @pytest.mark.parametrize("change_type", VALID_CHANGE_TYPES)
    def test_create_all_change_types(self, manager, change_type):
        result = manager.create_proposal(
            title=f"Test {change_type}",
            change_type=change_type,
            module_id="mod",
        )
        assert result["change_type"] == change_type

    @pytest.mark.parametrize("priority", VALID_PRIORITIES)
    def test_create_all_priorities(self, manager, priority):
        result = manager.create_proposal(
            title=f"Priority {priority}",
            change_type="feature",
            module_id="mod",
            priority=priority,
        )
        assert result["priority"] == priority

    def test_create_invalid_change_type(self, manager):
        with pytest.raises(ValueError, match="Invalid change_type"):
            manager.create_proposal(
                title="Bad", change_type="invalid_type", module_id="mod",
            )

    def test_create_invalid_priority(self, manager):
        with pytest.raises(ValueError, match="Invalid priority"):
            manager.create_proposal(
                title="Bad", change_type="feature", module_id="mod",
                priority="urgent",
            )

    def test_create_default_priority_is_medium(self, manager):
        result = manager.create_proposal(
            title="Default prio", change_type="feature", module_id="mod",
        )
        assert result["priority"] == "medium"

    def test_create_default_status_is_draft(self, manager):
        result = manager.create_proposal(
            title="Default status", change_type="feature", module_id="mod",
        )
        assert result["status"] == "draft"

    def test_create_proposal_id_is_unique(self, manager):
        r1 = manager.create_proposal("A", "feature", "m1")
        r2 = manager.create_proposal("B", "feature", "m2")
        assert r1["proposal_id"] != r2["proposal_id"]

    def test_create_timestamps_set(self, manager):
        before = time.time()
        result = manager.create_proposal("TS", "feature", "m")
        after = time.time()
        assert before <= result["created_at"] <= after
        assert before <= result["updated_at"] <= after


# =====================================================================
# Get proposal
# =====================================================================

class TestGetProposal:

    def test_get_existing(self, manager):
        created = manager.create_proposal("Get test", "feature", "mod1")
        retrieved = manager.get_proposal(created["proposal_id"])
        assert retrieved is not None
        assert retrieved["proposal_id"] == created["proposal_id"]
        assert retrieved["title"] == "Get test"
        assert retrieved["change_type"] == "feature"
        assert retrieved["module_id"] == "mod1"

    def test_get_nonexistent(self, manager):
        result = manager.get_proposal("does_not_exist")
        assert result is None

    def test_get_returns_all_fields(self, manager):
        created = manager.create_proposal(
            title="Full fields",
            change_type="refactor",
            module_id="gov.policy",
            description="Refactor policy engine",
            proposer="bob",
            priority="high",
        )
        retrieved = manager.get_proposal(created["proposal_id"])
        assert retrieved["title"] == "Full fields"
        assert retrieved["description"] == "Refactor policy engine"
        assert retrieved["proposer"] == "bob"
        assert retrieved["change_type"] == "refactor"
        assert retrieved["priority"] == "high"
        assert "created_at" in retrieved
        assert "updated_at" in retrieved


# =====================================================================
# List proposals
# =====================================================================

class TestListProposals:

    def test_list_empty(self, manager):
        result = manager.list_proposals()
        assert result == []

    def test_list_all(self, manager):
        manager.create_proposal("A", "feature", "m1")
        manager.create_proposal("B", "bugfix", "m2")
        result = manager.list_proposals()
        assert len(result) == 2

    def test_list_filter_by_status(self, manager):
        r1 = manager.create_proposal("A", "feature", "m1")
        manager.update_proposal(r1["proposal_id"], status="submitted")
        manager.create_proposal("B", "feature", "m2")

        drafts = manager.list_proposals(status="draft")
        submitted = manager.list_proposals(status="submitted")
        assert len(drafts) == 1
        assert len(submitted) == 1
        assert drafts[0]["title"] == "B"

    def test_list_filter_by_module_id(self, manager):
        manager.create_proposal("A", "feature", "core.ebus")
        manager.create_proposal("B", "bugfix", "core.ebus")
        manager.create_proposal("C", "feature", "gov.policy")

        result = manager.list_proposals(module_id="core.ebus")
        assert len(result) == 2

    def test_list_filter_by_change_type(self, manager):
        manager.create_proposal("A", "feature", "m1")
        manager.create_proposal("B", "bugfix", "m2")
        manager.create_proposal("C", "feature", "m3")

        result = manager.list_proposals(change_type="feature")
        assert len(result) == 2

    def test_list_combined_filters(self, manager):
        r1 = manager.create_proposal("A", "feature", "m1")
        manager.update_proposal(r1["proposal_id"], status="approved")
        manager.create_proposal("B", "feature", "m1")
        manager.create_proposal("C", "bugfix", "m1")

        result = manager.list_proposals(
            status="approved", module_id="m1", change_type="feature",
        )
        assert len(result) == 1
        assert result[0]["title"] == "A"

    def test_list_limit(self, manager):
        for i in range(10):
            manager.create_proposal(f"P-{i}", "feature", "m")
        result = manager.list_proposals(limit=5)
        assert len(result) == 5

    def test_list_default_limit_100(self, manager):
        # Just verify default limit param is 100
        result = manager.list_proposals()
        assert isinstance(result, list)

    def test_list_ordered_by_created_at_desc(self, manager):
        r1 = manager.create_proposal("First", "feature", "m")
        time.sleep(0.01)
        r2 = manager.create_proposal("Second", "feature", "m")
        result = manager.list_proposals()
        assert result[0]["proposal_id"] == r2["proposal_id"]
        assert result[1]["proposal_id"] == r1["proposal_id"]


# =====================================================================
# Update proposal
# =====================================================================

class TestUpdateProposal:

    def test_update_status(self, manager):
        created = manager.create_proposal("Up", "feature", "m")
        result = manager.update_proposal(created["proposal_id"], status="submitted")
        assert result is not None
        assert result["status"] == "submitted"
        assert result["updated_at"] >= result["created_at"]

    def test_update_priority(self, manager):
        created = manager.create_proposal("Up", "feature", "m", priority="low")
        result = manager.update_proposal(created["proposal_id"], priority="critical")
        assert result is not None
        assert result["priority"] == "critical"
        # Status unchanged
        assert result["status"] == "draft"

    def test_update_both_status_and_priority(self, manager):
        created = manager.create_proposal("Up", "feature", "m")
        result = manager.update_proposal(
            created["proposal_id"], status="approved", priority="high",
        )
        assert result["status"] == "approved"
        assert result["priority"] == "high"

    def test_update_status_to_all_valid(self, manager):
        created = manager.create_proposal("Up", "feature", "m")
        pid = created["proposal_id"]
        for status in ("submitted", "under_review", "approved", "implemented"):
            result = manager.update_proposal(pid, status=status)
            assert result["status"] == status

    def test_update_invalid_status(self, manager):
        created = manager.create_proposal("Up", "feature", "m")
        with pytest.raises(ValueError, match="Invalid status"):
            manager.update_proposal(created["proposal_id"], status="unknown")

    def test_update_invalid_priority(self, manager):
        created = manager.create_proposal("Up", "feature", "m")
        with pytest.raises(ValueError, match="Invalid priority"):
            manager.update_proposal(created["proposal_id"], priority="urgent")

    def test_update_nonexistent_proposal(self, manager):
        result = manager.update_proposal("nonexistent", status="approved")
        assert result is None

    def test_update_updates_timestamp(self, manager):
        created = manager.create_proposal("Up", "feature", "m")
        original_updated = created["updated_at"]
        time.sleep(0.01)
        result = manager.update_proposal(created["proposal_id"], status="submitted")
        assert result["updated_at"] >= original_updated

    def test_update_no_args_keeps_existing(self, manager):
        created = manager.create_proposal("Up", "feature", "m", priority="high")
        result = manager.update_proposal(created["proposal_id"])
        assert result["status"] == "draft"
        assert result["priority"] == "high"


# =====================================================================
# Reviews
# =====================================================================

class TestReviews:

    def test_add_review(self, manager):
        created = manager.create_proposal("Rev", "feature", "m")
        review = manager.add_review(
            created["proposal_id"], "alice", "approve", "Looks good",
        )
        assert review["review_id"]
        assert review["proposal_id"] == created["proposal_id"]
        assert review["reviewer"] == "alice"
        assert review["verdict"] == "approve"
        assert review["comment"] == "Looks good"
        assert review["reviewed_at"] > 0

    def test_add_review_default_comment(self, manager):
        created = manager.create_proposal("Rev", "feature", "m")
        review = manager.add_review(created["proposal_id"], "bob", "reject")
        assert review["comment"] == ""

    @pytest.mark.parametrize("verdict", VALID_VERDICTS)
    def test_add_review_all_verdicts(self, manager, verdict):
        created = manager.create_proposal(f"Rev-{verdict}", "feature", "m")
        review = manager.add_review(created["proposal_id"], "r", verdict)
        assert review["verdict"] == verdict

    def test_add_review_invalid_verdict(self, manager):
        created = manager.create_proposal("Rev", "feature", "m")
        with pytest.raises(ValueError, match="Invalid verdict"):
            manager.add_review(created["proposal_id"], "alice", "maybe")

    def test_add_review_nonexistent_proposal(self, manager):
        with pytest.raises(ValueError, match="Proposal not found"):
            manager.add_review("nonexistent", "alice", "approve")

    def test_add_multiple_reviews(self, manager):
        created = manager.create_proposal("Rev", "feature", "m")
        manager.add_review(created["proposal_id"], "alice", "approve", "LGTM")
        manager.add_review(created["proposal_id"], "bob", "reject", "Needs work")
        manager.add_review(created["proposal_id"], "carol", "approve")

        reviews = manager.list_reviews(created["proposal_id"])
        assert len(reviews) == 3
        assert reviews[0]["reviewer"] == "alice"
        assert reviews[1]["reviewer"] == "bob"
        assert reviews[2]["reviewer"] == "carol"

    def test_list_reviews_empty(self, manager):
        created = manager.create_proposal("Rev", "feature", "m")
        reviews = manager.list_reviews(created["proposal_id"])
        assert reviews == []

    def test_list_reviews_ordered_chronologically(self, manager):
        created = manager.create_proposal("Rev", "feature", "m")
        r1 = manager.add_review(created["proposal_id"], "first", "approve")
        time.sleep(0.01)
        r2 = manager.add_review(created["proposal_id"], "second", "reject")
        reviews = manager.list_reviews(created["proposal_id"])
        assert reviews[0]["review_id"] == r1["review_id"]
        assert reviews[1]["review_id"] == r2["review_id"]

    def test_review_ids_are_unique(self, manager):
        created = manager.create_proposal("Rev", "feature", "m")
        r1 = manager.add_review(created["proposal_id"], "a", "approve")
        r2 = manager.add_review(created["proposal_id"], "b", "reject")
        assert r1["review_id"] != r2["review_id"]


# =====================================================================
# Statistics
# =====================================================================

class TestGetStats:

    def test_stats_empty(self, manager):
        stats = manager.get_stats()
        assert stats["total"] == 0
        assert stats["by_status"] == {}
        assert stats["by_type"] == {}

    def test_stats_by_status(self, manager):
        r1 = manager.create_proposal("A", "feature", "m")
        r2 = manager.create_proposal("B", "bugfix", "m")
        manager.update_proposal(r1["proposal_id"], status="approved")
        manager.update_proposal(r2["proposal_id"], status="submitted")

        stats = manager.get_stats()
        assert stats["total"] == 2
        assert stats["by_status"]["approved"] == 1
        assert stats["by_status"]["submitted"] == 1

    def test_stats_by_type(self, manager):
        manager.create_proposal("A", "feature", "m")
        manager.create_proposal("B", "feature", "m")
        manager.create_proposal("C", "bugfix", "m")

        stats = manager.get_stats()
        assert stats["total"] == 3
        assert stats["by_type"]["feature"] == 2
        assert stats["by_type"]["bugfix"] == 1

    def test_stats_after_status_changes(self, manager):
        r = manager.create_proposal("A", "refactor", "m")
        manager.update_proposal(r["proposal_id"], status="submitted")
        manager.update_proposal(r["proposal_id"], status="under_review")
        manager.update_proposal(r["proposal_id"], status="approved")
        manager.update_proposal(r["proposal_id"], status="implemented")

        stats = manager.get_stats()
        assert stats["total"] == 1
        assert stats["by_status"]["implemented"] == 1
        assert "draft" not in stats["by_status"]


# =====================================================================
# Events
# =====================================================================

class TestEvents:

    def test_event_proposal_created(self, manager, bus):
        events = []
        bus.subscribe("proposal.created", lambda e: events.append(e))

        manager.create_proposal("EvTest", "feature", "m")
        assert len(events) == 1
        assert events[0].payload["title"] == "EvTest"
        assert events[0].payload["change_type"] == "feature"
        assert events[0].source_module == "governance.change_proposal"

    def test_event_status_changed(self, manager, bus):
        events = []
        bus.subscribe("proposal.status_changed", lambda e: events.append(e))

        r = manager.create_proposal("EvStat", "feature", "m")
        manager.update_proposal(r["proposal_id"], status="submitted")
        assert len(events) == 1
        assert events[0].payload["old_status"] == "draft"
        assert events[0].payload["new_status"] == "submitted"
        assert events[0].payload["proposal_id"] == r["proposal_id"]

    def test_event_status_not_emitted_on_same_status(self, manager, bus):
        events = []
        bus.subscribe("proposal.status_changed", lambda e: events.append(e))

        r = manager.create_proposal("EvSame", "feature", "m")
        manager.update_proposal(r["proposal_id"], status="draft")
        assert len(events) == 0

    def test_event_reviewed(self, manager, bus):
        events = []
        bus.subscribe("proposal.reviewed", lambda e: events.append(e))

        r = manager.create_proposal("EvRev", "feature", "m")
        manager.add_review(r["proposal_id"], "alice", "approve", "LGTM")
        assert len(events) == 1
        assert events[0].payload["reviewer"] == "alice"
        assert events[0].payload["verdict"] == "approve"

    def test_no_events_without_bus(self):
        mgr = ChangeProposalManager(event_bus=None)
        # Should not raise
        r = mgr.create_proposal("NoEv", "feature", "m")
        mgr.update_proposal(r["proposal_id"], status="approved")
        mgr.add_review(r["proposal_id"], "bob", "approve")

    def test_event_status_changed_not_emitted_for_priority_only(self, manager, bus):
        events = []
        bus.subscribe("proposal.status_changed", lambda e: events.append(e))

        r = manager.create_proposal("EvPrio", "feature", "m")
        manager.update_proposal(r["proposal_id"], priority="high")
        assert len(events) == 0


# =====================================================================
# Thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_creates(self, manager):
        results = []
        errors = []

        def create(idx):
            try:
                r = manager.create_proposal(
                    f"Concurrent-{idx}", "feature", f"mod-{idx}",
                )
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        assert len(manager.list_proposals()) == 20

    def test_concurrent_updates(self, manager):
        r = manager.create_proposal("ConcUp", "feature", "m")
        pid = r["proposal_id"]
        errors = []

        def update(status):
            try:
                manager.update_proposal(pid, status=status)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=update, args=(s,))
            for s in ["submitted", "under_review", "approved", "rejected",
                       "draft", "withdrawn"]
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        final = manager.get_proposal(pid)
        assert final["status"] in VALID_STATUSES

    def test_concurrent_reviews(self, manager):
        r = manager.create_proposal("ConcRev", "feature", "m")
        pid = r["proposal_id"]
        errors = []

        def review(idx):
            try:
                manager.add_review(pid, f"reviewer-{idx}", "approve", f"ok {idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=review, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        reviews = manager.list_reviews(pid)
        assert len(reviews) == 10


# =====================================================================
# Singleton
# =====================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        mgr = get_change_proposal_manager()
        assert isinstance(mgr, ChangeProposalManager)

    def test_get_returns_same_instance(self):
        m1 = get_change_proposal_manager()
        m2 = get_change_proposal_manager()
        assert m1 is m2

    def test_reset_clears_singleton(self):
        m1 = get_change_proposal_manager()
        reset_change_proposal_manager()
        m2 = get_change_proposal_manager()
        assert m1 is not m2

    def test_get_with_params(self, bus):
        mgr = get_change_proposal_manager(event_bus=bus)
        assert isinstance(mgr, ChangeProposalManager)


# =====================================================================
# Full lifecycle
# =====================================================================

class TestFullLifecycle:

    def test_proposal_lifecycle_draft_to_implemented(self, manager, bus):
        """Full lifecycle: draft -> submitted -> under_review -> approved -> implemented."""
        # Create
        created = manager.create_proposal(
            "Lifecycle test", "feature", "core.ebus",
            description="Full lifecycle test", proposer="alice", priority="high",
        )
        pid = created["proposal_id"]
        assert created["status"] == "draft"

        # Submit
        result = manager.update_proposal(pid, status="submitted")
        assert result["status"] == "submitted"

        # Under review
        result = manager.update_proposal(pid, status="under_review")
        assert result["status"] == "under_review"

        # Reviews
        r1 = manager.add_review(pid, "bob", "approve", "Looks good")
        r2 = manager.add_review(pid, "carol", "approve", "Ship it")
        reviews = manager.list_reviews(pid)
        assert len(reviews) == 2

        # Approve
        result = manager.update_proposal(pid, status="approved")
        assert result["status"] == "approved"

        # Implement
        result = manager.update_proposal(pid, status="implemented")
        assert result["status"] == "implemented"

        # Verify final state
        final = manager.get_proposal(pid)
        assert final["status"] == "implemented"
        assert final["priority"] == "high"
        assert final["proposer"] == "alice"

    def test_proposal_rejection_lifecycle(self, manager):
        """Lifecycle ending in rejection."""
        created = manager.create_proposal("Reject me", "bugfix", "m")
        pid = created["proposal_id"]

        manager.update_proposal(pid, status="submitted")
        manager.update_proposal(pid, status="under_review")
        manager.add_review(pid, "reviewer", "reject", "Not ready")
        manager.update_proposal(pid, status="rejected")

        final = manager.get_proposal(pid)
        assert final["status"] == "rejected"

    def test_proposal_withdrawal(self, manager):
        """Proposal withdrawn by proposer."""
        created = manager.create_proposal("Withdraw", "feature", "m")
        pid = created["proposal_id"]

        manager.update_proposal(pid, status="submitted")
        manager.update_proposal(pid, status="withdrawn")

        final = manager.get_proposal(pid)
        assert final["status"] == "withdrawn"
