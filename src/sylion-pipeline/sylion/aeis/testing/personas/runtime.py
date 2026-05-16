"""PersonaRuntime — drives L2/L3/L4 simulation steps.

Real cognitive modeling is in E8; E3 implements deterministic stubs that
honor persona's behavior_modifiers (latency multiplier, hesitation prob).

Determinism (Kimi E8 #2): each ``simulate_*`` call uses a fresh
``random.Random`` seeded from ``(rng_seed_root, persona_id, scenario_id,
simulation_id)`` so the same input always produces the same trace,
regardless of how many times ``simulate_workflow`` was called before.
"""
from __future__ import annotations

import hashlib
import logging
import math
import random
from typing import Any

from sylion.aeis.testing.ontology.enums import DLevel
from sylion.aeis.testing.ontology.objects import (
    Finding, HumanDecisionTrace, HumanErrorInjection, HumanNearMiss, HumanScenario,
)
from sylion.aeis.testing.ontology.store import OntologyStore
from sylion.aeis.testing.personas.registry import PersonaRegistry

log = logging.getLogger("sylion.aeis.testing.personas.runtime")


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce + clamp NaN/inf to default (Kimi E8 #3)."""
    try:
        f = float(value if value is not None else default)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(f):
        return default
    return f


def _clamp_unit(value: float) -> float:
    """Clamp to [0.0, 1.0] after NaN guard."""
    return max(0.0, min(1.0, value))


def _seed_from(*parts: Any) -> int:
    """Derive a stable 64-bit seed from arbitrary parts (Kimi E8 #2)."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False)


class PersonaRuntime:
    """Executes simulation layers L2/L3/L4 with persona behavior modulation."""

    def __init__(
        self,
        ontology: OntologyStore,
        registry: PersonaRegistry,
        rng_seed: int | None = None,
    ) -> None:
        self._ontology = ontology
        self._registry = registry
        self._rng_seed_root = (
            rng_seed if rng_seed is not None else _seed_from("w14_e8_default")
        )
        # Kept for backward-compat; not used for new simulate_* paths.
        self._rng = random.Random(self._rng_seed_root)

    def _rng_for(self, *parts: Any) -> random.Random:
        return random.Random(_seed_from(self._rng_seed_root, *parts))

    # ------------------------------------------------------------------
    # L2: Workflow simulation
    # ------------------------------------------------------------------

    def simulate_workflow(
        self,
        persona_id: str,
        scenario_id: str,
        simulation_id: str,
    ) -> HumanDecisionTrace:
        persona = self._registry.get(persona_id)
        if persona is None:
            raise ValueError(f"persona not found: {persona_id}")
        scenario = self._ontology.get(HumanScenario, scenario_id)
        if scenario is None:
            raise ValueError(f"scenario not found: {scenario_id}")

        # Per-call deterministic RNG: same (persona, scenario, simulation)
        # always produces the same trace.
        rng = self._rng_for("workflow", persona_id, scenario_id, simulation_id)
        decisions_made: list[dict] = []
        for step in scenario.workflow_steps:
            decision = self._simulate_step(persona, step, rng=rng)
            decisions_made.append(decision)

        # Behavior metrics derived from decisions
        latencies = [d["decision_latency_ms"] for d in decisions_made]
        hesitations = sum(1 for d in decisions_made if d.get("hesitated"))
        comprehension = self._estimate_comprehension(persona, scenario)

        trace = HumanDecisionTrace(
            persona_id=persona_id,
            scenario_id=scenario_id,
            simulation_id=simulation_id,
            decisions_made=decisions_made,
            visible_state_snapshot={
                "scenario_domain": scenario.domain,
                "steps_executed": len(decisions_made),
            },
            perception_model={
                "noticed_steps": [d["step_name"] for d in decisions_made if d.get("noticed", True)],
                "missed_steps": [d["step_name"] for d in decisions_made if not d.get("noticed", True)],
                "comprehension_score": comprehension,
            },
            behavior_metrics={
                "decision_latency_ms_total": sum(latencies),
                "decision_latency_ms_avg": (sum(latencies) / len(latencies)) if latencies else 0,
                "hesitation_count": hesitations,
                "undo_count": 0,
                "double_submit_attempts": 0,
                "gate_violation_attempts": 0,
                "wrong_project_attempts": 0,
                "stale_data_actions_attempted": 0,
                "mock_as_live_confusions": 0,
                "comprehension_score": comprehension,
                "risk_understanding_score": comprehension * 0.85,
                "final_action_awareness_score": comprehension * 0.7,
                "regret_flag": comprehension < 0.5,
            },
        )
        self._ontology.create(trace)
        return trace

    # ------------------------------------------------------------------
    # L3: Decision simulation
    # ------------------------------------------------------------------

    def simulate_decision(
        self,
        persona_id: str,
        gate_context: dict,
        simulation_id: str,
    ) -> dict:
        persona = self._registry.get(persona_id)
        if persona is None:
            raise ValueError(f"persona not found: {persona_id}")

        # Latency = base * persona's modifier
        modifier = float(persona.behavior_modifiers.get("decision_latency_multiplier", 1.0))
        base_latency = 800
        latency = int(base_latency * modifier)

        # Decision based on capability + risk_tolerance + gate D-level
        d_level = gate_context.get("d_level", "D2")
        comprehension = self._estimate_decision_comprehension(persona, gate_context)

        if persona.capability_level == "beginner" and d_level >= "D3":
            decision = "defer"
        elif persona.risk_tolerance == "low" and d_level >= "D4":
            decision = "defer"
        elif persona.risk_tolerance == "high":
            decision = "approve"
        else:
            decision = "approve" if comprehension > 0.7 else "defer"

        return {
            "persona_id": persona_id,
            "decision": decision,
            "decision_latency_ms": latency,
            "comprehension_score": _clamp_unit(comprehension),
            "d_level": d_level,
            "simulation_id": simulation_id,
        }

    # ------------------------------------------------------------------
    # L4: Error injection
    # ------------------------------------------------------------------

    def inject_error(
        self,
        persona_id: str,
        error_injection_id: str,
        simulation_id: str,
        system_blocks_action: bool = True,
    ) -> dict:
        """Run an error injection. Returns blocked/allowed result.

        For E3: caller declares whether the system blocked the action.
        E5 Guardians will determine this dynamically by inspecting events.
        """
        persona = self._registry.get(persona_id)
        if persona is None:
            raise ValueError(f"persona not found: {persona_id}")
        injection = self._ontology.get(HumanErrorInjection, error_injection_id)
        if injection is None:
            raise ValueError(f"error injection not found: {error_injection_id}")

        if system_blocks_action:
            # Blocked: NearMiss
            quality = self._estimate_message_quality(persona, injection)
            near_miss = HumanNearMiss(
                error_injection_id=error_injection_id,
                blocked_successfully=True,
                operator_message_quality_score=quality,
                future_risk="low" if quality > 0.7 else "medium",
                suggested_ui_improvement=(
                    "" if quality > 0.7
                    else f"persona '{persona.name}' may need clearer error message"
                ),
            )
            self._ontology.create(near_miss)
            return {
                "result": "blocked",
                "near_miss_id": near_miss.near_miss_id,
                "finding_id": None,
                "message_quality": quality,
                "comprehension_score": quality,
                "simulation_id": simulation_id,
            }

        # Not blocked: Finding (high severity per spec).
        # Kimi E8 #4: validate the d_level coming from the injection
        # against the canonical DLevel set before assigning. An injection
        # row with garbled `severity_if_system_allows_error` cannot poison
        # the resulting Finding.
        raw_d = injection.severity_if_system_allows_error
        d_level = raw_d if raw_d in DLevel.values() else DLevel.D2.value
        finding = Finding(
            severity=self._severity_for(d_level),
            d_level=d_level,
            title=f"L4 injection passed: {injection.error_class}",
            description=(
                f"Persona {persona.name} executed {injection.target_action} "
                f"and system did NOT block. "
                f"Expected: {injection.expected_system_response}. "
                f"Simulated target: {injection.simulated_target_d_level}."
            ),
            discovered_by=f"persona_runtime:{persona_id}",
        )
        self._ontology.create(finding)
        return {
            "result": "allowed",
            "near_miss_id": None,
            "finding_id": finding.finding_id,
            "severity": finding.severity,
            "d_level": finding.d_level,
            "comprehension_score": self._estimate_message_quality(persona, injection),
            "simulation_id": simulation_id,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _simulate_step(
        self, persona: Any, step: dict, rng: random.Random | None = None,
    ) -> dict:
        rng = rng or self._rng
        modifier = _safe_float(
            persona.behavior_modifiers.get("decision_latency_multiplier"), 1.0,
        )
        hesitation_prob = _clamp_unit(_safe_float(
            persona.behavior_modifiers.get("hesitation_probability"), 0.1,
        ))
        latency = int(500 * modifier)

        hesitated = rng.random() < hesitation_prob
        if hesitated:
            latency *= 3

        # Beginner persona may miss some steps
        noticed = True
        if persona.capability_level == "beginner":
            noticed = rng.random() > 0.15

        # Sanitize step name (Kimi E8 #5): scenarios.py builds steps from
        # caller strings; coerce to str + truncate so downstream consumers
        # never see arbitrary objects.
        raw_name = step.get("step", "unknown") if isinstance(step, dict) else "unknown"
        safe_name = str(raw_name)[:200]
        return {
            "step_name": safe_name,
            "decision_latency_ms": latency,
            "hesitated": hesitated,
            "noticed": noticed,
        }

    def _estimate_comprehension(self, persona: Any, scenario: HumanScenario) -> float:
        base = {"beginner": 0.55, "intermediate": 0.78, "expert": 0.92}
        b = base.get(persona.capability_level, 0.7)
        # Difficulty penalty
        penalty = {"easy": 0.0, "medium": 0.1, "hard": 0.25}.get(scenario.difficulty, 0.0)
        # Fatigue (NaN/inf guard — Kimi E8 #3)
        fatigue = _clamp_unit(_safe_float(
            persona.dynamic_state.get("fatigue_level"), 0.0,
        ))
        return _clamp_unit(b - penalty - 0.3 * fatigue)

    def _estimate_decision_comprehension(self, persona: Any, gate_context: dict) -> float:
        base = self._estimate_comprehension(persona, _DummyScenario())
        # Higher D-level harder; defensive parse so D10 / unknown fall back to D2.
        d = gate_context.get("d_level", "D2")
        d_num = 2
        if isinstance(d, str) and d.startswith("D") and len(d) >= 2:
            try:
                candidate = int(d[1:])
                if 0 <= candidate <= 5:
                    d_num = candidate
            except ValueError:
                pass
        penalty = max(0.0, (d_num - 2) * 0.08)
        return _clamp_unit(base - penalty)

    def _estimate_message_quality(self, persona: Any, injection: HumanErrorInjection) -> float:
        # Beginner needs clearer messages; expert reads less attentively
        base = {"beginner": 0.6, "intermediate": 0.75, "expert": 0.85}
        return base.get(persona.capability_level, 0.7)

    @staticmethod
    def _severity_for(d_level: str) -> str:
        # Higher D-level breach -> higher severity
        return {"D5": "P0", "D4": "P1", "D3": "P1", "D2": "P2"}.get(d_level, "P3")


class _DummyScenario:
    difficulty = "medium"


__all__ = ["PersonaRuntime"]
