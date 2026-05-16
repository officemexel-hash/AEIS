"""Wave A2 -- GovernanceAuditChain mechanics.

Verifies the unified hash chain backing TicketStore lifecycle:
  - submit/resolve/withdraw/escalate each append exactly one entry
  - sequence numbers are monotonic
  - chain integrity holds (verify_chain returns valid)
  - tampering with the underlying spine_entries table flips the verdict
  - entries_for(ticket_id) returns all events for that ticket
  - workspace + global tickets share the same chain (no per-origin shards)
"""

from __future__ import annotations

import pytest

from sylion.governance.audit_chain import (
    GovernanceAuditChain,
    PROJECT_EVENT_TYPES,
    TICKET_EVENT_TYPES,
    WORKSPACE_EVENT_TYPES,
    get_audit_chain,
    reset_audit_chain,
)
from sylion.governance.evidence_spine import GENESIS_PREV_HASH, get_governance_spine
from sylion.governance.ticket import (
    GovernanceTicket,
    get_ticket_store,
    reset_ticket_store,
)


@pytest.fixture(autouse=True)
def _reset():
    # Order matters: chain first (ticket_store calls into chain on submit).
    reset_audit_chain(":memory:")
    reset_ticket_store(":memory:")
    yield
    reset_audit_chain(":memory:")
    reset_ticket_store(":memory:")


def _ticket(origin: str, **overrides) -> GovernanceTicket:
    base = dict(
        origin=origin,
        decision_class="D2",
        gate_type="blocking",
        priority="P2",
        title=f"{origin} ticket",
        summary=f"summary {origin}",
        requested_by=f"{origin}_actor",
        payload={"src": origin},
    )
    base.update(overrides)
    return GovernanceTicket(**base)


class TestEventTypeWhitelists:

    def test_ticket_event_types_locked(self):
        assert TICKET_EVENT_TYPES == frozenset({
            "submitted", "resolved", "withdrawn", "escalated", "audit_attached",
        })

    def test_workspace_event_types_locked(self):
        assert "launch" in WORKSPACE_EVENT_TYPES
        assert "approve_masterplan" in WORKSPACE_EVENT_TYPES
        assert "freeze_canon" in WORKSPACE_EVENT_TYPES

    def test_project_event_types_locked(self):
        assert "create" in PROJECT_EVENT_TYPES
        assert "transition" in PROJECT_EVENT_TYPES

    def test_invalid_ticket_event_type_rejected(self):
        chain = get_audit_chain()
        with pytest.raises(ValueError, match="invalid ticket event_type"):
            chain.append_ticket_event("tid", "bogus")

    def test_invalid_workspace_event_type_rejected(self):
        chain = get_audit_chain()
        with pytest.raises(ValueError, match="invalid workspace event_type"):
            chain.append_workspace_event("ws", "bogus")

    def test_invalid_project_event_type_rejected(self):
        chain = get_audit_chain()
        with pytest.raises(ValueError, match="invalid project event_type"):
            chain.append_project_event("pid", "bogus")


class TestAppendReturnsEntryId:

    def test_ticket_event_returns_entry_id(self):
        chain = get_audit_chain()
        entry_id = chain.append_ticket_event("tid_1", "submitted", actor="alice")
        assert isinstance(entry_id, str) and len(entry_id) > 0

    def test_workspace_event_returns_entry_id(self):
        chain = get_audit_chain()
        entry_id = chain.append_workspace_event(
            "ws_1", "launch", actor="op", project_id="proj_1",
        )
        assert isinstance(entry_id, str) and len(entry_id) > 0

    def test_entry_retrievable_by_id(self):
        chain = get_audit_chain()
        entry_id = chain.append_ticket_event("tid_2", "submitted")
        entry = chain.get_entry(entry_id)
        assert entry is not None
        assert entry["entry_id"] == entry_id


class TestSubmitAppendsToChain:

    def test_submit_creates_chain_entry(self):
        store = get_ticket_store()
        tid = store.submit(_ticket("global", title="t1"))
        ticket = store.get(tid)
        assert ticket.audit_chain_ref is not None

    def test_chain_ref_points_to_real_entry(self):
        store = get_ticket_store()
        tid = store.submit(_ticket("global"))
        ticket = store.get(tid)
        chain = get_audit_chain()
        entry = chain.get_entry(ticket.audit_chain_ref)
        assert entry is not None
        assert entry["decision_id"] == tid

    def test_first_chain_entry_links_to_genesis(self):
        store = get_ticket_store()
        tid = store.submit(_ticket("global"))
        ticket = store.get(tid)
        chain = get_audit_chain()
        entry = chain.get_entry(ticket.audit_chain_ref)
        assert entry["prev_hash"] == GENESIS_PREV_HASH
        assert entry["sequence_num"] == 1


class TestLifecycleAppendsToChain:

    def test_resolve_appends_second_entry(self):
        store = get_ticket_store()
        tid = store.submit(_ticket("global"))
        store.resolve(tid, "approved", reviewer="alice", reason="LGTM")
        chain = get_audit_chain()
        entries = chain.entries_for(tid)
        assert len(entries) == 2
        types = [e["metadata"]["event_type"] for e in entries]
        assert types == ["submitted", "resolved"]

    def test_withdraw_appends_entry(self):
        store = get_ticket_store()
        tid = store.submit(_ticket("global"))
        store.withdraw(tid, reason="abandoned", actor="bob")
        entries = get_audit_chain().entries_for(tid)
        assert [e["metadata"]["event_type"] for e in entries] == [
            "submitted", "withdrawn",
        ]

    def test_escalate_appends_entry(self):
        store = get_ticket_store()
        tid = store.submit(_ticket("global"))
        store.escalate(tid, reason="SLA breach", actor="oncall")
        entries = get_audit_chain().entries_for(tid)
        assert [e["metadata"]["event_type"] for e in entries] == [
            "submitted", "escalated",
        ]

    def test_resolve_then_withdraw_blocked_no_extra_entry(self):
        # Once resolved, withdraw is a no-op -> no third entry.
        store = get_ticket_store()
        tid = store.submit(_ticket("global"))
        store.resolve(tid, "approved", reviewer="alice")
        store.withdraw(tid, reason="too late", actor="bob")
        entries = get_audit_chain().entries_for(tid)
        assert len(entries) == 2


class TestMonotonicSequence:

    def test_sequence_numbers_strictly_increase(self):
        store = get_ticket_store()
        store.submit(_ticket("global", title="g1"))
        store.submit(_ticket("workspace", title="w1"))
        store.submit(_ticket("funding", title="f1"))
        chain = get_audit_chain()
        all_entries = chain.all_entries()
        seqs = [e["sequence_num"] for e in all_entries]
        assert seqs == sorted(seqs)
        assert seqs == list(range(1, len(seqs) + 1))


class TestChainIntegrity:

    def test_empty_chain_valid(self):
        chain = get_audit_chain()
        result = chain.verify()
        assert result["valid"] is True
        assert result["total_entries"] == 0

    def test_clean_chain_valid_after_many_events(self):
        store = get_ticket_store()
        ids = [store.submit(_ticket("global", title=f"t{i}")) for i in range(5)]
        for tid in ids[:3]:
            store.resolve(tid, "approved", reviewer="alice")
        store.withdraw(ids[3], actor="bob")
        store.escalate(ids[4], reason="unclear", actor="oncall")

        chain = get_audit_chain()
        result = chain.verify()
        assert result["valid"] is True
        assert result["total_entries"] == 5 + 3 + 1 + 1  # 5 submit + 3 resolve + 1 wd + 1 esc

    def test_tampered_content_breaks_chain(self):
        store = get_ticket_store()
        store.submit(_ticket("global"))
        store.submit(_ticket("workspace"))

        # Tamper with the underlying spine: rewrite an entry's content_hash.
        spine = get_governance_spine()
        spine._conn.execute(
            "UPDATE spine_entries SET content_hash = 'ffff' WHERE sequence_num = 1"
        )
        spine._conn.commit()

        result = get_audit_chain().verify()
        assert result["valid"] is False
        assert result["broken_at"] is not None


class TestUnifiedAcrossOrigins:

    def test_six_origins_share_one_chain(self):
        store = get_ticket_store()
        ids = []
        for origin in ("workspace", "global", "funding", "mobile", "skill", "council"):
            ids.append(store.submit(_ticket(origin)))

        chain = get_audit_chain()
        all_entries = chain.all_entries()
        assert len(all_entries) == 6

        # All entries trace back to genesis -> linked chain, not 6 shards.
        seqs = [e["sequence_num"] for e in all_entries]
        assert seqs == [1, 2, 3, 4, 5, 6]

    def test_workspace_and_global_share_chain(self):
        store = get_ticket_store()
        ws_id = store.submit(_ticket("workspace", title="ws_decision"))
        global_id = store.submit(_ticket("global", title="global_decision"))

        chain = get_audit_chain()
        all_entries = chain.all_entries()

        decision_ids = {e["decision_id"] for e in all_entries}
        assert ws_id in decision_ids
        assert global_id in decision_ids
        # Verify chain is linked: second entry's prev_hash == first's entry_hash.
        assert all_entries[1]["prev_hash"] == all_entries[0]["entry_hash"]


class TestEntriesForFilter:

    def test_entries_for_returns_only_matching_decision(self):
        store = get_ticket_store()
        a = store.submit(_ticket("global", title="A"))
        b = store.submit(_ticket("global", title="B"))
        store.resolve(a, "approved", reviewer="r")

        chain = get_audit_chain()
        entries_a = chain.entries_for(a)
        entries_b = chain.entries_for(b)
        assert len(entries_a) == 2
        assert len(entries_b) == 1
        assert all(e["decision_id"] == a for e in entries_a)
        assert all(e["decision_id"] == b for e in entries_b)


class TestStats:

    def test_stats_count_matches_appends(self):
        store = get_ticket_store()
        for i in range(3):
            store.submit(_ticket("global", title=f"t{i}"))
        s = get_audit_chain().stats()
        assert s["total_entries"] == 3
        assert s["chain_valid"] is True
        assert s["last_sequence"] == 3


class TestSingletonReset:

    def test_reset_audit_chain_returns_fresh_instance(self):
        first = get_audit_chain()
        first.append_ticket_event("tid_x", "submitted")
        assert first.stats()["total_entries"] == 1

        reset_audit_chain(":memory:")
        second = get_audit_chain()
        assert second is not first
        # Fresh chain -> 0 entries.
        assert second.stats()["total_entries"] == 0

    def test_get_audit_chain_returns_singleton(self):
        a = get_audit_chain()
        b = get_audit_chain()
        assert a is b


class TestWorkspaceProjectAppends:

    def test_workspace_event_round_trips(self):
        chain = get_audit_chain()
        eid = chain.append_workspace_event(
            "ws_1", "approve_masterplan",
            actor="reviewer", project_id="proj_42",
            payload={"masterplan_version": "v3"},
        )
        entry = chain.get_entry(eid)
        assert entry["metadata"]["surface"] == "workspace"
        assert entry["metadata"]["project_id"] == "proj_42"
        assert entry["evidence_pack"]["payload"]["masterplan_version"] == "v3"

    def test_project_event_round_trips(self):
        chain = get_audit_chain()
        eid = chain.append_project_event(
            "proj_99", "transition",
            actor="system", payload={"from": "draft", "to": "active"},
        )
        entry = chain.get_entry(eid)
        assert entry["metadata"]["surface"] == "project"
        assert entry["evidence_pack"]["payload"]["to"] == "active"
