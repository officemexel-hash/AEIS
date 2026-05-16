"""Tests for SYLION AEIS core modules."""
import pytest


def test_module_registry_register_get(bus):
    from sylion.core.module_registry import ModuleRegistry, ModuleManifest, ModuleKind
    reg = ModuleRegistry()
    reg.register(ModuleManifest(module_id="core.test", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01"))
    m = reg.get("core.test")
    assert m is not None
    assert m["module_id"] == "core.test"
    assert m["lifecycle"] == "draft"


def test_module_registry_lifecycle(bus):
    from sylion.core.module_registry import ModuleRegistry, ModuleManifest, ModuleKind, ModuleLifecycleStage
    reg = ModuleRegistry()
    reg.register(ModuleManifest(module_id="core.lc", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01"))
    reg.transition("core.lc", ModuleLifecycleStage.BUILD)
    assert reg.get("core.lc")["lifecycle"] == "build"
    reg.transition("core.lc", ModuleLifecycleStage.VALIDATE)
    assert reg.get("core.lc")["lifecycle"] == "validate"


def test_module_registry_list(bus):
    from sylion.core.module_registry import ModuleRegistry, ModuleManifest, ModuleKind
    reg = ModuleRegistry()
    reg.register(ModuleManifest(module_id="a.x", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01"))
    reg.register(ModuleManifest(module_id="b.y", module_kind=ModuleKind.SECURITY, owner_plan="P09"))
    assert len(reg.list_modules()) == 2


def test_event_bus_publish_query(bus):
    from sylion.core.event_bus import SylionEvent
    bus.publish(SylionEvent(event_id="", topic="test.topic", payload={"k": "v"}, source_module="test"))
    results = bus.query(topic="test.topic")
    assert len(results) >= 1


def test_event_bus_catalog(bus):
    from sylion.core.event_bus import SylionEvent
    bus.publish(SylionEvent(event_id="", topic="cat.test", payload={}, source_module="test"))
    cat = bus.get_catalog()
    assert "cat.test" in cat


def test_event_bus_ack(bus):
    from sylion.core.event_bus import SylionEvent
    bus.publish(SylionEvent(event_id="", topic="ack.test", payload={}, source_module="test"))
    results = bus.query(topic="ack.test")
    assert len(results) >= 1
    bus.ack(results[0]["event_id"])


def test_evidence_spine_append_verify(spine):
    from sylion.core.evidence_spine import EvidenceEntry
    spine.append(EvidenceEntry(source_plan="P01", event_type="test", payload={"x": 1}))
    valid, msg = spine.verify_chain()
    assert valid


def test_evidence_spine_query(spine):
    from sylion.core.evidence_spine import EvidenceEntry
    spine.append(EvidenceEntry(source_plan="P01", event_type="test.a", payload={}))
    spine.append(EvidenceEntry(source_plan="P02", event_type="test.b", payload={}))
    assert len(spine.query(source_plan="P01")) >= 1
    assert len(spine.query(source_plan="P02")) >= 1


def test_decision_gate_classify(bus):
    from sylion.core.decision_gate_engine import DecisionGateEngine, DecisionRequest
    dge = DecisionGateEngine(event_bus=bus)
    r = dge.classify(DecisionRequest(description="test", source_plan="P01", change_type="config", blast_radius="low"))
    assert r.decision_class.value in ("D0", "D1")


def test_decision_gate_high_blast(bus):
    from sylion.core.decision_gate_engine import DecisionGateEngine, DecisionRequest
    dge = DecisionGateEngine(event_bus=bus)
    r = dge.classify(DecisionRequest(description="test", source_plan="P01", change_type="module", blast_radius="high", reversible=False))
    assert r.decision_class.value in ("D2", "D3")


def test_contract_registry(bus):
    from sylion.core.contract_registry import ContractRegistry, Contract
    cr = ContractRegistry(event_bus=bus)
    cr.publish(Contract(name="test-contract", version="1.0.0"))
    c = cr.get("test-contract")
    assert c is not None
    assert c["version"] == "1.0.0"


def test_contract_breaking_change(bus):
    from sylion.core.contract_registry import ContractRegistry, Contract
    cr = ContractRegistry(event_bus=bus)
    cr.publish(Contract(name="break-test", version="1.0.0"))
    result = cr.publish(Contract(name="break-test", version="2.0.0"))
    assert result["breaking"] is True


def test_bundle_assembler(registry):
    from sylion.core.module_registry import ModuleManifest, ModuleKind, ModuleLifecycleStage
    from sylion.core.bundle_assembler import BundleAssembler
    registry.register(ModuleManifest(module_id="ba.m1", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01"))
    registry.register(ModuleManifest(module_id="ba.m2", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01"))
    registry.transition("ba.m1", ModuleLifecycleStage.BUILD)
    registry.transition("ba.m1", ModuleLifecycleStage.VALIDATE)
    registry.transition("ba.m2", ModuleLifecycleStage.BUILD)
    registry.transition("ba.m2", ModuleLifecycleStage.VALIDATE)
    ba = BundleAssembler(registry=registry)
    bundle = ba.assemble(["ba.m1", "ba.m2"], created_by="test")
    v = ba.validate(bundle.bundle_id)
    assert v["valid"]


def test_environment_orchestrator(registry):
    from sylion.core.module_registry import ModuleManifest, ModuleKind
    from sylion.core.environment_orchestrator import EnvironmentOrchestrator, DeployRequest, DeployAction
    registry.register(ModuleManifest(module_id="eo.mod", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01"))
    eo = EnvironmentOrchestrator(registry=registry)
    dr = eo.deploy(DeployRequest(module_id="eo.mod", action=DeployAction.DEPLOY))
    assert dr.status == "success"


def test_manifest_loader():
    from sylion.core.manifest_loader import ManifestLoader
    ml = ManifestLoader()
    result = ml.load_dict({"module_id": "test", "module_kind": "A", "owner_plan": "P01"})
    assert result["module_id"] == "test"
