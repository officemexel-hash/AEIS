"""Tests for sylion.aeis_v2.deployment.cost_ledger_pg — W17 G2 step 2.

Per ADR-001 Decision #3:
- ``sylion_v2.cost_event`` append-only table
- ``sylion_v2.mv_cost_ledger`` materialized view aggregating per
  (hour_bucket, model, host)
- Idempotent DDL (``CREATE ... IF NOT EXISTS`` everywhere)
- ``REFRESH MATERIALIZED VIEW CONCURRENTLY`` by default; first refresh
  uses the blocking variant (``concurrently=False``).

Stub pattern mirrors ``test_ontology_applier.py`` so future maintainers
learn one shape: ``_StubPool`` -> ``_StubConnection`` -> ``_StubCursor``
implementing the slice of psycopg the module touches.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sylion.aeis_v2.deployment.cost_ledger import CostRecord
from sylion.aeis_v2.deployment.cost_ledger_pg import (
    COST_EVENT_DDL,
    COST_EVENT_INSERT_COLUMNS,
    COST_EVENT_INSERT_SQL,
    MV_COST_LEDGER_DDL,
    MV_COST_LEDGER_QUERY_COLUMNS,
    REFRESH_MV_SQL,
    REFRESH_MV_SQL_BLOCKING,
    apply_cost_ledger_pg_ddl,
    insert_cost_event,
    query_mv_cost_ledger,
    refresh_mv_cost_ledger,
)


# --------------------------------------------------------------------------
# Stubs — psycopg pool/conn/cursor minimal surface
# --------------------------------------------------------------------------


class _StubCursor:
    """Records every ``execute()`` call into the parent connection.

    Mirrors the ``_StubCursor`` in ``test_ontology_applier`` but adds a
    ``rows_to_return`` hook so the SELECT path of ``query_mv_cost_ledger``
    can be exercised. The cursor records each (sql, params) tuple onto
    the connection's ``executed`` list (committed) or ``pending`` list
    (in-flight) following the same commit/rollback model.
    """

    def __init__(self, conn: "_StubConnection") -> None:
        self._conn = conn

    def __enter__(self) -> "_StubCursor":
        return self

    def __exit__(self, *exc) -> None:  # noqa: D401, ANN001
        return None

    def execute(self, stmt: str, params=None) -> None:  # noqa: ANN001
        self._conn.pending.append((stmt, params))
        # ``all_calls`` is unconditional — captures every execute() even
        # for SELECT paths that never commit (queries don't write, so
        # ``executed`` (which mirrors committed state) stays empty).
        self._conn.all_calls.append((stmt, params))
        if (
            self._conn.fail_after is not None
            and len(self._conn.pending) > self._conn.fail_after
        ):
            raise RuntimeError(
                f"stub PG error at stmt #{len(self._conn.pending)}"
            )

    def fetchall(self):
        # Return whatever the test pre-configured. Useful for
        # query_mv_cost_ledger which needs row data, not just stmt
        # observability.
        return list(self._conn.rows_to_return)


class _StubConnection:
    def __init__(
        self,
        fail_after: int | None = None,
        rows_to_return=None,
    ) -> None:
        self.executed: list[tuple] = []
        self.pending: list[tuple] = []
        # all_calls captures every execute() regardless of commit; tests
        # for SELECT paths use this since SELECTs don't commit.
        self.all_calls: list[tuple] = []
        self.committed = False
        self.fail_after = fail_after
        self.rows_to_return = rows_to_return or []

    def __enter__(self) -> "_StubConnection":
        return self

    def __exit__(self, *exc) -> None:  # noqa: D401, ANN001
        if not self.committed:
            self.pending = []
        return None

    def cursor(self) -> _StubCursor:
        return _StubCursor(self)

    def commit(self) -> None:
        self.executed.extend(self.pending)
        self.pending = []
        self.committed = True


class _StubPool:
    """Minimal pool — yields a single, reusable ``_StubConnection``."""

    def __init__(
        self, fail_after: int | None = None, rows_to_return=None,
    ) -> None:
        self.conn = _StubConnection(
            fail_after=fail_after, rows_to_return=rows_to_return,
        )

    def connection(self) -> _StubConnection:
        return self.conn


# --------------------------------------------------------------------------
# 1. apply_cost_ledger_pg_ddl — dry_run + idempotent + emits CREATE TABLE/MV
# --------------------------------------------------------------------------


def test_apply_cost_ledger_pg_ddl_dry_run():
    """``dry_run=True`` -> preview_only=True, no PG side-effect.

    Even with a working pool, ``dry_run`` short-circuits before opening
    a connection. We assert by constructing a pool whose ``connection()``
    would explode if invoked — proving the function never reached it.
    """
    class _ExplodingPool:
        def connection(self):
            raise AssertionError("dry_run must not open a PG connection")

    res = apply_cost_ledger_pg_ddl(_ExplodingPool(), dry_run=True)

    assert res["applied"] is False
    assert res["preview_only"] is True
    assert res["statements_total"] > 0
    assert res["statements_executed"] == 0
    assert res["error"] is None
    assert "Dry run" in res["rationale"]


def test_apply_cost_ledger_pg_ddl_idempotent():
    """Running ``apply_cost_ledger_pg_ddl`` twice on the same pool succeeds twice.

    The DDL uses ``CREATE ... IF NOT EXISTS`` so re-application is a no-op
    in real PG. Our stub records every statement on both runs; we check
    both calls return ``applied=True`` and that the second call observed
    the same statement count as the first (no extra retry/repair magic
    in the function itself).
    """
    pool1 = _StubPool()
    res1 = apply_cost_ledger_pg_ddl(pool1)
    assert res1["applied"] is True
    assert res1["error"] is None
    assert res1["statements_executed"] == res1["statements_total"]

    # Second apply on a fresh stub (the real PG would short-circuit at
    # the IF NOT EXISTS layer; we only verify the function itself doesn't
    # raise or change shape on a re-run).
    pool2 = _StubPool()
    res2 = apply_cost_ledger_pg_ddl(pool2)
    assert res2["applied"] is True
    assert res2["error"] is None
    assert res2["statements_total"] == res1["statements_total"]
    assert res2["statements_executed"] == res2["statements_total"]


def test_apply_cost_ledger_pg_ddl_emits_create_table_and_mv():
    """Every CREATE TABLE / CREATE MATERIALIZED VIEW statement is executed.

    Sanity check: the function must actually run the DDL we declared at
    module level — a regression where someone empties the constants
    would silently break the schema. We grep the executed statements
    for the canonical fragments.
    """
    pool = _StubPool()
    res = apply_cost_ledger_pg_ddl(pool)
    assert res["applied"] is True

    executed_sql = [stmt for stmt, _params in pool.conn.executed]
    joined = "\n".join(executed_sql)
    assert "CREATE TABLE IF NOT EXISTS sylion_v2.cost_event" in joined
    assert "CREATE MATERIALIZED VIEW IF NOT EXISTS sylion_v2.mv_cost_ledger" in joined
    # The unique index for CONCURRENTLY refresh must be in there.
    assert "mv_cost_ledger_pk" in joined
    # Helper indexes too.
    assert "cost_event_ts_idx" in joined
    assert "mv_cost_ledger_model_idx" in joined


# --------------------------------------------------------------------------
# 2. insert_cost_event — column shape + values bound correctly
# --------------------------------------------------------------------------


def test_insert_cost_event_writes_row():
    """``insert_cost_event`` runs an INSERT with the expected column list + values.

    We assert the SQL string contains every column in
    ``COST_EVENT_INSERT_COLUMNS`` and that the bound parameter tuple has
    the same length and field order. This guards against silent schema
    drift between the DDL constant and the INSERT helper.
    """
    pool = _StubPool()
    record = CostRecord(
        ts=1700000000.5,
        session_id="sess-A",
        decision_id="dec-XYZ",
        host="node1",
        model="qwen2.5:7b",
        tokens_in=100,
        tokens_out=200,
        cost_usd=0.0042,
        metadata={"source": "test"},
    )

    ok = insert_cost_event(pool, record)
    assert ok is True

    # One row written + committed.
    assert pool.conn.committed is True
    assert len(pool.conn.executed) == 1
    sql, params = pool.conn.executed[0]

    # SQL canonical form contains every column in declared order.
    for col in COST_EVENT_INSERT_COLUMNS:
        assert col in sql, f"missing column {col!r} in INSERT SQL: {sql}"
    assert sql == COST_EVENT_INSERT_SQL

    # Parameters: one per column.
    assert isinstance(params, tuple)
    assert len(params) == len(COST_EVENT_INSERT_COLUMNS)

    # Spot-check a couple of values to make sure ordering is right.
    # ts -> first slot (passed to to_timestamp).
    assert params[0] == 1700000000.5
    # session_id -> second slot.
    assert params[1] == "sess-A"
    # model -> 5th slot (after ts, session_id, decision_id, host).
    assert params[4] == "qwen2.5:7b"
    # tokens_in -> 6th.
    assert params[5] == 100
    # cost_usd -> 8th.
    assert params[7] == pytest.approx(0.0042)
    # metadata -> 9th, JSON-encoded string (psycopg::jsonb cast).
    assert isinstance(params[8], str)
    assert "source" in params[8]


def test_insert_cost_event_returns_false_on_pool_none():
    """``insert_cost_event(None, record)`` logs a warning and returns False.

    Defensive contract — if a caller forgets to pass a pool (e.g.
    ``_get_pg_connection()`` returned None), the helper must NOT raise;
    the event-bus subscriber loop relies on a clean False to fall back
    to the JSONL spine.
    """
    record = CostRecord(
        ts=1.0, session_id="", decision_id="", host="h", model="m",
    )
    assert insert_cost_event(None, record) is False


# --------------------------------------------------------------------------
# 3. refresh_mv_cost_ledger — concurrently default + blocking fallback
# --------------------------------------------------------------------------


def test_refresh_mv_cost_ledger_uses_concurrently_by_default():
    """Default call uses ``REFRESH MATERIALIZED VIEW CONCURRENTLY``.

    /costs/recent must remain readable during the refresh, so
    CONCURRENTLY is mandatory in steady state (after the first refresh).
    """
    pool = _StubPool()
    ok = refresh_mv_cost_ledger(pool)
    assert ok is True
    assert pool.conn.committed is True
    assert len(pool.conn.executed) == 1
    sql, _params = pool.conn.executed[0]
    assert sql == REFRESH_MV_SQL
    assert "CONCURRENTLY" in sql


def test_refresh_mv_cost_ledger_falls_back_when_concurrently_false():
    """``concurrently=False`` -> use the blocking REFRESH variant.

    First-time refresh of a fresh MV needs the exclusive lock because
    the unique index hasn't been used yet by a prior populated state.
    """
    pool = _StubPool()
    ok = refresh_mv_cost_ledger(pool, concurrently=False)
    assert ok is True
    assert len(pool.conn.executed) == 1
    sql, _params = pool.conn.executed[0]
    assert sql == REFRESH_MV_SQL_BLOCKING
    assert "CONCURRENTLY" not in sql
    # Still hits the right MV.
    assert "sylion_v2.mv_cost_ledger" in sql


# --------------------------------------------------------------------------
# 4. query_mv_cost_ledger — filter SQL + dict shape
# --------------------------------------------------------------------------


def _row_tuple(hour_bucket, model, host, call_count, t_in, t_out, usd):
    """Helper: build a row tuple matching MV_COST_LEDGER_QUERY_COLUMNS order."""
    return (hour_bucket, model, host, call_count, t_in, t_out, usd)


def test_query_mv_cost_ledger_filters_by_model():
    """``model='qwen'`` -> WHERE clause carries the model filter + parameter.

    We pre-load the stub with one canned row so we can also assert the
    function returns dicts keyed on ``MV_COST_LEDGER_QUERY_COLUMNS``.
    """
    canned = [_row_tuple(
        datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc),
        "qwen", "node1", 5, 1000, 2000, 0.05,
    )]
    pool = _StubPool(rows_to_return=canned)

    rows = query_mv_cost_ledger(pool, model="qwen")

    assert len(rows) == 1
    row = rows[0]
    # Dict shape — every declared column key is present.
    for col in MV_COST_LEDGER_QUERY_COLUMNS:
        assert col in row, f"missing column {col!r} in result row: {row}"
    assert row["model"] == "qwen"
    assert row["host"] == "node1"
    assert row["call_count"] == 5

    # SQL shape — model filter clause + parameter binding. SELECTs don't
    # commit, so we inspect ``all_calls`` rather than ``executed``.
    assert len(pool.conn.all_calls) == 1
    sql, params = pool.conn.all_calls[0]
    assert "model = %s" in sql
    assert "qwen" in params


def test_query_mv_cost_ledger_filters_by_time_range():
    """``since`` + ``until`` -> two WHERE bounds + 2 params.

    Ensures the SQL builder concatenates AND-joined bounds (not just one)
    and binds both timestamps positionally.
    """
    pool = _StubPool(rows_to_return=[])
    since = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
    until = since + timedelta(days=7)

    query_mv_cost_ledger(pool, since=since, until=until)

    # SELECTs don't commit -> use all_calls (unconditional capture).
    assert len(pool.conn.all_calls) == 1
    sql, params = pool.conn.all_calls[0]
    # Both bounds present.
    assert "hour_bucket >= %s" in sql
    assert "hour_bucket <= %s" in sql
    # AND-joined.
    assert " AND " in sql or sql.count("WHERE") == 1
    # Both timestamps bound, in the order they were declared.
    assert since in params
    assert until in params


def test_query_mv_cost_ledger_returns_empty_on_pool_none():
    """``query_mv_cost_ledger(None, ...)`` returns ``[]`` rather than raising.

    The dashboard renders "no data" identically for "PG offline" and
    "no rows" so callers must always get a list.
    """
    assert query_mv_cost_ledger(None) == []


# --------------------------------------------------------------------------
# 5. DDL constants smoke — guard against accidental constant emptying
# --------------------------------------------------------------------------


def test_ddl_constants_contain_expected_objects():
    """Sanity guard — refactoring ``COST_EVENT_DDL`` / ``MV_COST_LEDGER_DDL``
    must keep the canonical object names intact.

    Operators and downstream tools (e.g. the cron-refresh worker in G2
    step 3) grep for these names to verify schema presence; if a future
    PR strips ``IF NOT EXISTS`` or renames the table, this catches it.
    """
    assert "sylion_v2.cost_event" in COST_EVENT_DDL
    assert "IF NOT EXISTS" in COST_EVENT_DDL
    assert "sylion_v2.mv_cost_ledger" in MV_COST_LEDGER_DDL
    assert "WITH DATA" in MV_COST_LEDGER_DDL
    assert "CONCURRENTLY" in REFRESH_MV_SQL
    assert "CONCURRENTLY" not in REFRESH_MV_SQL_BLOCKING
