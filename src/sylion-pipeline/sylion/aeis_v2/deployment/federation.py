"""W17 Federation — deterministic routing engine.

PDF §8.4 — *"Task wymagający qwen2.5:72b routowany do najtańszego
compute provider który ma model online."*

Algorytm Phase 0 (deterministic, side-effect-free):

1. **Privacy filter** — odrzuć node-y niezgodne z ``req.privacy_level``.
2. **Model availability** — wymagaj że ``req.model_id`` jest w
   ``node.available_models`` (lub jeden z ``fallback_models``).
3. **Cost cap** — jeśli ``req.max_cost_per_1k`` zdefiniowany, odrzuć
   node-y droższe.
4. **Sort** — locality preference > capacity_score > -cost.
5. **Pick top 1** — z rationale po polsku.

``RoutingDecision.rejected`` zawiera listę {node_id, reason} dla
audytu i replay UI.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sylion.aeis_v2.deployment.cost_ledger import (
    CostRecord,
    emit_cost_record,
)
from sylion.aeis_v2.deployment.nodes import Node, PrivacyLevel
from sylion.aeis_v2.deployment.registry import NodeRegistry, get_node_registry

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# W19 cost_cap_per_decision policy — narrow inline enforcement
# --------------------------------------------------------------------------
#
# The W19 policy catalog declares ``cost_cap_per_decision`` (limit
# 0.50 USD per single routing decision) but the full W19 evaluator +
# Release Rail enforcement is PARKED per ADR-001 #4 ("setki reinstalacji
# AEIS przy rozbudowanym systemie bezpieczeństwa to byłaby tragedia").
#
# Cost discipline is, however, a "no regrets" win: an LLM call that
# routes to a cloud provider charging 50 USD for a single completion is
# a bug regardless of any other policy. So we wire ONE specific policy —
# the cost cap — into the router right here, as a hardcoded check, and
# leave the generic policy DSL parked.
#
# Three modes (env ``SYLION_COST_CAP_MODE``):
#   - ``warn``  (default, Phase 0): log a warning, increment counter,
#                                    decision PROCEEDS. Operator sees
#                                    cost-cap pressure in metrics
#                                    without traffic disruption.
#   - ``deny``  (G2 candidate):     return a denied RoutingDecision
#                                    with ``error="cost_cap_exceeded"``.
#                                    Hard stop — caller must retry with
#                                    a cheaper model or relax privacy.
#   - ``off``                       skip the check entirely. Useful for
#                                    debugging and for tests that want
#                                    isolated control over the path.
#
# Phase 0 token estimate is hardcoded at 1000 (pessimistic upper bound)
# because ``RoutingRequest`` does not yet carry token counts. G2 will
# plug in actual prompt-token + max_response-token estimates.
COST_CAP_PER_DECISION_USD: float = 0.50  # W19 catalog: cost_cap_per_decision
COST_CAP_DEFAULT_MODE: Literal["warn", "deny", "off"] = "warn"
COST_CAP_ESTIMATED_TOKENS: int = 1000  # Phase 0 pessimistic upper bound
COST_CAP_MODE_ENV_VAR: str = "SYLION_COST_CAP_MODE"

# Module-level counter incremented every time warn-mode decision exceeds
# the cap. Tests inspect this via the module attribute. G2 will surface
# this on ``/health`` next to ``decisions_total``.
cost_cap_warnings_total: int = 0
_cost_cap_lock = threading.Lock()

# Runtime override (W17 G2 step from a7d2). When non-None, beats env var.
# Tests + operator REST endpoint set/clear via set_runtime_cost_cap_mode().
_RUNTIME_COST_CAP_MODE: Literal["warn", "deny", "off"] | None = None


@dataclass(frozen=True, slots=True)
class CostCapEvaluation:
    """Result of cost-cap evaluation per ADR-001 #4 (W19 PARKED carve-out).

    Attributes:
        mode: Resolved evaluation mode (``warn``/``deny``/``off``).
        estimated_usd: cost_per_1k * estimated_tokens / 1000.
        exceeded: True iff ``estimated_usd > COST_CAP_PER_DECISION_USD``.
        action: Final outcome — ``allow``/``warn``/``deny``. ``off`` mode
            ALWAYS yields ``allow`` regardless of ``exceeded``.
    """

    mode: Literal["warn", "deny", "off"]
    estimated_usd: float
    exceeded: bool
    action: Literal["allow", "warn", "deny"]


def set_runtime_cost_cap_mode(
    mode: Literal["warn", "deny", "off"] | None,
) -> None:
    """Set the runtime override (in-memory). Beats env when non-None.

    Pass ``None`` to clear and revert to env-resolved mode. Operator REST
    endpoint ``POST /cost-cap/mode`` and tests both go through this.

    Raises ``ValueError`` on invalid mode literal — last line of defence
    against a typo that would silently disable the cap.
    """
    if mode is not None and mode not in ("warn", "deny", "off"):
        raise ValueError(
            f"cost_cap mode must be one of {{warn, deny, off}} or None, "
            f"got {mode!r}"
        )
    global _RUNTIME_COST_CAP_MODE
    with _cost_cap_lock:
        _RUNTIME_COST_CAP_MODE = mode


def get_runtime_cost_cap_mode() -> dict[str, str | None]:
    """Diagnostic snapshot — runtime override, env resolution, effective."""
    with _cost_cap_lock:
        runtime = _RUNTIME_COST_CAP_MODE
    env_resolved = os.environ.get(COST_CAP_MODE_ENV_VAR, "").strip().lower() or None
    effective = _resolved_cost_cap_mode()
    return {
        "runtime": runtime,
        "env": env_resolved,
        "effective": effective,
    }


def reset_cost_cap_warnings_total() -> int:
    """Atomic reset; returns the previous value."""
    global cost_cap_warnings_total
    with _cost_cap_lock:
        prev = cost_cap_warnings_total
        cost_cap_warnings_total = 0
    return prev


def _resolved_cost_cap_mode() -> Literal["warn", "deny", "off"]:
    """Resolve effective mode: runtime override > env var > module default.

    Env wins over the module-level default so tests / operator overrides
    work without code changes. Unknown values are coerced to ``warn``
    (fail-open at the audit layer; a misconfigured env should never
    silently turn the cap off).
    """
    # Runtime override beats env (a7d2 W17 cost_cap REST runtime control).
    with _cost_cap_lock:
        runtime = _RUNTIME_COST_CAP_MODE
    if runtime is not None:
        return runtime
    raw = os.environ.get(COST_CAP_MODE_ENV_VAR, "").strip().lower()
    if raw in ("warn", "deny", "off"):
        return raw  # type: ignore[return-value]
    if raw:
        log.warning(
            "cost_cap: unknown %s=%r; falling back to default mode '%s'",
            COST_CAP_MODE_ENV_VAR, raw, COST_CAP_DEFAULT_MODE,
        )
    return COST_CAP_DEFAULT_MODE


def _evaluate_cost_cap(
    chosen_node: "Node | None" = None,
    chosen_model_id: str | None = None,
    *,
    cost_per_1k_usd: float | None = None,
    estimated_tokens: int | None = None,
    mode: Literal["warn", "deny", "off"] | None = None,
):
    """Cost-cap evaluation. Two call patterns supported:

    **Internal (from route())**: ``_evaluate_cost_cap(chosen_node, chosen_model_id)``
    returns ``(mode, estimated_usd, exceeded)`` tuple — preserved for backward
    compat with existing route() callsite.

    **Pure-helper (from REST simulator + tests)**:
    ``_evaluate_cost_cap(cost_per_1k_usd=..., estimated_tokens=..., mode=...)``
    returns ``CostCapEvaluation`` dataclass with all four fields populated.

    Mode ``off`` ALWAYS yields ``action='allow'`` regardless of ``exceeded``.

    Pure function: side effects (logging, counter, denied decision) live
    in ``route()`` so this helper stays trivially testable.
    """
    # Branch 2 (kwargs): pure helper for tests + REST simulator.
    if cost_per_1k_usd is not None or mode is not None:
        if mode is None:
            mode = _resolved_cost_cap_mode()
        tokens = estimated_tokens if estimated_tokens is not None else COST_CAP_ESTIMATED_TOKENS
        estimated = (cost_per_1k_usd or 0.0) * tokens / 1000.0
        exceeded = estimated > COST_CAP_PER_DECISION_USD
        if mode == "off":
            action: Literal["allow", "warn", "deny"] = "allow"
        elif exceeded and mode == "deny":
            action = "deny"
        elif exceeded and mode == "warn":
            action = "warn"
        else:
            action = "allow"
        return CostCapEvaluation(
            mode=mode, estimated_usd=estimated, exceeded=exceeded, action=action,
        )

    # Branch 1 (positional): backward compat for existing route() callsite.
    resolved_mode = _resolved_cost_cap_mode()
    cost_per_1k = chosen_node.cost_for(chosen_model_id) if chosen_node else 0.0
    estimated_usd = cost_per_1k * COST_CAP_ESTIMATED_TOKENS / 1000.0
    exceeded_b1 = estimated_usd > COST_CAP_PER_DECISION_USD
    return resolved_mode, estimated_usd, exceeded_b1


# --------------------------------------------------------------------------
# W17 P1-5: routing decision audit log (file-only fallback Phase 0)
# --------------------------------------------------------------------------
#
# Adversarial review (docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md,
# P1-5) flagged that ``route()`` produced no persistent audit trail — after
# the fact, "why did request X route to node Y" was unanswerable because
# nothing was written to stdlib logging or any audit sink. We now emit one
# JSONL row per decision to ``logs/v2/routing_audit.jsonl`` so the operator
# UI / replay tooling can correlate decisions by ``decision_id``.
#
# Phase 0: file-only fallback. G2 will move this to a PG audit table
# (``sylion_v2.routing_audit``) and keep the JSONL as DR fallback when PG
# is unreachable. Mirrors the W15 applier audit structure (apply_audit.jsonl).
#
# parents[3] resolves: federation.py -> deployment -> aeis_v2 -> sylion -> sylion-pipeline/
ROUTING_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "routing_audit.jsonl"
)


def _emit_routing_audit(
    decision: "RoutingDecision",
    request: "RoutingRequest",
    candidates_count: int,
    rejected_reasons: dict[str, int],
    chosen_node: Node | None,
    cost_for_chosen: float | None,
    decision_total: int,
    cost_cap_check: dict[str, Any] | None = None,
) -> None:
    """Write a structured audit row to the JSONL log per routing decision.

    Format (one JSON object per line):
      {ts, decision_id, model_id, privacy_level, prefer_locality,
       max_cost_per_1k, chosen_node_id, chosen_node_name, chosen_node_locality,
       candidates_count, rejected_reasons, cost_for_chosen, decision_total,
       cost_cap_check}

    ``cost_cap_check`` (W19 cost_cap_per_decision policy) carries the
    per-decision triple ``{mode, estimated_usd, exceeded}`` when the
    cost cap was evaluated. ``None`` for decisions that never reached
    the cost-cap stage (no candidates, no chosen node) so absence is
    distinguishable from "evaluated and ok".

    Failure to write the audit log is itself logged at WARNING level but
    does NOT raise — routing must complete even if audit infra is down
    (best-effort). Phase 0: file-only fallback. G2 will move to a PG audit
    table; the file remains as fallback when PG unreachable. Mirrors the
    W15 applier audit structure.
    """
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "decision_id": decision.decision_id,
        "model_id": request.model_id,
        "privacy_level": request.privacy_level.value,
        "prefer_locality": list(request.prefer_locality or []),
        "max_cost_per_1k": request.max_cost_per_1k,
        "chosen_node_id": decision.chosen_node_id,
        "chosen_node_name": chosen_node.name if chosen_node is not None else None,
        "chosen_node_locality": (
            chosen_node.locality if chosen_node is not None else None
        ),
        "candidates_count": candidates_count,
        "rejected_reasons": dict(rejected_reasons),
        "cost_for_chosen": cost_for_chosen,
        "decision_total": decision_total,
        "cost_cap_check": dict(cost_cap_check) if cost_cap_check else None,
    }
    try:
        ROUTING_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ROUTING_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("routing_audit: failed to write JSONL (%s)", exc)


def _record_decision_cost(
    decision: "RoutingDecision",
    request: "RoutingRequest",
    chosen_node: Node | None,
) -> None:
    """Emit a W17 cost-ledger row right after a routing decision finalizes.

    Per ADR-001 Decision #3 the cost-ledger is event-sourced — every
    routable LLM intent (Phase 0) and every actual call (G2) becomes a
    ``cost.recorded`` event. This helper bridges the routing-decision
    side: when ``route()`` picks a node, we immediately emit a
    placeholder-cost row keyed on ``decision.decision_id`` so:

    1. Operators can ``GET /api/v1/federation/costs/recent`` and see
       *which* models routed *where* even before the adapter call lands.
    2. The G2 reconciliation pipeline has a stable ``decision_id``
       to merge against once token counts arrive.

    **Phase 0 caveat (intentional)**: ``tokens_in = tokens_out = 0`` and
    ``cost_usd = 0.0``. The cost-per-1k for the chosen model lives on
    the routing audit row (``cost_for_chosen``) for the same
    ``decision_id`` — together they tell the full story. G2 will publish
    a follow-up ``cost.refined`` event after the adapter completes,
    keyed on ``decision_id``, that fills in the actual token counts and
    derives ``cost_usd = (tokens_in + tokens_out) / 1000 * cost_per_1k``.

    No-op when ``chosen_node is None`` (the router did not pick anyone —
    either privacy filtered everything or no node hosts the model). We
    do NOT record a "phantom" cost for those: the routing audit row
    already captures the rejection.
    """
    if chosen_node is None or decision.chosen_model_id is None:
        return
    record = CostRecord(
        ts=time.time(),
        session_id="",   # G2: filled by terminal_session when present.
        decision_id=decision.decision_id,
        host=chosen_node.node_id,
        model=decision.chosen_model_id,
        tokens_in=0,
        tokens_out=0,
        cost_usd=0.0,
        metadata={
            "phase": "0",
            "node_name": chosen_node.name,
            "node_locality": chosen_node.locality,
            "cost_per_1k": chosen_node.cost_for(decision.chosen_model_id),
        },
    )
    emit_cost_record(record)


# --------------------------------------------------------------------------
# P0-3 + P0-5: atomic decision counter + per-decision identity.
# --------------------------------------------------------------------------
#
# A single module-level lock guards the global decision counter so that
# concurrent ``route()`` calls cannot lose increments (P0-3). Each decision
# also gets a uuid hex id and a monotonic generation number (P0-5) so the
# caller can re-validate the chosen node is still active before using it,
# and so audit/replay can trace cross-instance ordering.

_decisions_lock = threading.Lock()
_decisions_total = 0

# ---------------------------------------------------------------------------
# Sprint 4 W19 wire-in — operator can plug in a policy_v2.RoutingGate via
# ``set_w19_routing_gate(...)`` to subject every federation route() decision
# to the W19 jinja policy evaluator.  Default ``None`` = backward-compat
# (no W19 check), so this module's existing callers see zero behavioural
# change until the operator opts in via the W19 production runbook.
# ---------------------------------------------------------------------------

_W19_ROUTING_GATE: Any | None = None
_W19_POLICY_TEMPLATE_PROVIDER: Any | None = None


def set_w19_routing_gate(gate: Any | None) -> None:
    """Install a :class:`policy_v2.RoutingGate` for all subsequent routes.

    Call with ``None`` to remove the gate (kill switch from runbook §5).
    """
    global _W19_ROUTING_GATE
    _W19_ROUTING_GATE = gate


def set_w19_policy_template_provider(provider: Any | None) -> None:
    """Install a callable ``() -> str | None`` that returns the active
    policy template body. Production wires this to
    ``PgPolicyRegistry.get_active_policy().template_str``.
    """
    global _W19_POLICY_TEMPLATE_PROVIDER
    _W19_POLICY_TEMPLATE_PROVIDER = provider


def _w19_check_or_none(req_decision_id: str, req_context: dict) -> Any | None:
    """If a W19 gate is installed, run it and return its decision.

    Returns ``None`` when no gate is installed OR when the gate call
    raises (best-effort — never blocks federation routing on a W19
    error).
    """
    gate = _W19_ROUTING_GATE
    if gate is None:
        return None
    try:
        provider = _W19_POLICY_TEMPLATE_PROVIDER
        template = provider() if callable(provider) else None
        return gate.check(
            decision_id=req_decision_id,
            policy_template=template,
            context=req_context,
        )
    except Exception:  # noqa: BLE001 — fail-open
        return None


def _next_decision_id() -> tuple[str, int]:
    """Return (decision_id, generation_counter) — atomic across all routers.

    P0-3: increment is now serialized; 100 concurrent routes always observe
    the counter as 100, never N-1 from lost-update races. P0-5: the
    decision_id (uuid hex, 12 chars) lets the caller log a stable handle for
    the chosen node so unregister/route races are detectable.
    """
    global _decisions_total
    with _decisions_lock:
        _decisions_total += 1
        gen = _decisions_total
    return uuid.uuid4().hex[:12], gen


# --------------------------------------------------------------------------
# Public types
# --------------------------------------------------------------------------


@dataclass
class RoutingRequest:
    """Wejście dla ``FederationRouter.route``.

    - ``model_id`` — preferowany model (np. ``"qwen2.5:72b"``).
    - ``privacy_level`` — pierwszy filtr (LOCAL_ONLY / PREFER_LOCAL /
      EXTERNAL_OK / ANY).
    - ``fallback_models`` — kolejność prób gdy ``model_id`` niedostępny.
    - ``max_cost_per_1k`` — twardy cap; node droższy odrzucony.
    - ``prefer_locality`` — np. ``["local", "lan"]``; jeśli niepuste, te
      lokalności wyprzedzają tie-break przed capacity_score.
    """

    model_id: str
    privacy_level: PrivacyLevel = PrivacyLevel.ANY
    fallback_models: list[str] = field(default_factory=list)
    max_cost_per_1k: float | None = None
    prefer_locality: list[str] = field(default_factory=list)


@dataclass
class RoutingDecision:
    """Wynik routingu.

    - ``chosen_node_id`` — ``None`` gdy żaden kandydat nie przeszedł
      filtrów (wszystkie modele niedostępne lub privacy zbyt restrykcyjne).
    - ``chosen_model_id`` — który model został finalnie wybrany
      (``req.model_id`` lub jeden z ``fallback_models``).
    - ``rationale`` — operator-visible opis decyzji po polsku.
    - ``candidates`` — wszystkie node_ids brane pod uwagę po privacy filter.
    - ``rejected`` — lista ``{node_id, reason}`` dla audytu.
    - ``decision_id`` — uuid hex (12 chars) per decision (P0-5). Empty for
      decisions produced before ``route()`` stamps them; should be non-empty
      on every decision returned by current code paths.
    - ``decision_generation`` — monotonic counter shared across all routers
      in the process (P0-5). Lets callers re-validate node staleness and
      orders decisions for replay/audit.
    """

    chosen_node_id: str | None
    chosen_model_id: str | None
    rationale: str
    candidates: list[str] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    decision_id: str = ""
    decision_generation: int = 0
    error: str | None = None  # populated when policy denies (e.g. cost_cap_exceeded)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chosen_node_id": self.chosen_node_id,
            "chosen_model_id": self.chosen_model_id,
            "rationale": self.rationale,
            "candidates": list(self.candidates),
            "rejected": [dict(r) for r in self.rejected],
            "decision_id": self.decision_id,
            "decision_generation": self.decision_generation,
            "error": self.error,
        }


# --------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------


class FederationRouter:
    """Deterministic Phase 0 router.

    Trzyma referencję do ``NodeRegistry`` (default = process singleton).
    ``decisions_total`` to lekki licznik dla ``/health`` endpointa —
    pomaga operatorowi zobaczyć "ile razy rola się odpaliła" bez
    sięgania do audit logu.
    """

    def __init__(self, registry: NodeRegistry | None = None) -> None:
        self._registry = registry or get_node_registry()
        # Per-instance counter, incremented under the same lock that drives the
        # module-level counter so it stays consistent under threading.
        self._decisions_total = 0
        self._decisions_total_lock = threading.Lock()

    @property
    def registry(self) -> NodeRegistry:
        return self._registry

    @property
    def decisions_total(self) -> int:
        """Per-instance count of routing decisions made (atomic).

        Read is unsynchronized — Python int reads are atomic, and a stale read
        is harmless for an observability counter.
        """
        return self._decisions_total

    # ------------------------------------------------------------------
    # Privacy filter (krok 1)
    # ------------------------------------------------------------------

    def _privacy_pass(self, node: Node, level: PrivacyLevel) -> bool:
        """Czy node mieści się w polityce prywatności."""
        if level == PrivacyLevel.LOCAL_ONLY:
            return node.locality == "local"
        # PREFER_LOCAL / EXTERNAL_OK / ANY akceptują wszystkie aktywne;
        # PREFER_LOCAL daje boost w sortowaniu (poniżej), nie w filtrze.
        return True

    # ------------------------------------------------------------------
    # Sortowanie kandydatów (krok 4)
    # ------------------------------------------------------------------

    def _sort_key(
        self,
        node: Node,
        model_id: str,
        req: RoutingRequest,
    ) -> tuple[int, float, float, str]:
        """Klucz sortowania (mniejszy = lepszy).

        Kolejność wag:

        1. ``locality_rank``: 0 dla preferowanej lokalności, większe dla
           pozostałych. Jeśli ``req.prefer_locality`` puste i privacy=
           PREFER_LOCAL — ``prefer`` zostaje wstrzyknięte jako ``["local"]``
           (linia poniżej), więc local domyślnie wygrywa bez dodatkowego boostu.
        2. ``-capacity_score`` — większa pojemność = wyższy priorytet
           (negacja bo sortujemy rosnąco).
        3. ``cost_for(model)`` — taniej = lepiej.
        4. ``node_id`` — final deterministic tie-breaker (W17 P1-3).

        **W17 P1-3 fix** — przed tą zmianą tuple miał 4 elementy. Gdy
        ``req.prefer_locality=[]`` i ``privacy_level=ANY`` (typowy ruch
        operatora bez wyrażonej preferencji), wszystkie node-y dostawały
        ``locality_rank=0``. Jeśli dwa node-y miały też identyczny
        ``capacity_score`` i identyczny ``cost_for``, cały klucz wynosił
        ``(0, -1.0, 0.05)`` i Python's stable sort rozstrzygał remis przez
        **kolejność rejestracji** w registry — node zarejestrowany jako
        pierwszy cicho zgarniał cały ruch.

        Doklejenie ``node.node_id`` jako tie-breakera daje:

        - **deterministykę**: ten sam zestaw node-ów + ten sam request →
          zawsze ten sam wybór (stabilne audyt + replay).
        - **load-spreading przez registry instances**: ``node_id`` to
          ``uuid.uuid4().hex`` generowany przy ``register()``, więc
          alfabetyczne pierwszeństwo nie wiąże się z pierwszeństwem
          rejestracji — różne instancje registry mają różnych zwycięzców.
        - **bez load-spreadingu w obrębie jednej instancji**: tied node-y
          zawsze wybierają tego samego "alfabetycznie pierwszego" zwycięzcę.
          To celowe ograniczenie Phase 0 — G2 zastąpi to hashowaniem
          ``hash((req.request_id, node.node_id))`` gdy ``RoutingRequest``
          dostanie stabilny ``request_id`` (obecnie go nie ma).

        Opcja B (load-spreading przez ``hash(req.request_id, node.node_id)``)
        była rozważana, ale ``RoutingRequest`` nie ma jeszcze pola
        ``request_id`` — dodanie go zmieniłoby publiczne API i byłoby
        poza zakresem P1-3. Migracja zaplanowana na G2.

        **W17 P1-7 fix** — usunięto redundantny ``privacy_local_boost``
        (drugi element 5-tuple z ab16). Adversarial review wykazało, że
        boost byl dead code: gdy ``prefer_locality=[]`` i privacy=
        PREFER_LOCAL, ``prefer`` zostaje wstrzyknięte jako ``["local"]``
        (linia poniżej) i ``locality_rank`` już koduje preferencję. Gdy
        operator dał ``prefer_locality=["cloud"]`` przy privacy=
        PREFER_LOCAL, boost próbował promować ``local`` w drugiej kolejności
        — co zaprzeczało jawnej operatorowej preferencji. Tuple skrócone
        z 5- do 4-elementowego.
        """
        # --- locality preference
        # P1-7: when prefer_locality is empty AND privacy=PREFER_LOCAL,
        # inject ["local"] so locality_rank alone encodes the implicit
        # preference. This is the SOLE machinery for PREFER_LOCAL — there
        # is no longer a secondary privacy_local_boost.
        prefer = list(req.prefer_locality or [])
        if not prefer and req.privacy_level == PrivacyLevel.PREFER_LOCAL:
            prefer = ["local"]
        if prefer:
            try:
                locality_rank = prefer.index(node.locality)
            except ValueError:
                locality_rank = len(prefer) + 1
        else:
            locality_rank = 0

        # --- capacity (większy lepszy → negacja bo sort rosnący)
        capacity_neg = -float(node.capacity_score)

        # --- koszt (mniejszy lepszy)
        cost = node.cost_for(model_id)

        # --- deterministic tie-break (W17 P1-3): pre-tej-zmiany Python's
        # stable sort rozstrzygał wszystkie ties przez kolejność rejestracji
        # → pierwszy zarejestrowany node zgarniał cały ruch. ``node_id``
        # to uuid hex z ``NodeRegistry.register``, więc:
        # - stabilny i deterministyczny per-(registry, model, req)
        # - bez biasu kolejności rejestracji (uuid jest random)
        # - nie zaburza wcześniejszych priorytetów (locality/capacity/cost)
        return (locality_rank, capacity_neg, cost, node.node_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _stamp(self, decision: RoutingDecision) -> RoutingDecision:
        """Attach atomic decision_id + generation to a fresh decision (P0-5)."""
        decision_id, generation = _next_decision_id()
        decision.decision_id = decision_id
        decision.decision_generation = generation
        return decision

    def route(self, req: RoutingRequest) -> RoutingDecision:
        """Wybierz node-a dla zadania.

        Algorytm patrz docstring modułu. Wynik jest deterministyczny —
        ten sam stan registry + ten sam ``RoutingRequest`` zawsze daje
        identyczny ``RoutingDecision``. To upraszcza testy i replay.

        P0-3: per-instance counter increment is now serialized under a lock
        so 100 concurrent routes always observe a +100 delta. P0-5: every
        returned decision carries a uuid decision_id and a monotonic
        decision_generation that lets callers re-validate freshness against
        the registry before actually using the chosen node.

        P1-5: every decision emits one JSONL audit row to
        ``ROUTING_AUDIT_LOG_PATH`` with the chosen node, request params,
        and a per-reason rejection breakdown. Audit failure is logged at
        WARNING but does NOT break routing (best-effort).

        W17 cost-ledger Phase 0 (ADR-001 Decision #3): when a node is
        chosen, ``_record_decision_cost`` emits a ``cost.recorded`` event
        keyed on ``decision_id``. Phase 0 records placeholder
        ``tokens=0`` / ``cost_usd=0.0`` because the adapter call has not
        happened yet at decision time; G2 reconciles after adapter
        completion via a follow-up ``cost.refined`` event.
        """
        with self._decisions_total_lock:
            self._decisions_total += 1
            decision_total_at_emit = self._decisions_total

        # Sprint 4 W19 pre-flight gate. Backward-compat: when no gate
        # is installed (default), ``_w19_check_or_none`` returns None and
        # routing proceeds normally. When the gate is installed and the
        # policy template renders ``"deny"`` for this request's context,
        # we short-circuit with a ``denied by W19 policy`` decision so
        # federation never picks a node for the disallowed request.
        # The gate's chained audit JSONL records the policy decision
        # independently of the federation routing audit.
        _w19_decision_id = f"fed-{uuid.uuid4().hex[:12]}"
        _w19_decision = _w19_check_or_none(
            _w19_decision_id,
            {
                "request": {
                    "model_id": req.model_id,
                    "privacy_level": str(getattr(req, "privacy_level", "")),
                    "fallback_models": list(req.fallback_models or []),
                    "max_cost_per_1k": req.max_cost_per_1k,
                    "prefer_locality": list(req.prefer_locality or []),
                },
            },
        )
        if _w19_decision is not None and _w19_decision.outcome == "deny":
            decision = self._stamp(RoutingDecision(
                chosen_node_id=None,
                chosen_model_id=None,
                rationale=(
                    f"Decyzja zablokowana przez W19 policy "
                    f"({_w19_decision.reason or 'policy_returned_deny'})."
                ),
                candidates=[],
                rejected=[],
            ))
            return decision

        # P1-5: rejection counts per reason, populated as filters drop nodes.
        rejected_reasons: dict[str, int] = {}

        active = self._registry.list_active()
        if not active:
            decision = self._stamp(RoutingDecision(
                chosen_node_id=None,
                chosen_model_id=None,
                rationale="Brak aktywnych node-ow w federacji (registry pusty lub wszystkie offline).",
                candidates=[],
                rejected=[],
            ))
            _emit_routing_audit(
                decision=decision,
                request=req,
                candidates_count=0,
                rejected_reasons=rejected_reasons,
                chosen_node=None,
                cost_for_chosen=None,
                decision_total=decision_total_at_emit,
            )
            return decision

        rejected: list[dict[str, Any]] = []

        # Krok 1: Privacy filter (działa też jako pierwszy zbiór kandydatów).
        privacy_pass: list[Node] = []
        for n in active:
            if self._privacy_pass(n, req.privacy_level):
                privacy_pass.append(n)
            else:
                rejected.append({
                    "node_id": n.node_id,
                    "reason": (
                        f"privacy={req.privacy_level.value} wymaga locality=local; "
                        f"node ma locality={n.locality}."
                    ),
                })
                rejected_reasons["privacy"] = rejected_reasons.get("privacy", 0) + 1

        if not privacy_pass:
            decision = self._stamp(RoutingDecision(
                chosen_node_id=None,
                chosen_model_id=None,
                rationale=(
                    f"Brak node-ow zgodnych z polityka prywatnosci "
                    f"'{req.privacy_level.value}'."
                ),
                candidates=[n.node_id for n in active],
                rejected=rejected,
            ))
            _emit_routing_audit(
                decision=decision,
                request=req,
                candidates_count=0,
                rejected_reasons=rejected_reasons,
                chosen_node=None,
                cost_for_chosen=None,
                decision_total=decision_total_at_emit,
            )
            return decision

        # Kolejność prób: preferowany model + fallback w kolejności podanej.
        models_to_try = [req.model_id] + list(req.fallback_models or [])
        candidates_ids = [n.node_id for n in privacy_pass]
        # P1-5: candidates_count is the size of the privacy-passed set —
        # the pool from which the model/cost filters select.
        candidates_count = len(privacy_pass)

        for model_attempt in models_to_try:
            # Krok 2: filter po model availability.
            with_model = [n for n in privacy_pass if n.serves(model_attempt)]
            without = [n for n in privacy_pass if not n.serves(model_attempt)]
            for n in without:
                rejected.append({
                    "node_id": n.node_id,
                    "reason": f"model '{model_attempt}' niedostepny (available_models={n.available_models}).",
                })
                rejected_reasons["no_model"] = rejected_reasons.get("no_model", 0) + 1
            if not with_model:
                continue

            # Krok 3: cost cap.
            if req.max_cost_per_1k is not None:
                affordable: list[Node] = []
                for n in with_model:
                    c = n.cost_for(model_attempt)
                    if c <= req.max_cost_per_1k:
                        affordable.append(n)
                    else:
                        rejected.append({
                            "node_id": n.node_id,
                            "reason": (
                                f"koszt {c:.5f} USD/1k przekracza cap "
                                f"{req.max_cost_per_1k:.5f} USD/1k dla '{model_attempt}'."
                            ),
                        })
                        rejected_reasons["cost_cap"] = (
                            rejected_reasons.get("cost_cap", 0) + 1
                        )
                with_model = affordable
                if not with_model:
                    continue

            # Krok 4 + 5: sort + pick top.
            with_model.sort(key=lambda n: self._sort_key(n, model_attempt, req))
            chosen = with_model[0]
            cost = chosen.cost_for(model_attempt)
            rationale_parts = [
                f"Wybrano '{chosen.name}'",
                f"locality={chosen.locality}",
                f"model '{model_attempt}' dostepny",
                f"capacity_score={chosen.capacity_score:.2f}",
                f"koszt {cost:.5f} USD/1k tokens",
            ]
            if model_attempt != req.model_id:
                rationale_parts.insert(
                    1,
                    f"fallback z '{req.model_id}' na '{model_attempt}'",
                )
            rationale = "; ".join(rationale_parts) + "."

            # W19 cost_cap_per_decision policy (warn/deny/off).
            # Evaluated AFTER candidate selection so we know the actual
            # node + model that would serve the request. The full W19
            # evaluator stays parked per ADR-001 #4 — this is a single,
            # hardcoded "no regrets" check.
            cap_mode, estimated_usd, cap_exceeded = _evaluate_cost_cap(
                chosen, model_attempt
            )
            cost_cap_check: dict[str, Any] | None = None
            if cap_mode != "off":
                cost_cap_check = {
                    "mode": cap_mode,
                    "estimated_usd": estimated_usd,
                    "exceeded": cap_exceeded,
                }

            if cap_mode == "deny" and cap_exceeded:
                deny_rationale = (
                    f"Estymowany koszt {estimated_usd:.4f} USD > limit "
                    f"{COST_CAP_PER_DECISION_USD} USD "
                    f"(W19 cost_cap_per_decision)."
                )
                decision = self._stamp(RoutingDecision(
                    chosen_node_id=None,
                    chosen_model_id=None,
                    rationale=deny_rationale,
                    candidates=candidates_ids,
                    rejected=rejected,
                    error="cost_cap_exceeded",
                ))
                _emit_routing_audit(
                    decision=decision,
                    request=req,
                    candidates_count=candidates_count,
                    rejected_reasons=rejected_reasons,
                    chosen_node=None,
                    cost_for_chosen=None,
                    decision_total=decision_total_at_emit,
                    cost_cap_check=cost_cap_check,
                )
                return decision

            if cap_mode == "warn" and cap_exceeded:
                global cost_cap_warnings_total
                with _cost_cap_lock:
                    cost_cap_warnings_total += 1
                log.warning(
                    "cost_cap: estimated %.4f USD > limit %.4f USD "
                    "(node=%s model=%s decision_total=%d) — W19 "
                    "cost_cap_per_decision warn-mode, decision PROCEEDS",
                    estimated_usd,
                    COST_CAP_PER_DECISION_USD,
                    chosen.name,
                    model_attempt,
                    decision_total_at_emit,
                )

            decision = self._stamp(RoutingDecision(
                chosen_node_id=chosen.node_id,
                chosen_model_id=model_attempt,
                rationale=rationale,
                candidates=candidates_ids,
                rejected=rejected,
            ))
            _emit_routing_audit(
                decision=decision,
                request=req,
                candidates_count=candidates_count,
                rejected_reasons=rejected_reasons,
                chosen_node=chosen,
                cost_for_chosen=cost,
                decision_total=decision_total_at_emit,
                cost_cap_check=cost_cap_check,
            )
            # W17 cost-ledger Phase 0 (ADR-001 #3): emit a placeholder
            # cost row keyed on decision_id so operators can correlate
            # routing decisions with future adapter-call cost rows.
            _record_decision_cost(decision, req, chosen)
            return decision

        # Wyszliśmy z pętli bez wyboru.
        tried = ", ".join(f"'{m}'" for m in models_to_try)
        decision = self._stamp(RoutingDecision(
            chosen_node_id=None,
            chosen_model_id=None,
            rationale=(
                f"Zaden node nie hostuje wymaganych modeli ({tried}) "
                f"lub wszystkie przekraczaja cap kosztu."
            ),
            candidates=candidates_ids,
            rejected=rejected,
        ))
        _emit_routing_audit(
            decision=decision,
            request=req,
            candidates_count=candidates_count,
            rejected_reasons=rejected_reasons,
            chosen_node=None,
            cost_for_chosen=None,
            decision_total=decision_total_at_emit,
        )
        return decision


# --------------------------------------------------------------------------
# Process singleton — double-checked locking (P0-4 fix)
# --------------------------------------------------------------------------
#
# Two threads racing through the old ``if _router is None`` check could both
# observe None and each create a FederationRouter, with the loser's state
# silently dropped. Double-checked locking serializes construction while
# keeping the fast path lock-free after init.

_router_singleton: FederationRouter | None = None
_router_singleton_lock = threading.Lock()

# Backward-compat alias — old internal name kept in sync for any callers.
_router: FederationRouter | None = None


def get_federation_router() -> FederationRouter:
    """Zwróć process-wide singleton ``FederationRouter`` z double-checked locking.

    Lazy-init — wykorzystuje ``get_node_registry()`` jako backing store.
    Testy mogą tworzyć własne instancje ``FederationRouter(registry)``
    aby uniknąć efektu singletona; produkcja używa tego getter-a.

    P0-4: classic ``if x is None: x = ...`` allowed two concurrent callers to
    both construct, dropping the loser's state. Now serialized.
    """
    global _router_singleton, _router
    # Fast path — already initialized.
    if _router_singleton is not None:
        return _router_singleton
    # Slow path — serialize construction.
    with _router_singleton_lock:
        if _router_singleton is not None:  # double-check inside lock
            return _router_singleton
        _router_singleton = FederationRouter(get_node_registry())
        _router = _router_singleton  # keep legacy name in sync
        return _router_singleton
