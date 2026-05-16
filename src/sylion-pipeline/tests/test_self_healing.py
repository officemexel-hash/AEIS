"""
Tests for sylion.monitoring.self_healing -- SelfHealingEngine

~40 tests covering rule CRUD, incident reporting, auto-heal evaluation,
incident listing/filtering, manual resolution, statistics, EventBus
emissions, condition matching, concurrency, and singleton lifecycle.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.monitoring.self_healing import (
    SelfHealingEngine,
    get_self_healing,
    reset_self_healing,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_self_healing()
    yield
    reset_self_healing()


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
def engine(bus):
    return SelfHealingEngine(event_bus=bus)


@pytest.fixture
def plain_engine():
    return SelfHealingEngine()


# ===========================================================================
# 1. Create rules
# ===========================================================================

class TestCreateRule:
    def test_returns_rule_id(self, engine):
        r = engine.create_rule("restart-rule",
                               {"metric": "error_rate", "operator": ">=",
                                "threshold": 0.5},
                               {"type": "restart"})
        assert isinstance(r["rule_id"], str) and len(r["rule_id"]) > 0

    def test_returns_name(self, engine):
        r = engine.create_rule("my-rule", {"metric": "x", "operator": ">=",
                                           "threshold": 1},
                               {"type": "alert"})
        assert r["name"] == "my-rule"

    def test_returns_condition_json(self, engine):
        cond = {"metric": "cpu", "operator": ">=", "threshold": 90}
        r = engine.create_rule("r", cond, {"type": "alert"})
        assert r["condition_json"] == cond

    def test_returns_action_json(self, engine):
        act = {"type": "restart", "module": "api"}
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, act)
        assert r["action_json"] == act

    def test_default_priority_zero(self, engine):
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, {"type": "alert"})
        assert r["priority"] == 0

    def test_custom_priority(self, engine):
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1},
                               {"type": "alert"}, priority=10)
        assert r["priority"] == 10

    def test_enabled_true(self, engine):
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, {"type": "alert"})
        assert r["enabled"] is True

    def test_empty_name_raises(self, engine):
        with pytest.raises(ValueError, match="name must not be empty"):
            engine.create_rule("", {"metric": "x", "operator": ">=",
                                    "threshold": 1}, {"type": "alert"})

    def test_emits_rule_created(self, engine, bus):
        engine.create_rule("r", {"metric": "x", "operator": ">=",
                                  "threshold": 1}, {"type": "alert"})
        topics = [e.topic for e in bus._captured]
        assert "rule_created" in topics


# ===========================================================================
# 2. Update rules
# ===========================================================================

class TestUpdateRule:
    def test_update_name(self, engine):
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, {"type": "alert"})
        updated = engine.update_rule(r["rule_id"], name="new-name")
        assert updated["name"] == "new-name"

    def test_update_condition(self, engine):
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, {"type": "alert"})
        new_cond = {"metric": "y", "operator": "<", "threshold": 5}
        updated = engine.update_rule(r["rule_id"], condition_json=new_cond)
        assert updated["condition_json"] == new_cond

    def test_update_action(self, engine):
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, {"type": "alert"})
        new_act = {"type": "restart", "module": "api"}
        updated = engine.update_rule(r["rule_id"], action_json=new_act)
        assert updated["action_json"] == new_act

    def test_update_priority(self, engine):
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, {"type": "alert"})
        updated = engine.update_rule(r["rule_id"], priority=99)
        assert updated["priority"] == 99

    def test_update_nonexistent_returns_none(self, engine):
        assert engine.update_rule("nonexistent", name="x") is None


# ===========================================================================
# 3. Delete rules
# ===========================================================================

class TestDeleteRule:
    def test_delete_existing(self, engine):
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, {"type": "alert"})
        assert engine.delete_rule(r["rule_id"]) is True

    def test_delete_nonexistent(self, engine):
        assert engine.delete_rule("nonexistent") is False

    def test_delete_removes_from_list(self, engine):
        r = engine.create_rule("r", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, {"type": "alert"})
        engine.delete_rule(r["rule_id"])
        rules = engine.list_rules()
        assert all(rule["rule_id"] != r["rule_id"] for rule in rules)


# ===========================================================================
# 4. List rules
# ===========================================================================

class TestListRules:
    def test_empty_list(self, plain_engine):
        assert plain_engine.list_rules() == []

    def test_lists_all(self, engine):
        engine.create_rule("r1", {"metric": "x", "operator": ">=",
                                   "threshold": 1}, {"type": "alert"})
        engine.create_rule("r2", {"metric": "y", "operator": ">=",
                                   "threshold": 2}, {"type": "restart"})
        assert len(engine.list_rules()) == 2

    def test_filter_by_priority(self, engine):
        engine.create_rule("r1", {"metric": "x", "operator": ">=",
                                   "threshold": 1}, {"type": "alert"},
                           priority=5)
        engine.create_rule("r2", {"metric": "y", "operator": ">=",
                                   "threshold": 2}, {"type": "restart"},
                           priority=10)
        result = engine.list_rules(priority=5)
        assert len(result) == 1
        assert result[0]["priority"] == 5

    def test_ordered_by_priority_desc(self, engine):
        engine.create_rule("low", {"metric": "x", "operator": ">=",
                                    "threshold": 1}, {"type": "alert"},
                           priority=1)
        engine.create_rule("high", {"metric": "x", "operator": ">=",
                                     "threshold": 1}, {"type": "restart"},
                           priority=10)
        rules = engine.list_rules()
        assert rules[0]["name"] == "high"
        assert rules[1]["name"] == "low"

    def test_parses_json_fields(self, engine):
        cond = {"metric": "cpu", "operator": ">=", "threshold": 90}
        act = {"type": "throttle", "factor": 0.5}
        engine.create_rule("r", cond, act)
        rules = engine.list_rules()
        assert rules[0]["condition_json"] == cond
        assert rules[0]["action_json"] == act


# ===========================================================================
# 5. Report incidents
# ===========================================================================

class TestReportIncident:
    def test_returns_incident_id(self, engine):
        r = engine.report_incident("monitor", "error_rate", 0.8)
        assert isinstance(r["incident_id"], str) and len(r["incident_id"]) > 0

    def test_returns_source(self, engine):
        r = engine.report_incident("api-server", "error_rate", 0.8)
        assert r["source"] == "api-server"

    def test_returns_metric(self, engine):
        r = engine.report_incident("s", "latency_ms", 500.0)
        assert r["metric"] == "latency_ms"

    def test_returns_value(self, engine):
        r = engine.report_incident("s", "latency_ms", 500.0)
        assert r["value"] == 500.0

    def test_returns_severity(self, engine):
        r = engine.report_incident("s", "m", 1.0, severity="high")
        assert r["severity"] == "high"

    def test_default_severity_medium(self, engine):
        r = engine.report_incident("s", "m", 1.0)
        assert r["severity"] == "medium"

    def test_invalid_severity_raises(self, engine):
        with pytest.raises(ValueError, match="Invalid severity"):
            engine.report_incident("s", "m", 1.0, severity="extreme")

    def test_no_matching_rule_auto_resolved_false(self, engine):
        r = engine.report_incident("s", "unknown_metric", 999.0)
        assert r["auto_resolved"] is False
        assert r["auto_actions"] == []

    def test_matching_rule_auto_resolved(self, engine):
        engine.create_rule("restart-on-high-error",
                           {"metric": "error_rate", "operator": ">=",
                            "threshold": 0.5},
                           {"type": "restart"})
        r = engine.report_incident("monitor", "error_rate", 0.8)
        assert r["auto_resolved"] is True
        assert len(r["auto_actions"]) == 1

    def test_matching_rule_action_has_type(self, engine):
        engine.create_rule("r", {"metric": "error_rate", "operator": ">=",
                                  "threshold": 0.5},
                           {"type": "restart", "module": "api"})
        r = engine.report_incident("s", "error_rate", 0.8)
        assert r["auto_actions"][0]["action_type"] == "restart"
        assert r["auto_actions"][0]["success"] is True

    def test_priority_ordering_first_match_wins(self, engine):
        engine.create_rule("low-priority",
                           {"metric": "error_rate", "operator": ">=",
                            "threshold": 0.5},
                           {"type": "alert"}, priority=1)
        engine.create_rule("high-priority",
                           {"metric": "error_rate", "operator": ">=",
                            "threshold": 0.5},
                           {"type": "restart"}, priority=10)
        r = engine.report_incident("s", "error_rate", 0.8)
        assert r["auto_resolved"] is True
        assert len(r["auto_actions"]) == 1
        assert r["auto_actions"][0]["action_type"] == "restart"

    def test_emits_incident_reported(self, engine, bus):
        engine.report_incident("s", "m", 1.0)
        topics = [e.topic for e in bus._captured]
        assert "incident_reported" in topics

    def test_auto_resolve_emits_events(self, engine, bus):
        engine.create_rule("r", {"metric": "error_rate", "operator": ">=",
                                  "threshold": 0.5},
                           {"type": "restart"})
        engine.report_incident("s", "error_rate", 0.8)
        topics = [e.topic for e in bus._captured]
        assert "auto_heal_triggered" in topics
        assert "incident_resolved" in topics


# ===========================================================================
# 6. Condition matching
# ===========================================================================

class TestConditionMatching:
    def test_gt_operator(self, engine):
        engine.create_rule("r", {"metric": "latency", "operator": ">",
                                  "threshold": 100},
                           {"type": "alert"})
        r = engine.report_incident("s", "latency", 150.0)
        assert r["auto_resolved"] is True

    def test_lt_operator(self, engine):
        engine.create_rule("r", {"metric": "health", "operator": "<",
                                  "threshold": 50},
                           {"type": "alert"})
        r = engine.report_incident("s", "health", 30.0)
        assert r["auto_resolved"] is True

    def test_lte_operator(self, engine):
        engine.create_rule("r", {"metric": "errors", "operator": "<=",
                                  "threshold": 0},
                           {"type": "alert"})
        r = engine.report_incident("s", "errors", 0.0)
        assert r["auto_resolved"] is True

    def test_eq_operator(self, engine):
        engine.create_rule("r", {"metric": "status", "operator": "==",
                                  "threshold": 0},
                           {"type": "alert"})
        r = engine.report_incident("s", "status", 0.0)
        assert r["auto_resolved"] is True

    def test_neq_operator(self, engine):
        engine.create_rule("r", {"metric": "status", "operator": "!=",
                                  "threshold": 200},
                           {"type": "alert"})
        r = engine.report_incident("s", "status", 404.0)
        assert r["auto_resolved"] is True

    def test_wrong_metric_no_match(self, engine):
        engine.create_rule("r", {"metric": "cpu", "operator": ">=",
                                  "threshold": 90},
                           {"type": "alert"})
        r = engine.report_incident("s", "memory", 95.0)
        assert r["auto_resolved"] is False

    def test_value_below_threshold_no_match(self, engine):
        engine.create_rule("r", {"metric": "error_rate", "operator": ">=",
                                  "threshold": 0.5},
                           {"type": "alert"})
        r = engine.report_incident("s", "error_rate", 0.3)
        assert r["auto_resolved"] is False


# ===========================================================================
# 7. Get incident
# ===========================================================================

class TestGetIncident:
    def test_get_existing(self, engine):
        r = engine.report_incident("s", "m", 1.0)
        inc = engine.get_incident(r["incident_id"])
        assert inc is not None
        assert inc["incident_id"] == r["incident_id"]

    def test_get_nonexistent(self, engine):
        assert engine.get_incident("nonexistent") is None

    def test_auto_resolved_status(self, engine):
        engine.create_rule("r", {"metric": "error_rate", "operator": ">=",
                                  "threshold": 0.5},
                           {"type": "restart"})
        r = engine.report_incident("s", "error_rate", 0.8)
        inc = engine.get_incident(r["incident_id"])
        assert inc["status"] == "auto_resolved"


# ===========================================================================
# 8. List incidents
# ===========================================================================

class TestListIncidents:
    def test_empty_list(self, plain_engine):
        assert plain_engine.list_incidents() == []

    def test_lists_all(self, engine):
        engine.report_incident("s1", "m1", 1.0)
        engine.report_incident("s2", "m2", 2.0)
        assert len(engine.list_incidents()) == 2

    def test_filter_by_status(self, engine):
        engine.create_rule("r", {"metric": "error_rate", "operator": ">=",
                                  "threshold": 0.5},
                           {"type": "restart"})
        engine.report_incident("s", "error_rate", 0.8)
        engine.report_incident("s", "other_metric", 1.0)
        resolved = engine.list_incidents(status="auto_resolved")
        assert len(resolved) == 1
        assert resolved[0]["status"] == "auto_resolved"

    def test_filter_by_severity(self, engine):
        engine.report_incident("s", "m1", 1.0, severity="high")
        engine.report_incident("s", "m2", 2.0, severity="low")
        result = engine.list_incidents(severity="high")
        assert len(result) == 1
        assert result[0]["severity"] == "high"

    def test_combined_filters(self, engine):
        engine.report_incident("s", "m1", 1.0, severity="high")
        engine.report_incident("s", "m2", 2.0, severity="low")
        result = engine.list_incidents(status="open", severity="high")
        assert len(result) == 1


# ===========================================================================
# 9. Resolve incident
# ===========================================================================

class TestResolveIncident:
    def test_resolve_updates_status(self, engine):
        r = engine.report_incident("s", "m", 1.0)
        resolved = engine.resolve_incident(r["incident_id"],
                                           "fixed by admin")
        assert resolved["status"] == "resolved"
        assert resolved["resolution"] == "fixed by admin"
        assert resolved["resolved_at"] is not None

    def test_resolve_nonexistent_returns_none(self, engine):
        assert engine.resolve_incident("nonexistent", "x") is None

    def test_resolve_emits_event(self, engine, bus):
        r = engine.report_incident("s", "m", 1.0)
        bus._captured.clear()
        engine.resolve_incident(r["incident_id"], "manual fix")
        topics = [e.topic for e in bus._captured]
        assert "incident_resolved" in topics


# ===========================================================================
# 10. Healing stats
# ===========================================================================

class TestGetHealingStats:
    def test_empty_stats(self, plain_engine):
        stats = plain_engine.get_healing_stats()
        assert stats["total_rules"] == 0
        assert stats["total_incidents"] == 0
        assert stats["total_healing_actions"] == 0
        assert stats["auto_resolved_count"] == 0
        assert stats["open_count"] == 0

    def test_counts_rules(self, engine):
        engine.create_rule("r1", {"metric": "x", "operator": ">=",
                                   "threshold": 1}, {"type": "alert"})
        engine.create_rule("r2", {"metric": "y", "operator": ">=",
                                   "threshold": 1}, {"type": "restart"})
        stats = engine.get_healing_stats()
        assert stats["total_rules"] == 2
        assert stats["enabled_rules"] == 2

    def test_counts_incidents(self, engine):
        engine.report_incident("s", "m1", 1.0)
        engine.report_incident("s", "m2", 2.0)
        stats = engine.get_healing_stats()
        assert stats["total_incidents"] == 2

    def test_by_status_breakdown(self, engine):
        engine.create_rule("r", {"metric": "m1", "operator": ">=",
                                  "threshold": 0.5},
                           {"type": "restart"})
        engine.report_incident("s", "m1", 0.8)
        engine.report_incident("s", "m2", 1.0)
        stats = engine.get_healing_stats()
        assert stats["incidents_by_status"]["auto_resolved"] == 1
        assert stats["incidents_by_status"]["open"] == 1

    def test_by_severity_breakdown(self, engine):
        engine.report_incident("s", "m", 1.0, severity="high")
        engine.report_incident("s", "m", 2.0, severity="low")
        stats = engine.get_healing_stats()
        assert stats["incidents_by_severity"]["high"] == 1
        assert stats["incidents_by_severity"]["low"] == 1

    def test_auto_resolved_count(self, engine):
        engine.create_rule("r", {"metric": "m", "operator": ">=",
                                  "threshold": 0.5},
                           {"type": "restart"})
        engine.report_incident("s", "m", 0.8)
        stats = engine.get_healing_stats()
        assert stats["auto_resolved_count"] == 1

    def test_counts_healing_actions(self, engine):
        engine.create_rule("r", {"metric": "m", "operator": ">=",
                                  "threshold": 0.5},
                           {"type": "restart"})
        engine.report_incident("s", "m", 0.8)
        stats = engine.get_healing_stats()
        assert stats["total_healing_actions"] == 1


# ===========================================================================
# 11. Concurrency
# ===========================================================================

class TestConcurrency:
    def test_concurrent_incident_reporting(self, plain_engine):
        plain_engine.create_rule("r", {"metric": "error_rate",
                                        "operator": ">=",
                                        "threshold": 0.5},
                                 {"type": "alert"})
        errors = []

        def worker(i):
            try:
                plain_engine.report_incident(
                    f"source-{i}", "error_rate", float(i) * 0.2)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(plain_engine.list_incidents()) == 10


# ===========================================================================
# 12. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        inst = get_self_healing()
        assert isinstance(inst, SelfHealingEngine)

    def test_get_is_idempotent(self):
        a = get_self_healing()
        b = get_self_healing()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_self_healing()
        reset_self_healing()
        b = get_self_healing()
        assert a is not b

    def test_double_reset_safe(self):
        reset_self_healing()
        reset_self_healing()
        inst = get_self_healing()
        assert isinstance(inst, SelfHealingEngine)
