"""Learning loop subpackage.

Three concerns split into separate modules:
- `signal_aggregator` — builds `LearningSignal` rows from a rolling window of
  recent `card_actions` (per master_spec §9.3 thresholds).
- `soft_learning` — auto-applies soft signals to preferences (best-effort gRPC
  with no-op fallback when preferences module is not reachable).
- `hard_learning` — operator-confirmation flow: emits `hard_change_requested`
  events, accepts confirm/reject from the service facade.
"""

from sylion.aeis.advisor.history.learning.signal_aggregator import (
    SOFT_LEARNING_THRESHOLD,
    SOFT_LEARNING_WINDOW,
    aggregate_signal_for_action,
)
from sylion.aeis.advisor.history.learning.soft_learning import apply_soft_signal
from sylion.aeis.advisor.history.learning.hard_learning import (
    confirm_hard_change,
    reject_hard_change,
    request_hard_change,
)

__all__ = [
    "SOFT_LEARNING_THRESHOLD",
    "SOFT_LEARNING_WINDOW",
    "aggregate_signal_for_action",
    "apply_soft_signal",
    "request_hard_change",
    "confirm_hard_change",
    "reject_hard_change",
]
