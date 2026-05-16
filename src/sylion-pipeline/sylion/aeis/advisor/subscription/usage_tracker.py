"""AEIS Advisor — Usage tracker."""

from __future__ import annotations

import logging
from typing import Any

from psycopg.rows import dict_row

from sylion.aeis.advisor import _db as shared_db
from sylion.aeis.advisor.subscription._db import ensure_tables
from sylion.aeis.advisor.subscription._models import UsageRecord, UsageReport

log = logging.getLogger("sylion.aeis.advisor.subscription.usage_tracker")


def record_usage(
    operator_id: str,
    provider_id: str,
    model_id: str,
    tokens_in: int,
    tokens_out: int,
    cost: float,
) -> UsageRecord:
    """Record a usage entry."""
    ensure_tables()
    rec = UsageRecord(
        operator_id=operator_id,
        provider_id=provider_id,
        model_id=model_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
    )
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO subscription_usage
            (record_id, operator_id, provider_id, model_id, tokens_in, tokens_out, cost_usd, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                rec.record_id,
                rec.operator_id,
                rec.provider_id,
                rec.model_id,
                rec.tokens_in,
                rec.tokens_out,
                rec.cost_usd,
                rec.timestamp,
            ),
        )
    return rec


def get_usage_report(
    operator_id: str,
    period_start: float,
    period_end: float,
) -> UsageReport:
    """Get aggregated usage report for a period."""
    ensure_tables()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT
                SUM(tokens_in) as total_tokens_in,
                SUM(tokens_out) as total_tokens_out,
                SUM(cost_usd) as total_cost_usd,
                COUNT(*) as record_count
            FROM subscription_usage
            WHERE operator_id = %s AND timestamp >= %s AND timestamp <= %s""",
            (operator_id, period_start, period_end),
        )
        row = cur.fetchone()
    return UsageReport(
        operator_id=operator_id,
        period_start=period_start,
        period_end=period_end,
        total_tokens_in=row["total_tokens_in"] or 0,
        total_tokens_out=row["total_tokens_out"] or 0,
        total_cost_usd=row["total_cost_usd"] or 0.0,
        record_count=row["record_count"] or 0,
    )
