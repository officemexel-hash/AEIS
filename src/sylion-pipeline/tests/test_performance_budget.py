"""Tests for SYLION Efficiency -- Performance Budget Manager."""
import threading

import pytest

from sylion.core.event_bus import EventBus
from sylion.efficiency.performance_budget import (
    CLASS_DEFAULTS,
    PerformanceBudget,
    PerformanceBudgetManager,
    get_performance_budget_manager,
    _defaults_for_class,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh EventBus for each test."""
    return EventBus()


@pytest.fixture
def mgr(bus):
    """Fresh PerformanceBudgetManager for each test."""
    return PerformanceBudgetManager(event_bus=bus)


# ===========================================================================
# 1. Data model tests
# ===========================================================================

class TestPerformanceBudgetDataclass:
    def test_default_values(self):
        b = PerformanceBudget(module_id="mod_a")
        assert b.module_id == "mod_a"
        assert b.max_code_lines == 500
        assert b.max_runtime_ms == 100.0
        assert b.max_memory_mb == 50.0
        assert b.max_cost_per_call == 0.01
        assert b.created_at > 0
        assert b.updated_at > 0

    def test_custom_values(self):
        b = PerformanceBudget(
            module_id="mod_b",
            max_code_lines=200,
            max_runtime_ms=30.0,
            max_memory_mb=10.0,
            max_cost_per_call=0.005,
        )
        assert b.max_code_lines == 200
        assert b.max_runtime_ms == 30.0
        assert b.max_memory_mb == 10.0
        assert b.max_cost_per_call == 0.005


# ===========================================================================
# 2. Class defaults
# ===========================================================================

class TestClassDefaults:
    def test_core_class_a(self):
        d = _defaults_for_class("A")
        assert d["max_code_lines"] == 500
        assert d["max_runtime_ms"] == 50.0
        assert d["max_memory_mb"] == 20.0

    def test_standard_class_b(self):
        d = _defaults_for_class("B")
        assert d["max_code_lines"] == 300
        assert d["max_runtime_ms"] == 100.0
        assert d["max_memory_mb"] == 50.0

    def test_device_class_m(self):
        d = _defaults_for_class("M")
        assert d["max_code_lines"] == 400
        assert d["max_runtime_ms"] == 200.0
        assert d["max_memory_mb"] == 100.0

    def test_unknown_class_falls_back_to_standard(self):
        d = _defaults_for_class("Z")
        assert d["max_code_lines"] == 300
        assert d["max_runtime_ms"] == 100.0

    def test_case_insensitive(self):
        assert _defaults_for_class("a") == _defaults_for_class("A")

    def test_all_standard_classes_share_same_defaults(self):
        for cls in "BCDEFGHI":
            assert _defaults_for_class(cls) == _defaults_for_class("B")

    def test_all_device_classes_share_same_defaults(self):
        for cls in "MNO":
            assert _defaults_for_class(cls) == _defaults_for_class("M")


# ===========================================================================
# 3. set_budget / get_budget
# ===========================================================================

class TestSetGetBudget:
    def test_set_budget_with_class_a_defaults(self, mgr):
        result = mgr.set_budget("core.kernel", module_class="A")
        assert result["module_class"] == "A"
        assert result["max_code_lines"] == 500
        assert result["max_runtime_ms"] == 50.0
        assert result["max_memory_mb"] == 20.0

    def test_set_budget_with_class_m_defaults(self, mgr):
        result = mgr.set_budget("dev.sensor", module_class="M")
        assert result["max_code_lines"] == 400
        assert result["max_runtime_ms"] == 200.0
        assert result["max_memory_mb"] == 100.0

    def test_set_budget_with_explicit_values(self, mgr):
        result = mgr.set_budget(
            "mod.custom", code_lines=100, runtime_ms=25.0,
            memory_mb=10.0, cost=0.005, module_class="A",
        )
        assert result["max_code_lines"] == 100
        assert result["max_runtime_ms"] == 25.0
        assert result["max_memory_mb"] == 10.0
        assert result["max_cost_per_call"] == 0.005

    def test_get_budget_returns_set_budget(self, mgr):
        mgr.set_budget("mod.getter", module_class="B")
        budget = mgr.get_budget("mod.getter")
        assert budget is not None
        assert budget["module_id"] == "mod.getter"
        assert budget["max_code_lines"] == 300

    def test_get_budget_nonexistent_returns_none(self, mgr):
        assert mgr.get_budget("no.such.module") is None

    def test_set_budget_upsert(self, mgr):
        mgr.set_budget("mod.upsert", code_lines=200, module_class="B")
        mgr.set_budget("mod.upsert", code_lines=500, runtime_ms=75.0, module_class="B")
        budget = mgr.get_budget("mod.upsert")
        assert budget["max_code_lines"] == 500
        assert budget["max_runtime_ms"] == 75.0

    def test_set_budget_default_class_when_none(self, mgr):
        result = mgr.set_budget("mod.noclass")
        assert result["module_class"] == "B"  # fallback


# ===========================================================================
# 4. check_budget
# ===========================================================================

class TestCheckBudget:
    def test_within_budget(self, mgr):
        mgr.set_budget("mod.ok", module_class="B")
        result = mgr.check_budget("mod.ok", actuals={
            "code_lines": 200,
            "runtime_ms": 50.0,
            "memory_mb": 30.0,
            "cost_per_call": 0.005,
        })
        assert result["within_budget"] is True
        assert result["violations"] == []

    def test_over_budget_code_lines(self, mgr):
        mgr.set_budget("mod.bloated", module_class="B")
        result = mgr.check_budget("mod.bloated", actuals={
            "code_lines": 400,
        })
        assert result["within_budget"] is False
        assert len(result["violations"]) == 1
        v = result["violations"][0]
        assert v["metric"] == "code_lines"
        assert v["dimension"] == "Code Bloat"
        assert v["actual"] == 400
        assert v["budget"] == 300

    def test_over_budget_runtime(self, mgr):
        mgr.set_budget("mod.slow", module_class="B")
        result = mgr.check_budget("mod.slow", actuals={
            "runtime_ms": 150.0,
        })
        assert result["within_budget"] is False
        assert result["violations"][0]["metric"] == "runtime_ms"
        assert result["violations"][0]["dimension"] == "Runtime Performance"

    def test_over_budget_memory(self, mgr):
        mgr.set_budget("mod.hungry", module_class="B")
        result = mgr.check_budget("mod.hungry", actuals={
            "memory_mb": 60.0,
        })
        assert result["within_budget"] is False
        assert result["violations"][0]["metric"] == "memory_mb"

    def test_over_budget_cost(self, mgr):
        mgr.set_budget("mod.expensive", module_class="B")
        result = mgr.check_budget("mod.expensive", actuals={
            "cost_per_call": 0.05,
        })
        assert result["within_budget"] is False
        assert result["violations"][0]["metric"] == "cost_per_call"

    def test_multiple_violations(self, mgr):
        mgr.set_budget("mod.terrible", module_class="A")
        result = mgr.check_budget("mod.terrible", actuals={
            "code_lines": 600,
            "runtime_ms": 80.0,
            "memory_mb": 30.0,
            "cost_per_call": 0.02,
        })
        assert result["within_budget"] is False
        assert len(result["violations"]) == 4

    def test_check_budget_no_budget_defined(self, mgr):
        result = mgr.check_budget("mod.nobudget", actuals={"code_lines": 9999})
        assert result["within_budget"] is True
        assert result["reason"] == "no_budget_defined"

    def test_check_budget_uses_db_measurements(self, mgr):
        mgr.set_budget("mod.dbcheck", module_class="B")
        mgr.record_measurement("mod.dbcheck", "code_lines", 250)
        result = mgr.check_budget("mod.dbcheck")
        assert result["within_budget"] is True
        assert result["actuals"]["code_lines"] == 250

    def test_check_budget_over_by_pct(self, mgr):
        mgr.set_budget("mod.pct", module_class="B")
        result = mgr.check_budget("mod.pct", actuals={"code_lines": 600})
        v = result["violations"][0]
        assert v["over_by"] == 300
        assert v["over_pct"] == pytest.approx(100.0)

    def test_exact_limit_is_within_budget(self, mgr):
        mgr.set_budget("mod.exact", module_class="B")
        result = mgr.check_budget("mod.exact", actuals={
            "code_lines": 300,
            "runtime_ms": 100.0,
            "memory_mb": 50.0,
            "cost_per_call": 0.01,
        })
        assert result["within_budget"] is True
        assert result["violations"] == []


# ===========================================================================
# 5. record_measurement / get_measurements
# ===========================================================================

class TestRecordMeasurement:
    def test_record_valid_metric(self, mgr):
        result = mgr.record_measurement("mod.m1", "code_lines", 200)
        assert result["module_id"] == "mod.m1"
        assert result["metric"] == "code_lines"
        assert result["value"] == 200
        assert result["measurement_id"]

    def test_record_invalid_metric_raises(self, mgr):
        with pytest.raises(ValueError, match="Invalid metric"):
            mgr.record_measurement("mod.m2", "invalid_metric", 42)

    def test_get_measurements_returns_recorded(self, mgr):
        mgr.record_measurement("mod.m3", "code_lines", 100)
        mgr.record_measurement("mod.m3", "runtime_ms", 50.0)
        measurements = mgr.get_measurements("mod.m3")
        assert len(measurements) == 2

    def test_get_measurements_filter_by_metric(self, mgr):
        mgr.record_measurement("mod.m4", "code_lines", 100)
        mgr.record_measurement("mod.m4", "runtime_ms", 50.0)
        measurements = mgr.get_measurements("mod.m4", metric="code_lines")
        assert len(measurements) == 1
        assert measurements[0]["metric"] == "code_lines"

    def test_get_latest_actuals(self, mgr):
        mgr.record_measurement("mod.m5", "code_lines", 100)
        mgr.record_measurement("mod.m5", "runtime_ms", 75.0)
        mgr.record_measurement("mod.m5", "memory_mb", 30.0)
        actuals = mgr.get_latest_actuals("mod.m5")
        assert actuals["code_lines"] == 100
        assert actuals["runtime_ms"] == 75.0
        assert actuals["memory_mb"] == 30.0

    def test_latest_actuals_returns_latest_value(self, mgr):
        mgr.record_measurement("mod.m6", "code_lines", 100)
        mgr.record_measurement("mod.m6", "code_lines", 250)
        actuals = mgr.get_latest_actuals("mod.m6")
        assert actuals["code_lines"] == 250


# ===========================================================================
# 6. list_over_budget / list_budgets
# ===========================================================================

class TestListOperations:
    def test_list_over_budget_empty(self, mgr):
        assert mgr.list_over_budget() == []

    def test_list_over_budget_finds_violators(self, mgr):
        mgr.set_budget("mod.good", module_class="B")
        mgr.record_measurement("mod.good", "code_lines", 200)

        mgr.set_budget("mod.bad", module_class="B")
        mgr.record_measurement("mod.bad", "code_lines", 400)

        over = mgr.list_over_budget()
        assert len(over) == 1
        assert over[0]["module_id"] == "mod.bad"

    def test_list_budgets_all(self, mgr):
        mgr.set_budget("mod.a", module_class="A")
        mgr.set_budget("mod.b", module_class="B")
        mgr.set_budget("mod.m", module_class="M")
        budgets = mgr.list_budgets()
        assert len(budgets) == 3

    def test_list_budgets_filter_by_class(self, mgr):
        mgr.set_budget("mod.a", module_class="A")
        mgr.set_budget("mod.b", module_class="B")
        mgr.set_budget("mod.m", module_class="M")
        class_a = mgr.list_budgets(module_class="A")
        assert len(class_a) == 1
        assert class_a[0]["module_id"] == "mod.a"

    def test_remove_budget(self, mgr):
        mgr.set_budget("mod.del", module_class="B")
        assert mgr.get_budget("mod.del") is not None
        assert mgr.remove_budget("mod.del") is True
        assert mgr.get_budget("mod.del") is None

    def test_remove_nonexistent_budget(self, mgr):
        assert mgr.remove_budget("no.such.module") is False


# ===========================================================================
# 7. Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_set_budget(self, mgr):
        errors: list[Exception] = []

        def set_b(i):
            try:
                mgr.set_budget(f"mod.concurrent_{i}", module_class="B")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=set_b, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        budgets = mgr.list_budgets()
        assert len(budgets) == 20

    def test_concurrent_record_and_check(self, mgr):
        mgr.set_budget("mod.race", code_lines=100, runtime_ms=50.0,
                        memory_mb=50.0, cost=0.01, module_class="B")
        errors: list[Exception] = []

        def record(i):
            try:
                mgr.record_measurement("mod.race", "code_lines", 50 + i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        measurements = mgr.get_measurements("mod.race")
        assert len(measurements) == 20


# ===========================================================================
# 8. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_performance_budget_manager_returns_instance(self):
        # Reset singleton
        import sylion.efficiency.performance_budget as pb_mod
        pb_mod._manager = None
        m = get_performance_budget_manager()
        assert isinstance(m, PerformanceBudgetManager)
        assert m is get_performance_budget_manager()
        # Clean up
        pb_mod._manager = None


# ===========================================================================
# 9. Event emission
# ===========================================================================

class TestEventEmission:
    def test_set_budget_emits_event(self, bus, mgr):
        events = []
        bus.subscribe("efficiency.performance_budget.budget_set", events.append)
        mgr.set_budget("mod.ev1", module_class="A")
        assert len(events) == 1
        assert events[0].payload["module_id"] == "mod.ev1"

    def test_check_budget_emits_event(self, bus, mgr):
        events = []
        bus.subscribe("efficiency.performance_budget.budget_checked", events.append)
        mgr.set_budget("mod.ev2", module_class="B")
        mgr.check_budget("mod.ev2", actuals={"code_lines": 100})
        assert len(events) == 1

    def test_record_measurement_emits_event(self, bus, mgr):
        events = []
        bus.subscribe("efficiency.performance_budget.measurement_recorded", events.append)
        mgr.record_measurement("mod.ev3", "code_lines", 100)
        assert len(events) == 1
        assert events[0].payload["value"] == 100
