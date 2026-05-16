"""History match snapshot.

Returns acceptance counts + rate for past cards similar to the current context.
Consumed by the engine's confidence calculator (`history_snapshot` arg).
"""

from __future__ import annotations

from typing import Any

from sylion.aeis.advisor.history._db import count_similar_actions


def get_history_match_snapshot(
    *,
    operator_id: str,
    recommendation_type: str,
    project_type: str | None = None,
    project_domain: str | None = None,
) -> dict[str, Any]:
    """Return the snapshot the engine confidence calculator expects.

    Shape:
        {
            "similar_accepted_count": int,
            "similar_rejected_count": int,
            "similar_acceptance_rate": float,    # 0.0 when no data
        }
    """
    accepted, rejected = count_similar_actions(
        operator_id, recommendation_type, project_type, project_domain
    )
    total = accepted + rejected
    rate = accepted / total if total else 0.0
    return {
        "similar_accepted_count": int(accepted),
        "similar_rejected_count": int(rejected),
        "similar_acceptance_rate": float(rate),
    }
