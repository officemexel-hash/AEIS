"""W19 staged rollout gate.

Sprint 4 prep deliverable. Once ADR-003 flips to ACCEPTED via the
Council Hybrid sign-off (commit b7013ad0) the W19 evaluator can be
wired into production federation routing — but only behind a *staged
rollout* so a regression in policy rendering cannot impact 100% of
traffic at once.

This module provides the gate: every routing decision is hashed to a
deterministic 0-99 bucket; the W19 evaluator runs only when that
bucket is below the configured percent. Unwired/disabled by default
(0%) per ADR-003 PROPOSED status.

Usage::

    from sylion.aeis_v2.policy_v2.staged_rollout import StagedRolloutGate

    gate = StagedRolloutGate()
    if gate.should_run("decision-uuid-here"):
        # render policy template + apply
        ...

Operator dial via env:

    SYLION_W19_STAGED_ROLLOUT_PERCENT  0..100  (default 0)

Per Kimi review k2 round 55:00 — successive observability gates:

    0  → 1% (canary)
    1  → 5% (early adopters)
    5  → 25% (broad)
    25 → 50% (most)
    50 → 100% (full)

The bucket function is a pure ``sha256(decision_id) % 100`` so it is
DETERMINISTIC: the same decision_id always lands in the same bucket
regardless of when the gate runs (no flapping when the rollout
percent stays the same).
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from dataclasses import dataclass

log = logging.getLogger(__name__)

#: Operator dial.
ROLLOUT_PERCENT_ENV: str = "SYLION_W19_STAGED_ROLLOUT_PERCENT"

#: Default percent when the env var is unset / unparseable. ADR-003 is
#: still PROPOSED at module load, so the safe default is 0 (off).
DEFAULT_ROLLOUT_PERCENT: int = 0


def _read_env_percent() -> int:
    """Parse the env var; clamp to ``[0, 100]``; default 0 on parse error."""
    raw = os.environ.get(ROLLOUT_PERCENT_ENV, str(DEFAULT_ROLLOUT_PERCENT))
    try:
        v = int(raw.strip())
    except (TypeError, ValueError):
        return DEFAULT_ROLLOUT_PERCENT
    return max(0, min(100, v))


def compute_rollout_bucket(decision_id: str, modulo: int = 100) -> int:
    """Deterministic bucket assignment.

    Returns ``int(sha256(decision_id) hex prefix, 16) % modulo``.
    Modulo clamps to ``[1, 100000]`` defensively.
    """
    if not decision_id:
        return 0
    modulo = max(1, min(100_000, modulo))
    digest = hashlib.sha256(decision_id.encode("utf-8")).hexdigest()
    # Use first 12 hex chars (48 bits) — plenty of entropy for 0-99.
    return int(digest[:12], 16) % modulo


def is_in_rollout_bucket(decision_id: str, percent: int) -> bool:
    """``True`` if ``decision_id``'s 0-99 bucket is below ``percent``.

    ``percent`` is clamped to ``[0, 100]``.
    """
    p = max(0, min(100, percent))
    if p == 0:
        return False
    if p == 100:
        return True
    return compute_rollout_bucket(decision_id, modulo=100) < p


@dataclass(frozen=True, slots=True)
class StagedRolloutGate:
    """Operator-controlled gate for the W19 evaluator.

    Construction is cheap; instances are safe to share across threads
    (no mutable state). The gate re-reads the env var on every call so
    operator changes propagate without restart.
    """

    #: Override env-driven percent (mostly for tests).
    fixed_percent: int | None = None

    @property
    def percent(self) -> int:
        """Effective percent — fixed override OR env var OR default."""
        if self.fixed_percent is not None:
            return max(0, min(100, self.fixed_percent))
        return _read_env_percent()

    def should_run(self, decision_id: str) -> bool:
        """Return ``True`` if the W19 evaluator should fire for this decision."""
        return is_in_rollout_bucket(decision_id, self.percent)

    def to_dict(self) -> dict[str, int | None]:
        return {
            "fixed_percent": self.fixed_percent,
            "effective_percent": self.percent,
        }


__all__ = [
    "DEFAULT_ROLLOUT_PERCENT",
    "ROLLOUT_PERCENT_ENV",
    "StagedRolloutGate",
    "compute_rollout_bucket",
    "is_in_rollout_bucket",
]
