"""REST <-> internal calls translation layer.

Etap 1 calls the engine service in-process. Etap 2 will replace the in-process
call with a real gRPC client speaking ``advisor.engine.v1.EngineService``.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from sylion.aeis.advisor.engine.service import get_engine_service

log = logging.getLogger("sylion.aeis.advisor.mobile_gateway.translator")


# 16 lifecycle hooks (per docs/claude_parallel/aeis_advisor/00_architecture/04_lifecycle_hooks.md).
_LIFECYCLE_HOOKS = (
    "aeis.system.model_setup_requested",
    "aeis.system.api_provider_setup_requested",
    "aeis.system.budget_config_requested",
    "aeis.idea.intake.completed",
    "aeis.idea.sot_model_selection_requested",
    "aeis.council.formation_requested",
    "aeis.system.autonomy_policy_change_requested",
    "aeis.idea.sot_drafted",
    "aeis.masterplan.created",
    "aeis.system.runtime_topology_change_requested",
    "aeis.system.vps_scaling_requested",
    "aeis.system.skill_selection_requested",
    "aeis.production.deploy_requested",
    "aeis.testing.started",
    "aeis.human_gate.ticket_pending",
    "aeis.final_approval.requested",
)


def list_recent_cards(operator_id: str, limit: int = 50) -> list[dict[str, Any]]:
    svc = get_engine_service()
    return svc.list_recommendations(operator_id=operator_id, limit=limit)


def get_card(card_id: str) -> Optional[dict[str, Any]]:
    svc = get_engine_service()
    return svc.get_recommendation(card_id=card_id)


def project_lifecycle_skeleton(project_id: str) -> dict[str, Any]:
    """Return a 16-phase skeleton for a project (stub — phases all 'pending')."""
    phases = [
        {"hook": hook, "phase_index": idx, "status": "pending"}
        for idx, hook in enumerate(_LIFECYCLE_HOOKS, start=1)
    ]
    return {"project_id": project_id, "phases": phases}


def build_offline_snapshot(operator_id: str) -> dict[str, Any]:
    """Build the cache snapshot expected by the mobile app (Etap 2)."""
    cards = list_recent_cards(operator_id=operator_id, limit=50)
    return {
        "operator_id": operator_id,
        "cards": cards,
        "projects": [],
        "human_gate_pending": [],
        "funding_deadlines": [],
        "settings": {},
        "snapshot_taken_at": time.time(),
    }


def card_d_level(card: dict[str, Any]) -> str:
    header = card.get("header") or {}
    return str(header.get("d_level") or "D0")
