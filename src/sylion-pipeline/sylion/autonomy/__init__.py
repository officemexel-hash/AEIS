"""SYLION Autonomy -- per-project autonomy loop attached to governance spine.

Wave A5 (RB-013): the autonomy stage machine is no longer an isolated
endpoint. Every D2+ transition submits a `GovernanceTicket` (origin='autonomy')
so the spine carries the audit trail end-to-end.

This namespace is intentionally separate from `sylion.aeis.autonomy_controller`
which models the fleet-level rollout (observe -> propose -> sandbox -> limited
-> full). The stage machine here is the per-project loop that runs *within*
a given autonomy stage.
"""

from sylion.autonomy.stage_machine import (
    AutonomyPhase,
    AutonomyStageMachine,
    AutonomyTransition,
    PHASE_ORDER,
    get_autonomy_machine,
    reset_autonomy_machine,
)

__all__ = [
    "AutonomyPhase",
    "AutonomyStageMachine",
    "AutonomyTransition",
    "PHASE_ORDER",
    "get_autonomy_machine",
    "reset_autonomy_machine",
]
