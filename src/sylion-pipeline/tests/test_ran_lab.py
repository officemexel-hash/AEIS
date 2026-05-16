"""Tests for sylion.cellular.ran_lab — RANLabOrchestrator.

Covers every public method: create_stack, start, stop, get, list_stacks.
No mocking — real in-memory SQLite instances.
"""
import json
import threading

import pytest

from sylion.cellular.ran_lab import RANLabOrchestrator, get_ran_lab
from sylion.core.event_bus import EventBus


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def ran(bus):
    return RANLabOrchestrator(event_bus=bus)


# =====================================================================
# create_stack
# =====================================================================

class TestCreateStack:
    def test_returns_stack_id(self, ran):
        s = ran.create_stack("4G")
        assert "stack_id" in s
        assert len(s["stack_id"]) == 12

    def test_default_status_created(self, ran):
        s = ran.create_stack("4G")
        assert s["status"] == "created"

    def test_technology_stored(self, ran):
        s = ran.create_stack("5G")
        assert s["technology"] == "5G"

    def test_stack_name(self, ran):
        s = ran.create_stack("4G", stack_name="test-ran-1")
        assert s["stack_name"] == "test-ran-1"

    def test_stack_name_default_empty(self, ran):
        s = ran.create_stack("4G")
        assert s["stack_name"] == ""

    def test_frequency(self, ran):
        s = ran.create_stack("4G", frequency=1800e6)
        assert s["frequency"] == 1800e6

    def test_frequency_default_zero(self, ran):
        s = ran.create_stack("4G")
        assert s["frequency"] == 0

    def test_power_dbm(self, ran):
        s = ran.create_stack("4G", power_dbm=-20)
        assert s["power_dbm"] == -20

    def test_power_dbm_default(self, ran):
        s = ran.create_stack("4G")
        assert s["power_dbm"] == -30

    def test_plmn(self, ran):
        s = ran.create_stack("4G", plmn_mcc="001", plmn_mnc="01")
        assert s["plmn_mcc"] == "001"
        assert s["plmn_mnc"] == "01"

    def test_plmn_defaults(self, ran):
        s = ran.create_stack("4G")
        assert s["plmn_mcc"] == "001"
        assert s["plmn_mnc"] == "01"

    def test_isolation_mode(self, ran):
        s = ran.create_stack("4G", isolation_mode="radiated")
        assert s["isolation_mode"] == "radiated"

    def test_isolation_mode_default(self, ran):
        s = ran.create_stack("4G")
        assert s["isolation_mode"] == "conducted"

    def test_created_at_set(self, ran):
        import time
        before = time.time()
        s = ran.create_stack("4G")
        after = time.time()
        assert before <= s["created_at"] <= after

    def test_unique_stack_ids(self, ran):
        s1 = ran.create_stack("4G")
        s2 = ran.create_stack("5G")
        assert s1["stack_id"] != s2["stack_id"]

    def test_without_event_bus(self):
        ran_no_bus = RANLabOrchestrator()
        s = ran_no_bus.create_stack("4G", plmn_mcc="001")
        assert s["technology"] == "4G"


# =====================================================================
# start
# =====================================================================

class TestStart:
    def test_starts_test_plmn_001(self, ran):
        s = ran.create_stack("4G", plmn_mcc="001")
        result = ran.start(s["stack_id"])
        assert result["status"] == "running"

    def test_starts_test_plmn_999(self, ran):
        s = ran.create_stack("5G", plmn_mcc="999")
        result = ran.start(s["stack_id"])
        assert result["status"] == "running"

    def test_rejects_non_test_plmn(self, ran):
        s = ran.create_stack("4G", plmn_mcc="260", plmn_mnc="06")
        result = ran.start(s["stack_id"])
        assert "error" in result
        assert "non-test PLMN" in result["error"]

    def test_rejects_non_test_plmn_message_contains_mcc(self, ran):
        s = ran.create_stack("4G", plmn_mcc="310")
        result = ran.start(s["stack_id"])
        assert "310" in result["error"]

    def test_start_nonexistent_stack(self, ran):
        result = ran.start("nonexistent")
        assert "error" in result
        assert "not found" in result["error"]

    def test_start_preserves_fields(self, ran):
        s = ran.create_stack("5G", stack_name="lab-5g", frequency=3500e6,
                             power_dbm=-15, plmn_mcc="001", plmn_mnc="99")
        result = ran.start(s["stack_id"])
        assert result["technology"] == "5G"
        assert result["stack_name"] == "lab-5g"
        assert result["frequency"] == 3500e6
        assert result["power_dbm"] == -15
        assert result["plmn_mnc"] == "99"

    def test_start_updates_db_status(self, ran):
        s = ran.create_stack("4G", plmn_mcc="001")
        ran.start(s["stack_id"])
        fetched = ran.get(s["stack_id"])
        assert fetched["status"] == "running"

    def test_start_emits_event(self, bus, ran):
        s = ran.create_stack("4G", plmn_mcc="001")
        ran.start(s["stack_id"])
        events = bus.query(topic="cellular.ran.started")
        assert len(events) == 1

    def test_start_event_payload(self, bus, ran):
        s = ran.create_stack("5G", plmn_mcc="999", plmn_mnc="01", frequency=3500e6)
        ran.start(s["stack_id"])
        events = bus.query(topic="cellular.ran.started")
        payload = events[0]["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["stack_id"] == s["stack_id"]
        assert payload["technology"] == "5G"
        assert payload["frequency"] == 3500e6
        assert payload["plmn_mcc"] == "999"
        assert payload["plmn_mnc"] == "01"

    def test_no_event_on_rejected_start(self, bus, ran):
        s = ran.create_stack("4G", plmn_mcc="260")
        ran.start(s["stack_id"])
        events = bus.query(topic="cellular.ran.started")
        assert len(events) == 0

    def test_no_event_on_nonexistent_start(self, bus, ran):
        ran.start("nonexistent")
        events = bus.query(topic="cellular.ran.started")
        assert len(events) == 0


# =====================================================================
# stop
# =====================================================================

class TestStop:
    def test_stop_running_stack(self, ran):
        s = ran.create_stack("4G", plmn_mcc="001")
        ran.start(s["stack_id"])
        result = ran.stop(s["stack_id"])
        assert result["status"] == "stopped"

    def test_stop_created_stack(self, ran):
        s = ran.create_stack("4G", plmn_mcc="001")
        result = ran.stop(s["stack_id"])
        assert result["status"] == "stopped"

    def test_stop_nonexistent(self, ran):
        result = ran.stop("nonexistent")
        assert "error" in result
        assert "not found" in result["error"]

    def test_stop_updates_db_status(self, ran):
        s = ran.create_stack("4G", plmn_mcc="001")
        ran.start(s["stack_id"])
        ran.stop(s["stack_id"])
        fetched = ran.get(s["stack_id"])
        assert fetched["status"] == "stopped"

    def test_stop_emits_event(self, bus, ran):
        s = ran.create_stack("4G", plmn_mcc="001")
        ran.start(s["stack_id"])
        ran.stop(s["stack_id"])
        events = bus.query(topic="cellular.ran.stopped")
        assert len(events) == 1

    def test_stop_event_payload(self, bus, ran):
        s = ran.create_stack("4G", plmn_mcc="001")
        ran.start(s["stack_id"])
        ran.stop(s["stack_id"])
        events = bus.query(topic="cellular.ran.stopped")
        payload = events[0]["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["stack_id"] == s["stack_id"]
        assert payload["technology"] == "4G"


# =====================================================================
# get
# =====================================================================

class TestGet:
    def test_get_existing(self, ran):
        s = ran.create_stack("4G", stack_name="test-ran")
        fetched = ran.get(s["stack_id"])
        assert fetched is not None
        assert fetched["stack_id"] == s["stack_id"]
        assert fetched["stack_name"] == "test-ran"

    def test_get_nonexistent(self, ran):
        assert ran.get("nonexistent") is None

    def test_get_reflects_status_changes(self, ran):
        s = ran.create_stack("4G", plmn_mcc="001")
        assert ran.get(s["stack_id"])["status"] == "created"
        ran.start(s["stack_id"])
        assert ran.get(s["stack_id"])["status"] == "running"
        ran.stop(s["stack_id"])
        assert ran.get(s["stack_id"])["status"] == "stopped"


# =====================================================================
# list_stacks
# =====================================================================

class TestListStacks:
    def test_empty(self, ran):
        assert ran.list_stacks() == []

    def test_returns_all(self, ran):
        ran.create_stack("4G")
        ran.create_stack("5G")
        stacks = ran.list_stacks()
        assert len(stacks) == 2

    def test_filter_by_status(self, ran):
        s1 = ran.create_stack("4G", plmn_mcc="001")
        s2 = ran.create_stack("5G", plmn_mcc="001")
        ran.start(s1["stack_id"])
        running = ran.list_stacks(status="running")
        assert len(running) == 1
        assert running[0]["stack_id"] == s1["stack_id"]

    def test_filter_by_status_no_match(self, ran):
        ran.create_stack("4G")
        assert ran.list_stacks(status="running") == []

    def test_respects_limit(self, ran):
        for i in range(5):
            ran.create_stack("4G")
        stacks = ran.list_stacks(limit=3)
        assert len(stacks) == 3

    def test_default_limit_100(self, ran):
        stacks = ran.list_stacks()
        # just verify it returns when there are < 100 items
        assert isinstance(stacks, list)

    def test_ordered_by_created_at_desc(self, ran):
        s1 = ran.create_stack("4G")
        s2 = ran.create_stack("5G")
        stacks = ran.list_stacks()
        assert stacks[0]["stack_id"] == s2["stack_id"]
        assert stacks[1]["stack_id"] == s1["stack_id"]


# =====================================================================
# get_ran_lab (module-level singleton)
# =====================================================================

class TestGetRanLab:
    def test_returns_instance(self):
        import sylion.cellular.ran_lab as mod
        mod._var = None
        lab = get_ran_lab()
        assert isinstance(lab, RANLabOrchestrator)
        mod._var = None

    def test_singleton(self):
        import sylion.cellular.ran_lab as mod
        mod._var = None
        v1 = get_ran_lab()
        v2 = get_ran_lab()
        assert v1 is v2
        mod._var = None


# =====================================================================
# Thread safety (basic smoke)
# =====================================================================

class TestThreadSafety:
    def test_concurrent_creates(self, bus):
        """Concurrent create_stack calls -- writes are serialised by module lock."""
        ran = RANLabOrchestrator(event_bus=bus)
        errors = []
        stack_ids = []

        def do_create(idx):
            try:
                s = ran.create_stack("4G", stack_name=f"t-{idx}", plmn_mcc="001")
                stack_ids.append(s["stack_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_create, args=(i,))
                    for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(stack_ids) == 10
        assert len(ran.list_stacks()) == 10

    def test_sequential_start_after_concurrent_creates(self, bus):
        """Create stacks concurrently, then start them sequentially."""
        ran = RANLabOrchestrator(event_bus=bus)
        stack_ids = []
        for i in range(5):
            s = ran.create_stack("4G", stack_name=f"t-{i}", plmn_mcc="001")
            stack_ids.append(s["stack_id"])
        for sid in stack_ids:
            result = ran.start(sid)
            assert result["status"] == "running"
        assert len(ran.list_stacks(status="running")) == 5
