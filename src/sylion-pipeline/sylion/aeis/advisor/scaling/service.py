"""AEIS Advisor — Scaling service."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sylion.aeis.advisor.scaling._models import ScalingCard, StagingPlan
from sylion.aeis.advisor.scaling.topology_recommender import recommend_topology
from sylion.aeis.advisor.scaling.staging_planner import propose_staging_plan
from sylion.aeis.advisor.scaling.env_inventory import (
    register_env as _register_env,
    get_env_inventory as _get_env_inventory,
)
from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.advisor.scaling.service")


class ScalingService:
    """Service for runtime scaling recommendations."""

    def __init__(self, event_bus: EventBus | None = None):
        self._event_bus = event_bus or get_event_bus()

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                payload=payload,
                source_module="sylion.aeis.advisor.scaling",
                timestamp=time.time(),
            ))

    def recommend_topology(
        self,
        operator_id: str,
        project_id: str,
        workload_profile: dict[str, Any],
    ) -> ScalingCard:
        """Recommend topology for a workload."""
        workload = dict(workload_profile)
        workload["project_id"] = project_id
        card = recommend_topology(operator_id, workload)

        self._emit("aeis.advisor.scaling.topology_recommended", {
            "card_id": card.card_id,
            "operator_id": operator_id,
            "project_id": project_id,
            "recommended": card.recommended,
            "d_level": card.d_level,
        })

        log.info("recommended topology %s for %s (D%s)",
                 card.recommended, project_id, card.d_level)
        return card

    def propose_staging_plan(
        self,
        current_topology: str,
        target_topology: str,
    ) -> StagingPlan:
        """Propose a staging plan."""
        plan = propose_staging_plan(current_topology, target_topology)

        self._emit("aeis.advisor.scaling.staging_proposed", {
            "plan_id": plan.plan_id,
            "current": current_topology,
            "target": target_topology,
            "phases": len(plan.phases),
        })

        return plan

    def get_env_inventory(self, operator_id: str) -> list[dict[str, Any]]:
        """List environments for an operator."""
        return [e.to_dict() for e in _get_env_inventory(operator_id)]

    def register_env(self, env_data: dict[str, Any]) -> dict[str, Any]:
        """Register an environment."""
        env = _register_env(env_data)
        self._emit("aeis.advisor.scaling.env_registered", {
            "env_id": env.env_id,
            "operator_id": env.operator_id,
            "kind": env.kind,
        })
        return env.to_dict()


_service: ScalingService | None = None


def get_scaling_service(event_bus: EventBus | None = None) -> ScalingService:
    """Get or create the global ScalingService singleton."""
    global _service
    if _service is None:
        _service = ScalingService(event_bus=event_bus)
    return _service


def reset_scaling_service() -> None:
    """Reset singleton for tests."""
    global _service
    _service = None
