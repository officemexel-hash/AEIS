"""Subscription quota tracking + remaining-quota lookup."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone
from decimal import Decimal
from typing import NamedTuple

from sylion.aeis.advisor.subscription import _db


class QuotaStatus(NamedTuple):
    has_quota: bool
    remaining_tokens: int
    remaining_usd: Decimal
    period_end: datetime
    plan_id: str
    subscription_id: str


def get_active_subscription_for_model(
    operator_id: str,
    model_id: str,
) -> dict | None:
    """Return active subscription covering this model, or None."""
    return _db.get_subscription_covering_model(operator_id, model_id)


def get_quota_status(operator_id: str, model_id: str) -> QuotaStatus | None:
    """Check if operator has remaining quota for this model in current period."""
    sub = get_active_subscription_for_model(operator_id, model_id)
    if not sub:
        return None

    now = datetime.now(timezone.utc)
    period_start, period_end = _compute_billing_period(now, sub["reset_day_of_month"])
    usage = _db.get_quota_usage(sub["subscription_id"], period_start) or {
        "tokens_consumed": 0,
        "usd_consumed": Decimal("0"),
    }

    token_quota = sub.get("monthly_quota_tokens")
    usd_quota = sub.get("monthly_quota_usd")
    remaining_tokens = max(0, int(token_quota or 0) - int(usage["tokens_consumed"]))
    remaining_usd = max(Decimal("0"), Decimal(str(usd_quota or "0")) - Decimal(str(usage["usd_consumed"])))

    has_token_quota = token_quota is None or remaining_tokens > 0
    has_usd_quota = usd_quota is None or remaining_usd > Decimal("0")

    return QuotaStatus(
        has_quota=has_token_quota and has_usd_quota,
        remaining_tokens=remaining_tokens,
        remaining_usd=remaining_usd,
        period_end=period_end,
        plan_id=str(sub["plan_id"]),
        subscription_id=str(sub["subscription_id"]),
    )


def consume_quota(
    subscription_id: str,
    tokens: int,
    cost_usd: Decimal,
) -> None:
    """Increment quota usage post-call."""
    now = datetime.now(timezone.utc)
    sub = _db.get_subscription(subscription_id)
    if sub is None:
        raise ValueError(f"subscription {subscription_id} not found")
    period_start, period_end = _compute_billing_period(now, sub["reset_day_of_month"])
    _db.upsert_quota_usage(subscription_id, period_start, period_end, tokens, cost_usd)


def _compute_billing_period(now: datetime, reset_day: int) -> tuple[datetime, datetime]:
    """Compute current monthly billing period boundaries."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    reset_day = min(max(int(reset_day), 1), 28)
    current_start = _period_boundary(now.year, now.month, reset_day)
    if now >= current_start:
        period_start = current_start
        next_year, next_month = _shift_month(now.year, now.month, 1)
        period_end = _period_boundary(next_year, next_month, reset_day)
    else:
        prev_year, prev_month = _shift_month(now.year, now.month, -1)
        period_start = _period_boundary(prev_year, prev_month, reset_day)
        period_end = current_start
    return period_start, period_end


def _period_boundary(year: int, month: int, reset_day: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(reset_day, last_day), tzinfo=timezone.utc)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    absolute = (year * 12 + (month - 1)) + delta
    return absolute // 12, absolute % 12 + 1
