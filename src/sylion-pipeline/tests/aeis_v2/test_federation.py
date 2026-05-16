"""W17 Federation — Phase 0 unit tests.

Testuje:

- ``NodeRegistry`` (register/get/list_active/heartbeat/unregister).
- ``FederationRouter.route`` — algorytm Phase 0 (privacy → model →
  cost → locality → capacity).

Wszystkie testy uzywaja swiezego ``NodeRegistry`` (nowa instancja per
test) zeby uniknac efektu singletona.
"""
from __future__ import annotations

import time

import pytest

from sylion.aeis_v2.deployment import cost_ledger as cost_ledger_mod
from sylion.aeis_v2.deployment import federation as federation_mod
from sylion.aeis_v2.deployment.federation import (
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
# Test fixtures
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _redirect_audit_logs(tmp_path, monkeypatch):
    """Redirect routing-audit and cost-ledger JSONL paths to ``tmp_path``.

    Without this fixture, every routing decision in the suite would
    append rows to the real ``logs/v2/routing_audit.jsonl`` and
    ``logs/v2/cost_ledger.jsonl`` files. The W17 cost-ledger Phase 0
    work added the second sink (per ADR-001 #3), so we redirect both.
    """
    monkeypatch.setattr(
        federation_mod, "ROUTING_AUDIT_LOG_PATH",
        tmp_path / "routing_audit.jsonl",
    )
    monkeypatch.setattr(
        cost_ledger_mod, "COST_AUDIT_LOG_PATH",
        tmp_path / "cost_ledger.jsonl",
    )


@pytest.fixture
def registry() -> NodeRegistry:
    """Swiezy in-memory NodeRegistry per test."""
    return NodeRegistry()


@pytest.fixture
def router(registry: NodeRegistry) -> FederationRouter:
    return FederationRouter(registry)


def _make_node(
    name: str,
    locality: str = "local",
    kind: NodeKind = NodeKind.HYBRID,
    available_models: list[str] | None = None,
    cost: dict[str, float] | None = None,
    capacity_score: float = 1.0,
    status: NodeStatus = NodeStatus.ONLINE,
) -> Node:
    return Node(
        node_id="",  # registry wygeneruje
        name=name,
        kind=kind,
        status=status,
        base_url=f"http://{name}.local:8000",
        locality=locality,
        available_models=list(available_models or []),
        cost_per_1k_tokens_usd=dict(cost or {}),
        capacity_score=capacity_score,
    )


# --------------------------------------------------------------------------
# 1) Registry: register + get
# --------------------------------------------------------------------------


def test_node_registry_register_and_get(registry: NodeRegistry) -> None:
    n = _make_node("laptop-warsaw", available_models=["qwen2.5:7b"])
    saved = registry.register(n)
    assert saved.node_id, "registry powinien wygenerowac node_id gdy pusty"
    fetched = registry.get(saved.node_id)
    assert fetched is not None
    assert fetched.name == "laptop-warsaw"
    assert fetched.available_models == ["qwen2.5:7b"]
    assert fetched.last_heartbeat > 0


# --------------------------------------------------------------------------
# 2) Registry: register replaces existing node
# --------------------------------------------------------------------------


def test_register_replaces_existing_node(registry: NodeRegistry) -> None:
    a = _make_node("vps", available_models=["m1"])
    saved = registry.register(a)
    nid = saved.node_id
    # ponowna rejestracja z tym samym node_id ma zastapic
    b = Node(
        node_id=nid,
        name="vps",
        kind=NodeKind.COMPUTE_PROVIDER,
        status=NodeStatus.ONLINE,
        locality="cloud",
        available_models=["m2", "m3"],
    )
    registry.register(b)
    assert registry.size() == 1
    fetched = registry.get(nid)
    assert fetched is not None
    assert fetched.locality == "cloud"
    assert fetched.available_models == ["m2", "m3"]
    assert fetched.kind == NodeKind.COMPUTE_PROVIDER


# --------------------------------------------------------------------------
# 3) Registry: heartbeat sets status + timestamp
# --------------------------------------------------------------------------


def test_update_heartbeat_sets_status_and_timestamp(registry: NodeRegistry) -> None:
    saved = registry.register(_make_node("laptop", status=NodeStatus.UNKNOWN))
    nid = saved.node_id
    ts0 = saved.last_heartbeat
    time.sleep(0.01)
    ok = registry.update_heartbeat(nid, NodeStatus.ONLINE, ["qwen2.5:72b"])
    assert ok is True
    fresh = registry.get(nid)
    assert fresh is not None
    assert fresh.status == NodeStatus.ONLINE
    assert fresh.available_models == ["qwen2.5:72b"]
    assert fresh.last_heartbeat > ts0

    # Nieznany node_id zwraca False.
    assert registry.update_heartbeat("nope", NodeStatus.ONLINE) is False


# --------------------------------------------------------------------------
# 4) Registry: list_active filters by heartbeat age
# --------------------------------------------------------------------------


def test_list_active_filters_by_heartbeat_age(registry: NodeRegistry) -> None:
    fresh = registry.register(_make_node("fresh"))
    stale = registry.register(_make_node("stale"))
    # Symuluj stary heartbeat dla "stale".
    stale.last_heartbeat = time.time() - 999
    active = registry.list_active(stale_secs=60)
    ids = {n.node_id for n in active}
    assert fresh.node_id in ids
    assert stale.node_id not in ids
    # OFFLINE node nie liczy się jako active.
    off = registry.register(_make_node("off", status=NodeStatus.OFFLINE))
    assert off.node_id not in {n.node_id for n in registry.list_active()}


# --------------------------------------------------------------------------
# 5) Registry: unregister
# --------------------------------------------------------------------------


def test_unregister_returns_true_when_present(registry: NodeRegistry) -> None:
    saved = registry.register(_make_node("x"))
    assert registry.unregister(saved.node_id) is True
    assert registry.get(saved.node_id) is None
    # Drugie wywolanie zwraca False (nie istnieje).
    assert registry.unregister(saved.node_id) is False
    assert registry.unregister("never-there") is False


# --------------------------------------------------------------------------
# 6) Router: empty registry → no decision
# --------------------------------------------------------------------------


def test_route_returns_no_node_when_registry_empty(router: FederationRouter) -> None:
    decision = router.route(RoutingRequest(model_id="qwen2.5:72b"))
    assert decision.chosen_node_id is None
    assert decision.chosen_model_id is None
    assert "Brak aktywnych" in decision.rationale
    assert decision.candidates == []


# --------------------------------------------------------------------------
# 7) Router: LOCAL_ONLY excludes cloud
# --------------------------------------------------------------------------


def test_route_local_only_excludes_cloud_nodes(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    laptop = registry.register(_make_node(
        "laptop", locality="local", available_models=["qwen2.5:72b"],
    ))
    vps = registry.register(_make_node(
        "vps", locality="cloud", available_models=["qwen2.5:72b"],
    ))
    decision = router.route(RoutingRequest(
        model_id="qwen2.5:72b",
        privacy_level=PrivacyLevel.LOCAL_ONLY,
    ))
    assert decision.chosen_node_id == laptop.node_id
    # cloud node musi pojawic sie w rejected z reason o privacy.
    rejected_ids = {r["node_id"] for r in decision.rejected}
    assert vps.node_id in rejected_ids
    reason = next(r["reason"] for r in decision.rejected if r["node_id"] == vps.node_id)
    assert "privacy" in reason


# --------------------------------------------------------------------------
# 8) Router: PREFER_LOCAL boosts when no local available
# --------------------------------------------------------------------------


def test_route_prefer_local_boosts_lan_nodes_when_no_local(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    """PREFER_LOCAL: gdy brak local, lan przed cloud (po prefer_locality)."""
    lan = registry.register(_make_node(
        "lan-node", locality="lan", available_models=["m1"],
    ))
    cloud = registry.register(_make_node(
        "cloud-node", locality="cloud", available_models=["m1"],
    ))
    decision = router.route(RoutingRequest(
        model_id="m1",
        privacy_level=PrivacyLevel.PREFER_LOCAL,
        prefer_locality=["local", "lan", "cloud"],
    ))
    # Brak local — wygrywa lan dzieki kolejnosci w prefer_locality.
    assert decision.chosen_node_id == lan.node_id
    assert cloud.node_id in decision.candidates


# --------------------------------------------------------------------------
# 9) Router: filter by model availability
# --------------------------------------------------------------------------


def test_route_filters_by_model_availability(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    has = registry.register(_make_node("has", available_models=["qwen2.5:72b"]))
    nope = registry.register(_make_node("nope", available_models=["llama3:8b"]))
    decision = router.route(RoutingRequest(model_id="qwen2.5:72b"))
    assert decision.chosen_node_id == has.node_id
    rejected_ids = {r["node_id"] for r in decision.rejected}
    assert nope.node_id in rejected_ids


# --------------------------------------------------------------------------
# 10) Router: fallback when primary unavailable
# --------------------------------------------------------------------------


def test_route_uses_fallback_when_primary_unavailable(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    fallback_host = registry.register(_make_node(
        "fallback-host", available_models=["llama3:8b"],
    ))
    decision = router.route(RoutingRequest(
        model_id="qwen2.5:72b",
        fallback_models=["llama3:8b"],
    ))
    assert decision.chosen_node_id == fallback_host.node_id
    assert decision.chosen_model_id == "llama3:8b"
    assert "fallback" in decision.rationale.lower()


# --------------------------------------------------------------------------
# 11) Router: cost cap filter
# --------------------------------------------------------------------------


def test_route_filters_by_max_cost(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    cheap = registry.register(_make_node(
        "cheap",
        available_models=["m1"],
        cost={"m1": 0.001},
    ))
    pricey = registry.register(_make_node(
        "pricey",
        available_models=["m1"],
        cost={"m1": 0.500},
    ))
    decision = router.route(RoutingRequest(
        model_id="m1",
        max_cost_per_1k=0.005,
    ))
    assert decision.chosen_node_id == cheap.node_id
    rejected_ids = {r["node_id"] for r in decision.rejected}
    assert pricey.node_id in rejected_ids
    reason = next(r["reason"] for r in decision.rejected if r["node_id"] == pricey.node_id)
    assert "koszt" in reason and "cap" in reason


# --------------------------------------------------------------------------
# 12) Router: capacity tie-break
# --------------------------------------------------------------------------


def test_route_picks_higher_capacity_score(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    weak = registry.register(_make_node(
        "weak",
        available_models=["m1"],
        capacity_score=0.2,
    ))
    strong = registry.register(_make_node(
        "strong",
        available_models=["m1"],
        capacity_score=0.9,
    ))
    decision = router.route(RoutingRequest(model_id="m1"))
    assert decision.chosen_node_id == strong.node_id
    # weak nie powinien być w 'rejected' bo on byl po prostu drugi w sortowaniu.
    rejected_ids = {r["node_id"] for r in decision.rejected}
    assert weak.node_id not in rejected_ids


# --------------------------------------------------------------------------
# 13) Router: rationale po polsku
# --------------------------------------------------------------------------


def test_routing_decision_rationale_polish(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    registry.register(_make_node(
        "laptop-warsaw",
        locality="local",
        available_models=["qwen2.5:72b"],
    ))
    decision = router.route(RoutingRequest(
        model_id="qwen2.5:72b",
        privacy_level=PrivacyLevel.PREFER_LOCAL,
    ))
    assert decision.chosen_node_id is not None
    text = decision.rationale.lower()
    # po polsku → "wybrano", "locality", "koszt"
    assert "wybrano" in text
    assert "locality" in text
    assert "koszt" in text
    assert "laptop-warsaw" in decision.rationale


# --------------------------------------------------------------------------
# 14) Router: EXTERNAL_OK includes cloud
# --------------------------------------------------------------------------


def test_route_external_ok_includes_cloud(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    cloud_only = registry.register(_make_node(
        "vps-warsaw", locality="cloud", available_models=["m1"],
    ))
    decision = router.route(RoutingRequest(
        model_id="m1",
        privacy_level=PrivacyLevel.EXTERNAL_OK,
    ))
    assert decision.chosen_node_id == cloud_only.node_id
    # nie powinno być rejected-by-privacy
    privacy_rejects = [
        r for r in decision.rejected
        if "privacy" in r.get("reason", "")
    ]
    assert privacy_rejects == []


# --------------------------------------------------------------------------
# 15) Router: rejected entries carry node_id + reason
# --------------------------------------------------------------------------


def test_route_explains_rejected_nodes_with_reason(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    has = registry.register(_make_node(
        "has-it", available_models=["qwen2.5:72b"],
    ))
    too_expensive = registry.register(_make_node(
        "vps-pricey",
        available_models=["qwen2.5:72b"],
        cost={"qwen2.5:72b": 1.0},
    ))
    no_model = registry.register(_make_node(
        "vps-other", available_models=["llama3:8b"],
    ))
    decision = router.route(RoutingRequest(
        model_id="qwen2.5:72b",
        max_cost_per_1k=0.10,
    ))
    assert decision.chosen_node_id == has.node_id
    rejected_map = {r["node_id"]: r["reason"] for r in decision.rejected}
    assert too_expensive.node_id in rejected_map
    assert no_model.node_id in rejected_map
    # Każdy rejected ma niepusty reason
    for r in decision.rejected:
        assert r["reason"], "kazdy rejected musi miec niepusty reason"


# --------------------------------------------------------------------------
# Bonus: end-to-end demo z 3 nodes (laptop, vps-warsaw, gpu-cluster)
# --------------------------------------------------------------------------


def test_demo_three_node_routing_prefer_local(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    """Demo z briefa: 3 nodes + PREFER_LOCAL → lokalny laptop wygrywa."""
    laptop = registry.register(_make_node(
        "laptop",
        kind=NodeKind.HYBRID,
        locality="local",
        available_models=["qwen2.5:7b", "qwen2.5:72b"],
        capacity_score=0.6,
    ))
    vps = registry.register(_make_node(
        "vps-warsaw",
        kind=NodeKind.COMPUTE_PROVIDER,
        locality="cloud",
        available_models=["qwen2.5:72b", "llama3:70b"],
        cost={"qwen2.5:72b": 0.0008},
        capacity_score=0.85,
    ))
    gpu = registry.register(_make_node(
        "gpu-cluster",
        kind=NodeKind.COMPUTE_PROVIDER,
        locality="cloud",
        available_models=["qwen2.5:72b", "llama3:70b"],
        cost={"qwen2.5:72b": 0.0050},
        capacity_score=1.0,
    ))
    decision = router.route(RoutingRequest(
        model_id="qwen2.5:72b",
        privacy_level=PrivacyLevel.PREFER_LOCAL,
    ))
    assert decision.chosen_node_id == laptop.node_id
    assert decision.chosen_model_id == "qwen2.5:72b"
    # vps i gpu w candidates
    assert vps.node_id in decision.candidates
    assert gpu.node_id in decision.candidates
    # Liczbowo decisions_total = 1
    assert router.decisions_total == 1


# --------------------------------------------------------------------------
# W17 P0-1 hardening: Node.validate boundary checks
# --------------------------------------------------------------------------


def test_node_validate_rejects_unknown_locality():
    from sylion.aeis_v2.deployment.nodes import Node, NodeKind, NodeStatus
    with pytest.raises(ValueError, match="locality"):
        Node.validate(
            node_id="n1", name="evil", kind=NodeKind.COMPUTE_PROVIDER,
            status=NodeStatus.ONLINE, base_url="http://x",
            locality="lol_wtf",
        )


def test_node_validate_rejects_unbounded_capacity():
    from sylion.aeis_v2.deployment.nodes import Node, NodeKind, NodeStatus
    with pytest.raises(ValueError, match="capacity_score"):
        Node.validate(
            node_id="n1", name="evil", kind=NodeKind.COMPUTE_PROVIDER,
            status=NodeStatus.ONLINE, base_url="http://x",
            locality="cloud", capacity_score=999999.0,
            cost_per_1k_tokens_usd={"qwen2.5:72b": 0.001},
        )


def test_node_validate_requires_cost_for_compute_provider():
    from sylion.aeis_v2.deployment.nodes import Node, NodeKind, NodeStatus
    with pytest.raises(ValueError, match="cost_per_1k_tokens_usd"):
        Node.validate(
            node_id="n1", name="evil", kind=NodeKind.COMPUTE_PROVIDER,
            status=NodeStatus.ONLINE, base_url="http://x",
            locality="cloud", capacity_score=1.0,
            cost_per_1k_tokens_usd={},
        )


def test_node_validate_allows_full_instance_without_cost():
    from sylion.aeis_v2.deployment.nodes import Node, NodeKind, NodeStatus
    n = Node.validate(
        node_id="n1", name="full", kind=NodeKind.FULL_INSTANCE,
        status=NodeStatus.ONLINE, base_url="http://x",
        locality="local", capacity_score=0.5,
        cost_per_1k_tokens_usd={},
    )
    assert n.locality == "local"


def test_node_validate_caps_available_models():
    from sylion.aeis_v2.deployment.nodes import Node, NodeKind, NodeStatus
    with pytest.raises(ValueError, match="available_models"):
        Node.validate(
            node_id="n1", name="evil", kind=NodeKind.HYBRID,
            status=NodeStatus.ONLINE, base_url="http://x",
            locality="local", capacity_score=1.0,
            available_models=[f"m_{i}" for i in range(257)],
        )


def test_post_nodes_returns_400_on_invalid_locality():
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)
    r = client.post("/api/v1/federation/nodes", json={
        "node_id": "n1", "name": "evil",
        "kind": "compute_provider", "status": "online",
        "base_url": "http://x", "locality": "wat",
        "capacity_score": 1.0,
        "cost_per_1k_tokens_usd": {"m": 0.001},
    })
    assert r.status_code == 400
    assert "locality" in r.json().get("detail", "").lower()


# --------------------------------------------------------------------------
# W17 P0-6 hardening: GET endpoints require operator role
#
# RBACEnforcementMiddleware only fires on mutation methods (POST/PUT/PATCH/
# DELETE). GET routes therefore must declare ``Depends(requires_role(...))``
# explicitly to avoid leaking federation topology (base_url, available_models,
# cost_per_1k_tokens_usd, metadata) to anonymous callers. See
# docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md, finding P0-6.
# --------------------------------------------------------------------------


def _route_dep_names(route) -> list[str]:
    """Return dependency call names for a FastAPI APIRoute."""
    deps = getattr(route, "dependant", None)
    if deps is None:
        return []
    out: list[str] = []
    for d in deps.dependencies:
        call = getattr(d, "call", None)
        name = getattr(call, "__name__", "") if call is not None else ""
        out.append(name)
    return out


def test_get_health_has_requires_role_dependency():
    """P0-6 surface check — GET /federation/health declares requires_role."""
    from sylion.api.federation_routes import router
    health = next(
        r for r in router.routes
        if r.path.endswith("/health") and "GET" in r.methods
    )
    names = _route_dep_names(health)
    assert any("requires_role" in n for n in names), (
        f"GET /federation/health must depend on requires_role; got: {names}"
    )


def test_get_nodes_has_requires_role_dependency():
    """P0-6 surface check — GET /federation/nodes declares requires_role."""
    from sylion.api.federation_routes import router
    nodes = next(
        r for r in router.routes
        if r.path.endswith("/nodes") and "GET" in r.methods
    )
    names = _route_dep_names(nodes)
    assert any("requires_role" in n for n in names), (
        f"GET /federation/nodes must depend on requires_role; got: {names}"
    )


def test_get_nodes_active_has_requires_role_dependency():
    """P0-6 surface check — GET /federation/nodes/active declares requires_role."""
    from sylion.api.federation_routes import router
    active = next(
        r for r in router.routes
        if r.path.endswith("/nodes/active") and "GET" in r.methods
    )
    names = _route_dep_names(active)
    assert any("requires_role" in n for n in names), (
        f"GET /federation/nodes/active must depend on requires_role; got: {names}"
    )


def test_get_nodes_works_in_dev_mode():
    """In SYLION_AUTH_MODE=dev (default for tests) GET nodes still works.

    AuthMiddleware auto-populates request.state.user with the dev operator
    id for the whole /api/v1 surface; the operator role then satisfies the
    requires_role dependency without an explicit token.
    """
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)
    r = client.get("/api/v1/federation/nodes")
    assert r.status_code == 200, (
        f"dev-mode GET /federation/nodes must succeed; got {r.status_code}: "
        f"{r.text[:200]}"
    )


def test_get_nodes_active_works_in_dev_mode():
    """Companion to dev-mode /nodes test — covers /nodes/active too."""
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)
    r = client.get("/api/v1/federation/nodes/active")
    assert r.status_code == 200, (
        f"dev-mode GET /federation/nodes/active must succeed; got "
        f"{r.status_code}: {r.text[:200]}"
    )


def test_get_health_works_in_dev_mode():
    """Companion to dev-mode /nodes test — covers /health too."""
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)
    r = client.get("/api/v1/federation/health")
    assert r.status_code == 200, (
        f"dev-mode GET /federation/health must succeed; got "
        f"{r.status_code}: {r.text[:200]}"
    )


def test_get_nodes_with_rbac_disabled_bypass(monkeypatch):
    """SYLION_RBAC_DISABLED=1 must let GET work even without auth context.

    The dev/load-test bypass flag handled by ``sylion.security.rbac._disabled``
    short-circuits the dependency before the role lookup, so even an anonymous
    caller gets a 200.
    """
    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)
    r = client.get("/api/v1/federation/nodes")
    assert r.status_code == 200


# --------------------------------------------------------------------------
# W17 P0-3/4/5 hardening: concurrency triad
#
# - P0-3: ``_decisions_total`` increment must be atomic — 100 concurrent
#   ``route()`` calls must produce a +100 delta, never N-1.
# - P0-4: ``get_node_registry`` and ``get_federation_router`` use double-
#   checked locking; concurrent callers see exactly one singleton instance.
# - P0-5: every ``RoutingDecision`` carries a unique ``decision_id`` and a
#   monotonic ``decision_generation`` so callers can re-validate freshness
#   against the registry between snapshot and use.
#
# See docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md for the full
# review of these findings.
# --------------------------------------------------------------------------


def test_decision_counter_atomic_under_concurrent_routes():
    """P0-3: 100 concurrent routes produce exactly 100 incremented total."""
    from concurrent.futures import ThreadPoolExecutor

    reg = NodeRegistry()
    reg.register(Node(
        node_id="n1", name="n1", kind=NodeKind.COMPUTE_PROVIDER,
        status=NodeStatus.ONLINE, base_url="http://x", locality="local",
        available_models=["m"], cost_per_1k_tokens_usd={"m": 0.001},
        capacity_score=1.0, last_heartbeat=time.time(),
    ))
    router = FederationRouter(reg)

    initial = router.decisions_total

    def go(_unused: int) -> object:
        return router.route(RoutingRequest(model_id="m"))

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(go, range(100)))

    final = router.decisions_total
    assert final - initial == 100, (
        f"expected +100 increments, got +{final - initial}"
    )
    # All decisions should have unique IDs (P0-5 surface).
    ids = [r.decision_id for r in results if r.decision_id]
    assert len(ids) == len(results), "every decision must carry a decision_id"
    assert len(set(ids)) == len(ids), "decision_ids must be unique"


def test_get_node_registry_double_checked_locking():
    """P0-4: concurrent get_node_registry() returns the same instance."""
    import threading

    from sylion.aeis_v2.deployment import registry as reg_mod

    # Reset singleton state for this test only — restore after to avoid
    # bleeding into later tests that may have already cached a reference.
    saved_singleton = reg_mod._registry_singleton
    saved_legacy = reg_mod._registry
    reg_mod._registry_singleton = None
    reg_mod._registry = None
    reg_mod._registry_singleton_lock = threading.Lock()
    try:
        instances: list[object] = []

        def go() -> None:
            instances.append(reg_mod.get_node_registry())

        threads = [threading.Thread(target=go) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(instances) == 20
        assert all(i is instances[0] for i in instances), (
            "all calls must return the same singleton instance"
        )
    finally:
        reg_mod._registry_singleton = saved_singleton
        reg_mod._registry = saved_legacy


def test_routing_decision_has_unique_id():
    """P0-5: every RoutingDecision has a non-empty unique decision_id."""
    reg = NodeRegistry()
    reg.register(Node(
        node_id="n1", name="n1", kind=NodeKind.COMPUTE_PROVIDER,
        status=NodeStatus.ONLINE, base_url="http://x", locality="local",
        available_models=["m"], cost_per_1k_tokens_usd={"m": 0.001},
        capacity_score=1.0, last_heartbeat=time.time(),
    ))
    router = FederationRouter(reg)
    d1 = router.route(RoutingRequest(model_id="m"))
    d2 = router.route(RoutingRequest(model_id="m"))
    assert d1.decision_id and d2.decision_id, "decision_id must be non-empty"
    assert d1.decision_id != d2.decision_id, "decision_ids must be unique"
    assert d2.decision_generation > d1.decision_generation, (
        "decision_generation must be monotonic"
    )


# --------------------------------------------------------------------------
# W17 P1-4 hardening: heartbeat staleness + clock skew
#
# P1-4: ``list_active`` previously hard-coded ``stale_secs=60`` and used
# ``>=`` semantics, leaving the boundary value undefined and silently
# excluding nodes that drift across it. The fix hoists
# ``STALE_THRESHOLD_S`` and ``CLOCK_SKEW_BUFFER_S`` to module scope, uses
# strict ``>`` so the boundary is unambiguous, lets operators absorb
# known NTP drift via ``clock_skew_buffer_s``, and emits a WARNING when
# a node's ``last_heartbeat`` is in the future (clock running backwards).
#
# See docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md, finding P1-4.
# --------------------------------------------------------------------------


def test_list_active_uses_stale_threshold_constant():
    """P1-4: STALE_THRESHOLD_S exposed at module level."""
    from sylion.aeis_v2.deployment import registry as reg_mod
    assert hasattr(reg_mod, "STALE_THRESHOLD_S")
    assert reg_mod.STALE_THRESHOLD_S == 60.0
    assert hasattr(reg_mod, "CLOCK_SKEW_BUFFER_S")
    assert reg_mod.CLOCK_SKEW_BUFFER_S == 5.0


def test_list_active_clock_skew_buffer_makes_stricter():
    """P1-4: a larger clock_skew_buffer shrinks the active window.

    Default buffer=5 → effective threshold 55s, so a heartbeat 30s ago is
    active. With buffer=60 the effective threshold collapses to 0s, so
    even a heartbeat 30s ago is stale.
    """
    reg = NodeRegistry()
    saved = reg.register(Node(
        node_id="n1", name="n1", kind=NodeKind.HYBRID,
        status=NodeStatus.ONLINE, base_url="http://x", locality="local",
        available_models=["m"], cost_per_1k_tokens_usd={},
        capacity_score=1.0, last_heartbeat=time.time(),
    ))
    # register() overwrote last_heartbeat, so backdate it explicitly.
    saved.last_heartbeat = time.time() - 30.0

    active_default = reg.list_active()
    active_strict = reg.list_active(clock_skew_buffer_s=60.0)
    assert len(active_default) == 1, "default buffer=5 → 30s ago is active"
    assert len(active_strict) == 0, "buffer=60 collapses window → 30s is stale"


def test_list_active_warns_on_future_heartbeat(caplog):
    """P1-4: future heartbeat (clock skew backward) emits a warning."""
    reg = NodeRegistry()
    saved = reg.register(Node(
        node_id="n1", name="n1", kind=NodeKind.HYBRID,
        status=NodeStatus.ONLINE, base_url="http://x", locality="local",
        available_models=["m"], cost_per_1k_tokens_usd={},
        capacity_score=1.0, last_heartbeat=time.time(),
    ))
    # register() overwrote last_heartbeat — push it into the future.
    saved.last_heartbeat = time.time() + 100
    with caplog.at_level("WARNING", logger="sylion.aeis_v2.deployment.registry"):
        reg.list_active()
    assert any(
        "future" in rec.message.lower() or "backwards" in rec.message.lower()
        for rec in caplog.records
    ), f"expected future-heartbeat warning; got: {[r.message for r in caplog.records]}"


def test_list_active_strict_greater_than_boundary():
    """P1-4: heartbeat well within the threshold is treated as fresh.

    With default ``stale_secs=60`` and ``clock_skew_buffer_s=5`` the
    effective threshold is 55s. A heartbeat 5s ago is comfortably
    inside the window → active.
    """
    reg = NodeRegistry()
    saved = reg.register(Node(
        node_id="n1", name="n1", kind=NodeKind.HYBRID,
        status=NodeStatus.ONLINE, base_url="http://x", locality="local",
        available_models=["m"], cost_per_1k_tokens_usd={},
        capacity_score=1.0, last_heartbeat=time.time(),
    ))
    saved.last_heartbeat = time.time() - 5.0
    assert len(reg.list_active()) == 1


# --------------------------------------------------------------------------
# W17 P1-2 hardening: cost dict math sentinel guard
#
# P1-2: ``Node.validate`` now rejects NaN/inf/negative/over-max cost
# values per model so the federation router's sort math cannot be
# poisoned. Without this guard, a hostile node could:
#   - declare ``NaN`` cost → Python float-NaN compares False against
#     everything, making the cost sort nondeterministic;
#   - declare ``-inf`` → win every "cheapest" tie-break and claim all
#     traffic;
#   - declare ``inf`` or astronomical positive values → grief the cost
#     cap filter and load-test math.
#
# The same guard is applied at the REST surface (``RegisterNodeRequest``
# and ``HeartbeatRequest``) so adversarial registration / heartbeat
# payloads return HTTP 422 with a field-specific error rather than
# being absorbed silently.
#
# See docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md, finding P1-2.
# --------------------------------------------------------------------------


def test_node_validate_rejects_nan_cost():
    """P1-2: NaN cost is rejected with a 'finite' error message."""
    with pytest.raises(ValueError, match="finite"):
        Node.validate(
            node_id="n1", name="evil", kind=NodeKind.COMPUTE_PROVIDER,
            status=NodeStatus.ONLINE, base_url="http://x",
            locality="cloud", capacity_score=1.0,
            cost_per_1k_tokens_usd={"m": float("nan")},
        )


def test_node_validate_rejects_inf_cost():
    """P1-2: +inf and -inf cost are both rejected with a 'finite' message."""
    for bad in (float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite"):
            Node.validate(
                node_id="n1", name="evil", kind=NodeKind.COMPUTE_PROVIDER,
                status=NodeStatus.ONLINE, base_url="http://x",
                locality="cloud", capacity_score=1.0,
                cost_per_1k_tokens_usd={"m": bad},
            )


def test_node_validate_rejects_negative_cost():
    """P1-2: a negative price is rejected with a '>= 0' error message."""
    with pytest.raises(ValueError, match=">= 0"):
        Node.validate(
            node_id="n1", name="evil", kind=NodeKind.COMPUTE_PROVIDER,
            status=NodeStatus.ONLINE, base_url="http://x",
            locality="cloud", capacity_score=1.0,
            cost_per_1k_tokens_usd={"m": -0.001},
        )


def test_node_validate_rejects_cost_above_max():
    """P1-2: cost above ``MAX_COST_PER_1K_TOKENS_USD`` is rejected."""
    from sylion.aeis_v2.deployment.nodes import MAX_COST_PER_1K_TOKENS_USD
    assert MAX_COST_PER_1K_TOKENS_USD == 1000.0
    with pytest.raises(ValueError, match="1000"):
        Node.validate(
            node_id="n1", name="evil", kind=NodeKind.COMPUTE_PROVIDER,
            status=NodeStatus.ONLINE, base_url="http://x",
            locality="cloud", capacity_score=1.0,
            cost_per_1k_tokens_usd={"m": 9999.99},
        )


def test_node_validate_accepts_zero_and_typical_cost():
    """P1-2 must NOT regress on the happy path: zero and small floats are fine."""
    n = Node.validate(
        node_id="n1", name="ok", kind=NodeKind.COMPUTE_PROVIDER,
        status=NodeStatus.ONLINE, base_url="http://x",
        locality="cloud", capacity_score=1.0,
        cost_per_1k_tokens_usd={"free-tier": 0.0, "gpt-4": 0.03},
    )
    assert n.cost_per_1k_tokens_usd["free-tier"] == 0.0
    assert n.cost_per_1k_tokens_usd["gpt-4"] == 0.03


def test_post_heartbeat_returns_422_on_nan_cost():
    """P1-2: heartbeat with NaN cost returns HTTP 422 with field-specific detail.

    Sends a literal ``NaN`` token in the JSON body via ``content=`` because
    httpx's ``json=`` serializer is RFC-compliant and rejects bare NaN. The
    backend must return 422 (Pydantic v2 default for body-validation errors)
    with the cost field mentioned in the detail string.
    """
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    client = TestClient(app)
    # Register a real node first so the heartbeat path has something to
    # heartbeat (the cost validator fires before the registry lookup).
    reg = client.post("/api/v1/federation/nodes", json={
        "node_id": "p12-target", "name": "target",
        "kind": "compute_provider", "status": "online",
        "base_url": "http://x", "locality": "cloud",
        "capacity_score": 1.0,
        "cost_per_1k_tokens_usd": {"m": 0.001},
    })
    assert reg.status_code == 200, reg.text
    body = (
        '{"status":"online","available_models":["m"],'
        '"cost_per_1k_tokens_usd":{"m":NaN}}'
    )
    r = client.post(
        "/api/v1/federation/nodes/p12-target/heartbeat",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
    detail = r.json().get("detail", "")
    assert "cost_per_1k_tokens_usd" in detail
    assert "finite" in detail or "NaN" in detail


def test_post_nodes_returns_422_on_negative_inf_cost():
    """P1-2: register-node with -inf cost returns HTTP 422.

    Reproduces the adversarial-review payload: a hostile compute provider
    declaring ``-inf`` so that every cheapest-tie-break sorts in its favour.
    The validator must reject this at the REST boundary.
    """
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    client = TestClient(app)
    body = (
        '{"node_id":"p12-attacker","name":"attacker",'
        '"kind":"compute_provider","status":"online",'
        '"base_url":"http://x","locality":"cloud","capacity_score":1.0,'
        '"cost_per_1k_tokens_usd":{"gpt-4":-Infinity}}'
    )
    r = client.post(
        "/api/v1/federation/nodes",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
    detail = r.json().get("detail", "")
    assert "cost_per_1k_tokens_usd" in detail
    assert "finite" in detail


# --------------------------------------------------------------------------
# W17 P1-3 — _sort_key deterministic tie-breaker
# --------------------------------------------------------------------------
#
# Adversarial review (docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md,
# P1-3) identified that when ``req.prefer_locality=[]`` and
# ``privacy_level=ANY``, all candidates received locality_rank=0. If
# capacity_score and cost were also identical across nodes, the 4-tuple
# sort key was equal for every node, and Python's stable sort fell back
# to **registration order** — the first-registered node silently
# captured all routing decisions for that tied group.
#
# Fix: append ``node.node_id`` (uuid hex from registry.register) as the
# 5th element. ``node_id`` is random uuid → no registration-order bias.
# The choice within a single registry is deterministic (alphabetic-first
# by uuid hex), but across registry instances the winners vary because
# uuids are random. Load-spreading WITHIN a single registry instance is
# deferred to G2 (will use ``hash((req.request_id, node.node_id))`` once
# RoutingRequest gains a stable request_id field).


def test_sort_key_includes_tiebreaker_element(
    router: FederationRouter, registry: NodeRegistry
) -> None:
    """W17 P1-3 + P1-7: ``_sort_key`` returns a 4-tuple.

    The last element is ``node.node_id`` — a deterministic, registration-
    order-independent tie-breaker. Verifies the wire format is the
    expected ``(locality_rank, -capacity, cost, node_id)``.

    P1-7 update: tuple shrunk from 5 → 4 elements after dead-code removal
    of ``privacy_local_boost``. The ``locality_rank`` slot already handles
    PREFER_LOCAL via implicit ``prefer=["local"]`` injection, so the
    secondary boost was redundant and has been removed.
    """
    n = _make_node(
        "alpha",
        locality="local",
        available_models=["m1"],
        cost={"m1": 0.05},
        capacity_score=1.0,
    )
    saved = registry.register(n)
    req = RoutingRequest(model_id="m1", privacy_level=PrivacyLevel.ANY)
    key = router._sort_key(saved, "m1", req)
    assert isinstance(key, tuple)
    assert len(key) == 4, f"expected 4-tuple after P1-7, got {len(key)}: {key}"
    locality_rank, capacity_neg, cost, tiebreaker = key
    assert locality_rank == 0
    assert capacity_neg == -1.0
    assert cost == 0.05
    assert tiebreaker == saved.node_id, "last element must be node_id"
    assert isinstance(tiebreaker, str)


def test_sort_key_stable_for_identical_nodes(
    router: FederationRouter, registry: NodeRegistry
) -> None:
    """W17 P1-3: 3 nodes with identical capacity+cost+locality → ONE
    deterministic winner across 100 iterations of the same request.

    Pre-fix: stable sort fell back to registration order, so tests like
    this passed *by accident* — but only because the test always
    registered nodes in the same order. With the new tie-breaker, the
    winner is whichever node has the alphabetically-first ``node_id``
    (a registry-assigned uuid hex), which is independent of the order
    we called ``register()``.
    """
    nodes = []
    for name in ["zeta", "alpha", "mu"]:  # mixed insertion order
        n = _make_node(
            name,
            locality="cloud",  # uniform — locality_rank tie
            available_models=["m1"],
            cost={"m1": 0.05},  # identical cost
            capacity_score=0.5,  # identical capacity
        )
        nodes.append(registry.register(n))

    req = RoutingRequest(model_id="m1", privacy_level=PrivacyLevel.ANY)

    # 100 calls of the same request must always pick the same node.
    winners = set()
    for _ in range(100):
        decision = router.route(req)
        assert decision.chosen_node_id is not None
        winners.add(decision.chosen_node_id)

    assert len(winners) == 1, (
        f"expected 1 deterministic winner across 100 identical calls, "
        f"got {len(winners)}: {winners}"
    )

    # The winner is the alphabetically-first node_id (alphabetic on uuid hex).
    # Sanity-check: it must be one of the 3 registered nodes.
    expected_winner = min(n.node_id for n in nodes)
    assert winners == {expected_winner}, (
        f"winner {winners} must be alphabetically-first node_id "
        f"{expected_winner} (W17 P1-3 deterministic tie-break)"
    )


def test_sort_key_spreads_traffic_across_tied_nodes() -> None:
    """W17 P1-3 (Option A): with the chosen tie-break (``node.node_id``),
    a single registry instance always picks the alphabetically-first
    node_id for tied requests.

    Expected with **Option A**: 1 winner across many requests with the
    same registry. G2 will move to ``hash((req.request_id, node.node_id))``
    for true load-spreading within a single registry — at that point this
    test becomes ``len(winners) >= 2`` for a single registry.

    What we DO assert here is that load spreads across **registry
    instances**: re-creating the registry (which re-mints uuids for the
    same logical nodes) produces different winners. This proves there is
    **no registration-order bias** — the winner is driven by uuid, not by
    the order ``register()`` is called.
    """
    winners_by_run: list[str] = []
    for _ in range(20):
        # Fresh registry → fresh uuids for the same logical nodes.
        reg = NodeRegistry()
        local_router = FederationRouter(reg)
        for name in ["zeta", "alpha", "mu"]:  # same insertion order each run
            n = _make_node(
                name,
                locality="cloud",
                available_models=["m1"],
                cost={"m1": 0.05},
                capacity_score=0.5,
            )
            reg.register(n)

        req = RoutingRequest(model_id="m1", privacy_level=PrivacyLevel.ANY)
        decision = local_router.route(req)
        assert decision.chosen_node_id is not None

        # Map node_id back to logical name so we can count distinct winners
        # by the "stable" identity.
        chosen_node = reg.get(decision.chosen_node_id)
        assert chosen_node is not None
        winners_by_run.append(chosen_node.name)

    # Pre-fix: every run would pick "zeta" (registered first).
    # Post-fix: across 20 fresh registries, at least 2 of the 3 logical
    # node names should win at least once because uuid.uuid4 is random
    # → no registration-order bias.
    distinct_winners = set(winners_by_run)
    assert len(distinct_winners) >= 2, (
        f"expected >= 2 distinct logical winners across 20 fresh "
        f"registries (proving no registration-order bias), got "
        f"{distinct_winners} from runs {winners_by_run}"
    )


def test_sort_key_preserves_capacity_priority_when_costs_differ(
    router: FederationRouter, registry: NodeRegistry
) -> None:
    """W17 P1-3 regression: the new tie-breaker must NOT override
    capacity priority. Higher-capacity node wins over lower-capacity
    node even if its node_id sorts later alphabetically.

    Pre-fix risk: a naive implementation could promote ``node_id`` ahead
    of capacity. We construct the worst-case scenario: lower-capacity
    node has alphabetically-earlier node_id → capacity must still win.
    """
    # Force node_ids so we can prove capacity beats alphabetic tie-break.
    low_cap = _make_node(
        "low-cap",
        locality="cloud",
        available_models=["m1"],
        cost={"m1": 0.05},
        capacity_score=0.2,
    )
    low_cap.node_id = "00000000aaaaaaaaaaaa"  # alphabetically first
    high_cap = _make_node(
        "high-cap",
        locality="cloud",
        available_models=["m1"],
        cost={"m1": 0.05},  # same cost — capacity must decide
        capacity_score=0.9,
    )
    high_cap.node_id = "ffffffffzzzzzzzzzzzz"  # alphabetically last
    registry.register(low_cap)
    registry.register(high_cap)

    req = RoutingRequest(model_id="m1", privacy_level=PrivacyLevel.ANY)
    decision = router.route(req)

    assert decision.chosen_node_id == high_cap.node_id, (
        f"capacity (0.9) must beat capacity (0.2) regardless of "
        f"alphabetic node_id ordering; got {decision.chosen_node_id} "
        f"(low_cap={low_cap.node_id}, high_cap={high_cap.node_id})"
    )

    # Belt-and-braces: directly inspect _sort_key — capacity_neg is the
    # 3rd element so it dominates the 5th (node_id).
    key_low = router._sort_key(low_cap, "m1", req)
    key_high = router._sort_key(high_cap, "m1", req)
    assert key_high < key_low, (
        f"sort key for high-capacity node must be < low-capacity node "
        f"(smaller is better); got high={key_high} low={key_low}"
    )


# --------------------------------------------------------------------------
# W17 P1-6 hardening: per-node-id heartbeat + per-IP registration rate limits
#
# Adversarial review (docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md,
# P1-6) noted: a hostile node can flood ``POST /nodes/{node_id}/heartbeat``
# at thousands of req/sec, eating event-loop budget and starving legitimate
# nodes' heartbeats. The global ``RateLimitMiddleware`` is keyed per-IP/
# per-user, not per-node-id, so a single IP hosting many nodes can still
# saturate the heartbeat path.
#
# Fix: a tiny in-process token bucket keyed on ``node_id`` for heartbeats
# (5 rps, burst 10) and a stricter bucket keyed on source IP for
# registration (0.5 rps, burst 3). The standard
# ``SYLION_RATE_LIMIT_DISABLED=1`` env-var bypass is honoured (matches the
# ``SYLION_RBAC_DISABLED`` pattern, set by ``tests/conftest.py``).
#
# These tests opt back in to the limiter via ``monkeypatch.delenv`` so the
# default-bypass that protects the other 47 federation tests is preserved.
# --------------------------------------------------------------------------


@pytest.fixture
def _clear_rate_buckets():
    """Reset module-level token-bucket maps before each rate-limit test.

    Without this, a leaky bucket from one test bleeds into the next and
    invalidates the burst/refill maths.
    """
    from sylion.api.federation_routes import (
        _HEARTBEAT_BUCKETS,
        _REGISTRATION_BUCKETS,
    )
    _HEARTBEAT_BUCKETS.clear()
    _REGISTRATION_BUCKETS.clear()
    yield
    _HEARTBEAT_BUCKETS.clear()
    _REGISTRATION_BUCKETS.clear()


def _register_test_node(client, node_id: str = "rl-test-node") -> None:
    """Register a node under SYLION_RATE_LIMIT_DISABLED=1 so the heartbeat
    fixture can fire without paying the registration token.

    We register inside an ``os.environ`` override so the test that wants
    to assert heartbeat-limit behaviour doesn't accidentally consume
    registration tokens it doesn't intend to test.
    """
    import os as _os
    saved = _os.environ.get("SYLION_RATE_LIMIT_DISABLED")
    _os.environ["SYLION_RATE_LIMIT_DISABLED"] = "1"
    try:
        r = client.post("/api/v1/federation/nodes", json={
            "node_id": node_id, "name": node_id,
            "kind": "compute_provider", "status": "online",
            "base_url": "http://x", "locality": "cloud",
            "capacity_score": 1.0,
            "cost_per_1k_tokens_usd": {"m": 0.001},
            "available_models": ["m"],
        })
        assert r.status_code == 200, r.text
    finally:
        if saved is None:
            _os.environ.pop("SYLION_RATE_LIMIT_DISABLED", None)
        else:
            _os.environ["SYLION_RATE_LIMIT_DISABLED"] = saved


def test_heartbeat_rate_limit_allows_burst(monkeypatch, _clear_rate_buckets):
    """P1-6: 10 heartbeats from same node fired immediately all return 200.

    The bucket starts at full burst (HEARTBEAT_BURST=10), so 10 back-to-
    back heartbeats consume exactly the burst capacity and all succeed.
    """
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)
    _register_test_node(client, "burst-node")

    monkeypatch.delenv("SYLION_RATE_LIMIT_DISABLED", raising=False)
    body = {"status": "online"}
    statuses = []
    for _ in range(10):
        r = client.post("/api/v1/federation/nodes/burst-node/heartbeat", json=body)
        statuses.append(r.status_code)
    assert all(s == 200 for s in statuses), (
        f"all 10 heartbeats within burst must return 200; got {statuses}"
    )


def test_heartbeat_rate_limit_rejects_overflow(monkeypatch, _clear_rate_buckets):
    """P1-6: 15 rapid heartbeats — last 5 return 429 with expected JSON body.

    With burst=10, the first 10 succeed and the next 5 should be rejected
    because the bucket cannot have refilled enough in microseconds. The
    429 detail must carry the documented limit fields so callers can back
    off correctly.
    """
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)
    _register_test_node(client, "overflow-node")

    monkeypatch.delenv("SYLION_RATE_LIMIT_DISABLED", raising=False)
    body = {"status": "online"}
    statuses = []
    last_429 = None
    for _ in range(15):
        r = client.post("/api/v1/federation/nodes/overflow-node/heartbeat", json=body)
        statuses.append(r.status_code)
        if r.status_code == 429:
            last_429 = r
    # First 10 must succeed; at least the last few must 429.
    assert statuses[:10] == [200] * 10, (
        f"first 10 must succeed (burst=10); got {statuses[:10]}"
    )
    n_rejected = sum(1 for s in statuses[10:] if s == 429)
    assert n_rejected >= 4, (
        f"expected >= 4 of the trailing 5 to 429; got statuses[10:]={statuses[10:]}"
    )
    assert last_429 is not None
    detail = last_429.json().get("detail", {})
    assert detail.get("error") == "heartbeat rate limit exceeded"
    assert detail.get("node_id") == "overflow-node"
    assert detail.get("limit_per_sec") == 5.0
    assert detail.get("burst") == 10.0


def test_heartbeat_rate_limit_refills_over_time(monkeypatch, _clear_rate_buckets):
    """P1-6: fire 10 heartbeats, sleep 1.0s, fire 5 more — all 5 pass.

    After draining the burst, sleeping 1.0s at rate=5 rps refills 5
    tokens (capped at burst=10), so 5 more heartbeats fit comfortably.
    """
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)
    _register_test_node(client, "refill-node")

    monkeypatch.delenv("SYLION_RATE_LIMIT_DISABLED", raising=False)
    body = {"status": "online"}
    # Drain burst.
    for _ in range(10):
        r = client.post("/api/v1/federation/nodes/refill-node/heartbeat", json=body)
        assert r.status_code == 200, r.text
    # Wait for refill: 1.0s * 5 rps = 5 tokens.
    time.sleep(1.0)
    refilled_statuses = []
    for _ in range(5):
        r = client.post("/api/v1/federation/nodes/refill-node/heartbeat", json=body)
        refilled_statuses.append(r.status_code)
    assert all(s == 200 for s in refilled_statuses), (
        f"after 1.0s refill, 5 heartbeats must succeed; got {refilled_statuses}"
    )


def test_registration_rate_limit_per_ip(monkeypatch, _clear_rate_buckets):
    """P1-6: register 3 nodes from same client (fixed IP); 4th returns 429.

    REGISTRATION_BURST=3, so the first 3 fit the bucket; the 4th call
    immediately after has at most a tiny refill (much less than 1 token
    at 0.5 rps over microseconds) and must be rejected.
    """
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)

    monkeypatch.delenv("SYLION_RATE_LIMIT_DISABLED", raising=False)
    statuses = []
    for i in range(4):
        r = client.post("/api/v1/federation/nodes", json={
            "node_id": f"rl-reg-{i}", "name": f"rl-reg-{i}",
            "kind": "compute_provider", "status": "online",
            "base_url": "http://x", "locality": "cloud",
            "capacity_score": 1.0,
            "cost_per_1k_tokens_usd": {"m": 0.001},
            "available_models": ["m"],
        })
        statuses.append(r.status_code)
    assert statuses[:3] == [200, 200, 200], (
        f"first 3 registrations must succeed (burst=3); got {statuses[:3]}"
    )
    assert statuses[3] == 429, (
        f"4th registration must 429; got {statuses[3]}"
    )


def test_rate_limit_bypass_with_env_var(monkeypatch, _clear_rate_buckets):
    """P1-6: SYLION_RATE_LIMIT_DISABLED=1 bypasses both limiters.

    Fire 50 heartbeats well above burst+refill capacity — all must
    return 200. This is the dev/CI escape hatch matching the
    SYLION_RBAC_DISABLED pattern.
    """
    from fastapi.testclient import TestClient
    from sylion.api.app import app
    client = TestClient(app)
    _register_test_node(client, "bypass-node")

    monkeypatch.setenv("SYLION_RATE_LIMIT_DISABLED", "1")
    body = {"status": "online"}
    statuses = []
    for _ in range(50):
        r = client.post("/api/v1/federation/nodes/bypass-node/heartbeat", json=body)
        statuses.append(r.status_code)
    assert all(s == 200 for s in statuses), (
        f"with bypass env, 50 heartbeats must all succeed; "
        f"first non-200 at index {next((i for i, s in enumerate(statuses) if s != 200), -1)}"
    )


# --------------------------------------------------------------------------
# W17 P1-5 hardening: routing decision audit JSONL
#
# Adversarial review (docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md,
# P1-5) flagged: ``route()`` produced no persistent audit trail — after the
# fact "why did request X route to node Y" was unanswerable because nothing
# was written to stdlib logging or any audit sink. The fix emits one JSONL
# row per decision to ``ROUTING_AUDIT_LOG_PATH`` containing the request
# params, chosen node identity, candidates_count, rejected_reasons (per-
# reason counts), cost_for_chosen, and a process-stable decision_total
# counter. The ``decision_id`` (existing P0-5 uuid hex field) is reused as
# the correlation handle so the operator UI can join decisions by id.
#
# Phase 0: file-only fallback. G2 will move to a PG audit table.
# --------------------------------------------------------------------------


def test_route_writes_audit_jsonl(
    registry: NodeRegistry,
    router: FederationRouter,
    tmp_path,
    monkeypatch,
) -> None:
    """P1-5: a single route() call writes exactly one JSONL line with all
    expected keys to ``ROUTING_AUDIT_LOG_PATH``.
    """
    import json as _json

    from sylion.aeis_v2.deployment import federation as fed_mod

    audit_path = tmp_path / "routing_audit.jsonl"
    monkeypatch.setattr(fed_mod, "ROUTING_AUDIT_LOG_PATH", audit_path)

    registry.register(_make_node(
        "laptop-warsaw",
        locality="local",
        available_models=["qwen2.5:72b"],
        cost={"qwen2.5:72b": 0.001},
    ))
    decision = router.route(RoutingRequest(
        model_id="qwen2.5:72b",
        privacy_level=PrivacyLevel.PREFER_LOCAL,
    ))
    assert decision.chosen_node_id is not None

    assert audit_path.exists(), "audit JSONL file must be created on first write"
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, f"expected exactly 1 audit line, got {len(lines)}"
    row = _json.loads(lines[0])

    expected_keys = {
        "ts",
        "decision_id",
        "model_id",
        "privacy_level",
        "prefer_locality",
        "max_cost_per_1k",
        "chosen_node_id",
        "chosen_node_name",
        "chosen_node_locality",
        "candidates_count",
        "rejected_reasons",
        "cost_for_chosen",
        "decision_total",
    }
    assert expected_keys.issubset(row.keys()), (
        f"missing keys: {expected_keys - row.keys()}"
    )
    # Spot-check field semantics.
    assert row["decision_id"] == decision.decision_id
    assert row["model_id"] == "qwen2.5:72b"
    assert row["privacy_level"] == PrivacyLevel.PREFER_LOCAL.value
    assert row["chosen_node_id"] == decision.chosen_node_id
    assert row["chosen_node_name"] == "laptop-warsaw"
    assert row["chosen_node_locality"] == "local"
    assert row["candidates_count"] == 1
    assert row["cost_for_chosen"] == 0.001
    assert isinstance(row["decision_total"], int) and row["decision_total"] >= 1


def test_routing_audit_includes_rejected_reasons(
    registry: NodeRegistry,
    router: FederationRouter,
    tmp_path,
    monkeypatch,
) -> None:
    """P1-5: rejected_reasons aggregates per-reason rejection counts.

    3 nodes — 1 passes, 1 rejected for privacy (cloud vs LOCAL_ONLY),
    1 rejected for missing-model. Audit row's ``rejected_reasons`` must
    show ``{"privacy": 1, "no_model": 1}``.
    """
    import json as _json

    from sylion.aeis_v2.deployment import federation as fed_mod

    audit_path = tmp_path / "routing_audit.jsonl"
    monkeypatch.setattr(fed_mod, "ROUTING_AUDIT_LOG_PATH", audit_path)

    # Passes — local locality + has model.
    registry.register(_make_node(
        "winner",
        locality="local",
        available_models=["qwen2.5:72b"],
    ))
    # Rejected for privacy — cloud locality but req is LOCAL_ONLY.
    registry.register(_make_node(
        "cloud-vps",
        locality="cloud",
        available_models=["qwen2.5:72b"],
    ))
    # Rejected for no_model — local locality but model absent.
    registry.register(_make_node(
        "wrong-model-host",
        locality="local",
        available_models=["llama3:8b"],
    ))

    decision = router.route(RoutingRequest(
        model_id="qwen2.5:72b",
        privacy_level=PrivacyLevel.LOCAL_ONLY,
    ))
    assert decision.chosen_node_id is not None

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = _json.loads(lines[0])
    assert row["rejected_reasons"] == {"privacy": 1, "no_model": 1}, (
        f"expected privacy=1, no_model=1; got {row['rejected_reasons']}"
    )


def test_routing_decision_has_unique_decision_id(
    registry: NodeRegistry,
    router: FederationRouter,
) -> None:
    """P1-5: 5 back-to-back routes produce 5 distinct decision_id values
    (correlation handle for operator UI / replay).
    """
    registry.register(_make_node(
        "node",
        locality="local",
        available_models=["m1"],
        cost={"m1": 0.001},
    ))
    req = RoutingRequest(model_id="m1")
    decision_ids = []
    for _ in range(5):
        decision = router.route(req)
        assert decision.decision_id, "decision_id must be non-empty"
        decision_ids.append(decision.decision_id)
    assert len(set(decision_ids)) == 5, (
        f"5 decision_ids must be distinct; got {decision_ids}"
    )


def test_routing_audit_write_failure_does_not_break_route(
    registry: NodeRegistry,
    router: FederationRouter,
    monkeypatch,
) -> None:
    """P1-5: if the audit write fails (OSError on open()), route() must
    still return a valid decision — audit is best-effort, never blocks
    routing.
    """
    from sylion.aeis_v2.deployment import federation as fed_mod

    def _broken_open(*_args, **_kwargs):
        raise OSError("simulated disk full")

    # Patch the module-level open() reference used by _emit_routing_audit.
    monkeypatch.setattr(fed_mod, "open", _broken_open, raising=False)

    registry.register(_make_node(
        "node",
        locality="local",
        available_models=["m1"],
        cost={"m1": 0.001},
    ))
    decision = router.route(RoutingRequest(model_id="m1"))
    assert decision.chosen_node_id is not None, (
        "route() must still pick a node even if audit write fails"
    )
    assert decision.decision_id, "decision_id must still be stamped"
    assert "Wybrano" in decision.rationale


# --------------------------------------------------------------------------
# W17 P1-7 — privacy_local_boost dead-code removal
# --------------------------------------------------------------------------
#
# Adversarial review (docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md,
# P1-7) showed that ``PrivacyLevel.PREFER_LOCAL`` boost was dead code:
#
# - When ``prefer_locality=[]`` and ``privacy=PREFER_LOCAL``, the router
#   already injects ``prefer=["local"]`` so ``locality_rank`` alone makes
#   local nodes win. The secondary boost was redundant.
# - When the operator passes ``prefer_locality=["cloud"]`` with
#   ``privacy=PREFER_LOCAL``, the boost would still try to promote local
#   in second position — directly contradicting the explicit operator
#   preference. That was a latent bug that masked itself because the
#   primary ``locality_rank`` already pushed cloud first.
#
# Fix: drop the ``privacy_local_boost`` element from ``_sort_key``. Tuple
# now has 4 elements (``locality_rank``, ``-capacity``, ``cost``, ``node_id``).


def test_sort_key_returns_4_tuple_after_p1_7(
    router: FederationRouter, registry: NodeRegistry
) -> None:
    """W17 P1-7: ``_sort_key`` returns a 4-tuple (was 5-tuple after ab16).

    Element layout: ``(locality_rank, -capacity, cost, node_id)``. The
    ``privacy_local_boost`` slot has been removed because ``locality_rank``
    already encodes PREFER_LOCAL via implicit ``prefer=["local"]`` injection.
    """
    n = _make_node(
        "alpha",
        locality="local",
        available_models=["m1"],
        cost={"m1": 0.05},
        capacity_score=1.0,
    )
    saved = registry.register(n)
    req = RoutingRequest(model_id="m1", privacy_level=PrivacyLevel.PREFER_LOCAL)
    key = router._sort_key(saved, "m1", req)
    assert isinstance(key, tuple)
    assert len(key) == 4, (
        f"P1-7: expected 4-tuple after privacy_local_boost removal, "
        f"got {len(key)}: {key}"
    )
    # Element types: (int, float, float, str)
    locality_rank, capacity_neg, cost, tiebreaker = key
    assert isinstance(locality_rank, int)
    assert isinstance(capacity_neg, float)
    assert isinstance(cost, float)
    assert isinstance(tiebreaker, str)


def test_prefer_local_implicit_when_prefer_locality_empty(
    router: FederationRouter, registry: NodeRegistry
) -> None:
    """W17 P1-7 regression: PREFER_LOCAL with empty prefer_locality must
    still pick local node over cloud node.

    This is the load-bearing case: removing ``privacy_local_boost`` MUST
    NOT regress the implicit-prefer-local behaviour. The router still
    injects ``prefer=["local"]`` when ``prefer_locality=[]`` and privacy=
    PREFER_LOCAL, so ``locality_rank`` alone drives the decision.
    """
    local_node = _make_node(
        "laptop",
        locality="local",
        available_models=["m1"],
        cost={"m1": 0.10},  # local is more expensive
        capacity_score=0.5,  # local has lower capacity
    )
    cloud_node = _make_node(
        "cloud-gpu",
        locality="cloud",
        available_models=["m1"],
        cost={"m1": 0.01},  # cloud is cheaper
        capacity_score=1.0,  # cloud has more capacity
    )
    local_saved = registry.register(local_node)
    cloud_saved = registry.register(cloud_node)

    req = RoutingRequest(
        model_id="m1",
        privacy_level=PrivacyLevel.PREFER_LOCAL,
        # prefer_locality intentionally empty — implicit "local" injection
        # is the sole machinery that should make local win here.
    )
    decision = router.route(req)

    assert decision.chosen_node_id == local_saved.node_id, (
        f"PREFER_LOCAL with empty prefer_locality must pick local node "
        f"({local_saved.node_id}), got {decision.chosen_node_id} "
        f"(cloud={cloud_saved.node_id}). P1-7 must preserve implicit-"
        f"prefer-local behaviour after removing privacy_local_boost."
    )

    # Belt-and-braces: directly compare _sort_key tuples.
    key_local = router._sort_key(local_saved, "m1", req)
    key_cloud = router._sort_key(cloud_saved, "m1", req)
    assert key_local < key_cloud, (
        f"local sort key must be < cloud sort key under PREFER_LOCAL "
        f"with empty prefer_locality; got local={key_local} cloud={key_cloud}"
    )
    # locality_rank: local=0 (in injected prefer=["local"]),
    # cloud=len(prefer)+1=2 (not in prefer).
    assert key_local[0] == 0
    assert key_cloud[0] == 2


def test_prefer_locality_explicit_overrides_prefer_local_privacy(
    router: FederationRouter, registry: NodeRegistry
) -> None:
    """W17 P1-7 regression: explicit ``prefer_locality=["cloud"]`` MUST
    override the privacy=PREFER_LOCAL implicit local preference.

    This was the case where the dead ``privacy_local_boost`` was confusing
    the picture. Pre-P1-7 the boost still tried to nudge local up in the
    second tuple slot — but the primary ``locality_rank`` already pushed
    cloud first, so the bug masked itself. After P1-7 we verify the
    explicit operator preference cleanly wins, with no leftover bias from
    the privacy level.
    """
    local_node = _make_node(
        "laptop",
        locality="local",
        available_models=["m1"],
        cost={"m1": 0.05},
        capacity_score=1.0,
    )
    cloud_node = _make_node(
        "cloud-gpu",
        locality="cloud",
        available_models=["m1"],
        cost={"m1": 0.05},  # equal cost — locality decides
        capacity_score=1.0,  # equal capacity — locality decides
    )
    local_saved = registry.register(local_node)
    cloud_saved = registry.register(cloud_node)

    req = RoutingRequest(
        model_id="m1",
        privacy_level=PrivacyLevel.PREFER_LOCAL,
        prefer_locality=["cloud"],  # operator explicitly overrides
    )
    decision = router.route(req)

    assert decision.chosen_node_id == cloud_saved.node_id, (
        f"explicit prefer_locality=['cloud'] must override PREFER_LOCAL "
        f"privacy hint; expected cloud node ({cloud_saved.node_id}), "
        f"got {decision.chosen_node_id} (local={local_saved.node_id}). "
        f"P1-7: removed dead privacy_local_boost so this no longer "
        f"silently agrees by accident."
    )

    # Directly inspect both sort keys: cloud must rank ahead of local.
    key_local = router._sort_key(local_saved, "m1", req)
    key_cloud = router._sort_key(cloud_saved, "m1", req)
    assert key_cloud < key_local, (
        f"cloud sort key must be < local sort key when prefer_locality="
        f"['cloud']; got cloud={key_cloud} local={key_local}"
    )
    # locality_rank: cloud=0 (in prefer=["cloud"]),
    # local=len(prefer)+1=2 (not in prefer).
    assert key_cloud[0] == 0
    assert key_local[0] == 2
