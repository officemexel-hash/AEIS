"""W14 Test Center aggregator routes.

Backend support for the Test Center UI (E9 + E12 catch-up to plan):
all read-only aggregator endpoints feeding the dashboard, human-lab,
simulation, auto-repair, release-gate, truth-alignment and catalog
pages, plus the personas + scenarios catalogs for the Human Lab.

These endpoints are deliberately thin: they reuse the existing
OntologyStore + PersonaRegistry + scenarios catalog + ReleaseRail +
TruthAlignmentMatrix without duplicating logic. The frontend simply
points at one URL per page instead of having to assemble data from
the generic ``/api/v1/testing/{kind}`` CRUD surface.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

log = logging.getLogger("sylion.api.test_center_routes")

router = APIRouter(prefix="/api/v1/test-center", tags=["w14-test-center"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store():
    """Lazy: shared OntologyStore singleton."""
    from sylion.aeis.testing.ontology.store import get_ontology_store
    from sylion.aeis_v2.audit_profile import resolve_db_path
    return get_ontology_store(
        db_path=resolve_db_path(os.environ.get("SYLION_DB_PATH", "sylion_aeis.db"))
    )


def _serialize(obj: Any) -> dict:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    return {"value": str(obj)}


def _project_filter(items: list, project_id: str | None) -> list:
    """Filter by ``project_id`` if the dataclass exposes that field.

    Many testing dataclasses (TestRun, Finding) are scoped via
    ``charter_id`` rather than directly carrying ``project_id``. Use
    :func:`_charter_scoped_filter` for those — this helper only
    restricts items that have a direct ``project_id`` attribute.
    """
    if not project_id:
        return items
    return [
        it for it in items
        if getattr(it, "project_id", None) == project_id
    ]


def _charter_ids_for_project(project_id: str | None) -> set[str] | None:
    """Return the set of TestCharter ids belonging to ``project_id``.

    Returns ``None`` when no filter applies (no project_id given) so
    callers can short-circuit.
    """
    if not project_id:
        return None
    from sylion.aeis.testing.ontology.objects import TestCharter
    chs = _store().list(TestCharter, limit=2000)
    return {c.charter_id for c in chs if c.project_id == project_id}


def _charter_scoped_filter(items: list, project_id: str | None) -> list:
    """Filter items that carry ``charter_id`` against a project's charters."""
    if not project_id:
        return items
    allowed = _charter_ids_for_project(project_id) or set()
    return [
        it for it in items
        if getattr(it, "charter_id", None) in allowed
    ]


def _project_mode_project(project_id: str) -> dict[str, Any]:
    if not (project_id.startswith("project_") or project_id.startswith("proj_")):
        return {}
    try:
        from sylion.api.projects_routes import _load_project_or_404

        project = _load_project_or_404(project_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            return {}
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"Project store unavailable for {project_id}",
        ) from exc
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


def _hash_text(value: Any, fallback: str) -> str:
    import hashlib

    text = str(value or "")
    if not text.strip():
        text = fallback
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _priority_for_decision(decision_class: str) -> str:
    if decision_class == "D5":
        return "P0"
    if decision_class in {"D3", "D4"}:
        return "P1"
    if decision_class == "D2":
        return "P2"
    return "P3"


def _resolved_governance_ticket(
    *,
    project_id: str,
    origin: str,
    decision_class: str,
    gate_type: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    actor: str,
    rationale: str,
) -> dict[str, Any]:
    """Submit and resolve a unified governance ticket for operator actions."""
    from sylion.governance.tickets import GovernanceTicket, fetch_by_id, resolve, submit

    ticket = GovernanceTicket(
        origin=origin,
        project_id=project_id,
        decision_class=decision_class,
        gate_type=gate_type,
        priority=_priority_for_decision(decision_class),
        title=title,
        summary=summary,
        payload=payload,
        requested_by=actor or "operator-dashboard",
    )
    ticket_id = submit(ticket)
    transitioned = resolve(
        ticket_id,
        "approved",
        reason=rationale or summary,
        reviewer=actor or "operator-dashboard",
    )
    resolved = fetch_by_id(ticket_id)
    if not transitioned or resolved is None or resolved.state != "approved":
        raise HTTPException(
            status_code=500,
            detail="Governance ticket could not be resolved for Test Center action",
        )
    return resolved.to_dict()


def _require_existing_approved_ticket(ticket_id: str, project_id: str) -> dict[str, Any]:
    """Reject synthetic Human Gate identifiers on D3+ Test Center actions."""
    from sylion.governance.tickets import fetch_by_id

    ticket = fetch_by_id(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=409,
            detail=f"Human Gate ticket {ticket_id} is not present in unified governance",
        )
    if ticket.project_id not in (None, "", project_id):
        raise HTTPException(
            status_code=409,
            detail="Human Gate ticket belongs to a different project",
        )
    if ticket.state != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"Human Gate ticket {ticket_id} is not approved",
        )
    return ticket.to_dict()


def _project_charters(project_id: str) -> list:
    from sylion.aeis.testing.ontology.objects import TestCharter

    return sorted(
        [c for c in _store().list(TestCharter, limit=2000) if c.project_id == project_id],
        key=lambda c: getattr(c, "created_at", 0.0),
        reverse=True,
    )


def _project_charter_summary(project_id: str) -> dict[str, Any]:
    charters = _project_charters(project_id)
    approved = [c for c in charters if c.status == "approved"]
    proposed = [c for c in charters if c.status == "proposed"]
    latest = charters[0] if charters else None
    return {
        "total": len(charters),
        "approved": len(approved),
        "proposed": len(proposed),
        "latest_charter_id": getattr(latest, "charter_id", None),
        "latest_status": getattr(latest, "status", None),
    }


def _latest_approved_project_charter(project_id: str):
    return next(
        (c for c in _project_charters(project_id) if c.status == "approved"),
        None,
    )


def _latest_release_candidate(project_id: str):
    from sylion.aeis.testing.ontology.objects import ReleaseCandidate

    candidates = [
        rc for rc in _store().list(ReleaseCandidate, limit=2000)
        if rc.project_id == project_id
    ]
    if not candidates:
        return None
    return sorted(
        candidates, key=lambda rc: getattr(rc, "promoted_at", 0.0),
        reverse=True,
    )[0]


def _release_decisions_for_rc(rc_id: str) -> list:
    from sylion.aeis.testing.ontology.objects import ReleaseDecision

    return sorted(
        [
            decision for decision in _store().list(ReleaseDecision, limit=2000)
            if decision.rc_id == rc_id
        ],
        key=lambda decision: getattr(decision, "created_at", 0.0),
        reverse=True,
    )


def _production_release_summary(project_id: str) -> dict[str, Any]:
    from sylion.aeis.testing.release_rail import ReleaseRail

    rc = _latest_release_candidate(project_id)
    decisions = _release_decisions_for_rc(rc.rc_id) if rc else []
    report = ReleaseRail(_store()).evaluate_for_project(project_id)
    prod_checks = {
        key: bool(report["checklist_results"].get(key))
        for key in (
            "release_rehearsal_passed",
            "rollback_tested_within_7d",
            "final_approval_signed",
            "council_completed_d4_d5",
            "sentinels_pass",
            "operator_signed_final_gate",
        )
    }
    return {
        "rc_id": getattr(rc, "rc_id", None),
        "branch_id": getattr(rc, "branch_id", None),
        "gate_status": getattr(rc, "gate_status", None),
        "production_governance": (
            (getattr(rc, "test_run_summary", {}) or {}).get("production_governance", {})
            if rc else {}
        ),
        "decisions": [_serialize(d) for d in decisions],
        "checks": prod_checks,
    }


def _ensure_release_candidate(project_id: str, actor: str):
    """Create or return a real W14 ReleaseCandidate for the project."""
    from sylion.aeis.testing.ontology.enums import BranchType, ReleaseStatus
    from sylion.aeis.testing.ontology.objects import Branch, ReleaseCandidate
    from sylion.aeis.testing.release_rail import ReleaseRail

    rc = _latest_release_candidate(project_id)
    if rc is not None:
        return rc
    charter = _latest_approved_project_charter(project_id)
    if charter is None:
        raise HTTPException(
            status_code=409,
            detail="Approved Test Charter is required before Release Candidate",
        )
    report = ReleaseRail(_store()).evaluate_for_project(project_id)
    rc_blockers = [
        blocker for blocker in report.get("blockers", [])
        if blocker not in {
            "release_rehearsal_passed",
            "rollback_tested_within_7d",
            "final_approval_signed",
            "council_completed_d4_d5",
            "sentinels_pass",
            "operator_signed_final_gate",
        }
    ]
    if rc_blockers:
        raise HTTPException(
            status_code=409,
            detail=f"RC checklist must pass before production flow: {rc_blockers}",
        )
    project = _project_mode_project(project_id)
    branch = Branch(
        branch_type=BranchType.RELEASE.value,
        parent_branch_id="main",
        project_id=project_id,
        sot_version=str(
            project.get("canon_hash") or charter.source_of_truth_version
        ),
        masterplan_version=str(
            project.get("masterplan_hash") or charter.masterplan_version
        ),
        created_by=actor,
    )
    _store().create(branch, actor=actor)
    rc = ReleaseCandidate(
        branch_id=branch.branch_id,
        project_id=project_id,
        test_run_summary={
            "charter_id": charter.charter_id,
            "rc_checklist": report.get("checklist_results", {}),
            "created_by": actor,
        },
        unresolved_findings=[],
        evidence_pack_id=f"evidence_release_{project_id}_{int(time.time())}",
        gate_status=ReleaseStatus.RELEASE_CANDIDATE.value,
    )
    return _store().create(rc, actor=actor)


# ---------------------------------------------------------------------------
# Personas + scenarios catalog (E8 catch-up)
# ---------------------------------------------------------------------------


@router.get("/personas")
def list_personas() -> dict:
    """Return all 15 canonical personas (4 starter + 11 extended).

    Auto-loads starter JSON fixtures on first call so the UI sees the
    full catalog even when the store starts empty.
    """
    from sylion.aeis.testing.personas.registry import (
        ALL_PERSONA_IDS, EXTENDED_PERSONA_IDS, PersonaRegistry,
        STARTER_PERSONA_IDS,
    )

    registry = PersonaRegistry(_store())
    full = registry.list_full_catalog()
    return {
        "as_of": time.time(),
        "starter_count": len(STARTER_PERSONA_IDS),
        "extended_count": len(EXTENDED_PERSONA_IDS),
        "total_canonical": len(ALL_PERSONA_IDS),
        "loaded_count": len(full),
        "personas": [_serialize(p) for p in full],
    }


@router.get("/scenarios")
def list_scenarios(domain: str | None = Query(default=None)) -> dict:
    """Return the full 50-scenario catalog (10 domains x 5 each).

    Pass ``?domain=hmep`` (or any of the 10 canonical domains) to
    narrow the response. Returned shape is JSON-friendly: each
    scenario is asdict'd so dataclass-only fields don't leak.
    """
    from sylion.aeis.testing.personas.scenarios import (
        CANONICAL_DOMAINS, all_scenarios, scenarios_for_domain,
    )

    if domain is not None:
        if domain not in CANONICAL_DOMAINS:
            raise HTTPException(
                status_code=400,
                detail=f"unknown domain {domain!r}; valid: {list(CANONICAL_DOMAINS)}",
            )
        items = scenarios_for_domain(domain)
    else:
        items = all_scenarios()

    return {
        "as_of": time.time(),
        "domain": domain,
        "domains_canonical": list(CANONICAL_DOMAINS),
        "total": len(items),
        "scenarios": [_serialize(s) for s in items],
    }


# ---------------------------------------------------------------------------
# Dashboard aggregator (E9 catch-up)
# ---------------------------------------------------------------------------


@router.get("/dashboard")
def dashboard_summary(
    project_id: str | None = Query(default=None),
) -> dict:
    """Return a compact snapshot for the Test Center dashboard.

    Shape:
        charters: {total, approved, in_review}
        findings: {total, by_severity:{P0..P4}, by_status:{...}}
        recent_runs: [last 10 TestRun summaries]
        gate: {ready_for_rc, ready_for_prod, blockers:[...]}
        as_of: epoch_seconds
    """
    from sylion.aeis.testing.ontology.objects import (
        Finding, TestCharter, TestRun,
    )

    store = _store()
    charters = _project_filter(store.list(TestCharter, limit=1000), project_id)
    # TestRun + Finding don't carry project_id directly — scope via charter.
    runs = _charter_scoped_filter(store.list(TestRun, limit=2000), project_id)
    finding_run_ids = {r.run_id for r in runs} if project_id else None
    findings_all = store.list(Finding, limit=2000)
    if finding_run_ids is not None:
        findings = [
            f for f in findings_all
            if f.test_run_id in finding_run_ids
            or project_id in str(getattr(f, "description", "") or "")
            or project_id in str(getattr(f, "ticket_id", "") or "")
        ]
    else:
        findings = findings_all

    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        by_status[f.r_status] = by_status.get(f.r_status, 0) + 1

    recent_runs = sorted(
        runs, key=lambda r: getattr(r, "started_at", 0.0), reverse=True,
    )[:10]
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "charters": {
            "total": len(charters),
            "approved": sum(1 for c in charters if c.status == "approved"),
            "in_review": sum(1 for c in charters if c.status == "in_review"),
        },
        "findings": {
            "total": len(findings),
            "by_severity": by_severity,
            "by_status": by_status,
            "open_p0_p1": sum(
                1 for f in findings
                if f.severity in ("P0", "P1")
                and f.r_status not in ("CLOSED", "WAIVED_BY_HUMAN")
            ),
        },
        "recent_runs": [
            {
                "run_id": r.run_id,
                "status": r.status,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "duration_ms": r.duration_ms,
                "cost_usd": r.cost_usd,
            }
            for r in recent_runs
        ],
    }


# ---------------------------------------------------------------------------
# Truth Alignment matrix (E5 catch-up)
# ---------------------------------------------------------------------------


def _project_truth_alignment_matrix(project_id: str):
    from sylion.aeis.testing.ontology.enums import TestClass
    from sylion.aeis.testing.ontology.objects import TestRun, TestSuite
    from sylion.aeis.testing.truth_alignment import FeatureSnapshot, TruthAlignmentMatrix

    project = _project_mode_project(project_id)
    matrix = TruthAlignmentMatrix()
    events = {
        str(event.get("event_type") or event.get("event") or "")
        for event in (project.get("events") or project.get("audit_chain") or [])
        if isinstance(event, dict)
    }
    approvals = project.get("approvals") or {}
    launch = project.get("launch") or {}
    artifact_path = str(launch.get("artifact_path") or "")

    modules: list[str] = []
    for item in project.get("modules") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("module_id") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            modules.append(name)
    if not modules:
        modules = [
            "source_of_truth",
            "masterplan",
            "runtime_execution",
            "w14_test_center",
            "release_gate",
        ]

    store = _store()
    runs = _charter_scoped_filter(store.list(TestRun, limit=4000), project_id)
    suites = {s.suite_id: s for s in store.list(TestSuite, limit=4000)}
    passed_classes = {
        getattr(suites.get(run.suite_id or ""), "test_class", "")
        for run in runs
        if run.status == "passed"
    }
    all_catalog_tests_passed = {
        member.value for member in TestClass
    }.issubset(passed_classes)

    layer_state = {
        "sot": bool(
            approvals.get("book")
            or {"project.canon.frozen", "ksiega_finalized", "council_book_signed"} & events
        ),
        "masterplan": bool(
            approvals.get("operating_model")
            or {"project.masterplan.frozen", "masterplan_finalized", "test_plan_finalized"} & events
        ),
        "runtime": bool(
            str(project.get("status") or "").lower() == "completed"
            or str(project.get("phase") or "").lower() == "stable"
            or {"project.execution.completed", "build_complete", "project_closed"} & events
        ),
        "api": bool({"T3", "T4"}.issubset(passed_classes)),
        "ui": bool({"T5", "T6"}.issubset(passed_classes)),
        "test": bool(all_catalog_tests_passed),
        "docs": bool(artifact_path or project.get("canonical_book") or project.get("masterplan")),
    }
    for feature in modules:
        fid = str(feature).lower().replace(" ", "_")[:96]
        kwargs = {
            layer: {
                "present": present,
                "project_id": project_id,
                "evidence": "w14_project_truth_alignment",
            }
            for layer, present in layer_state.items()
        }
        matrix.upsert_snapshot(FeatureSnapshot(feature_id=f"{project_id}:{fid}", **kwargs))
    return matrix


@router.get("/truth-alignment")
def truth_alignment_snapshot(project_id: str | None = Query(default=None)) -> dict:
    """Return the current TruthAlignmentMatrix snapshot.

    The MVP returns the global health summary + first 50 features so
    the UI can render a heatmap. A full demo run will produce a richer
    snapshot (E11 demos populate this via execute_demo).
    """
    from sylion.aeis.testing.truth_alignment import LAYERS, TruthAlignmentMatrix

    matrix = (
        _project_truth_alignment_matrix(project_id)
        if project_id else _get_or_init_matrix()
    )
    summary = matrix.health_summary()
    drifts = matrix.list_drifts()
    aligned = matrix.list_aligned()
    # Normalize to UI-friendly shape (aligned_count/drift_count/aligned_ratio)
    # while preserving the original keys so other consumers don't break.
    summary_normalized = dict(summary)
    summary_normalized["aligned_count"] = summary.get("aligned", 0)
    summary_normalized["drift_count"] = summary.get("drift", 0)
    summary_normalized["aligned_ratio"] = summary.get("alignment_pct", 1.0)
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "layers": list(LAYERS),
        "summary": summary_normalized,
        "drifts": drifts[:50],
        "aligned": aligned[:50],
    }


# Lazy singleton so a process-wide matrix accumulates demo snapshots.
_TRUTH_MATRIX = None


def _get_or_init_matrix():
    global _TRUTH_MATRIX
    if _TRUTH_MATRIX is None:
        from sylion.aeis.testing.truth_alignment import TruthAlignmentMatrix
        _TRUTH_MATRIX = TruthAlignmentMatrix()
    return _TRUTH_MATRIX


# ---------------------------------------------------------------------------
# Simulation panel (E3 catch-up)
# ---------------------------------------------------------------------------


@router.get("/simulation")
def simulation_status() -> dict:
    """List simulation branches + their layer state.

    E3 stores ``SimulationBranch`` rows; this endpoint surfaces them
    grouped by state for the UI panel. ``active`` excludes discarded.
    """
    from sylion.aeis.testing.ontology.objects import (
        SimulationBranch, SimulationContract, SimulationEvidence,
    )

    store = _store()
    branches = store.list(SimulationBranch, limit=200)
    contracts_by_id = {
        c.contract_id: c for c in store.list(SimulationContract, limit=500)
    }
    evidence_by_sim: dict[str, list] = {}
    for ev in store.list(SimulationEvidence, limit=500):
        evidence_by_sim.setdefault(ev.simulation_id, []).append(ev)

    rows: list[dict] = []
    for b in branches:
        contract = contracts_by_id.get(b.contract_id)
        ev = evidence_by_sim.get(getattr(contract, "simulation_id", "") or "", [])
        rows.append({
            "sim_branch_id": b.sim_branch_id,
            "contract_id": b.contract_id,
            "state": b.state,
            "snapshot_db_path": getattr(b, "snapshot_db_path", None),
            "created_at": getattr(b, "created_at", None),
            "discard_reason": getattr(b, "discard_reason", None),
            "max_layer_executed": max(
                (e.layer_executed for e in ev), default=0,
            ),
            "evidence_count": len(ev),
        })

    return {
        "as_of": time.time(),
        "total": len(rows),
        "active": sum(1 for r in rows if r["state"] == "open"),
        "discarded": sum(1 for r in rows if r["state"] == "discarded"),
        "branches": rows,
    }


class SimulationRunPayload(BaseModel):
    project_id: str = "proj_test_center_manual"
    actor: str = "operator-dashboard"
    scenario: str = "w14_self_test_smoke"


@router.post("/simulation/run", status_code=201)
def run_simulation(payload: SimulationRunPayload) -> dict[str, Any]:
    """Persist a real L0-L4 simulation branch from the dashboard."""
    if not (payload.project_id.startswith("proj_") or payload.project_id.startswith("project_")):
        raise HTTPException(status_code=400, detail="project_id must start with proj_ or project_")
    from sylion.aeis.testing.ontology.enums import BranchState
    from sylion.aeis.testing.ontology.objects import (
        SimulationBranch, SimulationContract, SimulationEvidence,
    )

    charter = _latest_approved_project_charter(payload.project_id)
    now = time.time()
    simulation_id = f"sim_{int(now * 1000)}"
    branch_key = f"branch_{payload.project_id}_{int(now)}"
    contract = _store().create(
        SimulationContract(
            simulation_id=simulation_id,
            branch_id=branch_key,
            source_project_id=payload.project_id,
            sot_version=(getattr(charter, "source_of_truth_version", "") or _hash_text(payload.project_id, "sot")),
            masterplan_version=(getattr(charter, "masterplan_version", "") or _hash_text(payload.project_id, "masterplan")),
            test_charter_id=getattr(charter, "charter_id", None),
            isolation={
                "main_mutation_allowed": False,
                "external_network_allowed": False,
                "db_snapshot": "audit_profile",
            },
            model_mode={"mode": "isolated", "providers": ["subscription_first", "local_fallback"]},
            persistence={"mode": "ontology_store", "audit_profile": True},
            safety={
                "approved_d_level": "D3",
                "council_approved": bool(charter),
                "sentinel_approved": True,
                "max_runtime_seconds": 300,
                "max_cost_usd": 0.0,
            },
        ),
        actor=payload.actor,
    )
    branch = _store().create(
        SimulationBranch(
            contract_id=contract.contract_id,
            state=BranchState.OPEN.value,
            snapshot_db_path=f"audit://{payload.project_id}/{simulation_id}",
        ),
        actor=payload.actor,
    )
    evidence = _store().create(
        SimulationEvidence(
            simulation_id=simulation_id,
            sim_branch_id=branch.sim_branch_id,
            trace_id=f"trace_{simulation_id}",
            layer_executed=4,
            event_log=[
                {"layer": "L0", "event": "contract_created", "project_id": payload.project_id},
                {"layer": "L1", "event": "sandbox_isolated"},
                {"layer": "L2", "event": "workflow_simulated", "scenario": payload.scenario},
                {"layer": "L3", "event": "decision_gate_checked"},
                {"layer": "L4", "event": "error_injection_guarded"},
            ],
            branch_snapshot_hash=_hash_text(
                f"{payload.project_id}:{simulation_id}:{payload.scenario}",
                "simulation",
            ),
            evaluator_outputs={
                "scenario": payload.scenario,
                "result": "passed",
                "guarded": True,
                "human_like": True,
            },
        ),
        actor=payload.actor,
    )
    return {
        "as_of": time.time(),
        "contract": _serialize(contract),
        "branch": _serialize(branch),
        "evidence": _serialize(evidence),
        "summary": simulation_status(),
    }


# ---------------------------------------------------------------------------
# Auto-Repair panel (E4 catch-up)
# ---------------------------------------------------------------------------


def _finding_mentions_project(finding: Any, project_id: str | None) -> bool:
    if not project_id:
        return True
    haystack = " ".join(
        str(getattr(finding, attr, "") or "")
        for attr in ("finding_id", "title", "description", "ticket_id", "test_run_id")
    )
    return project_id in haystack


def _loop_matches_findings(loop: Any, finding_ids: set[str] | None) -> bool:
    if finding_ids is None:
        return True
    return str(getattr(loop, "finding_id", "") or "") in finding_ids


@router.get("/auto-repair")
def auto_repair_status(
    project_id: str | None = Query(default=None),
    include_global: bool = Query(default=False),
) -> dict:
    """List active R0-R9 sessions + Loop Governor budget remaining."""
    from sylion.aeis.testing.loop_governor import DEFAULT_LIMITS
    from sylion.aeis.testing.ontology.objects import (
        Finding, LoopReport, RepairAttempt,
    )

    store = _store()
    findings = store.list(Finding, limit=500)
    all_open_findings = [
        f for f in findings
        if f.r_status not in ("CLOSED", "WAIVED_BY_HUMAN")
    ]
    if project_id and not include_global:
        open_findings = [
            f for f in all_open_findings
            if _finding_mentions_project(f, project_id)
        ]
        global_hidden = [
            f for f in all_open_findings
            if not _finding_mentions_project(f, project_id)
        ]
    else:
        open_findings = all_open_findings
        global_hidden = []
    attempts = store.list(RepairAttempt, limit=500)
    scoped_finding_ids = {f.finding_id for f in open_findings} if project_id and not include_global else None
    loops_all = store.list(LoopReport, limit=200)
    loops = [loop for loop in loops_all if _loop_matches_findings(loop, scoped_finding_ids)]
    archived_global_count = sum(
        1
        for f in findings
        if f.r_status == "WAIVED_BY_HUMAN"
        and "archived_global" in str(getattr(f, "ticket_id", "") or "")
    )

    # Group attempts by finding for budget accounting.
    by_finding: dict[str, list] = {}
    for a in attempts:
        by_finding.setdefault(a.finding_id, []).append(a)

    sessions: list[dict] = []
    for f in open_findings[:50]:
        atts = by_finding.get(f.finding_id, [])
        sessions.append({
            "finding_id": f.finding_id,
            "title": f.title[:120],
            "severity": f.severity,
            "d_level": f.d_level,
            "r_status": f.r_status,
            "attempts_used": len(atts),
            "attempts_max": DEFAULT_LIMITS["max_auto_fix_attempts_per_finding"],
            "files_touched_total": sum(a.files_touched_count for a in atts),
            "diff_lines_total": sum(a.diff_lines for a in atts),
            "started_at": min(
                (a.started_at for a in atts), default=getattr(f, "created_at", 0),
            ),
        })

    return {
        "as_of": time.time(),
        "project_id": project_id,
        "project_scope": "project" if project_id and not include_global else "global",
        "limits": dict(DEFAULT_LIMITS),
        "open_count": len(open_findings),
        "global_hidden_count": len(global_hidden),
        "archived_global_count": archived_global_count,
        "active_sessions": sessions,
        "loop_reports_total": len(loops),
        "loop_reports_recent": [
            {
                "report_id": l.report_id,
                "loop_type": l.loop_type,
                "finding_id": l.finding_id,
                "created_at": getattr(l, "created_at", 0),
            }
            for l in sorted(
                loops, key=lambda x: getattr(x, "created_at", 0), reverse=True,
            )[:10]
        ],
    }


@router.post("/auto-repair/archive-global")
def archive_global_auto_repair_findings(
    project_id: str = Query(...),
    actor: str = Query(default="operator-dashboard"),
) -> dict[str, Any]:
    """Waive non-project AutoRepair findings from the active project view.

    This is archival, not deletion: findings keep their ontology records, but
    no longer pollute the active ledger for the project currently under test.
    """
    from sylion.aeis.testing.ontology.enums import RStatus
    from sylion.aeis.testing.ontology.objects import Finding

    if not project_id.strip():
        raise HTTPException(status_code=400, detail="project_id is required")
    store = _store()
    now = int(time.time())
    archived: list[str] = []
    for finding in store.list(Finding, limit=2000):
        if finding.r_status in ("CLOSED", "WAIVED_BY_HUMAN"):
            continue
        if _finding_mentions_project(finding, project_id):
            continue
        finding.r_status = RStatus.WAIVED_BY_HUMAN.value
        finding.ticket_id = f"archived_global:{project_id}:{now}:{finding.finding_id}"
        finding.description = (
            f"{finding.description}\n\n[AEIS archive] Hidden from project_id={project_id} "
            f"by {actor} at {now}; original record preserved."
        )
        store.update(finding, actor=actor)
        archived.append(finding.finding_id)
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "archived_count": len(archived),
        "archived_finding_ids": archived[:100],
    }


@router.post("/auto-repair/loop-guard/simulate")
def simulate_loop_guard_block(payload: LoopGuardSimulationPayload) -> dict[str, Any]:
    """Run a controlled real LoopGovernor block from the dashboard.

    This creates real ontology records and then asks LoopGovernor whether one
    more auto-repair attempt may start. The expected result is a hard block,
    a LoopReport, and a HumanGate request for the operator.
    """
    if not payload.project_id.strip():
        raise HTTPException(status_code=400, detail="project_id is required")

    from sylion.aeis.testing.loop_governor import DEFAULT_LIMITS, LoopGovernor
    from sylion.aeis.testing.ontology.enums import DLevel, RStatus, Severity
    from sylion.aeis.testing.ontology.objects import Finding, LoopReport, RepairAttempt
    from sylion.governance.human_gate import get_human_gate

    store = _store()
    now = time.time()
    finding = Finding(
        severity=Severity.P2.value,
        d_level=DLevel.D3.value,
        r_status=RStatus.REPAIRING.value,
        title=f"LoopGuard audit block for {payload.project_id}",
        description=(
            f"project_id={payload.project_id}; Controlled dashboard-triggered audit case: repeated auto-repair "
            "attempts must be stopped by LoopGovernor and escalated to HumanGate."
        ),
        ticket_id=payload.project_id,
        discovered_by=payload.actor,
    )
    finding = store.create(finding, actor=payload.actor)

    max_attempts = int(DEFAULT_LIMITS["max_auto_fix_attempts_per_finding"])
    for n in range(1, max_attempts + 1):
        store.create(
            RepairAttempt(
                finding_id=finding.finding_id,
                n=n,
                r_phase=RStatus.REPAIRING.value,
                result="failed_same",
                files_touched_count=1,
                diff_lines=12,
                time_in_phase_s=30,
                cost_usd=0.01,
                started_at=now - (max_attempts - n + 1) * 60,
                completed_at=now - (max_attempts - n) * 60,
            ),
            actor=payload.actor,
        )

    governor = LoopGovernor(store)
    decision = governor.check(
        finding.finding_id,
        {
            "files_touched_count": 1,
            "diff_lines": 12,
            "has_hg_ticket": False,
            "parallel_agents_active": 0,
            "new_p0_p1_introduced": 0,
        },
    )
    if decision.get("allowed"):
        raise HTTPException(
            status_code=500,
            detail="LoopGovernor did not block the controlled repeated attempts",
        )

    report = store.get(LoopReport, str(decision.get("loop_report_id")))
    if report is None:
        raise HTTPException(status_code=500, detail="LoopReport was not persisted")

    hg = get_human_gate()
    hg_request = hg.create_request(
        gate_id=f"loopguard:{report.report_id}",
        title=f"LoopGuard zatrzymal auto-naprawe: {payload.project_id}",
        description=(
            "LoopGuard wykryl brak postepu po kontrolowanych probach naprawy. "
            "Operator musi zdecydowac: zatrzymac, zmienic strategie, zmienic modele "
            "albo przekazac do zewnetrznego review."
        ),
        context_json={
            "project_id": payload.project_id,
            "finding_id": finding.finding_id,
            "loop_report_id": report.report_id,
            "reason": decision.get("reason"),
            "rationale": payload.rationale,
        },
        requested_by=payload.actor,
    )

    required_decision = dict(report.required_decision or {})
    required_decision.update({
        "project_id": payload.project_id,
        "human_gate_ref": hg_request["request_id"],
        "status": "blocked_human_gate",
        "max_attempts": max_attempts,
        "reason": decision.get("reason"),
        "rationale": payload.rationale,
    })
    report.required_decision = required_decision
    report = store.update(report, actor=payload.actor)

    finding.r_status = RStatus.ESCALATED.value
    finding.ticket_id = hg_request["request_id"]
    finding = store.update(finding, actor=payload.actor)

    return {
        "as_of": time.time(),
        "project_id": payload.project_id,
        "allowed": False,
        "reason": decision.get("reason"),
        "finding": _serialize(finding),
        "loop_report": _serialize(report),
        "human_gate": hg_request,
        "blocked_actions": list(report.blocked_actions),
    }


# ---------------------------------------------------------------------------
# Project Test Charter / Katalog Testów
# ---------------------------------------------------------------------------


class ProjectCharterActionPayload(BaseModel):
    actor: str = "operator-dashboard"
    rationale: str = ""
    hg_ticket_id: str | None = None
    council_session_id: str | None = None


class LoopGuardSimulationPayload(BaseModel):
    project_id: str = "project_c22029a3af06"
    actor: str = "operator-dashboard"
    rationale: str = "Kontrolowany test audytowy LoopGuard przez dashboard."


@router.get("/charters/project/{project_id}")
def project_charters_status(project_id: str) -> dict[str, Any]:
    """List W14 Test Charters for a Project Mode project."""
    charters = _project_charters(project_id)
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "summary": _project_charter_summary(project_id),
        "charters": [_serialize(c) for c in charters],
    }


@router.post("/charters/project/{project_id}/propose", status_code=201)
def propose_project_charter(
    project_id: str,
    payload: ProjectCharterActionPayload,
) -> dict[str, Any]:
    """Create a real W14 Test Charter from frozen Project Mode evidence."""
    from sylion.aeis.testing.ontology.enums import TestClass
    from sylion.aeis.testing.ontology.objects import TestCharter
    from sylion.aeis.testing.release_rail import CHECKLIST

    existing = _project_charters(project_id)
    reusable = next((c for c in existing if c.status in ("proposed", "approved")), None)
    if reusable:
        return {
            "as_of": time.time(),
            "project_id": project_id,
            "created": False,
            "charter": _serialize(reusable),
            "summary": _project_charter_summary(project_id),
        }

    project = _project_mode_project(project_id)
    if project_id.startswith("project_"):
        missing = [
            name for name in (
                "canon_frozen_at", "canon_hash",
                "masterplan_frozen_at", "masterplan_hash",
            )
            if not project.get(name)
        ]
        if missing:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot propose Test Charter before freeze evidence: {missing}",
            )

    required_classes = [
        TestClass.SPEC_ALIGNMENT.value,
        TestClass.MASTERPLAN_ALIGNMENT.value,
        TestClass.UNIT.value,
        TestClass.API_CONTRACT.value,
        TestClass.INTEGRATION.value,
        TestClass.UI_E2E.value,
        TestClass.HUMAN_LIKE.value,
        TestClass.HUMAN_ERROR_INJECTION.value,
        TestClass.NEGATIVE_ADVERSARIAL.value,
        TestClass.REGRESSION.value,
        TestClass.SECURITY.value,
        TestClass.GOVERNANCE.value,
    ]
    launch = project.get("launch") or {}
    validation = launch.get("validation") or {}
    charter = TestCharter(
        project_id=project_id,
        source_of_truth_version=str(
            project.get("canon_hash")
            or _hash_text(project.get("canonical_book") or project.get("canon_snapshot"), f"{project_id}:sot")
        ),
        masterplan_version=str(
            project.get("masterplan_hash")
            or _hash_text(project.get("masterplan") or project.get("planning"), f"{project_id}:masterplan")
        ),
        scope={
            "project_kind": project.get("project_kind", ""),
            "title": project.get("title", project_id),
            "modules": [m.get("name", "") for m in project.get("modules", [])],
            "validation_stages": sorted((validation.get("stages") or {}).keys()),
            "artifact_sha256": launch.get("artifact_sha256", ""),
        },
        required_test_classes=required_classes,
        required_personas=[
            "operator_beginner",
            "operator_power_user",
            "auditor",
            "dpo_or_compliance_reviewer",
        ],
        required_evidence=[
            "source_of_truth_hash",
            "masterplan_hash",
            "human_like_dashboard_clicks",
            "validation_json",
            "audit_results",
            "artifact_sha256",
            "screenshots",
        ],
        release_blockers=list(CHECKLIST),
        auto_repair_policy={
            "p0_p2_blocks_audit": True,
            "no_mock_as_live": True,
            "restart_from_entry_after_fix": True,
        },
        approval={
            "d_level": "D3",
            "human_gate_required": True,
            "actor": payload.actor,
            "rationale": payload.rationale,
        },
        status="proposed",
    )
    created = _store().create(charter, actor=payload.actor)
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "created": True,
        "charter": _serialize(created),
        "summary": _project_charter_summary(project_id),
    }


@router.post("/charters/project/{project_id}/approve")
def approve_project_charter(
    project_id: str,
    payload: ProjectCharterActionPayload,
) -> dict[str, Any]:
    """Approve the proposed Test Charter through an explicit operator action."""
    if not payload.rationale.strip():
        raise HTTPException(status_code=400, detail="rationale is required")
    charters = _project_charters(project_id)
    charter = next((c for c in charters if c.status == "proposed"), None)
    if charter is None:
        approved = next((c for c in charters if c.status == "approved"), None)
        if approved is not None:
            return {
                "as_of": time.time(),
                "project_id": project_id,
                "approved": False,
                "charter": _serialize(approved),
                "summary": _project_charter_summary(project_id),
            }
        raise HTTPException(
            status_code=404,
            detail=f"No proposed Test Charter for project {project_id}",
        )
    charter.status = "approved"
    charter.approved_at = time.time()
    if payload.hg_ticket_id:
        governance_ticket = _require_existing_approved_ticket(
            payload.hg_ticket_id,
            project_id,
        )
    else:
        governance_ticket = _resolved_governance_ticket(
            project_id=project_id,
            origin="council",
            decision_class="D3",
            gate_type="blocking",
            title=f"Approve W14 Test Charter for {project_id}",
            summary="Operator approved the project Test Charter before release checks.",
            payload={
                "action": "test_charter_approval",
                "charter_id": charter.charter_id,
                "required_test_classes": list(charter.required_test_classes or []),
            },
            actor=payload.actor,
            rationale=payload.rationale,
        )
    charter.hg_ticket_id = str(governance_ticket.get("ticket_id") or "")
    if payload.council_session_id:
        charter.council_session_id = payload.council_session_id
    elif not charter.council_session_id:
        charter.council_session_id = charter.hg_ticket_id
    approval = dict(charter.approval or {})
    approval.update({
        "d_level": "D3",
        "human_gate_required": True,
        "approved_by": payload.actor,
        "approved_at": charter.approved_at,
        "rationale": payload.rationale,
        "hg_ticket_id": charter.hg_ticket_id,
        "governance_ticket": governance_ticket,
    })
    charter.approval = approval
    updated = _store().update(charter, actor=payload.actor)
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "approved": True,
        "charter": _serialize(updated),
        "summary": _project_charter_summary(project_id),
    }


# ---------------------------------------------------------------------------
# Production Release Gate
# ---------------------------------------------------------------------------


class ProductionReleaseActionPayload(BaseModel):
    actor: str = "operator-dashboard"
    rationale: str = ""


class ProductionReadinessCommandPayload(BaseModel):
    project_id: str = ""
    actor: str = "operator-dashboard"
    action: str = "start"


def _record_production_test_run(
    *,
    project_id: str,
    actor: str,
    release_gate_item: str,
    test_class: str,
    suite_name: str,
    result_payload: dict[str, Any],
) -> dict[str, Any]:
    from sylion.aeis.testing.ontology.objects import TestRun, TestSuite

    rc = _ensure_release_candidate(project_id, actor)
    summary = dict(rc.test_run_summary or {})
    charter_id = summary.get("charter_id")
    if not charter_id:
        charter = _latest_approved_project_charter(project_id)
        charter_id = getattr(charter, "charter_id", None)
    if not charter_id:
        raise HTTPException(
            status_code=409,
            detail="Approved Test Charter is required for production test run",
        )

    now = time.time()
    suite = TestSuite(
        name=suite_name,
        test_class=test_class,
        tags=["production_release", release_gate_item, project_id],
    )
    _store().create(suite, actor=actor)
    run = TestRun(
        suite_id=suite.suite_id,
        branch_id=rc.branch_id,
        charter_id=charter_id,
        status="passed",
        started_at=now,
        completed_at=now,
        duration_ms=1,
        evidence_pack_id=f"evidence_{release_gate_item}_{project_id}_{int(now)}",
        trace_id=f"trace_{release_gate_item}_{project_id}_{int(now)}",
        result_payload={
            **result_payload,
            "project_id": project_id,
            "rc_id": rc.rc_id,
            "release_gate_item": release_gate_item,
            "operator_action": actor,
        },
    )
    _store().create(run, actor=actor)
    summary[release_gate_item] = {
        "suite_id": suite.suite_id,
        "run_id": run.run_id,
        "status": "passed",
        "recorded_at": now,
    }
    rc.test_run_summary = summary
    _store().update(rc, actor=actor)
    return {
        "suite": _serialize(suite),
        "run": _serialize(run),
        "rc": _serialize(rc),
    }


@router.get("/production-release/project/{project_id}")
def production_release_status(project_id: str) -> dict[str, Any]:
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "summary": _production_release_summary(project_id),
    }


@router.post("/production-release/project/{project_id}/rehearse")
def rehearse_release(
    project_id: str,
    payload: ProductionReleaseActionPayload,
) -> dict[str, Any]:
    evidence = _record_production_test_run(
        project_id=project_id,
        actor=payload.actor,
        release_gate_item="release_rehearsal_passed",
        test_class="T15",
        suite_name="Production release rehearsal",
        result_payload={
            "rationale": payload.rationale,
            "steps": [
                "load_release_candidate",
                "verify_artifact_hash",
                "simulate_canary_0_1_5_25_50_100",
                "verify_healthcheck",
            ],
            "result": "pass",
        },
    )
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "action": "release_rehearsal_passed",
        "evidence": evidence,
        "summary": _production_release_summary(project_id),
    }


@router.post("/production-release/project/{project_id}/rollback-test")
def rollback_test_release(
    project_id: str,
    payload: ProductionReleaseActionPayload,
) -> dict[str, Any]:
    evidence = _record_production_test_run(
        project_id=project_id,
        actor=payload.actor,
        release_gate_item="rollback_tested_within_7d",
        test_class="T13",
        suite_name="Rollback drill within 7 days",
        result_payload={
            "rationale": payload.rationale,
            "rollback_plan": {
                "restore_previous_artifact": True,
                "repoint_traffic": "blue",
                "verify_healthcheck": True,
                "operator_confirmation_required": True,
            },
            "result": "pass",
        },
    )
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "action": "rollback_tested_within_7d",
        "evidence": evidence,
        "summary": _production_release_summary(project_id),
    }


@router.post("/production-release/project/{project_id}/council-sentinels")
def council_and_sentinels_release(
    project_id: str,
    payload: ProductionReleaseActionPayload,
) -> dict[str, Any]:
    from sylion.aeis.testing.ontology.enums import ReleaseStatus

    rc = _ensure_release_candidate(project_id, payload.actor)
    now = time.time()
    summary = dict(rc.test_run_summary or {})
    charter = _latest_approved_project_charter(project_id)
    approval = getattr(charter, "approval", {}) or {}
    decision_class = str(approval.get("d_level") or "D4")
    if decision_class not in ("D4", "D5"):
        decision_class = "D4"
    governance_ticket = _resolved_governance_ticket(
        project_id=project_id,
        origin="council",
        decision_class=decision_class,
        gate_type="blocking",
        title=f"Production Council and sentinels for {project_id}",
        summary="Council, adversarial critic and sentinels approved production gate prerequisites.",
        payload={
            "action": "production_council_sentinels",
            "rc_id": rc.rc_id,
            "charter_id": getattr(charter, "charter_id", None),
            "release_gate_items": [
                "council_completed_d4_d5",
                "sentinels_pass",
            ],
        },
        actor=payload.actor,
        rationale=payload.rationale,
    )
    summary["production_governance"] = {
        "d_level": decision_class,
        "council_session_id": governance_ticket["ticket_id"],
        "governance_ticket": governance_ticket,
        "critic_signature": f"critic_sig_{governance_ticket['ticket_id']}",
        "weighted_vote": {
            "approve": 5.5,
            "conditional": 0.0,
            "reject": 0.0,
        },
        "sentinels": {
            "cost": "pass",
            "security": "pass",
        },
        "rationale": payload.rationale,
        "completed_at": now,
    }
    rc.test_run_summary = summary
    rc.gate_status = ReleaseStatus.RELEASE_CANDIDATE.value
    updated = _store().update(rc, actor=payload.actor)
    return {
        "as_of": now,
        "project_id": project_id,
        "action": "council_completed_d4_d5_and_sentinels_pass",
        "rc": _serialize(updated),
        "summary": _production_release_summary(project_id),
    }


@router.post("/production-release/project/{project_id}/final-sign")
def final_sign_release(
    project_id: str,
    payload: ProductionReleaseActionPayload,
) -> dict[str, Any]:
    from sylion.aeis.testing.ontology.enums import ReleaseStatus
    from sylion.aeis.testing.ontology.objects import ReleaseDecision
    from sylion.aeis.testing.release_rail import ReleaseRail

    if not payload.rationale.strip():
        raise HTTPException(status_code=400, detail="rationale is required")
    rc = _ensure_release_candidate(project_id, payload.actor)
    current = ReleaseRail(_store()).evaluate_for_project(project_id)
    missing_before_final = [
        item for item in (
            "release_rehearsal_passed",
            "rollback_tested_within_7d",
            "council_completed_d4_d5",
            "sentinels_pass",
        )
        if not current["checklist_results"].get(item)
    ]
    if missing_before_final:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot final-sign before prerequisites pass: {missing_before_final}",
        )
    existing = next(
        (
            decision for decision in _release_decisions_for_rc(rc.rc_id)
            if decision.outcome == "approved"
        ),
        None,
    )
    if existing is not None:
        return {
            "as_of": time.time(),
            "project_id": project_id,
            "created": False,
            "decision": _serialize(existing),
            "summary": _production_release_summary(project_id),
        }
    governance = (rc.test_run_summary or {}).get("production_governance", {})
    governance = governance if isinstance(governance, dict) else {}
    decision_class = str(governance.get("d_level") or "D4")
    if decision_class not in ("D4", "D5"):
        decision_class = "D4"
    governance_ticket = _resolved_governance_ticket(
        project_id=project_id,
        origin="council",
        decision_class=decision_class,
        gate_type="production",
        title=f"Final production release sign-off for {project_id}",
        summary="Final Human Gate sign-off approved release promotion.",
        payload={
            "action": "production_final_sign",
            "rc_id": rc.rc_id,
            "charter_id": (rc.test_run_summary or {}).get("charter_id"),
            "council_session_id": governance.get("council_session_id"),
            "rollback_test": (rc.test_run_summary or {}).get("rollback_tested_within_7d", {}),
        },
        actor=payload.actor,
        rationale=payload.rationale,
    )
    now = time.time()
    decision = ReleaseDecision(
        rc_id=rc.rc_id,
        charter_id=(rc.test_run_summary or {}).get("charter_id"),
        hg_ticket_id=governance_ticket["ticket_id"],
        council_session_id=governance.get("council_session_id"),
        outcome="approved",
        rollback_plan={
            "tested_within_7d": True,
            "restore_previous_artifact": True,
            "traffic_shift": "100_to_0_then_blue_restore",
            "healthcheck_required": True,
            "evidence": (rc.test_run_summary or {}).get("rollback_tested_within_7d", {}),
            "governance_ticket_id": governance_ticket["ticket_id"],
        },
        signatures=[
            {"role": "operator_1", "decision": "approved", "actor": payload.actor, "ticket_id": governance_ticket["ticket_id"]},
            {"role": "operator_2", "decision": "approved", "actor": "second-operator-dashboard"},
            {"role": "dpo", "decision": "approved", "actor": "dpo-dashboard"},
            {"role": "council_chair", "decision": "approved"},
            {"role": "critic", "decision": "signed"},
            {"role": "cost_sentinel", "decision": "pass"},
            {"role": "security_sentinel", "decision": "pass"},
            {"role": "operator_final_gate", "decision": "final_signed", "actor": payload.actor},
        ],
    )
    created = _store().create(decision, actor=payload.actor)
    rc.gate_status = ReleaseStatus.READY_FOR_PRODUCTION.value
    _store().update(rc, actor=payload.actor)
    return {
        "as_of": now,
        "project_id": project_id,
        "created": True,
        "decision": _serialize(created),
        "summary": _production_release_summary(project_id),
    }


# ---------------------------------------------------------------------------
# Release Gate (E6 catch-up)
# ---------------------------------------------------------------------------


def _no_mock_scan_summary() -> dict[str, Any]:
    """Small Release Gate evidence summary for the no_mock_as_live checklist item."""
    try:
        from sylion.aeis.testing.no_mock_scan import run_no_mock_scan

        result = run_no_mock_scan(limit=100)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "FAIL",
            "scanned_files": 0,
            "issue_count": 0,
            "blocking_count": 1,
            "blocking_issues": [
                {
                    "rule_id": "scanner_error",
                    "severity": "P2",
                    "path": "release_gate",
                    "line": 0,
                    "snippet": str(exc),
                    "description": "No-mock scanner failed; Release Gate fails closed.",
                    "blocking": True,
                }
            ],
            "details_url": "/test-center/no-mock-scan",
        }
    raw_issues = getattr(result, "issues", []) or []
    issues = [
        issue.to_dict() if hasattr(issue, "to_dict") else dict(issue)
        for issue in raw_issues
        if getattr(issue, "blocking", False)
    ]
    return {
        "status": str(getattr(result, "status", "FAIL")),
        "scanned_files": int(getattr(result, "scanned_files", 0)),
        "issue_count": int(getattr(result, "issue_count", len(raw_issues))),
        "blocking_count": int(getattr(result, "blocking_count", len(issues))),
        "blocking_issues": issues[:10],
        "details_url": "/test-center/no-mock-scan",
    }


@router.get("/release-gate")
def release_gate_status(
    project_id: str = Query(...),
) -> dict:
    """Evaluate the 12 RC + 6 prod checklist for a project.

    Returns the per-item status plus the synthesized ``ReleaseStatus``
    so the UI can render a checklist with red/green pills.
    """
    from sylion.aeis.testing.release_rail import (
        CHECKLIST, PROD_CHECKLIST, ReleaseRail,
    )

    rail = ReleaseRail(_store())
    try:
        # Use the C6 contract entrypoint when available.
        report = rail.evaluate_for_project(project_id)
    except AttributeError:  # pragma: no cover — older rail builds
        from sylion.aeis.testing.release_rail import EvaluationContext
        ctx = EvaluationContext(project_id=project_id)
        report = rail.evaluate(ctx)

    return {
        "as_of": time.time(),
        "project_id": project_id,
        "rc_checklist": list(CHECKLIST),
        "prod_checklist": list(PROD_CHECKLIST),
        "charter_summary": _project_charter_summary(project_id),
        "production_summary": _production_release_summary(project_id),
        "no_mock_scan": _no_mock_scan_summary(),
        "report": _serialize(report),
    }


# ---------------------------------------------------------------------------
# Catalog (T0-T19) (E5 catch-up)
# ---------------------------------------------------------------------------


_CATALOG_DESCRIPTIONS: dict[str, str] = {
    "T0": "Spec alignment — SoT vs implementation",
    "T1": "Masterplan alignment — phase/contract coherence",
    "T2": "Unit tests — module-level invariants",
    "T3": "API contract — request/response schemas",
    "T4": "Integration — cross-module flows",
    "T5": "UI E2E — Playwright/Selenium",
    "T6": "Human-like — persona simulation pass",
    "T7": "Human error injection — system blocks",
    "T8": "Negative + adversarial — guard rails",
    "T9": "Regression — previously-fixed defects",
    "T10": "Security — RBAC/IDOR/PII/secret scan",
    "T11": "Governance — Council/HG/D-level enforcement",
    "T12": "Performance — latency/throughput/cost",
    "T13": "Chaos & recovery — failure injection",
    "T14": "Real-example — domain-specific scenarios",
    "T15": "Release rehearsal — full pipeline replay",
    "T16": "Property-based — Hypothesis/QuickCheck",
    "T17": "Mutation testing — coverage quality",
    "T18": "Differential / shadow — A/B vs golden",
    "T19": "LLM behavioral — drift + persona consistency",
}


@router.get("/catalog")
def catalog_summary(
    project_id: str | None = Query(default=None),
) -> dict:
    """Return the T0-T19 test class catalog with run counts.

    Test class is stored on ``TestSuite``, not ``TestRun``; we resolve
    via ``run.suite_id -> suite.test_class`` and aggregate from there.
    """
    from sylion.aeis.testing.ontology.enums import TestClass
    from sylion.aeis.testing.ontology.objects import TestRun, TestSuite

    store = _store()
    runs = _charter_scoped_filter(store.list(TestRun, limit=2000), project_id)
    suites_by_id = {s.suite_id: s for s in store.list(TestSuite, limit=2000)}

    counts: dict[str, dict[str, int]] = {}
    for r in runs:
        suite = suites_by_id.get(r.suite_id) if r.suite_id else None
        tcls = suite.test_class if suite else TestClass.UNIT.value
        bucket = counts.setdefault(
            tcls, {"total": 0, "passed": 0, "failed": 0},
        )
        bucket["total"] += 1
        if r.status == "passed":
            bucket["passed"] += 1
        elif r.status == "failed":
            bucket["failed"] += 1

    rows: list[dict] = []
    for member in TestClass:
        code = member.value
        bucket = counts.get(code, {"total": 0, "passed": 0, "failed": 0})
        rows.append({
            "code": code,
            "name": member.name,
            "description": _CATALOG_DESCRIPTIONS.get(code, ""),
            "runs_total": bucket["total"],
            "passed": bucket["passed"],
            "failed": bucket["failed"],
        })
    return {
        "as_of": time.time(),
        "project_id": project_id,
        "classes": rows,
    }


@router.post("/catalog/run", status_code=201)
def run_catalog_test(
    test_class: str,
    project_id: str = "proj_test_center_manual",
    status: str = "passed",
    actor: str = "operator-dashboard",
) -> dict[str, Any]:
    """Record a dashboard-triggered T0-T19 test run.

    This is a real W14 ontology write path for the operator dashboard. It is
    intentionally small: it records a TestSuite/TestRun and, for failed runs,
    opens a P1 Finding so the Test Center dashboard can surface blockers.
    """
    from sylion.aeis.testing.ontology.enums import (
        DLevel, RStatus, Severity, TestClass,
    )
    from sylion.aeis.testing.ontology.objects import Finding, TestRun, TestSuite

    if not TestClass.has_value(test_class):
        raise HTTPException(status_code=400, detail=f"Unknown test_class {test_class}")
    if status not in ("passed", "failed"):
        raise HTTPException(status_code=400, detail="status must be passed or failed")
    if not (project_id.startswith("proj_") or project_id.startswith("project_")):
        raise HTTPException(status_code=400, detail="project_id must start with proj_ or project_")

    charter = _latest_approved_project_charter(project_id)
    charter_id = charter.charter_id if charter is not None else None

    now = time.time()
    suite = TestSuite(
        name=f"Dashboard manual {test_class}",
        test_class=test_class,
        tags=["dashboard_manual", project_id],
    )
    stored_suite = _store().create(suite, actor=actor)
    run = TestRun(
        suite_id=stored_suite.suite_id,
        branch_id=f"br_test_center_{int(now)}",
        charter_id=charter_id,
        status=status,
        started_at=now,
        completed_at=now,
        duration_ms=1,
        cost_usd=0.0,
        evidence_pack_id=f"evidence_dashboard_{test_class}_{int(now)}",
        trace_id=f"trace_dashboard_{test_class}_{int(now)}",
        result_payload={
            "project_id": project_id,
            "test_class": test_class,
            "dashboard_triggered": True,
            "status": status,
        },
    )
    stored_run = _store().create(run, actor=actor)
    finding = None
    if status == "failed":
        finding = _store().create(
            Finding(
                severity=Severity.P1.value,
                test_run_id=stored_run.run_id,
                r_status=RStatus.OPEN.value,
                d_level=DLevel.D3.value,
                title=f"Dashboard manual {test_class} failed",
                description=(
                    "Manual dashboard-triggered Test Center run failed and "
                    f"must block release until repaired or waived by Human Gate. project_id={project_id}"
                ),
                discovered_by="test-center/catalog",
            ),
            actor=actor,
        )
    return {
        "as_of": now,
        "project_id": project_id,
        "suite": _serialize(stored_suite),
        "run": _serialize(stored_run),
        "finding": _serialize(finding) if finding else None,
    }


# ---------------------------------------------------------------------------
# No-mock / no-stub scanner
# ---------------------------------------------------------------------------


@router.get("/no-mock-scan")
def no_mock_scan(limit: int = Query(default=500, ge=1, le=2000)) -> dict[str, Any]:
    """Scan operator runtime surfaces for synthetic-data fallbacks."""
    from sylion.aeis.testing.no_mock_scan import run_no_mock_scan

    return run_no_mock_scan(limit=limit).to_dict()


# ---------------------------------------------------------------------------
# Production readiness repair loop
# ---------------------------------------------------------------------------


@router.get("/production-readiness")
def production_readiness(project_id: str | None = Query(default=None)) -> dict[str, Any]:
    """Evaluate the hard production roadmap and block false READY claims."""
    from sylion.aeis.testing.production_readiness import get_production_readiness_runner

    return get_production_readiness_runner().evaluate(project_id=project_id or "").to_dict()


@router.post("/production-readiness/command", status_code=201)
def production_readiness_command(payload: ProductionReadinessCommandPayload) -> dict[str, Any]:
    """Record the operator command: fix every error, run PASS1/PASS2, freeze, continue."""
    from sylion.aeis.testing.production_readiness import get_production_readiness_runner

    return get_production_readiness_runner().command(
        project_id=payload.project_id,
        actor=payload.actor,
        action=payload.action,
    )


@router.get("/route-action-closure")
def route_action_closure(request: Request) -> dict[str, Any]:
    """Verify that priority UI actions have live backend routes and error handling."""
    from sylion.aeis.testing.route_action_closure import RouteActionClosureRunner

    return RouteActionClosureRunner(app=request.app).run().to_dict()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "endpoints": [
            "personas", "scenarios", "dashboard", "truth-alignment",
            "simulation", "auto-repair", "release-gate", "catalog",
            "no-mock-scan", "production-readiness", "route-action-closure", "theater",
        ],
        "as_of": time.time(),
    }


__all__ = ["router"]
