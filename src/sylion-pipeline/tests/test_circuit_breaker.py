"""Tests for SYLION Monitoring -- Circuit Breaker.

45 tests covering creation, state transitions (closed/open/half_open),
force_open/force_close, event history, stats, thread safety,
EventBus integration, singleton, and edge cases.
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

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_circuit_breaker()
    yield
    reset_circuit_breaker()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def cb(bus):
    return CircuitBreakerManager(db_path=":memory:", event_bus=bus)


@pytest.fixture
def cb_no_bus():
    return CircuitBreakerManager(db_path=":memory:")


# ===========================================================================
# 1. Create breaker
# ===========================================================================

class TestCreateBreaker:
    def test_create_returns_dict(self, cb):
        result = cb.create_breaker("llm-api", failure_threshold=3,
                                    recovery_timeout=30.0, half_open_max=2)
        assert result["breaker_id"]
        assert result["name"] == "llm-api"
        assert result["failure_threshold"] == 3
        assert result["recovery_timeout"] == 30.0
        assert result["half_open_max"] == 2
        assert result["state"] == STATE_CLOSED

    def test_create_default_params(self, cb):
        result = cb.create_breaker("default-svc")
        assert result["failure_threshold"] == 5
        assert result["recovery_timeout"] == 60.0
        assert result["half_open_max"] == 3

    def test_create_starts_closed(self, cb):
        cb.create_breaker("svc.test")
        info = cb.get_breaker(
            cb.list_breakers()[0]["breaker_id"]
        )
        assert info["state"] == STATE_CLOSED
        assert info["failure_count"] == 0

    def test_create_multiple_breakers(self, cb):
        cb.create_breaker("svc.a")
        cb.create_breaker("svc.b")
        cb.create_breaker("svc.c")
        assert len(cb.list_breakers()) == 3


# ===========================================================================
# 2. Get breaker
# ===========================================================================

class TestGetBreaker:
    def test_get_existing(self, cb):
        created = cb.create_breaker("svc.get")
        info = cb.get_breaker(created["breaker_id"])
        assert info is not None
        assert info["name"] == "svc.get"
        assert info["state"] == STATE_CLOSED

    def test_get_nonexistent(self, cb):
        assert cb.get_breaker("nonexistent") is None

    def test_get_returns_all_fields(self, cb):
        created = cb.create_breaker("svc.fields", failure_threshold=7,
                                     recovery_timeout=45.0, half_open_max=4)
        info = cb.get_breaker(created["breaker_id"])
        assert "breaker_id" in info
        assert "name" in info
        assert "failure_threshold" in info
        assert "recovery_timeout" in info
        assert "half_open_max" in info
        assert "state" in info
        assert "failure_count" in info
        assert "success_count" in info
        assert "total_calls" in info
        assert "total_failures" in info
        assert "total_successes" in info
        assert "created_at" in info


# ===========================================================================
# 3. List breakers
# ===========================================================================

class TestListBreakers:
    def test_list_empty(self, cb):
        assert cb.list_breakers() == []

    def test_list_returns_all(self, cb):
        cb.create_breaker("svc.a")
        cb.create_breaker("svc.b")
        breakers = cb.list_breakers()
        assert len(breakers) == 2

    def test_list_filtered_by_status(self, cb):
        b1 = cb.create_breaker("svc.closed1", failure_threshold=1)
        b2 = cb.create_breaker("svc.closed2")
        cb.record_failure(b1["breaker_id"])  # b1 -> OPEN
        closed = cb.list_breakers(status=STATE_CLOSED)
        assert len(closed) == 1
        assert closed[0]["name"] == "svc.closed2"

    def test_list_shows_current_state(self, cb):
        b1 = cb.create_breaker("svc.open", failure_threshold=1)
        b2 = cb.create_breaker("svc.closed")
        cb.record_failure(b1["breaker_id"])
        breakers = cb.list_breakers()
        states = {b["name"]: b["state"] for b in breakers}
        assert states["svc.open"] == STATE_OPEN
        assert states["svc.closed"] == STATE_CLOSED


# ===========================================================================
# 4. Record success (CLOSED state)
# ===========================================================================

class TestRecordSuccessClosed:
    def test_success_resets_failure_count(self, cb):
        b = cb.create_breaker("svc.ok", failure_threshold=5)
        cb.record_failure(b["breaker_id"])
        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["failure_count"] == 2
        cb.record_success(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["failure_count"] == 0

    def test_success_stays_closed(self, cb):
        b = cb.create_breaker("svc.ok2")
        cb.record_success(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_CLOSED

    def test_success_increments_total_successes(self, cb):
        b = cb.create_breaker("svc.stat")
        cb.record_success(b["breaker_id"])
        cb.record_success(b["breaker_id"])
        info = cb.get_breaker(b["breaker_id"])
        assert info["total_successes"] == 2
        assert info["total_calls"] == 2

    def test_success_on_unregistered_raises(self, cb):
        with pytest.raises(ValueError, match="not found"):
            cb.record_success("no.such.breaker")


# ===========================================================================
# 5. Record failure (CLOSED -> OPEN)
# ===========================================================================

class TestRecordFailureClosed:
    def test_failure_increments_count(self, cb):
        b = cb.create_breaker("svc.f1", failure_threshold=5)
        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["failure_count"] == 1

    def test_failure_updates_last_failure_timestamp(self, cb):
        b = cb.create_breaker("svc.f2")
        before = time.time()
        cb.record_failure(b["breaker_id"])
        info = cb.get_breaker(b["breaker_id"])
        assert info["last_failure_at"] >= before

    def test_breaker_trips_at_threshold(self, cb):
        b = cb.create_breaker("svc.trip", failure_threshold=3)
        cb.record_failure(b["breaker_id"])
        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_CLOSED
        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_OPEN

    def test_breaker_stays_closed_below_threshold(self, cb):
        b = cb.create_breaker("svc.below", failure_threshold=5)
        for _ in range(4):
            cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_CLOSED

    def test_failure_on_unregistered_raises(self, cb):
        with pytest.raises(ValueError, match="not found"):
            cb.record_failure("no.such.breaker")

    def test_failure_increments_total_failures(self, cb):
        b = cb.create_breaker("svc.tf", failure_threshold=10)
        cb.record_failure(b["breaker_id"])
        cb.record_failure(b["breaker_id"])
        info = cb.get_breaker(b["breaker_id"])
        assert info["total_failures"] == 2
        assert info["total_calls"] == 2


# ===========================================================================
# 6. HALF_OPEN state
# ===========================================================================

class TestHalfOpenState:
    def test_resolve_half_open_after_timeout(self, cb):
        b = cb.create_breaker("svc.ho1", failure_threshold=1,
                               recovery_timeout=0.05)
        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_OPEN
        time.sleep(0.1)
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_HALF_OPEN

    def test_stays_open_before_timeout(self, cb):
        b = cb.create_breaker("svc.ho2", failure_threshold=1,
                               recovery_timeout=60.0)
        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_OPEN

    def test_success_in_half_open_increments_counter(self, cb):
        b = cb.create_breaker("svc.ho3", failure_threshold=1,
                               recovery_timeout=0.05, half_open_max=3)
        cb.record_failure(b["breaker_id"])
        time.sleep(0.1)
        cb.record_success(b["breaker_id"])
        # Still half_open (1/3)
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_HALF_OPEN

    def test_enough_successes_closes_breaker(self, cb):
        b = cb.create_breaker("svc.ho4", failure_threshold=1,
                               recovery_timeout=0.05, half_open_max=2)
        cb.record_failure(b["breaker_id"])
        time.sleep(0.1)
        cb.record_success(b["breaker_id"])
        cb.record_success(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_CLOSED

    def test_failure_in_half_open_reopens(self, cb):
        b = cb.create_breaker("svc.ho5", failure_threshold=1,
                               recovery_timeout=0.05, half_open_max=3)
        cb.record_failure(b["breaker_id"])
        time.sleep(0.1)
        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_OPEN

    def test_half_open_resets_on_reopen(self, cb):
        """After half-open -> failure -> open, success count resets."""
        b = cb.create_breaker("svc.ho7", failure_threshold=1,
                               recovery_timeout=0.05, half_open_max=2)
        cb.record_failure(b["breaker_id"])
        time.sleep(0.1)
        cb.record_success(b["breaker_id"])  # 1/2 successes
        cb.record_failure(b["breaker_id"])  # back to OPEN
        time.sleep(0.1)
        # Need 2 more successes to close
        cb.record_success(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_HALF_OPEN
        cb.record_success(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_CLOSED


# ===========================================================================
# 7. Get state
# ===========================================================================

class TestGetState:
    def test_get_state_closed(self, cb):
        b = cb.create_breaker("svc.state")
        assert cb.get_state(b["breaker_id"]) == STATE_CLOSED

    def test_get_state_open(self, cb):
        b = cb.create_breaker("svc.state.open", failure_threshold=1)
        cb.record_failure(b["breaker_id"])
        assert cb.get_state(b["breaker_id"]) == STATE_OPEN

    def test_get_state_nonexistent(self, cb):
        assert cb.get_state("nonexistent") is None

    def test_get_state_half_open_resolved(self, cb):
        b = cb.create_breaker("svc.state.ho", failure_threshold=1,
                               recovery_timeout=0.05)
        cb.record_failure(b["breaker_id"])
        time.sleep(0.1)
        assert cb.get_state(b["breaker_id"]) == STATE_HALF_OPEN


# ===========================================================================
# 8. Force open / force close
# ===========================================================================

class TestForceOpenClose:
    def test_force_open_transitions(self, cb):
        b = cb.create_breaker("svc.fo")
        assert cb.force_open(b["breaker_id"]) is True
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_OPEN

    def test_force_open_nonexistent(self, cb):
        assert cb.force_open("nonexistent") is False

    def test_force_close_transitions(self, cb):
        b = cb.create_breaker("svc.fc", failure_threshold=1)
        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_OPEN
        assert cb.force_close(b["breaker_id"]) is True
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_CLOSED

    def test_force_close_clears_counters(self, cb):
        b = cb.create_breaker("svc.fc2", failure_threshold=10)
        for _ in range(5):
            cb.record_failure(b["breaker_id"])
        cb.force_close(b["breaker_id"])
        info = cb.get_breaker(b["breaker_id"])
        assert info["failure_count"] == 0
        assert info["success_count"] == 0

    def test_force_close_nonexistent(self, cb):
        assert cb.force_close("nonexistent") is False

    def test_force_open_then_force_close(self, cb):
        b = cb.create_breaker("svc.fofc")
        cb.force_open(b["breaker_id"])
        assert cb.get_state(b["breaker_id"]) == STATE_OPEN
        cb.force_close(b["breaker_id"])
        assert cb.get_state(b["breaker_id"]) == STATE_CLOSED


# ===========================================================================
# 9. Events
# ===========================================================================

class TestGetEvents:
    def test_events_on_failure(self, cb):
        b = cb.create_breaker("svc.ev2", failure_threshold=10)
        cb.record_failure(b["breaker_id"])
        events = cb.get_events(b["breaker_id"])
        assert len(events) >= 1

    def test_events_on_success(self, cb):
        b = cb.create_breaker("svc.ev3")
        cb.record_success(b["breaker_id"])
        events = cb.get_events(b["breaker_id"])
        assert len(events) >= 1

    def test_events_on_state_change(self, cb):
        b = cb.create_breaker("svc.evst", failure_threshold=1)
        cb.record_failure(b["breaker_id"])
        events = cb.get_events(b["breaker_id"])
        assert len(events) >= 2  # failure event + state_change event

    def test_events_limit(self, cb):
        b = cb.create_breaker("svc.evlim", failure_threshold=100)
        for _ in range(10):
            cb.record_failure(b["breaker_id"])
        events = cb.get_events(b["breaker_id"], limit=5)
        assert len(events) == 5

    def test_state_change_events_recorded(self, cb):
        b = cb.create_breaker("svc.sc2", failure_threshold=1)
        cb.record_failure(b["breaker_id"])
        events = cb.get_events(b["breaker_id"])
        state_changes = [e for e in events if e["event_type"] == "state_change"]
        assert len(state_changes) >= 1

    def test_force_open_records_event(self, cb):
        b = cb.create_breaker("svc.foev")
        cb.force_open(b["breaker_id"])
        events = cb.get_events(b["breaker_id"])
        assert len(events) >= 1

    def test_force_close_records_event(self, cb):
        b = cb.create_breaker("svc.fcev", failure_threshold=1)
        cb.record_failure(b["breaker_id"])
        cb.force_close(b["breaker_id"])
        events = cb.get_events(b["breaker_id"])
        state_changes = [e for e in events if e["event_type"] == "state_change"]
        assert len(state_changes) >= 2  # open + close


# ===========================================================================
# 10. Stats
# ===========================================================================

class TestGetStats:
    def test_stats_empty(self, cb):
        stats = cb.get_stats()
        assert stats["total_breakers"] == 0
        assert stats["by_state"]["closed"] == 0
        assert stats["by_state"]["open"] == 0
        assert stats["by_state"]["half_open"] == 0

    def test_stats_counts_by_state(self, cb):
        b1 = cb.create_breaker("s1", failure_threshold=1)
        cb.create_breaker("s2")
        cb.create_breaker("s3")
        cb.record_failure(b1["breaker_id"])  # s1 -> OPEN
        stats = cb.get_stats()
        assert stats["total_breakers"] == 3
        assert stats["by_state"]["closed"] == 2
        assert stats["by_state"]["open"] == 1

    def test_stats_totals(self, cb):
        b = cb.create_breaker("s_rate", failure_threshold=10)
        cb.record_success(b["breaker_id"])
        cb.record_success(b["breaker_id"])
        cb.record_failure(b["breaker_id"])
        stats = cb.get_stats()
        assert stats["total_calls"] == 3
        assert stats["total_failures"] == 1
        assert stats["total_successes"] == 2

    def test_stats_half_open_count(self, cb):
        b = cb.create_breaker("s_ho", failure_threshold=1,
                               recovery_timeout=0.05)
        cb.record_failure(b["breaker_id"])
        time.sleep(0.1)
        # get_state resolves to half_open, but stats also resolve
        stats = cb.get_stats()
        assert stats["by_state"]["half_open"] == 1


# ===========================================================================
# 11. Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_create(self, cb):
        errors = []

        def create(i):
            try:
                cb.create_breaker(f"thread_{i}", failure_threshold=3)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(cb.list_breakers()) == 20

    def test_concurrent_failures(self, cb):
        b = cb.create_breaker("race", failure_threshold=100)
        errors = []

        def fail():
            try:
                cb.record_failure(b["breaker_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fail) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        info = cb.get_breaker(b["breaker_id"])
        assert info["failure_count"] == 30
        assert info["total_calls"] == 30

    def test_concurrent_success_and_failure(self, cb):
        b = cb.create_breaker("mixed", failure_threshold=50)
        errors = []

        def succeed():
            try:
                cb.record_success(b["breaker_id"])
            except Exception as e:
                errors.append(e)

        def fail():
            try:
                cb.record_failure(b["breaker_id"])
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(15):
            threads.append(threading.Thread(target=succeed))
            threads.append(threading.Thread(target=fail))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        info = cb.get_breaker(b["breaker_id"])
        assert info["total_calls"] == 30


# ===========================================================================
# 12. EventBus integration
# ===========================================================================

class TestEventBusIntegration:
    def test_create_emits_event(self, cb, bus):
        events = []
        bus.subscribe("breaker_created", events.append)
        cb.create_breaker("ev.create")
        assert len(events) == 1

    def test_success_emits_no_open(self, cb, bus):
        """Success in closed state should NOT emit breaker_closed."""
        events = []
        bus.subscribe("breaker_closed", events.append)
        b = cb.create_breaker("ev.suc")
        cb.record_success(b["breaker_id"])
        assert len(events) == 0  # no state change

    def test_failure_trips_emits_open(self, cb, bus):
        events = []
        bus.subscribe("breaker_opened", events.append)
        b = cb.create_breaker("ev.trip", failure_threshold=1)
        cb.record_failure(b["breaker_id"])
        assert len(events) == 1
        assert events[0].payload["breaker_id"] == b["breaker_id"]

    def test_half_open_close_emits_closed(self, cb, bus):
        events = []
        bus.subscribe("breaker_closed", events.append)
        b = cb.create_breaker("ev.ho", failure_threshold=1,
                               recovery_timeout=0.05, half_open_max=1)
        cb.record_failure(b["breaker_id"])
        time.sleep(0.1)
        cb.record_success(b["breaker_id"])
        assert len(events) == 1

    def test_force_open_emits_event(self, cb, bus):
        events = []
        bus.subscribe("breaker_opened", events.append)
        b = cb.create_breaker("ev.fo")
        cb.force_open(b["breaker_id"])
        assert len(events) == 1

    def test_force_close_emits_event(self, cb, bus):
        events = []
        bus.subscribe("breaker_closed", events.append)
        b = cb.create_breaker("ev.fc", failure_threshold=1)
        cb.record_failure(b["breaker_id"])
        cb.force_close(b["breaker_id"])
        assert len(events) == 1

    def test_no_events_without_bus(self, cb_no_bus):
        b = cb_no_bus.create_breaker("nobus")
        cb_no_bus.record_success(b["breaker_id"])
        cb_no_bus.record_failure(b["breaker_id"])
        cb_no_bus.force_open(b["breaker_id"])
        cb_no_bus.force_close(b["breaker_id"])
        # No crash = success


# ===========================================================================
# 13. Singleton
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


# ===========================================================================
# 14. Full cycle
# ===========================================================================

class TestFullCycle:
    def test_closed_to_open_to_half_open_to_closed(self, cb):
        """Full lifecycle: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
        b = cb.create_breaker("cycle", failure_threshold=2,
                               recovery_timeout=0.05, half_open_max=1)

        # CLOSED: add failures up to threshold
        cb.record_failure(b["breaker_id"])
        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_OPEN

        # Wait for recovery timeout -> HALF_OPEN
        time.sleep(0.1)
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_HALF_OPEN

        # Successful probe -> CLOSED
        cb.record_success(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_CLOSED
        assert cb.get_breaker(b["breaker_id"])["failure_count"] == 0

    def test_open_to_half_open_to_open_flapping(self, cb):
        """Circuit flaps: OPEN -> HALF_OPEN -> OPEN."""
        b = cb.create_breaker("flap", failure_threshold=1,
                               recovery_timeout=0.05, half_open_max=2)

        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_OPEN

        time.sleep(0.1)
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_HALF_OPEN

        cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["state"] == STATE_OPEN

    def test_success_resets_failure_count_in_closed(self, cb):
        """Success resets consecutive failures in CLOSED."""
        b = cb.create_breaker("reset.f", failure_threshold=5)
        for _ in range(4):
            cb.record_failure(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["failure_count"] == 4
        cb.record_success(b["breaker_id"])
        assert cb.get_breaker(b["breaker_id"])["failure_count"] == 0

    def test_total_calls_accumulates_across_states(self, cb):
        b = cb.create_breaker("accum", failure_threshold=2,
                               recovery_timeout=0.05, half_open_max=1)
        cb.record_success(b["breaker_id"])   # 1
        cb.record_failure(b["breaker_id"])   # 2
        cb.record_failure(b["breaker_id"])   # 3 -> OPEN
        time.sleep(0.1)
        cb.record_success(b["breaker_id"])   # 4 -> CLOSED
        info = cb.get_breaker(b["breaker_id"])
        assert info["total_calls"] == 4
        assert info["total_successes"] == 2
        assert info["total_failures"] == 2
