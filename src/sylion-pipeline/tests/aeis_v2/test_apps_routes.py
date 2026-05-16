"""W16 Apps Builder route tests.

The Apps Builder plane must expose a real registry: canonical templates,
persisted operator draft manifests, and per-app detail. Browser-only
success messages are not acceptable for the audit flow.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.api.apps_routes import router as apps_router


@pytest.fixture(autouse=True)
def _isolated_audit_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYLION_AUDIT_PROFILE_ID", f"pytest-apps-{uuid.uuid4().hex}")


def _client() -> TestClient:
    api = FastAPI()
    api.include_router(apps_router)
    return TestClient(api)


def test_get_apps_returns_canonical_templates_only_on_clean_start():
    client = _client()
    r = client.get("/api/v1/apps")
    assert r.status_code == 200
    body = r.json()
    assert body["created_count"] == 0
    assert body["template_count"] >= 5
    assert body["count"] == body["template_count"]
    ids = {app["id"] for app in body["apps"]}
    assert "inspection_field" in ids
    assert "approval_workflow" in ids


def test_get_apps_response_shape():
    client = _client()
    r = client.get("/api/v1/apps")
    assert r.status_code == 200
    apps = r.json()["apps"]
    expected_keys = {
        "id",
        "name",
        "description",
        "object_types",
        "widgets",
        "version",
        "source",
        "status",
        "template_id",
    }
    for entry in apps:
        assert expected_keys.issubset(entry.keys())
        assert entry["source"] == "canonical_template"
        assert entry["status"] == "available"
        assert isinstance(entry["object_types"], list)
        assert isinstance(entry["widgets"], list)
        assert len(entry["widgets"]) >= 3


def test_get_apps_health_returns_storage_status():
    client = _client()
    r = client.get("/api/v1/apps/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["storage"] == "sqlite"
    assert body["created_count"] == 0
    assert body["template_count"] >= 5
    assert "inspection_field" in body["template_ids"]


def test_get_template_by_id_returns_manifest():
    client = _client()
    r = client.get("/api/v1/apps/inspection_field")
    assert r.status_code == 200
    body = r.json()
    assert body["app"]["id"] == "inspection_field"
    assert body["manifest"]["schema_version"] == "w16.app_manifest.v1"
    assert body["manifest"]["template_id"] == "inspection_field"


def test_create_app_from_template_persists_draft_manifest():
    client = _client()
    r = client.post(
        "/api/v1/apps/from-template",
        json={
            "template_id": "inspection_field",
            "idea_text": "inspekcja terenowa raport audyt",
            "operator_id": "operator-main",
        },
    )
    assert r.status_code == 201
    body = r.json()
    app_id = body["app"]["id"]
    assert app_id.startswith("app_inspection_field_")
    assert body["app"]["status"] == "draft_manifest"
    assert body["manifest"]["idea_text"] == "inspekcja terenowa raport audyt"

    listed = client.get("/api/v1/apps").json()
    assert listed["created_count"] == 1
    assert listed["apps"][0]["id"] == app_id

    detail = client.get(f"/api/v1/apps/{app_id}")
    assert detail.status_code == 200
    assert detail.json()["manifest"]["app_id"] == app_id


def test_create_app_from_missing_template_returns_404():
    client = _client()
    r = client.post(
        "/api/v1/apps/from-template",
        json={"template_id": "missing-template", "operator_id": "operator-main"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "template not found"


def test_match_idea_returns_top_n_matches():
    client = _client()
    r = client.post(
        "/api/v1/apps/match-idea",
        json={
            "idea_text": "inspekcja terenowa raport audyt monitorowanie",
            "top_n": 5,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["phase"] == "template_matching"
    assert body["method_used"] == "tag_overlap"
    assert body["match_count"] == len(body["matches"])
    assert body["match_count"] >= 1
    first = body["matches"][0]
    assert "template" in first
    assert "score" in first and 0.0 <= first["score"] <= 1.0
    assert first["method"] == "tag_overlap"
    assert "reason_pl" in first


def test_match_idea_handles_natural_polish_inflections():
    client = _client()
    r = client.post(
        "/api/v1/apps/match-idea",
        json={
            "idea_text": (
                "Chce aplikacje do inspekcji terenowych z raportami audytu, "
                "zdjeciami i monitorowaniem zasobow."
            ),
            "top_n": 3,
        },
    )
    assert r.status_code == 200
    body = r.json()
    ids = [item["template"]["id"] for item in body["matches"]]
    assert "inspection_field" in ids


def test_match_idea_empty_text_returns_422():
    client = _client()
    r = client.post("/api/v1/apps/match-idea", json={"idea_text": ""})
    assert r.status_code == 422


def test_match_idea_too_long_returns_422():
    client = _client()
    r = client.post(
        "/api/v1/apps/match-idea",
        json={"idea_text": "a" * 2001},
    )
    assert r.status_code == 422


def test_match_idea_default_top_n_is_3():
    client = _client()
    r = client.post(
        "/api/v1/apps/match-idea",
        json={
            "idea_text": (
                "raporty inspekcja audyt magazyn serwis konserwacja "
                "zatwierdzanie dokumenty workflow ewidencja czas-pracy"
            ),
        },
    )
    assert r.status_code == 200
    assert r.json()["match_count"] <= 3

    r_high = client.post(
        "/api/v1/apps/match-idea",
        json={"idea_text": "inspekcja", "top_n": 11},
    )
    assert r_high.status_code == 422
    r_low = client.post(
        "/api/v1/apps/match-idea",
        json={"idea_text": "inspekcja", "top_n": 0},
    )
    assert r_low.status_code == 422
