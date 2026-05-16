"""Regression tests for skills registry/runtime truth-plane bootstrap."""

from sylion.skills.bootstrap import bootstrap_truth_plane
from sylion.skills.executor import get_skills_executor
from sylion.skills.registry import get_skills_registry
from sylion.skills.runtime import get_skills_runtime


def test_skills_truth_plane_syncs_manifest_runtime_registry_and_executor(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "seed.echo.yaml").write_text(
        "\n".join(
            [
                "skill_id: seed.echo",
                "name: Seed Echo",
                "version: 1.0.0",
                "description: Echo seed skill",
                "domain: core",
                "lifecycle: PUBLISHED",
                "inputs:",
                "  - name: message",
                "    type: string",
                "    required: false",
                "steps:",
                "  - Read message",
                "  - Return echo result",
                "",
            ]
        ),
        encoding="utf-8",
    )

    db_path = tmp_path / "skills.sqlite"
    result = bootstrap_truth_plane(
        db_path=db_path,
        skills_dir=skills_dir,
        reset=True,
    )

    assert result["runtime_loaded_skills"] == 1
    assert result["registry_total_skills"] == 1
    assert result["registered_from_runtime"] == 1

    runtime = get_skills_runtime()
    registry = get_skills_registry()
    executor = get_skills_executor()

    assert runtime.get_loaded_skill("seed.echo") is not None
    assert registry.get("seed.echo")["lifecycle"] == "PUBLISHED"

    executed = executor.execute("seed.echo", {"message": "hello"})
    assert executed["status"] == "completed"
    assert executed["output"]["execution_engine"] == "skills.runtime"
