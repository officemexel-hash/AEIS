"""Tests for sylion.governance.round_meta_factory.

Covers:
    * one happy-path test per Round (1, 2, 3) — verifies gate types,
      payload persistence, title and summary
    * Round 3 multi-gate composition (3 gate types in context)
    * invalid-round guard (ValueError)
    * input validation (TypeError on bad project_id / requested_by / payload)
    * idempotent gate id pattern (round_<n>) for audit chain joining
"""

from __future__ import annotations

import pytest

from sylion.governance.human_gate import HumanGate
from sylion.governance.round_meta_factory import (
    create_round_meta_ticket,
    _ROUND_GATE_TYPES,
)


@pytest.fixture
def hg() -> HumanGate:
    """Fresh in-memory HumanGate per test (isolation, no singleton bleed)."""
    return HumanGate(db_path=":memory:")


# ---------------------------------------------------------------------------
# Happy paths — one per Round
# ---------------------------------------------------------------------------


class TestRound1:
    """Round 1: idea -> ksiega, single 'blocking' gate."""

    def test_returns_ticket_id(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=1,
            project_id="proj-r1",
            payload={"council_size": 5},
            requested_by="alice",
            hg=hg,
        )
        assert isinstance(ticket_id, str)
        assert ticket_id  # non-empty

    def test_persists_round_and_gate_types(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=1,
            project_id="proj-r1",
            payload={"council_size": 5, "cost_limit_usd": 10.0},
            requested_by="alice",
            hg=hg,
        )
        req = hg.get_request(ticket_id)
        assert req is not None
        ctx = req["context_json"]
        assert ctx["round"] == 1
        assert ctx["gate_types"] == ["blocking"]
        assert ctx["primary_gate_type"] == "blocking"
        assert ctx["project_id"] == "proj-r1"
        # caller payload preserved
        assert ctx["council_size"] == 5
        assert ctx["cost_limit_usd"] == 10.0

    def test_title_contains_round_and_project(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=1, project_id="proj-r1", payload={},
            requested_by="alice", hg=hg,
        )
        req = hg.get_request(ticket_id)
        assert "Round 1" in req["title"]
        assert "proj-r1" in req["title"]

    def test_summary_mentions_ksiega(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=1, project_id="proj-r1", payload={},
            requested_by="alice", hg=hg,
        )
        req = hg.get_request(ticket_id)
        # Round 1 narrative must mention "Ksiegi" / "Source of Truth"
        assert "Ksiegi" in req["description"] or "Source of Truth" in req["description"]

    def test_gate_id_uses_round_prefix(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=1, project_id="proj-r1", payload={},
            requested_by="alice", hg=hg,
        )
        req = hg.get_request(ticket_id)
        # gate_id is round_1 — joinable in audit chain by round number.
        assert req["gate_id"] == "round_1"


class TestRound2:
    """Round 2: ksiega -> masterplan, single 'blocking' gate."""

    def test_round_2_ticket_creates(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=2,
            project_id="proj-r2",
            payload={"masterplan_strategy": "depth-first"},
            requested_by="bob",
            hg=hg,
        )
        req = hg.get_request(ticket_id)
        assert req is not None
        assert req["gate_id"] == "round_2"

    def test_round_2_gate_types(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=2, project_id="proj-r2", payload={},
            requested_by="bob", hg=hg,
        )
        ctx = hg.get_request(ticket_id)["context_json"]
        assert ctx["gate_types"] == ["blocking"]
        assert ctx["round"] == 2

    def test_round_2_summary_mentions_masterplan(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=2, project_id="proj-r2", payload={},
            requested_by="bob", hg=hg,
        )
        req = hg.get_request(ticket_id)
        assert "masterplanu" in req["description"].lower() or \
               "masterplan" in req["description"].lower()


class TestRound3:
    """Round 3: masterplan -> build, multi-gate (financial+production+external_action)."""

    def test_round_3_ticket_creates(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=3,
            project_id="proj-r3",
            payload={
                "cost_cap_usd": 250.0,
                "autonomy_level": "L2",
                "external_actions_policy": {"github": "allow", "deploy": "deny"},
            },
            requested_by="carol",
            hg=hg,
        )
        assert isinstance(ticket_id, str)

    def test_round_3_persists_all_three_gate_types(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=3, project_id="proj-r3",
            payload={"cost_cap_usd": 100.0, "autonomy_level": "L1"},
            requested_by="carol", hg=hg,
        )
        ctx = hg.get_request(ticket_id)["context_json"]
        # CRITICAL: all 3 gate types must be persisted for downstream auditors.
        assert ctx["gate_types"] == ["financial", "production", "external_action"]
        assert ctx["primary_gate_type"] == "financial"
        assert ctx["round"] == 3

    def test_round_3_summary_includes_cost_cap_and_autonomy(self, hg: HumanGate) -> None:
        ticket_id = create_round_meta_ticket(
            round=3, project_id="proj-r3",
            payload={"cost_cap_usd": 250.5, "autonomy_level": "L3"},
            requested_by="carol", hg=hg,
        )
        desc = hg.get_request(ticket_id)["description"]
        assert "250.50" in desc
        assert "L3" in desc

    def test_round_3_external_policy_preserved(self, hg: HumanGate) -> None:
        policy = {"github_push": "allow", "prod_deploy": "deny"}
        ticket_id = create_round_meta_ticket(
            round=3, project_id="proj-r3",
            payload={
                "cost_cap_usd": 50.0, "autonomy_level": "L0",
                "external_actions_policy": policy,
            },
            requested_by="carol", hg=hg,
        )
        ctx = hg.get_request(ticket_id)["context_json"]
        assert ctx["external_actions_policy"] == policy


# ---------------------------------------------------------------------------
# Validation guards
# ---------------------------------------------------------------------------


class TestValidation:

    @pytest.mark.parametrize("bad", [0, 4, 5, 99, -1])
    def test_invalid_round_raises_value_error(
        self, hg: HumanGate, bad: int,
    ) -> None:
        with pytest.raises(ValueError, match="Invalid round"):
            create_round_meta_ticket(
                round=bad,  # type: ignore[arg-type]
                project_id="p",
                payload={},
                requested_by="x",
                hg=hg,
            )

    def test_empty_project_id_raises_type_error(self, hg: HumanGate) -> None:
        with pytest.raises(TypeError, match="project_id"):
            create_round_meta_ticket(
                round=1, project_id="", payload={},
                requested_by="x", hg=hg,
            )

    def test_empty_requested_by_raises_type_error(self, hg: HumanGate) -> None:
        with pytest.raises(TypeError, match="requested_by"):
            create_round_meta_ticket(
                round=1, project_id="p", payload={},
                requested_by="", hg=hg,
            )

    def test_non_dict_payload_raises_type_error(self, hg: HumanGate) -> None:
        with pytest.raises(TypeError, match="payload"):
            create_round_meta_ticket(
                round=1, project_id="p",
                payload="not a dict",  # type: ignore[arg-type]
                requested_by="x", hg=hg,
            )


# ---------------------------------------------------------------------------
# Module-level invariants (audit chain joining)
# ---------------------------------------------------------------------------


class TestModuleInvariants:

    def test_round_gate_table_covers_1_2_3(self) -> None:
        assert set(_ROUND_GATE_TYPES.keys()) == {1, 2, 3}

    def test_round_3_is_the_only_multi_gate(self) -> None:
        assert len(_ROUND_GATE_TYPES[1]) == 1
        assert len(_ROUND_GATE_TYPES[2]) == 1
        assert len(_ROUND_GATE_TYPES[3]) == 3

    def test_round_3_gate_order_is_deterministic(self) -> None:
        # Order matters for audit replay — financial first by convention.
        assert _ROUND_GATE_TYPES[3] == [
            "financial", "production", "external_action",
        ]
