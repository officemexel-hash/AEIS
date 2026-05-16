"""W17 Deployment Plane — Compute Provider Federation (Phase 0).

PDF §8.4 — *"Hybrid Local + Central Deployment Architecture"*:

Trzy typy nodes (federated mesh):

- **Full instance** — pełen AEIS (worker + dashboard + LLM lokalnie).
- **Compute provider** — bare-metal/VPS który TYLKO hostuje modele
  (Ollama, vLLM, LM Studio); nie ma własnego AEIS.
- **Hybrid** — pełen AEIS + exposed local models (np. laptop deweloperski
  który dzieli się qwen2.5:7b z resztą federacji).

Federation routing — dowolny task wymagający np. ``qwen2.5:72b``
zostanie zrouterowany do najtańszego compute providera, który ma model
online. Privacy levels per task pozwalają operatorowi tagować zadania
jako *"must run locally"* / *"OK external"* / *"OK any provider"*.

Phase 0 deliverables:

- ``nodes.py``      — model ``Node`` + enumy (``NodeKind``,
  ``NodeStatus``, ``PrivacyLevel``).
- ``registry.py``   — thread-safe in-memory ``NodeRegistry`` + singleton
  ``get_node_registry()``.
- ``federation.py`` — ``FederationRouter`` z deterministic routing
  algorithm (privacy → model availability → cost → locality → capacity).

REST entry point: ``sylion/api/federation_routes.py``.

Charter docelowy: ``docs/v2/charters/W17_deployment_federation.md`` (G2).

Status: Phase 0 (in-memory only). Persystencja przez W15 OSDK pojawi się
w fazie G2 — wtedy ``Node`` stanie się ``ontology_type``-em w PG, a
heartbeaty zaczną zasilać ``federation_node_state`` event log.
"""
from __future__ import annotations

from sylion.aeis_v2.deployment.nodes import (
    Node,
    NodeKind,
    NodeStatus,
    PrivacyLevel,
)
from sylion.aeis_v2.deployment.registry import (
    NodeRegistry,
    get_node_registry,
)
from sylion.aeis_v2.deployment.federation import (
    FederationRouter,
    RoutingDecision,
    RoutingRequest,
    get_federation_router,
)
from sylion.aeis_v2.deployment.agent import (
    DeployAgent,
    DeployAgentConfig,
)

__all__ = [
    "Node",
    "NodeKind",
    "NodeStatus",
    "PrivacyLevel",
    "NodeRegistry",
    "get_node_registry",
    "FederationRouter",
    "RoutingDecision",
    "RoutingRequest",
    "get_federation_router",
    "DeployAgent",
    "DeployAgentConfig",
]
