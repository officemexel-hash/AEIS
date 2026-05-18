"""
SYLION API -- Core routes.

Endpoints for: module_registry, event_bus, evidence_spine,
decision_gate_engine, contract_registry, bundle_assembler.
"""

from fastapi import APIRouter, HTTPException

from sylion.core.module_registry import (
    ModuleManifest, ModuleKind, ModuleLifecycleStage, get_registry,
)
from sylion.core.event_bus import SylionEvent, get_event_bus
from sylion.core.evidence_spine import EvidenceEntry, get_evidence_spine
from sylion.core.decision_gate_engine import (
    DecisionRequest, DecisionClass, GateDefinition, get_decision_engine,
)
from sylion.core.contract_registry import get_contract_registry
from sylion.core.bundle_assembler import get_bundle_assembler

router = APIRouter(prefix="/api/v1/core", tags=["core"])


@router.get("/health")
def health() -> dict[str, object]:
    import time

    return {
        "status": "ok",
        "module": "core",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Module Registry
# ---------------------------------------------------------------------------

@router.get("/modules")
def list_modules(kind: str | None = None, milestone: str | None = None,
                 lifecycle: str | None = None):
    """List all registered modules with optional filters."""
    registry = get_registry()
    return {"modules": registry.list_modules(kind=kind, milestone=milestone,
                                             lifecycle=lifecycle)}


@router.post("/modules", status_code=201)
def register_module(module_id: str, module_kind: str, owner_plan: str,
                    description: str = "",
                    implementation_strategy: str = "greenfield",
                    contract_version: str = "1.0.0",
                    decision_class_entry: str = "D3",
                    depends_on: str = ""):
    """Register a new module in the system."""
    registry = get_registry()
    try:
        manifest = ModuleManifest(
            module_id=module_id,
            module_kind=ModuleKind(module_kind),
            owner_plan=owner_plan,
            description=description,
            implementation_strategy=implementation_strategy,
            contract_version=contract_version,
            decision_class_entry=decision_class_entry,
            depends_on=[d.strip() for d in depends_on.split(",") if d.strip()],
        )
        result = registry.register(manifest)
        return {"registered": result}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/modules/{module_id}")
def get_module(module_id: str):
    """Get a single module by ID."""
    registry = get_registry()
    mod = registry.get(module_id)
    if not mod:
        raise HTTPException(status_code=404, detail=f"Module {module_id} not found")
    return mod


@router.delete("/modules/{module_id}")
def deregister_module(module_id: str):
    """Deregister a module from the system."""
    registry = get_registry()
    try:
        removed = registry.deregister(module_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not removed:
        raise HTTPException(status_code=404, detail=f"Module {module_id} not found")
    return {"deregistered": module_id}


@router.post("/modules/{module_id}/transition")
def transition_module(module_id: str, target: str):
    """Transition a module to a new lifecycle stage."""
    registry = get_registry()
    try:
        result = registry.transition(module_id, ModuleLifecycleStage(target))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/modules/{module_id}/heartbeat")
def heartbeat_module(module_id: str):
    """Send a heartbeat for a module."""
    registry = get_registry()
    registry.heartbeat(module_id)
    return {"heartbeat": module_id}


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

@router.get("/events")
def list_events(topic: str | None = None, since: float | None = None,
                limit: int = 100):
    """Query events from the event bus."""
    bus = get_event_bus()
    return {"events": bus.query(topic=topic, since=since, limit=limit)}


@router.post("/events", status_code=201)
def publish_event(topic: str, payload: str = "{}",
                  source_module: str = ""):
    """Publish a new event to the event bus."""
    import json
    bus = get_event_bus()
    event = SylionEvent(
        event_id="", topic=topic,
        payload=json.loads(payload) if isinstance(payload, str) else {},
        source_module=source_module,
    )
    event_id = bus.publish(event)
    return {"event_id": event_id, "topic": topic}


@router.post("/events/{event_id}/ack")
def ack_event(event_id: str):
    """Acknowledge an event."""
    bus = get_event_bus()
    acked = bus.ack(event_id)
    if not acked:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return {"acked": event_id}


@router.get("/events/catalog")
def event_catalog():
    """Get event counts per topic."""
    bus = get_event_bus()
    return {"catalog": bus.get_catalog()}


@router.post("/events/replay")
def replay_events(since: float | None = None, topic: str | None = None):
    """Replay events to subscribers."""
    bus = get_event_bus()
    count = bus.replay(since=since, topic=topic)
    return {"replayed": count}


# ---------------------------------------------------------------------------
# Evidence Spine
# ---------------------------------------------------------------------------

@router.get("/evidence")
def query_evidence(source_plan: str | None = None,
                   event_type: str | None = None,
                   since: float | None = None,
                   limit: int = 100):
    """Query the immutable evidence spine."""
    spine = get_evidence_spine()
    return {"evidence": spine.query(source_plan=source_plan,
                                    event_type=event_type,
                                    since=since, limit=limit)}


@router.post("/evidence", status_code=201)
def append_evidence(source_plan: str, event_type: str,
                    payload: str = "{}", actor_id: str = ""):
    """Append a new entry to the evidence spine."""
    import json
    spine = get_evidence_spine()
    entry = EvidenceEntry(
        source_plan=source_plan,
        event_type=event_type,
        payload=json.loads(payload) if isinstance(payload, str) else {},
        actor_id=actor_id,
    )
    result = spine.append(entry)
    return result


@router.get("/evidence/verify")
def verify_evidence_chain():
    """Verify the integrity of the hash chain."""
    spine = get_evidence_spine()
    valid, message = spine.verify_chain()
    return {"valid": valid, "message": message}


@router.get("/evidence/replay")
def replay_evidence(since: float | None = None):
    """Replay evidence entries since a timestamp."""
    spine = get_evidence_spine()
    return {"evidence": spine.replay(since=since)}


@router.get("/evidence/artifacts")
def list_evidence_artifacts(source: str | None = None,
                            artifact_type: str | None = None,
                            limit: int = 100):
    """List registered evidence artifacts with checksums and retention policy."""
    spine = get_evidence_spine()
    return {"artifacts": spine.list_artifacts(source=source, artifact_type=artifact_type, limit=limit)}


@router.post("/evidence/artifacts/json", status_code=201)
def register_json_evidence_artifact(source: str,
                                    payload: str = "{}",
                                    artifact_type: str = "api_response",
                                    retention_policy: str = "default",
                                    metadata: str = "{}",
                                    actor_id: str = ""):
    """Register a JSON artifact in Evidence Spine and link it to the hash chain."""
    import json
    spine = get_evidence_spine()
    try:
        payload_json = json.loads(payload)
        metadata_json = json.loads(metadata)
        if not isinstance(payload_json, dict):
            raise ValueError("payload must be a JSON object")
        if not isinstance(metadata_json, dict):
            raise ValueError("metadata must be a JSON object")
        return spine.register_json_artifact(
            payload_json,
            source=source,
            artifact_type=artifact_type,
            retention_policy=retention_policy,
            metadata=metadata_json,
            actor_id=actor_id,
        )
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/evidence/artifacts/{evidence_id}")
def get_evidence_artifact(evidence_id: str):
    """Get one evidence artifact by evidence_id."""
    spine = get_evidence_spine()
    artifact = spine.get_artifact(evidence_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Evidence artifact {evidence_id} not found")
    return artifact


@router.get("/evidence/artifacts/{evidence_id}/verify")
def verify_evidence_artifact(evidence_id: str):
    """Verify an artifact checksum when the original file is still available."""
    spine = get_evidence_spine()
    result = spine.verify_artifact(evidence_id)
    if result.get("reason") == "not_found":
        raise HTTPException(status_code=404, detail=f"Evidence artifact {evidence_id} not found")
    return result


# ---------------------------------------------------------------------------
# Decision Gate Engine
# ---------------------------------------------------------------------------

@router.post("/decisions/classify", status_code=201)
def classify_decision(description: str, source_plan: str,
                      module_id: str = "",
                      change_type: str = "",
                      blast_radius: str = "low",
                      reversible: bool = True,
                      affects_contracts: bool = False,
                      affects_kernel: bool = False):
    """Classify a decision request to D0-D5."""
    engine = get_decision_engine()
    request = DecisionRequest(
        description=description,
        source_plan=source_plan,
        module_id=module_id,
        change_type=change_type,
        blast_radius=blast_radius,
        reversible=reversible,
        affects_contracts=affects_contracts,
        affects_kernel=affects_kernel,
    )
    record = engine.classify(request)
    return {
        "decision_id": record.decision_id,
        "decision_class": record.decision_class.value,
        "requirements": record.requirements,
        "status": record.status,
    }


@router.get("/decisions")
def list_decisions(decision_class: str | None = None,
                   source_plan: str | None = None):
    """List classified decisions."""
    engine = get_decision_engine()
    return {"decisions": engine.get_decisions(decision_class=decision_class,
                                               source_plan=source_plan)}


@router.post("/gates", status_code=201)
def register_gate(gate_id: str, name: str, description: str = "",
                  fail_condition: str = "", blocks: str = "",
                  decision_class_min: str = "D2"):
    """Register a new gate definition."""
    engine = get_decision_engine()
    gate = GateDefinition(
        gate_id=gate_id,
        name=name,
        description=description,
        fail_condition=fail_condition,
        blocks=blocks,
        decision_class_min=DecisionClass(decision_class_min),
    )
    return engine.register_gate(gate)


@router.post("/gates/{gate_id}/evaluate")
def evaluate_gate(gate_id: str, context: str = "{}"):
    """Evaluate a gate (pass/fail)."""
    import json
    engine = get_decision_engine()
    return engine.evaluate_gate(gate_id, json.loads(context) if isinstance(context, str) else {})


# ---------------------------------------------------------------------------
# Contract Registry
# ---------------------------------------------------------------------------

@router.post("/contracts", status_code=201)
def publish_contract(name: str, contract_type: str = "grpc_service",
                     version: str = "1.0.0", schema_def: str = "{}"):
    """Register a new contract."""
    reg = get_contract_registry()
    import json
    spec = json.loads(schema_def) if isinstance(schema_def, str) and schema_def else {}
    return reg.register_contract(name=name, version=version, spec_json=spec)


@router.get("/contracts")
def list_contracts(active_only: bool = False):
    """List contracts."""
    reg = get_contract_registry()
    return {"contracts": reg.list_contracts(active_only=active_only)}


@router.get("/contracts/{contract_id}")
def get_contract_by_id(contract_id: str):
    """Get a contract by ID."""
    reg = get_contract_registry()
    result = reg.get_contract(contract_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return result


# ---------------------------------------------------------------------------
# Bundle Assembler
# ---------------------------------------------------------------------------

@router.post("/bundles", status_code=201)
def assemble_bundle(module_ids: str, created_by: str = ""):
    """Assemble a bundle from a comma-separated list of module IDs."""
    asm = get_bundle_assembler()
    ids = [m.strip() for m in module_ids.split(",") if m.strip()]
    try:
        bundle = asm.assemble(ids, created_by=created_by)
        bundle_id = bundle.get("bundle_id") if isinstance(bundle, dict) else bundle.bundle_id
        modules = bundle.get("modules") if isinstance(bundle, dict) else bundle.modules
        state = bundle.get("state") if isinstance(bundle, dict) else bundle.state.value
        return {
            "bundle_id": bundle_id,
            "modules": modules,
            "state": state,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bundles/{bundle_id}/validate")
def validate_bundle(bundle_id: str):
    """Validate a bundle (check all modules at VALIDATE+ stage)."""
    asm = get_bundle_assembler()
    try:
        return asm.validate(bundle_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/bundles/{bundle_id}/ship")
def ship_bundle(bundle_id: str):
    """Ship a validated bundle."""
    asm = get_bundle_assembler()
    try:
        return asm.ship(bundle_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Version Manager
# ---------------------------------------------------------------------------

from sylion.core.version_manager import get_version_manager as _get_vm


@router.post("/versions", status_code=201)
def register_version(module_id: str, version: str,
                     changelog: str = "", compatibility: str = ""):
    """Register a module version."""
    import json as _json
    vm = _get_vm()
    comp = _json.loads(compatibility) if compatibility else None
    return vm.register_version(module_id, version,
                               changelog=changelog or None,
                               compatibility=comp)


@router.get("/versions/stats")
def version_stats():
    """Get version manager statistics."""
    return _get_vm().get_version_stats()


@router.get("/versions/history")
def version_history(module_id: str = None, change_type: str = None, limit: int = 50):
    """Get version history."""
    return {"history": _get_vm().get_history(
        module_id=module_id or None, change_type=change_type or None, limit=limit,
    )}


@router.get("/versions/current/{module_id}")
def get_current_version(module_id: str):
    """Get current version for a module."""
    result = _get_vm().get_current_version(module_id)
    if not result:
        raise HTTPException(404, f"No current version for {module_id}")
    return result


@router.post("/versions/set-current")
def set_current_version(body: dict):
    """Set current version for a module. Body: {module_id, version}"""
    vm = _get_vm()
    try:
        return vm.set_current(body["module_id"], body["version"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/versions/rollback/{module_id}")
def rollback_version(module_id: str):
    """Rollback a module to its previous version."""
    result = _get_vm().rollback(module_id)
    if not result:
        raise HTTPException(400, "No version to rollback to")
    return result


@router.post("/versions/check-compatibility")
def check_version_compatibility(body: dict):
    """Check version compatibility. Body: {module_id, version}"""
    return _get_vm().check_compatibility(body["module_id"], body["version"])


@router.get("/versions")
def list_versions(module_id: str = None, limit: int = 50):
    """List versions."""
    return {"versions": _get_vm().list_versions(module_id=module_id, limit=limit)}


@router.get("/versions/{version_id}")
def get_version(version_id: str):
    """Get a version by ID."""
    result = _get_vm().get_version(version_id)
    if not result:
        raise HTTPException(404, "Version not found")
    return result


@router.delete("/versions/{version_id}")
def delete_version(version_id: str):
    """Delete a version (cannot delete current)."""
    ok = _get_vm().delete_version(version_id)
    if not ok:
        raise HTTPException(400, "Cannot delete (not found or is current)")
    return {"deleted": version_id}


# ---------------------------------------------------------------------------
# Dependency Mapper -- lazy accessor
# ---------------------------------------------------------------------------

_dep_mapper = None


def _get_dep_mapper():
    global _dep_mapper
    if _dep_mapper is not None:
        return _dep_mapper
    from sylion.core.dependency_mapper import get_dependency_mapper
    _dep_mapper = get_dependency_mapper()
    return _dep_mapper


# ---------------------------------------------------------------------------
# Dependency Mapper -- request models
# ---------------------------------------------------------------------------

from pydantic import BaseModel as _BaseModel


class AddEdgeRequest(_BaseModel):
    from_module: str
    to_module: str
    dependency_type: str = "direct"
    contract_name: str = ""
    strength: float = 1.0


class ComputeGraphRequest(_BaseModel):
    root_module: str
    depth: int = 3


# ---------------------------------------------------------------------------
# Dependency Mapper -- endpoints
# (static routes before parameterized /{edge_id} routes)
# ---------------------------------------------------------------------------

@router.post("/dependencies", status_code=201)
def add_dependency_edge(body: AddEdgeRequest):
    """Add a dependency edge between two modules."""
    mapper = _get_dep_mapper()
    try:
        return mapper.add_edge(
            body.from_module, body.to_module,
            dependency_type=body.dependency_type,
            contract_name=body.contract_name,
            strength=body.strength,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dependencies")
def list_dependency_edges(from_module: str | None = None,
                          to_module: str | None = None,
                          dependency_type: str | None = None,
                          limit: int = 500):
    """List dependency edges with optional filters."""
    mapper = _get_dep_mapper()
    return {"edges": mapper.list_edges(
        from_module=from_module, to_module=to_module,
        dependency_type=dependency_type, limit=limit,
    )}


@router.get("/dependencies/dependents/{module_id}")
def get_dependents(module_id: str):
    """Get all modules that depend on the given module."""
    mapper = _get_dep_mapper()
    return {"dependents": mapper.get_dependents(module_id)}


@router.get("/dependencies/dependencies/{module_id}")
def get_dependencies(module_id: str):
    """Get all modules that the given module depends on."""
    mapper = _get_dep_mapper()
    return {"dependencies": mapper.get_dependencies(module_id)}


@router.post("/dependencies/graph")
def compute_dependency_graph(body: ComputeGraphRequest):
    """Compute a dependency graph from a root module using BFS."""
    mapper = _get_dep_mapper()
    return mapper.compute_graph(body.root_module, depth=body.depth)


@router.get("/dependencies/graphs")
def list_dependency_graphs(root_module: str | None = None, limit: int = 50):
    """List stored dependency graphs."""
    mapper = _get_dep_mapper()
    return {"graphs": mapper.list_graphs(root_module=root_module, limit=limit)}


@router.get("/dependencies/detect-cycles")
def detect_dependency_cycles():
    """Detect circular dependencies in the module graph."""
    mapper = _get_dep_mapper()
    cycles = mapper.detect_cycles()
    return {"cycles": cycles, "count": len(cycles)}


@router.get("/dependencies/stats")
def dependency_mapper_stats():
    """Get aggregate dependency mapper statistics."""
    return _get_dep_mapper().get_stats()


@router.delete("/dependencies/{edge_id}")
def remove_dependency_edge(edge_id: str):
    """Remove a dependency edge by ID."""
    mapper = _get_dep_mapper()
    removed = mapper.remove_edge(edge_id)
    if not removed:
        raise HTTPException(status_code=404,
                            detail=f"Edge {edge_id} not found")
    return {"removed": edge_id}
