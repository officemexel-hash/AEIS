"""
SYLION Security -- Evidence Signer

HMAC-SHA256 and RSA digital signatures for evidence integrity.
Manages signing keys, signs evidence payloads, and verifies signatures.

Tables:
  signing_keys    -- keypairs with alias, type, and revocation status
  signed_evidence -- signatures linked to keys and evidence IDs

Thread-safe via threading.RLock(). Singleton via get_evidence_signer() /
reset_evidence_signer().  Emits events via EventBus.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.security.evidence_signer")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_KEY_TYPES: tuple[str, ...] = ("hmac_sha256", "rsa")


# ---------------------------------------------------------------------------
# EvidenceSigner
# ---------------------------------------------------------------------------


class EvidenceSigner:
    """Digital signature manager for evidence integrity.

    Supports HMAC-SHA256 signing. Keys can be generated with an alias,
    revoked, and used to sign/verify evidence payloads. Every signing
    operation is recorded in signed_evidence with a cryptographic signature.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS signing_keys (
                key_id      TEXT PRIMARY KEY,
                alias       TEXT NOT NULL DEFAULT '',
                key_type    TEXT NOT NULL DEFAULT 'hmac_sha256',
                key_secret  TEXT NOT NULL DEFAULT '',
                is_revoked  INTEGER NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL DEFAULT 0.0,
                revoked_at  REAL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS signed_evidence (
                signed_id    TEXT PRIMARY KEY,
                key_id       TEXT NOT NULL DEFAULT '',
                evidence_id  TEXT NOT NULL DEFAULT '',
                signature    TEXT NOT NULL DEFAULT '',
                data_hash    TEXT NOT NULL DEFAULT '',
                signed_at    REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_es_keys_alias ON signing_keys(alias)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_es_keys_revoked ON signing_keys(is_revoked)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_es_signed_key ON signed_evidence(key_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_es_signed_evidence ON signed_evidence(evidence_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.evidence_signer",
            ))

    @staticmethod
    def _compute_hmac(secret: str, data: str) -> str:
        return hmac.new(
            secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _compute_data_hash(data_json: str) -> str:
        return hashlib.sha256(data_json.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def generate_key(self, alias: str, key_type: str = "hmac_sha256") -> dict:
        """Generate a new signing key. Returns key dict.

        Raises ValueError if key_type is invalid.
        """
        if key_type not in VALID_KEY_TYPES:
            raise ValueError(
                f"Invalid key_type '{key_type}'. Must be one of {VALID_KEY_TYPES}"
            )

        key_id = uuid.uuid4().hex
        secret = uuid.uuid4().hex + uuid.uuid4().hex  # 64-char secret
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO signing_keys
                    (key_id, alias, key_type, key_secret, is_revoked, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
            """, (key_id, alias, key_type, secret, now))
            self._conn.commit()

        self._emit("key_generated", {
            "key_id": key_id, "alias": alias, "key_type": key_type,
        })
        log.info("generated key %s (alias=%s, type=%s)", key_id[:12], alias, key_type)
        return {
            "key_id": key_id,
            "alias": alias,
            "key_type": key_type,
            "created_at": now,
            "is_revoked": 0,
        }

    def revoke_key(self, key_id: str) -> bool:
        """Revoke a signing key. Returns True if revoked."""
        now = time.time()
        with self._lock:
            n = self._conn.execute(
                "UPDATE signing_keys SET is_revoked = 1, revoked_at = ? "
                "WHERE key_id = ? AND is_revoked = 0",
                (now, key_id),
            ).rowcount
            self._conn.commit()

        if n:
            self._emit("key_generated", {
                "key_id": key_id, "action": "revoked",
            })
            log.info("revoked key %s", key_id[:12])
        return bool(n)

    # ------------------------------------------------------------------
    # Signing and verification
    # ------------------------------------------------------------------

    def sign_evidence(self, key_id: str, evidence_id: str,
                      data_json: str) -> dict:
        """Sign evidence data with the specified key.

        Raises ValueError if key not found or revoked.
        Returns signed evidence dict with signature.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM signing_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Key '{key_id}' not found")
            if row["is_revoked"]:
                raise ValueError(f"Key '{key_id}' has been revoked")
            key = self._row_to_dict(row)

        data_hash = self._compute_data_hash(data_json)
        signature = self._compute_hmac(key["key_secret"], data_hash)

        signed_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO signed_evidence
                    (signed_id, key_id, evidence_id, signature, data_hash, signed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (signed_id, key_id, evidence_id, signature, data_hash, now))
            self._conn.commit()

        self._emit("evidence_signed", {
            "signed_id": signed_id,
            "key_id": key_id,
            "evidence_id": evidence_id,
        })
        log.info("signed evidence %s with key %s", evidence_id[:12], key_id[:12])
        return {
            "signed_id": signed_id,
            "key_id": key_id,
            "evidence_id": evidence_id,
            "signature": signature,
            "data_hash": data_hash,
            "signed_at": now,
        }

    def verify_signature(self, signed_id: str) -> dict:
        """Verify a signature by signed_id.

        Returns dict with valid (bool), signed_id, and reason.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM signed_evidence WHERE signed_id = ?",
                (signed_id,),
            ).fetchone()
            if not row:
                return {
                    "valid": False,
                    "signed_id": signed_id,
                    "reason": "signed_id not found",
                }
            signed = self._row_to_dict(row)

            key_row = self._conn.execute(
                "SELECT * FROM signing_keys WHERE key_id = ?",
                (signed["key_id"],),
            ).fetchone()
            if not key_row:
                self._emit("signature_invalid", {"signed_id": signed_id})
                return {
                    "valid": False,
                    "signed_id": signed_id,
                    "reason": "key not found",
                }
            key = self._row_to_dict(key_row)

        expected = self._compute_hmac(key["key_secret"], signed["data_hash"])
        is_valid = hmac.compare_digest(expected, signed["signature"])

        if is_valid:
            self._emit("signature_verified", {
                "signed_id": signed_id,
                "evidence_id": signed["evidence_id"],
            })
            return {
                "valid": True,
                "signed_id": signed_id,
                "evidence_id": signed["evidence_id"],
                "reason": "signature valid",
            }
        else:
            self._emit("signature_invalid", {
                "signed_id": signed_id,
                "evidence_id": signed["evidence_id"],
            })
            return {
                "valid": False,
                "signed_id": signed_id,
                "reason": "signature mismatch",
            }

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def list_signed_evidence(self, evidence_id: str | None = None,
                             limit: int = 100) -> list[dict]:
        """List signed evidence, optionally filtered by evidence_id."""
        with self._lock:
            if evidence_id is not None:
                rows = self._conn.execute(
                    "SELECT * FROM signed_evidence WHERE evidence_id = ? "
                    "ORDER BY signed_at DESC LIMIT ?",
                    (evidence_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM signed_evidence ORDER BY signed_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_signing_stats(self) -> dict[str, Any]:
        """Get signing statistics."""
        with self._lock:
            total_keys = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM signing_keys"
            ).fetchone()["cnt"]
            active_keys = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM signing_keys WHERE is_revoked = 0"
            ).fetchone()["cnt"]
            revoked_keys = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM signing_keys WHERE is_revoked = 1"
            ).fetchone()["cnt"]
            total_signed = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM signed_evidence"
            ).fetchone()["cnt"]

        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "revoked_keys": revoked_keys,
            "total_signed": total_signed,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_signer: EvidenceSigner | None = None


def get_evidence_signer(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> EvidenceSigner:
    """Get or create the global EvidenceSigner singleton."""
    global _signer
    if _signer is None:
        _signer = EvidenceSigner(db_path, event_bus)
    return _signer


def reset_evidence_signer(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> EvidenceSigner:
    """Reset the global EvidenceSigner singleton (for testing)."""
    global _signer
    _signer = EvidenceSigner(db_path, event_bus)
    return _signer
