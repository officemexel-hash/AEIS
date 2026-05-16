"""Skills truth-plane bootstrap helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus


def bootstrap_truth_plane(
    *,
    db_path: str | Path | None = None,
    skills_dir: str | Path | None = None,
    event_bus: EventBus | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    """Bind registry, runtime, and executor to one store and synchronize specs.

    Manifest seed skills are first loaded into runtime. Existing registry
    records are then bootstrapped back into runtime, and any runtime-only
    manifest skill is registered as PUBLISHED so API/UI surfaces expose the
    same skill set.
    """

    from sylion.skills.executor import get_skills_executor, reset_skills_executor
    from sylion.skills.registry import get_skills_registry, reset_skills_registry
    from sylion.skills.runtime import get_skills_runtime, reset_skills_runtime

    if reset:
        registry = reset_skills_registry(db_path=db_path, event_bus=event_bus)
        runtime = reset_skills_runtime(db_path=db_path, skills_dir=skills_dir, event_bus=event_bus)
        executor = reset_skills_executor(db_path=db_path, event_bus=event_bus)
    else:
        registry = get_skills_registry(db_path=db_path, event_bus=event_bus)
        runtime = get_skills_runtime(db_path=db_path, skills_dir=skills_dir, event_bus=event_bus)
        executor = get_skills_executor(db_path=db_path, event_bus=event_bus)

    if runtime is None:
        runtime = get_skills_runtime(db_path=db_path, skills_dir=skills_dir, event_bus=event_bus)

    skills_path = Path(skills_dir) if skills_dir else None
    if skills_path and skills_path.exists():
        runtime.bootstrap_from(skills_path)

    loaded_from_registry = 0
    for skill in registry.list_skills(limit=10000):
        skill_id = skill.get("skill_id", "")
        if not skill_id or runtime.get_loaded_skill(skill_id):
            continue
        runtime_spec = skill.get("runtime_spec") or {}
        if runtime_spec and runtime.bootstrap_one(runtime_spec):
            loaded_from_registry += 1

    registered_from_runtime = 0
    for spec in runtime.list_loaded():
        skill_id = spec.get("skill_id") or spec.get("name")
        if not skill_id or registry.get(skill_id):
            continue

        registry.register_skill(
            {
                "skill_id": skill_id,
                "name": spec.get("name") or skill_id,
                "domain": spec.get("domain", ""),
                "owner_role": spec.get("owner_role", ""),
                "description": spec.get("description", ""),
                "version": spec.get("version", "1.0.0"),
                "lifecycle": str(spec.get("lifecycle") or "PUBLISHED").upper(),
                "inputs": spec.get("inputs", []),
                "outputs": spec.get("outputs", []),
                "runtime_spec": spec,
            },
            persist=True,
        )
        registered_from_runtime += 1

    runtime_stats = runtime.get_stats()
    registry_stats = registry.get_stats()
    executor_stats = executor.get_stats()

    return {
        "skills_dir": str(skills_path) if skills_path else "",
        "skills_dir_exists": bool(skills_path and skills_path.exists()),
        "runtime_loaded_skills": runtime_stats.get("loaded_skills", 0),
        "registry_total_skills": registry_stats.get("total_skills", 0),
        "registered_from_runtime": registered_from_runtime,
        "loaded_from_registry": loaded_from_registry,
        "executor_total_executions": executor_stats.get("total_executions", 0),
    }
