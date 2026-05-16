"""W14 Self-Audit — runs W14 on itself.

Verifies that the testing infrastructure can audit its own modules:
  - Ontology Store smoke (CRUD per object kind)
  - Actions registration smoke (20 handlers)
  - Branches + Simulation lifecycle smoke
  - Personas + Runtime smoke
  - Auto-Repair + Loop Governor + Merge Guard smoke
  - 13 Guardians smoke
  - Truth Alignment smoke
  - Charter + Findings store smoke
  - Release Rail smoke
  - Memory store smoke

Returns a dict per the W14SelfAudit canonical contract (sec 32.7).
"""
from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field

log = logging.getLogger("sylion.aeis.testing.self_audit")


@dataclass
class AuditResult:
    pillar: str
    status: str  # "pass" | "fail"
    details: dict = field(default_factory=dict)
    duration_s: float = 0.0
    error: str | None = None


class W14SelfAudit:
    """Run smoke checks across all W14 pillars."""

    def __init__(self) -> None:
        self.results: list[AuditResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_full_cycle(self) -> dict:
        """Run all 10 pillar smoke tests. Returns aggregate dict."""
        t0 = time.time()
        self.results = []
        self._check_ontology()
        self._check_actions()
        self._check_branches_and_simulation()
        self._check_personas_and_runtime()
        self._check_auto_repair_loop_merge()
        self._check_guardians()
        self._check_truth_alignment()
        self._check_charter_findings_stores()
        self._check_release_rail()
        self._check_memory()
        total_s = time.time() - t0

        passed = sum(1 for r in self.results if r.status == "pass")
        return {
            "status": "pass" if passed == len(self.results) else "fail",
            "total_pillars": len(self.results),
            "passed": passed,
            "failed": len(self.results) - passed,
            "duration_s": total_s,
            "results": [
                {
                    "pillar": r.pillar, "status": r.status,
                    "details": r.details, "duration_s": r.duration_s,
                    "error": r.error,
                } for r in self.results
            ],
        }

    # ------------------------------------------------------------------
    # Pillar checks
    # ------------------------------------------------------------------

    def _check_ontology(self) -> None:
        with self._timed("ontology") as r:
            from sylion.aeis.testing.ontology import ALL_OBJECTS, OntologyStore
            store = OntologyStore()
            r.details["object_kinds"] = len(ALL_OBJECTS)
            r.details["health"] = store.health()
            assert len(ALL_OBJECTS) >= 25

    def _check_actions(self) -> None:
        with self._timed("actions") as r:
            from sylion.aeis.testing.actions import (
                ALL_HANDLER_CLASSES, register_testing_actions,
            )
            from sylion.aeis.testing.ontology import OntologyStore
            store = OntologyStore()
            handlers = register_testing_actions(ontology=store)
            r.details["handler_count"] = len(handlers)
            r.details["expected_at_least"] = 19
            assert len(ALL_HANDLER_CLASSES) >= 19
            assert len(handlers) >= 19

    def _check_branches_and_simulation(self) -> None:
        with self._timed("branches+simulation") as r:
            from sylion.aeis.testing.branches import BranchManager
            from sylion.aeis.testing.ontology import OntologyStore
            from sylion.aeis.testing.simulation import (
                SimulationEngine, build_contract,
            )
            store = OntologyStore()
            mgr = BranchManager(ontology=store)
            br = mgr.create_branch(
                "simulation",
                parent_branch_id=None,
                project_id="proj_audit",
                sot_version="v1",
                masterplan_version="v1",
            )
            engine = SimulationEngine(
                ontology=store, cleanup_orphans_on_init=False,
            )
            ctx = build_contract(
                simulation_id=f"sim_audit_{int(time.time())}",
                branch_id=br.branch_id,
                source_project_id="proj_audit",
                sot_version="v1", masterplan_version="v1",
            )
            sid = engine.start(ctx, in_memory=True)
            engine.run_layer(sid, 1, {})
            engine.collect_evidence(sid)
            engine.discard(sid, reason="self_audit")
            r.details["sim_lifecycle_ok"] = True

    def _check_personas_and_runtime(self) -> None:
        with self._timed("personas+runtime") as r:
            from sylion.aeis.testing.ontology import OntologyStore
            from sylion.aeis.testing.personas import (
                PersonaRegistry,
            )
            store = OntologyStore()
            reg = PersonaRegistry(ontology=store)
            r.details["starter_personas"] = len(reg.list_starter())
            assert len(reg.list_starter()) >= 4

    def _check_auto_repair_loop_merge(self) -> None:
        with self._timed("auto_repair+loop+merge") as r:
            from sylion.aeis.testing.auto_repair_controller import (
                AutoRepairController,
            )
            from sylion.aeis.testing.loop_governor import (
                DEFAULT_LIMITS,
            )
            from sylion.aeis.testing.merge_guard import REJECTIONS
            from sylion.aeis.testing.ontology import OntologyStore
            from sylion.aeis.testing.ontology.objects import Finding
            store = OntologyStore()
            f = Finding(severity="P2", d_level="D2", title="audit",
                        description="self audit", discovered_by="self_audit")
            store.create(f)
            ctrl = AutoRepairController(ontology=store)
            session_id = ctrl.start_repair(f.finding_id, "br_audit_repair")
            assert isinstance(session_id, str) and session_id.startswith("ars_")
            r.details["loop_governor_limits"] = len(DEFAULT_LIMITS)
            r.details["merge_guard_rejections"] = len(REJECTIONS)

    def _check_guardians(self) -> None:
        with self._timed("guardians") as r:
            from sylion.aeis.testing.guardians import (
                ALL_GUARDIAN_CLASSES, register_all_guardians,
            )
            from sylion.aeis.testing.ontology import OntologyStore
            store = OntologyStore()
            guards = register_all_guardians(ontology=store)
            r.details["guardian_count"] = len(guards)
            assert len(ALL_GUARDIAN_CLASSES) == 13

    def _check_truth_alignment(self) -> None:
        with self._timed("truth_alignment") as r:
            from sylion.aeis.testing.truth_alignment import (
                LAYERS, FeatureSnapshot, TruthAlignmentMatrix,
            )
            m = TruthAlignmentMatrix()
            snap = FeatureSnapshot(
                feature_id="self_audit_smoke",
                sot={"present": True}, masterplan={"present": True},
                runtime={"present": True}, api={"present": True},
                ui={"present": True, "data_source": "live"},
                test={"present": True}, docs={"present": True},
            )
            m.upsert_snapshot(snap)
            row = m.build_for_feature("self_audit_smoke")
            r.details["layers"] = len(LAYERS)
            r.details["smoke_aligned"] = row["aligned"]
            assert row["aligned"]

    def _check_charter_findings_stores(self) -> None:
        with self._timed("charter+findings_stores") as r:
            from sylion.aeis.testing.charter import CharterStore
            from sylion.aeis.testing.findings import FindingStore
            from sylion.aeis.testing.ontology import OntologyStore
            from sylion.aeis.testing.ontology.objects import Finding, TestCharter
            store = OntologyStore()
            cs = CharterStore(ontology=store)
            charter = TestCharter(
                project_id="proj_audit",
                source_of_truth_version="v1", masterplan_version="v1",
                scope={}, required_test_classes=["T2"],
                required_personas=[], required_evidence=[],
                release_blockers=[], auto_repair_policy={},
                approval={}, status="draft",
            )
            cs.create(charter)
            cs.propose(charter.charter_id)
            cs.approve(charter.charter_id, approver="self_audit")
            fs = FindingStore(ontology=store)
            f = Finding(severity="P3", d_level="D2", title="audit f",
                        description="d", discovered_by="self", r_status="OPEN")
            fs.create(f, mirror_to_ticket=False)
            fs.transition(f.finding_id, "REPRODUCED")
            r.details["charter_lifecycle_ok"] = True
            r.details["finding_lifecycle_ok"] = True

    def _check_release_rail(self) -> None:
        with self._timed("release_rail") as r:
            from sylion.aeis.testing.ontology import OntologyStore
            from sylion.aeis.testing.release_rail import (
                PROD_CHECKLIST, RC_CHECKLIST, EvaluationContext, ReleaseRail,
            )
            rail = ReleaseRail(ontology=OntologyStore())
            ctx = EvaluationContext(
                project_id="proj_audit", rc_id="rc_audit",
                sot_approved=True, masterplan_approved=True,
            )
            verdict = rail.evaluate(ctx)
            r.details["rc_checklist"] = len(RC_CHECKLIST)
            r.details["prod_checklist"] = len(PROD_CHECKLIST)
            r.details["evaluation_ok"] = "status" in verdict

    def _check_memory(self) -> None:
        with self._timed("memory") as r:
            from sylion.aeis.testing.memory import TestingMemoryStore
            mem = TestingMemoryStore()
            mem.record_lesson(
                project_id="proj_audit", release_id="rel_audit",
                pattern_type="self_audit_smoke",
                context={"audit": True},
                detection={"by": "self_audit"},
                resolution={"action": "verified"},
            )
            mem.add_anti_pattern("audit_smoke_pattern", severity="D2")
            r.details["health"] = mem.health()
            r.details["lessons_persisted"] = len(mem.list_lessons())
            assert len(mem.list_lessons()) == 1

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _timed(self, pillar: str) -> "_AuditCtx":
        return _AuditCtx(pillar, self.results)


class _AuditCtx:
    def __init__(self, pillar: str, results: list[AuditResult]) -> None:
        self.pillar = pillar
        self.results = results
        self.r = AuditResult(pillar=pillar, status="pass")
        self.t0 = 0.0

    def __enter__(self) -> AuditResult:
        self.t0 = time.time()
        return self.r

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.r.duration_s = time.time() - self.t0
        if exc is not None:
            self.r.status = "fail"
            self.r.error = "".join(
                traceback.format_exception(exc_type, exc, tb)
            )[:500]
            log.warning("self-audit pillar '%s' failed: %s", self.pillar, exc)
        self.results.append(self.r)
        return True  # swallow exception, captured in result


__all__ = ["W14SelfAudit", "AuditResult"]
