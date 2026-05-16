"""SYLION Security — Cloud Provider Connector store (W14 BE-8.4).

Persistence + masking layer for cloud-hosting connector credentials
(Hetzner, AWS, GCP, Azure, DigitalOcean, Vultr, OVH, Linode). Credentials
are encrypted at rest via :mod:`sylion.security.key_vault` so they never
land on disk in plaintext.

The accompanying FastAPI surface lives in
:mod:`sylion.api.cloud_connectors_routes` and exposes:

* ``POST   /api/v1/cloud-connectors``           — register
* ``GET    /api/v1/cloud-connectors``           — list (masked)
* ``DELETE /api/v1/cloud-connectors/{id}``      — remove
* ``POST   /api/v1/cloud-connectors/{id}/test`` — smoke ping

F-Hetzner-1 (P1) / F-Connectors-1 (P3): closes the gap where the
operator-facing wizard had no persistent home for hosting credentials
and had to keep them in memory between deploys.

W14 BE-7 audit-profile redirect: when ``SYLION_AUDIT_PROFILE_ID`` is
set, the underlying SQLite path moves into the audit-isolated subtree
so clean-room AEIS audits do not see operator credentials.
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

log = logging.getLogger("sylion.security.cloud_connectors")

#: Cloud-hosting providers explicitly blessed by the v3.5 design. The
#: list is intentionally short — mirrors the 8 providers documented in
#: ``docs/v2/_drafts/local_models_poc/`` and the W14 round_meta brief.
ALLOWED_PROVIDERS: frozenset[str] = frozenset({
    "hetzner",         # first-class (HCloud REST API smoke-pingable)
    "aws", "gcp", "azure",
    "digitalocean", "vultr", "ovh", "linode", "scaleway", "ionos",
    # Providers exposed by the onboarding wizard and hosting smoke-test API.
    "cloudflare", "vercel", "render", "flyio", "railway", "custom",
})


def _uid() -> str:
    return uuid.uuid4().hex[:16]


def _mask_credentials(creds: dict[str, Any]) -> dict[str, Any]:
    """Return a display-safe copy. Keys with secret-looking names are
    replaced with ``"***<last4>"`` so the operator can still tell two
    keys apart in the UI without leaking the full value.
    """
    masked: dict[str, Any] = {}
    secret_keys = {
        "token", "api_key", "apikey", "secret", "secret_key",
        "secret_access_key", "access_key", "access_key_id",
        "password", "client_secret", "service_account",
        "subscription_key", "personal_access_token", "pat",
    }
    for key, value in (creds or {}).items():
        lower = str(key).lower()
        if lower in secret_keys or "secret" in lower or "token" in lower:
            text = str(value or "")
            if len(text) <= 4:
                masked[key] = "***"
            else:
                masked[key] = "***" + text[-4:]
        else:
            masked[key] = value
    return masked


class CloudConnectorStore:
    """SQLite-backed cloud connector store with encrypted credentials.

    Uses a single ``connectors`` table (provider, name, scope,
    credentials_encrypted, timestamps + last test status). Credentials
    are encrypted via the shared :class:`KeyVault` encryptor so the
    same vault secret unlocks them.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
    ):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self._db_path, check_same_thread=False, timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS connectors (
                connector_id           TEXT PRIMARY KEY,
                provider               TEXT NOT NULL,
                name                   TEXT NOT NULL,
                scope                  TEXT NOT NULL DEFAULT '',
                credentials_encrypted  TEXT NOT NULL,
                created_at             REAL NOT NULL,
                updated_at             REAL NOT NULL,
                last_test_at           REAL,
                last_test_status       TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_connectors_provider
                ON connectors(provider);
            CREATE INDEX IF NOT EXISTS idx_connectors_scope
                ON connectors(scope);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(SylionEvent(
            event_id="",
            topic=topic,
            payload=payload,
            source_module="security.cloud_connectors",
        ))

    @staticmethod
    def _validate_provider(provider: str) -> str:
        normalized = (provider or "").strip().lower()
        if normalized not in ALLOWED_PROVIDERS:
            raise ValueError(
                f"unsupported provider '{provider}', allowed: "
                f"{sorted(ALLOWED_PROVIDERS)}"
            )
        return normalized

    @staticmethod
    def _encryptor():
        # Lazy import — avoids pulling cryptography at module load when
        # the store is never instantiated (e.g. test collection).
        from sylion.security.key_vault import _Encryptor  # type: ignore
        return _Encryptor()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        # Always mask credentials for callers — there is no public API
        # to fetch the plaintext credentials by design. Use
        # :meth:`get_decrypted_credentials` if the test endpoint or a
        # deploy step needs to actually authenticate.
        try:
            decrypted_json = self._encryptor().decrypt(
                d.pop("credentials_encrypted"),
            )
            credentials = json.loads(decrypted_json)
            d["credentials_masked"] = _mask_credentials(credentials)
        except Exception:                                  # noqa: BLE001
            d.pop("credentials_encrypted", None)
            d["credentials_masked"] = {}
        return d

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        provider: str,
        name: str,
        credentials: dict[str, Any],
        scope: str = "",
    ) -> dict[str, Any]:
        """Register a new connector. Returns the created record (masked)."""
        if not name or not str(name).strip():
            raise ValueError("name must be non-empty")
        if not isinstance(credentials, dict):
            raise ValueError("credentials must be a dict")
        provider = self._validate_provider(provider)
        connector_id = _uid()
        now = time.time()
        creds_json = json.dumps(credentials, sort_keys=True, default=str)
        enc = self._encryptor().encrypt(creds_json)

        with self._lock:
            self._conn.execute(
                """INSERT INTO connectors
                    (connector_id, provider, name, scope,
                     credentials_encrypted, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    connector_id, provider, str(name).strip(),
                    str(scope or "").strip(), enc, now, now,
                ),
            )
            self._conn.commit()

        self._emit("cloud_connectors.registered", {
            "connector_id": connector_id,
            "provider": provider,
            "scope": scope,
        })
        log.info("registered connector %s provider=%s", connector_id, provider)
        return {
            "connector_id": connector_id,
            "provider": provider,
            "name": str(name).strip(),
            "scope": str(scope or "").strip(),
            "credentials_masked": _mask_credentials(credentials),
            "created_at": now,
            "updated_at": now,
            "last_test_at": None,
            "last_test_status": None,
        }

    def upsert(
        self,
        provider: str,
        name: str,
        credentials: dict[str, Any],
        scope: str = "",
    ) -> dict[str, Any]:
        """Create or update a connector identified by provider/name/scope."""
        if not name or not str(name).strip():
            raise ValueError("name must be non-empty")
        if not isinstance(credentials, dict):
            raise ValueError("credentials must be a dict")
        provider = self._validate_provider(provider)
        normalized_name = str(name).strip()
        normalized_scope = str(scope or "").strip()
        now = time.time()
        creds_json = json.dumps(credentials, sort_keys=True, default=str)
        enc = self._encryptor().encrypt(creds_json)

        with self._lock:
            row = self._conn.execute(
                """SELECT connector_id FROM connectors
                   WHERE provider = ? AND name = ? AND scope = ?""",
                (provider, normalized_name, normalized_scope),
            ).fetchone()
            if row:
                connector_id = row["connector_id"]
                self._conn.execute(
                    """UPDATE connectors
                          SET credentials_encrypted = ?,
                              updated_at = ?,
                              last_test_at = NULL,
                              last_test_status = NULL
                        WHERE connector_id = ?""",
                    (enc, now, connector_id),
                )
                self._conn.commit()
                self._emit("cloud_connectors.updated", {
                    "connector_id": connector_id,
                    "provider": provider,
                    "scope": normalized_scope,
                })
                return {
                    "connector_id": connector_id,
                    "provider": provider,
                    "name": normalized_name,
                    "scope": normalized_scope,
                    "credentials_masked": _mask_credentials(credentials),
                    "created_at": None,
                    "updated_at": now,
                    "last_test_at": None,
                    "last_test_status": None,
                }

        return self.register(
            provider=provider,
            name=normalized_name,
            credentials=credentials,
            scope=normalized_scope,
        )

    def get(self, connector_id: str) -> dict[str, Any] | None:
        """Return a single connector (masked) or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM connectors WHERE connector_id = ?",
                (connector_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list(
        self,
        provider: str | None = None,
        scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """List connectors (masked), optionally filtered."""
        with self._lock:
            q = "SELECT * FROM connectors WHERE 1=1"
            params: list[Any] = []
            if provider:
                q += " AND provider = ?"
                params.append(str(provider).lower())
            if scope is not None:
                q += " AND scope = ?"
                params.append(str(scope))
            q += " ORDER BY created_at ASC"
            rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete(self, connector_id: str) -> bool:
        """Hard-delete a connector. Returns True if a row was removed."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM connectors WHERE connector_id = ?",
                (connector_id,),
            )
            self._conn.commit()
            removed = cur.rowcount > 0
        if removed:
            self._emit("cloud_connectors.deleted", {
                "connector_id": connector_id,
            })
        return removed

    def get_decrypted_credentials(
        self, connector_id: str,
    ) -> dict[str, Any] | None:
        """Return the *plaintext* credentials. Used by /test only."""
        with self._lock:
            row = self._conn.execute(
                "SELECT credentials_encrypted FROM connectors "
                "WHERE connector_id = ?",
                (connector_id,),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(self._encryptor().decrypt(
                row["credentials_encrypted"],
            ))
        except Exception:                                  # noqa: BLE001
            log.warning("decrypt failed for connector %s", connector_id)
            return {}

    def record_test_result(
        self,
        connector_id: str,
        status: str,
    ) -> bool:
        """Persist the latest /test outcome. Returns True on success."""
        if status not in {"ok", "error", "unknown"}:
            raise ValueError(
                "status must be one of 'ok','error','unknown'",
            )
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                """UPDATE connectors
                      SET last_test_at = ?, last_test_status = ?,
                          updated_at = ?
                    WHERE connector_id = ?""",
                (now, status, now, connector_id),
            )
            self._conn.commit()
            return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CloudConnectorStore | None = None
_singleton_lock = threading.Lock()


def _audit_redirect(db_path: str | Path | None) -> str | Path | None:
    """W14 BE-7 redirect — keep operator connector creds out of audit DB."""
    if db_path is None or str(db_path) == ":memory:":
        return db_path
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path
    if not is_audit_mode():
        return db_path
    return resolve_db_path(Path(db_path))


def get_cloud_connector_store(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> CloudConnectorStore:
    """Process-wide singleton. First call decides db_path/event_bus."""
    global _instance
    with _singleton_lock:
        if _instance is None:
            _instance = CloudConnectorStore(_audit_redirect(db_path), event_bus)
        return _instance


def reset_cloud_connector_store(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> CloudConnectorStore:
    """Tests / app startup: replace the singleton."""
    global _instance
    with _singleton_lock:
        _instance = CloudConnectorStore(_audit_redirect(db_path), event_bus)
        return _instance


__all__ = [
    "ALLOWED_PROVIDERS",
    "CloudConnectorStore",
    "get_cloud_connector_store",
    "reset_cloud_connector_store",
]
