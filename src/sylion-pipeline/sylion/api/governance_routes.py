"""
SYLION API -- Governance routes.

Endpoints for: decision_ladder, council_workflow, roles,
gates_registry, evidence_workflow, policy_registry.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sylion.aeis.advisor.events.lifecycle import (
    await_advisor_decision,
    publish_lifecycle_event,
)
from sylion.security.rbac import requires_role

from sylion.governance.decision_ladder import (
    DecisionProposal, DecisionStatus, get_decision_ladder,
)
from sylion.governance.council_workflow import (
    CouncilSession, Vote, VoteValue, get_council_workflow,
)
from sylion.governance.roles import (
    AgentRole,
    Department,
    Permission,
    get_roles_manager as get_roles_registry,
)
from sylion.governance.gates_registry import (
    GateEvaluation, GateSeverity, get_gates_registry,
)
from sylion.governance.evidence_workflow import (
    EvidenceArtefact, get_evidence_workflow,
)
from sylion.core.decision_gate_engine import DecisionClass, GateDefinition

# Lazy import -- policy_registry may not exist yet
try:
    from sylion.governance.policy_registry import get_policy_registry
    _HAS_POLICY_REGISTRY = True
except ImportError:
    _HAS_POLICY_REGISTRY = False

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])


@router.get("/health")
def health() -> dict[str, object]:
    import time

    return {
        "status": "ok",
        "module": "governance",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Decision Ladder
# ---------------------------------------------------------------------------

class _ProposalBody(BaseModel):
    """JSON body shape for POST /governance/proposals.

    Bug fixed 2026-04-28: legacy signature used bare query parameters
    (``title: str, description: str, ...``) which forced FastAPI to
    interpret them as ``Query()``. The frontend's ``api.createProposal()``
    sends a JSON body, so the wizard at /governance ALWAYS got a 422 from
    Starlette ("Field required: query.title"). Now both styles work:
    body wins if present, query params are the fallback for the existing
    integration tests in tests/test_api_integration.py.
    """
    title: str | None = None
    description: str | None = None
    source_plan: str = ""
    scope: str = ""  # frontend-supplied taxonomy bucket
    module_id: str = ""
    change_type: str = ""
    blast_radius: str = "low"
    reversible: bool = True
    affects_contracts: bool = False
    affects_kernel: bool = False
    proposed_by: str = ""
    rollback_plan: str = ""


class _ProposalVoteBody(BaseModel):
    vote: str
    actor: str = "operator-dashboard"
    reason: str = ""


@router.post("/proposals", status_code=201)
def propose_decision(
    body: _ProposalBody | None = None,
    title: str | None = None,
    description: str | None = None,
    source_plan: str | None = None,
    module_id: str = "",
    change_type: str = "",
    blast_radius: str = "low",
    reversible: bool = True,
    affects_contracts: bool = False,
    affects_kernel: bool = False,
    proposed_by: str = "",
    rollback_plan: str = "",
):
    """Submit a new decision proposal. Auto-classifies to D0-D5.

    Accepts EITHER a JSON body (preferred — matches the frontend
    ``api.createProposal()`` shape with ``{title, description, scope}``)
    OR legacy query parameters (preserved for the existing pytest
    integration tests). Body always wins if both are present.
    """
    # Body takes precedence when present.
    if body is not None and (body.title or body.description):
        title = body.title or title
        description = body.description or description
        source_plan = body.source_plan or source_plan or ""
        module_id = body.module_id or module_id
        change_type = body.change_type or change_type
        blast_radius = body.blast_radius or blast_radius
        reversible = body.reversible if body.reversible is not None else reversible
        affects_contracts = body.affects_contracts or affects_contracts
        affects_kernel = body.affects_kernel or affects_kernel
        proposed_by = body.proposed_by or proposed_by
        rollback_plan = body.rollback_plan or rollback_plan

    if not title or not description:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "missing_required_fields",
                "required": ["title", "description"],
                "got_title": bool(title),
                "got_description": bool(description),
            },
        )

    ladder = get_decision_ladder()
    proposal = DecisionProposal(
        title=title,
        description=description,
        source_plan=source_plan or "",
        module_id=module_id,
        change_type=change_type,
        blast_radius=blast_radius,
        reversible=reversible,
        affects_contracts=affects_contracts,
        affects_kernel=affects_kernel,
        proposed_by=proposed_by,
        rollback_plan=rollback_plan,
    )
    return ladder.propose(proposal)


@router.get("/proposals")
def list_proposals(status: str | None = None,
                   decision_class: str | None = None,
                   source_plan: str | None = None):
    """List decision proposals with optional filters."""
    ladder = get_decision_ladder()
    return {"proposals": ladder.list_proposals(status=status,
                                               decision_class=decision_class,
                                               source_plan=source_plan)}


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str):
    """Get a single proposal by ID."""
    ladder = get_decision_ladder()
    proposal = ladder.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return proposal


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, approved_by: str = "",
                     notes: str = "",
                     _user: str = Depends(requires_role("owner"))):
    """Approve a classified proposal. Owner-only — D-level governance gate."""
    ladder = get_decision_ladder()
    result = ladder.approve(proposal_id, approved_by=approved_by, notes=notes)
    if not result.get("approved"):
        raise HTTPException(status_code=400, detail=result.get("message", "Approval failed"))
    event_id = publish_lifecycle_event(
        "aeis.final_approval.requested",
        {
            "decision_id": proposal_id,
            "project_id": result.get("module_id", ""),
            "d_level": result.get("decision_class", ""),
            "evidence_pack_id": result.get("evidence_pack_id"),
            "total_cost_usd_actual": 0,
            "total_cost_usd_budget": 0,
            "all_gates_passed": True,
        },
        source_module="sylion.api.governance_routes",
        primary_key=proposal_id,
    )
    decision = await_advisor_decision(event_id)
    if decision.get("decision") == "block":
        raise HTTPException(status_code=423, detail=decision)
    if decision.get("decision") == "defer_to_human_gate":
        raise HTTPException(status_code=202, detail=decision)
    return result


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, rejected_by: str = "",
                    reason: str = ""):
    """Reject a classified proposal."""
    ladder = get_decision_ladder()
    result = ladder.reject(proposal_id, rejected_by=rejected_by, reason=reason)
    if not result.get("rejected"):
        raise HTTPException(status_code=400, detail=result.get("message", "Rejection failed"))
    return result


@router.post("/proposals/{proposal_id}/vote")
def vote_proposal(proposal_id: str, body: _ProposalVoteBody):
    """Dashboard-compatible proposal vote endpoint.

    The frontend governance panel has a generic vote action. The backend
    canonical API exposes approve/reject transitions, so this endpoint keeps
    the UI contract live while still mutating the Decision Ladder state.
    """
    vote = (body.vote or "").strip().lower()
    ladder = get_decision_ladder()
    if vote in {"approve", "approved", "accept", "accepted", "yes", "tak"}:
        result = ladder.approve(
            proposal_id,
            approved_by=body.actor,
            notes=body.reason or "Approved through dashboard vote.",
        )
        if not result.get("approved"):
            raise HTTPException(status_code=400, detail=result.get("message", "Approval failed"))
        return {"proposal_id": proposal_id, "vote": vote, "result": result}
    if vote in {"reject", "rejected", "deny", "denied", "no", "nie"}:
        result = ladder.reject(
            proposal_id,
            rejected_by=body.actor,
            reason=body.reason or "Rejected through dashboard vote.",
        )
        if not result.get("rejected"):
            raise HTTPException(status_code=400, detail=result.get("message", "Rejection failed"))
        return {"proposal_id": proposal_id, "vote": vote, "result": result}
    raise HTTPException(
        status_code=422,
        detail={
            "error": "unsupported_vote",
            "accepted": ["approve", "reject"],
            "got": body.vote,
        },
    )


@router.post("/proposals/{proposal_id}/execute")
def execute_proposal(proposal_id: str,
                     _user: str = Depends(requires_role("owner"))):
    """Mark an approved proposal as executed. Owner-only — irreversible."""
    ladder = get_decision_ladder()
    result = ladder.execute(proposal_id)
    if not result.get("executed"):
        raise HTTPException(status_code=400, detail=result.get("message", "Execution failed"))
    return result


# ---------------------------------------------------------------------------
# Council Workflow
# ---------------------------------------------------------------------------

@router.post("/council/sessions", status_code=201)
def open_council_session(proposal_id: str, decision_class: str = "D3",
                         title: str = "", description: str = "",
                         evidence_ref: str = ""):
    """Open a new council voting session."""
    council = get_council_workflow()
    session = CouncilSession(
        proposal_id=proposal_id,
        decision_class=DecisionClass(decision_class),
        title=title,
        description=description,
        evidence_ref=evidence_ref,
    )
    return council.open_session(session)


@router.get("/council/sessions")
def list_council_sessions(status: str | None = None):
    """List council sessions with optional status filter."""
    council = get_council_workflow()
    return {"sessions": council.list_sessions(status=status)}


@router.get("/council/sessions/{session_id}")
def get_council_session(session_id: str):
    """Get a council session by ID."""
    council = get_council_workflow()
    session = council.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@router.post("/council/sessions/{session_id}/vote")
def cast_vote(session_id: str, member_id: str,
              value: str = "approve", rationale: str = ""):
    """Cast a vote in a council session."""
    council = get_council_workflow()
    vote = Vote(
        session_id=session_id,
        member_id=member_id,
        value=VoteValue(value),
        rationale=rationale,
    )
    result = council.cast_vote(vote)
    if not result.get("cast"):
        raise HTTPException(status_code=400, detail=result.get("message", "Vote failed"))
    return result


@router.post("/council/sessions/{session_id}/tally")
def tally_session(session_id: str):
    """Tally votes and determine outcome for a session."""
    council = get_council_workflow()
    return council.tally(session_id)


@router.post("/council/sessions/{session_id}/human-gate")
def human_gate_decide(session_id: str, decision: str, by: str = ""):
    """Human gate decision for D4+ sessions."""
    council = get_council_workflow()
    result = council.human_gate_decide(session_id, decision, by=by)
    if not result.get("decided"):
        raise HTTPException(status_code=400, detail=result.get("message", "Decision failed"))
    return result


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

@router.post("/roles", status_code=201)
def register_agent(name: str, department: str = "architecture",
                   level: int = 1, skills: str = "",
                   _user: str = Depends(requires_role("owner"))):
    """Register a new agent role. Owner-only — privilege escalation vector."""
    roles = get_roles_registry()
    role = AgentRole(
        name=name,
        department=Department(department),
        level=level,
        skills=[s.strip() for s in skills.split(",") if s.strip()],
    )
    try:
        return roles.register(role)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/roles")
def list_agents(department: str | None = None,
                active_only: bool = True):
    """List agent roles with optional filters."""
    roles = get_roles_registry()
    return {"agents": roles.list_agents(department=department,
                                        active_only=active_only)}


@router.get("/roles/{agent_id}")
def get_agent(agent_id: str):
    """Get a single agent by ID."""
    roles = get_roles_registry()
    agent = roles.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return agent


@router.delete("/roles/{agent_id}")
def deregister_agent(agent_id: str):
    """Deregister an agent."""
    roles = get_roles_registry()
    removed = roles.deregister(agent_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return {"deregistered": agent_id}


@router.post("/roles/{agent_id}/grant")
def grant_permission(agent_id: str, permission: str):
    """Grant a permission to an agent."""
    roles = get_roles_registry()
    try:
        return roles.grant_permission(agent_id, Permission(permission))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/roles/{agent_id}/revoke")
def revoke_permission(agent_id: str, permission: str):
    """Revoke a permission from an agent."""
    roles = get_roles_registry()
    try:
        return roles.revoke_permission(agent_id, Permission(permission))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/roles/{agent_id}/check-permission")
def check_permission(agent_id: str, permission: str):
    """Check if an agent has a specific permission."""
    roles = get_roles_registry()
    agent = roles.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    has = Permission(permission).value in set(agent.get("permissions", []))
    return {"agent_id": agent_id, "permission": permission, "granted": has}


# ---------------------------------------------------------------------------
# Gates Registry
# ---------------------------------------------------------------------------

@router.get("/gates")
def list_gates():
    """List all registered gate definitions."""
    gates = get_gates_registry()
    return {"gates": gates.list_gates()}


@router.post("/gates", status_code=201)
def register_gate(gate_id: str, name: str, description: str = "",
                  fail_condition: str = "", blocks: str = "",
                  decision_class_min: str = "D2",
                  severity: str = "blocking"):
    """Register a new gate."""
    gates = get_gates_registry()
    gate_def = GateDefinition(
        gate_id=gate_id,
        name=name,
        description=description,
        fail_condition=fail_condition,
        blocks=blocks,
        decision_class_min=DecisionClass(decision_class_min),
    )
    return gates.register_gate(gate_def, severity)


@router.post("/gates/{gate_id}/evaluate")
def evaluate_gate(gate_id: str, module_id: str = "",
                  result: str = "pass", message: str = "",
                  severity: str = "blocking"):
    """Evaluate a gate for a module."""
    gates = get_gates_registry()
    evaluation = GateEvaluation(
        gate_id=gate_id,
        module_id=module_id,
        result=result,
        severity=severity,
        message=message,
    )
    return gates.evaluate(evaluation)


@router.get("/gates/evaluations")
def list_gate_evaluations(gate_id: str | None = None,
                          module_id: str | None = None,
                          limit: int = 100):
    """List gate evaluations with optional filters."""
    gates = get_gates_registry()
    return {"evaluations": gates.get_evaluations(gate_id=gate_id,
                                                  module_id=module_id,
                                                  limit=limit)}


@router.get("/gates/blocking/{module_id}")
def check_blocking(module_id: str):
    """Check if any blocking gate has failed for a module."""
    gates = get_gates_registry()
    return gates.check_blocking(module_id)


# ---------------------------------------------------------------------------
# Evidence Workflow
# ---------------------------------------------------------------------------

@router.post("/evidence-packs", status_code=201)
def create_evidence_pack(proposal_id: str, decision_class: str,
                         created_by: str = ""):
    """Create a new evidence pack."""
    wf = get_evidence_workflow()
    return wf.create_pack(proposal_id, decision_class, created_by=created_by)


@router.get("/evidence-packs")
def list_evidence_packs(proposal_id: str | None = None,
                        status: str | None = None):
    """List evidence packs with optional filters."""
    wf = get_evidence_workflow()
    return {"packs": wf.list_packs(proposal_id=proposal_id, status=status)}


@router.get("/evidence-packs/{pack_id}")
def get_evidence_pack(pack_id: str):
    """Get a single evidence pack."""
    wf = get_evidence_workflow()
    pack = wf.get_pack(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Evidence pack {pack_id} not found")
    return pack


@router.post("/evidence-packs/{pack_id}/artefacts")
def add_artefact(pack_id: str, name: str, artefact_type: str,
                 content_hash: str = "", description: str = "",
                 source: str = ""):
    """Add an artefact to an evidence pack."""
    wf = get_evidence_workflow()
    artefact = EvidenceArtefact(
        name=name,
        artefact_type=artefact_type,
        content_hash=content_hash,
        description=description,
        source=source,
    )
    return wf.add_artefact(pack_id, artefact)


@router.post("/evidence-packs/{pack_id}/validate")
def validate_evidence_pack(pack_id: str):
    """Validate an evidence pack against decision class requirements."""
    wf = get_evidence_workflow()
    return wf.validate_pack(pack_id)


@router.post("/evidence-packs/{pack_id}/submit")
def submit_evidence_pack(pack_id: str):
    """Submit a validated evidence pack."""
    wf = get_evidence_workflow()
    return wf.submit_pack(pack_id)


# ---------------------------------------------------------------------------
# Policy Registry -- governance policies
# ---------------------------------------------------------------------------

@router.get("/policies")
def list_governance_policies(category: str | None = None,
                             enforcement: str | None = None,
                             enabled_only: bool = True):
    """List governance policies."""
    if not _HAS_POLICY_REGISTRY:
        return {"policies": [], "message": "policy_registry module not available"}
    reg = get_policy_registry()
    return {"policies": reg.list_policies(category=category,
                                          enforcement=enforcement,
                                          enabled_only=enabled_only)}


@router.post("/policies/{policy_id}/evaluate")
def evaluate_governance_policy(policy_id: str, target_type: str = "",
                               target_id: str = "",
                               result: str = "applied",
                               applied_by: str = ""):
    """Evaluate (apply) a governance policy against a target."""
    if not _HAS_POLICY_REGISTRY:
        raise HTTPException(status_code=501,
                            detail="policy_registry module not available")
    reg = get_policy_registry()
    policy = reg.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404,
                            detail=f"Policy {policy_id} not found")
    return reg.apply(policy_id, target_type, target_id,
                     result=result, applied_by=applied_by)


@router.get("/compliance/{scope}")
def check_compliance(scope: str, target_id: str | None = None):
    """Check compliance for a given scope.

    Returns all active policies in the given category and their
    latest application results for the optional target_id.
    """
    if not _HAS_POLICY_REGISTRY:
        return {"scope": scope, "compliant": True,
                "policies": [], "message": "policy_registry module not available"}
    reg = get_policy_registry()
    policies = reg.list_policies(category=scope, enabled_only=True)

    results = []
    for p in policies:
        pid = p.get("policy_id", "")
        entry = {"policy_id": pid, "name": p.get("name", ""),
                 "enforcement": p.get("enforcement", "advisory")}
        if target_id:
            apps = reg.get_applications(pid, limit=5)
            entry["recent_applications"] = apps
        results.append(entry)

    blocking = [r for r in results if r["enforcement"] == "blocking"]
    compliant = len(blocking) == 0

    return {"scope": scope, "compliant": compliant, "policies": results}


# ---------------------------------------------------------------------------
# Decision Snapshot -- lazy accessor
# ---------------------------------------------------------------------------

_snapshot = None


def _get_snapshot():
    global _snapshot
    if _snapshot is not None:
        return _snapshot
    from sylion.governance.decision_snapshot import get_decision_snapshot
    _snapshot = get_decision_snapshot()
    return _snapshot


# ---------------------------------------------------------------------------
# Decision Snapshot -- request models
# ---------------------------------------------------------------------------

class CaptureSnapshotRequest(BaseModel):
    decision_id: str
    gate_id: str = ""
    session_id: str = ""
    pipeline_run_id: str = ""
    choice_made: str = ""
    choice_id: str = ""
    consequences: dict = {}


class ChangeDecisionRequest(BaseModel):
    new_choice: str
    new_consequences: dict = {}


class AcknowledgeCascadeRequest(BaseModel):
    action_taken: str = ""


# ---------------------------------------------------------------------------
# Decision Snapshot -- endpoints
# ---------------------------------------------------------------------------

@router.post("/decision-snapshots", status_code=201)
def capture_decision_snapshot(body: CaptureSnapshotRequest):
    """Capture a decision snapshot for audit and cascade tracking."""
    snap = _get_snapshot()
    return snap.capture_snapshot(
        decision_id=body.decision_id,
        gate_id=body.gate_id,
        session_id=body.session_id,
        pipeline_run_id=body.pipeline_run_id,
        choice_made=body.choice_made,
        choice_id=body.choice_id,
        consequences=body.consequences,
    )


@router.get("/decision-snapshots")
def list_decision_snapshots(decision_class: Optional[str] = None,
                            is_active: Optional[bool] = None,
                            limit: int = 100):
    """List decision snapshots with optional filters."""
    snap = _get_snapshot()
    return {"snapshots": snap.list_snapshots(
        decision_class=decision_class,
        is_active=is_active,
        limit=limit,
    )}


@router.get("/decision-snapshots/timeline")
def get_snapshot_timeline(decision_id: Optional[str] = None,
                          gate_id: Optional[str] = None,
                          session_id: Optional[str] = None):
    """Get a timeline of decision snapshots."""
    snap = _get_snapshot()
    return {"timeline": snap.get_timeline(
        decision_id=decision_id,
        gate_id=gate_id,
        session_id=session_id,
    )}


@router.get("/decision-snapshots/active-chain")
def get_active_decision_chain():
    """Get the active decision chain with dependencies."""
    snap = _get_snapshot()
    return snap.get_active_chain()


@router.get("/decision-snapshots/{snapshot_id}")
def get_decision_snapshot(snapshot_id: str):
    """Get a single decision snapshot by ID."""
    snap = _get_snapshot()
    record = snap.get_snapshot(snapshot_id)
    if not record:
        raise HTTPException(status_code=404,
                            detail=f"Snapshot {snapshot_id} not found")
    return record


@router.post("/decision-snapshots/{snapshot_id}/change")
def change_decision(snapshot_id: str, body: ChangeDecisionRequest):
    """Change a decision and return cascade impact."""
    snap = _get_snapshot()
    result = snap.change_decision(
        snapshot_id,
        new_choice=body.new_choice,
        new_consequences=body.new_consequences,
    )
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Snapshot {snapshot_id} not found")
    return result


@router.get("/decision-snapshots/{snapshot_id}/cascade-impact")
def get_cascade_impact(snapshot_id: str):
    """Get the cascade impact tree for a decision snapshot."""
    snap = _get_snapshot()
    result = snap.get_cascade_impact(snapshot_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Snapshot {snapshot_id} not found")
    return result


@router.get("/decision-snapshots/{snapshot_id_1}/diff/{snapshot_id_2}")
def diff_decision_snapshots(snapshot_id_1: str, snapshot_id_2: str):
    """Diff module states between two decision snapshots."""
    snap = _get_snapshot()
    result = snap.diff_snapshots(snapshot_id_1, snapshot_id_2)
    if not result:
        raise HTTPException(status_code=404,
                            detail="One or both snapshots not found")
    return result


# ---------------------------------------------------------------------------
# Cascade Events
# ---------------------------------------------------------------------------

@router.post("/cascade-events/{event_id}/acknowledge")
def acknowledge_cascade_event(event_id: str,
                              body: AcknowledgeCascadeRequest):
    """Acknowledge a cascade event."""
    snap = _get_snapshot()
    result = snap.acknowledge_cascade(event_id,
                                      action_taken=body.action_taken)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Cascade event {event_id} not found")
    return result


@router.get("/cascade-events")
def list_cascade_events(requires_human: Optional[bool] = None):
    """List cascade events, optionally filtered."""
    snap = _get_snapshot()
    return {"events": snap.list_cascade_events(
        requires_human=requires_human,
    )}


# ---------------------------------------------------------------------------
# Evidence Spine -- lazy accessor
# ---------------------------------------------------------------------------

_spine = None
def _get_spine():
    global _spine
    if _spine is not None:
        return _spine
    from sylion.governance.evidence_spine import get_governance_spine
    _spine = get_governance_spine()
    return _spine


@router.get("/spine")
def list_spine_entries(from_seq: Optional[int] = None, to_seq: Optional[int] = None, entry_type: Optional[str] = None):
    return {"entries": _get_spine().get_spine(from_seq=from_seq, to_seq=to_seq, entry_type=entry_type)}

@router.get("/spine/stats")
def get_spine_stats():
    return _get_spine().get_chain_stats()

@router.get("/spine/verify")
def verify_spine_chain():
    return _get_spine().verify_chain()

@router.get("/spine/decision/{decision_id}")
def get_spine_for_decision(decision_id: str):
    return {"entries": _get_spine().get_entries_for_decision(decision_id)}

@router.get("/spine/{entry_id}")
def get_spine_entry(entry_id: str):
    result = _get_spine().get_entry(entry_id)
    if not result:
        raise HTTPException(404, "Entry not found")
    return {"entry": result}


# ---------------------------------------------------------------------------
# Compliance Engine -- lazy accessor
# ---------------------------------------------------------------------------

_compliance = None


def _get_compliance():
    global _compliance
    if _compliance is not None:
        return _compliance
    from sylion.governance.compliance_engine import get_compliance_engine
    _compliance = get_compliance_engine()
    return _compliance


# ---------------------------------------------------------------------------
# Compliance Engine -- request models
# ---------------------------------------------------------------------------

class AddRuleRequest(BaseModel):
    name: str
    scope: str
    rule_type: str
    parameters: dict
    severity: str = "blocking"
    description: str = ""


# ---------------------------------------------------------------------------
# Compliance Engine -- endpoints
# ---------------------------------------------------------------------------

@router.post("/compliance/rules", status_code=201)
def add_compliance_rule(body: AddRuleRequest):
    """Add a new compliance rule."""
    engine = _get_compliance()
    return engine.add_rule(
        name=body.name,
        scope=body.scope,
        rule_type=body.rule_type,
        parameters=body.parameters,
        severity=body.severity,
        description=body.description,
    )


@router.get("/compliance/rules")
def list_compliance_rules(scope: Optional[str] = None,
                          rule_type: Optional[str] = None,
                          enabled_only: bool = True):
    """List compliance rules with optional filters."""
    engine = _get_compliance()
    return {"rules": engine.list_rules(scope=scope,
                                       rule_type=rule_type,
                                       enabled_only=enabled_only)}


@router.delete("/compliance/rules/{rule_id}")
def remove_compliance_rule(rule_id: str):
    """Disable (soft-delete) a compliance rule."""
    engine = _get_compliance()
    removed = engine.remove_rule(rule_id)
    if not removed:
        raise HTTPException(status_code=404,
                            detail=f"Rule {rule_id} not found")
    return {"removed": rule_id}


@router.get("/compliance/check")
def check_compliance(decision_id: Optional[str] = None,
                     scope: str = "global"):
    """Run all applicable compliance rules against a decision."""
    engine = _get_compliance()
    return engine.check_compliance(decision_id=decision_id, scope=scope)


@router.get("/compliance/report")
def generate_compliance_report(scope: str = "global"):
    """Generate a compliance report for the given scope."""
    engine = _get_compliance()
    return engine.generate_report(scope=scope)


@router.get("/compliance/report/latest")
def get_latest_compliance_report(scope: str = "global"):
    """Return the most recent compliance report for a scope."""
    engine = _get_compliance()
    report = engine.get_latest_report(scope=scope)
    if not report:
        # Dashboard panels should be able to render a first-run state. Generate
        # a baseline report instead of making the UI handle an avoidable 404.
        return engine.generate_report(scope=scope)
    return report


@router.get("/compliance/score")
def get_compliance_score(scope: str = "global"):
    """Return the current compliance score (0.0 - 1.0)."""
    engine = _get_compliance()
    score = engine.get_compliance_score(scope=scope)
    return {"scope": scope, "score": score}


@router.get("/compliance/violations")
def list_compliance_violations(decision_id: Optional[str] = None,
                               scope: Optional[str] = None):
    """List all compliance violations (failed checks)."""
    engine = _get_compliance()
    return {"violations": engine.list_violations(decision_id=decision_id,
                                                  scope=scope)}


@router.get("/compliance/history")
def get_compliance_history(scope: str = "global", limit: int = 20):
    """List past compliance reports for a scope."""
    engine = _get_compliance()
    return {"history": engine.get_compliance_history(scope=scope,
                                                     limit=limit)}


# ---------------------------------------------------------------------------
# Conflict Resolver -- lazy accessor
# ---------------------------------------------------------------------------

_conflict = None


def _get_conflict():
    global _conflict
    if _conflict is not None:
        return _conflict
    from sylion.governance.conflict_resolver import get_conflict_resolver
    _conflict = get_conflict_resolver()
    return _conflict


# ---------------------------------------------------------------------------
# Conflict Resolver -- request models
# ---------------------------------------------------------------------------

class ResolveConflictRequest(BaseModel):
    resolution: str
    resolved_by: str = "system"
    details: dict = {}


# ---------------------------------------------------------------------------
# Conflict Resolver -- endpoints
# (static routes before parameterized /{conflict_id} routes)
# ---------------------------------------------------------------------------

@router.get("/conflicts")
def list_conflicts(status: Optional[str] = None,
                   severity: Optional[str] = None):
    """List conflicts with optional status / severity filters."""
    resolver = _get_conflict()
    return {"conflicts": resolver.list_conflicts(status=status,
                                                  severity=severity)}


@router.get("/conflicts/unresolved")
def get_unresolved_conflicts():
    """Return all detected / analyzing conflicts not yet resolved."""
    resolver = _get_conflict()
    return {"conflicts": resolver.get_unresolved()}


@router.get("/conflicts/stats")
def get_conflict_stats():
    """Return aggregate conflict statistics."""
    resolver = _get_conflict()
    return resolver.get_conflict_stats()


@router.get("/conflicts/{conflict_id}")
def get_conflict(conflict_id: str):
    """Get a single conflict by ID."""
    resolver = _get_conflict()
    conflict = resolver.get_conflict(conflict_id)
    if not conflict:
        raise HTTPException(status_code=404,
                            detail=f"Conflict {conflict_id} not found")
    return conflict


@router.post("/conflicts/{conflict_id}/analyze")
def analyze_conflict(conflict_id: str):
    """Deep analysis of a conflict with suggested resolution."""
    resolver = _get_conflict()
    result = resolver.analyze_conflict(conflict_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Conflict {conflict_id} not found")
    return result


@router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(conflict_id: str, body: ResolveConflictRequest):
    """Apply a resolution to a conflict."""
    resolver = _get_conflict()
    result = resolver.resolve_conflict(
        conflict_id,
        resolution=body.resolution,
        resolved_by=body.resolved_by,
        details=body.details,
    )
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Conflict {conflict_id} not found")
    return result


@router.post("/conflicts/{conflict_id}/auto-resolve")
def auto_resolve_conflict(conflict_id: str):
    """Attempt automatic resolution based on heuristics."""
    resolver = _get_conflict()
    return resolver.auto_resolve(conflict_id)


@router.post("/conflicts/{conflict_id}/escalate")
def escalate_conflict(conflict_id: str):
    """Escalate a conflict to council for D3+ decisions."""
    resolver = _get_conflict()
    result = resolver.escalate_to_council(conflict_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Conflict {conflict_id} not found")
    return result


# ---------------------------------------------------------------------------
# Decision Audit Trail -- lazy accessor
# ---------------------------------------------------------------------------

_audit = None


def _get_audit():
    global _audit
    if _audit is not None:
        return _audit
    from sylion.governance.decision_audit import get_decision_audit
    _audit = get_decision_audit()
    return _audit


# ---------------------------------------------------------------------------
# Decision Audit Trail -- endpoints
# (static routes before parameterized /{audit_id} routes)
# ---------------------------------------------------------------------------

@router.get("/audit/log")
def get_audit_log(decision_id: Optional[str] = None,
                  event_type: Optional[str] = None,
                  severity: Optional[str] = None,
                  source_module: Optional[str] = None,
                  from_time: Optional[float] = None,
                  to_time: Optional[float] = None,
                  limit: int = 100):
    """Filtered query of audit entries, ordered newest-first."""
    audit = _get_audit()
    return {"entries": audit.get_audit_log(
        decision_id=decision_id,
        event_type=event_type,
        severity=severity,
        source_module=source_module,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
    )}


@router.get("/audit/stats")
def get_audit_stats():
    """Aggregate statistics for the decision audit trail."""
    audit = _get_audit()
    return audit.get_audit_stats()


@router.get("/audit/export")
def export_audit_log(from_time: Optional[float] = None,
                     to_time: Optional[float] = None):
    """Export audit entries as JSON within the given time range."""
    audit = _get_audit()
    return {"data": audit.export_audit_log(from_time=from_time, to_time=to_time)}


@router.get("/audit/timeline/{decision_id}")
def get_audit_timeline(decision_id: str):
    """All audit events for a decision, chronological (oldest-first)."""
    audit = _get_audit()
    return {"timeline": audit.get_audit_timeline(decision_id)}


@router.get("/audit/{audit_id}")
def get_audit_entry(audit_id: str):
    """Get a single audit entry by ID."""
    audit = _get_audit()
    entry = audit.get_audit_entry(audit_id)
    if not entry:
        raise HTTPException(status_code=404,
                            detail=f"Audit entry {audit_id} not found")
    return entry


@router.delete("/audit/purge")
def purge_old_entries(older_than_days: int = 365):
    """Remove audit entries older than the given number of days."""
    audit = _get_audit()
    deleted = audit.purge_old_entries(older_than_days=older_than_days)
    return {"deleted": deleted, "older_than_days": older_than_days}


# ---------------------------------------------------------------------------
# Lifecycle Gates
# ---------------------------------------------------------------------------


@router.get("/lifecycle/stages")
def list_lifecycle_stages():
    """List all defined lifecycle stages."""
    return {"stages": [
        {"name": "draft", "label": "Draft", "order": 0},
        {"name": "build", "label": "Build", "order": 1},
        {"name": "validate", "label": "Validate", "order": 2},
        {"name": "shadow", "label": "Shadow", "order": 3},
        {"name": "dual", "label": "Dual Run", "order": 4},
        {"name": "cutover", "label": "Cutover", "order": 5},
        {"name": "stable", "label": "Stable", "order": 6},
        {"name": "deprecated", "label": "Deprecated", "order": 7},
    ]}


@router.get("/lifecycle/entries")
def list_lifecycle_entries(module_id: str = None):
    """List lifecycle gate enforcement entries."""
    from sylion.core.module_registry import get_registry
    reg = get_registry()
    modules = reg.list_modules()
    entries = []
    for m in modules:
        if module_id and m.get("module_id") != module_id:
            continue
        entries.append({
            "module_id": m.get("module_id", ""),
            "lifecycle": m.get("lifecycle", "draft"),
            "stage": m.get("lifecycle", "draft"),
            "registered_at": m.get("registered_at", 0),
            "last_heartbeat": m.get("last_heartbeat", 0),
        })
    return {"entries": entries}


# ---------------------------------------------------------------------------
# Cascade Analyzer -- lazy accessor
# ---------------------------------------------------------------------------

_cascade_analyzer = None


def _get_cascade_analyzer():
    global _cascade_analyzer
    if _cascade_analyzer is not None:
        return _cascade_analyzer
    from sylion.governance.cascade_analyzer import get_cascade_analyzer
    _cascade_analyzer = get_cascade_analyzer()
    return _cascade_analyzer


# ---------------------------------------------------------------------------
# Cascade Analyzer -- endpoints
# (static routes before parameterized /{analysis_id} routes)
# ---------------------------------------------------------------------------

@router.get("/cascade/stats")
def cascade_analyzer_stats():
    """Get cascade analyzer statistics."""
    return _get_cascade_analyzer().get_stats()


@router.get("/cascade/analyses")
def list_cascade_analyses(source_module: Optional[str] = None,
                          risk_level: Optional[str] = None,
                          limit: int = 100):
    """List cascade analyses with optional filters."""
    analyzer = _get_cascade_analyzer()
    return {"analyses": analyzer.list_analyses(source_module=source_module,
                                               risk_level=risk_level,
                                               limit=limit)}


@router.post("/cascade/analyze", status_code=201)
def analyze_cascade_change(source_module: str, change_type: str,
                           change_description: str = ""):
    """Analyze cascade effects of a change."""
    analyzer = _get_cascade_analyzer()
    try:
        return analyzer.analyze_change(source_module, change_type,
                                       change_description=change_description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cascade/analyses/{analysis_id}")
def get_cascade_analysis(analysis_id: str):
    """Get a single cascade analysis by ID."""
    result = _get_cascade_analyzer().get_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Analysis {analysis_id} not found")
    return result


@router.get("/cascade/analyses/{analysis_id}/paths")
def get_cascade_analysis_paths(analysis_id: str):
    """Get cascade paths for an analysis."""
    analyzer = _get_cascade_analyzer()
    analysis = analyzer.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404,
                            detail=f"Analysis {analysis_id} not found")
    return {"paths": analyzer.get_cascade_paths(analysis_id)}


# ---------------------------------------------------------------------------
# Conflict Detector -- lazy accessor
# ---------------------------------------------------------------------------

_conflict_detector = None


def _get_conflict_detector():
    global _conflict_detector
    if _conflict_detector is not None:
        return _conflict_detector
    from sylion.governance.conflict_detector import get_conflict_detector
    _conflict_detector = get_conflict_detector()
    return _conflict_detector


# ---------------------------------------------------------------------------
# Conflict Detector -- endpoints
# (static routes before parameterized /{conflict_id} routes)
# ---------------------------------------------------------------------------

@router.post("/conflict-detections", status_code=201)
def detect_conflict(module_id: str, change_a: str, change_b: str,
                    change_type: str = "concurrent_edit"):
    """Detect and record a conflict between concurrent changes."""
    detector = _get_conflict_detector()
    try:
        return detector.detect_conflict(module_id, change_a, change_b,
                                        change_type=change_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/conflict-detections")
def list_detected_conflicts(status: Optional[str] = None,
                            module_id: Optional[str] = None,
                            limit: int = 100):
    """List detected conflicts with optional filters."""
    detector = _get_conflict_detector()
    return {"conflicts": detector.list_conflicts(status=status,
                                                  module_id=module_id,
                                                  limit=limit)}


@router.get("/conflict-detections/stats")
def conflict_detector_stats():
    """Get conflict detector statistics."""
    return _get_conflict_detector().get_stats()


@router.post("/conflict-detections/rules", status_code=201)
def add_conflict_rule(conflict_type: str, detection_pattern: str,
                      auto_resolve: str = ""):
    """Add a conflict detection rule."""
    detector = _get_conflict_detector()
    try:
        return detector.add_rule(conflict_type, detection_pattern,
                                 auto_resolve=auto_resolve)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/conflict-detections/rules")
def list_conflict_rules():
    """List all conflict detection rules."""
    return {"rules": _get_conflict_detector().list_rules()}


@router.get("/conflict-detections/{conflict_id}")
def get_detected_conflict(conflict_id: str):
    """Get a single detected conflict by ID."""
    result = _get_conflict_detector().get_conflict(conflict_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Conflict {conflict_id} not found")
    return result


@router.post("/conflict-detections/{conflict_id}/resolve")
def resolve_detected_conflict(conflict_id: str, resolution: str):
    """Resolve a detected conflict."""
    detector = _get_conflict_detector()
    try:
        result = detector.resolve_conflict(conflict_id, resolution)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Conflict {conflict_id} not found")
    return result


# ---------------------------------------------------------------------------
# Compliance Checker -- lazy accessor
# ---------------------------------------------------------------------------

_compliance_checker = None


def _get_compliance_checker():
    global _compliance_checker
    if _compliance_checker is not None:
        return _compliance_checker
    from sylion.governance.compliance_checker import get_compliance_checker
    _compliance_checker = get_compliance_checker()
    return _compliance_checker


# ---------------------------------------------------------------------------
# Compliance Checker -- request models
# ---------------------------------------------------------------------------

class CreatePolicyRequest(BaseModel):
    name: str
    scope: str
    rules: list[dict] = []
    severity: str = "info"


class UpdatePolicyRequest(BaseModel):
    name: str | None = None
    rules: list[dict] | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Compliance Checker -- endpoints
# (static routes before parameterized /{policy_id} /{check_id} routes)
# ---------------------------------------------------------------------------

@router.get("/checker/stats")
def compliance_checker_stats():
    """Get compliance checker statistics."""
    return _get_compliance_checker().get_stats()


@router.post("/checker/policies", status_code=201)
def create_compliance_policy(body: CreatePolicyRequest):
    """Create a new compliance policy."""
    checker = _get_compliance_checker()
    try:
        return checker.create_policy(body.name, body.scope, body.rules,
                                     severity=body.severity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/checker/policies")
def list_compliance_policies(scope: Optional[str] = None,
                             enabled: Optional[bool] = None):
    """List compliance policies with optional filters."""
    return {"policies": _get_compliance_checker().list_policies(
        scope=scope, enabled=enabled,
    )}


@router.put("/checker/policies/{policy_id}")
def update_compliance_policy(policy_id: str, body: UpdatePolicyRequest):
    """Update a compliance policy."""
    checker = _get_compliance_checker()
    result = checker.update_policy(
        policy_id, name=body.name, rules=body.rules, enabled=body.enabled,
    )
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Policy {policy_id} not found")
    return result


@router.delete("/checker/policies/{policy_id}")
def delete_compliance_policy(policy_id: str):
    """Delete a compliance policy."""
    checker = _get_compliance_checker()
    deleted = checker.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Policy {policy_id} not found")
    return {"deleted": policy_id}


@router.post("/checker/check")
def run_compliance_check(module_id: str, scope: str = "all"):
    """Run compliance check for a module."""
    checker = _get_compliance_checker()
    try:
        return checker.check_compliance(module_id, scope=scope)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/checker/checks")
def list_compliance_checks(module_id: Optional[str] = None,
                           policy_id: Optional[str] = None,
                           status: Optional[str] = None,
                           limit: int = 100):
    """List compliance checks with optional filters."""
    return {"checks": _get_compliance_checker().list_checks(
        module_id=module_id, policy_id=policy_id,
        status=status, limit=limit,
    )}


@router.get("/checker/checks/{check_id}")
def get_compliance_check(check_id: str):
    """Get a single compliance check by ID."""
    result = _get_compliance_checker().get_check(check_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Check {check_id} not found")
    return result


# ---------------------------------------------------------------------------
# Risk Scorer -- lazy accessor
# ---------------------------------------------------------------------------

_risk_scorer = None


def _get_risk_scorer():
    global _risk_scorer
    if _risk_scorer is not None:
        return _risk_scorer
    from sylion.governance.risk_scorer import get_risk_scorer
    _risk_scorer = get_risk_scorer()
    return _risk_scorer


# ---------------------------------------------------------------------------
# Risk Scorer -- request models
# ---------------------------------------------------------------------------

class ComputeRiskRequest(BaseModel):
    module_id: str
    risk_type: str
    factors: dict = {}


class SetThresholdRequest(BaseModel):
    risk_type: str
    level: str
    min_score: float
    max_score: float
    action: str = ""


# ---------------------------------------------------------------------------
# Risk Scorer -- endpoints
# (static routes before parameterized /{module_id} routes)
# ---------------------------------------------------------------------------

@router.post("/risk/compute")
def compute_risk(body: ComputeRiskRequest):
    """Compute and persist a composite risk score."""
    scorer = _get_risk_scorer()
    try:
        return scorer.compute_risk(
            body.module_id, body.risk_type, body.factors,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/risk/scores")
def list_risk_scores(module_id: Optional[str] = None,
                     risk_type: Optional[str] = None,
                     limit: int = 100):
    """List risk scores with optional filters."""
    scorer = _get_risk_scorer()
    return {"scores": scorer.list_scores(module_id=module_id,
                                          risk_type=risk_type,
                                          limit=limit)}


@router.get("/risk/scores/latest/{module_id}")
def get_latest_risk_score(module_id: str, risk_type: str = "security"):
    """Get the most recent risk score for a module / risk_type pair."""
    scorer = _get_risk_scorer()
    result = scorer.get_latest_score(module_id, risk_type)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"No score found for {module_id}/{risk_type}")
    return result


@router.get("/risk/thresholds")
def list_risk_thresholds(risk_type: Optional[str] = None):
    """List configured risk thresholds."""
    scorer = _get_risk_scorer()
    return {"thresholds": scorer.list_thresholds(risk_type=risk_type)}


@router.post("/risk/thresholds")
def set_risk_threshold(body: SetThresholdRequest):
    """Configure a risk threshold level."""
    scorer = _get_risk_scorer()
    try:
        return scorer.set_threshold(
            body.risk_type, body.level,
            body.min_score, body.max_score, body.action,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/risk/level")
def get_risk_level(risk_type: str, score: float):
    """Determine risk level for a given score."""
    scorer = _get_risk_scorer()
    return scorer.get_risk_level(risk_type, score)


@router.get("/risk/stats")
def risk_scorer_stats():
    """Get aggregate risk scorer statistics."""
    return _get_risk_scorer().get_stats()


# ---------------------------------------------------------------------------
# Change Proposal -- lazy accessor
# ---------------------------------------------------------------------------

_change_proposal = None


def _get_change_proposal():
    global _change_proposal
    if _change_proposal is not None:
        return _change_proposal
    from sylion.governance.change_proposal import get_change_proposal_manager
    _change_proposal = get_change_proposal_manager()
    return _change_proposal


# ---------------------------------------------------------------------------
# Change Proposal -- request models
# ---------------------------------------------------------------------------

class CreateChangeProposalRequest(BaseModel):
    title: str
    change_type: str
    module_id: str
    description: str = ""
    proposer: str = ""
    priority: str = "medium"


class UpdateChangeProposalRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None


class AddReviewRequest(BaseModel):
    reviewer: str
    verdict: str
    comment: str = ""


# ---------------------------------------------------------------------------
# Change Proposal -- endpoints
# (static routes before parameterized /{proposal_id} routes)
# ---------------------------------------------------------------------------

@router.post("/cp/proposals", status_code=201)
def create_change_proposal(body: CreateChangeProposalRequest):
    """Create a new change proposal (RFC) in draft status."""
    mgr = _get_change_proposal()
    try:
        return mgr.create_proposal(
            title=body.title,
            change_type=body.change_type,
            module_id=body.module_id,
            description=body.description,
            proposer=body.proposer,
            priority=body.priority,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cp/proposals")
def list_change_proposals(status: Optional[str] = None,
                          module_id: Optional[str] = None,
                          change_type: Optional[str] = None,
                          limit: int = 100):
    """List change proposals with optional filters."""
    mgr = _get_change_proposal()
    return {"proposals": mgr.list_proposals(
        status=status, module_id=module_id,
        change_type=change_type, limit=limit,
    )}


@router.get("/cp/proposals/stats")
def change_proposal_stats():
    """Get change proposal statistics."""
    return _get_change_proposal().get_stats()


@router.get("/cp/proposals/{proposal_id}")
def get_change_proposal(proposal_id: str):
    """Get a single change proposal by ID."""
    mgr = _get_change_proposal()
    result = mgr.get_proposal(proposal_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Change proposal {proposal_id} not found")
    return result


@router.put("/cp/proposals/{proposal_id}")
def update_change_proposal(proposal_id: str, body: UpdateChangeProposalRequest):
    """Update a change proposal's status and/or priority."""
    mgr = _get_change_proposal()
    try:
        result = mgr.update_proposal(
            proposal_id, status=body.status, priority=body.priority,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Change proposal {proposal_id} not found")
    return result


@router.post("/cp/proposals/{proposal_id}/reviews", status_code=201)
def add_change_proposal_review(proposal_id: str, body: AddReviewRequest):
    """Add a review verdict to a change proposal."""
    mgr = _get_change_proposal()
    try:
        return mgr.add_review(
            proposal_id, body.reviewer, body.verdict, body.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cp/proposals/{proposal_id}/reviews")
def list_change_proposal_reviews(proposal_id: str):
    """List all reviews for a change proposal."""
    mgr = _get_change_proposal()
    return {"reviews": mgr.list_reviews(proposal_id)}


# ===========================================================================
# Unified Governance Tickets (Wave A1, 2026-04-24)
# Single canonical decision/HG ticket plane covering:
#   workspace | global | funding | mobile | skill | council
# Replaces split between workspace humangate sessions, global gates/human/requests
# and funding-local approvals.
# ===========================================================================

from sylion.governance.tickets import (  # noqa: E402  (intentional bottom-of-file)
    GovernanceTicket,
    VALID_DECISION_CLASSES,
    VALID_GATE_TYPES,
    VALID_ORIGINS,
    VALID_PRIORITIES,
    fetch_by_id as _ticket_fetch_by_id,
    fetch_pending as _ticket_fetch_pending,
    get_ticket_store,
    resolve as _ticket_resolve,
    stats as _ticket_stats,
    withdraw as _ticket_withdraw,
)


class TicketSubmitRequest(BaseModel):
    origin: str = "global"
    project_id: Optional[str] = None
    decision_class: str = "D2"
    gate_type: str = "blocking"
    priority: str = "P2"
    title: str = ""
    summary: str = ""
    payload: dict = {}
    requested_by: str = ""
    audit_chain_ref: Optional[str] = None


class TicketResolveRequest(BaseModel):
    decision: str  # approved | rejected | expired
    reason: Optional[str] = None
    reviewer: str = ""


class TicketWithdrawRequest(BaseModel):
    reason: str = ""
    actor: str = ""


def _sync_legacy_human_gate_ticket(ticket: GovernanceTicket | None, body: TicketResolveRequest) -> None:
    """Mirror unified HumanGate ticket decisions back to legacy owners.

    The dashboard resolves `/governance/tickets/{id}/resolve`, while idea
    intake still stores its lifecycle lock in IdeaVault and legacy HumanGate.
    Without this bridge the visible ticket disappears but the idea remains
    stuck in `awaiting_approval`.
    """
    if ticket is None:
        return
    payload = ticket.payload if isinstance(ticket.payload, dict) else {}
    legacy_gate_id = str(payload.get("legacy_gate_id") or "")
    if not legacy_gate_id:
        return
    reviewer = body.reviewer or "operator-console"
    reason = body.reason or f"unified governance ticket {body.decision}"
    if body.decision in {"approved", "rejected"}:
        try:
            from sylion.governance.human_gate import get_human_gate

            get_human_gate().submit_review(
                ticket.ticket_id,
                reviewer=reviewer,
                decision=body.decision,
                rationale=reason,
            )
        except Exception:
            pass
    if not legacy_gate_id.startswith("idea:"):
        return
    if body.decision not in {"approved", "rejected"}:
        return
    idea_id = legacy_gate_id.split(":", 1)[1].strip()
    if not idea_id:
        return
    try:
        from sylion.cognitive.idea_vault import get_idea_vault

        get_idea_vault().record_human_gate_decision(
            idea_id,
            body.decision,
            reviewer=reviewer,
            rationale=reason,
        )
    except Exception:
        pass


def _append_human_gate_audit_chain(ticket: GovernanceTicket | None, body: TicketResolveRequest) -> None:
    """Write D3+ HumanGate decisions to the active audit hash chain.

    Lifecycle events are useful for UI feeds, but V10 requires a canonical
    tamper-evident audit-chain row for operator decisions. This helper is
    intentionally best-effort so ticket resolution itself stays available if
    the audit profile is not active.
    """
    if ticket is None:
        return
    try:
        from sylion.aeis_v2.audit_chain import append_to_chain
        from sylion.aeis_v2.audit_profile import get_audit_profile_id, resolve_audit_chain_path

        append_to_chain(resolve_audit_chain_path("advisor_audit.jsonl"), {
            "kind": "human_gate.ticket_resolved",
            "audit_id": get_audit_profile_id(),
            "ticket_id": ticket.ticket_id,
            "origin": ticket.origin,
            "project_id": ticket.project_id,
            "decision_class": ticket.decision_class,
            "gate_type": ticket.gate_type,
            "priority": ticket.priority,
            "title": ticket.title,
            "decision": body.decision,
            "reason": body.reason or "",
            "reviewer": body.reviewer or "operator-console",
            "payload": ticket.payload if isinstance(ticket.payload, dict) else {},
        })
    except Exception:
        pass


def _validate_enum(field: str, value: str, allowed: frozenset[str]) -> None:
    if value not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"invalid {field} '{value}', allowed: {sorted(allowed)}",
        )


@router.post("/tickets", status_code=201)
def submit_governance_ticket(body: TicketSubmitRequest):
    """Submit a unified governance ticket.

    Hook v1.0 (2026-04-24).
    """
    _validate_enum("origin", body.origin, VALID_ORIGINS)
    _validate_enum("decision_class", body.decision_class, VALID_DECISION_CLASSES)
    _validate_enum("gate_type", body.gate_type, VALID_GATE_TYPES)
    _validate_enum("priority", body.priority, VALID_PRIORITIES)

    ticket = GovernanceTicket(
        origin=body.origin,
        project_id=body.project_id,
        decision_class=body.decision_class,
        gate_type=body.gate_type,
        priority=body.priority,
        title=body.title,
        summary=body.summary,
        payload=body.payload or {},
        requested_by=body.requested_by,
        audit_chain_ref=body.audit_chain_ref,
    )
    ticket_id = get_ticket_store().submit(ticket)
    out = ticket.to_dict()
    out["ticket_id"] = ticket_id
    publish_lifecycle_event(
        "aeis.human_gate.ticket_pending",
        {
            "ticket_id": ticket_id,
            "operator_id": body.requested_by or "",
            "d_level": body.decision_class,
            "source": body.origin,
            "source_card_id": body.payload.get("source_card_id"),
            "pending_count_user": 1,
        },
        source_module="sylion.api.governance_routes",
        primary_key=ticket_id,
    )
    return out


@router.get("/tickets/pending")
def list_pending_tickets(
    operator_id: Optional[str] = None,
    origin: Optional[str] = None,
    project_id: Optional[str] = None,
    priority: Optional[str] = None,
):
    """List pending tickets across all origins."""
    if origin and origin not in VALID_ORIGINS:
        raise HTTPException(status_code=422, detail=f"invalid origin '{origin}'")
    if priority and priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"invalid priority '{priority}'")
    tickets = _ticket_fetch_pending(
        operator_id=operator_id, origin=origin,
        project_id=project_id, priority=priority,
    )
    return {"tickets": [t.to_dict() for t in tickets], "count": len(tickets)}


@router.get("/tickets/stats")
def get_ticket_stats():
    """Aggregate ticket counts (total, by_state, by_origin, by_priority)."""
    return _ticket_stats()


@router.get("/tickets/{ticket_id}")
def get_governance_ticket(ticket_id: str):
    """Fetch one ticket by id (404 if missing)."""
    ticket = _ticket_fetch_by_id(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"ticket {ticket_id} not found")
    return ticket.to_dict()


@router.get("/tickets/{ticket_id}/events")
def get_governance_ticket_events(ticket_id: str):
    """Append-only event log for a ticket (created/resolved/withdrawn/escalated)."""
    ticket = _ticket_fetch_by_id(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"ticket {ticket_id} not found")
    return {"events": get_ticket_store().events(ticket_id)}


@router.post("/tickets/{ticket_id}/resolve")
def resolve_governance_ticket(ticket_id: str, body: TicketResolveRequest):
    """Resolve a pending ticket."""
    if body.decision not in {"approved", "rejected", "expired"}:
        raise HTTPException(status_code=422,
                            detail="decision must be approved|rejected|expired")
    ticket_before = _ticket_fetch_by_id(ticket_id)
    if (
        ticket_before is not None
        and ticket_before.decision_class in {"D3", "D4", "D5"}
        and body.decision in {"approved", "rejected"}
        and not str(body.reason or "").strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="reason is required for D3+ governance ticket resolution",
        )
    changed = _ticket_resolve(
        ticket_id, body.decision, reason=body.reason, reviewer=body.reviewer,
    )
    if not changed:
        raise HTTPException(status_code=409,
                            detail=f"ticket {ticket_id} missing or already final")
    _sync_legacy_human_gate_ticket(ticket_before, body)
    _append_human_gate_audit_chain(ticket_before, body)
    ticket = _ticket_fetch_by_id(ticket_id)
    return ticket.to_dict() if ticket else {"ticket_id": ticket_id, "state": body.decision}


@router.post("/tickets/{ticket_id}/withdraw")
def withdraw_governance_ticket(ticket_id: str, body: TicketWithdrawRequest):
    """Withdraw a pending ticket (creator-side cancel)."""
    changed = _ticket_withdraw(ticket_id, reason=body.reason, actor=body.actor)
    if not changed:
        raise HTTPException(status_code=409,
                            detail=f"ticket {ticket_id} missing or already final")
    ticket = _ticket_fetch_by_id(ticket_id)
    return ticket.to_dict() if ticket else {"ticket_id": ticket_id, "state": "withdrawn"}


@router.get("/tickets")
def list_governance_tickets(
    state: Optional[str] = None,
    origin: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 200,
):
    """List tickets with optional state/origin/project filter."""
    states = [state] if state else None
    if origin and origin not in VALID_ORIGINS:
        raise HTTPException(status_code=422, detail=f"invalid origin '{origin}'")
    tickets = get_ticket_store().list(
        states=states, origin=origin, project_id=project_id,
        limit=max(1, min(int(limit), 1000)),
    )
    return {"tickets": [t.to_dict() for t in tickets], "count": len(tickets)}
