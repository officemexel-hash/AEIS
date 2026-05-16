"""
tests/test_change_merger.py -- Change Merger tests

Covers:
- Merge request CRUD (create, get, list)
- Conflict detection
- Conflict resolution (manual, auto_ours, auto_theirs, custom)
- Auto merge workflow
- Statistics aggregation
- EventBus integration
- Thread safety (concurrent operations)
- Singleton get/reset
- Validation errors
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.change_merger import (
    VALID_CONFLICT_STATUSES,
    VALID_MERGE_STATUSES,
    VALID_RESOLUTION_TYPES,
    ChangeMerger,
    get_change_merger,
    reset_change_merger,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def merger(bus):
    return ChangeMerger(event_bus=bus)


@pytest.fixture(autouse=True)
def _reset_singleton():
    yield
    reset_change_merger()


# =====================================================================
# Constants
# =====================================================================

class TestConstants:

    def test_valid_merge_statuses(self):
        assert "pending" in VALID_MERGE_STATUSES
        assert "merged" in VALID_MERGE_STATUSES
        assert "failed" in VALID_MERGE_STATUSES

    def test_valid_conflict_statuses(self):
        assert "unresolved" in VALID_CONFLICT_STATUSES
        assert "resolved" in VALID_CONFLICT_STATUSES

    def test_valid_resolution_types(self):
        assert "manual" in VALID_RESOLUTION_TYPES
        assert "auto_ours" in VALID_RESOLUTION_TYPES
        assert "auto_theirs" in VALID_RESOLUTION_TYPES
        assert "custom" in VALID_RESOLUTION_TYPES


# =====================================================================
# Merge requests
# =====================================================================

class TestCreateMergeRequest:

    def test_create_basic(self, merger):
        result = merger.create_merge_request("feature/x", "main")
        assert result["merge_id"]
        assert result["source_branch"] == "feature/x"
        assert result["target_branch"] == "main"
        assert result["status"] == "pending"
        assert result["description"] == ""
        assert result["created_at"] > 0

    def test_create_with_description(self, merger):
        result = merger.create_merge_request(
            "fix/bug", "develop", description="Bug fix PR",
        )
        assert result["description"] == "Bug fix PR"

    def test_create_unique_ids(self, merger):
        r1 = merger.create_merge_request("a", "main")
        r2 = merger.create_merge_request("b", "main")
        assert r1["merge_id"] != r2["merge_id"]


class TestGetMergeRequest:

    def test_get_existing(self, merger):
        created = merger.create_merge_request("feature/a", "main")
        result = merger.get_merge_request(created["merge_id"])
        assert result is not None
        assert result["source_branch"] == "feature/a"

    def test_get_nonexistent(self, merger):
        assert merger.get_merge_request("nonexistent") is None


class TestListMergeRequests:

    def test_list_empty(self, merger):
        assert merger.list_merge_requests() == []

    def test_list_all(self, merger):
        merger.create_merge_request("a", "main")
        merger.create_merge_request("b", "main")
        result = merger.list_merge_requests()
        assert len(result) == 2

    def test_list_filter_by_status(self, merger):
        merger.create_merge_request("a", "main")
        # Change one to merged status
        mr = merger.create_merge_request("b", "main")
        merger.auto_merge(mr["merge_id"])
        pending = merger.list_merge_requests(status="pending")
        merged = merger.list_merge_requests(status="merged")
        assert len(pending) == 1
        assert len(merged) == 1

    def test_list_invalid_status(self, merger):
        with pytest.raises(ValueError, match="Invalid status"):
            merger.list_merge_requests(status="bad_status")

    def test_list_ordered_by_created_at_desc(self, merger):
        r1 = merger.create_merge_request("a", "main")
        time.sleep(0.01)
        r2 = merger.create_merge_request("b", "main")
        result = merger.list_merge_requests()
        assert result[0]["merge_id"] == r2["merge_id"]


# =====================================================================
# Conflict detection
# =====================================================================

class TestDetectConflicts:

    def test_detect_conflicts(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        conflicts = merger.detect_conflicts(mr["merge_id"])
        assert len(conflicts) >= 1
        assert conflicts[0]["merge_id"] == mr["merge_id"]
        assert conflicts[0]["status"] == "unresolved"

    def test_detect_conflicts_updates_status(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        merger.detect_conflicts(mr["merge_id"])
        updated = merger.get_merge_request(mr["merge_id"])
        assert updated["status"] == "conflicts_detected"

    def test_detect_conflicts_nonexistent(self, merger):
        with pytest.raises(ValueError, match="Merge request not found"):
            merger.detect_conflicts("nonexistent")

    def test_detect_conflicts_returns_existing(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        c1 = merger.detect_conflicts(mr["merge_id"])
        c2 = merger.detect_conflicts(mr["merge_id"])
        # Second call returns existing unresolved conflicts
        assert len(c2) == len(c1)


class TestGetConflicts:

    def test_get_conflicts(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        merger.detect_conflicts(mr["merge_id"])
        conflicts = merger.get_conflicts(mr["merge_id"])
        assert len(conflicts) >= 1

    def test_get_conflicts_by_status(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        merger.detect_conflicts(mr["merge_id"])
        unresolved = merger.get_conflicts(mr["merge_id"], status="unresolved")
        resolved = merger.get_conflicts(mr["merge_id"], status="resolved")
        assert len(unresolved) >= 1
        assert len(resolved) == 0

    def test_get_conflicts_empty(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        conflicts = merger.get_conflicts(mr["merge_id"])
        assert conflicts == []


# =====================================================================
# Conflict resolution
# =====================================================================

class TestResolveConflict:

    def test_resolve_manual(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        conflicts = merger.detect_conflicts(mr["merge_id"])
        cid = conflicts[0]["conflict_id"]
        result = merger.resolve_conflict(
            cid, resolution_type="manual",
            resolution_json='{"choice": "theirs"}',
            resolver="alice",
        )
        assert result["resolution_id"]
        assert result["conflict_id"] == cid
        assert result["resolution_type"] == "manual"
        assert result["resolver"] == "alice"

    @pytest.mark.parametrize("rtype", VALID_RESOLUTION_TYPES)
    def test_resolve_all_types(self, merger, rtype):
        mr = merger.create_merge_request(f"feat/{rtype}", "main")
        conflicts = merger.detect_conflicts(mr["merge_id"])
        cid = conflicts[0]["conflict_id"]
        result = merger.resolve_conflict(cid, resolution_type=rtype)
        assert result["resolution_type"] == rtype

    def test_resolve_invalid_type(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        conflicts = merger.detect_conflicts(mr["merge_id"])
        cid = conflicts[0]["conflict_id"]
        with pytest.raises(ValueError, match="Invalid resolution_type"):
            merger.resolve_conflict(cid, resolution_type="bad")

    def test_resolve_nonexistent_conflict(self, merger):
        with pytest.raises(ValueError, match="Conflict not found"):
            merger.resolve_conflict("nonexistent")

    def test_resolve_updates_conflict_status(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        conflicts = merger.detect_conflicts(mr["merge_id"])
        cid = conflicts[0]["conflict_id"]
        merger.resolve_conflict(cid, resolution_type="manual")
        resolved = merger.get_conflicts(mr["merge_id"], status="resolved")
        assert len(resolved) == 1


# =====================================================================
# Auto merge
# =====================================================================

class TestAutoMerge:

    def test_auto_merge(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        merger.detect_conflicts(mr["merge_id"])
        result = merger.auto_merge(mr["merge_id"])
        assert result["status"] == "merged"

    def test_auto_merge_resolves_all_conflicts(self, merger):
        mr = merger.create_merge_request("feature/x", "main")
        merger.detect_conflicts(mr["merge_id"])
        merger.auto_merge(mr["merge_id"])
        unresolved = merger.get_conflicts(mr["merge_id"], status="unresolved")
        resolved = merger.get_conflicts(mr["merge_id"], status="resolved")
        assert len(unresolved) == 0
        assert len(resolved) >= 1

    def test_auto_merge_nonexistent(self, merger):
        with pytest.raises(ValueError, match="Merge request not found"):
            merger.auto_merge("nonexistent")

    def test_auto_merge_no_conflicts(self, merger):
        mr = merger.create_merge_request("clean", "main")
        result = merger.auto_merge(mr["merge_id"])
        assert result["status"] == "merged"


# =====================================================================
# Statistics
# =====================================================================

class TestStats:

    def test_stats_empty(self, merger):
        stats = merger.get_merger_stats()
        assert stats["total_merges"] == 0
        assert stats["total_conflicts"] == 0
        assert stats["total_resolutions"] == 0

    def test_stats_after_create(self, merger):
        merger.create_merge_request("a", "main")
        merger.create_merge_request("b", "main")
        stats = merger.get_merger_stats()
        assert stats["total_merges"] == 2
        assert stats["merges_by_status"]["pending"] == 2

    def test_stats_after_conflicts(self, merger):
        mr = merger.create_merge_request("a", "main")
        merger.detect_conflicts(mr["merge_id"])
        stats = merger.get_merger_stats()
        assert stats["total_conflicts"] >= 1
        assert "unresolved" in stats["conflicts_by_status"]

    def test_stats_after_resolution(self, merger):
        mr = merger.create_merge_request("a", "main")
        conflicts = merger.detect_conflicts(mr["merge_id"])
        merger.resolve_conflict(conflicts[0]["conflict_id"])
        stats = merger.get_merger_stats()
        assert stats["total_resolutions"] >= 1


# =====================================================================
# Events
# =====================================================================

class TestEvents:

    def test_event_merge_requested(self, merger, bus):
        events = []
        bus.subscribe("merge_requested", lambda e: events.append(e))
        merger.create_merge_request("feat", "main")
        assert len(events) == 1
        assert events[0].payload["source_branch"] == "feat"
        assert events[0].source_module == "governance.change_merger"

    def test_event_conflict_detected(self, merger, bus):
        events = []
        bus.subscribe("conflict_detected", lambda e: events.append(e))
        mr = merger.create_merge_request("feat", "main")
        merger.detect_conflicts(mr["merge_id"])
        assert len(events) == 1
        assert events[0].payload["merge_id"] == mr["merge_id"]

    def test_event_conflict_resolved(self, merger, bus):
        events = []
        bus.subscribe("conflict_resolved", lambda e: events.append(e))
        mr = merger.create_merge_request("feat", "main")
        conflicts = merger.detect_conflicts(mr["merge_id"])
        merger.resolve_conflict(conflicts[0]["conflict_id"], resolver="bob")
        assert len(events) == 1
        assert events[0].payload["resolver"] == "bob"

    def test_event_merge_completed(self, merger, bus):
        events = []
        bus.subscribe("merge_completed", lambda e: events.append(e))
        mr = merger.create_merge_request("feat", "main")
        merger.detect_conflicts(mr["merge_id"])
        merger.auto_merge(mr["merge_id"])
        assert len(events) == 1
        assert events[0].payload["status"] == "merged"

    def test_no_events_without_bus(self):
        m = ChangeMerger(event_bus=None)
        mr = m.create_merge_request("a", "main")
        m.detect_conflicts(mr["merge_id"])
        m.auto_merge(mr["merge_id"])


# =====================================================================
# Thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_creates(self, merger):
        results = []
        errors = []

        def create(idx):
            try:
                r = merger.create_merge_request(f"branch-{idx}", "main")
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

    def test_concurrent_resolve(self, merger):
        mrs = []
        for i in range(5):
            mr = merger.create_merge_request(f"feat-{i}", "main")
            merger.detect_conflicts(mr["merge_id"])
            mrs.append(mr)

        errors = []

        def resolve(idx):
            try:
                conflicts = merger.get_conflicts(mrs[idx]["merge_id"])
                for c in conflicts:
                    merger.resolve_conflict(c["conflict_id"], resolver=f"r-{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=resolve, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# =====================================================================
# Singleton
# =====================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        m = get_change_merger()
        assert isinstance(m, ChangeMerger)

    def test_get_returns_same_instance(self):
        m1 = get_change_merger()
        m2 = get_change_merger()
        assert m1 is m2

    def test_reset_clears_singleton(self):
        m1 = get_change_merger()
        reset_change_merger()
        m2 = get_change_merger()
        assert m1 is not m2

    def test_get_with_params(self, bus):
        m = get_change_merger(event_bus=bus)
        assert isinstance(m, ChangeMerger)


# =====================================================================
# Full lifecycle
# =====================================================================

class TestFullLifecycle:

    def test_merge_lifecycle(self, merger, bus):
        """Full lifecycle: create -> detect -> resolve -> merge."""
        mr = merger.create_merge_request(
            "feature/awesome", "main",
            description="New awesome feature",
        )
        assert mr["status"] == "pending"

        conflicts = merger.detect_conflicts(mr["merge_id"])
        assert len(conflicts) >= 1
        updated = merger.get_merge_request(mr["merge_id"])
        assert updated["status"] == "conflicts_detected"

        for c in conflicts:
            merger.resolve_conflict(
                c["conflict_id"],
                resolution_type="manual",
                resolution_json='{"keep": "ours"}',
                resolver="dev",
            )

        resolved_conflicts = merger.get_conflicts(
            mr["merge_id"], status="resolved",
        )
        assert len(resolved_conflicts) == len(conflicts)

        stats = merger.get_merger_stats()
        assert stats["total_resolutions"] >= len(conflicts)
