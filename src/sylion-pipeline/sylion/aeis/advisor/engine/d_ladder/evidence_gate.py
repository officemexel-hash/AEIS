"""Evidence Pack requirement gate."""

from __future__ import annotations

from enum import Enum


_FUNDING_D3_TYPES = {
    "FUNDING_FORM_COMPANY",
    "FUNDING_CHANGE_LEGAL_FORM",
    "FUNDING_REGIONAL_RELOCATION",
}

_COST_OR_SUBSCRIPTION_TYPES = {
    "REC_TYPE_REDUCE_PREMIUM_USAGE",
    "REC_TYPE_MOVE_TO_CHEAPER_MODEL",
    "REC_TYPE_BLOCK_PRODUCTION_DEPLOY",
    "REC_TYPE_PURCHASE_PLAN",
    "REC_TYPE_DOWNGRADE_PLAN",
    "REC_TYPE_CANCEL_PLAN",
}


class EvidencePackRequirement(str, Enum):
    NONE = "none"
    LIGHT = "light"
    FULL = "full"


def determine_evidence_pack_requirement(
    *,
    d_level: str,
    recommendation_type: str = "",
    suggestion_type: str | None = None,
) -> EvidencePackRequirement:
    if d_level == "D5":
        return EvidencePackRequirement.FULL
    if d_level == "D4":
        return EvidencePackRequirement.FULL

    if d_level == "D3":
        if recommendation_type in _COST_OR_SUBSCRIPTION_TYPES:
            return EvidencePackRequirement.LIGHT
        if suggestion_type in _FUNDING_D3_TYPES:
            return EvidencePackRequirement.LIGHT
        if recommendation_type in {"REC_TYPE_AUTONOMY_POLICY", "REC_TYPE_VPS_SCALING", "REC_TYPE_FINAL_APPROVAL"}:
            return EvidencePackRequirement.LIGHT
    return EvidencePackRequirement.NONE
