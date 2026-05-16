"""Tests for sylion.efficiency.code_bloat module."""

import pytest

from sylion.efficiency.code_bloat import CodeBloatTracker, ModuleMetric, BloatDelta


class TestModuleMetric:
    def test_auto_timestamp(self):
        m = ModuleMetric(module_id="m1")
        assert m.measured_at > 0


class TestBloatDelta:
    def test_auto_id(self):
        d = BloatDelta(module_id="m1")
        assert d.record_id != ""


class TestCodeBloatTracker:
    @pytest.fixture
    def tracker(self):
        return CodeBloatTracker()

    def test_measure(self, tracker):
        result = tracker.measure("mod-a", loc=100, complexity=5, files=3, deps=2)
        assert result["module_id"] == "mod-a"
        assert result["bloat_score"] > 0

    def test_measure_updates(self, tracker):
        tracker.measure("mod-b", loc=50, complexity=3, deps=2)
        result = tracker.measure("mod-b", loc=60, complexity=4, deps=2)
        assert result["bloat_score"] > 0

    def test_get_module(self, tracker):
        tracker.measure("mod-c", loc=200, complexity=10)
        metric = tracker.get_module("mod-c")
        assert metric is not None
        assert metric["module_id"] == "mod-c"

    def test_get_module_not_found(self, tracker):
        assert tracker.get_module("nonexistent") is None

    def test_record_delta(self, tracker):
        result = tracker.record_delta("mod-d", before=100, after=120)
        assert result["module_id"] == "mod-d"
        assert result["delta_percent"] == pytest.approx(20.0)

    def test_get_history(self, tracker):
        tracker.record_delta("mod-e", 100, 110)
        tracker.record_delta("mod-e", 110, 130)
        history = tracker.get_history("mod-e")
        assert len(history) >= 2

    def test_get_history_empty(self, tracker):
        history = tracker.get_history("nonexistent")
        assert history == []

    def test_is_within_budget_pass(self, tracker):
        tracker.measure("mod-f", loc=50, complexity=2, deps=1)
        result = tracker.is_within_budget("mod-f", budget_percent=50.0)
        assert isinstance(result, bool)

    def test_is_within_budget_fail(self, tracker):
        tracker.measure("mod-g", loc=500, complexity=50, deps=10)
        result = tracker.is_within_budget("mod-g", budget_percent=0.0)
        assert isinstance(result, bool)

    def test_is_within_budget_not_found(self, tracker):
        result = tracker.is_within_budget("missing")
        assert isinstance(result, bool)

    def test_list_modules(self, tracker):
        tracker.measure("lm1", loc=100, complexity=5, deps=2)
        tracker.measure("lm2", loc=200, complexity=10, deps=3)
        modules = tracker.list_modules()
        assert len(modules) >= 2
