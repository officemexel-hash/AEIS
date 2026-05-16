"""W17 G1 deploy_agent — node lifecycle + heartbeat loop.

PDF §5.4 G1 — *"Each SYLION node runs a deploy_agent which on start
registers in central plane and every 30s sends heartbeat with its
available_models + capacity_score."*

Kazdy node SYLION (lokalnie laptop, VPS, klient factory) uruchamia
jednego ``DeployAgent`` ktory:

1. Na start: rejestruje sie w central plane (``POST /api/v1/federation/nodes``).
2. Co ``heartbeat_interval_s`` (default 30s): heartbeat + report
   ``available_models`` + ``capacity_score``.
3. Na shutdown: graceful unregister (best-effort, ``DELETE``).

Phase 0: in-process loop using ``asyncio``. Brak persystencji tokenow,
brak retry exponential backoffu — gdy register failuje, agent retryuje
przy nastepnym ticku heartbeatu. G2 dodaje:

- Persistent registration tokens (auth via ``api_key`` body).
- Cross-process restart resilience (state w W15 OSDK).
- Compose z W17 deployment lifecycle (register on systemd start).
- Provider-side ``available_models`` query (W11 abstraction zamiast
  hardcoded ``ai-providers/local-models/installed`` URL-a).

Spawn convention:

.. code-block:: python

    cfg = DeployAgentConfig(central_url="http://central:8000", node_name="laptop-w")
    agent = DeployAgent(cfg)
    task = asyncio.create_task(agent.loop())
    # ... pozniej
    agent.stop()
    await task
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

import httpx

from sylion.aeis_v2.deployment.nodes import NodeKind, NodeStatus

log = logging.getLogger(__name__)


@dataclass
class DeployAgentConfig:
    """Konfiguracja ``DeployAgent``-a (jedna instancja per proces)."""

    central_url: str = "http://127.0.0.1:8000"
    node_name: str = ""                     # autogen z uuid jesli pusty
    node_kind: NodeKind = NodeKind.HYBRID
    locality: str = "local"                 # local / lan / cloud
    heartbeat_interval_s: float = 30.0
    api_key: str | None = None              # bearer token gdy strict mode
    capacity_score: float = 1.0
    extra_tags: list[str] = field(default_factory=list)


class DeployAgent:
    """Agent ktory rejestruje + heartbeatuje z central federation plane.

    Single-node, single-event-loop. Spawnowany przez ``asyncio.create_task``.
    Idempotentny — wielokrotne ``register()`` ze statycznym ``node_id``-em
    (po first-call) skutkuje replacem w registry.
    """

    def __init__(self, cfg: DeployAgentConfig) -> None:
        self.cfg = cfg
        self.node_id: str | None = None
        self._stop = asyncio.Event()
        self._registered = False

    @property
    def headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            h["Authorization"] = f"Bearer {self.cfg.api_key}"
        return h

    async def register(self) -> str:
        """Zarejestruj ten node w central plane. Zwraca ``node_id``.

        Body mapuje na ``RegisterNodeRequest`` w
        ``sylion/api/federation_routes.py``. ``node_id`` generujemy
        po stronie agenta (uuid hex) zeby kolejne register-y po
        restarcie centrali mogly zachowac tozsamosc node-a.
        """
        node_name = self.cfg.node_name or f"node-{uuid.uuid4().hex[:8]}"
        models = await self._discover_models()
        kind_value = (
            self.cfg.node_kind.value
            if hasattr(self.cfg.node_kind, "value")
            else str(self.cfg.node_kind)
        )
        status_value = (
            NodeStatus.ONLINE.value
            if hasattr(NodeStatus.ONLINE, "value")
            else "online"
        )
        payload = {
            "node_id": uuid.uuid4().hex,
            "name": node_name,
            "kind": kind_value,
            "status": status_value,
            "base_url": self.cfg.central_url,
            "locality": self.cfg.locality,
            "tags": list(self.cfg.extra_tags),
            "available_models": models,
            "cost_per_1k_tokens_usd": {},
            "capacity_score": self.cfg.capacity_score,
        }
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                f"{self.cfg.central_url}/api/v1/federation/nodes",
                json=payload, headers=self.headers,
            )
            r.raise_for_status()
            body = r.json() if hasattr(r, "json") else {}
            self.node_id = (
                body.get("node_id") if isinstance(body, dict) else None
            ) or payload["node_id"]
            self._registered = True
            log.info(
                "deploy_agent: registered node_id=%s name=%s",
                self.node_id, node_name,
            )
            return self.node_id

    async def _discover_models(self) -> list[str]:
        """Best-effort: zwroc liste modeli ktore ten node hostuje.

        Phase 0: pyta lokalnego Ollama (przez ``ai-providers/local-models/installed``
        endpoint na ``central_url``); w razie 404/connect error zwraca [].
        G2 zintegruje sie z W11 provider abstraction (multi-provider
        merge: Ollama + LM Studio + vLLM + llama.cpp).
        """
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(
                    f"{self.cfg.central_url}/api/v1/ai-providers/local-models/installed"
                )
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        return [
                            m.get("name", "") for m in data
                            if isinstance(m, dict) and m.get("name")
                        ]
                    if isinstance(data, dict):
                        return [
                            m.get("name", "") for m in data.get("models", [])
                            if isinstance(m, dict) and m.get("name")
                        ]
        except Exception as exc:  # noqa: BLE001
            log.debug(
                "deploy_agent: _discover_models failed (%s) — empty list",
                exc,
            )
        return []

    async def heartbeat_once(self) -> bool:
        """Wyslij pojedynczy heartbeat. Zwroc ``True`` gdy 200.

        No-op (zwraca ``False``) gdy agent nie jest zarejestrowany —
        loop powinien w takim wypadku najpierw sprobowac register-a.
        """
        if not self.node_id or not self._registered:
            return False
        models = await self._discover_models()
        status_value = (
            NodeStatus.ONLINE.value
            if hasattr(NodeStatus.ONLINE, "value")
            else "online"
        )
        payload = {
            "status": status_value,
            "available_models": models,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.post(
                    f"{self.cfg.central_url}/api/v1/federation/nodes/{self.node_id}/heartbeat",
                    json=payload, headers=self.headers,
                )
                return r.status_code == 200
        except Exception as exc:  # noqa: BLE001
            log.warning("deploy_agent: heartbeat failed (%s)", exc)
            return False

    async def loop(self) -> None:
        """Glowna petla agenta — biegnie az do ``stop()``.

        Sekwencja:

        1. Pierwsze register (best-effort — gdy fail, kolejny tick
           heartbeatu sprobuje ponownie).
        2. Co ``heartbeat_interval_s`` budzimy sie i:
           - Jesli nie zarejestrowani → register.
           - Jesli zarejestrowani → heartbeat_once.
        3. Na ``stop()``: best-effort unregister + exit.
        """
        try:
            await self.register()
        except Exception as exc:  # noqa: BLE001
            log.error(
                "deploy_agent: register failed (%s) — agent will retry on next interval",
                exc,
            )
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self.cfg.heartbeat_interval_s,
                )
            except asyncio.TimeoutError:
                pass
            if self._stop.is_set():
                break
            if not self._registered:
                try:
                    await self.register()
                except Exception:  # noqa: BLE001
                    continue
            await self.heartbeat_once()
        await self._unregister_best_effort()

    async def _unregister_best_effort(self) -> None:
        """Graceful unregister — bledy logujemy ale nie propagujemy."""
        if not self.node_id:
            return
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                await c.delete(
                    f"{self.cfg.central_url}/api/v1/federation/nodes/{self.node_id}",
                    headers=self.headers,
                )
            log.info("deploy_agent: unregistered node_id=%s", self.node_id)
        except Exception as exc:  # noqa: BLE001
            log.debug(
                "deploy_agent: unregister failed (%s) — ignoring",
                exc,
            )

    def stop(self) -> None:
        """Sygnal do glownej petli zeby zakonczyla i zrobila unregister."""
        self._stop.set()
