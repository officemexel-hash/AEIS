"""Integration tests for role_resolver → Codex preferences/pricing + Claude engine.

Tests depending only on Codex Phase 2 (preferences/pricing) are active.
Tests needing Claude engine remain skipped.
"""

from __future__ import annotations

import uuid

import pytest

from sylion.aeis.advisor.preferences import get_preferences


def _uuid(suffix: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kimi-int.{suffix}"))


def test_resolve_with_real_preferences_blocked_provider_excluded():
    """Test Codex preferences resolver blocked_providers exclusion.

    Exercises: sylion.aeis.advisor.preferences (Codex Phase 2)
    """
    from sylion.aeis.advisor.role_resolver.service import get_role_resolver_service

    svc = get_role_resolver_service()
    uid = _uuid("op_int")
    get_preferences().set_preference(
        user_id=uid,
        project_type=None,
        project_domain=None,
        preference_key="blocked_providers",
        value=["anthropic"],
        bypass_hard_check=True,
    )
    get_preferences().set_preference(
        user_id=uid,
        project_type=None,
        project_domain=None,
        preference_key="cost_ceilings",
        value={"low": 200.0, "medium": 200.0, "high": 200.0, "critical": 200.0},
    )
    choice = svc.resolve_role(uid, "planner", "high")
    assert "claude" not in choice.model_id
    assert choice.reason in ("default_ensemble_pick", "local_fallback", "generic_fallback")


def test_resolve_with_real_pricing_cost_ceiling_enforced():
    """Test Codex pricing.estimator::estimate_cost enforces cost ceiling.

    Exercises: sylion.aeis.advisor.pricing.estimator (Codex Phase 2)
    """
    from sylion.aeis.advisor.pricing.estimator import estimate_cost
    from sylion.aeis.advisor.role_resolver.service import get_role_resolver_service

    svc = get_role_resolver_service()
    # Verify pricing module returns non-zero cost for premium model
    est = estimate_cost("claude-opus-4-7", 2000, 1000)
    assert float(est.total_cost_usd) > 0.0
    # With default low ceiling, opus should be dropped
    uid = _uuid("op_low_ceiling")
    get_preferences().set_preference(
        user_id=uid,
        project_type=None,
        project_domain=None,
        preference_key="cost_ceilings",
        value={"low": 1.0, "medium": 1.0, "high": 1.0, "critical": 1.0},
    )
    choice = svc.resolve_role(uid, "planner", "critical")
    # opus costs ~$105 for 2k/1k, should be dropped by ceiling
    assert choice.model_id != "claude-opus-4-7"
    assert choice.reason in ("generic_fallback", "local_fallback")


def test_resolve_falls_back_to_local_when_external_blocked():
    """Test local fallback when all external providers blocked by preferences.

    Exercises: sylion.aeis.advisor.preferences (Codex Phase 2)
    """
    from sylion.aeis.advisor.role_resolver.service import get_role_resolver_service

    svc = get_role_resolver_service()
    uid = _uuid("op_fb")
    get_preferences().set_preference(
        user_id=uid,
        project_type=None,
        project_domain=None,
        preference_key="blocked_providers",
        value=["anthropic", "openai", "google"],
        bypass_hard_check=True,
    )
    get_preferences().set_preference(
        user_id=uid,
        project_type=None,
        project_domain=None,
        preference_key="cost_ceilings",
        value={"low": 200.0, "medium": 200.0, "high": 200.0, "critical": 200.0},
    )
    choice = svc.resolve_role(uid, "planner", "medium")
    assert choice.is_local_fallback is True
    assert "qwen" in choice.model_id


@pytest.mark.skip(reason="awaiting Claude engine audit subscriber")
def test_routing_decision_audit_trail_persisted():
    """Test audit subscriber persists routing decision events.

    Exercises: sylion.aeis.advisor.events.audit_subscriber (Claude engine)
    Unskip after: commit [advisor][claude][engine] events audit subscriber
    """
    from sylion.aeis.advisor.events.audit_subscriber import AdvisorAuditSubscriber
    from sylion.aeis.advisor.role_resolver.service import get_role_resolver_service
    from sylion.core.event_backbone import get_event_backbone

    svc = get_role_resolver_service()
    backbone = get_event_backbone()
    subscriber = AdvisorAuditSubscriber(db_pool=None, event_backbone=backbone)

    svc.resolve_role(_uuid("op_aud"), "critic", "high")
    # Query advisor_events.events table for emitted routing_decision
    rows = subscriber.query_by_topic("aeis.advisor.role_resolver.routing_decision")
    assert len(rows) >= 1
