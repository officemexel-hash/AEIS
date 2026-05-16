"""Phase 3 W2.2 (scope-fill) — real SOPS+age envelope-encryption provider.

Until this module landed, ``key_store_unified`` had two backends with
real persistence (``file``, ``memory``) but the encryption layer was
either Fernet (when ``cryptography`` was installed) or *base64* —
plaintext-equivalent. Production secrets shipped via env-vars and the
fail-fast :func:`assert_safe_to_serve` was the only thing standing
between the operator and a leaked key.

This module implements a **SOPS-style envelope-encryption provider** in
process. It does *not* shell out to the `sops` binary; instead it uses
:mod:`pyrage` (a Rust-backed age v1 implementation) to wrap a per-file
*data key*, and :mod:`cryptography` AES-256-GCM to encrypt each leaf
value under that data key. The on-disk format is YAML, keyed by
``# sylion-secrets/v1`` so it is unmistakably *our* format — not a
drop-in for ``sops`` files (Phase 4 may add a ``SopsBinaryProvider`` for
that). The semantics, however, mirror SOPS:

* Each environment lives in ``secrets/{env}.yaml``.
* The *data key* is a 32-byte AES-GCM key, freshly generated per file.
* The data key is age-encrypted to one or more X25519 recipient public
  keys (``age1...``) listed in the file. Adding a new ops engineer
  means adding their public key as a recipient and re-wrapping the
  data key — value ciphertexts stay untouched.
* Each leaf secret is AES-GCM-encrypted under the data key with a
  random 12-byte nonce. Tampering with any value invalidates only
  that value (Poly1305 catches it on decrypt).

Identity (private key) selection:

* ``SYLION_AGE_IDENTITY``   → literal ``AGE-SECRET-KEY-...`` string.
* ``SYLION_AGE_IDENTITY_FILE`` → path to a key file (one identity per
  line, blank lines & ``#`` comments ignored).
* If neither is set the provider operates in *encrypt-only* mode and
  raises :class:`DecryptionUnavailable` on any ``get()``.

Why a separate module instead of folding into ``key_store_unified``?

The unified store still needs to back its SQLite schema; the SOPS
provider is a **file-backed source of truth** for environment
secrets that get *materialised into* the store at startup (see
:func:`prime_key_store_from_sops`). Keeping it standalone means the
SQLite store is unaware of the encryption-at-rest layer, and tests
can exercise either independently.
"""
from __future__ import annotations

import base64
import logging
import os
import secrets as _stdsecrets
from pathlib import Path
from typing import Iterable

import yaml

log = logging.getLogger("sylion.security.sops_provider")


SOPS_FILE_HEADER = "# sylion-secrets/v1"
DATA_KEY_BYTES = 32          # AES-256
LEAF_NONCE_BYTES = 12        # GCM standard


class DecryptionUnavailable(RuntimeError):
    """Raised when the provider has no identity loaded but a value is requested."""


class SopsFileError(ValueError):
    """File on disk is malformed or fails authentication."""


# ---------------------------------------------------------------------------
# crypto helpers
# ---------------------------------------------------------------------------


def _aesgcm_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """AES-GCM encrypt → ``nonce(12) || ciphertext_with_tag``."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = _stdsecrets.token_bytes(LEAF_NONCE_BYTES)
    blob = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce + blob


def _aesgcm_decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(blob) < LEAF_NONCE_BYTES + 16:  # 16-byte tag minimum
        raise SopsFileError("ciphertext too short")
    nonce, ct = blob[:LEAF_NONCE_BYTES], blob[LEAF_NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ct, aad)


def _age_encrypt(plaintext: bytes, recipients: list[str]) -> bytes:
    """Encrypt ``plaintext`` to one or more age recipients (``age1...``)."""
    import pyrage
    from pyrage import x25519

    rcps = [x25519.Recipient.from_str(r) for r in recipients]
    return pyrage.encrypt(plaintext, rcps)


def _age_decrypt(ciphertext: bytes, identities: list[str]) -> bytes:
    import pyrage
    from pyrage import x25519

    ids = [x25519.Identity.from_str(s) for s in identities]
    return pyrage.decrypt(ciphertext, ids)


def _load_identities() -> list[str]:
    """Resolve identity material from env. Returns possibly-empty list."""
    out: list[str] = []
    inline = os.environ.get("SYLION_AGE_IDENTITY", "").strip()
    if inline:
        out.extend(line.strip() for line in inline.splitlines() if line.strip())
    path = os.environ.get("SYLION_AGE_IDENTITY_FILE", "").strip()
    if path:
        p = Path(path).expanduser()
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                out.append(line)
        else:
            log.warning("SYLION_AGE_IDENTITY_FILE points to missing path: %s", p)
    return out


# ---------------------------------------------------------------------------
# Identity generation (helper for ops bootstrap)
# ---------------------------------------------------------------------------


def generate_age_identity() -> tuple[str, str]:
    """Return ``(identity, public)`` — the secret + the recipient string.

    Used by the ``scripts/secrets_init.py`` bootstrap; we expose it here
    so tests don't have to import pyrage themselves.
    """
    from pyrage import x25519

    ident = x25519.Identity.generate()
    return str(ident), str(ident.to_public())


# ---------------------------------------------------------------------------
# SopsAgeProvider
# ---------------------------------------------------------------------------


class SopsAgeProvider:
    """File-backed envelope-encryption provider.

    Lifecycle:

    * :meth:`encrypt_file` — write a fresh secrets file to disk, fresh
      data key, age-wrapped to ``recipients``.
    * :meth:`decrypt_file` — re-read a file using the loaded identity
      and return ``{name: plaintext}``.
    * :meth:`add_secret` / :meth:`remove_secret` — round-trip the file
      to mutate a single value.
    * :meth:`add_recipient` — re-wrap the data key for a new operator
      without re-encrypting the leaf values.

    Thread-safety: the provider holds no mutable state beyond the
    identity list. Each method is a stateless transform on the file
    bytes plus a per-call data key. It's safe to share across threads
    so long as concurrent writers don't race on the same file path.
    """

    def __init__(self, identities: list[str] | None = None):
        self._identities = list(identities) if identities is not None else _load_identities()

    # ------------------------------------------------------------------
    # high-level file I/O
    # ------------------------------------------------------------------

    def encrypt_file(
        self,
        path: str | Path,
        secrets: dict[str, str],
        recipients: list[str],
    ) -> Path:
        """Serialise ``secrets`` to ``path`` under fresh envelope.

        Returns the resolved Path so callers can chain.
        Raises :class:`SopsFileError` if recipients is empty.
        """
        if not recipients:
            raise SopsFileError("encrypt_file requires at least one recipient")

        data_key = _stdsecrets.token_bytes(DATA_KEY_BYTES)

        encrypted: dict[str, dict] = {}
        for name, value in secrets.items():
            blob = _aesgcm_encrypt(data_key, value.encode("utf-8"), aad=name.encode("utf-8"))
            encrypted[name] = {
                "enc": base64.b64encode(blob).decode("ascii"),
                "type": "str",
            }

        wrapped = _age_encrypt(data_key, recipients)
        body = {
            "recipients": list(recipients),
            "data_key": {
                "age": base64.b64encode(wrapped).decode("ascii"),
            },
            "secrets": encrypted,
        }

        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        text = SOPS_FILE_HEADER + "\n" + yaml.safe_dump(body, sort_keys=True)
        out_path.write_text(text, encoding="utf-8")
        log.info("sops: wrote %s with %d secrets / %d recipients",
                 out_path, len(secrets), len(recipients))
        return out_path

    def decrypt_file(self, path: str | Path) -> dict[str, str]:
        if not self._identities:
            raise DecryptionUnavailable(
                "no SYLION_AGE_IDENTITY / SYLION_AGE_IDENTITY_FILE configured"
            )
        body = self._load_body(path)
        wrapped_b64 = body.get("data_key", {}).get("age")
        if not wrapped_b64:
            raise SopsFileError(f"{path}: missing data_key.age")
        try:
            data_key = _age_decrypt(base64.b64decode(wrapped_b64), self._identities)
        except Exception as e:  # pyrage.DecryptError, etc.
            raise SopsFileError(f"{path}: data_key unwrap failed: {e}") from e

        out: dict[str, str] = {}
        for name, leaf in (body.get("secrets") or {}).items():
            blob = base64.b64decode(leaf["enc"])
            try:
                plaintext = _aesgcm_decrypt(data_key, blob, aad=name.encode("utf-8"))
            except Exception as e:
                raise SopsFileError(f"{path}: leaf {name!r} decrypt failed: {e}") from e
            out[name] = plaintext.decode("utf-8")
        return out

    def add_secret(
        self,
        path: str | Path,
        name: str,
        value: str,
    ) -> None:
        """Round-trip ``path``, add ``name=value``, write back.

        Cheaper than ``encrypt_file`` because we reuse the existing
        data key and only re-encrypt the new leaf.
        """
        if not self._identities:
            raise DecryptionUnavailable(
                "add_secret requires identity to unwrap data key"
            )
        body = self._load_body(path)
        wrapped_b64 = body["data_key"]["age"]
        data_key = _age_decrypt(base64.b64decode(wrapped_b64), self._identities)

        leaf_blob = _aesgcm_encrypt(data_key, value.encode("utf-8"), aad=name.encode("utf-8"))
        body.setdefault("secrets", {})[name] = {
            "enc": base64.b64encode(leaf_blob).decode("ascii"),
            "type": "str",
        }

        text = SOPS_FILE_HEADER + "\n" + yaml.safe_dump(body, sort_keys=True)
        Path(path).write_text(text, encoding="utf-8")

    def remove_secret(self, path: str | Path, name: str) -> bool:
        body = self._load_body(path)
        sec = body.get("secrets") or {}
        if name not in sec:
            return False
        sec.pop(name)
        body["secrets"] = sec
        text = SOPS_FILE_HEADER + "\n" + yaml.safe_dump(body, sort_keys=True)
        Path(path).write_text(text, encoding="utf-8")
        return True

    def add_recipient(self, path: str | Path, recipient: str) -> None:
        """Re-wrap the data key so ``recipient`` (an ``age1...`` pubkey)
        can also decrypt — leaves leaf ciphertexts untouched."""
        if not self._identities:
            raise DecryptionUnavailable(
                "add_recipient requires identity to unwrap data key first"
            )
        body = self._load_body(path)
        wrapped_b64 = body["data_key"]["age"]
        data_key = _age_decrypt(base64.b64decode(wrapped_b64), self._identities)

        new_recipients = list(dict.fromkeys(list(body.get("recipients", [])) + [recipient]))
        wrapped = _age_encrypt(data_key, new_recipients)
        body["recipients"] = new_recipients
        body["data_key"]["age"] = base64.b64encode(wrapped).decode("ascii")

        text = SOPS_FILE_HEADER + "\n" + yaml.safe_dump(body, sort_keys=True)
        Path(path).write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # introspection
    # ------------------------------------------------------------------

    def list_secrets(self, path: str | Path) -> list[str]:
        """Return the secret names present in ``path`` *without* decrypting them."""
        body = self._load_body(path)
        return sorted((body.get("secrets") or {}).keys())

    def list_recipients(self, path: str | Path) -> list[str]:
        body = self._load_body(path)
        return list(body.get("recipients") or [])

    def has_identity(self) -> bool:
        return bool(self._identities)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _load_body(self, path: str | Path) -> dict:
        p = Path(path)
        if not p.exists():
            raise SopsFileError(f"secrets file not found: {p}")
        text = p.read_text(encoding="utf-8")
        first_nl = text.find("\n")
        header = text[:first_nl] if first_nl >= 0 else text
        if header.strip() != SOPS_FILE_HEADER:
            raise SopsFileError(
                f"{p}: missing or wrong header (expected {SOPS_FILE_HEADER!r}, "
                f"got {header!r})"
            )
        body = yaml.safe_load(text[first_nl + 1:]) or {}
        if not isinstance(body, dict):
            raise SopsFileError(f"{p}: top-level YAML must be a mapping")
        return body


# ---------------------------------------------------------------------------
# Integration with key_store_unified
# ---------------------------------------------------------------------------


def prime_key_store_from_sops(
    env: str | None = None,
    secrets_dir: str | Path | None = None,
    *,
    actor: str = "sops-bootstrap",
) -> int:
    """Decrypt ``secrets/{env}.yaml`` and put each value into the
    unified key store under scope ``secrets``.

    Returns the number of secrets primed. Silent no-op if:

    * the file doesn't exist (the deployment hasn't migrated yet), or
    * no identity is configured (dev environment without operator key).

    This is meant to be called from :func:`sylion.api.app.lifespan`
    *before* any module reads from the store.
    """
    env = env or os.environ.get("SYLION_AEIS_ENV", "dev")
    base = Path(secrets_dir) if secrets_dir else Path(os.environ.get(
        "SYLION_SECRETS_DIR",
        Path(__file__).resolve().parent.parent.parent / "secrets",
    ))
    path = base / f"{env}.yaml"
    if not path.exists():
        log.info("sops prime: %s not found, skipping", path)
        return 0

    provider = SopsAgeProvider()
    if not provider.has_identity():
        log.warning(
            "sops prime: file %s exists but no SYLION_AGE_IDENTITY[_FILE] "
            "configured — leaving env-vars untouched",
            path,
        )
        return 0

    secrets = provider.decrypt_file(path)
    from sylion.security.key_store_unified import get_key_store_unified

    store = get_key_store_unified()
    for name, value in secrets.items():
        store.put(name, value, scope="secrets",
                  metadata={"source": "sops", "file": str(path)},
                  actor=actor)
    log.info("sops prime: loaded %d secrets from %s", len(secrets), path)
    return len(secrets)


__all__ = [
    "DecryptionUnavailable",
    "SopsFileError",
    "SopsAgeProvider",
    "SOPS_FILE_HEADER",
    "generate_age_identity",
    "prime_key_store_from_sops",
]
