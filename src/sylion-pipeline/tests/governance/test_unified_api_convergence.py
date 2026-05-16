"""Wave A-Cleanup -- unified API convergence.

DoD:
  [x] `from sylion.governance import submit` works (Hook v1.0 convenience).
  [x] Both import paths (`sylion.governance` and `sylion.governance.tickets`)
      resolve to the *same* callable (no split-brain surfaces).
  [x] Council quality layer is importable via `sylion.cognitive.council`.
  [x] Single TicketStore singleton — `get_ticket_store()` is identity-stable
      across convenience and explicit imports.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Direct-from-package imports (convenience path)
# ---------------------------------------------------------------------------

class TestGovernancePackageConvenience:

    def test_submit_importable_from_package_root(self):
        from sylion.governance import submit
        assert callable(submit)

    def test_full_hook_api_on_package_root(self):
        from sylion.governance import (  # noqa: F401
            GovernanceTicket,
            submit, fetch_pending, fetch_by_id,
            resolve, withdraw, escalate, stats,
            VALID_ORIGINS, VALID_DECISION_CLASSES, VALID_GATE_TYPES,
            VALID_PRIORITIES, VALID_STATES,
        )

    def test_no_split_brain_submit(self):
        from sylion.governance import submit as submit_a
        from sylion.governance.tickets import submit as submit_b
        # Both paths must expose the SAME function object -- otherwise
        # callers could race against two different TicketStore bindings.
        assert submit_a is submit_b

    @pytest.mark.parametrize("name", [
        "submit", "fetch_pending", "fetch_by_id", "resolve",
        "withdraw", "escalate", "stats",
    ])
    def test_every_hook_is_single_binding(self, name):
        import sylion.governance as pkg
        import sylion.governance.tickets as mod
        assert getattr(pkg, name) is getattr(mod, name)


# ---------------------------------------------------------------------------
# Single source of truth -- ticket store / audit chain / ModelRegistry
# ---------------------------------------------------------------------------

class TestSingletonConsistency:

    def test_ticket_store_identity(self):
        from sylion.governance import get_ticket_store as a
        from sylion.governance.ticket import get_ticket_store as b
        from sylion.governance.tickets import get_ticket_store as c
        # All three references point at the SAME singleton factory.
        assert a is b is c
        # Actual store instance is identity-stable across calls.
        assert a() is b() is c()

    def test_audit_chain_identity(self):
        from sylion.governance import get_audit_chain as a
        from sylion.governance.audit_chain import get_audit_chain as b
        assert a is b
        assert a() is b()

    def test_valid_origins_single_source(self):
        from sylion.governance import VALID_ORIGINS as a
        from sylion.governance.ticket import VALID_ORIGINS as b
        from sylion.governance.tickets import VALID_ORIGINS as c
        assert a is b is c


# ---------------------------------------------------------------------------
# Cognitive Council quality layer reachable
# ---------------------------------------------------------------------------

class TestCognitiveCouncilSurface:

    def test_import_voting_facade(self):
        from sylion.cognitive.council import (  # noqa: F401
            COUNCIL_ROLES,
            DECISION_CLASS_TIERS,
            MODEL_TIER_HIERARCHY,
            ROLE_PROMPT_TEMPLATES,
            SeededVote,
            format_role_prompt,
            get_role_template,
            register_role_template,
            reset_role_templates,
            seeded_vote,
            select_model_for_class,
        )

    def test_council_does_not_leak_state_into_governance(self):
        # Cognitive council quality layer is decoupled from governance
        # ticket plane -- no implicit writes on import.
        from sylion.cognitive.council import seeded_vote
        from sylion.governance import get_ticket_store
        store = get_ticket_store()
        before = store.stats()["total"]
        _ = seeded_vote("probe", "planner", 1, "D2")
        assert store.stats()["total"] == before


# ---------------------------------------------------------------------------
# Autonomy surface is discoverable
# ---------------------------------------------------------------------------

class TestAutonomySurface:

    def test_import_facade(self):
        from sylion.autonomy import (  # noqa: F401
            AutonomyPhase,
            AutonomyStageMachine,
            AutonomyTransition,
            PHASE_ORDER,
            get_autonomy_machine,
            reset_autonomy_machine,
        )

    def test_autonomy_origin_in_governance_valid_set(self):
        from sylion.governance import VALID_ORIGINS
        assert "autonomy" in VALID_ORIGINS
