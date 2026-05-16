"""End-to-end recommendation lifecycle integration test.

Exercises the engine -> history -> learning chain inside a single test:

  1. Idea intake event drives the engine to emit a card.
  2. LLM judge audit row is recorded.
  3. Operator action (accept) flows through history.record_action.
  4. After the soft-learning threshold, a learning signal is created.
  5. The history confidence-provider snapshot reflects the action.

The engine and history services share the same in-memory PG pool, so module
boundaries are exercised without mocking.
"""

from __future__ import annotations

import uuid

import pytest

from sylion.aeis.advisor import _db as shared_db
from sylion.aeis.advisor.engine import get_engine_service
from sylion.aeis.advisor.history.confidence_provider.history_match import (
    get_history_match_snapshot,
)
from sylion.aeis.advisor.history.service import get_history_service

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres


def test_idea_intake_to_card_to_action_to_history(captured_bus):
    """Idea intake -> card emitted -> operator accepts -> history records."""
    engine = get_engine_service()
    history = get_history_service()
    history.attach_to_event_bus(captured_bus)

    operator_id = str(uuid.uuid4())
    idea_id = str(uuid.uuid4())

    cards = engine.submit_event(
        topic="aeis.idea.intake.completed",
        payload={
            "idea_id": idea_id,
            "operator_id": operator_id,
            "project_domain": "software",
            "project_type": "research",
        },
        operator_id=operator_id,
    )
    assert cards, "engine must emit at least one card for idea intake"

    card_id = cards[0]["header"]["card_id"]
    d_level = cards[0]["header"]["d_level"]
    assert d_level in {"D0", "D1", "D2", "D3", "D4", "D5"}

    audits = engine.list_audits_for_card(card_id=card_id)
    if not audits:
        from psycopg.rows import dict_row
        with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM advisor_engine.llm_judge_audit")
            audits = cur.fetchall()
    assert audits, "an LLM judge audit row must exist for the emitted card"

    history.record_action(
        card_id=card_id,
        operator_id=operator_id,
        action="accept",
        context={
            "recommendation_type": "REC_TYPE_IDEA_INTAKE_GUIDANCE",
            "project_type": "research",
            "project_domain": "software",
        },
    )
    actions = history.list_actions_for_card(card_id)
    assert len(actions) == 1
    assert actions[0].action == "accept"
    assert "aeis.advisor.history.action_recorded" in captured_bus.topics()


def test_repeated_accepts_trigger_soft_learning_signal(captured_bus):
    """Five consecutive accepts must produce a card_acceptance learning signal."""
    history = get_history_service()
    history.attach_to_event_bus(captured_bus)

    operator_id = str(uuid.uuid4())
    for i in range(5):
        history.record_action(
            card_id=f"c-int-{i}",
            operator_id=operator_id,
            action="accept",
            context={
                "recommendation_type": "REC_TYPE_PURCHASE_PLAN",
                "project_type": "research",
                "project_domain": "funding",
            },
        )

    topics = captured_bus.topics()
    assert "aeis.advisor.history.learning_signal_emitted" in topics
    assert "aeis.advisor.history.soft_learning_applied" in topics

    signals = history.list_learning_signals(operator_id)
    assert any(s.signal_type == "card_acceptance" for s in signals)


def test_history_match_snapshot_reflects_recorded_actions():
    """history_match snapshot consumed by engine confidence must reflect actions."""
    history = get_history_service()

    operator_id = str(uuid.uuid4())
    for i in range(3):
        history.record_action(
            card_id=f"snap-acc-{i}",
            operator_id=operator_id,
            action="accept",
            context={
                "recommendation_type": "REC_TYPE_PURCHASE_PLAN",
                "project_type": "research",
                "project_domain": "funding",
            },
        )
    history.record_action(
        card_id="snap-rej-1",
        operator_id=operator_id,
        action="reject",
        context={
            "recommendation_type": "REC_TYPE_PURCHASE_PLAN",
            "project_type": "research",
            "project_domain": "funding",
        },
    )

    snap = get_history_match_snapshot(
        operator_id=operator_id,
        recommendation_type="REC_TYPE_PURCHASE_PLAN",
        project_type="research",
        project_domain="funding",
    )
    assert snap["similar_accepted_count"] == 3
    assert snap["similar_rejected_count"] == 1
    assert 0.0 < snap["similar_acceptance_rate"] < 1.0


def test_dont_learn_flag_blocks_signal_creation_after_streak(captured_bus):
    """An action with dont_learn=True must short-circuit the learning path."""
    history = get_history_service()
    history.attach_to_event_bus(captured_bus)

    operator_id = str(uuid.uuid4())
    for i in range(4):
        history.record_action(
            card_id=f"streak-{i}",
            operator_id=operator_id,
            action="accept",
            context={
                "recommendation_type": "REC_TYPE_PURCHASE_PLAN",
                "project_type": "research",
                "project_domain": "funding",
            },
        )

    captured_bus.events.clear()
    history.record_action(
        card_id="dontlearn-1",
        operator_id=operator_id,
        action="accept",
        context={
            "recommendation_type": "REC_TYPE_PURCHASE_PLAN",
            "project_type": "research",
            "project_domain": "funding",
            "dont_learn": True,
        },
    )

    topics = captured_bus.topics()
    assert "aeis.advisor.history.skip_learning_recorded" in topics
    assert "aeis.advisor.history.learning_signal_emitted" not in topics

    signals = history.list_learning_signals(operator_id)
    for s in signals:
        assert s.source_card_id != "dontlearn-1"
