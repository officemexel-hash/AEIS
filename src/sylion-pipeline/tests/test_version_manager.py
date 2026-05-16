"""Tests for sylion.core.version_manager"""

import json
import time
import threading

import pytest

from sylion.core.version_manager import (
    VersionManager,
    get_version_manager,
    reset_version_manager,
)
from sylion.core.event_bus import EventBus


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def vm(bus):
    return VersionManager(":memory:", event_bus=bus)


class TestVersionManager:

    # --- Register ---

    def test_register_version_first_is_current(self, vm):
        r = vm.register_version("mod_a", "1.0.0")
        assert r["version_id"]
        assert r["module_id"] == "mod_a"
        assert r["version"] == "1.0.0"
        assert r["is_current"] is True

    def test_register_version_second_not_current(self, vm):
        vm.register_version("mod_a", "1.0.0")
        r = vm.register_version("mod_a", "1.1.0")
        assert r["is_current"] is False

    def test_register_version_with_changelog(self, vm):
        r = vm.register_version("mod_a", "1.0.0", changelog="Initial release")
        assert r["changelog"] == "Initial release"

    def test_register_version_with_compatibility(self, vm):
        compat = {"mod_b": "2.0.0"}
        r = vm.register_version("mod_a", "1.0.0", compatibility=compat)
        assert r["compatibility"] == compat

    def test_register_multiple_modules(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_b", "2.0.0")
        cur_a = vm.get_current_version("mod_a")
        cur_b = vm.get_current_version("mod_b")
        assert cur_a["version"] == "1.0.0"
        assert cur_b["version"] == "2.0.0"

    # --- Get ---

    def test_get_version_exists(self, vm):
        r = vm.register_version("mod_a", "1.0.0")
        got = vm.get_version(r["version_id"])
        assert got["version_id"] == r["version_id"]

    def test_get_version_not_found(self, vm):
        assert vm.get_version("nonexistent") is None

    def test_get_current_version(self, vm):
        vm.register_version("mod_a", "1.0.0")
        cur = vm.get_current_version("mod_a")
        assert cur["version"] == "1.0.0"
        assert cur["is_current"] is True

    def test_get_current_version_none(self, vm):
        assert vm.get_current_version("mod_a") is None

    # --- List ---

    def test_list_versions_all(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_b", "2.0.0")
        versions = vm.list_versions()
        assert len(versions) == 2

    def test_list_versions_by_module(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_a", "1.1.0")
        vm.register_version("mod_b", "2.0.0")
        versions = vm.list_versions(module_id="mod_a")
        assert len(versions) == 2

    def test_list_versions_limit(self, vm):
        for i in range(10):
            vm.register_version("mod_a", f"1.{i}.0")
        versions = vm.list_versions(limit=5)
        assert len(versions) == 5

    # --- Set current ---

    def test_set_current(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_a", "1.1.0")
        result = vm.set_current("mod_a", "1.1.0")
        assert result["is_current"] is True
        cur = vm.get_current_version("mod_a")
        assert cur["version"] == "1.1.0"

    def test_set_current_records_history(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_a", "1.1.0")
        vm.set_current("mod_a", "1.1.0")
        history = vm.get_history(module_id="mod_a")
        types = [h["change_type"] for h in history]
        assert "update" in types

    def test_set_current_invalid_version(self, vm):
        vm.register_version("mod_a", "1.0.0")
        with pytest.raises(ValueError, match="not found"):
            vm.set_current("mod_a", "9.9.9")

    def test_set_current_unsets_previous(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_a", "1.1.0")
        vm.set_current("mod_a", "1.1.0")
        versions = vm.list_versions(module_id="mod_a")
        currents = [v for v in versions if v["is_current"]]
        assert len(currents) == 1
        assert currents[0]["version"] == "1.1.0"

    # --- Rollback ---

    def test_rollback(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_a", "1.1.0")
        vm.set_current("mod_a", "1.1.0")
        vm.register_version("mod_a", "1.2.0")
        vm.set_current("mod_a", "1.2.0")
        result = vm.rollback("mod_a")
        assert result is not None
        cur = vm.get_current_version("mod_a")
        assert cur["version"] == "1.1.0"

    def test_rollback_no_history(self, vm):
        vm.register_version("mod_a", "1.0.0")
        result = vm.rollback("mod_a")
        assert result is None

    def test_rollback_emits_event(self, vm, bus):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_a", "1.1.0")
        vm.set_current("mod_a", "1.1.0")
        vm.register_version("mod_a", "1.2.0")
        vm.set_current("mod_a", "1.2.0")
        vm.rollback("mod_a")
        events = bus.query(topic="version.rollback")
        assert len(events) >= 1

    # --- History ---

    def test_get_history(self, vm):
        vm.register_version("mod_a", "1.0.0")
        history = vm.get_history(module_id="mod_a")
        assert len(history) >= 1
        assert history[0]["change_type"] == "install"

    def test_get_history_by_type(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_a", "1.1.0")
        vm.set_current("mod_a", "1.1.0")
        updates = vm.get_history(change_type="update")
        installs = vm.get_history(change_type="install")
        assert len(installs) >= 1
        assert len(updates) >= 1

    def test_get_history_all(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_b", "2.0.0")
        history = vm.get_history()
        assert len(history) >= 2

    def test_get_history_limit(self, vm):
        for i in range(5):
            vm.register_version(f"mod_{i}", f"1.{i}.0")
        history = vm.get_history(limit=3)
        assert len(history) == 3

    # --- Compatibility ---

    def test_check_compatibility_ok(self, vm):
        vm.register_version("mod_b", "2.0.0")
        vm.register_version("mod_a", "1.0.0", compatibility={"mod_b": "2.0.0"})
        result = vm.check_compatibility("mod_a", "1.0.0")
        assert result["compatible"] is True
        assert result["issues"] == []

    def test_check_compatibility_missing_dep(self, vm):
        vm.register_version("mod_a", "1.0.0", compatibility={"mod_b": "2.0.0"})
        result = vm.check_compatibility("mod_a", "1.0.0")
        assert result["compatible"] is False
        assert len(result["issues"]) == 1

    def test_check_compatibility_version_too_low(self, vm):
        vm.register_version("mod_b", "1.0.0")
        vm.register_version("mod_a", "1.0.0", compatibility={"mod_b": "2.0.0"})
        result = vm.check_compatibility("mod_a", "1.0.0")
        assert result["compatible"] is False

    def test_check_compatibility_no_constraints(self, vm):
        vm.register_version("mod_a", "1.0.0")
        result = vm.check_compatibility("mod_a", "1.0.0")
        assert result["compatible"] is True

    # --- Stats ---

    def test_get_version_stats(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_b", "2.0.0")
        stats = vm.get_version_stats()
        assert stats["total_modules"] == 2
        assert stats["total_versions"] == 2

    def test_get_version_stats_empty(self, vm):
        stats = vm.get_version_stats()
        assert stats["total_modules"] == 0
        assert stats["total_versions"] == 0

    # --- Delete ---

    def test_delete_version(self, vm):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_a", "1.1.0")
        versions = vm.list_versions(module_id="mod_a")
        non_current = [v for v in versions if not v["is_current"]][0]
        assert vm.delete_version(non_current["version_id"]) is True

    def test_delete_version_current_fails(self, vm):
        r = vm.register_version("mod_a", "1.0.0")
        assert vm.delete_version(r["version_id"]) is False

    def test_delete_version_not_found(self, vm):
        assert vm.delete_version("nonexistent") is False

    # --- EventBus ---

    def test_event_bus_registered(self, vm, bus):
        vm.register_version("mod_a", "1.0.0")
        events = bus.query(topic="version.registered")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["module_id"] == "mod_a"

    def test_event_bus_changed(self, vm, bus):
        vm.register_version("mod_a", "1.0.0")
        vm.register_version("mod_a", "1.1.0")
        vm.set_current("mod_a", "1.1.0")
        events = bus.query(topic="version.changed")
        assert len(events) == 1

    # --- Singleton ---

    def test_singleton_get(self):
        reset_version_manager()
        a = get_version_manager()
        b = get_version_manager()
        assert a is b

    def test_singleton_reset(self):
        reset_version_manager()
        a = get_version_manager()
        b = reset_version_manager()
        assert a is not b

    # --- Thread safety ---

    def test_concurrent_registrations(self, vm):
        results = []
        errors = []

        def register(n):
            try:
                r = vm.register_version(f"mod_{n}", "1.0.0")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20

    # --- Compatibility JSON parsing ---

    def test_compatibility_parsed(self, vm):
        compat = {"mod_b": "2.0.0", "mod_c": "1.5.0"}
        r = vm.register_version("mod_a", "1.0.0", compatibility=compat)
        got = vm.get_version(r["version_id"])
        assert got["compatibility"] == compat

    # --- Edge cases ---

    def test_list_versions_empty(self, vm):
        assert vm.list_versions() == []

    def test_get_history_empty(self, vm):
        assert vm.get_history() == []

    def test_no_event_bus(self):
        vm_no_bus = VersionManager(":memory:", event_bus=None)
        r = vm_no_bus.register_version("mod_a", "1.0.0")
        assert r["version_id"]
