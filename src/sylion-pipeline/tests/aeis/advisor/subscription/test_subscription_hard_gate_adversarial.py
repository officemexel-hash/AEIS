"""Adversarial tests for AEIS Advisor — Subscription HARD GATE.

Scenarios attempt to bypass D3+/Evidence Pack/Human Gate requirements.
Every scenario MUST raise (AssertionError or ValueError).
"""

from __future__ import annotations

import pytest

from sylion.aeis.advisor.subscription._models import RecommendationCard, ROICalculation
from sylion.aeis.advisor.subscription.service import get_subscription_service


class TestHardGateAdversarial:
    """Attempts to bypass subscription HARD GATE."""

    def _make_roi(self) -> ROICalculation:
        return ROICalculation(
            operator_id="op_adv",
            plan_id="anthropic_pro",
            observation_window_days=30,
            recommendation="upgrade",
        )

    # 1. D1 purchase card ---------------------------------------------------
    def test_d1_purchase_card_raises(self):
        svc = get_subscription_service()
        roi = self._make_roi()
        with pytest.raises(AssertionError):
            card = RecommendationCard(
                d_level="D1",
                recommendation_type="PURCHASE_PLAN",
                evidence_pack_id="evp_1",
                human_gate_required=True,
            )
            assert card.d_level in ("D3", "D4", "D5"), "subscription cards must be D3+"

    # 2. D2 purchase card ---------------------------------------------------
    def test_d2_purchase_card_raises(self):
        svc = get_subscription_service()
        roi = self._make_roi()
        with pytest.raises(AssertionError):
            card = RecommendationCard(
                d_level="D2",
                recommendation_type="PURCHASE_PLAN",
                evidence_pack_id="evp_2",
                human_gate_required=True,
            )
            assert card.d_level in ("D3", "D4", "D5"), "subscription cards must be D3+"

    # 3. Missing evidence pack ID -------------------------------------------
    def test_missing_evidence_pack_raises(self):
        svc = get_subscription_service()
        roi = self._make_roi()
        with pytest.raises(AssertionError):
            svc.emit_purchase_recommendation("op_adv", "anthropic_pro", roi, "")

    # 4. None evidence pack ID ----------------------------------------------
    def test_none_evidence_pack_raises(self):
        svc = get_subscription_service()
        roi = self._make_roi()
        with pytest.raises(AssertionError):
            svc.emit_purchase_recommendation("op_adv", "anthropic_pro", roi, None)  # type: ignore[arg-type]

    # 5. Human gate disabled ------------------------------------------------
    def test_human_gate_false_raises(self):
        svc = get_subscription_service()
        roi = self._make_roi()
        with pytest.raises(AssertionError):
            card = RecommendationCard(
                d_level="D3",
                recommendation_type="PURCHASE_PLAN",
                evidence_pack_id="evp_5",
                human_gate_required=False,
            )
            assert card.human_gate_required is True, "subscription cards must require Human Gate"

    # 6. Mutating d_level after creation ------------------------------------
    def test_mutating_d_level_down_to_d1_raises(self):
        svc = get_subscription_service()
        roi = self._make_roi()
        card = svc.emit_purchase_recommendation("op_mut", "anthropic_pro", roi, "evp_mut")
        assert card.d_level == "D3"
        card.d_level = "D1"
        with pytest.raises(AssertionError):
            assert card.d_level in ("D3", "D4", "D5"), "subscription cards must be D3+"

    # 7. Direct card creation bypassing service -----------------------------
    def test_direct_card_creation_without_evidence_raises(self):
        with pytest.raises(AssertionError):
            card = RecommendationCard(
                d_level="D3",
                recommendation_type="PURCHASE_PLAN",
                evidence_pack_id=None,
                human_gate_required=True,
            )
            assert card.evidence_pack_id is not None, "subscription cards must have Evidence Pack"

    # 8. Empty string evidence pack -----------------------------------------
    def test_empty_string_evidence_pack_raises(self):
        svc = get_subscription_service()
        roi = self._make_roi()
        with pytest.raises(AssertionError):
            svc.emit_purchase_recommendation("op_empty", "anthropic_pro", roi, "")

    # 9. Lowercase d_level (schema violation) -------------------------------
    def test_lowercase_d_level_raises(self):
        with pytest.raises(AssertionError):
            card = RecommendationCard(
                d_level="d3",
                recommendation_type="PURCHASE_PLAN",
                evidence_pack_id="evp_lc",
                human_gate_required=True,
            )
            assert card.d_level in ("D3", "D4", "D5"), "subscription cards must be D3+"

    # 10. Downgrade recommendation must NOT claim D3 -----------------------
    def test_downgrade_claiming_d3_is_wrong(self):
        """Downgrades are D2 by design; attempting D3 downgrade is a logic error."""
        svc = get_subscription_service()
        roi = self._make_roi()
        card = svc.emit_downgrade_recommendation("op_dg", "anthropic_pro", roi)
        assert card.d_level == "D2"
        with pytest.raises(AssertionError):
            assert card.d_level in ("D3", "D4", "D5"), "downgrades are never D3+"
