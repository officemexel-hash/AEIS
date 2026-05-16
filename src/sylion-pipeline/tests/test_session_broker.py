"""Tests for sylion.security.session_broker — SessionBroker."""

import json
import threading
import time

import pytest

from sylion.security.session_broker import SessionBroker, get_session_broker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_broker() -> SessionBroker:
    return SessionBroker(db_path=":memory:")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSessionBrokerCreate:
    def test_create_session_basic(self):
        broker = _make_broker()
        result = broker.create("sess-1", "user-1", "tok-1")
        assert result["session_id"] == "sess-1"
        assert result["user_id"] == "user-1"
        assert result["token"] == "tok-1"
        assert result["timeout_seconds"] == 3600
        assert "created_at" in result

    def test_create_session_with_timeout(self):
        broker = _make_broker()
        result = broker.create("sess-2", "user-1", "tok-2", timeout=7200)
        assert result["timeout_seconds"] == 7200

    def test_create_session_with_metadata(self):
        broker = _make_broker()
        result = broker.create("sess-3", "user-1", "tok-3", metadata={"role": "admin"})
        assert result["session_id"] == "sess-3"

    def test_create_session_auto_id(self):
        broker = _make_broker()
        result = broker.create("", "user-1", "tok-4")
        assert result["session_id"] != ""

    def test_create_session_with_ip(self):
        broker = _make_broker()
        result = broker.create("sess-5", "user-1", "tok-5", ip_address="10.0.0.1")
        assert result["ip_address"] == "10.0.0.1"


class TestSessionBrokerValidate:
    def test_validate_valid_session(self):
        broker = _make_broker()
        broker.create("sess-1", "user-1", "tok-1")
        result = broker.validate("sess-1")
        assert result is not None
        assert result["session_id"] == "sess-1"

    def test_validate_nonexistent(self):
        broker = _make_broker()
        result = broker.validate("nonexistent")
        assert result is None

    def test_validate_updates_last_activity(self):
        broker = _make_broker()
        broker.create("sess-1", "user-1", "tok-1")
        time.sleep(0.01)
        result = broker.validate("sess-1")
        assert result is not None
        assert result["last_activity"] >= result["created_at"]

    def test_validate_expired_session(self):
        broker = _make_broker()
        # Create a session with 1 second timeout
        broker.create("sess-exp", "user-1", "tok-exp", timeout=1)
        # Manually expire it by setting last_activity far in the past
        broker._conn.execute(
            "UPDATE managed_sessions SET last_activity = ? WHERE session_id = ?",
            (time.time() - 100, "sess-exp"),
        )
        broker._conn.commit()
        result = broker.validate("sess-exp")
        assert result is None


class TestSessionBrokerRefresh:
    def test_refresh_existing(self):
        broker = _make_broker()
        broker.create("sess-1", "user-1", "tok-1")
        ok = broker.refresh("sess-1")
        assert ok is True

    def test_refresh_nonexistent(self):
        broker = _make_broker()
        ok = broker.refresh("nonexistent")
        assert ok is False


class TestSessionBrokerDestroy:
    def test_destroy_existing(self):
        broker = _make_broker()
        broker.create("sess-1", "user-1", "tok-1")
        ok = broker.destroy("sess-1")
        assert ok is True
        assert broker.validate("sess-1") is None

    def test_destroy_nonexistent(self):
        broker = _make_broker()
        ok = broker.destroy("nonexistent")
        assert ok is False


class TestSessionBrokerList:
    def test_list_all_sessions(self):
        broker = _make_broker()
        broker.create("s1", "u1", "t1")
        broker.create("s2", "u2", "t2")
        sessions = broker.list_sessions()
        assert len(sessions) == 2

    def test_list_by_user(self):
        broker = _make_broker()
        broker.create("s1", "u1", "t1")
        broker.create("s2", "u2", "t2")
        broker.create("s3", "u1", "t3")
        sessions = broker.list_sessions(user_id="u1")
        assert len(sessions) == 2
        assert all(s["user_id"] == "u1" for s in sessions)

    def test_list_empty(self):
        broker = _make_broker()
        sessions = broker.list_sessions()
        assert sessions == []

    def test_list_parses_metadata(self):
        broker = _make_broker()
        broker.create("s1", "u1", "t1", metadata={"role": "admin"})
        sessions = broker.list_sessions()
        assert sessions[0]["metadata"] == {"role": "admin"}


class TestSessionBrokerCleanup:
    def test_cleanup_removes_expired(self):
        broker = _make_broker()
        broker.create("s1", "u1", "t1", timeout=3600)
        # Manually expire one
        broker.create("s2", "u2", "t2", timeout=1)
        broker._conn.execute(
            "UPDATE managed_sessions SET last_activity = ? WHERE session_id = ?",
            (time.time() - 100, "s2"),
        )
        broker._conn.commit()
        removed = broker.cleanup_expired()
        assert removed == 1
        assert broker.validate("s1") is not None

    def test_cleanup_none_expired(self):
        broker = _make_broker()
        broker.create("s1", "u1", "t1")
        removed = broker.cleanup_expired()
        assert removed == 0


class TestSessionBrokerStats:
    def test_stats_empty(self):
        broker = _make_broker()
        stats = broker.get_stats()
        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0
        assert stats["expired_sessions"] == 0

    def test_stats_with_sessions(self):
        broker = _make_broker()
        broker.create("s1", "u1", "t1")
        broker.create("s2", "u1", "t2")
        broker.create("s3", "u2", "t3")
        stats = broker.get_stats()
        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 3
        assert "u1" in stats["by_user"]
        assert stats["by_user"]["u1"] == 2

    def test_stats_with_expired(self):
        broker = _make_broker()
        broker.create("s1", "u1", "t1", timeout=1)
        broker._conn.execute(
            "UPDATE managed_sessions SET last_activity = ? WHERE session_id = ?",
            (time.time() - 100, "s1"),
        )
        broker._conn.commit()
        stats = broker.get_stats()
        assert stats["expired_sessions"] == 1
        assert stats["active_sessions"] == 0


class TestSessionBrokerSingleton:
    def test_get_session_broker_returns_instance(self):
        # Reset singleton
        import sylion.security.session_broker as mod
        mod._broker = None
        broker = get_session_broker(db_path=":memory:")
        assert isinstance(broker, SessionBroker)
        mod._broker = None


class TestSessionBrokerConcurrency:
    def test_concurrent_creates(self):
        broker = _make_broker()
        errors = []

        def create_session(i):
            try:
                broker.create(f"s-{i}", f"u-{i}", f"t-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_session, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        sessions = broker.list_sessions()
        assert len(sessions) == 20
