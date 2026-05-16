"""Tests for the W15 G2 phase 1 pool migration — v2-first with v1 fallback.

Phase 0 of G2 shipped the dedicated v2 pool foundation
(``sylion.aeis_v2.db.pool_v2.get_v2_pool``). Phase 1 (this test module)
covers the consumer-side fallback helper used by:

- ``sylion.aeis_v2.ontology.applier._get_pg_connection``
- ``sylion.aeis_v2.deployment.cost_ledger_pg._get_pg_connection``

Both delegate to ``sylion.aeis_v2.db.get_pool_with_fallback`` so the
fallback policy is single-sourced. Tests cover:

1. v2 pool returned when reachable.
2. v1 fallback when v2 returns ``None`` (PG unreachable from v2's
   perspective, or advisor _db missing inside ``pool_v2``).
3. v1 fallback when the v2 module itself raises ``ImportError`` (partial
   deployment / packaging defect).
4. ``SYLION_USE_V2_POOL=0`` forces the v1 path entirely (operator
   rollback knob).
5. cost-ledger PG ``_get_pg_connection`` shares the same fallback path.

Heavy mocking — no real PG connection in any test. We only verify the
selection logic; the v2 pool itself is covered by ``test_pool_v2.py``
and the v1 advisor pool by the existing advisor tests.
"""
from __future__ import annotations

from unittest import mock

import pytest

from sylion.aeis_v2 import db as v2_db
from sylion.aeis_v2.deployment import cost_ledger_pg as cost_ledger_pg_mod
from sylion.aeis_v2.ontology import applier as applier_mod


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_v2_pool_singleton():
    """Wipe the v2 pool singleton before/after every test in this module.

    Without this, a stub pool created by one test could leak into the
    next via the module-level ``_pool`` cache in ``pool_v2``.
    """
    v2_db.reset_v2_pool()
    yield
    v2_db.reset_v2_pool()


@pytest.fixture
def _force_v2_enabled(monkeypatch):
    """Default to v2 enabled — explicit so tests document the env state.

    The helper checks ``SYLION_USE_V2_POOL`` against ``"1"``. If the
    runner's env happens to have it set to ``"0"`` (e.g. a developer
    debugging the rollback path locally), some assertions would flip
    silently. Pinning it here makes the test contract explicit.
    """
    monkeypatch.setenv("SYLION_USE_V2_POOL", "1")


# --------------------------------------------------------------------------
# 1. applier prefers v2 pool when available
# --------------------------------------------------------------------------


def test_applier_uses_v2_pool_when_available(monkeypatch, _force_v2_enabled):
    """When ``get_v2_pool()`` returns a pool, the applier must use it.

    Asserts:
    - ``applier._get_pg_connection()`` returns the v2 sentinel.
    - The v1 ``get_pool`` is NEVER consulted (importing it would be a
      regression — operators set ``SYLION_USE_V2_POOL=1`` precisely to
      keep advisor traffic off the v1 pool).
    """
    v2_sentinel = mock.MagicMock(name="v2_pool_sentinel")

    v1_get_pool_called = []

    def _v1_get_pool_spy():
        v1_get_pool_called.append(True)
        return mock.MagicMock(name="v1_pool_should_not_be_used")

    monkeypatch.setattr(v2_db, "get_v2_pool", lambda: v2_sentinel)
    # Also patch the module-level binding inside the package __init__ so
    # the helper's call sees the same sentinel.
    monkeypatch.setattr(
        "sylion.aeis_v2.db.get_v2_pool", lambda: v2_sentinel,
    )
    monkeypatch.setattr("sylion.aeis.advisor._db.get_pool", _v1_get_pool_spy)

    result = applier_mod._get_pg_connection()

    assert result is v2_sentinel, (
        "applier should return the v2 pool when available"
    )
    assert not v1_get_pool_called, (
        "v1 get_pool must not be called when v2 pool is reachable"
    )


# --------------------------------------------------------------------------
# 2. v1 fallback when v2 returns None
# --------------------------------------------------------------------------


def test_applier_falls_back_to_v1_when_v2_returns_none(
    monkeypatch, _force_v2_enabled,
):
    """When ``get_v2_pool()`` returns ``None``, the applier falls back to v1.

    The v2 pool returns ``None`` for two real-world reasons:

    1. PG unreachable from v2's perspective (``PGUnreachable`` typed
       exception caught inside ``pool_v2.get_v2_pool``).
    2. v1 advisor _db missing inside the v2 pool's bootstrap (returns
       ``None`` at ERROR level).

    Either way the applier should still try v1 — if v1 succeeds we
    proceed; if v1 also fails we end up at preview-only.
    """
    v1_sentinel = mock.MagicMock(name="v1_pool_sentinel")

    monkeypatch.setattr("sylion.aeis_v2.db.get_v2_pool", lambda: None)
    monkeypatch.setattr(
        "sylion.aeis.advisor._db.get_pool", lambda: v1_sentinel,
    )

    result = applier_mod._get_pg_connection()

    assert result is v1_sentinel, (
        "applier should fall back to the v1 pool when v2 returns None"
    )


# --------------------------------------------------------------------------
# 3. v1 fallback when v2 module import fails
# --------------------------------------------------------------------------


def test_applier_falls_back_to_v1_when_v2_import_fails(
    monkeypatch, caplog, _force_v2_enabled,
):
    """When ``get_v2_pool()`` itself raises ``ImportError``, fall back to v1.

    This is the "v2 module not deployed" / "partial install" branch —
    operators see an ERROR log so monitoring can flag the deployment
    defect, but the call still returns the v1 pool so the operator UI
    keeps functioning instead of going straight to preview-only.
    """
    v1_sentinel = mock.MagicMock(name="v1_pool_sentinel")

    def _raise_import_error():
        raise ImportError("simulated v2 pool module missing")

    monkeypatch.setattr("sylion.aeis_v2.db.get_v2_pool", _raise_import_error)
    monkeypatch.setattr(
        "sylion.aeis.advisor._db.get_pool", lambda: v1_sentinel,
    )

    import logging
    with caplog.at_level(logging.ERROR):
        result = applier_mod._get_pg_connection()

    assert result is v1_sentinel, (
        "applier should fall back to v1 pool on v2 ImportError"
    )
    assert any(
        "v2 pool import failed" in rec.message and rec.levelname == "ERROR"
        for rec in caplog.records
    ), (
        f"expected ERROR log mentioning v2 pool import failure; got {caplog.records!r}"
    )


# --------------------------------------------------------------------------
# 4. SYLION_USE_V2_POOL=0 disables v2 entirely
# --------------------------------------------------------------------------


def test_use_v2_pool_env_flag_disables_v2(monkeypatch):
    """``SYLION_USE_V2_POOL=0`` -> applier goes straight to v1, never calls v2.

    This is the operator rollback knob: when the v2 pool misbehaves
    under load, set the env var and restart the process — no code
    change, no redeploy. We verify the rollback by spying on the v2
    factory and asserting it was never invoked.
    """
    monkeypatch.setenv("SYLION_USE_V2_POOL", "0")

    v1_sentinel = mock.MagicMock(name="v1_pool_sentinel")
    v2_calls: list[bool] = []

    def _v2_spy():
        v2_calls.append(True)
        return mock.MagicMock(name="v2_pool_should_not_be_used")

    monkeypatch.setattr("sylion.aeis_v2.db.get_v2_pool", _v2_spy)
    monkeypatch.setattr(
        "sylion.aeis.advisor._db.get_pool", lambda: v1_sentinel,
    )

    result = applier_mod._get_pg_connection()

    assert result is v1_sentinel, (
        "with SYLION_USE_V2_POOL=0, applier must go directly to v1"
    )
    assert not v2_calls, (
        "v2 pool factory must never be invoked when env flag disables v2"
    )


# --------------------------------------------------------------------------
# 5. cost_ledger_pg shares the same fallback path
# --------------------------------------------------------------------------


def test_cost_ledger_pg_uses_v2_pool_when_available(
    monkeypatch, _force_v2_enabled,
):
    """``cost_ledger_pg._get_pg_connection`` shares the same fallback policy.

    Both the W15 applier and the W17 cost-ledger PG layer delegate to
    ``sylion.aeis_v2.db.get_pool_with_fallback`` so operators have one
    rollback knob and one set of severity gradients in the logs. This
    test asserts the cost-ledger module respects the v2-first ordering
    just like the applier.
    """
    v2_sentinel = mock.MagicMock(name="v2_pool_sentinel_for_cost_ledger")

    v1_calls: list[bool] = []

    def _v1_spy():
        v1_calls.append(True)
        return mock.MagicMock(name="v1_pool_should_not_be_used")

    monkeypatch.setattr("sylion.aeis_v2.db.get_v2_pool", lambda: v2_sentinel)
    monkeypatch.setattr("sylion.aeis.advisor._db.get_pool", _v1_spy)

    result = cost_ledger_pg_mod._get_pg_connection()

    assert result is v2_sentinel, (
        "cost_ledger_pg should use the v2 pool when available"
    )
    assert not v1_calls, (
        "v1 get_pool must not be consulted when v2 succeeds for cost_ledger_pg"
    )


# --------------------------------------------------------------------------
# 6. cost_ledger_pg falls back to v1 when v2 returns None
# --------------------------------------------------------------------------


def test_cost_ledger_pg_falls_back_to_v1_when_v2_returns_none(
    monkeypatch, _force_v2_enabled,
):
    """Mirror of test #2 but for the cost-ledger PG module.

    Belt-and-suspenders coverage — the two modules call the same
    helper, but a future refactor that copy-pastes the helper into one
    of them and forgets to update the other would silently break this.
    """
    v1_sentinel = mock.MagicMock(name="v1_pool_sentinel_for_cost_ledger")

    monkeypatch.setattr("sylion.aeis_v2.db.get_v2_pool", lambda: None)
    monkeypatch.setattr(
        "sylion.aeis.advisor._db.get_pool", lambda: v1_sentinel,
    )

    result = cost_ledger_pg_mod._get_pg_connection()

    assert result is v1_sentinel, (
        "cost_ledger_pg should fall back to v1 when v2 returns None"
    )


# --------------------------------------------------------------------------
# 7. Both pools unreachable -> None (preview-only)
# --------------------------------------------------------------------------


def test_both_pools_unreachable_returns_none(
    monkeypatch, _force_v2_enabled,
):
    """When v2 returns None AND v1 raises ``PGUnreachable``, return ``None``.

    This is the steady-state "PG offline" scenario. Both pools should
    be tried; the helper should not raise; the caller (applier or
    cost_ledger_pg) interprets ``None`` as "go to preview-only mode".
    """
    from sylion.aeis.advisor._db import PGUnreachable

    def _raise_pg_unreachable():
        raise PGUnreachable("simulated PG offline")

    monkeypatch.setattr("sylion.aeis_v2.db.get_v2_pool", lambda: None)
    monkeypatch.setattr(
        "sylion.aeis.advisor._db.get_pool", _raise_pg_unreachable,
    )

    # Both consumers must agree on the None contract.
    assert applier_mod._get_pg_connection() is None
    assert cost_ledger_pg_mod._get_pg_connection() is None
