"""Phase 3 W2.2 (scope-fill) — SopsAgeProvider end-to-end tests.

Each test exercises real X25519 + age + AES-GCM crypto via :mod:`pyrage`
and :mod:`cryptography` — no stubs. We assert:

* Round-trip: encrypt → decrypt yields the same plaintext.
* Tamper detection: mutating a leaf ciphertext (or its name AAD) makes
  decrypt raise.
* Multi-recipient: a file encrypted to two recipients can be decrypted
  by *either* identity in isolation.
* ``prime_key_store_from_sops`` materialises secrets into the unified
  store under scope ``secrets``.
* No identity → ``decrypt_file`` raises :class:`DecryptionUnavailable`.

We *do not* try to make the file format compatible with the real
`sops` binary — sylion-secrets/v1 is our own envelope. The tests that
care about real interoperability would shell out to ``sops`` if a
binary is on PATH; we leave that for Phase 4.
"""
from __future__ import annotations

import base64
from pathlib import Path

import pytest
import yaml

from sylion.security.sops_provider import (
    DecryptionUnavailable,
    SOPS_FILE_HEADER,
    SopsAgeProvider,
    SopsFileError,
    generate_age_identity,
    prime_key_store_from_sops,
)


@pytest.fixture
def keypair() -> tuple[str, str]:
    """Return ``(identity, recipient)`` strings."""
    return generate_age_identity()


@pytest.fixture
def provider(monkeypatch, keypair):
    identity, _ = keypair
    monkeypatch.setenv("SYLION_AGE_IDENTITY", identity)
    return SopsAgeProvider()


# ---------------------------------------------------------------------------
# round-trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_encrypt_then_decrypt_returns_same_plaintext(
        self, provider, keypair, tmp_path
    ):
        _, recipient = keypair
        path = tmp_path / "dev.yaml"
        provider.encrypt_file(
            path,
            secrets={
                "OPENAI_API_KEY": "fixture-openai-key",
                "DATABASE_URL": "postgres://user:pass@db/sylion",
            },
            recipients=[recipient],
        )

        out = provider.decrypt_file(path)
        assert out == {
            "OPENAI_API_KEY": "fixture-openai-key",
            "DATABASE_URL": "postgres://user:pass@db/sylion",
        }

    def test_file_starts_with_canonical_header(
        self, provider, keypair, tmp_path
    ):
        _, recipient = keypair
        path = tmp_path / "dev.yaml"
        provider.encrypt_file(path, {"X": "y"}, recipients=[recipient])
        text = path.read_text(encoding="utf-8")
        assert text.startswith(SOPS_FILE_HEADER + "\n")

    def test_secrets_are_actually_encrypted_on_disk(
        self, provider, keypair, tmp_path
    ):
        _, recipient = keypair
        path = tmp_path / "dev.yaml"
        secret = "this-string-must-not-leak"
        provider.encrypt_file(path, {"X": secret}, recipients=[recipient])
        raw = path.read_text(encoding="utf-8")
        assert secret not in raw, "plaintext leaked into encrypted file"


# ---------------------------------------------------------------------------
# tamper detection
# ---------------------------------------------------------------------------


class TestTamperDetection:
    def test_mutating_leaf_ciphertext_breaks_decrypt(
        self, provider, keypair, tmp_path
    ):
        _, recipient = keypair
        path = tmp_path / "dev.yaml"
        provider.encrypt_file(path, {"X": "y"}, recipients=[recipient])

        # Flip a byte in the leaf ciphertext.
        body = yaml.safe_load(path.read_text(encoding="utf-8").split("\n", 1)[1])
        leaf = base64.b64decode(body["secrets"]["X"]["enc"])
        flipped = bytearray(leaf)
        flipped[-1] ^= 0x01
        body["secrets"]["X"]["enc"] = base64.b64encode(bytes(flipped)).decode("ascii")
        path.write_text(
            SOPS_FILE_HEADER + "\n" + yaml.safe_dump(body, sort_keys=True),
            encoding="utf-8",
        )

        with pytest.raises(SopsFileError):
            provider.decrypt_file(path)

    def test_renaming_a_leaf_breaks_decrypt(
        self, provider, keypair, tmp_path
    ):
        # Name is bound as AAD — renaming on disk must invalidate the leaf.
        _, recipient = keypair
        path = tmp_path / "dev.yaml"
        provider.encrypt_file(path, {"X": "y"}, recipients=[recipient])

        body = yaml.safe_load(path.read_text(encoding="utf-8").split("\n", 1)[1])
        body["secrets"]["X_RENAMED"] = body["secrets"].pop("X")
        path.write_text(
            SOPS_FILE_HEADER + "\n" + yaml.safe_dump(body, sort_keys=True),
            encoding="utf-8",
        )

        with pytest.raises(SopsFileError):
            provider.decrypt_file(path)

    def test_missing_header_raises(self, provider, tmp_path):
        path = tmp_path / "junk.yaml"
        path.write_text("not_our_format: true\n", encoding="utf-8")
        with pytest.raises(SopsFileError):
            provider.decrypt_file(path)


# ---------------------------------------------------------------------------
# multi-recipient
# ---------------------------------------------------------------------------


class TestMultiRecipient:
    def test_either_recipient_can_decrypt(self, monkeypatch, tmp_path):
        id1, rcp1 = generate_age_identity()
        id2, rcp2 = generate_age_identity()
        path = tmp_path / "dev.yaml"

        # Encryptor doesn't need an identity — just recipients.
        monkeypatch.delenv("SYLION_AGE_IDENTITY", raising=False)
        encryptor = SopsAgeProvider()
        encryptor.encrypt_file(path, {"X": "shared"}, recipients=[rcp1, rcp2])

        # Decrypt as identity 1
        monkeypatch.setenv("SYLION_AGE_IDENTITY", id1)
        assert SopsAgeProvider().decrypt_file(path) == {"X": "shared"}

        # And as identity 2
        monkeypatch.setenv("SYLION_AGE_IDENTITY", id2)
        assert SopsAgeProvider().decrypt_file(path) == {"X": "shared"}

    def test_add_recipient_does_not_change_leaf_bytes(
        self, provider, keypair, tmp_path
    ):
        _, recipient = keypair
        path = tmp_path / "dev.yaml"
        provider.encrypt_file(path, {"X": "y"}, recipients=[recipient])

        body_before = yaml.safe_load(
            path.read_text(encoding="utf-8").split("\n", 1)[1]
        )
        leaf_before = body_before["secrets"]["X"]["enc"]

        _, rcp2 = generate_age_identity()
        provider.add_recipient(path, rcp2)

        body_after = yaml.safe_load(
            path.read_text(encoding="utf-8").split("\n", 1)[1]
        )
        assert body_after["secrets"]["X"]["enc"] == leaf_before, (
            "add_recipient must not re-encrypt leaf values"
        )
        # Data key should now wrap to TWO recipients
        assert len(body_after["recipients"]) == 2


# ---------------------------------------------------------------------------
# missing identity
# ---------------------------------------------------------------------------


class TestNoIdentity:
    def test_decrypt_without_identity_raises_unavailable(
        self, monkeypatch, keypair, tmp_path
    ):
        identity, recipient = keypair
        path = tmp_path / "dev.yaml"

        monkeypatch.setenv("SYLION_AGE_IDENTITY", identity)
        SopsAgeProvider().encrypt_file(path, {"X": "y"}, [recipient])

        monkeypatch.delenv("SYLION_AGE_IDENTITY", raising=False)
        monkeypatch.delenv("SYLION_AGE_IDENTITY_FILE", raising=False)
        with pytest.raises(DecryptionUnavailable):
            SopsAgeProvider().decrypt_file(path)

    def test_encrypt_with_no_recipients_raises(
        self, provider, tmp_path
    ):
        with pytest.raises(SopsFileError):
            provider.encrypt_file(tmp_path / "x.yaml", {"X": "y"}, recipients=[])

    def test_identity_file_supports_comments_and_blank_lines(
        self, monkeypatch, tmp_path
    ):
        identity, recipient = generate_age_identity()
        keyfile = tmp_path / "id.txt"
        keyfile.write_text(
            f"# operator A\n\n{identity}\n# end\n",
            encoding="utf-8",
        )

        monkeypatch.delenv("SYLION_AGE_IDENTITY", raising=False)
        monkeypatch.setenv("SYLION_AGE_IDENTITY_FILE", str(keyfile))

        path = tmp_path / "dev.yaml"
        SopsAgeProvider().encrypt_file(path, {"X": "y"}, [recipient])
        assert SopsAgeProvider().decrypt_file(path) == {"X": "y"}


# ---------------------------------------------------------------------------
# introspection without decrypt
# ---------------------------------------------------------------------------


class TestIntrospection:
    def test_list_secrets_does_not_require_identity(
        self, monkeypatch, keypair, tmp_path
    ):
        identity, recipient = keypair
        monkeypatch.setenv("SYLION_AGE_IDENTITY", identity)
        path = tmp_path / "dev.yaml"
        SopsAgeProvider().encrypt_file(
            path, {"A": "1", "B": "2"}, recipients=[recipient]
        )

        monkeypatch.delenv("SYLION_AGE_IDENTITY", raising=False)
        names = SopsAgeProvider().list_secrets(path)
        assert names == ["A", "B"]

    def test_list_recipients_returns_what_was_set(
        self, provider, keypair, tmp_path
    ):
        _, recipient = keypair
        path = tmp_path / "dev.yaml"
        provider.encrypt_file(path, {"X": "y"}, recipients=[recipient])
        assert provider.list_recipients(path) == [recipient]


# ---------------------------------------------------------------------------
# add_secret / remove_secret
# ---------------------------------------------------------------------------


class TestMutation:
    def test_add_secret_appears_on_decrypt(
        self, provider, keypair, tmp_path
    ):
        _, recipient = keypair
        path = tmp_path / "dev.yaml"
        provider.encrypt_file(path, {"A": "1"}, recipients=[recipient])
        provider.add_secret(path, "B", "2")
        assert provider.decrypt_file(path) == {"A": "1", "B": "2"}

    def test_remove_secret_drops_from_file(
        self, provider, keypair, tmp_path
    ):
        _, recipient = keypair
        path = tmp_path / "dev.yaml"
        provider.encrypt_file(path, {"A": "1", "B": "2"}, [recipient])
        assert provider.remove_secret(path, "A") is True
        assert provider.decrypt_file(path) == {"B": "2"}
        assert provider.remove_secret(path, "GHOST") is False


# ---------------------------------------------------------------------------
# prime_key_store_from_sops integration
# ---------------------------------------------------------------------------


class TestPrimeKeyStore:
    def test_prime_loads_secrets_into_unified_store(
        self, monkeypatch, tmp_path
    ):
        from sylion.security.key_store_unified import (
            reset_key_store_unified,
            get_key_store_unified,
        )

        identity, recipient = generate_age_identity()
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        env_path = secrets_dir / "test.yaml"

        monkeypatch.setenv("SYLION_AGE_IDENTITY", identity)
        SopsAgeProvider().encrypt_file(
            env_path,
            {"OPENAI_API_KEY": "sk-from-sops",
             "DB_URL": "postgres://primed"},
            recipients=[recipient],
        )

        # Use a fresh in-memory store for the test.
        reset_key_store_unified(db_path=":memory:", backend="memory")
        n = prime_key_store_from_sops(env="test", secrets_dir=secrets_dir)
        assert n == 2

        store = get_key_store_unified()
        assert store.get("OPENAI_API_KEY") == "sk-from-sops"
        assert store.get("DB_URL") == "postgres://primed"

        # All entries scoped under "secrets"
        keys = [k for k in store.list_keys(scope="secrets")]
        assert {k["key_id"] for k in keys} == {"OPENAI_API_KEY", "DB_URL"}

    def test_prime_silent_when_file_missing(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.delenv("SYLION_AGE_IDENTITY", raising=False)
        n = prime_key_store_from_sops(env="ghost", secrets_dir=tmp_path)
        assert n == 0

    def test_prime_silent_when_no_identity(
        self, monkeypatch, tmp_path
    ):
        # Create an encrypted file with one identity, then prime as a
        # process with no identity loaded — should warn and skip.
        identity, recipient = generate_age_identity()
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        env_path = secrets_dir / "test.yaml"

        monkeypatch.setenv("SYLION_AGE_IDENTITY", identity)
        SopsAgeProvider().encrypt_file(
            env_path, {"X": "y"}, recipients=[recipient]
        )

        monkeypatch.delenv("SYLION_AGE_IDENTITY", raising=False)
        monkeypatch.delenv("SYLION_AGE_IDENTITY_FILE", raising=False)
        assert prime_key_store_from_sops(env="test", secrets_dir=secrets_dir) == 0
