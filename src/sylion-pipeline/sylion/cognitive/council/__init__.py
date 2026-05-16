"""SYLION Cognitive -- Council quality layer (Wave A-LLM).

Quality-of-reasoning helpers wrapped around the Council 4/4 voting plane:
  * FIX-016 -- role-specific prompt templates (planner, critic, security,
    legal, finance, council_chair).
  * FIX-017 -- deterministic seeded votes (replay-safe).
  * FIX-023 -- decision_class-aware model tier selection (cheap-fast vs
    deep-slow).

Public Hook v1.0 (2026-04-25). Owner: A-GOV. Read-only for B / K / D.
"""

from sylion.cognitive.council.voting import (
    COUNCIL_ROLES,
    DECISION_CLASS_TIERS,
    MODEL_TIER_HIERARCHY,
    ROLE_PROMPT_TEMPLATES,
    SeededVote,
    format_role_prompt,
    get_role_template,
    register_role_template,
    reset_role_templates,
    seeded_vote,
    select_model_for_class,
)

__all__ = [
    "COUNCIL_ROLES",
    "DECISION_CLASS_TIERS",
    "MODEL_TIER_HIERARCHY",
    "ROLE_PROMPT_TEMPLATES",
    "SeededVote",
    "format_role_prompt",
    "get_role_template",
    "register_role_template",
    "reset_role_templates",
    "seeded_vote",
    "select_model_for_class",
]
