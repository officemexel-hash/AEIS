"""Integration tests for subscription → Codex pricing + actions.

Pricing-dependent tests are active.
Actions-dependent tests remain skipped.
"""

from __future__ import annotations

import pytest


def test_record_usage_via_real_pricing_correctly_calculates_cost():
    """Test Codex pricing.estimator computes per-usage cost for subscription.

    Exercises: sylion.aeis.advisor.pricing.estimator (Codex Phase 2)
    """
    from sylion.aeis.advisor.pricing.estimator import estimate_cost
    from sylion.aeis.advisor.subscription.service import get_subscription_service

    svc = get_subscription_service()
    est = estimate_cost("claude-sonnet-4-6", 2000, 1000)
    assert float(est.total_cost_usd) > 0.0

    rec = svc.record_usage("op_p", "anthropic", "claude-sonnet-4-6", 2000, 1000, float(est.total_cost_usd))
    assert rec.cost_usd == pytest.approx(float(est.total_cost_usd), rel=1e-6)


def test_roi_calculator_with_real_30day_usage_metrics():
    """Test ROI calculator aggregates real usage from subscription_usage table.

    Exercises: sylion.aeis.advisor.subscription.usage_tracker + roi_calculator (Kimi)
               + sylion.aeis.advisor.pricing.estimator (Codex Phase 2)
    """
    from sylion.aeis.advisor.pricing.estimator import estimate_cost
    from sylion.aeis.advisor.subscription.service import get_subscription_service

    svc = get_subscription_service()
    est = estimate_cost("claude-sonnet-4-6", 2000, 1000)
    for _ in range(30):
        svc.record_usage("op_roi", "anthropic", "claude-sonnet-4-6", 2000, 1000, float(est.total_cost_usd))

    roi = svc.compute_roi("op_roi", "anthropic_pro", 30)
    assert roi.usage_cost_without_plan > 0.0
    assert roi.break_even_days is not None


@pytest.mark.skip(reason="awaiting Codex/Claude actions service")
def test_purchase_card_human_gate_required_via_real_actions_module():
    """Test Codex actions module routes purchase card with human gate flag.

    Exercises: sylion.aeis.advisor.actions.service (Codex Phase 2 / Claude)
    """
    from sylion.aeis.advisor.actions.service import ActionsService
    from sylion.aeis.advisor.subscription.service import get_subscription_service

    sub_svc = get_subscription_service()
    roi = sub_svc.compute_roi("op_hg", "anthropic_pro", 30)
    card = sub_svc.emit_purchase_recommendation("op_hg", "anthropic_pro", roi, "evp_int_1")

    act_svc = ActionsService()
    result = act_svc.handle_action({
        "action_type": "PURCHASE_PLAN",
        "card_id": card.card_id,
        "operator_id": "op_hg",
    })
    assert result["human_gate_required"] is True


@pytest.mark.skip(reason="awaiting Codex/Claude actions service")
def test_evidence_pack_id_present_when_actions_handles_purchase_card():
    """Test evidence pack ID flows through actions handler for D3+ purchase.

    Exercises: sylion.aeis.advisor.actions.service (Codex Phase 2 / Claude)
    """
    from sylion.aeis.advisor.actions.service import ActionsService
    from sylion.aeis.advisor.subscription.service import get_subscription_service

    sub_svc = get_subscription_service()
    roi = sub_svc.compute_roi("op_ev", "anthropic_pro", 30)
    card = sub_svc.emit_purchase_recommendation("op_ev", "anthropic_pro", roi, "evp_int_2")

    act_svc = ActionsService()
    result = act_svc.handle_action({
        "action_type": "PURCHASE_PLAN",
        "card_id": card.card_id,
        "evidence_pack_id": card.evidence_pack_id,
    })
    assert result["evidence_pack_id"] == "evp_int_2"
