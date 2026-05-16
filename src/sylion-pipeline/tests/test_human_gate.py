"""Tests for sylion.governance.human_gate -- HumanGate.

~40 tests covering: create_request, submit_review, get_request,
list_requests, get_reviews, escalate_request, get_stats, singleton,
concurrency, edge cases, error handling.
"""

from __future__ import annotations

import threading

import pytest

from sylion.governance.human_gate import (
    HumanGate,
    get_human_gate,
    reset_human_gate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_human_gate()
    yield
    reset_human_gate()


@pytest.fixture
def gate():
    return HumanGate(db_path=":memory:")


# ===========================================================================
# TestCreateRequest
# ===========================================================================

class TestCreateRequest:

    def test_create_returns_request_id(self, gate):
        result = gate.create_request(title="Review needed")
        assert "request_id" in result
        assert isinstance(result["request_id"], str)

    def test_create_returns_title(self, gate):
        result = gate.create_request(title="Review needed")
        assert result["title"] == "Review needed"

    def test_create_with_gate_id(self, gate):
        result = gate.create_request(gate_id="G-001", title="T")
        assert result["gate_id"] == "G-001"

    def test_create_with_description(self, gate):
        result = gate.create_request(title="T", description="Details")
        req = gate.get_request(result["request_id"])
        assert req["description"] == "Details"

    def test_create_with_context(self, gate):
        ctx = {"pipeline_run": "run-123", "module": "auth"}
        result = gate.create_request(title="T", context_json=ctx)
        req = gate.get_request(result["request_id"])
        assert req["context_json"] == ctx

    def test_create_with_requested_by(self, gate):
        result = gate.create_request(title="T", requested_by="alice")
        assert result["requested_by"] == "alice"

    def test_create_default_status_pending(self, gate):
        result = gate.create_request(title="T")
        assert result["status"] == "pending"

    def test_create_has_created_at(self, gate):
        result = gate.create_request(title="T")
        assert result["created_at"] > 0

    def test_create_unique_ids(self, gate):
        a = gate.create_request(title="A")
        b = gate.create_request(title="B")
        assert a["request_id"] != b["request_id"]


# ===========================================================================
# TestSubmitReview
# ===========================================================================

class TestSubmitReview:

    def test_submit_approved(self, gate):
        r = gate.create_request(title="T")
        review = gate.submit_review(r["request_id"], "alice", "approved",
                                    "Looks good")
        assert review["decision"] == "approved"
        assert review["reviewer"] == "alice"

    def test_submit_rejected(self, gate):
        r = gate.create_request(title="T")
        review = gate.submit_review(r["request_id"], "bob", "rejected",
                                    "Not ready")
        assert review["decision"] == "rejected"

    def test_submit_needs_info(self, gate):
        r = gate.create_request(title="T")
        review = gate.submit_review(r["request_id"], "carol",
                                    "needs_info", "Need more data")
        assert review["decision"] == "needs_info"

    def test_submit_invalid_decision(self, gate):
        r = gate.create_request(title="T")
        result = gate.submit_review(r["request_id"], "alice", "maybe")
        assert result is None

    def test_submit_nonexistent_request(self, gate):
        result = gate.submit_review("nonexistent", "alice", "approved")
        assert result is None

    def test_submit_updates_request_status_approved(self, gate):
        r = gate.create_request(title="T")
        gate.submit_review(r["request_id"], "alice", "approved")
        req = gate.get_request(r["request_id"])
        assert req["status"] == "approved"

    def test_submit_updates_request_status_rejected(self, gate):
        r = gate.create_request(title="T")
        gate.submit_review(r["request_id"], "bob", "rejected")
        req = gate.get_request(r["request_id"])
        assert req["status"] == "rejected"

    def test_submit_updates_request_status_needs_info(self, gate):
        r = gate.create_request(title="T")
        gate.submit_review(r["request_id"], "carol", "needs_info")
        req = gate.get_request(r["request_id"])
        assert req["status"] == "needs_info"

    def test_submit_has_review_id(self, gate):
        r = gate.create_request(title="T")
        review = gate.submit_review(r["request_id"], "alice", "approved")
        assert "review_id" in review
        assert isinstance(review["review_id"], str)

    def test_submit_has_reviewed_at(self, gate):
        r = gate.create_request(title="T")
        review = gate.submit_review(r["request_id"], "alice", "approved")
        assert review["reviewed_at"] > 0

    def test_submit_with_rationale(self, gate):
        r = gate.create_request(title="T")
        review = gate.submit_review(r["request_id"], "alice", "approved",
                                    "LGTM")
        assert review["rationale"] == "LGTM"


# ===========================================================================
# TestGetRequest
# ===========================================================================

class TestGetRequest:

    def test_get_existing(self, gate):
        r = gate.create_request(title="T", description="D")
        req = gate.get_request(r["request_id"])
        assert req is not None
        assert req["title"] == "T"
        assert req["description"] == "D"

    def test_get_nonexistent(self, gate):
        assert gate.get_request("nonexistent") is None

    def test_get_parses_context_json(self, gate):
        ctx = {"key": "value"}
        r = gate.create_request(title="T", context_json=ctx)
        req = gate.get_request(r["request_id"])
        assert req["context_json"] == ctx

    def test_get_escalated_is_bool(self, gate):
        r = gate.create_request(title="T")
        req = gate.get_request(r["request_id"])
        assert isinstance(req["escalated"], bool)
        assert req["escalated"] is False


# ===========================================================================
# TestListRequests
# ===========================================================================

class TestListRequests:

    def test_list_empty(self, gate):
        assert gate.list_requests() == []

    def test_list_returns_all(self, gate):
        gate.create_request(title="A")
        gate.create_request(title="B")
        assert len(gate.list_requests()) == 2

    def test_list_filter_by_status(self, gate):
        r1 = gate.create_request(title="A")
        gate.create_request(title="B")
        gate.submit_review(r1["request_id"], "alice", "approved")
        pending = gate.list_requests(status="pending")
        assert len(pending) == 1
        assert pending[0]["title"] == "B"

    def test_list_filter_by_reviewer(self, gate):
        r1 = gate.create_request(title="A")
        gate.create_request(title="B")
        gate.submit_review(r1["request_id"], "alice", "approved")
        result = gate.list_requests(reviewer="alice")
        assert len(result) == 1
        assert result[0]["request_id"] == r1["request_id"]

    def test_list_filter_status_no_match(self, gate):
        gate.create_request(title="A")
        assert gate.list_requests(status="approved") == []

    def test_list_ordered_desc(self, gate):
        gate.create_request(title="First")
        gate.create_request(title="Second")
        reqs = gate.list_requests()
        assert reqs[0]["title"] == "Second"


# ===========================================================================
# TestGetReviews
# ===========================================================================

class TestGetReviews:

    def test_empty(self, gate):
        r = gate.create_request(title="T")
        assert gate.get_reviews(r["request_id"]) == []

    def test_returns_reviews(self, gate):
        r = gate.create_request(title="T")
        gate.submit_review(r["request_id"], "alice", "approved", "OK")
        reviews = gate.get_reviews(r["request_id"])
        assert len(reviews) == 1
        assert reviews[0]["reviewer"] == "alice"
        assert reviews[0]["decision"] == "approved"

    def test_multiple_reviews(self, gate):
        r = gate.create_request(title="T")
        gate.submit_review(r["request_id"], "alice", "needs_info")
        gate.submit_review(r["request_id"], "bob", "approved")
        reviews = gate.get_reviews(r["request_id"])
        assert len(reviews) == 2

    def test_nonexistent_request(self, gate):
        assert gate.get_reviews("nonexistent") == []


# ===========================================================================
# TestEscalateRequest
# ===========================================================================

class TestEscalateRequest:

    def test_escalate_pending(self, gate):
        r = gate.create_request(title="T")
        result = gate.escalate_request(r["request_id"], "urgent")
        assert result is not None
        assert result["status"] == "escalated"
        assert result["escalated"] is True

    def test_escalate_sets_reason(self, gate):
        r = gate.create_request(title="T")
        result = gate.escalate_request(r["request_id"], "needs VP approval")
        assert result["escalation_reason"] == "needs VP approval"

    def test_escalate_nonexistent(self, gate):
        result = gate.escalate_request("nonexistent")
        assert result is None

    def test_escalate_reflected_in_list(self, gate):
        r = gate.create_request(title="T")
        gate.escalate_request(r["request_id"])
        escalated = gate.list_requests(status="escalated")
        assert len(escalated) == 1


# ===========================================================================
# TestGetStats
# ===========================================================================

class TestGetStats:

    def test_stats_empty(self, gate):
        stats = gate.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_reviews"] == 0
        assert stats["escalated"] == 0

    def test_stats_with_data(self, gate):
        r1 = gate.create_request(title="A")
        r2 = gate.create_request(title="B")
        gate.submit_review(r1["request_id"], "alice", "approved")
        gate.submit_review(r2["request_id"], "bob", "rejected")
        stats = gate.get_stats()
        assert stats["total_requests"] == 2
        assert stats["total_reviews"] == 2

    def test_stats_by_status(self, gate):
        r1 = gate.create_request(title="A")
        gate.create_request(title="B")
        gate.submit_review(r1["request_id"], "alice", "approved")
        stats = gate.get_stats()
        assert stats["by_status"]["approved"] == 1
        assert stats["by_status"]["pending"] == 1

    def test_stats_escalated(self, gate):
        r = gate.create_request(title="T")
        gate.escalate_request(r["request_id"])
        stats = gate.get_stats()
        assert stats["escalated"] == 1


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        inst = get_human_gate(db_path=":memory:")
        assert isinstance(inst, HumanGate)

    def test_get_idempotent(self):
        a = get_human_gate(db_path=":memory:")
        b = get_human_gate()
        assert a is b

    def test_reset_creates_new(self):
        a = get_human_gate(db_path=":memory:")
        reset_human_gate(db_path=":memory:")
        b = get_human_gate(db_path=":memory:")
        assert a is not b


# ===========================================================================
# TestConcurrency
# ===========================================================================

class TestConcurrency:

    def test_concurrent_create_requests(self, gate):
        errors = []

        def create(i):
            try:
                gate.create_request(title=f"Req {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert gate.get_stats()["total_requests"] == 20

    def test_concurrent_reviews(self, gate):
        errors = []
        r = gate.create_request(title="T")

        def review(reviewer):
            try:
                gate.submit_review(r["request_id"], reviewer, "approved")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=review,
                                    args=(f"reviewer-{i}",))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(gate.get_reviews(r["request_id"])) == 10
