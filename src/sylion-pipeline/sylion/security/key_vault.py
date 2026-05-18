"""
SYLION Security — Key Vault

Encrypted key storage, model hierarchy management, and council member
configuration.  All secrets are encrypted at rest using Fernet (AES-128-CBC
with HMAC-SHA256) when the ``cryptography`` package is available, otherwise
falls back to base64 encoding.

Tables:
  api_keys               -- encrypted API keys per provider
  model_hierarchies      -- named model hierarchies with level definitions
  council_member_configs -- council member model / role / prompt configs

Singleton: get_key_vault() / reset_key_vault()
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
import warnings
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

warnings.warn(
    "key_vault is deprecated; use key_store_unified",
    DeprecationWarning,
    stacklevel=2,
)

log = logging.getLogger("sylion.security.key_vault")

# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

_FERNET_AVAILABLE = False
try:
    from cryptography.fernet import Fernet as _Fernet
    from cryptography.hazmat.primitives import hashes as _hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as _PBKDF2HMAC
    _FERNET_AVAILABLE = True
except ImportError:
    pass

_DEFAULT_VAULT_SECRET = "sylion-vault-default-secret-key-change-me"


class _Encryptor:
    """Stateless encrypt/decrypt wrapper.  Picks Fernet when available,
    otherwise base64 (obfuscation only -- NOT secure)."""

    def __init__(self, secret: str | None = None):
        raw = secret or os.environ.get("SYLION_VAULT_SECRET") or _DEFAULT_VAULT_SECRET
        self._fernet: Any = None
        if _FERNET_AVAILABLE:
            # Derive a valid Fernet key from the secret via PBKDF2
            kdf = _PBKDF2HMAC(
                algorithm=_hashes.SHA256(),
                length=32,
                salt=b"sylion-key-vault-salt",
                iterations=480_000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(raw.encode("utf-8")))
            self._fernet = _Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        if self._fernet is not None:
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        # Fallback: base64 (obfuscation only)
        return base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        if self._fernet is not None:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        return base64.b64decode(token.encode("utf-8")).decode("utf-8")


# ---------------------------------------------------------------------------
# Key Vault
# ---------------------------------------------------------------------------

class KeyVault:
    """Encrypted key storage, model hierarchies, and council member configs.

    Parameters
    ----------
    db_path : str | Path | None
        SQLite database path.  Defaults to the AEIS runtime database unless
        ``":memory:"`` is passed explicitly.
    event_bus : EventBus | None
        Optional event bus for publishing vault events.
    vault_secret : str | None
        Secret used to derive the encryption key.  Falls back to the
        ``SYLION_VAULT_SECRET`` environment variable, then a default.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
        vault_secret: str | None = None,
    ):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._encryptor = _Encryptor(vault_secret)
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id        TEXT PRIMARY KEY,
                provider      TEXT NOT NULL,
                encrypted_key TEXT NOT NULL,
                display_name  TEXT,
                metadata      TEXT,
                is_active     INTEGER NOT NULL DEFAULT 0,
                created_at    REAL NOT NULL,
                updated_at    REAL
            );

            CREATE TABLE IF NOT EXISTS model_hierarchies (
                hierarchy_id  TEXT PRIMARY KEY,
                name          TEXT NOT NULL UNIQUE,
                levels        TEXT NOT NULL,
                is_active     INTEGER NOT NULL DEFAULT 0,
                created_at    REAL NOT NULL,
                updated_at    REAL
            );

            CREATE TABLE IF NOT EXISTS council_member_configs (
                member_id     TEXT PRIMARY KEY,
                model_id      TEXT NOT NULL,
                role          TEXT NOT NULL,
                priority      INTEGER NOT NULL DEFAULT 0,
                rank          TEXT NOT NULL DEFAULT 'primary',
                voting_weight REAL NOT NULL DEFAULT 1.0,
                specialization TEXT NOT NULL DEFAULT '',
                max_tokens    INTEGER NOT NULL DEFAULT 0,
                system_prompt TEXT,
                created_at    REAL NOT NULL,
                updated_at    REAL
            );

            CREATE INDEX IF NOT EXISTS idx_api_keys_provider
                ON api_keys(provider);
            CREATE INDEX IF NOT EXISTS idx_api_keys_active
                ON api_keys(provider, is_active);
        """)
        self._ensure_column("council_member_configs", "rank", "TEXT NOT NULL DEFAULT 'primary'")
        self._ensure_column("council_member_configs", "voting_weight", "REAL NOT NULL DEFAULT 1.0")
        self._ensure_column("council_member_configs", "specialization", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("council_member_configs", "max_tokens", "INTEGER NOT NULL DEFAULT 0")
        self._conn.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        existing = {
            row["name"]
            for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="security.key_vault",
            ))

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        for key in ("metadata", "levels", "system_prompt"):
            if d.get(key) is not None and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    @staticmethod
    def _mask_key(encrypted_key: str, decrypted: str) -> str:
        """Return a masked version for display, e.g. 'sk-...a1b2'."""
        if len(decrypted) <= 8:
            return "****"
        return decrypted[:3] + "..." + decrypted[-4:]

    # ------------------------------------------------------------------
    # API Key methods
    # ------------------------------------------------------------------

    def store_key(
        self,
        provider: str,
        encrypted_key: str,
        display_name: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Store an API key, encrypted at rest.

        Parameters
        ----------
        provider : str
            Provider identifier (e.g. ``"openai"``, ``"anthropic"``).
        encrypted_key : str
            The *plaintext* key to be encrypted before storage.
        display_name : str | None
            Optional human-readable name.
        metadata : dict | None
            Optional arbitrary metadata.

        Returns
        -------
        dict
            Created key record (without decrypted key).
        """
        provider = provider.lower()
        key_id = self._uid()
        now = time.time()

        enc = self._encryptor.encrypt(encrypted_key)
        metadata_json = (
            json.dumps(metadata, sort_keys=True, default=str)
            if metadata is not None else None
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO api_keys
                    (key_id, provider, encrypted_key, display_name, metadata,
                     is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                key_id, provider, enc, display_name, metadata_json,
                now, now,
            ))
            self._conn.commit()

        masked = self._mask_key(enc, encrypted_key)

        result = {
            "key_id": key_id,
            "provider": provider,
            "display_name": display_name,
            "masked_key": masked,
            "is_active": False,
            "created_at": now,
        }

        self._emit("vault.key.stored", {
            "key_id": key_id,
            "provider": provider,
        })
        log.info("stored key %s for provider %s", key_id, provider)
        return result

    def get_decrypted_key(self, key_id: str) -> str | None:
        """Decrypt and return the plaintext key."""
        with self._lock:
            row = self._conn.execute(
                "SELECT encrypted_key FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()
        if not row:
            return None
        return self._encryptor.decrypt(row["encrypted_key"])

    def get_key_info(self, key_id: str) -> dict | None:
        """Return key metadata without decrypting the key."""
        with self._lock:
            row = self._conn.execute(
                "SELECT key_id, provider, display_name, metadata, "
                "       is_active, created_at, updated_at "
                "FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()
        if not row:
            return None
        d = self._parse_row(row)
        return d

    def list_keys(self, provider: str | None = None) -> list[dict]:
        """Return masked keys for display, optionally filtered by provider."""
        with self._lock:
            if provider:
                rows = self._conn.execute(
                    "SELECT key_id, provider, encrypted_key, display_name, "
                    "       metadata, is_active, created_at, updated_at "
                    "FROM api_keys WHERE provider = ? ORDER BY created_at ASC",
                    (provider.lower(),),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT key_id, provider, encrypted_key, display_name, "
                    "       metadata, is_active, created_at, updated_at "
                    "FROM api_keys ORDER BY created_at ASC",
                ).fetchall()

        results: list[dict] = []
        for row in rows:
            d = self._parse_row(row)
            # Mask key
            try:
                decrypted = self._encryptor.decrypt(row["encrypted_key"])
                d["masked_key"] = self._mask_key(row["encrypted_key"], decrypted)
            except Exception:
                d["masked_key"] = "***error***"
            del d["encrypted_key"]
            results.append(d)
        return results

    def validate_key(self, key_id: str) -> dict:
        """Validate a key.  Currently checks format only (prefix-based).

        Returns
        -------
        dict
            ``{"key_id": ..., "provider": ..., "valid": bool, "reason": str}``
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT provider, encrypted_key FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()
        if not row:
            return {"key_id": key_id, "valid": False, "reason": "not_found"}

        decrypted = self._encryptor.decrypt(row["encrypted_key"])

        # Provider-specific format checks
        provider = row["provider"]
        valid = True
        reason = "ok"

        if provider == "openai":
            if not decrypted.startswith("sk-"):
                valid = False
                reason = "openai key must start with 'sk-'"
        elif provider == "anthropic":
            if not decrypted.startswith("sk-ant-"):
                valid = False
                reason = "anthropic key must start with 'sk-ant-'"
        elif provider in ("google", "mistral", "cohere", "deepseek",
                          "groq", "together", "fireworks"):
            if len(decrypted) < 8:
                valid = False
                reason = f"{provider} key too short (min 8 chars)"

        self._emit("vault.key.validated", {
            "key_id": key_id,
            "provider": provider,
            "valid": valid,
        })
        return {
            "key_id": key_id,
            "provider": provider,
            "valid": valid,
            "reason": reason,
        }

    def activate_key(self, key_id: str) -> dict:
        """Set a key as the active key for its provider (deactivates others)."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT provider FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()
            if not row:
                return {"key_id": key_id, "activated": False, "reason": "not_found"}
            provider = row["provider"]
            # Deactivate all keys for this provider
            self._conn.execute(
                "UPDATE api_keys SET is_active = 0, updated_at = ? "
                "WHERE provider = ?",
                (now, provider),
            )
            # Activate the chosen key
            self._conn.execute(
                "UPDATE api_keys SET is_active = 1, updated_at = ? "
                "WHERE key_id = ?",
                (now, key_id),
            )
            self._conn.commit()

        return {
            "key_id": key_id,
            "provider": provider,
            "activated": True,
        }

    def deactivate_key(self, key_id: str) -> dict:
        """Deactivate a key."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT provider FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()
            if not row:
                return {"key_id": key_id, "deactivated": False, "reason": "not_found"}
            self._conn.execute(
                "UPDATE api_keys SET is_active = 0, updated_at = ? "
                "WHERE key_id = ?",
                (now, key_id),
            )
            self._conn.commit()

        return {
            "key_id": key_id,
            "provider": row["provider"],
            "deactivated": True,
        }

    def delete_key(self, key_id: str) -> bool:
        """Delete a key.  Returns True if deleted, False if not found."""
        with self._lock:
            count = self._conn.execute(
                "DELETE FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).rowcount
            self._conn.commit()
        return count > 0

    # ------------------------------------------------------------------
    # Model Hierarchy methods
    # ------------------------------------------------------------------

    def save_hierarchy(self, name: str, levels: list[dict]) -> dict:
        """Save a model hierarchy.

        Parameters
        ----------
        name : str
            Unique name for the hierarchy.
        levels : list[dict]
            Each dict has keys: ``level`` (int), ``model_id`` (str),
            ``task_types`` (list[str]).

        Returns
        -------
        dict
            Created hierarchy record.
        """
        hierarchy_id = self._uid()
        now = time.time()
        levels_json = json.dumps(levels, sort_keys=True, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO model_hierarchies
                    (hierarchy_id, name, levels, is_active, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
            """, (
                hierarchy_id, name, levels_json, now, now,
            ))
            self._conn.commit()

        result = {
            "hierarchy_id": hierarchy_id,
            "name": name,
            "levels": levels,
            "is_active": False,
            "created_at": now,
        }

        self._emit("vault.hierarchy.saved", {
            "hierarchy_id": hierarchy_id,
            "name": name,
        })
        log.info("saved hierarchy %s (%s)", hierarchy_id, name)
        return result

    def update_hierarchy(
        self,
        hierarchy_id: str,
        *,
        name: str | None = None,
        levels: list[dict] | None = None,
        is_active: bool | None = None,
    ) -> dict | None:
        """Update a stored hierarchy by ID and optionally activate it."""
        now = time.time()
        updates: list[str] = []
        values: list[Any] = []
        if name is not None:
            updates.append("name = ?")
            values.append(name)
        if levels is not None:
            updates.append("levels = ?")
            values.append(json.dumps(levels, sort_keys=True, default=str))
        if is_active is not None:
            updates.append("is_active = ?")
            values.append(1 if is_active else 0)
        updates.append("updated_at = ?")
        values.append(now)

        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM model_hierarchies WHERE hierarchy_id = ?",
                (hierarchy_id,),
            ).fetchone()
            if not existing:
                return None
            if is_active:
                self._conn.execute(
                    "UPDATE model_hierarchies SET is_active = 0, updated_at = ?",
                    (now,),
                )
            values.append(hierarchy_id)
            self._conn.execute(
                f"UPDATE model_hierarchies SET {', '.join(updates)} WHERE hierarchy_id = ?",
                tuple(values),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM model_hierarchies WHERE hierarchy_id = ?",
                (hierarchy_id,),
            ).fetchone()

        result = self._parse_row(row)
        self._emit("vault.hierarchy.updated", {
            "hierarchy_id": hierarchy_id,
            "name": result.get("name"),
            "is_active": bool(result.get("is_active")),
        })
        return result

    def upsert_hierarchy(
        self,
        name: str,
        levels: list[dict],
        *,
        is_active: bool = False,
    ) -> dict:
        """Create or replace a hierarchy by unique name."""
        with self._lock:
            row = self._conn.execute(
                "SELECT hierarchy_id FROM model_hierarchies WHERE name = ?",
                (name,),
            ).fetchone()
        if row:
            updated = self.update_hierarchy(
                row["hierarchy_id"],
                name=name,
                levels=levels,
                is_active=is_active,
            )
            if updated is None:
                raise RuntimeError("hierarchy disappeared during upsert")
            return updated

        created = self.save_hierarchy(name, levels)
        if is_active:
            self.set_active_hierarchy(created["hierarchy_id"])
            refreshed = self.get_hierarchy(created["hierarchy_id"])
            return refreshed or created
        return created

    def get_hierarchy(self, hierarchy_id: str) -> dict | None:
        """Return a single hierarchy by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM model_hierarchies WHERE hierarchy_id = ?",
                (hierarchy_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def list_hierarchies(self) -> list[dict]:
        """Return all hierarchies."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM model_hierarchies ORDER BY created_at ASC"
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    def set_active_hierarchy(self, hierarchy_id: str) -> dict:
        """Set a hierarchy as the active one (deactivates all others)."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT name FROM model_hierarchies WHERE hierarchy_id = ?",
                (hierarchy_id,),
            ).fetchone()
            if not row:
                return {
                    "hierarchy_id": hierarchy_id,
                    "activated": False,
                    "reason": "not_found",
                }
            # Deactivate all
            self._conn.execute(
                "UPDATE model_hierarchies SET is_active = 0, updated_at = ?",
                (now,),
            )
            # Activate chosen
            self._conn.execute(
                "UPDATE model_hierarchies SET is_active = 1, updated_at = ? "
                "WHERE hierarchy_id = ?",
                (now, hierarchy_id),
            )
            self._conn.commit()

        return {
            "hierarchy_id": hierarchy_id,
            "name": row["name"],
            "activated": True,
        }

    # ------------------------------------------------------------------
    # Council Member methods
    # ------------------------------------------------------------------

    def configure_council_member(
        self,
        member_id: str,
        model_id: str,
        role: str,
        priority: int,
        system_prompt: str | None = None,
        rank: str = "primary",
        voting_weight: float = 1.0,
        specialization: str = "",
        max_tokens: int = 0,
    ) -> dict:
        """Create or update a council member configuration.

        If a config for ``member_id`` already exists it is replaced (upsert).

        Parameters
        ----------
        member_id : str
            Unique member identifier.
        model_id : str
            Model to use (e.g. ``"gpt-4"``).
        role : str
            Role description (e.g. ``"analyst"``).
        priority : int
            Priority (higher = called first).
        system_prompt : str | None
            Optional system prompt override.

        Returns
        -------
        dict
            Member config record.
        """
        now = time.time()

        with self._lock:
            existing = self._conn.execute(
                "SELECT member_id FROM council_member_configs WHERE member_id = ?",
                (member_id,),
            ).fetchone()

            if existing:
                self._conn.execute("""
                    UPDATE council_member_configs
                    SET model_id = ?, role = ?, priority = ?,
                        rank = ?, voting_weight = ?, specialization = ?,
                        max_tokens = ?, system_prompt = ?, updated_at = ?
                    WHERE member_id = ?
                """, (
                    model_id, role, priority, rank, voting_weight,
                    specialization, max_tokens, system_prompt, now, member_id,
                ))
            else:
                self._conn.execute("""
                    INSERT INTO council_member_configs
                        (member_id, model_id, role, priority,
                         rank, voting_weight, specialization, max_tokens,
                         system_prompt, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (member_id, model_id, role, priority,
                      rank, voting_weight, specialization, max_tokens,
                      system_prompt, now, now))
            self._conn.commit()

        result = {
            "member_id": member_id,
            "model_id": model_id,
            "role": role,
            "priority": priority,
            "rank": rank,
            "voting_weight": voting_weight,
            "specialization": specialization,
            "max_tokens": max_tokens,
            "system_prompt": system_prompt,
            "updated_at": now,
        }

        self._emit("vault.council_member.configured", {
            "member_id": member_id,
            "model_id": model_id,
            "role": role,
        })
        log.info("configured council member %s (model=%s, role=%s)",
                 member_id, model_id, role)
        return result

    def get_council_member(self, member_id: str) -> dict | None:
        """Return a single council member config."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM council_member_configs WHERE member_id = ?",
                (member_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def list_council_members(self) -> list[dict]:
        """Return all council member configs ordered by priority desc."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM council_member_configs "
                "ORDER BY priority DESC, created_at ASC"
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    def remove_council_member(self, member_id: str) -> bool:
        """Remove a council member config.  Returns True if removed."""
        with self._lock:
            count = self._conn.execute(
                "DELETE FROM council_member_configs WHERE member_id = ?",
                (member_id,),
            ).rowcount
            self._conn.commit()
        return count > 0


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_vault: KeyVault | None = None


def _default_vault_db_path() -> Path:
    env_path = os.environ.get("SYLION_KEY_VAULT_DB")
    if env_path:
        return Path(env_path)
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "data" / "sylion_key_vault.db"


def _audit_redirect(db_path: str | Path | None) -> str | Path | None:
    """W14 BE-7: redirect onto audit-isolated DB when SYLION_AUDIT_PROFILE_ID set.

    Keeps secrets vault out of operator data during clean-room AEIS audits
    (sekcja 4.2.1 "Gate czystej dystrybucji").
    """
    if db_path is None or str(db_path) == ":memory:":
        return db_path
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path
    if not is_audit_mode():
        return db_path
    return resolve_db_path(Path(db_path))


def get_key_vault(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
    vault_secret: str | None = None,
) -> KeyVault:
    global _vault
    if _vault is None:
        target_path = _default_vault_db_path() if db_path is None else db_path
        _vault = KeyVault(_audit_redirect(target_path), event_bus, vault_secret)
    return _vault


def reset_key_vault(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
    vault_secret: str | None = None,
) -> KeyVault:
    global _vault
    target_path = _default_vault_db_path() if db_path is None else db_path
    _vault = KeyVault(_audit_redirect(target_path), event_bus, vault_secret)
    return _vault
