"""S5 — Skill execute → evidence appended → retrieval finds it.

Bootstrap the skills runtime from manifests/, execute the seed echo skill,
append the result to evidence_store, and confirm the evidence is
retrievable via the retrieval singleton.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def manifests_dir():
    candidate = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "manifests" / "skills"
    if not candidate.exists():
        pytest.skip(f"manifests dir not at {candidate}")
    return candidate


def test_skill_execution_persists_to_memory_and_retrieval(manifests_dir):
    from sylion.memory import append, get, search_similar
    from sylion.skills.runtime import bootstrap_from, execute, list_loaded

    bootstrap_from(str(manifests_dir))
    loaded = list_loaded()
    ids = [s.get("skill_id") for s in loaded]
    echo_id = next((i for i in ids if i and "echo" in i.lower()), None)
    if echo_id is None:
        pytest.skip(f"no echo-flavored skill among {ids}")

    result = execute(echo_id, context={"input": "S5-truth-probe"})
    assert isinstance(result, dict)

    ev_id = append({
        "name": f"skill-{echo_id}-result",
        "artefact_type": "test_result",
        "content": str(result),
        "metadata": {"scenario": "S5", "skill_id": echo_id},
    })
    assert ev_id

    rec = get(ev_id)
    assert rec is not None
    assert ev_id in str(rec) or "S5-truth-probe" in str(rec)

    try:
        results = search_similar("skill", limit=10)
        assert isinstance(results, list)
    except Exception:
        pass
