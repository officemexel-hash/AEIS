"""
Tests for sylion.core.contract_registry -- ContractRegistry

Covers:
  - register_contract: validation, return values, spec_json as dict/str
  - update_contract: version archiving, spec update, non-existent contract
  - deprecate_contract: active->deprecated, already deprecated, not found
  - get_contract: found / not-found
  - list_contracts: active_only filter, limit
  - bind_contract: validation, contract existence check, event emission
  - unbind: found / not-found
  - get_bindings: all / filtered by contract_id
  - validate_binding: active contract, deprecated contract, no binding, not found
  - EventBus events: contract_registered, contract_updated, contract_deprecated,
    binding_created
  - Thread safety: concurrent register_contract calls
  - Singleton: get_contract_registry / reset_contract_registry
"""
from __future__ import annotations

import json
import threading

import pytest

from sylion.core.contract_registry import (
    ContractRegistry,
    get_contract_registry,
    reset_contract_registry,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    eb = EventBus()
    eb._captured: list[SylionEvent] = []

    _orig = eb.publish

    def _capture(event: SylionEvent):
        eb._captured.append(event)
        return _orig(event)

    eb.publish = _capture
    return eb


@pytest.fixture
def registry():
    """Fresh ContractRegistry (in-memory, no event bus)."""
    return ContractRegistry()


@pytest.fixture
def registry_with_bus(bus):
    """ContractRegistry wired to the captured EventBus."""
    return ContractRegistry(event_bus=bus)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register(registry: ContractRegistry, name: str = "test-contract",
              version: str = "1.0.0", spec: str = "{}") -> dict:
    return registry.register_contract(name, version, spec)


# ============================================================================
# TestRegisterContract
# ============================================================================

class TestRegisterContract:
    def test_basic_registration(self, registry):
        result = _register(registry)
        assert result["contract_id"]
        assert result["name"] == "test-contract"
        assert result["version"] == "1.0.0"
        assert result["status"] == "active"
        assert result["created_at"] > 0

    def test_spec_json_as_string(self, registry):
        spec = '{"fields": ["a", "b"]}'
        result = registry.register_contract("c1", "1.0.0", spec)
        assert result["spec_json"] == spec

    def test_spec_json_as_dict(self, registry):
        spec = {"fields": ["a", "b"]}
        result = registry.register_contract("c1", "1.0.0", spec)
        parsed = json.loads(result["spec_json"])
        assert parsed["fields"] == ["a", "b"]

    def test_empty_name_raises(self, registry):
        with pytest.raises(ValueError, match="non-empty"):
            registry.register_contract("", "1.0.0")

    def test_empty_version_raises(self, registry):
        with pytest.raises(ValueError, match="non-empty"):
            registry.register_contract("my-contract", "")

    def test_default_spec_json(self, registry):
        result = registry.register_contract("c1", "1.0.0")
        assert result["spec_json"] == "{}"

    def test_stored_in_db(self, registry):
        _register(registry)
        contracts = registry.list_contracts()
        assert len(contracts) == 1
        assert contracts[0]["name"] == "test-contract"

    def test_emits_contract_registered(self, registry_with_bus, bus):
        registry_with_bus.register_contract("evt-c", "1.0.0")
        topics = [e.topic for e in bus._captured]
        assert "contract_registered" in topics
        event = [e for e in bus._captured if e.topic == "contract_registered"][0]
        assert event.payload["name"] == "evt-c"

    def test_unique_contract_ids(self, registry):
        r1 = registry.register_contract("c1", "1.0.0")
        r2 = registry.register_contract("c2", "1.0.0")
        assert r1["contract_id"] != r2["contract_id"]


# ============================================================================
# TestUpdateContract
# ============================================================================

class TestUpdateContract:
    def test_update_version(self, registry):
        c = _register(registry, name="upd-c", version="1.0.0")
        result = registry.update_contract(c["contract_id"], "2.0.0", '{"new": true}')
        assert result is not None
        assert result["version"] == "2.0.0"

    def test_update_spec_json(self, registry):
        c = _register(registry, name="upd-spec", version="1.0.0")
        new_spec = {"upgraded": True}
        result = registry.update_contract(c["contract_id"], "1.1.0", new_spec, "minor bump")
        parsed = json.loads(result["spec_json"])
        assert parsed["upgraded"] is True

    def test_update_archives_old_version(self, registry):
        c = _register(registry, name="archive-c", version="1.0.0", spec='{"old": true}')
        registry.update_contract(c["contract_id"], "2.0.0", '{"new": true}', "major change")

        with registry._lock:
            rows = registry._conn.execute(
                "SELECT * FROM contract_versions WHERE contract_id = ?",
                (c["contract_id"],),
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["version"] == "1.0.0"
        assert rows[0]["breaking_changes"] == "major change"

    def test_update_nonexistent_returns_none(self, registry):
        result = registry.update_contract("nonexistent", "2.0.0")
        assert result is None

    def test_update_empty_contract_id_raises(self, registry):
        with pytest.raises(ValueError, match="non-empty"):
            registry.update_contract("", "2.0.0")

    def test_update_empty_new_version_raises(self, registry):
        c = _register(registry)
        with pytest.raises(ValueError, match="non-empty"):
            registry.update_contract(c["contract_id"], "")

    def test_emits_contract_updated(self, registry_with_bus, bus):
        c = registry_with_bus.register_contract("upd-evt", "1.0.0")
        registry_with_bus.update_contract(c["contract_id"], "2.0.0")
        topics = [e.topic for e in bus._captured]
        assert "contract_updated" in topics

    def test_updated_at_changes(self, registry):
        c = _register(registry, name="ts-c", version="1.0.0")
        import time
        time.sleep(0.01)
        result = registry.update_contract(c["contract_id"], "1.1.0")
        assert result["updated_at"] > c["created_at"]


# ============================================================================
# TestDeprecateContract
# ============================================================================

class TestDeprecateContract:
    def test_deprecate_active(self, registry):
        c = _register(registry, name="dep-c")
        assert registry.deprecate_contract(c["contract_id"]) is True
        contract = registry.get_contract(c["contract_id"])
        assert contract["status"] == "deprecated"

    def test_deprecate_already_deprecated(self, registry):
        c = _register(registry, name="dep-twice")
        registry.deprecate_contract(c["contract_id"])
        assert registry.deprecate_contract(c["contract_id"]) is False

    def test_deprecate_nonexistent(self, registry):
        assert registry.deprecate_contract("nonexistent") is False

    def test_deprecate_empty_id_raises(self, registry):
        with pytest.raises(ValueError, match="non-empty"):
            registry.deprecate_contract("")

    def test_emits_contract_deprecated(self, registry_with_bus, bus):
        c = registry_with_bus.register_contract("dep-evt", "1.0.0")
        registry_with_bus.deprecate_contract(c["contract_id"])
        topics = [e.topic for e in bus._captured]
        assert "contract_deprecated" in topics

    def test_deprecated_not_in_active_list(self, registry):
        c = _register(registry, name="active-filter")
        registry.deprecate_contract(c["contract_id"])
        active = registry.list_contracts(active_only=True)
        assert len(active) == 0


# ============================================================================
# TestGetContract
# ============================================================================

class TestGetContract:
    def test_get_existing(self, registry):
        c = _register(registry, name="get-c")
        result = registry.get_contract(c["contract_id"])
        assert result is not None
        assert result["name"] == "get-c"

    def test_get_nonexistent(self, registry):
        assert registry.get_contract("nonexistent") is None

    def test_get_returns_all_fields(self, registry):
        c = registry.register_contract("full-c", "2.0.0", '{"key": "val"}')
        result = registry.get_contract(c["contract_id"])
        assert "contract_id" in result
        assert "name" in result
        assert "version" in result
        assert "spec_json" in result
        assert "status" in result
        assert "created_at" in result
        assert "updated_at" in result


# ============================================================================
# TestListContracts
# ============================================================================

class TestListContracts:
    def test_list_all(self, registry):
        _register(registry, name="c1")
        _register(registry, name="c2")
        _register(registry, name="c3")
        assert len(registry.list_contracts()) == 3

    def test_list_active_only(self, registry):
        c1 = _register(registry, name="active-c")
        _register(registry, name="active-c2")
        registry.deprecate_contract(c1["contract_id"])
        active = registry.list_contracts(active_only=True)
        assert len(active) == 1
        assert active[0]["name"] == "active-c2"

    def test_list_limit(self, registry):
        for i in range(10):
            _register(registry, name=f"c-{i}")
        assert len(registry.list_contracts(limit=5)) == 5

    def test_list_empty(self, registry):
        assert registry.list_contracts() == []

    def test_list_includes_deprecated(self, registry):
        c1 = _register(registry, name="dep-list")
        registry.deprecate_contract(c1["contract_id"])
        all_contracts = registry.list_contracts()
        assert len(all_contracts) == 1


# ============================================================================
# TestBindContract
# ============================================================================

class TestBindContract:
    def test_basic_binding(self, registry):
        c = _register(registry, name="bind-c")
        result = registry.bind_contract(c["contract_id"], "consumer.mod", "provider.mod")
        assert result["binding_id"]
        assert result["consumer_module"] == "consumer.mod"
        assert result["provider_module"] == "provider.mod"
        assert result["created_at"] > 0

    def test_bind_nonexistent_contract_raises(self, registry):
        with pytest.raises(ValueError, match="not found"):
            registry.bind_contract("nonexistent", "consumer", "provider")

    def test_bind_empty_contract_id_raises(self, registry):
        with pytest.raises(ValueError, match="non-empty"):
            registry.bind_contract("", "consumer", "provider")

    def test_bind_empty_consumer_raises(self, registry):
        c = _register(registry, name="bind-ec")
        with pytest.raises(ValueError, match="non-empty"):
            registry.bind_contract(c["contract_id"], "", "provider")

    def test_bind_empty_provider_raises(self, registry):
        c = _register(registry, name="bind-ep")
        with pytest.raises(ValueError, match="non-empty"):
            registry.bind_contract(c["contract_id"], "consumer", "")

    def test_emits_binding_created(self, registry_with_bus, bus):
        c = registry_with_bus.register_contract("bind-evt", "1.0.0")
        registry_with_bus.bind_contract(c["contract_id"], "mod.a", "mod.b")
        topics = [e.topic for e in bus._captured]
        assert "binding_created" in topics

    def test_multiple_bindings_same_contract(self, registry):
        c = _register(registry, name="multi-bind")
        registry.bind_contract(c["contract_id"], "c1", "p1")
        registry.bind_contract(c["contract_id"], "c2", "p2")
        bindings = registry.get_bindings(c["contract_id"])
        assert len(bindings) == 2


# ============================================================================
# TestUnbind
# ============================================================================

class TestUnbind:
    def test_unbind_existing(self, registry):
        c = _register(registry, name="unbind-c")
        b = registry.bind_contract(c["contract_id"], "consumer", "provider")
        assert registry.unbind(b["binding_id"]) is True
        assert registry.get_bindings(c["contract_id"]) == []

    def test_unbind_nonexistent(self, registry):
        assert registry.unbind("nonexistent") is False

    def test_unbind_twice_returns_false(self, registry):
        c = _register(registry, name="unbind-twice")
        b = registry.bind_contract(c["contract_id"], "c", "p")
        assert registry.unbind(b["binding_id"]) is True
        assert registry.unbind(b["binding_id"]) is False


# ============================================================================
# TestGetBindings
# ============================================================================

class TestGetBindings:
    def test_get_all_bindings(self, registry):
        c1 = _register(registry, name="bind-a")
        c2 = _register(registry, name="bind-b")
        registry.bind_contract(c1["contract_id"], "c1", "p1")
        registry.bind_contract(c2["contract_id"], "c2", "p2")
        assert len(registry.get_bindings()) == 2

    def test_get_bindings_by_contract(self, registry):
        c1 = _register(registry, name="filter-a")
        c2 = _register(registry, name="filter-b")
        registry.bind_contract(c1["contract_id"], "c1", "p1")
        registry.bind_contract(c2["contract_id"], "c2", "p2")
        assert len(registry.get_bindings(c1["contract_id"])) == 1

    def test_get_bindings_empty(self, registry):
        assert registry.get_bindings() == []

    def test_get_bindings_nonexistent_contract(self, registry):
        assert registry.get_bindings("nonexistent") == []


# ============================================================================
# TestValidateBinding
# ============================================================================

class TestValidateBinding:
    def test_valid_binding(self, registry):
        c = _register(registry, name="valid-bind")
        registry.bind_contract(c["contract_id"], "consumer", "provider")
        result = registry.validate_binding(c["contract_id"], "consumer", "provider")
        assert result["valid"] is True
        assert result["reason"] == "ok"

    def test_contract_not_found(self, registry):
        result = registry.validate_binding("nonexistent", "consumer", "provider")
        assert result["valid"] is False
        assert "not found" in result["reason"]

    def test_contract_deprecated(self, registry):
        c = _register(registry, name="dep-bind")
        registry.bind_contract(c["contract_id"], "consumer", "provider")
        registry.deprecate_contract(c["contract_id"])
        result = registry.validate_binding(c["contract_id"], "consumer", "provider")
        assert result["valid"] is False
        assert "deprecated" in result["reason"]

    def test_no_binding_between_modules(self, registry):
        c = _register(registry, name="no-bind")
        result = registry.validate_binding(c["contract_id"], "consumer", "provider")
        assert result["valid"] is False
        assert "no binding" in result["reason"]

    def test_wrong_consumer(self, registry):
        c = _register(registry, name="wrong-c")
        registry.bind_contract(c["contract_id"], "correct_consumer", "provider")
        result = registry.validate_binding(c["contract_id"], "wrong_consumer", "provider")
        assert result["valid"] is False

    def test_wrong_provider(self, registry):
        c = _register(registry, name="wrong-p")
        registry.bind_contract(c["contract_id"], "consumer", "correct_provider")
        result = registry.validate_binding(c["contract_id"], "consumer", "wrong_provider")
        assert result["valid"] is False


# ============================================================================
# TestThreadSafety
# ============================================================================

class TestThreadSafety:
    def test_concurrent_register(self, registry):
        errors: list[Exception] = []

        def worker(n: int):
            try:
                for i in range(10):
                    registry.register_contract(f"concurrent_{n}_{i}", "1.0.0")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(registry.list_contracts()) == 50

    def test_concurrent_read_write(self, registry):
        errors: list[Exception] = []

        c = registry.register_contract("rw-contract", "1.0.0")

        def writer():
            try:
                for i in range(20):
                    registry.bind_contract(c["contract_id"], f"c_{i}", f"p_{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    registry.list_contracts()
                    registry.get_bindings()
                    registry.get_contract(c["contract_id"])
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ============================================================================
# TestSingleton
# ============================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        reset_contract_registry()
        r = get_contract_registry()
        assert isinstance(r, ContractRegistry)
        reset_contract_registry()

    def test_get_returns_same_instance(self):
        reset_contract_registry()
        r1 = get_contract_registry()
        r2 = get_contract_registry()
        assert r1 is r2
        reset_contract_registry()

    def test_reset_clears_singleton(self):
        reset_contract_registry()
        r1 = get_contract_registry()
        reset_contract_registry()
        r2 = get_contract_registry()
        assert r1 is not r2
        reset_contract_registry()
