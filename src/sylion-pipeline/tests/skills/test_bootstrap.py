from pathlib import Path

from sylion.skills.runtime import SkillsRuntime


def _seed_manifests_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "manifests" / "skills"
        if candidate.exists():
            return candidate
    raise AssertionError("seed manifests directory not found")


def test_bootstrap_from_seed_manifests_loads_demo_skills():
    runtime = SkillsRuntime()
    runtime.bootstrap_from(_seed_manifests_dir())

    loaded = runtime.list_loaded()
    loaded_ids = {skill["skill_id"] for skill in loaded if skill}

    assert {"seed.echo", "seed.tokenize", "seed.summarize"}.issubset(loaded_ids)
    assert runtime.get_stats()["loaded_skills"] >= 3
