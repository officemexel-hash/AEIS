"""W14 Simulation L0-L4 — graduated test environments.

- L0: pure-Python in-memory, no I/O — fastest, for unit-level fan-out tests.
- L1: SQLite as PG substitute — fast, for query-shape tests.
- L2: real PG transient (transaction rolled back at end) — medium, for DDL
  tests. Stub raises ``NotImplementedError`` — deferred to G2.
- L3 (placeholder): real PG persistent — slow, dedicated test schema.
- L4 (placeholder): full multi-host federation — out of scope Phase 0.

Phase 0 of this module: L0 + L1 only. L2-L4 stubs raise
``NotImplementedError`` so callers can branch on level without wrapping
every call site in a try/except.

Design notes
------------

Why not always use L2/L3? They require a live PG — every CI agent and
every developer workstation would need one. L0/L1 cover ~80 percent of
the common test shapes (data flow, query shape, simple constraint
checks) at zero infrastructure cost, leaving L2/L3 for the genuinely
DDL-bound or transactional tests where SQLite's relaxed semantics would
let bugs through.

The ``SimSession`` dataclass holds the active context: level enum,
backend connection (``None`` for L0, sqlite3.Connection for L1),
optional cleanup callable, and a free-form ``resources`` dict that
fixtures can populate with in-memory state (L0) or auxiliary metadata
(L1).

``with_session`` is the recommended entry point — it guarantees
``close()`` runs even on exceptions, so a SQLite connection or
in-memory state never leaks across tests.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator


class SimLevel(Enum):
    """Five graduated simulation levels per W14 charter §Sim L0-L4."""

    L0_PURE = "L0_pure_python"
    L1_SQLITE = "L1_sqlite"
    L2_PG_TRANSIENT = "L2_pg_transient"
    L3_PG_PERSISTENT = "L3_pg_persistent"
    L4_FEDERATION = "L4_federation"


@dataclass
class SimSession:
    """Active simulation context.

    Attributes
    ----------
    level:
        Which level this session represents — useful for fixtures that
        want to branch on backend (e.g. "if L0 use dict, else SQL").
    conn:
        Backend-specific connection. ``None`` for L0 (no I/O at all),
        ``sqlite3.Connection`` for L1, future ``psycopg.Connection`` for
        L2+. Typed as ``Any`` so the dataclass doesn't drag in psycopg.
    cleanup:
        Optional zero-arg callable run by ``close()``. Set by the
        factory functions (closes connections, removes temp files).
    resources:
        Free-form dict for in-memory state. L0 fixtures populate this
        directly (e.g. ``resources["customers"] = [...]``); L1 fixtures
        may use it for metadata that doesn't fit SQLite (e.g. a row of
        sample IDs returned by a populator).
    """

    level: SimLevel
    conn: Any = None
    cleanup: Callable[[], None] | None = None
    resources: dict[str, Any] = field(default_factory=dict)

    def close(self) -> None:
        """Run cleanup if registered, then mark cleanup as done.

        Safe to call multiple times — second and subsequent calls are
        no-ops because ``cleanup`` is set to ``None`` after the first
        invocation. Exceptions from the cleanup callable propagate (a
        broken cleanup should fail loud, not silently leak resources).
        """
        if self.cleanup is not None:
            try:
                self.cleanup()
            finally:
                self.cleanup = None


# --------------------------------------------------------------------------
# Factory functions — one per level
# --------------------------------------------------------------------------


def create_l0_session() -> SimSession:
    """L0: pure-Python session, no DB.

    Resources is just an empty dict for in-memory state. Each call
    returns a fresh session — there is no global singleton, so two
    parallel L0 sessions cannot accidentally mutate each other's data.
    """
    return SimSession(
        level=SimLevel.L0_PURE,
        conn=None,
        cleanup=None,
        resources={},
    )


def create_l1_session(
    *,
    db_path: Path | str = ":memory:",
) -> SimSession:
    """L1: SQLite session for query-shape tests.

    Args:
        db_path: ``":memory:"`` (default) for an ephemeral in-memory DB;
            a filesystem path for a disk-backed test DB. Disk-backed
            mode is for cases where the test wants to inspect the DB
            after teardown — production tests should stick to
            in-memory.

    The session's ``conn`` is a ``sqlite3.Connection`` with
    ``row_factory = sqlite3.Row`` so cursors return dict-like rows (one
    less foot-gun for fixtures that .keys() the result).

    Cleanup closes the connection. Memory-backed DBs are reclaimed by
    the GC; disk-backed paths are NOT auto-deleted — the caller is
    responsible for using ``tmp_path`` or similar.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    def _cleanup() -> None:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            # SQLite raises on double-close in some backports; swallow
            # so the rest of the cleanup chain still runs.
            pass

    return SimSession(
        level=SimLevel.L1_SQLITE,
        conn=conn,
        cleanup=_cleanup,
        resources={"db_path": str(db_path)},
    )


def create_l2_session() -> SimSession:
    """L2: real PG transient. NotImplementedError — needs PG, deferred to G2.

    Plan: open a v2 PG pool connection, BEGIN a transaction, hand it to
    the caller, and ROLLBACK on close. This requires the v2 PG pool
    (``sylion.aeis_v2.db.pool_v2``) to be wired to a disposable test
    database — that work is gated behind W15 G2.
    """
    raise NotImplementedError("L2 simulation requires PG; deferred to G2")


def create_l3_session() -> SimSession:
    """L3: real PG persistent (dedicated test schema). Placeholder.

    Plan: connect to a long-lived ``sylion_v2_test`` schema, run the
    test against it, leave artifacts behind for post-mortem inspection.
    Requires the same v2 pool plumbing as L2 plus a schema lifecycle
    manager. Out of scope Phase 0.
    """
    raise NotImplementedError(
        "L3 simulation requires persistent PG schema; deferred to W15 G3",
    )


def create_l4_session() -> SimSession:
    """L4: full multi-host federation. Out of scope Phase 0.

    Plan: spin up a small federation (advisor + 2 spokes), run the
    workload across them, tear down. Requires the federation
    coordinator (``sylion.aeis_v2.deployment``) to be sufficiently
    mature, which is multiple charters away.
    """
    raise NotImplementedError(
        "L4 federation simulation out of scope Phase 0; tracked under W17",
    )


_LEVEL_FACTORIES: dict[SimLevel, Callable[..., SimSession]] = {
    SimLevel.L0_PURE: create_l0_session,
    SimLevel.L1_SQLITE: create_l1_session,
    SimLevel.L2_PG_TRANSIENT: create_l2_session,
    SimLevel.L3_PG_PERSISTENT: create_l3_session,
    SimLevel.L4_FEDERATION: create_l4_session,
}


def create_session(level: SimLevel | str, **kwargs: Any) -> SimSession:
    """Factory dispatching on level.

    Args:
        level: ``SimLevel`` enum member or its string value (e.g.
            ``"L0_pure_python"``). Strings make the API friendly to
            CLI/JSON callers that don't import the enum.
        **kwargs: forwarded to the level-specific factory (currently
            only L1 accepts kwargs — ``db_path``).

    Raises:
        ValueError: when ``level`` is a string that doesn't match any
            ``SimLevel`` value.
        NotImplementedError: when ``level`` is L2/L3/L4 (Phase 0 stubs).
    """
    if isinstance(level, str):
        try:
            level = SimLevel(level)
        except ValueError as exc:
            valid = ", ".join(lv.value for lv in SimLevel)
            raise ValueError(
                f"Unknown SimLevel '{level}'. Valid: {valid}",
            ) from exc
    factory = _LEVEL_FACTORIES[level]
    return factory(**kwargs)


@contextmanager
def with_session(
    level: SimLevel | str,
    **kwargs: Any,
) -> Iterator[SimSession]:
    """Context manager for a simulation session.

    Usage::

        with with_session(SimLevel.L1_SQLITE) as sim:
            sim.conn.execute("CREATE TABLE foo (...)")

    Guarantees ``sim.close()`` runs on both normal exit and exception
    paths so a SQLite connection or in-memory state never leaks across
    tests.
    """
    sim = create_session(level, **kwargs)
    try:
        yield sim
    finally:
        sim.close()


# --------------------------------------------------------------------------
# Sample fixtures — demo customers in L0 and L1
# --------------------------------------------------------------------------
#
# These exist so a smoke test of the simulation plane can verify the
# whole shape (factory -> populate -> assertion) without depending on
# the real v2 ontology manifests. The "customer" type here is a
# minimal stand-in — three columns that every CRM-shaped fixture would
# want.


def _demo_customer(idx: int) -> dict[str, Any]:
    """Build one demo customer dict.

    Stable shape so tests can compare against a fixed fixture:
    ``{id, name, email}``. ``id`` is the 1-indexed integer (matches what
    most ORMs assign). Email is deterministic from ``idx`` so the same
    seed always produces the same sequence.
    """
    return {
        "id": idx,
        "name": f"Customer {idx}",
        "email": f"customer{idx}@example.com",
    }


def populate_l0_with_demo_customers(
    sim: SimSession,
    count: int = 5,
) -> list[dict[str, Any]]:
    """Add ``count`` customer dicts to ``sim.resources['customers']``.

    Args:
        sim: an L0 session (raises ValueError on other levels — the L1
            populator below is the right tool for SQLite).
        count: how many customers to add. Defaults to 5.

    Returns:
        The list that was added — same reference now stored under
        ``sim.resources['customers']`` so callers can either use the
        return value or read from the session.
    """
    if sim.level is not SimLevel.L0_PURE:
        raise ValueError(
            f"populate_l0_with_demo_customers requires L0 session, "
            f"got {sim.level.value}",
        )
    customers = [_demo_customer(i) for i in range(1, count + 1)]
    sim.resources["customers"] = customers
    return customers


def populate_l1_with_demo_customers(
    sim: SimSession,
    count: int = 5,
) -> int:
    """CREATE TABLE customer + INSERT ``count`` rows in the L1 sqlite db.

    Args:
        sim: an L1 session (raises ValueError on other levels).
        count: how many rows to insert. Defaults to 5.

    Returns:
        The number of rows actually inserted (``count``). Useful as a
        smoke value for tests; cheaper than re-querying COUNT(*).

    The table shape mirrors ``_demo_customer``:
        ``CREATE TABLE customer (id INTEGER PRIMARY KEY, name TEXT NOT NULL,
        email TEXT NOT NULL)``.

    Idempotent at the DDL level — uses ``CREATE TABLE IF NOT EXISTS`` so
    a second call only adds more rows instead of erroring on duplicate
    table.
    """
    if sim.level is not SimLevel.L1_SQLITE:
        raise ValueError(
            f"populate_l1_with_demo_customers requires L1 session, "
            f"got {sim.level.value}",
        )
    conn: sqlite3.Connection = sim.conn
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customer (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        )
        """,
    )
    rows = [
        (c["id"], c["name"], c["email"])
        for c in (_demo_customer(i) for i in range(1, count + 1))
    ]
    conn.executemany(
        "INSERT INTO customer (id, name, email) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    return count
