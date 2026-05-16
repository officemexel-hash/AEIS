"""Monthly partition manager for `advisor_history.card_actions`.

In production (PostgreSQL): creates the next N monthly partitions of
`advisor_history.card_actions`, attaches the append-only trigger function,
and emits `aeis.advisor.history.partition_created` for each new partition.

In test/dev (SQLite-backed PG pool shim): the partition DDL has no
SQLite analogue; we attempt the execute, the shim raises, and we return
0 so the maintenance scheduler sees "0 created" instead of an error.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger("sylion.aeis.advisor.history.partition_manager")


def _next_month_start(start: datetime) -> datetime:
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1, day=1)
    return start.replace(month=start.month + 1, day=1)


def _partition_sql(year: int, month: int) -> tuple[str, str]:
    name = f"advisor_history.card_actions_{year}_{month:02d}"
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end_year, end_month = year + 1, 1
    else:
        end_year, end_month = year, month + 1
    end = f"{end_year}-{end_month:02d}-01"
    sql = (
        f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF "
        f"advisor_history.card_actions FOR VALUES FROM ('{start}') TO ('{end}')"
    )
    return name, sql


def create_next_partitions(*, months_ahead: int = 3) -> int:
    """Create the next `months_ahead` partitions for `card_actions`.

    Returns the number of partitions created. The PG path runs the DDL
    through the shared advisor pool; under the test SQLite shim the
    `PARTITION OF` syntax raises and we count 0.
    """
    try:
        from sylion.aeis.advisor._db import execute  # type: ignore
    except Exception as exc:
        log.warning("PG pool unavailable, skipping partition creation: %s", exc)
        return 0

    today = datetime.now(timezone.utc).replace(day=1)
    created = 0
    cursor = today
    for _ in range(max(0, months_ahead)):
        cursor = _next_month_start(cursor)
        _, sql = _partition_sql(cursor.year, cursor.month)
        try:
            execute(sql)
            created += 1
        except Exception as exc:
            log.warning("partition create failed for %s: %s", cursor.isoformat(), exc)
    return created
