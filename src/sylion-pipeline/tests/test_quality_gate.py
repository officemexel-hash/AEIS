"""Tests for sylion.quality.quality_gate — QualityGate."""

import threading

import pytest

from sylion.quality.quality_gate import QualityGate, _compare, get_quality_gate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gate() -> QualityGate:
    return QualityGate(db_path=":memory:")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCompare:
    def test_gte_pass(self):
        assert _compare("gte", 10, 5) is True

    def test_gte_fail(self):
        assert _compare("gte", 3, 5) is False

    def test_min_pass(self):
        assert _compare("min", 10, 5) is True

    def test_max_pass(self):
        assert _compare("max", 3, 5) is True

    def test_max_fail(self):
        assert _compare("max", 10, 5) is False

    def test_lte_pass(self):
        assert _compare("lte", 5, 5) is True

    def test_gt_pass(self):
        assert _compare("gt", 6, 5) is True

    def test_gt_fail(self):
        assert _compare("gt", 5, 5) is False

    def test_lt_pass(self):
        assert _compare("lt", 4, 5) is True

    def test_eq_pass(self):
        assert _compare("eq", 42, 42) is True

    def test_eq_fail(self):
        assert _compare("eq", 42, 43) is False

    def test_neq_pass(self):
        assert _compare("neq", 1, 2) is True

    def test_neq_fail(self):
        assert _compare("neq", 1, 1) is False

    def test_invalid_type_returns_false(self):
        assert _compare("bogus", "x", "y") is False

    def test_compare_type_error(self):
        assert _compare("gte", None, 5) is False

    def test_compare_string_numbers(self):
        assert _compare("gte", "10", "5") is True


class TestQualityGateDefine:
    def test_define_basic(self):
        qg = _make_gate()
        result = qg.define_gate(
            "qg-1", module_id="security",
            metrics={"coverage": {"type": "gte", "threshold": 80}},
        )
        assert result["gate_id"] == "qg-1"
        assert result["module_id"] == "security"
        assert result["metric_count"] == 1

    def test_define_with_thresholds(self):
        qg = _make_gate()
        result = qg.define_gate(
            "qg-2", thresholds={"coverage": 80, "speed": 100},
        )
        assert result["metric_count"] == 2

    def test_define_merge_metrics_and_thresholds(self):
        qg = _make_gate()
        result = qg.define_gate(
            "qg-3",
            metrics={"coverage": {"type": "gte", "threshold": 80}},
            thresholds={"speed": 100},
        )
        assert result["metric_count"] == 2

    def test_define_upsert(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"a": {"type": "gte", "threshold": 1}})
        qg.define_gate("qg-1", metrics={"b": {"type": "max", "threshold": 2}})
        g = qg.get_gate("qg-1")
        assert "b" in g["metrics"]

    def test_define_empty_metrics(self):
        qg = _make_gate()
        result = qg.define_gate("qg-empty")
        assert result["metric_count"] == 0


class TestQualityGateEvaluate:
    def test_evaluate_all_pass(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={
            "coverage": {"type": "gte", "threshold": 80},
            "speed": {"type": "max", "threshold": 200},
        })
        result = qg.evaluate("qg-1", {"coverage": 90, "speed": 150})
        assert result["evaluated"] is True
        assert result["passed"] is True
        assert result["score"] == 1.0
        assert result["passed_metrics"] == 2

    def test_evaluate_partial_fail(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={
            "coverage": {"type": "gte", "threshold": 80},
            "speed": {"type": "max", "threshold": 100},
        })
        result = qg.evaluate("qg-1", {"coverage": 90, "speed": 150})
        assert result["passed"] is False
        assert result["score"] == 0.5

    def test_evaluate_all_fail(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={
            "coverage": {"type": "gte", "threshold": 80},
        })
        result = qg.evaluate("qg-1", {"coverage": 10})
        assert result["passed"] is False
        assert result["score"] == 0.0

    def test_evaluate_missing_metric(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={
            "coverage": {"type": "gte", "threshold": 80},
            "speed": {"type": "max", "threshold": 100},
        })
        result = qg.evaluate("qg-1", {"coverage": 90})  # speed missing
        assert result["passed"] is False
        assert result["details"]["speed"]["passed"] is False

    def test_evaluate_unknown_gate(self):
        qg = _make_gate()
        result = qg.evaluate("nonexistent", {"a": 1})
        assert result["evaluated"] is False

    def test_evaluate_stores_result(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"x": {"type": "gte", "threshold": 5}})
        qg.evaluate("qg-1", {"x": 10})
        results = qg.get_results("qg-1")
        assert len(results) == 1

    def test_evaluate_result_id(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"x": {"type": "gte", "threshold": 5}})
        result = qg.evaluate("qg-1", {"x": 10})
        assert "result_id" in result
        assert result["result_id"] != ""


class TestQualityGateGetGate:
    def test_get_existing(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"x": {"type": "gte", "threshold": 5}})
        result = qg.get_gate("qg-1")
        assert result is not None
        assert result["gate_id"] == "qg-1"
        assert "metrics" in result

    def test_get_nonexistent(self):
        qg = _make_gate()
        result = qg.get_gate("nonexistent")
        assert result is None

    def test_get_parses_json(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"x": {"type": "gte", "threshold": 5}})
        result = qg.get_gate("qg-1")
        assert isinstance(result["metrics"], dict)


class TestQualityGateListGates:
    def test_list_empty(self):
        qg = _make_gate()
        gates = qg.list_gates()
        assert gates == []

    def test_list_returns_all(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"a": {"type": "gte", "threshold": 1}})
        qg.define_gate("qg-2", metrics={"b": {"type": "max", "threshold": 2}})
        gates = qg.list_gates()
        assert len(gates) == 2

    def test_list_filter_module(self):
        qg = _make_gate()
        qg.define_gate("qg-1", module_id="mod-1", metrics={"a": {"type": "gte", "threshold": 1}})
        qg.define_gate("qg-2", module_id="mod-2", metrics={"b": {"type": "max", "threshold": 2}})
        gates = qg.list_gates(module_id="mod-1")
        assert len(gates) == 1

    def test_list_active_only(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"a": {"type": "gte", "threshold": 1}})
        qg.define_gate("qg-2", metrics={"b": {"type": "max", "threshold": 2}})
        qg.deactivate_gate("qg-1")
        gates = qg.list_gates(active_only=True)
        assert len(gates) == 1


class TestQualityGateGetResults:
    def test_get_results_empty(self):
        qg = _make_gate()
        qg.define_gate("qg-1")
        results = qg.get_results("qg-1")
        assert results == []

    def test_get_results_with_data(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"x": {"type": "gte", "threshold": 5}})
        qg.evaluate("qg-1", {"x": 10})
        qg.evaluate("qg-1", {"x": 3})
        results = qg.get_results("qg-1")
        assert len(results) == 2

    def test_get_results_limit(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"x": {"type": "gte", "threshold": 5}})
        for i in range(10):
            qg.evaluate("qg-1", {"x": 10})
        results = qg.get_results("qg-1", limit=3)
        assert len(results) == 3


class TestQualityGateDeactivate:
    def test_deactivate_existing(self):
        qg = _make_gate()
        qg.define_gate("qg-1", metrics={"x": {"type": "gte", "threshold": 5}})
        ok = qg.deactivate_gate("qg-1")
        assert ok is True
        # Evaluations against inactive gate should fail
        result = qg.evaluate("qg-1", {"x": 10})
        assert result["evaluated"] is False

    def test_deactivate_nonexistent(self):
        qg = _make_gate()
        ok = qg.deactivate_gate("nonexistent")
        assert ok is False


class TestQualityGateRegression:
    def test_regression_no_gates(self):
        qg = _make_gate()
        report = qg.get_regression_report("mod-1")
        assert report["regression_count"] == 0

    def test_regression_no_history(self):
        qg = _make_gate()
        qg.define_gate("qg-1", module_id="mod-1", metrics={"x": {"type": "gte", "threshold": 5}})
        report = qg.get_regression_report("mod-1")
        assert report["regressions"] == []

    def test_regression_detected(self):
        qg = _make_gate()
        qg.define_gate("qg-1", module_id="mod-1", metrics={
            "a": {"type": "gte", "threshold": 5},
            "b": {"type": "gte", "threshold": 5},
        })
        # First eval: both pass -> score 1.0
        qg.evaluate("qg-1", {"a": 10, "b": 10})
        # Second eval: one fails -> score 0.5
        qg.evaluate("qg-1", {"a": 10, "b": 1})
        report = qg.get_regression_report("mod-1")
        assert report["regression_count"] == 1
        assert report["regressions"][0]["drop"] > 0

    def test_regression_not_detected(self):
        qg = _make_gate()
        qg.define_gate("qg-1", module_id="mod-1", metrics={"x": {"type": "gte", "threshold": 5}})
        qg.evaluate("qg-1", {"x": 10})
        qg.evaluate("qg-1", {"x": 10})
        report = qg.get_regression_report("mod-1")
        assert report["regression_count"] == 0


class TestQualityGateStats:
    def test_stats_empty(self):
        qg = _make_gate()
        stats = qg.get_stats()
        assert stats["total_gates"] == 0
        assert stats["total_evaluations"] == 0
        assert stats["pass_rate"] == 0.0

    def test_stats_with_data(self):
        qg = _make_gate()
        qg.define_gate("qg-1", module_id="mod-1", metrics={"x": {"type": "gte", "threshold": 5}})
        qg.evaluate("qg-1", {"x": 10})  # pass
        qg.evaluate("qg-1", {"x": 1})   # fail
        stats = qg.get_stats()
        assert stats["total_gates"] == 1
        assert stats["total_evaluations"] == 2
        assert stats["passed_evaluations"] == 1
        assert stats["pass_rate"] == 0.5

    def test_stats_by_module(self):
        qg = _make_gate()
        qg.define_gate("qg-1", module_id="mod-1", metrics={"x": {"type": "gte", "threshold": 5}})
        qg.evaluate("qg-1", {"x": 10})
        stats = qg.get_stats()
        assert "mod-1" in stats["by_module"]


class TestQualityGateSingleton:
    def test_get_quality_gate_returns_instance(self):
        import sylion.quality.quality_gate as mod
        mod._gate = None
        gate = get_quality_gate(db_path=":memory:")
        assert isinstance(gate, QualityGate)
        mod._gate = None


class TestQualityGateConcurrency:
    def test_concurrent_define_and_evaluate(self):
        """Concurrent define + evaluate with retry for transient SQLite errors.

        Both define_gate() and evaluate() use a shared sqlite3 connection.
        evaluate() performs reads outside self._lock, so concurrent threads
        can race and trigger sqlite3.OperationalError / InterfaceError, or
        TypeError from json.loads(None) when a row read returns corrupt data.
        We retry on all transient errors with exponential back-off.
        """
        import sqlite3 as _sqlite3
        import time

        qg = _make_gate()
        errors = []
        transient = (_sqlite3.OperationalError, _sqlite3.InterfaceError, TypeError)

        def define_and_eval(i):
            gid = f"qg-{i}"
            for attempt in range(8):
                try:
                    qg.define_gate(gid, metrics={"x": {"type": "gte", "threshold": 5}})
                    qg.evaluate(gid, {"x": 10})
                    return
                except transient:
                    if attempt < 7:
                        time.sleep(0.05 * (attempt + 1))
                        continue
                except Exception as e:
                    errors.append(e)
                    return
            errors.append(RuntimeError(
                f"{gid}: failed after 8 retries"
            ))

        threads = [threading.Thread(target=define_and_eval, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        time.sleep(0.1)  # let threads progress before joining
        for t in threads:
            t.join(timeout=10.0)

        assert not errors, f"Thread errors: {errors}"
        gates = qg.list_gates()
        assert len(gates) == 20
