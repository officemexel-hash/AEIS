"""Semantic / structural validators."""
from __future__ import annotations

from typing import Mapping


def require_branch_not_main(branch_id: str, field_name: str = "branch_id") -> None:
    """HARD constraint: PatchProposal.branch_id MUST NOT be 'main'."""
    if branch_id == "main":
        raise ValueError(
            f"{field_name} must not be 'main' — patches MUST live on a branch"
        )


def require_status_transition(current: str, proposed: str,
                              transitions: Mapping[str, set[str]],
                              field_name: str = "status") -> None:
    """Require proposed status to be a legal transition from current."""
    allowed = transitions.get(current, set())
    if proposed == current:
        return
    if proposed not in allowed:
        raise ValueError(
            f"{field_name}: illegal transition {current!r} -> {proposed!r}; "
            f"allowed: {sorted(allowed)}"
        )
