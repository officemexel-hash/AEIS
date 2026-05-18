"""Skills integration layer for pipeline and dispatch execution."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.evidence_spine import EvidenceSpine
from sylion.skills.demand_signal import DemandSignalAnalyzer, get_demand_signal_analyzer
from sylion.skills.executor import SkillsExecutor, get_skills_executor

log = logging.getLogger("sylion.skills.integration")


@dataclass
class SkillExecutionContext:
    skill_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    project_id: str = ""
    pipeline_id: str = ""
    step_id: str = ""
    dispatch_source: str = ""
    actor_id: str = ""
    retention_policy: str = "production-freeze"


class SkillIntegrationLayer:
    """Bridge skills into pipeline steps, dispatch and evidence."""

    def __init__(
        self,
        *,
        executor: SkillsExecutor | None = None,
        demand_analyzer: DemandSignalAnalyzer | None = None,
        evidence_spine: EvidenceSpine | None = None,
        event_bus: EventBus | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._executor = executor or get_skills_executor(db_path=db_path, event_bus=event_bus)
        self._demand_analyzer = demand_analyzer or get_demand_signal_analyzer(db_path=db_path, event_bus=event_bus)
        self._evidence_spine = evidence_spine or EvidenceSpine(db_path=db_path, event_bus=event_bus)

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="skills.integration",
            ))

    def _execute_with_evidence(self, context: SkillExecutionContext, *, source: str) -> dict[str, Any]:
        inputs = dict(context.inputs or {})
        if context.project_id:
            inputs.setdefault("project_id", context.project_id)
        if context.pipeline_id:
            inputs.setdefault("pipeline_id", context.pipeline_id)
        if context.step_id:
            inputs.setdefault("step_id", context.step_id)
        if context.dispatch_source:
            inputs.setdefault("dispatch_source", context.dispatch_source)

        started_at = time.time()
        execution = self._executor.execute(context.skill_id, input_data=inputs)
        evidence = self._evidence_spine.register_json_artifact(
            {
                "skill_id": context.skill_id,
                "project_id": context.project_id,
                "pipeline_id": context.pipeline_id,
                "step_id": context.step_id,
                "dispatch_source": context.dispatch_source,
                "execution": execution,
                "started_at": started_at,
                "finished_at": time.time(),
            },
            source=source,
            artifact_type="skill_execution",
            retention_policy=context.retention_policy,
            metadata={
                "skill_id": context.skill_id,
                "project_id": context.project_id,
                "pipeline_id": context.pipeline_id,
                "step_id": context.step_id,
                "dispatch_source": context.dispatch_source,
            },
            actor_id=context.actor_id,
        )
        result = {
            "ok": execution.get("status") == "completed",
            "skill_id": context.skill_id,
            "project_id": context.project_id,
            "pipeline_id": context.pipeline_id,
            "step_id": context.step_id,
            "dispatch_source": context.dispatch_source,
            "execution": execution,
            "evidence_id": evidence["evidence_id"],
            "evidence_checksum": evidence["checksum"],
            "source": source,
        }
        self._emit("skill.integration.executed", {
            "skill_id": context.skill_id,
            "status": execution.get("status"),
            "evidence_id": evidence["evidence_id"],
            "source": source,
        })
        log.info("integrated skill %s via %s evidence=%s", context.skill_id, source, evidence["evidence_id"])
        return result

    def execute_pipeline_step(
        self,
        skill_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        pipeline_id: str = "",
        step_id: str = "",
        project_id: str = "",
        actor_id: str = "",
        retention_policy: str = "production-freeze",
    ) -> dict[str, Any]:
        return self._execute_with_evidence(
            SkillExecutionContext(
                skill_id=skill_id,
                inputs=inputs or {},
                project_id=project_id,
                pipeline_id=pipeline_id,
                step_id=step_id,
                actor_id=actor_id,
                retention_policy=retention_policy,
            ),
            source="skills.pipeline",
        )

    def dispatch(
        self,
        skill_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        dispatch_source: str = "J5",
        project_id: str = "",
        actor_id: str = "",
        retention_policy: str = "production-freeze",
    ) -> dict[str, Any]:
        return self._execute_with_evidence(
            SkillExecutionContext(
                skill_id=skill_id,
                inputs=inputs or {},
                project_id=project_id,
                dispatch_source=dispatch_source,
                actor_id=actor_id,
                retention_policy=retention_policy,
            ),
            source="skills.dispatch",
        )

    def record_demand_and_analyze(
        self,
        *,
        signal_type: str,
        source: str,
        skill_id: str = "",
        confidence: float = 0.5,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        signal = self._demand_analyzer.record(
            signal_type,
            source=source,
            skill_id=skill_id,
            confidence=confidence,
            details=details or {},
        )
        report = self._demand_analyzer.analyze()
        self._emit("skill.integration.demand_consumed", {
            "signal_id": signal.get("signal_id"),
            "skill_id": skill_id,
            "report_id": report.get("report_id"),
        })
        return {"signal": signal, "report": report}


_integration_layer: SkillIntegrationLayer | None = None


def get_skill_integration_layer(
    *,
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
    evidence_spine: EvidenceSpine | None = None,
) -> SkillIntegrationLayer:
    global _integration_layer
    if _integration_layer is None:
        _integration_layer = SkillIntegrationLayer(
            db_path=db_path,
            event_bus=event_bus,
            evidence_spine=evidence_spine,
        )
    return _integration_layer


def reset_skill_integration_layer() -> None:
    global _integration_layer
    _integration_layer = None
