"""Tests for sylion.core.nats_health module."""

import pytest

from sylion.core.nats_health import check_nats_health


class TestNatsHealth:
    def test_check_returns_dict(self):
        result = check_nats_health("nats://localhost:4222")
        assert isinstance(result, dict)
        assert "connected" in result

    def test_check_not_connected_on_bad_url(self):
        result = check_nats_health("nats://nonexistent:4222")
        assert result["connected"] is False

    def test_check_has_server_id(self):
        result = check_nats_health("nats://localhost:4222")
        assert "server_id" in result

    def test_check_has_cluster(self):
        result = check_nats_health("nats://localhost:4222")
        assert "cluster" in result

    def test_check_has_streams_count(self):
        result = check_nats_health("nats://localhost:4222")
        assert "streams_count" in result

    def test_check_has_error_when_not_connected(self):
        result = check_nats_health("nats://nonexistent:4222")
        assert "error" in result or result["connected"] is False
