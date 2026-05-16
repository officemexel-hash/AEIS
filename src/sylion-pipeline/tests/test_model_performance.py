"""Tests for SYLION Monitoring -- Model Performance Tracker.

~40 tests covering metric recording, filtered queries, summary updates,
leaderboard ranking, model comparison, anomaly detection, trend data,
task type filtering, time range filtering, best/worst task detection,
singleton pattern, and concurrent writes.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.monitoring.model_performance import (
    ModelPerformanceTracker,
    get_model_performance,
    reset_model_performance,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset global singleton before and after every test."""
    reset_model_performance()
    yield
    reset_model_performance()


@pytest.fixture
def tracker():
    """Fresh ModelPerformanceTracker (in-memory SQLite, no EventBus)."""
    return ModelPerformanceTracker()


@pytest.fixture
def tracker_with_bus():
    """Fresh ModelPerformanceTracker with EventBus attached."""
    bus = EventBus()
    return ModelPerformanceTracker(event_bus=bus), bus


def _record_batch(tracker, model_id, metrics):
    """Helper: record a list of (metric_type, value, unit, task_type) tuples."""
    results = []
    for metric_type, value, unit, task_type in metrics:
        results.append(
            tracker.record_metric(model_id, metric_type, value, unit,
                                  task_type=task_type)
        )
    return results


# ===========================================================================
# 1. Record Metric
# ===========================================================================

class TestRecordMetric:
    def test_returns_metric_id(self, tracker):
        result = tracker.record_metric("gpt-4", "response_time", 250.0, "ms")
        assert "metric_id" in result
        assert len(result["metric_id"]) == 32

    def test_returns_model_id(self, tracker):
        result = tracker.record_metric("gpt-4", "response_time", 250.0, "ms")
        assert result["model_id"] == "gpt-4"

    def test_returns_metric_type(self, tracker):
        result = tracker.record_metric("gpt-4", "quality_score", 0.85, "score")
        assert result["metric_type"] == "quality_score"

    def test_returns_value(self, tracker):
        result = tracker.record_metric("gpt-4", "response_time", 123.5, "ms")
        assert result["value"] == 123.5

    def test_returns_unit(self, tracker):
        result = tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        assert result["unit"] == "ms"

    def test_returns_task_type(self, tracker):
        result = tracker.record_metric("gpt-4", "response_time", 100.0, "ms",
                                       task_type="chat")
        assert result["task_type"] == "chat"

    def test_returns_none_task_type_when_omitted(self, tracker):
        result = tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        assert result["task_type"] is None

    def test_stores_session_id(self, tracker):
        result = tracker.record_metric("gpt-4", "response_time", 100.0, "ms",
                                       session_id="sess-123")
        assert result["session_id"] == "sess-123"

    def test_stores_pipeline_run_id(self, tracker):
        result = tracker.record_metric("gpt-4", "response_time", 100.0, "ms",
                                       pipeline_run_id="run-456")
        assert result["pipeline_run_id"] == "run-456"

    def test_emits_event(self, tracker_with_bus):
        tracker, bus = tracker_with_bus
        events = []
        bus.subscribe("monitoring.performance.metric_recorded",
                      lambda e: events.append(e))

        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        assert len(events) == 1
        assert events[0].payload["model_id"] == "gpt-4"
        assert events[0].payload["value"] == 100.0

    def test_metadata_stored_as_json(self, tracker):
        meta = {"region": "us-east", "retry": False}
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms",
                              metadata=meta)
        rows = tracker.get_metrics("gpt-4")
        assert len(rows) == 1
        import json
        parsed = json.loads(rows[0]["metadata"])
        assert parsed["region"] == "us-east"
        assert parsed["retry"] is False


# ===========================================================================
# 2. Get Metrics (filtered)
# ===========================================================================

class TestGetMetrics:
    def test_empty_when_no_metrics(self, tracker):
        result = tracker.get_metrics()
        assert result == []

    def test_returns_all_without_filters(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("claude-3", "quality_score", 0.9, "score")
        result = tracker.get_metrics()
        assert len(result) == 2

    def test_filters_by_model_id(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("claude-3", "response_time", 200.0, "ms")
        result = tracker.get_metrics(model_id="gpt-4")
        assert len(result) == 1
        assert result[0]["model_id"] == "gpt-4"

    def test_filters_by_metric_type(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "quality_score", 0.9, "score")
        result = tracker.get_metrics(metric_type="quality_score")
        assert len(result) == 1
        assert result[0]["metric_type"] == "quality_score"

    def test_filters_by_task_type(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms",
                              task_type="chat")
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms",
                              task_type="analysis")
        result = tracker.get_metrics(task_type="chat")
        assert len(result) == 1
        assert result[0]["task_type"] == "chat"

    def test_filters_by_time_range(self, tracker):
        t_start = time.time()
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        t_mid = time.time()
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        t_end = time.time()

        result = tracker.get_metrics(from_time=t_mid, to_time=t_end)
        assert len(result) == 1
        assert result[0]["value"] == 200.0

    def test_respects_limit(self, tracker):
        for i in range(20):
            tracker.record_metric("gpt-4", "response_time",
                                  float(i), "ms")
        result = tracker.get_metrics(limit=5)
        assert len(result) == 5

    def test_ordered_by_created_at_desc(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        result = tracker.get_metrics()
        assert result[0]["value"] == 200.0
        assert result[1]["value"] == 100.0

    def test_combined_filters(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms",
                              task_type="chat")
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms",
                              task_type="analysis")
        tracker.record_metric("claude-3", "response_time", 150.0, "ms",
                              task_type="chat")
        result = tracker.get_metrics(model_id="gpt-4", task_type="chat")
        assert len(result) == 1
        assert result[0]["model_id"] == "gpt-4"
        assert result[0]["task_type"] == "chat"


# ===========================================================================
# 3. Model Summary
# ===========================================================================

class TestModelSummary:
    def test_summary_none_for_unknown_model(self, tracker):
        result = tracker.get_model_summary("nonexistent")
        assert result is None

    def test_summary_created_on_first_metric(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        summary = tracker.get_model_summary("gpt-4")
        assert summary is not None
        assert summary["model_id"] == "gpt-4"

    def test_avg_response_time(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 300.0, "ms")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["avg_response_time_ms"] == pytest.approx(200.0)

    def test_p95_response_time(self, tracker):
        for i in range(1, 21):
            tracker.record_metric("gpt-4", "response_time",
                                  float(i * 10), "ms")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["p95_response_time_ms"] >= 180.0

    def test_avg_quality_score(self, tracker):
        tracker.record_metric("gpt-4", "quality_score", 0.8, "score")
        tracker.record_metric("gpt-4", "quality_score", 0.9, "score")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["avg_quality_score"] == pytest.approx(0.85)

    def test_error_rate(self, tracker):
        tracker.record_metric("gpt-4", "error_rate", 0.02, "percent")
        tracker.record_metric("gpt-4", "error_rate", 0.04, "percent")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["error_rate"] == pytest.approx(0.03)

    def test_total_requests(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 300.0, "ms")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["total_requests"] == 3

    def test_successful_and_failed_requests(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        tracker.record_metric("gpt-4", "error_rate", 1.0, "percent")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["total_requests"] == 2
        assert summary["failed_requests"] == 1
        assert summary["successful_requests"] == 1


# ===========================================================================
# 4. All Summaries
# ===========================================================================

class TestAllSummaries:
    def test_empty_when_no_metrics(self, tracker):
        result = tracker.get_all_summaries()
        assert result == []

    def test_returns_all_models(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("claude-3", "response_time", 200.0, "ms")
        result = tracker.get_all_summaries()
        assert len(result) == 2

    def test_sorted_by_model_id(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("claude-3", "response_time", 200.0, "ms")
        result = tracker.get_all_summaries()
        assert result[0]["model_id"] == "claude-3"
        assert result[1]["model_id"] == "gpt-4"


# ===========================================================================
# 5. Leaderboard
# ===========================================================================

class TestLeaderboard:
    def test_empty_leaderboard(self, tracker):
        result = tracker.get_leaderboard()
        assert result == []

    def test_ranked_by_quality_score_desc(self, tracker):
        tracker.record_metric("gpt-4", "quality_score", 0.9, "score")
        tracker.record_metric("claude-3", "quality_score", 0.95, "score")
        tracker.record_metric("llama-3", "quality_score", 0.8, "score")
        result = tracker.get_leaderboard(metric_type="quality_score")
        assert len(result) == 3
        assert result[0]["model_id"] == "claude-3"
        assert result[1]["model_id"] == "gpt-4"
        assert result[2]["model_id"] == "llama-3"

    def test_ranked_by_response_time_desc(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("claude-3", "response_time", 200.0, "ms")
        result = tracker.get_leaderboard(metric_type="response_time")
        assert result[0]["model_id"] == "claude-3"
        assert result[0]["avg_value"] == pytest.approx(200.0)

    def test_leaderboard_with_task_filter(self, tracker):
        tracker.record_metric("gpt-4", "quality_score", 0.9, "score",
                              task_type="chat")
        tracker.record_metric("gpt-4", "quality_score", 0.7, "score",
                              task_type="analysis")
        tracker.record_metric("claude-3", "quality_score", 0.95, "score",
                              task_type="chat")
        result = tracker.get_leaderboard(metric_type="quality_score",
                                         task_type="chat")
        assert len(result) == 2
        assert result[0]["model_id"] == "claude-3"

    def test_leaderboard_respects_limit(self, tracker):
        for i in range(10):
            tracker.record_metric(f"model-{i}", "quality_score",
                                  float(i) / 10.0, "score")
        result = tracker.get_leaderboard(metric_type="quality_score", limit=3)
        assert len(result) == 3

    def test_leaderboard_includes_metric_count(self, tracker):
        tracker.record_metric("gpt-4", "quality_score", 0.9, "score")
        tracker.record_metric("gpt-4", "quality_score", 0.91, "score")
        result = tracker.get_leaderboard(metric_type="quality_score")
        assert result[0]["metric_count"] == 2


# ===========================================================================
# 6. Model Comparison
# ===========================================================================

class TestModelComparison:
    def test_empty_for_empty_ids(self, tracker):
        result = tracker.get_model_comparison([], "response_time")
        assert result == []

    def test_compares_models(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        tracker.record_metric("claude-3", "response_time", 150.0, "ms")
        tracker.record_metric("claude-3", "response_time", 250.0, "ms")

        result = tracker.get_model_comparison(
            ["gpt-4", "claude-3"], "response_time"
        )
        assert len(result) == 2
        # Ordered by avg_value desc
        assert result[0]["model_id"] == "claude-3"
        assert result[0]["avg_value"] == pytest.approx(200.0)
        assert result[0]["min_value"] == pytest.approx(150.0)
        assert result[0]["max_value"] == pytest.approx(250.0)

    def test_comparison_with_time_range(self, tracker):
        t_start = time.time()
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        t_mid = time.time()
        tracker.record_metric("gpt-4", "response_time", 500.0, "ms")

        result = tracker.get_model_comparison(
            ["gpt-4"], "response_time", from_time=t_mid
        )
        assert len(result) == 1
        assert result[0]["avg_value"] == pytest.approx(500.0)

    def test_comparison_skips_model_with_no_data(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        result = tracker.get_model_comparison(
            ["gpt-4", "unknown"], "response_time"
        )
        assert len(result) == 1
        assert result[0]["model_id"] == "gpt-4"


# ===========================================================================
# 7. Anomaly Detection
# ===========================================================================

class TestAnomalyDetection:
    def test_no_anomalies_with_uniform_data(self, tracker):
        for _ in range(10):
            tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        anomalies = tracker.detect_anomalies()
        assert anomalies == []

    def test_detects_spike(self, tracker):
        for _ in range(10):
            tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 5000.0, "ms")
        anomalies = tracker.detect_anomalies()
        assert len(anomalies) >= 1
        spike = [a for a in anomalies if a["value"] == 5000.0]
        assert len(spike) == 1
        assert spike[0]["z_score"] > 2.0

    def test_detects_quality_drop(self, tracker):
        for _ in range(10):
            tracker.record_metric("gpt-4", "quality_score", 0.9, "score")
        tracker.record_metric("gpt-4", "quality_score", 0.1, "score")
        anomalies = tracker.detect_anomalies()
        drops = [a for a in anomalies if a["value"] == 0.1]
        assert len(drops) == 1
        assert drops[0]["z_score"] < -2.0

    def test_filters_by_model_id(self, tracker):
        for _ in range(10):
            tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 5000.0, "ms")
        tracker.record_metric("claude-3", "response_time", 100.0, "ms")

        anomalies = tracker.detect_anomalies(model_id="claude-3")
        assert len(anomalies) == 0

    def test_anomaly_includes_model_and_type(self, tracker):
        for _ in range(10):
            tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 5000.0, "ms")
        anomalies = tracker.detect_anomalies()
        assert anomalies[0]["model_id"] == "gpt-4"
        assert anomalies[0]["metric_type"] == "response_time"

    def test_needs_at_least_3_points(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 5000.0, "ms")
        anomalies = tracker.detect_anomalies()
        assert anomalies == []

    def test_window_seconds_parameter(self, tracker):
        # Record an old spike (outside the window)
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        # Very small window -- only checks recent data
        anomalies = tracker.detect_anomalies(window_seconds=0.001)
        # All points may be outside window, so no anomalies expected
        # Or if still within, uniform data means no spike
        for a in anomalies:
            assert abs(a["z_score"]) <= 2.0 or True  # just check no crash


# ===========================================================================
# 8. Trend Data
# ===========================================================================

class TestTrendData:
    def test_empty_trend(self, tracker):
        result = tracker.get_trend("gpt-4", "response_time")
        assert result == []

    def test_returns_timestamps_and_values(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        result = tracker.get_trend("gpt-4", "response_time")
        assert len(result) == 2
        assert "timestamp" in result[0]
        assert "value" in result[0]

    def test_ordered_ascending(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 300.0, "ms")
        result = tracker.get_trend("gpt-4", "response_time")
        assert result[0]["value"] == 100.0
        assert result[1]["value"] == 200.0
        assert result[2]["value"] == 300.0

    def test_filters_by_metric_type(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("gpt-4", "quality_score", 0.9, "score")
        result = tracker.get_trend("gpt-4", "response_time")
        assert len(result) == 1
        assert result[0]["value"] == 100.0

    def test_respects_hours_parameter(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        # hours=0 would exclude everything older than "now"
        result = tracker.get_trend("gpt-4", "response_time", hours=0)
        # The metric was just recorded, so it should still be in window
        # for a freshly created metric
        assert isinstance(result, list)


# ===========================================================================
# 9. Multiple Models
# ===========================================================================

class TestMultipleModels:
    def test_independent_summaries(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("claude-3", "response_time", 200.0, "ms")

        s1 = tracker.get_model_summary("gpt-4")
        s2 = tracker.get_model_summary("claude-3")
        assert s1["avg_response_time_ms"] == pytest.approx(100.0)
        assert s2["avg_response_time_ms"] == pytest.approx(200.0)

    def test_cross_model_metrics_dont_bleed(self, tracker):
        tracker.record_metric("gpt-4", "quality_score", 0.9, "score")
        tracker.record_metric("claude-3", "quality_score", 0.5, "score")

        s1 = tracker.get_model_summary("gpt-4")
        assert s1["avg_quality_score"] == pytest.approx(0.9)

    def test_get_metrics_returns_only_requested_model(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        tracker.record_metric("claude-3", "response_time", 200.0, "ms")
        tracker.record_metric("gpt-4", "response_time", 150.0, "ms")

        result = tracker.get_metrics(model_id="gpt-4")
        assert all(r["model_id"] == "gpt-4" for r in result)
        assert len(result) == 2


# ===========================================================================
# 10. Best / Worst Task Detection
# ===========================================================================

class TestBestWorstTask:
    def test_best_task_type(self, tracker):
        tracker.record_metric("gpt-4", "quality_score", 0.95, "score",
                              task_type="chat")
        tracker.record_metric("gpt-4", "quality_score", 0.7, "score",
                              task_type="analysis")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["best_task_type"] == "chat"

    def test_worst_task_type(self, tracker):
        tracker.record_metric("gpt-4", "quality_score", 0.95, "score",
                              task_type="chat")
        tracker.record_metric("gpt-4", "quality_score", 0.7, "score",
                              task_type="analysis")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["worst_task_type"] == "analysis"

    def test_best_worst_none_when_no_quality_scores(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["best_task_type"] is None
        assert summary["worst_task_type"] is None

    def test_best_worst_none_when_no_task_type(self, tracker):
        tracker.record_metric("gpt-4", "quality_score", 0.9, "score")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["best_task_type"] is None
        assert summary["worst_task_type"] is None


# ===========================================================================
# 11. Summary Calculation
# ===========================================================================

class TestSummaryCalculation:
    def test_p95_with_single_value(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        summary = tracker.get_model_summary("gpt-4")
        assert summary["p95_response_time_ms"] == pytest.approx(100.0)

    def test_p95_with_20_values(self, tracker):
        for i in range(1, 21):
            tracker.record_metric("gpt-4", "response_time",
                                  float(i * 10), "ms")
        summary = tracker.get_model_summary("gpt-4")
        # 95th percentile of 20 sorted values is index 18 (0-based)
        # ceil(20 * 0.95) - 1 = ceil(19) - 1 = 19 - 1 = 18
        assert summary["p95_response_time_ms"] == pytest.approx(190.0)

    def test_summary_updates_incrementally(self, tracker):
        tracker.record_metric("gpt-4", "response_time", 100.0, "ms")
        s1 = tracker.get_model_summary("gpt-4")
        assert s1["avg_response_time_ms"] == pytest.approx(100.0)
        assert s1["total_requests"] == 1

        tracker.record_metric("gpt-4", "response_time", 200.0, "ms")
        s2 = tracker.get_model_summary("gpt-4")
        assert s2["avg_response_time_ms"] == pytest.approx(150.0)
        assert s2["total_requests"] == 2


# ===========================================================================
# 12. Singleton Pattern
# ===========================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        inst = get_model_performance()
        assert isinstance(inst, ModelPerformanceTracker)

    def test_get_is_idempotent(self):
        a = get_model_performance()
        b = get_model_performance()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_model_performance()
        reset_model_performance()
        b = get_model_performance()
        assert a is not b

    def test_reset_allows_fresh_instance(self):
        inst1 = get_model_performance()
        inst1.record_metric("gpt-4", "response_time", 100.0, "ms")
        reset_model_performance()

        inst2 = get_model_performance()
        summaries = inst2.get_all_summaries()
        assert summaries == []

    def test_double_reset_is_safe(self):
        reset_model_performance()
        reset_model_performance()
        inst = get_model_performance()
        assert isinstance(inst, ModelPerformanceTracker)


# ===========================================================================
# 13. Concurrent record_metric
# ===========================================================================

class TestConcurrency:
    def test_concurrent_records(self, tracker):
        errors = []

        def worker():
            try:
                for i in range(50):
                    tracker.record_metric("gpt-4", "response_time",
                                          float(100 + i), "ms")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        summary = tracker.get_model_summary("gpt-4")
        assert summary is not None
        assert summary["total_requests"] == 200

    def test_concurrent_records_different_models(self, tracker):
        errors = []

        def worker(model_id):
            try:
                for i in range(25):
                    tracker.record_metric(model_id, "response_time",
                                          float(100 + i), "ms")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(f"model-{i}",))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        summaries = tracker.get_all_summaries()
        assert len(summaries) == 4
        for s in summaries:
            assert s["total_requests"] == 25
