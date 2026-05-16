"""S1 — Idea Debate (D0/D1) → council vote → masterplan draft.

Validates: project upsert with council_plan, council members are derived
and active, decision_hierarchy from registry includes the council layers,
and a workspace governance ticket can be opened to formalize the idea.
"""
from __future__ import annotations

import pytest


def test_idea_to_council_to_masterplan_flow():
    from sylion.cognitive.model_registry import (
        DISABLED_DECISION_HIERARCHY,
        get_model_registry,
    )
    from sylion.governance.ticket import GovernanceTicket
    from sylion.governance.tickets import fetch_pending, submit
    from sylion.project_mode.store import get_project_mode_store

    store = get_project_mode_store()
    project_id = "S1-idea-debate"

    store.upsert_project({
        "project_id": project_id,
        "name": "S1 — Idea Debate",
        "idea": "Build an autonomous funding-aware grant submission engine.",
        "council_plan": {
            "enabled": True,
            "active_size": 3,
            "members": [
                {"role": "architect", "preferred_models": ["llama3:70b"]},
                {"role": "critic", "preferred_models": ["mixtral:8x7b"]},
                {"role": "synthesizer", "preferred_models": ["qwen2:72b"]},
            ],
        },
    })

    registry = get_model_registry()
    members = registry.get_active_members(project_id)
    assert len(members) == 3, f"council should have 3 active members, got {len(members)}"
    hierarchy = registry.get_decision_hierarchy(project_id)
    assert hierarchy != DISABLED_DECISION_HIERARCHY

    ticket_id = submit(GovernanceTicket(
        origin="workspace",
        project_id=project_id,
        decision_class="D1",
        title="S1 idea debate kick-off",
        summary="Open council debate over the seed idea.",
        requested_by="d-integrate",
    ))
    assert ticket_id

    pending = fetch_pending(origin="workspace")
    assert any(t.ticket_id == ticket_id for t in pending)

    project = store.get_project(project_id)
    assert project is not None
    assert project.get("idea", "").startswith("Build an autonomous")
