from fastapi.testclient import TestClient

from sylion.api.app import app
from sylion.memory import bootstrap, get_memory_plane, search, write
from sylion.memory.evidence_store import reset_evidence_store
from sylion.memory.indexer import reset_indexer
from sylion.memory.plane import MemoryPlane, reset_memory_plane
from sylion.memory.retrieval import reset_retrieval
from sylion.memory.self_model_store import reset_self_model_store


client = TestClient(app)


def _reset_all() -> None:
    reset_memory_plane()
    reset_indexer()
    reset_evidence_store()
    reset_retrieval()
    reset_self_model_store()


def test_memory_plane_write_creates_evidence_and_project_scoped_search(tmp_path):
    plane = MemoryPlane(db_path=tmp_path / "memory.sqlite")

    first = plane.write(
        content="Alpha deployment rollback plan for project A",
        project_id="project-a",
        provenance={"source": "operator_dashboard", "flow": "W10"},
        created_by="operator@example.com",
        metadata={"decision_class": "D3"},
    )
    second = plane.write(
        content="Alpha funding application notes for project B",
        project_id="project-b",
        provenance={"source": "funding_module", "flow": "K2"},
        created_by="operator@example.com",
    )

    assert first["entry_id"].startswith("mem_")
    assert first["evidence_id"].startswith("ev_")
    assert first["provenance"]["source"] == "operator_dashboard"
    assert first["metadata"]["decision_class"] == "D3"
    assert first["content_hash"]

    artifact = plane._evidence_spine.get_artifact(first["evidence_id"])
    assert artifact is not None
    assert artifact["source"] == "memory_plane"
    assert artifact["artifact_type"] == "memory_entry"

    hits_a = plane.search("alpha project", limit=10, project_id="project-a")
    assert [item["entry_id"] for item in hits_a] == [first["entry_id"]]

    hits_b = plane.search("alpha project", limit=10, project_id="project-b")
    assert [item["entry_id"] for item in hits_b] == [second["entry_id"]]

    project_entries = plane.list_project("project-a")
    assert [item["entry_id"] for item in project_entries] == [first["entry_id"]]


def test_memory_plane_requires_provenance_source(tmp_path):
    plane = MemoryPlane(db_path=tmp_path / "memory.sqlite")

    try:
        plane.write(content="No source", provenance={}, project_id="project-a")
    except ValueError as exc:
        assert "provenance.source" in str(exc)
    else:
        raise AssertionError("MemoryPlane accepted a write without provenance.source")


def test_memory_public_hooks_use_canonical_plane(tmp_path):
    _reset_all()
    bootstrap({"db_path": tmp_path / "memory.sqlite"})

    entry = write(
        content="Canonical public hook memory entry",
        project_id="project-hook",
        provenance={"source": "public_hook_test"},
        created_by="tester",
    )

    assert get_memory_plane().get(entry["entry_id"])["evidence_id"] == entry["evidence_id"]
    assert [item["entry_id"] for item in search("canonical", project_id="project-hook")] == [entry["entry_id"]]

    _reset_all()


def test_memory_plane_routes_write_search_and_fetch():
    _reset_all()

    response = client.post(
        "/api/v1/memory/plane/write",
        json={
            "content": "Route memory entry for project route-a",
            "project_id": "route-a",
            "provenance": {"source": "api_test", "flow": "memory_plane"},
            "created_by": "operator@example.com",
            "metadata": {"scope": "route"},
        },
    )
    assert response.status_code == 201
    entry = response.json()
    assert entry["evidence_id"].startswith("ev_")
    assert entry["project_id"] == "route-a"

    search_response = client.get(
        "/api/v1/memory/plane/search",
        params={"query": "route memory", "project_id": "route-a"},
    )
    assert search_response.status_code == 200
    assert [item["entry_id"] for item in search_response.json()["results"]] == [entry["entry_id"]]

    project_response = client.get("/api/v1/memory/plane/projects/route-a")
    assert project_response.status_code == 200
    assert [item["entry_id"] for item in project_response.json()["entries"]] == [entry["entry_id"]]

    fetch_response = client.get(f"/api/v1/memory/plane/entries/{entry['entry_id']}")
    assert fetch_response.status_code == 200
    assert fetch_response.json()["provenance"]["source"] == "api_test"

    stats_response = client.get("/api/v1/memory/plane/stats")
    assert stats_response.status_code == 200
    assert stats_response.json()["total_entries"] >= 1

    _reset_all()
