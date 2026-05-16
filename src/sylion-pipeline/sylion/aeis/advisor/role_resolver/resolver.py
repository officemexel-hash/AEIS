"""Role resolution with subscription-first cost routing.

Priority order:
1. Operator override
2. Blocked providers exclusion
3. Active subscription quota preference
4. PAYG ceiling enforcement
5. Default routing matrix
6. Local fallback if nothing else available
"""

from __future__ import annotations

import logging

from sylion.aeis.advisor.role_resolver._models import ModelChoice
from sylion.aeis.advisor.role_resolver.routing_table import (
    DEFAULT_ROUTING_BY_PURPOSE,
    DEFAULT_ROUTING_BY_ROLE,
)

log = logging.getLogger("sylion.aeis.advisor.role_resolver.resolver")


def _provider_of(model_id: str) -> str:
    """Determine provider from model_id."""
    if model_id.startswith("claude"):
        return "anthropic"
    if model_id.startswith("gpt"):
        return "openai"
    if model_id.startswith("gemini"):
        return "google"
    if model_id.startswith("qwen"):
        return "local"
    return "unknown"


def _is_model_available(operator_id: str, model_id: str) -> bool:
    """Check if model is available (not blocked and known to pricing)."""
    from sylion.aeis.advisor.preferences import get_preferences
    from sylion.aeis.advisor.pricing import catalog

    blocked = get_preferences().get_blocked_providers(user_id=operator_id) or []
    provider = _provider_of(model_id)
    if provider in blocked:
        return False
    return catalog.get_model(model_id) is not None


def _cost_ceiling_value(operator_id: str, risk_level: str) -> float:
    from sylion.aeis.advisor.preferences import get_preferences

    ceilings = get_preferences().get_effective(
        user_id=operator_id, project_type=None, project_domain=None, preference_key="cost_ceilings"
    ).value or {}
    return float(ceilings.get(risk_level, 6.0))


def _within_cost_ceiling(model_id: str, risk_level: str, operator_id: str) -> bool:
    """Check if model cost is within operator ceiling for risk level."""
    from sylion.aeis.advisor.pricing.estimator import effective_cost_estimate

    ceiling = _cost_ceiling_value(operator_id, risk_level)
    est, _ = effective_cost_estimate(operator_id, model_id, 2000, 1000)
    return float(est.total_cost_usd) <= ceiling


def _get_operator_override(
    operator_id: str,
    judge_purpose: str,
    risk_level: str,
) -> str | None:
    """Get operator override for judge purpose + risk level."""
    from sylion.aeis.advisor.preferences import get_preferences

    override_raw = get_preferences().get_effective(
        user_id=operator_id, project_type=None, project_domain=None, preference_key="llm_judge_routing_override"
    ).value or {}
    if isinstance(override_raw, dict):
        return override_raw.get(f"{judge_purpose}:{risk_level}") or override_raw.get(judge_purpose)
    return None


def _find_local_fallback(operator_id: str) -> str | None:
    """Find any available local model as fallback."""
    for model_id in ["qwen2.5:72b-instruct", "qwen2.5:7b-instruct"]:
        if _is_model_available(operator_id, model_id):
            return model_id
    return None


def _normalize_candidates(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item]
    return [value]


def _select_candidate(
    operator_id: str,
    candidates: list[str],
    risk_level: str,
    preferred_reason: str,
    budget_reason: str,
) -> ModelChoice | None:
    from sylion.aeis.advisor.pricing.estimator import effective_cost_estimate
    from sylion.aeis.advisor.subscription.quota_tracker import get_quota_status

    available = [model_id for model_id in candidates if _is_model_available(operator_id, model_id)]
    if not available:
        return None

    subscription_pool: list[tuple[str, int]] = []
    for model_id in available:
        quota = get_quota_status(operator_id, model_id)
        if quota and quota.has_quota:
            subscription_pool.append((model_id, quota.remaining_tokens))
    if subscription_pool:
        subscription_pool.sort(key=lambda item: item[1], reverse=True)
        chosen_model = subscription_pool[0][0]
        return ModelChoice(
            model_id=chosen_model,
            reason=f"{preferred_reason}_subscription",
            estimated_cost_usd=0.0,
            used_subscription=True,
            suggested_alternative=subscription_pool[1][0] if len(subscription_pool) > 1 else None,
        )

    ceiling = _cost_ceiling_value(operator_id, risk_level)
    affordable: list[tuple[str, float]] = []
    rejected: list[tuple[str, float]] = []
    for model_id in available:
        estimate, _ = effective_cost_estimate(operator_id, model_id, 2000, 1000)
        total_cost = float(estimate.total_cost_usd)
        if total_cost <= ceiling:
            affordable.append((model_id, total_cost))
        else:
            rejected.append((model_id, total_cost))

    if affordable:
        chosen_model, total_cost = affordable[0]
        is_generic_local = preferred_reason == "generic_fallback" and _provider_of(chosen_model) == "local"
        return ModelChoice(
            model_id=chosen_model,
            reason="local_fallback" if is_generic_local else preferred_reason,
            is_local_fallback=is_generic_local,
            estimated_cost_usd=total_cost,
            suggested_alternative=affordable[1][0] if len(affordable) > 1 else None,
        )

    if rejected:
        cheapest_model, cheapest_cost = min(rejected, key=lambda item: item[1])
        return ModelChoice(
            model_id="",
            reason=budget_reason,
            estimated_cost_usd=cheapest_cost,
            budget_exceeded=True,
            suggested_alternative=cheapest_model,
        )

    return None


def resolve_judge_model(
    operator_id: str,
    judge_purpose: str,
    risk_level: str,
) -> ModelChoice:
    """Resolve judge model for given purpose and risk level."""
    budget_block: ModelChoice | None = None
    override = _get_operator_override(operator_id, judge_purpose, risk_level)
    if override and _is_model_available(operator_id, override):
        choice = _select_candidate(
            operator_id,
            [override],
            risk_level,
            preferred_reason="operator_override",
            budget_reason="operator_override_budget_exceeded",
        )
        if choice is not None and choice.model_id:
            return choice
        if choice is not None and choice.budget_exceeded:
            budget_block = choice

    default = DEFAULT_ROUTING_BY_PURPOSE.get(judge_purpose, {}).get(risk_level)
    choice = _select_candidate(
        operator_id,
        _normalize_candidates(default),
        risk_level,
        preferred_reason="default_ensemble_pick" if isinstance(default, list) else "default_routing",
        budget_reason="default_routing_budget_exceeded",
    )
    if choice is not None and choice.model_id:
        return choice
    if choice is not None and choice.budget_exceeded:
        budget_block = choice

    from sylion.aeis.advisor.pricing import catalog

    generic_choice = _select_candidate(
        operator_id,
        [model.model_id for model in catalog.list_models()],
        risk_level,
        preferred_reason="generic_fallback",
        budget_reason="generic_fallback_budget_exceeded",
    )
    if generic_choice is not None and generic_choice.model_id:
        return generic_choice
    if generic_choice is not None and generic_choice.budget_exceeded:
        budget_block = generic_choice

    local = _find_local_fallback(operator_id)
    if local:
        return ModelChoice(model_id=local, reason="local_fallback", is_local_fallback=True)

    raise RuntimeError(f"No available model for {judge_purpose}/{risk_level}")


def resolve_role_model(
    operator_id: str,
    role: str,
    risk_level: str,
) -> ModelChoice:
    """Resolve model for an abstract role."""
    budget_block: ModelChoice | None = None
    default = DEFAULT_ROUTING_BY_ROLE.get(role, {}).get(risk_level)
    choice = _select_candidate(
        operator_id,
        _normalize_candidates(default),
        risk_level,
        preferred_reason="default_role_ensemble" if isinstance(default, list) else "default_role_routing",
        budget_reason="default_role_budget_exceeded",
    )
    if choice is not None and choice.model_id:
        return choice
    if choice is not None and choice.budget_exceeded:
        budget_block = choice

    from sylion.aeis.advisor.pricing import catalog

    generic_choice = _select_candidate(
        operator_id,
        [model.model_id for model in catalog.list_models()],
        risk_level,
        preferred_reason="generic_fallback",
        budget_reason="generic_fallback_budget_exceeded",
    )
    if generic_choice is not None and generic_choice.model_id:
        return generic_choice
    if generic_choice is not None and generic_choice.budget_exceeded:
        budget_block = generic_choice

    local = _find_local_fallback(operator_id)
    if local:
        return ModelChoice(model_id=local, reason="local_fallback", is_local_fallback=True)

    raise RuntimeError(f"No available model for role {role}/{risk_level}")
