"""
Comprehensive tests for sylion.security.key_vault -- KeyVault class.

Covers: encryption round-trip, key CRUD, validation, activation,
hierarchies, council member configs, events, thread safety, singleton,
and edge cases.  Target: 30+ tests.
"""
from __future__ import annotations

import threading
import time

import pytest

from sylion.security.key_vault import (
    KeyVault,
    _Encryptor,
    get_key_vault,
    reset_key_vault,
)
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global singleton before and after each test."""
    import sylion.security.key_vault as _mod
    _mod._vault = None
    yield
    _mod._vault = None


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def vault(bus: EventBus) -> KeyVault:
    return KeyVault(db_path=":memory:", event_bus=bus, vault_secret="test-secret-1234")


@pytest.fixture
def vault_no_bus() -> KeyVault:
    return KeyVault(db_path=":memory:", event_bus=None, vault_secret="test-secret-1234")


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

class TestEncryptor:

    def test_encrypt_decrypt_roundtrip(self):
        enc = _Encryptor("my-secret")
        plaintext = "sk-test-api-key-12345"
        token = enc.encrypt(plaintext)
        assert enc.decrypt(token) == plaintext

    def test_encrypt_produces_different_ciphertext(self):
        enc = _Encryptor("my-secret")
        t1 = enc.encrypt("hello")
        t2 = enc.encrypt("hello")
        # Fernet uses IV/randomness so ciphertexts should differ
        # (if Fernet available; base64 fallback is deterministic)
        from sylion.security.key_vault import _FERNET_AVAILABLE
        if _FERNET_AVAILABLE:
            assert t1 != t2

    def test_encrypt_decrypt_empty_string(self):
        enc = _Encryptor("secret")
        token = enc.encrypt("")
        assert enc.decrypt(token) == ""

    def test_encrypt_decrypt_unicode(self):
        enc = _Encryptor("secret")
        plaintext = "key-\u00e9\u00e8\u00ea\u00eb-\u4e2d\u6587"
        token = enc.encrypt(plaintext)
        assert enc.decrypt(token) == plaintext

    def test_different_secrets_different_ciphertext(self):
        enc1 = _Encryptor("secret-a")
        enc2 = _Encryptor("secret-b")
        from sylion.security.key_vault import _FERNET_AVAILABLE
        if _FERNET_AVAILABLE:
            # Fernet with different keys produces different ciphertext
            t1 = enc1.encrypt("hello")
            # Cannot decrypt with wrong key
            with pytest.raises(Exception):
                enc2.decrypt(t1)

    def test_default_secret_uses_env_var(self, monkeypatch):
        monkeypatch.setenv("SYLION_VAULT_SECRET", "env-secret-value")
        enc = _Encryptor(None)
        token = enc.encrypt("test")
        # Build another encryptor from same env var
        enc2 = _Encryptor(None)
        assert enc2.decrypt(token) == "test"


# ---------------------------------------------------------------------------
# store_key
# ---------------------------------------------------------------------------

class TestStoreKey:

    def test_store_returns_key_id(self, vault):
        result = vault.store_key("openai", "sk-test-123")
        assert "key_id" in result
        assert len(result["key_id"]) == 12

    def test_store_returns_provider(self, vault):
        result = vault.store_key("openai", "sk-test-123")
        assert result["provider"] == "openai"

    def test_store_provider_case_insensitive(self, vault):
        result = vault.store_key("OpenAI", "sk-test")
        assert result["provider"] == "openai"

    def test_store_with_display_name(self, vault):
        result = vault.store_key("openai", "sk-test", display_name="My Key")
        assert result["display_name"] == "My Key"

    def test_store_with_metadata(self, vault):
        result = vault.store_key("openai", "sk-test", metadata={"region": "us"})
        assert result["masked_key"] is not None

    def test_store_default_not_active(self, vault):
        result = vault.store_key("openai", "sk-test")
        assert result["is_active"] is False

    def test_store_returns_created_at(self, vault):
        before = time.time()
        result = vault.store_key("openai", "sk-test")
        after = time.time()
        assert before <= result["created_at"] <= after

    def test_store_emits_event(self, vault, bus):
        vault.store_key("openai", "sk-test")
        events = bus.query(topic="vault.key.stored")
        assert len(events) == 1
        import json
        payload = json.loads(events[0]["payload"]) if isinstance(events[0]["payload"], str) else events[0]["payload"]
        assert payload["provider"] == "openai"

    def test_store_without_event_bus(self, vault_no_bus):
        result = vault_no_bus.store_key("openai", "sk-test")
        assert result["key_id"]  # no crash

    def test_masked_key_format(self, vault):
        result = vault.store_key("openai", "sk-test-long-api-key-value")
        masked = result["masked_key"]
        assert masked.startswith("sk-")
        assert "..." in masked


# ---------------------------------------------------------------------------
# get_decrypted_key / get_key_info
# ---------------------------------------------------------------------------

class TestGetDecryptedKey:

    def test_decrypt_roundtrip(self, vault):
        stored = vault.store_key("openai", "sk-secret-key-123")
        decrypted = vault.get_decrypted_key(stored["key_id"])
        assert decrypted == "sk-secret-key-123"

    def test_decrypt_nonexistent(self, vault):
        assert vault.get_decrypted_key("no-such-key") is None


class TestGetKeyInfo:

    def test_returns_metadata(self, vault):
        stored = vault.store_key("openai", "sk-test",
                                 display_name="Prod",
                                 metadata={"env": "prod"})
        info = vault.get_key_info(stored["key_id"])
        assert info is not None
        assert info["provider"] == "openai"
        assert info["display_name"] == "Prod"
        assert info["metadata"] == {"env": "prod"}

    def test_no_encrypted_key_in_info(self, vault):
        stored = vault.store_key("openai", "sk-test")
        info = vault.get_key_info(stored["key_id"])
        assert "encrypted_key" not in info

    def test_nonexistent_returns_none(self, vault):
        assert vault.get_key_info("nope") is None


# ---------------------------------------------------------------------------
# list_keys
# ---------------------------------------------------------------------------

class TestListKeys:

    def test_list_empty(self, vault):
        assert vault.list_keys() == []

    def test_list_all(self, vault):
        vault.store_key("openai", "sk-1")
        vault.store_key("anthropic", "sk-ant-2")
        keys = vault.list_keys()
        assert len(keys) == 2

    def test_list_filter_by_provider(self, vault):
        vault.store_key("openai", "sk-1")
        vault.store_key("anthropic", "sk-ant-2")
        vault.store_key("openai", "sk-3")
        openai_keys = vault.list_keys(provider="openai")
        assert len(openai_keys) == 2
        anthropic_keys = vault.list_keys(provider="anthropic")
        assert len(anthropic_keys) == 1

    def test_list_never_contains_encrypted_key(self, vault):
        vault.store_key("openai", "sk-secret")
        keys = vault.list_keys()
        for k in keys:
            assert "encrypted_key" not in k

    def test_list_contains_masked_key(self, vault):
        vault.store_key("openai", "sk-long-api-key-value")
        keys = vault.list_keys()
        assert len(keys) == 1
        assert "masked_key" in keys[0]


# ---------------------------------------------------------------------------
# validate_key
# ---------------------------------------------------------------------------

class TestValidateKey:

    def test_validate_openai_valid(self, vault):
        stored = vault.store_key("openai", "sk-abc123")
        result = vault.validate_key(stored["key_id"])
        assert result["valid"] is True
        assert result["reason"] == "ok"

    def test_validate_openai_invalid_prefix(self, vault):
        stored = vault.store_key("openai", "wrong-prefix-key")
        result = vault.validate_key(stored["key_id"])
        assert result["valid"] is False
        assert "sk-" in result["reason"]

    def test_validate_anthropic_valid(self, vault):
        stored = vault.store_key("anthropic", "sk-ant-api-key-xyz")
        result = vault.validate_key(stored["key_id"])
        assert result["valid"] is True

    def test_validate_anthropic_invalid_prefix(self, vault):
        stored = vault.store_key("anthropic", "sk-wrong-prefix")
        result = vault.validate_key(stored["key_id"])
        assert result["valid"] is False

    def test_validate_other_provider_short_key(self, vault):
        stored = vault.store_key("google", "short")
        result = vault.validate_key(stored["key_id"])
        assert result["valid"] is False
        assert "too short" in result["reason"]

    def test_validate_other_provider_long_enough(self, vault):
        stored = vault.store_key("google", "a-valid-long-enough-key-value")
        result = vault.validate_key(stored["key_id"])
        assert result["valid"] is True

    def test_validate_nonexistent(self, vault):
        result = vault.validate_key("no-key")
        assert result["valid"] is False
        assert result["reason"] == "not_found"

    def test_validate_emits_event(self, vault, bus):
        stored = vault.store_key("openai", "sk-valid")
        vault.validate_key(stored["key_id"])
        events = bus.query(topic="vault.key.validated")
        assert len(events) == 1


# ---------------------------------------------------------------------------
# activate_key / deactivate_key / delete_key
# ---------------------------------------------------------------------------

class TestActivateKey:

    def test_activate_sets_active(self, vault):
        stored = vault.store_key("openai", "sk-test")
        result = vault.activate_key(stored["key_id"])
        assert result["activated"] is True
        info = vault.get_key_info(stored["key_id"])
        assert info["is_active"] is True or info["is_active"] == 1

    def test_activate_deactivates_others_for_provider(self, vault):
        k1 = vault.store_key("openai", "sk-1")
        vault.activate_key(k1["key_id"])
        k2 = vault.store_key("openai", "sk-2")
        vault.activate_key(k2["key_id"])
        # k1 should now be inactive
        info1 = vault.get_key_info(k1["key_id"])
        assert info1["is_active"] is False or info1["is_active"] == 0
        info2 = vault.get_key_info(k2["key_id"])
        assert info2["is_active"] is True or info2["is_active"] == 1

    def test_activate_nonexistent(self, vault):
        result = vault.activate_key("no-key")
        assert result["activated"] is False
        assert result["reason"] == "not_found"


class TestDeactivateKey:

    def test_deactivate(self, vault):
        stored = vault.store_key("openai", "sk-test")
        vault.activate_key(stored["key_id"])
        result = vault.deactivate_key(stored["key_id"])
        assert result["deactivated"] is True
        info = vault.get_key_info(stored["key_id"])
        assert info["is_active"] is False or info["is_active"] == 0

    def test_deactivate_nonexistent(self, vault):
        result = vault.deactivate_key("no-key")
        assert result["deactivated"] is False
        assert result["reason"] == "not_found"


class TestDeleteKey:

    def test_delete_existing(self, vault):
        stored = vault.store_key("openai", "sk-test")
        assert vault.delete_key(stored["key_id"]) is True

    def test_delete_nonexistent(self, vault):
        assert vault.delete_key("no-key") is False

    def test_deleted_key_not_listed(self, vault):
        stored = vault.store_key("openai", "sk-test")
        vault.delete_key(stored["key_id"])
        assert vault.list_keys() == []

    def test_deleted_key_cannot_be_decrypted(self, vault):
        stored = vault.store_key("openai", "sk-test")
        vault.delete_key(stored["key_id"])
        assert vault.get_decrypted_key(stored["key_id"]) is None


# ---------------------------------------------------------------------------
# Model Hierarchies
# ---------------------------------------------------------------------------

class TestSaveHierarchy:

    def test_save_returns_hierarchy_id(self, vault):
        result = vault.save_hierarchy("standard", [
            {"level": 1, "model_id": "gpt-4", "task_types": ["reasoning"]},
        ])
        assert "hierarchy_id" in result
        assert len(result["hierarchy_id"]) == 12

    def test_save_returns_name_and_levels(self, vault):
        levels = [
            {"level": 1, "model_id": "gpt-4", "task_types": ["reasoning"]},
            {"level": 2, "model_id": "gpt-3.5", "task_types": ["chat"]},
        ]
        result = vault.save_hierarchy("Standard", levels)
        assert result["name"] == "Standard"
        assert result["levels"] == levels

    def test_save_default_not_active(self, vault):
        result = vault.save_hierarchy("H1", [])
        assert result["is_active"] is False

    def test_save_emits_event(self, vault, bus):
        vault.save_hierarchy("H1", [])
        events = bus.query(topic="vault.hierarchy.saved")
        assert len(events) == 1
        import json
        payload = json.loads(events[0]["payload"]) if isinstance(events[0]["payload"], str) else events[0]["payload"]
        assert payload["name"] == "H1"


class TestGetHierarchy:

    def test_get_existing(self, vault):
        saved = vault.save_hierarchy("H1", [
            {"level": 1, "model_id": "gpt-4", "task_types": ["reasoning"]},
        ])
        fetched = vault.get_hierarchy(saved["hierarchy_id"])
        assert fetched is not None
        assert fetched["name"] == "H1"
        assert fetched["levels"] == [
            {"level": 1, "model_id": "gpt-4", "task_types": ["reasoning"]},
        ]

    def test_get_nonexistent(self, vault):
        assert vault.get_hierarchy("no-id") is None


class TestListHierarchies:

    def test_list_empty(self, vault):
        assert vault.list_hierarchies() == []

    def test_list_multiple(self, vault):
        vault.save_hierarchy("H1", [])
        vault.save_hierarchy("H2", [])
        result = vault.list_hierarchies()
        assert len(result) == 2


class TestSetActiveHierarchy:

    def test_set_active(self, vault):
        h = vault.save_hierarchy("H1", [])
        result = vault.set_active_hierarchy(h["hierarchy_id"])
        assert result["activated"] is True
        fetched = vault.get_hierarchy(h["hierarchy_id"])
        assert fetched["is_active"] is True or fetched["is_active"] == 1

    def test_set_active_deactivates_others(self, vault):
        h1 = vault.save_hierarchy("H1", [])
        h2 = vault.save_hierarchy("H2", [])
        vault.set_active_hierarchy(h1["hierarchy_id"])
        vault.set_active_hierarchy(h2["hierarchy_id"])
        f1 = vault.get_hierarchy(h1["hierarchy_id"])
        assert f1["is_active"] is False or f1["is_active"] == 0

    def test_set_active_nonexistent(self, vault):
        result = vault.set_active_hierarchy("no-id")
        assert result["activated"] is False
        assert result["reason"] == "not_found"


# ---------------------------------------------------------------------------
# Council Member Configs
# ---------------------------------------------------------------------------

class TestConfigureCouncilMember:

    def test_create_member(self, vault):
        result = vault.configure_council_member(
            "member-1", "gpt-4", "analyst", 5,
            system_prompt="You are an analyst.",
        )
        assert result["member_id"] == "member-1"
        assert result["model_id"] == "gpt-4"
        assert result["role"] == "analyst"
        assert result["priority"] == 5
        assert result["system_prompt"] == "You are an analyst."

    def test_upsert_existing_member(self, vault):
        vault.configure_council_member("m1", "gpt-4", "analyst", 5)
        result = vault.configure_council_member("m1", "gpt-3.5", "reviewer", 3)
        assert result["model_id"] == "gpt-3.5"
        assert result["role"] == "reviewer"
        assert result["priority"] == 3
        # Should still be only one member
        members = vault.list_council_members()
        assert len(members) == 1

    def test_emits_event(self, vault, bus):
        vault.configure_council_member("m1", "gpt-4", "analyst", 5)
        events = bus.query(topic="vault.council_member.configured")
        assert len(events) == 1
        import json
        payload = json.loads(events[0]["payload"]) if isinstance(events[0]["payload"], str) else events[0]["payload"]
        assert payload["member_id"] == "m1"


class TestGetCouncilMember:

    def test_get_existing(self, vault):
        vault.configure_council_member("m1", "gpt-4", "analyst", 5,
                                        system_prompt="Think.")
        member = vault.get_council_member("m1")
        assert member is not None
        assert member["model_id"] == "gpt-4"
        assert member["system_prompt"] == "Think."

    def test_get_nonexistent(self, vault):
        assert vault.get_council_member("no-member") is None


class TestListCouncilMembers:

    def test_list_empty(self, vault):
        assert vault.list_council_members() == []

    def test_list_ordered_by_priority_desc(self, vault):
        vault.configure_council_member("low", "gpt-3.5", "chat", 1)
        vault.configure_council_member("high", "gpt-4", "reasoning", 10)
        vault.configure_council_member("mid", "gpt-4", "analyst", 5)
        members = vault.list_council_members()
        assert len(members) == 3
        assert members[0]["priority"] >= members[1]["priority"]
        assert members[1]["priority"] >= members[2]["priority"]


class TestRemoveCouncilMember:

    def test_remove_existing(self, vault):
        vault.configure_council_member("m1", "gpt-4", "analyst", 5)
        assert vault.remove_council_member("m1") is True
        assert vault.get_council_member("m1") is None

    def test_remove_nonexistent(self, vault):
        assert vault.remove_council_member("no-member") is False

    def test_removed_not_in_list(self, vault):
        vault.configure_council_member("m1", "gpt-4", "analyst", 5)
        vault.configure_council_member("m2", "gpt-3.5", "chat", 1)
        vault.remove_council_member("m1")
        members = vault.list_council_members()
        assert len(members) == 1
        assert members[0]["member_id"] == "m2"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_returns_instance(self, bus):
        v = get_key_vault(db_path=":memory:", event_bus=bus,
                          vault_secret="s")
        assert isinstance(v, KeyVault)

    def test_idempotent(self, bus):
        v1 = get_key_vault(db_path=":memory:", event_bus=bus,
                           vault_secret="s")
        v2 = get_key_vault(db_path=":memory:", event_bus=bus,
                           vault_secret="s")
        assert v1 is v2

    def test_reset_creates_new(self, bus):
        v1 = get_key_vault(db_path=":memory:", event_bus=bus,
                           vault_secret="s")
        v2 = reset_key_vault(db_path=":memory:", event_bus=bus,
                             vault_secret="s")
        assert v1 is not v2

    def test_reset_returns_instance(self, bus):
        v = reset_key_vault(db_path=":memory:", event_bus=bus,
                            vault_secret="s")
        assert isinstance(v, KeyVault)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_store_keys(self, vault):
        errors: list[Exception] = []
        keys_ids: list[str] = []

        def store_n(n: int):
            try:
                for i in range(10):
                    result = vault.store_key("openai", f"sk-thread-{n}-{i}")
                    keys_ids.append(result["key_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=store_n, args=(i,))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        keys = vault.list_keys(provider="openai")
        assert len(keys) == 50

    def test_concurrent_council_config(self, vault):
        errors: list[Exception] = []

        def config_member(mid: str):
            try:
                for i in range(10):
                    vault.configure_council_member(
                        mid, "gpt-4", "analyst", i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=config_member, args=(f"m{i}",))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        members = vault.list_council_members()
        assert len(members) == 5
