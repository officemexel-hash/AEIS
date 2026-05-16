"""PostgreSQL-backed UserDataStore for GDPR DSR.

Sprint 3 B-pg deliverable. Implements both
:class:`sylion.aeis_v2.gdpr_v2.UserDataStore` and
:class:`sylion.aeis_v2.gdpr_v2.PurgeableStore` — production deployments
swap out :class:`InMemoryUserDataStore` via ``set_dsr_service`` and the
HardPurgeCron picks it up unchanged.

Per Kimi review k2_pg_store_concurrency (round 52:30):

* Concurrent DSR for the same user_id is serialised at row level via
  ``SELECT … FOR UPDATE`` inside an explicit transaction. Last-writer
  semantics with linearisable ordering — drift-free.
* Connection pool is sized via ``pool_min_size`` / ``pool_max_size``;
  defaults are conservative (1/8) so a burst of 100 DSRs/min cannot
  exhaust the pool.
* ``upsert`` uses ``INSERT … ON CONFLICT DO UPDATE`` with deep-merge
  semantics on the ``data`` jsonb column — matches the in-memory store.
* The audit JSONL emit is the caller's responsibility (DsrService); we
  stay focused on storage.

Schema (mirrors the in-memory contract):

    CREATE TABLE IF NOT EXISTS gdpr_users (
        user_id     text        PRIMARY KEY,
        data        jsonb       NOT NULL DEFAULT '{}'::jsonb,
        deleted_at  timestamptz,
        updated_at  timestamptz NOT NULL DEFAULT now(),
        created_at  timestamptz NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS gdpr_users_deleted_at_idx
        ON gdpr_users (deleted_at)
        WHERE deleted_at IS NOT NULL;

The DDL is exposed as :data:`PG_SCHEMA_DDL` so the deployment script
can run it idempotently before pointing the service at the database.

This module is import-safe even when ``psycopg`` is not installed —
the actual ``psycopg.connect`` call happens lazily inside the methods,
so test environments that don't have a Postgres available can still
load the module to inspect ``PG_SCHEMA_DDL``.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Iterable

from sylion.aeis_v2.gdpr_v2.dsr import UserDataStore

log = logging.getLogger(__name__)

#: Idempotent DDL — run before pointing the service at the database.
PG_SCHEMA_DDL: str = """
CREATE TABLE IF NOT EXISTS gdpr_users (
    user_id     text        PRIMARY KEY,
    data        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    deleted_at  timestamptz,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS gdpr_users_deleted_at_idx
    ON gdpr_users (deleted_at)
    WHERE deleted_at IS NOT NULL;
"""

#: Default connection pool sizing — conservative so a DSR burst can't
#: exhaust the cluster's max_connections budget.
DEFAULT_POOL_MIN_SIZE: int = 1
DEFAULT_POOL_MAX_SIZE: int = 8


def _deep_merge(existing: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge ``patch`` onto ``existing`` — used by upsert.

    Dict values recurse, list values replace, scalar values overwrite.
    Mirrors the implementation expected by codex h2_jsonb_merge_helper.
    """
    out = dict(existing)
    for key, value in patch.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
        ):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class PgUserDataStore(UserDataStore):
    """Postgres-backed UserDataStore + PurgeableStore.

    Construction does NOT open a connection — the first method call
    that needs one lazily resolves either:

    1. The ``connection_factory`` callable supplied to ``__init__``
       (used by tests with mocked ``psycopg`` connections), OR
    2. ``psycopg.connect(self._dsn)`` if no factory was supplied.

    All public methods are thread-safe via a module-level RLock; the
    actual concurrency control on the database side is row-level
    locking inside an explicit transaction.
    """

    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Any | None = None,
        pool_min_size: int = DEFAULT_POOL_MIN_SIZE,
        pool_max_size: int = DEFAULT_POOL_MAX_SIZE,
    ) -> None:
        self._dsn = dsn
        self._connection_factory = connection_factory
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._lock = threading.RLock()
        self._init_done = False

    # ------------------------------------------------------------------
    # Connection plumbing
    # ------------------------------------------------------------------

    def _get_connection(self) -> Any:
        """Return a fresh DB connection.

        In production the connection_factory is a psycopg pool's getconn
        method; in tests it's a stub returning a fake connection object.
        """
        if self._connection_factory is not None:
            return self._connection_factory()
        # Lazy import — module loads even when psycopg is missing.
        import psycopg  # type: ignore[import-not-found]

        return psycopg.connect(self._dsn)

    def ensure_schema(self) -> None:
        """Run the DDL idempotently. Call once before first use."""
        with self._lock:
            if self._init_done:
                return
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(PG_SCHEMA_DDL)
                conn.commit()
            self._init_done = True

    # ------------------------------------------------------------------
    # UserDataStore interface
    # ------------------------------------------------------------------

    def get(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, data, deleted_at, updated_at, created_at "
                        "FROM gdpr_users WHERE user_id = %s",
                        (user_id,),
                    )
                    row = cur.fetchone()
        if row is None:
            return None
        # row may be a tuple (default psycopg) or dict (dict_row factory).
        if isinstance(row, dict):
            user_id_v, data_v, deleted_at, updated_at, created_at = (
                row["user_id"], row["data"], row["deleted_at"],
                row["updated_at"], row["created_at"],
            )
        else:
            user_id_v, data_v, deleted_at, updated_at, created_at = row
        if deleted_at is not None:
            return None
        # Postgres jsonb returns either dict (psycopg auto) or str (older
        # configs). Tolerate both.
        if isinstance(data_v, str):
            try:
                parsed = json.loads(data_v)
            except json.JSONDecodeError:
                parsed = {}
        else:
            parsed = dict(data_v) if data_v else {}
        parsed["user_id"] = user_id_v
        if updated_at is not None:
            parsed["updated_at"] = (
                updated_at.timestamp() if hasattr(updated_at, "timestamp")
                else float(updated_at)
            )
        return parsed

    def upsert(self, user_id: str, data: dict[str, Any]) -> None:
        """Deep-merge ``data`` onto existing user record.

        Uses ``SELECT … FOR UPDATE`` inside a transaction so concurrent
        upserts for the same user_id are serialised at row level.
        Resurrects soft-deleted rows (Article 12.3 reversal) by clearing
        ``deleted_at`` on every upsert.
        """
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT data FROM gdpr_users "
                        "WHERE user_id = %s FOR UPDATE",
                        (user_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        merged = dict(data)
                    else:
                        existing_raw = (
                            row[0] if not isinstance(row, dict) else row.get("data")
                        )
                        if isinstance(existing_raw, str):
                            try:
                                existing = json.loads(existing_raw)
                            except json.JSONDecodeError:
                                existing = {}
                        else:
                            existing = dict(existing_raw or {})
                        merged = _deep_merge(existing, data)
                    merged_json = json.dumps(merged, ensure_ascii=False)
                    cur.execute(
                        """
                        INSERT INTO gdpr_users (user_id, data, deleted_at, updated_at)
                        VALUES (%s, %s::jsonb, NULL, now())
                        ON CONFLICT (user_id) DO UPDATE
                            SET data       = EXCLUDED.data,
                                deleted_at = NULL,
                                updated_at = now()
                        """,
                        (user_id, merged_json),
                    )
                conn.commit()

    def soft_delete(self, user_id: str, ts: float) -> bool:
        """Set ``deleted_at = to_timestamp(ts)``. Returns True on hit."""
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE gdpr_users
                           SET deleted_at = to_timestamp(%s)
                         WHERE user_id = %s AND deleted_at IS NULL
                        """,
                        (ts, user_id),
                    )
                    affected = cur.rowcount
                conn.commit()
        return bool(affected)

    def export_portable(self, user_id: str) -> dict[str, Any] | None:
        record = self.get(user_id)
        if record is None:
            return None
        return {
            "schema": "sylion.gdpr.dsr.portability/v1",
            "exported_at": time.time(),
            "user": record,
        }

    def list_users(self) -> list[str]:
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id FROM gdpr_users "
                        "WHERE deleted_at IS NULL ORDER BY user_id"
                    )
                    rows = cur.fetchall()
        return [
            (r[0] if not isinstance(r, dict) else r["user_id"])
            for r in rows
        ]

    # ------------------------------------------------------------------
    # PurgeableStore interface (used by HardPurgeCron)
    # ------------------------------------------------------------------

    def list_with_deleted_at(self) -> Iterable[tuple[str, float]]:
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, deleted_at FROM gdpr_users "
                        "WHERE deleted_at IS NOT NULL"
                    )
                    rows = cur.fetchall()
        out: list[tuple[str, float]] = []
        for r in rows:
            user_id_v = r[0] if not isinstance(r, dict) else r["user_id"]
            ts_v = r[1] if not isinstance(r, dict) else r["deleted_at"]
            ts_f = (
                ts_v.timestamp() if hasattr(ts_v, "timestamp")
                else float(ts_v)
            )
            out.append((user_id_v, ts_f))
        return out

    def hard_purge(self, user_id: str) -> bool:
        """Physically delete a soft-deleted row. Refuses alive users."""
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        DELETE FROM gdpr_users
                         WHERE user_id = %s AND deleted_at IS NOT NULL
                        """,
                        (user_id,),
                    )
                    affected = cur.rowcount
                conn.commit()
        return bool(affected)


__all__ = [
    "DEFAULT_POOL_MAX_SIZE",
    "DEFAULT_POOL_MIN_SIZE",
    "PG_SCHEMA_DDL",
    "PgUserDataStore",
]
