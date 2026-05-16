"""
Tests for security dedup K4.2 — ProfileUnified canonical module.
"""

from __future__ import annotations

import pytest

from sylion.security.profile_unified import (
    ProfileSwapManager,
    get_profile_unified,
    reset_profile_unified,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_profile_unified()
    yield
    reset_profile_unified()


class TestLifecycle:
    def test_request_approve_execute(self):
        mgr = ProfileSwapManager(":memory:")
        swap = mgr.request_swap("mod-1", "dev", "prod", reason="deploy")
        assert swap["status"] == "pending"
        approved = mgr.approve_swap(swap["swap_id"], "alice")
        assert approved["status"] == "approved"
        executed = mgr.execute_swap(swap["swap_id"])
        assert executed["status"] == "executed"

    def test_reject_swap(self):
        mgr = ProfileSwapManager(":memory:")
        swap = mgr.request_swap("mod-1", "dev", "prod")
        rejected = mgr.reject_swap(swap["swap_id"], "bob", "no budget")
        assert rejected["status"] == "rejected"

    def test_list_and_stats(self):
        mgr = ProfileSwapManager(":memory:")
        mgr.request_swap("m1", "dev", "prod")
        mgr.request_swap("m2", "test", "staging")
        assert len(mgr.list_swaps()) == 2
        assert len(mgr.list_swaps(status="pending")) == 2
        stats = mgr.get_swap_stats()
        assert stats["total_swaps"] == 2


class testAuditTrail:
    def test_audit_records(self):
        mgr = ProfileSwapManager(":memory:")
        swap = mgr.request_swap("m1", "dev", "prod")
        audit = mgr.get_swap_audit(swap["swap_id"])
        assert len(audit) == 1
        assert audit[0]["action"] == "requested"
