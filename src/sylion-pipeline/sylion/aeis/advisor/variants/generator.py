"""Variant generator — computes cost, time, risk, quality per variant."""

from __future__ import annotations

import logging
from typing import Any

from sylion.aeis.advisor.variants._models import Variant, VariantSet
from sylion.aeis.advisor.variants.templates import (
    ALL_TEMPLATES,
    COST_SAVING_TEMPLATE,
    BALANCED_TEMPLATE,
    AGGRESSIVE_TEMPLATE,
)
from sylion.aeis.advisor.pricing.estimator import estimate_cost

log = logging.getLogger("sylion.aeis.advisor.variants.generator")


def _estimate_variant_cost(params: dict[str, Any]) -> float:
    """Estimate cost for a variant based on its parameters."""
    cost = 0.0
    council_size = params.get("council_size", 5)
    vps_envs = params.get("vps_envs", 0)
    use_external = params.get("use_external_apis", False)
    critic = params.get("critic_model")

    # Base cost: council members × estimated calls
    calls_per_council_member = 4
    if use_external:
        # External calls cost more — assume claude-sonnet-4-6 for moderate
        for _ in range(council_size * calls_per_council_member):
            est = estimate_cost("claude-sonnet-4-6", 1500, 750)
            cost += float(est.total_cost_usd)
    else:
        # Local calls are free
        for _ in range(council_size * calls_per_council_member):
            est = estimate_cost("qwen2.5:72b-instruct", 1500, 750)
            cost += float(est.total_cost_usd)

    # Critic cost
    if critic:
        est = estimate_cost(critic, 2000, 1000)
        cost += float(est.total_cost_usd) * 2  # critic runs twice per cycle

    # VPS cost: $20/month per env (amortized to per-project estimate)
    cost += vps_envs * 20.0

    return round(cost, 2)


def _estimate_variant_time(params: dict[str, Any]) -> float:
    """Estimate time in hours for a variant."""
    council_size = params.get("council_size", 5)
    vps_envs = params.get("vps_envs", 0)
    use_local = params.get("use_local_models", True)
    use_external = params.get("use_external_apis", False)

    # Base time per council round (hours)
    base_time = 0.5
    if not use_external and use_local:
        base_time = 1.2  # local is slower
    if use_external:
        base_time = 0.5  # external APIs faster

    # Parallelization from VPS
    parallel_factor = max(1, vps_envs + 1)
    total_cycles = 3  # assume 3 council rounds
    return round((base_time * council_size * total_cycles) / parallel_factor, 1)


def _assess_risk(params: dict[str, Any]) -> str:
    """Assess risk level for a variant."""
    council_size = params.get("council_size", 5)
    use_external = params.get("use_external_apis", False)
    vps_envs = params.get("vps_envs", 0)
    critic = params.get("critic_model")

    if not use_external and council_size <= 3:
        return "low"
    if use_external and council_size >= 7 and vps_envs >= 2 and critic:
        return "high"
    if use_external and vps_envs >= 3:
        return "high"
    return "medium"


def _project_quality(params: dict[str, Any]) -> float:
    """Project quality score 0.0–1.0."""
    score = 0.5
    council_size = params.get("council_size", 5)
    critic = params.get("critic_model")
    use_external = params.get("use_external_apis", False)

    # More council = more oversight
    score += min(council_size * 0.03, 0.25)
    # External APIs = better models
    if use_external:
        score += 0.1
    # Critic = review layer
    if critic:
        score += 0.1
    # VPS scaling = faster iteration
    vps_envs = params.get("vps_envs", 0)
    score += min(vps_envs * 0.02, 0.05)

    return round(min(score, 1.0), 2)


def generate_variants(context: dict[str, Any] | None = None) -> VariantSet:
    """Generate 3 strategic variants for a project context."""
    ctx_id = (context or {}).get("context_id", "default")
    variants: list[Variant] = []

    for tmpl in ALL_TEMPLATES:
        params = dict(tmpl["parameters"])
        # Allow context overrides
        if context:
            for k, v in context.items():
                if k in params:
                    params[k] = v

        variant = Variant(
            name=tmpl["name"],
            description=tmpl["description"],
            parameters=params,
            estimated_cost_usd=_estimate_variant_cost(params),
            estimated_time_hours=_estimate_variant_time(params),
            risk_level=_assess_risk(params),
            quality_projection=_project_quality(params),
        )
        variants.append(variant)

    return VariantSet(context_id=ctx_id, variants=variants)


def compare_variants(variant_ids: list[str], variant_set: VariantSet) -> dict[str, Any]:
    """Build a simple comparison matrix between variants."""
    selected = [v for v in variant_set.variants if v.variant_id in variant_ids]
    if len(selected) < 2:
        return {"variant_ids": variant_ids, "dimensions": []}

    dims: list[dict[str, Any]] = []
    dimensions = ["estimated_cost_usd", "estimated_time_hours", "risk_level", "quality_projection"]

    for dim in dimensions:
        values = [(v.name, getattr(v, dim)) for v in selected]
        if dim in ("estimated_cost_usd", "estimated_time_hours"):
            winner = min(values, key=lambda x: x[1])[0]
        elif dim == "risk_level":
            order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            winner = min(values, key=lambda x: order.get(x[1], 1))[0]
        else:  # quality_projection
            winner = max(values, key=lambda x: x[1])[0]

        dims.append({
            "dimension": dim,
            "values": {name: val for name, val in values},
            "winner": winner,
        })

    return {"variant_ids": variant_ids, "dimensions": dims}
