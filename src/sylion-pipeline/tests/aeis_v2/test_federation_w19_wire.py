"""Tests for sprint 4 federation route() ↔ W19 RoutingGate wire-in."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Setup helpers — minimal RoutingRequest + a single-node registry stub.
# ---------------------------------------------------------------------------


def _make_router(tmp_path: Path):
    """Build a FederationRouter against an empty registry — for backward-compat
    tests we just need the route() entry point to exist; the request will hit
    the "Brak aktywnych node-ow" path when no W19 gate is installed."""
    from sylion.aeis_v2.deployment.federation import FederationRouter
    from sylion.aeis_v2.deployment.registry import NodeRegistry

    registry = NodeRegistry()
    router = FederationRouter(registry=registry)
    return router


def _make_request():
    from sylion.aeis_v2.deployment.federation import (
        PrivacyLevel,
        RoutingRequest,
    )

    return RoutingRequest(
        model_id="test-model",
        privacy_level=PrivacyLevel.ANY,
    )


@pytest.fixture(autouse=True)
def _isolate_w19_module_state(monkeypatch: pytest.MonkeyPatch):
    """Reset module-level _W19_ROUTING_GATE + provider after every test."""
    import sylion.aeis_v2.deployment.federation as fed

    monkeypatch.setattr(fed, "_W19_ROUTING_GATE", None)
    monkeypatch.setattr(fed, "_W19_POLICY_TEMPLATE_PROVIDER", None)
    yield
    monkeypatch.setattr(fed, "_W19_ROUTING_GATE", None)
    monkeypatch.setattr(fed, "_W19_POLICY_TEMPLATE_PROVIDER", None)


# ---------------------------------------------------------------------------
# Backward-compat: no W19 gate installed → behaves identically to before.
# ---------------------------------------------------------------------------


def test_no_gate_route_proceeds_to_existing_logic(tmp_path: Path) -> None:
    """Empty registry + no W19 gate → router emits "Brak aktywnych node-ow"."""
    router = _make_router(tmp_path)
    decision = router.route(_make_request())
    # Federation's existing no-active-nodes path:
    assert decision.chosen_node_id is None
    assert "Brak aktywnych node-ow" in decision.rationale
    # Critically NOT the W19 deny path:
    assert "W19 policy" not in decision.rationale


def test_set_w19_routing_gate_installs_then_removes() -> None:
    import sylion.aeis_v2.deployment.federation as fed

    sentinel = object()
    fed.set_w19_routing_gate(sentinel)
    assert fed._W19_ROUTING_GATE is sentinel
    fed.set_w19_routing_gate(None)
    assert fed._W19_ROUTING_GATE is None


def test_set_template_provider_installs_then_removes() -> None:
    import sylion.aeis_v2.deployment.federation as fed

    fn = lambda: "allow"
    fed.set_w19_policy_template_provider(fn)
    assert fed._W19_POLICY_TEMPLATE_PROVIDER is fn
    fed.set_w19_policy_template_provider(None)
    assert fed._W19_POLICY_TEMPLATE_PROVIDER is None


# ---------------------------------------------------------------------------
# With gate installed: deny path short-circuits route().
# ---------------------------------------------------------------------------


class _StubGateAlwaysDeny:
    """Stub that mimics policy_v2.RoutingGate.check return shape."""

    def check(self, *, decision_id: str, policy_template: str | None,
              context: dict[str, Any]) -> Any:
        from sylion.aeis_v2.policy_v2 import RoutingDecision

        return RoutingDecision(
            decision_id=decision_id,
            outcome="deny",
            rendered="deny",
            reason="policy_returned_deny",
            elapsed_ms=0.5,
            rolled_out=True,
        )


class _StubGateAlwaysAllow:
    def check(self, *, decision_id: str, policy_template: str | None,
              context: dict[str, Any]) -> Any:
        from sylion.aeis_v2.policy_v2 import RoutingDecision

        return RoutingDecision(
            decision_id=decision_id,
            outcome="allow",
            rendered="allow",
            reason="policy_returned_allow_or_other",
            elapsed_ms=0.5,
            rolled_out=True,
        )


class _StubGateRaises:
    def check(self, *, decision_id: str, policy_template: str | None,
              context: dict[str, Any]) -> Any:
        raise RuntimeError("simulated W19 gate failure")


def test_gate_deny_short_circuits_route(tmp_path: Path) -> None:
    import sylion.aeis_v2.deployment.federation as fed

    fed.set_w19_routing_gate(_StubGateAlwaysDeny())
    fed.set_w19_policy_template_provider(lambda: "deny")

    router = _make_router(tmp_path)
    decision = router.route(_make_request())
    assert decision.chosen_node_id is None
    assert "W19 policy" in decision.rationale
    assert "policy_returned_deny" in decision.rationale


def test_gate_allow_does_not_short_circuit(tmp_path: Path) -> None:
    """When gate allows, route() proceeds to the normal logic."""
    import sylion.aeis_v2.deployment.federation as fed

    fed.set_w19_routing_gate(_StubGateAlwaysAllow())
    fed.set_w19_policy_template_provider(lambda: "allow")

    router = _make_router(tmp_path)
    decision = router.route(_make_request())
    # Empty registry → "Brak aktywnych node-ow" path (NOT the W19 deny path).
    assert "W19 policy" not in decision.rationale


def test_gate_failure_falls_open(tmp_path: Path) -> None:
    """A raising gate must NOT block routing — falls open per Kimi k1."""
    import sylion.aeis_v2.deployment.federation as fed

    fed.set_w19_routing_gate(_StubGateRaises())
    fed.set_w19_policy_template_provider(lambda: "anything")

    router = _make_router(tmp_path)
    decision = router.route(_make_request())
    # Same path as no-gate behaviour.
    assert decision.chosen_node_id is None
    assert "W19 policy" not in decision.rationale


def test_gate_skipped_outcome_does_not_short_circuit(tmp_path: Path) -> None:
    """outcome="skipped" / "error" / "allow" all proceed — only "deny" blocks."""
    import sylion.aeis_v2.deployment.federation as fed
    from sylion.aeis_v2.policy_v2 import RoutingDecision as _RD

    class _Skipped:
        def check(self, *, decision_id, policy_template, context):
            return _RD(
                decision_id=decision_id, outcome="skipped",
                rendered=None, reason="evaluator_flag_off",
                elapsed_ms=0.1, rolled_out=False,
            )

    fed.set_w19_routing_gate(_Skipped())
    router = _make_router(tmp_path)
    decision = router.route(_make_request())
    assert "W19 policy" not in decision.rationale


def test_gate_template_provider_called_per_route(tmp_path: Path) -> None:
    """The template provider must run on every route() call so PG updates
    propagate immediately without router restart."""
    import sylion.aeis_v2.deployment.federation as fed

    fed.set_w19_routing_gate(_StubGateAlwaysAllow())
    calls: list[int] = []

    def _provider() -> str:
        calls.append(1)
        return "allow"

    fed.set_w19_policy_template_provider(_provider)

    router = _make_router(tmp_path)
    router.route(_make_request())
    router.route(_make_request())
    router.route(_make_request())
    assert len(calls) == 3


def test_w19_check_helper_returns_none_when_no_gate() -> None:
    """The internal helper preserves the no-W19 fast path."""
    import sylion.aeis_v2.deployment.federation as fed

    out = fed._w19_check_or_none("dec-1", {"x": 1})
    assert out is None


def test_w19_check_helper_returns_none_on_provider_raises() -> None:
    """Provider raising = same as no template. Gate.check still consulted."""
    import sylion.aeis_v2.deployment.federation as fed

    fed.set_w19_routing_gate(_StubGateAlwaysAllow())

    def _broken_provider() -> str:
        raise RuntimeError("provider boom")

    fed.set_w19_policy_template_provider(_broken_provider)
    # The helper falls open — returns None — instead of letting the
    # exception propagate up to route().
    out = fed._w19_check_or_none("dec-2", {"x": 1})
    assert out is None
