"""Tests for SYLION Execution — Tool Registry.

Covers: register, get, list, update, deprecate, authorization checks,
stats, error handling, event emission, thread safety.
"""
import threading

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.execution.tool_registry import RiskLevel, ToolRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def registry(bus):
    return ToolRegistry(event_bus=bus)


@pytest.fixture
def registry_no_bus():
    return ToolRegistry(event_bus=None)


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_returns_descriptor(self, registry):
        result = registry.register_tool(
            "tool.search", "Web Search", description="Search the web",
            risk_level="medium", category="web",
        )
        assert result["tool_id"] == "tool.search"
        assert result["name"] == "Web Search"
        assert result["risk_level"] == "medium"

    def test_register_with_schema(self, registry):
        schema = {"type": "object", "properties": {"q": {"type": "string"}}}
        registry.register_tool("tool.schema", "Schema Tool", parameters_schema=schema)
        tool = registry.get_tool("tool.schema")
        assert tool["parameters_schema"]["type"] == "object"

    def test_register_default_risk_level(self, registry):
        registry.register_tool("tool.default", "Default Risk")
        tool = registry.get_tool("tool.default")
        assert tool["risk_level"] == "low"

    def test_register_upsert(self, registry):
        registry.register_tool("tool.dup", "First")
        registry.register_tool("tool.dup", "Second")
        tool = registry.get_tool("tool.dup")
        assert tool["name"] == "Second"

    def test_register_invalid_risk_raises(self, registry):
        with pytest.raises(ValueError, match="Invalid risk_level"):
            registry.register_tool("tool.bad", "Bad", risk_level="extreme")


# ---------------------------------------------------------------------------
# 2. Get
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing_tool(self, registry):
        registry.register_tool("tool.get", "GetTest", category="test")
        tool = registry.get_tool("tool.get")
        assert tool is not None
        assert tool["tool_id"] == "tool.get"
        assert tool["category"] == "test"

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get_tool("nonexistent") is None

    def test_get_parses_json_schema(self, registry):
        schema = {"type": "array", "items": {"type": "integer"}}
        registry.register_tool("tool.json", "JSON", parameters_schema=schema)
        tool = registry.get_tool("tool.json")
        assert isinstance(tool["parameters_schema"], dict)

    def test_get_deprecated_as_bool(self, registry):
        registry.register_tool("tool.dep", "Dep")
        registry.deprecate_tool("tool.dep")
        tool = registry.get_tool("tool.dep")
        assert tool["deprecated"] is True


# ---------------------------------------------------------------------------
# 3. List
# ---------------------------------------------------------------------------

class TestList:
    def test_list_empty(self, registry):
        assert registry.list_tools() == []

    def test_list_all(self, registry):
        registry.register_tool("tool.a", "Alpha", category="x")
        registry.register_tool("tool.b", "Beta", category="y")
        tools = registry.list_tools()
        assert len(tools) == 2
        # Ordered by name
        assert tools[0]["name"] == "Alpha"

    def test_list_filter_by_category(self, registry):
        registry.register_tool("tool.a", "A", category="web")
        registry.register_tool("tool.b", "B", category="data")
        result = registry.list_tools(category="web")
        assert len(result) == 1
        assert result[0]["category"] == "web"

    def test_list_filter_by_risk(self, registry):
        registry.register_tool("tool.low", "Low", risk_level="low")
        registry.register_tool("tool.high", "High", risk_level="high")
        result = registry.list_tools(risk_level="high")
        assert len(result) == 1
        assert result[0]["risk_level"] == "high"


# ---------------------------------------------------------------------------
# 4. Update
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_name(self, registry):
        registry.register_tool("tool.upd", "Old")
        result = registry.update_tool("tool.upd", name="New")
        assert result["updated"] is True
        assert registry.get_tool("tool.upd")["name"] == "New"

    def test_update_risk_level(self, registry):
        registry.register_tool("tool.risk", "Risk")
        result = registry.update_tool("tool.risk", risk_level="critical")
        assert result["updated"] is True
        assert registry.get_tool("tool.risk")["risk_level"] == "critical"

    def test_update_nonexistent_tool(self, registry):
        result = registry.update_tool("ghost", name="boo")
        assert result["updated"] is False

    def test_update_no_fields(self, registry):
        result = registry.update_tool("any", foo="bar")
        assert result["updated"] is False

    def test_update_invalid_risk_raises(self, registry):
        registry.register_tool("tool.bad_risk", "X")
        with pytest.raises(ValueError, match="Invalid risk_level"):
            registry.update_tool("tool.bad_risk", risk_level="nuclear")


# ---------------------------------------------------------------------------
# 5. Deprecate
# ---------------------------------------------------------------------------

class TestDeprecate:
    def test_deprecate_tool(self, registry):
        registry.register_tool("tool.dep", "Dep")
        result = registry.deprecate_tool("tool.dep")
        assert result["deprecated"] is True

    def test_deprecate_nonexistent(self, registry):
        result = registry.deprecate_tool("ghost")
        assert result["deprecated"] is False

    def test_deprecate_already_deprecated(self, registry):
        registry.register_tool("tool.twice", "Twice")
        registry.deprecate_tool("tool.twice")
        result = registry.deprecate_tool("tool.twice")
        assert result["deprecated"] is False
        assert "already deprecated" in result["message"]


# ---------------------------------------------------------------------------
# 6. Authorization
# ---------------------------------------------------------------------------

class TestAuthorization:
    def test_low_risk_authorized_at_d0(self, registry):
        registry.register_tool("tool.low", "Low", risk_level="low")
        result = registry.check_authorization("tool.low", "D0")
        assert result["authorized"] is True

    def test_critical_risk_denied_at_d0(self, registry):
        registry.register_tool("tool.crit", "Crit", risk_level="critical")
        result = registry.check_authorization("tool.crit", "D0")
        assert result["authorized"] is False
        assert "reason" in result

    def test_critical_risk_authorized_at_d3(self, registry):
        registry.register_tool("tool.crit2", "Crit2", risk_level="critical")
        result = registry.check_authorization("tool.crit2", "D3")
        assert result["authorized"] is True

    def test_nonexistent_tool_denied(self, registry):
        result = registry.check_authorization("ghost", "D5")
        assert result["authorized"] is False
        assert "not found" in result["reason"]

    def test_deprecated_tool_denied(self, registry):
        registry.register_tool("tool.dep", "Dep", risk_level="low")
        registry.deprecate_tool("tool.dep")
        result = registry.check_authorization("tool.dep", "D0")
        assert result["authorized"] is False
        assert "deprecated" in result["reason"]


# ---------------------------------------------------------------------------
# 7. Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_empty(self, registry):
        stats = registry.get_stats()
        assert stats["total"] == 0
        assert stats["deprecated_count"] == 0

    def test_stats_counts(self, registry):
        registry.register_tool("tool.a", "A", category="web", risk_level="low")
        registry.register_tool("tool.b", "B", category="data", risk_level="high")
        registry.register_tool("tool.c", "C", category="web", risk_level="low")
        stats = registry.get_stats()
        assert stats["total"] == 3
        assert stats["by_category"]["web"] == 2
        assert stats["by_risk_level"]["low"] == 2
        assert stats["deprecated_count"] == 0

    def test_stats_deprecated_count(self, registry):
        registry.register_tool("tool.a", "A")
        registry.register_tool("tool.b", "B")
        registry.deprecate_tool("tool.a")
        stats = registry.get_stats()
        assert stats["deprecated_count"] == 1

    def test_stats_uncategorized(self, registry):
        registry.register_tool("tool.nocat", "NoCat")
        stats = registry.get_stats()
        assert stats["by_category"]["uncategorized"] == 1


# ---------------------------------------------------------------------------
# 8. Event emission
# ---------------------------------------------------------------------------

class TestEvents:
    def test_register_emits_event(self, registry, bus):
        received = []
        bus.subscribe("execution.tool_registry.registered", lambda e: received.append(e))
        registry.register_tool("tool.evt", "Evt")
        assert len(received) == 1
        assert received[0].payload["tool_id"] == "tool.evt"

    def test_update_emits_event(self, registry, bus):
        received = []
        bus.subscribe("execution.tool_registry.updated", lambda e: received.append(e))
        registry.register_tool("tool.u", "U")
        registry.update_tool("tool.u", name="U2")
        assert len(received) == 1

    def test_deprecate_emits_event(self, registry, bus):
        received = []
        bus.subscribe("execution.tool_registry.deprecated", lambda e: received.append(e))
        registry.register_tool("tool.d", "D")
        registry.deprecate_tool("tool.d")
        assert len(received) == 1

    def test_no_bus_no_error(self, registry_no_bus):
        registry_no_bus.register_tool("tool.nobus", "NoBus")
        registry_no_bus.update_tool("tool.nobus", name="StillNoBus")
        registry_no_bus.deprecate_tool("tool.nobus")


# ---------------------------------------------------------------------------
# 9. Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_registrations(self, registry):
        errors = []

        def register(idx):
            try:
                registry.register_tool(f"tool.t{idx}", f"Thread {idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert registry.get_stats()["total"] == 20
