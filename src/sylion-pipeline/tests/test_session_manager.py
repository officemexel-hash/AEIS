"""Tests for sylion.security.session_manager -- SessionManager.

Covers user CRUD, session lifecycle, audit events, expiry cleanup,
EventBus integration, concurrency, and edge cases.
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.session_manager import (
    SESSION_TTL_SECONDS,
    VALID_ACTIONS,
    VALID_ROLES,
    SessionManager,
    get_session_manager,
    reset_session_manager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(event_bus: EventBus | None = None) -> SessionManager:
    return SessionManager(db_path=":memory:", event_bus=event_bus)


def _make_user(mgr: SessionManager, username: str = "alice",
               role: str = "admin") -> dict:
    return mgr.create_user(username, f"{username}@sylion.io", role=role)


def _make_session(mgr: SessionManager, user_id: str,
                  ip: str = "127.0.0.1") -> dict:
    return mgr.create_session(user_id, ip_address=ip)


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    def test_valid_roles(self):
        assert "admin" in VALID_ROLES
        assert "operator" in VALID_ROLES
        assert "viewer" in VALID_ROLES
        assert "service" in VALID_ROLES
        assert len(VALID_ROLES) == 4

    def test_valid_actions(self):
        expected = {"login", "logout", "api_call", "config_change",
                    "key_access", "data_export"}
        assert set(VALID_ACTIONS) == expected

    def test_session_ttl_is_24h(self):
        assert SESSION_TTL_SECONDS == 86400


# ===========================================================================
# 2. User CRUD
# ===========================================================================


class TestCreateUser:
    def test_basic_create(self):
        mgr = _make_manager()
        u = mgr.create_user("alice", "alice@sylion.io", "admin", "hash123")
        assert u["user_id"] != ""
        assert u["username"] == "alice"
        assert u["email"] == "alice@sylion.io"
        assert u["role"] == "admin"
        assert u["is_active"] == 1
        assert u["created_at"] > 0
        assert u["last_login"] == 0.0

    def test_default_role_is_viewer(self):
        mgr = _make_manager()
        u = mgr.create_user("bob", "bob@sylion.io")
        assert u["role"] == "viewer"

    def test_default_password_hash_empty(self):
        mgr = _make_manager()
        u = mgr.create_user("carol", "carol@sylion.io")
        # get_user returns raw row which includes password_hash
        fetched = mgr.get_user(u["user_id"])
        assert fetched["password_hash"] == ""

    def test_rejects_invalid_role(self):
        mgr = _make_manager()
        with pytest.raises(ValueError, match="Invalid role"):
            mgr.create_user("dave", "dave@sylion.io", role="superadmin")

    def test_rejects_duplicate_username(self):
        mgr = _make_manager()
        mgr.create_user("eve", "eve@sylion.io")
        with pytest.raises(Exception):
            mgr.create_user("eve", "eve2@sylion.io")

    def test_all_valid_roles_accepted(self):
        mgr = _make_manager()
        for i, role in enumerate(VALID_ROLES):
            u = mgr.create_user(f"user_{i}", f"u{i}@sylion.io", role=role)
            assert u["role"] == role


class TestGetUser:
    def test_get_existing(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        fetched = mgr.get_user(u["user_id"])
        assert fetched is not None
        assert fetched["username"] == "alice"

    def test_get_nonexistent(self):
        mgr = _make_manager()
        assert mgr.get_user("no-such-id") is None


class TestListUsers:
    def test_list_all(self):
        mgr = _make_manager()
        _make_user(mgr, "alice", "admin")
        _make_user(mgr, "bob", "viewer")
        users = mgr.list_users()
        assert len(users) == 2

    def test_filter_by_role(self):
        mgr = _make_manager()
        _make_user(mgr, "alice", "admin")
        _make_user(mgr, "bob", "viewer")
        admins = mgr.list_users(role="admin")
        assert len(admins) == 1
        assert admins[0]["username"] == "alice"

    def test_filter_by_active(self):
        mgr = _make_manager()
        u = _make_user(mgr, "alice", "admin")
        mgr.update_user(u["user_id"], is_active=0)
        active = mgr.list_users(is_active=1)
        assert len(active) == 0
        inactive = mgr.list_users(is_active=0)
        assert len(inactive) == 1

    def test_filter_by_role_and_active(self):
        mgr = _make_manager()
        u1 = _make_user(mgr, "alice", "admin")
        _make_user(mgr, "bob", "viewer")
        mgr.update_user(u1["user_id"], is_active=0)
        result = mgr.list_users(role="admin", is_active=0)
        assert len(result) == 1
        assert result[0]["username"] == "alice"

    def test_empty_list(self):
        mgr = _make_manager()
        assert mgr.list_users() == []


class TestUpdateUser:
    def test_update_email(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        updated = mgr.update_user(u["user_id"], email="new@sylion.io")
        assert updated["email"] == "new@sylion.io"

    def test_update_role(self):
        mgr = _make_manager()
        u = _make_user(mgr, role="viewer")
        updated = mgr.update_user(u["user_id"], role="operator")
        assert updated["role"] == "operator"

    def test_update_is_active(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        updated = mgr.update_user(u["user_id"], is_active=0)
        assert updated["is_active"] == 0

    def test_update_multiple_fields(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        updated = mgr.update_user(
            u["user_id"], email="x@y.com", role="service", is_active=0,
        )
        assert updated["email"] == "x@y.com"
        assert updated["role"] == "service"
        assert updated["is_active"] == 0

    def test_update_nonexistent_returns_none(self):
        mgr = _make_manager()
        assert mgr.update_user("nope", email="x@y.com") is None

    def test_update_rejects_invalid_role(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        with pytest.raises(ValueError, match="Invalid role"):
            mgr.update_user(u["user_id"], role="hacker")

    def test_update_no_fields_returns_user(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        result = mgr.update_user(u["user_id"])
        assert result is not None
        assert result["user_id"] == u["user_id"]


# ===========================================================================
# 3. Session lifecycle
# ===========================================================================


class TestCreateSession:
    def test_basic_create(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        assert s["session_id"] != ""
        assert s["token"] != ""
        assert s["user_id"] == u["user_id"]
        assert s["ip_address"] == "127.0.0.1"
        assert s["is_active"] == 1
        assert s["expires_at"] > s["created_at"]

    def test_ttl_is_24h(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        ttl = s["expires_at"] - s["created_at"]
        assert abs(ttl - SESSION_TTL_SECONDS) < 1

    def test_updates_last_login(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        time.sleep(0.01)
        _make_session(mgr, u["user_id"])
        fetched = mgr.get_user(u["user_id"])
        assert fetched["last_login"] > u["created_at"]

    def test_stores_user_agent(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = mgr.create_session(u["user_id"], user_agent="Mozilla/5.0")
        assert s["user_agent"] == "Mozilla/5.0"

    def test_rejects_nonexistent_user(self):
        mgr = _make_manager()
        with pytest.raises(ValueError, match="does not exist"):
            _make_session(mgr, "no-such-user")

    def test_rejects_inactive_user(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        mgr.update_user(u["user_id"], is_active=0)
        with pytest.raises(ValueError, match="inactive"):
            _make_session(mgr, u["user_id"])


class TestValidateSession:
    def test_valid_token(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        result = mgr.validate_session(s["token"])
        assert result is not None
        assert result["session"]["session_id"] == s["session_id"]
        assert result["user"]["user_id"] == u["user_id"]

    def test_invalid_token_returns_none(self):
        mgr = _make_manager()
        assert mgr.validate_session("bogus-token") is None

    def test_revoked_session_returns_none(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        mgr.revoke_session(s["session_id"])
        assert mgr.validate_session(s["token"]) is None

    def test_expired_session_returns_none(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        # Force expire
        mgr._conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
            (time.time() - 100, s["session_id"]),
        )
        mgr._conn.commit()
        assert mgr.validate_session(s["token"]) is None

    def test_inactive_user_session_returns_none(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        mgr.update_user(u["user_id"], is_active=0)
        assert mgr.validate_session(s["token"]) is None


class TestRevokeSession:
    def test_revoke_active(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        assert mgr.revoke_session(s["session_id"]) is True

    def test_revoke_already_revoked(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        mgr.revoke_session(s["session_id"])
        assert mgr.revoke_session(s["session_id"]) is False

    def test_revoke_nonexistent(self):
        mgr = _make_manager()
        assert mgr.revoke_session("nope") is False


class TestListSessions:
    def test_list_all(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        _make_session(mgr, u["user_id"])
        _make_session(mgr, u["user_id"])
        assert len(mgr.list_sessions()) == 2

    def test_filter_by_user(self):
        mgr = _make_manager()
        u1 = _make_user(mgr, "alice", "admin")
        u2 = _make_user(mgr, "bob", "viewer")
        _make_session(mgr, u1["user_id"])
        _make_session(mgr, u2["user_id"])
        result = mgr.list_sessions(user_id=u1["user_id"])
        assert len(result) == 1

    def test_filter_by_active(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        mgr.revoke_session(s["session_id"])
        active = mgr.list_sessions(is_active=1)
        assert len(active) == 0
        inactive = mgr.list_sessions(is_active=0)
        assert len(inactive) == 1

    def test_empty(self):
        mgr = _make_manager()
        assert mgr.list_sessions() == []


# ===========================================================================
# 4. Audit events
# ===========================================================================


class TestAuditEvent:
    def test_basic_record(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        ev = mgr.audit_event(s["session_id"], "login", ip_address="10.0.0.1")
        assert ev["event_id"] != ""
        assert ev["action"] == "login"
        assert ev["session_id"] == s["session_id"]
        assert ev["user_id"] == u["user_id"]
        assert ev["timestamp"] > 0

    def test_with_metadata(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        ev = mgr.audit_event(
            s["session_id"], "api_call", resource="/api/health",
            metadata={"status": 200},
        )
        assert ev["resource"] == "/api/health"
        assert ev["metadata"] == {"status": 200}

    def test_rejects_invalid_action(self):
        mgr = _make_manager()
        with pytest.raises(ValueError, match="Invalid action"):
            mgr.audit_event("sid", "hack_the_gibson")

    def test_all_valid_actions(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        for action in VALID_ACTIONS:
            ev = mgr.audit_event(s["session_id"], action)
            assert ev["action"] == action

    def test_resolves_user_from_session(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        ev = mgr.audit_event(s["session_id"], "logout")
        assert ev["user_id"] == u["user_id"]

    def test_unknown_session_still_records(self):
        mgr = _make_manager()
        ev = mgr.audit_event("unknown-session", "login")
        assert ev["user_id"] == ""
        assert ev["session_id"] == "unknown-session"


class TestListAuditEvents:
    def test_list_all(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        mgr.audit_event(s["session_id"], "login")
        mgr.audit_event(s["session_id"], "api_call")
        assert len(mgr.list_audit_events()) == 2

    def test_filter_by_user(self):
        mgr = _make_manager()
        u1 = _make_user(mgr, "alice", "admin")
        u2 = _make_user(mgr, "bob", "viewer")
        s1 = _make_session(mgr, u1["user_id"])
        s2 = _make_session(mgr, u2["user_id"])
        mgr.audit_event(s1["session_id"], "login")
        mgr.audit_event(s2["session_id"], "login")
        result = mgr.list_audit_events(user_id=u1["user_id"])
        assert len(result) == 1

    def test_filter_by_action(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        mgr.audit_event(s["session_id"], "login")
        mgr.audit_event(s["session_id"], "api_call")
        result = mgr.list_audit_events(action="login")
        assert len(result) == 1
        assert result[0]["action"] == "login"

    def test_limit(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        for i in range(10):
            mgr.audit_event(s["session_id"], "api_call", resource=f"/r{i}")
        result = mgr.list_audit_events(limit=5)
        assert len(result) == 5

    def test_metadata_parsed_as_dict(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        mgr.audit_event(
            s["session_id"], "config_change",
            metadata={"key": "val", "num": 42},
        )
        events = mgr.list_audit_events(action="config_change")
        assert events[0]["metadata"] == {"key": "val", "num": 42}

    def test_empty(self):
        mgr = _make_manager()
        assert mgr.list_audit_events() == []


# ===========================================================================
# 5. Expiry cleanup
# ===========================================================================


class TestCleanupExpired:
    def test_deactivates_expired(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        # Force expire
        mgr._conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
            (time.time() - 10, s["session_id"]),
        )
        mgr._conn.commit()
        count = mgr.cleanup_expired()
        assert count == 1
        sessions = mgr.list_sessions(is_active=1)
        assert len(sessions) == 0

    def test_nothing_to_cleanup(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        _make_session(mgr, u["user_id"])
        assert mgr.cleanup_expired() == 0

    def test_does_not_touch_active(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        _make_session(mgr, u["user_id"])
        count = mgr.cleanup_expired()
        assert count == 0
        assert len(mgr.list_sessions(is_active=1)) == 1


# ===========================================================================
# 6. EventBus integration
# ===========================================================================


class TestEventBusIntegration:
    def test_session_created_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("session.created", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        u = _make_user(mgr)
        _make_session(mgr, u["user_id"])
        assert len(collected) == 1
        assert "session_id" in collected[0].payload
        assert collected[0].payload["user_id"] == u["user_id"]

    def test_session_revoked_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("session.revoked", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        mgr.revoke_session(s["session_id"])
        assert len(collected) == 1
        assert collected[0].payload["session_id"] == s["session_id"]

    def test_session_expired_event_on_validate(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("session.expired", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        # Force expire
        mgr._conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
            (time.time() - 10, s["session_id"]),
        )
        mgr._conn.commit()
        mgr.validate_session(s["token"])
        assert len(collected) == 1
        assert collected[0].payload["session_id"] == s["session_id"]

    def test_session_expired_event_on_cleanup(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("session.expired", lambda e: collected.append(e))
        mgr = _make_manager(event_bus=bus)
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        # Force expire
        mgr._conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
            (time.time() - 10, s["session_id"]),
        )
        mgr._conn.commit()
        mgr.cleanup_expired()
        assert len(collected) == 1

    def test_no_event_without_bus(self):
        mgr = _make_manager(event_bus=None)
        u = _make_user(mgr)
        _make_session(mgr, u["user_id"])
        # Should not raise -- just silently skip emission


# ===========================================================================
# 7. Singleton
# ===========================================================================


class TestSingleton:
    def test_get_session_manager(self):
        import sylion.security.session_manager as mod
        mod._manager = None
        mgr = get_session_manager(db_path=":memory:")
        assert isinstance(mgr, SessionManager)
        mod._manager = None

    def test_reset_session_manager(self):
        import sylion.security.session_manager as mod
        mod._manager = None
        mgr1 = get_session_manager(db_path=":memory:")
        mgr2 = reset_session_manager(db_path=":memory:")
        assert mgr2 is not mgr1
        mod._manager = None

    def test_get_returns_same_instance(self):
        import sylion.security.session_manager as mod
        mod._manager = None
        mgr1 = get_session_manager(db_path=":memory:")
        mgr2 = get_session_manager()
        assert mgr1 is mgr2
        mod._manager = None


# ===========================================================================
# 8. Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_session_creation(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        results = []
        errors = []

        def create(i):
            try:
                s = _make_session(mgr, u["user_id"])
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
        assert len(set(results)) == 20  # all unique

    def test_concurrent_validate(self):
        mgr = _make_manager()
        u = _make_user(mgr)
        s = _make_session(mgr, u["user_id"])
        results = []
        errors = []

        def validate():
            try:
                r = mgr.validate_session(s["token"])
                results.append(r is not None)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=validate) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(results)
