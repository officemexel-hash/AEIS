from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sylion.api.app import app
from sylion.memory.obsidian_sync import ObsidianMemorySync


client = TestClient(app)
PROJECT_BASE = "/api/v1/project-start"
EXECUTION_BASE = "/api/v1/execution-start"


def _project(project_id: str, *, state: str = "CLOSED", domain: str = "crm") -> dict:
    return {
        "project_id": project_id,
        "name": f"{project_id} title",
        "state": state,
        "idea_text": "Local AEIS project with durable memory reuse and closure evidence.",
        "classification": {
            "domain": domain,
            "project_type": "internal_app",
            "d_level_label": "D3",
            "detected_signals": ["memory", domain],
        },
        "scope": {"in_scope": ["memory sync"], "constraints": ["local only"]},
        "goals": {"summary": "Persist closure lessons for reuse."},
        "planning": {"status": "complete"},
        "execution": {
            "project_closure": {
                "calibration": {"learnings": ["Reuse local CRM acceptance checks"]},
                "artifacts": {
                    "operator_report": {
                        "path": f"reports/{project_id}.md",
                        "sha256": "abc",
                    }
                },
            }
        },
    }


def test_obsidian_sync_writes_note_evidence_tags_and_status(tmp_path: Path) -> None:
    sync = ObsidianMemorySync(tmp_path / "vault")

    result = sync.sync_project(_project("proj_memory_alpha"), source="pytest")

    note = Path(result["note_path"])
    evidence = Path(result["evidence_path"])
    assert note.exists()
    assert evidence.exists()
    text = note.read_text(encoding="utf-8")
    assert "# proj_memory_alpha title" in text.lower()
    assert "#domain-crm" in text
    assert "Evidence hash" in text
    status = sync.status("proj_memory_alpha")
    assert status["synced"] is True
    assert status["note_sha256"] == result["note_sha256"]


def test_obsidian_graph_exposes_backlinks_between_related_projects(tmp_path: Path) -> None:
    sync = ObsidianMemorySync(tmp_path / "vault")
    sync.sync_project(_project("proj_memory_a"), source="pytest")

    result = sync.sync_project(
        _project("proj_memory_b"),
        related_projects=[{"project_id": "proj_memory_a", "title": "Alpha memory"}],
        source="pytest",
    )

    note_text = Path(result["note_path"]).read_text(encoding="utf-8")
    graph = sync.graph()
    assert "[[proj_memory_a|Alpha memory]]" in note_text
    assert {"source": "proj_memory_b", "target": "proj_memory_a", "type": "obsidian_backlink"} in graph["edges"]
    assert graph["counts"]["nodes"] == 2
    assert graph["counts"]["edges"] >= 1


def test_obsidian_sync_rejects_open_project_without_force(tmp_path: Path) -> None:
    sync = ObsidianMemorySync(tmp_path / "vault")

    try:
        sync.sync_project(_project("proj_open", state="DEPLOYED"), source="pytest")
    except ValueError as exc:
        assert "only CLOSED projects" in str(exc)
    else:
        raise AssertionError("open project sync should fail")


def test_phase41_auto_syncs_closed_project_to_obsidian(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "phase41.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("SYLION_OBSIDIAN_VAULT_ROOT", str(tmp_path / "obsidian_vault"))

    created = client.post(
        f"{PROJECT_BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "P1 Memory Closure",
            "idea_text": "Local CRM memory project without payments, without external deploy, with closure lessons.",
            "customer_context": "Operator local test.",
            "deadline": "2026-06",
            "budget_hint_eur": 300,
            "template_id": "polish_saas_payment",
        },
    )
    assert created.status_code == 200
    project = created.json()["project"]
    project["state"] = "DEPLOYED"

    from sylion.api.project_start_routes import _save_project

    _save_project(project)

    closed = client.post(
        f"{EXECUTION_BASE}/projects/{project['project_id']}/phase41/close-project",
        json={
            "approved": True,
            "operator_id": "operator",
            "closed_date": "2026-06-27",
            "warranty_start": "2026-06-27",
            "warranty_end": "2026-07-27",
        },
    )
    assert closed.status_code == 200
    payload = closed.json()
    sync_result = payload["project"]["execution"]["project_closure"]["long_horizon_memory"]
    assert sync_result["status"] == "synced"
    assert Path(sync_result["note_path"]).exists()
    assert payload["acceptance"]["accepted"] is True
    assert any(item["id"] == "long_horizon_memory" and item["status"] == "pass" for item in payload["acceptance"]["checks"])


def test_obsidian_api_status_graph_and_manual_sync(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("SYLION_OBSIDIAN_VAULT_ROOT", str(tmp_path / "vault"))

    created = client.post(
        f"{PROJECT_BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "P1 Memory API",
            "idea_text": "Local memory API project, no payments, no VPS.",
            "customer_context": "Operator local test.",
            "deadline": "2026-06",
            "budget_hint_eur": 300,
            "template_id": "polish_saas_payment",
        },
    )
    assert created.status_code == 200
    project = created.json()["project"]
    project["state"] = "CLOSED"

    from sylion.api.project_start_routes import _save_project

    _save_project(project)

    status_before = client.get(f"/api/v1/memory/obsidian/status?project_id={project['project_id']}")
    assert status_before.status_code == 200
    assert status_before.json()["synced"] is False

    synced = client.post(
        "/api/v1/memory/obsidian/sync",
        json={"project_id": project["project_id"], "related_project_ids": [], "source": "pytest_api"},
    )
    assert synced.status_code == 200
    assert synced.json()["status"] == "synced"

    graph = client.get("/api/v1/memory/obsidian/graph")
    assert graph.status_code == 200
    assert graph.json()["counts"]["nodes"] >= 1
