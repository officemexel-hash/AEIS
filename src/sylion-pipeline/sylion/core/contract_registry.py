"""
SYLION Core -- Contract Registry

Manages interface agreements (contracts) between modules.  Each contract has
a name, version, JSON spec, and lifecycle status (active / deprecated).
Binding records track which consumer/provider pairs are coupled to a contract.

Tables:
  contracts         -- interface agreements with name, version, spec, status
  contract_versions -- historical versions for audit trail
  contract_bindings -- consumer<->provider links bound to a contract

Events:
  contract_registered  -- emitted when register_contract() is called
  contract_updated     -- emitted when update_contract() is called
  contract_deprecated  -- emitted when deprecate_contract() is called
  binding_created      -- emitted when bind_contract() is called

gRPC planned: RegisterContract, UpdateContract, DeprecateContract,
              BindContract, UnbindContract, ValidateBinding
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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.core.contract_registry")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = ("active", "deprecated")


class ContractRegistry:
    """Manages interface contracts between modules. SQLite-backed. Thread-safe."""

    def __init__(self, db_path: str | Path | None = None, event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
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
            CREATE TABLE IF NOT EXISTS contracts (
                contract_id  TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                version      TEXT NOT NULL,
                spec_json    TEXT NOT NULL DEFAULT '{}',
                status       TEXT NOT NULL DEFAULT 'active',
                created_at   REAL NOT NULL,
                updated_at   REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contracts_name
                ON contracts(name)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contracts_status
                ON contracts(status)
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS contract_versions (
                version_id   TEXT PRIMARY KEY,
                contract_id  TEXT NOT NULL,
                version      TEXT NOT NULL,
                spec_json    TEXT NOT NULL DEFAULT '{}',
                breaking_changes TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                FOREIGN KEY (contract_id) REFERENCES contracts(contract_id)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cv_contract
                ON contract_versions(contract_id)
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS contract_bindings (
                binding_id       TEXT PRIMARY KEY,
                contract_id      TEXT NOT NULL,
                consumer_module  TEXT NOT NULL,
                provider_module  TEXT NOT NULL,
                created_at       REAL NOT NULL,
                FOREIGN KEY (contract_id) REFERENCES contracts(contract_id)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cb_contract
                ON contract_bindings(contract_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cb_consumer
                ON contract_bindings(consumer_module)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cb_provider
                ON contract_bindings(provider_module)
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="core.contract_registry",
            ))

    # ------------------------------------------------------------------
    # Contract CRUD
    # ------------------------------------------------------------------

    def register_contract(
        self,
        name: str,
        version: str,
        spec_json: str | dict = "{}",
    ) -> dict:
        """Register a new contract. Returns the contract record as a dict."""
        if not name or not version:
            raise ValueError("name and version must be non-empty")

        if isinstance(spec_json, dict):
            spec_json = json.dumps(spec_json)

        contract_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO contracts
                    (contract_id, name, version, spec_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
            """, (contract_id, name, version, spec_json, now, now))
            self._conn.commit()

        log.info("registered contract %s v%s (%s)", name, version, contract_id)
        self._emit("contract_registered", {
            "contract_id": contract_id,
            "name": name,
            "version": version,
        })
        return {
            "contract_id": contract_id,
            "name": name,
            "version": version,
            "spec_json": spec_json,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

    def update_contract(
        self,
        contract_id: str,
        new_version: str,
        spec_json: str | dict = "{}",
        breaking_changes: str = "",
    ) -> dict | None:
        """Update a contract with a new version.  Stores the old version in
        contract_versions for audit.  Returns updated contract or None."""
        if not contract_id or not new_version:
            raise ValueError("contract_id and new_version must be non-empty")

        if isinstance(spec_json, dict):
            spec_json = json.dumps(spec_json)

        now = time.time()

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM contracts WHERE contract_id = ?",
                (contract_id,),
            ).fetchone()
            if not row:
                return None

            # Archive old version
            version_id = uuid.uuid4().hex
            self._conn.execute("""
                INSERT INTO contract_versions
                    (version_id, contract_id, version, spec_json, breaking_changes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (version_id, contract_id, row["version"], row["spec_json"], breaking_changes, now))

            # Apply update
            self._conn.execute("""
                UPDATE contracts
                SET version = ?, spec_json = ?, updated_at = ?
                WHERE contract_id = ?
            """, (new_version, spec_json, now, contract_id))
            self._conn.commit()

            updated = self._conn.execute(
                "SELECT * FROM contracts WHERE contract_id = ?",
                (contract_id,),
            ).fetchone()

        log.info("updated contract %s to v%s", contract_id, new_version)
        self._emit("contract_updated", {
            "contract_id": contract_id,
            "new_version": new_version,
            "breaking_changes": breaking_changes,
        })
        return dict(updated) if updated else None

    def deprecate_contract(self, contract_id: str) -> bool:
        """Mark a contract as deprecated. Returns True if found and was active."""
        if not contract_id:
            raise ValueError("contract_id must be non-empty")

        now = time.time()
        with self._lock:
            n = self._conn.execute("""
                UPDATE contracts SET status = 'deprecated', updated_at = ?
                WHERE contract_id = ? AND status = 'active'
            """, (now, contract_id)).rowcount
            self._conn.commit()

        if n:
            log.info("deprecated contract %s", contract_id)
            self._emit("contract_deprecated", {
                "contract_id": contract_id,
            })
        return bool(n)

    def get_contract(self, contract_id: str) -> dict | None:
        """Retrieve a single contract by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM contracts WHERE contract_id = ?",
                (contract_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_contracts(
        self,
        active_only: bool = False,
        limit: int = 500,
    ) -> list[dict]:
        """List contracts, optionally filtering to active only."""
        q = "SELECT * FROM contracts WHERE 1=1"
        params: list[Any] = []
        if active_only:
            q += " AND status = 'active'"
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Bindings
    # ------------------------------------------------------------------

    def bind_contract(
        self,
        contract_id: str,
        consumer_module: str,
        provider_module: str,
    ) -> dict:
        """Bind a consumer and provider module to a contract."""
        if not contract_id or not consumer_module or not provider_module:
            raise ValueError("contract_id, consumer_module, and provider_module must be non-empty")

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM contracts WHERE contract_id = ?",
                (contract_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Contract {contract_id} not found")

        binding_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO contract_bindings
                    (binding_id, contract_id, consumer_module, provider_module, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (binding_id, contract_id, consumer_module, provider_module, now))
            self._conn.commit()

        log.info(
            "bound contract %s: %s -> %s",
            contract_id, consumer_module, provider_module,
        )
        self._emit("binding_created", {
            "binding_id": binding_id,
            "contract_id": contract_id,
            "consumer_module": consumer_module,
            "provider_module": provider_module,
        })
        return {
            "binding_id": binding_id,
            "contract_id": contract_id,
            "consumer_module": consumer_module,
            "provider_module": provider_module,
            "created_at": now,
        }

    def unbind(self, binding_id: str) -> bool:
        """Remove a binding by binding_id. Returns True if found."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM contract_bindings WHERE binding_id = ?",
                (binding_id,),
            ).rowcount
            self._conn.commit()
        if n:
            log.info("removed binding %s", binding_id)
        return bool(n)

    def get_bindings(self, contract_id: str | None = None) -> list[dict]:
        """List bindings, optionally filtered by contract_id."""
        q = "SELECT * FROM contract_bindings WHERE 1=1"
        params: list[Any] = []
        if contract_id:
            q += " AND contract_id = ?"
            params.append(contract_id)
        q += " ORDER BY created_at DESC"

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def validate_binding(
        self,
        contract_id: str,
        consumer: str,
        provider: str,
    ) -> dict:
        """Check if consumer/provider are bound and the contract is active.

        Returns dict with keys: valid (bool), reason (str).
        """
        with self._lock:
            contract = self._conn.execute(
                "SELECT * FROM contracts WHERE contract_id = ?",
                (contract_id,),
            ).fetchone()
            if not contract:
                return {"valid": False, "reason": "contract not found"}

            if contract["status"] != "active":
                return {"valid": False, "reason": f"contract is {contract['status']}"}

            binding = self._conn.execute("""
                SELECT * FROM contract_bindings
                WHERE contract_id = ?
                  AND consumer_module = ?
                  AND provider_module = ?
                LIMIT 1
            """, (contract_id, consumer, provider)).fetchone()

        if not binding:
            return {"valid": False, "reason": "no binding between consumer and provider"}

        return {"valid": True, "reason": "ok"}

    # ------------------------------------------------------------------
    # Legacy API methods (backward compatibility)
    # ------------------------------------------------------------------

    def publish(self, contract: "Contract") -> dict:
        """Publish a Contract object (legacy API).

        Registers the contract and detects breaking changes by comparing
        major version numbers.
        """
        breaking = False
        with self._lock:
            existing = self._conn.execute(
                "SELECT version FROM contracts WHERE name = ? ORDER BY created_at DESC LIMIT 1",
                (contract.name,),
            ).fetchone()

        if existing:
            old_major = int(existing["version"].split(".")[0])
            new_major = int(contract.version.split(".")[0])
            breaking = new_major > old_major

        result = self.register_contract(
            name=contract.name,
            version=contract.version,
            spec_json=contract.schema_def,
        )
        result["breaking"] = breaking
        return result

    def get(self, name: str, version: str | None = None) -> dict | None:
        """Get a contract by name, optionally by version (legacy API)."""
        with self._lock:
            if version:
                row = self._conn.execute(
                    "SELECT * FROM contract_versions WHERE contract_id IN "
                    "(SELECT contract_id FROM contracts WHERE name = ?) AND version = ?",
                    (name, version),
                ).fetchone()
                if row:
                    return dict(row)
                # Also check current contracts
                row = self._conn.execute(
                    "SELECT * FROM contracts WHERE name = ? AND version = ?",
                    (name, version),
                ).fetchone()
                return dict(row) if row else None
            # Return latest by name
            row = self._conn.execute(
                "SELECT * FROM contracts WHERE name = ? ORDER BY created_at DESC LIMIT 1",
                (name,),
            ).fetchone()
            if row:
                d = dict(row)
                d["is_latest"] = 1
                return d
            return None

    def list_versions(self, name: str) -> list[dict]:
        """List all versions of a contract by name (legacy API)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM contracts WHERE name = ? ORDER BY created_at",
                (name,),
            ).fetchall()
            result = [dict(r) for r in rows]
            # Also check archived versions
            contract_ids = [r["contract_id"] for r in result]
            if contract_ids:
                placeholders = ",".join("?" * len(contract_ids))
                vrows = self._conn.execute(
                    f"SELECT * FROM contract_versions WHERE contract_id IN ({placeholders})",
                    contract_ids,
                ).fetchall()
                result.extend(dict(r) for r in vrows)
        return result

    def list_all(self, contract_type: str | None = None) -> list[dict]:
        """List all latest contracts, optionally filtered by type (legacy API)."""
        with self._lock:
            q = ("SELECT c.* FROM contracts c "
                 "INNER JOIN (SELECT name, MAX(created_at) as max_ts "
                 "            FROM contracts GROUP BY name) latest "
                 "ON c.name = latest.name AND c.created_at = latest.max_ts")
            params: list[Any] = []
            rows = self._conn.execute(q, params).fetchall()
            result = [dict(r) for r in rows]
            if contract_type:
                result = [r for r in result if r.get("contract_type") == contract_type]
        return result

    def check_compatibility(self, name: str, new_version: str) -> dict:
        """Check compatibility of a new version for an existing contract."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT version FROM contracts WHERE name = ? ORDER BY created_at DESC LIMIT 1",
                (name,),
            ).fetchone()

        if not existing:
            return {"compatible": True, "breaking": False, "message": "no existing version"}

        old_version = existing["version"]
        old_major = int(old_version.split(".")[0])
        new_major = int(new_version.split(".")[0])
        breaking = new_major > old_major

        return {
            "compatible": not breaking,
            "breaking": breaking,
            "old_version": old_version,
            "new_version": new_version,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_registry: ContractRegistry | None = None


def get_contract_registry(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ContractRegistry:
    global _registry
    if _registry is None:
        _registry = ContractRegistry(db_path, event_bus)
    return _registry


def reset_contract_registry() -> None:
    global _registry
    _registry = None


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------
# Old API exposed Contract (dataclass), ContractType (enum).  The refactored
# module uses a simpler dict-based interface.  Provide stubs so that legacy
# imports still resolve at collection time.

from dataclasses import dataclass as _dataclass
from enum import Enum


class ContractType(str, Enum):
    GRPC_SERVICE = "grpc_service"
    EVENT_SCHEMA = "event_schema"
    DATA_CONTRACT = "data_contract"
    REST_API = "rest_api"
    CONFIG_SCHEMA = "config_schema"
    POLICY_DEF = "policy_def"


@_dataclass
class Contract:
    name: str = ""
    contract_type: ContractType = ContractType.GRPC_SERVICE
    version: str = "1.0.0"
    schema_def: str = "{}"
    producer_module: str = ""
    consumer_modules: list | None = None
    description: str = ""
    contract_id: str = ""

    def __post_init__(self):
        if self.consumer_modules is None:
            self.consumer_modules = []
        if not self.contract_id:
            self.contract_id = uuid.uuid4().hex
