"""W7 Role Catalog Phase-0 extension tests (capability taxonomy + match-task).

Validates the new endpoints layered on top of the original Phase-0 routes:

- ``GET  /api/v1/role-catalog/capabilities``                  -> deduplicated taxonomy
- ``GET  /api/v1/role-catalog/by-capability/{capability_id}`` -> roles by capability
- ``POST /api/v1/role-catalog/match-task``                    -> capability overlap matcher

The catalog ships three enriched roles (``data_engineer``, ``frontend_specialist``,
``ai_orchestrator``) carrying the new ``capabilities`` / ``skill_level`` /
``required_tools`` / ``prerequisite_roles`` fields. Legacy roles still load with
empty/``"any"`` defaults.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.api.role_catalog_routes import router as role_catalog_router


def _client() -> TestClient:
    """Mount the W7 router on a bare FastAPI app (no lifespan, no DB)."""
    api = FastAPI()
    api.include_router(role_catalog_router)
    return TestClient(api)


# --------------------------------------------------------------------------
# GET /api/v1/role-catalog/capabilities
# --------------------------------------------------------------------------


def test_get_capabilities_returns_deduplicated_list() -> None:
    """Capability ids must appear at most once even if many roles declare them."""
    client = _client()
    r = client.get("/api/v1/role-catalog/capabilities")
    assert r.status_code == 200
    body = r.json()

    assert isinstance(body["count"], int)
    assert isinstance(body["capabilities"], list)
    assert body["count"] == len(body["capabilities"])

    ids = [entry["id"] for entry in body["capabilities"]]
    assert len(ids) == len(set(ids)), f"capabilities not deduplicated: {ids}"

    # Enriched-role capabilities must surface in the taxonomy.
    expected_subset = {"sql", "python", "airflow", "react", "llm_routing"}
    assert expected_subset.issubset(set(ids)), (
        f"missing enriched capabilities: {expected_subset - set(ids)}"
    )


def test_get_capabilities_includes_role_count_per_capability() -> None:
    """Each capability entry must carry a positive ``role_count``."""
    client = _client()
    r = client.get("/api/v1/role-catalog/capabilities")
    assert r.status_code == 200
    body = r.json()

    by_id = {entry["id"]: entry for entry in body["capabilities"]}
    # ``sql`` is currently held only by data_engineer -> count == 1.
    assert by_id["sql"]["role_count"] == 1
    # ``llm_routing`` is held only by ai_orchestrator -> count == 1.
    assert by_id["llm_routing"]["role_count"] == 1
    for entry in body["capabilities"]:
        assert entry["role_count"] >= 1, entry


# --------------------------------------------------------------------------
# GET /api/v1/role-catalog/by-capability/{capability_id}
# --------------------------------------------------------------------------


def test_get_by_capability_returns_roles_with_that_capability() -> None:
    """``sql`` -> data_engineer; the response carries the summary shape."""
    client = _client()
    r = client.get("/api/v1/role-catalog/by-capability/sql")
    assert r.status_code == 200
    body = r.json()

    assert body["capability"] == "sql"
    assert body["total"] >= 1
    role_ids = {entry["id"] for entry in body["roles"]}
    assert "data_engineer" in role_ids

    # Summaries must surface the new W7 fields.
    de = next(r for r in body["roles"] if r["id"] == "data_engineer")
    assert de["skill_level"] == "senior"
    assert "sql" in de["capabilities"]


def test_get_by_capability_unknown_returns_empty_list() -> None:
    """Unknown capability ids yield an empty list (200, not 404).

    Mirrors the existing pattern: ``/category`` returns 400 for invalid
    enum values, but capabilities are open-ended so we surface emptiness.
    """
    client = _client()
    r = client.get("/api/v1/role-catalog/by-capability/__no_such_cap__")
    assert r.status_code == 200
    body = r.json()
    assert body["capability"] == "__no_such_cap__"
    assert body["total"] == 0
    assert body["roles"] == []


# --------------------------------------------------------------------------
# POST /api/v1/role-catalog/match-task
# --------------------------------------------------------------------------


def test_post_match_task_ranks_by_capability_overlap() -> None:
    """Requesting [sql, python] -> data_engineer must rank first."""
    client = _client()
    r = client.post(
        "/api/v1/role-catalog/match-task",
        json={
            "task_description": "Build a daily ETL pipeline for analytics.",
            "required_capabilities": ["sql", "python"],
            "skill_level": "any",
        },
    )
    assert r.status_code == 200
    body = r.json()

    assert body["engine"] == "capability-overlap-v0"
    assert body["matches"], "expected at least one match"
    top = body["matches"][0]
    assert top["role"]["id"] == "data_engineer"
    assert set(top["matched_capabilities"]) == {"sql", "python"}
    assert top["score"] > 0


def test_post_match_task_filters_by_skill_level() -> None:
    """Requesting ``senior`` excludes mid-level roles like frontend_specialist.

    ``frontend_specialist`` has capabilities=[typescript, react, ...] at
    skill_level=mid. Requesting senior+ with those capabilities must still
    return *some* match (the request itself is plausible) but must NOT
    surface the mid-level role.
    """
    client = _client()
    r = client.post(
        "/api/v1/role-catalog/match-task",
        json={
            "task_description": "",
            "required_capabilities": ["react", "typescript"],
            "skill_level": "senior",
        },
    )
    assert r.status_code == 200
    body = r.json()

    matched_ids = {entry["role"]["id"] for entry in body["matches"]}
    assert "frontend_specialist" not in matched_ids, (
        f"mid-level role must not match senior+ filter: {matched_ids}"
    )

    # The principal-level ai_orchestrator does NOT carry react/typescript,
    # so the senior-filtered match list for those caps should be empty.
    assert body["matches"] == [], (
        f"no senior+ role declares react/typescript yet, got: {matched_ids}"
    )


def test_post_match_task_invalid_skill_level_returns_400() -> None:
    """Skill-level value must belong to the canonical enum."""
    client = _client()
    r = client.post(
        "/api/v1/role-catalog/match-task",
        json={
            "task_description": "anything",
            "required_capabilities": [],
            "skill_level": "wizard",
        },
    )
    assert r.status_code == 400


def test_post_match_task_principal_request_returns_ai_orchestrator() -> None:
    """Capability ``llm_routing`` is only on ai_orchestrator (principal)."""
    client = _client()
    r = client.post(
        "/api/v1/role-catalog/match-task",
        json={
            "task_description": "Design LLM routing across model tiers.",
            "required_capabilities": ["llm_routing", "prompt_engineering"],
            "skill_level": "principal",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["matches"], "expected ai_orchestrator to match"
    top = body["matches"][0]
    assert top["role"]["id"] == "ai_orchestrator"
    assert top["role"]["skill_level"] == "principal"
