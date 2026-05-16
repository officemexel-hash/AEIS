"""Tests for sylion.security.profile_swap -- ProfileSwapManager.

Covers: swap lifecycle (request, approve, reject, execute),
audit trail, stats, EventBus integration, concurrency, singleton, edge cases.
~35 tests.
"""

import threading

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.profile_swap import (
    VALID_STATUSES,
    ProfileSwapManager,
    get_profile_swap,
    reset_profile_swap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(event_bus: EventBus | None = None) -> ProfileSwapManager:
    return ProfileSwapManager(db_path=":memory:", event_bus=event_bus)


def _make_swap(mgr: ProfileSwapManager, target: str = "target-1",
               from_p: str = "low", to_p: str = "high") -> dict:
    return mgr.request_swap(target, from_p, to_p, "test reason")


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    def test_valid_statuses(self):
        expected = {"pending", "approved", "executed", "rejected", "cancelled"}
        assert set(VALID_STATUSES) == expected


# ===========================================================================
# 2. Request swap
# ===========================================================================


class TestRequestSwap:
    def test_basic_request(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        assert s["swap_id"] != ""
        assert s["target_id"] == "target-1"
        assert s["from_profile"] == "low"
        assert s["to_profile"] == "high"
        assert s["status"] == "pending"
        assert s["requested_at"] > 0

    def test_rejects_same_profile(self):
        mgr = _make_manager()
        with pytest.raises(ValueError, match="must be different"):
            mgr.request_swap("t1", "medium", "medium")

    def test_stores_reason(self):
        mgr = _make_manager()
        s = mgr.request_swap("t1", "a", "b", "urgent security need")
        assert s["reason"] == "urgent security need"

    def test_default_reason_empty(self):
        mgr = _make_manager()
        s = mgr.request_swap("t1", "a", "b")
        assert s["reason"] == ""

    def test_initial_timestamps(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        assert s["approved_at"] == 0.0
        assert s["executed_at"] == 0.0


# ===========================================================================
# 3. Approve swap
# ===========================================================================


class TestApproveSwap:
    def test_approve_pending(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        result = mgr.approve_swap(s["swap_id"], "admin_alice")
        assert result is not None
        assert result["status"] == "approved"
        assert result["approver"] == "admin_alice"
        assert result["approved_at"] > 0

    def test_approve_nonexistent(self):
        mgr = _make_manager()
        assert mgr.approve_swap("no-swap", "admin") is None

    def test_approve_non_pending_raises(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        mgr.approve_swap(s["swap_id"], "admin")
        with pytest.raises(ValueError, match="not pending"):
            mgr.approve_swap(s["swap_id"], "admin2")


# ===========================================================================
# 4. Reject swap
# ===========================================================================


class TestRejectSwap:
    def test_reject_pending(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        result = mgr.reject_swap(s["swap_id"], "admin_bob", "not needed")
        assert result is not None
        assert result["status"] == "rejected"
        assert result["approver"] == "admin_bob"
        assert result["reject_reason"] == "not needed"

    def test_reject_nonexistent(self):
        mgr = _make_manager()
        assert mgr.reject_swap("no-swap", "admin") is None

    def test_reject_non_pending_raises(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        mgr.approve_swap(s["swap_id"], "admin")
        with pytest.raises(ValueError, match="not pending"):
            mgr.reject_swap(s["swap_id"], "admin")

    def test_reject_default_reason_empty(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        result = mgr.reject_swap(s["swap_id"], "admin")
        assert result["reject_reason"] == ""


# ===========================================================================
# 5. Execute swap
# ===========================================================================


class TestExecuteSwap:
    def test_execute_approved(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        mgr.approve_swap(s["swap_id"], "admin")
        result = mgr.execute_swap(s["swap_id"])
        assert result is not None
        assert result["status"] == "executed"
        assert result["executed_at"] > 0

    def test_execute_nonexistent(self):
        mgr = _make_manager()
        assert mgr.execute_swap("no-swap") is None

    def test_execute_non_approved_raises(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        with pytest.raises(ValueError, match="not approved"):
            mgr.execute_swap(s["swap_id"])

    def test_full_lifecycle(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        mgr.approve_swap(s["swap_id"], "admin")
        executed = mgr.execute_swap(s["swap_id"])
        assert executed["status"] == "executed"
        assert executed["executed_at"] > 0
        assert executed["approved_at"] > 0
        assert executed["requested_at"] > 0


# ===========================================================================
# 6. Queries
# ===========================================================================


class TestGetSwap:
    def test_get_existing(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        fetched = mgr.get_swap(s["swap_id"])
        assert fetched is not None
        assert fetched["swap_id"] == s["swap_id"]

    def test_get_nonexistent(self):
        mgr = _make_manager()
        assert mgr.get_swap("no-swap") is None


class TestListSwaps:
    def test_list_all(self):
        mgr = _make_manager()
        _make_swap(mgr)
        _make_swap(mgr, target="target-2")
        assert len(mgr.list_swaps()) == 2

    def test_filter_by_status(self):
        mgr = _make_manager()
        s1 = _make_swap(mgr)
        _make_swap(mgr, target="target-2")
        mgr.approve_swap(s1["swap_id"], "admin")
        pending = mgr.list_swaps(status="pending")
        assert len(pending) == 1

    def test_invalid_status_raises(self):
        mgr = _make_manager()
        with pytest.raises(ValueError, match="Invalid status"):
            mgr.list_swaps(status="unknown")

    def test_empty_list(self):
        mgr = _make_manager()
        assert mgr.list_swaps() == []


class TestGetSwapAudit:
    def test_audit_on_request(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        audit = mgr.get_swap_audit(s["swap_id"])
        assert len(audit) >= 1
        assert audit[0]["action"] == "requested"

    def test_audit_trail_full_lifecycle(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        mgr.approve_swap(s["swap_id"], "admin")
        mgr.execute_swap(s["swap_id"])
        audit = mgr.get_swap_audit(s["swap_id"])
        actions = [a["action"] for a in audit]
        assert "requested" in actions
        assert "approved" in actions
        assert "executed" in actions

    def test_rejected_swap_audit(self):
        mgr = _make_manager()
        s = _make_swap(mgr)
        mgr.reject_swap(s["swap_id"], "admin", "bad idea")
        audit = mgr.get_swap_audit(s["swap_id"])
        actions = [a["action"] for a in audit]
        assert "rejected" in actions

    def test_nonexistent_swap_empty_audit(self):
        mgr = _make_manager()
        assert mgr.get_swap_audit("no-swap") == []


# ===========================================================================
# 7. Stats
# ===========================================================================


class TestGetSwapStats:
    def test_empty_stats(self):
        mgr = _make_manager()
        stats = mgr.get_swap_stats()
        assert stats["total_swaps"] == 0
        assert stats["by_status"] == {}

    def test_with_swaps(self):
        mgr = _make_manager()
        s1 = _make_swap(mgr)
        _make_swap(mgr, target="t2")
        mgr.approve_swap(s1["swap_id"], "admin")
        stats = mgr.get_swap_stats()
        assert stats["total_swaps"] == 2
        assert stats["by_status"]["pending"] == 1
        assert stats["by_status"]["approved"] == 1


# ===========================================================================
# 8. EventBus integration
# ===========================================================================


class TestEventBusIntegration:
    def test_swap_requested_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("swap_requested", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        _make_swap(mgr)
        assert len(collected) == 1
        assert "swap_id" in collected[0].payload

    def test_swap_approved_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("swap_approved", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        s = _make_swap(mgr)
        mgr.approve_swap(s["swap_id"], "admin")
        assert len(collected) == 1
        assert collected[0].payload["approver"] == "admin"

    def test_swap_executed_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("swap_executed", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        s = _make_swap(mgr)
        mgr.approve_swap(s["swap_id"], "admin")
        mgr.execute_swap(s["swap_id"])
        assert len(collected) == 1
        assert "target_id" in collected[0].payload

    def test_swap_rejected_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("swap_rejected", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        s = _make_swap(mgr)
        mgr.reject_swap(s["swap_id"], "admin", "nope")
        assert len(collected) == 1

    def test_no_event_without_bus(self):
        mgr = _make_manager(event_bus=None)
        _make_swap(mgr)
        # Should not raise


# ===========================================================================
# 9. Singleton
# ===========================================================================


class TestSingleton:
    def test_get_profile_swap(self):
        import sylion.security.profile_swap as mod
        mod._manager = None
        mgr = get_profile_swap(db_path=":memory:")
        assert isinstance(mgr, ProfileSwapManager)
        mod._manager = None

    def test_reset_profile_swap(self):
        import sylion.security.profile_swap as mod
        mod._manager = None
        mgr1 = get_profile_swap(db_path=":memory:")
        mgr2 = reset_profile_swap(db_path=":memory:")
        assert mgr2 is not mgr1
        mod._manager = None

    def test_get_returns_same_instance(self):
        import sylion.security.profile_swap as mod
        mod._manager = None
        mgr1 = get_profile_swap(db_path=":memory:")
        mgr2 = get_profile_swap()
        assert mgr1 is mgr2
        mod._manager = None


# ===========================================================================
# 10. Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_swap_requests(self):
        mgr = _make_manager()
        results = []
        errors = []

        def create(i):
            try:
                s = mgr.request_swap(f"target-{i}", "low", "high")
                results.append(s["swap_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_approve_and_query(self):
        mgr = _make_manager()
        swaps = [_make_swap(mgr, target=f"t{i}") for i in range(10)]
        errors = []

        def approve(swap_id):
            try:
                mgr.approve_swap(swap_id, "admin")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=approve, args=(s["swap_id"],))
                    for s in swaps]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        approved = mgr.list_swaps(status="approved")
        assert len(approved) == 10
