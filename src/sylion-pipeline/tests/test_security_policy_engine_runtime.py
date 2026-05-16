"""Focused tests for sylion.security.policy_engine fail-closed evaluation."""

import json

from sylion.core.event_bus import EventBus
from sylion.security.policy_engine import PolicyEngine


def test_rule_based_policy_passes_with_matching_context():
    engine = PolicyEngine(db_path=":memory:")
    engine.create_policy(
        "access-pass",
        "Access Pass",
        rules=[
            {"field": "role", "operator": "in", "value": ["admin", "ops"]},
            {"field": "failed_logins", "operator": "lte", "value": 2},
        ],
    )

    result = engine.evaluate(
        "access-pass",
        "api/admin",
        {"role": "admin", "failed_logins": 1},
    )

    assert result["result"] == "pass"
    assert result["details"]["violation_count"] == 0


def test_rule_based_policy_fails_when_context_violates_rules():
    bus = EventBus(db_path=":memory:")
    engine = PolicyEngine(db_path=":memory:", event_bus=bus)
    engine.create_policy(
        "access-fail",
        "Access Fail",
        severity="critical",
        rules=[{"field": "role", "operator": "eq", "value": "admin"}],
    )

    result = engine.evaluate("access-fail", "api/admin", {"role": "guest"})

    assert result["result"] == "fail"
    assert result["details"]["violation_count"] == 1
    violations = bus.query(topic="security.policy.violation")
    assert len(violations) == 1
    payload = json.loads(violations[0]["payload"])
    assert payload["policy_id"] == "access-fail"


def test_inferred_rule_shapes_are_machine_evaluated():
    engine = PolicyEngine(db_path=":memory:")
    engine.create_policy(
        "cfg-baseline",
        "Config Baseline",
        policy_type="config",
        rules=[
            {"rule": "max_connections", "value": 100},
            {"rule": "timeout_seconds", "value": 30},
            {"rule": "drift_detection", "enabled": True},
            {"rule": "notify_admin", "channel": "slack"},
        ],
    )

    result = engine.evaluate(
        "cfg-baseline",
        "server_config",
        {
            "max_connections": 100,
            "timeout_seconds": 30,
            "drift_detection": True,
            "channel": "slack",
        },
    )

    assert result["result"] == "pass"
    assert result["details"]["passed_rules"] == 4


def test_missing_context_fails_closed_for_machine_evaluable_rules():
    engine = PolicyEngine(db_path=":memory:")
    engine.create_policy(
        "cfg-missing",
        "Config Missing",
        rules=[{"rule": "timeout_seconds", "value": 30}],
    )

    result = engine.evaluate("cfg-missing", "server_config")

    assert result["result"] == "fail"
    assert result["details"]["violation_count"] == 1


def test_empty_policy_passes_without_fake_rule_results():
    engine = PolicyEngine(db_path=":memory:")
    engine.create_policy("empty", "Empty", rules=[])

    result = engine.evaluate("empty", "api/health")

    assert result["result"] == "pass"
    assert result["details"]["total_rules"] == 0


def test_missing_policy_returns_error():
    engine = PolicyEngine(db_path=":memory:")

    result = engine.evaluate("ghost", "api/ghost")

    assert result["result"] == "error"
    assert result["details"]["reason"] == "policy_not_found"


def test_disabled_policy_blocks_evaluation():
    engine = PolicyEngine(db_path=":memory:")
    engine.create_policy("disabled", "Disabled", rules=[{"field": "role", "operator": "eq", "value": "admin"}])
    engine.disable_policy("disabled")

    result = engine.evaluate("disabled", "api/admin", {"role": "admin"})

    assert result["result"] == "blocked"
    assert result["details"]["reason"] == "policy_disabled"
