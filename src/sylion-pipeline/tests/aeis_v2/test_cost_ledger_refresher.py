"""Tests for sylion.aeis_v2.deployment.cost_ledger_refresher — W17 G2 step 3.

Covers:

- Module constants (default interval, initial delay, audit path).
- Daemon thread lifecycle (start spawns thread, stop signals exit).
- The "first refresh blocking, subsequent CONCURRENTLY" guarantee.
- Stats tracking (success / failure counters + average duration).
- Audit JSONL one row per refresh, with the expected schema.
- Graceful handling when the PG pool is unreachable (None).
- Singleton accessor + reset helper.

Tests use SHORT intervals (interval_s=0.05) so the suite still runs
under one second total despite spinning real threads.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from sylion.aeis_v2.deployment import cost_ledger_refresher as refresher_mod
from sylion.aeis_v2.deployment.cost_ledger_refresher import (
    REFRESH_AUDIT_LOG_PATH,
    REFRESH_INITIAL_DELAY_S,
    REFRESH_INTERVAL_S,
    CostLedgerRefresher,
    RefreshStats,
    get_refresher,
    reset_refresher,
)
from sylion.aeis_v2.deployment.cost_ledger_pg import (
    REFRESH_MV_SQL,
    REFRESH_MV_SQL_BLOCKING,
)


# --------------------------------------------------------------------------
# Stubs — psycopg pool/conn/cursor minimal surface, mirroring
# test_cost_ledger_pg._StubPool. Adds an outcome controller so tests can
# force success/failure per refresh attempt deterministically.
# --------------------------------------------------------------------------


class _StubCursor:
    def __init__(self, conn: "_StubConnection") -> None:
        self._conn = conn

    def __enter__(self) -> "_StubCursor":
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN001
        return None

    def execute(self, stmt: str, params=None) -> None:  # noqa: ANN001
        self._conn.executed_sql.append(stmt)
        if self._conn.fail:
            raise RuntimeError("stub PG refresh error")


class _StubConnection:
    def __init__(self, fail: bool = False) -> None:
        self.executed_sql: list[str] = []
        self.fail = fail
        self.committed = False

    def __enter__(self) -> "_StubConnection":
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN001
        return None

    def cursor(self) -> _StubCursor:
        return _StubCursor(self)

    def commit(self) -> None:
        self.committed = True


class _StubPool:
    """Reusable pool with a controllable failure flag.

    Records every executed SQL string so tests can assert which
    REFRESH variant the worker used (blocking vs CONCURRENTLY).
    """

    def __init__(self, fail: bool = False) -> None:
        self.conn = _StubConnection(fail=fail)

    def connection(self) -> _StubConnection:
        # Reuse the same connection so all_calls accumulate across
        # refresh attempts in one test.
        return self.conn

    @property
    def executed_sql(self) -> list[str]:
        return self.conn.executed_sql


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _redirect_audit_path(tmp_path, monkeypatch):
    """Redirect the audit JSONL to ``tmp_path`` so tests don't pollute logs/v2."""
    monkeypatch.setattr(
        refresher_mod, "REFRESH_AUDIT_LOG_PATH",
        tmp_path / "cost_ledger_refresh.jsonl",
    )


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Drop any leaked singleton before AND after each test.

    Ensures previous-test threads are joined and the next test gets a
    pristine ``get_refresher()`` lazy-init.
    """
    reset_refresher()
    yield
    reset_refresher()


@pytest.fixture
def stub_pool() -> _StubPool:
    """Default stub pool — every refresh succeeds."""
    return _StubPool(fail=False)


@pytest.fixture
def make_refresher(monkeypatch):
    """Factory that builds a CostLedgerRefresher wired to a fake pool.

    The factory monkeypatches ``_resolve_pool`` so the worker never
    talks to real PG. Tests can pass a ``pool`` (or None) to control
    the refresh outcome.
    """
    def _factory(
        pool=None,
        *,
        interval_s: float = 0.05,
        initial_delay_s: float = 0.0,
    ) -> CostLedgerRefresher:
        ref = CostLedgerRefresher(
            interval_s=interval_s,
            initial_delay_s=initial_delay_s,
        )
        # Bind the resolver to the per-test pool stub.
        ref._resolve_pool = lambda: pool  # type: ignore[method-assign]
        return ref
    return _factory


def _wait_for(predicate, *, timeout_s: float = 1.0, poll_s: float = 0.005):
    """Spin until ``predicate()`` returns truthy or ``timeout_s`` elapses.

    Returns the final predicate value (truthy on success, falsy on
    timeout). Uses short polls so tests stay fast.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        v = predicate()
        if v:
            return v
        time.sleep(poll_s)
    return predicate()


# --------------------------------------------------------------------------
# 1. Constants smoke
# --------------------------------------------------------------------------


def test_refresher_constants_have_defaults():
    """Module-level defaults are sensible: interval > 0, initial_delay >= 0.

    The audit path lives under ``logs/v2/`` so it co-locates with the
    other v2 audit feeds (cost_ledger.jsonl, routing_audit.jsonl).
    """
    # Defaults can be overridden by env vars; we just check the live
    # values are well-formed (positive interval, non-negative delay).
    assert REFRESH_INTERVAL_S > 0
    assert REFRESH_INITIAL_DELAY_S >= 0
    # Audit path lives in logs/v2/ alongside cost_ledger.jsonl.
    assert REFRESH_AUDIT_LOG_PATH.name == "cost_ledger_refresh.jsonl"
    assert "logs" in REFRESH_AUDIT_LOG_PATH.parts
    assert "v2" in REFRESH_AUDIT_LOG_PATH.parts


# --------------------------------------------------------------------------
# 2. Lifecycle — start spawns thread; stop signals exit
# --------------------------------------------------------------------------


def test_refresher_start_creates_thread(make_refresher, stub_pool):
    """``start()`` spawns a daemon thread that becomes alive within one tick."""
    ref = make_refresher(stub_pool, interval_s=0.05, initial_delay_s=0.0)
    assert not ref.is_running()
    ref.start()
    try:
        # Thread should report alive immediately after start().
        assert _wait_for(ref.is_running, timeout_s=0.5)
        # The internal thread handle is a daemon (so it can't block
        # process shutdown).
        assert ref._thread is not None
        assert ref._thread.daemon is True
        assert ref._thread.name == "cost-ledger-refresher"
    finally:
        ref.stop(timeout_s=1.0)


def test_refresher_stop_signals_thread_exit(make_refresher, stub_pool):
    """``stop()`` returns True when the thread exits within timeout.

    With interval_s=0.05 the worst-case wait is ~50ms; we give 1.0s of
    headroom so CI scheduling jitter doesn't flake the test.
    """
    ref = make_refresher(stub_pool, interval_s=0.05, initial_delay_s=0.0)
    ref.start()
    # Let it tick at least once so we're definitely inside the loop.
    assert _wait_for(
        lambda: ref.stats.total_refreshes >= 1, timeout_s=1.0,
    )
    ok = ref.stop(timeout_s=1.0)
    assert ok is True
    assert not ref.is_running()


# --------------------------------------------------------------------------
# 3. First refresh blocking, subsequent CONCURRENTLY
# --------------------------------------------------------------------------


def test_refresher_first_refresh_uses_blocking_sql(make_refresher, stub_pool):
    """The first attempt MUST use ``REFRESH MATERIALIZED VIEW`` (no CONCURRENTLY).

    A fresh MV doesn't have a populated state yet — CONCURRENTLY would
    raise ``cannot refresh materialized view ... concurrently`` until
    after the first non-concurrent refresh.
    """
    ref = make_refresher(stub_pool, interval_s=10.0, initial_delay_s=0.0)
    ref.start()
    # Wait for the first refresh to land.
    assert _wait_for(
        lambda: ref.stats.total_refreshes >= 1, timeout_s=1.0,
    )
    ref.stop(timeout_s=1.0)
    # First SQL executed must be the blocking variant.
    assert len(stub_pool.executed_sql) >= 1
    assert stub_pool.executed_sql[0] == REFRESH_MV_SQL_BLOCKING
    assert "CONCURRENTLY" not in stub_pool.executed_sql[0]


def test_refresher_subsequent_refreshes_use_concurrently(
    make_refresher, stub_pool,
):
    """After the first refresh completes, every subsequent call uses CONCURRENTLY.

    Drives the loop for at least 2 refreshes (interval 0.02s), then
    asserts the SQL log has [BLOCKING, CONCURRENTLY, CONCURRENTLY, ...].
    """
    ref = make_refresher(stub_pool, interval_s=0.02, initial_delay_s=0.0)
    ref.start()
    # Wait for at least 3 refreshes to make sure we caught >=2 follow-ups.
    assert _wait_for(
        lambda: ref.stats.total_refreshes >= 3, timeout_s=1.5,
    )
    ref.stop(timeout_s=1.0)
    sqls = list(stub_pool.executed_sql)
    assert sqls[0] == REFRESH_MV_SQL_BLOCKING
    # All non-first refreshes must use the CONCURRENTLY form.
    for sql in sqls[1:]:
        assert sql == REFRESH_MV_SQL
        assert "CONCURRENTLY" in sql


# --------------------------------------------------------------------------
# 4. Stats tracking — success and failure counters
# --------------------------------------------------------------------------


def test_refresher_stats_track_success_and_failure(make_refresher):
    """Stats split refreshes into success_count + error_count.

    We toggle the stub's ``fail`` flag mid-run so the worker observes
    both outcomes within one test.
    """
    pool = _StubPool(fail=False)
    ref = make_refresher(pool, interval_s=0.02, initial_delay_s=0.0)
    ref.start()
    # Wait for >=1 successful refresh.
    assert _wait_for(
        lambda: ref.stats.success_count >= 1, timeout_s=1.0,
    )
    # Now flip the pool to fail and wait for the next attempt.
    pool.conn.fail = True
    initial_total = ref.stats.total_refreshes
    assert _wait_for(
        lambda: ref.stats.total_refreshes > initial_total
        and ref.stats.error_count >= 1,
        timeout_s=1.0,
    )
    ref.stop(timeout_s=1.0)

    final = ref.stats
    assert final.success_count >= 1
    assert final.error_count >= 1
    # last_error should reflect the last failure mode.
    assert final.last_error is not None
    # avg_duration_ms is a sane positive float.
    assert final.avg_duration_ms >= 0.0
    # to_dict carries every documented key incl. the derived avg.
    d = final.to_dict()
    assert "avg_duration_ms" in d
    assert "success_count" in d
    assert "error_count" in d
    assert "last_refresh_ts" in d


# --------------------------------------------------------------------------
# 5. Audit JSONL — one row per refresh
# --------------------------------------------------------------------------


def test_refresher_emits_audit_jsonl_per_refresh(
    make_refresher, stub_pool, tmp_path,
):
    """Every refresh attempt appends one well-formed JSON row to the audit log.

    Schema: ``{ts, duration_ms, success, error, concurrently}``.
    """
    ref = make_refresher(stub_pool, interval_s=0.02, initial_delay_s=0.0)
    ref.start()
    assert _wait_for(
        lambda: ref.stats.total_refreshes >= 3, timeout_s=1.5,
    )
    ref.stop(timeout_s=1.0)

    audit_path: Path = refresher_mod.REFRESH_AUDIT_LOG_PATH
    assert audit_path.exists()
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 3

    rows = [json.loads(l) for l in lines]
    for row in rows:
        # Schema check.
        assert set(row.keys()) >= {
            "ts", "duration_ms", "success", "error", "concurrently",
        }
        assert isinstance(row["ts"], (int, float))
        assert isinstance(row["duration_ms"], (int, float))
        assert isinstance(row["success"], bool)
        assert isinstance(row["concurrently"], bool)
    # First row uses concurrently=False (steady-state guard); later rows
    # use concurrently=True.
    assert rows[0]["concurrently"] is False
    assert rows[1]["concurrently"] is True


# --------------------------------------------------------------------------
# 6. Graceful handling when PG is unreachable
# --------------------------------------------------------------------------


def test_refresher_handles_pg_unreachable_gracefully(make_refresher):
    """When ``_resolve_pool()`` returns None the worker records error rows
    but does NOT crash and keeps looping.

    Production failure mode: PG is down briefly during deploy. The cron
    worker must keep ticking so the audit feed shows the gap and stats
    light up the dashboard alert.
    """
    ref = make_refresher(pool=None, interval_s=0.02, initial_delay_s=0.0)
    ref.start()
    assert _wait_for(
        lambda: ref.stats.total_refreshes >= 2, timeout_s=1.0,
    )
    ref.stop(timeout_s=1.0)

    # Every attempt failed with the documented error string.
    final = ref.stats
    assert final.error_count == final.total_refreshes
    assert final.success_count == 0
    assert final.last_error == "pg_unreachable"
    # Audit rows reflect the same failure.
    audit_path: Path = refresher_mod.REFRESH_AUDIT_LOG_PATH
    rows = [
        json.loads(l) for l in
        audit_path.read_text(encoding="utf-8").strip().splitlines()
    ]
    for row in rows:
        assert row["success"] is False
        assert row["error"] == "pg_unreachable"


# --------------------------------------------------------------------------
# 7. Singleton accessor
# --------------------------------------------------------------------------


def test_get_refresher_singleton():
    """``get_refresher()`` returns the same instance across calls until reset."""
    a = get_refresher()
    b = get_refresher()
    assert a is b
    # ``reset_refresher`` drops the instance; next call lazy-inits a fresh one.
    reset_refresher()
    c = get_refresher()
    assert c is not a


# --------------------------------------------------------------------------
# 8. Bonus — start() is idempotent + double-stop is safe
# --------------------------------------------------------------------------


def test_refresher_start_idempotent_and_double_stop_safe(
    make_refresher, stub_pool,
):
    """Calling ``start()`` twice does not spawn a second thread.

    Reusing the singleton from REST endpoints means callers may issue
    multiple ``POST /costs/refresher/start`` requests; the second must
    be a no-op rather than leaking threads.
    """
    ref = make_refresher(stub_pool, interval_s=0.05, initial_delay_s=0.0)
    ref.start()
    first_thread = ref._thread
    ref.start()
    # Same thread instance — second start was a no-op.
    assert ref._thread is first_thread
    assert ref.stop(timeout_s=1.0) is True
    # Second stop on an already-stopped refresher is a clean no-op.
    assert ref.stop(timeout_s=0.1) is True


# --------------------------------------------------------------------------
# 9. Bonus — invalid construction args raise ValueError
# --------------------------------------------------------------------------


def test_refresher_init_validates_interval():
    """interval_s <= 0 and initial_delay_s < 0 must be rejected."""
    with pytest.raises(ValueError):
        CostLedgerRefresher(interval_s=0.0)
    with pytest.raises(ValueError):
        CostLedgerRefresher(interval_s=-1.0)
    with pytest.raises(ValueError):
        CostLedgerRefresher(interval_s=1.0, initial_delay_s=-0.1)


# --------------------------------------------------------------------------
# 10. Bonus — RefreshStats.avg_duration_ms zero on empty
# --------------------------------------------------------------------------


def test_refresh_stats_avg_zero_on_empty():
    """Brand-new ``RefreshStats`` reports ``avg_duration_ms == 0.0``.

    Avoids a ZeroDivisionError in the operator UI when the daemon has
    never run.
    """
    s = RefreshStats()
    assert s.avg_duration_ms == 0.0
    d = s.to_dict()
    assert d["avg_duration_ms"] == 0.0
    assert d["total_refreshes"] == 0
