"""SYLION Cognitive -- Council voting quality layer (Wave A-LLM).

Three orthogonal fixes packaged into one focused module:

  * FIX-016 -- per-role prompt templates so each Council seat
    (planner / critic / security / legal / finance / council_chair) reasons
    from its own perspective rather than a generic chat prompt.

  * FIX-017 -- deterministic seeded votes. Given the same idea + role +
    seed, ``seeded_vote(...)`` always returns the same vote and rationale.
    This is what makes Council decisions auditable / replayable for
    governance review (see RB-017).

  * FIX-023 -- model selection strategy keyed off `decision_class`. D0/D1
    decisions go to the cheap-fast tier ("haiku-tier"), D2/D3 to the
    balanced tier ("sonnet-tier"), and D4/D5 to the deep-slow tier
    ("opus-tier"). The selection is a stable lookup with optional
    operator override for a specific class.

Public Hook v1.0 (2026-04-25). Owner: A-GOV. Read-only for B / K / D.

Side effects: NONE. This module is pure (no SQLite, no network, no
EventBus). The deterministic-vote behavior is realized via stdlib hashing
and ``random.Random(seed)``, so tests are stable across machines.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field
from typing import Iterable

# ---------------------------------------------------------------------------
# FIX-016 -- Role prompt templates
# ---------------------------------------------------------------------------

# Canonical Council seat names. Other roles (e.g. team-specific reviewers)
# can be added via ``register_role_template``.
COUNCIL_ROLES: tuple[str, ...] = (
    "planner",
    "critic",
    "security",
    "legal",
    "finance",
    "council_chair",
)


_DEFAULT_ROLE_PROMPT_TEMPLATES: dict[str, str] = {
    "planner": (
        "You are the Council Planner. Evaluate whether this idea is "
        "executable from a roadmap and capacity standpoint.\n\n"
        "Idea: {idea}\n\n"
        "Decision class: {decision_class}\n"
        "Vote APPROVE if the plan is feasible within current quarter capacity.\n"
        "Vote REJECT if it conflicts with active priorities.\n"
        "Vote ABSTAIN if the proposal lacks the milestones needed to plan.\n"
        "Return JSON: {{\"vote\": ..., \"rationale\": ...}}."
    ),
    "critic": (
        "You are the Council Critic. Stress-test the assumptions in the "
        "proposal. Look for logical gaps, missing evidence, or unstated "
        "dependencies.\n\n"
        "Idea: {idea}\n\n"
        "Decision class: {decision_class}\n"
        "Vote APPROVE only if the reasoning holds without unstated leaps.\n"
        "Vote REJECT if a load-bearing assumption is unsupported.\n"
        "Vote ABSTAIN if the evidence pack is incomplete but not contradictory.\n"
        "Return JSON: {{\"vote\": ..., \"rationale\": ...}}."
    ),
    "security": (
        "You are the Council Security Reviewer. Examine threat surface, "
        "secret handling, supply-chain risk, and least-privilege "
        "compliance.\n\n"
        "Idea: {idea}\n\n"
        "Decision class: {decision_class}\n"
        "Vote APPROVE only if there is no new attack surface or it is "
        "explicitly mitigated.\n"
        "Vote REJECT on any non-mitigated security regression.\n"
        "Vote ABSTAIN if the proposal does not touch security-relevant "
        "surfaces.\n"
        "Return JSON: {{\"vote\": ..., \"rationale\": ...}}."
    ),
    "legal": (
        "You are the Council Legal Reviewer. Evaluate the proposal against "
        "applicable regulations (GDPR, AI Act, license compatibility, "
        "contract obligations).\n\n"
        "Idea: {idea}\n\n"
        "Decision class: {decision_class}\n"
        "Vote APPROVE if compliant or already covered by an existing waiver.\n"
        "Vote REJECT on any unmitigated regulatory exposure.\n"
        "Vote ABSTAIN if the proposal is jurisdiction-ambiguous and needs "
        "explicit scoping before review.\n"
        "Return JSON: {{\"vote\": ..., \"rationale\": ...}}."
    ),
    "finance": (
        "You are the Council Finance Reviewer. Assess budget impact, "
        "expected ROI, and runway sensitivity.\n\n"
        "Idea: {idea}\n\n"
        "Decision class: {decision_class}\n"
        "Vote APPROVE if the cost is within the active quarter budget AND "
        "the expected return is positive.\n"
        "Vote REJECT if it puts runway under threshold.\n"
        "Vote ABSTAIN if the financial impact is non-material (<1% of budget).\n"
        "Return JSON: {{\"vote\": ..., \"rationale\": ...}}."
    ),
    "council_chair": (
        "You are the Council Chair. Read the other reviewers' rationales and "
        "render a tie-breaking judgment.\n\n"
        "Idea: {idea}\n\n"
        "Decision class: {decision_class}\n"
        "Vote APPROVE if the majority of distinct concerns have been mitigated.\n"
        "Vote REJECT if any blocking concern remains unaddressed.\n"
        "Vote ABSTAIN only if quorum could not be reached.\n"
        "Return JSON: {{\"vote\": ..., \"rationale\": ...}}."
    ),
}

# Mutable runtime registry (initialized from the canonical defaults).
ROLE_PROMPT_TEMPLATES: dict[str, str] = dict(_DEFAULT_ROLE_PROMPT_TEMPLATES)


def reset_role_templates() -> None:
    """Restore the role template registry to canonical defaults.

    Hook v1.0 (2026-04-25).
    """
    ROLE_PROMPT_TEMPLATES.clear()
    ROLE_PROMPT_TEMPLATES.update(_DEFAULT_ROLE_PROMPT_TEMPLATES)


def register_role_template(role: str, template: str) -> None:
    """Register or replace a role's prompt template.

    Hook v1.0 (2026-04-25).

    The template MUST contain ``{idea}`` and ``{decision_class}``
    placeholders so :func:`format_role_prompt` can render it.
    """
    if "{idea}" not in template:
        raise ValueError(
            f"role '{role}' template must contain '{{idea}}' placeholder"
        )
    if "{decision_class}" not in template:
        raise ValueError(
            f"role '{role}' template must contain '{{decision_class}}' "
            "placeholder"
        )
    ROLE_PROMPT_TEMPLATES[role] = template


def get_role_template(role: str) -> str:
    """Return the prompt template for ``role``.

    Hook v1.0 (2026-04-25). Raises ``KeyError`` on unknown role.
    """
    return ROLE_PROMPT_TEMPLATES[role]


def format_role_prompt(
    role: str,
    idea: str,
    decision_class: str = "D2",
) -> str:
    """Render the role-specific prompt for ``idea`` at ``decision_class``.

    Hook v1.0 (2026-04-25).
    """
    template = get_role_template(role)
    return template.format(idea=idea, decision_class=decision_class)


# ---------------------------------------------------------------------------
# FIX-017 -- Deterministic seeded votes
# ---------------------------------------------------------------------------


@dataclass
class SeededVote:
    """A reproducible vote produced by :func:`seeded_vote`.

    Equal ``(idea, role, seed)`` triples always produce equal votes (same
    ``vote`` AND same ``rationale_hash``).
    """

    idea: str
    role: str
    seed: int
    decision_class: str
    vote: str           # "approve" | "reject" | "abstain"
    rationale: str
    rationale_hash: str
    model_id: str
    extras: dict[str, str] = field(default_factory=dict)


# Per-role bias weights (approve, reject, abstain). These are stable across
# replays; tweaking them is a Hook bump.
_ROLE_BIAS: dict[str, tuple[float, float, float]] = {
    "planner":       (0.55, 0.30, 0.15),
    "critic":        (0.30, 0.50, 0.20),
    "security":      (0.30, 0.55, 0.15),
    "legal":         (0.35, 0.40, 0.25),
    "finance":       (0.45, 0.40, 0.15),
    "council_chair": (0.50, 0.35, 0.15),
}

_DEFAULT_BIAS: tuple[float, float, float] = (0.45, 0.40, 0.15)

# Decision-class skew: higher classes nudge the deliberation toward
# REJECT to reflect the higher bar of approval at D4+.
_CLASS_SKEW: dict[str, tuple[float, float, float]] = {
    "D0": (+0.10, -0.05, -0.05),
    "D1": (+0.05, -0.02, -0.03),
    "D2": (+0.00, +0.00, +0.00),
    "D3": (-0.05, +0.05, +0.00),
    "D4": (-0.10, +0.10, +0.00),
    "D5": (-0.15, +0.15, +0.00),
}

_KEYWORD_SECURITY = re.compile(
    r"\b(secret|password|token|exploit|vuln|cve|injection|rce|priv ?esc)\b",
    re.IGNORECASE,
)
_KEYWORD_LEGAL = re.compile(
    r"\b(gdpr|ccpa|copyright|license|patent|export\s*control|nda|contract)\b",
    re.IGNORECASE,
)


def _stable_seed(idea: str, role: str, seed: int) -> int:
    """Mix (idea, role, seed) into a stable 64-bit integer."""
    h = hashlib.blake2b(
        f"{role}|{seed}|{idea}".encode("utf-8"),
        digest_size=8,
    )
    return int.from_bytes(h.digest(), "big")


def _resolve_bias(role: str, decision_class: str, idea: str) -> tuple[float, float, float]:
    base = list(_ROLE_BIAS.get(role, _DEFAULT_BIAS))
    skew = _CLASS_SKEW.get(decision_class, (0.0, 0.0, 0.0))
    weights = [
        max(0.0, base[0] + skew[0]),
        max(0.0, base[1] + skew[1]),
        max(0.0, base[2] + skew[2]),
    ]
    # Role-specific keyword sensitivities -- nudge REJECT if the
    # corresponding regulator's keywords appear in the idea text.
    if role == "security" and _KEYWORD_SECURITY.search(idea):
        weights[1] += 0.25
    if role == "legal" and _KEYWORD_LEGAL.search(idea):
        weights[1] += 0.20
    total = sum(weights) or 1.0
    return tuple(w / total for w in weights)  # type: ignore[return-value]


def seeded_vote(
    idea: str,
    role: str,
    seed: int,
    decision_class: str = "D2",
    model_id: str | None = None,
) -> SeededVote:
    """Produce a deterministic, replay-safe vote for ``(idea, role, seed)``.

    Hook v1.0 (2026-04-25).

    Args:
      idea: free-text proposal under review.
      role: one of :data:`COUNCIL_ROLES` (or any role registered via
            :func:`register_role_template`).
      seed: integer seed -- the same seed always produces the same vote.
      decision_class: D0..D5 (only the prefix is used by the bias model).
      model_id: optional model id; if ``None``, derived via
                :func:`select_model_for_class`.

    Returns:
      :class:`SeededVote` -- equal seed/idea/role tuples produce equal
      results.

    Raises:
      KeyError if the role has no registered template.
    """
    # Make sure the role exists (or fall through to default bias if it's
    # registered but has no canonical template entry).
    if role not in ROLE_PROMPT_TEMPLATES and role not in _ROLE_BIAS:
        raise KeyError(f"unknown council role '{role}'")

    rng = random.Random(_stable_seed(idea, role, seed))
    weights = _resolve_bias(role, decision_class, idea)
    pick = rng.choices(["approve", "reject", "abstain"], weights=list(weights), k=1)[0]

    rationale = (
        f"role={role} decision_class={decision_class} weights="
        f"{weights[0]:.2f}/{weights[1]:.2f}/{weights[2]:.2f} -> {pick}"
    )
    rationale_hash = hashlib.sha256(rationale.encode("utf-8")).hexdigest()[:16]

    return SeededVote(
        idea=idea,
        role=role,
        seed=seed,
        decision_class=decision_class,
        vote=pick,
        rationale=rationale,
        rationale_hash=rationale_hash,
        model_id=model_id or select_model_for_class(decision_class),
        extras={"weights": ",".join(f"{w:.4f}" for w in weights)},
    )


def replay_votes(
    items: Iterable[tuple[str, str, int, str]],
) -> list[SeededVote]:
    """Convenience: replay a list of ``(idea, role, seed, decision_class)``.

    Hook v1.0 (2026-04-25).
    """
    return [seeded_vote(idea, role, seed, dc) for idea, role, seed, dc in items]


# ---------------------------------------------------------------------------
# FIX-023 -- decision_class -> model tier selection
# ---------------------------------------------------------------------------


# Tier hierarchy in monotonic-cost order.
MODEL_TIER_HIERARCHY: tuple[str, ...] = (
    "haiku-tier",
    "sonnet-tier",
    "opus-tier",
)


_DEFAULT_DECISION_CLASS_TIERS: dict[str, str] = {
    "D0": "haiku-tier",
    "D1": "haiku-tier",
    "D2": "sonnet-tier",
    "D3": "sonnet-tier",
    "D4": "opus-tier",
    "D5": "opus-tier",
}

# Mutable registry so tests / operators can override the default mapping.
DECISION_CLASS_TIERS: dict[str, str] = dict(_DEFAULT_DECISION_CLASS_TIERS)


def select_model_for_class(decision_class: str) -> str:
    """Return the model tier for ``decision_class``.

    Hook v1.0 (2026-04-25).

    D0/D1 -> haiku-tier (cheap-fast)
    D2/D3 -> sonnet-tier (balanced)
    D4/D5 -> opus-tier (deep-slow)

    Raises ``KeyError`` for unknown classes (caller's responsibility to
    validate against ``sylion.governance.ticket.VALID_DECISION_CLASSES``).
    """
    return DECISION_CLASS_TIERS[decision_class]


def override_class_tier(decision_class: str, tier: str) -> None:
    """Operator override for a single decision_class.

    Hook v1.0 (2026-04-25). ``tier`` MUST appear in
    :data:`MODEL_TIER_HIERARCHY`; otherwise ValueError.
    """
    if tier not in MODEL_TIER_HIERARCHY:
        raise ValueError(
            f"unknown tier '{tier}'; valid: {list(MODEL_TIER_HIERARCHY)}"
        )
    DECISION_CLASS_TIERS[decision_class] = tier


def reset_class_tiers() -> None:
    """Restore the decision_class -> tier map to defaults.

    Hook v1.0 (2026-04-25).
    """
    DECISION_CLASS_TIERS.clear()
    DECISION_CLASS_TIERS.update(_DEFAULT_DECISION_CLASS_TIERS)
