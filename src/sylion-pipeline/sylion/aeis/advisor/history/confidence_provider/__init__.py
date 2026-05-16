"""Confidence provider — feeds the engine's 4-component confidence formula.

Two snapshots:
- `history_match` — similar past cards within the same context (component 2,
  weight 0.4 in master_spec §4 confidence formula)
- `historical_acceptance` — operator's lifetime acceptance rate for this
  recommendation_type (4th component, added per E5 decision)

Both shapes are dict-of-primitives so the engine can consume them without
importing history dataclasses.
"""

from sylion.aeis.advisor.history.confidence_provider.history_match import (
    get_history_match_snapshot,
)
from sylion.aeis.advisor.history.confidence_provider.historical_acceptance import (
    get_historical_acceptance_snapshot,
)

__all__ = ["get_history_match_snapshot", "get_historical_acceptance_snapshot"]
