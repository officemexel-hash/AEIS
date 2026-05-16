"""Per-operator monthly funding-research token budget enforcement.

The funding module spends tokens for grant-discovery research, scoring with the
LLM judge, consortium search, and simulations. These usages are tracked in
`advisor_funding_research_logs` and capped against
`SYLION_ADVISOR_FUNDING_TOKEN_BUDGET_MONTHLY` (default 100000) per (operator,
calendar month).
"""

from __future__ import annotations

import os
import time

from sylion.aeis.advisor.funding import _db
from sylion.aeis.advisor.funding._models import FundingResearchLog, RESEARCH_PURPOSES


DEFAULT_BUDGET = 100_000


class TokenBudgetExceeded(RuntimeError):
    pass


def monthly_budget() -> int:
    raw = os.environ.get("SYLION_ADVISOR_FUNDING_TOKEN_BUDGET_MONTHLY")
    if not raw:
        return DEFAULT_BUDGET
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_BUDGET


def _start_of_current_month() -> float:
    now = time.gmtime()
    return float(time.mktime((now.tm_year, now.tm_mon, 1, 0, 0, 0, 0, 0, 0)))


def usage_this_month(operator_id: str) -> int:
    return _db.sum_research_tokens_for_period(
        operator_id=operator_id, since_epoch=_start_of_current_month()
    )


def remaining_budget(operator_id: str) -> int:
    return max(0, monthly_budget() - usage_this_month(operator_id))


def check_budget_or_raise(operator_id: str, projected_tokens: int) -> None:
    if remaining_budget(operator_id) < projected_tokens:
        raise TokenBudgetExceeded(
            f"funding token budget exhausted for operator={operator_id} "
            f"projected={projected_tokens} remaining={remaining_budget(operator_id)}"
        )


def record_usage(
    *,
    operator_id: str,
    research_purpose: str,
    prompt_tokens: int,
    response_tokens: int,
    cost_usd: float,
    model_id: str,
    external_research: bool = False,
    related_card_id: str = "",
) -> FundingResearchLog:
    if research_purpose not in RESEARCH_PURPOSES:
        raise ValueError(f"unknown research_purpose: {research_purpose}")
    log_entry = FundingResearchLog(
        operator_id=operator_id,
        research_purpose=research_purpose,
        prompt_tokens=prompt_tokens,
        response_tokens=response_tokens,
        cost_usd=cost_usd,
        model_id=model_id,
        external_research=external_research,
        related_card_id=related_card_id,
    )
    _db.insert_research_log(log_entry)
    return log_entry
