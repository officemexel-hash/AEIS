"""
SYLION Cognitive -- Model Registry

Tracks available AI models and their capabilities, including performance snapshots.

Tables:
  registered_models, model_capabilities, model_performance_snapshots

Wave A3 (RB-004 + RB-012): adds project-scoped council semantics so the
registry and project_mode_store share ONE truth plane for council membership
and decision hierarchy. New API:
  - get_active_members(project_id=None) -> list[CouncilMember]
  - is_enabled(project_id) -> bool
  - get_decision_hierarchy(project_id) -> list[str]

Singleton: get_model_registry() / reset_model_registry()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.cognitive.model_registry")


# ---------------------------------------------------------------------------
# CouncilMember (project-scoped or global)
# ---------------------------------------------------------------------------

@dataclass
class CouncilMember:
    """One council member -- project-scoped if project_id is set, else global."""
    member_id: str
    project_id: str | None
    member_role: str = ""
    provider: str = ""
    model_id: str = ""
    voting_weight: float = 1.0
    active: bool = True
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Default decision hierarchy when council is enabled but project has none configured.
DEFAULT_DECISION_HIERARCHY: list[str] = ["operator", "planner_council", "engineer_council"]
# Decision hierarchy when council is disabled — operator-only fallback.
DISABLED_DECISION_HIERARCHY: list[str] = ["operator_only"]
VALID_PROFICIENCIES: tuple[str, ...] = ("low", "medium", "high", "expert")
PROFICIENCY_ORDER: dict[str, int] = {name: idx for idx, name in enumerate(VALID_PROFICIENCIES)}


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """Tracks available AI models and their capabilities.

    Thread-safe. SQLite-backed. Emits events on model registration,
    capability additions, and performance recordings.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS registered_models (
                model_id      TEXT PRIMARY KEY,
                provider      TEXT NOT NULL DEFAULT '',
                display_name  TEXT NOT NULL DEFAULT '',
                config_json   TEXT NOT NULL DEFAULT '{}',
                is_active     INTEGER NOT NULL DEFAULT 1,
                registered_at REAL NOT NULL,
                updated_at    REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_capabilities (
                capability_id  TEXT PRIMARY KEY,
                model_id       TEXT NOT NULL,
                capability     TEXT NOT NULL DEFAULT '',
                metadata_json  TEXT NOT NULL DEFAULT '{}',
                created_at     REAL NOT NULL,
                FOREIGN KEY (model_id) REFERENCES registered_models(model_id)
            );
            CREATE TABLE IF NOT EXISTS model_performance_snapshots (
                snapshot_id  TEXT PRIMARY KEY,
                model_id     TEXT NOT NULL,
                metrics_json TEXT NOT NULL DEFAULT '{}',
                recorded_at  REAL NOT NULL,
                FOREIGN KEY (model_id) REFERENCES registered_models(model_id)
            );
            CREATE INDEX IF NOT EXISTS idx_rm_provider ON registered_models(provider);
            CREATE INDEX IF NOT EXISTS idx_rm_active ON registered_models(is_active);
            CREATE INDEX IF NOT EXISTS idx_mc_model ON model_capabilities(model_id);
            CREATE INDEX IF NOT EXISTS idx_mc_cap ON model_capabilities(capability);
            CREATE INDEX IF NOT EXISTS idx_mps_model ON model_performance_snapshots(model_id);
            CREATE INDEX IF NOT EXISTS idx_mps_recorded ON model_performance_snapshots(recorded_at);
        """)
        self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.model_registry",
            ))

    @staticmethod
    def _parse_json(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            parsed = json.loads(str(raw))
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _hydrate_model(self, row: sqlite3.Row | dict[str, Any], *, include_details: bool = True) -> dict[str, Any]:
        model = dict(row)
        config = self._parse_json(model.get("config_json"))
        model["model_family"] = config.get("model_family")
        model["context_window"] = config.get("context_window")
        model["cost_per_1k_in"] = float(config.get("cost_per_1k_in") or 0.0)
        model["cost_per_1k_out"] = float(config.get("cost_per_1k_out") or 0.0)
        if not include_details:
            return model
        model["capabilities"] = self._capabilities_for_model(model["model_id"])
        latest = self.get_performance(model["model_id"], limit=1)
        model["latest_health"] = latest[0] if latest else None
        return model

    def _capabilities_for_model(self, model_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM model_capabilities WHERE model_id = ? ORDER BY created_at ASC",
            (model_id,),
        ).fetchall()
        capabilities: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            meta = self._parse_json(item.get("metadata_json"))
            item["task_type"] = item.get("capability", "")
            item["proficiency"] = meta.get("proficiency", "medium")
            item["max_tokens"] = meta.get("max_tokens")
            item["metadata"] = meta
            capabilities.append(item)
        return capabilities

    # ------------------------------------------------------------------
    # Model CRUD
    # ------------------------------------------------------------------

    def register_model(self, model_id: str, provider: str, display_name: str,
                       config_json: str = "{}", model_family: str | None = None,
                       context_window: int | None = None,
                       cost_per_1k_in: float = 0.0,
                       cost_per_1k_out: float = 0.0,
                       **extra: Any) -> dict:
        """Register a new model. Returns model dict."""
        if not model_id or not model_id.strip():
            raise ValueError("model_id must not be empty")
        try:
            cfg = json.loads(config_json) if isinstance(config_json, str) else dict(config_json or {})
            if not isinstance(cfg, dict):
                raise ValueError("config_json must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid config_json: {exc}") from exc
        cfg.update(extra)
        cfg["model_family"] = model_family
        cfg["context_window"] = context_window
        cfg["cost_per_1k_in"] = float(cost_per_1k_in or 0.0)
        cfg["cost_per_1k_out"] = float(cost_per_1k_out or 0.0)
        config_json = json.dumps(cfg, sort_keys=True)

        now = time.time()

        with self._lock:
            existing = self._conn.execute(
                "SELECT model_id FROM registered_models WHERE model_id = ?",
                (model_id,),
            ).fetchone()
            if existing:
                # Update existing model
                self._conn.execute(
                    "UPDATE registered_models "
                    "SET provider = ?, display_name = ?, config_json = ?, is_active = 1, updated_at = ? "
                    "WHERE model_id = ?",
                    (provider, display_name, config_json, now, model_id),
                )
                self._conn.commit()
            else:
                self._conn.execute(
                    "INSERT INTO registered_models "
                    "(model_id, provider, display_name, config_json, is_active, registered_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 1, ?, ?)",
                    (model_id, provider, display_name, config_json, now, now),
                )
                self._conn.commit()

        result = self._hydrate_model({
            "model_id": model_id, "provider": provider,
            "display_name": display_name, "config_json": config_json,
            "is_active": 1, "registered_at": now, "updated_at": now,
        }, include_details=False)
        self._emit("model.registered", {
            "model_id": model_id, "provider": provider,
        })
        log.info("register_model %s [%s/%s]", model_id, provider, display_name)
        return result

    def update_model(self, model_id: str, **fields) -> dict | None:
        """Update mutable fields on a model. Returns updated dict or None."""
        allowed = {"provider", "display_name", "config_json", "model_family", "context_window", "cost_per_1k_in", "cost_per_1k_out"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_model(model_id)

        config_updates = {k: updates.pop(k) for k in list(updates) if k not in {"provider", "display_name", "config_json"}}
        if "config_json" in updates or config_updates:
            try:
                base = updates.get("config_json")
                if base is None:
                    current = self.get_model(model_id)
                    base = current.get("config_json") if current else "{}"
                cfg = json.loads(base) if isinstance(base, str) else dict(base or {})
                if not isinstance(cfg, dict):
                    raise ValueError("config_json must be a JSON object")
                cfg.update(config_updates)
                updates["config_json"] = json.dumps(cfg, sort_keys=True)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid config_json: {exc}") from exc

        now = time.time()
        updates["updated_at"] = now

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM registered_models WHERE model_id = ? AND is_active = 1",
                (model_id,),
            ).fetchone()
            if not row:
                return None

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [model_id]
            self._conn.execute(
                f"UPDATE registered_models SET {set_clause} WHERE model_id = ?",
                values,
            )
            self._conn.commit()

        result = dict(row)
        result.update(updates)
        log.info("update_model %s", model_id[:12])
        return self._hydrate_model(result, include_details=False)

    def deregister_model(self, model_id: str) -> bool:
        """Soft-delete a model (sets is_active = 0). Returns True if found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT model_id FROM registered_models WHERE model_id = ? AND is_active = 1",
                (model_id,),
            ).fetchone()
            if not row:
                return False

            now = time.time()
            self._conn.execute(
                "UPDATE registered_models SET is_active = 0, updated_at = ? WHERE model_id = ?",
                (now, model_id),
            )
            self._conn.commit()

        log.info("deregister_model %s", model_id[:12])
        self._emit("model.deregistered", {"model_id": model_id})
        return True

    def get_model(self, model_id: str) -> dict | None:
        """Retrieve a single active model by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM registered_models WHERE model_id = ? AND is_active = 1",
                (model_id,),
            ).fetchone()
            return self._hydrate_model(row) if row else None

    def list_models(self, provider: str | None = None,
                    capability: str | None = None,
                    family: str | None = None,
                    is_active: bool | None = True) -> list[dict]:
        """List active models with optional filters."""
        with self._lock:
            active_clause = ""
            params: list[Any] = []
            if is_active is not None:
                active_clause = " AND rm.is_active = ?"
                params.append(1 if is_active else 0)
            if capability is not None:
                rows = self._conn.execute(
                    "SELECT DISTINCT rm.* FROM registered_models rm "
                    "JOIN model_capabilities mc ON rm.model_id = mc.model_id "
                    f"WHERE mc.capability = ?{active_clause} "
                    "ORDER BY rm.display_name ASC",
                    [capability, *params],
                ).fetchall()
            else:
                clauses = ["1=1"]
                params = []
                if is_active is not None:
                    clauses.append("is_active = ?")
                    params.append(1 if is_active else 0)
                if provider is not None:
                    clauses.append("provider = ?")
                    params.append(provider)
                rows = self._conn.execute(
                    "SELECT * FROM registered_models WHERE " + " AND ".join(clauses) + " ORDER BY display_name ASC",
                    params,
                ).fetchall()
            models = [self._hydrate_model(r, include_details=False) for r in rows]
        if family is not None:
            models = [m for m in models if m.get("model_family") == family]
        return models

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def add_capability(self, model_id: str, capability: str,
                       proficiency: str = "medium",
                       max_tokens: int | None = None,
                       metadata_json: str | dict[str, Any] | None = None) -> dict:
        """Add a capability to a model. Returns capability dict."""
        if proficiency not in VALID_PROFICIENCIES:
            parsed = self._parse_json(proficiency)
            if parsed:
                metadata_json = parsed if metadata_json is None else metadata_json
                proficiency = str(parsed.get("proficiency") or "medium")
            if proficiency not in VALID_PROFICIENCIES:
                raise ValueError(f"Invalid proficiency '{proficiency}'")
        try:
            meta = self._parse_json(metadata_json)
            if not isinstance(meta, dict):
                raise ValueError("metadata_json must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid metadata_json: {exc}") from exc
        meta["proficiency"] = proficiency
        if max_tokens is not None:
            meta["max_tokens"] = max_tokens
        metadata_json_str = json.dumps(meta, sort_keys=True)

        capability_id = self._uid()
        now = time.time()

        with self._lock:
            model = self._conn.execute(
                "SELECT model_id FROM registered_models WHERE model_id = ? AND is_active = 1",
                (model_id,),
            ).fetchone()
            if not model:
                raise ValueError(f"Model '{model_id}' not found or inactive")

            self._conn.execute(
                "INSERT INTO model_capabilities "
                "(capability_id, model_id, capability, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (capability_id, model_id, capability, metadata_json_str, now),
            )
            self._conn.commit()

        result = {
            "capability_id": capability_id, "model_id": model_id,
            "capability": capability, "task_type": capability,
            "proficiency": proficiency, "max_tokens": max_tokens,
            "metadata_json": metadata_json_str,
            "created_at": now,
        }
        self._emit("model.capability.added", {
            "capability_id": capability_id, "model_id": model_id,
            "capability": capability, "task_type": capability,
        })
        log.info("add_capability %s [%s] to %s", capability_id[:12], capability, model_id)
        return result

    def remove_capability(self, capability_id: str) -> bool:
        """Remove a capability by ID. Returns True if found and removed."""
        with self._lock:
            row = self._conn.execute(
                "SELECT capability_id FROM model_capabilities WHERE capability_id = ?",
                (capability_id,),
            ).fetchone()
            if not row:
                return False
            self._conn.execute(
                "DELETE FROM model_capabilities WHERE capability_id = ?",
                (capability_id,),
            )
            self._conn.commit()
        log.info("remove_capability %s", capability_id[:12])
        return True

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------

    def record_performance(self, model_id: str, metrics_json: str = "{}") -> dict:
        """Record a performance snapshot for a model. Returns snapshot dict."""
        try:
            metrics = json.loads(metrics_json)
            if not isinstance(metrics, dict):
                raise ValueError("metrics_json must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid metrics_json: {exc}") from exc

        snapshot_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute(
                "INSERT INTO model_performance_snapshots "
                "(snapshot_id, model_id, metrics_json, recorded_at) "
                "VALUES (?, ?, ?, ?)",
                (snapshot_id, model_id, metrics_json, now),
            )
            self._conn.commit()

        result = {
            "snapshot_id": snapshot_id, "model_id": model_id,
            "metrics_json": metrics_json, "recorded_at": now,
            **metrics,
        }
        self._emit("model.health.recorded", {
            "snapshot_id": snapshot_id, "model_id": model_id, **metrics,
        })
        log.info("record_performance %s for %s", snapshot_id[:12], model_id[:12])
        return result

    def record_health(
        self,
        model_id: str,
        latency_ms: float,
        success: bool,
        tokens_used: int = 0,
        error: str | None = None,
    ) -> dict:
        """Record the latest health/performance snapshot."""
        result = self.record_performance(
            model_id,
            json.dumps({
                "latency_ms": latency_ms,
                "success": bool(success),
                "tokens_used": int(tokens_used or 0),
                "error": error,
            }, sort_keys=True),
        )
        result["health_id"] = result["snapshot_id"]
        return result

    def get_performance(self, model_id: str, limit: int = 100) -> list[dict]:
        """Get performance snapshots for a model."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM model_performance_snapshots "
                "WHERE model_id = ? ORDER BY recorded_at DESC LIMIT ?",
                (model_id, limit),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item.update(self._parse_json(item.get("metrics_json")))
            result.append(item)
        return result

    def get_model_health(self, model_id: str, limit: int = 100) -> list[dict]:
        records = self.get_performance(model_id, limit=limit)
        for record in records:
            record["health_id"] = record.get("snapshot_id")
        return records

    def get_model_for_task(self, task_type: str, min_proficiency: str = "low") -> list[dict]:
        """Return active models capable of a task, best proficiency first."""
        models = self.list_models(capability=task_type)
        min_rank = PROFICIENCY_ORDER.get(min_proficiency, 0)
        filtered: list[dict] = []
        for model in models:
            caps = [cap for cap in self._capabilities_for_model(model["model_id"]) if cap.get("task_type") == task_type]
            best_cap = max(caps, key=lambda cap: PROFICIENCY_ORDER.get(str(cap.get("proficiency")), 0), default=None)
            best = PROFICIENCY_ORDER.get(str(best_cap.get("proficiency")) if best_cap else "", 0)
            model["task_proficiency"] = best
            model["matching_capability"] = best_cap
            if best >= min_rank:
                filtered.append(model)
        return sorted(filtered, key=lambda item: item.get("task_proficiency", 0), reverse=True)

    def compare_models(self, model_ids: list[str]) -> dict:
        """Return simple comparison stats for selected active models."""
        models = [self.get_model(model_id) for model_id in model_ids]
        models = [model for model in models if model is not None]
        if not models:
            return {"models": [], "comparison": {}}
        comparison = {
            "largest_context": max(models, key=lambda m: m.get("context_window") or 0)["model_id"],
            "cheapest_input": min(models, key=lambda m: m.get("cost_per_1k_in") or 0.0)["model_id"],
            "most_capabilities": max(models, key=lambda m: len(m.get("capabilities") or []))["model_id"],
            "fastest": min(models, key=lambda m: self._model_stats(m["model_id"])["avg_latency_ms"] or float("inf"))["model_id"],
            "most_reliable": max(models, key=lambda m: self._model_stats(m["model_id"])["success_rate"])["model_id"],
        }
        return {"models": models, "comparison": comparison}

    def search_models(self, query: str) -> list[dict]:
        q = (query or "").lower()
        return [
            model for model in self.list_models()
            if q in str(model.get("model_id", "")).lower()
            or q in str(model.get("display_name", "")).lower()
            or q in str(model.get("provider", "")).lower()
            or q in str(model.get("model_family", "")).lower()
        ]

    # ------------------------------------------------------------------
    # Council semantics (Wave A3 -- RB-004 + RB-012)
    # ------------------------------------------------------------------

    def get_active_members(
        self, project_id: str | None = None,
    ) -> list[CouncilMember]:
        """Return active council members.

        - If project_id is None: returns all globally active models wrapped as
          CouncilMember (treats every active registered_model as a candidate).
        - If project_id is provided: returns members from project_mode_store's
          per-project council_members, filtered to active=True.
          Honors council_plan.enabled: when disabled, returns [].

        This is the SINGLE source of truth callers should use; never read
        council_members straight off the project dict.
        """
        if project_id is None:
            return [
                CouncilMember(
                    member_id=m["model_id"],
                    project_id=None,
                    member_role="model",
                    provider=m.get("provider", ""),
                    model_id=m["model_id"],
                    voting_weight=1.0,
                    active=bool(m.get("is_active", 1)),
                )
                for m in self.list_models()
            ]

        # Project-scoped path: lazy import to avoid circular deps.
        try:
            from sylion.project_mode.store import get_project_mode_store
        except Exception as exc:
            log.warning(
                "project_mode_store unavailable, returning [] for project %s: %s",
                project_id, exc,
            )
            return []

        if not self.is_enabled(project_id):
            return []

        store = get_project_mode_store()
        try:
            council = store.get_project_council(project_id)
        except KeyError:
            return []
        members_raw = council.get("members") or []
        return [
            CouncilMember(
                member_id=m.get("council_member_id") or m.get("member_id") or "",
                project_id=project_id,
                member_role=m.get("member_role", ""),
                provider=m.get("provider", ""),
                model_id=m.get("model_id", ""),
                voting_weight=float(m.get("voting_weight", 1.0) or 1.0),
                active=bool(m.get("active", True)),
                config=m.get("config") or {},
            )
            for m in members_raw
            if bool(m.get("active", True))
        ]

    def is_enabled(self, project_id: str) -> bool:
        """Whether the council plane is enabled for a project.

        Reads `council_plan.enabled` (default True if absent for legacy compat).
        Returns True if the project does not exist (graceful default).
        """
        try:
            from sylion.project_mode.store import get_project_mode_store
        except Exception:
            return True
        store = get_project_mode_store()
        project = store.get_project(project_id)
        if project is None:
            return True
        plan = project.get("council_plan") or {}
        return bool(plan.get("enabled", True))

    def get_decision_hierarchy(self, project_id: str) -> list[str]:
        """Return the ordered decision hierarchy for a project.

        - council disabled -> ["operator_only"] (no planner_council).
        - council enabled, project has governance_policy.decision_layers -> use those.
        - council enabled, no layers configured -> DEFAULT_DECISION_HIERARCHY.
        """
        if not self.is_enabled(project_id):
            return list(DISABLED_DECISION_HIERARCHY)
        try:
            from sylion.project_mode.store import get_project_mode_store
        except Exception:
            return list(DEFAULT_DECISION_HIERARCHY)
        store = get_project_mode_store()
        project = store.get_project(project_id)
        if project is None:
            return list(DEFAULT_DECISION_HIERARCHY)
        layers = (project.get("governance_policy") or {}).get("decision_layers") or []
        if not layers:
            return list(DEFAULT_DECISION_HIERARCHY)
        return [str(name) for name in layers]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def _model_stats(self, model_id: str) -> dict[str, Any]:
        records = self.get_model_health(model_id, limit=10000)
        total = len(records)
        successes = sum(1 for item in records if bool(item.get("success")))
        failures = total - successes
        total_latency = sum(float(item.get("latency_ms") or 0.0) for item in records)
        total_tokens = sum(int(item.get("tokens_used") or 0) for item in records)
        model = self.get_model(model_id) or {
            "model_id": model_id,
            "cost_per_1k_in": 0.0,
            "cost_per_1k_out": 0.0,
        }
        avg_cost_per_1k = (float(model.get("cost_per_1k_in") or 0.0) + float(model.get("cost_per_1k_out") or 0.0)) / 2
        return {
            "model_id": model_id,
            "total_calls": total,
            "success_count": successes,
            "failure_count": failures,
            "success_rate": round((successes / total) * 100, 2) if total else 0.0,
            "avg_latency_ms": (total_latency / total) if total else 0.0,
            "total_tokens_used": total_tokens,
            "estimated_cost": (total_tokens * avg_cost_per_1k) / 1000 if total_tokens else 0.0,
        }

    def get_model_stats(self, model_id: str | None = None) -> dict:
        """Aggregate registry statistics or per-model health statistics."""
        if model_id is not None:
            return self._model_stats(model_id)

        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM registered_models",
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            active_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM registered_models WHERE is_active = 1",
            ).fetchone()
            active = active_row["cnt"] if active_row else 0

            prov_rows = self._conn.execute(
                "SELECT provider, COUNT(*) as cnt FROM registered_models "
                "GROUP BY provider",
            ).fetchall()
            by_provider = {r["provider"]: r["cnt"] for r in prov_rows}
            rows = self._conn.execute("SELECT * FROM registered_models").fetchall()
            by_family: dict[str, int] = {}
            for row in rows:
                family = self._hydrate_model(row, include_details=False).get("model_family")
                if family:
                    by_family[str(family)] = by_family.get(str(family), 0) + 1

            cap_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM model_capabilities",
            ).fetchone()["cnt"]

            perf_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM model_performance_snapshots",
            ).fetchone()["cnt"]

        return {
            "total_models": total,
            "active_models": active,
            "inactive_models": total - active,
            "by_provider": by_provider,
            "by_family": by_family,
            "total_capabilities": cap_count,
            "total_performance_snapshots": perf_count,
            "overall_health": self._overall_health(),
        }

    def _overall_health(self) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        with self._lock:
            rows = self._conn.execute("SELECT * FROM model_performance_snapshots").fetchall()
        for row in rows:
            item = dict(row)
            item.update(self._parse_json(item.get("metrics_json")))
            records.append(item)
        total = len(records)
        successes = sum(1 for item in records if bool(item.get("success")))
        total_latency = sum(float(item.get("latency_ms") or 0.0) for item in records)
        return {
            "total_calls": total,
            "success_rate": round((successes / total) * 100, 2) if total else 0.0,
            "avg_latency_ms": (total_latency / total) if total else 0.0,
        }

    def get_registry_stats(self) -> dict:
        return self.get_model_stats()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_registry: ModelRegistry | None = None


def _audit_redirect(db_path: str | Path | None) -> str | Path | None:
    if db_path is None or str(db_path) == ":memory:":
        return db_path
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path
    if not is_audit_mode():
        return db_path
    return resolve_db_path(Path(db_path))


def get_model_registry(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry(_audit_redirect(db_path), event_bus)
    return _registry


def reset_model_registry(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> ModelRegistry:
    global _registry
    _registry = ModelRegistry(_audit_redirect(db_path), event_bus)
    return _registry
