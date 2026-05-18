from sylion.core.evidence_spine import EvidenceSpine
from sylion.skills.demand_signal import get_demand_signal_analyzer, reset_demand_signal_analyzer
from sylion.skills.executor import get_skills_executor, reset_skills_executor
from sylion.skills.integration import SkillIntegrationLayer, reset_skill_integration_layer
from sylion.skills.registry import get_skills_registry, reset_skills_registry
from sylion.skills.runtime import reset_skills_runtime


def _reset_all(db_path):
    reset_skills_runtime(db_path=db_path)
    reset_skills_registry(db_path=db_path)
    reset_skills_executor(db_path=db_path)
    reset_demand_signal_analyzer(db_path=db_path)
    reset_skill_integration_layer()


def _register_published_echo(db_path, skill_id="integration.echo"):
    registry = get_skills_registry(db_path=db_path)
    registry.register(
        skill_id,
        "Integration echo",
        domain="integration",
        owner_role="operator",
        description="Echo skill used by integration layer tests.",
        runtime_spec={
            "skill_id": skill_id,
            "name": "Integration echo",
            "entry_point": "sylion.skills.catalog:seed_echo_handler",
            "inputs": [{"name": "text", "type": "string", "required": True}],
            "outputs": [{"name": "output", "type": "string"}],
            "steps": ["Read text.", "Return text."],
        },
    )
    registry.publish(skill_id)


def test_pipeline_step_executes_skill_and_registers_evidence(tmp_path):
    db_path = tmp_path / "skills.sqlite"
    _reset_all(db_path)
    _register_published_echo(db_path)

    evidence = EvidenceSpine(db_path=tmp_path / "evidence.sqlite")
    layer = SkillIntegrationLayer(
        executor=get_skills_executor(db_path=db_path),
        demand_analyzer=get_demand_signal_analyzer(db_path=db_path),
        evidence_spine=evidence,
        db_path=db_path,
    )

    result = layer.execute_pipeline_step(
        "integration.echo",
        {"text": "pipeline-ok"},
        pipeline_id="W10",
        step_id="step-echo",
        project_id="project-skills",
        actor_id="operator@example.com",
    )

    assert result["ok"] is True
    assert result["execution"]["status"] == "completed"
    assert result["execution"]["output"]["runtime_output"] == "pipeline-ok"
    assert result["evidence_id"].startswith("ev_")

    artifact = evidence.get_artifact(result["evidence_id"])
    assert artifact is not None
    assert artifact["source"] == "skills.pipeline"
    assert artifact["artifact_type"] == "skill_execution"
    assert artifact["metadata"]["pipeline_id"] == "W10"


def test_dispatch_adapter_executes_skill_with_dispatch_source(tmp_path):
    db_path = tmp_path / "skills.sqlite"
    _reset_all(db_path)
    _register_published_echo(db_path)

    evidence = EvidenceSpine(db_path=tmp_path / "evidence.sqlite")
    layer = SkillIntegrationLayer(
        executor=get_skills_executor(db_path=db_path),
        demand_analyzer=get_demand_signal_analyzer(db_path=db_path),
        evidence_spine=evidence,
        db_path=db_path,
    )

    result = layer.dispatch(
        "integration.echo",
        {"text": "dispatch-ok"},
        dispatch_source="J5",
        project_id="project-skills",
    )

    assert result["ok"] is True
    assert result["dispatch_source"] == "J5"
    artifact = evidence.get_artifact(result["evidence_id"])
    assert artifact["source"] == "skills.dispatch"
    assert artifact["metadata"]["dispatch_source"] == "J5"


def test_demand_consumer_records_signal_and_report(tmp_path):
    db_path = tmp_path / "skills.sqlite"
    _reset_all(db_path)
    layer = SkillIntegrationLayer(
        executor=get_skills_executor(db_path=db_path),
        demand_analyzer=get_demand_signal_analyzer(db_path=db_path),
        evidence_spine=EvidenceSpine(db_path=tmp_path / "evidence.sqlite"),
        db_path=db_path,
    )

    result = layer.record_demand_and_analyze(
        signal_type="pipeline_needs_skill",
        source="W10",
        skill_id="integration.echo",
        confidence=0.9,
        details={"pipeline_id": "W10"},
    )

    assert result["signal"]["signal_type"] == "pipeline_needs_skill"
    assert result["report"]["signal_count"] == 1
    assert result["report"]["top_demands"][0]["skill_id"] == "integration.echo"
