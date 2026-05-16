"""Tests for SelfPreservationEngine -- self-preservation and safety shutdown.

22 tests covering check_health, get/set mode, get_health_score, get_checks,
should_shutdown, get_stats, thread safety, singleton, and EventBus integration.
"""

import threading
import time

import pytest

from sylion.aeis.self_preservation import (
    SelfPreservationEngine,
    get_self_preservation_engine,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh in-memory EventBus capturing events."""
    eb = EventBus()
    eb._captured: list[SylionEvent] = []
    eb.subscribe("*", lambda e: eb._captured.append(e))
    return eb


@pytest.fixture
def eng(bus):
    """Fresh in-memory SelfPreservationEngine with EventBus."""
    return SelfPreservationEngine(event_bus=bus)


@pytest.fixture
def eng_no_bus():
    """Fresh in-memory SelfPreservationEngine without EventBus."""
    return SelfPreservationEngine()


# ===================================================================
# Initialization
# ===================================================================

class TestInit:
    def test_default_memory_db(self, eng_no_bus):
        assert eng_no_bus._db_path == ":memory:"

    def test_custom_db_path(self, tmp_path):
        db = tmp_path / "sp.db"
        e = SelfPreservationEngine(db_path=str(db))
        assert e._db_path == str(db)

    def test_tables_created(self, eng_no_bus):
        tables = eng_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "preservation_state" in names
        assert "health_checks" in names

    def test_indexes_created(self, eng_no_bus):
        indexes = eng_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        names = {r["name"] for r in indexes}
        assert "idx_hc_component" in names
        assert "idx_hc_ts" in names

    def test_initial_state_normal(self, eng_no_bus):
        assert eng_no_bus.get_mode() == "normal"

    def test_initial_health_score(self, eng_no_bus):
        assert eng_no_bus.get_health_score() == 1.0

    def test_has_lock(self, eng_no_bus):
        assert isinstance(eng_no_bus._lock, type(threading.Lock()))

    def test_wal_mode_for_file_db(self, tmp_path):
        db = tmp_path / "wal_test.db"
        e = SelfPreservationEngine(db_path=str(db))
        mode = e._conn.execute("PRAGMA journal_mode").fetchone()["journal_mode"]
        assert mode == "wal"


# ===================================================================
# check_health
# ===================================================================

class TestCheckHealth:
    def test_check_returns_result(self, eng):
        result = eng.check_health("db", status="healthy", score=0.95)
        assert result["check_id"]
        assert result["component"] == "db"
        assert result["status"] == "healthy"
        assert result["score"] == 0.95

    def test_check_stored_in_db(self, eng):
        r = eng.check_health("api", status="degraded", message="Slow", score=0.6)
        row = eng._conn.execute(
            "SELECT * FROM health_checks WHERE check_id = ?",
            (r["check_id"],),
        ).fetchone()
        assert row is not None
        assert row["component"] == "api"
        assert row["status"] == "degraded"
        assert row["message"] == "Slow"
        assert row["score"] == 0.6

    def test_check_updates_health_score(self, eng):
        eng.check_health("comp_a", score=0.8)
        eng.check_health("comp_b", score=0.6)
        score = eng.get_health_score()
        assert abs(score - 0.7) < 0.01

    def test_check_emits_event(self, eng, bus):
        eng.check_health("db", status="healthy", score=1.0)
        events = [e for e in bus._captured
                  if e.topic == "aeis.self_preservation.health_checked"]
        assert len(events) == 1
        assert events[0].payload["component"] == "db"
        assert events[0].payload["status"] == "healthy"

    def test_multiple_checks_same_component(self, eng):
        eng.check_health("db", score=0.5)
        eng.check_health("db", score=0.9)
        # Latest check per component determines score
        score = eng.get_health_score()
        assert abs(score - 0.9) < 0.01

    def test_check_default_status_healthy(self, eng):
        r = eng.check_health("comp")
        assert r["status"] == "healthy"

    def test_check_default_score_1(self, eng):
        r = eng.check_health("comp")
        assert r["score"] == 1.0


# ===================================================================
# Mode management
# ===================================================================

class TestModeManagement:
    def test_get_initial_mode(self, eng):
        assert eng.get_mode() == "normal"

    def test_set_mode_caution(self, eng):
        result = eng.set_mode("caution")
        assert result["mode"] == "caution"
        assert eng.get_mode() == "caution"

    def test_set_mode_critical(self, eng):
        eng.set_mode("critical")
        assert eng.get_mode() == "critical"

    def test_set_mode_shutdown(self, eng):
        eng.set_mode("shutdown")
        assert eng.get_mode() == "shutdown"

    def test_set_mode_normal_restore(self, eng):
        eng.set_mode("caution")
        eng.set_mode("normal")
        assert eng.get_mode() == "normal"

    def test_invalid_mode_raises(self, eng):
        with pytest.raises(ValueError, match="Invalid mode"):
            eng.set_mode("unknown")

    def test_set_mode_emits_event(self, eng, bus):
        eng.set_mode("caution")
        events = [e for e in bus._captured
                  if e.topic == "aeis.self_preservation.mode_changed"]
        assert len(events) == 1
        assert events[0].payload["mode"] == "caution"


# ===================================================================
# Health score
# ===================================================================

class TestHealthScore:
    def test_initial_score_1(self, eng):
        assert eng.get_health_score() == 1.0

    def test_single_component(self, eng):
        eng.check_health("comp", score=0.75)
        assert abs(eng.get_health_score() - 0.75) < 0.01

    def test_multiple_components_averages_latest(self, eng):
        eng.check_health("a", score=0.8)
        eng.check_health("b", score=0.6)
        score = eng.get_health_score()
        assert abs(score - 0.7) < 0.01

    def test_score_uses_latest_per_component(self, eng):
        eng.check_health("a", score=0.4)
        eng.check_health("a", score=0.9)
        eng.check_health("b", score=0.5)
        score = eng.get_health_score()
        expected = (0.9 + 0.5) / 2
        assert abs(score - expected) < 0.01


# ===================================================================
# get_checks
# ===================================================================

class TestGetChecks:
    def test_empty_returns_empty(self, eng):
        assert eng.get_checks() == []

    def test_returns_all_checks(self, eng):
        eng.check_health("a")
        eng.check_health("b")
        assert len(eng.get_checks()) == 2

    def test_filter_by_component(self, eng):
        eng.check_health("a")
        eng.check_health("b")
        results = eng.get_checks(component="a")
        assert len(results) == 1
        assert results[0]["component"] == "a"

    def test_limit_works(self, eng):
        for i in range(10):
            eng.check_health(f"comp")
        results = eng.get_checks(limit=3)
        assert len(results) == 3

    def test_ordered_by_timestamp_desc(self, eng):
        eng.check_health("a", score=0.1)
        eng.check_health("a", score=0.9)
        results = eng.get_checks(component="a")
        assert results[0]["score"] == 0.9


# ===================================================================
# should_shutdown
# ===================================================================

class TestShouldShutdown:
    def test_normal_mode_no_shutdown(self, eng):
        assert eng.should_shutdown() is False

    def test_critical_mode_triggers_shutdown(self, eng):
        eng.set_mode("critical")
        assert eng.should_shutdown() is True

    def test_shutdown_mode_triggers_shutdown(self, eng):
        eng.set_mode("shutdown")
        assert eng.should_shutdown() is True

    def test_low_health_triggers_shutdown(self, eng):
        eng.check_health("comp", score=0.2)
        assert eng.should_shutdown() is True

    def test_caution_mode_no_shutdown(self, eng):
        eng.set_mode("caution")
        assert eng.should_shutdown() is False

    def test_above_threshold_no_shutdown(self, eng):
        eng.check_health("comp", score=0.35)
        assert eng.should_shutdown() is False


# ===================================================================
# get_stats
# ===================================================================

class TestGetStats:
    def test_initial_stats(self, eng):
        stats = eng.get_stats()
        assert stats["mode"] == "normal"
        assert stats["health_score"] == 1.0
        assert stats["should_shutdown"] is False
        assert stats["total_checks"] == 0
        assert stats["by_status"] == {}
        assert stats["by_component"] == {}

    def test_stats_after_checks(self, eng):
        eng.check_health("db", status="healthy", score=0.95)
        eng.check_health("api", status="degraded", score=0.6)
        stats = eng.get_stats()
        assert stats["total_checks"] == 2
        assert stats["by_status"]["healthy"] == 1
        assert stats["by_status"]["degraded"] == 1
        assert stats["by_component"]["db"] == 1
        assert stats["by_component"]["api"] == 1

    def test_stats_after_mode_change(self, eng):
        eng.set_mode("caution")
        stats = eng.get_stats()
        assert stats["mode"] == "caution"


# ===================================================================
# Thread safety
# ===================================================================

class TestThreadSafety:
    def test_concurrent_health_checks(self, eng):
        errors = []

        def check(n):
            try:
                eng.check_health(f"comp_{n}", score=0.5 + n * 0.02)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        count = eng._conn.execute("SELECT COUNT(*) as c FROM health_checks").fetchone()
        assert count["c"] == 20

    def test_concurrent_mode_changes(self, eng):
        errors = []
        modes = ["caution", "normal", "critical", "normal", "caution"]

        def set_mode(m):
            try:
                eng.set_mode(m)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=set_mode, args=(modes[i % len(modes)],))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # Final mode should be a valid mode
        assert eng.get_mode() in ("normal", "caution", "critical", "shutdown")


# ===================================================================
# Singleton
# ===================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        import sylion.aeis.self_preservation as mod
        mod._engine = None
        e = get_self_preservation_engine()
        assert isinstance(e, SelfPreservationEngine)
        mod._engine = None

    def test_singleton_returns_same_instance(self):
        import sylion.aeis.self_preservation as mod
        mod._engine = None
        e1 = get_self_preservation_engine()
        e2 = get_self_preservation_engine()
        assert e1 is e2
        mod._engine = None


# ===================================================================
# EventBus integration
# ===================================================================

class TestEventBusIntegration:
    def test_no_bus_no_error(self, eng_no_bus):
        eng_no_bus.check_health("comp", score=0.9)
        eng_no_bus.set_mode("caution")
        # No crash = success

    def test_event_source_module(self, eng, bus):
        eng.check_health("db")
        events = [e for e in bus._captured
                  if e.topic == "aeis.self_preservation.health_checked"]
        assert events[0].source_module == "aeis.self_preservation"

    def test_multiple_events_different_topics(self, eng, bus):
        eng.check_health("db")
        eng.set_mode("caution")
        topics = {e.topic for e in bus._captured}
        assert "aeis.self_preservation.health_checked" in topics
        assert "aeis.self_preservation.mode_changed" in topics
