"""Wave A1 -- All 5 origins land in unified TicketStore.

Verifies the DoD criterion that workspace/global/funding/mobile/skill submisje
share one truth plane (one table, one query).
"""

from __future__ import annotations

import pytest

from sylion.governance.tickets import (
    GovernanceTicket,
    fetch_pending,
    reset_ticket_store,
    stats,
    submit,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_ticket_store()
    yield
    reset_ticket_store()


def _make(origin: str, **overrides) -> GovernanceTicket:
    base = dict(
        origin=origin,
        project_id="proj_42",
        decision_class="D2",
        gate_type="blocking",
        priority="P2",
        title=f"{origin} ticket",
        summary=f"summary for {origin}",
        payload={"src": origin},
        requested_by=f"{origin}_actor",
    )
    base.update(overrides)
    return GovernanceTicket(**base)


class TestAllOriginsUnified:

    def test_workspace_origin_lands_in_store(self):
        tid = submit(_make("workspace"))
        assert any(t.ticket_id == tid for t in fetch_pending(origin="workspace"))

    def test_global_origin_lands_in_store(self):
        tid = submit(_make("global"))
        assert any(t.ticket_id == tid for t in fetch_pending(origin="global"))

    def test_funding_origin_lands_in_store(self):
        tid = submit(_make("funding", gate_type="financial",
                           decision_class="D3", priority="P1"))
        assert any(t.ticket_id == tid for t in fetch_pending(origin="funding"))

    def test_mobile_origin_lands_in_store(self):
        tid = submit(_make("mobile"))
        assert any(t.ticket_id == tid for t in fetch_pending(origin="mobile"))

    def test_skill_origin_lands_in_store(self):
        tid = submit(_make("skill", payload={"skill_invocation_id": "inv_99"}))
        assert any(t.ticket_id == tid for t in fetch_pending(origin="skill"))

    def test_council_origin_lands_in_store(self):
        tid = submit(_make("council", decision_class="D4"))
        assert any(t.ticket_id == tid for t in fetch_pending(origin="council"))

    def test_execution_guard_origin_lands_in_store(self):
        tid = submit(_make("execution_guard", decision_class="D3", gate_type="production"))
        assert any(t.ticket_id == tid for t in fetch_pending(origin="execution_guard"))


class TestSingleTableAggregate:

    def test_all_origins_in_one_pending_query(self):
        for origin in ("workspace", "global", "funding", "mobile", "skill", "council", "execution_guard"):
            submit(_make(origin))
        pending = fetch_pending()
        assert len(pending) == 7
        origins = {t.origin for t in pending}
        assert origins == {
            "workspace", "global", "funding", "mobile", "skill", "council", "execution_guard",
        }

    def test_stats_include_all_origins(self):
        for origin in ("workspace", "global", "funding", "mobile", "skill", "council", "execution_guard"):
            submit(_make(origin))
        s = stats()
        assert s["total"] == 7
        for origin in ("workspace", "global", "funding", "mobile", "skill", "council", "execution_guard"):
            assert s["by_origin"].get(origin, 0) == 1


class TestPriorityOrderingAcrossOrigins:

    def test_p0_funding_outranks_p3_workspace(self):
        submit(_make("workspace", priority="P3", title="ws_low"))
        submit(_make("funding", priority="P0", title="fund_critical"))
        submit(_make("global", priority="P2", title="g_normal"))

        pending = fetch_pending()
        assert [t.priority for t in pending] == ["P0", "P2", "P3"]
        assert pending[0].origin == "funding"


class TestProjectScoping:

    def test_filter_by_project(self):
        submit(_make("workspace", project_id="proj_1"))
        submit(_make("skill", project_id="proj_1"))
        submit(_make("global", project_id="proj_2"))

        proj1 = fetch_pending(project_id="proj_1")
        assert len(proj1) == 2
        assert {t.origin for t in proj1} == {"workspace", "skill"}

        proj2 = fetch_pending(project_id="proj_2")
        assert len(proj2) == 1
        assert proj2[0].origin == "global"


class TestPayloadIntegrityPerOrigin:

    def test_funding_payload_round_trip(self):
        payload = {"application_id": "app_42", "portal": "EC", "amount": 250_000}
        t = _make("funding", payload=payload)
        tid = submit(t)
        fetched = next(x for x in fetch_pending(origin="funding") if x.ticket_id == tid)
        assert fetched.payload == payload

    def test_mobile_payload_round_trip(self):
        payload = {"device_token": "abc", "deeplink": "sylion://approve/123"}
        t = _make("mobile", payload=payload)
        tid = submit(t)
        fetched = next(x for x in fetch_pending(origin="mobile") if x.ticket_id == tid)
        assert fetched.payload == payload

    def test_skill_invocation_id_in_payload(self):
        # B/K request hook: skill_invocation_id is an extra field in payload.
        payload = {"skill_invocation_id": "inv_77", "skill_id": "seed.echo"}
        t = _make("skill", payload=payload)
        tid = submit(t)
        fetched = next(x for x in fetch_pending(origin="skill") if x.ticket_id == tid)
        assert fetched.payload["skill_invocation_id"] == "inv_77"
