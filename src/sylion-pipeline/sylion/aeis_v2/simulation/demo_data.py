"""W14 Sim demo data populators — 5 demo datasets for L0/L1 sessions.

Phase 0: hardcoded sample rows for the five demo object types
(``customer``, ``project``, ``vehicle``, ``idea``, ``task``). Loads into
L1 (sqlite) sessions for fast tests and L0 (pure-python) sessions for
unit tests that just want a realistic dataset shape without a DB.

The demo rows are designed to mirror the shape of the canonical
``manifests/_demos/*.yaml`` (committed by the W14 ``a13b`` task) and are
translated to dict-of-lists for in-memory use here so unit tests don't
need the manifest loader on the import path.

Why "demo data" and not "test fixtures"?
----------------------------------------

Because these rows are also used by the W14 demo runner — the same five
datasets (Polish names, Polish-style addresses, IDs that read naturally
in a console) are shown to humans during demos. Keeping fixtures and
demo content in one place avoids a mismatch where the test data and the
demo data evolve separately and fall out of sync.

Public API:

    DEMO_DATASETS                  -- {"customer": [...], "project": [...], ...}
    populate_l0(sim, type_id)      -- adds rows to ``sim.resources[type_id]``
    populate_l1(sim, type_id)      -- CREATE TABLE + INSERT rows in sqlite
    populate_all_l0(sim)           -- loads all 5 datasets into an L0 session
    populate_all_l1(sim)           -- loads all 5 datasets into an L1 session

Both populators return the row count for the given type (or a dict of
counts in the ``populate_all_*`` form). The L1 populator commits the
INSERTs so subsequent SELECTs in the same connection see the rows
without needing an explicit commit on the test side.
"""
from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------
# Demo dataset 1/5 — customer (CRM-shaped)
# --------------------------------------------------------------------------

DEMO_CUSTOMERS: list[dict[str, Any]] = [
    {
        "id": "c-001",
        "name_pl": "Anna Kowalska",
        "email": "anna.kowalska@example.com",
        "status": "active",
        "city": "Warszawa",
        "owner_id": None,
    },
    {
        "id": "c-002",
        "name_pl": "Piotr Nowak",
        "email": "p.nowak@example.com",
        "status": "active",
        "city": "Krakow",
        "owner_id": None,
    },
    {
        "id": "c-003",
        "name_pl": "Maria Wisniewska",
        "email": "m.wisniewska@example.com",
        "status": "inactive",
        "city": "Gdansk",
        "owner_id": None,
    },
    {
        "id": "c-004",
        "name_pl": "Jan Lewandowski",
        "email": "jan.l@example.com",
        "status": "active",
        "city": "Poznan",
        "owner_id": None,
    },
    {
        "id": "c-005",
        "name_pl": "Katarzyna Wojcik",
        "email": "k.wojcik@example.com",
        "status": "active",
        "city": "Wroclaw",
        "owner_id": None,
    },
]


# --------------------------------------------------------------------------
# Demo dataset 2/5 — project
# --------------------------------------------------------------------------

DEMO_PROJECTS: list[dict[str, Any]] = [
    {
        "id": "p-001",
        "name_pl": "Modernizacja CRM",
        "status": "active",
        "owner_id": "c-001",
        "budget_pln": "120000",
        "deadline": "2026-09-30",
    },
    {
        "id": "p-002",
        "name_pl": "Migracja danych klientow",
        "status": "active",
        "owner_id": "c-002",
        "budget_pln": "45000",
        "deadline": "2026-06-15",
    },
    {
        "id": "p-003",
        "name_pl": "Wdrozenie panelu raportowego",
        "status": "planned",
        "owner_id": "c-004",
        "budget_pln": "60000",
        "deadline": "2026-12-01",
    },
    {
        "id": "p-004",
        "name_pl": "Audyt bezpieczenstwa",
        "status": "completed",
        "owner_id": "c-001",
        "budget_pln": "30000",
        "deadline": "2026-03-31",
    },
    {
        "id": "p-005",
        "name_pl": "Integracja z fakturowaniem",
        "status": "active",
        "owner_id": "c-005",
        "budget_pln": "85000",
        "deadline": "2026-08-10",
    },
]


# --------------------------------------------------------------------------
# Demo dataset 3/5 — vehicle (fleet management shape)
# --------------------------------------------------------------------------

DEMO_VEHICLES: list[dict[str, Any]] = [
    {
        "id": "v-001",
        "plate": "WA12345",
        "model": "Skoda Octavia",
        "year": "2022",
        "status": "available",
        "owner_id": None,
    },
    {
        "id": "v-002",
        "plate": "KR67890",
        "model": "Volkswagen Passat",
        "year": "2021",
        "status": "in_service",
        "owner_id": "c-002",
    },
    {
        "id": "v-003",
        "plate": "GD11122",
        "model": "Toyota Corolla",
        "year": "2023",
        "status": "available",
        "owner_id": None,
    },
    {
        "id": "v-004",
        "plate": "PO33344",
        "model": "Ford Mondeo",
        "year": "2020",
        "status": "maintenance",
        "owner_id": "c-004",
    },
    {
        "id": "v-005",
        "plate": "WR55566",
        "model": "Hyundai i30",
        "year": "2024",
        "status": "available",
        "owner_id": None,
    },
]


# --------------------------------------------------------------------------
# Demo dataset 4/5 — idea (idea vault shape)
# --------------------------------------------------------------------------

DEMO_IDEAS: list[dict[str, Any]] = [
    {
        "id": "i-001",
        "title_pl": "Automatyczne raporty miesieczne",
        "status": "draft",
        "author_id": "c-001",
        "score": "0.72",
        "tag": "reporting",
    },
    {
        "id": "i-002",
        "title_pl": "Powiadomienia push dla klientow",
        "status": "approved",
        "author_id": "c-002",
        "score": "0.84",
        "tag": "notifications",
    },
    {
        "id": "i-003",
        "title_pl": "Eksport CSV z panelu",
        "status": "implemented",
        "author_id": "c-004",
        "score": "0.65",
        "tag": "export",
    },
    {
        "id": "i-004",
        "title_pl": "Tryb ciemny w aplikacji",
        "status": "draft",
        "author_id": "c-005",
        "score": "0.58",
        "tag": "ui",
    },
    {
        "id": "i-005",
        "title_pl": "Rozliczanie kosztow per projekt",
        "status": "rejected",
        "author_id": "c-003",
        "score": "0.41",
        "tag": "billing",
    },
]


# --------------------------------------------------------------------------
# Demo dataset 5/5 — task (workflow shape)
# --------------------------------------------------------------------------

DEMO_TASKS: list[dict[str, Any]] = [
    {
        "id": "t-001",
        "title_pl": "Przygotowac raport sprzedazy",
        "status": "open",
        "owner_id": "c-001",
        "project_id": "p-001",
        "priority": "high",
    },
    {
        "id": "t-002",
        "title_pl": "Zaktualizowac dane klientow",
        "status": "in_progress",
        "owner_id": "c-002",
        "project_id": "p-002",
        "priority": "medium",
    },
    {
        "id": "t-003",
        "title_pl": "Test integracyjny faktur",
        "status": "blocked",
        "owner_id": "c-005",
        "project_id": "p-005",
        "priority": "high",
    },
    {
        "id": "t-004",
        "title_pl": "Code review modulu raportow",
        "status": "done",
        "owner_id": "c-004",
        "project_id": "p-003",
        "priority": "medium",
    },
    {
        "id": "t-005",
        "title_pl": "Spotkanie z zespolem audytu",
        "status": "open",
        "owner_id": "c-001",
        "project_id": "p-004",
        "priority": "low",
    },
]


# --------------------------------------------------------------------------
# Top-level dataset registry
# --------------------------------------------------------------------------
#
# Maps the canonical type_id (matches the ``ontology`` type IDs used in
# the v2 contract layer) to the list of demo rows. New demo types should
# be added here AND in ``manifests/_demos/<type_id>.yaml`` so the demo
# runner and the unit tests stay in sync.

DEMO_DATASETS: dict[str, list[dict[str, Any]]] = {
    "customer": DEMO_CUSTOMERS,
    "project": DEMO_PROJECTS,
    "vehicle": DEMO_VEHICLES,
    "idea": DEMO_IDEAS,
    "task": DEMO_TASKS,
}


# --------------------------------------------------------------------------
# L0 populator
# --------------------------------------------------------------------------


def populate_l0(sim: Any, type_id: str) -> int:
    """Add demo rows to ``sim.resources[type_id]``.

    Args:
        sim: a simulation session (typically L0; the function only
            touches ``sim.resources`` so it works on any session that
            exposes that attribute, but the L1 path should use
            :func:`populate_l1` to actually exercise the SQLite backend).
        type_id: one of the keys in :data:`DEMO_DATASETS` (currently
            ``customer``, ``project``, ``vehicle``, ``idea``, ``task``).

    Returns:
        Number of rows added (always ``len(DEMO_DATASETS[type_id])``).

    Raises:
        ValueError: when ``type_id`` is not a known demo dataset. The
            message lists the valid options so the caller can fix the
            typo without re-reading this module.

    The stored list is a fresh ``list(...)`` copy of the canonical demo
    rows so the test's mutations never bleed back into the module-level
    constants. The dicts inside are still shared by reference — if a
    test wants deep isolation it should ``copy.deepcopy`` itself.
    """
    if type_id not in DEMO_DATASETS:
        valid = ", ".join(sorted(DEMO_DATASETS))
        raise ValueError(
            f"unknown demo dataset: {type_id!r}; valid: {valid}",
        )
    rows = list(DEMO_DATASETS[type_id])
    sim.resources[type_id] = rows
    return len(rows)


# --------------------------------------------------------------------------
# L1 populator
# --------------------------------------------------------------------------


def populate_l1(sim: Any, type_id: str) -> int:
    """Create the demo table for ``type_id`` and INSERT all demo rows.

    Args:
        sim: an L1 simulation session whose ``conn`` is a
            ``sqlite3.Connection``. Caller is responsible for level
            checking — the function only requires a working
            ``sim.conn.cursor()``.
        type_id: one of the keys in :data:`DEMO_DATASETS`.

    Returns:
        Number of rows inserted.

    Raises:
        ValueError: when ``type_id`` is not a known demo dataset.

    The CREATE TABLE uses ``IF NOT EXISTS`` so a second call against
    the same session simply re-inserts (with duplicate IDs since
    columns are TEXT, not PRIMARY KEY — the populator chooses
    permissive shapes so all five datasets share the same code path).
    All values are coerced to strings via ``str(...)`` to keep the
    schema uniform; ``None`` values are passed through as SQL NULL.
    """
    if type_id not in DEMO_DATASETS:
        valid = ", ".join(sorted(DEMO_DATASETS))
        raise ValueError(
            f"unknown demo dataset: {type_id!r}; valid: {valid}",
        )
    rows = DEMO_DATASETS[type_id]
    cur = sim.conn.cursor()
    columns = list(rows[0].keys())
    col_defs = ", ".join(f"{c} TEXT" for c in columns)
    cur.execute(f"CREATE TABLE IF NOT EXISTS {type_id} ({col_defs})")
    placeholders = ", ".join(["?"] * len(columns))
    insert_sql = (
        f"INSERT INTO {type_id} ({', '.join(columns)}) "
        f"VALUES ({placeholders})"
    )
    for row in rows:
        cur.execute(
            insert_sql,
            [str(row[c]) if row[c] is not None else None for c in columns],
        )
    sim.conn.commit()
    return len(rows)


# --------------------------------------------------------------------------
# Convenience: load all 5 datasets at once
# --------------------------------------------------------------------------


def populate_all_l0(sim: Any) -> dict[str, int]:
    """Load all 5 demo datasets into an L0 session.

    Returns a ``{type_id: row_count}`` mapping so the caller can sanity-
    check the result without re-counting each list. Useful for tests
    that just want "a realistic dataset" without picking individual
    types.
    """
    return {tid: populate_l0(sim, tid) for tid in DEMO_DATASETS}


def populate_all_l1(sim: Any) -> dict[str, int]:
    """Load all 5 demo datasets into an L1 sqlite session.

    Same shape as :func:`populate_all_l0` but creates 5 tables in the
    SQLite db and inserts the rows. After this call:

        sim.conn.execute("SELECT COUNT(*) FROM customer").fetchone()

    will return 5 (or whatever the canonical demo count is for that
    type).
    """
    return {tid: populate_l1(sim, tid) for tid in DEMO_DATASETS}
