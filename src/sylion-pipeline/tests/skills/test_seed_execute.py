from pathlib import Path

from sylion.skills.runtime import SkillsRuntime


def _seed_manifests_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "manifests" / "skills"
        if candidate.exists():
            return candidate
    raise AssertionError("seed manifests directory not found")


def test_seed_echo_execute_returns_raw_text():
    runtime = SkillsRuntime()
    runtime.bootstrap_from(_seed_manifests_dir())

    result = runtime.execute("seed.echo", {"text": "hello"})

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["output"] == "hello"
