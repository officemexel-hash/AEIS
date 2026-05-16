"""Hard learning — operator-confirmation flow.

Some preference changes are too consequential for soft auto-apply (per
master_spec §9.3). The signal is flagged `hard_change_status='pending'`,
the `aeis.advisor.history.hard_change_requested` event is emitted by the
service facade, and the operator must confirm or reject via the UI/REST.
"""

from __future__ import annotations

import logging

from sylion.aeis.advisor.history._db import (
    fetch_signal_by_id,
    update_signal_applied,
    update_signal_hard_status,
)
from sylion.aeis.advisor.history._models import LearningSignal
from sylion.aeis.advisor.history.learning.soft_learning import apply_soft_signal

log = logging.getLogger("sylion.aeis.advisor.history.learning.hard_learning")


def request_hard_change(signal: LearningSignal) -> None:
    """Mark the signal as pending confirmation. No-op if already pending."""
    if signal.hard_change_status == "pending":
        return
    update_signal_hard_status(signal.signal_id, "pending")
    signal.hard_change_status = "pending"


def confirm_hard_change(*, signal_id: str, operator_id: str) -> bool:
    """Confirm a pending hard change: apply to preferences + flip status."""
    signal = fetch_signal_by_id(signal_id)
    if signal is None or signal.operator_id != operator_id:
        return False
    if signal.hard_change_status != "pending":
        return False

    result = apply_soft_signal(signal)
    update_signal_hard_status(signal_id, "confirmed")
    if result.get("applied"):
        update_signal_applied(signal_id)
    else:
        log.warning(
            "hard change confirmed but preferences apply failed: signal=%s reason=%s",
            signal_id,
            result.get("reason"),
        )
    return True


def reject_hard_change(*, signal_id: str, operator_id: str) -> bool:
    """Reject a pending hard change: status -> 'rejected', do not apply."""
    signal = fetch_signal_by_id(signal_id)
    if signal is None or signal.operator_id != operator_id:
        return False
    if signal.hard_change_status != "pending":
        return False
    update_signal_hard_status(signal_id, "rejected")
    return True
