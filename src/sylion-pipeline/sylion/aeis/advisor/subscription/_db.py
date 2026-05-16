"""AEIS Advisor - Subscription DB layer (PG-only)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from psycopg.rows import dict_row

from sylion.aeis.advisor import _db as shared_db

log = logging.getLogger("sylion.aeis.advisor.subscription._db")


def ensure_tables() -> None:
    """No-op in PG-only mode. Schema lives in Alembic migration."""
    return None


def list_active_subscriptions(operator_id: str) -> list[dict[str, Any]]:
    sql = """
        SELECT subscription_id, operator_id, provider_id, plan_id,
               monthly_quota_tokens, monthly_quota_usd, reset_day_of_month,
               models_covered, active_from, active_until, monthly_fee_usd, is_active
        FROM advisor_subscription.active_subscriptions
        WHERE operator_id = %s
          AND is_active = true
          AND active_from <= now()
          AND (active_until IS NULL OR active_until >= now())
        ORDER BY active_from DESC, subscription_id DESC
    """
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, (operator_id,))
        return [_normalize_subscription_row(row) for row in cur.fetchall()]


def create_subscription(
    *,
    operator_id: str,
    provider_id: str,
    plan_id: str,
    monthly_quota_tokens: int | None = None,
    monthly_quota_usd: Decimal | float | str | None = None,
    reset_day_of_month: int = 1,
    models_covered: list[str] | None = None,
    active_from: datetime | None = None,
    active_until: datetime | None = None,
    monthly_fee_usd: Decimal | float | str | None = None,
    is_active: bool = True,
) -> dict[str, Any]:
    sql = """
        INSERT INTO advisor_subscription.active_subscriptions (
            operator_id, provider_id, plan_id, monthly_quota_tokens, monthly_quota_usd,
            reset_day_of_month, models_covered, active_from, active_until, monthly_fee_usd, is_active
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::text[], %s, %s, %s, %s)
        RETURNING subscription_id, operator_id, provider_id, plan_id,
                  monthly_quota_tokens, monthly_quota_usd, reset_day_of_month,
                  models_covered, active_from, active_until, monthly_fee_usd, is_active
    """
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            sql,
            (
                operator_id,
                provider_id,
                plan_id,
                monthly_quota_tokens,
                _decimal_or_none(monthly_quota_usd),
                _sanitize_reset_day(reset_day_of_month),
                models_covered or [],
                active_from or datetime.now(timezone.utc),
                active_until,
                _decimal_or_none(monthly_fee_usd),
                is_active,
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("subscription insert did not return a row")
    return _normalize_subscription_row(row)


def deactivate_subscription(subscription_id: str) -> bool:
    sql = """
        UPDATE advisor_subscription.active_subscriptions
        SET is_active = false, active_until = COALESCE(active_until, now())
        WHERE subscription_id = %s
          AND is_active = true
    """
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (subscription_id,))
        return cur.rowcount > 0


def get_subscription(subscription_id: str) -> dict[str, Any] | None:
    sql = """
        SELECT subscription_id, operator_id, provider_id, plan_id,
               monthly_quota_tokens, monthly_quota_usd, reset_day_of_month,
               models_covered, active_from, active_until, monthly_fee_usd, is_active
        FROM advisor_subscription.active_subscriptions
        WHERE subscription_id = %s
    """
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, (subscription_id,))
        row = cur.fetchone()
    if row is None:
        return None
    return _normalize_subscription_row(row)


def get_subscription_covering_model(operator_id: str, model_id: str) -> dict[str, Any] | None:
    sql = """
        SELECT subscription_id, operator_id, provider_id, plan_id,
               monthly_quota_tokens, monthly_quota_usd, reset_day_of_month,
               models_covered, active_from, active_until, monthly_fee_usd, is_active
        FROM advisor_subscription.active_subscriptions
        WHERE operator_id = %s
          AND is_active = true
          AND active_from <= now()
          AND (active_until IS NULL OR active_until >= now())
          AND %s = ANY(COALESCE(models_covered, ARRAY[]::text[]))
        ORDER BY active_from DESC, subscription_id DESC
        LIMIT 1
    """
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, (operator_id, model_id))
        row = cur.fetchone()
    if row is None:
        return None
    return _normalize_subscription_row(row)


def get_quota_usage(subscription_id: str, period_start: datetime) -> dict[str, Any] | None:
    sql = """
        SELECT usage_id, subscription_id, period_start, period_end,
               tokens_consumed, usd_consumed, call_count, last_call_at
        FROM advisor_subscription.quota_usage
        WHERE subscription_id = %s AND period_start = %s
    """
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, (subscription_id, period_start))
        row = cur.fetchone()
    if row is None:
        return None
    return _normalize_quota_usage_row(row)


def upsert_quota_usage(
    subscription_id: str,
    period_start: datetime,
    period_end: datetime,
    tokens: int,
    cost_usd: Decimal | float | str,
) -> dict[str, Any]:
    sql = """
        INSERT INTO advisor_subscription.quota_usage (
            subscription_id, period_start, period_end, tokens_consumed,
            usd_consumed, call_count, last_call_at
        )
        VALUES (%s, %s, %s, %s, %s, 1, now())
        ON CONFLICT (subscription_id, period_start) DO UPDATE SET
            period_end = EXCLUDED.period_end,
            tokens_consumed = advisor_subscription.quota_usage.tokens_consumed + EXCLUDED.tokens_consumed,
            usd_consumed = advisor_subscription.quota_usage.usd_consumed + EXCLUDED.usd_consumed,
            call_count = advisor_subscription.quota_usage.call_count + 1,
            last_call_at = now()
        RETURNING usage_id, subscription_id, period_start, period_end,
                  tokens_consumed, usd_consumed, call_count, last_call_at
    """
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            sql,
            (
                subscription_id,
                period_start,
                period_end,
                max(0, int(tokens)),
                _decimal_or_zero(cost_usd),
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("quota usage upsert did not return a row")
    return _normalize_quota_usage_row(row)


def _normalize_subscription_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["monthly_quota_usd"] = _decimal_or_none(out.get("monthly_quota_usd"))
    out["monthly_fee_usd"] = _decimal_or_none(out.get("monthly_fee_usd"))
    out["reset_day_of_month"] = _sanitize_reset_day(out.get("reset_day_of_month") or 1)
    out["models_covered"] = list(out.get("models_covered") or [])
    if out.get("monthly_quota_tokens") is not None:
        out["monthly_quota_tokens"] = int(out["monthly_quota_tokens"])
    return out


def _normalize_quota_usage_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["tokens_consumed"] = int(out.get("tokens_consumed") or 0)
    out["call_count"] = int(out.get("call_count") or 0)
    out["usd_consumed"] = _decimal_or_zero(out.get("usd_consumed"))
    return out


def _sanitize_reset_day(value: int | None) -> int:
    day = int(value or 1)
    return min(max(day, 1), 28)


def _decimal_or_zero(value: Decimal | float | str | None) -> Decimal:
    return _decimal_or_none(value) or Decimal("0")


def _decimal_or_none(value: Decimal | float | str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
