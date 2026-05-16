"""Tests for SYLION AEIS Environment Orchestrator -- multi-environment support.

Covers:
  - Environment registration and listing
  - Active environment management
  - Switching with approval
  - Environment comparison / diff
  - Validation
  - Thread safety
  - Singleton
  - EventBus emission
  - Legacy deploy API backward compatibility
"""
from __future__ import annotations

import threading
import time

import pytest

from sylion.core.environment_orchestrator import (
    DeployAction,
    DeployRequest,
    EnvironmentOrchestrator,
    get_environment_orchestrator,
    reset_environment_orchestrator,
)
from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.module_registry import (
    ModuleKind,
    ModuleLifecycleStage,
    ModuleManifest,
    ModuleRegistry,
    SecurityProfile,
)
from sylion.security.profiles import PROFILES


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global singleton before and after each test."""
    reset_environment_orchestrator()
    yield
    reset_environment_orchestrator()


def _make_orchestrator(*, with_bus: bool = False) -> EnvironmentOrchestrator:
    """Create a fresh orchestrator with its own in-memory DB."""
    bus = EventBus() if with_bus else None
    return EnvironmentOrchestrator(db_path=":memory:", event_bus=bus)


def _make_registry(*module_ids: str, lifecycle: str = "stable") -> ModuleRegistry:
    """Create a module registry with given IDs at the given lifecycle stage."""
    reg = ModuleRegistry()
    for mid in module_ids:
        manifest = ModuleManifest(
            module_id=mid,
            module_kind=ModuleKind.CORE_KERNEL,
            owner_plan="P01",
            lifecycle_stage=ModuleLifecycleStage(lifecycle),
        )
        reg.register(manifest)
    return reg


# ---------------------------------------------------------------------------
# 1. Environment registration
# ---------------------------------------------------------------------------

class TestRegisterEnvironment:
    def test_register_dev_environment(self):
        orch = _make_orchestrator()
        result = orch.register_environment("dev", "dev-light", ["mod_a", "mod_b"])
        assert result["registered"] is True
        assert result["env_id"] == "dev"
        assert result["profile"] == "dev-light"

    def test_register_all_four_environments(self):
        orch = _make_orchestrator()
        envs = [
            ("dev", "dev-light", ["m1"]),
            ("test", "test-light", ["m1", "m2"]),
            ("staging", "staging-strict", ["m1", "m2", "m3"]),
            ("prod", "prod-strict", ["m1", "m2", "m3", "m4"]),
        ]
        for env_id, profile, modules in envs:
            result = orch.register_environment(env_id, profile, modules)
            assert result["registered"] is True

    def test_register_with_config(self):
        orch = _make_orchestrator()
        result = orch.register_environment(
            "dev", "dev-light", ["m1"],
            config={"debug": True, "log_level": "DEBUG"},
        )
        assert result["registered"] is True

    def test_register_duplicate_rejected(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        result = orch.register_environment("dev", "test-light")
        assert result["registered"] is False
        assert "already registered" in result["message"]

    def test_register_unknown_profile_rejected(self):
        orch = _make_orchestrator()
        result = orch.register_environment("dev", "unknown-profile")
        assert result["registered"] is False
        assert "Unknown profile" in result["message"]

    def test_register_empty_modules_list(self):
        orch = _make_orchestrator()
        result = orch.register_environment("empty", "dev-light", [])
        assert result["registered"] is True

    def test_register_no_modules_defaults_empty(self):
        orch = _make_orchestrator()
        result = orch.register_environment("dev", "dev-light")
        assert result["registered"] is True
        cfg = orch.get_environment_config("dev")
        assert cfg["modules"] == []

    def test_register_with_no_config_defaults_empty(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1"])
        cfg = orch.get_environment_config("dev")
        assert cfg["config"] == {}


# ---------------------------------------------------------------------------
# 2. Listing environments
# ---------------------------------------------------------------------------

class TestListEnvironments:
    def test_list_empty(self):
        orch = _make_orchestrator()
        assert orch.list_environments() == []

    def test_list_single(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1"])
        envs = orch.list_environments()
        assert len(envs) == 1
        assert envs[0]["env_id"] == "dev"
        assert envs[0]["profile"] == "dev-light"
        assert envs[0]["module_count"] == 1

    def test_list_multiple(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1"])
        orch.register_environment("prod", "prod-strict", ["m1", "m2", "m3"])
        envs = orch.list_environments()
        assert len(envs) == 2

    def test_list_shows_active_flag(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        orch.register_environment("test", "test-light")
        envs = orch.list_environments()
        # First registered becomes active by default
        dev_env = next(e for e in envs if e["env_id"] == "dev")
        test_env = next(e for e in envs if e["env_id"] == "test")
        assert dev_env["is_active"] is True
        assert test_env["is_active"] is False


# ---------------------------------------------------------------------------
# 3. Active environment management
# ---------------------------------------------------------------------------

class TestActiveEnvironment:
    def test_no_active_when_empty(self):
        orch = _make_orchestrator()
        assert orch.get_active_environment() is None

    def test_first_registered_becomes_active(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1"])
        active = orch.get_active_environment()
        assert active is not None
        assert active["env_id"] == "dev"
        assert active["profile"] == "dev-light"

    def test_first_registered_active_among_many(self):
        orch = _make_orchestrator()
        orch.register_environment("test", "test-light")
        orch.register_environment("prod", "prod-strict")
        active = orch.get_active_environment()
        assert active["env_id"] == "test"

    def test_active_returns_full_config(self):
        orch = _make_orchestrator()
        orch.register_environment(
            "dev", "dev-light", ["m1", "m2"],
            config={"debug": True},
        )
        active = orch.get_active_environment()
        assert active["modules"] == ["m1", "m2"]
        assert active["config"]["debug"] is True
        assert active["security"] is not None
        assert active["security"]["auth_mode"] == "bootstrap"


# ---------------------------------------------------------------------------
# 4. Switching environments
# ---------------------------------------------------------------------------

class TestSwitchEnvironment:
    def test_switch_with_approval(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        orch.register_environment("prod", "prod-strict")
        result = orch.switch_environment("prod", "approval-123")
        assert result["switched"] is True
        assert result["from_env"] == "dev"
        assert result["to_env"] == "prod"
        assert orch.get_active_environment()["env_id"] == "prod"

    def test_switch_without_approval_rejected(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        orch.register_environment("prod", "prod-strict")
        result = orch.switch_environment("prod", "")
        assert result["switched"] is False
        assert "approval_id is required" in result["message"]

    def test_switch_blank_approval_rejected(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        orch.register_environment("prod", "prod-strict")
        result = orch.switch_environment("prod", "   ")
        assert result["switched"] is False

    def test_switch_to_same_env_rejected(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        result = orch.switch_environment("dev", "approval-1")
        assert result["switched"] is False
        assert "Already on" in result["message"]

    def test_switch_to_unknown_env_rejected(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        result = orch.switch_environment("nonexistent", "approval-1")
        assert result["switched"] is False
        assert "not found" in result["message"]

    def test_switch_records_in_history(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        orch.register_environment("staging", "staging-strict")
        orch.switch_environment("staging", "approval-1")
        history = orch.get_switch_history()
        assert len(history) == 1
        assert history[0]["from_env"] == "dev"
        assert history[0]["to_env"] == "staging"
        assert history[0]["approval_id"] == "approval-1"

    def test_multiple_switches(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        orch.register_environment("test", "test-light")
        orch.register_environment("prod", "prod-strict")

        orch.switch_environment("test", "approval-1")
        orch.switch_environment("prod", "approval-2")

        history = orch.get_switch_history()
        assert len(history) == 2
        assert history[0]["to_env"] == "test"
        assert history[1]["to_env"] == "prod"

    def test_switch_updates_active_flag_in_listing(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        orch.register_environment("prod", "prod-strict")
        orch.switch_environment("prod", "approval-1")

        envs = orch.list_environments()
        dev_env = next(e for e in envs if e["env_id"] == "dev")
        prod_env = next(e for e in envs if e["env_id"] == "prod")
        assert dev_env["is_active"] is False
        assert prod_env["is_active"] is True


# ---------------------------------------------------------------------------
# 5. Get environment config
# ---------------------------------------------------------------------------

class TestGetEnvironmentConfig:
    def test_returns_full_config(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1"], {"key": "val"})
        cfg = orch.get_environment_config("dev")
        assert cfg["env_id"] == "dev"
        assert cfg["profile"] == "dev-light"
        assert cfg["modules"] == ["m1"]
        assert cfg["config"]["key"] == "val"

    def test_returns_security_details(self):
        orch = _make_orchestrator()
        orch.register_environment("prod", "prod-strict")
        cfg = orch.get_environment_config("prod")
        assert cfg["security"]["auth_mode"] == "mTLS"
        assert cfg["security"]["audit_level"] == "full"
        assert cfg["security"]["exec_guard"] == "enforce"
        assert cfg["security"]["encryption_at_rest"] is True
        assert cfg["security"]["signing_enabled"] is True

    def test_returns_none_for_unknown(self):
        orch = _make_orchestrator()
        assert orch.get_environment_config("nonexistent") is None

    def test_dev_light_security(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        cfg = orch.get_environment_config("dev")
        assert cfg["security"]["auth_mode"] == "bootstrap"
        assert cfg["security"]["exec_guard"] == "off"
        assert cfg["security"]["encryption_at_rest"] is False

    def test_staging_strict_security(self):
        orch = _make_orchestrator()
        orch.register_environment("staging", "staging-strict")
        cfg = orch.get_environment_config("staging")
        assert cfg["security"]["policy_enforcement"] == "strict"


# ---------------------------------------------------------------------------
# 6. Environment comparison
# ---------------------------------------------------------------------------

class TestCompareEnvironments:
    def test_compare_different_profiles(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1"])
        orch.register_environment("prod", "prod-strict", ["m1"])
        result = orch.compare_environments("dev", "prod")
        assert result["comparable"] is True
        assert result["profile_diff"]["same"] is False
        assert result["profile_diff"]["env_a"] == "dev-light"
        assert result["profile_diff"]["env_b"] == "prod-strict"

    def test_compare_module_differences(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1", "m2", "m3"])
        orch.register_environment("prod", "prod-strict", ["m1", "m2", "m4"])
        result = orch.compare_environments("dev", "prod")
        assert result["modules_only_in_a"] == ["m3"]
        assert result["modules_only_in_b"] == ["m4"]
        assert sorted(result["modules_common"]) == ["m1", "m2"]

    def test_compare_config_diff(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", config={"debug": True, "timeout": 30})
        orch.register_environment("prod", "prod-strict", config={"debug": False, "timeout": 10})
        result = orch.compare_environments("dev", "prod")
        assert "debug" in result["config_diff"]
        assert result["config_diff"]["debug"]["env_a"] is True
        assert result["config_diff"]["debug"]["env_b"] is False

    def test_compare_same_environments(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1"], {"k": "v"})
        result = orch.compare_environments("dev", "dev")
        assert result["comparable"] is True
        assert result["profile_diff"]["same"] is True
        assert result["modules_only_in_a"] == []
        assert result["modules_only_in_b"] == []
        assert result["config_diff"] == {}

    def test_compare_unknown_environment(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        result = orch.compare_environments("dev", "nonexistent")
        assert result["comparable"] is False
        assert "not found" in result["message"]


# ---------------------------------------------------------------------------
# 7. Diff (active vs target)
# ---------------------------------------------------------------------------

class TestGetDiff:
    def test_diff_active_vs_target(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1"])
        orch.register_environment("prod", "prod-strict", ["m1", "m2"])
        diff = orch.get_diff("prod")
        assert diff["comparable"] is True
        assert diff["env_a"] == "dev"
        assert diff["env_b"] == "prod"
        assert diff["modules_only_in_b"] == ["m2"]

    def test_diff_no_active_env(self):
        orch = _make_orchestrator()
        orch.register_environment("prod", "prod-strict")
        # Reset active to simulate no active environment
        orch._conn.execute("DELETE FROM sylion_env_meta WHERE key = 'active_env'")
        orch._conn.commit()
        diff = orch.get_diff("prod")
        assert diff["comparable"] is False
        assert "No active environment" in diff["message"]


# ---------------------------------------------------------------------------
# 8. Validation
# ---------------------------------------------------------------------------

class TestValidateEnvironment:
    def test_validate_unknown_environment(self):
        orch = _make_orchestrator()
        result = orch.validate_environment("nonexistent")
        assert result["valid"] is False
        assert "not found" in result["message"]

    def test_validate_with_no_registry(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1", "m2"])
        result = orch.validate_environment("dev")
        # Without registry, modules assumed healthy
        assert result["valid"] is True
        assert result["healthy_modules"] == ["m1", "m2"]

    def test_validate_all_healthy(self):
        orch = _make_orchestrator()
        reg = _make_registry("m1", "m2", lifecycle="stable")
        orch.set_registry(reg)
        orch.register_environment("dev", "dev-light", ["m1", "m2"])
        result = orch.validate_environment("dev")
        assert result["valid"] is True
        assert len(result["healthy_modules"]) == 2
        assert len(result["unhealthy_modules"]) == 0

    def test_validate_unhealthy_module(self):
        orch = _make_orchestrator()
        reg = _make_registry("m1", lifecycle="draft")
        orch.set_registry(reg)
        orch.register_environment("dev", "dev-light", ["m1"])
        result = orch.validate_environment("dev")
        assert result["valid"] is False
        assert "m1" in result["unhealthy_modules"]

    def test_validate_missing_module(self):
        orch = _make_orchestrator()
        reg = _make_registry("m1", lifecycle="stable")
        orch.set_registry(reg)
        orch.register_environment("dev", "dev-light", ["m1", "m_missing"])
        result = orch.validate_environment("dev")
        assert result["valid"] is False
        assert "m_missing" in result["missing_modules"]

    def test_validate_mixed_health(self):
        orch = _make_orchestrator()
        reg = _make_registry("m_good", lifecycle="stable")
        reg2 = _make_registry("m_bad", lifecycle="draft")
        # Merge: register m_bad in the same registry
        reg.register(ModuleManifest(
            module_id="m_bad",
            module_kind=ModuleKind.CORE_KERNEL,
            owner_plan="P01",
            lifecycle_stage=ModuleLifecycleStage.DRAFT,
        ))
        orch.set_registry(reg)
        orch.register_environment("dev", "dev-light", ["m_good", "m_bad", "m_missing"])
        result = orch.validate_environment("dev")
        assert result["valid"] is False
        assert "m_good" in result["healthy_modules"]
        assert "m_bad" in result["unhealthy_modules"]
        assert "m_missing" in result["missing_modules"]


# ---------------------------------------------------------------------------
# 9. EventBus emission
# ---------------------------------------------------------------------------

class TestEventBusEmission:
    def test_register_emits_event(self):
        bus = EventBus()
        orch = _make_orchestrator(with_bus=True)
        orch._event_bus = bus

        events: list[SylionEvent] = []
        bus.subscribe("environment.registered", events.append)

        orch.register_environment("dev", "dev-light", ["m1"])

        assert len(events) == 1
        assert events[0].payload["env_id"] == "dev"
        assert events[0].payload["profile"] == "dev-light"
        assert events[0].payload["module_count"] == 1

    def test_switch_emits_event(self):
        bus = EventBus()
        orch = _make_orchestrator()
        orch._event_bus = bus

        events: list[SylionEvent] = []
        bus.subscribe("environment.switched", events.append)

        orch.register_environment("dev", "dev-light")
        orch.register_environment("prod", "prod-strict")
        orch.switch_environment("prod", "approval-xyz")

        assert len(events) == 1
        assert events[0].payload["from_env"] == "dev"
        assert events[0].payload["to_env"] == "prod"
        assert events[0].payload["approval_id"] == "approval-xyz"

    def test_deploy_emits_event(self):
        bus = EventBus()
        orch = _make_orchestrator()
        orch._event_bus = bus

        events: list[SylionEvent] = []
        bus.subscribe("environment.deployed", events.append)

        reg = _make_registry("m1", lifecycle="draft")
        orch.set_registry(reg)
        orch.deploy(DeployRequest(module_id="m1", action=DeployAction.DEPLOY))

        assert len(events) == 1
        assert events[0].payload["module_id"] == "m1"

    def test_no_event_without_bus(self):
        orch = _make_orchestrator()
        # Should not raise
        orch.register_environment("dev", "dev-light")
        orch.switch_environment("dev", "approval-1")  # same env, no-op


# ---------------------------------------------------------------------------
# 10. Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_registrations(self):
        orch = _make_orchestrator()
        errors: list[Exception] = []

        def register(env_id: str, profile: str):
            try:
                orch.register_environment(env_id, profile)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register, args=(f"env_{i}", "dev-light"))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        envs = orch.list_environments()
        assert len(envs) == 20

    def test_concurrent_switches(self):
        orch = _make_orchestrator()
        # Register 10 environments
        for i in range(10):
            orch.register_environment(f"env_{i}", "dev-light")

        errors: list[Exception] = []

        def switch(target: str):
            try:
                orch.switch_environment(target, f"approval-{target}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=switch, args=(f"env_{i}",))
            for i in range(1, 10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Exactly one should have won
        active = orch.get_active_environment()
        assert active is not None
        history = orch.get_switch_history()
        assert len(history) >= 1

    def test_concurrent_reads_and_writes(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", ["m1"])
        orch.register_environment("prod", "prod-strict", ["m1", "m2"])

        errors: list[Exception] = []

        def reader():
            try:
                for _ in range(50):
                    orch.list_environments()
                    orch.get_active_environment()
                    orch.get_environment_config("dev")
                    orch.compare_environments("dev", "prod")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                orch.switch_environment("prod", "approval-1")
                orch.switch_environment("dev", "approval-2")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# 11. Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_same_instance(self):
        orch1 = get_environment_orchestrator()
        orch2 = get_environment_orchestrator()
        assert orch1 is orch2

    def test_reset_clears_singleton(self):
        orch1 = get_environment_orchestrator()
        reset_environment_orchestrator()
        orch2 = get_environment_orchestrator()
        assert orch1 is not orch2

    def test_singleton_stores_data(self):
        orch = get_environment_orchestrator()
        orch.register_environment("dev", "dev-light")
        orch2 = get_environment_orchestrator()
        envs = orch2.list_environments()
        assert len(envs) == 1


# ---------------------------------------------------------------------------
# 12. Legacy deploy API (backward compatibility)
# ---------------------------------------------------------------------------

class TestLegacyDeploy:
    def test_deploy_without_registry_fails(self):
        orch = _make_orchestrator()
        result = orch.deploy(DeployRequest(module_id="m1", action=DeployAction.DEPLOY))
        assert result.status == "failed"

    def test_deploy_transitions_lifecycle(self):
        orch = _make_orchestrator()
        reg = _make_registry("m1", lifecycle="draft")
        orch.set_registry(reg)
        result = orch.deploy(DeployRequest(module_id="m1", action=DeployAction.DEPLOY))
        assert result.status == "success"
        mod = reg.get("m1")
        assert mod["lifecycle"] == "build"

    def test_get_status_with_registry(self):
        orch = _make_orchestrator()
        reg = _make_registry("m1", lifecycle="stable")
        orch.set_registry(reg)
        status = orch.get_status()
        assert len(status) == 1

    def test_get_status_without_registry(self):
        orch = _make_orchestrator()
        assert orch.get_status() == []


# ---------------------------------------------------------------------------
# 13. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_switch_history_persists(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light")
        orch.register_environment("test", "test-light")
        orch.register_environment("prod", "prod-strict")

        orch.switch_environment("test", "approval-1")
        orch.switch_environment("prod", "approval-2")
        orch.switch_environment("dev", "approval-3")

        history = orch.get_switch_history()
        assert len(history) == 3
        assert history[0]["to_env"] == "test"
        assert history[1]["to_env"] == "prod"
        assert history[2]["to_env"] == "dev"

    def test_config_with_nested_values(self):
        orch = _make_orchestrator()
        config = {
            "database": {"host": "localhost", "port": 5432},
            "features": ["a", "b", "c"],
        }
        orch.register_environment("dev", "dev-light", config=config)
        cfg = orch.get_environment_config("dev")
        assert cfg["config"]["database"]["host"] == "localhost"
        assert cfg["config"]["features"] == ["a", "b", "c"]

    def test_large_number_of_environments(self):
        orch = _make_orchestrator()
        for i in range(50):
            result = orch.register_environment(f"env_{i:03d}", "dev-light", [f"m_{i}"])
            assert result["registered"] is True
        envs = orch.list_environments()
        assert len(envs) == 50

    def test_compare_environments_both_missing(self):
        orch = _make_orchestrator()
        result = orch.compare_environments("a", "b")
        assert result["comparable"] is False
        assert "not found" in result["message"]

    def test_validate_empty_modules_is_valid(self):
        orch = _make_orchestrator()
        orch.register_environment("dev", "dev-light", [])
        result = orch.validate_environment("dev")
        assert result["valid"] is True
        assert result["healthy_modules"] == []

    def test_all_four_profiles_registered(self):
        orch = _make_orchestrator()
        for profile_name in ("dev-light", "test-light", "staging-strict", "prod-strict"):
            env_id = profile_name.replace("-", "_")
            result = orch.register_environment(env_id, profile_name)
            assert result["registered"] is True
            cfg = orch.get_environment_config(env_id)
            assert cfg["security"]["auth_mode"] == PROFILES[profile_name].auth_mode
