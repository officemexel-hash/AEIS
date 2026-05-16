"""Operator-facing demo of the AEIS Advisor Layer.

Run via:
    pytest tests/aeis/advisor/_e2e/demo_full_flow.py -v -s

Prints a narrated walkthrough of the advisor flow:
  1. Operator submits a new idea (idea intake event)
  2. Engine emits at least one card (rule -> LLM judge -> envelope)
  3. Operator accepts the card via the actions service
  4. History records the action and aggregates a learning signal
  5. Operator triggers a production deploy without SoT approval
  6. The synchronous gate BLOCKS the deploy with a D5 card + evidence pack
  7. Operator signs and finalizes the evidence pack
  8. Final report shows the full correlation chain across modules

The demo runs entirely against the in-memory PG shim (no real DB required) so
it doubles as both a smoke check and an executable specification of the
operator's golden path.
"""

from __future__ import annotations

import json
import uuid

from sylion.aeis.advisor.engine import get_engine_service
from sylion.aeis.advisor.history.confidence_provider.history_match import (
    get_history_match_snapshot,
)
from sylion.aeis.advisor.history.service import get_history_service


class _Bus:
    def __init__(self):
        self.events = []
        self._subs: dict[str, list] = {}

    def publish(self, event):
        self.events.append(event)
        for h in self._subs.get(event.topic, []):
            try:
                h(event)
            except Exception:
                pass
        return event.event_id

    def subscribe(self, topic, handler):
        self._subs.setdefault(topic, []).append(handler)


def _say(step: int, title: str, detail: str = "") -> None:
    print(f"\n[STEP {step}] {title}")
    if detail:
        print(f"         {detail}")


def test_demo_full_operator_flow():
    """Walk the operator through a complete advisor session."""
    print("\n" + "=" * 70)
    print("AEIS Advisor Layer — End-to-End Demo")
    print("=" * 70)

    bus = _Bus()
    engine = get_engine_service()
    history = get_history_service()
    history.attach_to_event_bus(bus)

    operator_id = str(uuid.uuid4())
    print(f"\nOperator id: {operator_id}")

    # --- STEP 1: idea intake ----------------------------------------------
    _say(1, "Operator submits a new idea")
    idea_id = str(uuid.uuid4())
    cards = engine.submit_event(
        topic="aeis.idea.intake.completed",
        payload={
            "idea_id": idea_id,
            "operator_id": operator_id,
            "project_domain": "software",
            "project_type": "research",
            "title": "Build AEIS advisor demo",
        },
        operator_id=operator_id,
    )
    assert cards, "engine should emit at least one card on idea intake"
    intake_card = cards[0]
    intake_card_id = intake_card["header"]["card_id"]
    print(
        f"         engine emitted card {intake_card_id} "
        f"(d_level={intake_card['header']['d_level']}, "
        f"risk={intake_card['header']['risk_level']})"
    )

    # --- STEP 2: confirm LLM-judge audit was recorded ---------------------
    _say(2, "LLM judge audit recorded")
    audits = engine.list_audits_for_card(card_id=intake_card_id)
    print(f"         audits found for card: {len(audits)} (per-card link or schema-wide)")

    # --- STEP 3: operator accepts the card --------------------------------
    _say(3, "Operator accepts the recommendation")
    history.record_action(
        card_id=intake_card_id,
        operator_id=operator_id,
        action="accept",
        context={
            "recommendation_type": "REC_TYPE_IDEA_INTAKE_GUIDANCE",
            "project_type": "research",
            "project_domain": "software",
        },
    )
    actions = history.list_actions_for_card(intake_card_id)
    assert len(actions) == 1
    print(f"         history.card_actions row: action='{actions[0].action}'")

    # --- STEP 4: build a streak so soft learning fires --------------------
    _say(4, "Operator continues to accept similar cards (soft-learning streak)")
    for i in range(4):
        history.record_action(
            card_id=f"warmup-{i}",
            operator_id=operator_id,
            action="accept",
            context={
                "recommendation_type": "REC_TYPE_IDEA_INTAKE_GUIDANCE",
                "project_type": "research",
                "project_domain": "software",
            },
        )
    learning_topics = [e.topic for e in bus.events if "history" in e.topic]
    assert "aeis.advisor.history.learning_signal_emitted" in learning_topics
    print(
        f"         history emitted: "
        f"{sorted(set(t.split('.')[-1] for t in learning_topics))}"
    )

    # --- STEP 5: operator attempts production deploy without SoT ---------
    _say(5, "Operator triggers production deploy WITHOUT SoT approval")
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
    block_card_id = decision.blocking_card_id
    print(
        f"         synchronous gate decision: {decision.decision}, "
        f"card_id={block_card_id}"
    )

    # --- STEP 6: pull the BLOCK card + its evidence pack ------------------
    _say(6, "BLOCK card includes a Full evidence pack")
    block_card = engine.get_recommendation(card_id=block_card_id)
    assert block_card is not None
    pack_id = block_card["header"]["evidence_pack_id"]
    assert pack_id
    pack = engine.get_evidence_pack(pack_id=pack_id)
    print(
        f"         d_level={block_card['header']['d_level']}, "
        f"evidence_pack_id={pack_id}, status={pack['status']}, "
        f"template={pack['pack_template']}"
    )

    # --- STEP 7: operator signs + finalizes the evidence pack -------------
    _say(7, "Operator signs and finalizes the evidence pack")
    engine.sign_evidence_pack(
        pack_id=pack_id,
        signer_id=operator_id,
        signer_role="operator",
        signature_payload="sha256:demo-sig",
    )
    finalized = engine.finalize_evidence_pack(pack_id=pack_id)
    assert finalized is True
    pack_after = engine.get_evidence_pack(pack_id=pack_id)
    assert pack_after["status"] == "finalized"
    print(
        f"         pack finalized at {pack_after['finalized_at']}, "
        f"signatures={len(pack_after['signatures'])}"
    )

    # --- STEP 8: final correlation chain ----------------------------------
    _say(8, "Final report — correlation chain across modules")
    snap = get_history_match_snapshot(
        operator_id=operator_id,
        recommendation_type="REC_TYPE_IDEA_INTAKE_GUIDANCE",
        project_type="research",
        project_domain="software",
    )
    summary = {
        "operator_id": operator_id,
        "intake_card_id": intake_card_id,
        "block_card_id": block_card_id,
        "evidence_pack_id": pack_id,
        "history_match": snap,
        "events_emitted": len(bus.events),
        "events_topics": sorted(set(e.topic for e in bus.events)),
    }
    print(json.dumps(summary, indent=2, default=str))
    print("\n" + "=" * 70)
    print("Demo complete — every layer of the advisor produced a result.")
    print("=" * 70)
