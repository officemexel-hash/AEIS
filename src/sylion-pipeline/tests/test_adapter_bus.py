"""Tests for sylion.execution.adapter_bus -- AdapterBus.

Covers: register_adapter, update_adapter, deregister_adapter,
get_adapter, list_adapters, add_route, remove_route, list_routes,
transform_data, log_transform, get_adapter_stats,
event emission, error handling, thread safety, singleton lifecycle.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.execution.adapter_bus import (
    AdapterBus,
    get_adapter_bus,
    reset_adapter_bus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    reset_adapter_bus()
    yield
    reset_adapter_bus()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def adapter(bus):
    return AdapterBus(event_bus=bus)


@pytest.fixture
def adapter_no_bus():
    return AdapterBus(event_bus=None)


# ===========================================================================
# TestRegisterAdapter
# ===========================================================================

class TestRegisterAdapter:

    def test_register_returns_descriptor(self, adapter):
        result = adapter.register_adapter("JSON Adapter", "json")
        assert result["adapter_id"]
        assert result["name"] == "JSON Adapter"
        assert result["protocol"] == "json"
        assert result["status"] == "active"

    def test_register_default_protocol(self, adapter):
        result = adapter.register_adapter("Default")
        assert result["protocol"] == "json"

    def test_register_with_config(self, adapter):
        result = adapter.register_adapter("Cfg", config_json={"strict": True})
        a = adapter.get_adapter(result["adapter_id"])
        assert a["config"]["strict"] is True

    def test_register_multiple(self, adapter):
        adapter.register_adapter("A", "json")
        adapter.register_adapter("B", "xml")
        adapter.register_adapter("C", "protobuf")
        assert len(adapter.list_adapters()) == 3

    def test_register_emits_event(self, adapter, bus):
        events = []
        bus.subscribe("adapter_registered", events.append)
        adapter.register_adapter("Evt", "json")
        assert len(events) == 1
        assert events[0].payload["protocol"] == "json"

    def test_register_unique_ids(self, adapter):
        r1 = adapter.register_adapter("X")
        r2 = adapter.register_adapter("Y")
        assert r1["adapter_id"] != r2["adapter_id"]


# ===========================================================================
# TestUpdateAdapter
# ===========================================================================

class TestUpdateAdapter:

    def test_update_name(self, adapter):
        r = adapter.register_adapter("Old")
        updated = adapter.update_adapter(r["adapter_id"], name="New")
        assert updated["name"] == "New"

    def test_update_protocol(self, adapter):
        r = adapter.register_adapter("Proto", "json")
        updated = adapter.update_adapter(r["adapter_id"], protocol="xml")
        assert updated["protocol"] == "xml"

    def test_update_status(self, adapter):
        r = adapter.register_adapter("Stat")
        updated = adapter.update_adapter(r["adapter_id"], status="inactive")
        assert updated["status"] == "inactive"

    def test_update_config_dict(self, adapter):
        r = adapter.register_adapter("CfgUpd")
        updated = adapter.update_adapter(r["adapter_id"],
                                         config={"k": "v"})
        a = adapter.get_adapter(r["adapter_id"])
        assert a["config"]["k"] == "v"

    def test_update_nonexistent(self, adapter):
        assert adapter.update_adapter("ghost", name="Nope") is None

    def test_update_no_allowed_fields(self, adapter):
        r = adapter.register_adapter("Bad")
        assert adapter.update_adapter(r["adapter_id"], bad="x") is None


# ===========================================================================
# TestDeregisterAdapter
# ===========================================================================

class TestDeregisterAdapter:

    def test_deregister_existing(self, adapter):
        r = adapter.register_adapter("Del")
        assert adapter.deregister_adapter(r["adapter_id"]) is True
        assert adapter.get_adapter(r["adapter_id"]) is None

    def test_deregister_nonexistent(self, adapter):
        assert adapter.deregister_adapter("ghost") is False

    def test_deregister_removes_routes(self, adapter):
        r = adapter.register_adapter("DelRte")
        aid = r["adapter_id"]
        adapter.add_route(aid, "json", "xml")
        adapter.deregister_adapter(aid)
        assert adapter.list_routes(adapter_id=aid) == []

    def test_deregister_removes_logs(self, adapter):
        r = adapter.register_adapter("DelLog")
        aid = r["adapter_id"]
        adapter.log_transform(aid, None, True, 1.0)
        adapter.deregister_adapter(aid)
        assert adapter.get_adapter_stats()["total_transforms"] == 0

    def test_deregister_twice(self, adapter):
        r = adapter.register_adapter("Twice")
        aid = r["adapter_id"]
        assert adapter.deregister_adapter(aid) is True
        assert adapter.deregister_adapter(aid) is False


# ===========================================================================
# TestGetAdapter
# ===========================================================================

class TestGetAdapter:

    def test_get_existing(self, adapter):
        r = adapter.register_adapter("Get", "json")
        a = adapter.get_adapter(r["adapter_id"])
        assert a is not None
        assert a["name"] == "Get"
        assert a["protocol"] == "json"

    def test_get_nonexistent(self, adapter):
        assert adapter.get_adapter("ghost") is None

    def test_get_parses_config(self, adapter):
        r = adapter.register_adapter("Cfg", config_json={"x": 1})
        a = adapter.get_adapter(r["adapter_id"])
        assert isinstance(a["config"], dict)
        assert a["config"]["x"] == 1


# ===========================================================================
# TestListAdapters
# ===========================================================================

class TestListAdapters:

    def test_list_empty(self, adapter):
        assert adapter.list_adapters() == []

    def test_list_all(self, adapter):
        adapter.register_adapter("A", "json")
        adapter.register_adapter("B", "xml")
        assert len(adapter.list_adapters()) == 2

    def test_list_filter_by_protocol(self, adapter):
        adapter.register_adapter("J1", "json")
        adapter.register_adapter("X1", "xml")
        result = adapter.list_adapters(protocol="json")
        assert len(result) == 1
        assert result[0]["protocol"] == "json"

    def test_list_parses_config(self, adapter):
        adapter.register_adapter("P", config_json={"k": "v"})
        result = adapter.list_adapters()
        assert isinstance(result[0]["config"], dict)


# ===========================================================================
# TestRouteManagement
# ===========================================================================

class TestRouteManagement:

    def test_add_route(self, adapter):
        r = adapter.register_adapter("Rte")
        route = adapter.add_route(r["adapter_id"], "json", "xml",
                                  {"mapping": {"a": "b"}})
        assert route["route_id"]
        assert route["source_format"] == "json"
        assert route["target_format"] == "xml"

    def test_add_route_emits_event(self, adapter, bus):
        events = []
        bus.subscribe("route_added", events.append)
        r = adapter.register_adapter("REvt")
        adapter.add_route(r["adapter_id"], "json", "xml")
        assert len(events) == 1

    def test_remove_route(self, adapter):
        r = adapter.register_adapter("RRm")
        route = adapter.add_route(r["adapter_id"], "json", "xml")
        assert adapter.remove_route(route["route_id"]) is True
        assert adapter.list_routes(adapter_id=r["adapter_id"]) == []

    def test_remove_nonexistent_route(self, adapter):
        assert adapter.remove_route("ghost") is False

    def test_list_routes_all(self, adapter):
        r = adapter.register_adapter("LR")
        adapter.add_route(r["adapter_id"], "json", "xml")
        adapter.add_route(r["adapter_id"], "xml", "json")
        assert len(adapter.list_routes()) == 2

    def test_list_routes_by_adapter(self, adapter):
        r1 = adapter.register_adapter("LR1")
        r2 = adapter.register_adapter("LR2")
        adapter.add_route(r1["adapter_id"], "json", "xml")
        adapter.add_route(r2["adapter_id"], "csv", "json")
        assert len(adapter.list_routes(adapter_id=r1["adapter_id"])) == 1

    def test_list_routes_parses_transform(self, adapter):
        r = adapter.register_adapter("TP")
        adapter.add_route(r["adapter_id"], "json", "xml",
                          {"mapping": {"x": "y"}})
        routes = adapter.list_routes()
        assert isinstance(routes[0]["transform_json"], dict)


# ===========================================================================
# TestTransformData
# ===========================================================================

class TestTransformData:

    def _setup(self, adapter):
        r = adapter.register_adapter("Tr")
        route = adapter.add_route(r["adapter_id"], "json", "xml",
                                  {"mapping": {"old": "new"}})
        return route["route_id"]

    def test_transform_with_mapping(self, adapter):
        route_id = self._setup(adapter)
        result = adapter.transform_data(route_id, {"old": "value"})
        assert result["success"] is True
        assert result["data"]["new"] == "value"
        assert "old" not in result["data"]

    def test_transform_with_include(self, adapter):
        r = adapter.register_adapter("Inc")
        route = adapter.add_route(r["adapter_id"], "json", "json",
                                  {"include": ["a", "b"]})
        result = adapter.transform_data(route["route_id"],
                                        {"a": 1, "b": 2, "c": 3})
        assert result["success"] is True
        assert result["data"] == {"a": 1, "b": 2}

    def test_transform_with_defaults(self, adapter):
        r = adapter.register_adapter("Def")
        route = adapter.add_route(r["adapter_id"], "json", "json",
                                  {"defaults": {"version": 2}})
        result = adapter.transform_data(route["route_id"], {"x": 1})
        assert result["success"] is True
        assert result["data"]["version"] == 2

    def test_transform_nonexistent_route(self, adapter):
        result = adapter.transform_data("ghost", {})
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_transform_completed_emits_event(self, adapter, bus):
        events = []
        bus.subscribe("transform_completed", events.append)
        route_id = self._setup(adapter)
        adapter.transform_data(route_id, {"old": "v"})
        assert len(events) == 1

    def test_transform_no_data(self, adapter):
        route_id = self._setup(adapter)
        result = adapter.transform_data(route_id)
        assert result["success"] is True


# ===========================================================================
# TestLogTransform
# ===========================================================================

class TestLogTransform:

    def test_log_success(self, adapter):
        r = adapter.register_adapter("Log")
        result = adapter.log_transform(r["adapter_id"], "r1", True, 5.0)
        assert result["success"] is True

    def test_log_failure(self, adapter):
        r = adapter.register_adapter("LogF")
        result = adapter.log_transform(r["adapter_id"], "r1", False, 0.0)
        assert result["success"] is False


# ===========================================================================
# TestGetAdapterStats
# ===========================================================================

class TestGetAdapterStats:

    def test_empty_stats(self, adapter):
        stats = adapter.get_adapter_stats()
        assert stats["total_adapters"] == 0
        assert stats["total_routes"] == 0
        assert stats["total_transforms"] == 0
        assert stats["failed_transforms"] == 0

    def test_stats_with_data(self, adapter):
        r = adapter.register_adapter("S1", "json")
        r2 = adapter.register_adapter("S2", "xml")
        adapter.add_route(r["adapter_id"], "json", "xml")
        adapter.log_transform(r["adapter_id"], None, True, 1.0)
        adapter.log_transform(r["adapter_id"], None, False, 0.0)
        stats = adapter.get_adapter_stats()
        assert stats["total_adapters"] == 2
        assert stats["total_routes"] == 1
        assert stats["total_transforms"] == 2
        assert stats["failed_transforms"] == 1
        assert stats["by_protocol"]["json"] == 1
        assert stats["by_protocol"]["xml"] == 1


# ===========================================================================
# TestNoBus
# ===========================================================================

class TestNoBus:

    def test_no_bus_no_crash(self, adapter_no_bus):
        r = adapter_no_bus.register_adapter("NB")
        adapter_no_bus.add_route(r["adapter_id"], "json", "xml")
        adapter_no_bus.log_transform(r["adapter_id"], None, True, 1.0)
        adapter_no_bus.deregister_adapter(r["adapter_id"])


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        assert isinstance(get_adapter_bus(), AdapterBus)

    def test_idempotent(self):
        a = get_adapter_bus()
        b = get_adapter_bus()
        assert a is b

    def test_reset_creates_new(self):
        a = get_adapter_bus()
        b = reset_adapter_bus()
        assert a is not b


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_registrations(self, adapter):
        errors = []

        def register(idx):
            try:
                adapter.register_adapter(f"A-{idx}", "json")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(adapter.list_adapters()) == 20

    def test_concurrent_routes(self, adapter):
        r = adapter.register_adapter("ConcRte")
        aid = r["adapter_id"]
        errors = []

        def add_route(idx):
            try:
                adapter.add_route(aid, f"fmt_{idx}", f"out_{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_route, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(adapter.list_routes(adapter_id=aid)) == 20
