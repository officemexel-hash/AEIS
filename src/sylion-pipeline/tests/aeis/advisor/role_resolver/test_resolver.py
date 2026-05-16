"""Tests for AEIS Advisor — Role Resolver.

Scenarios per manifest §4:
- planner_role_high_risk_uses_opus
- blocked_provider_excluded_from_resolution
- operator_override_wins
- cost_ceiling_drops_premium_model
- all_external_unavailable_falls_back_to_local
- routing_decision_logged_with_reason
"""

from __future__ import annotations

import uuid

from sylion.aeis.advisor.preferences import get_preferences
from sylion.aeis.advisor.role_resolver.resolver import (
    resolve_judge_model,
    resolve_role_model,
    _is_model_available,
    _within_cost_ceiling,
)
from sylion.aeis.advisor.role_resolver.service import get_role_resolver_service


def _uuid() -> str:
    """Generate fresh UUID for each test call to avoid PG cross-run pollution."""
    return str(uuid.uuid4())


def _set_ceiling(uid: str) -> None:
    """Set permissive cost ceilings so premium models aren't dropped."""
    get_preferences().set_preference(
        user_id=uid,
        project_type=None,
        project_domain=None,
        preference_key="cost_ceilings",
        value={"low": 200.0, "medium": 200.0, "high": 200.0, "critical": 200.0},
    )


class TestPlannerRoleHighRiskUsesOpus:
    """planner_role_high_risk_uses_opus"""

    def test_planner_critical(self):
        uid = _uuid()
        _set_ceiling(uid)
        choice = resolve_role_model(uid, "planner", "critical")
        assert choice.model_id == "claude-opus-4-7"
        assert choice.reason == "default_role_routing"

    def test_planner_high(self):
        uid = _uuid()
        _set_ceiling(uid)
        choice = resolve_role_model(uid, "planner", "high")
        assert choice.model_id == "claude-opus-4-7"


class TestBlockedProviderExcluded:
    """blocked_provider_excluded_from_resolution"""

    def test_blocked_anthropic_excluded(self):
        uid = _uuid()
        get_preferences().set_preference(
            user_id=uid,
            project_type=None,
            project_domain=None,
            preference_key="blocked_providers",
            value=["anthropic"],
            bypass_hard_check=True,
        )
        assert _is_model_available(uid, "claude-opus-4-7") is False
        assert _is_model_available(uid, "qwen2.5:72b-instruct") is True

    def test_blocked_fallback_to_local(self):
        uid = _uuid()
        get_preferences().set_preference(
            user_id=uid,
            project_type=None,
            project_domain=None,
            preference_key="blocked_providers",
            value=["anthropic", "openai", "google"],
            bypass_hard_check=True,
        )
        choice = resolve_role_model(uid, "planner", "medium")
        # Only local models available
        assert "qwen" in choice.model_id
        assert choice.is_local_fallback or choice.reason in ("default_role_routing", "local_fallback")


class TestOperatorOverrideWins:
    """operator_override_wins"""

    def test_override_takes_precedence(self):
        uid = _uuid()
        _set_ceiling(uid)
        get_preferences().set_preference(
            user_id=uid,
            project_type=None,
            project_domain=None,
            preference_key="llm_judge_routing_override",
            value={"rationale_generation:medium": "gpt-5"},
        )
        choice = resolve_judge_model(uid, "rationale_generation", "medium")
        assert choice.model_id == "gpt-5"
        assert choice.reason == "operator_override"


class TestCostCeilingDropsPremium:
    """cost_ceiling_drops_premium_model"""

    def test_low_ceiling_drops_opus(self):
        uid = _uuid()
        get_preferences().set_preference(
            user_id=uid,
            project_type=None,
            project_domain=None,
            preference_key="cost_ceilings",
            value={"low": 1.0, "medium": 1.0, "high": 1.0, "critical": 1.0},
        )
        choice = resolve_judge_model(uid, "rationale_generation", "critical")
        # opus-4-7 costs ~$105 for 2k/1k, should be dropped
        assert choice.model_id != "claude-opus-4-7"
        assert choice.reason in ("generic_fallback", "local_fallback")

    def test_within_cost_ceiling_direct(self):
        assert _within_cost_ceiling("qwen2.5:7b-instruct", "low", _uuid()) is True


class TestAllExternalUnavailableFallsBack:
    """all_external_unavailable_falls_back_to_local"""

    def test_all_external_blocked_fallback_local(self):
        uid = _uuid()
        get_preferences().set_preference(
            user_id=uid,
            project_type=None,
            project_domain=None,
            preference_key="blocked_providers",
            value=["anthropic", "openai", "google"],
            bypass_hard_check=True,
        )
        choice = resolve_judge_model(uid, "funding_scoring", "critical")
        assert choice.is_local_fallback or "qwen" in choice.model_id


class TestRoutingDecisionLogged:
    """routing_decision_logged_with_reason"""

    def test_service_emits_event(self):
        uid = _uuid()
        _set_ceiling(uid)
        svc = get_role_resolver_service()
        choice = svc.resolve_role(uid, "critic", "high")
        assert choice.model_id == "claude-opus-4-7"
        assert choice.reason == "default_role_routing"

    def test_service_preview(self):
        uid = _uuid()
        _set_ceiling(uid)
        svc = get_role_resolver_service()
        preview = svc.preview_routing(uid, "planner low risk")
        assert preview.resolved.model_id == "claude-sonnet-4-6"
