"""Tests for surface.ws_gateway module."""
import pytest
from sylion.surface.ws_gateway import WSGateway, get_ws_gateway
import sylion.surface.ws_gateway as mod


@pytest.fixture
def ws():
    mod._gateway = None
    return WSGateway()


class TestWSGateway:
    def test_connect(self, ws):
        result = ws.connect(user_id="user-1", client_id="client-1")
        assert result["status"] == "connected"
        assert "conn_id" in result

    def test_disconnect(self, ws):
        conn = ws.connect(user_id="user-2", client_id="client-2")
        result = ws.disconnect(conn["conn_id"])
        assert result["status"] == "disconnected"

    def test_subscribe(self, ws):
        conn = ws.connect(user_id="user-3", client_id="client-3")
        result = ws.subscribe(conn["conn_id"], ["events.decision.*"])
        assert conn["conn_id"] in result["conn_id"]
        assert "events.decision.*" in result["channels"]

    def test_broadcast(self, ws):
        c1 = ws.connect(user_id="u4", client_id="c4", channels=["test.*"])
        c2 = ws.connect(user_id="u5", client_id="c5", channels=["test.*"])
        result = ws.broadcast("test.*", {"data": "hello"})
        assert result["recipient_count"] >= 2

    def test_get_stats(self, ws):
        ws.connect(user_id="u6", client_id="c6")
        stats = ws.get_stats()
        assert stats["total_connections"] >= 1
        assert stats["active_connections"] >= 1
