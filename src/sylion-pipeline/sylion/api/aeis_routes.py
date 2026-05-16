"""
SYLION API -- AEIS routes.

Endpoints for: improvement_queue, self_explanation, self_limitation,
autonomy_controller, integration_controller, evidence_pack.
"""

from fastapi import APIRouter, HTTPException

from sylion.aeis.improvement_queue import get_improvement_queue
from sylion.aeis.self_explanation import get_self_explanation_engine
from sylion.aeis.self_limitation import get_self_limitation_engine

try:
    from sylion.aeis.self_evolution import get_self_evolution
    from sylion.aeis.adaptation_engine import get_adaptation_engine
    _HAS_EVOLUTION = True
except ImportError:
    _HAS_EVOLUTION = False

# Lazy imports -- module may not exist yet
try:
    from sylion.aeis.autonomy_controller import (
        AutonomyAction, AutonomyStage, get_autonomy_controller,
    )
    _HAS_AUTONOMY = True
except ImportError:
    _HAS_AUTONOMY = False

try:
    from sylion.aeis.integration_controller import get_integration_controller
    _HAS_INTEGRATION = True
except ImportError:
    _HAS_INTEGRATION = False

try:
    from sylion.aeis.evidence_pack import get_evidence_pack_collector
    _HAS_EVIDENCE_PACK = True
except ImportError:
    _HAS_EVIDENCE_PACK = False

router = APIRouter(prefix="/api/v1/aeis", tags=["aeis"])


@router.get("/health")
def health() -> dict[str, object]:
    import time

    return {
        "status": "ok",
        "module": "aeis",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Improvement Queue
# ---------------------------------------------------------------------------

@router.post("/improvements", status_code=201)
def submit_improvement(title: str, description: str = "",
                       category: str = "performance", priority: int = 0,
                       source: str = "", evidence: str = "{}"):
    """Submit a new improvement proposal."""
    import json
    q = get_improvement_queue()
    return q.submit(
        title, description=description, category=category,
        priority=priority, source=source,
        evidence=json.loads(evidence) if isinstance(evidence, str) else None,
    )


@router.get("/improvements")
def list_improvements(status: str | None = None,
                      category: str | None = None,
                      limit: int = 100):
    """List improvement proposals."""
    q = get_improvement_queue()
    return {"improvements": q.list_improvements(status=status,
                                                category=category,
                                                limit=limit)}


@router.get("/improvements/next")
def get_next_improvement():
    """Get the next improvement to work on."""
    q = get_improvement_queue()
    result = q.get_next()
    if not result:
        return {"improvement": None, "message": "No queued improvements"}
    return result


@router.post("/improvements/{improvement_id}/start")
def start_improvement(improvement_id: str):
    """Mark an improvement as in-progress."""
    q = get_improvement_queue()
    return q.start(improvement_id)


@router.post("/improvements/{improvement_id}/complete")
def complete_improvement(improvement_id: str, result: str = ""):
    """Mark an improvement as completed."""
    q = get_improvement_queue()
    return q.complete(improvement_id, result=result)


@router.post("/improvements/{improvement_id}/reject")
def reject_improvement(improvement_id: str, reason: str = ""):
    """Reject an improvement proposal."""
    q = get_improvement_queue()
    return q.reject(improvement_id, reason=reason)


@router.get("/improvements/stats")
def improvement_stats():
    """Get improvement queue statistics."""
    q = get_improvement_queue()
    return q.get_stats()


# ---------------------------------------------------------------------------
# Autonomy Controller
# ---------------------------------------------------------------------------

@router.get("/autonomy/stages")
def list_autonomy_stages():
    """List all autonomy stages with descriptions."""
    if not _HAS_AUTONOMY:
        stages = [
            {"stage": "observe", "level": 1,
             "description": "AEIS can READ system state, CANNOT modify anything"},
            {"stage": "propose", "level": 2,
             "description": "AEIS can propose changes, needs D2+ approval"},
            {"stage": "sandbox", "level": 3,
             "description": "AEIS executes in sandbox environment"},
            {"stage": "limited", "level": 4,
             "description": "Limited production with guardrails"},
            {"stage": "full", "level": 5,
             "description": "Full autonomy under Canon"},
        ]
        return {"stages": stages}
    return {"stages": [
        {"stage": s.value, "level": i + 1, "description": s.__doc__.strip()}
        for i, s in enumerate(AutonomyStage)
    ]}


@router.get("/autonomy/status")
def get_autonomy_status():
    """Get current autonomy stage and gate requirements."""
    if not _HAS_AUTONOMY:
        return {
            "current_stage": "observe",
            "stage_entered_at": 0.0,
            "available": False,
            "message": "autonomy_controller module not available",
        }
    ctrl = get_autonomy_controller()
    return ctrl.get_stats()


@router.post("/autonomy/advance")
def advance_autonomy_stage(
    observation_24h_clean: bool = False,
    observation_error_count: int = -1,
    explanation_accuracy: float = 0.0,
    boundaries_mapped: bool = False,
    improvement_proposals_count: int = 0,
    all_proposals_reviewed: bool = False,
    sandbox_executions_count: int = 0,
    sandbox_side_effects: int = -1,
    council_approved: bool = False,
    external_reviewed: bool = False,
    limited_prod_days_clean: int = 0,
):
    """Attempt to advance to the next autonomy stage."""
    if not _HAS_AUTONOMY:
        raise HTTPException(status_code=501,
                            detail="autonomy_controller module not available")
    ctrl = get_autonomy_controller()
    requirements = {
        "observation_24h_clean": observation_24h_clean,
        "observation_error_count": observation_error_count,
        "explanation_accuracy": explanation_accuracy,
        "boundaries_mapped": boundaries_mapped,
        "improvement_proposals_count": improvement_proposals_count,
        "all_proposals_reviewed": all_proposals_reviewed,
        "sandbox_executions_count": sandbox_executions_count,
        "sandbox_side_effects": sandbox_side_effects,
        "council_approved": council_approved,
        "external_reviewed": external_reviewed,
        "limited_prod_days_clean": limited_prod_days_clean,
    }
    return ctrl.advance_stage(requirements)


@router.get("/autonomy/actions")
def list_autonomy_actions(action: str | None = None, limit: int = 100):
    """Get autonomy action history."""
    if not _HAS_AUTONOMY:
        return {"actions": [], "message": "autonomy_controller module not available"}
    ctrl = get_autonomy_controller()
    return {"actions": ctrl.get_action_history(action=action, limit=limit)}


# ---------------------------------------------------------------------------
# Self-Explanation Engine
# ---------------------------------------------------------------------------

@router.post("/explanations", status_code=201)
def generate_explanation(decision_id: str, question: str,
                         explanation: str = "",
                         reasoning_steps: str = "[]",
                         confidence: float = 0.0):
    """Generate a self-explanation for a decision."""
    import json
    engine = get_self_explanation_engine()
    return engine.generate(
        decision_id, question, explanation=explanation,
        reasoning_steps=json.loads(reasoning_steps) if isinstance(reasoning_steps, str) else None,
        confidence=confidence,
    )


@router.get("/explanations")
def list_explanations(validated: int | None = None, limit: int = 100):
    """List explanations."""
    engine = get_self_explanation_engine()
    return {"explanations": engine.list_explanations(validated=validated,
                                                     limit=limit)}


@router.get("/explanations/{explanation_id}")
def get_explanation(explanation_id: str):
    """Get a single explanation by ID."""
    engine = get_self_explanation_engine()
    result = engine.get_explanation(explanation_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Explanation {explanation_id} not found")
    return result


@router.post("/explanations/{explanation_id}/validate")
def validate_explanation(explanation_id: str, validator: str,
                         verdict: str, feedback: str = ""):
    """Validate an explanation."""
    engine = get_self_explanation_engine()
    return engine.validate(explanation_id, validator, verdict, feedback=feedback)


@router.get("/explanations/stats")
def explanation_stats():
    """Get self-explanation statistics."""
    engine = get_self_explanation_engine()
    return engine.get_stats()


# ---------------------------------------------------------------------------
# Self-Limitation Engine
# ---------------------------------------------------------------------------

@router.post("/limitations/policies", status_code=201)
def register_limitation_policy(policy_id: str, name: str,
                               description: str = "",
                               category: str = "safety",
                               threshold: float = 0.0, unit: str = ""):
    """Register a new self-limitation policy."""
    engine = get_self_limitation_engine()
    return engine.register_policy(policy_id, name, description=description,
                                  category=category, threshold=threshold,
                                  unit=unit)


@router.get("/limitations/policies")
def list_limitation_policies(category: str | None = None,
                             enabled_only: bool = True):
    """List self-limitation policies."""
    engine = get_self_limitation_engine()
    return {"policies": engine.list_policies(category=category,
                                             enabled_only=enabled_only)}


@router.get("/limitations/policies/{policy_id}")
def get_limitation_policy(policy_id: str):
    """Get a self-limitation policy by ID."""
    engine = get_self_limitation_engine()
    result = engine.get_policy(policy_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Policy {policy_id} not found")
    return result


@router.post("/limitations/check")
def check_limitation(policy_id: str, value: float):
    """Check a value against a limitation policy."""
    engine = get_self_limitation_engine()
    result = engine.check(policy_id, value)
    return {"policy_id": policy_id, "value": value, "result": result}


@router.post("/limitations/violations", status_code=201)
def record_limitation_violation(policy_id: str, value: float,
                                severity: str = "warning",
                                details: str = "{}"):
    """Record a limitation violation."""
    import json
    engine = get_self_limitation_engine()
    return engine.record_violation(
        policy_id, value, severity=severity,
        details=json.loads(details) if isinstance(details, str) else None,
    )


@router.get("/limitations/violations")
def list_limitation_violations(policy_id: str | None = None,
                               limit: int = 100):
    """List limitation violations."""
    engine = get_self_limitation_engine()
    return {"violations": engine.get_violations(policy_id=policy_id,
                                                limit=limit)}


@router.get("/limitations/stats")
def limitation_stats():
    """Get self-limitation statistics."""
    engine = get_self_limitation_engine()
    return engine.get_stats()


# ---------------------------------------------------------------------------
# Rate Limitation (Self-Limitation -- rate policies & usage)
# ---------------------------------------------------------------------------

@router.get("/limitation/policies")
def rate_policies(scope: str | None = None):
    """List rate-limitation policies."""
    engine = get_self_limitation_engine()
    # Self-limitation engine exposes rate policies via internal DB
    # Return all rate policies
    try:
        policies = engine.list_rate_policies(scope=scope)
    except AttributeError:
        # Fallback: query raw from internal connection
        conn = engine._conn
        if scope:
            rows = conn.execute(
                "SELECT * FROM sylion_rate_policies WHERE scope = ?",
                (scope,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sylion_rate_policies"
            ).fetchall()
        policies = [dict(r) for r in rows]
    return {"policies": policies}


@router.get("/limitation/usage")
def rate_usage(scope: str = "", identifier: str = "",
               window_seconds: float = 3600.0):
    """Get current rate-limit usage for a scope/identifier."""
    engine = get_self_limitation_engine()
    if not scope or not identifier:
        return {"usage": 0, "scope": scope, "identifier": identifier}
    usage = engine.get_usage(scope, identifier, window_seconds)
    return {"usage": usage, "scope": scope, "identifier": identifier,
            "window_seconds": window_seconds}


# ---------------------------------------------------------------------------
# Self-Evolution Engine
# ---------------------------------------------------------------------------

@router.post("/evolution/propose", status_code=201)
def propose_evolution(target_module: str, mutation_type: str,
                      description: str = "", rationale: str = "",
                      expected_fitness_delta: float = 0.0,
                      risk_level: str = "low", rollback_plan: str = "",
                      metadata: str = "{}"):
    """Submit an evolution proposal."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Evolution module not available")
    import json
    evo = get_self_evolution()
    return evo.propose(
        target_module, mutation_type, description=description,
        rationale=rationale, expected_fitness_delta=expected_fitness_delta,
        risk_level=risk_level, rollback_plan=rollback_plan,
        metadata=json.loads(metadata) if isinstance(metadata, str) else None,
    )


@router.get("/evolution/proposals")
def list_evolution_proposals(target_module: str | None = None,
                             state: str | None = None,
                             mutation_type: str | None = None,
                             limit: int = 100):
    """List evolution proposals."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Evolution module not available")
    evo = get_self_evolution()
    return {"proposals": evo.list_proposals(target_module=target_module,
                                            state=state,
                                            mutation_type=mutation_type,
                                            limit=limit)}


@router.get("/evolution/proposals/{proposal_id}")
def get_evolution_proposal(proposal_id: str):
    """Get an evolution proposal."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Evolution module not available")
    evo = get_self_evolution()
    result = evo.get(proposal_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Proposal {proposal_id} not found")
    return result


@router.post("/evolution/proposals/{proposal_id}/transition")
def transition_evolution(proposal_id: str, new_state: str, reason: str = ""):
    """Transition an evolution proposal to a new state."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Evolution module not available")
    evo = get_self_evolution()
    return evo.transition(proposal_id, new_state, reason=reason)


@router.post("/evolution/proposals/{proposal_id}/fitness")
def record_evolution_fitness(proposal_id: str, fitness_before: float,
                             fitness_after: float):
    """Record fitness measurements for a proposal."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Evolution module not available")
    evo = get_self_evolution()
    return evo.record_fitness(proposal_id, fitness_before, fitness_after)


@router.get("/evolution/proposals/{proposal_id}/events")
def get_evolution_events(proposal_id: str):
    """Get event history for a proposal."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Evolution module not available")
    evo = get_self_evolution()
    return {"events": evo.get_events(proposal_id)}


@router.get("/evolution/stats")
def evolution_stats():
    """Get evolution engine statistics."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Evolution module not available")
    evo = get_self_evolution()
    return evo.get_stats()


# ---------------------------------------------------------------------------
# Adaptation Engine
# ---------------------------------------------------------------------------

@router.post("/adaptation/feedback", status_code=201)
def ingest_feedback(source: str, metric: str, value: float,
                    threshold: float = 0.0, severity: str = "info",
                    message: str = ""):
    """Ingest a feedback signal."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Adaptation module not available")
    engine = get_adaptation_engine()
    return engine.ingest_feedback(source, metric, value, threshold=threshold,
                                  severity=severity, message=message)


@router.get("/adaptation/feedback")
def list_feedback(metric: str | None = None, limit: int = 100):
    """List feedback signals."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Adaptation module not available")
    engine = get_adaptation_engine()
    return {"signals": engine.get_feedback(metric=metric, limit=limit)}


@router.get("/adaptation/adaptations")
def list_adaptations(adaptation_type: str | None = None,
                     state: str | None = None, limit: int = 100):
    """List adaptations."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Adaptation module not available")
    engine = get_adaptation_engine()
    return {"adaptations": engine.list_adaptations(adaptation_type=adaptation_type,
                                                    state=state, limit=limit)}


@router.get("/adaptation/adaptations/{adaptation_id}")
def get_adaptation(adaptation_id: str):
    """Get an adaptation by ID."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Adaptation module not available")
    engine = get_adaptation_engine()
    result = engine.get(adaptation_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Adaptation {adaptation_id} not found")
    return result


@router.post("/adaptation/adaptations/{adaptation_id}/apply")
def apply_adaptation(adaptation_id: str, outcome: str = ""):
    """Apply an adaptation."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Adaptation module not available")
    engine = get_adaptation_engine()
    return engine.apply(adaptation_id, outcome=outcome)


@router.post("/adaptation/adaptations/{adaptation_id}/complete")
def complete_adaptation(adaptation_id: str, outcome: str = ""):
    """Complete an adaptation."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Adaptation module not available")
    engine = get_adaptation_engine()
    return engine.complete(adaptation_id, outcome=outcome)


@router.post("/adaptation/rules", status_code=201)
def add_adaptation_rule(name: str, trigger_metric: str,
                        condition_op: str = ">", threshold: float = 0.0,
                        adaptation_type: str = "threshold_adjust",
                        strategy: str = "", priority: int = 0):
    """Add an adaptation rule."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Adaptation module not available")
    engine = get_adaptation_engine()
    return engine.add_rule(name, trigger_metric, condition_op=condition_op,
                           threshold=threshold, adaptation_type=adaptation_type,
                           strategy=strategy, priority=priority)


@router.get("/adaptation/rules")
def list_adaptation_rules(enabled_only: bool = False):
    """List adaptation rules."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Adaptation module not available")
    engine = get_adaptation_engine()
    return {"rules": engine.list_rules(enabled_only=enabled_only)}


@router.get("/adaptation/stats")
def adaptation_stats():
    """Get adaptation engine statistics."""
    if not _HAS_EVOLUTION:
        raise HTTPException(status_code=501, detail="Adaptation module not available")
    engine = get_adaptation_engine()
    return engine.get_stats()


# ---------------------------------------------------------------------------
# Integration Controller (Phase 4)
# ---------------------------------------------------------------------------

@router.get("/integration/stage")
def get_integration_stage():
    """Get the current AEIS integration stage."""
    if not _HAS_INTEGRATION:
        raise HTTPException(status_code=501,
                            detail="integration_controller module not available")
    ctrl = get_integration_controller()
    return ctrl.get_current_stage()


@router.post("/integration/advance")
def advance_integration_stage():
    """Advance to the next AEIS integration stage."""
    if not _HAS_INTEGRATION:
        raise HTTPException(status_code=501,
                            detail="integration_controller module not available")
    ctrl = get_integration_controller()
    return ctrl.advance_stage()


@router.post("/integration/downgrade")
def emergency_integration_downgrade(reason: str):
    """Emergency downgrade AEIS integration back to observe."""
    if not _HAS_INTEGRATION:
        raise HTTPException(status_code=501,
                            detail="integration_controller module not available")
    ctrl = get_integration_controller()
    return ctrl.emergency_downgrade(reason)


@router.get("/integration/history")
def get_integration_history(limit: int = 100):
    """Get AEIS integration stage transition history."""
    if not _HAS_INTEGRATION:
        raise HTTPException(status_code=501,
                            detail="integration_controller module not available")
    ctrl = get_integration_controller()
    return {"history": ctrl.get_stage_history(limit=limit)}


@router.get("/integration/stats")
def integration_stats():
    """Get integration controller statistics."""
    if not _HAS_INTEGRATION:
        raise HTTPException(status_code=501,
                            detail="integration_controller module not available")
    ctrl = get_integration_controller()
    return ctrl.get_stats()


# ---------------------------------------------------------------------------
# Evidence Pack Collector (Phase 4)
# ---------------------------------------------------------------------------

@router.post("/evidence/packs", status_code=201)
def create_evidence_pack(decision_class: str, context: str = "{}"):
    """Create a new evidence pack for a decision class."""
    if not _HAS_EVIDENCE_PACK:
        raise HTTPException(status_code=501,
                            detail="evidence_pack module not available")
    import json
    collector = get_evidence_pack_collector()
    return collector.create_pack(
        decision_class,
        context=json.loads(context) if isinstance(context, str) else None,
    )


@router.get("/evidence/packs")
def list_evidence_packs(decision_class: str | None = None,
                        limit: int = 100):
    """List evidence packs."""
    if not _HAS_EVIDENCE_PACK:
        raise HTTPException(status_code=501,
                            detail="evidence_pack module not available")
    collector = get_evidence_pack_collector()
    return {"packs": collector.list_packs(decision_class=decision_class,
                                          limit=limit)}


@router.get("/evidence/packs/{pack_id}")
def get_evidence_pack(pack_id: str):
    """Get a full evidence pack with all items."""
    if not _HAS_EVIDENCE_PACK:
        raise HTTPException(status_code=501,
                            detail="evidence_pack module not available")
    collector = get_evidence_pack_collector()
    result = collector.get_pack(pack_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Evidence pack {pack_id} not found")
    return result


@router.post("/evidence/packs/{pack_id}/items", status_code=201)
def add_evidence_item(pack_id: str, evidence_type: str,
                      data: str = "{}"):
    """Add an evidence item to a pack."""
    if not _HAS_EVIDENCE_PACK:
        raise HTTPException(status_code=501,
                            detail="evidence_pack module not available")
    import json
    collector = get_evidence_pack_collector()
    parsed = json.loads(data) if isinstance(data, str) else {}
    method_map = {
        "observation": collector.add_observation_evidence,
        "proposal": collector.add_proposal_evidence,
        "validation": collector.add_validation_evidence,
        "boundary": collector.add_boundary_evidence,
    }
    add_fn = method_map.get(evidence_type)
    if not add_fn:
        raise HTTPException(status_code=400,
                            detail=f"Invalid evidence_type: {evidence_type}")
    return add_fn(pack_id, parsed)


@router.post("/evidence/packs/{pack_id}/seal")
def seal_evidence_pack(pack_id: str):
    """Seal an evidence pack, making it immutable."""
    if not _HAS_EVIDENCE_PACK:
        raise HTTPException(status_code=501,
                            detail="evidence_pack module not available")
    collector = get_evidence_pack_collector()
    return collector.seal_pack(pack_id)


@router.post("/evidence/packs/{pack_id}/verify")
def verify_evidence_pack(pack_id: str):
    """Verify integrity of an evidence pack."""
    if not _HAS_EVIDENCE_PACK:
        raise HTTPException(status_code=501,
                            detail="evidence_pack module not available")
    collector = get_evidence_pack_collector()
    return collector.verify_pack_integrity(pack_id)


@router.get("/evidence/stats")
def evidence_pack_stats():
    """Get evidence pack collector statistics."""
    if not _HAS_EVIDENCE_PACK:
        raise HTTPException(status_code=501,
                            detail="evidence_pack module not available")
    collector = get_evidence_pack_collector()
    return collector.get_stats()
