"""W17 Federation x W19 cost_cap_per_decision policy — wiring tests.

Background
----------
The W19 policy catalog declares ``cost_cap_per_decision`` (limit
0.50 USD per decision). Per ADR-001 #4 the full W19 policy DSL evaluator
is PARKED; we wire ONE specific policy — the cost cap — into the W17
``FederationRouter.route`` path as a hardcoded "no regrets" check.

Three modes (env ``SYLION_COST_CAP_MODE``):
  - ``warn`` (default): log a warning, increment counter, decision
                        PROCEEDS.
  - ``deny``:           return a denied RoutingDecision with
                        ``error="cost_cap_exceeded"`` and
                        ``chosen_node_id=None``.
  - ``off``:            skip the check entirely.

Audit row gains a ``cost_cap_check: {mode, estimated_usd, exceeded}``
field for the operator UI / replay tooling.

Phase 0 token estimate is hardcoded at 1000 (pessimistic upper bound);
G2 will plug in actual prompt + max-response token counts.
"""
from __future__ import annotations

import json

import pytest

from sylion.aeis_v2.deployment import cost_ledger as cost_ledger_mod
from sylion.aeis_v2.deployment import federation as federation_mod
from sylion.aeis_v2.deployment.federation import (
    COST_CAP_PER_DECISION_USD,
    FederationRouter,
    RoutingRequest,
)
from sylion.aeis_v2.deployment.nodes import (
    Node,
    NodeKind,
    NodeStatus,
    PrivacyLevel,
)
from sylion.aeis_v2.deployment.registry import NodeRegistry


# --------------------------------------------------------------------------
# Test fixtures (mirror tests/aeis_v2/test_federation.py)
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _redirect_audit_logs(tmp_path, monkeypatch):
    """Redirect routing-audit + cost-ledger JSONL paths to ``tmp_path``."""
    monkeypatch.setattr(
        federation_mod, "ROUTING_AUDIT_LOG_PATH",
        tmp_path / "routing_audit.jsonl",
    )
    monkeypatch.setattr(
        cost_ledger_mod, "COST_AUDIT_LOG_PATH",
        tmp_path / "cost_ledger.jsonl",
    )


@pytest.fixture(autouse=True)
def _reset_cost_cap_warnings(monkeypatch):
    """Reset the module-level warn counter so tests do not bleed."""
    monkeypatch.setattr(federation_mod, "cost_cap_warnings_total", 0)


@pytest.fixture
def registry() -> NodeRegistry:
    return NodeRegistry()


@pytest.fixture
def router(registry: NodeRegistry) -> FederationRouter:
    return FederationRouter(registry)


def _expensive_node(name: str = "expensive-cloud") -> Node:
    """Cloud node priced so a 1000-token call costs > 0.50 USD.

    cost_per_1k = 0.60 USD * 1000 tokens / 1000 = 0.60 USD per decision,
    which exceeds the 0.50 USD cap.
    """
    return Node(
        node_id="",
        name=name,
        kind=NodeKind.COMPUTE_PROVIDER,
        status=NodeStatus.ONLINE,
        base_url=f"http://{name}.cloud:8000",
        locality="cloud",
        available_models=["gpt-4-premium"],
        cost_per_1k_tokens_usd={"gpt-4-premium": 0.60},
        capacity_score=1.0,
    )


def _cheap_node(name: str = "laptop-warsaw") -> Node:
    """Local node, well below the cost cap (0.001 USD per 1k tokens)."""
    return Node(
        node_id="",
        name=name,
        kind=NodeKind.HYBRID,
        status=NodeStatus.ONLINE,
        base_url=f"http://{name}.local:8000",
        locality="local",
        available_models=["qwen2.5:72b"],
        cost_per_1k_tokens_usd={"qwen2.5:72b": 0.001},
        capacity_score=1.0,
    )


# --------------------------------------------------------------------------
# 1) ``off`` mode skips the check entirely.
# --------------------------------------------------------------------------


def test_cost_cap_off_skips_check(
    registry: NodeRegistry,
    router: FederationRouter,
    monkeypatch,
    caplog,
) -> None:
    """``SYLION_COST_CAP_MODE=off`` short-circuits — no warn, no deny.

    A node priced at 0.60 USD/1k tokens *would* exceed the 0.50 USD cap
    in any other mode. With ``off``, the decision PROCEEDS and the audit
    row carries ``cost_cap_check=None``.
    """
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "off")
    registry.register(_expensive_node())

    with caplog.at_level("WARNING", logger="sylion.aeis_v2.deployment.federation"):
        decision = router.route(RoutingRequest(
            model_id="gpt-4-premium",
            privacy_level=PrivacyLevel.ANY,
        ))

    assert decision.chosen_node_id is not None, "off mode must NOT block"
    assert decision.error is None
    assert federation_mod.cost_cap_warnings_total == 0, (
        "off mode must NOT increment the warn counter"
    )
    assert not any("cost_cap" in rec.message for rec in caplog.records), (
        "off mode must emit no cost_cap warnings"
    )

    # Audit row should reflect that the check was skipped.
    audit_path = federation_mod.ROUTING_AUDIT_LOG_PATH
    row = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["cost_cap_check"] is None, (
        f"off mode must record cost_cap_check=None; got {row['cost_cap_check']!r}"
    )


# --------------------------------------------------------------------------
# 2) ``warn`` mode does NOT block — emits warning + increments counter.
# --------------------------------------------------------------------------


def test_cost_cap_warn_does_not_block_decision_but_logs_warning(
    registry: NodeRegistry,
    router: FederationRouter,
    monkeypatch,
    caplog,
) -> None:
    """Warn mode (default) is non-blocking but observable.

    The decision still chooses the expensive node (no cheaper option),
    but the operator sees a WARNING log line and the warn-counter ticks
    up — so cost-cap pressure shows up in metrics without disrupting
    traffic.
    """
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "warn")
    registry.register(_expensive_node())

    with caplog.at_level("WARNING", logger="sylion.aeis_v2.deployment.federation"):
        decision = router.route(RoutingRequest(
            model_id="gpt-4-premium",
            privacy_level=PrivacyLevel.ANY,
        ))

    # Decision MUST proceed.
    assert decision.chosen_node_id is not None, "warn mode must NOT deny"
    assert decision.error is None
    assert decision.chosen_model_id == "gpt-4-premium"

    # Counter must have ticked exactly once.
    assert federation_mod.cost_cap_warnings_total == 1, (
        f"expected exactly 1 warn-counter increment, got "
        f"{federation_mod.cost_cap_warnings_total}"
    )

    # caplog must contain the cost_cap warning.
    matching = [
        rec for rec in caplog.records
        if "cost_cap" in rec.message and rec.levelname == "WARNING"
    ]
    assert matching, (
        "expected a cost_cap WARNING log line; got "
        f"{[r.message for r in caplog.records]}"
    )


# --------------------------------------------------------------------------
# 3) ``deny`` mode returns a denied decision when the cap is exceeded.
# --------------------------------------------------------------------------


def test_cost_cap_deny_returns_denied_decision_when_exceeded(
    registry: NodeRegistry,
    router: FederationRouter,
    monkeypatch,
) -> None:
    """Deny mode hard-stops: ``chosen_node_id=None``,
    ``error="cost_cap_exceeded"``, and the rationale references the
    W19 policy name + the offending estimate."""
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "deny")
    registry.register(_expensive_node())

    decision = router.route(RoutingRequest(
        model_id="gpt-4-premium",
        privacy_level=PrivacyLevel.ANY,
    ))

    assert decision.chosen_node_id is None, "deny must zero the chosen node"
    assert decision.chosen_model_id is None
    assert decision.error == "cost_cap_exceeded"
    assert "cost_cap_per_decision" in decision.rationale, (
        f"rationale must reference policy name; got {decision.rationale!r}"
    )
    # Sanity: the rationale should also mention the configured limit.
    assert f"{COST_CAP_PER_DECISION_USD}" in decision.rationale


# --------------------------------------------------------------------------
# 4) When the estimated cost is well under the cap, every mode passes
#    cleanly.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["warn", "deny", "off"])
def test_cost_cap_under_limit_passes_in_all_modes(
    registry: NodeRegistry,
    router: FederationRouter,
    monkeypatch,
    mode: str,
) -> None:
    """A cheap local node costs 0.001 USD/1k tokens => 0.001 USD per
    decision, which is far below the 0.50 USD cap. The decision must
    succeed cleanly under every mode, with no warn-counter tick and no
    deny error."""
    monkeypatch.setenv("SYLION_COST_CAP_MODE", mode)
    registry.register(_cheap_node())

    decision = router.route(RoutingRequest(
        model_id="qwen2.5:72b",
        privacy_level=PrivacyLevel.PREFER_LOCAL,
    ))

    assert decision.chosen_node_id is not None, f"mode={mode} must succeed"
    assert decision.error is None
    assert federation_mod.cost_cap_warnings_total == 0, (
        f"mode={mode}: under-limit decision must NOT increment warn counter"
    )


# --------------------------------------------------------------------------
# 5) Audit row carries the ``cost_cap_check`` triple.
# --------------------------------------------------------------------------


def test_cost_cap_audit_row_has_cost_cap_check_field(
    registry: NodeRegistry,
    router: FederationRouter,
    monkeypatch,
) -> None:
    """The routing audit JSONL row must include
    ``cost_cap_check: {mode, estimated_usd, exceeded}`` whenever the
    cap was evaluated. We exercise warn-mode with an expensive node so
    every triple field has an interesting value."""
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "warn")
    registry.register(_expensive_node())

    decision = router.route(RoutingRequest(
        model_id="gpt-4-premium",
        privacy_level=PrivacyLevel.ANY,
    ))
    assert decision.chosen_node_id is not None

    audit_path = federation_mod.ROUTING_AUDIT_LOG_PATH
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, f"expected exactly 1 audit row, got {len(lines)}"
    row = json.loads(lines[0])

    assert "cost_cap_check" in row, "audit row must declare cost_cap_check key"
    check = row["cost_cap_check"]
    assert isinstance(check, dict), (
        f"cost_cap_check must be a dict when evaluated; got {check!r}"
    )
    assert check["mode"] == "warn"
    # 0.60 USD/1k * 1000 tokens / 1000 == 0.60 USD per decision.
    assert check["estimated_usd"] == pytest.approx(0.60, rel=1e-9)
    assert check["exceeded"] is True


# --------------------------------------------------------------------------
# 6) The env var takes precedence over the module-level default.
# --------------------------------------------------------------------------


def test_cost_cap_mode_env_var_takes_precedence(
    registry: NodeRegistry,
    router: FederationRouter,
    monkeypatch,
) -> None:
    """Sanity check on the env-resolution helper.

    The default mode (``COST_CAP_DEFAULT_MODE``) is ``warn``, so to prove
    the env wins we set it to ``deny`` and observe a denied decision.
    Then we flip the env to ``off`` and observe the same expensive
    request go through. Both observations must hold without code edits.
    """
    registry.register(_expensive_node())

    # Round 1: env=deny -> decision denied.
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "deny")
    deny_decision = router.route(RoutingRequest(
        model_id="gpt-4-premium",
        privacy_level=PrivacyLevel.ANY,
    ))
    assert deny_decision.chosen_node_id is None
    assert deny_decision.error == "cost_cap_exceeded"

    # Round 2: env=off -> decision goes through with no warn / no error.
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "off")
    off_decision = router.route(RoutingRequest(
        model_id="gpt-4-premium",
        privacy_level=PrivacyLevel.ANY,
    ))
    assert off_decision.chosen_node_id is not None
    assert off_decision.error is None
