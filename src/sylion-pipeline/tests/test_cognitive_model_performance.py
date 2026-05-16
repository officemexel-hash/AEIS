"""
Comprehensive tests for sylion.cognitive.model_performance -- ModelPerformanceTracker.

~40 tests covering: metric recording, validation, filtered queries,
summary computation/retrieval, leaderboard ranking, aggregate stats,
event emission, singleton pattern, thread safety, edge cases.
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.cognitive.model_performance import (
    ModelPerformanceTracker,
    VALID_METRIC_TYPES,
    VALID_PERIODS,
    get_model_performance_tracker,
    reset_model_performance_tracker,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tracker(bus: EventBus | None = None) -> ModelPerformanceTracker:
    """Create a fresh in-memory ModelPerformanceTracker."""
    return ModelPerformanceTracker(event_bus=bus)


def _record_sample(
    tracker: ModelPerformanceTracker,
    model_id: str = "gpt-4o",
    metric_type: str = "accuracy",
    metric_value: float = 0.92,
    tokens_used: int = 500,
    latency_ms: float = 150.0,
    metadata: dict | None = None,
) -> dict:
    """Record a sample metric and return the result."""
    return tracker.record_metric(
        model_id=model_id,
        metric_type=metric_type,
        metric_value=metric_value,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        metadata=metadata,
    )


# ===========================================================================
# 1. Constants & Module Attributes
# ===========================================================================

class TestConstants:
    def test_valid_metric_types(self):
        assert "accuracy" in VALID_METRIC_TYPES
        assert "latency" in VALID_METRIC_TYPES
        assert "cost" in VALID_METRIC_TYPES
        assert "tokens" in VALID_METRIC_TYPES
        assert "overall" in VALID_METRIC_TYPES
        assert len(VALID_METRIC_TYPES) == 5

    def test_valid_periods(self):
        assert "hourly" in VALID_PERIODS
        assert "daily" in VALID_PERIODS
        assert "weekly" in VALID_PERIODS
        assert "monthly" in VALID_PERIODS
        assert len(VALID_PERIODS) == 4


# ===========================================================================
# 2. Record Metric
# ===========================================================================

class TestRecordMetric:
    def test_returns_metric_id(self):
        t = _tracker()
        result = _record_sample(t)
        assert "metric_id" in result
        assert len(result["metric_id"]) > 0

    def test_returns_model_id(self):
        t = _tracker()
        result = _record_sample(t, model_id="claude-3")
        assert result["model_id"] == "claude-3"

    def test_returns_metric_type(self):
        t = _tracker()
        result = _record_sample(t, metric_type="latency")
        assert result["metric_type"] == "latency"

    def test_returns_metric_value(self):
        t = _tracker()
        result = _record_sample(t, metric_value=0.85)
        assert result["metric_value"] == pytest.approx(0.85)

    def test_returns_tokens_used(self):
        t = _tracker()
        result = _record_sample(t, tokens_used=1024)
        assert result["tokens_used"] == 1024

    def test_returns_latency_ms(self):
        t = _tracker()
        result = _record_sample(t, latency_ms=350.5)
        assert result["latency_ms"] == pytest.approx(350.5)

    def test_returns_timestamp(self):
        t = _tracker()
        before = time.time()
        result = _record_sample(t)
        after = time.time()
        assert before <= result["timestamp"] <= after

    def test_stores_metadata_as_dict(self):
        t = _tracker()
        meta = {"region": "eu-west", "retry": True, "attempt": 2}
        result = _record_sample(t, metadata=meta)
        assert result["metadata"] == meta

    def test_defaults_tokens_and_latency(self):
        t = _tracker()
        result = t.record_metric("m1", "accuracy", 0.9)
        assert result["tokens_used"] == 0
        assert result["latency_ms"] == 0.0

    def test_rejects_invalid_metric_type(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Invalid metric_type"):
            t.record_metric("m1", "invalid_type", 1.0)

    def test_all_valid_metric_types_accepted(self):
        t = _tracker()
        for mt in VALID_METRIC_TYPES:
            result = t.record_metric("m1", mt, 1.0)
            assert result["metric_type"] == mt

    def test_emits_metric_recorded_event(self):
        bus = EventBus()
        t = _tracker(bus=bus)
        events = []
        bus.subscribe("performance.metric_recorded",
                       lambda e: events.append(e))

        _record_sample(t, model_id="gpt-4o")
        assert len(events) == 1
        assert events[0].payload["model_id"] == "gpt-4o"
        assert events[0].payload["metric_type"] == "accuracy"

    def test_no_event_without_bus(self):
        t = _tracker(bus=None)
        result = _record_sample(t)
        assert result["metric_id"]  # no crash, event silently skipped

    def test_event_contains_all_fields(self):
        bus = EventBus()
        t = _tracker(bus=bus)
        events = []
        bus.subscribe("performance.metric_recorded",
                       lambda e: events.append(e))

        t.record_metric("m1", "accuracy", 0.9, tokens_used=100, latency_ms=200)
        payload = events[0].payload
        assert "metric_id" in payload
        assert payload["model_id"] == "m1"
        assert payload["metric_type"] == "accuracy"
        assert payload["metric_value"] == pytest.approx(0.9)
        assert payload["tokens_used"] == 100
        assert payload["latency_ms"] == pytest.approx(200.0)


# ===========================================================================
# 3. Get Metrics (filtered)
# ===========================================================================

class TestGetMetrics:
    def test_empty_when_no_metrics(self):
        t = _tracker()
        assert t.get_metrics() == []

    def test_returns_all_without_filters(self):
        t = _tracker()
        _record_sample(t, model_id="m1")
        _record_sample(t, model_id="m2")
        result = t.get_metrics()
        assert len(result) == 2

    def test_filters_by_model_id(self):
        t = _tracker()
        _record_sample(t, model_id="m1")
        _record_sample(t, model_id="m2")
        result = t.get_metrics(model_id="m1")
        assert len(result) == 1
        assert result[0]["model_id"] == "m1"

    def test_filters_by_metric_type(self):
        t = _tracker()
        _record_sample(t, metric_type="accuracy")
        _record_sample(t, metric_type="latency")
        result = t.get_metrics(metric_type="latency")
        assert len(result) == 1
        assert result[0]["metric_type"] == "latency"

    def test_filters_by_since(self):
        t = _tracker()
        _record_sample(t)
        cutoff = time.time()
        time.sleep(0.01)
        _record_sample(t, model_id="m2")
        result = t.get_metrics(since=cutoff)
        assert len(result) == 1
        assert result[0]["model_id"] == "m2"

    def test_respects_limit(self):
        t = _tracker()
        for i in range(20):
            _record_sample(t, model_id=f"m{i}")
        result = t.get_metrics(limit=5)
        assert len(result) == 5

    def test_ordered_by_timestamp_desc(self):
        t = _tracker()
        _record_sample(t, metric_value=1.0)
        _record_sample(t, metric_value=2.0)
        result = t.get_metrics()
        assert result[0]["metric_value"] == pytest.approx(2.0)
        assert result[1]["metric_value"] == pytest.approx(1.0)

    def test_combined_filters(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9, latency_ms=100)
        t.record_metric("m1", "latency", 200.0, latency_ms=200)
        t.record_metric("m2", "accuracy", 0.8, latency_ms=150)
        result = t.get_metrics(model_id="m1", metric_type="accuracy")
        assert len(result) == 1
        assert result[0]["model_id"] == "m1"
        assert result[0]["metric_type"] == "accuracy"

    def test_metadata_deserialized(self):
        t = _tracker()
        meta = {"key": "value", "num": 42}
        t.record_metric("m1", "accuracy", 0.9, metadata=meta)
        rows = t.get_metrics(model_id="m1")
        assert rows[0]["metadata"] == meta


# ===========================================================================
# 4. Compute Summary
# ===========================================================================

class TestComputeSummary:
    def test_returns_summary_dict(self):
        t = _tracker()
        _record_sample(t)
        result = t.compute_summary("gpt-4o", "daily")
        assert "summary_id" in result
        assert result["model_id"] == "gpt-4o"
        assert result["period"] == "daily"

    def test_avg_latency(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9, latency_ms=100)
        t.record_metric("m1", "accuracy", 0.9, latency_ms=200)
        summary = t.compute_summary("m1", "daily")
        assert summary["avg_latency"] == pytest.approx(150.0)

    def test_avg_score(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.8)
        t.record_metric("m1", "accuracy", 0.9)
        summary = t.compute_summary("m1", "daily")
        assert summary["avg_score"] == pytest.approx(0.85, abs=1e-3)

    def test_total_calls(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        t.record_metric("m1", "latency", 100.0)
        t.record_metric("m1", "accuracy", 0.9)
        summary = t.compute_summary("m1", "daily")
        assert summary["total_calls"] == 3

    def test_total_tokens(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9, tokens_used=500)
        t.record_metric("m1", "accuracy", 0.9, tokens_used=300)
        summary = t.compute_summary("m1", "daily")
        assert summary["total_tokens"] == 800

    def test_total_cost_from_cost_metrics(self):
        t = _tracker()
        t.record_metric("m1", "cost", 0.05)
        t.record_metric("m1", "cost", 0.03)
        summary = t.compute_summary("m1", "daily")
        assert summary["total_cost"] == pytest.approx(0.08, abs=1e-3)

    def test_total_cost_zero_when_no_cost_metrics(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        summary = t.compute_summary("m1", "daily")
        assert summary["total_cost"] == 0.0

    def test_rejects_invalid_period(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Invalid period"):
            t.compute_summary("m1", "yearly")

    def test_all_valid_periods(self):
        t = _tracker()
        _record_sample(t)
        for period in VALID_PERIODS:
            result = t.compute_summary("gpt-4o", period)
            assert result["period"] == period

    def test_summary_stored_in_db(self):
        t = _tracker()
        _record_sample(t)
        t.compute_summary("gpt-4o", "daily")
        retrieved = t.get_summary("gpt-4o", "daily")
        assert retrieved is not None
        assert retrieved["model_id"] == "gpt-4o"

    def test_computed_at_set(self):
        t = _tracker()
        _record_sample(t)
        before = time.time()
        summary = t.compute_summary("gpt-4o", "daily")
        after = time.time()
        assert before <= summary["computed_at"] <= after


# ===========================================================================
# 5. Get Summary
# ===========================================================================

class TestGetSummary:
    def test_returns_none_when_no_summary(self):
        t = _tracker()
        assert t.get_summary("nonexistent", "daily") is None

    def test_returns_latest_summary(self):
        t = _tracker()
        _record_sample(t)
        t.compute_summary("gpt-4o", "daily")
        _record_sample(t, metric_value=0.5)
        t.compute_summary("gpt-4o", "daily")
        result = t.get_summary("gpt-4o", "daily")
        # Second summary has lower avg score due to 0.5
        assert result is not None
        assert result["total_calls"] == 2

    def test_rejects_invalid_period(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Invalid period"):
            t.get_summary("m1", "century")

    def test_different_periods_independent(self):
        t = _tracker()
        _record_sample(t)
        daily = t.compute_summary("gpt-4o", "daily")
        weekly = t.compute_summary("gpt-4o", "weekly")
        assert daily["period"] == "daily"
        assert weekly["period"] == "weekly"
        assert daily["summary_id"] != weekly["summary_id"]


# ===========================================================================
# 6. List Summaries
# ===========================================================================

class TestListSummaries:
    def test_empty_when_no_summaries(self):
        t = _tracker()
        assert t.list_summaries() == []

    def test_returns_all_summaries(self):
        t = _tracker()
        _record_sample(t)
        t.compute_summary("gpt-4o", "daily")
        t.compute_summary("gpt-4o", "weekly")
        result = t.list_summaries()
        assert len(result) == 2

    def test_filters_by_period(self):
        t = _tracker()
        _record_sample(t)
        t.compute_summary("gpt-4o", "daily")
        t.compute_summary("gpt-4o", "weekly")
        result = t.list_summaries(period="daily")
        assert len(result) == 1
        assert result[0]["period"] == "daily"

    def test_respects_limit(self):
        t = _tracker()
        _record_sample(t)
        for _ in range(5):
            t.compute_summary("gpt-4o", "daily")
        result = t.list_summaries(limit=3)
        assert len(result) == 3

    def test_ordered_by_computed_at_desc(self):
        t = _tracker()
        _record_sample(t)
        t.compute_summary("gpt-4o", "daily")
        t.compute_summary("gpt-4o", "weekly")
        result = t.list_summaries()
        assert result[0]["period"] == "weekly"


# ===========================================================================
# 7. Update Leaderboard
# ===========================================================================

class TestUpdateLeaderboard:
    def test_returns_ranked_entries(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        t.record_metric("m2", "accuracy", 0.8)
        t.record_metric("m3", "accuracy", 0.95)
        result = t.update_leaderboard("accuracy")
        assert len(result) == 3
        assert result[0]["model_id"] == "m3"
        assert result[0]["rank"] == 1
        assert result[1]["model_id"] == "m1"
        assert result[1]["rank"] == 2
        assert result[2]["model_id"] == "m2"
        assert result[2]["rank"] == 3

    def test_overall_uses_all_types(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        t.record_metric("m1", "latency", 100.0)
        t.record_metric("m2", "accuracy", 0.5)
        result = t.update_leaderboard("overall")
        # m1 avg = (0.9 + 100.0) / 2 = 50.45, m2 avg = 0.5
        assert len(result) == 2
        assert result[0]["model_id"] == "m1"

    def test_replaces_old_entries(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        t.update_leaderboard("accuracy")
        t.record_metric("m2", "accuracy", 0.95)
        t.update_leaderboard("accuracy")
        result = t.get_leaderboard("accuracy")
        assert len(result) == 2  # m1 + m2, no duplicate m1 from first run

    def test_emits_leaderboard_updated_event(self):
        bus = EventBus()
        t = _tracker(bus=bus)
        events = []
        bus.subscribe("performance.leaderboard_updated",
                       lambda e: events.append(e))

        _record_sample(t)
        t.update_leaderboard("accuracy")
        assert len(events) == 1
        assert events[0].payload["metric_type"] == "accuracy"
        assert events[0].payload["entries_count"] == 1

    def test_rejects_invalid_metric_type(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Invalid metric_type"):
            t.update_leaderboard("nonexistent")

    def test_empty_leaderboard_when_no_data(self):
        t = _tracker()
        result = t.update_leaderboard("accuracy")
        assert result == []

    def test_entry_has_all_fields(self):
        t = _tracker()
        _record_sample(t)
        entries = t.update_leaderboard("accuracy")
        entry = entries[0]
        assert "entry_id" in entry
        assert "model_id" in entry
        assert "metric_type" in entry
        assert "rank" in entry
        assert "score" in entry
        assert "updated_at" in entry


# ===========================================================================
# 8. Get Leaderboard
# ===========================================================================

class TestGetLeaderboard:
    def test_empty_when_not_computed(self):
        t = _tracker()
        assert t.get_leaderboard("accuracy") == []

    def test_returns_computed_rankings(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        t.record_metric("m2", "accuracy", 0.8)
        t.update_leaderboard("accuracy")
        result = t.get_leaderboard("accuracy")
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_ordered_by_rank(self):
        t = _tracker()
        for i in range(5):
            t.record_metric(f"m{i}", "accuracy", float(i) / 10.0)
        t.update_leaderboard("accuracy")
        result = t.get_leaderboard("accuracy")
        ranks = [r["rank"] for r in result]
        assert ranks == sorted(ranks)

    def test_rejects_invalid_metric_type(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Invalid metric_type"):
            t.get_leaderboard("bad_type")

    def test_independent_per_metric_type(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        t.record_metric("m2", "accuracy", 0.8)
        t.record_metric("m1", "latency", 100.0)
        t.record_metric("m2", "latency", 200.0)
        t.update_leaderboard("accuracy")
        t.update_leaderboard("latency")
        acc = t.get_leaderboard("accuracy")
        lat = t.get_leaderboard("latency")
        assert acc[0]["model_id"] == "m1"
        assert lat[0]["model_id"] == "m2"  # 200 > 100, ranked higher


# ===========================================================================
# 9. Get Stats
# ===========================================================================

class TestGetStats:
    def test_empty_stats(self):
        t = _tracker()
        stats = t.get_stats()
        assert stats["total_metrics"] == 0
        assert stats["unique_models"] == 0
        assert stats["total_tokens"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["avg_latency"] == 0.0
        assert stats["avg_score"] == 0.0
        assert stats["by_model"] == {}

    def test_total_metrics(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        t.record_metric("m1", "latency", 100.0)
        t.record_metric("m2", "accuracy", 0.8)
        stats = t.get_stats()
        assert stats["total_metrics"] == 3

    def test_unique_models(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        t.record_metric("m2", "accuracy", 0.8)
        t.record_metric("m3", "accuracy", 0.7)
        stats = t.get_stats()
        assert stats["unique_models"] == 3

    def test_total_tokens(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9, tokens_used=500)
        t.record_metric("m1", "accuracy", 0.9, tokens_used=300)
        stats = t.get_stats()
        assert stats["total_tokens"] == 800

    def test_total_cost(self):
        t = _tracker()
        t.record_metric("m1", "cost", 0.05)
        t.record_metric("m1", "cost", 0.03)
        stats = t.get_stats()
        assert stats["total_cost"] == pytest.approx(0.08, abs=1e-3)

    def test_avg_latency(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9, latency_ms=100)
        t.record_metric("m1", "accuracy", 0.9, latency_ms=200)
        stats = t.get_stats()
        assert stats["avg_latency"] == pytest.approx(150.0)

    def test_avg_score(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.8)
        t.record_metric("m1", "accuracy", 0.9)
        stats = t.get_stats()
        assert stats["avg_score"] == pytest.approx(0.85, abs=1e-3)

    def test_by_model_breakdown(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9, tokens_used=100, latency_ms=50)
        t.record_metric("m2", "accuracy", 0.8, tokens_used=200, latency_ms=100)
        stats = t.get_stats()
        assert "m1" in stats["by_model"]
        assert "m2" in stats["by_model"]
        assert stats["by_model"]["m1"]["total_tokens"] == 100
        assert stats["by_model"]["m2"]["total_tokens"] == 200


# ===========================================================================
# 10. Singleton Pattern
# ===========================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        reset_model_performance_tracker()
        inst = get_model_performance_tracker()
        assert isinstance(inst, ModelPerformanceTracker)
        reset_model_performance_tracker()

    def test_get_is_idempotent(self):
        reset_model_performance_tracker()
        a = get_model_performance_tracker()
        b = get_model_performance_tracker()
        assert a is b
        reset_model_performance_tracker()

    def test_reset_clears_singleton(self):
        reset_model_performance_tracker()
        a = get_model_performance_tracker()
        reset_model_performance_tracker()
        b = get_model_performance_tracker()
        assert a is not b
        reset_model_performance_tracker()

    def test_reset_allows_fresh_instance(self):
        reset_model_performance_tracker()
        inst1 = get_model_performance_tracker()
        inst1.record_metric("m1", "accuracy", 0.9)
        reset_model_performance_tracker()
        inst2 = get_model_performance_tracker()
        assert inst2.get_stats()["total_metrics"] == 0
        reset_model_performance_tracker()

    def test_double_reset_is_safe(self):
        reset_model_performance_tracker()
        reset_model_performance_tracker()
        inst = get_model_performance_tracker()
        assert isinstance(inst, ModelPerformanceTracker)
        reset_model_performance_tracker()


# ===========================================================================
# 11. Concurrency
# ===========================================================================

class TestConcurrency:
    def test_concurrent_record_metric(self):
        t = _tracker()
        errors: list[Exception] = []

        def worker(model_id: str):
            try:
                for i in range(50):
                    t.record_metric(model_id, "accuracy", float(i) / 50.0,
                                    tokens_used=10, latency_ms=100.0 + i)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(f"m{i}",))
            for i in range(4)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(errors) == 0
        stats = t.get_stats()
        assert stats["total_metrics"] == 200
        assert stats["unique_models"] == 4

    def test_concurrent_compute_summary(self):
        t = _tracker()
        for i in range(20):
            t.record_metric("m1", "accuracy", 0.9, tokens_used=100,
                            latency_ms=150.0)

        errors: list[Exception] = []

        def worker(period: str):
            try:
                for _ in range(10):
                    t.compute_summary("m1", period)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(p,))
            for p in VALID_PERIODS
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(errors) == 0
        summaries = t.list_summaries()
        assert len(summaries) > 0

    def test_concurrent_record_and_leaderboard(self):
        t = _tracker()
        errors: list[Exception] = []

        def recorder():
            try:
                for i in range(30):
                    t.record_metric("m1", "accuracy", float(i) / 30.0)
            except Exception as e:
                errors.append(e)

        def leaderboard_updater():
            try:
                for _ in range(10):
                    t.update_leaderboard("accuracy")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=recorder),
            threading.Thread(target=leaderboard_updater),
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(errors) == 0


# ===========================================================================
# 12. Edge Cases
# ===========================================================================

class TestEdgeCases:
    def test_metadata_none(self):
        t = _tracker()
        result = t.record_metric("m1", "accuracy", 0.9, metadata=None)
        assert result["metadata"] is None

    def test_metadata_complex_nested(self):
        t = _tracker()
        meta = {"nested": {"a": [1, 2, 3], "b": {"c": True}}}
        result = t.record_metric("m1", "accuracy", 0.9, metadata=meta)
        assert result["metadata"] == meta
        rows = t.get_metrics(model_id="m1")
        assert rows[0]["metadata"] == meta

    def test_zero_metric_value(self):
        t = _tracker()
        result = t.record_metric("m1", "cost", 0.0)
        assert result["metric_value"] == 0.0

    def test_negative_metric_value(self):
        t = _tracker()
        result = t.record_metric("m1", "latency", -5.0)
        assert result["metric_value"] == -5.0

    def test_large_token_count(self):
        t = _tracker()
        result = t.record_metric("m1", "accuracy", 0.9, tokens_used=1_000_000)
        assert result["tokens_used"] == 1_000_000

    def test_compute_summary_no_data(self):
        t = _tracker()
        summary = t.compute_summary("nonexistent", "daily")
        assert summary["total_calls"] == 0
        assert summary["avg_latency"] == 0.0

    def test_multiple_summaries_kept(self):
        t = _tracker()
        _record_sample(t)
        s1 = t.compute_summary("gpt-4o", "daily")
        _record_sample(t, metric_value=0.5)
        s2 = t.compute_summary("gpt-4o", "daily")
        assert s1["summary_id"] != s2["summary_id"]
        all_s = t.list_summaries(period="daily")
        assert len(all_s) == 2

    def test_get_metrics_with_all_filters(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9, tokens_used=100, latency_ms=50)
        t.record_metric("m1", "latency", 200.0, tokens_used=200, latency_ms=200)
        t.record_metric("m2", "accuracy", 0.8, tokens_used=300, latency_ms=100)
        now = time.time()
        result = t.get_metrics(model_id="m1", metric_type="accuracy",
                               since=now - 10, limit=10)
        assert len(result) == 1
        assert result[0]["model_id"] == "m1"
        assert result[0]["metric_type"] == "accuracy"

    def test_leaderboard_with_tie(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9)
        t.record_metric("m2", "accuracy", 0.9)
        entries = t.update_leaderboard("accuracy")
        assert len(entries) == 2
        # Both have same score, both should be present
        scores = [e["score"] for e in entries]
        assert scores[0] == pytest.approx(scores[1])

    def test_stats_after_multiple_operations(self):
        t = _tracker()
        t.record_metric("m1", "accuracy", 0.9, tokens_used=100, latency_ms=50)
        t.record_metric("m1", "cost", 0.05, tokens_used=200, latency_ms=100)
        t.record_metric("m2", "latency", 150.0, tokens_used=50, latency_ms=150)
        stats = t.get_stats()
        assert stats["total_metrics"] == 3
        assert stats["unique_models"] == 2
        assert stats["total_tokens"] == 350
        assert stats["total_cost"] == pytest.approx(0.05, abs=1e-3)
