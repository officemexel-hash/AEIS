"""Tests for SYLION Monitoring -- Circuit Breaker.

Tests covering registration, state transitions, call wrapping,
thread safety, EventBus integration, singleton, stats, and edge cases.
Matches the actual CircuitBreakerManager API.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.monitoring.circuit_breaker import (
    STATE_CLOSED,
    STATE_HALF_OPEN,
    STATE_OPEN,
    CircuitBreakerManager,
    get_circuit_breaker,
    reset_circuit_breaker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh EventBus per test."""
    return EventBus()


@pytest.fixture
def cb(bus):
    """Fresh CircuitBreakerManager with EventBus attached."""
    return CircuitBreakerManager(db_path=":memory:", event_bus=bus)


@pytest.fixture
def cb_no_bus():
    """Fresh CircuitBreakerManager without EventBus."""
    return CircuitBreakerManager(db_path=":memory:")


# ===========================================================================
# 1. Create / Get
# ===========================================================================

class TestCreateBreaker:
    def test_create_returns_config(self, cb):
        result = cb.create_breaker(
            "OpenAI GPT-4",
            failure_threshold=3,
            recovery_timeout=30.0,
            half_open_max=2,
        )
        assert "breaker_id" in result
        assert result["name"] == "OpenAI GPT-4"
        assert result["failure_threshold"] == 3
        assert result["recovery_timeout"] == 30.0
        assert result["half_open_max"] == 2
        assert result["state"] == STATE_CLOSED

    def test_create_default_params(self, cb):
        result = cb.create_breaker("Default")
        assert result["failure_threshold"] == 5
        assert result["recovery_timeout"] == 60.0
        assert result["half_open_max"] == 3

    def test_create_creates_closed_breaker(self, cb):
        cb.create_breaker("Test", failure_threshold=3)
        info = cb.get_breaker(
            cb.list_breakers()[0]["breaker_id"]
        )
        assert info["state"] == STATE_CLOSED
        assert info["failure_count"] == 0

    def test_create_multiple_breakers(self, cb):
        cb.create_breaker("A", failure_threshold=1)
        cb.create_breaker("B", failure_threshold=2)
        breakers = cb.list_breakers()
        assert len(breakers) == 2


# ===========================================================================
# 2. List / Filter breakers
# ===========================================================================

class TestListBreakers:
    def test_list_empty(self, cb):
        assert cb.list_breakers() == []

    def test_list_returns_all(self, cb):
        cb.create_breaker("A")
        cb.create_breaker("B")
        breakers = cb.list_breakers()
        assert len(breakers) == 2

    def test_list_filter_by_status(self, cb):
        cb.create_breaker("Closed", failure_threshold=1)
        cb.create_breaker("ToOpen", failure_threshold=1)
        # Trip the second one
        bid = cb.list_breakers()[1]["breaker_id"]
        cb.record_failure(bid)
        result = cb.list_breakers(status=STATE_OPEN)
        assert len(result) == 1


# ===========================================================================
# 3. Record success in CLOSED state
# ===========================================================================

class TestRecordSuccessClosed:
    def test_success_resets_failure_count(self, cb):
        cb.create_breaker("Reset", failure_threshold=5)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        cb.record_failure(bid)
        assert cb.get_breaker(bid)["failure_count"] == 2
        cb.record_success(bid)
        assert cb.get_breaker(bid)["failure_count"] == 0

    def test_success_increments_total_calls(self, cb):
        cb.create_breaker("Inc")
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_success(bid)
        cb.record_success(bid)
        assert cb.get_breaker(bid)["total_calls"] == 2

    def test_success_on_unregistered_raises(self, cb):
        with pytest.raises(ValueError, match="not found"):
            cb.record_success("no-such")


# ===========================================================================
# 4. Record failure in CLOSED state -> trips to OPEN
# ===========================================================================

class TestRecordFailureClosed:
    def test_failure_increments_count(self, cb):
        cb.create_breaker("Fail", failure_threshold=5)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        assert cb.get_breaker(bid)["failure_count"] == 1

    def test_failure_threshold_opens_breaker(self, cb):
        cb.create_breaker("Thresh", failure_threshold=2)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        cb.record_failure(bid)
        assert cb.get_breaker(bid)["state"] == STATE_OPEN

    def test_failure_on_unregistered_raises(self, cb):
        with pytest.raises(ValueError, match="not found"):
            cb.record_failure("no-such")


# ===========================================================================
# 5. OPEN state
# ===========================================================================

class TestOpenState:
    def test_open_records_failures(self, cb):
        cb.create_breaker("Open", failure_threshold=1)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        # Now open, additional failures still update stats
        cb.record_failure(bid)
        assert cb.get_breaker(bid)["total_failures"] == 2


# ===========================================================================
# 6. Timeout transitions to HALF_OPEN
# ===========================================================================

class TestTimeoutTransition:
    def test_timeout_transitions_to_half_open(self, cb):
        cb.create_breaker("Timeout", failure_threshold=1,
                          recovery_timeout=0.05)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        assert cb.get_breaker(bid)["state"] == STATE_OPEN
        time.sleep(0.1)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN

    def test_stays_open_before_timeout(self, cb):
        cb.create_breaker("Early", failure_threshold=1,
                          recovery_timeout=60.0)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        assert cb.get_breaker(bid)["state"] == STATE_OPEN


# ===========================================================================
# 7. HALF_OPEN success -> CLOSED
# ===========================================================================

class TestHalfOpenSuccess:
    def test_half_open_success_increment(self, cb):
        cb.create_breaker("HO", failure_threshold=1,
                          recovery_timeout=0.05, half_open_max=2)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        time.sleep(0.1)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN
        cb.record_success(bid)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN
        assert cb.get_breaker(bid)["success_count"] == 1

    def test_enough_successes_closes_breaker(self, cb):
        cb.create_breaker("Close", failure_threshold=1,
                          recovery_timeout=0.05, half_open_max=2)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        time.sleep(0.1)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN
        cb.record_success(bid)
        cb.record_success(bid)
        assert cb.get_breaker(bid)["state"] == STATE_CLOSED


# ===========================================================================
# 8. HALF_OPEN failure -> OPEN
# ===========================================================================

class TestHalfOpenFailure:
    def test_half_open_failure_reopens(self, cb):
        cb.create_breaker("ReHO", failure_threshold=1,
                          recovery_timeout=0.05, half_open_max=3)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        time.sleep(0.1)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN
        cb.record_failure(bid)
        assert cb.get_breaker(bid)["state"] == STATE_OPEN


# ===========================================================================
# 9. Force open (manual trip)
# ===========================================================================

class TestForceOpen:
    def test_force_open_transitions_to_open(self, cb):
        cb.create_breaker("Force", failure_threshold=10)
        bid = cb.list_breakers()[0]["breaker_id"]
        assert cb.get_breaker(bid)["state"] == STATE_CLOSED
        assert cb.force_open(bid) is True
        assert cb.get_breaker(bid)["state"] == STATE_OPEN

    def test_force_open_nonexistent_returns_false(self, cb):
        assert cb.force_open("no-such") is False


# ===========================================================================
# 10. Force close (manual reset)
# ===========================================================================

class TestForceClose:
    def test_force_close_transitions_to_closed(self, cb):
        cb.create_breaker("FC", failure_threshold=1)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        assert cb.get_breaker(bid)["state"] == STATE_OPEN
        assert cb.force_close(bid) is True
        assert cb.get_breaker(bid)["state"] == STATE_CLOSED

    def test_force_close_clears_failure_count(self, cb):
        cb.create_breaker("Clr", failure_threshold=10)
        bid = cb.list_breakers()[0]["breaker_id"]
        for _ in range(5):
            cb.record_failure(bid)
        cb.force_close(bid)
        assert cb.get_breaker(bid)["failure_count"] == 0

    def test_force_close_nonexistent_returns_false(self, cb):
        assert cb.force_close("no-such") is False

    def test_force_close_half_open_to_closed(self, cb):
        cb.create_breaker("HOFC", failure_threshold=1,
                          recovery_timeout=0.05)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        time.sleep(0.1)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN
        cb.force_close(bid)
        assert cb.get_breaker(bid)["state"] == STATE_CLOSED


# ===========================================================================
# 11. Get events
# ===========================================================================

class TestGetEvents:
    def test_get_events_returns_all(self, cb):
        cb.create_breaker("Ev")
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_success(bid)
        cb.record_failure(bid)
        events = cb.get_events(bid)
        assert len(events) >= 2

    def test_get_events_limit(self, cb):
        cb.create_breaker("Lim")
        bid = cb.list_breakers()[0]["breaker_id"]
        for _ in range(20):
            cb.record_success(bid)
        events = cb.get_events(bid, limit=5)
        assert len(events) == 5

    def test_events_have_required_fields(self, cb):
        cb.create_breaker("Fields")
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_success(bid)
        events = cb.get_events(bid)
        assert len(events) >= 1
        e = events[0]
        assert "event_id" in e
        assert "breaker_id" in e
        assert "event_type" in e
        assert "created_at" in e
        assert e["breaker_id"] == bid


# ===========================================================================
# 12. Get stats
# ===========================================================================

class TestGetStats:
    def test_stats_empty(self, cb):
        stats = cb.get_stats()
        assert stats["total_breakers"] == 0
        assert stats["by_state"] == {
            STATE_CLOSED: 0, STATE_OPEN: 0, STATE_HALF_OPEN: 0,
        }
        assert stats["total_calls"] == 0
        assert stats["total_failures"] == 0

    def test_stats_counts_by_state(self, cb):
        cb.create_breaker("s1", failure_threshold=1)
        cb.create_breaker("s2")
        b1 = cb.list_breakers(status=STATE_CLOSED)[0]["breaker_id"]
        cb.record_failure(b1)
        stats = cb.get_stats()
        assert stats["total_breakers"] == 2
        assert stats["by_state"][STATE_CLOSED] == 1
        assert stats["by_state"][STATE_OPEN] == 1

    def test_stats_totals(self, cb):
        cb.create_breaker("s", failure_threshold=10)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_success(bid)
        cb.record_success(bid)
        cb.record_failure(bid)
        stats = cb.get_stats()
        assert stats["total_calls"] == 3
        assert stats["total_failures"] == 1
        assert stats["total_successes"] == 2


# ===========================================================================
# 13. Multiple breakers independent
# ===========================================================================

class TestMultipleBreakers:
    def test_independent_state(self, cb):
        cb.create_breaker("A", failure_threshold=1)
        cb.create_breaker("B")
        a_id = [b["breaker_id"] for b in cb.list_breakers()
                if b["name"] == "A"][0]
        cb.record_failure(a_id)
        assert cb.get_breaker(a_id)["state"] == STATE_OPEN
        b_id = [b["breaker_id"] for b in cb.list_breakers()
                if b["name"] == "B"][0]
        assert cb.get_breaker(b_id)["state"] == STATE_CLOSED

    def test_independent_counts(self, cb):
        cb.create_breaker("X")
        cb.create_breaker("Y")
        x_id = [b["breaker_id"] for b in cb.list_breakers()
                if b["name"] == "X"][0]
        y_id = [b["breaker_id"] for b in cb.list_breakers()
                if b["name"] == "Y"][0]
        cb.record_failure(x_id)
        cb.record_failure(x_id)
        assert cb.get_breaker(x_id)["failure_count"] == 2
        assert cb.get_breaker(y_id)["failure_count"] == 0


# ===========================================================================
# 14. Concurrent operations
# ===========================================================================

class TestConcurrentOperations:
    def test_concurrent_create(self, cb):
        errors = []

        def create(i):
            try:
                cb.create_breaker(f"thread_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(cb.list_breakers()) == 20

    def test_concurrent_failures(self, cb):
        cb.create_breaker("race", failure_threshold=100)
        bid = cb.list_breakers()[0]["breaker_id"]
        errors = []

        def fail():
            try:
                cb.record_failure(bid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fail) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        info = cb.get_breaker(bid)
        assert info["failure_count"] == 30
        assert info["total_calls"] == 30


# ===========================================================================
# 15. EventBus integration
# ===========================================================================

class TestEventBusIntegration:
    def test_create_emits_event(self, cb, bus):
        events = []
        bus.subscribe("breaker_created", events.append)
        cb.create_breaker("ev-reg")
        assert len(events) == 1
        assert events[0].payload["name"] == "ev-reg"

    def test_success_emits_event(self, cb, bus):
        events = []
        bus.subscribe("breaker_opened", events.append)
        cb.create_breaker("ev-suc", failure_threshold=1)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        assert len(events) >= 1

    def test_no_events_without_bus(self, cb_no_bus):
        """Operations succeed without EventBus (no crash)."""
        cb_no_bus.create_breaker("nobus")
        bid = cb_no_bus.list_breakers()[0]["breaker_id"]
        cb_no_bus.record_success(bid)
        cb_no_bus.record_failure(bid)
        cb_no_bus.force_open(bid)
        cb_no_bus.force_close(bid)


# ===========================================================================
# 16. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_circuit_breaker_returns_instance(self):
        import sylion.monitoring.circuit_breaker as mod
        mod._instance = None
        instance = get_circuit_breaker()
        assert isinstance(instance, CircuitBreakerManager)
        assert instance is get_circuit_breaker()
        mod._instance = None

    def test_singleton_reuses_same_instance(self):
        import sylion.monitoring.circuit_breaker as mod
        mod._instance = None
        a = get_circuit_breaker()
        b = get_circuit_breaker()
        assert a is b
        mod._instance = None

    def test_reset_circuit_breaker(self):
        import sylion.monitoring.circuit_breaker as mod
        mod._instance = None
        a = get_circuit_breaker()
        reset_circuit_breaker()
        b = get_circuit_breaker()
        assert a is not b
        mod._instance = None


# ===========================================================================
# 17. Full lifecycle
# ===========================================================================

class TestFullLifecycle:
    def test_closed_to_open_to_half_open_to_closed(self, cb):
        """Full lifecycle: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
        cb.create_breaker("cycle", failure_threshold=2,
                          recovery_timeout=0.05, half_open_max=1)
        bid = cb.list_breakers()[0]["breaker_id"]
        # CLOSED -> add failures
        cb.record_failure(bid)
        cb.record_failure(bid)
        assert cb.get_breaker(bid)["state"] == STATE_OPEN

        # OPEN -> wait for timeout
        time.sleep(0.1)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN

        # HALF_OPEN -> success -> CLOSED
        cb.record_success(bid)
        assert cb.get_breaker(bid)["state"] == STATE_CLOSED
        assert cb.get_breaker(bid)["failure_count"] == 0

    def test_total_calls_accumulates_across_states(self, cb):
        cb.create_breaker("accum", failure_threshold=2,
                          recovery_timeout=0.05, half_open_max=1)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_success(bid)   # 1
        cb.record_failure(bid)   # 2
        cb.record_failure(bid)   # 3 -> OPEN
        time.sleep(0.1)
        cb.record_success(bid)   # 4 -> CLOSED
        info = cb.get_breaker(bid)
        assert info["total_calls"] == 4
        assert info["total_failures"] == 2

    def test_half_open_resets_on_reopen(self, cb):
        """After half-open -> failure -> open, success count resets."""
        cb.create_breaker("horeopen", failure_threshold=1,
                          recovery_timeout=0.05, half_open_max=2)
        bid = cb.list_breakers()[0]["breaker_id"]
        cb.record_failure(bid)
        time.sleep(0.1)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN
        cb.record_success(bid)  # 1/2
        cb.record_failure(bid)  # back to OPEN
        time.sleep(0.1)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN
        # success_count should have been reset
        cb.record_success(bid)
        assert cb.get_breaker(bid)["state"] == STATE_HALF_OPEN
        cb.record_success(bid)
        assert cb.get_breaker(bid)["state"] == STATE_CLOSED
