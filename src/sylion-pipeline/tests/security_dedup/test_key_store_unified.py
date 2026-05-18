"""
Tests for security dedup K4.3 — KeyStoreUnified canonical module.
"""

from __future__ import annotations

import pytest

from sylion.security.key_store_unified import (
    KeyStoreUnified,
    get_key_store_unified,
    reset_key_store_unified,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_key_store_unified()
    yield
    reset_key_store_unified()


class TestPutAndGet:
    def test_store_and_retrieve(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("api-key-1", "secret-value")
        assert ks.get("api-key-1") == "secret-value"

    def test_update_existing(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1")
        ks.put("k1", "v2")
        assert ks.get("k1") == "v2"

    def test_scope(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1", scope="api")
        ks.put("k2", "v2", scope="db")
        assert len(ks.list_keys(scope="api")) == 1
        assert len(ks.list_keys(scope="db")) == 1
        assert len(ks.list_keys()) == 2

    def test_metadata(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1", metadata={"env": "prod"})
        # metadata is stored but not returned by get()
        assert ks.get("k1") == "v1"


class TestRotate:
    def test_rotate_existing(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1")
        result = ks.rotate("k1", "v2")
        assert result is not None
        assert result["version"] == 2
        assert ks.get("k1") == "v2"

    def test_rotate_missing(self):
        ks = KeyStoreUnified(":memory:")
        assert ks.rotate("missing", "v") is None

    def test_rotate_can_update_metadata_without_returning_ciphertext(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1", metadata={"owner": "security"})
        ks.rotate("k1", "v2", metadata_update={"rotated_by": "test"})

        desc = ks.describe("k1")

        assert desc is not None
        assert desc["metadata"]["owner"] == "security"
        assert desc["metadata"]["rotated_by"] == "test"
        assert "ciphertext" not in desc


class TestDelete:
    def test_delete_existing(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1")
        assert ks.delete("k1") is True
        assert ks.get("k1") is None

    def test_delete_missing(self):
        ks = KeyStoreUnified(":memory:")
        assert ks.delete("missing") is False


class TestAuditLog:
    def test_audit_trail(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1", actor="alice")
        ks.get("k1", actor="bob")
        log = ks.audit_log("k1")
        assert len(log) == 2
        actions = {e["action"] for e in log}
        assert "put" in actions
        assert "get" in actions

    def test_audit_log_all(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1")
        ks.put("k2", "v2")
        assert len(ks.audit_log()) == 2

    def test_record_audit_adds_safe_custom_event(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1")
        ks.record_audit("k1", "lifecycle.validate", actor="tester")

        actions = {row["action"] for row in ks.audit_log("k1")}

        assert "lifecycle.validate" in actions


class TestStats:
    def test_empty_stats(self):
        ks = KeyStoreUnified(":memory:")
        stats = ks.stats()
        assert stats["total_keys"] == 0

    def test_stats_with_data(self):
        ks = KeyStoreUnified(":memory:")
        ks.put("k1", "v1", scope="api")
        ks.put("k2", "v2", scope="api")
        ks.put("k3", "v3", scope="db")
        stats = ks.stats()
        assert stats["total_keys"] == 3
        assert stats["by_scope"]["api"] == 2
        assert stats["by_scope"]["db"] == 1


class TestSingleton:
    def test_get_returns_instance(self):
        ks = get_key_store_unified()
        assert isinstance(ks, KeyStoreUnified)

    def test_reset_creates_fresh(self):
        ks1 = get_key_store_unified()
        ks1.put("k1", "v1")
        ks2 = reset_key_store_unified()
        assert ks1 is not ks2


class TestDatabasePath:
    def test_creates_parent_directory_for_file_db(self, tmp_path):
        target = tmp_path / "missing" / "nested" / "store.db"

        ks = KeyStoreUnified(target)
        ks.put("k1", "v1")

        assert target.exists()
        assert ks.get("k1") == "v1"
