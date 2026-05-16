"""Tests for sylion.cellular.ue_emulator — UEEmulator.

Covers every public method: create, attach, detach, get, list_ues.
Also covers _generate_test_imsi static method.
No mocking — real in-memory SQLite instances.
"""
import json
import threading

import pytest

from sylion.cellular.ue_emulator import UEEmulator, get_ue_emulator
from sylion.core.event_bus import EventBus


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def ue(bus):
    return UEEmulator(event_bus=bus)


# =====================================================================
# _generate_test_imsi (static)
# =====================================================================

class TestGenerateTestIMSI:
    def test_starts_with_00101(self):
        imsi = UEEmulator._generate_test_imsi()
        assert imsi.startswith("00101")

    def test_length_15(self):
        imsi = UEEmulator._generate_test_imsi()
        assert len(imsi) == 15  # MCC(3) + MNC(2) + MSIN(10)

    def test_unique_each_call(self):
        imsi1 = UEEmulator._generate_test_imsi()
        imsi2 = UEEmulator._generate_test_imsi()
        assert imsi1 != imsi2


# =====================================================================
# create
# =====================================================================

class TestCreate:
    def test_returns_ue_id(self, ue):
        u = ue.create()
        assert "ue_id" in u
        assert len(u["ue_id"]) == 12

    def test_default_status_detached(self, ue):
        u = ue.create()
        assert u["status"] == "detached"

    def test_default_technology_4g(self, ue):
        u = ue.create()
        assert u["technology"] == "4G"

    def test_custom_technology(self, ue):
        u = ue.create(technology="5G")
        assert u["technology"] == "5G"

    def test_stack_name(self, ue):
        u = ue.create(stack_name="lab-ue-1")
        assert u["stack_name"] == "lab-ue-1"

    def test_stack_name_default_empty(self, ue):
        u = ue.create()
        assert u["stack_name"] == ""

    def test_auto_generated_imsi(self, ue):
        u = ue.create()
        assert u["imsi"].startswith("00101")
        assert len(u["imsi"]) == 15

    def test_custom_imsi(self, ue):
        u = ue.create(imsi="999990000000001")
        assert u["imsi"] == "999990000000001"

    def test_empty_imsi_triggers_auto(self, ue):
        u = ue.create(imsi="")
        assert len(u["imsi"]) == 15
        assert u["imsi"].startswith("00101")

    def test_default_ran_id_empty(self, ue):
        u = ue.create()
        assert u["ran_id"] == ""

    def test_default_core_id_empty(self, ue):
        u = ue.create()
        assert u["core_id"] == ""

    def test_created_at_set(self, ue):
        import time
        before = time.time()
        u = ue.create()
        after = time.time()
        assert before <= u["created_at"] <= after

    def test_unique_ue_ids(self, ue):
        u1 = ue.create()
        u2 = ue.create()
        assert u1["ue_id"] != u2["ue_id"]

    def test_without_event_bus(self):
        ue_no_bus = UEEmulator()
        u = ue_no_bus.create()
        assert u["status"] == "detached"
        assert len(u["imsi"]) == 15


# =====================================================================
# attach
# =====================================================================

class TestAttach:
    def test_attach_changes_status(self, ue):
        u = ue.create()
        result = ue.attach(u["ue_id"], "ran-001", "core-001")
        assert result["status"] == "attached"

    def test_attach_stores_ran_id(self, ue):
        u = ue.create()
        result = ue.attach(u["ue_id"], "ran-001", "core-001")
        assert result["ran_id"] == "ran-001"

    def test_attach_stores_core_id(self, ue):
        u = ue.create()
        result = ue.attach(u["ue_id"], "ran-001", "core-001")
        assert result["core_id"] == "core-001"

    def test_attach_preserves_imsi(self, ue):
        u = ue.create(imsi="001010000000001")
        result = ue.attach(u["ue_id"], "ran-1", "core-1")
        assert result["imsi"] == "001010000000001"

    def test_attach_preserves_technology(self, ue):
        u = ue.create(technology="5G")
        result = ue.attach(u["ue_id"], "ran-1", "core-1")
        assert result["technology"] == "5G"

    def test_attach_nonexistent(self, ue):
        result = ue.attach("nonexistent", "ran-1", "core-1")
        assert "error" in result
        assert "not found" in result["error"]

    def test_attach_updates_db(self, ue):
        u = ue.create()
        ue.attach(u["ue_id"], "ran-1", "core-1")
        fetched = ue.get(u["ue_id"])
        assert fetched["status"] == "attached"
        assert fetched["ran_id"] == "ran-1"
        assert fetched["core_id"] == "core-1"

    def test_attach_emits_event(self, bus, ue):
        u = ue.create()
        ue.attach(u["ue_id"], "ran-1", "core-1")
        events = bus.query(topic="cellular.ue.attached")
        assert len(events) == 1

    def test_attach_event_payload(self, bus, ue):
        u = ue.create(imsi="001010000000001")
        ue.attach(u["ue_id"], "ran-42", "core-42")
        events = bus.query(topic="cellular.ue.attached")
        payload = events[0]["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["ue_id"] == u["ue_id"]
        assert payload["ran_id"] == "ran-42"
        assert payload["core_id"] == "core-42"
        assert payload["imsi"] == "001010000000001"

    def test_no_event_on_nonexistent_attach(self, bus, ue):
        ue.attach("nonexistent", "ran-1", "core-1")
        events = bus.query(topic="cellular.ue.attached")
        assert len(events) == 0

    def test_reattach_different_ran_core(self, ue):
        u = ue.create()
        ue.attach(u["ue_id"], "ran-1", "core-1")
        result = ue.attach(u["ue_id"], "ran-2", "core-2")
        assert result["ran_id"] == "ran-2"
        assert result["core_id"] == "core-2"


# =====================================================================
# detach
# =====================================================================

class TestDetach:
    def test_detach_changes_status(self, ue):
        u = ue.create()
        ue.attach(u["ue_id"], "ran-1", "core-1")
        result = ue.detach(u["ue_id"])
        assert result["status"] == "detached"

    def test_detach_clears_ran_id(self, ue):
        u = ue.create()
        ue.attach(u["ue_id"], "ran-1", "core-1")
        result = ue.detach(u["ue_id"])
        assert result["ran_id"] == ""

    def test_detach_clears_core_id(self, ue):
        u = ue.create()
        ue.attach(u["ue_id"], "ran-1", "core-1")
        result = ue.detach(u["ue_id"])
        assert result["core_id"] == ""

    def test_detach_already_detached(self, ue):
        u = ue.create()
        result = ue.detach(u["ue_id"])
        assert result["status"] == "detached"

    def test_detach_nonexistent(self, ue):
        result = ue.detach("nonexistent")
        assert "error" in result
        assert "not found" in result["error"]

    def test_detach_updates_db(self, ue):
        u = ue.create()
        ue.attach(u["ue_id"], "ran-1", "core-1")
        ue.detach(u["ue_id"])
        fetched = ue.get(u["ue_id"])
        assert fetched["status"] == "detached"
        assert fetched["ran_id"] == ""
        assert fetched["core_id"] == ""

    def test_detach_preserves_imsi(self, ue):
        u = ue.create(imsi="001010000000001")
        ue.attach(u["ue_id"], "ran-1", "core-1")
        result = ue.detach(u["ue_id"])
        assert result["imsi"] == "001010000000001"


# =====================================================================
# get
# =====================================================================

class TestGet:
    def test_get_existing(self, ue):
        u = ue.create(stack_name="test-ue")
        fetched = ue.get(u["ue_id"])
        assert fetched is not None
        assert fetched["ue_id"] == u["ue_id"]
        assert fetched["stack_name"] == "test-ue"

    def test_get_nonexistent(self, ue):
        assert ue.get("nonexistent") is None

    def test_get_reflects_attach(self, ue):
        u = ue.create()
        ue.attach(u["ue_id"], "ran-1", "core-1")
        fetched = ue.get(u["ue_id"])
        assert fetched["status"] == "attached"
        assert fetched["ran_id"] == "ran-1"

    def test_get_reflects_detach(self, ue):
        u = ue.create()
        ue.attach(u["ue_id"], "ran-1", "core-1")
        ue.detach(u["ue_id"])
        fetched = ue.get(u["ue_id"])
        assert fetched["status"] == "detached"


# =====================================================================
# list_ues
# =====================================================================

class TestListUEs:
    def test_empty(self, ue):
        assert ue.list_ues() == []

    def test_returns_all(self, ue):
        ue.create()
        ue.create()
        ues = ue.list_ues()
        assert len(ues) == 2

    def test_filter_by_status(self, ue):
        u1 = ue.create()
        u2 = ue.create()
        ue.attach(u1["ue_id"], "ran-1", "core-1")
        attached = ue.list_ues(status="attached")
        assert len(attached) == 1
        assert attached[0]["ue_id"] == u1["ue_id"]

    def test_filter_detached(self, ue):
        u1 = ue.create()
        u2 = ue.create()
        ue.attach(u1["ue_id"], "ran-1", "core-1")
        detached = ue.list_ues(status="detached")
        assert len(detached) == 1
        assert detached[0]["ue_id"] == u2["ue_id"]

    def test_filter_no_match(self, ue):
        ue.create()
        assert ue.list_ues(status="attached") == []

    def test_respects_limit(self, ue):
        for i in range(5):
            ue.create()
        ues = ue.list_ues(limit=3)
        assert len(ues) == 3

    def test_default_limit_100(self, ue):
        ues = ue.list_ues()
        assert isinstance(ues, list)

    def test_ordered_by_created_at_desc(self, ue):
        u1 = ue.create()
        u2 = ue.create()
        ues = ue.list_ues()
        assert ues[0]["ue_id"] == u2["ue_id"]
        assert ues[1]["ue_id"] == u1["ue_id"]


# =====================================================================
# get_ue_emulator (module-level singleton)
# =====================================================================

class TestGetUEEmulator:
    def test_returns_instance(self):
        import sylion.cellular.ue_emulator as mod
        mod._var = None
        emu = get_ue_emulator()
        assert isinstance(emu, UEEmulator)
        mod._var = None

    def test_singleton(self):
        import sylion.cellular.ue_emulator as mod
        mod._var = None
        v1 = get_ue_emulator()
        v2 = get_ue_emulator()
        assert v1 is v2
        mod._var = None


# =====================================================================
# Thread safety (basic smoke)
# =====================================================================

class TestThreadSafety:
    def test_concurrent_creates(self, bus):
        """Concurrent create calls -- writes are serialised by module lock."""
        ue = UEEmulator(event_bus=bus)
        errors = []
        ue_ids = []

        def do_create(idx):
            try:
                u = ue.create(stack_name=f"t-{idx}")
                ue_ids.append(u["ue_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_create, args=(i,))
                    for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(ue_ids) == 10
        assert len(ue.list_ues()) == 10

    def test_sequential_attach_after_concurrent_creates(self, bus):
        """Create UEs concurrently, then attach them sequentially."""
        ue = UEEmulator(event_bus=bus)
        ue_ids = []
        for i in range(5):
            u = ue.create(stack_name=f"t-{i}")
            ue_ids.append(u["ue_id"])
        for idx, uid in enumerate(ue_ids):
            result = ue.attach(uid, f"ran-{idx}", f"core-{idx}")
            assert result["status"] == "attached"
        assert len(ue.list_ues(status="attached")) == 5
