"""L0: SimulationContract defaults + builder.

The contract is the *first* layer — it defines what is allowed in the
sandbox, what is persisted, and the safety budget. Every L1-L4 operation
must be initiated against an active contract.
"""
from __future__ import annotations

from typing import Any

from sylion.aeis.testing.ontology.objects import SimulationContract

# ----------------------------------------------------------------------
# Default policy
# ----------------------------------------------------------------------

DEFAULT_ISOLATION: dict[str, bool] = {
    "main_mutation_allowed": False,
    "external_network_allowed": False,
    "real_device_allowed": False,
    "real_payment_allowed": False,
    "real_email_send_allowed": False,
    "object_changes_auto_discard": True,
}

DEFAULT_MODEL_MODE: dict[str, str] = {
    "llm_mode": "deterministic_stub",
    "event_bus_mode": "isolated_bus",
    "pricing_mode": "profile",
}

DEFAULT_PERSISTENCE: dict[str, bool] = {
    "persist_human_decision_trace": True,
    "persist_findings": True,
    "persist_evidence": True,
    "discard_object_state": True,
}

DEFAULT_SAFETY: dict[str, Any] = {
    "max_runtime_seconds": 900,
    "max_cost_usd": 1.00,
    "max_actions": 200,
    "max_repair_attempts": 2,
}


# Hard upper bounds (cannot be exceeded even by override)
HARD_MAX_RUNTIME_SECONDS = 3600
HARD_MAX_COST_USD = 10.0
HARD_MAX_ACTIONS = 1000


def build_contract(
    simulation_id: str,
    branch_id: str,
    source_project_id: str,
    sot_version: str,
    masterplan_version: str,
    test_charter_id: str | None = None,
    isolation_overrides: dict | None = None,
    model_mode_overrides: dict | None = None,
    persistence_overrides: dict | None = None,
    safety_overrides: dict | None = None,
) -> SimulationContract:
    """Build a SimulationContract with defaults + safe overrides.

    Raises ValueError if hard bounds are violated by override.
    """
    import math

    isolation = {**DEFAULT_ISOLATION, **(isolation_overrides or {})}
    model_mode = {**DEFAULT_MODEL_MODE, **(model_mode_overrides or {})}
    persistence = {**DEFAULT_PERSISTENCE, **(persistence_overrides or {})}
    safety = {**DEFAULT_SAFETY, **(safety_overrides or {})}

    # NaN/Inf bypass guard (Kimi attack #4): NaN comparisons return False
    # so ``nan > HARD_MAX_RUNTIME_SECONDS`` would silently pass.
    for key in ("max_runtime_seconds", "max_cost_usd", "max_actions",
                "max_repair_attempts"):
        v = safety.get(key)
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"safety.{key} must be numeric, got {type(v).__name__}")
        if not math.isfinite(float(v)):
            raise ValueError(f"safety.{key} must be finite (got {v!r})")
        if v < 0:
            raise ValueError(f"safety.{key} must be >= 0 (got {v!r})")

    # Hard bounds
    if safety["max_runtime_seconds"] > HARD_MAX_RUNTIME_SECONDS:
        raise ValueError(
            f"max_runtime_seconds exceeds hard limit "
            f"({HARD_MAX_RUNTIME_SECONDS})"
        )
    if safety["max_cost_usd"] > HARD_MAX_COST_USD:
        raise ValueError(
            f"max_cost_usd exceeds hard limit ({HARD_MAX_COST_USD})"
        )
    if safety["max_actions"] > HARD_MAX_ACTIONS:
        raise ValueError(
            f"max_actions exceeds hard limit ({HARD_MAX_ACTIONS})"
        )

    # Defensive checks against accidental main mutation. The dataclass
    # __post_init__ validators in objects.py enforce the same invariants
    # at persistence time; this layer rejects misuse early so the build
    # fails fast and the caller does NOT need to construct a privileged
    # contract just to test the happy path.
    if isolation["main_mutation_allowed"] is True:
        d_level = safety.get("approved_d_level")
        council_ok = bool(safety.get("council_approved", False))
        if d_level != "D5" or not council_ok:
            raise ValueError(
                "main_mutation_allowed=True requires safety.approved_d_level=D5 "
                "AND safety.council_approved=True"
            )
    if isolation["external_network_allowed"] is True:
        d_level = safety.get("approved_d_level")
        sentinel_ok = bool(safety.get("sentinel_approved", False))
        if d_level not in ("D4", "D5") or not sentinel_ok:
            raise ValueError(
                "external_network_allowed=True requires "
                "safety.approved_d_level in [D4, D5] "
                "AND safety.sentinel_approved=True"
            )
    if isolation["real_device_allowed"] is True:
        d_level = safety.get("approved_d_level")
        device_gate_ok = bool(safety.get("device_gate_approved", False))
        if d_level != "D5" or not device_gate_ok:
            raise ValueError(
                "real_device_allowed=True requires safety.approved_d_level=D5 "
                "AND safety.device_gate_approved=True"
            )

    return SimulationContract(
        simulation_id=simulation_id,
        branch_id=branch_id,
        source_project_id=source_project_id,
        sot_version=sot_version,
        masterplan_version=masterplan_version,
        test_charter_id=test_charter_id,
        isolation=isolation,
        model_mode=model_mode,
        persistence=persistence,
        safety=safety,
    )


__all__ = [
    "build_contract",
    "DEFAULT_ISOLATION", "DEFAULT_MODEL_MODE",
    "DEFAULT_PERSISTENCE", "DEFAULT_SAFETY",
    "HARD_MAX_RUNTIME_SECONDS", "HARD_MAX_COST_USD", "HARD_MAX_ACTIONS",
]
