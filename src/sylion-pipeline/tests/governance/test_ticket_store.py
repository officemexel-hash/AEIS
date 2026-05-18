"""Wave A1 -- TicketStore CRUD tests.

Covers: submit, fetch_by_id, fetch_pending, resolve, withdraw, escalate,
stats, events, validation, idempotency.
"""

from __future__ import annotations

import pytest

from sylion.governance.ticket import (
    GovernanceTicket,
    TicketStore,
    VALID_DECISION_CLASSES,
    VALID_GATE_TYPES,
    VALID_ORIGINS,
    VALID_PRIORITIES,
    reset_ticket_store,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_ticket_store()
    yield
    reset_ticket_store()


@pytest.fixture
def store():
    return TicketStore(db_path=":memory:")


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------

class TestSubmit:

    def test_submit_returns_ticket_id(self, store):
        t = GovernanceTicket(origin="global", title="t1")
        tid = store.submit(t)
        assert tid == t.ticket_id
        assert isinstance(tid, str) and len(tid) >= 8

    def test_submit_persists_ticket(self, store):
        t = GovernanceTicket(origin="workspace", title="x")
        tid = store.submit(t)
        fetched = store.get(tid)
        assert fetched is not None
        assert fetched.title == "x"
        assert fetched.origin == "workspace"

    def test_submit_idempotent(self, store):
        t = GovernanceTicket(origin="global", title="dup")
        tid1 = store.submit(t)
        tid2 = store.submit(t)
        assert tid1 == tid2
        assert len(store.list()) == 1

    def test_submit_default_state_pending(self, store):
        t = GovernanceTicket(origin="skill", title="s")
        store.submit(t)
        assert store.get(t.ticket_id).state == "pending"

    def test_submit_records_created_event(self, store):
        t = GovernanceTicket(origin="funding", title="f")
        store.submit(t)
        events = store.events(t.ticket_id)
        assert len(events) == 1
        assert events[0]["event_type"] == "created"

    def test_submit_invalid_origin_raises(self, store):
        with pytest.raises(ValueError):
            store.submit(GovernanceTicket(origin="bogus", title="x"))

    def test_submit_invalid_decision_class_raises(self, store):
        with pytest.raises(ValueError):
            store.submit(GovernanceTicket(decision_class="D9", title="x"))

    def test_submit_invalid_priority_raises(self, store):
        with pytest.raises(ValueError):
            store.submit(GovernanceTicket(priority="P9", title="x"))

    def test_submit_payload_round_trip(self, store):
        payload = {"app_id": "a1", "amount": 100_000, "nested": {"k": "v"}}
        t = GovernanceTicket(origin="funding", payload=payload, title="t")
        store.submit(t)
        fetched = store.get(t.ticket_id)
        assert fetched.payload == payload

    def test_submit_sla_default_for_priority(self, store):
        t = GovernanceTicket(origin="global", priority="P1", title="x")
        store.submit(t)
        fetched = store.get(t.ticket_id)
        assert fetched.sla_deadline > fetched.created_at


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------

class TestResolve:

    def test_resolve_approved(self, store):
        t = GovernanceTicket(origin="global", title="r1")
        tid = store.submit(t)
        assert store.resolve(tid, "approved", reason="ok", reviewer="alice")
        fetched = store.get(tid)
        assert fetched.state == "approved"
        assert fetched.resolved_by == "alice"
        assert fetched.resolution_reason == "ok"
        assert fetched.resolved_at is not None

    def test_resolve_rejected(self, store):
        t = GovernanceTicket(origin="skill", title="r2")
        tid = store.submit(t)
        store.resolve(tid, "rejected", reason="bad", reviewer="bob")
        assert store.get(tid).state == "rejected"

    def test_resolve_expired(self, store):
        t = GovernanceTicket(origin="mobile", title="r3")
        tid = store.submit(t)
        store.resolve(tid, "expired", reason="sla", reviewer="system")
        assert store.get(tid).state == "expired"

    def test_resolve_missing_ticket_returns_false(self, store):
        assert store.resolve("does_not_exist", "approved") is False

    def test_resolve_already_final_returns_false(self, store):
        t = GovernanceTicket(origin="global", title="r4")
        tid = store.submit(t)
        store.resolve(tid, "approved", reviewer="a")
        assert store.resolve(tid, "rejected", reviewer="b") is False

    def test_resolve_invalid_decision_raises(self, store):
        t = GovernanceTicket(origin="global", title="r5")
        tid = store.submit(t)
        with pytest.raises(ValueError):
            store.resolve(tid, "maybe")

    def test_resolve_d3_terminal_decision_requires_reason(self, store):
        t = GovernanceTicket(
            origin="global",
            decision_class="D3",
            title="r5b",
        )
        tid = store.submit(t)
        with pytest.raises(ValueError, match="reason is required"):
            store.resolve(tid, "approved", reviewer="alice")
        assert store.get(tid).state == "pending"

    def test_resolve_records_event(self, store):
        t = GovernanceTicket(origin="global", title="r6")
        tid = store.submit(t)
        store.resolve(tid, "approved", reviewer="alice")
        events = store.events(tid)
        assert any(e["event_type"] == "resolved" for e in events)


# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------

class TestWithdraw:

    def test_withdraw_pending_succeeds(self, store):
        t = GovernanceTicket(origin="global", title="w1")
        tid = store.submit(t)
        assert store.withdraw(tid, reason="oops", actor="alice")
        assert store.get(tid).state == "withdrawn"

    def test_withdraw_already_resolved_fails(self, store):
        t = GovernanceTicket(origin="global", title="w2")
        tid = store.submit(t)
        store.resolve(tid, "approved", reviewer="bob")
        assert store.withdraw(tid) is False

    def test_withdraw_missing_returns_false(self, store):
        assert store.withdraw("nope") is False


# ---------------------------------------------------------------------------
# Escalate
# ---------------------------------------------------------------------------

class TestEscalate:

    def test_escalate_pending(self, store):
        t = GovernanceTicket(origin="global", title="e1")
        tid = store.submit(t)
        assert store.escalate(tid, reason="urgent", actor="alice")
        assert store.get(tid).state == "escalated"

    def test_resolve_escalated_ticket(self, store):
        t = GovernanceTicket(
            origin="global",
            decision_class="D3",
            title="e1b",
        )
        tid = store.submit(t)
        assert store.escalate(tid, reason="urgent", actor="alice")
        assert store.resolve(
            tid,
            "approved",
            reason="higher tier accepted the D3 change",
            reviewer="bob",
        )
        assert store.get(tid).state == "approved"

    def test_escalate_already_resolved_fails(self, store):
        t = GovernanceTicket(origin="global", title="e2")
        tid = store.submit(t)
        store.resolve(tid, "approved", reviewer="x")
        assert store.escalate(tid) is False


# ---------------------------------------------------------------------------
# Fetch / list
# ---------------------------------------------------------------------------

class TestFetch:

    def test_fetch_pending_excludes_resolved(self, store):
        a = GovernanceTicket(origin="global", title="a")
        b = GovernanceTicket(origin="global", title="b")
        store.submit(a)
        store.submit(b)
        store.resolve(a.ticket_id, "approved", reviewer="x")
        pending = store.fetch_pending()
        assert len(pending) == 1
        assert pending[0].ticket_id == b.ticket_id

    def test_fetch_pending_includes_escalated_reviewable_tickets(self, store):
        t = GovernanceTicket(origin="global", title="needs higher tier")
        store.submit(t)
        store.escalate(t.ticket_id, reason="P0 review", actor="alice")
        pending = store.fetch_pending()
        assert len(pending) == 1
        assert pending[0].state == "escalated"

    def test_fetch_pending_filters_origin(self, store):
        store.submit(GovernanceTicket(origin="funding", title="f"))
        store.submit(GovernanceTicket(origin="mobile", title="m"))
        funding = store.fetch_pending(origin="funding")
        assert len(funding) == 1
        assert funding[0].origin == "funding"

    def test_fetch_pending_filters_project(self, store):
        store.submit(GovernanceTicket(origin="workspace", project_id="p1", title="x"))
        store.submit(GovernanceTicket(origin="workspace", project_id="p2", title="y"))
        result = store.fetch_pending(project_id="p1")
        assert len(result) == 1
        assert result[0].project_id == "p1"

    def test_fetch_pending_priority_order(self, store):
        store.submit(GovernanceTicket(origin="global", priority="P3", title="lo"))
        store.submit(GovernanceTicket(origin="global", priority="P0", title="hi"))
        store.submit(GovernanceTicket(origin="global", priority="P2", title="md"))
        pending = store.fetch_pending()
        assert [t.priority for t in pending] == ["P0", "P2", "P3"]

    def test_fetch_pending_invalid_origin_returns_empty(self, store):
        store.submit(GovernanceTicket(origin="global", title="x"))
        assert store.fetch_pending(origin="not_a_real_origin") == []

    def test_list_with_states_filter(self, store):
        a = GovernanceTicket(origin="global", title="a")
        b = GovernanceTicket(origin="global", title="b")
        store.submit(a)
        store.submit(b)
        store.resolve(a.ticket_id, "approved", reviewer="x")
        approved = store.list(states=["approved"])
        assert len(approved) == 1
        assert approved[0].state == "approved"

    def test_get_missing_returns_none(self, store):
        assert store.get("nope") is None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:

    def test_stats_total(self, store):
        for i in range(3):
            store.submit(GovernanceTicket(origin="global", title=f"t{i}"))
        s = store.stats()
        assert s["total"] == 3

    def test_stats_by_origin(self, store):
        store.submit(GovernanceTicket(origin="funding", title="f"))
        store.submit(GovernanceTicket(origin="funding", title="f2"))
        store.submit(GovernanceTicket(origin="mobile", title="m"))
        s = store.stats()
        assert s["by_origin"]["funding"] == 2
        assert s["by_origin"]["mobile"] == 1

    def test_stats_by_state(self, store):
        a = GovernanceTicket(origin="global", title="a")
        b = GovernanceTicket(origin="global", title="b")
        store.submit(a)
        store.submit(b)
        store.resolve(a.ticket_id, "approved", reviewer="x")
        s = store.stats()
        assert s["by_state"]["approved"] == 1
        assert s["by_state"]["pending"] == 1


# ---------------------------------------------------------------------------
# AuditChain ref
# ---------------------------------------------------------------------------

class TestAuditChainRef:

    def test_attach_audit_chain(self, store):
        t = GovernanceTicket(origin="global", title="ac")
        tid = store.submit(t)
        assert store.attach_audit_chain(tid, "audit_abc123")
        assert store.get(tid).audit_chain_ref == "audit_abc123"

    def test_attach_audit_chain_missing_returns_false(self, store):
        assert store.attach_audit_chain("nope", "ref") is False


# ---------------------------------------------------------------------------
# Constants exposed
# ---------------------------------------------------------------------------

class TestConstants:

    def test_origins_set(self):
        # W14 BE-8.2: round_meta admitted to the origin enum so FE
        # wave-4 round_meta wizards can submit tickets natively.
        assert VALID_ORIGINS == frozenset({
            "workspace", "global", "funding", "mobile", "skill", "council",
            "autonomy", "round_meta", "execution_guard",
        })

    def test_decision_classes(self):
        assert VALID_DECISION_CLASSES == frozenset({
            "D0", "D1", "D2", "D3", "D4", "D5",
        })

    def test_priorities(self):
        assert VALID_PRIORITIES == frozenset({"P0", "P1", "P2", "P3", "P4"})

    def test_gate_types_nonempty(self):
        assert "blocking" in VALID_GATE_TYPES
        assert "financial" in VALID_GATE_TYPES
        assert "external_action" in VALID_GATE_TYPES
