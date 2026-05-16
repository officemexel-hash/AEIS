"""Tests for SYLION Environment Hot-Swap Orchestrator."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from sylion.core.hot_swap import (
    HotSwapOrchestrator,
    HotSwapResult,
    Environment,
    get_hot_swap_orchestrator,
    reset_hot_swap_orchestrator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure singleton is reset between tests."""
    reset_hot_swap_orchestrator()
    yield
    reset_hot_swap_orchestrator()


@pytest.fixture
def orch() -> HotSwapOrchestrator:
    """Fresh orchestrator with no event bus."""
    return HotSwapOrchestrator()


@pytest.fixture
def mock_bus():
    """Mock EventBus that records published events."""
    bus = MagicMock()
    bus.publish = MagicMock()
    return bus


@pytest.fixture
def orch_with_bus(mock_bus) -> HotSwapOrchestrator:
    """Orchestrator wired to a mock event bus."""
    return HotSwapOrchestrator(event_bus=mock_bus)


# ---------------------------------------------------------------------------
# 1. Environment listing
# ---------------------------------------------------------------------------

class TestListEnvironments:

    def test_returns_three_default_envs(self, orch):
        envs = orch.list_environments()
        names = {e["name"] for e in envs}
        assert names == {"dev", "staging", "prod"}

    def test_dev_is_active_by_default(self, orch):
        envs = orch.list_environments()
        dev = next(e for e in envs if e["name"] == "dev")
        assert dev["is_active"] is True
        staging = next(e for e in envs if e["name"] == "staging")
        assert staging["is_active"] is False

    def test_each_env_has_config(self, orch):
        envs = orch.list_environments()
        for env in envs:
            assert isinstance(env["config"], dict)
            assert "security_profile" in env["config"]

    def test_each_env_has_active_since(self, orch):
        envs = orch.list_environments()
        for env in envs:
            assert env["active_since"] > 0


# ---------------------------------------------------------------------------
# 2. Switch all modules
# ---------------------------------------------------------------------------

class TestSwitchAllModules:

    def test_switch_to_staging(self, orch):
        orch.bind_module("mod-a", "dev")
        orch.bind_module("mod-b", "dev")
        result = orch.switch_env("staging")
        assert result.success is True
        assert result.old_env == "dev"
        assert result.new_env == "staging"
        assert sorted(result.switched_modules) == ["mod-a", "mod-b"]

    def test_active_env_updates(self, orch):
        orch.switch_env("prod")
        active = orch.get_active()
        assert active["name"] == "prod"

    def test_switch_no_modules_is_ok(self, orch):
        result = orch.switch_env("staging")
        assert result.success is True
        assert result.switched_modules == []


# ---------------------------------------------------------------------------
# 3. Switch with module filter
# ---------------------------------------------------------------------------

class TestSwitchWithFilter:

    def test_only_switches_filtered_modules(self, orch):
        orch.bind_module("mod-a", "dev")
        orch.bind_module("mod-b", "dev")
        result = orch.switch_env("staging", module_filter=["mod-a"])
        assert result.success is True
        assert result.switched_modules == ["mod-a"]

        # mod-b should still be in dev
        mod_b_env = orch.get_module_env("mod-b")
        assert mod_b_env["env_name"] == "dev"

        # mod-a should now be in staging
        mod_a_env = orch.get_module_env("mod-a")
        assert mod_a_env["env_name"] == "staging"

    def test_filter_does_not_change_active_env(self, orch):
        orch.bind_module("mod-a", "dev")
        orch.switch_env("staging", module_filter=["mod-a"])
        # Active env stays dev because filter means partial switch
        active = orch.get_active()
        assert active["name"] == "dev"

    def test_empty_filter_switches_nothing(self, orch):
        orch.bind_module("mod-a", "dev")
        result = orch.switch_env("staging", module_filter=[])
        assert result.success is True
        assert result.switched_modules == []


# ---------------------------------------------------------------------------
# 4. Bind / get module env
# ---------------------------------------------------------------------------

class TestBindModule:

    def test_bind_and_get(self, orch):
        result = orch.bind_module("mod-x", "prod")
        assert result["bound"] is True
        assert result["env_name"] == "prod"

        env_info = orch.get_module_env("mod-x")
        assert env_info["module_id"] == "mod-x"
        assert env_info["env_name"] == "prod"

    def test_rebind_changes_env(self, orch):
        orch.bind_module("mod-y", "dev")
        orch.bind_module("mod-y", "staging")
        env_info = orch.get_module_env("mod-y")
        assert env_info["env_name"] == "staging"

    def test_unknown_env_returns_error(self, orch):
        result = orch.bind_module("mod-z", "nonexistent")
        assert result["bound"] is False
        assert "Unknown environment" in result["message"]

    def test_unbound_module_returns_none(self, orch):
        env_info = orch.get_module_env("ghost-module")
        assert env_info["env_name"] is None


# ---------------------------------------------------------------------------
# 5. Unknown environment handling
# ---------------------------------------------------------------------------

class TestUnknownEnvironment:

    def test_switch_to_unknown_fails(self, orch):
        result = orch.switch_env("does-not-exist")
        assert result.success is False
        assert result.new_env == "does-not-exist"

    def test_switch_to_unknown_with_filter_fails(self, orch):
        result = orch.switch_env("invalid", module_filter=["mod-a"])
        assert result.success is False


# ---------------------------------------------------------------------------
# 6. Event emission with mock bus
# ---------------------------------------------------------------------------

class TestEventEmission:

    def test_switch_emits_hot_swap_event(self, orch_with_bus, mock_bus):
        orch_with_bus.switch_env("staging")
        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][0]
        assert event.topic == "env.hot_swap"
        assert event.payload["old_env"] == "dev"
        assert event.payload["new_env"] == "staging"
        assert event.source_module == "core.hot_swap"

    def test_bind_emits_module_bound_event(self, orch_with_bus, mock_bus):
        orch_with_bus.bind_module("mod-a", "prod")
        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][0]
        assert event.topic == "env.module_bound"
        assert event.payload["module_id"] == "mod-a"
        assert event.payload["env_name"] == "prod"

    def test_no_event_without_bus(self, orch):
        # Should not raise even with no event bus
        orch.switch_env("prod")
        orch.bind_module("mod-a", "staging")


# ---------------------------------------------------------------------------
# 7. Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_switches(self, orch):
        errors: list[Exception] = []
        results: list[HotSwapResult] = []
        lock = threading.Lock()

        def worker(target: str):
            try:
                r = orch.switch_env(target)
                with lock:
                    results.append(r)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=worker, args=("staging",)),
            threading.Thread(target=worker, args=("prod",)),
            threading.Thread(target=worker, args=("dev",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_concurrent_binds(self, orch):
        errors: list[Exception] = []
        results: list[dict] = []
        lock = threading.Lock()

        def worker(module_id: str, env_name: str):
            try:
                r = orch.bind_module(module_id, env_name)
                with lock:
                    results.append(r)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=worker, args=("mod-a", "dev")),
            threading.Thread(target=worker, args=("mod-b", "staging")),
            threading.Thread(target=worker, args=("mod-c", "prod")),
            threading.Thread(target=worker, args=("mod-d", "dev")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(r["bound"] for r in results)

    def test_concurrent_read_write(self, orch):
        """Reads and writes interleaved should not crash."""
        errors: list[Exception] = []
        lock = threading.Lock()

        def reader():
            try:
                for _ in range(50):
                    orch.list_environments()
                    orch.get_active()
                    orch.health_check()
            except Exception as e:
                with lock:
                    errors.append(e)

        def writer():
            try:
                for i in range(50):
                    orch.bind_module(f"mod-{i}", "staging")
                    orch.switch_env("staging")
                    orch.switch_env("dev")
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# 8. Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:

    def test_returns_healthy(self, orch):
        health = orch.health_check()
        assert health["status"] == "healthy"
        assert health["active_env"] == "dev"

    def test_reports_env_list(self, orch):
        health = orch.health_check()
        env_names = {e["name"] for e in health["environments"]}
        assert env_names == {"dev", "staging", "prod"}

    def test_module_count_tracks_bindings(self, orch):
        orch.bind_module("m1", "dev")
        orch.bind_module("m2", "staging")
        health = orch.health_check()
        dev_env = next(e for e in health["environments"] if e["name"] == "dev")
        staging_env = next(e for e in health["environments"] if e["name"] == "staging")
        assert dev_env["module_count"] == 1
        assert staging_env["module_count"] == 1

    def test_is_active_flag(self, orch):
        health = orch.health_check()
        for env in health["environments"]:
            assert env["is_active"] == (env["name"] == "dev")


# ---------------------------------------------------------------------------
# 9. Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_returns_instance(self):
        orch = get_hot_swap_orchestrator()
        assert isinstance(orch, HotSwapOrchestrator)

    def test_singleton_is_same_instance(self):
        a = get_hot_swap_orchestrator()
        b = get_hot_swap_orchestrator()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_hot_swap_orchestrator()
        reset_hot_swap_orchestrator()
        b = get_hot_swap_orchestrator()
        assert a is not b
