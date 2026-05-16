"""Tests for ``sylion.aeis_v2.simulation`` — W14 Sim L0-L4 plane.

Phase 0 covers:

1. L0 factory returns a pure-Python session (no conn, empty resources).
2. Two L0 sessions don't share state (resources dict is per-instance).
3. L1 factory creates a real ``sqlite3.Connection`` (in-memory by default).
4. L1 session can execute CREATE TABLE without raising.
5. L2 factory raises ``NotImplementedError`` (deferred to G2).
6. ``with_session`` runs cleanup on exit even when the body raises.
7. ``with_session`` for L1 closes the SQLite connection on exit.
8. ``populate_l0_with_demo_customers`` yields N dicts under
   ``sim.resources['customers']``.
9. ``populate_l1_with_demo_customers`` actually creates 5 rows in
   ``customer`` table (verifiable via ``SELECT COUNT(*)``).

Plus type-mismatch guards (calling L0 populator on L1 session, etc.)
and the ``create_session`` string-dispatch.

Tests use ``:memory:`` SQLite so no file I/O leaks between runs.
"""
from __future__ import annotations

import sqlite3

import pytest

from sylion.aeis_v2.simulation import (
    SimLevel,
    SimSession,
    create_l0_session,
    create_l1_session,
    create_l2_session,
    create_session,
    populate_l0_with_demo_customers,
    populate_l1_with_demo_customers,
    with_session,
)


# --------------------------------------------------------------------------
# 1. L0 factory shape
# --------------------------------------------------------------------------


def test_create_l0_session_returns_pure_python_context():
    """L0 session has no DB conn and an empty resources dict."""
    sim = create_l0_session()
    assert isinstance(sim, SimSession)
    assert sim.level is SimLevel.L0_PURE
    assert sim.conn is None
    assert sim.resources == {}
    # close() on L0 is a no-op — must not raise.
    sim.close()


# --------------------------------------------------------------------------
# 2. L0 isolation
# --------------------------------------------------------------------------


def test_l0_session_resources_is_isolated_per_session():
    """Two L0 sessions don't share their ``resources`` dict.

    Regression guard against accidentally using a class-level mutable
    default — that would silently leak state across tests.
    """
    sim_a = create_l0_session()
    sim_b = create_l0_session()
    sim_a.resources["foo"] = 1
    assert "foo" not in sim_b.resources
    assert sim_a.resources is not sim_b.resources


# --------------------------------------------------------------------------
# 3. L1 factory shape
# --------------------------------------------------------------------------


def test_create_l1_session_creates_sqlite_in_memory_db():
    """L1 default is ``:memory:`` and exposes a real ``sqlite3.Connection``."""
    sim = create_l1_session()
    try:
        assert sim.level is SimLevel.L1_SQLITE
        assert isinstance(sim.conn, sqlite3.Connection)
        # Row factory should be sqlite3.Row for dict-like access.
        cur = sim.conn.execute("SELECT 1 AS ok")
        row = cur.fetchone()
        assert row["ok"] == 1
        # db_path metadata propagated.
        assert sim.resources.get("db_path") == ":memory:"
    finally:
        sim.close()


# --------------------------------------------------------------------------
# 4. L1 DDL works
# --------------------------------------------------------------------------


def test_l1_session_can_execute_create_table():
    """L1's SQLite conn can run CREATE TABLE — query-shape tests work."""
    with with_session(SimLevel.L1_SQLITE) as sim:
        sim.conn.execute(
            "CREATE TABLE thing (id INTEGER PRIMARY KEY, name TEXT)",
        )
        sim.conn.commit()
        cur = sim.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='thing'",
        )
        assert cur.fetchone() is not None


# --------------------------------------------------------------------------
# 5. L2 stub raises
# --------------------------------------------------------------------------


def test_create_l2_session_raises_not_implemented():
    """L2 stub raises ``NotImplementedError`` with a 'deferred to G2' message."""
    with pytest.raises(NotImplementedError, match="G2"):
        create_l2_session()
    # via factory dispatch
    with pytest.raises(NotImplementedError):
        create_session(SimLevel.L2_PG_TRANSIENT)
    # via string dispatch
    with pytest.raises(NotImplementedError):
        create_session("L2_pg_transient")


# --------------------------------------------------------------------------
# 6. with_session cleanup runs on exit (L0 + exception path)
# --------------------------------------------------------------------------


def test_with_session_l0_runs_cleanup_on_exit():
    """``with_session`` calls ``close()`` even when the body raises.

    L0 has no real cleanup, so we install a sentinel ourselves and
    confirm it fires.
    """
    fired: list[bool] = []

    class _Boom(Exception):
        pass

    with pytest.raises(_Boom):
        with with_session(SimLevel.L0_PURE) as sim:
            sim.cleanup = lambda: fired.append(True)
            raise _Boom("body failed")
    assert fired == [True]


# --------------------------------------------------------------------------
# 7. with_session for L1 closes the connection
# --------------------------------------------------------------------------


def test_with_session_l1_closes_connection_on_exit():
    """After ``with_session`` exits, the SQLite conn is closed.

    A closed sqlite3.Connection raises ``sqlite3.ProgrammingError`` on
    ``execute`` — we observe that to confirm cleanup ran.
    """
    captured: dict[str, sqlite3.Connection] = {}
    with with_session(SimLevel.L1_SQLITE) as sim:
        captured["conn"] = sim.conn
    with pytest.raises(sqlite3.ProgrammingError):
        captured["conn"].execute("SELECT 1")


# --------------------------------------------------------------------------
# 8. L0 populate fixture
# --------------------------------------------------------------------------


def test_populate_l0_demo_customers_yields_n_dicts():
    """L0 populator produces N dicts under ``sim.resources['customers']``."""
    sim = create_l0_session()
    customers = populate_l0_with_demo_customers(sim, count=5)
    assert isinstance(customers, list)
    assert len(customers) == 5
    assert all(isinstance(c, dict) for c in customers)
    assert sim.resources["customers"] is customers
    # First/last dicts have the expected stable shape.
    assert customers[0] == {
        "id": 1, "name": "Customer 1", "email": "customer1@example.com",
    }
    assert customers[-1]["id"] == 5


def test_populate_l0_demo_customers_rejects_l1_session():
    """L0 populator must refuse a non-L0 session — clear error message."""
    sim = create_l1_session()
    try:
        with pytest.raises(ValueError, match="L0 session"):
            populate_l0_with_demo_customers(sim, count=3)
    finally:
        sim.close()


# --------------------------------------------------------------------------
# 9. L1 populate fixture
# --------------------------------------------------------------------------


def test_populate_l1_demo_customers_creates_5_rows():
    """L1 populator creates the customer table and inserts 5 rows."""
    with with_session(SimLevel.L1_SQLITE) as sim:
        inserted = populate_l1_with_demo_customers(sim, count=5)
        assert inserted == 5
        cur = sim.conn.execute("SELECT COUNT(*) AS n FROM customer")
        assert cur.fetchone()["n"] == 5
        # Spot-check shape of one row.
        cur = sim.conn.execute(
            "SELECT id, name, email FROM customer WHERE id = 3",
        )
        row = cur.fetchone()
        assert row["name"] == "Customer 3"
        assert row["email"] == "customer3@example.com"


def test_populate_l1_demo_customers_rejects_l0_session():
    """L1 populator must refuse a non-L1 session."""
    sim = create_l0_session()
    with pytest.raises(ValueError, match="L1 session"):
        populate_l1_with_demo_customers(sim, count=3)


# --------------------------------------------------------------------------
# 10. create_session string dispatch
# --------------------------------------------------------------------------


def test_create_session_accepts_string_level():
    """``create_session`` accepts a level string or a ``SimLevel``."""
    sim = create_session("L0_pure_python")
    try:
        assert sim.level is SimLevel.L0_PURE
    finally:
        sim.close()


def test_create_session_rejects_unknown_level():
    """Unknown level strings raise ValueError listing the valid options."""
    with pytest.raises(ValueError, match="Valid:"):
        create_session("L99_warp_drive")
