"""Historical acceptance snapshot.

4th confidence component (per E5 decision in master_spec §4): the operator's
lifetime acceptance rate for a given recommendation_type, regardless of
project_type / project_domain.
"""

from __future__ import annotations

from typing import Any

from sylion.aeis.advisor.history._db import count_actions_by_status


def get_historical_acceptance_snapshot(
    *,
    operator_id: str,
    recommendation_type: str,
) -> dict[str, Any]:
    """Return the snapshot the engine confidence calculator expects.

    Shape:
        {
            "operator_accepted_count": int,
            "operator_rejected_count": int,
            "operator_acceptance_rate_for_type": float,    # 0.0 when no data
        }
    """
    accepted, rejected = count_actions_by_status(operator_id, recommendation_type)
    total = accepted + rejected
    rate = accepted / total if total else 0.0
    return {
        "operator_accepted_count": int(accepted),
        "operator_rejected_count": int(rejected),
        "operator_acceptance_rate_for_type": float(rate),
    }
