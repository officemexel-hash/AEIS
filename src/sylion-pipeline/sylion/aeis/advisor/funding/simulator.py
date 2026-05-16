"""Three-mode simulator: static, dynamic, auto-generated.

Static  — predefined scenarios per common transitions.
Dynamic — operator-supplied changes; recompute the score with the patch applied.
Auto    — top-3 candidate changes ranked by predicted score delta (greedy).
"""

from __future__ import annotations

import copy
from typing import Any

from sylion.aeis.advisor.funding._models import (
    Company,
    GrantProgram,
    IdeaContext,
    Money,
    ScoringHistoryEntry,
    SimulationChange,
    SimulationScenario,
)
from sylion.aeis.advisor.funding.scoring.calculator import (
    score_with_profile,
)
from sylion.aeis.advisor.funding.scoring.profile_loader import (
    ensure_profile,
)


_STATIC_TEMPLATES: list[dict[str, Any]] = [
    {
        "label": "Co jeśli założysz sp. z o.o.?",
        "field": "legal_form",
        "to_value": "sp_z_o_o",
        "explanation": "Spółka z o.o. zwiększa szansę na grantach, które wymagają formy kapitałowej.",
        "cost_usd": "1500",
        "time_seconds": 14 * 86400,
    },
    {
        "label": "Co jeśli przeniesiesz siedzibę do PL-MZ?",
        "field": "region",
        "to_value": "PL-MZ",
        "explanation": "Województwo mazowieckie odblokowuje regionalne nabory FENG.",
        "cost_usd": "3500",
        "time_seconds": 30 * 86400,
    },
    {
        "label": "Co jeśli zwiększysz budżet R&D o 10%?",
        "field": "rd_budget_history",
        "to_value": "+10%",
        "explanation": "Wyższy budżet R&D wzmacnia komponent capacity.",
        "cost_usd": "0",
        "time_seconds": 7 * 86400,
    },
]


def static_scenarios(
    company: Company, idea: IdeaContext, grant: GrantProgram
) -> list[SimulationScenario]:
    profile = ensure_profile(grant.program_id)
    scenarios: list[SimulationScenario] = []
    for tmpl in _STATIC_TEMPLATES:
        patched = _apply_company_patch(company, {tmpl["field"]: tmpl["to_value"]})
        total, breakdown, _ = score_with_profile(patched, idea, grant, profile)
        scenarios.append(
            SimulationScenario(
                label=tmpl["label"],
                mode="static",
                changes=[
                    SimulationChange(
                        field_path=f"company.{tmpl['field']}",
                        from_value=str(getattr(company, tmpl["field"], "")),
                        to_value=str(tmpl["to_value"]),
                        explanation=tmpl["explanation"],
                    )
                ],
                resulting_eligibility_score=total,
                resulting_breakdown=breakdown,
                cost_to_implement=Money(amount=str(tmpl["cost_usd"]), currency="USD"),
                time_to_implement_seconds=int(tmpl["time_seconds"]),
            )
        )
    return scenarios


def dynamic_scenario(
    company: Company,
    idea: IdeaContext,
    grant: GrantProgram,
    operator_changes: dict[str, Any],
    label: str = "Operator what-if",
) -> SimulationScenario:
    """Apply operator-supplied changes and recompute."""
    profile = ensure_profile(grant.program_id)
    patched = _apply_company_patch(company, operator_changes)
    total, breakdown, _ = score_with_profile(patched, idea, grant, profile)
    changes = [
        SimulationChange(
            field_path=f"company.{k}",
            from_value=str(getattr(company, k, "")),
            to_value=str(v),
            explanation="Operator-driven change",
        )
        for k, v in operator_changes.items()
    ]
    return SimulationScenario(
        label=label,
        mode="dynamic",
        changes=changes,
        resulting_eligibility_score=total,
        resulting_breakdown=breakdown,
        cost_to_implement=Money(amount="0", currency="USD"),
        time_to_implement_seconds=0,
    )


def auto_scenarios(
    company: Company,
    idea: IdeaContext,
    grant: GrantProgram,
    *,
    baseline: ScoringHistoryEntry | None = None,
    top_n: int = 3,
) -> list[SimulationScenario]:
    """Greedy MVP heuristic: rank candidate single-field changes by predicted delta_score."""
    profile = ensure_profile(grant.program_id)
    base_total, base_breakdown, _ = score_with_profile(company, idea, grant, profile)
    if baseline is not None:
        base_total = baseline.total_score

    candidates: list[dict[str, Any]] = []
    for tmpl in _STATIC_TEMPLATES:
        patched = _apply_company_patch(company, {tmpl["field"]: tmpl["to_value"]})
        total, breakdown, _ = score_with_profile(patched, idea, grant, profile)
        candidates.append({
            "label": tmpl["label"],
            "field": tmpl["field"],
            "to_value": tmpl["to_value"],
            "explanation": tmpl["explanation"],
            "delta": total - base_total,
            "total": total,
            "breakdown": breakdown,
            "cost_usd": tmpl["cost_usd"],
            "time_seconds": tmpl["time_seconds"],
        })

    # Add a few synthetic component-driven candidates: the lowest-scoring
    # components are surfaced as "boost X" suggestions when the static templates
    # don't already cover them.
    weighted_gaps = [
        (c.component_id, (100.0 - c.score) * (c.weight_in_grant / 100.0), c)
        for c in base_breakdown
        if c.score < 60.0
    ]
    weighted_gaps.sort(key=lambda x: x[1], reverse=True)
    for cid, weighted_gap, comp in weighted_gaps:
        if any(c["field"].endswith(cid) for c in candidates):
            continue
        synthetic_total = min(100.0, base_total + weighted_gap)
        candidates.append({
            "label": f"Boost component {cid}",
            "field": f"component.{cid}",
            "to_value": "improved",
            "explanation": f"Targeted improvement of component {cid} (current={comp.score:.1f}).",
            "delta": synthetic_total - base_total,
            "total": synthetic_total,
            "breakdown": base_breakdown,
            "cost_usd": "0",
            "time_seconds": 14 * 86400,
        })

    candidates.sort(key=lambda x: x["delta"], reverse=True)
    selected = [c for c in candidates if c["delta"] > 0][:top_n]
    if not selected:
        selected = candidates[:top_n]
    return [
        SimulationScenario(
            label=str(c["label"]),
            mode="auto_generated",
            changes=[
                SimulationChange(
                    field_path=f"company.{c['field']}" if not c['field'].startswith('component.') else c['field'],
                    from_value=str(getattr(company, c["field"], "")) if not c['field'].startswith('component.') else "current",
                    to_value=str(c["to_value"]),
                    explanation=str(c["explanation"]),
                )
            ],
            resulting_eligibility_score=float(c["total"]),
            resulting_breakdown=list(c["breakdown"]),
            cost_to_implement=Money(amount=str(c["cost_usd"]), currency="USD"),
            time_to_implement_seconds=int(c["time_seconds"]),
        )
        for c in selected
    ]


def _apply_company_patch(company: Company, patch: dict[str, Any]) -> Company:
    patched = copy.deepcopy(company)
    for k, v in patch.items():
        if k == "rd_budget_history":
            if isinstance(v, str) and v.startswith("+") and v.endswith("%"):
                pct = float(v.strip("+%")) / 100.0
                bumped = []
                for rec in patched.rd_budget_history or []:
                    rec2 = dict(rec)
                    rec2["budget_usd"] = float(rec2.get("budget_usd", 0.0)) * (1.0 + pct)
                    bumped.append(rec2)
                if not bumped:
                    bumped = [{"year": 2026, "budget_usd": 50000.0 * (1.0 + pct)}]
                patched.rd_budget_history = bumped
            elif isinstance(v, list):
                patched.rd_budget_history = v
        elif k == "pkd_codes" and isinstance(v, list):
            patched.pkd_codes = list(v)
        elif hasattr(patched, k):
            setattr(patched, k, v)
    return patched
