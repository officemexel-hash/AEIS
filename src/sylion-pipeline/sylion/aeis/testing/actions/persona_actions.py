"""W14 persona actions (6): register / scenario / simulate workflow|decision / inject error / record_comprehension.

Note: simulate_*, inject_human_error are E2 STUBS — real execution requires
E3 PersonaRuntime + SimulationEngine. Stubs validate payloads, create
ontology records (HumanDecisionTrace, Finding, NearMiss) and return
notes about E3 dependency.
"""
from __future__ import annotations

from sylion.aeis.testing.actions.base import TestingActionHandler
from sylion.aeis.testing.ontology.enums import (
    DLevel, GateType, PersonaCapability, Severity,
)
from sylion.aeis.testing.ontology.objects import (
    Finding, HumanDecisionTrace, HumanErrorInjection,
    HumanNearMiss, HumanPersona, HumanScenario,
)


class RegisterPersonaHandler(TestingActionHandler):
    target_action: str = "register_persona"
    d_level: DLevel = DLevel.D1
    phase: str = "IMMEDIATE"
    mirror_to_ticket: bool = False

    def validate(self, payload: dict) -> None:
        self._require_keys(payload, "persona_data")
        pd = payload["persona_data"]
        if not isinstance(pd, dict):
            raise ValueError("register_persona: persona_data must be dict")
        for f in ("name", "capability_level", "error_proneness",
                  "attention_span_min", "trust_in_ai_baseline",
                  "risk_tolerance", "dynamic_state", "behavior_modifiers"):
            if f not in pd:
                raise ValueError(f"register_persona: persona_data missing field: {f}")
        if pd["capability_level"] not in PersonaCapability.values():
            raise ValueError(
                f"register_persona: invalid capability_level: {pd['capability_level']}"
            )

    def execute(self, payload: dict, intent_id: str) -> dict:
        pd = payload["persona_data"]
        persona = HumanPersona(
            name=pd["name"],
            capability_level=pd["capability_level"],
            expertise_domains=list(pd.get("expertise_domains", [])),
            error_proneness=float(pd["error_proneness"]),
            attention_span_min=int(pd["attention_span_min"]),
            trust_in_ai_baseline=float(pd["trust_in_ai_baseline"]),
            risk_tolerance=pd["risk_tolerance"],
            dynamic_state=pd["dynamic_state"],
            behavior_modifiers=pd["behavior_modifiers"],
        )
        if self.ontology is not None:
            self.ontology.create(persona)
        self._emit("aeis.testing.human.persona_registered", {
            "persona_id": persona.persona_id,
            "name": persona.name,
        }, trace_id=intent_id)
        return {"persona_id": persona.persona_id}


class RegisterHumanScenarioHandler(TestingActionHandler):
    target_action: str = "register_human_scenario"
    d_level: DLevel = DLevel.D2
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.NON_BLOCKING

    def validate(self, payload: dict) -> None:
        self._require_keys(payload, "scenario_data", "registered_by")
        sd = payload["scenario_data"]
        for f in ("persona_id", "domain", "workflow_steps",
                  "decision_points", "success_criteria",
                  "comprehension_check", "difficulty"):
            if f not in sd:
                raise ValueError(f"register_human_scenario: missing field: {f}")
        if sd["difficulty"] not in ("easy", "medium", "hard"):
            raise ValueError(
                f"register_human_scenario: difficulty must be easy/medium/hard, "
                f"got: {sd['difficulty']}"
            )

    def execute(self, payload: dict, intent_id: str) -> dict:
        sd = payload["scenario_data"]
        scenario = HumanScenario(
            persona_id=sd["persona_id"],
            domain=sd["domain"],
            workflow_steps=list(sd["workflow_steps"]),
            decision_points=list(sd["decision_points"]),
            success_criteria=list(sd["success_criteria"]),
            comprehension_check=sd["comprehension_check"],
            difficulty=sd["difficulty"],
        )
        if self.ontology is not None:
            self.ontology.create(scenario)
        self._mirror_ticket(
            project_id="",
            title=f"Register human scenario for {sd['persona_id']}",
            summary=f"Domain: {sd['domain']}, difficulty: {sd['difficulty']}",
            payload={"scenario_id": scenario.scenario_id},
            requested_by=payload["registered_by"],
        )
        self._emit("aeis.testing.human.scenario_registered", {
            "scenario_id": scenario.scenario_id,
            "persona_id": scenario.persona_id,
        }, trace_id=intent_id)
        return {"scenario_id": scenario.scenario_id}


class SimulateHumanWorkflowHandler(TestingActionHandler):
    target_action: str = "simulate_human_workflow"
    d_level: DLevel = DLevel.D1
    phase: str = "IMMEDIATE"
    mirror_to_ticket: bool = False

    def validate(self, payload: dict) -> None:
        self._require_keys(payload, "persona_id", "scenario_id", "simulation_id")

    def execute(self, payload: dict, intent_id: str) -> dict:
        # E2 stub: create HumanDecisionTrace placeholder
        if self.ontology is None:
            raise RuntimeError("simulate_human_workflow: ontology not configured")
        trace = HumanDecisionTrace(
            persona_id=payload["persona_id"],
            scenario_id=payload["scenario_id"],
            simulation_id=payload["simulation_id"],
            decisions_made=[],
            visible_state_snapshot={"_e2_stub": True},
            perception_model={"_e2_stub": True},
            behavior_metrics={"_e2_stub": True, "comprehension_score": 0.0},
        )
        self.ontology.create(trace)
        self._emit("aeis.testing.human.workflow_simulated", {
            "trace_id": trace.trace_id,
            "persona_id": payload["persona_id"],
        })
        return {
            "trace_id": trace.trace_id,
            "note": "E2 stub: real simulation requires E3 PersonaRuntime + SimulationEngine",
        }


class SimulateHumanDecisionHandler(TestingActionHandler):
    target_action: str = "simulate_human_decision"
    d_level: DLevel = DLevel.D1
    phase: str = "IMMEDIATE"
    mirror_to_ticket: bool = False

    def validate(self, payload: dict) -> None:
        self._require_keys(payload, "persona_id", "gate_context", "simulation_id")

    def execute(self, payload: dict, intent_id: str) -> dict:
        # E2 stub: deterministic placeholder
        self._emit("aeis.testing.human.decision_simulated", {
            "persona_id": payload["persona_id"],
            "simulation_id": payload["simulation_id"],
            "_e2_stub": True,
        }, trace_id=intent_id)
        return {
            "decision": "defer",  # safe default for stub
            "latency_ms": 0,
            "comprehension_score": 0.0,
            "note": "E2 stub: real decision simulation requires E3 PersonaRuntime",
        }


_DLEVEL_RANK: dict[str, int] = {
    DLevel.D0.value: 0, DLevel.D1.value: 1, DLevel.D2.value: 2,
    DLevel.D3.value: 3, DLevel.D4.value: 4, DLevel.D5.value: 5,
}


def _max_d_level(*levels: str) -> str:
    """Return the highest-rank DLevel string among inputs."""
    best = max(
        (lvl for lvl in levels if lvl in _DLEVEL_RANK),
        key=lambda lvl: _DLEVEL_RANK[lvl],
        default=DLevel.D2.value,
    )
    return best


class InjectHumanErrorHandler(TestingActionHandler):
    """L4 error injection.

    action_d_level=D2 (running the test).
    finding_d_level = max(simulated_target_d_level, severity_if_system_allows_error).

    Caller must report the observed system response via the ``system_blocks``
    boolean in the payload (True if the system correctly blocked the action,
    False if it did not). E3 PersonaRuntime supplies this; for unit tests the
    flag is passed directly. When system_blocks=False we open a Finding at
    finding_d_level=max(simulated_target, severity_if_allowed); when True we
    record a NearMiss instead.
    """

    target_action: str = "inject_human_error"
    d_level: DLevel = DLevel.D2
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.NON_BLOCKING

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "persona_id", "error_injection_id", "simulation_id",
            "system_blocks",
        )
        self._require_prefix(payload, "error_injection_id", "hei_")
        if not isinstance(payload["system_blocks"], bool):
            raise ValueError("inject_human_error: system_blocks must be bool")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("inject_human_error: ontology not configured")
        injection = self.ontology.get(
            HumanErrorInjection, payload["error_injection_id"]
        )
        if injection is None:
            raise ValueError(
                f"error injection not found: {payload['error_injection_id']}"
            )

        finding_d_level = _max_d_level(
            injection.simulated_target_d_level,
            injection.severity_if_system_allows_error,
        )

        if payload["system_blocks"]:
            quality = float(payload.get("operator_message_quality_score", 0.7))
            near_miss = HumanNearMiss(
                error_injection_id=injection.injection_id,
                blocked_successfully=True,
                operator_message_quality_score=quality,
                future_risk=payload.get(
                    "future_risk",
                    "low" if quality > 0.7 else "medium",
                ),
                suggested_ui_improvement=payload.get("suggested_ui_improvement", ""),
            )
            self.ontology.create(near_miss)
            self._emit("aeis.testing.human.error_injected", {
                "injection_id": injection.injection_id,
                "persona_id": payload["persona_id"],
                "trace_id": intent_id,
            })
            self._emit("aeis.testing.human.error_blocked", {
                "near_miss_id": near_miss.near_miss_id,
                "trace_id": intent_id,
            })
            self._mirror_ticket(
                project_id=payload.get("project_id", ""),
                title=f"Human error blocked: {injection.error_class}",
                summary=(
                    f"target={injection.target_action} "
                    f"sim_target={injection.simulated_target_d_level} "
                    f"sev_if_allowed={injection.severity_if_system_allows_error}"
                ),
                payload={
                    "injection_id": injection.injection_id,
                    "near_miss_id": near_miss.near_miss_id,
                    "intent_id": intent_id,
                },
            )
            return {
                "result": "blocked",
                "near_miss_id": near_miss.near_miss_id,
                "finding_id": None,
                "finding_d_level": finding_d_level,
            }

        # System failed to block — escalate to Finding at the elevated D-level.
        finding = Finding(
            severity=Severity.P0.value
            if finding_d_level in (DLevel.D4.value, DLevel.D5.value)
            else Severity.P1.value,
            d_level=finding_d_level,
            title=f"L4 injection passed: {injection.error_class}",
            description=(
                f"Persona {payload['persona_id']} executed "
                f"{injection.target_action}; system did NOT block. "
                f"Expected: {injection.expected_system_response}. "
                f"Severity-if-allowed: {injection.severity_if_system_allows_error}; "
                f"simulated target D-level: {injection.simulated_target_d_level}."
            ),
            discovered_by=f"persona:{payload['persona_id']}",
        )
        self.ontology.create(finding)
        self._emit("aeis.testing.human.error_injected", {
            "injection_id": injection.injection_id,
            "persona_id": payload["persona_id"],
            "trace_id": intent_id,
        })
        self._emit("aeis.testing.human.error_allowed", {
            "finding_id": finding.finding_id,
            "trace_id": intent_id,
        })
        self._emit("aeis.testing.finding.detected", {
            "finding_id": finding.finding_id,
            "d_level": finding_d_level,
            "trace_id": intent_id,
        })
        self._mirror_ticket(
            project_id=payload.get("project_id", ""),
            title=f"L4 INJECTION PASSED: {injection.error_class}",
            summary=(
                f"target={injection.target_action} "
                f"finding_d_level={finding_d_level}"
            ),
            payload={
                "injection_id": injection.injection_id,
                "finding_id": finding.finding_id,
                "intent_id": intent_id,
            },
            gate_type_override=GateType.BLOCKING,
        )
        return {
            "result": "allowed",
            "near_miss_id": None,
            "finding_id": finding.finding_id,
            "finding_d_level": finding_d_level,
            "severity": finding.severity,
        }


class RecordComprehensionFindingHandler(TestingActionHandler):
    target_action: str = "record_comprehension_finding"
    d_level: DLevel = DLevel.D1
    phase: str = "IMMEDIATE"
    mirror_to_ticket: bool = False

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "persona_id", "scenario_id",
            "comprehension_score", "ui_element", "misunderstood_text",
        )
        self._require_in_range(payload, "comprehension_score", 0.0, 1.0)

    def execute(self, payload: dict, intent_id: str) -> dict:
        finding = Finding(
            severity=Severity.P3.value,
            d_level=DLevel.D2.value,
            title=f"UX comprehension failure on {payload['ui_element']}",
            description=(
                f"Persona {payload['persona_id']} did not understand: "
                f"{payload['misunderstood_text'][:200]}. "
                f"Score: {payload['comprehension_score']:.2f}"
            ),
            discovered_by=f"persona:{payload['persona_id']}",
        )
        if self.ontology is not None:
            self.ontology.create(finding)
        self._emit("aeis.testing.human.comprehension_failed", {
            "persona_id": payload["persona_id"],
            "scenario_id": payload["scenario_id"],
            "score": payload["comprehension_score"],
        }, trace_id=intent_id)
        self._emit("aeis.testing.finding.detected", {
            "finding_id": finding.finding_id,
            "severity": finding.severity,
        }, trace_id=intent_id)
        return {"finding_id": finding.finding_id}


PERSONA_HANDLERS = (
    RegisterPersonaHandler,
    RegisterHumanScenarioHandler,
    SimulateHumanWorkflowHandler,
    SimulateHumanDecisionHandler,
    InjectHumanErrorHandler,
    RecordComprehensionFindingHandler,
)
