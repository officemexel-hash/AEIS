"""AEIS Advisor — Role Resolver service."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.aeis.advisor.role_resolver._models import (
    ModelChoice,
    Role,
    RoutingEntry,
    RoutingPreview,
)
from sylion.aeis.advisor.role_resolver._validators import ensure_model_available
from sylion.aeis.advisor.role_resolver.resolver import (
    _get_operator_override,
    resolve_judge_model,
    resolve_role_model,
)
from sylion.aeis.advisor.role_resolver.routing_table import (
    DEFAULT_ROUTING_BY_PURPOSE,
    DEFAULT_ROUTING_BY_ROLE,
    RISK_LEVELS,
    ROLES,
    PURPOSES,
)
from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.advisor.role_resolver.service")


class RoleResolverService:
    """Service for resolving abstract roles to concrete LLM models."""

    def __init__(self, event_bus: EventBus | None = None):
        self._event_bus = event_bus or get_event_bus()

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                payload=payload,
                source_module="sylion.aeis.advisor.role_resolver",
                timestamp=time.time(),
            ))

    def resolve_role(
        self,
        operator_id: str,
        role: str,
        risk_level: str,
        project_domain: str = "",
        project_type: str = "",
    ) -> ModelChoice:
        """Resolve an abstract role to a concrete model choice."""
        choice = resolve_role_model(operator_id, role, risk_level)

        event_topic = "aeis.advisor.role_resolver.routing_decision"
        if choice.reason == "operator_override":
            event_topic = "aeis.advisor.role_resolver.override_applied"
        elif choice.is_local_fallback:
            event_topic = "aeis.advisor.role_resolver.fallback_to_local"

        self._emit(event_topic, {
            "operator_id": operator_id,
            "role": role,
            "risk_level": risk_level,
            "project_domain": project_domain,
            "project_type": project_type,
            "resolved_model": choice.model_id,
            "reason": choice.reason,
            "is_local_fallback": choice.is_local_fallback,
            "used_subscription": choice.used_subscription,
            "budget_exceeded": choice.budget_exceeded,
            "suggested_alternative": choice.suggested_alternative,
        })

        log.info("resolved role=%s risk=%s -> %s (%s)",
                 role, risk_level, choice.model_id, choice.reason)
        return choice

    def resolve_judge(
        self,
        operator_id: str,
        judge_purpose: str,
        risk_level: str,
    ) -> ModelChoice:
        """Resolve a judge purpose to a concrete model choice."""
        override = _get_operator_override(operator_id, judge_purpose, risk_level)
        if override:
            for model_id in [part.strip() for part in override.split("+") if part.strip()]:
                ensure_model_available(operator_id, model_id)

        choice = resolve_judge_model(operator_id, judge_purpose, risk_level)

        event_topic = "aeis.advisor.role_resolver.routing_decision"
        if choice.reason == "operator_override":
            event_topic = "aeis.advisor.role_resolver.override_applied"
        elif choice.is_local_fallback:
            event_topic = "aeis.advisor.role_resolver.fallback_to_local"

        self._emit(event_topic, {
            "operator_id": operator_id,
            "judge_purpose": judge_purpose,
            "risk_level": risk_level,
            "resolved_model": choice.model_id,
            "reason": choice.reason,
            "is_local_fallback": choice.is_local_fallback,
            "used_subscription": choice.used_subscription,
            "budget_exceeded": choice.budget_exceeded,
            "suggested_alternative": choice.suggested_alternative,
        })

        log.info("resolved judge=%s risk=%s -> %s (%s)",
                 judge_purpose, risk_level, choice.model_id, choice.reason)
        return choice

    def list_available_roles(self) -> list[Role]:
        """List all available abstract roles."""
        return [
            Role(role_id=r, name=r.replace("_", " ").title(), description="")
            for r in ROLES
        ]

    def get_routing_matrix(self) -> list[RoutingEntry]:
        """Return the full default routing matrix."""
        entries: list[RoutingEntry] = []
        for purpose, levels in DEFAULT_ROUTING_BY_PURPOSE.items():
            for risk, model in levels.items():
                entries.append(RoutingEntry(
                    purpose_or_role=purpose,
                    risk_level=risk,
                    model_id=model,
                    description="purpose-based",
                ))
        for role, levels in DEFAULT_ROUTING_BY_ROLE.items():
            for risk, model in levels.items():
                entries.append(RoutingEntry(
                    purpose_or_role=role,
                    risk_level=risk,
                    model_id=model,
                    description="role-based",
                ))
        return entries

    def preview_routing(
        self,
        operator_id: str,
        scenario: str,
    ) -> RoutingPreview:
        """Preview routing for a scenario."""
        # Simple heuristic: if scenario contains a role name, resolve that
        # otherwise resolve as judge purpose
        role = None
        risk = "medium"
        for r in ROLES:
            if r in scenario.lower():
                role = r
                break
        for lvl in RISK_LEVELS:
            if lvl in scenario.lower():
                risk = lvl
                break

        if role:
            resolved = resolve_role_model(operator_id, role, risk)
        else:
            purpose = "rationale_generation"
            for p in PURPOSES:
                if p in scenario.lower():
                    purpose = p
                    break
            resolved = resolve_judge_model(operator_id, purpose, risk)

        # Gather alternatives
        alternatives: list[ModelChoice] = []
        from sylion.aeis.advisor.pricing import catalog
        for m in catalog.list_models():
            mid = m.model_id
            if mid != resolved.model_id:
                alternatives.append(ModelChoice(model_id=mid, reason="alternative"))

        return RoutingPreview(
            operator_id=operator_id,
            scenario=scenario,
            resolved=resolved,
            alternatives=alternatives[:3],
        )


_service: RoleResolverService | None = None


def get_role_resolver_service(event_bus: EventBus | None = None) -> RoleResolverService:
    """Get or create the global RoleResolverService singleton."""
    global _service
    if _service is None:
        _service = RoleResolverService(event_bus=event_bus)
    return _service


def reset_role_resolver_service() -> None:
    """Reset singleton for tests."""
    global _service
    _service = None
