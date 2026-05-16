"""Regression tests for the W14 E2 review-fix pass.

Each test pins a behavior surfaced by Codex / Kimi / gpt-oss so future
edits can't quietly regress it.
"""
from __future__ import annotations

import pytest

from sylion.aeis.testing.actions.charter_actions import (
    ApproveTestCharterHandler,
    ProposeTestCharterHandler,
)
from sylion.aeis.testing.actions.repair_actions import (
    ApprovePatchHandler,
    ProposePatchHandler,
)
from sylion.aeis.testing.actions.persona_actions import (
    _max_d_level,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    Finding,
    TestCharter,
)


@pytest.fixture
def store() -> OntologyStore:
    return OntologyStore()


@pytest.fixture
def stub_tickets():
    class StubTicketStore:
        def __init__(self) -> None:
            self.submitted: list[dict] = []

        def submit(self, ticket) -> str:
            # GovernanceTicket may be either a real dataclass or a generic
            # object; capture the relevant fields generically.
            self.submitted.append({
                "origin": getattr(ticket, "origin", ""),
                "decision_class": getattr(ticket, "decision_class", ""),
                "title": getattr(ticket, "title", ""),
                "payload": getattr(ticket, "payload", {}),
            })
            return f"tkt_{len(self.submitted):04d}"

    return StubTicketStore()


# ---------------------------------------------------------------------------
# Codex bug #2 — ApproveTestCharter must call _mirror_ticket()
# ---------------------------------------------------------------------------


def test_approve_charter_mirrors_to_ticket(store, stub_tickets):
    propose = ProposeTestCharterHandler(ontology=store, tickets=stub_tickets)
    create_payload = {
        "project_id": "proj_demo123def",
        "source_of_truth_version": "1",
        "masterplan_version": "1",
        "scope": {"x": 1},
        "required_test_classes": ["T2"],
    }
    propose.validate(create_payload)
    proposed = propose.execute(create_payload, intent_id="i_propose")

    approve = ApproveTestCharterHandler(ontology=store, tickets=stub_tickets)
    approve_payload = {
        "charter_id": proposed["charter_id"],
        "hg_ticket_id": "hg_x",
        "approver": "alice",
        "rationale": "all checks pass",
    }
    approve.validate(approve_payload)
    result = approve.execute(approve_payload, intent_id="i_approve")
    assert result["status"] == "approved"
    assert result["ticket_id"] is not None
    # Both propose and approve mirrored a ticket -> 2 entries.
    assert len(stub_tickets.submitted) == 2
    assert stub_tickets.submitted[1]["title"].startswith("Approve test charter ")


def test_approve_charter_rejects_when_status_not_proposed(store, stub_tickets):
    """Direct ontology mutation to 'approved' must not let approve_charter pass."""
    charter = TestCharter(
        project_id="proj_abc123def456",
        source_of_truth_version="1",
        masterplan_version="1",
        scope={"x": 1},
        required_test_classes=["T2"],
        required_personas=["operator_beginner"],
        required_evidence=["test_result"],
        release_blockers=["P0"],
        auto_repair_policy={},
        approval={"d_level": "D3"},
        status="draft",
    )
    store.create(charter)

    h = ApproveTestCharterHandler(ontology=store, tickets=stub_tickets)
    p = {
        "charter_id": charter.charter_id,
        "hg_ticket_id": "hg_x",
        "approver": "alice",
        "rationale": "ok",
    }
    h.validate(p)
    with pytest.raises(ValueError, match="proposed"):
        h.execute(p, intent_id="i")


# ---------------------------------------------------------------------------
# Codex bug #3 — ApprovePatch must call _mirror_ticket()
# ---------------------------------------------------------------------------


def test_approve_patch_mirrors_to_ticket(store, stub_tickets):
    finding = Finding(
        title="bug",
        description="d",
        discovered_by="evaluator",
    )
    store.create(finding)

    propose = ProposePatchHandler(ontology=store, tickets=stub_tickets)
    propose_payload = {
        "finding_id": finding.finding_id,
        "branch_id": "br_repair_xxx",
        "diff_text": "--- a\n+++ b\n@@\n+x",
        "files_touched": ["a.py"],
        "diff_lines_added": 1,
        "diff_lines_removed": 0,
        "tests_to_run": ["pytest"],
        "proposed_by": "claude",
    }
    propose.validate(propose_payload)
    pres = propose.execute(propose_payload, intent_id="i_propose")

    approve = ApprovePatchHandler(ontology=store, tickets=stub_tickets)
    approve_payload = {
        "proposal_id": pres["proposal_id"],
        "approver": "alice",
        "rationale": "looks good",
    }
    approve.validate(approve_payload)
    result = approve.execute(approve_payload, intent_id="i_approve")
    assert result["status"] == "approved"
    assert result["ticket_id"] is not None
    # propose + approve both mirrored.
    titles = [t["title"] for t in stub_tickets.submitted]
    assert any(t.startswith("Approve patch ") for t in titles)


# ---------------------------------------------------------------------------
# Kimi attack #1 — ProposePatch defensive branch_id check in execute()
# ---------------------------------------------------------------------------


def test_propose_patch_execute_rejects_main_even_without_validate(store):
    """Caller skips validate() and calls execute() directly with branch_id=main."""
    finding = Finding(
        title="bug", description="d", discovered_by="evaluator",
    )
    store.create(finding)
    h = ProposePatchHandler(ontology=store)
    bad_payload = {
        "finding_id": finding.finding_id,
        "branch_id": "main",
        "diff_text": "--- a\n+++ b\n@@\n+x",
        "files_touched": ["a.py"],
        "diff_lines_added": 1,
        "diff_lines_removed": 0,
        "tests_to_run": ["pytest"],
        "proposed_by": "claude",
    }
    # Bypass validate() — execute() must still refuse main.
    with pytest.raises(ValueError, match="main"):
        h.execute(bad_payload, intent_id="i")


# ---------------------------------------------------------------------------
# Kimi attack #4 — main normalization (case/whitespace/unicode)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", [
    "main", "MAIN", "Main", " main", "main ", "main\n", "MaIn",
])
def test_propose_patch_validate_rejects_main_variants(store, variant):
    h = ProposePatchHandler(ontology=store)
    payload = {
        "finding_id": "find_xxxxxxxxxxxxxxxx",
        "branch_id": variant,
        "diff_text": "x",
        "files_touched": ["a.py"],
        "diff_lines_added": 1,
        "diff_lines_removed": 0,
        "tests_to_run": ["pytest"],
        "proposed_by": "claude",
    }
    with pytest.raises(ValueError, match="main"):
        h.validate(payload)


# ---------------------------------------------------------------------------
# Codex bug #1 — InjectHumanError computes finding_d_level=max(...)
# ---------------------------------------------------------------------------


def test_inject_d_level_max_helper() -> None:
    assert _max_d_level("D1", "D5", "D3") == "D5"
    assert _max_d_level("D2") == "D2"
    assert _max_d_level("D0", "D0") == "D0"
    # Unknown values fall back to default D2 (defensive)
    assert _max_d_level("garbage") == "D2"


# ---------------------------------------------------------------------------
# Kimi attack #6 — waive_finding rationale must be non-empty
# ---------------------------------------------------------------------------


def test_waive_finding_rejects_blank_rationale(store) -> None:
    from sylion.aeis.testing.actions.finding_actions import WaiveFindingHandler

    h = WaiveFindingHandler(ontology=store)
    import time as _t
    p = {
        "finding_id": "find_xxxxxxxxxxxxxxxx",
        "hg_ticket_id": "hg_x",
        "rationale": "   ",  # only whitespace
        "expiry_at": _t.time() + 25 * 3600,
    }
    with pytest.raises(ValueError, match="rationale"):
        h.validate(p)


# ---------------------------------------------------------------------------
# Spec drift — every emit must carry trace_id matching intent_id
# ---------------------------------------------------------------------------


def test_propose_charter_emits_with_trace_id(store, stub_tickets):
    captured: list = []

    class SpyBus:
        def publish(self, event):
            captured.append(event)

    spy = SpyBus()
    h = ProposeTestCharterHandler(ontology=store, tickets=stub_tickets, event_bus=spy)
    payload = {
        "project_id": "proj_abc123def456",
        "source_of_truth_version": "1",
        "masterplan_version": "1",
        "scope": {"x": 1},
        "required_test_classes": ["T2"],
    }
    h.validate(payload)
    h.execute(payload, intent_id="trace_xyz")
    assert len(captured) >= 1
    for ev in captured:
        # SylionEvent has either .topic or .event_type and .payload
        topic = getattr(ev, "topic", None) or getattr(ev, "event_type", None)
        assert topic and topic.startswith("aeis.testing.")
        assert ev.payload.get("trace_id") == "trace_xyz", (
            f"event {topic} missing trace_id"
        )


# ---------------------------------------------------------------------------
# Codex bug #5 — CommandBus.register_handler now exposed and integrated
# ---------------------------------------------------------------------------


def test_command_bus_register_handler_and_lookup() -> None:
    from sylion.aeis.testing.actions import register_testing_actions
    from sylion.surface.command_bus import CommandBus

    bus = CommandBus()
    handlers = register_testing_actions(bus=bus, ontology=OntologyStore())
    assert len(handlers) >= 19
    # Every registered handler must be visible via lookup.
    for action_name, h in handlers.items():
        looked = bus.lookup_handler("testing", action_name)
        assert looked is h
    # list_handlers introspection works.
    listing = bus.list_handlers(target_module="testing")
    assert len(listing) == len(handlers)
    actions_seen = {row["target_action"] for row in listing}
    assert "propose_test_charter" in actions_seen
    assert "apply_patch_to_branch" in actions_seen


def test_command_bus_register_handler_rejects_duplicate() -> None:
    from sylion.aeis.testing.actions.charter_actions import (
        ProposeTestCharterHandler,
    )
    from sylion.surface.command_bus import CommandBus

    bus = CommandBus()
    h1 = ProposeTestCharterHandler(ontology=OntologyStore())
    h2 = ProposeTestCharterHandler(ontology=OntologyStore())
    bus.register_handler(h1)
    with pytest.raises(RuntimeError, match="duplicate"):
        bus.register_handler(h2)


def test_command_bus_register_handler_rejects_missing_methods() -> None:
    from sylion.surface.command_bus import CommandBus

    class BadHandler:
        target_action = "fake_action"
        # validate / execute missing

    bus = CommandBus()
    with pytest.raises(ValueError, match="validate"):
        bus.register_handler(BadHandler())
