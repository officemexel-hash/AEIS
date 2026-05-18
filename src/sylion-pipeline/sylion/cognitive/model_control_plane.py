"""Unified model control plane for provider, model, routing and budget state."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from sylion.cognitive.model_registry import ModelRegistry
from sylion.cognitive.model_router import ModelRouter
from sylion.core.event_bus import EventBus, SylionEvent
from sylion.monitoring.model_budget import ModelBudgetManager

log = logging.getLogger("sylion.cognitive.model_control_plane")


class ModelControlPlane:
    """Single runtime facade over model registry, routing and budget checks."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        event_bus: EventBus | None = None,
        model_registry: ModelRegistry | None = None,
        model_router: ModelRouter | None = None,
        budget_manager: ModelBudgetManager | None = None,
    ) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self.model_registry = model_registry or ModelRegistry(db_path=self._db_path, event_bus=event_bus)
        self.model_router = model_router or ModelRouter(db_path=self._db_path, event_bus=event_bus)
        self.budget_manager = budget_manager or ModelBudgetManager(db_path=self._db_path, event_bus=event_bus)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS model_control_providers (
                provider_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL DEFAULT '',
                models_json TEXT NOT NULL DEFAULT '[]',
                quotas_json TEXT NOT NULL DEFAULT '{}',
                keys_ref TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                registered_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_control_routes (
                route_id TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                project_id TEXT NOT NULL DEFAULT '',
                model_id TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                fallback_chain_json TEXT NOT NULL DEFAULT '[]',
                constraints_json TEXT NOT NULL DEFAULT '{}',
                updated_at REAL NOT NULL,
                UNIQUE(stage, project_id)
            );
            CREATE TABLE IF NOT EXISTS model_control_council_configs (
                project_id TEXT PRIMARY KEY,
                quorum INTEGER NOT NULL DEFAULT 1,
                roles_json TEXT NOT NULL DEFAULT '[]',
                weights_json TEXT NOT NULL DEFAULT '{}',
                model_assignments_json TEXT NOT NULL DEFAULT '{}',
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mcp_routes_stage_project
                ON model_control_routes(stage, project_id);
        """)
        self._conn.commit()

    @staticmethod
    def _json_loads(raw: Any, default: Any) -> Any:
        if raw is None or raw == "":
            return default
        if isinstance(raw, (dict, list)):
            return raw
        try:
            parsed = json.loads(str(raw))
        except (TypeError, json.JSONDecodeError):
            return default
        return parsed

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value if value is not None else {}, sort_keys=True)

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="cognitive.model_control_plane",
            ))

    def _provider_row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["models"] = self._json_loads(item.pop("models_json"), [])
        item["quotas"] = self._json_loads(item.pop("quotas_json"), {})
        item["metadata"] = self._json_loads(item.pop("metadata_json"), {})
        return item

    def _route_row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["fallback_chain"] = self._json_loads(item.pop("fallback_chain_json"), [])
        item["constraints"] = self._json_loads(item.pop("constraints_json"), {})
        return item

    def _council_row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["roles"] = self._json_loads(item.pop("roles_json"), [])
        item["weights"] = self._json_loads(item.pop("weights_json"), {})
        item["model_assignments"] = self._json_loads(item.pop("model_assignments_json"), {})
        return item

    def _require_model(self, model_id: str) -> dict[str, Any]:
        model = self.model_registry.get_model(model_id)
        if not model:
            raise ValueError(f"model_id must exist in ModelRegistry: {model_id}")
        return model

    @staticmethod
    def _capabilities(model_def: dict[str, Any]) -> list[str]:
        caps = model_def.get("capabilities") or []
        return [str(cap) for cap in caps if str(cap).strip()]

    @staticmethod
    def _cost_per_1k(model: dict[str, Any]) -> float:
        cost_in = float(model.get("cost_per_1k_in") or 0.0)
        cost_out = float(model.get("cost_per_1k_out") or 0.0)
        if cost_in or cost_out:
            return (cost_in + cost_out) / 2
        config = ModelControlPlane._json_loads(model.get("config_json"), {})
        return float(config.get("cost_per_1k_tokens") or config.get("cost_per_1k_tokens_usd") or 0.0)

    def register_provider(
        self,
        provider_id: str,
        *,
        display_name: str = "",
        models: list[dict[str, Any]] | None = None,
        quotas: dict[str, Any] | None = None,
        keys_ref: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider_id = (provider_id or "").strip()
        if not provider_id:
            raise ValueError("provider_id must not be empty")
        now = time.time()
        model_defs = list(models or [])
        with self._lock:
            existing = self._conn.execute(
                "SELECT registered_at FROM model_control_providers WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
            registered_at = float(existing["registered_at"]) if existing else now
            self._conn.execute("""
                INSERT INTO model_control_providers
                    (provider_id, display_name, models_json, quotas_json, keys_ref,
                     metadata_json, registered_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    models_json = excluded.models_json,
                    quotas_json = excluded.quotas_json,
                    keys_ref = excluded.keys_ref,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
            """, (
                provider_id,
                display_name or provider_id,
                self._json_dumps(model_defs),
                self._json_dumps(quotas or {}),
                keys_ref,
                self._json_dumps(metadata or {}),
                registered_at,
                now,
            ))
            self._conn.commit()

        registered_models: list[dict[str, Any]] = []
        for model_def in model_defs:
            registered_models.append(self._register_provider_model(provider_id, model_def))

        result = self.get_provider(provider_id) or {}
        result["registered_models"] = registered_models
        self._emit("model_control.provider.registered", {
            "provider_id": provider_id,
            "model_count": len(registered_models),
            "keys_ref": keys_ref,
        })
        return result

    def _register_provider_model(self, provider_id: str, model_def: dict[str, Any]) -> dict[str, Any]:
        model_id = str(model_def.get("model_id") or "").strip()
        if not model_id:
            raise ValueError("provider model requires model_id")
        cost_profile = dict(model_def.get("cost_profile") or {})
        config = dict(model_def.get("config") or {})
        config.update({
            "provider_model": model_def.get("provider_model") or model_id,
            "cost_per_1k_tokens": float(cost_profile.get("cost_per_1k_tokens") or 0.0),
        })
        registered = self.model_registry.register_model(
            model_id=model_id,
            provider=provider_id,
            display_name=str(model_def.get("display_name") or model_id),
            config_json=self._json_dumps(config),
            model_family=model_def.get("model_family"),
            context_window=model_def.get("context_window") or cost_profile.get("context_window"),
            cost_per_1k_in=float(cost_profile.get("cost_per_1k_in") or 0.0),
            cost_per_1k_out=float(cost_profile.get("cost_per_1k_out") or 0.0),
        )
        capabilities = self._capabilities(model_def)
        existing_caps = {
            cap.get("task_type") or cap.get("capability")
            for cap in (self.model_registry.get_model(model_id) or {}).get("capabilities", [])
        }
        for capability in capabilities:
            if capability not in existing_caps:
                self.model_registry.add_capability(model_id, capability, model_def.get("proficiency", "medium"))
        self.model_router.register_model(
            model_id=model_id,
            provider=provider_id,
            model_name=str(model_def.get("display_name") or model_id),
            capabilities=capabilities,
            cost_per_1k_tokens=float(cost_profile.get("cost_per_1k_tokens") or self._cost_per_1k(registered)),
        )
        budget = model_def.get("budget") or {}
        if budget:
            self.set_budget(
                model_id,
                daily_limit=float(budget.get("daily_limit") or 0.0),
                monthly_limit=float(budget.get("monthly_limit") or 0.0),
                alert_threshold_pct=float(budget.get("alert_threshold_pct") or 80.0),
                provider=provider_id,
                fallback_model_id=str(budget.get("fallback_model_id") or ""),
            )
        return self.model_registry.get_model(model_id) or registered

    def get_provider(self, provider_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM model_control_providers WHERE provider_id = ?",
            (provider_id,),
        ).fetchone()
        return self._provider_row(row) if row else None

    def list_providers(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM model_control_providers ORDER BY provider_id"
        ).fetchall()
        return [self._provider_row(row) for row in rows]

    def set_budget(
        self,
        model_id: str,
        *,
        daily_limit: float = 0.0,
        monthly_limit: float = 0.0,
        alert_threshold_pct: float = 80.0,
        provider: str = "",
        fallback_model_id: str = "",
    ) -> dict[str, Any]:
        model = self._require_model(model_id)
        if fallback_model_id:
            self._require_model(fallback_model_id)
        return self.budget_manager.set_budget(
            model_id,
            daily_limit=daily_limit,
            monthly_limit=monthly_limit,
            alert_threshold_pct=alert_threshold_pct,
            provider=provider or str(model.get("provider") or ""),
            fallback_model_id=fallback_model_id,
        )

    def record_usage(self, model_id: str, *, tokens: int, cost: float, task_type: str = "") -> dict[str, Any]:
        self._require_model(model_id)
        return self.budget_manager.record_usage(model_id, tokens, cost, task_type=task_type)

    def set_routing(
        self,
        stage: str,
        model_id: str,
        *,
        project_id: str = "",
        fallback_chain: list[str] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stage = (stage or "").strip()
        if not stage:
            raise ValueError("stage must not be empty")
        model = self._require_model(model_id)
        fallbacks = [m for m in (fallback_chain or []) if m and m != model_id]
        for fallback_model_id in fallbacks:
            self._require_model(fallback_model_id)
        now = time.time()
        route_id = f"{project_id or 'global'}:{stage}"
        with self._lock:
            self._conn.execute("""
                INSERT INTO model_control_routes
                    (route_id, stage, project_id, model_id, provider,
                     fallback_chain_json, constraints_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stage, project_id) DO UPDATE SET
                    model_id = excluded.model_id,
                    provider = excluded.provider,
                    fallback_chain_json = excluded.fallback_chain_json,
                    constraints_json = excluded.constraints_json,
                    updated_at = excluded.updated_at
            """, (
                route_id,
                stage,
                project_id or "",
                model_id,
                str(model.get("provider") or ""),
                self._json_dumps(fallbacks),
                self._json_dumps(constraints or {}),
                now,
            ))
            self._conn.commit()
        result = self.get_route(stage, project_id=project_id) or {}
        self._emit("model_control.routing.updated", result)
        return result

    def get_route(self, stage: str, *, project_id: str = "") -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM model_control_routes WHERE stage = ? AND project_id = ?",
            (stage, project_id or ""),
        ).fetchone()
        return self._route_row(row) if row else None

    def list_routes(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM model_control_routes ORDER BY project_id, stage"
        ).fetchall()
        return [self._route_row(row) for row in rows]

    def _resolve_route_row(self, stage: str, project_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("""
            SELECT * FROM model_control_routes
            WHERE stage = ? AND project_id IN (?, '')
            ORDER BY CASE WHEN project_id = ? THEN 0 ELSE 1 END
            LIMIT 1
        """, (stage, project_id or "", project_id or "")).fetchone()
        return self._route_row(row) if row else None

    def resolve_route(
        self,
        stage: str,
        *,
        project_id: str = "",
        task_type: str = "",
        estimated_cost: float = 0.0,
    ) -> dict[str, Any]:
        route = self._resolve_route_row(stage, project_id)
        if not route:
            raise ValueError(f"routing stage not configured: {stage}")
        constraints = route.get("constraints") or {}
        max_cost_per_1k = constraints.get("max_cost_per_1k")
        chain = [route["model_id"], *[m for m in route.get("fallback_chain", []) if m != route["model_id"]]]
        attempts: list[dict[str, Any]] = []
        for model_id in chain:
            model = self.model_registry.get_model(model_id)
            if not model:
                attempts.append({"model_id": model_id, "allowed": False, "reason": "not_registered"})
                continue
            model_cost = self._cost_per_1k(model)
            if max_cost_per_1k is not None and model_cost > float(max_cost_per_1k):
                attempts.append({
                    "model_id": model_id,
                    "allowed": False,
                    "reason": "cost_profile_exceeds_route_constraint",
                    "cost_per_1k": model_cost,
                })
                continue
            budget = self.budget_manager.check_budget(model_id)
            attempts.append({
                "model_id": model_id,
                "allowed": bool(budget.get("allowed", True)),
                "reason": "" if budget.get("allowed", True) else "budget_blocked",
                "budget": budget,
                "cost_per_1k": model_cost,
            })
            if budget.get("allowed", True):
                result = {
                    "allowed": True,
                    "stage": stage,
                    "project_id": project_id or "",
                    "task_type": task_type,
                    "selected_model_id": model_id,
                    "provider": model.get("provider") or "",
                    "fallback_used": model_id != route["model_id"],
                    "budget_enforced": True,
                    "estimated_cost": estimated_cost,
                    "route": route,
                    "attempts": attempts,
                }
                self._emit("model_control.routing.resolved", result)
                return result
        return {
            "allowed": False,
            "stage": stage,
            "project_id": project_id or "",
            "task_type": task_type,
            "selected_model_id": "",
            "budget_enforced": True,
            "reason": "no_model_passed_budget_or_constraints",
            "route": route,
            "attempts": attempts,
        }

    def configure_council(
        self,
        project_id: str,
        *,
        quorum: int,
        roles: list[str],
        weights: dict[str, float] | None = None,
        model_assignments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        project_id = (project_id or "").strip()
        if not project_id:
            raise ValueError("project_id must not be empty")
        if quorum < 1:
            raise ValueError("quorum must be >= 1")
        clean_roles = [str(role) for role in roles if str(role).strip()]
        if not clean_roles:
            raise ValueError("roles must not be empty")
        assignments = dict(model_assignments or {})
        for role, model_id in assignments.items():
            if role not in clean_roles:
                raise ValueError(f"model assignment role not declared: {role}")
            self._require_model(model_id)
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO model_control_council_configs
                    (project_id, quorum, roles_json, weights_json,
                     model_assignments_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    quorum = excluded.quorum,
                    roles_json = excluded.roles_json,
                    weights_json = excluded.weights_json,
                    model_assignments_json = excluded.model_assignments_json,
                    updated_at = excluded.updated_at
            """, (
                project_id,
                int(quorum),
                self._json_dumps(clean_roles),
                self._json_dumps(weights or {}),
                self._json_dumps(assignments),
                now,
            ))
            self._conn.commit()
        result = self.get_council_config(project_id) or {}
        self._emit("model_control.council.configured", result)
        return result

    def get_council_config(self, project_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM model_control_council_configs WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return self._council_row(row) if row else None

    def list_council_configs(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM model_control_council_configs ORDER BY project_id"
        ).fetchall()
        return [self._council_row(row) for row in rows]

    def snapshot(self) -> dict[str, Any]:
        models = self.model_registry.list_models(is_active=True)
        return {
            "providers": self.list_providers(),
            "models": models,
            "model_stats": self.model_registry.get_model_stats(),
            "routes": self.list_routes(),
            "budgets": self.budget_manager.list_budgets(),
            "council_configs": self.list_council_configs(),
            "control_checks": {
                "all_routes_reference_registered_models": all(
                    self.model_registry.get_model(route["model_id"]) is not None
                    for route in self.list_routes()
                ),
                "budget_enforcer_available": True,
                "model_count": len(models),
            },
        }


_control_plane: ModelControlPlane | None = None


def get_model_control_plane(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ModelControlPlane:
    global _control_plane
    if _control_plane is None:
        _control_plane = ModelControlPlane(db_path=db_path, event_bus=event_bus)
    elif db_path is not None and str(db_path) != _control_plane._db_path:
        _control_plane = ModelControlPlane(db_path=db_path, event_bus=event_bus)
    return _control_plane


def reset_model_control_plane(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ModelControlPlane | None:
    global _control_plane
    _control_plane = None
    if db_path is not None or event_bus is not None:
        _control_plane = ModelControlPlane(db_path=db_path, event_bus=event_bus)
    return _control_plane
