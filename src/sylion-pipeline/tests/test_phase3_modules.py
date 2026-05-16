"""
Integration test: verify all Phase 3 modules load, have consistent API shape,
and cross-module integration works.
"""

import importlib
import pytest


# ---------------------------------------------------------------------------
# Module Import Verification
# ---------------------------------------------------------------------------

MODULES_UNDER_TEST = [
    ("sylion.skills.catalog", "SkillsCatalog"),
    ("sylion.aeis.self_evolution", "SelfEvolution"),
    ("sylion.aeis.adaptation_engine", "AdaptationEngine"),
    ("sylion.skills.registry", "SkillsRegistry"),
    ("sylion.skills.executor", "SkillsExecutor"),
    ("sylion.aeis.self_observation", "SelfObservation"),
    ("sylion.aeis.improvement_queue", "ImprovementQueue"),
    ("sylion.aeis.self_explanation", "SelfExplanationEngine"),
    ("sylion.aeis.self_limitation", "SelfLimitationEngine"),
    ("sylion.aeis.self_preservation", "SelfPreservationEngine"),
    ("sylion.core.event_bus", "EventBus"),
    ("sylion.core.module_registry", "ModuleRegistry"),
    ("sylion.core.contract_registry", "ContractRegistry"),
]


@pytest.mark.parametrize("module_path,class_name", MODULES_UNDER_TEST)
def test_module_imports(module_path, class_name):
    """Verify every module imports and has the expected class."""
    mod = importlib.import_module(module_path)
    assert hasattr(mod, class_name), f"{module_path} missing {class_name}"


# ---------------------------------------------------------------------------
# Cross-Module Integration
# ---------------------------------------------------------------------------

def test_skills_catalog_to_registry_integration():
    """Skills catalog can reference skills from the registry."""
    from sylion.skills.catalog import SkillsCatalog
    from sylion.skills.registry import SkillsRegistry

    registry = SkillsRegistry()
    catalog = SkillsCatalog()

    reg_result = registry.register("s-int-1", "Integration Skill", domain="test")
    assert reg_result["skill_id"] == "s-int-1"

    cat_result = catalog.add("s-int-1", "Integration Skill", category="test")
    assert cat_result["skill_id"] == "s-int-1"

    # Verify cross-reference
    skill = registry.get("s-int-1")
    assert skill is not None
    cat_entry = catalog.get_by_skill("s-int-1")
    assert cat_entry is not None
    assert cat_entry["name"] == skill["name"]


def test_evolution_to_adaptation_integration():
    """Evolution proposals can trigger adaptations."""
    from sylion.aeis.self_evolution import SelfEvolution
    from sylion.aeis.adaptation_engine import AdaptationEngine

    evo = SelfEvolution()
    adapt = AdaptationEngine()

    # Propose an evolution
    proposal = evo.propose("core.event_bus", "parameter_tune",
                           description="Tune batch size",
                           expected_fitness_delta=0.15)
    assert proposal["state"] == "PROPOSED"

    # Create an adaptation triggered by the proposal
    adaptation = adapt.create_adaptation(
        adaptation_type="parameter_tune",
        trigger_metric="throughput",
        trigger_value=100.0,
        target_value=150.0,
        strategy="increase_batch_size",
    )
    assert adaptation["state"] == "PENDING"

    # Walk evolution through lifecycle
    evo.transition(proposal["proposal_id"], "EVALUATING")
    evo.transition(proposal["proposal_id"], "APPROVED")
    evo.transition(proposal["proposal_id"], "APPLYING")

    # Apply adaptation
    adapt.apply(adaptation["adaptation_id"])
    adapt.complete(adaptation["adaptation_id"])

    # Verify both are in correct states
    p = evo.get(proposal["proposal_id"])
    assert p["state"] == "APPLYING"

    a = adapt.get(adaptation["adaptation_id"])
    assert a["state"] == "COMPLETED"


def test_observation_to_adaptation_pipeline():
    """Self-observation data can trigger adaptation rules."""
    from sylion.aeis.self_observation import SelfObservation
    from sylion.aeis.adaptation_engine import AdaptationEngine

    obs = SelfObservation()
    adapt = AdaptationEngine()

    # Record high CPU observation
    obs.record("cpu_usage", 0.95, unit="ratio", source="monitor")

    # Set up an adaptation rule
    adapt.add_rule(
        name="High CPU Auto-Scale",
        trigger_metric="cpu_usage",
        condition_op=">",
        threshold=0.90,
        adaptation_type="resource_rebalance",
        strategy="scale_out",
    )

    # Ingest feedback triggers the rule
    result = adapt.ingest_feedback("monitor", "cpu_usage", 0.95)
    assert result["triggered_adaptations"] == 1

    # Verify stats
    obs_stats = obs.get_stats()
    assert obs_stats["total_observations"] == 1

    adapt_stats = adapt.get_stats()
    assert adapt_stats["total_adaptations"] == 1
    assert adapt_stats["total_feedback_signals"] == 1


def test_event_bus_integration():
    """All modules emit events via EventBus when connected."""
    from sylion.core.event_bus import EventBus, SylionEvent
    from sylion.skills.catalog import SkillsCatalog
    from sylion.aeis.self_evolution import SelfEvolution

    events = []

    class CaptureBus:
        def publish(self, event: SylionEvent):
            events.append({"topic": event.topic, "payload": event.payload})

    bus = CaptureBus()

    catalog = SkillsCatalog(event_bus=bus)
    catalog.add("s-1", "Test Skill", category="kernel")

    evo = SelfEvolution(event_bus=bus)
    evo.propose("core.test", "mutation", description="test mutation")

    assert len(events) >= 2
    topics = [e["topic"] for e in events]
    assert "skill.catalog.added" in topics
    assert "aeis.self_evolution.proposed" in topics


def test_full_skills_lifecycle():
    """Full skill lifecycle: register -> catalog -> execute -> deprecate."""
    from sylion.skills.registry import SkillsRegistry
    from sylion.skills.catalog import SkillsCatalog
    from sylion.skills.executor import SkillsExecutor

    registry = SkillsRegistry()
    catalog = SkillsCatalog()
    executor = SkillsExecutor()

    # Register
    reg = registry.register("lifecycle-1", "Lifecycle Test Skill",
                            domain="test", description="Full lifecycle test")
    assert reg["lifecycle"] == "DRAFT"

    # Add to catalog
    cat = catalog.add("lifecycle-1", "Lifecycle Test Skill",
                      category="test", domain="test")
    assert cat["category"] == "test"

    # Publish
    pub = registry.publish("lifecycle-1")
    assert pub["lifecycle"] == "PUBLISHED"

    # Execute
    exe = executor.execute("lifecycle-1", input_data={"test": True})
    assert exe["status"] == "completed"

    # Track usage
    catalog.track_usage(cat["entry_id"])
    entry = catalog.get(cat["entry_id"])
    assert entry["usage_count"] == 1

    # Deprecate
    dep = registry.deprecate("lifecycle-1")
    assert dep["lifecycle"] == "DEPRECATED"

    # Verify stats
    reg_stats = registry.get_stats()
    assert reg_stats["total_skills"] == 1

    cat_stats = catalog.get_stats()
    assert cat_stats["total_entries"] == 1

    exe_stats = executor.get_stats()
    assert exe_stats["total_executions"] == 1


def test_evolution_lifecycle_with_fitness():
    """Complete evolution lifecycle with fitness tracking."""
    from sylion.aeis.self_evolution import SelfEvolution

    evo = SelfEvolution()

    # Propose
    p = evo.propose(
        "cognitive.planner", "strategy_change",
        description="Switch to tree-of-thought",
        rationale="Better planning depth",
        expected_fitness_delta=0.2,
        risk_level="medium",
        rollback_plan="Revert to chain-of-thought",
    )

    pid = p["proposal_id"]

    # Record baseline fitness
    evo.record_fitness(pid, fitness_before=0.65, fitness_after=0.0)

    # Evaluate
    evo.transition(pid, "EVALUATING")

    # Simulate improved fitness after testing
    evo.record_fitness(pid, fitness_before=0.65, fitness_after=0.82)

    # Approve and apply
    evo.transition(pid, "APPROVED")
    evo.transition(pid, "APPLYING")
    evo.transition(pid, "VERIFIED")

    # Verify full history
    events = evo.get_events(pid)
    states = [e["to_state"] for e in events]
    assert states == ["EVALUATING", "APPROVED", "APPLYING", "VERIFIED"]

    proposal = evo.get(pid)
    assert proposal["fitness_after"] == 0.82
    assert proposal["fitness_before"] == 0.65


def test_adaptation_rules_engine():
    """Adaptation rules engine with multiple conditions."""
    from sylion.aeis.adaptation_engine import AdaptationEngine

    engine = AdaptationEngine()

    # Add multiple rules
    engine.add_rule("High CPU", "cpu", ">", 0.9, "resource_rebalance", "scale_out")
    engine.add_rule("Low Memory", "memory", "<", 0.1, "resource_rebalance", "free_cache")
    engine.add_rule("High Latency", "latency", ">", 100, "parameter_tune", "reduce_timeout")

    # Trigger CPU rule
    r1 = engine.ingest_feedback("mon", "cpu", 0.95)
    assert r1["triggered_adaptations"] == 1

    # Trigger memory rule
    r2 = engine.ingest_feedback("mon", "memory", 0.05)
    assert r2["triggered_adaptations"] == 1

    # Don't trigger latency (below threshold)
    r3 = engine.ingest_feedback("mon", "latency", 50)
    assert r3["triggered_adaptations"] == 0

    # Verify 2 adaptations created
    stats = engine.get_stats()
    assert stats["total_adaptations"] == 2
    assert stats["total_feedback_signals"] == 3

    # Complete first adaptation lifecycle
    adapt_id = r1["adaptation_ids"][0]
    engine.apply(adapt_id)
    engine.complete(adapt_id, "Scaled out successfully")

    a = engine.get(adapt_id)
    assert a["state"] == "COMPLETED"
    assert a["outcome"] == "Scaled out successfully"
