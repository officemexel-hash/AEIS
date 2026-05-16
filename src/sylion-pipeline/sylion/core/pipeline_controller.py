"""
SYLION Core -- Pipeline Controller

Top-level orchestrator for the idea-to-code pipeline.
Coordinates: Planner, CodeAgent, WorkflowEngine, DecisionGateEngine, EvidenceSpine.

Thread-safe. SQLite-backed for restart recovery.

gRPC planned: SubmitIdea, ExecuteRun, GetRun, ListRuns, CancelRun
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.core.pipeline_controller")


# ---------------------------------------------------------------------------
# PipelineRun dataclass
# ---------------------------------------------------------------------------

@dataclass
class PipelineRun:
    """A single pipeline execution."""
    run_id: str = ""
    idea: str = ""
    status: str = "pending"
    plan: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.run_id:
            self.run_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


# ---------------------------------------------------------------------------
# PipelineController
# ---------------------------------------------------------------------------

class PipelineController:
    """Orchestrates the full idea-to-code pipeline.

    Uses: Planner, CodeAgent, WorkflowEngine, DecisionGateEngine
    Thread-safe. SQLite-backed for restart recovery.
    """

    def __init__(
        self,
        planner=None,
        code_agent=None,
        workflow_engine=None,
        decision_gate=None,
        evidence_spine=None,
        event_bus: EventBus | None = None,
        db_path: str | Path | None = None,
    ):
        # Subsystem references -- all optional for testing
        self._planner = planner
        self._code_agent = code_agent
        self._workflow_engine = workflow_engine
        self._decision_gate = decision_gate
        self._evidence_spine = evidence_spine
        self._event_bus = event_bus

        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # --- Schema -----------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id        TEXT PRIMARY KEY,
                idea          TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'pending',
                plan_json     TEXT NOT NULL DEFAULT '{}',
                steps_json    TEXT NOT NULL DEFAULT '[]',
                context_json  TEXT NOT NULL DEFAULT '{}',
                created_at    REAL NOT NULL,
                completed_at  REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pipeline_status ON pipeline_runs(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pipeline_created ON pipeline_runs(created_at)"
        )
        self._conn.commit()

    # --- Internal helpers -------------------------------------------------------

    def _run_from_row(self, row: sqlite3.Row) -> dict:
        return {
            "run_id": row["run_id"],
            "idea": row["idea"],
            "status": row["status"],
            "plan": json.loads(row["plan_json"]),
            "steps": json.loads(row["steps_json"]),
            "context": json.loads(row["context_json"]),
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    def _persist_run(self, run: PipelineRun, context: dict | None = None):
        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO pipeline_runs
                (run_id, idea, status, plan_json, steps_json, context_json, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                run.idea,
                run.status,
                json.dumps(run.plan, default=str),
                json.dumps(run.steps, default=str),
                json.dumps(context or {}, default=str),
                run.created_at,
                run.completed_at,
            ))
            self._conn.commit()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="core.pipeline_controller",
            ))

    # --- Public API -------------------------------------------------------------

    def submit_idea(self, idea: str, context: dict | None = None) -> dict:
        """Submit an idea and start the pipeline.

        Steps:
        1. Create PipelineRun record (status="pending")
        2. Emit event "pipeline.idea_submitted"
        3. Return {"run_id": ..., "status": "pending"}

        Does NOT block. Use execute_run() to actually run it.
        """
        run = PipelineRun(idea=idea)
        self._persist_run(run, context)
        self._emit("pipeline.idea_submitted", {"run_id": run.run_id, "idea": idea})
        log.info("idea submitted: %s", run.run_id[:12])
        return {"run_id": run.run_id, "status": "pending"}

    def execute_run(self, run_id: str) -> dict:
        """Execute a pipeline run. This is the main orchestrator.

        Steps:
        1. Load run from DB, set status="planning"
        2. If planner available: planner.decompose(idea) -> plan
        3. Set status="generating"
        4. For each step in plan:
           a. If code_agent available: code_agent.generate(step["description"])
           b. Record step result
           c. If decision_gate available: gate.evaluate(step) -> check if approved
           d. If not approved, mark step as failed, continue
        5. Set status="complete" (or "failed" if any step failed)
        6. Emit event "pipeline.run_completed"
        7. Return full run dict

        All steps are wrapped in try/except -- a failure in one step records the error
        but doesn't crash the controller. Failed steps get status="failed".
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row:
                return {"error": f"run {run_id} not found"}
            context = json.loads(row["context_json"])

        run = PipelineRun(
            run_id=row["run_id"],
            idea=row["idea"],
            status=row["status"],
            plan=json.loads(row["plan_json"]),
            steps=json.loads(row["steps_json"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

        # ---- Phase 1: Planning ------------------------------------------------
        run.status = "planning"
        self._persist_run(run, context)
        self._emit("pipeline.run_planning", {"run_id": run.run_id})

        if self._planner is not None:
            try:
                run.plan = self._planner.decompose_idea(run.idea)
                log.info("plan generated for %s: %d steps", run.run_id[:12], len(run.plan.get("steps", [])))
            except Exception:
                log.exception("planner failed for run %s", run.run_id[:12])
                run.status = "failed"
                run.completed_at = time.time()
                self._persist_run(run, context)
                self._emit("pipeline.run_failed", {
                    "run_id": run.run_id, "phase": "planning",
                    "error": "planner.decompose() raised exception",
                })
                return self._run_from_row(
                    self._conn.execute("SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
                )

        # ---- Phase 2: Generating & Reviewing ----------------------------------
        run.status = "generating"
        self._persist_run(run, context)
        self._emit("pipeline.run_generating", {"run_id": run.run_id})

        steps = run.plan.get("steps", [])
        if not steps:
            # No steps from planner -- treat as single-step idea
            steps = [{"step_id": "s1", "name": "idea", "description": run.idea}]

        any_failed = False
        for step_def in steps:
            step_id = step_def.get("step_id", uuid.uuid4().hex[:8])
            step_record = {
                "step_id": step_id,
                "name": step_def.get("name", ""),
                "description": step_def.get("description", ""),
                "status": "pending",
                "result": {},
            }

            try:
                # Generate code
                if self._code_agent is not None:
                    step_record["status"] = "generating"
                    result = self._code_agent.generate(step_record["description"])
                    step_record["result"] = result if isinstance(result, dict) else {"output": str(result)}
                    if step_record["result"].get("metadata", {}).get("quality_guard_failed"):
                        step_record["status"] = "failed"
                        step_record["result"]["quality_gate"] = {
                            "result": "fail",
                            "reason": "placeholder_or_generic_output_after_repair",
                            "blocks": "pipeline execution",
                        }
                        any_failed = True
                        run.steps.append(step_record)
                        continue
                    step_record["status"] = "reviewing"
                else:
                    step_record["status"] = "reviewing"
                    step_record["result"] = {"output": "skipped (no code_agent)"}

                # Evaluate gate
                if self._decision_gate is not None:
                    gate_id = f"pipeline_step_{step_id}"
                    # Ensure gate is registered (auto-register if not)
                    try:
                        from sylion.core.decision_gate_engine import GateDefinition
                        if hasattr(self._decision_gate, "_gates") and gate_id not in self._decision_gate._gates:
                            self._decision_gate.register_gate(GateDefinition(
                                gate_id=gate_id,
                                name=f"Pipeline step: {step_record.get('name', step_id)}",
                                description="Auto-registered pipeline step gate",
                                fail_condition="step raises exception",
                                blocks="pipeline execution",
                            ))
                    except Exception:
                        pass
                    gate_result = self._decision_gate.evaluate_gate(gate_id, step_record)
                    gate_val = gate_result.get("result", "pass")
                    approved = str(gate_val) not in ("fail", "GateResult.FAIL")
                    if not approved:
                        step_record["status"] = "failed"
                        step_record["result"]["gate"] = gate_result
                        any_failed = True
                        log.warning("gate rejected step %s in run %s", step_id, run.run_id[:12])
                    else:
                        step_record["status"] = "complete"
                        step_record["result"]["gate"] = gate_result
                else:
                    step_record["status"] = "complete"

            except Exception:
                log.exception("step %s failed in run %s", step_id, run.run_id[:12])
                step_record["status"] = "failed"
                step_record["result"]["error"] = "step execution raised exception"
                any_failed = True

            run.steps.append(step_record)

        quality_findings = []
        for step in run.steps:
            result = step.get("result", {}) if isinstance(step, dict) else {}
            metadata = result.get("metadata", {}) if isinstance(result, dict) else {}
            for finding in metadata.get("quality_findings", []) or []:
                quality_findings.append({
                    "step_id": step.get("step_id"),
                    "step_name": step.get("name"),
                    "finding": finding,
                })

        run.plan["product_artifact"] = {
            "contract": "AEIS product artifact v1",
            "run_id": run.run_id,
            "idea": run.idea,
            "step_count": len(run.steps),
            "completed_steps": sum(1 for step in run.steps if step.get("status") == "complete"),
            "failed_steps": sum(1 for step in run.steps if step.get("status") == "failed"),
            "model_trace": sorted({
                str((step.get("result") or {}).get("model_id") or "")
                for step in run.steps
                if (step.get("result") or {}).get("model_id")
            }),
            "quality_findings": quality_findings,
            "quality_gate": "failed" if quality_findings or any_failed else "passed",
        }

        # ---- Phase 3: Finalize ------------------------------------------------
        if any_failed:
            run.status = "failed"
            run.completed_at = time.time()
            self._persist_run(run, context)
            self._emit("pipeline.run_failed", {"run_id": run.run_id})
            log.info("run %s completed with failures", run.run_id[:12])
        else:
            run.status = "complete"
            run.completed_at = time.time()
            self._persist_run(run, context)
            self._emit("pipeline.run_completed", {"run_id": run.run_id})
            log.info("run %s completed successfully", run.run_id[:12])

        # Return fresh state from DB
        with self._lock:
            final_row = self._conn.execute(
                "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._run_from_row(final_row)

    def get_run(self, run_id: str) -> dict | None:
        """Get pipeline run status."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if not row:
            return None
        return self._run_from_row(row)

    def list_runs(self, status: str | None = None, limit: int = 50) -> list[dict]:
        """List pipeline runs."""
        with self._lock:
            q = "SELECT * FROM pipeline_runs WHERE 1=1"
            params: list[Any] = []
            if status:
                q += " AND status = ?"
                params.append(status)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(q, params).fetchall()
        return [self._run_from_row(r) for r in rows]

    def cancel_run(self, run_id: str) -> dict:
        """Cancel a running pipeline."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row:
                return {"error": f"run {run_id} not found"}

            current_status = row["status"]
            if current_status in ("complete", "failed"):
                return {"run_id": run_id, "status": current_status, "message": "run already finished"}

            self._conn.execute(
                "UPDATE pipeline_runs SET status = 'cancelled', completed_at = ? WHERE run_id = ?",
                (time.time(), run_id),
            )
            self._conn.commit()

        self._emit("pipeline.run_cancelled", {"run_id": run_id})
        log.info("run %s cancelled (was %s)", run_id[:12], current_status)
        return {"run_id": run_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_controller: PipelineController | None = None


def get_pipeline_controller(
    planner=None,
    code_agent=None,
    workflow_engine=None,
    decision_gate=None,
    evidence_spine=None,
    event_bus: EventBus | None = None,
    db_path: str | Path | None = None,
) -> PipelineController:
    global _controller
    if _controller is None:
        _controller = PipelineController(
            planner=planner,
            code_agent=code_agent,
            workflow_engine=workflow_engine,
            decision_gate=decision_gate,
            evidence_spine=evidence_spine,
            event_bus=event_bus,
            db_path=db_path,
        )
    return _controller


def reset_pipeline_controller():
    """Reset the global singleton. For testing only."""
    global _controller
    _controller = None
