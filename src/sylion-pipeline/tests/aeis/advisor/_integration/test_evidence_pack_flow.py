"""Evidence Pack creation + signing + finalization integration tests.

Per `06_evidence_pack_template.md`:
  - D5 cards must always carry a finalised pack before they can be acted on
  - D3 cost / subscription / funding cards trigger a Light pack auto-attached

The engine creates the pack BEFORE the card emits, so evidence_pack_id is
populated on the card header.
"""

from __future__ import annotations

import uuid

from sylion.aeis.advisor.engine import get_engine_service


def test_d5_block_card_creates_full_evidence_pack():
    """A BLOCK production deploy card (D5) must auto-create a pack."""
    engine = get_engine_service()
    operator_id = str(uuid.uuid4())

    cards = engine.submit_event(
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
    )
    assert cards
    card = cards[0]
    pack_id = card["header"]["evidence_pack_id"]
    assert pack_id, "D5 card must reference an evidence pack"

    pack = engine.get_evidence_pack(pack_id=pack_id)
    assert pack is not None
    assert pack["d_level"] == "D5"
    assert pack["pack_template"] in ("d5_full", "d3_light")
    assert pack["status"] == "draft"
    assert pack["rationale"]
    assert pack["rollback_plan"]
    assert pack["fidelity_test"]


def test_pack_signing_and_finalization_round_trip():
    """Signature insertion + finalize update flips status to finalized."""
    engine = get_engine_service()
    operator_id = str(uuid.uuid4())

    cards = engine.submit_event(
        topic="aeis.production.deploy_requested",
        payload={
            "operator_id": operator_id,
            "project_id": str(uuid.uuid4()),
            "sot_approved": False,
            "is_production": True,
        },
        operator_id=operator_id,
    )
    pack_id = cards[0]["header"]["evidence_pack_id"]

    sig_id = engine.sign_evidence_pack(
        pack_id=pack_id,
        signer_id=operator_id,
        signer_role="operator",
        signature_payload="sha256:test-sig",
    )
    assert sig_id

    pack = engine.get_evidence_pack(pack_id=pack_id)
    assert pack["signatures"]
    assert pack["signatures"][0]["signer_role"] == "operator"

    finalized = engine.finalize_evidence_pack(pack_id=pack_id)
    assert finalized is True

    pack_after = engine.get_evidence_pack(pack_id=pack_id)
    assert pack_after["status"] == "finalized"
    assert pack_after["finalized_at"] is not None


def test_low_risk_card_does_not_create_evidence_pack():
    """A vanilla idea_intake card is D0 -> no pack required."""
    engine = get_engine_service()
    operator_id = str(uuid.uuid4())

    cards = engine.submit_event(
        topic="aeis.idea.intake.completed",
        payload={
            "idea_id": str(uuid.uuid4()),
            "operator_id": operator_id,
            "project_domain": "research",
        },
        operator_id=operator_id,
    )
    assert cards
    # idea_intake_initial_guidance default is D0 -> no pack required.
    assert cards[0]["header"]["evidence_pack_id"] == ""
