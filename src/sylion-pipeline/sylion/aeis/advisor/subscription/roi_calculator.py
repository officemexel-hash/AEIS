"""AEIS Advisor — ROI calculator."""

from __future__ import annotations

import logging
from typing import Any

from sylion.aeis.advisor.subscription._models import ROICalculation
from sylion.aeis.advisor.subscription.plan_catalog import get_plan
from sylion.aeis.advisor.subscription.usage_tracker import get_usage_report

log = logging.getLogger("sylion.aeis.advisor.subscription.roi_calculator")


def compute_roi(
    operator_id: str,
    plan_id: str,
    observation_window_days: int = 30,
) -> ROICalculation:
    """Compute ROI for a plan over an observation window."""
    import time

    plan = get_plan(plan_id)
    if plan is None:
        return ROICalculation(
            operator_id=operator_id,
            plan_id=plan_id,
            observation_window_days=observation_window_days,
            recommendation="unknown_plan",
        )

    period_end = time.time()
    period_start = period_end - (observation_window_days * 86400)
    report = get_usage_report(operator_id, period_start, period_end)

    usage_cost = report.total_cost_usd
    plan_monthly = plan.monthly_price_usd
    plan_cost_for_window = plan_monthly * (observation_window_days / 30.0)

    # Break-even: when usage cost equals plan cost
    daily_usage = usage_cost / observation_window_days if observation_window_days > 0 else 0.0
    break_even_days = None
    if daily_usage > 0:
        break_even_days = round(plan_monthly / daily_usage, 1)

    # Recommendation logic
    if usage_cost == 0:
        recommendation = "downgrade"
    elif usage_cost > plan_cost_for_window * 1.5:
        recommendation = "upgrade"
    elif usage_cost < plan_cost_for_window * 0.3:
        recommendation = "downgrade"
    else:
        recommendation = "keep"

    return ROICalculation(
        operator_id=operator_id,
        plan_id=plan_id,
        observation_window_days=observation_window_days,
        usage_cost_without_plan=round(usage_cost, 2),
        plan_cost=round(plan_cost_for_window, 2),
        break_even_days=break_even_days,
        recommendation=recommendation,
    )
