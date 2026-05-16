"""Synchronous gate (H13/H16) integration tests.

H13 production deploy and H16 final approval lifecycle hooks call
`engine.evaluate_gate(...)` and wait for a verdict (`proceed`/`block`/
`defer_to_human_gate`). The block path emits `REC_TYPE_BLOCK_PRODUCTION_DEPLOY`
when the SoT was not approved.
"""

from __future__ import annotations

import uuid

from sylion.aeis.advisor.engine import get_engine_service


def test_production_deploy_blocked_when_sot_not_approved():
    """SoT not approved -> gate must BLOCK with a card_id reference."""
    engine = get_engine_service()
    operator_id = str(uuid.uuid4())

    decision = engine.evaluate_gate(
        topic="aeis.production.deploy_requested",
        payload={
            "operator_id": operator_id,
            "project_id": str(uuid.uuid4()),
            "masterplan_id": str(uuid.uuid4()),
            "bundle_id": str(uuid.uuid4()),
            "sot_approved": False,
            "council_approved": False,
            "is_production": True,
        },
        operator_id=operator_id,
        timeout_s=5.0,
    )
    assert decision.decision == "block"
    assert decision.blocking_card_id

    rec = engine.get_recommendation(card_id=decision.blocking_card_id)
    assert rec is not None
    # The block card is unconditionally D5 per default_rules.py.
    assert rec["header"]["d_level"] == "D5"
    # An evidence pack is always created for D5.
    assert rec["header"]["evidence_pack_id"]


def test_production_deploy_proceeds_when_sot_approved():
    """When SoT is approved no BLOCK card is emitted -> gate must PROCEED."""
    engine = get_engine_service()
    operator_id = str(uuid.uuid4())

    decision = engine.evaluate_gate(
        topic="aeis.production.deploy_requested",
        payload={
            "operator_id": operator_id,
            "project_id": str(uuid.uuid4()),
            "masterplan_id": str(uuid.uuid4()),
            "bundle_id": str(uuid.uuid4()),
            "sot_approved": True,
            "council_approved": True,
            "is_production": True,
        },
        operator_id=operator_id,
        timeout_s=5.0,
    )
    assert decision.decision == "proceed"
    assert decision.blocking_card_id == ""


def test_gate_falls_through_to_proceed_when_no_rules_match():
    """An unknown topic must not block: gate defaults to PROCEED."""
    engine = get_engine_service()
    operator_id = str(uuid.uuid4())

    decision = engine.evaluate_gate(
        topic="aeis.unknown.event_for_gate_test",
        payload={"operator_id": operator_id},
        operator_id=operator_id,
        timeout_s=2.0,
    )
    assert decision.decision == "proceed"
