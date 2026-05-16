"""Wave A2 -- Workspace and global governance share ONE audit chain.

DoD criterion for Wave A2:
  Workspace decision (project launch, masterplan approval) and global
  governance decision (D3+ ticket resolution) MUST land in the same
  hash-chained audit log -- not separate shards.

This test validates the cross-surface guarantee end-to-end:
  1. workspace.launch -> chain entry
  2. global ticket submitted -> chain entry (linked via prev_hash)
  3. workspace.approve_masterplan -> chain entry (linked)
  4. global ticket resolved -> chain entry (linked)
  5. verify_chain() -> valid, with all 4 entries in one ordered chain
"""

from __future__ import annotations

import pytest

from sylion.governance.audit_chain import (
    get_audit_chain,
    reset_audit_chain,
)
from sylion.governance.evidence_spine import GENESIS_PREV_HASH
from sylion.governance.ticket import (
    GovernanceTicket,
    get_ticket_store,
    reset_ticket_store,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_audit_chain(":memory:")
    reset_ticket_store(":memory:")
    yield
    reset_audit_chain(":memory:")
    reset_ticket_store(":memory:")


def _ticket(origin: str, **overrides) -> GovernanceTicket:
    base = dict(
        origin=origin,
        decision_class="D3",
        gate_type="blocking",
        priority="P1",
        title=f"{origin} title",
        summary=f"summary {origin}",
        requested_by=f"{origin}_actor",
    )
    base.update(overrides)
    return GovernanceTicket(**base)


class TestUnifiedChainAcrossSurfaces:

    def test_workspace_then_global_form_linked_chain(self):
        chain = get_audit_chain()
        store = get_ticket_store()

        # 1. Workspace launches a project (workspace surface event).
        ws_entry_1 = chain.append_workspace_event(
            "ws_alpha", "launch",
            actor="founder", project_id="proj_alpha",
            payload={"plan": "MVP"},
        )

        # 2. Global ticket submitted via TicketStore.
        global_tid = store.submit(_ticket("global", title="release toggle"))

        # 3. Workspace approves the masterplan.
        ws_entry_2 = chain.append_workspace_event(
            "ws_alpha", "approve_masterplan",
            actor="reviewer", project_id="proj_alpha",
            payload={"version": "v1"},
        )

        # 4. Global ticket resolved.
        store.resolve(global_tid, "approved", reviewer="ops", reason="LGTM")

        # All four events are in the same chain.
        all_entries = chain.all_entries()
        assert len(all_entries) == 4

        # Sequence: 1, 2, 3, 4 — chain is linear.
        seqs = [e["sequence_num"] for e in all_entries]
        assert seqs == [1, 2, 3, 4]

        # Hash linkage: entry N+1.prev_hash == entry N.entry_hash.
        assert all_entries[0]["prev_hash"] == GENESIS_PREV_HASH
        for i in range(1, len(all_entries)):
            assert all_entries[i]["prev_hash"] == all_entries[i - 1]["entry_hash"]

        # Verify integrity end-to-end.
        result = chain.verify()
        assert result["valid"] is True
        assert result["total_entries"] == 4

    def test_six_origins_plus_workspace_in_one_chain(self):
        chain = get_audit_chain()
        store = get_ticket_store()

        # One ticket per origin.
        ticket_ids = []
        for origin in ("workspace", "global", "funding", "mobile", "skill", "council"):
            ticket_ids.append(store.submit(_ticket(origin)))

        # Workspace event interleaved.
        ws_event_id = chain.append_workspace_event(
            "ws_main", "freeze_canon",
            actor="curator", project_id="proj_main",
        )

        # All 7 events in one chain.
        all_entries = chain.all_entries()
        assert len(all_entries) == 7

        # Verify the chain is intact.
        result = chain.verify()
        assert result["valid"] is True

        # Workspace entry coexists with origin tickets (no shards).
        decision_ids = {e["decision_id"] for e in all_entries}
        for tid in ticket_ids:
            assert tid in decision_ids
        assert "ws_main" in decision_ids

    def test_chain_entry_records_origin_metadata(self):
        # Workspace events labeled surface=workspace; ticket events surface=ticket.
        chain = get_audit_chain()
        store = get_ticket_store()

        store.submit(_ticket("global", title="g"))
        chain.append_workspace_event(
            "ws_x", "launch", actor="a", project_id="p_x",
        )

        all_entries = chain.all_entries()
        surfaces = [e["metadata"]["surface"] for e in all_entries]
        assert surfaces == ["ticket", "workspace"]


class TestAuditChainRefAttachment:

    def test_ticket_audit_chain_ref_resolves_to_workspace_chain_entry(self):
        # The ticket's audit_chain_ref must point at an entry in the SAME chain
        # that workspace events get appended to. Not a separate per-origin chain.
        chain = get_audit_chain()
        store = get_ticket_store()

        chain.append_workspace_event(
            "ws_first", "launch", actor="founder", project_id="proj_first",
        )
        tid = store.submit(_ticket("global", title="t"))

        ticket = store.get(tid)
        ref = ticket.audit_chain_ref
        assert ref is not None

        entry = chain.get_entry(ref)
        assert entry is not None
        # That entry sits at sequence 2 (workspace was sequence 1).
        assert entry["sequence_num"] == 2

    def test_audit_chain_ref_persists_after_resolve(self):
        # audit_chain_ref points at the FIRST chain entry for the ticket
        # (the "submitted" one). Resolving the ticket adds a NEW chain entry
        # but does not change the ticket's audit_chain_ref pointer.
        store = get_ticket_store()
        tid = store.submit(_ticket("global", title="t"))
        before = store.get(tid).audit_chain_ref

        store.resolve(tid, "approved", reviewer="alice")
        after = store.get(tid).audit_chain_ref
        assert after == before

        # But the chain has 2 entries for this ticket now.
        events = get_audit_chain().entries_for(tid)
        assert len(events) == 2


class TestVerifyEndToEndAfterMixedActivity:

    def test_chain_remains_valid_after_mixed_workspace_and_global_activity(self):
        chain = get_audit_chain()
        store = get_ticket_store()

        # Simulate a busy day: 10 mixed events.
        chain.append_workspace_event("ws1", "launch", project_id="p1")
        t1 = store.submit(_ticket("global", title="g1"))
        t2 = store.submit(_ticket("workspace", title="w1"))
        chain.append_workspace_event("ws1", "approve_masterplan", project_id="p1")
        store.resolve(t1, "approved", reviewer="a")
        chain.append_workspace_event("ws2", "launch", project_id="p2")
        t3 = store.submit(_ticket("funding", title="f1"))
        store.withdraw(t2, actor="alice")
        chain.append_workspace_event("ws2", "freeze_canon", project_id="p2")
        store.escalate(t3, reason="risk", actor="oncall")

        result = chain.verify()
        assert result["valid"] is True
        assert result["total_entries"] == 10
