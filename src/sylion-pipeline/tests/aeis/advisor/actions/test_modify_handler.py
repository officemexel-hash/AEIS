from __future__ import annotations

import json

import pytest

from sylion.aeis.advisor.actions._models import ActionContext, CardAction
from sylion.aeis.advisor.actions.handlers.modify_handler import ModifyHandler
from sylion.aeis.advisor.engine import _db as engine_db
from sylion.aeis.advisor.engine._db import fetch_recommendation_by_id, insert_recommendation, reset_engine_db
from sylion.aeis.advisor.engine._models import AdvisorCardEnvelope, AdvisorCardHeader, DecisionCard


@pytest.fixture()
def sqlite_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_db, "_use_sqlite_store", lambda: True)
    monkeypatch.setattr(engine_db, "_sqlite_db_path", lambda: str(tmp_path / "advisor_engine.db"))
    if engine_db._sqlite_conn is not None:
        engine_db._sqlite_conn.close()
    engine_db._sqlite_conn = None
    reset_engine_db()
    yield
    reset_engine_db()
    if engine_db._sqlite_conn is not None:
        engine_db._sqlite_conn.close()
    engine_db._sqlite_conn = None


def _seed_decision_card(card_id: str = "card-mod") -> None:
    insert_recommendation(
        AdvisorCardEnvelope(
            header=AdvisorCardHeader(
                card_id=card_id,
                card_type="decision",
                title="Karta testowa",
                rationale="stara rekomendacja widoczna w rationale",
                confidence_score=0.8,
                confidence_label="high",
                sources=["rule_engine"],
                risk_level="low",
                project_domain="software",
                project_type="audit",
                d_level="D1",
                operator_id="op-1",
            ),
            decision=DecisionCard(
                recommendation="stara rekomendacja w body",
                expected_benefit="test",
                expected_downside="test",
                quality_impact="test",
                recommendation_type="test_modify",
            ),
        )
    )


def test_modify_updates_rendered_card_content(sqlite_engine):
    _seed_decision_card()
    new_text = "nowa rekomendacja operatora widoczna po odswiezeniu dashboardu"

    result = ModifyHandler().handle(
        ActionContext(
            card_id="card-mod",
            action=CardAction.MODIFY,
            operator_id="op-1",
            modified_recommendation=new_text,
        )
    )

    assert result.success is True
    row = fetch_recommendation_by_id("card-mod")
    assert row is not None
    assert row["rationale"] == new_text
    body = json.loads(row["body_jsonb"])
    tags = json.loads(row["tags"])
    assert body["recommendation"] == new_text
    assert body["modified_recommendation"] == new_text
    assert body["operator_modified_recommendation"] == new_text
    assert body["original_recommendation"] == "stara rekomendacja w body"
    assert body["modified_by_operator"] is True
    assert "modified_by_operator" in tags


def test_modify_missing_card_fails(sqlite_engine):
    result = ModifyHandler().handle(
        ActionContext(
            card_id="missing-card",
            action=CardAction.MODIFY,
            operator_id="op-1",
            modified_recommendation="nowa rekomendacja",
        )
    )

    assert result.success is False
    assert result.error_message == "card_not_found"
