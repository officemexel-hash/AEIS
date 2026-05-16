"""
SYLION Core -- Bundle Assembler

Assembles versioned bundles of components that can be deployed together.
Each bundle contains components (module references with config), tracks
version history, and supports deployment to target environments.

Tables:
  bundles            -- named bundles with status and description
  bundle_components  -- individual components attached to a bundle
  bundle_versions    -- versioned snapshots for audit and rollback

Events:
  bundle_created    -- emitted when create_bundle() is called
  component_added   -- emitted when add_component() is called
  version_created   -- emitted when create_version() is called
  bundle_deployed   -- emitted when deploy_bundle() is called

gRPC planned: CreateBundle, AddComponent, RemoveComponent,
              CreateVersion, DeployBundle, GetBundle
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

log = logging.getLogger("sylion.core.bundle_assembler")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = ("draft", "ready", "deploying", "deployed", "failed")


class BundleAssembler:
    """Assembles versioned bundles of components. SQLite-backed. Thread-safe."""

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
            CREATE TABLE IF NOT EXISTS bundles (
                bundle_id   TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'draft',
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bundles_name
                ON bundles(name)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bundles_status
                ON bundles(status)
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS bundle_components (
                component_id   TEXT PRIMARY KEY,
                bundle_id      TEXT NOT NULL,
                component_type TEXT NOT NULL,
                component_ref  TEXT NOT NULL,
                config_json    TEXT NOT NULL DEFAULT '{}',
                created_at     REAL NOT NULL,
                FOREIGN KEY (bundle_id) REFERENCES bundles(bundle_id)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bc_bundle
                ON bundle_components(bundle_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bc_type
                ON bundle_components(component_type)
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS bundle_versions (
                version_id  TEXT PRIMARY KEY,
                bundle_id   TEXT NOT NULL,
                version_tag TEXT NOT NULL,
                snapshot    TEXT NOT NULL DEFAULT '{}',
                created_at  REAL NOT NULL,
                FOREIGN KEY (bundle_id) REFERENCES bundles(bundle_id)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bv_bundle
                ON bundle_versions(bundle_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bv_tag
                ON bundle_versions(bundle_id, version_tag)
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
                source_module="core.bundle_assembler",
            ))

    # ------------------------------------------------------------------
    # Bundle CRUD
    # ------------------------------------------------------------------

    def create_bundle(
        self,
        name: str,
        description: str = "",
        components_list: list[dict] | None = None,
    ) -> dict:
        """Create a new bundle, optionally with initial components.

        Each component dict may contain: component_type, component_ref, config_json.
        """
        if not name:
            raise ValueError("name must be non-empty")

        bundle_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO bundles
                    (bundle_id, name, description, status, created_at, updated_at)
                VALUES (?, ?, ?, 'draft', ?, ?)
            """, (bundle_id, name, description, now, now))

            added_components: list[dict] = []
            if components_list:
                for comp in components_list:
                    cid = uuid.uuid4().hex
                    comp_type = comp.get("component_type", "module")
                    comp_ref = comp.get("component_ref", "")
                    config = comp.get("config_json", "{}")
                    if isinstance(config, dict):
                        config = json.dumps(config)

                    self._conn.execute("""
                        INSERT INTO bundle_components
                            (component_id, bundle_id, component_type, component_ref,
                             config_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (cid, bundle_id, comp_type, comp_ref, config, now))

                    added_components.append({
                        "component_id": cid,
                        "bundle_id": bundle_id,
                        "component_type": comp_type,
                        "component_ref": comp_ref,
                        "config_json": config,
                    })

            self._conn.commit()

        log.info("created bundle %s (%s) with %d components", bundle_id, name, len(added_components))
        self._emit("bundle_created", {
            "bundle_id": bundle_id,
            "name": name,
            "component_count": len(added_components),
        })
        return {
            "bundle_id": bundle_id,
            "name": name,
            "description": description,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
            "components": added_components,
        }

    def add_component(
        self,
        bundle_id: str,
        component_type: str,
        component_ref: str,
        config_json: str | dict = "{}",
    ) -> dict:
        """Add a component to an existing bundle."""
        if not bundle_id or not component_type or not component_ref:
            raise ValueError("bundle_id, component_type, and component_ref must be non-empty")

        if isinstance(config_json, dict):
            config_json = json.dumps(config_json)

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM bundles WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Bundle {bundle_id} not found")

        component_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO bundle_components
                    (component_id, bundle_id, component_type, component_ref,
                     config_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (component_id, bundle_id, component_type, component_ref, config_json, now))
            self._conn.execute(
                "UPDATE bundles SET updated_at = ? WHERE bundle_id = ?",
                (now, bundle_id),
            )
            self._conn.commit()

        log.info("added component %s (%s) to bundle %s", component_ref, component_type, bundle_id)
        self._emit("component_added", {
            "component_id": component_id,
            "bundle_id": bundle_id,
            "component_type": component_type,
            "component_ref": component_ref,
        })
        return {
            "component_id": component_id,
            "bundle_id": bundle_id,
            "component_type": component_type,
            "component_ref": component_ref,
            "config_json": config_json,
            "created_at": now,
        }

    def remove_component(self, bundle_id: str, component_id: str) -> bool:
        """Remove a component from a bundle. Returns True if found."""
        if not bundle_id or not component_id:
            raise ValueError("bundle_id and component_id must be non-empty")

        now = time.time()
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM bundle_components WHERE component_id = ? AND bundle_id = ?",
                (component_id, bundle_id),
            ).rowcount
            if n:
                self._conn.execute(
                    "UPDATE bundles SET updated_at = ? WHERE bundle_id = ?",
                    (now, bundle_id),
                )
            self._conn.commit()

        if n:
            log.info("removed component %s from bundle %s", component_id, bundle_id)
        return bool(n)

    def get_bundle(self, bundle_id: str) -> dict | None:
        """Retrieve a bundle with all its components."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM bundles WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
            if not row:
                return None

            components = self._conn.execute(
                "SELECT * FROM bundle_components WHERE bundle_id = ? ORDER BY created_at",
                (bundle_id,),
            ).fetchall()

        result = dict(row)
        result["components"] = [dict(c) for c in components]
        return result

    def list_bundles(
        self,
        status: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """List bundles, optionally filtered by status."""
        q = "SELECT * FROM bundles WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    def create_version(self, bundle_id: str, version_tag: str) -> dict | None:
        """Snapshot the current state of a bundle as a version.

        Stores all components as a JSON snapshot in bundle_versions.
        Returns the version record or None if bundle not found.
        """
        if not bundle_id or not version_tag:
            raise ValueError("bundle_id and version_tag must be non-empty")

        now = time.time()

        with self._lock:
            bundle = self._conn.execute(
                "SELECT * FROM bundles WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
            if not bundle:
                return None

            components = self._conn.execute(
                "SELECT * FROM bundle_components WHERE bundle_id = ? ORDER BY created_at",
                (bundle_id,),
            ).fetchall()

            snapshot = json.dumps({
                "bundle": dict(bundle),
                "components": [dict(c) for c in components],
            }, default=str)

            version_id = uuid.uuid4().hex
            self._conn.execute("""
                INSERT INTO bundle_versions
                    (version_id, bundle_id, version_tag, snapshot, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (version_id, bundle_id, version_tag, snapshot, now))
            self._conn.commit()

        log.info("created version %s for bundle %s", version_tag, bundle_id)
        self._emit("version_created", {
            "version_id": version_id,
            "bundle_id": bundle_id,
            "version_tag": version_tag,
        })
        return {
            "version_id": version_id,
            "bundle_id": bundle_id,
            "version_tag": version_tag,
            "created_at": now,
        }

    def get_version(self, bundle_id: str, version_tag: str) -> dict | None:
        """Retrieve a specific version of a bundle."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM bundle_versions WHERE bundle_id = ? AND version_tag = ?",
                (bundle_id, version_tag),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["snapshot"] = json.loads(result["snapshot"])
        return result

    def list_versions(self, bundle_id: str) -> list[dict]:
        """List all versions for a bundle."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT version_id, bundle_id, version_tag, created_at "
                "FROM bundle_versions WHERE bundle_id = ? ORDER BY created_at DESC",
                (bundle_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Deployment
    # ------------------------------------------------------------------

    def deploy_bundle(self, bundle_id: str, target_env: str) -> dict | None:
        """Deploy a bundle to a target environment.

        Changes bundle status to 'deploying' and emits bundle_deployed event.
        Returns updated bundle dict or None if bundle not found.
        """
        if not bundle_id or not target_env:
            raise ValueError("bundle_id and target_env must be non-empty")

        now = time.time()

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM bundles WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
            if not row:
                return None

            self._conn.execute(
                "UPDATE bundles SET status = 'deploying', updated_at = ? WHERE bundle_id = ?",
                (now, bundle_id),
            )
            self._conn.commit()

        log.info("deploying bundle %s to %s", bundle_id, target_env)
        self._emit("bundle_deployed", {
            "bundle_id": bundle_id,
            "target_env": target_env,
            "status": "deploying",
        })
        return {
            "bundle_id": bundle_id,
            "name": row["name"],
            "status": "deploying",
            "target_env": target_env,
            "updated_at": now,
        }

    # ------------------------------------------------------------------
    # Legacy bundle flow
    # ------------------------------------------------------------------

    def assemble(self, module_ids: list[str],
                 created_by: str = "") -> dict:
        """Create a deployment bundle from module IDs.

        The core REST routes historically exposed ``assemble/validate/ship``.
        Keep those verbs as a small compatibility layer over the current
        component-based bundle model.
        """
        modules = [module_id for module_id in module_ids if module_id]
        if not modules:
            raise ValueError("module_ids must contain at least one module")
        components = [
            {
                "component_type": "module",
                "component_ref": module_id,
                "config_json": {"created_by": created_by} if created_by else {},
            }
            for module_id in modules
        ]
        bundle = self.create_bundle(
            name=f"bundle-{int(time.time())}-{uuid.uuid4().hex[:6]}",
            description=f"Assembled by {created_by}" if created_by else "",
            components_list=components,
        )
        bundle["modules"] = modules
        bundle["state"] = "draft"
        return bundle

    def validate(self, bundle_id: str) -> dict:
        """Mark a bundle ready after validation."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM bundles WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Bundle {bundle_id} not found")
            self._conn.execute(
                "UPDATE bundles SET status = 'ready', updated_at = ? "
                "WHERE bundle_id = ?",
                (now, bundle_id),
            )
            self._conn.commit()
        self._emit("bundle_validated", {"bundle_id": bundle_id, "status": "ready"})
        return {"bundle_id": bundle_id, "valid": True, "state": "ready"}

    def ship(self, bundle_id: str, target_env: str = "production") -> dict:
        """Ship a validated bundle to a target environment."""
        result = self.deploy_bundle(bundle_id, target_env)
        if result is None:
            raise ValueError(f"Bundle {bundle_id} not found")
        result["shipped"] = True
        result["state"] = result.get("status", "deploying")
        return result


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_assembler: BundleAssembler | None = None


def get_bundle_assembler(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> BundleAssembler:
    global _assembler
    if _assembler is None:
        _assembler = BundleAssembler(db_path, event_bus)
    return _assembler


def reset_bundle_assembler() -> None:
    global _assembler
    _assembler = None


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------
from dataclasses import dataclass as _dataclass
from enum import Enum


class BundleState(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"


@_dataclass
class Bundle:
    bundle_id: str = ""
    name: str = ""
    description: str = ""
    status: str = "draft"
    components: list | None = None
