"""Tests for skills.runtime module."""

import pytest
from pathlib import Path
from sylion.skills.runtime import SkillsRuntime, SkillSpec, load_skill_spec


@pytest.fixture
def runtime():
    return SkillsRuntime()


@pytest.fixture
def runtime_with_skills(tmp_path):
    """Create a runtime with test skill definitions."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text(
        "name: test-skill\nversion: 1.0.0\ndescription: A test skill\n"
        "parallel_safe: true\nidempotent: true\n"
        "inputs:\n  - name: module_id\n    type: string\n    required: true\n"
        "outputs:\n  - service.py\n"
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\n---\n# Test Skill\n\n"
        "## Execution steps\n\n1. **Read module** - read the module\n"
        "2. **Generate code** - generate the code\n"
        "3. **Write file** - write the output\n\n"
        "## Safety rules\n\n1. No production databases\n2. No network calls\n"
    )
    return SkillsRuntime(skills_dir=tmp_path)


def test_discover_skills(runtime_with_skills):
    names = runtime_with_skills.list_specs()
    assert "test-skill" in names


def test_get_spec(runtime_with_skills):
    spec = runtime_with_skills.get_spec("test-skill")
    assert spec is not None
    assert spec["name"] == "test-skill"
    assert spec["version"] == "1.0.0"
    assert len(spec["inputs"]) == 1
    assert spec["inputs"][0]["name"] == "module_id"
    assert spec["inputs"][0]["required"] is True
    assert len(spec["steps"]) == 3


def test_execute_known_skill(runtime_with_skills):
    result = runtime_with_skills.execute("test-skill", {"module_id": "core.test"})
    assert result["status"] == "completed"
    assert "exec_id" in result
    assert result["steps_completed"] == 3
    assert "output" in result


def test_execute_unknown_skill(runtime):
    result = runtime.execute("nonexistent-skill", {})
    assert result["status"] == "failed"
    assert "Unknown skill" in result["error"]


def test_validate_missing_required(runtime_with_skills):
    result = runtime_with_skills.execute("test-skill", {})
    assert result["status"] == "failed"
    assert "Missing required input" in result["error"]


def test_execute_with_handler(runtime_with_skills):
    def custom_handler(spec, inputs):
        return {"custom": True, "module": inputs["module_id"]}

    result = runtime_with_skills.execute(
        "test-skill", {"module_id": "core.custom"}, handler=custom_handler,
    )
    assert result["status"] == "completed"
    assert result["output"]["custom"] is True
    assert result["output"]["module"] == "core.custom"


def test_execute_handler_exception(runtime_with_skills):
    def bad_handler(spec, inputs):
        raise RuntimeError("Handler failed")

    result = runtime_with_skills.execute(
        "test-skill", {"module_id": "core.bad"}, handler=bad_handler,
    )
    assert result["status"] == "failed"
    assert "Handler failed" in result["error"]


def test_get_execution(runtime_with_skills):
    executed = runtime_with_skills.execute("test-skill", {"module_id": "core.x"})
    record = runtime_with_skills.get_execution(executed["exec_id"])
    assert record is not None
    assert record["skill_name"] == "test-skill"
    assert record["status"] == "completed"


def test_get_execution_not_found(runtime):
    assert runtime.get_execution("nonexistent") is None


def test_list_executions(runtime_with_skills):
    runtime_with_skills.execute("test-skill", {"module_id": "a"})
    runtime_with_skills.execute("test-skill", {"module_id": "b"})

    all_exec = runtime_with_skills.list_executions()
    assert len(all_exec) == 2

    completed = runtime_with_skills.list_executions(status="completed")
    assert len(completed) == 2


def test_stats(runtime_with_skills):
    runtime_with_skills.execute("test-skill", {"module_id": "x"})
    runtime_with_skills.execute("test-skill", {"module_id": "y"})
    runtime_with_skills.execute("nonexistent", {})

    stats = runtime_with_skills.get_stats()
    assert stats["total_executions"] == 3
    assert stats["loaded_skills"] == 1
    assert stats["by_status"]["completed"] == 2
    assert stats["by_status"]["failed"] == 1


def test_discover_no_dir(runtime):
    result = runtime.discover_skills()
    assert result == []


def test_load_skill_spec(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n# My Skill\n")
    (skill_dir / "skill.yaml").write_text("name: my-skill\nversion: 2.0.0\n")

    spec = load_skill_spec(skill_dir)
    assert spec is not None
    assert spec.name == "my-skill"
    assert spec.version == "2.0.0"


def test_load_skill_spec_no_md(tmp_path):
    skill_dir = tmp_path / "empty"
    skill_dir.mkdir()
    assert load_skill_spec(skill_dir) is None


def test_safety_rules_parsed(runtime_with_skills):
    spec = runtime_with_skills.get_spec("test-skill")
    assert len(spec["safety_rules"]) == 2
    assert "No production databases" in spec["safety_rules"][0]


def test_eventbus_integration():
    from sylion.core.event_bus import EventBus, SylionEvent

    events = []

    class CaptureBus:
        def publish(self, event: SylionEvent):
            events.append({"topic": event.topic, "payload": event.payload})

    rt = SkillsRuntime(event_bus=CaptureBus())
    rt._specs["demo-skill"] = SkillSpec(name="demo-skill", inputs=[])
    rt.execute("demo-skill", {})

    assert len(events) == 1
    assert events[0]["topic"] == "skill.runtime.executed"
