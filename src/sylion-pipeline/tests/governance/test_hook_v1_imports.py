"""Wave A6 -- Hook points exposed for B (skills/memory/mobile) and K (funding).

DoD per PROMPT_01 sec 6:
  [x] B i K mogą bez crash zaimportować `governance.tickets.submit`.
  [x] Docstring zawiera "Hook v1.0".

This module is *the* contract test: if it goes red, B/K builds break and
A-GOV owes them a REQUEST entry + bump.
"""

from __future__ import annotations

import inspect

import pytest

import sylion.governance.ticket as _ticket_mod


# ---------------------------------------------------------------------------
# Plain-import smoke (B and K must be able to do these)
# ---------------------------------------------------------------------------

class TestPublicHookImports:

    def test_b_skills_can_import_submit(self):
        from sylion.governance.tickets import submit  # noqa: F401
        assert callable(submit)

    def test_b_mobile_can_import_governance_ticket(self):
        from sylion.governance.tickets import GovernanceTicket  # noqa: F401
        assert GovernanceTicket is _ticket_mod.GovernanceTicket

    def test_k_funding_can_import_full_surface(self):
        # K-SURF funding bridge call site touches everything in one go.
        from sylion.governance.tickets import (  # noqa: F401
            GovernanceTicket,
            VALID_ORIGINS,
            VALID_DECISION_CLASSES,
            VALID_GATE_TYPES,
            VALID_PRIORITIES,
            submit,
            fetch_pending,
            fetch_by_id,
            resolve,
            withdraw,
            escalate,
            stats,
        )

    def test_package_root_exposes_governance_ticket(self):
        # `from sylion.governance import GovernanceTicket` shorthand.
        from sylion.governance import GovernanceTicket
        assert GovernanceTicket is _ticket_mod.GovernanceTicket


# ---------------------------------------------------------------------------
# Hook v1.0 versioning is documented (per INTEGRATION_CONTRACTS sec 12)
# ---------------------------------------------------------------------------

class TestHookV1Versioning:

    def test_module_docstring_advertises_hook_v1(self):
        import sylion.governance.tickets as tickets_mod
        assert tickets_mod.__doc__ is not None
        assert "Hook v1.0" in tickets_mod.__doc__

    @pytest.mark.parametrize("name", [
        "submit", "fetch_pending", "fetch_by_id", "resolve",
        "withdraw", "escalate", "stats",
    ])
    def test_each_hook_function_has_v1_docstring(self, name):
        import sylion.governance.tickets as tickets_mod
        fn = getattr(tickets_mod, name)
        assert fn.__doc__ is not None, f"{name} missing docstring"
        assert "Hook v1.0" in fn.__doc__, (
            f"{name} docstring must advertise Hook v1.0"
        )


# ---------------------------------------------------------------------------
# Origin enum covers all caller namespaces (B, K, autonomy)
# ---------------------------------------------------------------------------

class TestOriginCoverage:

    @pytest.mark.parametrize("origin", [
        "skill", "mobile", "funding", "council", "workspace", "global",
        "autonomy", "round_meta", "execution_guard",
    ])
    def test_origin_accepted(self, origin):
        from sylion.governance.tickets import VALID_ORIGINS
        assert origin in VALID_ORIGINS

    def test_no_unexpected_origins(self):
        from sylion.governance.tickets import VALID_ORIGINS
        # W14 BE-8.2: ``round_meta`` joined the canonical origin set
        # so FE wave-4 wizards can submit governance tickets without
        # masquerading as ``workspace``.
        assert VALID_ORIGINS == frozenset({
            "workspace", "global", "funding", "mobile", "skill",
            "council", "autonomy", "round_meta", "execution_guard",
        })


# ---------------------------------------------------------------------------
# Round-trip: each caller-facing origin actually submits + fetches
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    _ticket_mod.reset_ticket_store(":memory:")
    yield
    _ticket_mod.reset_ticket_store(":memory:")


class TestRoundTrip:

    def test_b_skills_submit_round_trip(self):
        from sylion.governance.tickets import (
            GovernanceTicket, submit, fetch_by_id,
        )
        tid = submit(GovernanceTicket(
            origin="skill",
            decision_class="D2",
            gate_type="non_blocking",
            title="register echo skill",
            payload={"skill_id": "echo", "manifest_hash": "deadbeef"},
            requested_by="skills_runtime",
        ))
        assert fetch_by_id(tid).origin == "skill"

    def test_b_mobile_submit_round_trip(self):
        from sylion.governance.tickets import (
            GovernanceTicket, submit, fetch_by_id,
        )
        tid = submit(GovernanceTicket(
            origin="mobile",
            decision_class="D1",
            gate_type="non_blocking",
            title="mobile gate request",
            requested_by="operator_mobile",
        ))
        assert fetch_by_id(tid).origin == "mobile"

    def test_k_funding_submit_round_trip(self):
        from sylion.governance.tickets import (
            GovernanceTicket, submit, fetch_by_id,
        )
        tid = submit(GovernanceTicket(
            origin="funding",
            decision_class="D3",
            gate_type="financial",
            priority="P1",
            title="Horizon Europe submission",
            payload={"application_id": "app_456", "amount": 250_000},
            requested_by="funding_autopilot",
        ))
        ticket = fetch_by_id(tid)
        assert ticket.origin == "funding"
        assert ticket.decision_class == "D3"
        assert ticket.payload["amount"] == 250_000

    def test_autonomy_origin_round_trip(self):
        from sylion.governance.tickets import (
            GovernanceTicket, submit, fetch_by_id,
        )
        tid = submit(GovernanceTicket(
            origin="autonomy",
            decision_class="D2",
            gate_type="blocking",
            title="autonomy escalation",
            requested_by="autonomy_machine",
        ))
        assert fetch_by_id(tid).origin == "autonomy"


# ---------------------------------------------------------------------------
# Signatures are stable -- changing them is a Hook bump (v1.0 -> v1.1+)
# ---------------------------------------------------------------------------

class TestStableSignatures:

    def test_submit_signature(self):
        from sylion.governance.tickets import submit
        sig = inspect.signature(submit)
        assert list(sig.parameters) == ["ticket"]

    def test_resolve_signature(self):
        from sylion.governance.tickets import resolve
        sig = inspect.signature(resolve)
        params = list(sig.parameters)
        # ticket_id, decision required; reason/reviewer optional with defaults.
        assert params[:2] == ["ticket_id", "decision"]
        assert "reason" in params and "reviewer" in params

    def test_fetch_pending_signature(self):
        from sylion.governance.tickets import fetch_pending
        sig = inspect.signature(fetch_pending)
        # All filters are optional kwargs.
        for name in ("operator_id", "origin", "project_id", "priority"):
            assert sig.parameters[name].default is None
