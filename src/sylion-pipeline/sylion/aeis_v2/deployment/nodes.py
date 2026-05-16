"""W17 Federation — Node model + enums.

PDF §8.4 — kanoniczna typologia trzech rodzajów nodes w mesh-u:

- ``FULL_INSTANCE`` — komplet AEIS (worker, dashboard, lokalne LLM).
- ``COMPUTE_PROVIDER`` — bare-metal/VPS hostujący wyłącznie modele
  (Ollama / vLLM / LM Studio); nie biorący udziału w decyzjach.
- ``HYBRID`` — AEIS + exposed local models (np. laptop developerski).

``PrivacyLevel`` opisuje *gdzie* dany task wolno wykonać. Federation
router wykorzystuje tę wartość jako pierwszy filtr listy kandydatów —
przed kosztem, capacity i availability.

``NodeStatus`` to bieżący snapshot zdrowia. Heartbeat ustawia status na
``ONLINE`` i odświeża ``last_heartbeat``; brak heartbeatu przez
> stale_secs (default 60s) automatycznie deklasyfikuje node z
``list_active`` (nie zmienia statusu — tylko wyklucza z routingu).

Phase 0 — ``dataclass``-y bez ORM, in-memory. Persystencja w G2 przez
W15 OSDK (``ontology_type: federation_node``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# W17 P0-1 hardening: bounded whitelists for boundary validation.
LOCALITY_WHITELIST = frozenset({"local", "lan", "cloud", "edge"})
MAX_AVAILABLE_MODELS = 256

# W17 P1-2 hardening: math sentinel guard against NaN/inf/negative cost
# poisoning. ``Node.cost_per_1k_tokens_usd`` feeds into ``FederationRouter``
# sort math; Python's float-NaN compares False against everything, which
# makes the sort nondeterministic, and ``-inf`` would let a hostile node
# claim every "cheapest" tie-break. The upper bound rejects "$10M per 1k
# tokens" griefing — no real-world model is that expensive, so any value
# above 1000 USD/1k is almost certainly accidental or adversarial.
MAX_COST_PER_1K_TOKENS_USD = 1000.0


class NodeKind(str, Enum):
    """Trzy typy nodes w federacji (PDF §8.4)."""

    FULL_INSTANCE = "full_instance"        # pełen AEIS, może być compute też
    COMPUTE_PROVIDER = "compute_provider"  # tylko serwuje modele LLM
    HYBRID = "hybrid"                      # pełen AEIS + exposed local models


class NodeStatus(str, Enum):
    """Status node-a w federacji."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class PrivacyLevel(str, Enum):
    """Polityka prywatności / lokalności wykonania zadania.

    PDF §8.4: *"Privacy levels per task — tagged 'must run locally' /
    'OK external' / 'OK any provider'."*
    """

    LOCAL_ONLY = "local_only"      # task musi run locally (np. dane PII)
    PREFER_LOCAL = "prefer_local"  # lokalne dostają boost, ale fallback OK
    EXTERNAL_OK = "external_ok"    # cloud OK, ale local też w grze
    ANY = "any"                    # cokolwiek — najtańszy/najbliższy wygrywa


@dataclass
class Node:
    """Pojedynczy member federacji.

    Atrybuty:

    - ``node_id`` — uuid hex, generowany przez registry przy rejestracji.
    - ``name`` — human-readable, np. ``"laptop-warsaw"``,
      ``"vps-warsaw-01"``, ``"gpu-cluster-fra"``.
    - ``kind`` — ``NodeKind``.
    - ``status`` — ``NodeStatus``; default ``UNKNOWN``, ustawiane heartbeat-em.
    - ``base_url`` — adres wewnętrzny przez który AEIS odpyta node-a
      (np. ``http://10.0.0.5:11434`` dla Ollama).
    - ``locality`` — ``"local"`` / ``"lan"`` / ``"cloud"``; używane przez
      privacy filter.
    - ``tags`` — wolne tagi (``"gpu"``, ``"warsaw"``, ``"experimental"``).
    - ``available_models`` — lista ``model_id`` które node aktualnie hostuje.
    - ``cost_per_1k_tokens_usd`` — mapa ``model_id → cena``. Brak wpisu =
      darmowy (lokalny laptop).
    - ``last_heartbeat`` — epoch seconds; aktualizowane przez registry.
    - ``capacity_score`` — 0..1; weight tie-breakera w routingu (większy
      → wyższa szansa wygrania).
    - ``metadata`` — dowolne pola dodatkowe (``gpu_model``, ``ram_gb``, …).
    """

    node_id: str
    name: str
    kind: NodeKind
    status: NodeStatus = NodeStatus.UNKNOWN
    base_url: str = ""
    locality: str = "local"
    tags: list[str] = field(default_factory=list)
    available_models: list[str] = field(default_factory=list)
    cost_per_1k_tokens_usd: dict[str, float] = field(default_factory=dict)
    last_heartbeat: float = 0.0
    capacity_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def validate(cls, **kwargs: Any) -> "Node":
        """Build a Node and validate fields. Use instead of Node(**kwargs) at boundaries.

        P0-1 hardening: enforce locality whitelist, capacity_score bounds,
        cost-per-1k for compute providers, and available_models length.
        Raises ``ValueError`` on violation.
        """
        locality = kwargs.get("locality", "local")
        if locality not in LOCALITY_WHITELIST:
            raise ValueError(
                f"locality '{locality}' invalid; must be one of {sorted(LOCALITY_WHITELIST)}"
            )
        capacity = float(kwargs.get("capacity_score", 1.0))
        if not (0.0 <= capacity <= 1.0):
            raise ValueError(
                f"capacity_score must be in [0.0, 1.0], got {capacity}"
            )
        models = kwargs.get("available_models", []) or []
        if len(models) > MAX_AVAILABLE_MODELS:
            raise ValueError(
                f"available_models has {len(models)} entries; max is {MAX_AVAILABLE_MODELS}"
            )
        kind = kwargs.get("kind")
        cost = kwargs.get("cost_per_1k_tokens_usd", {}) or {}
        # Only enforce cost-mandatory for COMPUTE_PROVIDER (the dedicated
        # provider tier); FULL_INSTANCE and HYBRID may default cost
        # (laptop = free).
        if hasattr(kind, "value"):
            kind_val = kind.value
        else:
            kind_val = str(kind) if kind else ""
        if kind_val == "compute_provider" and not cost:
            raise ValueError(
                "kind=compute_provider must declare at least one entry in "
                "cost_per_1k_tokens_usd"
            )
        # W17 P1-2: per-value sanity check on every cost entry. Without
        # this, a hostile node can poison the routing sort (NaN compares
        # False against everything → nondeterministic), claim every
        # cheapest-tie-break (-inf), or grief the cost cap filter (+inf
        # always exceeds, but only after wasting compare cycles).
        for model_id, price in cost.items():
            try:
                p = float(price)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"cost for model '{model_id}' is not numeric: {price!r}"
                ) from exc
            if math.isnan(p) or math.isinf(p):
                raise ValueError(
                    f"cost for model '{model_id}' must be finite, got {price!r}"
                )
            if p < 0:
                raise ValueError(
                    f"cost for model '{model_id}' must be >= 0, got {p}"
                )
            if p > MAX_COST_PER_1K_TOKENS_USD:
                raise ValueError(
                    f"cost for model '{model_id}' exceeds max "
                    f"{MAX_COST_PER_1K_TOKENS_USD} USD/1k tokens, got {p}"
                )
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dump dla REST i replay/audit."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "kind": self.kind.value if isinstance(self.kind, NodeKind) else self.kind,
            "status": self.status.value if isinstance(self.status, NodeStatus) else self.status,
            "base_url": self.base_url,
            "locality": self.locality,
            "tags": list(self.tags),
            "available_models": list(self.available_models),
            "cost_per_1k_tokens_usd": dict(self.cost_per_1k_tokens_usd),
            "last_heartbeat": self.last_heartbeat,
            "capacity_score": self.capacity_score,
            "metadata": dict(self.metadata),
        }

    def cost_for(self, model_id: str) -> float:
        """Zwróć koszt 1k tokens dla danego modelu lub 0.0 gdy brak wpisu.

        Konwencja: brak wpisu w mapie = lokalne (darmowe). Phase 0 nie
        rozróżnia in/out; G2 doda strukturę ``{"input": x, "output": y}``.
        """
        return float(self.cost_per_1k_tokens_usd.get(model_id, 0.0))

    def serves(self, model_id: str) -> bool:
        """Czy node hostuje dany model."""
        return model_id in self.available_models
