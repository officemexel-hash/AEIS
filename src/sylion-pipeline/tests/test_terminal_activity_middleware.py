from __future__ import annotations

import time

from fastapi.testclient import TestClient

from sylion.aeis_v2.terminal import replay
from sylion.api.app import app


client = TestClient(app)


def test_dashboard_api_call_is_recorded_in_terminal_replay(monkeypatch, tmp_path):
    monkeypatch.setattr(replay, "REPLAY_LOG_DIR", tmp_path / "terminal_replay")

    start = time.time() - 1
    response = client.get("/api/v1/ontology/types")
    end = time.time() + 1

    assert response.status_code == 200
    recorded = replay.get_replay_slice(start, end, layer="W15")
    messages = [event["message"] for event in recorded.events]

    assert any("GET /api/v1/ontology/types -> 200" in message for message in messages)
    assert all("sk-" not in message for message in messages)


def test_dashboard_activity_does_not_record_request_body_secrets(monkeypatch, tmp_path):
    monkeypatch.setattr(replay, "REPLAY_LOG_DIR", tmp_path / "terminal_replay")
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "terminal_activity.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))

    start = time.time() - 1
    response = client.post(
        "/api/v1/project-start/projects/create",
        json={
            "creation_path": "idea",
            "name": "Terminal Activity Secret Probe",
            "idea_text": "Local test only. Secret-shaped value sk-proj-test-leak-check must never appear in W18.",
            "customer_context": "Runtime observability test.",
            "deadline": "2026-06",
            "budget_hint_eur": 100,
            "template_id": "local_test",
        },
    )
    end = time.time() + 1

    assert response.status_code == 200
    recorded = replay.get_replay_slice(start, end, layer="AEIS")
    joined = "\n".join(event["message"] for event in recorded.events)

    assert "POST /api/v1/project-start/projects/create -> 200" in joined
    assert "sk-proj-test-leak-check" not in joined
    assert "Secret Probe" not in joined
