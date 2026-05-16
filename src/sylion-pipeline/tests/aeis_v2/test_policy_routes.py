"""W19 Policy / Security Plane — Phase 0 route tests.

Covers the read-only catalogue + permissive evaluator stub exposed under
``/api/v1/policy``:

- ``GET  /api/v1/policy/policies``              → list 4 hardcoded demo
                                                   policies.
- ``GET  /api/v1/policy/health``                → smoke endpoint, registry
                                                   size + ids.
- ``GET  /api/v1/policy/policies/{policy_id}``  → match by id or 404.
- ``POST /api/v1/policy/evaluate``              → Phase 0 always-allow stub.

The tests intentionally avoid loading the full app fixture state
(databases, lifespan); each test mounts the W19 router on a fresh
``FastAPI()`` instance via ``app.include_router(...)`` to keep them fast
and decoupled from the PG-backed tests in ``test_ontology_*``. Mirrors
the W16 ``test_apps_routes.py`` structure (committed in 702c62de).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.api.policy_routes import router as policy_router


def _client() -> TestClient:
    """Return a TestClient with only the W19 router mounted (no lifespan)."""
    api = FastAPI()
    api.include_router(policy_router)
    return TestClient(api)


# --------------------------------------------------------------------------
# GET /api/v1/policy/policies
# --------------------------------------------------------------------------


def test_get_policies_returns_4_demo_policies():
    """List endpoint returns the 4 hardcoded Phase 0 demo policies."""
    client = _client()
    r = client.get("/api/v1/policy/policies")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 4
    assert len(body["policies"]) == 4
    ids = {policy["id"] for policy in body["policies"]}
    assert ids == {
        "data_locality_eu",
        "cost_cap_per_decision",
        "rbac_operator_only_mutations",
        "audit_required_for_external_models",
    }


def test_get_policies_response_shape():
    """Each policy entry must carry the documented Phase 0 keys."""
    client = _client()
    r = client.get("/api/v1/policy/policies")
    assert r.status_code == 200
    policies = r.json()["policies"]
    expected_keys = {
        "id",
        "name",
        "description",
        "category",
        "scope",
        "evaluation_mode",
        "version",
    }
    for entry in policies:
        assert expected_keys.issubset(entry.keys()), (
            f"policy {entry.get('id')!r} missing keys: "
            f"{expected_keys - entry.keys()}"
        )
        assert entry["category"] in {"privacy", "cost_control", "rbac", "audit"}
        assert entry["scope"] in {"global", "decision", "node"}
        assert entry["evaluation_mode"] in {"deny_on_violation", "warn", "log_only"}
        assert entry["version"] == "0.1.0"


# --------------------------------------------------------------------------
# GET /api/v1/policy/policies/{policy_id}
# --------------------------------------------------------------------------


def test_get_policy_by_id_returns_match():
    """Per-policy detail returns the matching catalogue entry verbatim."""
    client = _client()
    r = client.get("/api/v1/policy/policies/data_locality_eu")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "data_locality_eu"
    assert body["name"] == "Dane w UE"
    assert body["category"] == "privacy"
    assert body["scope"] == "global"
    assert body["evaluation_mode"] == "deny_on_violation"


def test_get_policy_by_id_returns_404_on_unknown():
    """Unknown policy ids yield a structured 404 with the catalogue listing."""
    client = _client()
    r = client.get("/api/v1/policy/policies/not_a_real_policy")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["policy_id"] == "not_a_real_policy"
    # Detail is structured (not a bare string) so the operator UI can
    # branch on the available_ids list rather than parsing the message.
    assert "available_ids" in detail
    assert "data_locality_eu" in detail["available_ids"]


# --------------------------------------------------------------------------
# POST /api/v1/policy/evaluate
# --------------------------------------------------------------------------


def test_post_evaluate_returns_phase0_allow():
    """Phase 0 evaluator always returns ``allow`` and tags the reason."""
    client = _client()
    r = client.post(
        "/api/v1/policy/evaluate",
        json={
            "policy_id": "rbac_operator_only_mutations",
            "context": {"actor": "admin", "action": "POST"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "allow"
    assert body["policy_id"] == "rbac_operator_only_mutations"
    assert "Phase 0" in body["reason"]
