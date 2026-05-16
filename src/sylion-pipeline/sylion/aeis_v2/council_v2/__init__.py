"""SYLION AEIS v2 — Council Hybrid wedge for W16 G1 cascade.

Step 3 of the 3-step W16 G1 cascade (per ``apps_v2/__init__.py`` notes):

    Phase 0 (tag-overlap)  →  G1 step 2 (embeddings refinement)
                                      ↓
                            G1 step 3 (this package — Council Hybrid wedge)

The wedge takes ranked candidates from ``match_idea_to_templates_g1`` and
runs them through the canonical 9-role :class:`CouncilHybrid` deliberation
returning a weighted vote, dissents, and sentinel evaluations. It is the
first production caller of CouncilHybrid from the v2 layer.

Per ADR-001 #2 the wedge is layered (composes existing council_hybrid.py
without modifying it) and per ADR-002 the simulation of role analyses uses
deterministic stubs so the wedge stays test-friendly without LLM calls.
"""

from sylion.aeis_v2.council_v2.adapters import (
    DEFAULT_MODEL,
    DEFAULT_ROLE_TIMEOUT_S,
    OllamaRoleAdapter,
    ScriptedRoleAdapter,
    make_ollama_evaluator,
    parse_role_verdict_response,
    render_role_prompt,
)
from sylion.aeis_v2.council_v2.wedge import (
    CouncilWedgeDecision,
    evaluate_match_with_council,
    simulate_role_verdict,
)

__all__ = [
    "CouncilWedgeDecision",
    "DEFAULT_MODEL",
    "DEFAULT_ROLE_TIMEOUT_S",
    "OllamaRoleAdapter",
    "ScriptedRoleAdapter",
    "evaluate_match_with_council",
    "make_ollama_evaluator",
    "parse_role_verdict_response",
    "render_role_prompt",
    "simulate_role_verdict",
]
