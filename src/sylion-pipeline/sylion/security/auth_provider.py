"""
SYLION Security -- Auth Provider

Manages authentication providers and token lifecycle.
SQLite-backed storage with thread-safe access.

Tables:
  auth_providers -- registered authentication providers
  auth_sessions  -- authenticated user sessions
  auth_tokens    -- token lifecycle records

Thread-safe via threading.RLock(). Singleton via get_auth_provider() /
reset_auth_provider().  Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.security.auth_provider")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PROVIDER_TYPES: tuple[str, ...] = ("local", "ldap", "oauth2", "saml", "api_key")
TOKEN_TTL_SECONDS: int = 3600  # 1 hour


# ---------------------------------------------------------------------------
# AuthProvider
# ---------------------------------------------------------------------------


class AuthProvider:
    """Authentication providers, sessions, and token lifecycle.

    SQLite-backed with RLock for thread safety.  Providers handle
    authentication logic; tokens track session validity with TTL.
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
            CREATE TABLE IF NOT EXISTS auth_providers (
                provider_id   TEXT PRIMARY KEY,
                name          TEXT UNIQUE NOT NULL,
                provider_type TEXT NOT NULL DEFAULT 'local',
                config_json   TEXT NOT NULL DEFAULT '{}',
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    REAL NOT NULL DEFAULT 0.0,
                updated_at    REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_users (
                user_id        TEXT PRIMARY KEY,
                username       TEXT UNIQUE NOT NULL,
                password_hash  TEXT NOT NULL DEFAULT '',
                role           TEXT NOT NULL DEFAULT 'user',
                metadata_json  TEXT NOT NULL DEFAULT '{}',
                is_active      INTEGER NOT NULL DEFAULT 1,
                created_at     REAL NOT NULL DEFAULT 0.0,
                last_login_at  REAL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_au_username ON auth_users(username)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_au_role ON auth_users(role)"
        )
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_id  TEXT PRIMARY KEY,
                provider_id TEXT NOT NULL DEFAULT '',
                user_id     TEXT NOT NULL DEFAULT '',
                ip_address  TEXT NOT NULL DEFAULT '',
                metadata    TEXT NOT NULL DEFAULT '{}',
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token_id    TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL DEFAULT '',
                provider_id TEXT NOT NULL DEFAULT '',
                user_id     TEXT NOT NULL DEFAULT '',
                token       TEXT NOT NULL DEFAULT '',
                expires_at  REAL NOT NULL DEFAULT 0.0,
                is_revoked  INTEGER NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ap_providers_type ON auth_providers(provider_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ap_providers_active ON auth_providers(is_active)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ap_sessions_provider ON auth_sessions(provider_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ap_sessions_user ON auth_sessions(user_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ap_sessions_active ON auth_sessions(is_active)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ap_tokens_session ON auth_tokens(session_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ap_tokens_token ON auth_tokens(token)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ap_tokens_user ON auth_tokens(user_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ap_tokens_expires ON auth_tokens(expires_at)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    def _parse_json(self, raw: str) -> Any:
        try:
            return json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.auth_provider",
            ))

    # ------------------------------------------------------------------
    # Provider management
    # ------------------------------------------------------------------

    def register_provider(self, name: str, provider_type: str = "local",
                          config_json: Any = None) -> dict:
        """Register a new auth provider. Returns provider dict.

        Raises ValueError if provider_type is invalid.
        """
        if provider_type not in VALID_PROVIDER_TYPES:
            raise ValueError(
                f"Invalid provider_type '{provider_type}'. "
                f"Must be one of {VALID_PROVIDER_TYPES}"
            )

        provider_id = uuid.uuid4().hex
        now = time.time()
        config_str = json.dumps(config_json or {}, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO auth_providers
                    (provider_id, name, provider_type, config_json,
                     is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (provider_id, name, provider_type, config_str, now, now))
            self._conn.commit()

        self._emit("provider_registered", {
            "provider_id": provider_id,
            "name": name,
            "provider_type": provider_type,
        })
        log.info("registered auth provider %s (type=%s)", name, provider_type)
        return {
            "provider_id": provider_id,
            "name": name,
            "provider_type": provider_type,
            "config_json": config_json or {},
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        }

    def update_provider(self, provider_id: str, name: str | None = None,
                        provider_type: str | None = None,
                        config_json: Any = None,
                        is_active: int | None = None) -> dict | None:
        """Update provider fields. Returns updated provider dict or None."""
        if provider_type is not None and provider_type not in VALID_PROVIDER_TYPES:
            raise ValueError(
                f"Invalid provider_type '{provider_type}'. "
                f"Must be one of {VALID_PROVIDER_TYPES}"
            )

        sets: list[str] = []
        params: list[Any] = []

        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if provider_type is not None:
            sets.append("provider_type = ?")
            params.append(provider_type)
        if config_json is not None:
            sets.append("config_json = ?")
            params.append(json.dumps(config_json, default=str))
        if is_active is not None:
            sets.append("is_active = ?")
            params.append(is_active)

        if not sets:
            return self._get_provider_raw(provider_id)

        sets.append("updated_at = ?")
        params.append(time.time())
        params.append(provider_id)

        with self._lock:
            n = self._conn.execute(
                f"UPDATE auth_providers SET {', '.join(sets)} WHERE provider_id = ?",
                params,
            ).rowcount
            self._conn.commit()

        if not n:
            return None

        log.info("updated auth provider %s", provider_id[:12])
        return self._get_provider_raw(provider_id)

    def _get_provider_raw(self, provider_id: str) -> dict | None:
        """Internal: get provider without acquiring lock."""
        row = self._conn.execute(
            "SELECT * FROM auth_providers WHERE provider_id = ?",
            (provider_id,),
        ).fetchone()
        if not row:
            return None
        d = self._row_to_dict(row)
        d["config_json"] = self._parse_json(d.get("config_json", "{}"))
        return d

    def deregister_provider(self, provider_id: str) -> bool:
        """Soft-delete a provider (set is_active=0). Returns True if deleted."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE auth_providers SET is_active = 0, updated_at = ? "
                "WHERE provider_id = ? AND is_active = 1",
                (time.time(), provider_id),
            ).rowcount
            self._conn.commit()

        if n:
            log.info("deregistered auth provider %s", provider_id[:12])
        return bool(n)

    def list_providers(self, provider_type: str | None = None) -> list[dict]:
        """List providers, optionally filtered by provider_type."""
        conditions: list[str] = []
        params: list[Any] = []

        if provider_type is not None:
            conditions.append("provider_type = ?")
            params.append(provider_type)

        where = "WHERE is_active = 1"
        if conditions:
            where += " AND " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM auth_providers {where} ORDER BY created_at",
                params,
            ).fetchall()
        results = []
        for r in rows:
            d = self._row_to_dict(r)
            d["config_json"] = self._parse_json(d.get("config_json", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # User management (local-style)
    # ------------------------------------------------------------------

    def create_user(self, user_id: str, username: str, password_hash: str,
                    role: str = "user", metadata: dict | None = None) -> dict:
        """Register a local user record.

        ``user_id`` is the canonical id; ``username`` must be unique.
        Returns the created user dict (without password_hash).
        Raises ValueError on duplicate user_id or username.
        """
        now = time.time()
        meta_str = json.dumps(metadata or {}, default=str)
        with self._lock:
            try:
                self._conn.execute("""
                    INSERT INTO auth_users
                        (user_id, username, password_hash, role,
                         metadata_json, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (user_id, username, password_hash, role, meta_str, now))
                self._conn.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"user already exists: id={user_id} or username={username}"
                ) from exc

        self._emit("user_created", {
            "user_id": user_id, "username": username, "role": role,
        })
        log.info("created auth user %s (username=%s, role=%s)",
                 user_id, username, role)
        return {
            "user_id": user_id,
            "username": username,
            "role": role,
            "metadata": metadata or {},
            "is_active": 1,
            "created_at": now,
        }

    def get_user(self, user_id: str) -> dict | None:
        """Return the user record by user_id, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT user_id, username, role, metadata_json, "
                "       is_active, created_at, last_login_at "
                "FROM auth_users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["metadata"] = self._parse_json(d.pop("metadata_json", "{}"))
        return d

    def list_users(self, role: str | None = None,
                   active_only: bool = True) -> list[dict]:
        """List users, optionally filtered by role / active status."""
        sql = ("SELECT user_id, username, role, metadata_json, "
               "       is_active, created_at, last_login_at "
               "FROM auth_users WHERE 1=1")
        args: list[Any] = []
        if active_only:
            sql += " AND is_active = 1"
        if role is not None:
            sql += " AND role = ?"
            args.append(role)
        sql += " ORDER BY created_at"
        with self._lock:
            rows = self._conn.execute(sql, tuple(args)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["metadata"] = self._parse_json(d.pop("metadata_json", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, provider_id_or_username: str,
                     credentials_or_password: Any = None) -> dict | None:
        """Authenticate.

        Polymorphic dispatch by 2nd-arg type:
        - If ``credentials_or_password`` is a ``str`` -> treat as a local
          username + password_hash login. Returns the user dict (or None).
        - Otherwise -> treat 1st arg as provider_id, 2nd as credentials_json
          (dict/None). Returns the session+token dict.

        Raises ValueError when in provider-mode and the provider is missing.
        """
        # Local-user dispatch -------------------------------------------------
        if isinstance(credentials_or_password, str):
            username = provider_id_or_username
            password_hash = credentials_or_password
            with self._lock:
                row = self._conn.execute(
                    "SELECT user_id, username, role, password_hash, is_active "
                    "FROM auth_users WHERE username = ?",
                    (username,),
                ).fetchone()
                if not row or not row["is_active"]:
                    return None
                if row["password_hash"] != password_hash:
                    return None
                self._conn.execute(
                    "UPDATE auth_users SET last_login_at = ? WHERE user_id = ?",
                    (time.time(), row["user_id"]),
                )
                self._conn.commit()
            user = {
                "user_id": row["user_id"],
                "username": row["username"],
                "role": row["role"],
            }
            self._emit("user_authenticated", user)
            return user

        # Provider dispatch ---------------------------------------------------
        provider_id = provider_id_or_username
        credentials_json = credentials_or_password
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM auth_providers WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Provider '{provider_id}' does not exist")
            provider = self._row_to_dict(row)
            if not provider["is_active"]:
                raise ValueError(f"Provider '{provider_id}' is inactive")

        creds = credentials_json or {}
        user_id = creds.get("user_id", creds.get("username", "anonymous"))
        ip_address = creds.get("ip_address", "")

        session_id = uuid.uuid4().hex
        token_id = uuid.uuid4().hex
        token_value = uuid.uuid4().hex
        now = time.time()
        expires_at = now + TOKEN_TTL_SECONDS

        meta_str = json.dumps({"credentials_provided": bool(creds)}, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO auth_sessions
                    (session_id, provider_id, user_id, ip_address,
                     metadata, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (session_id, provider_id, user_id, ip_address,
                  meta_str, now))

            self._conn.execute("""
                INSERT INTO auth_tokens
                    (token_id, session_id, provider_id, user_id,
                     token, expires_at, is_revoked, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """, (token_id, session_id, provider_id, user_id,
                  token_value, expires_at, now))
            self._conn.commit()

        self._emit("user_authenticated", {
            "session_id": session_id,
            "provider_id": provider_id,
            "user_id": user_id,
        })
        log.info("authenticated user %s via %s", user_id, provider["name"])
        return {
            "session_id": session_id,
            "token_id": token_id,
            "token": token_value,
            "provider_id": provider_id,
            "user_id": user_id,
            "expires_at": expires_at,
        }

    def validate_token(self, token_id: str) -> dict | None:
        """Validate a token. Returns token dict with session info or None.

        Checks that the token exists, is not revoked, and has not expired.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM auth_tokens WHERE token_id = ?",
                (token_id,),
            ).fetchone()
            if not row:
                return None

            token = self._row_to_dict(row)

            if token["is_revoked"]:
                return None

            now = time.time()
            if token["expires_at"] > 0 and token["expires_at"] < now:
                return None

            session = self._conn.execute(
                "SELECT * FROM auth_sessions WHERE session_id = ?",
                (token["session_id"],),
            ).fetchone()
            if not session or not session["is_active"]:
                return None

        return {
            "token": token,
            "session": self._row_to_dict(session),
        }

    def revoke_token(self, token_id: str) -> bool:
        """Revoke a token. Returns True if revoked."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE auth_tokens SET is_revoked = 1 WHERE token_id = ? AND is_revoked = 0",
                (token_id,),
            ).rowcount
            self._conn.commit()

        if n:
            self._emit("token_revoked", {"token_id": token_id})
            log.info("revoked token %s", token_id[:12])
        return bool(n)

    def refresh_token(self, token_id: str) -> dict | None:
        """Refresh a token (extend expiry). Returns updated token dict or None.

        Raises ValueError if token is revoked or expired.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM auth_tokens WHERE token_id = ?",
                (token_id,),
            ).fetchone()
            if not row:
                return None
            token = self._row_to_dict(row)

        if token["is_revoked"]:
            raise ValueError(f"Token '{token_id}' is revoked")
        now = time.time()
        if token["expires_at"] > 0 and token["expires_at"] < now:
            raise ValueError(f"Token '{token_id}' has expired")

        new_expires = now + TOKEN_TTL_SECONDS
        with self._lock:
            n = self._conn.execute(
                "UPDATE auth_tokens SET expires_at = ? WHERE token_id = ?",
                (new_expires, token_id),
            ).rowcount
            self._conn.commit()

        if not n:
            return None

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM auth_tokens WHERE token_id = ?",
                (token_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> dict | None:
        """Retrieve a session by session_id. Returns dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM auth_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        d = self._row_to_dict(row)
        d["metadata"] = self._parse_json(d.get("metadata", "{}"))
        return d

    def list_sessions(self, user_id: str | None = None) -> list[dict]:
        """List sessions, optionally filtered by user_id."""
        conditions: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)

        where = "WHERE is_active = 1"
        if conditions:
            where += " AND " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM auth_sessions {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        results = []
        for r in rows:
            d = self._row_to_dict(r)
            d["metadata"] = self._parse_json(d.get("metadata", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_auth_stats(self) -> dict:
        """Return aggregate statistics about providers, sessions, and tokens."""
        with self._lock:
            total_providers = self._conn.execute(
                "SELECT COUNT(*) FROM auth_providers"
            ).fetchone()[0]
            active_providers = self._conn.execute(
                "SELECT COUNT(*) FROM auth_providers WHERE is_active = 1"
            ).fetchone()[0]

            type_rows = self._conn.execute(
                "SELECT provider_type, COUNT(*) as cnt FROM auth_providers "
                "WHERE is_active = 1 GROUP BY provider_type"
            ).fetchall()
            providers_by_type = {r["provider_type"]: r["cnt"] for r in type_rows}

            total_sessions = self._conn.execute(
                "SELECT COUNT(*) FROM auth_sessions"
            ).fetchone()[0]
            active_sessions = self._conn.execute(
                "SELECT COUNT(*) FROM auth_sessions WHERE is_active = 1"
            ).fetchone()[0]

            total_tokens = self._conn.execute(
                "SELECT COUNT(*) FROM auth_tokens"
            ).fetchone()[0]
            revoked_tokens = self._conn.execute(
                "SELECT COUNT(*) FROM auth_tokens WHERE is_revoked = 1"
            ).fetchone()[0]

        return {
            "total_providers": total_providers,
            "active_providers": active_providers,
            "providers_by_type": providers_by_type,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_tokens": total_tokens,
            "revoked_tokens": revoked_tokens,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: AuthProvider | None = None


def get_auth_provider(db_path: str | Path | None = None,
                      event_bus: EventBus | None = None) -> AuthProvider:
    """Get or create the global AuthProvider singleton."""
    global _manager
    if _manager is None:
        _manager = AuthProvider(db_path, event_bus)
    return _manager


def reset_auth_provider(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> AuthProvider:
    """Reset the global AuthProvider singleton (for testing)."""
    global _manager
    _manager = AuthProvider(db_path, event_bus)
    return _manager
