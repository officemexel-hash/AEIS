"""W16 G1 cascade step 3 — Council Hybrid wedge.

The wedge composes :class:`sylion.governance.council_hybrid.CouncilHybrid`
to produce a weighted vote over a ranked set of :class:`MatchResult`
candidates returned by ``match_idea_to_templates_g1``.

Pipeline (per call to :func:`evaluate_match_with_council`):

1. Open a council session
   ``topic = f"match-idea-g1: {idea_text[:50]}"``
2. Add each of the 9 canonical roles as a participant with default weight
   from :data:`council_hybrid.DEFAULT_ROLE_WEIGHTS`.
3. For each role, generate a deterministic verdict via
   :func:`simulate_role_verdict` (production callers can swap this for a
   real model adapter; the simulator keeps tests reproducible without
   touching the LLM stack).
4. Compute the weighted consensus.
5. Return :class:`CouncilWedgeDecision` carrying the chosen template,
   the verdict, dissenters (roles that voted against the majority) and
   the council session id (for audit traceback).

The wedge does NOT call ``consolidate_with_signatures`` — the critic
signature step is operator-driven (per W16 charter §4) and lands at G2.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.governance.council_hybrid import (
    DEFAULT_ROLE_WEIGHTS,
    RANK_MULTIPLIER,
    SENTINEL_ROLES,
    VALID_ROLES,
    CouncilHybrid,
    get_council_hybrid,
)

log = logging.getLogger(__name__)


def _default_audit_path() -> Path:
    try:
        from sylion.aeis_v2.audit_profile import resolve_audit_chain_path

        return resolve_audit_chain_path(
            "council_wedge.jsonl",
            Path(__file__).resolve().parents[3] / "logs" / "v2",
        )
    except Exception:  # noqa: BLE001
        return (
            Path(__file__).resolve().parents[3]
            / "logs" / "v2" / "council_wedge.jsonl"
        )

#: Default rank assignment per canonical role.  Sentinels run as
#: ``review_only`` (lighter weight + signal-only); the rest are ``primary``.
DEFAULT_RANK_BY_ROLE: dict[str, str] = {
    "planner":            "primary",
    "architect":          "primary",
    "critic":             "primary",
    "verifier":           "senior",
    "governance":         "primary",
    "cost_sentinel":      "review_only",
    "security_sentinel":  "review_only",
    "domain_specialist":  "senior",
    "funding_specialist": "senior",
}

#: Audit JSONL path — best-effort emission.  Mirrors the ``logs/v2``
#: convention used elsewhere in the v2 layer.
AUDIT_LOG_PATH = (
    _default_audit_path()
)


@dataclass(frozen=True, slots=True)
class CouncilWedgeDecision:
    """Outcome of a Council Hybrid wedge evaluation.

    Attributes:
        chosen_template_id: id of the picked AppTemplate (from G1 top-1).
        verdict: ``"approve" | "reject" | "conditional" | "tie" | "no_data"``.
        weights: dict mapping verdict label to summed weight.
        dissents: list of role names that voted against the majority verdict.
        sentinel_blocks: list of sentinel roles that vetoed (verdict=reject).
        session_id: council session id for audit traceback.
    """

    chosen_template_id: str
    verdict: str
    weights: dict[str, float]
    dissents: list[str]
    sentinel_blocks: list[str]
    session_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chosen_template_id": self.chosen_template_id,
            "verdict": self.verdict,
            "weights": dict(self.weights),
            "dissents": list(self.dissents),
            "sentinel_blocks": list(self.sentinel_blocks),
            "session_id": self.session_id,
        }


def simulate_role_verdict(role: str, top_score: float, tags: list[str]) -> tuple[str, float, str]:
    """Deterministic verdict simulation for tests / offline use.

    Returns ``(verdict, confidence, rationale)``. Production callers
    should swap this for a real model adapter — the wedge accepts any
    callable with the same signature via ``role_evaluator`` parameter.

    Heuristics (deliberately simple, deterministic, test-friendly):

    * top_score ≥ 0.7 → approve (high confidence)
    * 0.4 ≤ top_score < 0.7 → conditional
    * top_score < 0.4 → reject

    Per-role nuance:

    * critic: bumps borderline (0.55-0.7) to ``conditional`` (stricter).
    * cost_sentinel: rejects if tags include ``"complex"`` or ``"premium"``.
    * security_sentinel: rejects if tags include ``"public"``,
      ``"unsigned"`` or ``"unsafe"``.
    """
    if top_score >= 0.7:
        verdict, confidence = "approve", 0.85
    elif top_score >= 0.4:
        verdict, confidence = "conditional", 0.65
    else:
        verdict, confidence = "reject", 0.7

    tags_set = {t.lower() for t in tags}

    if role == "critic" and 0.55 <= top_score < 0.7:
        verdict, confidence = "conditional", 0.7

    if role == "cost_sentinel" and tags_set & {"complex", "premium", "expensive"}:
        verdict, confidence = "reject", 0.8

    if role == "security_sentinel" and tags_set & {"public", "unsigned", "unsafe"}:
        verdict, confidence = "reject", 0.85

    rationale = (
        f"role={role} top_score={top_score:.3f} verdict={verdict}"
        f" conf={confidence:.2f}"
    )
    return verdict, confidence, rationale


def _emit_audit(payload: dict[str, Any]) -> None:
    """Best-effort audit JSONL emit. Tamper-evident chain (ac97e957)."""
    try:
        from sylion.aeis_v2.audit_chain import append_to_chain

        append_to_chain(AUDIT_LOG_PATH, payload)
    except Exception as exc:  # noqa: BLE001
        log.warning("council_wedge: audit emit failed (%s)", exc)


def evaluate_match_with_council(
    matches: list[dict[str, Any]],
    *,
    idea_text: str,
    council: CouncilHybrid | None = None,
    role_evaluator: Any | None = None,
) -> CouncilWedgeDecision:
    """Run the council vote over a set of G1 matches and return the verdict.

    Args:
        matches: ordered list of dicts as produced by ``MatchResult.to_dict()``
            (must contain ``template``, ``score``, ``method``, ``reason_pl``).
        idea_text: the operator idea text (used as session topic).
        council: optional pre-built CouncilHybrid (testing). If None, the
            module-level singleton from ``get_council_hybrid()`` is used.
        role_evaluator: callable ``(role, top_score, tags) -> (verdict,
            confidence, rationale)``. Defaults to
            :func:`simulate_role_verdict`.

    Returns:
        :class:`CouncilWedgeDecision` describing the outcome.

    Raises:
        ValueError: if ``matches`` is empty.
    """
    if not matches:
        raise ValueError("matches must contain at least one candidate")

    ch = council or get_council_hybrid()
    evaluator = role_evaluator or simulate_role_verdict

    top = matches[0]
    template = top.get("template") or {}
    template_id = str(template.get("id", "unknown"))
    tags = list(template.get("tags") or [])
    top_score = float(top.get("score", 0.0))

    topic = f"match-idea-g1: {idea_text[:50]}"
    session = ch.open_session(
        topic=topic,
        models=list(VALID_ROLES),
        context=f"top_score={top_score:.3f} template_id={template_id}",
    )
    session_id = session["session_id"]

    # Add participants and analyses for each canonical role.
    for role in VALID_ROLES:
        rank = DEFAULT_RANK_BY_ROLE.get(role, "primary")
        weight = (
            DEFAULT_ROLE_WEIGHTS.get(role, 1.0)
            * RANK_MULTIPLIER.get(rank, 1.0)
        )
        ch.add_participant(
            session_id=session_id,
            model_id=role,
            role=role,
            rank=rank,
            weight=weight,
        )
        verdict, confidence, rationale = evaluator(role, top_score, tags)
        ch.add_analysis(
            session_id=session_id,
            model_id=role,
            analysis_text=f"role={role} score={top_score:.3f} tags={tags}",
            verdict=verdict,
            confidence=confidence,
            rationale=rationale,
        )
        # Sentinels also emit a sentinel evaluation row so weighted
        # consensus picks up sentinel_blocks for downstream gating.
        if role in SENTINEL_ROLES:
            ch.record_sentinel_evaluation(
                session_id=session_id,
                sentinel_role=role,
                model_id=role,
                verdict=verdict,
                score=confidence,
                details=rationale,
            )

    consensus = ch.compute_weighted_consensus(session_id)

    majority = consensus["verdict"]
    by_model = consensus.get("by_model", []) or []
    dissents = sorted(
        m["model_id"] for m in by_model if m.get("verdict") != majority
    )
    sentinel_blocks = list(consensus.get("sentinel_blocks") or [])
    weights = dict(consensus.get("weights") or {})

    decision = CouncilWedgeDecision(
        chosen_template_id=template_id,
        verdict=majority,
        weights=weights,
        dissents=dissents,
        sentinel_blocks=sentinel_blocks,
        session_id=session_id,
    )

    _emit_audit({
        "ts": time.time(),
        "kind": "council_wedge.decision",
        "topic": topic,
        **decision.to_dict(),
    })

    log.info(
        "council_wedge: idea=%r template=%s verdict=%s dissents=%d sentinels=%s",
        idea_text[:30], template_id, majority, len(dissents), sentinel_blocks,
    )
    return decision
