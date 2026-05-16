"""Tests for sylion.governance.policy_registry — PolicyRegistry."""

import json
import threading
import time

import pytest

from sylion.governance.policy_registry import PolicyRegistry, get_policy_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry() -> PolicyRegistry:
    return PolicyRegistry(db_path=":memory:")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPolicyRegistryRegister:
    def test_register_basic(self):
        reg = _make_registry()
        result = reg.register("pol-1", "No Deploy Friday", description="Block deploys on Friday")
        assert result["policy_id"] == "pol-1"
        assert result["name"] == "No Deploy Friday"
        assert result["enabled"] == 1

    def test_register_with_category(self):
        reg = _make_registry()
        result = reg.register("pol-2", "Test Policy", category="security")
        assert result["category"] == "security"

    def test_register_with_rules(self):
        reg = _make_registry()
        rules = [{"field": "action", "operator": "neq", "value": "deploy"}]
        result = reg.register("pol-3", "Rule Policy", rules=rules)
        assert result["rules"] == rules

    def test_register_with_enforcement(self):
        reg = _make_registry()
        result = reg.register("pol-4", "Strict Policy", enforcement="strict")
        assert result["enforcement"] == "strict"

    def test_register_upsert(self):
        reg = _make_registry()
        reg.register("pol-1", "First Version")
        reg.register("pol-1", "Second Version")
        result = reg.get("pol-1")
        assert result["name"] == "Second Version"

    def test_register_default_category(self):
        reg = _make_registry()
        result = reg.register("pol-5", "Default Cat")
        assert result["category"] == "governance"

    def test_register_default_enforcement(self):
        reg = _make_registry()
        result = reg.register("pol-6", "Default Enf")
        assert result["enforcement"] == "advisory"


class TestPolicyRegistryGet:
    def test_get_existing(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        result = reg.get("pol-1")
        assert result is not None
        assert result["policy_id"] == "pol-1"
        assert result["name"] == "Test"

    def test_get_nonexistent(self):
        reg = _make_registry()
        result = reg.get("nonexistent")
        assert result is None

    def test_get_parses_rules_json(self):
        reg = _make_registry()
        rules = [{"field": "env", "value": "prod"}]
        reg.register("pol-1", "Rules", rules=rules)
        result = reg.get("pol-1")
        assert isinstance(result["rules"], list)
        assert result["rules"][0]["field"] == "env"


class TestPolicyRegistryList:
    def test_list_empty(self):
        reg = _make_registry()
        policies = reg.list_policies()
        assert policies == []

    def test_list_returns_all_enabled(self):
        reg = _make_registry()
        reg.register("p1", "A")
        reg.register("p2", "B")
        policies = reg.list_policies()
        assert len(policies) == 2

    def test_list_filter_category(self):
        reg = _make_registry()
        reg.register("p1", "A", category="security")
        reg.register("p2", "B", category="governance")
        policies = reg.list_policies(category="security")
        assert len(policies) == 1

    def test_list_filter_enforcement(self):
        reg = _make_registry()
        reg.register("p1", "A", enforcement="strict")
        reg.register("p2", "B", enforcement="advisory")
        policies = reg.list_policies(enforcement="strict")
        assert len(policies) == 1

    def test_list_disabled_not_shown_by_default(self):
        reg = _make_registry()
        reg.register("p1", "A")
        reg.disable("p1")
        policies = reg.list_policies(enabled_only=True)
        assert len(policies) == 0

    def test_list_includes_disabled(self):
        reg = _make_registry()
        reg.register("p1", "A")
        reg.disable("p1")
        policies = reg.list_policies(enabled_only=False)
        assert len(policies) == 1


class TestPolicyRegistryUpdate:
    def test_update_rules(self):
        reg = _make_registry()
        reg.register("pol-1", "Test", rules=[{"a": 1}])
        result = reg.update_policy("pol-1", rules=[{"b": 2}])
        assert result is not None
        assert result["rules"] == [{"b": 2}]
        assert result["version"] == 2

    def test_update_enforcement(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        result = reg.update_policy("pol-1", enforcement="strict")
        assert result["enforcement"] == "strict"

    def test_update_nonexistent(self):
        reg = _make_registry()
        result = reg.update_policy("nonexistent", rules=[])
        assert result is None

    def test_update_increments_version(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        reg.update_policy("pol-1", rules=[{"x": 1}])
        result = reg.update_policy("pol-1", rules=[{"y": 2}])
        assert result["version"] == 3


class TestPolicyRegistryEnableDisable:
    def test_disable(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        result = reg.disable("pol-1")
        assert result is not None
        assert result["enabled"] == 0

    def test_enable(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        reg.disable("pol-1")
        result = reg.enable("pol-1")
        assert result is not None
        assert result["enabled"] == 1

    def test_disable_nonexistent(self):
        reg = _make_registry()
        result = reg.disable("nonexistent")
        assert result is None

    def test_enable_nonexistent(self):
        reg = _make_registry()
        result = reg.enable("nonexistent")
        assert result is None


class TestPolicyRegistryApply:
    def test_apply_basic(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        result = reg.apply("pol-1", "module", "mod-1", result="applied", applied_by="admin")
        assert result["policy_id"] == "pol-1"
        assert result["target_type"] == "module"
        assert result["target_id"] == "mod-1"
        assert result["result"] == "applied"
        assert "application_id" in result

    def test_apply_with_result(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        result = reg.apply("pol-1", "module", "m1", result="rejected")
        assert result["result"] == "rejected"

    def test_get_applications(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        reg.apply("pol-1", "module", "m1")
        reg.apply("pol-1", "module", "m2")
        apps = reg.get_applications("pol-1")
        assert len(apps) == 2

    def test_get_applications_empty(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        apps = reg.get_applications("pol-1")
        assert apps == []

    def test_get_applications_limit(self):
        reg = _make_registry()
        reg.register("pol-1", "Test")
        for i in range(10):
            reg.apply("pol-1", "module", f"m-{i}")
        apps = reg.get_applications("pol-1", limit=3)
        assert len(apps) == 3


class TestPolicyRegistrySingleton:
    def test_get_policy_registry_returns_instance(self):
        import sylion.governance.policy_registry as mod
        mod._registry = None
        reg = get_policy_registry(db_path=":memory:")
        assert isinstance(reg, PolicyRegistry)
        mod._registry = None


class TestPolicyRegistryConcurrency:
    def test_concurrent_register_and_apply(self):
        reg = _make_registry()
        reg.register("pol-1", "Concurrent Test")
        errors = []

        def apply_policy(i):
            try:
                reg.apply("pol-1", "module", f"m-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=apply_policy, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        apps = reg.get_applications("pol-1")
        assert len(apps) == 20
