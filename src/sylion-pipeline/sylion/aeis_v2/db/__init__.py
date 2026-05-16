"""W15 G2: dedicated v2 PostgreSQL pool package.

Phase 0 of the G2 migration shipped the pool foundation only
(``pool_v2.get_v2_pool``). Phase 1 (this round) wires the consumer-side
fallback helper used by the W15 applier and the W17 cost-ledger PG
layer so they prefer the v2 pool when available and gracefully fall
back to the v1 advisor pool when the v2 path is disabled or fails to
import.

Re-exports the public surface so call sites can do::

    from sylion.aeis_v2.db import get_v2_pool, get_pool_with_fallback

without reaching into the ``pool_v2`` submodule.

Operator rollback path:

- ``SYLION_USE_V2_POOL=0`` -> skip the v2 pool entirely; route every
  acquisition through the v1 advisor pool. Use this when the v2 pool
  misbehaves under load and you need the legacy code path immediately.
- ``SYLION_USE_V2_POOL=1`` (default) -> try v2 first, fall back to v1
  only if v2 returns ``None`` or its module is not importable.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sylion.aeis_v2.db.pg_schema_diff import PgSchemaDiff
from sylion.aeis_v2.db.pool_v2 import get_v2_pool, reset_v2_pool

__all__ = ["PgSchemaDiff", "get_v2_pool", "reset_v2_pool", "get_pool_with_fallback"]


_log = logging.getLogger(__name__)


def get_pool_with_fallback(*, logger: logging.Logger | None = None) -> Any:
    """Return a psycopg pool, preferring v2 with v1 fallback.

    Phase 1 of the W15 G2 pool migration. The applier and the
    cost-ledger PG layer both call this helper so they share one
    rollback knob (``SYLION_USE_V2_POOL``) and one set of severity
    gradients in the logs.

    Resolution order:

    1. If ``SYLION_USE_V2_POOL`` is set to ``"0"``, skip step 2 entirely
       — operator forced rollback to v1.
    2. Try ``get_v2_pool()``. If it returns a pool, that's what we
       use. If the import itself fails (packaging defect, partial
       deployment), log at ERROR and fall through to step 3.
    3. Fall back to v1 ``sylion.aeis.advisor._db.get_pool()``. The
       three-branch error handling matches the historical applier
       contract:

       - ``ImportError`` (advisor pool module missing): log.error,
         return ``None``. Packaging defect — caller goes preview-only.
       - ``PGUnreachable`` (typed exception from v1 ``_db``): log.info,
         return ``None``. Routine — PG offline.
       - any other ``Exception``: log.error with ``exc_info=True``,
         return ``None``. Unexpected — pool init blew up.

    Args:
        logger: optional logger override. Defaults to this module's
            logger (``sylion.aeis_v2.db``). Callers pass their own
            module logger so log lines are attributed to the calling
            module (applier, cost_ledger_pg, etc.) without needing to
            mutate the helper's behavior.

    Returns:
        A psycopg connection pool, or ``None`` when neither pool is
        reachable.
    """
    log = logger or _log
    use_v2 = os.environ.get("SYLION_USE_V2_POOL", "1") == "1"

    if use_v2:
        try:
            v2_pool = get_v2_pool()
        except ImportError as exc:
            log.error(
                "pool fallback: v2 pool import failed (%s) - falling back "
                "to v1 advisor pool",
                exc,
            )
        else:
            if v2_pool is not None:
                return v2_pool
            # v2 returned None (PG unreachable from v2's perspective, or
            # advisor _db missing inside pool_v2). Fall through to v1 -
            # if v1 is reachable, the v2 path likely just hit a transient
            # blip; if v1 is also unreachable, both will return None
            # and the caller goes preview-only either way.

    try:
        from sylion.aeis.advisor._db import PGUnreachable, get_pool
    except ImportError as exc:
        log.error(
            "pool fallback: v1 advisor pool module missing (%s) - install "
            "the 'advisor' extra; preview-only mode",
            exc,
        )
        return None

    try:
        return get_pool()
    except PGUnreachable as exc:
        log.info(
            "pool fallback: PG unreachable (%s) - preview-only mode", exc,
        )
        return None
    except Exception as exc:  # noqa: BLE001 - unexpected pool init failure
        log.error(
            "pool fallback: pool init failed unexpectedly (%s) - "
            "investigate config/env; preview-only mode for now",
            exc, exc_info=True,
        )
        return None
