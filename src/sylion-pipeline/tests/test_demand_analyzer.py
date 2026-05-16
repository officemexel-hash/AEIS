"""Tests for sylion.skills.demand_analyzer — SkillDemandAnalyzer."""
import threading
import time

import pytest

from sylion.skills.demand_analyzer import (
    SkillDemandAnalyzer,
    get_skill_demand_analyzer,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def da():
    """Fresh SkillDemandAnalyzer per test (in-memory)."""
    return SkillDemandAnalyzer(db_path=":memory:")


@pytest.fixture
def da_with_bus(event_bus):
    """SkillDemandAnalyzer wired to a real EventBus."""
    return SkillDemandAnalyzer(db_path=":memory:", event_bus=event_bus)


# ===========================================================================
# 1. Initialization & schema
# ===========================================================================

class TestInit:
    def test_default_in_memory(self, da):
        assert da._db_path == ":memory:"

    def test_tables_created(self, da):
        rows = da._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('sylion_demand_signals','sylion_skill_demand')"
        ).fetchall()
        names = {r["name"] for r in rows}
        assert "sylion_demand_signals" in names
        assert "sylion_skill_demand" in names

    def test_indexes_created(self, da):
        rows = da._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='sylion_demand_signals'"
        ).fetchall()
        names = {r["name"] for r in rows}
        assert "idx_ds_skill" in names
        assert "idx_ds_source" in names
        assert "idx_ds_recorded" in names

    def test_wal_mode_for_file_db(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        da = SkillDemandAnalyzer(db_path=db_file)
        mode = da._conn.execute("PRAGMA journal_mode").fetchone()["journal_mode"]
        assert mode == "wal"


# ===========================================================================
# 2. record_signal
# ===========================================================================

class TestRecordSignal:
    def test_record_basic(self, da):
        result = da.record_signal("sk-1", "user_request", 5.0)
        assert result["skill_id"] == "sk-1"
        assert result["demand_score"] == 5.0
        assert "signal_id" in result

    def test_record_default_score(self, da):
        result = da.record_signal("sk-2", "api")
        assert result["demand_score"] == 1.0

    def test_record_with_context(self, da):
        ctx = {"region": "eu", "urgency": "high"}
        result = da.record_signal("sk-3", "monitor", 3.0, context=ctx)
        assert result["skill_id"] == "sk-3"

    def test_record_multiple_signals_same_skill(self, da):
        da.record_signal("sk-1", "s1", 2.0)
        da.record_signal("sk-1", "s2", 4.0)
        da.record_signal("sk-1", "s3", 6.0)
        demand = da.get_demand("sk-1")
        assert demand is not None
        assert demand["signal_count"] == 3
        assert demand["total_score"] == pytest.approx(12.0)
        assert demand["avg_score"] == pytest.approx(4.0)

    def test_record_signal_count_in_db(self, da):
        da.record_signal("sk-a", "src", 1.0)
        da.record_signal("sk-b", "src", 2.0)
        cnt = da._conn.execute(
            "SELECT COUNT(*) AS c FROM sylion_demand_signals"
        ).fetchone()["c"]
        assert cnt == 2

    def test_record_updates_last_seen(self, da):
        da.record_signal("sk-x", "s", 1.0)
        t1 = da.get_demand("sk-x")["last_seen"]
        time.sleep(0.01)
        da.record_signal("sk-x", "s", 2.0)
        t2 = da.get_demand("sk-x")["last_seen"]
        assert t2 >= t1


# ===========================================================================
# 3. get_demand
# ===========================================================================

class TestGetDemand:
    def test_returns_none_for_unknown(self, da):
        assert da.get_demand("nonexistent") is None

    def test_returns_aggregate(self, da):
        da.record_signal("sk-1", "a", 3.0)
        da.record_signal("sk-1", "b", 7.0)
        d = da.get_demand("sk-1")
        assert d["skill_id"] == "sk-1"
        assert d["signal_count"] == 2
        assert d["total_score"] == pytest.approx(10.0)
        assert d["avg_score"] == pytest.approx(5.0)

    def test_demand_has_timestamps(self, da):
        da.record_signal("sk-t", "s", 1.0)
        d = da.get_demand("sk-t")
        assert d["first_seen"] > 0
        assert d["last_seen"] >= d["first_seen"]


# ===========================================================================
# 4. get_trending_skills
# ===========================================================================

class TestTrending:
    def test_empty_returns_empty(self, da):
        assert da.get_trending_skills() == []

    def test_trending_returns_skill(self, da):
        da.record_signal("sk-hot", "s", 5.0)
        trending = da.get_trending_skills(limit=10)
        assert len(trending) >= 1
        assert trending[0]["skill_id"] == "sk-hot"

    def test_trending_respects_limit(self, da):
        for i in range(20):
            da.record_signal(f"sk-{i}", "s", float(i))
        trending = da.get_trending_skills(limit=5)
        assert len(trending) <= 5

    def test_trending_has_growth_fields(self, da):
        da.record_signal("sk-g", "s", 3.0)
        trending = da.get_trending_skills(limit=10)
        t = trending[0]
        assert "growth" in t
        assert "growth_rate" in t
        assert "recent_count" in t
        assert "older_count" in t
        assert "recent_score" in t

    def test_trending_with_historical_data(self, da):
        now = time.time()
        # Insert old signal (14 days ago)
        da._conn.execute(
            "INSERT INTO sylion_demand_signals (signal_id, skill_id, source, demand_score, context, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("sig-old", "sk-rising", "s", 1.0, '{}', now - 14 * 86400),
        )
        da._conn.execute(
            "INSERT INTO sylion_skill_demand (skill_id, total_score, signal_count, avg_score, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("sk-rising", 1.0, 1, 1.0, now - 14 * 86400, now - 14 * 86400),
        )
        da._conn.commit()
        # Recent signal
        da.record_signal("sk-rising", "s", 5.0)
        trending = da.get_trending_skills(limit=10)
        found = [t for t in trending if t["skill_id"] == "sk-rising"]
        assert len(found) >= 1
        assert found[0]["growth"] >= 0


# ===========================================================================
# 5. get_gap_analysis
# ===========================================================================

class TestGapAnalysis:
    def test_empty_returns_empty(self, da):
        assert da.get_gap_analysis() == []

    def test_gap_with_high_demand_zero_supply(self, da):
        da.record_signal("sk-gap", "s", 10.0)
        da.set_published_count("sk-gap", 0)
        gaps = da.get_gap_analysis()
        assert len(gaps) >= 1
        g = gaps[0]
        assert g["skill_id"] == "sk-gap"
        assert g["published_count"] == 0
        assert g["gap_ratio"] == pytest.approx(10.0)

    def test_gap_with_supply_no_demand(self, da):
        da.record_signal("sk-ok", "s", 2.0)
        da.set_published_count("sk-ok", 10)
        gaps = da.get_gap_analysis()
        ok_entries = [g for g in gaps if g["skill_id"] == "sk-ok"]
        assert len(ok_entries) == 1
        assert ok_entries[0]["gap_ratio"] == pytest.approx(0.2)

    def test_gap_sorted_by_ratio_desc(self, da):
        da.record_signal("sk-lo", "s", 2.0)
        da.set_published_count("sk-lo", 10)
        da.record_signal("sk-hi", "s", 20.0)
        da.set_published_count("sk-hi", 0)
        gaps = da.get_gap_analysis()
        assert gaps[0]["skill_id"] == "sk-hi"
        assert gaps[1]["skill_id"] == "sk-lo"

    def test_gap_has_required_fields(self, da):
        da.record_signal("sk-f", "s", 5.0)
        gaps = da.get_gap_analysis()
        g = gaps[0]
        for key in ("skill_id", "total_score", "signal_count", "avg_score",
                     "published_count", "gap_ratio"):
            assert key in g


# ===========================================================================
# 6. predict_demand
# ===========================================================================

class TestPredictDemand:
    def test_no_data_returns_zero(self, da):
        pred = da.predict_demand("sk-none")
        assert pred["predicted_score"] == 0.0
        assert pred["data_points"] == 0

    def test_single_data_point(self, da):
        da.record_signal("sk-one", "s", 5.0)
        pred = da.predict_demand("sk-one", horizon_days=10)
        assert pred["data_points"] == 1
        assert pred["predicted_score"] > 0
        assert pred["slope"] == 0.0

    def test_multiple_points_prediction(self, da):
        for i in range(10):
            da.record_signal("sk-multi", "s", float(i + 1))
        pred = da.predict_demand("sk-multi", horizon_days=7)
        assert pred["data_points"] == 10
        assert pred["predicted_score"] >= 0
        assert pred["current_daily_avg"] > 0

    def test_prediction_respects_horizon(self, da):
        da.record_signal("sk-hz", "s", 10.0)
        pred_7 = da.predict_demand("sk-hz", horizon_days=7)
        pred_30 = da.predict_demand("sk-hz", horizon_days=30)
        assert pred_30["horizon_days"] == 30
        assert pred_7["horizon_days"] == 7

    def test_prediction_negative_clamped_to_zero(self, da):
        """Predicted score should never be negative."""
        # Insert a decreasing trend
        now = time.time()
        for day in range(20, 0, -1):
            ts = now - day * 86400
            da._conn.execute(
                "INSERT INTO sylion_demand_signals "
                "(signal_id, skill_id, source, demand_score, context, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f"sig-dec-{day}", "sk-dec", "s", 0.1, '{}', ts),
            )
        da._conn.commit()
        # Ensure skill_demand row exists
        da._conn.execute(
            "INSERT OR IGNORE INTO sylion_skill_demand "
            "(skill_id, total_score, signal_count, avg_score, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("sk-dec", 2.0, 20, 0.1, now - 20 * 86400, now),
        )
        da._conn.commit()
        pred = da.predict_demand("sk-dec", horizon_days=30)
        assert pred["predicted_score"] >= 0.0

    def test_prediction_with_custom_horizon(self, da):
        da.record_signal("sk-ch", "s", 3.0)
        pred = da.predict_demand("sk-ch", horizon_days=90)
        assert pred["horizon_days"] == 90


# ===========================================================================
# 7. get_stats
# ===========================================================================

class TestGetStats:
    def test_empty_stats(self, da):
        stats = da.get_stats()
        assert stats["total_signals"] == 0
        assert stats["unique_skills"] == 0
        assert stats["average_demand"] == 0.0

    def test_stats_after_records(self, da):
        da.record_signal("sk-1", "api", 5.0)
        da.record_signal("sk-2", "user", 3.0)
        da.record_signal("sk-1", "api", 7.0)
        stats = da.get_stats()
        assert stats["total_signals"] == 3
        assert stats["unique_skills"] == 2
        assert stats["average_demand"] > 0

    def test_stats_total_demand_score(self, da):
        da.record_signal("sk-ts", "s", 4.0)
        da.record_signal("sk-ts", "s", 6.0)
        stats = da.get_stats()
        assert stats["total_demand_score"] == pytest.approx(10.0)

    def test_stats_by_source(self, da):
        da.record_signal("sk-s", "api", 1.0)
        da.record_signal("sk-s", "ui", 2.0)
        da.record_signal("sk-s", "api", 3.0)
        stats = da.get_stats()
        assert "api" in stats["by_source"]
        assert stats["by_source"]["api"]["count"] == 2
        assert "ui" in stats["by_source"]


# ===========================================================================
# 8. EventBus integration
# ===========================================================================

class TestEventBusIntegration:
    def test_record_emits_event(self, da_with_bus):
        events = []
        da_with_bus._event_bus.subscribe("skill.demand.signal_recorded", events.append)
        da_with_bus.record_signal("sk-ev", "test", 5.0)
        assert len(events) == 1
        assert events[0].payload["skill_id"] == "sk-ev"
        assert events[0].payload["demand_score"] == 5.0

    def test_event_source_module(self, da_with_bus):
        events = []
        da_with_bus._event_bus.subscribe("*", events.append)
        da_with_bus.record_signal("sk-src", "s", 1.0)
        assert events[0].source_module == "skills.demand_analyzer"

    def test_no_event_bus_no_error(self, da):
        # Should not raise even without event bus
        da.record_signal("sk-noev", "s", 1.0)


# ===========================================================================
# 9. Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_record(self, da):
        errors = []

        def writer(skill_id, count):
            try:
                for i in range(count):
                    da.record_signal(skill_id, f"thread-{skill_id}", 1.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(f"sk-t{i}", 20))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = da.get_stats()
        assert stats["total_signals"] == 100
        assert stats["unique_skills"] == 5

    def test_concurrent_read_write(self, da):
        da.record_signal("sk-rw", "s", 1.0)
        errors = []

        def reader():
            try:
                for _ in range(20):
                    da.get_demand("sk-rw")
                    da.get_stats()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(20):
                    da.record_signal("sk-rw", "s", 1.0)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ===========================================================================
# 10. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_skill_demand_analyzer_returns_instance(self):
        # Reset singleton
        import sylion.skills.demand_analyzer as mod
        mod._analyzer = None
        a = get_skill_demand_analyzer(db_path=":memory:")
        assert isinstance(a, SkillDemandAnalyzer)

    def test_singleton_same_instance(self):
        import sylion.skills.demand_analyzer as mod
        mod._analyzer = None
        a1 = get_skill_demand_analyzer(db_path=":memory:")
        a2 = get_skill_demand_analyzer()
        assert a1 is a2
        # Cleanup
        mod._analyzer = None


# ===========================================================================
# 11. Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_zero_demand_score(self, da):
        da.record_signal("sk-zero", "s", 0.0)
        d = da.get_demand("sk-zero")
        assert d["total_score"] == 0.0
        assert d["signal_count"] == 1

    def test_negative_demand_score(self, da):
        da.record_signal("sk-neg", "s", -2.0)
        d = da.get_demand("sk-neg")
        assert d["total_score"] == pytest.approx(-2.0)

    def test_large_demand_score(self, da):
        da.record_signal("sk-big", "s", 1e9)
        d = da.get_demand("sk-big")
        assert d["total_score"] == pytest.approx(1e9)

    def test_empty_skill_id(self, da):
        result = da.record_signal("", "s", 1.0)
        assert result["skill_id"] == ""

    def test_special_chars_in_source(self, da):
        result = da.record_signal("sk-sp", "source/with'special\"chars", 1.0)
        assert result["skill_id"] == "sk-sp"

    def test_context_none_becomes_empty_dict(self, da):
        da.record_signal("sk-ctx", "s", 1.0, context=None)
        row = da._conn.execute(
            "SELECT context FROM sylion_demand_signals WHERE skill_id='sk-ctx'"
        ).fetchone()
        assert row["context"] == "{}"

    def test_set_published_count_nonexistent_skill(self, da):
        # Should not raise, just no-op
        da.set_published_count("ghost", 5)

    def test_many_skills_gap_analysis(self, da):
        for i in range(50):
            da.record_signal(f"sk-many-{i}", "s", float(i))
            da.set_published_count(f"sk-many-{i}", max(1, i))
        gaps = da.get_gap_analysis()
        assert len(gaps) == 50
