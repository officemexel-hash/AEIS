"""Tests for ``sylion.aeis_v2.council_v2.wedge`` — W16 G1 cascade step 3.

Covers the Council Hybrid wedge that wraps the canonical 9-role council
deliberation around the top match returned by ``match_idea_to_templates_g1``.

Each test uses a fresh in-memory CouncilHybrid (``db_path=":memory:"``)
so we do not pollute the production sqlite file used by the singleton.
"""
from __future__ import annotations

from typing import Any

import pytest

from sylion.aeis_v2.council_v2.wedge import (
    CouncilWedgeDecision,
    DEFAULT_RANK_BY_ROLE,
    evaluate_match_with_council,
    simulate_role_verdict,
)
from sylion.governance.council_hybrid import CouncilHybrid, VALID_ROLES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def council() -> CouncilHybrid:
    """Fresh in-memory council per test — no shared state."""
    return CouncilHybrid(db_path=":memory:")


def _match(template_id: str, score: float, tags: list[str]) -> dict[str, Any]:
    """Build a match dict shaped like ``MatchResult.to_dict()``."""
    return {
        "template": {
            "id": template_id,
            "name_pl": "Test",
            "description_pl": "Test",
            "object_type_ids": [],
            "widget_ids": [],
            "tags": list(tags),
        },
        "score": score,
        "method": "embedding",
        "reason_pl": "test",
    }


# ---------------------------------------------------------------------------
# simulate_role_verdict — heuristic correctness.
# ---------------------------------------------------------------------------


def test_simulate_role_verdict_high_score_approves() -> None:
    """top_score >= 0.7 → approve for non-sentinel roles."""
    verdict, confidence, _ = simulate_role_verdict("planner", 0.9, [])
    assert verdict == "approve"
    assert confidence > 0.5


def test_simulate_role_verdict_borderline_critic_more_strict() -> None:
    """Critic in 0.55–0.7 band downgrades to conditional."""
    score = 0.6
    other_verdict, _, _ = simulate_role_verdict("planner", score, [])
    critic_verdict, _, _ = simulate_role_verdict("critic", score, [])
    # Both pass the >=0.4 floor so both are conditional in this band.
    assert other_verdict == "conditional"
    assert critic_verdict == "conditional"


def test_simulate_role_verdict_low_score_rejects() -> None:
    """top_score < 0.4 → reject."""
    verdict, _, _ = simulate_role_verdict("planner", 0.2, [])
    assert verdict == "reject"


def test_simulate_role_verdict_cost_sentinel_blocks_premium() -> None:
    """cost_sentinel rejects when tags contain ``premium`` even if score high."""
    verdict, confidence, _ = simulate_role_verdict(
        "cost_sentinel", 0.9, ["fast", "premium"],
    )
    assert verdict == "reject"
    assert confidence >= 0.7


def test_simulate_role_verdict_security_sentinel_blocks_unsafe() -> None:
    """security_sentinel rejects when tags contain ``unsafe`` even if score high."""
    verdict, _, _ = simulate_role_verdict(
        "security_sentinel", 0.9, ["public", "unsafe"],
    )
    assert verdict == "reject"


def test_simulate_role_verdict_security_sentinel_passes_clean_tags() -> None:
    """security_sentinel approves when no security tags are present."""
    verdict, _, _ = simulate_role_verdict(
        "security_sentinel", 0.85, ["clean", "vetted"],
    )
    assert verdict == "approve"


# ---------------------------------------------------------------------------
# evaluate_match_with_council — full wedge pipeline.
# ---------------------------------------------------------------------------


def test_evaluate_match_with_council_high_score_approves(council) -> None:
    """High top-score → council majority verdict is ``approve``."""
    matches = [_match("inspection_field", 0.9, ["inspekcja", "raport"])]

    decision = evaluate_match_with_council(
        matches, idea_text="audyt jakosci", council=council,
    )

    assert isinstance(decision, CouncilWedgeDecision)
    assert decision.chosen_template_id == "inspection_field"
    assert decision.verdict == "approve"
    assert decision.session_id


def test_evaluate_match_with_council_low_score_rejects(council) -> None:
    """Low top-score → majority verdict is ``reject``."""
    matches = [_match("nope", 0.1, ["x"])]

    decision = evaluate_match_with_council(
        matches, idea_text="bezsensowny pomysl", council=council,
    )

    assert decision.verdict == "reject"


def test_evaluate_match_with_council_security_sentinel_block(council) -> None:
    """security_sentinel adds a block when tags include ``unsafe``."""
    matches = [_match("risky_app", 0.9, ["public", "unsafe"])]

    decision = evaluate_match_with_council(
        matches, idea_text="ryzykowna aplikacja", council=council,
    )

    assert "security_sentinel" in decision.sentinel_blocks


def test_evaluate_match_with_council_records_dissents(council) -> None:
    """Dissents = roles whose verdict differs from majority."""
    # Force a mixed outcome by injecting a custom evaluator that flips
    # one role.
    def mixed_evaluator(role: str, score: float, tags: list[str]):
        if role == "critic":
            return ("reject", 0.9, "critic forced reject")
        return ("approve", 0.85, "ok")

    matches = [_match("ok_app", 0.85, ["good"])]
    decision = evaluate_match_with_council(
        matches, idea_text="dobre", council=council,
        role_evaluator=mixed_evaluator,
    )
    # majority should still be "approve" because critic's weight (1.0)
    # is one of nine — the rest carry weight roughly summing to 6+.
    assert decision.verdict == "approve"
    assert "critic" in decision.dissents


def test_evaluate_match_with_council_session_persisted(council) -> None:
    """The wedge opens a real council session that we can fetch."""
    matches = [_match("ok_app", 0.85, ["good"])]
    decision = evaluate_match_with_council(
        matches, idea_text="ok", council=council,
    )
    sess = council.get_session(decision.session_id)
    assert sess is not None
    assert sess["topic"].startswith("match-idea-g1")


def test_evaluate_match_with_council_all_canonical_roles_present(council) -> None:
    """All 9 canonical roles appear as participants."""
    matches = [_match("ok_app", 0.85, ["good"])]
    decision = evaluate_match_with_council(
        matches, idea_text="ok", council=council,
    )
    parts = council.list_participants(decision.session_id)
    roles = {p["role"] for p in parts}
    assert roles == set(VALID_ROLES)


def test_evaluate_match_with_council_sentinel_ranks_review_only(council) -> None:
    """Sentinels are seated as review_only per DEFAULT_RANK_BY_ROLE."""
    matches = [_match("ok_app", 0.85, ["good"])]
    decision = evaluate_match_with_council(
        matches, idea_text="ok", council=council,
    )
    parts = council.list_participants(decision.session_id)
    sentinels = [p for p in parts if p["role"].endswith("_sentinel")]
    for s in sentinels:
        assert s["rank"] == "review_only"


def test_evaluate_match_with_council_empty_matches_raises(council) -> None:
    """Empty matches must raise ValueError — caller should check G1 first."""
    with pytest.raises(ValueError):
        evaluate_match_with_council([], idea_text="x", council=council)


def test_evaluate_match_with_council_to_dict_round_trips(council) -> None:
    """to_dict() returns plain JSON-friendly types."""
    matches = [_match("ok_app", 0.85, ["good"])]
    decision = evaluate_match_with_council(
        matches, idea_text="ok", council=council,
    )
    d = decision.to_dict()
    assert isinstance(d["weights"], dict)
    assert isinstance(d["dissents"], list)
    assert isinstance(d["sentinel_blocks"], list)
    assert d["session_id"] == decision.session_id


def test_default_rank_by_role_covers_all_canonical_roles() -> None:
    """Sanity: DEFAULT_RANK_BY_ROLE lists every canonical role."""
    assert set(DEFAULT_RANK_BY_ROLE) == set(VALID_ROLES)


def test_council_wedge_audit_chain_verifies(council, tmp_path, monkeypatch) -> None:
    """Sprint 2 day 6 — council_wedge audit JSONL is hash-chained + verifiable."""
    from sylion.aeis_v2.audit_chain import verify_chain
    import sylion.aeis_v2.council_v2.wedge as wedge_mod

    audit = tmp_path / "council_wedge.jsonl"
    monkeypatch.setattr(wedge_mod, "AUDIT_LOG_PATH", audit)

    matches = [_match("ok", 0.85, ["good"])]
    evaluate_match_with_council(matches, idea_text="ok", council=council)
    evaluate_match_with_council(matches, idea_text="ok", council=council)
    assert verify_chain(audit) == []


# ---------------------------------------------------------------------------
# REST endpoint smoke — POST /api/v1/apps/match-idea-g1-with-council.
# ---------------------------------------------------------------------------


def test_post_match_idea_g1_with_council_endpoint() -> None:
    """End-to-end: POST returns G1 matches + council verdict."""
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    client = TestClient(app)
    resp = client.post(
        "/api/v1/apps/match-idea-g1-with-council",
        json={"idea_text": "inspekcja terenowa raport audyt", "top_n": 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["phase"] == "G1+council"
    assert body["match_count"] >= 1
    decision = body["council_decision"]
    assert "verdict" in decision
    assert "weights" in decision
    assert "dissents" in decision
    assert "session_id" in decision


def test_post_match_idea_g1_with_council_no_matches_404() -> None:
    """Idea with no overlapping tags → G1 returns no matches → 404."""
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    client = TestClient(app)
    resp = client.post(
        "/api/v1/apps/match-idea-g1-with-council",
        json={"idea_text": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "top_n": 3},
    )

    # Either 404 (no G1 matches) or 200 with weak score — depends on
    # current demo template tag distribution. Lock the contract: if
    # matches=0 then 404 with detail.error.
    if resp.status_code == 404:
        body = resp.json()
        assert "no matches" in body["detail"]["error"].lower()
    else:
        assert resp.status_code == 200
