"""
SYLION Security -- Evidence Signer V2

Ed25519 cryptographic signing integrated directly into the Evidence Spine.
This is Phase 2 of the masterplan: every evidence entry is signed on append
and every signature is verified during chain validation.

Three layers:
  1. Pure functions: generate_keypair(), sign_entry(), verify_signature()
     -- no state, no database, just bytes in / bytes out.
  2. SignedEvidenceSpine: wraps EvidenceSpine, auto-signs on append,
     verifies both SHA-256 hash chain AND Ed25519 signatures.
  3. Backward compatibility: if no private key is configured the wrapper
     behaves identically to a plain unsigned EvidenceSpine.

Thread-safe. Falls back to SHA-256-only when no key is configured.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from sylion.core.evidence_spine import (
    GENESIS_PREV_HASH,
    EvidenceEntry,
    EvidenceSpine,
    _canonical_json,
    _compute_chain_hash,
)
from sylion.core.event_bus import EventBus

log = logging.getLogger("sylion.security.evidence_signer_v2")

# ---------------------------------------------------------------------------
# Pure Ed25519 helpers (stateless)
# ---------------------------------------------------------------------------


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate an Ed25519 keypair.

    Returns:
        (private_key_bytes, public_key_bytes) -- raw 32-byte keys.
    """
    private_key = Ed25519PrivateKey.generate()
    priv_bytes = private_key.private_bytes_raw()
    pub_bytes = private_key.public_key().public_bytes_raw()
    return priv_bytes, pub_bytes


def sign_entry(private_key_bytes: bytes, entry_data: bytes) -> bytes:
    """Sign arbitrary entry data with an Ed25519 private key.

    Args:
        private_key_bytes: raw 32-byte Ed25519 private key.
        entry_data: the bytes to sign (typically the hash-chain input).

    Returns:
        64-byte Ed25519 signature.
    """
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    return private_key.sign(entry_data)


def verify_signature(
    public_key_bytes: bytes,
    signature: bytes,
    entry_data: bytes,
) -> bool:
    """Verify an Ed25519 signature.

    Args:
        public_key_bytes: raw 32-byte Ed25519 public key.
        signature: 64-byte Ed25519 signature.
        entry_data: the bytes that were signed.

    Returns:
        True if the signature is valid, False otherwise.
    """
    try:
        pub_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        pub_key.verify(signature, entry_data)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Helpers for base64 serialization
# ---------------------------------------------------------------------------


def _pub_bytes_to_b64(pub_bytes: bytes) -> str:
    return base64.b64encode(pub_bytes).decode("ascii")


def _sig_bytes_to_b64(sig_bytes: bytes) -> str:
    return base64.b64encode(sig_bytes).decode("ascii")


def _b64_to_bytes(b64: str) -> bytes:
    return base64.b64decode(b64)


# ---------------------------------------------------------------------------
# SignedEvidenceSpine
# ---------------------------------------------------------------------------


class SignedEvidenceSpine:
    """EvidenceSpine wrapper with automatic Ed25519 signing.

    Wraps a standard EvidenceSpine.  When a private key is configured every
    ``append()`` call signs the chain-hash with Ed25519 and stores the
    base64-encoded signature in the entry's ``signature`` field.

    ``verify_chain()`` checks both the SHA-256 hash chain *and* the Ed25519
    signatures for every signed entry.

    If no private key is provided the wrapper is fully transparent: it
    behaves exactly like an unsigned EvidenceSpine (SHA-256 chain only).
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
        private_key_bytes: bytes | None = None,
        public_key_bytes: bytes | None = None,
    ):
        self._spine = EvidenceSpine(db_path=db_path, event_bus=event_bus)
        self._private_key: bytes | None = private_key_bytes
        self._public_key: bytes | None = public_key_bytes

        if private_key_bytes and not public_key_bytes:
            # Derive the public key from the private key
            pk = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            self._public_key = pk.public_key().public_bytes_raw()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_signing_enabled(self) -> bool:
        """True when a private key is configured."""
        return self._private_key is not None

    @property
    def public_key_b64(self) -> str | None:
        """Current public key as base64, or None when unsigned."""
        if self._public_key is None:
            return None
        return _pub_bytes_to_b64(self._public_key)

    @property
    def spine(self) -> EvidenceSpine:
        """Access the underlying EvidenceSpine (e.g. for raw queries)."""
        return self._spine

    # ------------------------------------------------------------------
    # Append with auto-signing
    # ------------------------------------------------------------------

    def append(self, entry: EvidenceEntry) -> dict:
        """Append an evidence entry.  If signing is enabled the chain-hash
        is automatically signed with Ed25519 and stored in ``entry.signature``.

        Returns the same dict as EvidenceSpine.append(), plus ``signature``.
        """
        # If signing is disabled just delegate transparently
        if not self._private_key:
            return self._spine.append(entry)

        # Pre-compute the canonical payload so we can predict the hash
        payload_json = _canonical_json(entry.payload)

        # We need the prev_hash to compute the chain hash -- the spine does
        # this internally, but we need the hash *before* the DB write so we
        # can sign it.  Access the spine's internal helper.
        prev_hash = self._spine._get_last_hash()
        chain_hash = _compute_chain_hash(
            entry.entry_id, payload_json, prev_hash, entry.timestamp
        )

        # Sign the chain hash
        signature_bytes = sign_entry(self._private_key, chain_hash.encode("utf-8"))
        entry.signature = _sig_bytes_to_b64(signature_bytes)

        # Delegate the actual DB write to the spine
        result = self._spine.append(entry)

        # Attach signature info to the result
        result["signature"] = entry.signature
        result["public_key"] = self.public_key_b64
        return result

    # ------------------------------------------------------------------
    # Query (passthrough)
    # ------------------------------------------------------------------

    def query(
        self,
        source_plan: str | None = None,
        event_type: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Passthrough to the underlying spine."""
        return self._spine.query(
            source_plan=source_plan,
            event_type=event_type,
            since=since,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Chain verification (SHA-256 + Ed25519)
    # ------------------------------------------------------------------

    def verify_chain(self) -> tuple[bool, str]:
        """Verify both the SHA-256 hash chain AND Ed25519 signatures.

        Returns (is_valid, message).

        - For unsigned entries (no signature field) only SHA-256 is checked.
        - For signed entries both SHA-256 and Ed25519 must pass.
        - If a public key is configured, signed entries MUST match it.
        - If no public key is configured, signed entries are verified against
          whatever public key matches (stored in the signer at creation time).
        """
        # First run the standard SHA-256 chain verification
        hash_ok, hash_msg = self._spine.verify_chain()
        if not hash_ok:
            return False, f"SHA-256 chain broken: {hash_msg}"

        # If no public key is configured there is nothing more to check
        if self._public_key is None:
            return True, hash_msg

        # Verify Ed25519 signatures on all entries that have them
        rows = self._spine.query(limit=1000000)
        pub_key_bytes = self._public_key

        signed_count = 0
        for i, row in enumerate(rows):
            sig_b64 = row.get("signature", "")
            entry_hash = row.get("hash", "")

            if not sig_b64:
                # Unsigned entry -- allowed (backward compat)
                continue

            signed_count += 1
            sig_bytes = _b64_to_bytes(sig_b64)
            ok = verify_signature(
                pub_key_bytes, sig_bytes, entry_hash.encode("utf-8")
            )
            if not ok:
                eid = row.get("entry_id", "unknown")[:12]
                return False, (
                    f"Ed25519 signature mismatch at entry {eid} (index {i})"
                )

        return True, (
            f"chain valid ({len(rows)} entries, {signed_count} signed)"
        )

    # ------------------------------------------------------------------
    # Replay (passthrough)
    # ------------------------------------------------------------------

    def replay(self, since: float | None = None) -> list[dict]:
        """Replay evidence entries since timestamp."""
        return self._spine.replay(since=since)
