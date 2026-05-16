"""
Tests for sylion.security.phantom_wrapper -- PhantomWrapper

Covers session creation, validation, operation recording, revocation,
listing, stats, TTL expiry, scope enforcement, EventBus integration,
singleton, and concurrency.
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.phantom_wrapper import (
    DEFAULT_TTL_SECONDS,
    PhantomWrapper,
    get_phantom_wrapper,
    reset_phantom_wrapper,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wrapper(event_bus: EventBus | None = None) -> PhantomWrapper:
    return PhantomWrapper(db_path=":memory:", event_bus=event_bus)


def _make_session(wrapper: PhantomWrapper, user_id: str = "user1",
                  scope: str = "", ttl: int = 3600) -> dict:
    return wrapper.create_session(user_id, scope, ttl)


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    def test_default_ttl(self):
        assert DEFAULT_TTL_SECONDS == 3600


# ===========================================================================
# 2. Session creation
# ===========================================================================


class TestCreateSession:
    def test_basic_create(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1")
        assert s["session_id"] != ""
        assert s["user_id"] == "user1"
        assert s["is_active"] == 1
        assert s["created_at"] > 0
        assert s["expires_at"] > s["created_at"]

    def test_with_scope(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1", scope="read,write")
        assert s["scope"] == "read,write"

    def test_custom_ttl(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1", ttl_seconds=300)
        assert s["ttl_seconds"] == 300
        ttl = s["expires_at"] - s["created_at"]
        assert abs(ttl - 300) < 1

    def test_default_ttl(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1")
        ttl = s["expires_at"] - s["created_at"]
        assert abs(ttl - DEFAULT_TTL_SECONDS) < 1

    def test_unique_session_ids(self):
        wrapper = _make_wrapper()
        s1 = wrapper.create_session("u1")
        s2 = wrapper.create_session("u1")
        assert s1["session_id"] != s2["session_id"]


# ===========================================================================
# 3. Session validation
# ===========================================================================


class TestValidateSession:
    def test_valid_session(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        result = wrapper.validate_session(s["session_id"])
        assert result["allowed"] is True
        assert result["reason"] == "valid"

    def test_nonexistent_session(self):
        wrapper = _make_wrapper()
        result = wrapper.validate_session("nope")
        assert result["allowed"] is False
        assert "not found" in result["reason"]

    def test_revoked_session(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        wrapper.revoke_session(s["session_id"])
        result = wrapper.validate_session(s["session_id"])
        assert result["allowed"] is False
        assert "revoked" in result["reason"]

    def test_expired_session(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1", ttl_seconds=1)
        # Force expire
        wrapper._conn.execute(
            "UPDATE phantom_sessions SET expires_at = ? WHERE session_id = ?",
            (time.time() - 10, s["session_id"]),
        )
        wrapper._conn.commit()
        result = wrapper.validate_session(s["session_id"])
        assert result["allowed"] is False
        assert "expired" in result["reason"]

    def test_scope_allowed(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1", scope="read,write")
        result = wrapper.validate_session(s["session_id"], "read")
        assert result["allowed"] is True

    def test_scope_denied(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1", scope="read,write")
        result = wrapper.validate_session(s["session_id"], "delete")
        assert result["allowed"] is False
        assert "not in scope" in result["reason"]

    def test_empty_scope_allows_all(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1", scope="")
        result = wrapper.validate_session(s["session_id"], "anything")
        assert result["allowed"] is True

    def test_session_data_returned(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        result = wrapper.validate_session(s["session_id"])
        assert result["session"] is not None
        assert result["session"]["user_id"] == "user1"


# ===========================================================================
# 4. Operation recording
# ===========================================================================


class TestRecordOperation:
    def test_basic_record(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        op = wrapper.record_operation(s["session_id"], "read", "/data", "ok")
        assert op["op_id"] != ""
        assert op["session_id"] == s["session_id"]
        assert op["operation"] == "read"
        assert op["resource"] == "/data"
        assert op["result"] == "ok"
        assert op["timestamp"] > 0

    def test_record_with_scope(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1", scope="read")
        op = wrapper.record_operation(s["session_id"], "read", "/file")
        assert op["operation"] == "read"

    def test_record_out_of_scope_raises(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1", scope="read")
        with pytest.raises(ValueError, match="not in scope"):
            wrapper.record_operation(s["session_id"], "delete", "/file")

    def test_record_on_expired_raises(self):
        wrapper = _make_wrapper()
        s = wrapper.create_session("user1", ttl_seconds=1)
        wrapper._conn.execute(
            "UPDATE phantom_sessions SET expires_at = ? WHERE session_id = ?",
            (time.time() - 10, s["session_id"]),
        )
        wrapper._conn.commit()
        with pytest.raises(ValueError, match="expired"):
            wrapper.record_operation(s["session_id"], "read")

    def test_record_on_revoked_raises(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        wrapper.revoke_session(s["session_id"])
        with pytest.raises(ValueError, match="revoked"):
            wrapper.record_operation(s["session_id"], "read")

    def test_record_on_nonexistent_raises(self):
        wrapper = _make_wrapper()
        with pytest.raises(ValueError, match="not found"):
            wrapper.record_operation("nope", "read")


# ===========================================================================
# 5. Session revocation
# ===========================================================================


class TestRevokeSession:
    def test_revoke_active(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        assert wrapper.revoke_session(s["session_id"]) is True

    def test_revoke_already_revoked(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        wrapper.revoke_session(s["session_id"])
        assert wrapper.revoke_session(s["session_id"]) is False

    def test_revoke_nonexistent(self):
        wrapper = _make_wrapper()
        assert wrapper.revoke_session("nope") is False


# ===========================================================================
# 6. Session retrieval
# ===========================================================================


class TestGetSession:
    def test_get_existing(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        fetched = wrapper.get_session(s["session_id"])
        assert fetched is not None
        assert fetched["user_id"] == "user1"

    def test_get_nonexistent(self):
        wrapper = _make_wrapper()
        assert wrapper.get_session("nope") is None


# ===========================================================================
# 7. Session listing
# ===========================================================================


class TestListSessions:
    def test_list_all(self):
        wrapper = _make_wrapper()
        wrapper.create_session("u1")
        wrapper.create_session("u2")
        sessions = wrapper.list_sessions()
        assert len(sessions) == 2

    def test_filter_by_user(self):
        wrapper = _make_wrapper()
        wrapper.create_session("u1")
        wrapper.create_session("u2")
        result = wrapper.list_sessions(user_id="u1")
        assert len(result) == 1
        assert result[0]["user_id"] == "u1"

    def test_filter_by_active(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        wrapper.revoke_session(s["session_id"])
        active = wrapper.list_sessions(is_active=1)
        assert len(active) == 0
        inactive = wrapper.list_sessions(is_active=0)
        assert len(inactive) == 1

    def test_filter_by_user_and_active(self):
        wrapper = _make_wrapper()
        s1 = wrapper.create_session("u1")
        wrapper.create_session("u2")
        wrapper.revoke_session(s1["session_id"])
        result = wrapper.list_sessions(user_id="u1", is_active=0)
        assert len(result) == 1

    def test_empty(self):
        wrapper = _make_wrapper()
        assert wrapper.list_sessions() == []


# ===========================================================================
# 8. Stats
# ===========================================================================


class TestGetSessionStats:
    def test_initial_stats(self):
        wrapper = _make_wrapper()
        stats = wrapper.get_session_stats()
        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0
        assert stats["total_operations"] == 0

    def test_after_operations(self):
        wrapper = _make_wrapper()
        s1 = wrapper.create_session("u1")
        s2 = wrapper.create_session("u2")
        wrapper.revoke_session(s2["session_id"])
        wrapper.record_operation(s1["session_id"], "read", "/data", "ok")
        wrapper.record_operation(s1["session_id"], "write", "/data", "ok")
        stats = wrapper.get_session_stats()
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 1
        assert stats["revoked_sessions"] == 1
        assert stats["total_operations"] == 2


# ===========================================================================
# 9. EventBus integration
# ===========================================================================


class TestEventBusIntegration:
    def test_session_created_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("session_created", lambda e: collected.append(e))
        wrapper = _make_wrapper(event_bus=bus)
        wrapper.create_session("u1")
        assert len(collected) == 1
        assert collected[0].payload["user_id"] == "u1"

    def test_operation_recorded_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("operation_recorded", lambda e: collected.append(e))
        wrapper = _make_wrapper(event_bus=bus)
        s = _make_session(wrapper)
        wrapper.record_operation(s["session_id"], "read")
        assert len(collected) == 1
        assert collected[0].payload["operation"] == "read"

    def test_session_revoked_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("session_revoked", lambda e: collected.append(e))
        wrapper = _make_wrapper(event_bus=bus)
        s = _make_session(wrapper)
        wrapper.revoke_session(s["session_id"])
        assert len(collected) == 1
        assert collected[0].payload["session_id"] == s["session_id"]

    def test_session_expired_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("session_expired", lambda e: collected.append(e))
        wrapper = _make_wrapper(event_bus=bus)
        s = wrapper.create_session("u1", ttl_seconds=1)
        wrapper._conn.execute(
            "UPDATE phantom_sessions SET expires_at = ? WHERE session_id = ?",
            (time.time() - 10, s["session_id"]),
        )
        wrapper._conn.commit()
        wrapper.validate_session(s["session_id"])
        assert len(collected) == 1

    def test_no_event_without_bus(self):
        wrapper = _make_wrapper(event_bus=None)
        wrapper.create_session("u1")
        # Should not raise


# ===========================================================================
# 10. Singleton
# ===========================================================================


class TestSingleton:
    def test_get_phantom_wrapper(self):
        import sylion.security.phantom_wrapper as mod
        mod._wrapper = None
        w = get_phantom_wrapper(db_path=":memory:")
        assert isinstance(w, PhantomWrapper)
        mod._wrapper = None

    def test_reset_phantom_wrapper(self):
        import sylion.security.phantom_wrapper as mod
        mod._wrapper = None
        w1 = get_phantom_wrapper(db_path=":memory:")
        w2 = reset_phantom_wrapper(db_path=":memory:")
        assert w2 is not w1
        mod._wrapper = None

    def test_get_returns_same_instance(self):
        import sylion.security.phantom_wrapper as mod
        mod._wrapper = None
        w1 = get_phantom_wrapper(db_path=":memory:")
        w2 = get_phantom_wrapper()
        assert w1 is w2
        mod._wrapper = None


# ===========================================================================
# 11. Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_session_creation(self):
        wrapper = _make_wrapper()
        results = []
        errors = []

        def create(i):
            try:
                s = wrapper.create_session(f"user_{i}")
                results.append(s["session_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_validate(self):
        wrapper = _make_wrapper()
        s = _make_session(wrapper)
        results = []
        errors = []

        def validate():
            try:
                r = wrapper.validate_session(s["session_id"])
                results.append(r["allowed"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=validate) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(results)
