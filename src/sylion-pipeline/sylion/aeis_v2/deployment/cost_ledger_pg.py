"""W17 G2 step 2: PG materialized view aggregator for cost-ledger.

Per ADR-001 Decision #3:

- ``sylion_v2.cost_event`` — append-only PG table populated by an
  ``aeis.v2.cost.recorded`` event_bus subscriber (G2 step 3 wires the
  subscriber; this module exposes the DDL + insert helper that the
  subscriber will call).
- ``sylion_v2.mv_cost_ledger`` — materialized view aggregating
  ``cost_event`` per ``(date_trunc('hour', ts), model, host)`` so the
  operator dashboard can answer "spend per model last 7 days" without
  scanning the raw event table on every request.
- ``REFRESH MATERIALIZED VIEW CONCURRENTLY`` runs on a cron schedule
  (G2 step 3 — ``cron_refresh_worker.py``); first refresh after the MV is
  created MUST use ``concurrently=False`` because CONCURRENTLY requires
  a prior populated state and a unique index — both satisfied only after
  the initial population pass.
- The Phase 0 JSONL fallback (``cost_ledger.py``) stays as the
  disaster-recovery spine — when PG is unreachable, operators still have
  the file. A future replay tool will sync the JSONL backlog into
  ``cost_event`` after the database returns.

Module shape mirrors ``sylion.aeis_v2.ontology.applier``:

- ``apply_*_ddl`` returns a ``dict`` with ``applied / statements_executed
  / error`` so the operator UI can render it the same way as
  ``ApplyResult``.
- The pool stub surface used in ``test_ontology_applier`` is reused
  unchanged by ``test_cost_ledger_pg`` so future maintainers learn one
  pattern.
- ``_CONNECTIVITY_EXCS`` import dance is duplicated rather than imported
  cross-module so this file has zero coupling on the W15 applier — the
  cost-ledger PG layer is meant to be deployable independently of W15.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sylion.aeis_v2.deployment.cost_ledger import CostRecord

log = logging.getLogger(__name__)


# Reuse the same "is this a transient connectivity hiccup?" classifier as
# the applier so the operator UI can branch on a stable error prefix
# (``connectivity:`` vs ``ddl:``). Duplicated rather than imported so the
# cost-ledger PG layer has no dep on the W15 applier module.
try:
    import psycopg as _psycopg  # noqa: F401
    _CONNECTIVITY_EXCS: tuple[type[BaseException], ...] = (
        _psycopg.OperationalError,
        _psycopg.InterfaceError,
        BrokenPipeError,
        ConnectionError,
        OSError,
    )
except ImportError:
    _CONNECTIVITY_EXCS = (BrokenPipeError, ConnectionError, OSError)


def _get_pg_connection():
    """Return a psycopg pool or ``None`` if PG unreachable / pool init failed.

    W15 G2 phase 1: prefer the dedicated v2 pool with v1 fallback. The
    cost-ledger PG layer's existing public API (``apply_cost_ledger_pg_ddl``,
    ``insert_cost_event``, ``refresh_mv_cost_ledger``, ``query_mv_cost_ledger``)
    keeps accepting an explicit ``pool`` argument - callers that already
    have a pool (FastAPI route handlers wired up at app startup, tests
    with stub pools) pass it through unchanged. This helper exists for
    new call sites (cron workers, ad-hoc maintenance scripts, future
    in-process schedulers) that want a one-call resolver matching the
    same semantics as the W15 applier.

    Operator rollback: set ``SYLION_USE_V2_POOL=0`` to force the v1
    advisor pool path immediately.

    Delegates to ``sylion.aeis_v2.db.get_pool_with_fallback`` so the
    fallback policy is single-sourced with the W15 applier - see that
    helper for severity gradients and full env-flag semantics.
    """
    from sylion.aeis_v2.db import get_pool_with_fallback
    return get_pool_with_fallback(logger=log)


# --------------------------------------------------------------------------
# DDL — append-only event table + materialized view + indexes
# --------------------------------------------------------------------------
#
# Why split into three constants rather than one big string?
# - ``COST_EVENT_DDL`` and ``MV_COST_LEDGER_DDL`` are emitted in two
#   separate runs by ``apply_cost_ledger_pg_ddl`` so the executor can
#   report ``statements_executed`` accurately if the MV creation fails
#   while the event table succeeds (the table is recoverable; a missing
#   MV just means refresh-mv produces no rows on the first call).
# - ``REFRESH_MV_SQL`` lives at module level so the cron worker (G2
#   step 3) can import the exact same string the tests assert against,
#   keeping the contract single-sourced.
#
# Idempotency is guaranteed by ``CREATE TABLE/INDEX/MATERIALIZED VIEW IF
# NOT EXISTS`` everywhere — ``apply_cost_ledger_pg_ddl(pool)`` can be
# called on every advisor boot without changing the schema after the
# first successful run.

COST_EVENT_DDL = """
CREATE TABLE IF NOT EXISTS sylion_v2.cost_event (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    session_id TEXT,
    decision_id TEXT,
    host TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_in BIGINT NOT NULL DEFAULT 0,
    tokens_out BIGINT NOT NULL DEFAULT 0,
    cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0.0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cost_event_ts_idx ON sylion_v2.cost_event (ts DESC);
CREATE INDEX IF NOT EXISTS cost_event_session_idx ON sylion_v2.cost_event (session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS cost_event_model_idx ON sylion_v2.cost_event (model);
""".strip()


MV_COST_LEDGER_DDL = """
CREATE MATERIALIZED VIEW IF NOT EXISTS sylion_v2.mv_cost_ledger AS
SELECT
    date_trunc('hour', ts) AS hour_bucket,
    model,
    host,
    COUNT(*)::BIGINT AS call_count,
    SUM(tokens_in)::BIGINT AS total_tokens_in,
    SUM(tokens_out)::BIGINT AS total_tokens_out,
    SUM(cost_usd)::NUMERIC(14,6) AS total_usd
FROM sylion_v2.cost_event
GROUP BY date_trunc('hour', ts), model, host
WITH DATA;

-- REFRESH MATERIALIZED VIEW CONCURRENTLY requires a UNIQUE index on the
-- view; without it postgres refuses the concurrent refresh and falls
-- back to taking the exclusive lock that blocks /costs/recent reads.
CREATE UNIQUE INDEX IF NOT EXISTS mv_cost_ledger_pk
    ON sylion_v2.mv_cost_ledger (hour_bucket, model, host);

-- Convenience indexes for the operator-dashboard query patterns:
-- "spend by model" (group on model first) and "newest first" timeline scan.
CREATE INDEX IF NOT EXISTS mv_cost_ledger_model_idx
    ON sylion_v2.mv_cost_ledger (model);
CREATE INDEX IF NOT EXISTS mv_cost_ledger_hour_idx
    ON sylion_v2.mv_cost_ledger (hour_bucket DESC);
""".strip()


REFRESH_MV_SQL = "REFRESH MATERIALIZED VIEW CONCURRENTLY sylion_v2.mv_cost_ledger;"
REFRESH_MV_SQL_BLOCKING = "REFRESH MATERIALIZED VIEW sylion_v2.mv_cost_ledger;"


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------


def _split_statements(ddl: str) -> list[str]:
    """Split a multi-statement DDL block on ``;`` + newline boundaries.

    Naive splitter — fine for our hand-written DDL that does not contain
    semicolons inside string literals or function bodies. Empty
    statements (e.g. trailing newlines) are dropped. Comments are
    preserved as part of the statement they belong to so psycopg sees the
    same SQL the operator sees in the source file.
    """
    out: list[str] = []
    for raw in ddl.split(";"):
        stmt = raw.strip()
        if not stmt:
            continue
        # Re-attach the trailing semicolon so server-side parsers that
        # expect statement terminators don't choke on the last fragment.
        out.append(stmt + ";")
    return out


def _execute_statements_with_conn(
    conn, statements: list[str],
) -> tuple[int, str | None]:
    """Run every DDL statement on an existing connection (no commit, no release).

    Mirrors ``applier._execute_statements_with_conn`` — caller owns the
    connection lifecycle (acquire, commit, release). Returns
    ``(executed, error_or_None)`` with the same ``connectivity:`` /
    ``ddl:`` prefix convention so the operator UI can branch on failure
    class.
    """
    executed = 0
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
                executed += 1
    except _CONNECTIVITY_EXCS as exc:
        return executed, f"connectivity: {type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 — DDL/SQL error class
        return executed, f"ddl: {type(exc).__name__}: {exc}"
    return executed, None


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def apply_cost_ledger_pg_ddl(
    pool, *, dry_run: bool = False,
) -> dict[str, Any]:
    """Apply ``cost_event`` table + ``mv_cost_ledger`` materialized view DDL.

    Idempotent: every CREATE uses ``IF NOT EXISTS`` so re-running on an
    already-applied schema is a safe no-op.

    Args:
        pool: psycopg connection pool (or stub satisfying
            ``pool.connection() -> conn`` with ``conn.cursor()``,
            ``cur.execute(stmt)`` and ``conn.commit()``).
        dry_run: when True, return the would-execute statement count
            without touching the pool. Used by the operator UI's "show
            me what would change" button.

    Returns:
        ``{
            "applied": bool,
            "preview_only": bool,
            "statements_total": int,
            "statements_executed": int,
            "error": str | None,
            "rationale": str,
        }`` — same shape ``apply_manifest`` uses, so the dashboard
        renderer accepts both interchangeably.
    """
    statements = _split_statements(COST_EVENT_DDL) + _split_statements(MV_COST_LEDGER_DDL)
    total = len(statements)

    if dry_run:
        return {
            "applied": False,
            "preview_only": True,
            "statements_total": total,
            "statements_executed": 0,
            "error": None,
            "rationale": (
                f"Dry run — {total} statement gotowe ale nie wykonane "
                f"(cost_event + mv_cost_ledger DDL)."
            ),
        }

    if pool is None:
        return {
            "applied": False,
            "preview_only": True,
            "statements_total": total,
            "statements_executed": 0,
            "error": None,
            "rationale": (
                f"PG niedostepny — DDL nie zaaplikowany ({total} stmt). "
                "Sprawdz polaczenie i sprobuj ponownie."
            ),
        }

    try:
        with pool.connection() as conn:
            executed, error = _execute_statements_with_conn(conn, statements)
            if error is not None:
                log.exception(
                    "cost_ledger_pg: DDL failed at stmt %d/%d: %s",
                    executed + 1, total, error,
                )
                return {
                    "applied": False,
                    "preview_only": False,
                    "statements_total": total,
                    "statements_executed": executed,
                    "error": error,
                    "rationale": (
                        f"DDL wykonany do {executed}/{total} statement gdy "
                        "wystapil blad. Transakcja wycofana. Szczegoly w error."
                    ),
                }
            conn.commit()
    except _CONNECTIVITY_EXCS as exc:
        return {
            "applied": False,
            "preview_only": False,
            "statements_total": total,
            "statements_executed": 0,
            "error": f"connectivity: {type(exc).__name__}: {exc}",
            "rationale": "Polaczenie z PG zerwane podczas DDL — retry mozliwy.",
        }
    except Exception as exc:  # noqa: BLE001 — pool/commit-level DDL error
        return {
            "applied": False,
            "preview_only": False,
            "statements_total": total,
            "statements_executed": 0,
            "error": f"ddl: {type(exc).__name__}: {exc}",
            "rationale": "Blad DDL na poziomie commit — sprawdz schemat.",
        }

    return {
        "applied": True,
        "preview_only": False,
        "statements_total": total,
        "statements_executed": total,
        "error": None,
        "rationale": (
            f"Zaaplikowano {total} statement: cost_event + mv_cost_ledger "
            "z indeksami."
        ),
    }


# Column order of the INSERT statement — single source of truth so the
# tests can assert on it without re-deriving the SQL by string-matching.
COST_EVENT_INSERT_COLUMNS: tuple[str, ...] = (
    "ts",
    "session_id",
    "decision_id",
    "host",
    "model",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "metadata",
)


# Module-level so the cron worker / test harness imports the same string
# that ``insert_cost_event`` actually executes.
COST_EVENT_INSERT_SQL = (
    "INSERT INTO sylion_v2.cost_event "
    "(ts, session_id, decision_id, host, model, tokens_in, tokens_out, "
    "cost_usd, metadata) "
    "VALUES (to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s, %s::jsonb);"
)


def insert_cost_event(pool, record: CostRecord) -> bool:
    """Insert a single ``CostRecord`` into ``sylion_v2.cost_event``.

    The G2 cost-event subscriber calls this in its event-bus handler;
    failure is logged at WARNING and returned as ``False`` so the
    subscriber can decide whether to retry, drop, or fall back to the
    JSONL spine.

    Args:
        pool: psycopg pool or stub with ``pool.connection() -> conn``.
        record: ``CostRecord`` from the event_bus payload.

    Returns:
        ``True`` if the row committed, ``False`` on any error
        (connectivity or SQL). Errors are logged but not raised — the
        caller (event-bus handler) must not crash on a single bad row.
    """
    if pool is None:
        log.warning("cost_ledger_pg: insert_cost_event called with None pool")
        return False

    # Serialize metadata to a JSON string so psycopg's %s::jsonb cast is
    # stable across psycopg2/psycopg3 (psycopg3's adaptation of dict ->
    # json works but is not enabled by default in every deployment).
    import json as _json
    metadata_json = _json.dumps(record.metadata, ensure_ascii=False)

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    COST_EVENT_INSERT_SQL,
                    (
                        float(record.ts),
                        record.session_id or None,
                        record.decision_id or None,
                        record.host,
                        record.model,
                        int(record.tokens_in),
                        int(record.tokens_out),
                        float(record.cost_usd),
                        metadata_json,
                    ),
                )
            conn.commit()
    except _CONNECTIVITY_EXCS as exc:
        log.warning(
            "cost_ledger_pg: insert connectivity error (%s) — record dropped",
            exc,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "cost_ledger_pg: insert sql error (%s) — record dropped", exc,
        )
        return False
    return True


def refresh_mv_cost_ledger(pool, *, concurrently: bool = True) -> bool:
    """Refresh ``sylion_v2.mv_cost_ledger``.

    Args:
        pool: psycopg pool / stub.
        concurrently: when True (default), uses ``REFRESH MATERIALIZED
            VIEW CONCURRENTLY`` so /costs/recent readers are not blocked.
            Pass ``False`` for the FIRST refresh after a fresh
            ``apply_cost_ledger_pg_ddl`` run — CONCURRENTLY requires the
            view to be already populated AND have a unique index, which
            isn't guaranteed at the very first refresh.

    Returns:
        ``True`` on success, ``False`` on any error. Errors are logged at
        WARNING — the cron worker (G2 step 3) decides whether to retry or
        alert the operator.
    """
    if pool is None:
        log.warning("cost_ledger_pg: refresh_mv_cost_ledger called with None pool")
        return False

    sql = REFRESH_MV_SQL if concurrently else REFRESH_MV_SQL_BLOCKING

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
    except _CONNECTIVITY_EXCS as exc:
        log.warning(
            "cost_ledger_pg: refresh connectivity error (%s)", exc,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        log.warning("cost_ledger_pg: refresh sql error (%s)", exc)
        return False
    return True


# Column order returned by the SELECT — single source of truth for both
# the SQL and the dict shape produced by ``query_mv_cost_ledger``.
MV_COST_LEDGER_QUERY_COLUMNS: tuple[str, ...] = (
    "hour_bucket",
    "model",
    "host",
    "call_count",
    "total_tokens_in",
    "total_tokens_out",
    "total_usd",
)


def query_mv_cost_ledger(
    pool,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    model: str | None = None,
    host: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Query the ``mv_cost_ledger`` materialized view with optional filters.

    Args:
        pool: psycopg pool or stub.
        since: lower bound on ``hour_bucket`` (inclusive). ``None`` = no
            lower bound.
        until: upper bound on ``hour_bucket`` (inclusive). ``None`` = no
            upper bound.
        model: exact match filter on the ``model`` column.
        host: exact match filter on the ``host`` column.
        limit: cap rows returned (None = unlimited; in practice clamp at
            the route level via FastAPI query param validation).

    Returns:
        List of dicts keyed by ``MV_COST_LEDGER_QUERY_COLUMNS``. Empty
        list on PG error or when no rows match — the operator UI renders
        "no data in window" identically for both cases.
    """
    if pool is None:
        log.warning("cost_ledger_pg: query_mv_cost_ledger called with None pool")
        return []

    where: list[str] = []
    params: list[Any] = []
    if since is not None:
        where.append("hour_bucket >= %s")
        params.append(since)
    if until is not None:
        where.append("hour_bucket <= %s")
        params.append(until)
    if model is not None:
        where.append("model = %s")
        params.append(model)
    if host is not None:
        where.append("host = %s")
        params.append(host)

    sql_parts = [
        "SELECT hour_bucket, model, host, call_count, total_tokens_in, "
        "total_tokens_out, total_usd FROM sylion_v2.mv_cost_ledger",
    ]
    if where:
        sql_parts.append("WHERE " + " AND ".join(where))
    sql_parts.append("ORDER BY hour_bucket DESC")
    if limit is not None and limit >= 0:
        sql_parts.append("LIMIT %s")
        params.append(int(limit))
    sql = " ".join(sql_parts) + ";"

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall() if hasattr(cur, "fetchall") else []
    except _CONNECTIVITY_EXCS as exc:
        log.warning(
            "cost_ledger_pg: query connectivity error (%s)", exc,
        )
        return []
    except Exception as exc:  # noqa: BLE001
        log.warning("cost_ledger_pg: query sql error (%s)", exc)
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append({k: row.get(k) for k in MV_COST_LEDGER_QUERY_COLUMNS})
        else:
            out.append({
                col: row[i] if i < len(row) else None
                for i, col in enumerate(MV_COST_LEDGER_QUERY_COLUMNS)
            })
    return out
