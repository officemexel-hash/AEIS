"""W17 G1 deploy_agent — Phase 0 unit tests.

Stub ``httpx.AsyncClient`` przez ``monkeypatch`` zeby uniknac realnych
sockets. Pattern zgodny z ``tests/providers/test_local_providers.py``:
korzystamy z ``asyncio.run()`` zamiast pytest-asyncio markerow zeby
test suite dzialal na vanilla pytest.

Pokrycie:

1. ``test_register_posts_to_central``
2. ``test_heartbeat_skipped_when_not_registered``
3. ``test_heartbeat_returns_true_on_200``
4. ``test_unregister_called_on_stop``
5. ``test_discover_models_handles_unreachable_gracefully``
6. ``test_register_payload_shape_matches_register_node_request`` (bonus)
7. ``test_loop_retries_register_on_failure`` (bonus)
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from sylion.aeis_v2.deployment.agent import DeployAgent, DeployAgentConfig
from sylion.aeis_v2.deployment.nodes import NodeKind


def _run(coro):
    """Drive an async coroutine to completion in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Stub httpx.AsyncClient — minimal subset uzywany przez agenta
# ---------------------------------------------------------------------------


class _StubResponse:
    def __init__(self, status_code: int = 200, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self) -> Any:
        return self._payload

    @property
    def text(self) -> str:
        return str(self._payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# Zapisuje wszystkie wywolania ktore agent wykona.
_CALLS: list[dict[str, Any]] = []
# Routing tabela: (method, url_suffix) → _StubResponse | callable
_ROUTES: dict[tuple[str, str], Any] = {}


def _route(
    method: str,
    url: str,
    json_payload: dict | None = None,
) -> _StubResponse:
    _CALLS.append({"method": method, "url": url, "json": json_payload})
    for (m, suffix), response in _ROUTES.items():
        if m == method and url.endswith(suffix):
            if callable(response):
                return response(url, json_payload)
            return response
    # Default 404 — pomaga zauwazyc nieoczekiwane requesty.
    return _StubResponse(404, {"error": f"no stub for {method} {url}"})


class _StubAsyncClient:
    def __init__(self, *_, **__) -> None:
        self.last_url: str | None = None

    async def __aenter__(self) -> "_StubAsyncClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def get(self, url: str, headers: dict | None = None, **_) -> _StubResponse:
        self.last_url = url
        return _route("GET", url)

    async def post(
        self, url: str, json: dict | None = None, headers: dict | None = None, **_
    ) -> _StubResponse:
        self.last_url = url
        return _route("POST", url, json)

    async def delete(self, url: str, headers: dict | None = None, **_) -> _StubResponse:
        self.last_url = url
        return _route("DELETE", url)


@pytest.fixture
def stub_httpx(monkeypatch):
    """Patch ``httpx.AsyncClient`` w module ``agent``-a + reset routing."""
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)
    _ROUTES.clear()
    _CALLS.clear()
    yield {"routes": _ROUTES, "calls": _CALLS}
    _ROUTES.clear()
    _CALLS.clear()


# ---------------------------------------------------------------------------
# 1) register POST-uje do central plane
# ---------------------------------------------------------------------------


def test_register_posts_to_central(stub_httpx) -> None:
    """``register()`` POST-uje na ``/api/v1/federation/nodes`` z node_id w body."""

    def register_handler(_url: str, payload: dict | None) -> _StubResponse:
        # Echo back the node_id sent by the agent.
        return _StubResponse(200, {"node_id": (payload or {}).get("node_id")})

    stub_httpx["routes"][("POST", "/api/v1/federation/nodes")] = register_handler
    # Discovery endpoint — pusta lista modeli.
    stub_httpx["routes"][
        ("GET", "/api/v1/ai-providers/local-models/installed")
    ] = _StubResponse(200, {"models": []})

    agent = DeployAgent(DeployAgentConfig(
        central_url="http://central:8000",
        node_name="laptop-warsaw",
        node_kind=NodeKind.HYBRID,
        locality="local",
        capacity_score=0.7,
        extra_tags=["dev"],
    ))
    nid = _run(agent.register())

    assert nid, "register() musi zwrocic node_id"
    assert agent._registered is True
    # Sprawdz ze byl POST z odpowiednim body.
    posts = [c for c in stub_httpx["calls"] if c["method"] == "POST"]
    assert any(c["url"].endswith("/api/v1/federation/nodes") for c in posts)
    body = next(
        c["json"] for c in posts
        if c["url"].endswith("/api/v1/federation/nodes")
    )
    assert body["name"] == "laptop-warsaw"
    assert body["kind"] == "hybrid"
    assert body["locality"] == "local"
    assert body["capacity_score"] == 0.7
    assert body["tags"] == ["dev"]
    assert "node_id" in body and len(body["node_id"]) == 32  # uuid hex


# ---------------------------------------------------------------------------
# 2) heartbeat skipped when not registered
# ---------------------------------------------------------------------------


def test_heartbeat_skipped_when_not_registered(stub_httpx) -> None:
    """``heartbeat_once`` zwraca False gdy ``_registered=False`` (no HTTP call)."""
    agent = DeployAgent(DeployAgentConfig(central_url="http://central:8000"))
    ok = _run(agent.heartbeat_once())
    assert ok is False
    # Zaden POST nie powinien byc wykonany.
    posts = [c for c in stub_httpx["calls"] if c["method"] == "POST"]
    assert posts == [], "heartbeat nie powinien wysylac zadnego POST-a"


# ---------------------------------------------------------------------------
# 3) heartbeat zwraca True na 200
# ---------------------------------------------------------------------------


def test_heartbeat_returns_true_on_200(stub_httpx) -> None:
    """``heartbeat_once`` zwraca True gdy central plane odpowiedzial 200."""
    stub_httpx["routes"][
        ("POST", "/api/v1/federation/nodes")
    ] = _StubResponse(200, {"node_id": "abc123"})
    stub_httpx["routes"][
        ("GET", "/api/v1/ai-providers/local-models/installed")
    ] = _StubResponse(200, {"models": [{"name": "qwen2.5:7b"}]})
    stub_httpx["routes"][
        ("POST", "/api/v1/federation/nodes/abc123/heartbeat")
    ] = _StubResponse(200, {"ok": True})

    agent = DeployAgent(DeployAgentConfig(central_url="http://central:8000"))
    _run(agent.register())
    assert agent.node_id == "abc123"
    ok = _run(agent.heartbeat_once())
    assert ok is True

    # Heartbeat body musi zawierac status + available_models.
    hb_calls = [
        c for c in stub_httpx["calls"]
        if c["method"] == "POST" and "/heartbeat" in c["url"]
    ]
    assert len(hb_calls) == 1
    body = hb_calls[0]["json"]
    assert body["status"] == "online"
    assert body["available_models"] == ["qwen2.5:7b"]


# ---------------------------------------------------------------------------
# 4) unregister wolany przy stop()
# ---------------------------------------------------------------------------


def test_unregister_called_on_stop(stub_httpx) -> None:
    """Po ``stop()`` loop wykonuje DELETE /nodes/{node_id} (best-effort)."""
    stub_httpx["routes"][
        ("POST", "/api/v1/federation/nodes")
    ] = _StubResponse(200, {"node_id": "node-xyz"})
    stub_httpx["routes"][
        ("GET", "/api/v1/ai-providers/local-models/installed")
    ] = _StubResponse(200, {"models": []})
    stub_httpx["routes"][
        ("POST", "/api/v1/federation/nodes/node-xyz/heartbeat")
    ] = _StubResponse(200, {"ok": True})
    stub_httpx["routes"][
        ("DELETE", "/api/v1/federation/nodes/node-xyz")
    ] = _StubResponse(200, {"ok": True, "node_id": "node-xyz"})

    async def _exercise() -> None:
        agent = DeployAgent(DeployAgentConfig(
            central_url="http://central:8000",
            heartbeat_interval_s=10.0,  # tak duzo, ze nie zdazy sie ticknac
        ))
        task = asyncio.create_task(agent.loop())
        # Daj loop-owi ticknac raz: register sie wykona, potem wait_for stop.
        await asyncio.sleep(0.05)
        agent.stop()
        await asyncio.wait_for(task, timeout=2.0)

    _run(_exercise())

    deletes = [c for c in stub_httpx["calls"] if c["method"] == "DELETE"]
    assert len(deletes) == 1
    assert deletes[0]["url"].endswith("/api/v1/federation/nodes/node-xyz")


# ---------------------------------------------------------------------------
# 5) discover_models toleruje brak central plane
# ---------------------------------------------------------------------------


def test_discover_models_handles_unreachable_gracefully(
    monkeypatch, stub_httpx
) -> None:
    """Gdy ``GET /local-models/installed`` rzuci ConnectionError → [] zwracane."""

    class _Boom(_StubAsyncClient):
        async def get(self, *_a, **_kw):
            raise ConnectionError("central plane down")

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _Boom)

    agent = DeployAgent(DeployAgentConfig(central_url="http://central:8000"))
    out = _run(agent._discover_models())
    assert out == []


# ---------------------------------------------------------------------------
# 6) Bonus: payload shape kompatybilny z RegisterNodeRequest
# ---------------------------------------------------------------------------


def test_register_payload_shape_matches_register_node_request(
    stub_httpx,
) -> None:
    """register payload musi byc valid dla ``RegisterNodeRequest`` (FastAPI)."""
    stub_httpx["routes"][
        ("POST", "/api/v1/federation/nodes")
    ] = _StubResponse(200, {"node_id": "n1"})
    stub_httpx["routes"][
        ("GET", "/api/v1/ai-providers/local-models/installed")
    ] = _StubResponse(200, [])

    agent = DeployAgent(DeployAgentConfig(
        central_url="http://x",
        node_name="vps-warsaw-01",
        node_kind=NodeKind.COMPUTE_PROVIDER,
        locality="cloud",
    ))
    _run(agent.register())

    body = next(
        c["json"] for c in stub_httpx["calls"]
        if c["method"] == "POST" and c["url"].endswith("/api/v1/federation/nodes")
    )
    # Wszystkie wymagane fieldy obecne i prawidlowe typy.
    for required in (
        "node_id", "name", "kind", "status", "base_url",
        "locality", "tags", "available_models",
        "cost_per_1k_tokens_usd", "capacity_score",
    ):
        assert required in body, f"brakuje pola '{required}' w register payload"
    assert isinstance(body["tags"], list)
    assert isinstance(body["available_models"], list)
    assert isinstance(body["cost_per_1k_tokens_usd"], dict)
    assert body["kind"] == "compute_provider"


# ---------------------------------------------------------------------------
# 7) Bonus: loop retryuje register gdy pierwszy raz failuje
# ---------------------------------------------------------------------------


def test_loop_retries_register_on_failure(stub_httpx) -> None:
    """Gdy pierwszy register rzuci, ``loop`` retryuje przy kolejnym ticku."""
    attempts = {"n": 0}

    def register_handler(_url: str, _payload: dict | None) -> _StubResponse:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return _StubResponse(500, {"error": "boom"})  # first time fails
        return _StubResponse(200, {"node_id": "retry-1"})

    stub_httpx["routes"][("POST", "/api/v1/federation/nodes")] = register_handler
    stub_httpx["routes"][
        ("GET", "/api/v1/ai-providers/local-models/installed")
    ] = _StubResponse(200, [])
    stub_httpx["routes"][
        ("POST", "/api/v1/federation/nodes/retry-1/heartbeat")
    ] = _StubResponse(200, {"ok": True})
    stub_httpx["routes"][
        ("DELETE", "/api/v1/federation/nodes/retry-1")
    ] = _StubResponse(200, {"ok": True})

    captured: dict[str, DeployAgent] = {}

    async def _exercise() -> None:
        agent = DeployAgent(DeployAgentConfig(
            central_url="http://central:8000",
            heartbeat_interval_s=0.05,  # szybki tick zeby test sie nie ciagnal
        ))
        captured["agent"] = agent
        task = asyncio.create_task(agent.loop())
        # Czekamy na 2 ticki: pierwszy register fail, drugi retry → success.
        await asyncio.sleep(0.25)
        agent.stop()
        await asyncio.wait_for(task, timeout=2.0)

    _run(_exercise())

    assert attempts["n"] >= 2, "register powinno byc wywolane co najmniej 2x"
    assert captured["agent"].node_id == "retry-1"
