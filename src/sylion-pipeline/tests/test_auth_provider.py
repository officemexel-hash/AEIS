"""Tests for sylion.security.auth_provider -- AuthProvider.

Covers: provider CRUD, authentication, token lifecycle, sessions, stats,
EventBus integration, concurrency, singleton, and edge cases.
~40 tests.
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.auth_provider import (
    TOKEN_TTL_SECONDS,
    VALID_PROVIDER_TYPES,
    AuthProvider,
    get_auth_provider,
    reset_auth_provider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(event_bus: EventBus | None = None) -> AuthProvider:
    return AuthProvider(db_path=":memory:", event_bus=event_bus)


def _register_provider(mgr: AuthProvider, name: str = "local-auth",
                       ptype: str = "local") -> dict:
    return mgr.register_provider(name, ptype, {"host": "localhost"})


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    def test_valid_provider_types(self):
        expected = {"local", "ldap", "oauth2", "saml", "api_key"}
        assert set(VALID_PROVIDER_TYPES) == expected

    def test_token_ttl_is_1_hour(self):
        assert TOKEN_TTL_SECONDS == 3600


# ===========================================================================
# 2. Provider CRUD
# ===========================================================================


class TestRegisterProvider:
    def test_basic_register(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        assert p["provider_id"] != ""
        assert p["name"] == "local-auth"
        assert p["provider_type"] == "local"
        assert p["is_active"] == 1
        assert p["created_at"] > 0

    def test_with_config(self):
        mgr = _make_provider()
        p = mgr.register_provider("ldap-main", "ldap", {"host": "ldap.co"})
        assert p["config_json"] == {"host": "ldap.co"}

    def test_default_type_is_local(self):
        mgr = _make_provider()
        p = mgr.register_provider("default")
        assert p["provider_type"] == "local"

    def test_rejects_invalid_type(self):
        mgr = _make_provider()
        with pytest.raises(ValueError, match="Invalid provider_type"):
            mgr.register_provider("bad", provider_type="kerberos")

    def test_all_types_accepted(self):
        mgr = _make_provider()
        for pt in VALID_PROVIDER_TYPES:
            p = mgr.register_provider(f"prov-{pt}", pt)
            assert p["provider_type"] == pt

    def test_default_config_empty(self):
        mgr = _make_provider()
        p = mgr.register_provider("no-config")
        assert p["config_json"] == {}


class TestUpdateProvider:
    def test_update_name(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        updated = mgr.update_provider(p["provider_id"], name="new-name")
        assert updated["name"] == "new-name"

    def test_update_type(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        updated = mgr.update_provider(p["provider_id"], provider_type="oauth2")
        assert updated["provider_type"] == "oauth2"

    def test_update_config(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        updated = mgr.update_provider(
            p["provider_id"], config_json={"host": "new.co"},
        )
        assert updated["config_json"] == {"host": "new.co"}

    def test_update_is_active(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        updated = mgr.update_provider(p["provider_id"], is_active=0)
        assert updated["is_active"] == 0

    def test_update_multiple_fields(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        updated = mgr.update_provider(
            p["provider_id"], name="x", provider_type="saml",
        )
        assert updated["name"] == "x"
        assert updated["provider_type"] == "saml"

    def test_update_nonexistent_returns_none(self):
        mgr = _make_provider()
        assert mgr.update_provider("nope", name="x") is None

    def test_update_rejects_invalid_type(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        with pytest.raises(ValueError, match="Invalid provider_type"):
            mgr.update_provider(p["provider_id"], provider_type="bad")

    def test_update_no_fields_returns_provider(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        result = mgr.update_provider(p["provider_id"])
        assert result is not None


class TestDeregisterProvider:
    def test_deregister_existing(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        assert mgr.deregister_provider(p["provider_id"]) is True

    def test_deregister_nonexistent(self):
        mgr = _make_provider()
        assert mgr.deregister_provider("nope") is False

    def test_deregister_twice(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        mgr.deregister_provider(p["provider_id"])
        assert mgr.deregister_provider(p["provider_id"]) is False


class TestListProviders:
    def test_list_all(self):
        mgr = _make_provider()
        _register_provider(mgr, "a", "local")
        _register_provider(mgr, "b", "oauth2")
        assert len(mgr.list_providers()) == 2

    def test_filter_by_type(self):
        mgr = _make_provider()
        _register_provider(mgr, "a", "local")
        _register_provider(mgr, "b", "oauth2")
        result = mgr.list_providers(provider_type="oauth2")
        assert len(result) == 1
        assert result[0]["provider_type"] == "oauth2"

    def test_excludes_deregistered(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        mgr.deregister_provider(p["provider_id"])
        assert len(mgr.list_providers()) == 0

    def test_empty_list(self):
        mgr = _make_provider()
        assert mgr.list_providers() == []


# ===========================================================================
# 3. Authentication
# ===========================================================================


class TestAuthenticate:
    def test_basic_auth(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        result = mgr.authenticate(p["provider_id"], {"user_id": "alice"})
        assert result["session_id"] != ""
        assert result["token_id"] != ""
        assert result["token"] != ""
        assert result["provider_id"] == p["provider_id"]
        assert result["user_id"] == "alice"
        assert result["expires_at"] > time.time()

    def test_extracts_user_id_from_username(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        result = mgr.authenticate(
            p["provider_id"], {"username": "bob"},
        )
        assert result["user_id"] == "bob"

    def test_default_user_is_anonymous(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        result = mgr.authenticate(p["provider_id"])
        assert result["user_id"] == "anonymous"

    def test_nonexistent_provider_raises(self):
        mgr = _make_provider()
        with pytest.raises(ValueError, match="does not exist"):
            mgr.authenticate("no-provider")

    def test_inactive_provider_raises(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        mgr.update_provider(p["provider_id"], is_active=0)
        with pytest.raises(ValueError, match="inactive"):
            mgr.authenticate(p["provider_id"])

    def test_ttl_is_1_hour(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        before = time.time()
        result = mgr.authenticate(p["provider_id"], {"user_id": "u"})
        ttl = result["expires_at"] - before
        assert abs(ttl - TOKEN_TTL_SECONDS) < 2


# ===========================================================================
# 4. Token lifecycle
# ===========================================================================


class TestValidateToken:
    def test_valid_token(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"], {"user_id": "alice"})
        result = mgr.validate_token(auth["token_id"])
        assert result is not None
        assert result["token"]["token_id"] == auth["token_id"]
        assert result["session"]["user_id"] == "alice"

    def test_invalid_token_returns_none(self):
        mgr = _make_provider()
        assert mgr.validate_token("no-token") is None

    def test_revoked_token_returns_none(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"])
        mgr.revoke_token(auth["token_id"])
        assert mgr.validate_token(auth["token_id"]) is None

    def test_expired_token_returns_none(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"])
        # Force expire
        mgr._conn.execute(
            "UPDATE auth_tokens SET expires_at = ? WHERE token_id = ?",
            (time.time() - 100, auth["token_id"]),
        )
        mgr._conn.commit()
        assert mgr.validate_token(auth["token_id"]) is None


class TestRevokeToken:
    def test_revoke_existing(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"])
        assert mgr.revoke_token(auth["token_id"]) is True

    def test_revoke_nonexistent(self):
        mgr = _make_provider()
        assert mgr.revoke_token("no-token") is False

    def test_revoke_twice(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"])
        mgr.revoke_token(auth["token_id"])
        assert mgr.revoke_token(auth["token_id"]) is False


class TestRefreshToken:
    def test_refresh_extends_expiry(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"])
        old_expires = auth["expires_at"]
        time.sleep(0.01)
        refreshed = mgr.refresh_token(auth["token_id"])
        assert refreshed is not None
        assert refreshed["expires_at"] > old_expires

    def test_refresh_nonexistent_returns_none(self):
        mgr = _make_provider()
        assert mgr.refresh_token("no-token") is None

    def test_refresh_revoked_raises(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"])
        mgr.revoke_token(auth["token_id"])
        with pytest.raises(ValueError, match="revoked"):
            mgr.refresh_token(auth["token_id"])

    def test_refresh_expired_raises(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"])
        mgr._conn.execute(
            "UPDATE auth_tokens SET expires_at = ? WHERE token_id = ?",
            (time.time() - 100, auth["token_id"]),
        )
        mgr._conn.commit()
        with pytest.raises(ValueError, match="expired"):
            mgr.refresh_token(auth["token_id"])


# ===========================================================================
# 5. Sessions
# ===========================================================================


class TestGetSession:
    def test_get_existing(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"], {"user_id": "alice"})
        session = mgr.get_session(auth["session_id"])
        assert session is not None
        assert session["user_id"] == "alice"

    def test_get_nonexistent(self):
        mgr = _make_provider()
        assert mgr.get_session("no-session") is None

    def test_metadata_parsed(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"], {"user_id": "alice"})
        session = mgr.get_session(auth["session_id"])
        assert isinstance(session["metadata"], dict)


class TestListSessions:
    def test_list_active(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        mgr.authenticate(p["provider_id"], {"user_id": "alice"})
        mgr.authenticate(p["provider_id"], {"user_id": "bob"})
        sessions = mgr.list_sessions()
        assert len(sessions) == 2

    def test_filter_by_user(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        mgr.authenticate(p["provider_id"], {"user_id": "alice"})
        mgr.authenticate(p["provider_id"], {"user_id": "bob"})
        result = mgr.list_sessions(user_id="alice")
        assert len(result) == 1
        assert result[0]["user_id"] == "alice"

    def test_empty(self):
        mgr = _make_provider()
        assert mgr.list_sessions() == []


# ===========================================================================
# 6. Stats
# ===========================================================================


class TestGetAuthStats:
    def test_empty_stats(self):
        mgr = _make_provider()
        stats = mgr.get_auth_stats()
        assert stats["total_providers"] == 0
        assert stats["active_providers"] == 0
        assert stats["total_sessions"] == 0
        assert stats["total_tokens"] == 0

    def test_with_data(self):
        mgr = _make_provider()
        p1 = _register_provider(mgr, "local-1", "local")
        p2 = mgr.register_provider("oauth-1", "oauth2")
        mgr.authenticate(p1["provider_id"], {"user_id": "alice"})
        mgr.authenticate(p2["provider_id"], {"user_id": "bob"})
        stats = mgr.get_auth_stats()
        assert stats["total_providers"] == 2
        assert stats["active_providers"] == 2
        assert stats["total_sessions"] == 2
        assert stats["total_tokens"] == 2
        assert stats["providers_by_type"]["local"] == 1
        assert stats["providers_by_type"]["oauth2"] == 1

    def test_revoked_tokens_counted(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"])
        mgr.revoke_token(auth["token_id"])
        stats = mgr.get_auth_stats()
        assert stats["revoked_tokens"] == 1


# ===========================================================================
# 7. EventBus integration
# ===========================================================================


class TestEventBusIntegration:
    def test_provider_registered_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("provider_registered", lambda e: collected.append(e))
        mgr = _make_provider(event_bus=bus)
        _register_provider(mgr)
        assert len(collected) == 1
        assert "provider_id" in collected[0].payload

    def test_user_authenticated_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("user_authenticated", lambda e: collected.append(e))
        mgr = _make_provider(event_bus=bus)
        p = _register_provider(mgr)
        mgr.authenticate(p["provider_id"], {"user_id": "alice"})
        assert len(collected) == 1
        assert collected[0].payload["user_id"] == "alice"

    def test_token_revoked_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("token_revoked", lambda e: collected.append(e))
        mgr = _make_provider(event_bus=bus)
        p = _register_provider(mgr)
        auth = mgr.authenticate(p["provider_id"])
        mgr.revoke_token(auth["token_id"])
        assert len(collected) == 1
        assert collected[0].payload["token_id"] == auth["token_id"]

    def test_no_event_without_bus(self):
        mgr = _make_provider(event_bus=None)
        _register_provider(mgr)
        # Should not raise


# ===========================================================================
# 8. Singleton
# ===========================================================================


class TestSingleton:
    def test_get_auth_provider(self):
        import sylion.security.auth_provider as mod
        mod._manager = None
        mgr = get_auth_provider(db_path=":memory:")
        assert isinstance(mgr, AuthProvider)
        mod._manager = None

    def test_reset_auth_provider(self):
        import sylion.security.auth_provider as mod
        mod._manager = None
        mgr1 = get_auth_provider(db_path=":memory:")
        mgr2 = reset_auth_provider(db_path=":memory:")
        assert mgr2 is not mgr1
        mod._manager = None

    def test_get_returns_same_instance(self):
        import sylion.security.auth_provider as mod
        mod._manager = None
        mgr1 = get_auth_provider(db_path=":memory:")
        mgr2 = get_auth_provider()
        assert mgr1 is mgr2
        mod._manager = None


# ===========================================================================
# 9. Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_authentication(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        results = []
        errors = []

        def auth(i):
            try:
                auth_result = mgr.authenticate(
                    p["provider_id"], {"user_id": f"user-{i}"},
                )
                results.append(auth_result["token_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=auth, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_validate_and_auth(self):
        mgr = _make_provider()
        p = _register_provider(mgr)
        auth_result = mgr.authenticate(p["provider_id"], {"user_id": "u"})
        token_id = auth_result["token_id"]
        errors = []

        def validate():
            try:
                for _ in range(10):
                    mgr.validate_token(token_id)
            except Exception as e:
                errors.append(e)

        def auth_more():
            try:
                for i in range(10):
                    mgr.authenticate(p["provider_id"], {"user_id": f"u{i}"})
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=validate),
            threading.Thread(target=validate),
            threading.Thread(target=auth_more),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
