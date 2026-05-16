"""W7 Role Catalog tests.

Validates that:
- Every role declared in ``_index.yaml`` has a corresponding YAML manifest.
- Every role manifest parses cleanly into a ``Role`` dataclass.
- ``get_role`` / ``list_roles`` / ``list_categories`` behave as documented.
- The heuristic ``match_role_to_task`` ranks plausible roles for sample tasks.
- The REST routes (`/api/v1/role-catalog`) surface the catalog.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.skills.roles import (
    ROLE_REGISTRY,
    VALID_CATEGORIES,
    VALID_COST_PROFILES,
    Role,
    get_role,
    list_categories,
    list_roles,
    match_role_to_task,
)

_ROLES_DIR = Path(__file__).resolve().parents[2] / "sylion" / "skills" / "roles"
_INDEX_FILE = _ROLES_DIR / "_index.yaml"


def _load_router():
    routes_path = (
        Path(__file__).resolve().parents[2]
        / "sylion"
        / "api"
        / "role_catalog_routes.py"
    )
    spec = importlib.util.spec_from_file_location(
        "role_catalog_routes_test_module", routes_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(_load_router())
    return TestClient(app)


# ---------------------------------------------------------------------------
# Index + manifest integrity
# ---------------------------------------------------------------------------


def test_index_file_exists_and_parses() -> None:
    assert _INDEX_FILE.exists(), f"missing role index at {_INDEX_FILE}"
    payload = yaml.safe_load(_INDEX_FILE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert payload.get("roles"), "_index.yaml has no roles list"
    assert payload.get("categories"), "_index.yaml has no categories"


def test_every_index_role_has_manifest() -> None:
    payload = yaml.safe_load(_INDEX_FILE.read_text(encoding="utf-8"))
    role_entries = payload["roles"]
    assert isinstance(role_entries, list)
    for entry in role_entries:
        assert isinstance(entry, dict), entry
        filename = entry.get("file")
        assert filename, f"index entry missing 'file': {entry}"
        path = _ROLES_DIR / filename
        assert path.exists(), f"manifest file missing for {entry['id']}: {path}"


def test_every_manifest_parses_into_role() -> None:
    """Each *.yaml in roles/ (except _index.yaml) parses into a Role."""
    for path in _ROLES_DIR.glob("*.yaml"):
        if path.name.startswith("_"):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict), f"{path} did not parse into a dict"
        # The bootstrapper should have already validated this — sanity check.
        role = ROLE_REGISTRY.get(raw["id"])
        assert role is not None, f"role {raw['id']!r} not in registry"
        assert isinstance(role, Role)
        assert role.category in VALID_CATEGORIES
        assert role.cost_profile in VALID_COST_PROFILES
        assert role.system_prompt, f"role {role.id} has empty system_prompt"


def test_registry_contains_all_pdf_section_8_2_roles() -> None:
    """SYLION v2 PDF §8.2 lists these roles — all must exist."""
    expected = {
        # text
        "copywriter", "editor", "fact_checker", "translator",
        "ghostwriter", "technical_writer",
        # code
        "code_implementer", "code_reviewer", "refactorer", "debugger",
        "test_writer", "security_auditor",
        # visual
        "graphic_designer", "illustrator", "ui_designer",
        "photo_editor", "video_editor",
        # audio
        "composer", "sound_designer", "voiceover_artist", "transcriber",
        # strategy
        "researcher", "analyst", "strategist", "planner", "project_manager",
        # mobile
        "ios_specialist", "android_specialist", "react_native_specialist",
        # web
        "frontend_specialist", "backend_specialist", "fullstack_implementer",
        # domain
        "lawyer", "accountant", "scientist", "marketer",
        "sales", "customer_support",
    }
    missing = expected - set(ROLE_REGISTRY.keys())
    assert not missing, f"missing PDF §8.2 roles: {sorted(missing)}"


def test_registry_size_matches_index_total_roles() -> None:
    payload = yaml.safe_load(_INDEX_FILE.read_text(encoding="utf-8"))
    declared = payload.get("total_roles")
    assert declared is not None
    assert len(ROLE_REGISTRY) == declared, (
        f"_index.yaml total_roles={declared} but registry has "
        f"{len(ROLE_REGISTRY)} roles loaded"
    )


# ---------------------------------------------------------------------------
# get_role / list_roles / list_categories
# ---------------------------------------------------------------------------


def test_get_role_copywriter_returns_full_manifest() -> None:
    role = get_role("copywriter")
    assert role is not None
    assert role.id == "copywriter"
    assert role.category == "text"
    assert role.system_prompt
    assert role.preferred_models  # non-empty
    assert role.typical_tasks  # non-empty


def test_get_role_unknown_returns_none() -> None:
    assert get_role("does-not-exist") is None
    assert get_role("") is None


def test_list_roles_text_category_has_at_least_5() -> None:
    text_roles = list_roles(category="text")
    assert len(text_roles) >= 5
    ids = {r.id for r in text_roles}
    assert "copywriter" in ids
    assert "editor" in ids


def test_list_roles_no_filter_returns_all() -> None:
    assert len(list_roles()) == len(ROLE_REGISTRY)


def test_list_categories_returns_all_top_level_categories() -> None:
    cats = list_categories()
    cat_ids = {c["id"] for c in cats}
    expected_categories = {
        "text", "code", "visual", "audio",
        "strategy", "mobile", "web", "domain",
    }
    assert expected_categories.issubset(cat_ids)


# ---------------------------------------------------------------------------
# Heuristic matcher
# ---------------------------------------------------------------------------


def test_match_role_landing_page_includes_copywriter_top_3() -> None:
    matches = match_role_to_task(
        "napisz landing page dla SaaS produktywnościowego",
        available_models={"claude-opus-4-7", "gpt-4o"},
    )
    top_ids = [m.id for m in matches][:3]
    assert "copywriter" in top_ids, f"copywriter not in top 3: {top_ids}"


def test_match_role_security_audit_includes_security_auditor() -> None:
    matches = match_role_to_task(
        "Przeprowadź audyt bezpieczeństwa OWASP dla nowego REST API",
        available_models={"claude-opus-4-7"},
    )
    ids = [m.id for m in matches]
    assert "security_auditor" in ids


def test_match_role_empty_task_returns_empty() -> None:
    assert match_role_to_task("", available_models=set()) == []


def test_match_role_top_n_limits_results() -> None:
    matches = match_role_to_task(
        "ios swift android kotlin react native", top_n=2
    )
    assert len(matches) <= 2


# ---------------------------------------------------------------------------
# REST routes
# ---------------------------------------------------------------------------


def test_route_health(client: TestClient) -> None:
    resp = client.get("/api/v1/role-catalog/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "role_catalog"
    assert payload["total_roles"] == len(ROLE_REGISTRY)


def test_route_list_all_roles(client: TestClient) -> None:
    resp = client.get("/api/v1/role-catalog")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == len(ROLE_REGISTRY)
    assert any(r["id"] == "copywriter" for r in payload["roles"])


def test_route_list_roles_filtered_by_category(client: TestClient) -> None:
    resp = client.get("/api/v1/role-catalog", params={"category": "text"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["category"] == "text"
    assert all(r["category"] == "text" for r in payload["roles"])


def test_route_list_roles_unknown_category_400(client: TestClient) -> None:
    resp = client.get("/api/v1/role-catalog", params={"category": "nope"})
    assert resp.status_code == 400


def test_route_list_categories(client: TestClient) -> None:
    resp = client.get("/api/v1/role-catalog/categories")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] >= 8
    cat_ids = {c["id"] for c in payload["categories"]}
    assert "text" in cat_ids
    assert "code" in cat_ids


def test_route_get_role_by_id(client: TestClient) -> None:
    resp = client.get("/api/v1/role-catalog/copywriter")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["id"] == "copywriter"
    assert payload["category"] == "text"
    assert payload["system_prompt"]


def test_route_get_role_unknown_404(client: TestClient) -> None:
    resp = client.get("/api/v1/role-catalog/does-not-exist")
    assert resp.status_code == 404


def test_route_get_roles_by_category(client: TestClient) -> None:
    resp = client.get("/api/v1/role-catalog/category/text")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["category"] == "text"
    assert payload["total"] >= 5
    assert all(r["category"] == "text" for r in payload["roles"])


def test_route_match_landing_page(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/role-catalog/match",
        json={
            "task": "napisz landing page dla SaaS",
            "available_models": ["claude-opus-4-7", "gpt-4o"],
            "top_n": 5,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    match_ids = [m["id"] for m in payload["matches"]]
    assert "copywriter" in match_ids
    assert payload["engine"] == "heuristic-v0"


def test_route_match_validates_task_required(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/role-catalog/match",
        json={"task": "", "available_models": []},
    )
    # Empty string fails min_length=1 validation.
    assert resp.status_code == 422
