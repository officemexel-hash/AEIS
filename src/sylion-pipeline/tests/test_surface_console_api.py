"""Tests for surface.console_api module."""
import pytest
from sylion.surface.console_api import ConsoleAPI, get_console_api


@pytest.fixture
def api():
    get_console_api.__code__.co_freevars
    import sylion.surface.console_api as mod
    mod._api = None
    return ConsoleAPI()


class TestConsoleAPI:
    def test_register_endpoint(self, api):
        result = api.register("/api/v1/test", "GET", handler="test_handler")
        assert "endpoint_id" in result
        assert result["path"] == "/api/v1/test"
        assert result["method"] == "GET"

    def test_record_request(self, api):
        ep = api.register("/api/v1/test", "GET")
        result = api.record_request(ep["endpoint_id"], user_id="u1", status_code=200, latency_ms=42)
        assert result["status_code"] == 200

    def test_get_endpoint(self, api):
        ep = api.register("/api/v1/test2", "POST", description="test desc")
        got = api.get_endpoint(ep["endpoint_id"])
        assert got is not None
        assert got["path"] == "/api/v1/test2"
        assert got["description"] == "test desc"

    def test_list_endpoints(self, api):
        api.register("/a", "GET")
        api.register("/b", "POST")
        eps = api.list_endpoints()
        assert len(eps) >= 2

    def test_get_stats(self, api):
        ep = api.register("/stats", "GET")
        api.record_request(ep["endpoint_id"], status_code=200)
        api.record_request(ep["endpoint_id"], status_code=404)
        stats = api.get_stats()
        assert stats["total_requests"] >= 2
        assert stats["active_endpoints"] >= 1

    def test_get_endpoint_not_found(self, api):
        assert api.get_endpoint("nonexistent") is None
