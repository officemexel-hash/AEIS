"""Tests for sylion.security.bootstrap_init module."""

import pytest

from sylion.security.bootstrap_init import BootstrapInit, BootstrapState


class TestBootstrapState:
    def test_auto_timestamp(self):
        s = BootstrapState(key="test", value="val")
        assert s.updated_at > 0

    def test_custom_values(self):
        s = BootstrapState(key="k", value="v", updated_at=100.0)
        assert s.key == "k"
        assert s.value == "v"
        assert s.updated_at == 100.0


class TestBootstrapInit:
    @pytest.fixture
    def bootstrap(self):
        return BootstrapInit()

    def test_bootstrap_without_provider_skips(self, bootstrap):
        result = bootstrap.bootstrap()
        assert result["status"] == "skipped"
        assert result["reason"] == "no auth_provider"

    def test_get_status_not_bootstrapped(self, bootstrap):
        status = bootstrap.get_status()
        assert status["status"] == "not_bootstrapped"

    def test_reset(self, bootstrap):
        result = bootstrap.reset()
        assert result is True

    def test_bootstrap_with_mock_provider(self):
        class MockProvider:
            def __init__(self):
                self.users = []
                self.sessions = []
                self._conn = type("C", (), {"execute": lambda s, q, p=None: type("R", (), {"__getitem__": lambda s, k: 0})()})()

            def list_users(self, active_only=False):
                return self.users

            def create_user(self, **kwargs):
                self.users.append(kwargs)

            def create_session(self, **kwargs):
                self.sessions.append(kwargs)

        provider = MockProvider()
        bi = BootstrapInit(auth_provider=provider)
        result = bi.bootstrap()
        assert result["status"] == "completed"
        assert "admin" in result["created_users"]
        assert "viewer" in result["created_users"]
        assert result["created_session"] is True

    def test_bootstrap_idempotent(self):
        class MockProvider:
            def __init__(self):
                self.users = [{"user_id": "existing"}]
                self.sessions = [{"token": "existing"}]
                self._conn = type("C", (), {"execute": lambda s, q, p=None: type("R", (), {"__getitem__": lambda s, k: 1, "fetchone": lambda s: type("R2", (), {"__getitem__": lambda s, k: 1})()})()})()

            def list_users(self, active_only=False):
                return self.users

        provider = MockProvider()
        bi = BootstrapInit(auth_provider=provider)
        result = bi.bootstrap()
        assert result["status"] == "completed"
        assert result["created_users"] == []

    def test_get_status_after_bootstrap(self):
        class MockProvider:
            def __init__(self):
                self.users = []
                self._conn = type("C", (), {"execute": lambda s, q, p=None: type("R", (), {"__getitem__": lambda s, k: 0})()})()
            def list_users(self, **kw): return self.users
            def create_user(self, **kw): self.users.append(kw)
            def create_session(self, **kw): pass

        bi = BootstrapInit(auth_provider=MockProvider())
        bi.bootstrap()
        status = bi.get_status()
        assert "value" in status
        assert status["value"]["created_users"] == ["admin", "viewer"]

    def test_reset_clears_status(self):
        class MockProvider:
            def __init__(self):
                self.users = []
                self._conn = type("C", (), {"execute": lambda s, q, p=None: type("R", (), {"__getitem__": lambda s, k: 0})()})()
            def list_users(self, **kw): return self.users
            def create_user(self, **kw): self.users.append(kw)
            def create_session(self, **kw): pass

        bi = BootstrapInit(auth_provider=MockProvider())
        bi.bootstrap()
        bi.reset()
        status = bi.get_status()
        assert status["status"] == "not_bootstrapped"
