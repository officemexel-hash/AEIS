"""SimulationEngine — orchestrates L0 contract + L1 sandbox + L2-L4 stubs.

E3 scope:
- start(contract) -> simulation_id, instantiates TransactionalSandbox
- run_layer(simulation_id, layer, payload) -> dict
    L1: program execution stub (sandbox-side)
    L2: workflow simulation stub (delegates to PersonaRuntime in E3.2)
    L3: decision simulation stub
    L4: error injection stub
- collect_evidence(simulation_id) -> SimulationEvidence persisted to parent
- discard(simulation_id) -> drops sandbox state
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sylion.aeis.testing.ontology.objects import (
    SimulationBranch, SimulationContract, SimulationEvidence,
)
from sylion.aeis.testing.ontology.store import OntologyStore
from sylion.aeis.testing.simulation.sandbox import TransactionalSandbox

log = logging.getLogger("sylion.aeis.testing.simulation.engine")


class SimulationEngine:
    """Orchestrator for L0-L4 simulations."""

    VALID_LAYERS = (1, 2, 3, 4)

    def __init__(
        self,
        ontology: OntologyStore,
        event_bus: Any | None = None,
        snapshot_base_dir: str | None = None,
        cleanup_orphans_on_init: bool = True,
    ) -> None:
        self._ontology = ontology
        self._event_bus = event_bus
        self._snapshot_base_dir = snapshot_base_dir
        self._active: dict[str, dict] = {}  # simulation_id -> {sandbox, contract, sim_branch}
        if cleanup_orphans_on_init:
            # Crash recovery: prune sim_*_*.db files left behind by a
            # previous process. Active set is empty on init by design —
            # callers can register active sims explicitly via attach().
            try:
                TransactionalSandbox.cleanup_orphans(
                    active_simulation_ids=set(),
                    base_dir=snapshot_base_dir,
                )
            except Exception:  # pragma: no cover
                log.exception("cleanup_orphans on init failed")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        contract: SimulationContract,
        in_memory: bool = False,
    ) -> str:
        """Start sandbox for a new simulation. Returns simulation_id."""
        if contract.simulation_id in self._active:
            raise RuntimeError(
                f"simulation already active: {contract.simulation_id}"
            )
        # Persist contract + branch
        self._ontology.create(contract)
        sim_branch = SimulationBranch(
            sim_branch_id=f"simb_{uuid.uuid4().hex[:12]}",
            contract_id=contract.contract_id,
            state="open",
        )

        sandbox = TransactionalSandbox(
            simulation_id=contract.simulation_id,
            in_memory=in_memory,
            snapshot_base_dir=self._snapshot_base_dir,
        )
        sandbox.start()
        # Persist the snapshot path so crash-recovery can join the dots
        # between the SimulationBranch row and the on-disk sandbox file.
        if sandbox.snapshot is not None:
            sim_branch.snapshot_db_path = str(sandbox.snapshot.path)
        self._ontology.create(sim_branch)

        self._active[contract.simulation_id] = {
            "sandbox": sandbox,
            "contract": contract,
            "sim_branch": sim_branch,
            "started_at": time.time(),
            "max_layer": 0,
        }
        self._emit("aeis.testing.simulation.branch_created", {
            "simulation_id": contract.simulation_id,
            "sim_branch_id": sim_branch.sim_branch_id,
            "snapshot_db_path": sim_branch.snapshot_db_path,
        })
        log.info("simulation started: %s (branch=%s, snapshot=%s)",
                 contract.simulation_id[:12], sim_branch.sim_branch_id[:12],
                 sim_branch.snapshot_db_path)
        return contract.simulation_id

    def run_layer(self, simulation_id: str, layer: int, payload: dict) -> dict:
        """Execute a layer in the active sandbox."""
        if layer not in self.VALID_LAYERS:
            raise ValueError(f"layer must be in {self.VALID_LAYERS}, got: {layer}")
        if simulation_id not in self._active:
            raise ValueError(f"simulation not active: {simulation_id}")
        ctx = self._active[simulation_id]
        sandbox: TransactionalSandbox = ctx["sandbox"]
        contract: SimulationContract = ctx["contract"]

        # Safety check: have we exceeded budget?
        m = sandbox.metrics()
        safety = contract.safety
        if m["action_count"] >= safety["max_actions"]:
            raise RuntimeError(
                f"max_actions exceeded ({safety['max_actions']})"
            )
        if m["cost_usd"] >= safety["max_cost_usd"]:
            raise RuntimeError(
                f"max_cost_usd exceeded ({safety['max_cost_usd']})"
            )
        if m["duration_s"] >= safety["max_runtime_seconds"]:
            raise RuntimeError(
                f"max_runtime_seconds exceeded ({safety['max_runtime_seconds']})"
            )

        sandbox.record_action()
        result = self._dispatch_layer(layer, sandbox, payload)
        # Track the highest layer reached so collect_evidence can persist
        # an accurate ``layer_executed`` rather than always reporting 4.
        if layer > ctx["max_layer"]:
            ctx["max_layer"] = layer
        return result

    def collect_evidence(
        self,
        simulation_id: str,
        screenshots_uri: list[str] | None = None,
    ) -> SimulationEvidence:
        """Snapshot sandbox state and persist as SimulationEvidence."""
        if simulation_id not in self._active:
            raise ValueError(f"simulation not active: {simulation_id}")
        ctx = self._active[simulation_id]
        sandbox: TransactionalSandbox = ctx["sandbox"]
        sim_branch: SimulationBranch = ctx["sim_branch"]
        snap = sandbox.collect_evidence()

        # Prefer the file-content hash from the snapshot when available
        # (verifiable against the on-disk sandbox), fall back to a hash
        # of the ontology-health dict for the in-memory case.
        snapshot_hash = snap.get("snapshot_hash") or self._hash_dict(
            snap["ontology_health"]
        )
        layer_executed = max(int(ctx.get("max_layer", 0)), 1)
        evidence = SimulationEvidence(
            simulation_id=simulation_id,
            sim_branch_id=sim_branch.sim_branch_id,
            trace_id=simulation_id,
            layer_executed=layer_executed,
            screenshots_uri=list(screenshots_uri or []),
            event_log=snap["event_log"],
            branch_snapshot_hash=snapshot_hash,
            evaluator_outputs={"metrics": snap["metrics"]},
        )
        self._ontology.create(evidence)
        self._emit("aeis.testing.simulation.evidence_collected", {
            "evidence_id": evidence.evidence_id,
            "simulation_id": simulation_id,
            "layer_executed": layer_executed,
        })
        return evidence

    def discard(self, simulation_id: str, reason: str = "") -> None:
        """Tear down sandbox; persist sim_branch state=discarded.

        Order matters: the on-disk snapshot is removed *before* we drop
        the in-memory registry entry, so a crash mid-discard leaves the
        registry referencing a missing file (recoverable via
        ``cleanup_orphans``) rather than the file referencing a missing
        registry entry (orphan we can't link back).
        """
        if simulation_id not in self._active:
            return
        ctx = self._active[simulation_id]
        sandbox: TransactionalSandbox = ctx["sandbox"]
        sim_branch: SimulationBranch = ctx["sim_branch"]

        # 1. File-system cleanup first (idempotent).
        try:
            sandbox.discard()
        except Exception:  # pragma: no cover
            log.exception("sandbox discard raised; continuing")

        # 2. Persist the discarded state on the SimulationBranch row so
        #    crash-recovery can tell whether the entry was already torn
        #    down or just abandoned.
        sim_branch.state = "discarded"
        sim_branch.discard_reason = reason or "auto-discard after run"
        sim_branch.discarded_at = time.time()
        try:
            self._ontology.update(sim_branch)
        except Exception:  # pragma: no cover
            log.exception("sim_branch update raised; continuing")

        # 3. Finally drop the in-memory active entry.
        self._active.pop(simulation_id, None)

        self._emit("aeis.testing.simulation.branch_discarded", {
            "simulation_id": simulation_id,
            "sim_branch_id": sim_branch.sim_branch_id,
            "reason": reason,
        })
        log.info("simulation discarded: %s", simulation_id[:12])

    def get_metrics(self, simulation_id: str) -> dict:
        if simulation_id not in self._active:
            raise ValueError(f"simulation not active: {simulation_id}")
        return self._active[simulation_id]["sandbox"].metrics()

    # ------------------------------------------------------------------
    # Layer dispatch (E3 stubs)
    # ------------------------------------------------------------------

    def _dispatch_layer(
        self, layer: int, sandbox: TransactionalSandbox, payload: dict,
    ) -> dict:
        if layer == 1:
            return self._l1_program(sandbox, payload)
        if layer == 2:
            return self._l2_workflow(sandbox, payload)
        if layer == 3:
            return self._l3_decision(sandbox, payload)
        if layer == 4:
            return self._l4_error(sandbox, payload)
        raise ValueError(f"unknown layer: {layer}")

    def _l1_program(self, sandbox: TransactionalSandbox, payload: dict) -> dict:
        """L1: arbitrary program execution in the sandbox.

        The caller typically uses sandbox.ontology / sandbox.llm directly.
        This method just records the call as an action.
        """
        return {
            "layer": 1,
            "action": "program_step",
            "payload_keys": list(payload.keys()),
            "ok": True,
        }

    def _l2_workflow(self, sandbox: TransactionalSandbox, payload: dict) -> dict:
        """L2 stub: real impl handed to PersonaRuntime.simulate_workflow."""
        return {
            "layer": 2,
            "ok": True,
            "note": "L2 stub: invoke PersonaRuntime.simulate_workflow",
        }

    def _l3_decision(self, sandbox: TransactionalSandbox, payload: dict) -> dict:
        """L3 stub: real impl handed to PersonaRuntime.simulate_decision."""
        return {
            "layer": 3,
            "ok": True,
            "note": "L3 stub: invoke PersonaRuntime.simulate_decision",
        }

    def _l4_error(self, sandbox: TransactionalSandbox, payload: dict) -> dict:
        """L4 stub: real impl handed to PersonaRuntime.inject_error."""
        return {
            "layer": 4,
            "ok": True,
            "note": "L4 stub: invoke PersonaRuntime.inject_error",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_dict(d: dict) -> str:
        import hashlib
        import json
        return hashlib.sha256(
            json.dumps(d, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def _emit(self, event_type: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_type=event_type,
                payload=payload,
                producer_module="aeis.testing.simulation",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed (%s): %s", event_type, e)


__all__ = ["SimulationEngine"]
