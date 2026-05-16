"""Tests for ``sylion.aeis_v2.simulation.demo_data`` — 5-type populator.

Phase 0 covers:

1. The module exposes exactly 5 demo datasets — customer/project/
   vehicle/idea/task.
2. The customer dataset has 5 entries with Polish-style names.
3. ``populate_l0`` adds rows under ``sim.resources[type_id]``.
4. ``populate_l0`` raises ValueError for an unknown ``type_id``.
5. ``populate_l1`` creates the table and inserts rows in a sqlite
   ``:memory:`` connection (verified via ``SELECT COUNT(*)``).
6. ``populate_l1`` returns a row count that matches the demo data length.
7. ``populate_all_l0`` loads all 5 datasets in one call.
8. ``populate_all_l1`` creates all 5 tables in one call.

Tests are hermetic — they either use ``create_l0_session`` /
``create_l1_session`` from the just-landed ``simulation/levels.py``, or
construct a bare ``sqlite3.connect(":memory:")`` directly. Either way,
no test depends on a filesystem path or a live PG.
"""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from sylion.aeis_v2.simulation import (
    SimLevel,
    create_l0_session,
    create_l1_session,
)
from sylion.aeis_v2.simulation.demo_data import (
    DEMO_CUSTOMERS,
    DEMO_DATASETS,
    populate_all_l0,
    populate_all_l1,
    populate_l0,
    populate_l1,
)


# --------------------------------------------------------------------------
# 1. Demo dataset registry shape
# --------------------------------------------------------------------------


def test_demo_datasets_have_5_types():
    """``DEMO_DATASETS`` exposes the 5 canonical demo types."""
    assert set(DEMO_DATASETS.keys()) == {
        "customer",
        "project",
        "vehicle",
        "idea",
        "task",
    }
    # Each dataset has 5 entries — keeps fixtures predictable for tests
    # that count rows.
    for type_id, rows in DEMO_DATASETS.items():
        assert len(rows) == 5, f"dataset {type_id} should have 5 rows"


# --------------------------------------------------------------------------
# 2. Customer dataset — Polish names
# --------------------------------------------------------------------------


def test_demo_customers_has_5_polish_names():
    """The customer demo dataset has 5 entries with realistic Polish names."""
    assert len(DEMO_CUSTOMERS) == 5
    expected_names = {
        "Anna Kowalska",
        "Piotr Nowak",
        "Maria Wisniewska",
        "Jan Lewandowski",
        "Katarzyna Wojcik",
    }
    actual_names = {c["name_pl"] for c in DEMO_CUSTOMERS}
    assert actual_names == expected_names
    # Every entry has the same shape — id/name_pl/email/status/city/owner_id.
    for c in DEMO_CUSTOMERS:
        assert set(c.keys()) >= {
            "id",
            "name_pl",
            "email",
            "status",
            "city",
            "owner_id",
        }


# --------------------------------------------------------------------------
# 3. populate_l0 happy path
# --------------------------------------------------------------------------


def test_populate_l0_adds_rows_to_resources():
    """``populate_l0`` adds the demo rows under ``sim.resources[type_id]``."""
    sim = create_l0_session()
    n = populate_l0(sim, "customer")
    assert n == 5
    assert "customer" in sim.resources
    assert len(sim.resources["customer"]) == 5
    # The stored list should be a copy, not the same reference as the
    # module-level constant — otherwise a test mutation would leak across
    # other tests that import DEMO_CUSTOMERS.
    assert sim.resources["customer"] is not DEMO_CUSTOMERS
    # First row carries the canonical Polish name.
    assert sim.resources["customer"][0]["name_pl"] == "Anna Kowalska"


# --------------------------------------------------------------------------
# 4. populate_l0 error path
# --------------------------------------------------------------------------


def test_populate_l0_unknown_type_raises():
    """``populate_l0`` raises ValueError listing valid types on bad input."""
    sim = create_l0_session()
    with pytest.raises(ValueError, match="unknown demo dataset"):
        populate_l0(sim, "spaceship")
    # The error message lists the valid options so the caller can fix
    # the typo without re-reading the module.
    with pytest.raises(ValueError, match="customer"):
        populate_l0(sim, "spaceship")


# --------------------------------------------------------------------------
# 5. populate_l1 happy path with bare sqlite — fully hermetic
# --------------------------------------------------------------------------


def test_populate_l1_creates_table_and_inserts():
    """``populate_l1`` CREATEs the table and INSERTs rows in :memory: sqlite.

    Uses a bare ``sqlite3.connect(":memory:")`` wrapped in a
    ``SimpleNamespace`` so the test does not depend on the levels.py
    factory at all — gives us a hermetic check of the populator's SQL.
    """
    conn = sqlite3.connect(":memory:")
    try:
        sim = SimpleNamespace(conn=conn)
        n = populate_l1(sim, "customer")
        assert n == 5
        # Table exists in sqlite_master.
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='customer'",
        )
        assert cur.fetchone() is not None
        # COUNT(*) confirms 5 rows were inserted.
        cur = conn.execute("SELECT COUNT(*) FROM customer")
        assert cur.fetchone()[0] == 5
        # Spot-check one row carries the canonical Polish name.
        cur = conn.execute(
            "SELECT name_pl FROM customer WHERE id = 'c-001'",
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Anna Kowalska"
    finally:
        conn.close()


# --------------------------------------------------------------------------
# 6. populate_l1 row count matches dataset length
# --------------------------------------------------------------------------


def test_populate_l1_count_matches_demo_data():
    """``populate_l1`` returns a count equal to ``len(DEMO_DATASETS[type_id])``."""
    sim = create_l1_session()
    try:
        for type_id in DEMO_DATASETS:
            inserted = populate_l1(sim, type_id)
            assert inserted == len(DEMO_DATASETS[type_id])
            # And SELECT COUNT(*) confirms the same count is in the db.
            cur = sim.conn.execute(f"SELECT COUNT(*) FROM {type_id}")
            assert cur.fetchone()[0] == len(DEMO_DATASETS[type_id])
    finally:
        sim.close()


# --------------------------------------------------------------------------
# 7. populate_all_l0 loads all 5 datasets
# --------------------------------------------------------------------------


def test_populate_all_l0_loads_all_5_datasets():
    """``populate_all_l0`` returns a {type_id: count} dict for all 5 types."""
    sim = create_l0_session()
    counts = populate_all_l0(sim)
    assert set(counts.keys()) == {
        "customer",
        "project",
        "vehicle",
        "idea",
        "task",
    }
    assert all(c == 5 for c in counts.values())
    # All 5 datasets are now under sim.resources.
    for type_id in DEMO_DATASETS:
        assert type_id in sim.resources
        assert len(sim.resources[type_id]) == 5


# --------------------------------------------------------------------------
# 8. populate_all_l1 creates all 5 tables
# --------------------------------------------------------------------------


def test_populate_all_l1_creates_5_tables():
    """``populate_all_l1`` creates all 5 demo tables in the sqlite db."""
    sim = create_l1_session()
    try:
        assert sim.level is SimLevel.L1_SQLITE
        counts = populate_all_l1(sim)
        assert set(counts.keys()) == {
            "customer",
            "project",
            "vehicle",
            "idea",
            "task",
        }
        # Verify each table exists and has 5 rows.
        for type_id in DEMO_DATASETS:
            cur = sim.conn.execute(
                "SELECT name FROM sqlite_master "
                f"WHERE type='table' AND name='{type_id}'",
            )
            assert cur.fetchone() is not None, f"{type_id} table missing"
            cur = sim.conn.execute(f"SELECT COUNT(*) FROM {type_id}")
            assert cur.fetchone()[0] == 5
    finally:
        sim.close()


# --------------------------------------------------------------------------
# 9. populate_l1 unknown type raises (parity with L0)
# --------------------------------------------------------------------------


def test_populate_l1_unknown_type_raises():
    """``populate_l1`` raises ValueError for an unknown ``type_id``.

    Symmetry with :func:`test_populate_l0_unknown_type_raises` — both
    populators should fail the same way for the same bad input so the
    caller can write level-agnostic error handling.
    """
    sim = create_l1_session()
    try:
        with pytest.raises(ValueError, match="unknown demo dataset"):
            populate_l1(sim, "spaceship")
    finally:
        sim.close()
