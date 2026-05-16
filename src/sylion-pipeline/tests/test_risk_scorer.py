"""Tests for SYLION Governance -- Risk Scorer.

Covers: compute_risk, score retrieval, thresholds, risk levels, stats,
event emission, thread safety, validation, and singleton management.
"""
import json
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.risk_scorer import (
    DEFAULT_THRESHOLDS,
    VALID_LEVELS,
    VALID_RISK_TYPES,
    RiskScorer,
    get_risk_scorer,
    reset_risk_scorer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scorer():
    """Fresh RiskScorer with :memory: SQLite."""
    return RiskScorer(db_path=":memory:")


@pytest.fixture
def scorer_with_bus():
    """RiskScorer connected to a real EventBus."""
    bus = EventBus(db_path=":memory:")
    return RiskScorer(db_path=":memory:", event_bus=bus), bus


# ---------------------------------------------------------------------------
# Test: compute_risk — basic
# ---------------------------------------------------------------------------

class TestComputeRisk:
    def test_computes_score_from_factors(self, scorer):
        result = scorer.compute_risk("mod-a", "security",
                                     {"vuln_count": 0.8, "exposure": 0.6})
        assert "score_id" in result
        assert result["module_id"] == "mod-a"
        assert result["risk_type"] == "security"
        assert 0.0 <= result["score"] <= 1.0
        assert result["level"] in VALID_LEVELS
        assert result["computed_at"] > 0

    def test_empty_factors_gives_zero(self, scorer):
        result = scorer.compute_risk("mod-b", "quality")
        assert result["score"] == 0.0
        assert result["level"] == "low"

    def test_none_factors_gives_zero(self, scorer):
        result = scorer.compute_risk("mod-c", "operational", factors=None)
        assert result["score"] == 0.0

    def test_all_max_factors_gives_high(self, scorer):
        result = scorer.compute_risk("mod-d", "security",
                                     {"a": 1.0, "b": 1.0, "c": 1.0})
        assert result["score"] == 1.0
        assert result["level"] == "critical"

    def test_factors_clamped_above_one(self, scorer):
        result = scorer.compute_risk("mod-e", "dependency",
                                     {"factor1": 5.0})
        assert result["score"] == 1.0

    def test_factors_clamped_below_zero(self, scorer):
        result = scorer.compute_risk("mod-f", "compliance",
                                     {"factor1": -0.5})
        assert result["score"] == 0.0

    def test_average_of_factors(self, scorer):
        result = scorer.compute_risk("mod-g", "quality",
                                     {"a": 0.0, "b": 1.0})
        assert abs(result["score"] - 0.5) < 1e-6

    def test_mixed_valid_and_invalid_values(self, scorer):
        result = scorer.compute_risk("mod-h", "operational",
                                     {"valid": 0.5, "invalid": "bad"})
        assert result["score"] == 0.25  # 0.5 + 0.0 / 2

    def test_factors_stored_in_result(self, scorer):
        factors = {"x": 0.3, "y": 0.7}
        result = scorer.compute_risk("mod-i", "security", factors)
        assert result["factors"] == factors

    def test_rejects_invalid_risk_type(self, scorer):
        with pytest.raises(ValueError, match="Invalid risk_type"):
            scorer.compute_risk("mod-j", "nonexistent", {"a": 0.5})

    def test_all_valid_risk_types_accepted(self, scorer):
        for rt in VALID_RISK_TYPES:
            result = scorer.compute_risk("mod-rt", rt, {"f": 0.5})
            assert result["risk_type"] == rt

    def test_score_id_is_unique(self, scorer):
        r1 = scorer.compute_risk("mod-k", "security", {"a": 0.5})
        r2 = scorer.compute_risk("mod-k", "security", {"a": 0.6})
        assert r1["score_id"] != r2["score_id"]

    def test_computed_at_is_recent(self, scorer):
        before = time.time()
        result = scorer.compute_risk("mod-l", "quality", {"a": 0.2})
        after = time.time()
        assert before <= result["computed_at"] <= after


# ---------------------------------------------------------------------------
# Test: score level classification
# ---------------------------------------------------------------------------

class TestScoreLevelClassification:
    def test_low_score(self, scorer):
        result = scorer.compute_risk("mod-low", "security", {"a": 0.1})
        assert result["level"] == "low"

    def test_medium_score(self, scorer):
        result = scorer.compute_risk("mod-med", "security", {"a": 0.45})
        assert result["level"] == "medium"

    def test_high_score(self, scorer):
        result = scorer.compute_risk("mod-hi", "security", {"a": 0.7})
        assert result["level"] == "high"

    def test_critical_score(self, scorer):
        result = scorer.compute_risk("mod-crit", "security", {"a": 0.9})
        assert result["level"] == "critical"

    def test_exact_boundary_low_medium(self, scorer):
        result = scorer.compute_risk("mod-b1", "security", {"a": 0.3})
        assert result["level"] == "medium"

    def test_exact_boundary_medium_high(self, scorer):
        result = scorer.compute_risk("mod-b2", "security", {"a": 0.6})
        assert result["level"] == "high"

    def test_exact_boundary_high_critical(self, scorer):
        result = scorer.compute_risk("mod-b3", "security", {"a": 0.8})
        assert result["level"] == "critical"


# ---------------------------------------------------------------------------
# Test: get_score
# ---------------------------------------------------------------------------

class TestGetScore:
    def test_returns_computed_score(self, scorer):
        r = scorer.compute_risk("mod-a", "security", {"a": 0.5})
        fetched = scorer.get_score(r["score_id"])
        assert fetched is not None
        assert fetched["score_id"] == r["score_id"]
        assert fetched["module_id"] == "mod-a"

    def test_returns_none_for_missing(self, scorer):
        assert scorer.get_score("nonexistent") is None

    def test_factors_deserialized_as_dict(self, scorer):
        r = scorer.compute_risk("mod-f", "quality", {"x": 0.3, "y": 0.7})
        fetched = scorer.get_score(r["score_id"])
        assert isinstance(fetched["factors"], dict)
        assert fetched["factors"]["x"] == 0.3


# ---------------------------------------------------------------------------
# Test: list_scores
# ---------------------------------------------------------------------------

class TestListScores:
    def test_lists_all_scores(self, scorer):
        scorer.compute_risk("m1", "security", {"a": 0.1})
        scorer.compute_risk("m2", "quality", {"b": 0.2})
        results = scorer.list_scores()
        assert len(results) == 2

    def test_filter_by_module_id(self, scorer):
        scorer.compute_risk("m1", "security", {"a": 0.1})
        scorer.compute_risk("m2", "security", {"a": 0.2})
        results = scorer.list_scores(module_id="m1")
        assert len(results) == 1
        assert results[0]["module_id"] == "m1"

    def test_filter_by_risk_type(self, scorer):
        scorer.compute_risk("m1", "security", {"a": 0.1})
        scorer.compute_risk("m1", "quality", {"a": 0.2})
        results = scorer.list_scores(risk_type="quality")
        assert len(results) == 1
        assert results[0]["risk_type"] == "quality"

    def test_filter_by_both(self, scorer):
        scorer.compute_risk("m1", "security", {"a": 0.1})
        scorer.compute_risk("m1", "quality", {"a": 0.2})
        scorer.compute_risk("m2", "security", {"a": 0.3})
        results = scorer.list_scores(module_id="m1", risk_type="security")
        assert len(results) == 1

    def test_respects_limit(self, scorer):
        for i in range(10):
            scorer.compute_risk("m-lim", "security", {"a": 0.1 * i})
        results = scorer.list_scores(limit=5)
        assert len(results) == 5

    def test_newest_first_order(self, scorer):
        scorer.compute_risk("m-ord", "security", {"a": 0.1})
        time.sleep(0.01)
        scorer.compute_risk("m-ord", "security", {"a": 0.9})
        results = scorer.list_scores(module_id="m-ord")
        assert results[0]["score"] > results[1]["score"]

    def test_empty_when_no_match(self, scorer):
        scorer.compute_risk("m1", "security", {"a": 0.1})
        results = scorer.list_scores(module_id="m-nope")
        assert results == []


# ---------------------------------------------------------------------------
# Test: get_latest_score
# ---------------------------------------------------------------------------

class TestGetLatestScore:
    def test_returns_most_recent(self, scorer):
        scorer.compute_risk("m-lt", "security", {"a": 0.2})
        time.sleep(0.01)
        latest = scorer.compute_risk("m-lt", "security", {"b": 0.8})
        result = scorer.get_latest_score("m-lt", "security")
        assert result["score_id"] == latest["score_id"]

    def test_returns_none_when_no_scores(self, scorer):
        result = scorer.get_latest_score("m-none", "security")
        assert result is None

    def test_ignores_other_risk_types(self, scorer):
        scorer.compute_risk("m-lt2", "security", {"a": 0.5})
        scorer.compute_risk("m-lt2", "quality", {"a": 0.9})
        result = scorer.get_latest_score("m-lt2", "security")
        assert result["risk_type"] == "security"


# ---------------------------------------------------------------------------
# Test: set_threshold
# ---------------------------------------------------------------------------

class TestSetThreshold:
    def test_creates_threshold(self, scorer):
        result = scorer.set_threshold("security", "high", 0.7, 0.9, "escalate")
        assert result["risk_type"] == "security"
        assert result["level"] == "high"
        assert result["min_score"] == 0.7
        assert result["max_score"] == 0.9
        assert result["action"] == "escalate"

    def test_replaces_existing_for_same_type_level(self, scorer):
        scorer.set_threshold("security", "high", 0.6, 0.8, "old")
        scorer.set_threshold("security", "high", 0.65, 0.85, "new")
        thresholds = scorer.list_thresholds(risk_type="security")
        # Filter to only security-specific (not wildcard '*') entries
        security_high = [t for t in thresholds
                         if t["level"] == "high" and t["risk_type"] == "security"]
        assert len(security_high) == 1
        assert security_high[0]["action"] == "new"

    def test_rejects_invalid_risk_type(self, scorer):
        with pytest.raises(ValueError, match="Invalid risk_type"):
            scorer.set_threshold("invalid", "high", 0.6, 0.8)

    def test_accepts_wildcard_risk_type(self, scorer):
        result = scorer.set_threshold("*", "low", 0.0, 0.2)
        assert result["risk_type"] == "*"

    def test_rejects_invalid_level(self, scorer):
        with pytest.raises(ValueError, match="Invalid level"):
            scorer.set_threshold("security", "extreme", 0.6, 0.8)

    def test_rejects_inverted_range(self, scorer):
        with pytest.raises(ValueError, match="Invalid score range"):
            scorer.set_threshold("security", "high", 0.8, 0.6)

    def test_rejects_negative_min(self, scorer):
        with pytest.raises(ValueError, match="Invalid score range"):
            scorer.set_threshold("security", "high", -0.1, 0.5)

    def test_rejects_max_above_one(self, scorer):
        with pytest.raises(ValueError, match="Invalid score range"):
            scorer.set_threshold("security", "high", 0.5, 1.5)

    def test_rejects_equal_min_max(self, scorer):
        with pytest.raises(ValueError, match="Invalid score range"):
            scorer.set_threshold("security", "high", 0.5, 0.5)


# ---------------------------------------------------------------------------
# Test: list_thresholds
# ---------------------------------------------------------------------------

class TestListThresholds:
    def test_lists_default_thresholds(self, scorer):
        thresholds = scorer.list_thresholds()
        assert len(thresholds) == 4  # default low/medium/high/critical

    def test_filter_by_risk_type_includes_wildcard(self, scorer):
        thresholds = scorer.list_thresholds(risk_type="security")
        # Should include the wildcard '*' thresholds
        assert len(thresholds) >= 4

    def test_returns_all_without_filter(self, scorer):
        scorer.set_threshold("security", "critical", 0.9, 1.0, "block")
        thresholds = scorer.list_thresholds()
        assert len(thresholds) >= 5


# ---------------------------------------------------------------------------
# Test: get_risk_level
# ---------------------------------------------------------------------------

class TestGetRiskLevel:
    def test_uses_default_thresholds(self, scorer):
        assert scorer.get_risk_level("security", 0.1)["level"] == "low"
        assert scorer.get_risk_level("security", 0.4)["level"] == "medium"
        assert scorer.get_risk_level("security", 0.7)["level"] == "high"
        assert scorer.get_risk_level("security", 0.9)["level"] == "critical"

    def test_uses_specific_thresholds_over_wildcard(self, scorer):
        scorer.set_threshold("quality", "low", 0.0, 0.5, "relaxed")
        result = scorer.get_risk_level("quality", 0.4)
        assert result["level"] == "low"
        assert result["action"] == "relaxed"

    def test_returns_fallback_for_no_match(self, scorer):
        # Clear all thresholds to test fallback
        with scorer._lock:
            scorer._conn.execute("DELETE FROM risk_thresholds")
            scorer._conn.commit()
        result = scorer.get_risk_level("security", 0.5)
        assert result["level"] == "medium"

    def test_includes_action(self, scorer):
        result = scorer.get_risk_level("security", 0.1)
        assert "action" in result


# ---------------------------------------------------------------------------
# Test: get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty_stats(self, scorer):
        stats = scorer.get_stats()
        assert stats["total_scores"] == 0
        assert stats["unique_modules"] == 0
        assert stats["average_score"] == 0.0
        assert stats["max_score"] == 0.0
        assert stats["by_risk_type"] == {}
        assert stats["threshold_count"] == 4

    def test_counts_scores(self, scorer):
        scorer.compute_risk("m1", "security", {"a": 0.5})
        scorer.compute_risk("m2", "quality", {"b": 0.3})
        stats = scorer.get_stats()
        assert stats["total_scores"] == 2
        assert stats["unique_modules"] == 2

    def test_by_risk_type_breakdown(self, scorer):
        scorer.compute_risk("m1", "security", {"a": 0.5})
        scorer.compute_risk("m1", "security", {"a": 0.6})
        scorer.compute_risk("m1", "quality", {"a": 0.3})
        stats = scorer.get_stats()
        assert stats["by_risk_type"]["security"] == 2
        assert stats["by_risk_type"]["quality"] == 1

    def test_by_level_breakdown(self, scorer):
        scorer.compute_risk("m1", "security", {"a": 0.1})  # low
        scorer.compute_risk("m2", "security", {"a": 0.9})  # critical
        stats = scorer.get_stats()
        assert stats["by_level"]["low"] == 1
        assert stats["by_level"]["critical"] == 1

    def test_average_and_max_score(self, scorer):
        scorer.compute_risk("m1", "security", {"a": 0.2})
        scorer.compute_risk("m2", "security", {"a": 0.8})
        stats = scorer.get_stats()
        assert abs(stats["average_score"] - 0.5) < 1e-6
        assert abs(stats["max_score"] - 0.8) < 1e-6


# ---------------------------------------------------------------------------
# Test: EventBus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_emits_event_on_high_score(self, scorer_with_bus):
        scorer, bus = scorer_with_bus
        events = []
        bus.subscribe("risk.score_computed", lambda e: events.append(e))
        scorer.compute_risk("m-high", "security", {"a": 0.7})
        assert len(events) == 1
        assert events[0].payload["module_id"] == "m-high"
        assert events[0].payload["level"] == "high"

    def test_emits_event_on_critical_score(self, scorer_with_bus):
        scorer, bus = scorer_with_bus
        events = []
        bus.subscribe("risk.score_computed", lambda e: events.append(e))
        scorer.compute_risk("m-crit", "security", {"a": 0.9})
        assert len(events) == 1
        assert events[0].payload["level"] == "critical"

    def test_no_event_on_low_score(self, scorer_with_bus):
        scorer, bus = scorer_with_bus
        events = []
        bus.subscribe("risk.score_computed", lambda e: events.append(e))
        scorer.compute_risk("m-low", "security", {"a": 0.1})
        assert len(events) == 0

    def test_no_event_on_medium_score(self, scorer_with_bus):
        scorer, bus = scorer_with_bus
        events = []
        bus.subscribe("risk.score_computed", lambda e: events.append(e))
        scorer.compute_risk("m-med", "security", {"a": 0.4})
        assert len(events) == 0

    def test_event_payload_has_all_fields(self, scorer_with_bus):
        scorer, bus = scorer_with_bus
        events = []
        bus.subscribe("risk.score_computed", lambda e: events.append(e))
        scorer.compute_risk("m-pl", "security", {"a": 0.8})
        payload = events[0].payload
        assert "score_id" in payload
        assert "module_id" in payload
        assert "risk_type" in payload
        assert "score" in payload
        assert "level" in payload
        assert "action" in payload
        assert "factors" in payload

    def test_no_event_without_bus(self, scorer):
        # Should not raise -- _emit gracefully handles None event_bus
        scorer.compute_risk("m-nb", "security", {"a": 0.9})

    def test_threshold_set_emits_event(self, scorer_with_bus):
        scorer, bus = scorer_with_bus
        events = []
        bus.subscribe("risk.threshold_set", lambda e: events.append(e))
        scorer.set_threshold("security", "critical", 0.9, 1.0, "block")
        assert len(events) == 1
        assert events[0].payload["level"] == "critical"


# ---------------------------------------------------------------------------
# Test: thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_computes(self, scorer):
        errors = []

        def compute(idx):
            try:
                scorer.compute_risk(
                    f"concurrent-{idx}", "security",
                    {"factor": idx / 20.0},
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=compute, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(scorer.list_scores()) == 20

    def test_concurrent_read_write(self, scorer):
        scorer.compute_risk("rw-base", "security", {"a": 0.5})
        errors = []

        def reader():
            try:
                for _ in range(50):
                    scorer.get_score("nonexistent")
                    scorer.list_scores(module_id="rw-base")
                    scorer.get_latest_score("rw-base", "security")
                    scorer.get_stats()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    scorer.compute_risk(
                        "rw-base", "security",
                        {"factor": i / 10.0},
                    )
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
# Test: singleton management
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_risk_scorer_returns_same_instance(self):
        reset_risk_scorer()
        s1 = get_risk_scorer(db_path=":memory:")
        s2 = get_risk_scorer()
        assert s1 is s2
        reset_risk_scorer()

    def test_reset_clears_singleton(self):
        s1 = get_risk_scorer(db_path=":memory:")
        reset_risk_scorer()
        s2 = get_risk_scorer(db_path=":memory:")
        assert s1 is not s2
        reset_risk_scorer()


# ---------------------------------------------------------------------------
# Test: constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_valid_risk_types(self):
        assert "security" in VALID_RISK_TYPES
        assert "quality" in VALID_RISK_TYPES
        assert "operational" in VALID_RISK_TYPES
        assert "dependency" in VALID_RISK_TYPES
        assert "compliance" in VALID_RISK_TYPES
        assert len(VALID_RISK_TYPES) == 5

    def test_valid_levels(self):
        assert "low" in VALID_LEVELS
        assert "medium" in VALID_LEVELS
        assert "high" in VALID_LEVELS
        assert "critical" in VALID_LEVELS
        assert len(VALID_LEVELS) == 4

    def test_default_thresholds_cover_full_range(self):
        # Default thresholds should cover 0.0 to 1.0
        levels = {t["level"] for t in DEFAULT_THRESHOLDS}
        assert levels == {"low", "medium", "high", "critical"}
