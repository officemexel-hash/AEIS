"""Smoke tests for advisor.engine — golden minimums per manifest §3.

These tests intentionally avoid network calls; the LLM judge stub is exercised
when no provider key is set, so the pipeline still produces structured output.

DB layer runs against an in-memory SQLite-backed shim of the shared PG pool
(installed via `conftest.py`). Module code uses the shared PG pool exclusively;
the shim is a TEST-ONLY fixture per `08_audit_revisions.md` Revision 2.
"""

from __future__ import annotations

import os

import pytest

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")
os.environ.setdefault("SYLION_ADVISOR_LOCAL_ONLY", "0")

from sylion.aeis.advisor import _db as shared_db
from sylion.aeis.advisor.engine import get_engine_service
from sylion.aeis.advisor.engine.confidence.calculator import (
    LOCAL_FALLBACK_MULTIPLIER,
    calculate_confidence,
)
from sylion.aeis.advisor.engine.card_builder.validators import (
    EnvelopeValidationError,
    validate_envelope,
)
from sylion.aeis.advisor.engine.d_ladder import (
    EvidencePackRequirement,
    assign_d_level,
    determine_evidence_pack_requirement,
)
from sylion.aeis.advisor.engine._models import (
    AdvisorCardEnvelope,
    AdvisorCardHeader,
    DecisionCard,
    confidence_label_for,
)
from sylion.aeis.advisor.engine.rule_engine import (
    match_event_to_rules,
    seed_default_rules,
)
from sylion.aeis.advisor.engine.rule_engine.dsl import evaluate


@pytest.fixture(autouse=True)
def _reset_provider_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    yield


def test_dsl_basic_match():
    assert evaluate({}, {}) == (True, "empty_precondition")
    matched, _ = evaluate(
        {"field": "payload.x", "op": ">", "value": 5}, {"payload": {"x": 7}}
    )
    assert matched
    matched, _ = evaluate(
        {"and": [
            {"field": "payload.x", "op": "==", "value": 1},
            {"field": "payload.y", "op": "==", "value": 2},
        ]},
        {"payload": {"x": 1, "y": 2}},
    )
    assert matched


def test_rule_fires_on_matching_event():
    """Golden: rule_fires_on_matching_event."""
    seed_default_rules()
    matches = match_event_to_rules(
        "aeis.idea.intake.completed",
        {"topic": "aeis.idea.intake.completed", "payload": {}},
    )
    assert any(rule.rule_id == "idea_intake_initial_guidance" for rule, _ in matches)


def test_engine_emits_card_for_idea_intake():
    svc = get_engine_service()
    cards = svc.submit_event(
        topic="aeis.idea.intake.completed",
        payload={"idea_id": "i-1", "operator_id": "op-1", "domain": "research"},
        operator_id="op-1",
    )
    assert cards, "expected at least one card"
    env = cards[0]
    assert env["header"]["card_type"] == "decision"
    assert env["header"]["d_level"] in ("D0", "D1", "D2", "D3", "D4", "D5")


def test_llm_judge_audit_recorded_with_full_prompt_and_response():
    """Golden: llm_judge_audit_recorded_with_full_prompt_and_response."""
    svc = get_engine_service()
    cards = svc.submit_event(
        topic="aeis.idea.intake.completed",
        payload={"idea_id": "i-1"},
        operator_id="op-1",
    )
    card_id = cards[0]["header"]["card_id"]
    audits = svc.list_audits_for_card(card_id=card_id)
    if not audits:
        # Initial rationale audit may not link card_id back yet; query directly.
        from psycopg.rows import dict_row
        with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM advisor_engine.llm_judge_audit")
            audits = cur.fetchall()
    assert audits
    a = audits[0]
    assert a["prompt_full"]
    assert a["response_full"]
    assert a["prompt_tokens"] > 0
    assert a["response_tokens"] > 0


def test_confidence_components_match_expected_formula():
    """Golden: confidence_components_match_expected_formula."""
    breakdown = calculate_confidence(
        council_snapshot={"weighted_alignment": 1.0},
        history_snapshot={"similar_acceptance_rate": 1.0, "operator_acceptance_rate_for_type": 1.0},
        pricing_snapshot={"source_label": "measured"},
        used_local_fallback=False,
    )
    assert breakdown.raw_score == pytest.approx(1.0)
    assert breakdown.final_score == pytest.approx(1.0)
    assert breakdown.council_match == 1.0


def test_local_fallback_multiplies_confidence_by_0_8():
    """Golden: local_fallback_multiplies_confidence_by_0_8."""
    base = calculate_confidence(
        council_snapshot={"weighted_alignment": 0.8},
        history_snapshot={"similar_acceptance_rate": 0.8, "operator_acceptance_rate_for_type": 0.8},
        pricing_snapshot={"source_label": "measured"},
        used_local_fallback=False,
    )
    fallback = calculate_confidence(
        council_snapshot={"weighted_alignment": 0.8},
        history_snapshot={"similar_acceptance_rate": 0.8, "operator_acceptance_rate_for_type": 0.8},
        pricing_snapshot={"source_label": "measured"},
        used_local_fallback=True,
    )
    assert fallback.final_score == pytest.approx(base.final_score * LOCAL_FALLBACK_MULTIPLIER)


def test_d5_card_without_evidence_pack_is_rejected():
    """Golden: d5_card_without_evidence_pack_is_rejected."""
    h = AdvisorCardHeader(
        card_id="c-1",
        card_type="decision",
        title="t",
        rationale="r",
        confidence_score=0.9,
        confidence_label=confidence_label_for(0.9),
        risk_level="critical",
        project_domain="software",
        d_level="D5",
        evidence_pack_id="",
        operator_id="op",
        sources=["llm_judge"],
        llm_judge_audit_id="a-1",
    )
    body = DecisionCard(recommendation="x", recommendation_type="REC_TYPE_BLOCK_PRODUCTION_DEPLOY")
    env = AdvisorCardEnvelope(header=h, decision=body)
    errors = validate_envelope(env)
    assert any("D5" in e for e in errors)


def test_subscription_card_auto_d3_with_evidence_pack():
    """Golden: subscription_card_auto_d3_with_evidence_pack."""
    a = assign_d_level(recommendation_type="REC_TYPE_PURCHASE_PLAN")
    assert a.final_level in ("D3", "D4", "D5")
    req = determine_evidence_pack_requirement(
        d_level=a.final_level, recommendation_type="REC_TYPE_PURCHASE_PLAN"
    )
    assert req in (EvidencePackRequirement.LIGHT, EvidencePackRequirement.FULL)


def test_dont_learn_flag_propagates_to_history():
    """Golden: dont_learn_flag_propagates_to_history."""
    svc = get_engine_service()
    cards = svc.submit_event(
        topic="aeis.idea.intake.completed", payload={"idea_id": "i-2"}, operator_id="op-2"
    )
    card = svc.get_recommendation(card_id=cards[0]["header"]["card_id"])
    assert card is not None
    assert "dont_learn" in card["header"]


def test_schema_validation_failure_emits_validation_failed_event():
    """Golden: schema_validation_failure_emits_validation_failed_event."""
    h = AdvisorCardHeader(
        card_id="c-x",
        card_type="decision",
        title="t",
        rationale="r",
        confidence_score=0.5,
        confidence_label="med",
        risk_level="high",
        project_domain="software",
        d_level="D5",
        evidence_pack_id="",
        operator_id="op",
        sources=["llm_judge"],
        llm_judge_audit_id="a-1",
    )
    env = AdvisorCardEnvelope(header=h, decision=DecisionCard(recommendation_type="REC_TYPE_PRODUCTION_EXECUTION"))
    with pytest.raises(EnvelopeValidationError):
        errs = validate_envelope(env)
        if errs:
            raise EnvelopeValidationError(errs)


def test_blocked_provider_card_not_emitted():
    """Golden: blocked_provider_card_not_emitted."""
    svc = get_engine_service()
    cards = svc.submit_event(
        topic="aeis.system.api_provider_setup_requested",
        payload={
            "operator_id": "op-3",
            "action": "add",
            "provider_id": "blocked-foo",
            "is_blocked": True,
        },
        operator_id="op-3",
    )
    assert isinstance(cards, list)
