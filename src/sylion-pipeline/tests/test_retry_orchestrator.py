"""
Tests for SYLION Execution -- Retry Orchestrator

Covers: policy CRUD, attempt registration, exponential backoff with jitter,
dead letter queue flow, statistics, concurrent access, singleton lifecycle.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.execution.retry_orchestrator import (
    DeadLetterEntry,
    RetryAttempt,
    RetryOrchestrator,
    RetryPolicy,
    get_retry_orchestrator,
    reset_retry_orchestrator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orch():
    """Fresh in-memory RetryOrchestrator per test."""
    return RetryOrchestrator()


@pytest.fixture
def orch_with_bus():
    """RetryOrchestrator with a mock EventBus."""
    bus = MagicMock(spec=EventBus)
    return RetryOrchestrator(event_bus=bus), bus


@pytest.fixture
def orch_with_policy(orch):
    """Orchestrator with a default policy pre-created."""
    policy = orch.create_policy("default", max_retries=3, base_delay_ms=100,
                                max_delay_ms=5000, backoff_factor=2.0,
                                jitter=0.1)
    return orch, policy


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:

    def test_retry_policy_defaults(self):
        p = RetryPolicy()
        assert p.max_retries == 3
        assert p.base_delay_ms == 1000
        assert p.max_delay_ms == 60000
        assert p.backoff_factor == 2.0
        assert p.jitter == 0.1
        assert p.retryable_errors == []
        assert p.enabled == 1

    def test_retry_attempt_defaults(self):
        a = RetryAttempt()
        assert a.operation_type == ""
        assert a.attempt_number == 0
        assert a.result == ""

    def test_dead_letter_entry_defaults(self):
        d = DeadLetterEntry()
        assert d.dlq_id == ""
        assert d.total_attempts == 0
        assert d.requires_manual_review == 0


# ===========================================================================
# Policy CRUD
# ===========================================================================

class TestPolicyCRUD:

    def test_create_policy_returns_dict(self, orch):
        p = orch.create_policy("fast")
        assert p["policy_id"]
        assert p["name"] == "fast"
        assert p["enabled"] == 1

    def test_create_policy_default_values(self, orch):
        p = orch.create_policy("defaults")
        assert p["max_retries"] == 3
        assert p["base_delay_ms"] == 1000
        assert p["max_delay_ms"] == 60000
        assert p["backoff_factor"] == 2.0
        assert p["jitter"] == 0.1
        assert p["retryable_errors"] == []
        assert p["description"] == ""

    def test_create_policy_custom_values(self, orch):
        p = orch.create_policy(
            "custom", max_retries=5, base_delay_ms=200,
            max_delay_ms=30000, backoff_factor=3.0, jitter=0.5,
            retryable_errors=["TimeoutError", "ConnectionError"],
            description="custom policy",
        )
        assert p["max_retries"] == 5
        assert p["base_delay_ms"] == 200
        assert p["max_delay_ms"] == 30000
        assert p["backoff_factor"] == 3.0
        assert p["jitter"] == 0.5
        assert p["retryable_errors"] == ["TimeoutError", "ConnectionError"]
        assert p["description"] == "custom policy"

    def test_create_policy_has_created_at(self, orch):
        p = orch.create_policy("timed")
        assert p["created_at"] > 0

    def test_create_policy_emits_event(self, orch_with_bus):
        orch, bus = orch_with_bus
        orch.create_policy("eventful")
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert isinstance(event, SylionEvent)
        assert event.topic == "execution.retry.policy_created"

    def test_get_policy(self, orch):
        created = orch.create_policy("getme")
        fetched = orch.get_policy(created["policy_id"])
        assert fetched is not None
        assert fetched["name"] == "getme"

    def test_get_policy_nonexistent(self, orch):
        assert orch.get_policy("nope") is None

    def test_update_policy(self, orch):
        p = orch.create_policy("updatable")
        result = orch.update_policy(p["policy_id"], max_retries=10, name="updated")
        assert result is not None
        assert result["max_retries"] == 10
        assert result["name"] == "updated"

    def test_update_policy_unknown_field_raises(self, orch):
        p = orch.create_policy("badfield")
        with pytest.raises(ValueError, match="unknown field"):
            orch.update_policy(p["policy_id"], nonexistent_field="x")

    def test_update_policy_nonexistent(self, orch):
        result = orch.update_policy("ghost", max_retries=1)
        assert result is None

    def test_update_policy_retryable_errors(self, orch):
        p = orch.create_policy("errors")
        result = orch.update_policy(p["policy_id"],
                                     retryable_errors=["ValueError"])
        assert result["retryable_errors"] == ["ValueError"]

    def test_update_policy_emits_event(self, orch_with_bus):
        orch, bus = orch_with_bus
        p = orch.create_policy("ev")
        bus.publish.reset_mock()
        orch.update_policy(p["policy_id"], max_retries=7)
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert event.topic == "execution.retry.policy_updated"

    def test_list_policies_includes_all(self, orch):
        orch.create_policy("a")
        orch.create_policy("b")
        all_policies = orch.list_policies(enabled_only=False)
        assert len(all_policies) >= 2

    def test_list_policies_enabled_only(self, orch):
        orch.create_policy("enabled")
        p = orch.create_policy("disabled")
        orch.update_policy(p["policy_id"], enabled=0)
        enabled = orch.list_policies(enabled_only=True)
        names = [x["name"] for x in enabled]
        assert "enabled" in names
        assert "disabled" not in names

    def test_disable_policy(self, orch):
        p = orch.create_policy("toggle")
        orch.update_policy(p["policy_id"], enabled=0)
        fetched = orch.get_policy(p["policy_id"])
        assert fetched["enabled"] == 0


# ===========================================================================
# Attempt registration
# ===========================================================================

class TestAttemptRegistration:

    def test_register_first_attempt(self, orch_with_policy):
        orch, policy = orch_with_policy
        result = orch.register_attempt("llm_call", "op-001",
                                       policy_id=policy["policy_id"],
                                       error_type="TimeoutError",
                                       error_message="timed out")
        assert result["attempt_id"]
        assert result["attempt_number"] == 1
        assert result["should_retry"] is True
        assert result["moved_to_dlq"] is False
        assert result["next_delay_ms"] > 0

    def test_register_attempt_increments(self, orch_with_policy):
        orch, policy = orch_with_policy
        r1 = orch.register_attempt("llm_call", "op-002",
                                   policy_id=policy["policy_id"])
        r2 = orch.register_attempt("llm_call", "op-002",
                                   policy_id=policy["policy_id"])
        assert r1["attempt_number"] == 1
        assert r2["attempt_number"] == 2

    def test_register_attempt_exceeds_max_moves_to_dlq(self, orch_with_policy):
        orch, policy = orch_with_policy
        pid = policy["policy_id"]
        orch.register_attempt("llm_call", "op-003", policy_id=pid)
        orch.register_attempt("llm_call", "op-003", policy_id=pid)
        r3 = orch.register_attempt("llm_call", "op-003", policy_id=pid)
        assert r3["attempt_number"] == 3
        assert r3["should_retry"] is False
        assert r3["moved_to_dlq"] is True

    def test_dlq_entry_created_after_exhaustion(self, orch_with_policy):
        orch, policy = orch_with_policy
        pid = policy["policy_id"]
        for _ in range(3):
            orch.register_attempt("llm_call", "op-004", policy_id=pid)
        dlq = orch.get_dlq_entries()
        assert len(dlq) >= 1
        entry = [e for e in dlq if e["operation_id"] == "op-004"][0]
        assert entry["total_attempts"] == 3

    def test_register_attempt_without_policy_uses_default(self, orch):
        orch.create_policy("auto")
        result = orch.register_attempt("pipeline_step", "op-auto")
        assert result["attempt_id"]
        assert result["attempt_number"] == 1

    def test_register_attempt_no_policy_at_all(self, orch):
        result = orch.register_attempt("http_request", "op-nopolicy")
        assert result["attempt_id"]
        assert result["attempt_number"] == 1

    def test_non_retryable_error_goes_to_dlq(self, orch):
        p = orch.create_policy("filtered",
                               retryable_errors=["TimeoutError"])
        result = orch.register_attempt("llm_call", "op-bad",
                                       policy_id=p["policy_id"],
                                       error_type="SyntaxError",
                                       error_message="bad syntax")
        assert result["moved_to_dlq"] is True
        assert result["should_retry"] is False

    def test_retryable_error_allows_retry(self, orch):
        p = orch.create_policy("filtered",
                               max_retries=3,
                               retryable_errors=["TimeoutError"])
        result = orch.register_attempt("llm_call", "op-ok",
                                       policy_id=p["policy_id"],
                                       error_type="TimeoutError",
                                       error_message="slow")
        assert result["should_retry"] is True
        assert result["moved_to_dlq"] is False

    def test_register_attempt_with_payload_preserved_in_dlq(self, orch_with_policy):
        orch, policy = orch_with_policy
        pid = policy["policy_id"]
        for _ in range(3):
            orch.register_attempt("custom", "op-payload", policy_id=pid,
                                  payload={"key": "value"})
        dlq = orch.get_dlq_entries()
        entry = [e for e in dlq if e["operation_id"] == "op-payload"][0]
        assert entry["payload"]["key"] == "value"

    def test_register_attempt_emits_event(self, orch_with_bus):
        orch, bus = orch_with_bus
        orch.create_policy("ev-test")
        bus.publish.reset_mock()
        orch.register_attempt("llm_call", "ev-op")
        bus.publish.assert_called()
        topics = [c[0][0].topic for c in bus.publish.call_args_list]
        assert "execution.retry.attempt_registered" in topics

    def test_register_attempt_stores_error_info(self, orch_with_policy):
        orch, policy = orch_with_policy
        orch.register_attempt("llm_call", "err-op",
                              policy_id=policy["policy_id"],
                              error_type="ConnectionError",
                              error_message="refused")
        attempts = orch.get_attempts(operation_id="err-op")
        assert attempts[0]["error_type"] == "ConnectionError"
        assert attempts[0]["error_message"] == "refused"


# ===========================================================================
# Delay calculation
# ===========================================================================

class TestDelayCalculation:

    def test_first_attempt_delay_is_base(self, orch):
        p = orch.create_policy("delay-test", base_delay_ms=100,
                               backoff_factor=2.0, jitter=0.0,
                               max_delay_ms=60000)
        delay = orch.get_next_delay(p["policy_id"], 1)
        assert delay == 100

    def test_second_attempt_doubles(self, orch):
        p = orch.create_policy("delay-test", base_delay_ms=100,
                               backoff_factor=2.0, jitter=0.0,
                               max_delay_ms=60000)
        delay = orch.get_next_delay(p["policy_id"], 2)
        assert delay == 200

    def test_third_attempt_quadruples(self, orch):
        p = orch.create_policy("delay-test", base_delay_ms=100,
                               backoff_factor=2.0, jitter=0.0,
                               max_delay_ms=60000)
        delay = orch.get_next_delay(p["policy_id"], 3)
        assert delay == 400

    def test_max_delay_is_capped(self, orch):
        p = orch.create_policy("capped", base_delay_ms=100,
                               backoff_factor=10.0, jitter=0.0,
                               max_delay_ms=500)
        delay = orch.get_next_delay(p["policy_id"], 5)
        assert delay <= 500

    def test_jitter_adds_variance(self, orch):
        p = orch.create_policy("jittery", base_delay_ms=1000,
                               backoff_factor=1.0, jitter=0.5,
                               max_delay_ms=10000)
        delays = set()
        for _ in range(100):
            delays.add(orch.get_next_delay(p["policy_id"], 1))
        assert len(delays) > 1

    def test_jitter_range_within_bounds(self, orch):
        """With jitter=0.3 and base=1000, factor=1.0: delay in [1000, 1300]."""
        p = orch.create_policy("bounds", base_delay_ms=1000,
                               backoff_factor=1.0, jitter=0.3,
                               max_delay_ms=10000)
        for _ in range(200):
            d = orch.get_next_delay(p["policy_id"], 1)
            assert 1000 <= d <= 1300

    def test_get_next_delay_nonexistent_policy(self, orch):
        assert orch.get_next_delay("ghost", 1) == 0

    def test_custom_backoff_factor(self, orch):
        p = orch.create_policy("factor3", base_delay_ms=100,
                               backoff_factor=3.0, jitter=0.0,
                               max_delay_ms=60000)
        assert orch.get_next_delay(p["policy_id"], 1) == 100
        assert orch.get_next_delay(p["policy_id"], 2) == 300
        assert orch.get_next_delay(p["policy_id"], 3) == 900


# ===========================================================================
# Record success
# ===========================================================================

class TestRecordSuccess:

    def test_record_success(self, orch_with_policy):
        orch, policy = orch_with_policy
        orch.register_attempt("llm_call", "op-s", policy_id=policy["policy_id"])
        ok = orch.record_success("llm_call", "op-s")
        assert ok is True

    def test_record_success_creates_success_attempt(self, orch_with_policy):
        orch, policy = orch_with_policy
        orch.register_attempt("llm_call", "op-s2", policy_id=policy["policy_id"])
        orch.record_success("llm_call", "op-s2")
        attempts = orch.get_attempts(operation_type="llm_call",
                                     operation_id="op-s2")
        results = [a["result"] for a in attempts]
        assert "success" in results

    def test_record_success_no_prior_attempts(self, orch):
        ok = orch.record_success("module_call", "fresh-op")
        assert ok is True

    def test_record_success_emits_event(self, orch_with_bus):
        orch, bus = orch_with_bus
        orch.record_success("llm_call", "ev-s")
        bus.publish.assert_called()
        topics = [c[0][0].topic for c in bus.publish.call_args_list]
        assert "execution.retry.success_recorded" in topics


# ===========================================================================
# Get attempts
# ===========================================================================

class TestGetAttempts:

    def test_get_attempts_by_operation_type(self, orch_with_policy):
        orch, policy = orch_with_policy
        orch.register_attempt("llm_call", "a1", policy_id=policy["policy_id"])
        orch.register_attempt("pipeline_step", "b1", policy_id=policy["policy_id"])
        llm = orch.get_attempts(operation_type="llm_call")
        assert len(llm) >= 1
        assert all(a["operation_type"] == "llm_call" for a in llm)

    def test_get_attempts_by_operation_id(self, orch_with_policy):
        orch, policy = orch_with_policy
        orch.register_attempt("llm_call", "specific", policy_id=policy["policy_id"])
        orch.register_attempt("llm_call", "other", policy_id=policy["policy_id"])
        specific = orch.get_attempts(operation_id="specific")
        assert len(specific) == 1
        assert specific[0]["operation_id"] == "specific"

    def test_get_attempts_by_result(self, orch_with_policy):
        orch, policy = orch_with_policy
        orch.register_attempt("llm_call", "r1", policy_id=policy["policy_id"])
        orch.record_success("llm_call", "r1")
        successes = orch.get_attempts(result="success")
        assert len(successes) >= 1
        assert all(a["result"] == "success" for a in successes)

    def test_get_attempts_by_policy_id(self, orch):
        p1 = orch.create_policy("p1")
        p2 = orch.create_policy("p2")
        orch.register_attempt("llm_call", "x1", policy_id=p1["policy_id"])
        orch.register_attempt("llm_call", "x2", policy_id=p2["policy_id"])
        result = orch.get_attempts(policy_id=p1["policy_id"])
        assert len(result) == 1
        assert result[0]["policy_id"] == p1["policy_id"]

    def test_get_attempts_limit(self, orch_with_policy):
        orch, policy = orch_with_policy
        for i in range(10):
            orch.register_attempt("llm_call", f"lim-{i}",
                                  policy_id=policy["policy_id"])
        limited = orch.get_attempts(limit=5)
        assert len(limited) == 5

    def test_get_attempts_no_filter(self, orch_with_policy):
        orch, policy = orch_with_policy
        orch.register_attempt("llm_call", "nf1", policy_id=policy["policy_id"])
        orch.register_attempt("pipeline_step", "nf2", policy_id=policy["policy_id"])
        all_attempts = orch.get_attempts()
        assert len(all_attempts) >= 2


# ===========================================================================
# Dead Letter Queue
# ===========================================================================

class TestDeadLetterQueue:

    def _exhaust_retries(self, orch, policy, op_id):
        pid = policy["policy_id"]
        for _ in range(policy["max_retries"]):
            orch.register_attempt("llm_call", op_id, policy_id=pid)

    def test_dlq_entry_created(self, orch_with_policy):
        orch, policy = orch_with_policy
        self._exhaust_retries(orch, policy, "dlq-1")
        entries = orch.get_dlq_entries()
        dlq_ids = [e["operation_id"] for e in entries]
        assert "dlq-1" in dlq_ids

    def test_dlq_entry_fields(self, orch_with_policy):
        orch, policy = orch_with_policy
        pid = policy["policy_id"]
        orch.register_attempt("llm_call", "dlq-fields", policy_id=pid,
                              error_type="TimeoutError",
                              error_message="connection lost")
        orch.register_attempt("llm_call", "dlq-fields", policy_id=pid,
                              error_type="TimeoutError",
                              error_message="still lost")
        orch.register_attempt("llm_call", "dlq-fields", policy_id=pid,
                              error_type="TimeoutError",
                              error_message="final failure")
        entries = orch.get_dlq_entries()
        entry = [e for e in entries if e["operation_id"] == "dlq-fields"][0]
        assert entry["total_attempts"] == 3
        assert entry["operation_type"] == "llm_call"
        assert entry["requires_manual_review"] == 1
        assert entry["created_at"] > 0

    def test_get_dlq_unreviewed(self, orch_with_policy):
        orch, policy = orch_with_policy
        self._exhaust_retries(orch, policy, "dlq-unrev")
        unreviewed = orch.get_dlq_entries(reviewed=False)
        assert len(unreviewed) >= 1
        assert all(e.get("reviewed_by", "") == "" for e in unreviewed)

    def test_get_dlq_reviewed(self, orch_with_policy):
        orch, policy = orch_with_policy
        self._exhaust_retries(orch, policy, "dlq-rev")
        entries = orch.get_dlq_entries(operation_type="llm_call")
        dlq = [e for e in entries if e["operation_id"] == "dlq-rev"][0]
        orch.review_dlq_entry(dlq["dlq_id"], "admin", action="discard")
        reviewed = orch.get_dlq_entries(reviewed=True)
        assert len(reviewed) >= 1

    def test_review_dlq_entry(self, orch_with_policy):
        orch, policy = orch_with_policy
        self._exhaust_retries(orch, policy, "dlq-review")
        entries = orch.get_dlq_entries()
        dlq = [e for e in entries if e["operation_id"] == "dlq-review"][0]
        result = orch.review_dlq_entry(dlq["dlq_id"], "reviewer", action="discard")
        assert result["reviewed_by"] == "reviewer"
        assert result["action"] == "discard"

    def test_review_dlq_entry_nonexistent(self, orch):
        result = orch.review_dlq_entry("ghost", "admin")
        assert result is None

    def test_retry_dlq_entry(self, orch_with_policy):
        orch, policy = orch_with_policy
        self._exhaust_retries(orch, policy, "dlq-retry")
        entries = orch.get_dlq_entries()
        dlq = [e for e in entries if e["operation_id"] == "dlq-retry"][0]
        result = orch.retry_dlq_entry(dlq["dlq_id"])
        assert result is not None
        assert result["operation_id"] == "dlq-retry"

    def test_retry_dlq_entry_removes_from_dlq(self, orch_with_policy):
        orch, policy = orch_with_policy
        self._exhaust_retries(orch, policy, "dlq-remove")
        entries = orch.get_dlq_entries()
        dlq = [e for e in entries if e["operation_id"] == "dlq-remove"][0]
        orch.retry_dlq_entry(dlq["dlq_id"])
        remaining = orch.get_dlq_entries()
        ids = [e["operation_id"] for e in remaining]
        assert "dlq-remove" not in ids

    def test_retry_dlq_entry_clears_old_attempts(self, orch_with_policy):
        orch, policy = orch_with_policy
        self._exhaust_retries(orch, policy, "dlq-clear")
        entries = orch.get_dlq_entries()
        dlq = [e for e in entries if e["operation_id"] == "dlq-clear"][0]
        orch.retry_dlq_entry(dlq["dlq_id"])
        # Register again -- should start from attempt 1
        r = orch.register_attempt("llm_call", "dlq-clear",
                                  policy_id=policy["policy_id"])
        assert r["attempt_number"] == 1

    def test_retry_dlq_entry_nonexistent(self, orch):
        assert orch.retry_dlq_entry("ghost") is None

    def test_get_dlq_by_operation_type(self, orch):
        p = orch.create_policy("dlq-type-test")
        for i in range(3):
            orch.register_attempt("http_request", f"http-{i}",
                                  policy_id=p["policy_id"])
        for i in range(3):
            orch.register_attempt("pipeline_step", f"pipe-{i}",
                                  policy_id=p["policy_id"])
        http_dlq = orch.get_dlq_entries(operation_type="http_request")
        assert all(e["operation_type"] == "http_request" for e in http_dlq)

    def test_dlq_update_on_repeat(self, orch_with_policy):
        """Second DLQ move for same op updates the existing entry."""
        orch, policy = orch_with_policy
        pid = policy["policy_id"]
        for _ in range(3):
            orch.register_attempt("llm_call", "dlq-dup", policy_id=pid)
        # Clear attempts, exhaust again
        with orch._lock:
            orch._conn.execute(
                "DELETE FROM retry_attempts WHERE operation_id = 'dlq-dup'"
            )
            orch._conn.commit()
        for _ in range(3):
            orch.register_attempt("llm_call", "dlq-dup", policy_id=pid)
        dlq = orch.get_dlq_entries()
        matches = [e for e in dlq if e["operation_id"] == "dlq-dup"]
        assert len(matches) == 1
        assert matches[0]["total_attempts"] == 3

    def test_retry_dlq_entry_emits_event(self, orch_with_bus):
        orch, bus = orch_with_bus
        p = orch.create_policy("dlq-ev", max_retries=1)
        orch.register_attempt("llm_call", "dlq-ev-op", policy_id=p["policy_id"])
        bus.publish.reset_mock()
        entries = orch.get_dlq_entries()
        dlq = [e for e in entries if e["operation_id"] == "dlq-ev-op"][0]
        orch.retry_dlq_entry(dlq["dlq_id"])
        topics = [c[0][0].topic for c in bus.publish.call_args_list]
        assert "execution.retry.dlq_retried" in topics


# ===========================================================================
# Statistics
# ===========================================================================

class TestStats:

    def test_stats_empty(self, orch):
        stats = orch.get_stats()
        assert stats["total_policies"] == 0
        assert stats["total_attempts"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["dlq_count"] == 0
        assert stats["by_operation_type"] == {}

    def test_stats_with_data(self, orch_with_policy):
        orch, policy = orch_with_policy
        pid = policy["policy_id"]
        orch.register_attempt("llm_call", "s1", policy_id=pid)
        orch.register_attempt("llm_call", "s2", policy_id=pid)
        orch.record_success("llm_call", "s2")
        stats = orch.get_stats()
        assert stats["total_policies"] >= 1
        assert stats["total_attempts"] >= 2
        assert stats["success_rate"] > 0
        assert "llm_call" in stats["by_operation_type"]

    def test_stats_dlq_count(self, orch_with_policy):
        orch, policy = orch_with_policy
        for _ in range(3):
            orch.register_attempt("llm_call", "st-1",
                                  policy_id=policy["policy_id"])
        stats = orch.get_stats()
        assert stats["dlq_count"] >= 1

    def test_stats_by_operation_type(self, orch):
        p = orch.create_policy("multi")
        orch.register_attempt("llm_call", "m1", policy_id=p["policy_id"])
        orch.register_attempt("pipeline_step", "m2", policy_id=p["policy_id"])
        orch.register_attempt("http_request", "m3", policy_id=p["policy_id"])
        stats = orch.get_stats()
        bot = stats["by_operation_type"]
        assert "llm_call" in bot
        assert "pipeline_step" in bot
        assert "http_request" in bot

    def test_stats_success_rate_calculation(self, orch):
        p = orch.create_policy("rate")
        orch.register_attempt("llm_call", "r1", policy_id=p["policy_id"])
        orch.record_success("llm_call", "r1")
        orch.register_attempt("llm_call", "r2", policy_id=p["policy_id"])
        # r1 has 2 attempts (fail + success), r2 has 1 attempt (fail)
        # Total attempts: 3, successes: 1 (from the success attempt)
        stats = orch.get_stats()
        assert stats["success_rate"] > 0.0


# ===========================================================================
# Concurrent access
# ===========================================================================

class TestConcurrency:

    def test_concurrent_register_attempts(self, orch_with_policy):
        orch, policy = orch_with_policy
        pid = policy["policy_id"]
        errors = []
        n_threads = 10

        def worker(idx):
            try:
                for j in range(3):
                    orch.register_attempt("llm_call", f"concurrent-{idx}",
                                          policy_id=pid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        attempts = orch.get_attempts(operation_type="llm_call")
        assert len(attempts) == n_threads * 3

    def test_concurrent_policy_creation(self, orch):
        errors = []
        n_threads = 10

        def worker(idx):
            try:
                orch.create_policy(f"policy-{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        policies = orch.list_policies(enabled_only=False)
        assert len(policies) == n_threads

    def test_concurrent_dlq_operations(self, orch):
        p = orch.create_policy("conc-dlq", max_retries=1)
        pid = p["policy_id"]
        errors = []

        def worker(idx):
            try:
                orch.register_attempt("llm_call", f"dlq-conc-{idx}",
                                      policy_id=pid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        dlq = orch.get_dlq_entries()
        assert len(dlq) == 5

    def test_concurrent_reads_and_writes(self, orch_with_policy):
        orch, policy = orch_with_policy
        pid = policy["policy_id"]
        errors = []

        def writer():
            try:
                for i in range(20):
                    orch.register_attempt("llm_call", f"rw-{i}",
                                          policy_id=pid)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    orch.get_stats()
                    orch.list_policies()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer),
                   threading.Thread(target=reader),
                   threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:

    def test_get_retry_orchestrator_returns_instance(self):
        reset_retry_orchestrator()
        inst = get_retry_orchestrator()
        assert isinstance(inst, RetryOrchestrator)

    def test_get_retry_orchestrator_same_instance(self):
        reset_retry_orchestrator()
        a = get_retry_orchestrator()
        b = get_retry_orchestrator()
        assert a is b

    def test_reset_retry_orchestrator(self):
        reset_retry_orchestrator()
        a = get_retry_orchestrator()
        reset_retry_orchestrator()
        b = get_retry_orchestrator()
        assert a is not b
        reset_retry_orchestrator()

    def test_singleton_with_custom_db(self):
        reset_retry_orchestrator()
        inst = get_retry_orchestrator()
        assert inst._db_path == ":memory:"
        reset_retry_orchestrator()


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_zero_jitter(self, orch):
        p = orch.create_policy("no-jitter", base_delay_ms=500,
                               backoff_factor=2.0, jitter=0.0,
                               max_delay_ms=10000)
        d1 = orch.get_next_delay(p["policy_id"], 1)
        d2 = orch.get_next_delay(p["policy_id"], 2)
        assert d1 == 500
        assert d2 == 1000

    def test_high_jitter(self, orch):
        p = orch.create_policy("high-jitter", base_delay_ms=1000,
                               backoff_factor=1.0, jitter=1.0,
                               max_delay_ms=10000)
        delays = set()
        for _ in range(100):
            delays.add(orch.get_next_delay(p["policy_id"], 1))
        assert len(delays) > 1
        for d in delays:
            assert 1000 <= d <= 2000

    def test_max_retries_one(self, orch):
        p = orch.create_policy("single-shot", max_retries=1)
        r = orch.register_attempt("custom", "one-shot",
                                  policy_id=p["policy_id"])
        assert r["attempt_number"] == 1
        assert r["should_retry"] is False
        assert r["moved_to_dlq"] is True

    def test_large_backoff_factor(self, orch):
        p = orch.create_policy("big-factor", base_delay_ms=10,
                               backoff_factor=10.0, jitter=0.0,
                               max_delay_ms=10000)
        assert orch.get_next_delay(p["policy_id"], 1) == 10
        assert orch.get_next_delay(p["policy_id"], 2) == 100
        assert orch.get_next_delay(p["policy_id"], 3) == 1000
        assert orch.get_next_delay(p["policy_id"], 4) == 10000
        assert orch.get_next_delay(p["policy_id"], 5) == 10000  # capped

    def test_all_operation_types(self, orch):
        p = orch.create_policy("all-types")
        types = ["llm_call", "pipeline_step", "module_call",
                 "http_request", "custom"]
        for t in types:
            r = orch.register_attempt(t, f"op-{t}",
                                      policy_id=p["policy_id"])
            assert r["attempt_id"]
        stats = orch.get_stats()
        assert len(stats["by_operation_type"]) == 5
