"""Tests for sylion.security.security_profiles -- SecurityProfilesManager.

Covers: profile CRUD, rule management, evaluation, stats,
EventBus integration, concurrency, singleton, and edge cases.
~40 tests.
"""

import threading

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.security_profiles import (
    VALID_LEVELS,
    VALID_RULE_TYPES,
    SecurityProfilesManager,
    get_security_profiles,
    reset_security_profiles,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(event_bus: EventBus | None = None) -> SecurityProfilesManager:
    return SecurityProfilesManager(db_path=":memory:", event_bus=event_bus)


def _make_profile(mgr: SecurityProfilesManager, name: str = "test-profile",
                  level: str = "medium") -> dict:
    return mgr.create_profile(name, level, f"Description for {name}")


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    def test_valid_levels(self):
        assert "low" in VALID_LEVELS
        assert "medium" in VALID_LEVELS
        assert "high" in VALID_LEVELS
        assert "critical" in VALID_LEVELS
        assert len(VALID_LEVELS) == 4

    def test_valid_rule_types(self):
        expected = {"allow", "deny", "require", "transform"}
        assert set(VALID_RULE_TYPES) == expected


# ===========================================================================
# 2. Profile CRUD
# ===========================================================================


class TestCreateProfile:
    def test_basic_create(self):
        mgr = _make_manager()
        p = mgr.create_profile("web", "high", "Web security profile")
        assert p["profile_id"] != ""
        assert p["name"] == "web"
        assert p["level"] == "high"
        assert p["description"] == "Web security profile"
        assert p["is_active"] == 1
        assert p["created_at"] > 0

    def test_default_level_is_medium(self):
        mgr = _make_manager()
        p = mgr.create_profile("default")
        assert p["level"] == "medium"

    def test_default_description_empty(self):
        mgr = _make_manager()
        p = mgr.create_profile("empty-desc")
        assert p["description"] == ""

    def test_rejects_invalid_level(self):
        mgr = _make_manager()
        with pytest.raises(ValueError, match="Invalid level"):
            mgr.create_profile("bad", level="ultra")

    def test_all_valid_levels_accepted(self):
        mgr = _make_manager()
        for level in VALID_LEVELS:
            p = mgr.create_profile(f"prof-{level}", level=level)
            assert p["level"] == level

    def test_with_rules_json(self):
        mgr = _make_manager()
        rules = [{"name": "r1", "type": "allow"}]
        p = mgr.create_profile("rules-test", rules_json=rules)
        assert p["rules_json"] == rules

    def test_rules_json_default_empty_list(self):
        mgr = _make_manager()
        p = mgr.create_profile("no-rules")
        assert p["rules_json"] == []


class TestGetProfile:
    def test_get_existing(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        fetched = mgr.get_profile(p["profile_id"])
        assert fetched is not None
        assert fetched["name"] == "test-profile"

    def test_get_nonexistent(self):
        mgr = _make_manager()
        assert mgr.get_profile("no-such-id") is None


class TestListProfiles:
    def test_list_all(self):
        mgr = _make_manager()
        _make_profile(mgr, "alpha", "low")
        _make_profile(mgr, "beta", "high")
        assert len(mgr.list_profiles()) == 2

    def test_filter_by_level(self):
        mgr = _make_manager()
        _make_profile(mgr, "alpha", "low")
        _make_profile(mgr, "beta", "high")
        result = mgr.list_profiles(level="high")
        assert len(result) == 1
        assert result[0]["name"] == "beta"

    def test_empty_list(self):
        mgr = _make_manager()
        assert mgr.list_profiles() == []

    def test_excludes_deleted(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.delete_profile(p["profile_id"])
        assert len(mgr.list_profiles()) == 0


class TestUpdateProfile:
    def test_update_name(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        updated = mgr.update_profile(p["profile_id"], name="new-name")
        assert updated["name"] == "new-name"

    def test_update_level(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        updated = mgr.update_profile(p["profile_id"], level="critical")
        assert updated["level"] == "critical"

    def test_update_description(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        updated = mgr.update_profile(p["profile_id"], description="new desc")
        assert updated["description"] == "new desc"

    def test_update_multiple_fields(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        updated = mgr.update_profile(
            p["profile_id"], name="x", level="high", description="d",
        )
        assert updated["name"] == "x"
        assert updated["level"] == "high"
        assert updated["description"] == "d"

    def test_update_nonexistent_returns_none(self):
        mgr = _make_manager()
        assert mgr.update_profile("nope", name="x") is None

    def test_update_rejects_invalid_level(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        with pytest.raises(ValueError, match="Invalid level"):
            mgr.update_profile(p["profile_id"], level="invalid")

    def test_update_no_fields_returns_profile(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        result = mgr.update_profile(p["profile_id"])
        assert result is not None
        assert result["profile_id"] == p["profile_id"]


class TestDeleteProfile:
    def test_delete_existing(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        assert mgr.delete_profile(p["profile_id"]) is True

    def test_delete_nonexistent(self):
        mgr = _make_manager()
        assert mgr.delete_profile("nope") is False

    def test_delete_twice(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.delete_profile(p["profile_id"])
        assert mgr.delete_profile(p["profile_id"]) is False


# ===========================================================================
# 3. Rules
# ===========================================================================


class TestAddRule:
    def test_basic_add(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        rule = mgr.add_rule(p["profile_id"], "no-admin", "deny",
                            {"keys": ["admin"]})
        assert rule["rule_id"] != ""
        assert rule["rule_name"] == "no-admin"
        assert rule["rule_type"] == "deny"
        assert rule["config_json"] == {"keys": ["admin"]}

    def test_rejects_invalid_rule_type(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        with pytest.raises(ValueError, match="Invalid rule_type"):
            mgr.add_rule(p["profile_id"], "bad-rule", "invalid_type")

    def test_rejects_nonexistent_profile(self):
        mgr = _make_manager()
        with pytest.raises(ValueError, match="does not exist"):
            mgr.add_rule("no-profile", "rule", "allow")

    def test_all_rule_types_accepted(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        for rt in VALID_RULE_TYPES:
            rule = mgr.add_rule(p["profile_id"], f"rule-{rt}", rt)
            assert rule["rule_type"] == rt

    def test_default_config_empty(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        rule = mgr.add_rule(p["profile_id"], "plain", "allow")
        assert rule["config_json"] == {}


class TestRemoveRule:
    def test_remove_existing(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        rule = mgr.add_rule(p["profile_id"], "r1", "allow")
        assert mgr.remove_rule(rule["rule_id"]) is True

    def test_remove_nonexistent(self):
        mgr = _make_manager()
        assert mgr.remove_rule("no-rule") is False

    def test_remove_twice(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        rule = mgr.add_rule(p["profile_id"], "r1", "allow")
        mgr.remove_rule(rule["rule_id"])
        assert mgr.remove_rule(rule["rule_id"]) is False


class TestGetRules:
    def test_empty_rules(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        assert mgr.get_rules(p["profile_id"]) == []

    def test_multiple_rules(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.add_rule(p["profile_id"], "r1", "deny", {"keys": ["a"]})
        mgr.add_rule(p["profile_id"], "r2", "require", {"keys": ["b"]})
        rules = mgr.get_rules(p["profile_id"])
        assert len(rules) == 2

    def test_config_json_parsed(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.add_rule(p["profile_id"], "r1", "deny", {"keys": ["x", "y"]})
        rules = mgr.get_rules(p["profile_id"])
        assert rules[0]["config_json"] == {"keys": ["x", "y"]}


# ===========================================================================
# 4. Evaluation
# ===========================================================================


class TestEvaluateProfile:
    def test_compliant_no_rules(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        result = mgr.evaluate_profile(p["profile_id"], {"user": "alice"})
        assert result["compliant"] is True
        assert result["violations"] == []
        assert result["total_rules"] == 0

    def test_deny_rule_violation(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.add_rule(p["profile_id"], "deny-admin", "deny",
                     {"keys": ["admin"]})
        result = mgr.evaluate_profile(p["profile_id"], {"admin": True})
        assert result["compliant"] is False
        assert len(result["violations"]) == 1
        assert "admin" in result["violations"][0]["reason"]

    def test_deny_rule_pass(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.add_rule(p["profile_id"], "deny-admin", "deny",
                     {"keys": ["admin"]})
        result = mgr.evaluate_profile(p["profile_id"], {"user": "alice"})
        assert result["compliant"] is True

    def test_require_rule_violation(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.add_rule(p["profile_id"], "req-token", "require",
                     {"keys": ["token"]})
        result = mgr.evaluate_profile(p["profile_id"], {"user": "alice"})
        assert result["compliant"] is False
        assert len(result["violations"]) == 1
        assert "token" in result["violations"][0]["reason"]

    def test_require_rule_pass(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.add_rule(p["profile_id"], "req-token", "require",
                     {"keys": ["token"]})
        result = mgr.evaluate_profile(
            p["profile_id"], {"token": "abc123"},
        )
        assert result["compliant"] is True

    def test_nonexistent_profile_raises(self):
        mgr = _make_manager()
        with pytest.raises(ValueError, match="does not exist"):
            mgr.evaluate_profile("no-profile")

    def test_empty_context(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.add_rule(p["profile_id"], "req-x", "require", {"keys": ["x"]})
        result = mgr.evaluate_profile(p["profile_id"])
        assert result["compliant"] is False

    def test_result_has_profile_info(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        result = mgr.evaluate_profile(p["profile_id"])
        assert result["profile_name"] == "test-profile"
        assert result["level"] == "medium"
        assert result["evaluated_at"] > 0


# ===========================================================================
# 5. Stats
# ===========================================================================


class TestGetProfileStats:
    def test_empty_stats(self):
        mgr = _make_manager()
        stats = mgr.get_profile_stats()
        assert stats["total_profiles"] == 0
        assert stats["active_profiles"] == 0
        assert stats["total_rules"] == 0
        assert stats["by_level"] == {}

    def test_with_profiles(self):
        mgr = _make_manager()
        _make_profile(mgr, "a", "low")
        _make_profile(mgr, "b", "high")
        stats = mgr.get_profile_stats()
        assert stats["total_profiles"] == 2
        assert stats["active_profiles"] == 2
        assert stats["by_level"]["low"] == 1
        assert stats["by_level"]["high"] == 1

    def test_with_rules(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        mgr.add_rule(p["profile_id"], "r1", "allow")
        mgr.add_rule(p["profile_id"], "r2", "deny")
        stats = mgr.get_profile_stats()
        assert stats["total_rules"] == 2


# ===========================================================================
# 6. EventBus integration
# ===========================================================================


class TestEventBusIntegration:
    def test_profile_created_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("profile_created", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        mgr.create_profile("event-test", "high")
        assert len(collected) == 1
        assert collected[0].payload["name"] == "event-test"

    def test_profile_updated_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("profile_updated", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        p = mgr.create_profile("up-test", "medium")
        mgr.update_profile(p["profile_id"], name="renamed")
        assert len(collected) == 1

    def test_profile_evaluated_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("profile_evaluated", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        p = mgr.create_profile("eval-test")
        mgr.evaluate_profile(p["profile_id"])
        assert len(collected) == 1
        assert "compliant" in collected[0].payload

    def test_no_event_without_bus(self):
        mgr = _make_manager(event_bus=None)
        mgr.create_profile("no-bus")
        # Should not raise


# ===========================================================================
# 7. Singleton
# ===========================================================================


class TestSingleton:
    def test_get_security_profiles(self):
        import sylion.security.security_profiles as mod
        mod._manager = None
        mgr = get_security_profiles(db_path=":memory:")
        assert isinstance(mgr, SecurityProfilesManager)
        mod._manager = None

    def test_reset_security_profiles(self):
        import sylion.security.security_profiles as mod
        mod._manager = None
        mgr1 = get_security_profiles(db_path=":memory:")
        mgr2 = reset_security_profiles(db_path=":memory:")
        assert mgr2 is not mgr1
        mod._manager = None

    def test_get_returns_same_instance(self):
        import sylion.security.security_profiles as mod
        mod._manager = None
        mgr1 = get_security_profiles(db_path=":memory:")
        mgr2 = get_security_profiles()
        assert mgr1 is mgr2
        mod._manager = None


# ===========================================================================
# 8. Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_profile_creation(self):
        mgr = _make_manager()
        results = []
        errors = []

        def create(i):
            try:
                p = mgr.create_profile(f"profile-{i}", "medium")
                results.append(p["profile_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_read_write(self):
        mgr = _make_manager()
        p = _make_profile(mgr)
        errors = []

        def read_loop():
            try:
                for _ in range(20):
                    mgr.get_profile(p["profile_id"])
            except Exception as e:
                errors.append(e)

        def write_loop():
            try:
                for i in range(20):
                    mgr.add_rule(p["profile_id"], f"rule-{i}", "allow")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=read_loop),
            threading.Thread(target=read_loop),
            threading.Thread(target=write_loop),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(mgr.get_rules(p["profile_id"])) == 20
