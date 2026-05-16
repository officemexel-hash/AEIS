"""
SYLION Governance — Round Meta-Orchestration HG Ticket Factory.

Creates Human Gate tickets for the three Round chokepoints in the
canonical idea -> ksiega -> masterplan -> build flow:

    Round 1 (idea -> ksiega):       blocking
    Round 2 (ksiega -> masterplan): blocking
    Round 3 (masterplan -> build):  multi-gate
                                    [financial, production, external_action]

The factory wraps :func:`sylion.governance.human_gate.get_human_gate`
so the rest of the system stays decoupled from HG internals — callers
just hand in a payload and get back a ticket id.

Invariants:
    * Round 3 always emits at least one ticket and persists ALL gate
      types in ``payload['gate_types']`` so downstream auditors can
      verify multi-gate composition without re-deriving it.
    * ``round`` is restricted at type-check time to literal {1, 2, 3};
      runtime guard rejects anything else with ValueError so callers
      can't slip an int through ``Any``.
    * The ticket title and summary are deterministic per round to make
      audit chain replay reproducible.

Used by:
    * frontend Round 1 banner (AR-1) -> /api/v1/ideas/{id}/promote
    * frontend Round 2 banner (FE-4) -> /api/v1/projects/{id}/round-2/approve
    * frontend Round 3 banner (AR-2) -> /api/v1/projects/{id}/build/authorize
"""

from __future__ import annotations

from typing import Any, Literal, get_args

from sylion.governance.human_gate import HumanGate, get_human_gate

# ---------------------------------------------------------------------------
# Public type aliases
# ---------------------------------------------------------------------------

#: Allowed Round numbers in the meta-orchestration state machine.
RoundNumber = Literal[1, 2, 3]

#: HG gate types used by the Round factory. Subset of the HG global vocab
#: ("blocking", "non-blocking", "batch", "emergency", "financial", "legal",
#: "production", "security", "external_action", "final").
GateType = Literal["blocking", "production", "financial", "external_action"]

# Round -> ordered list of gate types (Round 3 is multi-gate).
_ROUND_GATE_TYPES: dict[int, list[GateType]] = {
    1: ["blocking"],
    2: ["blocking"],
    3: ["financial", "production", "external_action"],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_round_meta_ticket(
    *,
    round: RoundNumber,
    project_id: str,
    payload: dict[str, Any],
    requested_by: str,
    hg: HumanGate | None = None,
) -> str:
    """Create a Human Gate ticket for one of the three Round chokepoints.

    Args:
        round: 1 (idea -> ksiega), 2 (ksiega -> masterplan), 3 (masterplan -> build).
        project_id: target project id (used in title + persisted in context).
        payload: round-specific data — for Round 3 typically
            ``{"cost_cap_usd": float, "autonomy_level": "L0..L4",
            "external_actions_policy": dict}``.
        requested_by: actor id (operator name or system id).
        hg: optional HumanGate instance for testing; defaults to the
            singleton from ``get_human_gate()``.

    Returns:
        The ticket / request id (string).

    Raises:
        ValueError: if ``round`` is not 1, 2, or 3.
        TypeError: if required string args are missing or wrong type.
    """
    if round not in get_args(RoundNumber):
        raise ValueError(
            f"Invalid round: {round!r}. Must be one of {get_args(RoundNumber)}."
        )
    if not isinstance(project_id, str) or not project_id:
        raise TypeError("project_id must be a non-empty string")
    if not isinstance(requested_by, str) or not requested_by:
        raise TypeError("requested_by must be a non-empty string")
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")

    gate_types = _ROUND_GATE_TYPES[round]
    title = f"Round {round} approval — project {project_id}"
    summary = _build_summary(round, payload)

    # Persist round + all gate types alongside caller's payload so audit
    # replay reconstructs full multi-gate composition without guessing.
    context: dict[str, Any] = {
        **payload,
        "round": round,
        "project_id": project_id,
        "gate_types": list(gate_types),
        "primary_gate_type": gate_types[0],
    }

    gate = hg if hg is not None else get_human_gate()
    request = gate.create_request(
        gate_id=f"round_{round}",
        title=title,
        description=summary,
        context_json=context,
        requested_by=requested_by,
    )
    return str(request["request_id"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_summary(round: int, payload: dict[str, Any]) -> str:
    """Deterministic round-specific summary for audit replay."""
    if round == 1:
        return (
            "Zatwierdzenie skladu Rady i limitu kosztu dla wytworzenia Ksiegi "
            "(Source of Truth)."
        )
    if round == 2:
        return (
            "Zatwierdzenie skladu Rady i zasad planowania dla wygenerowania "
            "masterplanu na podstawie zamrozonej Ksiegi."
        )
    if round == 3:
        cost_cap = float(payload.get("cost_cap_usd", 0.0))
        autonomy = str(payload.get("autonomy_level", "L0"))
        return (
            f"Autoryzacja rozpoczecia budowy. Cost cap: ${cost_cap:.2f}, "
            f"autonomy: {autonomy}. Multi-gate: financial+production+external_action."
        )
    return ""  # unreachable thanks to the validate-on-entry guard
