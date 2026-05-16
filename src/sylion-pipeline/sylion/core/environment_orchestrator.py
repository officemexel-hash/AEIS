"""
SYLION Core -- Environment Orchestrator

Manage module deployment lifecycle with shadow->dual->cutover transitions.
Multi-environment support: dev-light, test-light, staging-strict, prod-strict.

Each environment has its own security profile, module list, and configuration.
Environment switching requires governance approval (approval_id).
SQLite-backed, thread-safe via threading.Lock, singleton pattern.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus
from sylion.core.module_registry import (
    ModuleRegistry, ModuleLifecycleStage, get_registry,
)
from sylion.security.profiles import PROFILES, SecurityProfile

# Re-export BundleAssembler for backward compatibility
from sylion.core.bundle_assembler import (  # noqa: F401
    BundleAssembler, get_bundle_assembler,
)
try:
    from sylion.core.bundle_assembler import BundleState, Bundle  # noqa: F401
except ImportError:
    pass

log = logging.getLogger("sylion.core.environment_orchestrator")


class DeployAction(str, Enum):
    DEPLOY   = "deploy"
    UNDEPLOY = "undeploy"
    SWAP     = "swap"


@dataclass
class DeployRequest:
    module_id: str
    action: DeployAction
    version: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    requested_by: str = ""


@dataclass
class DeployResult:
    request_id: str = ""
    module_id: str = ""
    action: DeployAction = DeployAction.DEPLOY
    status: str = "failed"
    message: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.request_id:
            self.request_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


class EnvironmentOrchestrator:
    """Manage module deployment lifecycle and multi-environment orchestration.

    Each environment is a named deployment target (dev, test, staging, prod)
    with an associated security profile, a list of module IDs, and arbitrary
    config overrides. Switching the active environment requires a governance
    approval_id.

    SQLite-backed, thread-safe via threading.Lock, singleton pattern.
    Integrates with EventBus for all state changes.
    """

    def __init__(self, db_path: str = ":memory:",
                 event_bus: EventBus | None = None,
                 registry: ModuleRegistry | None = None):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._event_bus = event_bus
        self._registry = registry
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Internal: table setup
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_environments (
                env_id       TEXT PRIMARY KEY,
                profile      TEXT NOT NULL,
                modules      TEXT NOT NULL DEFAULT '[]',
                config       TEXT NOT NULL DEFAULT '{}',
                created_at   REAL NOT NULL DEFAULT 0,
                updated_at   REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_env_switch_log (
                switch_id    TEXT PRIMARY KEY,
                from_env     TEXT NOT NULL,
                to_env       TEXT NOT NULL,
                approval_id  TEXT NOT NULL,
                switched_at  REAL NOT NULL DEFAULT 0
            )
        """)
        # Track active environment in a key-value meta table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_env_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Internal: set / get active env in meta
    # ------------------------------------------------------------------

    def _set_active_env(self, env_id: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO sylion_env_meta (key, value) VALUES ('active_env', ?)",
            (env_id,),
        )
        self._conn.commit()

    def _get_active_env(self) -> str | None:
        with self._lock:
            return self._get_active_env_unlocked()

    def _get_active_env_unlocked(self) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM sylion_env_meta WHERE key = 'active_env'"
        ).fetchone()
        return row["value"] if row else None

    def _emit(self, topic: str, payload: dict) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="core.environment_orchestrator",
            ))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_environment(
        self,
        env_id: str,
        profile: str,
        modules: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict:
        """Register a named environment.

        Args:
            env_id: Unique environment identifier (e.g. "dev", "test", "staging", "prod").
            profile: Security profile name from PROFILES (e.g. "dev-light", "prod-strict").
            modules: List of module IDs associated with this environment.
            config: Arbitrary config overrides for this environment.

        Returns:
            dict with keys: registered, env_id, profile, message.
        """
        if profile not in PROFILES:
            return {
                "registered": False,
                "env_id": env_id,
                "profile": profile,
                "message": f"Unknown profile: {profile}",
            }

        modules = modules or []
        config = config or {}
        now = time.time()

        with self._lock:
            existing = self._conn.execute(
                "SELECT env_id FROM sylion_environments WHERE env_id = ?",
                (env_id,),
            ).fetchone()
            if existing:
                return {
                    "registered": False,
                    "env_id": env_id,
                    "profile": profile,
                    "message": f"Environment '{env_id}' already registered",
                }

            self._conn.execute("""
                INSERT INTO sylion_environments (env_id, profile, modules, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (env_id, profile, json.dumps(modules),
                  json.dumps(config, default=str), now, now))
            self._conn.commit()

        # If no active environment yet, set this as active
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM sylion_env_meta WHERE key = 'active_env'"
            ).fetchone()
            if not row:
                self._conn.execute(
                    "INSERT OR REPLACE INTO sylion_env_meta (key, value) VALUES ('active_env', ?)",
                    (env_id,),
                )
                self._conn.commit()

        self._emit("environment.registered", {
            "env_id": env_id, "profile": profile,
            "module_count": len(modules),
        })

        log.info("environment registered: %s (profile=%s, modules=%d)",
                 env_id, profile, len(modules))

        return {
            "registered": True,
            "env_id": env_id,
            "profile": profile,
            "message": f"Environment '{env_id}' registered with profile '{profile}'",
        }

    def get_active_environment(self) -> dict | None:
        """Return the full config of the current active environment, or None."""
        active_id = self._get_active_env()
        if active_id is None:
            return None
        return self.get_environment_config(active_id)

    def switch_environment(self, target_env_id: str, approval_id: str) -> dict:
        """Switch active environment. Requires governance approval_id.

        Args:
            target_env_id: Environment to switch to.
            approval_id: Governance approval token (non-empty string).

        Returns:
            dict with keys: switched, from_env, to_env, approval_id, message.
        """
        if not approval_id or not approval_id.strip():
            return {
                "switched": False,
                "from_env": self._get_active_env(),
                "to_env": target_env_id,
                "approval_id": approval_id,
                "message": "approval_id is required for environment switch",
            }

        with self._lock:
            target = self._conn.execute(
                "SELECT env_id FROM sylion_environments WHERE env_id = ?",
                (target_env_id,),
            ).fetchone()
            if not target:
                return {
                    "switched": False,
                    "from_env": self._get_active_env_unlocked(),
                    "to_env": target_env_id,
                    "approval_id": approval_id,
                    "message": f"Environment '{target_env_id}' not found",
                }

            from_env = self._get_active_env_unlocked()
            if from_env == target_env_id:
                return {
                    "switched": False,
                    "from_env": from_env,
                    "to_env": target_env_id,
                    "approval_id": approval_id,
                    "message": f"Already on environment '{target_env_id}'",
                }

            switch_id = uuid.uuid4().hex
            now = time.time()

            self._conn.execute(
                "INSERT OR REPLACE INTO sylion_env_meta (key, value) VALUES ('active_env', ?)",
                (target_env_id,),
            )

            self._conn.execute("""
                INSERT INTO sylion_env_switch_log (switch_id, from_env, to_env, approval_id, switched_at)
                VALUES (?, ?, ?, ?, ?)
            """, (switch_id, from_env, target_env_id, approval_id, now))
            self._conn.commit()

        self._emit("environment.switched", {
            "switch_id": switch_id,
            "from_env": from_env,
            "to_env": target_env_id,
            "approval_id": approval_id,
        })

        log.info("environment switched: %s -> %s (approval=%s)",
                 from_env, target_env_id, approval_id[:12])

        return {
            "switched": True,
            "from_env": from_env,
            "to_env": target_env_id,
            "approval_id": approval_id,
            "message": f"Switched from '{from_env}' to '{target_env_id}'",
        }

    def get_environment_config(self, env_id: str) -> dict | None:
        """Return full config for a given environment.

        Returns dict with keys: env_id, profile, modules, config, or None.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_environments WHERE env_id = ?",
                (env_id,),
            ).fetchone()
            if not row:
                return None

            profile_name = row["profile"]
            modules_raw = row["modules"]
            config_raw = row["config"]
            created_at = row["created_at"]
            updated_at = row["updated_at"]

        sec_profile = PROFILES.get(profile_name)

        return {
            "env_id": env_id,
            "profile": profile_name,
            "security": {
                "auth_mode": sec_profile.auth_mode if sec_profile else None,
                "audit_level": sec_profile.audit_level if sec_profile else None,
                "exec_guard": sec_profile.exec_guard if sec_profile else None,
                "encryption_at_rest": sec_profile.encryption_at_rest if sec_profile else None,
                "signing_enabled": sec_profile.signing_enabled if sec_profile else None,
                "policy_enforcement": sec_profile.policy_enforcement if sec_profile else None,
                "rate_limit": sec_profile.rate_limit if sec_profile else None,
                "session_timeout": sec_profile.session_timeout if sec_profile else None,
            } if sec_profile else None,
            "modules": json.loads(modules_raw),
            "config": json.loads(config_raw),
            "created_at": created_at,
            "updated_at": updated_at,
        }

    def list_environments(self) -> list[dict]:
        """List all registered environments with summary info."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT env_id, profile, modules FROM sylion_environments ORDER BY env_id"
            ).fetchall()
            active_row = self._conn.execute(
                "SELECT value FROM sylion_env_meta WHERE key = 'active_env'"
            ).fetchone()
            active_id = active_row["value"] if active_row else None

            result = []
            for row in rows:
                modules = json.loads(row["modules"])
                result.append({
                    "env_id": row["env_id"],
                    "profile": row["profile"],
                    "module_count": len(modules),
                    "is_active": row["env_id"] == active_id,
                })
        return result

    def validate_environment(self, env_id: str) -> dict:
        """Validate all modules in an environment are healthy.

        Returns dict with: valid, env_id, healthy_modules, unhealthy_modules,
        missing_modules, message.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT modules, profile FROM sylion_environments WHERE env_id = ?",
                (env_id,),
            ).fetchone()
            if not row:
                return {
                    "valid": False,
                    "env_id": env_id,
                    "healthy_modules": [],
                    "unhealthy_modules": [],
                    "missing_modules": [],
                    "message": f"Environment '{env_id}' not found",
                }
            module_ids: list[str] = json.loads(row["modules"])
            profile_name = row["profile"]

        healthy: list[str] = []
        unhealthy: list[str] = []
        missing: list[str] = []

        if self._registry is not None:
            for mid in module_ids:
                mod = self._registry.get(mid)
                if mod is None:
                    missing.append(mid)
                elif mod.get("lifecycle") in ("stable", "cutover", "dual"):
                    healthy.append(mid)
                else:
                    unhealthy.append(mid)
        else:
            # Without a registry, all declared modules are assumed healthy
            healthy = list(module_ids)

        is_valid = len(unhealthy) == 0 and len(missing) == 0

        return {
            "valid": is_valid,
            "env_id": env_id,
            "profile": profile_name,
            "healthy_modules": healthy,
            "unhealthy_modules": unhealthy,
            "missing_modules": missing,
            "message": (
                "All modules healthy"
                if is_valid
                else f"{len(unhealthy)} unhealthy, {len(missing)} missing"
            ),
        }

    def compare_environments(self, env_a: str, env_b: str) -> dict:
        """Compare two environments: profiles, module sets, configs.

        Returns dict with: comparable, env_a, env_b, profile_diff,
        modules_only_in_a, modules_only_in_b, config_diff.
        """
        cfg_a = self.get_environment_config(env_a)
        cfg_b = self.get_environment_config(env_b)

        if cfg_a is None or cfg_b is None:
            missing = []
            if cfg_a is None:
                missing.append(env_a)
            if cfg_b is None:
                missing.append(env_b)
            return {
                "comparable": False,
                "env_a": env_a,
                "env_b": env_b,
                "message": f"Environment(s) not found: {missing}",
            }

        modules_a = set(cfg_a["modules"])
        modules_b = set(cfg_b["modules"])

        # Config diff: keys present in one but not the other, or different values
        config_diff: dict[str, Any] = {}
        all_config_keys = set(cfg_a["config"].keys()) | set(cfg_b["config"].keys())
        for key in all_config_keys:
            val_a = cfg_a["config"].get(key)
            val_b = cfg_b["config"].get(key)
            if val_a != val_b:
                config_diff[key] = {"env_a": val_a, "env_b": val_b}

        return {
            "comparable": True,
            "env_a": env_a,
            "env_b": env_b,
            "profile_diff": {
                "env_a": cfg_a["profile"],
                "env_b": cfg_b["profile"],
                "same": cfg_a["profile"] == cfg_b["profile"],
            },
            "modules_only_in_a": sorted(modules_a - modules_b),
            "modules_only_in_b": sorted(modules_b - modules_a),
            "modules_common": sorted(modules_a & modules_b),
            "config_diff": config_diff,
        }

    def get_diff(self, env_id: str) -> dict:
        """Show differences between the active environment and a target environment.

        Returns the same structure as compare_environments, but compares
        the current active environment with the given env_id.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM sylion_env_meta WHERE key = 'active_env'"
            ).fetchone()
            active = row["value"] if row else None
        if active is None:
            return {
                "comparable": False,
                "env_a": None,
                "env_b": env_id,
                "message": "No active environment set",
            }
        return self.compare_environments(active, env_id)

    # ------------------------------------------------------------------
    # Legacy deploy API (preserved for backward compatibility)
    # ------------------------------------------------------------------

    def set_registry(self, registry: ModuleRegistry) -> None:
        """Inject a module registry for deploy operations."""
        self._registry = registry

    def deploy(self, request: DeployRequest) -> DeployResult:
        """Deploy a module to its next lifecycle stage."""
        if self._registry is None:
            return DeployResult(
                module_id=request.module_id, action=request.action,
                status="failed", message="No module registry configured"
            )

        mod = self._registry.get(request.module_id)
        if not mod:
            return DeployResult(
                module_id=request.module_id, action=request.action,
                status="failed", message=f"Module {request.module_id} not found"
            )

        current = ModuleLifecycleStage(mod["lifecycle"])

        if request.action == DeployAction.DEPLOY:
            transitions = {
                ModuleLifecycleStage.DRAFT: ModuleLifecycleStage.BUILD,
                ModuleLifecycleStage.BUILD: ModuleLifecycleStage.VALIDATE,
                ModuleLifecycleStage.VALIDATE: ModuleLifecycleStage.SHADOW,
                ModuleLifecycleStage.SHADOW: ModuleLifecycleStage.DUAL,
                ModuleLifecycleStage.DUAL: ModuleLifecycleStage.CUTOVER,
                ModuleLifecycleStage.CUTOVER: ModuleLifecycleStage.STABLE,
            }
            target = transitions.get(current)
            if not target:
                return DeployResult(
                    module_id=request.module_id, action=request.action,
                    status="failed", message=f"Cannot deploy from {current.value}"
                )

            try:
                self._registry.transition(request.module_id, target)
            except ValueError as e:
                return DeployResult(
                    module_id=request.module_id, action=request.action,
                    status="failed", message=str(e)
                )

            msg = f"{request.module_id}: {current.value} -> {target.value}"

        elif request.action == DeployAction.SWAP:
            msg = f"{request.module_id}: implementation swapped"

        elif request.action == DeployAction.UNDEPLOY:
            rollback = {
                ModuleLifecycleStage.DUAL: ModuleLifecycleStage.SHADOW,
                ModuleLifecycleStage.CUTOVER: ModuleLifecycleStage.DUAL,
            }
            target = rollback.get(current)
            if not target:
                return DeployResult(
                    module_id=request.module_id, action=request.action,
                    status="failed", message=f"Cannot undeploy from {current.value}"
                )
            try:
                self._registry.transition(request.module_id, target)
            except ValueError as e:
                return DeployResult(
                    module_id=request.module_id, action=request.action,
                    status="failed", message=str(e)
                )
            msg = f"{request.module_id}: rolled back {current.value} -> {target.value}"

        else:
            return DeployResult(
                module_id=request.module_id, action=request.action,
                status="failed", message=f"Unknown action {request.action}"
            )

        self._emit("environment.deployed", {
            "module_id": request.module_id,
            "action": request.action.value,
        })

        log.info(msg)
        return DeployResult(
            module_id=request.module_id, action=request.action,
            status="success", message=msg
        )

    def get_status(self) -> list[dict]:
        if self._registry is not None:
            return self._registry.list_modules()
        return []

    def get_switch_history(self) -> list[dict]:
        """Return chronological list of environment switches."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sylion_env_switch_log ORDER BY switched_at ASC"
            ).fetchall()
            return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_env_orch: EnvironmentOrchestrator | None = None


def get_environment_orchestrator(db_path: str = ":memory:",
                                 event_bus: EventBus | None = None) -> EnvironmentOrchestrator:
    global _env_orch
    if _env_orch is None:
        _env_orch = EnvironmentOrchestrator(db_path, event_bus)
    return _env_orch


def reset_environment_orchestrator() -> None:
    """Reset the global singleton (for testing only)."""
    global _env_orch
    if _env_orch is not None:
        try:
            _env_orch._conn.close()
        except Exception:
            pass
    _env_orch = None
