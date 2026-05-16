"""Tests for sylion.security.secret_provider -- SecretProvider.

Covers: store_secret, get_secret, rotate_secret, delete_secret,
list_secrets, get_secret_history, log_access, get_access_log,
get_secret_stats, event emission, error handling, thread safety,
singleton lifecycle.
"""

from __future__ import annotations

import base64
import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.secret_provider import (
    SecretProvider,
    get_secret_provider,
    reset_secret_provider,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    reset_secret_provider()
    yield
    reset_secret_provider()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def provider(bus):
    return SecretProvider(event_bus=bus)


@pytest.fixture
def provider_no_bus():
    return SecretProvider(event_bus=None)


# ===========================================================================
# TestStoreSecret
# ===========================================================================

class TestStoreSecret:

    def test_store_basic(self, provider):
        result = provider.store_secret("db_password", "hunter2")
        assert result["name"] == "db_password"
        assert result["scope"] == "default"
        assert result["version"] == 1

    def test_store_with_scope(self, provider):
        result = provider.store_secret("api_key", "key123", scope="prod")
        assert result["scope"] == "prod"

    def test_store_with_metadata(self, provider):
        result = provider.store_secret("token", "tok",
                                       metadata_json={"owner": "admin"})
        secret = provider.get_secret("token")
        assert secret["metadata_json"]["owner"] == "admin"

    def test_store_upsert_increments_version(self, provider):
        provider.store_secret("dup", "v1")
        provider.store_secret("dup", "v2")
        secret = provider.get_secret("dup")
        assert secret["version"] == 2
        assert secret["value"] == "v2"

    def test_store_emits_event(self, provider, bus):
        events = []
        bus.subscribe("secret_stored", events.append)
        provider.store_secret("evt", "val")
        assert len(events) == 1
        assert events[0].payload["name"] == "evt"

    def test_store_value_is_base64_encoded(self, provider):
        provider.store_secret("enc", "hello world")
        row = provider._conn.execute(
            "SELECT value_encrypted FROM secrets WHERE name = 'enc'"
        ).fetchone()
        assert row["value_encrypted"] == \
            base64.b64encode(b"hello world").decode("ascii")


# ===========================================================================
# TestGetSecret
# ===========================================================================

class TestGetSecret:

    def test_get_existing(self, provider):
        provider.store_secret("get_test", "secret123")
        secret = provider.get_secret("get_test")
        assert secret is not None
        assert secret["value"] == "secret123"
        assert secret["scope"] == "default"

    def test_get_nonexistent(self, provider):
        assert provider.get_secret("ghost") is None

    def test_get_decodes_value(self, provider):
        provider.store_secret("decode", "my_secret")
        secret = provider.get_secret("decode")
        assert secret["value"] == "my_secret"

    def test_get_parses_metadata(self, provider):
        provider.store_secret("meta", "val",
                              metadata_json={"env": "staging"})
        secret = provider.get_secret("meta")
        assert isinstance(secret["metadata_json"], dict)
        assert secret["metadata_json"]["env"] == "staging"

    def test_get_logs_access(self, provider):
        provider.store_secret("logchk", "val")
        provider.get_secret("logchk")
        log_entries = provider.get_access_log()
        assert any(e["secret_name"] == "logchk" and e["action"] == "read"
                   for e in log_entries)

    def test_get_emits_accessed_event(self, provider, bus):
        events = []
        bus.subscribe("secret_accessed", events.append)
        provider.store_secret("acc", "val")
        provider.get_secret("acc")
        assert len(events) == 1


# ===========================================================================
# TestRotateSecret
# ===========================================================================

class TestRotateSecret:

    def test_rotate_existing(self, provider):
        provider.store_secret("rot", "old_val")
        result = provider.rotate_secret("rot", "new_val")
        assert result is not None
        assert result["version"] == 2
        secret = provider.get_secret("rot")
        assert secret["value"] == "new_val"

    def test_rotate_nonexistent(self, provider):
        assert provider.rotate_secret("ghost", "val") is None

    def test_rotate_multiple_times(self, provider):
        provider.store_secret("multi", "v1")
        provider.rotate_secret("multi", "v2")
        result = provider.rotate_secret("multi", "v3")
        assert result["version"] == 3

    def test_rotate_creates_version_history(self, provider):
        provider.store_secret("hist", "v1")
        provider.rotate_secret("hist", "v2")
        provider.rotate_secret("hist", "v3")
        versions = provider.get_secret_history("hist")
        assert len(versions) == 3

    def test_rotate_emits_event(self, provider, bus):
        events = []
        bus.subscribe("secret_rotated", events.append)
        provider.store_secret("revt", "v1")
        provider.rotate_secret("revt", "v2")
        assert len(events) == 1
        assert events[0].payload["new_version"] == 2

    def test_rotate_logs_access(self, provider):
        provider.store_secret("rlog", "v1")
        provider.rotate_secret("rlog", "v2")
        log_entries = provider.get_access_log()
        rotate_entries = [e for e in log_entries
                          if e["action"] == "rotate"
                          and e["secret_name"] == "rlog"]
        assert len(rotate_entries) >= 1


# ===========================================================================
# TestDeleteSecret
# ===========================================================================

class TestDeleteSecret:

    def test_delete_existing(self, provider):
        provider.store_secret("del", "val")
        assert provider.delete_secret("del") is True
        assert provider.get_secret("del") is None

    def test_delete_nonexistent(self, provider):
        assert provider.delete_secret("ghost") is False

    def test_delete_removes_versions(self, provider):
        provider.store_secret("vdel", "v1")
        provider.rotate_secret("vdel", "v2")
        provider.delete_secret("vdel")
        assert provider.get_secret_history("vdel") == []

    def test_delete_emits_event(self, provider, bus):
        events = []
        bus.subscribe("secret_deleted", events.append)
        provider.store_secret("devt", "val")
        provider.delete_secret("devt")
        assert len(events) == 1

    def test_delete_logs_access(self, provider):
        provider.store_secret("dlog", "val")
        provider.delete_secret("dlog")
        log_entries = provider.get_access_log()
        assert any(e["action"] == "delete" and e["secret_name"] == "dlog"
                   for e in log_entries)


# ===========================================================================
# TestListSecrets
# ===========================================================================

class TestListSecrets:

    def test_list_empty(self, provider):
        assert provider.list_secrets() == []

    def test_list_all(self, provider):
        provider.store_secret("a", "v1")
        provider.store_secret("b", "v2")
        result = provider.list_secrets()
        assert len(result) == 2
        names = [s["name"] for s in result]
        assert names == sorted(names)

    def test_list_filter_by_scope(self, provider):
        provider.store_secret("s1", "v1", scope="prod")
        provider.store_secret("s2", "v2", scope="dev")
        result = provider.list_secrets(scope="prod")
        assert len(result) == 1
        assert result[0]["name"] == "s1"

    def test_list_excludes_values(self, provider):
        provider.store_secret("hide", "secret_val")
        result = provider.list_secrets()
        assert "value" not in result[0]
        assert "value_encrypted" not in result[0]


# ===========================================================================
# TestSecretHistory
# ===========================================================================

class TestSecretHistory:

    def test_history_empty(self, provider):
        provider.store_secret("nohist", "v1")
        # Only 1 version, so history has 1 entry
        history = provider.get_secret_history("nohist")
        assert len(history) == 1

    def test_history_multiple_versions(self, provider):
        provider.store_secret("mhist", "v1")
        provider.rotate_secret("mhist", "v2")
        provider.rotate_secret("mhist", "v3")
        history = provider.get_secret_history("mhist")
        assert len(history) == 3

    def test_history_with_limit(self, provider):
        provider.store_secret("lhist", "v1")
        for i in range(5):
            provider.rotate_secret("lhist", f"v{i+2}")
        history = provider.get_secret_history("lhist", limit=2)
        assert len(history) == 2

    def test_history_nonexistent(self, provider):
        assert provider.get_secret_history("ghost") == []


# ===========================================================================
# TestAccessLog
# ===========================================================================

class TestAccessLog:

    def test_log_access(self, provider):
        result = provider.log_access("sec", "user1", "read")
        assert result["log_id"]
        assert result["action"] == "read"

    def test_get_access_log(self, provider):
        provider.store_secret("log1", "v")
        provider.get_secret("log1")
        log_entries = provider.get_access_log()
        assert len(log_entries) >= 1

    def test_get_access_log_with_limit(self, provider):
        provider.store_secret("lim1", "v")
        for _ in range(10):
            provider.get_secret("lim1")
        log_entries = provider.get_access_log(limit=3)
        assert len(log_entries) == 3


# ===========================================================================
# TestGetSecretStats
# ===========================================================================

class TestGetSecretStats:

    def test_empty_stats(self, provider):
        stats = provider.get_secret_stats()
        assert stats["total_secrets"] == 0
        assert stats["by_scope"] == {}
        assert stats["total_versions"] == 0

    def test_stats_with_secrets(self, provider):
        provider.store_secret("s1", "v1", scope="prod")
        provider.store_secret("s2", "v2", scope="dev")
        provider.store_secret("s3", "v3", scope="prod")
        stats = provider.get_secret_stats()
        assert stats["total_secrets"] == 3
        assert stats["by_scope"]["prod"] == 2
        assert stats["by_scope"]["dev"] == 1

    def test_stats_with_versions(self, provider):
        provider.store_secret("vs", "v1")
        provider.rotate_secret("vs", "v2")
        provider.rotate_secret("vs", "v3")
        stats = provider.get_secret_stats()
        assert stats["total_versions"] == 3

    def test_stats_with_access_log(self, provider):
        provider.store_secret("as", "v")
        provider.get_secret("as")
        stats = provider.get_secret_stats()
        assert stats["total_access_events"] >= 1
        assert "read" in stats["by_action"]


# ===========================================================================
# TestNoBus
# ===========================================================================

class TestNoBus:

    def test_no_bus_no_crash(self, provider_no_bus):
        provider_no_bus.store_secret("nb", "val")
        provider_no_bus.get_secret("nb")
        provider_no_bus.rotate_secret("nb", "new")
        provider_no_bus.delete_secret("nb")


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        assert isinstance(get_secret_provider(), SecretProvider)

    def test_idempotent(self):
        a = get_secret_provider()
        b = get_secret_provider()
        assert a is b

    def test_reset_creates_new(self):
        a = get_secret_provider()
        b = reset_secret_provider()
        assert a is not b


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_store_and_read(self, provider):
        errors = []
        results = []

        def store_and_read(idx):
            try:
                name = f"secret-{idx}"
                provider.store_secret(name, f"val-{idx}")
                s = provider.get_secret(name)
                results.append(s["value"] == f"val-{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=store_and_read, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(results)

    def test_concurrent_rotates(self, provider):
        provider.store_secret("concurrent_rot", "v0")
        errors = []

        def rotate(idx):
            try:
                provider.rotate_secret("concurrent_rot", f"v{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=rotate, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        versions = provider.get_secret_history("concurrent_rot")
        assert len(versions) == 11  # 1 initial + 10 rotates
