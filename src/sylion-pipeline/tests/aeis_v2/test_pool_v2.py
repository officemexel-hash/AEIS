"""Tests for sylion.aeis_v2.db.pool_v2 — W15 G2 dedicated pool foundation.

Phase 0 of G2: only the pool factory exists; no consumer migrated yet.
These tests exercise:

- Default constants honour the v2-specific values (max=20, timeout=5,
  statement_timeout=60000ms).
- Constants are env-overridable when the module is reloaded (so the
  operator can tune via env without code changes).
- ``get_v2_pool`` returns ``None`` cleanly when the v1 advisor _db
  module is unavailable (defensive against partial deployments).
- ``get_v2_pool`` returns ``None`` when PG is unreachable (typed
  ``PGUnreachable`` propagation from v1 _db).
- Singleton semantics — second call returns the same pool instance.
- ``reset_v2_pool`` closes the singleton and clears it so the next
  ``get_v2_pool`` re-initialises.

Heavy mocking — no real PG connection in these tests.
"""
from __future__ import annotations

import importlib
import logging
import sys
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def _reset_pool_singleton():
    """Ensure the module-level singleton is wiped between tests.

    Without this, a stub pool created by one test would leak into the
    next and the singleton-detection asserts would observe stale state.
    """
    from sylion.aeis_v2.db import pool_v2

    pool_v2.reset_v2_pool()
    yield
    pool_v2.reset_v2_pool()


def test_constants_have_v2_defaults():
    """Without env overrides, the v2 pool must use the stricter defaults.

    These are NOT the v1 advisor pool values; the whole point of G2 is a
    dedicated pool with: max=20 (was 10), timeout=5 (was 2),
    statement_timeout=60000ms (v1 had no per-session timeout).
    """
    from sylion.aeis_v2.db import pool_v2

    # We only assert on values we explicitly set defaults for. If a CI
    # environment exports SYLION_V2_POOL_MAX_SIZE the assertion would be
    # spurious — but the test runner runs in a clean env so this is fine.
    assert pool_v2.POOL_V2_MAX_SIZE == 20
    assert pool_v2.POOL_V2_TIMEOUT_S == 5.0
    assert pool_v2.POOL_V2_STATEMENT_TIMEOUT_MS == 60000
    assert pool_v2.POOL_V2_SCHEMA_PATH == "sylion_v2, public"
    assert pool_v2.POOL_V2_ISOLATION == "REPEATABLE READ"


def test_constants_overridable_via_env(monkeypatch):
    """Operator must be able to tune pool sizing via env without code change.

    Reload the module under monkeypatched env so the module-level
    constants re-evaluate ``os.environ.get(...)`` against the patched
    values.
    """
    monkeypatch.setenv("SYLION_V2_POOL_MAX_SIZE", "50")
    monkeypatch.setenv("SYLION_V2_POOL_TIMEOUT_S", "12.5")
    monkeypatch.setenv("SYLION_V2_STATEMENT_TIMEOUT_MS", "120000")
    monkeypatch.setenv("SYLION_V2_SCHEMA_PATH", "custom_schema, public")
    monkeypatch.setenv("SYLION_V2_ISOLATION", "SERIALIZABLE")

    # Force a fresh module-level evaluation of the os.environ.get(...)
    # constants. Drop the cached module so other tests reload the
    # default-env version on next access.
    sys.modules.pop("sylion.aeis_v2.db.pool_v2", None)
    sys.modules.pop("sylion.aeis_v2.db", None)
    from sylion.aeis_v2.db import pool_v2 as reloaded

    try:
        assert reloaded.POOL_V2_MAX_SIZE == 50
        assert reloaded.POOL_V2_TIMEOUT_S == 12.5
        assert reloaded.POOL_V2_STATEMENT_TIMEOUT_MS == 120000
        assert reloaded.POOL_V2_SCHEMA_PATH == "custom_schema, public"
        assert reloaded.POOL_V2_ISOLATION == "SERIALIZABLE"
    finally:
        # Restore default-env module state so subsequent tests see the
        # documented defaults again.
        sys.modules.pop("sylion.aeis_v2.db.pool_v2", None)
        sys.modules.pop("sylion.aeis_v2.db", None)
        importlib.import_module("sylion.aeis_v2.db.pool_v2")


def test_get_v2_pool_returns_none_when_advisor_db_missing(caplog):
    """If v1 advisor _db is missing (partial install), return None at error level.

    This is a packaging defect — the operator deployed aeis_v2 without
    the v1 advisor extra. We must not crash; log at ERROR so the issue
    is visible in monitoring, then return None so callers can fall back
    to preview-only / SQLite paths.
    """
    from sylion.aeis_v2.db import pool_v2

    real_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "sylion.aeis.advisor._db":
            raise ImportError("simulated missing advisor module")
        return real_import(name, *args, **kwargs)

    with mock.patch("builtins.__import__", side_effect=_fake_import):
        with caplog.at_level(logging.ERROR, logger="sylion.aeis_v2.db.pool_v2"):
            result = pool_v2.get_v2_pool()

    assert result is None
    assert any(
        "advisor _db missing" in rec.message and rec.levelname == "ERROR"
        for rec in caplog.records
    ), f"expected ERROR log mentioning advisor _db missing; got {caplog.records!r}"


def test_get_v2_pool_returns_none_when_pg_unreachable(caplog):
    """When v1 _db raises PGUnreachable, propagate as None at info level.

    This is the "PG offline" branch — routine, not a config bug, so log
    at INFO. Caller (applier, cost_ledger_pg, etc.) treats None pool as
    "go to preview-only / JSONL fallback".
    """
    from sylion.aeis.advisor._db import PGUnreachable
    from sylion.aeis_v2.db import pool_v2

    def _raise_pg_unreachable():
        raise PGUnreachable("simulated PG offline")

    with mock.patch.object(pool_v2, "get_v2_pool", wraps=pool_v2.get_v2_pool):
        # Patch the v1 _build_dsn so the import inside get_v2_pool
        # succeeds but the subsequent call raises the typed exception.
        with mock.patch(
            "sylion.aeis.advisor._db._build_dsn",
            side_effect=_raise_pg_unreachable,
        ):
            with caplog.at_level(logging.INFO, logger="sylion.aeis_v2.db.pool_v2"):
                result = pool_v2.get_v2_pool()

    assert result is None
    assert any(
        "PG unreachable" in rec.message and rec.levelname == "INFO"
        for rec in caplog.records
    ), f"expected INFO log mentioning PG unreachable; got {caplog.records!r}"


def test_get_v2_pool_singleton():
    """First call inits the pool, second call returns the same instance.

    This is the contract for a process-wide singleton — call sites in
    applier / cost_ledger_pg cannot be allowed to spawn parallel pools
    or we'd blow past the 20-connection cap on the PG side.
    """
    from sylion.aeis_v2.db import pool_v2

    sentinel_pool = mock.MagicMock(name="psycopg_pool_instance")

    fake_module = mock.MagicMock()
    fake_module.ConnectionPool = mock.MagicMock(return_value=sentinel_pool)

    with mock.patch.dict(sys.modules, {"psycopg_pool": fake_module}):
        first = pool_v2.get_v2_pool()
        second = pool_v2.get_v2_pool()

    assert first is sentinel_pool
    assert second is first
    # ConnectionPool constructor should have been called exactly once
    # despite two get_v2_pool() calls — this is the singleton property.
    assert fake_module.ConnectionPool.call_count == 1


def test_reset_v2_pool_clears_singleton():
    """``reset_v2_pool`` closes the existing pool and re-init on next get.

    Used by tests + the (future) /admin/pool-reset operator endpoint
    after a PG primary failover so we re-establish connections against
    the new endpoint.
    """
    from sylion.aeis_v2.db import pool_v2

    first_pool = mock.MagicMock(name="first_pool_instance")
    second_pool = mock.MagicMock(name="second_pool_instance")

    fake_module = mock.MagicMock()
    fake_module.ConnectionPool = mock.MagicMock(side_effect=[first_pool, second_pool])

    with mock.patch.dict(sys.modules, {"psycopg_pool": fake_module}):
        a = pool_v2.get_v2_pool()
        assert a is first_pool

        pool_v2.reset_v2_pool()
        # First pool's close() should have been called best-effort.
        first_pool.close.assert_called_once()

        b = pool_v2.get_v2_pool()
        assert b is second_pool
        assert b is not a

    # Constructor should have been called twice: once before reset, once after.
    assert fake_module.ConnectionPool.call_count == 2
