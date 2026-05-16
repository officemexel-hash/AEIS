import pytest

import sylion.skills.registry as registry_mod
from sylion.skills.registry import SkillsRegistry
from sylion.skills.runtime import get_skills_runtime, reset_skills_runtime


@pytest.fixture(autouse=True)
def _reset_singletons():
    registry_mod._registry = None
    reset_skills_runtime()
    yield
    registry_mod._registry = None
    reset_skills_runtime()


def test_register_skill_bootstraps_runtime_immediately():
    registry = SkillsRegistry()

    result = registry.register_skill(
        {
            "skill_id": "inline.echo",
            "name": "inline.echo",
            "description": "Inline runtime registration",
            "runtime_spec": {
                "skill_id": "inline.echo",
                "name": "inline.echo",
                "description": "Inline runtime registration",
                "entry_point": "sylion.skills.catalog:seed_echo_handler",
                "inputs": [{"name": "text", "type": "string", "required": True}],
                "outputs": [{"name": "output", "type": "string"}],
                "steps": [
                    "Read the text payload.",
                    "Return the exact same text.",
                ],
            },
        }
    )

    runtime = get_skills_runtime()
    state = runtime.get_loaded_skill("inline.echo")
    execution = runtime.execute("inline.echo", {"text": "ready"})

    assert result["loaded_in_runtime"] is True
    assert state is not None
    assert execution["status"] == "completed"
    assert execution["output"] == "ready"
