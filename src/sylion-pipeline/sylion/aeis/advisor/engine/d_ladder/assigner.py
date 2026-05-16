"""D-level assigner with default mapping + 5 upgrade rules.

Default mapping per docs/.../05_decision_ladder.md §2.
Upgrade rules U1-U5 applied in order; cap at D5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sylion.aeis.advisor.engine._models import CardContext


_LEVEL_INDEX = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4, "D5": 5}
_LEVEL_BY_INDEX = {v: k for k, v in _LEVEL_INDEX.items()}


# Default per-recommendation-type mapping
_DEFAULT_MAPPING: dict[str, str] = {
    "REC_TYPE_MODEL_SETUP": "D1",
    "REC_TYPE_API_PROVIDER_SETUP": "D1",
    "REC_TYPE_BUDGET_CONFIG": "D2",
    "REC_TYPE_IDEA_INTAKE_GUIDANCE": "D0",
    "REC_TYPE_SOT_MODEL_SELECTION": "D1",
    "REC_TYPE_COUNCIL_FORMATION": "D2",
    "REC_TYPE_AUTONOMY_POLICY": "D3",
    "REC_TYPE_SOT_DRAFTING": "D0",
    "REC_TYPE_MASTERPLAN_GUIDANCE": "D1",
    "REC_TYPE_RUNTIME_TOPOLOGY": "D2",
    "REC_TYPE_VPS_SCALING": "D3",
    "REC_TYPE_SKILL_SELECTION": "D1",
    "REC_TYPE_PRODUCTION_EXECUTION": "D3",
    "REC_TYPE_TESTING_GUIDANCE": "D0",
    "REC_TYPE_HUMAN_GATE_BATCH": "D1",
    "REC_TYPE_FINAL_APPROVAL": "D3",
    "REC_TYPE_REDUCE_PREMIUM_USAGE": "D2",
    "REC_TYPE_MOVE_TO_CHEAPER_MODEL": "D2",
    "REC_TYPE_ADD_CRITIC_MODEL": "D1",
    "REC_TYPE_SPLIT_LARGE_MODULE": "D2",
    "REC_TYPE_BATCH_HUMAN_GATE_TICKETS": "D1",
    "REC_TYPE_BLOCK_PRODUCTION_DEPLOY": "D5",
    "REC_TYPE_PURCHASE_PLAN": "D3",
    "REC_TYPE_DOWNGRADE_PLAN": "D2",
    "REC_TYPE_CANCEL_PLAN": "D3",
}

_FUNDING_DEFAULT_MAPPING: dict[str, str] = {
    "FUNDING_GRANT_FIT": "D0",
    "FUNDING_HOW_TO_QUALIFY": "D1",
    "FUNDING_FORM_COMPANY": "D3",
    "FUNDING_CHANGE_LEGAL_FORM": "D3",
    "FUNDING_REGIONAL_RELOCATION": "D3",
    "FUNDING_FIND_CONSORTIUM": "D2",
    "FUNDING_ADJUST_IDEA_FOR_GRANT": "D2",
    "FUNDING_DEADLINE_WARNING": "D1",
    "FUNDING_GAP_CLOSURE_PLAN": "D2",
    "FUNDING_SCOPE_ADJUSTMENT": "D2",
}

_HARD_CHANGE_PREFERENCE_KEYS = {
    "autonomy_level",
    "runtime_strategy",
    "approval_timeout_behavior",
    "trusted_providers",
    "blocked_providers",
    "funding_advisor_enabled",
    "funding_countries",
    "meta_recommendations_enabled",
}

_COST_OR_SUBSCRIPTION_TYPES = {
    "REC_TYPE_REDUCE_PREMIUM_USAGE",
    "REC_TYPE_MOVE_TO_CHEAPER_MODEL",
    "REC_TYPE_BLOCK_PRODUCTION_DEPLOY",
    "REC_TYPE_PURCHASE_PLAN",
    "REC_TYPE_DOWNGRADE_PLAN",
    "REC_TYPE_CANCEL_PLAN",
}


@dataclass
class DLevelAssignment:
    final_level: str
    default_from_type: str
    rules_applied: list[dict[str, Any]] = field(default_factory=list)
    capped_at_d5: bool = False

    def trace(self) -> dict[str, Any]:
        return {
            "default_from_type": self.default_from_type,
            "rules_applied": self.rules_applied,
            "final": self.final_level,
            "capped_at_d5": self.capped_at_d5,
        }


def assign_d_level(
    *,
    recommendation_type: str,
    suggestion_type: str | None = None,
    context: CardContext | None = None,
) -> DLevelAssignment:
    default = _DEFAULT_MAPPING.get(recommendation_type, "D1")
    if suggestion_type:
        default = _max_level(default, _FUNDING_DEFAULT_MAPPING.get(suggestion_type, "D0"))

    current_idx = _LEVEL_INDEX[default]
    rules_applied: list[dict] = []

    if context is not None:
        # U1 cost magnitude
        cost = context.cost_estimate_usd
        if cost > 10_000:
            current_idx, rules_applied = _bump(current_idx, rules_applied, "U1_cost_magnitude", f"${cost:.2f}", 3)
        elif cost > 1_000:
            current_idx, rules_applied = _bump(current_idx, rules_applied, "U1_cost_magnitude", f"${cost:.2f}", 2)
        elif cost > 100:
            current_idx, rules_applied = _bump(current_idx, rules_applied, "U1_cost_magnitude", f"${cost:.2f}", 1)

        # U2 blast radius
        if context.affects_multiple_projects:
            current_idx, rules_applied = _bump(current_idx, rules_applied, "U2_blast_radius", "multi_project", 1)
        if context.affects_production:
            current_idx, rules_applied = _bump(current_idx, rules_applied, "U2_blast_radius", "production", 1)

        # U3 reversibility
        if context.rollback_takes_days >= 1.0:
            current_idx, rules_applied = _bump(current_idx, rules_applied, "U3_reversibility", "rollback>=1d", 1)
        if context.rollback_data_loss:
            # min D4 enforcement
            if current_idx < _LEVEL_INDEX["D4"]:
                rules_applied.append(
                    {"rule": "U3_reversibility", "input": "data_loss_risk", "delta": f"min_D4 (was {_LEVEL_BY_INDEX[current_idx]})"}
                )
                current_idx = _LEVEL_INDEX["D4"]

        # U4 hard preferences
        prefs = context.preferences or {}
        changed_keys = set(prefs.get("__changing_keys__") or [])
        if changed_keys & _HARD_CHANGE_PREFERENCE_KEYS:
            if current_idx < _LEVEL_INDEX["D3"]:
                rules_applied.append(
                    {"rule": "U4_hard_preferences", "input": list(changed_keys), "delta": "min_D3"}
                )
                current_idx = _LEVEL_INDEX["D3"]

        # U5 autonomy
        autonomy = context.autonomy_level or prefs.get("autonomy_level") or "suggest"
        if autonomy == "manual" and current_idx > _LEVEL_INDEX["D0"]:
            if current_idx < _LEVEL_INDEX["D3"]:
                rules_applied.append(
                    {"rule": "U5_autonomy", "input": "manual", "delta": "min_D3 for non-D0 cards"}
                )
                current_idx = _LEVEL_INDEX["D3"]

    capped = False
    if current_idx > _LEVEL_INDEX["D5"]:
        current_idx = _LEVEL_INDEX["D5"]
        capped = True

    return DLevelAssignment(
        final_level=_LEVEL_BY_INDEX[current_idx],
        default_from_type=default,
        rules_applied=rules_applied,
        capped_at_d5=capped,
    )


def _max_level(a: str, b: str) -> str:
    return a if _LEVEL_INDEX[a] >= _LEVEL_INDEX[b] else b


def _bump(idx: int, rules_applied: list[dict], rule: str, input_label: str, delta: int):
    new_idx = min(_LEVEL_INDEX["D5"], idx + delta)
    rules_applied.append({"rule": rule, "input": input_label, "delta": f"+{delta}"})
    return new_idx, rules_applied
