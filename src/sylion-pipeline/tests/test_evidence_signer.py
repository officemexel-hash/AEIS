"""
Tests for sylion.security.evidence_signer -- EvidenceSigner

Covers key generation, revocation, signing, verification,
listing, stats, EventBus integration, singleton, and concurrency.
"""

import threading

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.evidence_signer import (
    VALID_KEY_TYPES,
    EvidenceSigner,
    get_evidence_signer,
    reset_evidence_signer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signer(event_bus: EventBus | None = None) -> EvidenceSigner:
    return EvidenceSigner(db_path=":memory:", event_bus=event_bus)


def _make_key(signer: EvidenceSigner, alias: str = "test_key",
              key_type: str = "hmac_sha256") -> dict:
    return signer.generate_key(alias, key_type)


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    def test_valid_key_types(self):
        assert "hmac_sha256" in VALID_KEY_TYPES
        assert "rsa" in VALID_KEY_TYPES

    def test_valid_key_types_count(self):
        assert len(VALID_KEY_TYPES) == 2


# ===========================================================================
# 2. Key generation
# ===========================================================================


class TestGenerateKey:
    def test_basic_generate(self):
        signer = _make_signer()
        k = signer.generate_key("mykey")
        assert k["key_id"] != ""
        assert k["alias"] == "mykey"
        assert k["key_type"] == "hmac_sha256"
        assert k["is_revoked"] == 0
        assert k["created_at"] > 0

    def test_default_type_is_hmac(self):
        signer = _make_signer()
        k = signer.generate_key("k1")
        assert k["key_type"] == "hmac_sha256"

    def test_explicit_rsa_type(self):
        signer = _make_signer()
        k = signer.generate_key("rsa_key", key_type="rsa")
        assert k["key_type"] == "rsa"

    def test_rejects_invalid_type(self):
        signer = _make_signer()
        with pytest.raises(ValueError, match="Invalid key_type"):
            signer.generate_key("bad", key_type="ed25519")

    def test_unique_key_ids(self):
        signer = _make_signer()
        k1 = signer.generate_key("k1")
        k2 = signer.generate_key("k2")
        assert k1["key_id"] != k2["key_id"]


# ===========================================================================
# 3. Key revocation
# ===========================================================================


class TestRevokeKey:
    def test_revoke_active_key(self):
        signer = _make_signer()
        k = _make_key(signer)
        assert signer.revoke_key(k["key_id"]) is True

    def test_revoke_already_revoked(self):
        signer = _make_signer()
        k = _make_key(signer)
        signer.revoke_key(k["key_id"])
        assert signer.revoke_key(k["key_id"]) is False

    def test_revoke_nonexistent(self):
        signer = _make_signer()
        assert signer.revoke_key("nope") is False


# ===========================================================================
# 4. Signing
# ===========================================================================


class TestSignEvidence:
    def test_basic_sign(self):
        signer = _make_signer()
        k = _make_key(signer)
        sig = signer.sign_evidence(k["key_id"], "ev001", '{"data": "test"}')
        assert sig["signed_id"] != ""
        assert sig["key_id"] == k["key_id"]
        assert sig["evidence_id"] == "ev001"
        assert sig["signature"] != ""
        assert sig["data_hash"] != ""
        assert sig["signed_at"] > 0

    def test_signature_deterministic_hash(self):
        signer = _make_signer()
        k = _make_key(signer)
        data = '{"data": "test"}'
        sig1 = signer.sign_evidence(k["key_id"], "ev1", data)
        sig2 = signer.sign_evidence(k["key_id"], "ev2", data)
        assert sig1["data_hash"] == sig2["data_hash"]

    def test_different_data_different_hash(self):
        signer = _make_signer()
        k = _make_key(signer)
        sig1 = signer.sign_evidence(k["key_id"], "ev1", '{"a": 1}')
        sig2 = signer.sign_evidence(k["key_id"], "ev2", '{"a": 2}')
        assert sig1["data_hash"] != sig2["data_hash"]

    def test_sign_with_revoked_key_raises(self):
        signer = _make_signer()
        k = _make_key(signer)
        signer.revoke_key(k["key_id"])
        with pytest.raises(ValueError, match="revoked"):
            signer.sign_evidence(k["key_id"], "ev1", "{}")

    def test_sign_with_nonexistent_key_raises(self):
        signer = _make_signer()
        with pytest.raises(ValueError, match="not found"):
            signer.sign_evidence("nokey", "ev1", "{}")

    def test_sign_same_evidence_multiple_times(self):
        signer = _make_signer()
        k = _make_key(signer)
        sig1 = signer.sign_evidence(k["key_id"], "ev1", '{"x":1}')
        sig2 = signer.sign_evidence(k["key_id"], "ev1", '{"x":1}')
        assert sig1["signed_id"] != sig2["signed_id"]
        assert sig1["data_hash"] == sig2["data_hash"]


# ===========================================================================
# 5. Verification
# ===========================================================================


class TestVerifySignature:
    def test_valid_signature(self):
        signer = _make_signer()
        k = _make_key(signer)
        sig = signer.sign_evidence(k["key_id"], "ev1", '{"ok": true}')
        result = signer.verify_signature(sig["signed_id"])
        assert result["valid"] is True
        assert result["evidence_id"] == "ev1"

    def test_invalid_after_tamper(self):
        signer = _make_signer()
        k = _make_key(signer)
        sig = signer.sign_evidence(k["key_id"], "ev1", '{"original": true}')
        signer._conn.execute(
            "UPDATE signed_evidence SET data_hash = ? WHERE signed_id = ?",
            ("tampered_hash", sig["signed_id"]),
        )
        signer._conn.commit()
        result = signer.verify_signature(sig["signed_id"])
        assert result["valid"] is False
        assert "mismatch" in result["reason"]

    def test_nonexistent_signed_id(self):
        signer = _make_signer()
        result = signer.verify_signature("nope")
        assert result["valid"] is False
        assert "not found" in result["reason"]

    def test_verify_after_key_revocation(self):
        signer = _make_signer()
        k = _make_key(signer)
        sig = signer.sign_evidence(k["key_id"], "ev1", '{"data": 1}')
        signer.revoke_key(k["key_id"])
        result = signer.verify_signature(sig["signed_id"])
        assert result["valid"] is True

    def test_tampered_signature(self):
        signer = _make_signer()
        k = _make_key(signer)
        sig = signer.sign_evidence(k["key_id"], "ev1", '{"data": 1}')
        signer._conn.execute(
            "UPDATE signed_evidence SET signature = 'fakesig' WHERE signed_id = ?",
            (sig["signed_id"],),
        )
        signer._conn.commit()
        result = signer.verify_signature(sig["signed_id"])
        assert result["valid"] is False


# ===========================================================================
# 6. Listing
# ===========================================================================


class TestListSignedEvidence:
    def test_list_all(self):
        signer = _make_signer()
        k = _make_key(signer)
        signer.sign_evidence(k["key_id"], "ev1", "{}")
        signer.sign_evidence(k["key_id"], "ev2", "{}")
        result = signer.list_signed_evidence()
        assert len(result) == 2

    def test_filter_by_evidence_id(self):
        signer = _make_signer()
        k = _make_key(signer)
        signer.sign_evidence(k["key_id"], "ev1", "{}")
        signer.sign_evidence(k["key_id"], "ev2", "{}")
        result = signer.list_signed_evidence(evidence_id="ev1")
        assert len(result) == 1
        assert result[0]["evidence_id"] == "ev1"

    def test_empty_list(self):
        signer = _make_signer()
        assert signer.list_signed_evidence() == []

    def test_limit(self):
        signer = _make_signer()
        k = _make_key(signer)
        for i in range(10):
            signer.sign_evidence(k["key_id"], f"ev{i}", "{}")
        result = signer.list_signed_evidence(limit=5)
        assert len(result) == 5


# ===========================================================================
# 7. Stats
# ===========================================================================


class TestGetSigningStats:
    def test_initial_stats(self):
        signer = _make_signer()
        stats = signer.get_signing_stats()
        assert stats["total_keys"] == 0
        assert stats["active_keys"] == 0
        assert stats["revoked_keys"] == 0
        assert stats["total_signed"] == 0

    def test_after_operations(self):
        signer = _make_signer()
        k1 = _make_key(signer, "k1")
        k2 = _make_key(signer, "k2")
        signer.revoke_key(k2["key_id"])
        signer.sign_evidence(k1["key_id"], "ev1", "{}")
        signer.sign_evidence(k1["key_id"], "ev2", "{}")
        stats = signer.get_signing_stats()
        assert stats["total_keys"] == 2
        assert stats["active_keys"] == 1
        assert stats["revoked_keys"] == 1
        assert stats["total_signed"] == 2


# ===========================================================================
# 8. EventBus integration
# ===========================================================================


class TestEventBusIntegration:
    def test_key_generated_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("key_generated", lambda e: collected.append(e))
        signer = _make_signer(event_bus=bus)
        signer.generate_key("evkey")
        assert len(collected) == 1
        assert collected[0].payload["alias"] == "evkey"

    def test_evidence_signed_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("evidence_signed", lambda e: collected.append(e))
        signer = _make_signer(event_bus=bus)
        k = _make_key(signer)
        signer.sign_evidence(k["key_id"], "ev1", "{}")
        assert len(collected) == 1
        assert collected[0].payload["evidence_id"] == "ev1"

    def test_signature_verified_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("signature_verified", lambda e: collected.append(e))
        signer = _make_signer(event_bus=bus)
        k = _make_key(signer)
        sig = signer.sign_evidence(k["key_id"], "ev1", "{}")
        signer.verify_signature(sig["signed_id"])
        assert len(collected) == 1

    def test_signature_invalid_event_on_tamper(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("signature_invalid", lambda e: collected.append(e))
        signer = _make_signer(event_bus=bus)
        k = _make_key(signer)
        sig = signer.sign_evidence(k["key_id"], "ev1", "{}")
        signer._conn.execute(
            "UPDATE signed_evidence SET data_hash = 'bad' WHERE signed_id = ?",
            (sig["signed_id"],),
        )
        signer._conn.commit()
        signer.verify_signature(sig["signed_id"])
        assert len(collected) == 1

    def test_no_event_without_bus(self):
        signer = _make_signer(event_bus=None)
        k = _make_key(signer)
        signer.sign_evidence(k["key_id"], "ev1", "{}")
        # Should not raise


# ===========================================================================
# 9. Singleton
# ===========================================================================


class TestSingleton:
    def test_get_evidence_signer(self):
        import sylion.security.evidence_signer as mod
        mod._signer = None
        s = get_evidence_signer(db_path=":memory:")
        assert isinstance(s, EvidenceSigner)
        mod._signer = None

    def test_reset_evidence_signer(self):
        import sylion.security.evidence_signer as mod
        mod._signer = None
        s1 = get_evidence_signer(db_path=":memory:")
        s2 = reset_evidence_signer(db_path=":memory:")
        assert s2 is not s1
        mod._signer = None

    def test_get_returns_same_instance(self):
        import sylion.security.evidence_signer as mod
        mod._signer = None
        s1 = get_evidence_signer(db_path=":memory:")
        s2 = get_evidence_signer()
        assert s1 is s2
        mod._signer = None


# ===========================================================================
# 10. Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_signing(self):
        signer = _make_signer()
        k = _make_key(signer)
        results = []
        errors = []

        def sign(i):
            try:
                sig = signer.sign_evidence(k["key_id"], f"ev{i}", f'{{"i": {i}}}')
                results.append(sig["signed_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=sign, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_verify(self):
        signer = _make_signer()
        k = _make_key(signer)
        sig = signer.sign_evidence(k["key_id"], "ev1", '{"test": true}')
        results = []
        errors = []

        def verify():
            try:
                r = signer.verify_signature(sig["signed_id"])
                results.append(r["valid"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=verify) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(results)
