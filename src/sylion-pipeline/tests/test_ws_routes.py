"""Tests for sylion.api.ws_routes module."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from sylion.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestWSStats:
    def test_ws_stats_returns_count(self, client):
        resp = client.get("/ws/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_connections" in data
        assert isinstance(data["active_connections"], int)


class TestWSEvents:
    def test_ws_connect_and_ping(self, client):
        with client.websocket_connect("/ws/events") as ws:
            ws.send_text(json.dumps({"action": "ping"}))
            msg = ws.receive_json()
            assert msg["action"] == "pong"

    def test_ws_subscribe(self, client):
        with client.websocket_connect("/ws/events") as ws:
            ws.send_text(json.dumps({"action": "subscribe", "topic": "module.*"}))
            msg = ws.receive_json()
            assert msg["action"] == "subscribed"
            assert msg["topic"] == "module.*"

    def test_ws_invalid_json(self, client):
        with client.websocket_connect("/ws/events") as ws:
            ws.send_text("not-json")
            msg = ws.receive_json()
            assert msg["error"] == "invalid json"

    def test_ws_stats_counts_connections(self, client):
        before = client.get("/ws/stats").json()["active_connections"]
        with client.websocket_connect("/ws/events") as ws:
            ws.send_text(json.dumps({"action": "ping"}))
            ws.receive_json()
            during = client.get("/ws/stats").json()["active_connections"]
            assert during >= before
        after = client.get("/ws/stats").json()["active_connections"]
        assert after == before


class TestWSOverview:
    def test_ws_overview_accepts_legacy_token_and_pings(self, client):
        with client.websocket_connect("/ws/overview?token=legacy") as ws:
            initial = ws.receive_json()
            assert initial["type"] == "overview"
            assert initial["status"] == "ok"
            assert initial["compatibility"]["canonical"] == "/ws/workspace"

            ws.send_text(json.dumps({"action": "ping"}))
            pong = ws.receive_json()
            assert pong["action"] == "pong"

    def test_ws_overview_sends_snapshot_on_request(self, client):
        with client.websocket_connect("/ws/overview") as ws:
            ws.receive_json()
            ws.send_text(json.dumps({"type": "snapshot"}))
            msg = ws.receive_json()
            assert msg["type"] == "overview"
            assert msg["websockets"]["events"] == "/ws/events"


class TestConnectionManager:
    def test_manager_singleton(self):
        from sylion.api.ws_routes import get_manager
        m1 = get_manager()
        m2 = get_manager()
        assert m1 is m2

    def test_manager_initial_count(self):
        from sylion.api.ws_routes import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.active_count == 0
