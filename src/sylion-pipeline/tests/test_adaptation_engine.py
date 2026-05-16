"""Tests for aeis.adaptation_engine module."""

import pytest
from sylion.aeis.adaptation_engine import AdaptationEngine, VALID_ADAPTATION_TYPES


@pytest.fixture
def engine():
    return AdaptationEngine()


def test_create_adaptation(engine):
    result = engine.create_adaptation(
        adaptation_type="threshold_adjust",
        trigger_metric="cpu_usage",
        trigger_value=0.95,
        target_value=0.80,
        strategy="reduce_load",
    )
    assert result["adaptation_type"] == "threshold_adjust"
    assert result["trigger_metric"] == "cpu_usage"
    assert result["state"] == "PENDING"
    assert "adaptation_id" in result


def test_create_invalid_type(engine):
    with pytest.raises(ValueError, match="Invalid adaptation type"):
        engine.create_adaptation(adaptation_type="invalid_type", trigger_metric="x")


def test_get_adaptation(engine):
    created = engine.create_adaptation(
        adaptation_type="parameter_tune", trigger_metric="latency"
    )
    adapt = engine.get(created["adaptation_id"])
    assert adapt is not None
    assert adapt["adaptation_type"] == "parameter_tune"
    assert adapt["affected_modules"] == []


def test_get_not_found(engine):
    assert engine.get("nonexistent") is None


def test_apply_adaptation(engine):
    created = engine.create_adaptation(
        adaptation_type="threshold_adjust", trigger_metric="cpu_usage"
    )
    result = engine.apply(created["adaptation_id"], outcome="Load reduced")
    assert result["state"] == "ACTIVE"

    adapt = engine.get(created["adaptation_id"])
    assert adapt["state"] == "ACTIVE"
    assert adapt["outcome"] == "Load reduced"


def test_apply_wrong_state(engine):
    created = engine.create_adaptation(
        adaptation_type="threshold_adjust", trigger_metric="cpu"
    )
    engine.apply(created["adaptation_id"])
    with pytest.raises(ValueError, match="Can only apply PENDING"):
        engine.apply(created["adaptation_id"])


def test_complete_adaptation(engine):
    created = engine.create_adaptation(
        adaptation_type="threshold_adjust", trigger_metric="cpu"
    )
    engine.apply(created["adaptation_id"])
    result = engine.complete(created["adaptation_id"], outcome="Successful")
    assert result["state"] == "COMPLETED"


def test_complete_wrong_state(engine):
    created = engine.create_adaptation(
        adaptation_type="threshold_adjust", trigger_metric="cpu"
    )
    with pytest.raises(ValueError, match="Can only complete ACTIVE"):
        engine.complete(created["adaptation_id"])


def test_fail_adaptation(engine):
    created = engine.create_adaptation(
        adaptation_type="threshold_adjust", trigger_metric="cpu"
    )
    result = engine.fail(created["adaptation_id"], reason="Timeout")
    assert result["state"] == "FAILED"


def test_full_lifecycle(engine):
    created = engine.create_adaptation(
        adaptation_type="resource_rebalance",
        trigger_metric="memory",
        trigger_value=0.90,
        target_value=0.70,
    )
    engine.apply(created["adaptation_id"])
    engine.complete(created["adaptation_id"])
    adapt = engine.get(created["adaptation_id"])
    assert adapt["state"] == "COMPLETED"


def test_ingest_feedback(engine):
    result = engine.ingest_feedback(
        source="monitor",
        metric="cpu_usage",
        value=0.95,
        threshold=0.80,
        severity="warning",
    )
    assert result["metric"] == "cpu_usage"
    assert result["value"] == 0.95
    assert "signal_id" in result


def test_feedback_triggers_rule(engine):
    engine.add_rule(
        name="High CPU",
        trigger_metric="cpu_usage",
        condition_op=">",
        threshold=0.90,
        adaptation_type="resource_rebalance",
        strategy="scale_out",
    )

    result = engine.ingest_feedback(
        source="monitor", metric="cpu_usage", value=0.95, threshold=0.90
    )
    assert result["triggered_adaptations"] == 1
    assert len(result["adaptation_ids"]) == 1


def test_feedback_no_trigger(engine):
    engine.add_rule(
        name="High CPU",
        trigger_metric="cpu_usage",
        condition_op=">",
        threshold=0.90,
        adaptation_type="resource_rebalance",
    )

    result = engine.ingest_feedback(
        source="monitor", metric="cpu_usage", value=0.50
    )
    assert result["triggered_adaptations"] == 0


def test_rule_condition_ops(engine):
    # Test < operator
    engine.add_rule("Low Mem", "memory_free", condition_op="<", threshold=0.10,
                    adaptation_type="resource_rebalance")
    result = engine.ingest_feedback("mon", "memory_free", value=0.05)
    assert result["triggered_adaptations"] == 1

    # Test >= operator
    engine2 = AdaptationEngine()
    engine2.add_rule("High Lat", "latency", condition_op=">=", threshold=100.0,
                     adaptation_type="parameter_tune")
    result2 = engine2.ingest_feedback("mon", "latency", value=100.0)
    assert result2["triggered_adaptations"] == 1


def test_add_rule(engine):
    result = engine.add_rule(
        name="High CPU",
        trigger_metric="cpu_usage",
        condition_op=">",
        threshold=0.90,
        adaptation_type="threshold_adjust",
    )
    assert "rule_id" in result
    assert result["name"] == "High CPU"


def test_list_rules(engine):
    engine.add_rule("Rule 1", "cpu", threshold=0.9, adaptation_type="threshold_adjust")
    engine.add_rule("Rule 2", "mem", threshold=0.1, adaptation_type="resource_rebalance")

    rules = engine.list_rules()
    assert len(rules) == 2

    # enabled_only
    rules_enabled = engine.list_rules(enabled_only=True)
    assert len(rules_enabled) == 2


def test_list_adaptations(engine):
    engine.create_adaptation("threshold_adjust", "cpu")
    engine.create_adaptation("parameter_tune", "latency")
    engine.create_adaptation("threshold_adjust", "memory")

    all_adapt = engine.list_adaptations()
    assert len(all_adapt) == 3

    filtered = engine.list_adaptations(adaptation_type="threshold_adjust")
    assert len(filtered) == 2


def test_get_feedback(engine):
    engine.ingest_feedback("mon", "cpu", value=0.9)
    engine.ingest_feedback("mon", "mem", value=0.5)
    engine.ingest_feedback("mon", "cpu", value=0.8)

    all_fb = engine.get_feedback()
    assert len(all_fb) == 3

    cpu_fb = engine.get_feedback(metric="cpu")
    assert len(cpu_fb) == 2


def test_stats(engine):
    engine.create_adaptation("threshold_adjust", "cpu")
    engine.create_adaptation("parameter_tune", "latency")
    engine.ingest_feedback("mon", "cpu", value=0.9)

    stats = engine.get_stats()
    assert stats["total_adaptations"] == 2
    assert stats["total_feedback_signals"] == 1
    assert stats["by_state"]["PENDING"] == 2
    assert stats["by_type"]["threshold_adjust"] == 1
