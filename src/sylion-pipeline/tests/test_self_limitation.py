"""
Tests for sylion.aeis.self_limitation — SelfLimitationEngine

Covers: register_policy, check_rate, record_action, get_usage, get_violations,
throttle, get_stats, reset_all, thread safety, singleton, edge cases.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.aeis.self_limitation import (
    SelfLimitationEngine,
    get_self_limitation_engine,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """Fresh in-memory engine per test."""
    return SelfLimitationEngine(db_path=":memory:")


@pytest.fixture
def engine_with_bus():
    """Engine with a real EventBus for event emission testing."""
    bus = EventBus(db_path=":memory:")
    eng = SelfLimitationEngine(db_path=":memory:", event_bus=bus)
    return eng, bus


# ---------------------------------------------------------------------------
# 1. Initialization & table creation
# ---------------------------------------------------------------------------

class TestInit:
    def test_in_memory_default(self):
        eng = SelfLimitationEngine()
        assert eng._db_path == ":memory:"

    def test_custom_db_path(self, tmp_path):
        db = tmp_path / "test_limit.db"
        eng = SelfLimitationEngine(db_path=str(db))
        assert eng._db_path == str(db)

    def test_wal_mode_on_file_db(self, tmp_path):
        db = tmp_path / "wal_test.db"
        eng = SelfLimitationEngine(db_path=str(db))
        row = eng._conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] in ("wal", "memory")

    def test_tables_created(self, engine):
        tables = [r[0] for r in engine._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "sylion_rate_policies" in tables
        assert "sylion_rate_events" in tables

    def test_indexes_created(self, engine):
        indexes = [r[0] for r in engine._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()]
        assert any("rate_policy" in idx for idx in indexes)
        assert any("rate_event" in idx for idx in indexes)

    def test_lock_instance(self, engine):
        assert isinstance(engine._lock, type(threading.Lock()))


# ---------------------------------------------------------------------------
# 2. register_policy
# ---------------------------------------------------------------------------

class TestRegisterPolicy:
    def test_basic_registration(self, engine):
        result = engine.register_policy(
            "p1", "api.call", max_calls=10, window_seconds=60.0
        )
        assert result["policy_id"] == "p1"
        assert result["scope"] == "api.call"
        assert result["max_calls"] == 10
        assert result["window_seconds"] == 60.0
        assert result["action"] == "throttle"

    def test_custom_action(self, engine):
        result = engine.register_policy(
            "p2", "login.attempt", max_calls=5, window_seconds=300, action="block"
        )
        assert result["action"] == "block"

    def test_upsert_replaces_existing(self, engine):
        engine.register_policy("p1", "api.call", 10, 60)
        engine.register_policy("p1", "api.call", 20, 120, action="alert")
        row = engine._conn.execute(
            "SELECT * FROM sylion_rate_policies WHERE policy_id='p1'"
        ).fetchone()
        assert row["max_calls"] == 20
        assert row["window_seconds"] == 120
        assert row["action"] == "alert"

    def test_multiple_policies_different_scopes(self, engine):
        engine.register_policy("p1", "api.call", 10, 60)
        engine.register_policy("p2", "login.attempt", 5, 300)
        rows = engine._conn.execute(
            "SELECT * FROM sylion_rate_policies ORDER BY policy_id"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["scope"] == "api.call"
        assert rows[1]["scope"] == "login.attempt"

    def test_created_at_set(self, engine):
        before = time.time()
        engine.register_policy("p1", "test", 1, 1)
        after = time.time()
        row = engine._conn.execute(
            "SELECT created_at FROM sylion_rate_policies WHERE policy_id='p1'"
        ).fetchone()
        assert before <= row["created_at"] <= after

    def test_emits_event(self, engine_with_bus):
        engine, bus = engine_with_bus
        captured = []
        bus.subscribe("aeis.self_limitation.policy_registered",
                       lambda e: captured.append(e))
        engine.register_policy("p1", "api.call", 10, 60)
        assert len(captured) == 1
        assert captured[0].payload["policy_id"] == "p1"
        assert captured[0].payload["scope"] == "api.call"


# ---------------------------------------------------------------------------
# 3. check_rate
# ---------------------------------------------------------------------------

class TestCheckRate:
    def test_no_policy_allows(self, engine):
        result = engine.check_rate("unknown.scope", "user1")
        assert result["allowed"] is True
        assert result["remaining"] == -1

    def test_within_limits(self, engine):
        engine.register_policy("p1", "api.call", 10, 60)
        result = engine.check_rate("api.call", "user1")
        assert result["allowed"] is True
        assert result["remaining"] == 10

    def test_remaining_decreases(self, engine):
        engine.register_policy("p1", "api.call", 5, 60)
        for i in range(3):
            engine.record_action("api.call", "user1", "req", "ok")
        result = engine.check_rate("api.call", "user1")
        assert result["allowed"] is True
        assert result["remaining"] == 2

    def test_at_limit_not_allowed(self, engine):
        engine.register_policy("p1", "api.call", 3, 60)
        for _ in range(3):
            engine.record_action("api.call", "user1", "req", "ok")
        result = engine.check_rate("api.call", "user1")
        assert result["allowed"] is False
        assert result["remaining"] == 0

    def test_reset_at_in_future(self, engine):
        engine.register_policy("p1", "api.call", 10, 60)
        before = time.time()
        result = engine.check_rate("api.call", "user1")
        assert result["reset_at"] >= before

    def test_different_identifiers_independent(self, engine):
        engine.register_policy("p1", "api.call", 2, 60)
        engine.record_action("api.call", "user1", "req", "ok")
        engine.record_action("api.call", "user1", "req", "ok")
        # user1 at limit
        assert engine.check_rate("api.call", "user1")["allowed"] is False
        # user2 still fine
        assert engine.check_rate("api.call", "user2")["allowed"] is True

    def test_throttle_cooldown_blocks(self, engine):
        engine.register_policy("p1", "api.call", 100, 60)
        engine.throttle("api.call", "user1", 10.0)
        result = engine.check_rate("api.call", "user1")
        assert result["allowed"] is False
        assert result["reset_at"] > time.time()

    def test_expired_cooldown_allows(self, engine):
        engine.register_policy("p1", "api.call", 100, 60)
        engine.throttle("api.call", "user1", 0.0)  # cooldown already expired
        time.sleep(0.01)
        result = engine.check_rate("api.call", "user1")
        assert result["allowed"] is True

    def test_emits_violation_event(self, engine_with_bus):
        engine, bus = engine_with_bus
        engine.register_policy("p1", "api.call", 1, 60)
        engine.record_action("api.call", "user1", "req", "ok")
        captured = []
        bus.subscribe("aeis.self_limitation.rate_violation",
                       lambda e: captured.append(e))
        engine.check_rate("api.call", "user1")
        assert len(captured) == 1
        assert captured[0].payload["scope"] == "api.call"


# ---------------------------------------------------------------------------
# 4. record_action
# ---------------------------------------------------------------------------

class TestRecordAction:
    def test_basic_record(self, engine):
        result = engine.record_action("api.call", "user1", "request", "success")
        assert result["scope"] == "api.call"
        assert result["identifier"] == "user1"
        assert result["is_violation"] is False

    def test_event_id_incremented(self, engine):
        r1 = engine.record_action("scope", "id1", "", "")
        r2 = engine.record_action("scope", "id2", "", "")
        assert r2["event_id"] > r1["event_id"]

    def test_violation_flagged_when_over_limit(self, engine):
        engine.register_policy("p1", "api.call", 2, 60)
        engine.record_action("api.call", "user1", "req", "ok")
        engine.record_action("api.call", "user1", "req", "ok")
        result = engine.record_action("api.call", "user1", "req", "ok")
        assert result["is_violation"] is True

    def test_no_violation_when_under_limit(self, engine):
        engine.register_policy("p1", "api.call", 100, 60)
        result = engine.record_action("api.call", "user1", "req", "ok")
        assert result["is_violation"] is False

    def test_violation_event_emitted(self, engine_with_bus):
        engine, bus = engine_with_bus
        engine.register_policy("p1", "api.call", 1, 60)
        engine.record_action("api.call", "user1", "req", "ok")
        captured = []
        bus.subscribe("aeis.self_limitation.action_violation",
                       lambda e: captured.append(e))
        engine.record_action("api.call", "user1", "req", "blocked")
        assert len(captured) == 1
        assert captured[0].payload["scope"] == "api.call"

    def test_record_without_policy(self, engine):
        result = engine.record_action("no.policy", "user1", "test", "ok")
        assert result["is_violation"] is False

    def test_timestamp_stored(self, engine):
        before = time.time()
        engine.record_action("scope", "id", "", "")
        after = time.time()
        row = engine._conn.execute(
            "SELECT timestamp FROM sylion_rate_events LIMIT 1"
        ).fetchone()
        assert before <= row["timestamp"] <= after


# ---------------------------------------------------------------------------
# 5. get_usage
# ---------------------------------------------------------------------------

class TestGetUsage:
    def test_empty_usage(self, engine):
        assert engine.get_usage("api.call", "user1", 60) == 0

    def test_counts_events_in_window(self, engine):
        for _ in range(5):
            engine.record_action("api.call", "user1", "req", "ok")
        assert engine.get_usage("api.call", "user1", 60) == 5

    def test_different_scopes_independent(self, engine):
        engine.record_action("api.call", "user1", "", "")
        engine.record_action("api.call", "user1", "", "")
        engine.record_action("login.attempt", "user1", "", "")
        assert engine.get_usage("api.call", "user1", 60) == 2
        assert engine.get_usage("login.attempt", "user1", 60) == 1

    def test_different_identifiers_independent(self, engine):
        engine.record_action("api.call", "user1", "", "")
        engine.record_action("api.call", "user2", "", "")
        engine.record_action("api.call", "user2", "", "")
        assert engine.get_usage("api.call", "user1", 60) == 1
        assert engine.get_usage("api.call", "user2", 60) == 2

    def test_window_boundary(self, engine):
        engine.record_action("scope", "id", "", "")
        # Zero window should exclude everything
        time.sleep(0.01)
        assert engine.get_usage("scope", "id", 0.001) == 0


# ---------------------------------------------------------------------------
# 6. get_violations
# ---------------------------------------------------------------------------

class TestGetViolations:
    def test_no_violations(self, engine):
        assert engine.get_violations() == []

    def test_returns_violations_only(self, engine):
        engine.register_policy("p1", "api.call", 1, 60)
        engine.record_action("api.call", "user1", "req", "ok")  # within
        engine.record_action("api.call", "user1", "req", "blocked")  # violation
        violations = engine.get_violations()
        assert len(violations) == 1
        assert violations[0]["is_violation"] == 1

    def test_filter_by_scope(self, engine):
        engine.register_policy("p1", "api.call", 1, 60)
        engine.register_policy("p2", "login", 1, 60)
        engine.record_action("api.call", "user1", "", "")
        engine.record_action("api.call", "user1", "", "")  # violation
        engine.record_action("login", "user1", "", "")
        engine.record_action("login", "user1", "", "")  # violation
        violations = engine.get_violations(scope="api.call")
        assert len(violations) == 1
        assert violations[0]["scope"] == "api.call"

    def test_filter_by_identifier(self, engine):
        engine.register_policy("p1", "api.call", 1, 60)
        engine.record_action("api.call", "user1", "", "")
        engine.record_action("api.call", "user1", "", "")  # violation
        engine.record_action("api.call", "user2", "", "")
        engine.record_action("api.call", "user2", "", "")  # violation
        violations = engine.get_violations(identifier="user1")
        assert len(violations) == 1
        assert violations[0]["identifier"] == "user1"

    def test_limit_parameter(self, engine):
        engine.register_policy("p1", "api.call", 1, 60)
        for i in range(20):
            engine.record_action("api.call", "user1", "", "")
        violations = engine.get_violations(limit=5)
        assert len(violations) == 5


# ---------------------------------------------------------------------------
# 7. throttle
# ---------------------------------------------------------------------------

class TestThrottle:
    def test_basic_throttle(self, engine):
        result = engine.throttle("api.call", "user1", 30.0)
        assert result["scope"] == "api.call"
        assert result["identifier"] == "user1"
        assert result["cooldown_until"] > time.time()

    def test_cooldown_duration(self, engine):
        before = time.time()
        result = engine.throttle("api.call", "user1", 60.0)
        assert result["cooldown_until"] >= before + 59.0
        assert result["cooldown_until"] <= before + 61.0

    def test_throttle_stored_as_event(self, engine):
        engine.throttle("api.call", "user1", 10.0)
        row = engine._conn.execute(
            "SELECT * FROM sylion_rate_events WHERE action='throttle_cooldown'"
        ).fetchone()
        assert row is not None
        assert row["scope"] == "api.call"
        assert row["identifier"] == "user1"

    def test_throttle_affects_check_rate(self, engine):
        engine.register_policy("p1", "api.call", 100, 60)
        engine.throttle("api.call", "user1", 60.0)
        result = engine.check_rate("api.call", "user1")
        assert result["allowed"] is False

    def test_throttle_expiry(self, engine):
        engine.register_policy("p1", "api.call", 100, 60)
        engine.throttle("api.call", "user1", 0.001)
        time.sleep(0.01)
        result = engine.check_rate("api.call", "user1")
        assert result["allowed"] is True

    def test_emits_throttle_event(self, engine_with_bus):
        engine, bus = engine_with_bus
        captured = []
        bus.subscribe("aeis.self_limitation.throttle_applied",
                       lambda e: captured.append(e))
        engine.throttle("api.call", "user1", 30.0)
        assert len(captured) == 1
        assert captured[0].payload["cooldown_seconds"] == 30.0


# ---------------------------------------------------------------------------
# 8. get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty_stats(self, engine):
        stats = engine.get_stats()
        assert stats["total_policies"] == 0
        assert stats["total_actions"] == 0
        assert stats["violation_count"] == 0
        assert stats["top_scopes"] == {}

    def test_policies_counted(self, engine):
        engine.register_policy("p1", "s1", 10, 60)
        engine.register_policy("p2", "s2", 5, 30)
        assert engine.get_stats()["total_policies"] == 2

    def test_actions_counted(self, engine):
        engine.record_action("s1", "id1", "", "")
        engine.record_action("s2", "id2", "", "")
        assert engine.get_stats()["total_actions"] == 2

    def test_violation_count(self, engine):
        engine.register_policy("p1", "api.call", 1, 60)
        engine.record_action("api.call", "u1", "", "")
        engine.record_action("api.call", "u1", "", "")  # violation
        assert engine.get_stats()["violation_count"] == 1

    def test_top_scopes(self, engine):
        for _ in range(5):
            engine.record_action("api.call", "u1", "", "")
        for _ in range(3):
            engine.record_action("login", "u1", "", "")
        stats = engine.get_stats()
        assert stats["top_scopes"]["api.call"] == 5
        assert stats["top_scopes"]["login"] == 3


# ---------------------------------------------------------------------------
# 9. reset_all
# ---------------------------------------------------------------------------

class TestResetAll:
    def test_clears_events(self, engine):
        engine.record_action("s1", "id1", "", "")
        engine.record_action("s2", "id2", "", "")
        result = engine.reset_all()
        assert result["deleted_events"] == 2
        assert engine.get_stats()["total_actions"] == 0

    def test_preserves_policies(self, engine):
        engine.register_policy("p1", "api.call", 10, 60)
        engine.record_action("api.call", "user1", "", "")
        engine.reset_all()
        assert engine.get_stats()["total_policies"] == 1
        assert engine.get_stats()["total_actions"] == 0

    def test_empty_reset(self, engine):
        result = engine.reset_all()
        assert result["deleted_events"] == 0

    def test_emits_reset_event(self, engine_with_bus):
        engine, bus = engine_with_bus
        captured = []
        bus.subscribe("aeis.self_limitation.reset",
                       lambda e: captured.append(e))
        engine.reset_all()
        assert len(captured) == 1


# ---------------------------------------------------------------------------
# 10. Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_record_actions(self, engine):
        engine.register_policy("p1", "api.call", 1000, 60)
        errors = []

        def worker():
            try:
                for _ in range(50):
                    engine.record_action("api.call", "thread_user", "req", "ok")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert engine.get_usage("api.call", "thread_user", 60) == 200

    def test_concurrent_register_policies(self, engine):
        errors = []

        def worker(i):
            try:
                engine.register_policy(f"p_{i}", f"scope_{i}", 10, 60)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert engine.get_stats()["total_policies"] == 20

    def test_concurrent_check_and_record(self, engine):
        engine.register_policy("p1", "api.call", 500, 60)
        errors = []

        def checker():
            try:
                for _ in range(30):
                    engine.check_rate("api.call", "user1")
            except Exception as e:
                errors.append(e)

        def recorder():
            try:
                for _ in range(30):
                    engine.record_action("api.call", "user1", "req", "ok")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=checker),
            threading.Thread(target=recorder),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_throttle(self, engine):
        errors = []

        def worker(i):
            try:
                engine.throttle("api.call", f"user_{i}", 10.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# 11. Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_instance(self):
        eng = get_self_limitation_engine(db_path=":memory:")
        assert isinstance(eng, SelfLimitationEngine)

    def test_singleton_returns_same(self):
        # Reset singleton for test isolation
        import sylion.aeis.self_limitation as mod
        mod._engine = None
        eng1 = get_self_limitation_engine(db_path=":memory:")
        eng2 = get_self_limitation_engine()
        assert eng1 is eng2
        # Cleanup
        mod._engine = None


# ---------------------------------------------------------------------------
# 12. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_max_calls(self, engine):
        engine.register_policy("p1", "strict", max_calls=0, window_seconds=60)
        result = engine.check_rate("strict", "user1")
        assert result["allowed"] is False

    def test_very_large_window(self, engine):
        engine.register_policy("p1", "long", max_calls=1000, window_seconds=999999)
        result = engine.check_rate("long", "user1")
        assert result["allowed"] is True

    def test_single_call_policy(self, engine):
        engine.register_policy("p1", "once", max_calls=1, window_seconds=60)
        engine.record_action("once", "user1", "req", "ok")
        assert engine.check_rate("once", "user1")["allowed"] is False

    def test_scope_isolation(self, engine):
        engine.register_policy("p1", "scope_a", 1, 60)
        engine.record_action("scope_a", "user1", "", "")
        engine.record_action("scope_a", "user1", "", "")  # violation
        # Different scope unaffected
        assert engine.get_usage("scope_b", "user1", 60) == 0

    def test_multiple_policies_same_scope_replaces(self, engine):
        engine.register_policy("p1", "api.call", 10, 60)
        engine.register_policy("p2", "api.call", 5, 30)
        # check_rate only uses first policy found
        result = engine.check_rate("api.call", "user1")
        # Both policies exist for same scope; check_rate uses first match
        assert result["allowed"] is True

    def test_record_action_with_special_chars(self, engine):
        result = engine.record_action("api/call", "user@example.com", "req", "ok")
        assert result["is_violation"] is False

    def test_violation_with_throttle_interaction(self, engine):
        engine.register_policy("p1", "api.call", 5, 60)
        engine.throttle("api.call", "user1", 10.0)
        result = engine.check_rate("api.call", "user1")
        assert result["allowed"] is False
        # Even though no actions were recorded
        assert engine.get_usage("api.call", "user1", 60) == 0

    def test_window_expiry(self, engine):
        engine.register_policy("p1", "fast", max_calls=1, window_seconds=0.01)
        engine.record_action("fast", "user1", "req", "ok")
        # Immediately at limit
        assert engine.check_rate("fast", "user1")["allowed"] is False
        # Wait for window to expire
        time.sleep(0.02)
        assert engine.get_usage("fast", "user1", 0.01) == 0
        assert engine.check_rate("fast", "user1")["allowed"] is True

    def test_stats_after_mixed_operations(self, engine):
        engine.register_policy("p1", "api.call", 2, 60)
        engine.record_action("api.call", "u1", "req", "ok")
        engine.record_action("api.call", "u1", "req", "ok")
        engine.record_action("api.call", "u1", "req", "blocked")  # violation
        engine.throttle("api.call", "u2", 30.0)
        engine.record_action("login", "u1", "req", "ok")

        stats = engine.get_stats()
        assert stats["total_policies"] == 1
        assert stats["total_actions"] == 5  # 3 api + 1 throttle + 1 login
        assert stats["violation_count"] == 1
        assert "api.call" in stats["top_scopes"]
        assert "login" in stats["top_scopes"]

    def test_reset_then_reuse(self, engine):
        engine.register_policy("p1", "api.call", 10, 60)
        engine.record_action("api.call", "u1", "", "")
        engine.reset_all()
        # Can record again after reset
        engine.record_action("api.call", "u1", "", "")
        assert engine.get_stats()["total_actions"] == 1
