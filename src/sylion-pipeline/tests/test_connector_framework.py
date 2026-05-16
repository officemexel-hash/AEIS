"""Tests for sylion.execution.connector_framework -- ConnectorFramework.

Covers: register_connector, update_connector, deregister_connector,
get_connector, list_connectors, get_config, update_config,
check_health, record_health, get_health_history, get_connector_stats,
event emission, error handling, thread safety, singleton lifecycle.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.execution.connector_framework import (
    ConnectorFramework,
    get_connector_framework,
    reset_connector_framework,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    reset_connector_framework()
    yield
    reset_connector_framework()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def fw(bus):
    return ConnectorFramework(event_bus=bus)


@pytest.fixture
def fw_no_bus():
    return ConnectorFramework(event_bus=None)


# ===========================================================================
# TestRegisterConnector
# ===========================================================================

class TestRegisterConnector:

    def test_register_returns_descriptor(self, fw):
        result = fw.register_connector("External API", "api",
                                       {"timeout": 30})
        assert result["connector_id"]
        assert result["name"] == "External API"
        assert result["connector_type"] == "api"
        assert result["status"] == "active"

    def test_register_default_type(self, fw):
        result = fw.register_connector("Default")
        assert result["connector_type"] == "api"

    def test_register_with_config(self, fw):
        fw.register_connector("With Config", config_json={"retries": 3})
        conn = fw.get_connector(result_id := fw.list_connectors()[0]["connector_id"])
        assert conn["config"]["retries"] == 3

    def test_register_multiple(self, fw):
        fw.register_connector("A", "api")
        fw.register_connector("B", "database")
        fw.register_connector("C", "mq")
        assert len(fw.list_connectors()) == 3

    def test_register_emits_event(self, fw, bus):
        events = []
        bus.subscribe("connector_registered", events.append)
        fw.register_connector("Evt", "api")
        assert len(events) == 1
        assert events[0].payload["connector_type"] == "api"

    def test_register_generates_unique_ids(self, fw):
        r1 = fw.register_connector("First")
        r2 = fw.register_connector("Second")
        assert r1["connector_id"] != r2["connector_id"]


# ===========================================================================
# TestUpdateConnector
# ===========================================================================

class TestUpdateConnector:

    def test_update_name(self, fw):
        r = fw.register_connector("Old Name")
        updated = fw.update_connector(r["connector_id"], name="New Name")
        assert updated["name"] == "New Name"

    def test_update_type(self, fw):
        r = fw.register_connector("X", "api")
        updated = fw.update_connector(r["connector_id"], connector_type="database")
        assert updated["connector_type"] == "database"

    def test_update_status(self, fw):
        r = fw.register_connector("Y")
        updated = fw.update_connector(r["connector_id"], status="inactive")
        assert updated["status"] == "inactive"

    def test_update_nonexistent_returns_none(self, fw):
        assert fw.update_connector("ghost", name="Nope") is None

    def test_update_no_allowed_fields_returns_none(self, fw):
        r = fw.register_connector("Z")
        assert fw.update_connector(r["connector_id"], bad_field="x") is None

    def test_update_emits_event(self, fw, bus):
        events = []
        bus.subscribe("connector_updated", events.append)
        r = fw.register_connector("Upd")
        fw.update_connector(r["connector_id"], name="Upd2")
        assert len(events) == 1
        assert "name" in events[0].payload["updated_fields"]


# ===========================================================================
# TestDeregisterConnector
# ===========================================================================

class TestDeregisterConnector:

    def test_deregister_existing(self, fw):
        r = fw.register_connector("Del")
        assert fw.deregister_connector(r["connector_id"]) is True
        assert fw.get_connector(r["connector_id"]) is None

    def test_deregister_nonexistent(self, fw):
        assert fw.deregister_connector("ghost") is False

    def test_deregister_removes_config(self, fw):
        r = fw.register_connector("DelCfg", config_json={"k": "v"})
        cid = r["connector_id"]
        fw.deregister_connector(cid)
        assert fw.get_config(cid) is None

    def test_deregister_removes_health(self, fw):
        r = fw.register_connector("DelHealth")
        cid = r["connector_id"]
        fw.record_health(cid, "healthy", 10.0)
        fw.deregister_connector(cid)
        assert fw.get_health_history(cid) == []

    def test_deregister_emits_event(self, fw, bus):
        events = []
        bus.subscribe("connector_deregistered", events.append)
        r = fw.register_connector("DelEvt")
        fw.deregister_connector(r["connector_id"])
        assert len(events) == 1

    def test_deregister_twice(self, fw):
        r = fw.register_connector("Twice")
        cid = r["connector_id"]
        assert fw.deregister_connector(cid) is True
        assert fw.deregister_connector(cid) is False


# ===========================================================================
# TestGetConnector
# ===========================================================================

class TestGetConnector:

    def test_get_existing(self, fw):
        r = fw.register_connector("Get", "api", {"k": "v"})
        conn = fw.get_connector(r["connector_id"])
        assert conn is not None
        assert conn["name"] == "Get"
        assert conn["config"]["k"] == "v"

    def test_get_nonexistent(self, fw):
        assert fw.get_connector("ghost") is None

    def test_get_includes_config(self, fw):
        r = fw.register_connector("CfgGet", config_json={"x": 1})
        conn = fw.get_connector(r["connector_id"])
        assert isinstance(conn["config"], dict)


# ===========================================================================
# TestListConnectors
# ===========================================================================

class TestListConnectors:

    def test_list_empty(self, fw):
        assert fw.list_connectors() == []

    def test_list_all(self, fw):
        fw.register_connector("Alpha", "api")
        fw.register_connector("Beta", "database")
        result = fw.list_connectors()
        assert len(result) == 2

    def test_list_filter_by_type(self, fw):
        fw.register_connector("API1", "api")
        fw.register_connector("DB1", "database")
        result = fw.list_connectors(connector_type="api")
        assert len(result) == 1
        assert result[0]["connector_type"] == "api"

    def test_list_no_filter_returns_all(self, fw):
        fw.register_connector("A", "api")
        fw.register_connector("B", "mq")
        assert len(fw.list_connectors()) == 2


# ===========================================================================
# TestConfigManagement
# ===========================================================================

class TestConfigManagement:

    def test_get_config_after_register(self, fw):
        r = fw.register_connector("Cfg", config_json={"timeout": 30})
        cfg = fw.get_config(r["connector_id"])
        assert cfg["timeout"] == 30

    def test_get_config_nonexistent(self, fw):
        assert fw.get_config("ghost") is None

    def test_update_config(self, fw):
        r = fw.register_connector("CfgUpd", config_json={"v": 1})
        cid = r["connector_id"]
        assert fw.update_config(cid, {"v": 2}) is True
        assert fw.get_config(cid)["v"] == 2

    def test_update_config_nonexistent_connector(self, fw):
        assert fw.update_config("ghost", {"v": 1}) is False

    def test_config_versioning(self, fw):
        r = fw.register_connector("Ver", config_json={"v": 1})
        cid = r["connector_id"]
        fw.update_config(cid, {"v": 2})
        fw.update_config(cid, {"v": 3})
        assert fw.get_config(cid)["v"] == 3


# ===========================================================================
# TestHealthTracking
# ===========================================================================

class TestHealthTracking:

    def test_record_health(self, fw):
        r = fw.register_connector("H")
        cid = r["connector_id"]
        result = fw.record_health(cid, "healthy", 15.5)
        assert result["status"] == "healthy"
        assert result["latency_ms"] == 15.5

    def test_check_health_latest(self, fw):
        r = fw.register_connector("H2")
        cid = r["connector_id"]
        fw.record_health(cid, "healthy", 5.0)
        fw.record_health(cid, "degraded", 100.0)
        h = fw.check_health(cid)
        assert h["status"] == "degraded"

    def test_check_health_no_records(self, fw):
        r = fw.register_connector("H3")
        assert fw.check_health(r["connector_id"]) is None

    def test_get_health_history(self, fw):
        r = fw.register_connector("Hist")
        cid = r["connector_id"]
        for i in range(5):
            fw.record_health(cid, "healthy", float(i))
        history = fw.get_health_history(cid)
        assert len(history) == 5

    def test_get_health_history_with_limit(self, fw):
        r = fw.register_connector("Lim")
        cid = r["connector_id"]
        for i in range(10):
            fw.record_health(cid, "healthy", float(i))
        history = fw.get_health_history(cid, limit=3)
        assert len(history) == 3

    def test_unhealthy_emits_event(self, fw, bus):
        events = []
        bus.subscribe("connector_unhealthy", events.append)
        r = fw.register_connector("Unh")
        fw.record_health(r["connector_id"], "down", 0.0)
        assert len(events) == 1
        assert events[0].payload["health_status"] == "down"

    def test_healthy_no_unhealthy_event(self, fw, bus):
        events = []
        bus.subscribe("connector_unhealthy", events.append)
        r = fw.register_connector("Ok")
        fw.record_health(r["connector_id"], "healthy", 5.0)
        assert len(events) == 0


# ===========================================================================
# TestGetConnectorStats
# ===========================================================================

class TestGetConnectorStats:

    def test_empty_stats(self, fw):
        stats = fw.get_connector_stats()
        assert stats["total"] == 0
        assert stats["by_type"] == {}
        assert stats["unhealthy"] == 0

    def test_stats_with_connectors(self, fw):
        fw.register_connector("A", "api")
        fw.register_connector("B", "database")
        fw.register_connector("C", "api")
        stats = fw.get_connector_stats()
        assert stats["total"] == 3
        assert stats["by_type"]["api"] == 2
        assert stats["by_type"]["database"] == 1

    def test_stats_unhealthy_count(self, fw):
        r = fw.register_connector("U", "api")
        fw.record_health(r["connector_id"], "down", 0.0)
        stats = fw.get_connector_stats()
        assert stats["unhealthy"] == 1


# ===========================================================================
# TestNoBus
# ===========================================================================

class TestNoBus:

    def test_no_bus_no_crash(self, fw_no_bus):
        r = fw_no_bus.register_connector("NB")
        fw_no_bus.update_connector(r["connector_id"], name="NB2")
        fw_no_bus.record_health(r["connector_id"], "healthy", 1.0)
        fw_no_bus.deregister_connector(r["connector_id"])


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        assert isinstance(get_connector_framework(), ConnectorFramework)

    def test_idempotent(self):
        a = get_connector_framework()
        b = get_connector_framework()
        assert a is b

    def test_reset_creates_new(self):
        a = get_connector_framework()
        b = reset_connector_framework()
        assert a is not b


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_registrations(self, fw):
        errors = []

        def register(idx):
            try:
                fw.register_connector(f"Conn-{idx}", "api")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(fw.list_connectors()) == 20

    def test_concurrent_health_records(self, fw):
        r = fw.register_connector("ConcHealth")
        cid = r["connector_id"]
        errors = []

        def record(idx):
            try:
                fw.record_health(cid, "healthy", float(idx))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(fw.get_health_history(cid)) == 20
