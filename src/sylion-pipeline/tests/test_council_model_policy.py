from __future__ import annotations

import json

from sylion.cognitive.model_registry import get_model_registry, reset_model_registry
from sylion.governance.council_workflow import (
    CouncilSession,
    Vote,
    VoteValue,
    get_council_workflow,
)
from sylion.governance.human_gate import reset_human_gate
from sylion.governance.ticket import reset_ticket_store
from sylion.monitoring.model_budget import reset_model_budget


def _reset_runtime(db_path):
    reset_ticket_store(db_path=db_path)
    reset_human_gate(db_path=db_path)
    reset_model_registry(db_path=db_path)
    reset_model_budget()
    import sylion.governance.council_workflow as workflow

    workflow._council = None
    return get_council_workflow(db_path=db_path)


def test_unregistered_manual_council_vote_still_works(tmp_path):
    council = _reset_runtime(tmp_path / "manual-vote.sqlite")
    opened = council.open_session(CouncilSession(proposal_id="p-manual", title="Manual vote"))

    result = council.cast_vote(
        Vote(
            session_id=opened["session_id"],
            member_id="human-architect",
            value=VoteValue.APPROVE,
            rationale="Manual operator vote",
        )
    )

    assert result["cast"] is True
    assert result["policy"]["registered"] is False


def test_registered_read_only_model_cannot_cast_council_vote(tmp_path):
    council = _reset_runtime(tmp_path / "blocked-model-vote.sqlite")
    registry = get_model_registry()
    registry.register_model(
        model_id="readonly-council-model",
        provider="openai",
        display_name="Read only council model",
        config_json=json.dumps({
            "access_level": "read_only",
            "approval_policy": "always_human_gate",
        }),
    )
    opened = council.open_session(CouncilSession(proposal_id="p-block", title="Blocked vote"))

    result = council.cast_vote(
        Vote(
            session_id=opened["session_id"],
            member_id="readonly-council-model",
            value=VoteValue.APPROVE,
            rationale="Should not be accepted",
        )
    )

    assert result["cast"] is False
    assert "read_only" in result["message"]
    assert result["policy"]["human_gate_request"]["gate_id"] == "ai_model_runtime_policy"
    assert council.tally(opened["session_id"])["total"] == 0
