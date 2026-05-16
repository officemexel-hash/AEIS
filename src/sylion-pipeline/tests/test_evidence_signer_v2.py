"""
Tests for SYLION Security -- Evidence Signer V2

Ed25519 cryptographic signing integrated into the EvidenceSpine.
Phase 2 masterplan validation.
"""

import pytest

from sylion.security.evidence_signer_v2 import (
    SignedEvidenceSpine,
    generate_keypair,
    sign_entry,
    verify_signature,
)
from sylion.core.evidence_spine import EvidenceEntry


# ============================================================================
# 1. Pure function tests
# ============================================================================


class TestKeypairGeneration:
    """generate_keypair() produces valid Ed25519 key material."""

    def test_returns_two_byte_strings(self):
        priv, pub = generate_keypair()
        assert isinstance(priv, bytes)
        assert isinstance(pub, bytes)

    def test_key_lengths(self):
        """Ed25519 keys are 32 bytes each."""
        priv, pub = generate_keypair()
        assert len(priv) == 32
        assert len(pub) == 32

    def test_deterministic_public_from_private(self):
        """Same private key always derives the same public key."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        priv, pub = generate_keypair()
        pk = Ed25519PrivateKey.from_private_bytes(priv)
        derived_pub = pk.public_key().public_bytes_raw()
        assert derived_pub == pub

    def test_unique_keys_each_call(self):
        """Each call produces a different keypair."""
        priv1, pub1 = generate_keypair()
        priv2, pub2 = generate_keypair()
        assert priv1 != priv2
        assert pub1 != pub2


class TestSignAndVerify:
    """sign_entry() and verify_signature() round-trip correctly."""

    def test_valid_signature_verifies(self):
        priv, pub = generate_keypair()
        data = b"hello evidence spine"
        sig = sign_entry(priv, data)
        assert verify_signature(pub, sig, data) is True

    def test_signature_is_64_bytes(self):
        priv, _ = generate_keypair()
        sig = sign_entry(priv, b"data")
        assert len(sig) == 64

    def test_wrong_data_fails(self):
        priv, pub = generate_keypair()
        sig = sign_entry(priv, b"correct data")
        assert verify_signature(pub, sig, b"tampered data") is False

    def test_wrong_key_fails(self):
        priv1, _ = generate_keypair()
        _, pub2 = generate_keypair()
        sig = sign_entry(priv1, b"data")
        assert verify_signature(pub2, sig, b"data") is False

    def test_corrupted_signature_fails(self):
        priv, pub = generate_keypair()
        sig = sign_entry(priv, b"data")
        corrupted = bytearray(sig)
        corrupted[0] ^= 0xFF
        assert verify_signature(pub, bytes(corrupted), b"data") is False

    def test_empty_data_signs(self):
        priv, pub = generate_keypair()
        sig = sign_entry(priv, b"")
        assert verify_signature(pub, sig, b"") is True

    def test_large_payload_signs(self):
        priv, pub = generate_keypair()
        data = b"x" * 1_000_000
        sig = sign_entry(priv, data)
        assert verify_signature(pub, sig, data) is True


class TestTamperDetection:
    """Modifying signed data makes verification fail."""

    def test_single_bit_flip_detected(self):
        priv, pub = generate_keypair()
        original = b"critical evidence payload"
        sig = sign_entry(priv, original)
        tampered = bytearray(original)
        tampered[5] ^= 0x01  # flip one bit
        assert verify_signature(pub, sig, bytes(tampered)) is False

    def test_truncation_detected(self):
        priv, pub = generate_keypair()
        original = b"do not truncate this"
        sig = sign_entry(priv, original)
        truncated = original[:-3]
        assert verify_signature(pub, sig, truncated) is False

    def test_append_detected(self):
        priv, pub = generate_keypair()
        original = b"exact content"
        sig = sign_entry(priv, original)
        appended = original + b"extra"
        assert verify_signature(pub, sig, appended) is False


# ============================================================================
# 2. SignedEvidenceSpine integration tests
# ============================================================================


def _make_entry(source_plan: str = "test-plan", event_type: str = "test.event",
                payload: dict | None = None, actor_id: str = "tester") -> EvidenceEntry:
    return EvidenceEntry(
        source_plan=source_plan,
        event_type=event_type,
        payload=payload or {"action": "test"},
        actor_id=actor_id,
    )


class TestSignedEvidenceSpineAppend:
    """SignedEvidenceSpine.append() auto-signs when a key is configured."""

    def test_append_with_signing(self):
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        entry = _make_entry()
        result = spine.append(entry)

        assert "signature" in result
        assert result["signature"] != ""
        assert "public_key" in result
        assert result["public_key"] is not None

    def test_entry_has_signature_after_append(self):
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        entry = _make_entry()
        spine.append(entry)
        assert entry.signature != ""

    def test_multiple_appends_all_signed(self):
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        results = []
        for i in range(5):
            entry = _make_entry(payload={"seq": i})
            results.append(spine.append(entry))

        assert all(r["signature"] for r in results)
        # All signatures should be different (different hashes signed)
        sigs = [r["signature"] for r in results]
        assert len(set(sigs)) == 5


class TestSignedEvidenceSpineChainVerification:
    """verify_chain() checks both SHA-256 and Ed25519."""

    def test_valid_chain_verifies(self):
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        for i in range(5):
            spine.append(_make_entry(payload={"i": i}))

        ok, msg = spine.verify_chain()
        assert ok is True
        assert "5 entries" in msg
        assert "5 signed" in msg

    def test_tampered_hash_breaks_chain(self):
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        spine.append(_make_entry())
        spine.append(_make_entry())

        # Tamper with a hash directly in the DB
        spine.spine._conn.execute(
            "UPDATE evidence_spine SET hash = 'deadbeef' WHERE rowid = 1"
        )
        spine.spine._conn.commit()

        ok, msg = spine.verify_chain()
        assert ok is False
        assert "SHA-256 chain broken" in msg

    def test_tampered_signature_detected(self):
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        spine.append(_make_entry())

        # Tamper with the signature
        spine.spine._conn.execute(
            "UPDATE evidence_spine SET signature = 'AAAA' WHERE rowid = 1"
        )
        spine.spine._conn.commit()

        ok, msg = spine.verify_chain()
        assert ok is False
        assert "signature mismatch" in msg

    def test_tampered_payload_detected(self):
        """Tampering with the payload changes the hash, breaking SHA-256 chain."""
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        spine.append(_make_entry(payload={"amount": 100}))
        spine.append(_make_entry(payload={"amount": 200}))

        # Tamper with the payload of the first entry
        import json
        spine.spine._conn.execute(
            "UPDATE evidence_spine SET payload = ? WHERE rowid = 1",
            (json.dumps({"amount": 99999}),),
        )
        spine.spine._conn.commit()

        ok, msg = spine.verify_chain()
        assert ok is False


class TestSignedEvidenceSpineBackwardCompat:
    """When no key is configured, behaves like unsigned EvidenceSpine."""

    def test_unsigned_append_works(self):
        spine = SignedEvidenceSpine()  # no key
        entry = _make_entry()
        result = spine.append(entry)

        assert "entry_id" in result
        assert "hash" in result
        # No signature key in result for unsigned mode
        assert result.get("signature", "") == ""

    def test_unsigned_chain_valid(self):
        spine = SignedEvidenceSpine()
        for i in range(3):
            spine.append(_make_entry(payload={"i": i}))

        ok, msg = spine.verify_chain()
        assert ok is True
        assert "3 entries" in msg

    def test_is_signing_enabled_false_without_key(self):
        spine = SignedEvidenceSpine()
        assert spine.is_signing_enabled is False

    def test_is_signing_enabled_true_with_key(self):
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        assert spine.is_signing_enabled is True

    def test_public_key_b64_none_without_key(self):
        spine = SignedEvidenceSpine()
        assert spine.public_key_b64 is None

    def test_public_key_b64_present_with_key(self):
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        assert spine.public_key_b64 is not None
        assert len(spine.public_key_b64) > 0

    def test_mixed_signed_and_unsigned_entries(self):
        """A spine can have unsigned entries (appended before key was set)
        alongside signed entries.  verify_chain() should still pass."""
        import tempfile, os

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            # Phase 1: unsigned entries
            unsigned_spine = SignedEvidenceSpine(db_path=db_path)
            unsigned_spine.append(_make_entry(payload={"phase": "unsigned"}))
            assert unsigned_spine.is_signing_enabled is False
            # Close the connection so the next spine can open the same file
            unsigned_spine.spine._conn.close()

            # Phase 2: signed, wrapping the same DB
            priv, pub = generate_keypair()
            signed_spine = SignedEvidenceSpine(
                db_path=db_path,
                private_key_bytes=priv,
                public_key_bytes=pub,
            )
            signed_spine.append(_make_entry(payload={"phase": "signed"}))

            # Chain should be valid: unsigned entry passes SHA-256 only,
            # signed entry passes both SHA-256 and Ed25519
            ok, msg = signed_spine.verify_chain()
            assert ok is True
            assert "1 signed" in msg

            signed_spine.spine._conn.close()
        finally:
            try:
                os.unlink(db_path)
            except PermissionError:
                pass

    def test_private_key_derives_public(self):
        """If only private_key_bytes is given, public key is derived."""
        priv, pub_expected = generate_keypair()
        spine = SignedEvidenceSpine(private_key_bytes=priv)
        assert spine._public_key == pub_expected
        assert spine.is_signing_enabled is True


class TestSignedEvidenceSpineQuery:
    """Query passthrough works correctly."""

    def test_query_returns_entries(self):
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        spine.append(_make_entry(source_plan="plan-A"))
        spine.append(_make_entry(source_plan="plan-B"))

        all_entries = spine.query()
        assert len(all_entries) == 2

        filtered = spine.query(source_plan="plan-A")
        assert len(filtered) == 1
        assert filtered[0]["source_plan"] == "plan-A"

    def test_replay_returns_entries(self):
        import time
        priv, pub = generate_keypair()
        spine = SignedEvidenceSpine(
            private_key_bytes=priv, public_key_bytes=pub
        )
        spine.append(_make_entry())
        time.sleep(0.01)
        t = time.time()
        spine.append(_make_entry())

        replayed = spine.replay(since=t)
        assert len(replayed) >= 1
