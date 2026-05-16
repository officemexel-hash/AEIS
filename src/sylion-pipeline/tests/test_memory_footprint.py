"""
Tests for sylion.efficiency.memory_footprint — MemoryFootprintTracker

CRUD: snapshot, set_budget, check_budget
Queries: get_snapshots, get_current, detect_leaks
Budget logic: within/over based on max_rss/max_heap vs current
Leak detection: trend analysis over a window
Events: verify EventBus emissions
"""

from __future__ import annotations

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.efficiency.memory_footprint import MemoryFootprintTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
def tracker(bus):
    return MemoryFootprintTracker(event_bus=bus)


# ---------------------------------------------------------------------------
# Snapshot CRUD
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot_returns_expected_fields(self, tracker):
        result = tracker.snapshot("mod_a", rss=1024, heap=512, peak=2048, gc=3)
        assert result["module_id"] == "mod_a"
        assert "snapshot_id" in result
        assert "timestamp" in result

    def test_snapshot_stores_all_fields(self, tracker):
        tracker.snapshot("mod_b", rss=2048, heap=1024, peak=4096, gc=5)
        rows = tracker.get_snapshots("mod_b")
        assert len(rows) == 1
        r = rows[0]
        assert r["module_id"] == "mod_b"
        assert r["rss_bytes"] == 2048
        assert r["heap_bytes"] == 1024
        assert r["peak_bytes"] == 4096
        assert r["gc_count"] == 5

    def test_snapshot_defaults(self, tracker):
        tracker.snapshot("mod_c")
        rows = tracker.get_snapshots("mod_c")
        r = rows[0]
        assert r["rss_bytes"] == 0
        assert r["heap_bytes"] == 0
        assert r["peak_bytes"] == 0
        assert r["gc_count"] == 0

    def test_multiple_snapshots_ordered_desc(self, tracker):
        for i in range(4):
            tracker.snapshot("mod_d", rss=100 * (i + 1))
        rows = tracker.get_snapshots("mod_d")
        assert len(rows) == 4
        assert rows[0]["rss_bytes"] >= rows[1]["rss_bytes"]

    def test_get_snapshots_respects_limit(self, tracker):
        for i in range(10):
            tracker.snapshot("mod_e", rss=i * 100)
        rows = tracker.get_snapshots("mod_e", limit=3)
        assert len(rows) == 3

    def test_get_current_returns_latest(self, tracker):
        tracker.snapshot("mod_f", rss=100)
        tracker.snapshot("mod_f", rss=200)
        current = tracker.get_current("mod_f")
        assert current is not None
        assert current["rss_bytes"] == 200

    def test_get_current_nonexistent_returns_none(self, tracker):
        assert tracker.get_current("no_module") is None


# ---------------------------------------------------------------------------
# Budget management
# ---------------------------------------------------------------------------

class TestBudget:
    def test_set_budget_returns_fields(self, tracker):
        result = tracker.set_budget("mod_g", max_rss=10000, max_heap=5000)
        assert result["module_id"] == "mod_g"
        assert result["max_rss_bytes"] == 10000
        assert result["max_heap_bytes"] == 5000

    def test_check_budget_within_limits(self, tracker):
        tracker.set_budget("mod_h", max_rss=10000, max_heap=5000)
        tracker.snapshot("mod_h", rss=5000, heap=2000)
        result = tracker.check_budget("mod_h")
        assert result["status"] == "within"

    def test_check_budget_over_rss(self, tracker):
        tracker.set_budget("mod_i", max_rss=1000, max_heap=5000)
        tracker.snapshot("mod_i", rss=2000, heap=1000)
        result = tracker.check_budget("mod_i")
        assert result["status"] == "over"

    def test_check_budget_over_heap(self, tracker):
        tracker.set_budget("mod_j", max_rss=10000, max_heap=500)
        tracker.snapshot("mod_j", rss=100, heap=1000)
        result = tracker.check_budget("mod_j")
        assert result["status"] == "over"

    def test_check_budget_no_budget_returns_within(self, tracker):
        tracker.snapshot("mod_k", rss=99999)
        result = tracker.check_budget("mod_k")
        assert result["status"] == "within"
        assert result["reason"] == "no_budget_defined"

    def test_check_budget_no_snapshots_returns_within(self, tracker):
        tracker.set_budget("mod_l", max_rss=1000)
        result = tracker.check_budget("mod_l")
        assert result["status"] == "within"
        assert result["reason"] == "no_snapshots"

    def test_check_budget_zero_limit_never_triggers(self, tracker):
        tracker.set_budget("mod_z", max_rss=0, max_heap=0)
        tracker.snapshot("mod_z", rss=999999, heap=999999)
        result = tracker.check_budget("mod_z")
        assert result["status"] == "within"


# ---------------------------------------------------------------------------
# Leak detection
# ---------------------------------------------------------------------------

class TestLeakDetection:
    def test_insufficient_data(self, tracker):
        tracker.snapshot("leak_a", rss=100)
        result = tracker.detect_leaks("leak_a")
        assert result["leak_suspected"] is False
        assert result["reason"] == "insufficient_data"

    def test_no_leak_stable_rss(self, tracker):
        for i in range(5):
            tracker.snapshot("leak_b", rss=1000)
        result = tracker.detect_leaks("leak_b")
        assert result["leak_suspected"] is False

    def test_leak_detected_growing_rss(self, tracker):
        for i in range(5):
            tracker.snapshot("leak_c", rss=1000 + i * 500)
        result = tracker.detect_leaks("leak_c")
        assert result["leak_suspected"] is True
        assert result["trend_rss_delta"] > 0

    def test_leak_from_zero_rss(self, tracker):
        tracker.snapshot("leak_d", rss=0)
        tracker.snapshot("leak_d", rss=100)
        result = tracker.detect_leaks("leak_d")
        assert result["leak_suspected"] is True

    def test_detect_leaks_respects_window(self, tracker):
        # First 5 are stable, last 5 grow
        for i in range(5):
            tracker.snapshot("leak_e", rss=1000)
        for i in range(5):
            tracker.snapshot("leak_e", rss=1000 + i * 500)
        # Window=5 only looks at the growing part
        result = tracker.detect_leaks("leak_e", window=5)
        assert result["window_size"] == 5


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class TestMemoryFootprintEvents:
    def test_snapshot_emits_event(self, tracker, bus):
        tracker.snapshot("ev_mod", rss=100)
        topics = [e.topic for e in bus._captured]
        assert "efficiency.memory_footprint.snapshotted" in topics

    def test_set_budget_emits_event(self, tracker, bus):
        tracker.set_budget("ev_bud", max_rss=5000)
        topics = [e.topic for e in bus._captured]
        assert "efficiency.memory_footprint.budget_set" in topics

    def test_check_budget_over_emits_event(self, tracker, bus):
        tracker.set_budget("ev_chk", max_rss=100)
        tracker.snapshot("ev_chk", rss=500)
        tracker.check_budget("ev_chk")
        topics = [e.topic for e in bus._captured]
        assert "efficiency.memory_footprint.budget_checked" in topics
