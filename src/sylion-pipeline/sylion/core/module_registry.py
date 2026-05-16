"""
SYLION Core — Module Registry

Single source of truth about living modules in the system.
Every module must register before it can operate.

Module lifecycle: draft → build → validate → shadow → dual → cutover → stable → deprecated

gRPC planned: RegisterModule, ListModules, GetModule, DeregisterModule
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("sylion.core.module_registry")


class ModuleKind(str, Enum):
    CORE_KERNEL  = "A"
    COGNITIVE    = "B"
    EXECUTION    = "C"
    MEMORY       = "D"
    GOVERNANCE   = "E"
    SECURITY     = "F"
    EFFICIENCY   = "G"
    AEIS_SELF    = "H"
    SKILLS       = "I"
    SURFACE      = "J"
    REBUILD      = "K"
    QUALITY      = "L"
    DEVICES      = "M"
    SDR          = "N"
    CELLULAR     = "O"
    ADVISOR      = "P"


class ModuleLifecycleStage(str, Enum):
    DRAFT      = "draft"
    BUILD      = "build"
    VALIDATE   = "validate"
    SHADOW     = "shadow"
    DUAL       = "dual"
    CUTOVER    = "cutover"
    STABLE     = "stable"
    DEPRECATED = "deprecated"


class SecurityProfile(str, Enum):
    DEV_LIGHT       = "dev-light"
    TEST_LIGHT      = "test-light"
    STAGING_STRICT  = "staging-strict"
    PROD_STRICT     = "prod-strict"


_VALID_TRANSITIONS: dict[ModuleLifecycleStage, set[ModuleLifecycleStage]] = {
    ModuleLifecycleStage.DRAFT:      {ModuleLifecycleStage.BUILD},
    ModuleLifecycleStage.BUILD:      {ModuleLifecycleStage.VALIDATE, ModuleLifecycleStage.DRAFT},
    ModuleLifecycleStage.VALIDATE:   {ModuleLifecycleStage.SHADOW, ModuleLifecycleStage.BUILD},
    ModuleLifecycleStage.SHADOW:     {ModuleLifecycleStage.DUAL, ModuleLifecycleStage.VALIDATE},
    ModuleLifecycleStage.DUAL:       {ModuleLifecycleStage.CUTOVER, ModuleLifecycleStage.SHADOW},
    ModuleLifecycleStage.CUTOVER:    {ModuleLifecycleStage.STABLE, ModuleLifecycleStage.DUAL},
    ModuleLifecycleStage.STABLE:     {ModuleLifecycleStage.DEPRECATED, ModuleLifecycleStage.SHADOW},
    ModuleLifecycleStage.DEPRECATED: set(),
}


@dataclass
class ModuleManifest:
    module_id: str
    module_kind: ModuleKind
    owner_plan: str
    implementation_strategy: str = "greenfield"
    contract_version: str = "1.0.0"
    decision_class_entry: str = "D3"
    security_profile: SecurityProfile = SecurityProfile.DEV_LIGHT
    auth_mode: str = "bootstrap"
    execution_guard: str = "off"
    audit_mode: str = "basic"
    depends_on: list[str] = field(default_factory=list)
    description: str = ""
    version: str = "1.0.0"
    milestone: str = "M0"
    lifecycle_stage: ModuleLifecycleStage = ModuleLifecycleStage.DRAFT
    registered_at: float = 0.0
    last_heartbeat: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id, "module_kind": self.module_kind.value,
            "owner_plan": self.owner_plan, "description": self.description,
            "lifecycle_stage": self.lifecycle_stage.value, "milestone": self.milestone,
        }


class ModuleRegistry:
    """Single source of truth about living modules. SQLite-backed. Thread-safe."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._callbacks: list[Callable[[str, dict], None]] = []
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_table()

    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_modules (
                module_id TEXT PRIMARY KEY, module_kind TEXT NOT NULL, owner_plan TEXT NOT NULL,
                strategy TEXT NOT NULL DEFAULT 'greenfield', contract_ver TEXT NOT NULL DEFAULT '1.0.0',
                decision_cls TEXT NOT NULL DEFAULT 'D3', sec_profile TEXT NOT NULL DEFAULT 'dev-light',
                auth_mode TEXT NOT NULL DEFAULT 'bootstrap', exec_guard TEXT NOT NULL DEFAULT 'off',
                audit_mode TEXT NOT NULL DEFAULT 'basic', depends_on TEXT NOT NULL DEFAULT '[]',
                description TEXT NOT NULL DEFAULT '', version TEXT NOT NULL DEFAULT '1.0.0',
                milestone TEXT NOT NULL DEFAULT 'M0', lifecycle TEXT NOT NULL DEFAULT 'draft',
                registered_at REAL NOT NULL DEFAULT 0, last_heartbeat REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.commit()

    def on_event(self, callback: Callable[[str, dict], None]):
        self._callbacks.append(callback)

    def _emit(self, event_type: str, payload: dict):
        for cb in self._callbacks:
            try:
                cb(event_type, payload)
            except Exception:
                log.exception("callback error for %s", event_type)

    def register(self, manifest: ModuleManifest) -> dict:
        now = time.time()
        manifest.registered_at = now
        manifest.last_heartbeat = now

        with self._lock:
            if self._conn.execute("SELECT 1 FROM sylion_modules WHERE module_id=?",
                                  (manifest.module_id,)).fetchone():
                raise ValueError(f"Module {manifest.module_id} already registered")

            for dep in manifest.depends_on:
                if not self._conn.execute("SELECT 1 FROM sylion_modules WHERE module_id=?",
                                          (dep,)).fetchone():
                    raise ValueError(f"Dependency {dep} not registered")

            self._conn.execute("""
                INSERT INTO sylion_modules (module_id, module_kind, owner_plan, strategy,
                    contract_ver, decision_cls, sec_profile, auth_mode, exec_guard, audit_mode,
                    depends_on, description, version, milestone, lifecycle, registered_at, last_heartbeat)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (manifest.module_id, manifest.module_kind.value, manifest.owner_plan,
                  manifest.implementation_strategy, manifest.contract_version,
                  manifest.decision_class_entry, manifest.security_profile.value,
                  manifest.auth_mode, manifest.execution_guard, manifest.audit_mode,
                  json.dumps(manifest.depends_on), manifest.description, manifest.version,
                  manifest.milestone, manifest.lifecycle_stage.value, now, now))
            self._conn.commit()

        self._emit("module.registered", {"module_id": manifest.module_id})
        log.info("registered %s (%s)", manifest.module_id, manifest.module_kind.value)
        return manifest.to_dict()

    def deregister(self, module_id: str) -> bool:
        with self._lock:
            dependents = self._conn.execute(
                "SELECT module_id FROM sylion_modules WHERE depends_on LIKE ?",
                (f'%"{module_id}"%',)
            ).fetchall()
            if dependents:
                raise ValueError(f"Cannot deregister: {[r['module_id'] for r in dependents]} depend on {module_id}")
            n = self._conn.execute("DELETE FROM sylion_modules WHERE module_id=?", (module_id,)).rowcount
            self._conn.commit()
        if n:
            self._emit("module.deregistered", {"module_id": module_id})
        return bool(n)

    def get(self, module_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM sylion_modules WHERE module_id=?", (module_id,)).fetchone()
            return dict(row) if row else None

    def list_modules(self, kind: str | None = None, milestone: str | None = None,
                     lifecycle: str | None = None) -> list[dict]:
        q, p = "SELECT * FROM sylion_modules WHERE 1=1", []
        if kind:    q += " AND module_kind=?";  p.append(kind)
        if milestone: q += " AND milestone=?";  p.append(milestone)
        if lifecycle: q += " AND lifecycle=?";  p.append(lifecycle)
        with self._lock:
            return [dict(r) for r in self._conn.execute(q + " ORDER BY module_id", p).fetchall()]

    def transition(self, module_id: str, target: ModuleLifecycleStage) -> dict:
        with self._lock:
            row = self._conn.execute("SELECT lifecycle FROM sylion_modules WHERE module_id=?",
                                     (module_id,)).fetchone()
            if not row:
                raise ValueError(f"Module {module_id} not found")
            current = ModuleLifecycleStage(row["lifecycle"])
            if target not in _VALID_TRANSITIONS.get(current, set()):
                raise ValueError(f"Invalid {current.value} → {target.value} for {module_id}")
            self._conn.execute("UPDATE sylion_modules SET lifecycle=?, last_heartbeat=? WHERE module_id=?",
                               (target.value, time.time(), module_id))
            self._conn.commit()
        self._emit("module.lifecycle.transition", {"module_id": module_id, "from": current.value, "to": target.value})
        return {"module_id": module_id, "lifecycle": target.value}

    def heartbeat(self, module_id: str):
        with self._lock:
            self._conn.execute("UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
                               (time.time(), module_id))
            self._conn.commit()


_registry: ModuleRegistry | None = None

def get_registry(db_path: str | Path | None = None) -> ModuleRegistry:
    global _registry
    if _registry is None:
        _registry = ModuleRegistry(db_path)
    return _registry
