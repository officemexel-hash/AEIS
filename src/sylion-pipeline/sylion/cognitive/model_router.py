"""
SYLION Cognitive -- Model Router (M2)

Routes AI/LLM requests to optimal models based on task type, complexity,
and budget constraints. Tracks usage statistics and cost reporting.

SQLite-backed with WAL mode, thread-safe via threading.Lock, singleton
via get_model_router(). Emits events via EventBus integration.

Tables:
  - sylion_models: registered AI models with capabilities and pricing
  - sylion_model_usage: per-request usage records with latency and cost
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.cognitive.model_router")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ModelInfo:
    """A registered AI model."""
    model_id: str = ""
    provider: str = ""
    model_name: str = ""
    capabilities: str = "[]"  # JSON array stored in SQLite
    cost_per_1k_tokens: float = 0.0
    registered_at: float = 0.0

    def __post_init__(self):
        if not self.registered_at:
            self.registered_at = time.time()


@dataclass
class UsageRecord:
    """A usage record for an AI model invocation."""
    usage_id: str = ""
    model_id: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    success: int = 1
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.usage_id:
            self.usage_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Complexity levels
# ---------------------------------------------------------------------------

COMPLEXITY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

CAPABILITY_COMPLEXITY_MAP = {
    "simple_chat": "low",
    "translation": "low",
    "summarization": "medium",
    "code_generation": "medium",
    "analysis": "medium",
    "reasoning": "high",
    "vision": "high",
    "multi_step": "high",
    "planning": "critical",
    "autonomous": "critical",
}


# ---------------------------------------------------------------------------
# Model Router
# ---------------------------------------------------------------------------

class ModelRouter:
    """Route AI requests to optimal models by task, complexity, and budget.

    Thread-safe via threading.Lock. SQLite-backed with WAL mode.
    Emits events on registration, routing, and usage recording.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._event_bus = event_bus
        self._ensure_tables()

    def _ensure_tables(self):
        """Create sylion_models and sylion_model_usage tables."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_models (
                model_id          TEXT PRIMARY KEY,
                provider          TEXT NOT NULL DEFAULT '',
                model_name        TEXT NOT NULL DEFAULT '',
                capabilities      TEXT NOT NULL DEFAULT '[]',
                cost_per_1k_tokens REAL NOT NULL DEFAULT 0.0,
                registered_at     REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_model_usage (
                usage_id    TEXT PRIMARY KEY,
                model_id    TEXT NOT NULL DEFAULT '',
                tokens_in   INTEGER NOT NULL DEFAULT 0,
                tokens_out  INTEGER NOT NULL DEFAULT 0,
                latency_ms  REAL NOT NULL DEFAULT 0.0,
                success     INTEGER NOT NULL DEFAULT 1,
                timestamp   REAL NOT NULL,
                FOREIGN KEY (model_id) REFERENCES sylion_models(model_id)
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_model ON sylion_model_usage(model_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_ts ON sylion_model_usage(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_success ON sylion_model_usage(success)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_models_provider ON sylion_models(provider)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Model registration
    # ------------------------------------------------------------------

    def register_model(self, model_id: str, provider: str, model_name: str,
                       capabilities: list[str] | None = None,
                       cost_per_1k_tokens: float = 0.0) -> dict:
        """Register or update an AI model.

        Args:
            model_id: Unique model identifier (e.g. "gpt-4o", "claude-3.5").
            provider: Provider name (e.g. "openai", "anthropic").
            model_name: Human-readable model name.
            capabilities: List of capability strings (e.g. ["vision", "code"]).
            cost_per_1k_tokens: Cost per 1000 tokens (combined in+out estimate).

        Returns:
            Dict with model registration summary.
        """
        if capabilities is None:
            capabilities = []

        caps_json = json.dumps(capabilities)
        registered_at = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO sylion_models
                (model_id, provider, model_name, capabilities,
                 cost_per_1k_tokens, registered_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (model_id, provider, model_name, caps_json,
                  cost_per_1k_tokens, registered_at))
            self._conn.commit()

        self._emit("model_router.model.registered", {
            "model_id": model_id,
            "provider": provider,
            "model_name": model_name,
        })
        log.info("registered model %s (%s/%s, cost=%.4f/1k)",
                 model_id, provider, model_name, cost_per_1k_tokens)
        return {
            "model_id": model_id,
            "provider": provider,
            "model_name": model_name,
            "capabilities": capabilities,
            "cost_per_1k_tokens": cost_per_1k_tokens,
        }

    def get_model(self, model_id: str) -> dict | None:
        """Get model details by model_id.

        Returns:
            Dict with model details, or None if not found.
        """
        row = self._conn.execute(
            "SELECT * FROM sylion_models WHERE model_id = ?",
            (model_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["capabilities"] = json.loads(result.get("capabilities", "[]"))
        return result

    def list_models(self, provider: str | None = None,
                    capability: str | None = None) -> list[dict]:
        """List registered models, optionally filtered.

        Args:
            provider: Filter by provider name.
            capability: Filter by capability (model must include this capability).

        Returns:
            List of model dicts, ordered by cost ascending.
        """
        query = "SELECT * FROM sylion_models WHERE 1=1"
        params: list[Any] = []

        if provider:
            query += " AND provider = ?"
            params.append(provider)

        if capability:
            # JSON-compatible containment check using LIKE
            query += " AND capabilities LIKE ?"
            params.append(f'%"{capability}"%')

        query += " ORDER BY cost_per_1k_tokens ASC"

        rows = self._conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["capabilities"] = json.loads(d.get("capabilities", "[]"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route_request(self, task_type: str, complexity: str = "medium",
                      budget: float | None = None) -> dict | None:
        """Select the best model for a given request.

        Routing logic:
          1. Filter models by capability matching task_type.
          2. Filter by budget (cost_per_1k_tokens <= budget).
          3. Select cheapest model that meets requirements.
          4. If no capability match, fall back to cheapest within budget.

        Args:
            task_type: Type of task (e.g. "code_generation", "translation").
            complexity: Complexity level ("low", "medium", "high", "critical").
            budget: Maximum cost per 1k tokens. None = no budget limit.

        Returns:
            Dict with selected model details, or None if no model matches.
        """
        models = self.list_models()

        if not models:
            log.warning("no models registered for routing")
            return None

        complexity_rank = COMPLEXITY_ORDER.get(complexity, 1)

        # Step 1: Try capability-based match
        capable_models = []
        for m in models:
            caps = m.get("capabilities", [])
            if task_type in caps:
                capable_models.append(m)

        # Step 2: Apply budget filter
        candidates = capable_models if capable_models else models

        if budget is not None:
            candidates = [m for m in candidates
                          if m["cost_per_1k_tokens"] <= budget]

        if not candidates:
            log.warning(
                "no model matches task_type=%s complexity=%s budget=%s",
                task_type, complexity, budget,
            )
            return None

        # Step 3: For higher complexity, prefer more capable (expensive) models
        # For low/medium, pick cheapest. For high/critical, pick best within budget.
        if complexity_rank >= 2 and capable_models:
            # Sort descending by cost for high complexity (prefer stronger model)
            candidates.sort(key=lambda m: m["cost_per_1k_tokens"], reverse=True)
        else:
            # Sort ascending by cost (cheapest first) -- already sorted
            pass

        selected = candidates[0]

        self._emit("model_router.request.routed", {
            "task_type": task_type,
            "complexity": complexity,
            "budget": budget,
            "selected_model": selected["model_id"],
        })
        log.info("routed %s (complexity=%s) -> %s",
                 task_type, complexity, selected["model_id"])
        return selected

    # ------------------------------------------------------------------
    # Usage tracking
    # ------------------------------------------------------------------

    def record_usage(self, model_id: str, tokens_in: int, tokens_out: int,
                     latency_ms: float, success: bool = True) -> dict:
        """Record usage statistics for a model invocation.

        Args:
            model_id: The model that was used.
            tokens_in: Number of input tokens.
            tokens_out: Number of output tokens.
            latency_ms: Request latency in milliseconds.
            success: Whether the request was successful.

        Returns:
            Dict with usage record summary.
        """
        record = UsageRecord(
            model_id=model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            success=1 if success else 0,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO sylion_model_usage
                (usage_id, model_id, tokens_in, tokens_out,
                 latency_ms, success, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.usage_id, record.model_id,
                record.tokens_in, record.tokens_out,
                record.latency_ms, record.success, record.timestamp,
            ))
            self._conn.commit()

        self._emit("model_router.usage.recorded", {
            "usage_id": record.usage_id,
            "model_id": model_id,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "success": success,
        })
        log.info("recorded usage for %s: %d/%d tokens, %.1fms, success=%s",
                 model_id, tokens_in, tokens_out, latency_ms, success)
        return {
            "usage_id": record.usage_id,
            "model_id": model_id,
            "tokens_total": tokens_in + tokens_out,
            "latency_ms": latency_ms,
            "success": success,
        }

    def get_usage_stats(self, model_id: str | None = None,
                        days: int = 30) -> dict:
        """Get usage statistics.

        Args:
            model_id: Filter by model. None = aggregate all models.
            days: Lookback period in days.

        Returns:
            Dict with usage statistics (counts, costs, latency averages).
        """
        since = time.time() - (days * 86400)

        query = """
            SELECT
                COUNT(*) as total_requests,
                SUM(tokens_in) as total_tokens_in,
                SUM(tokens_out) as total_tokens_out,
                AVG(latency_ms) as avg_latency_ms,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failure_count
            FROM sylion_model_usage
            WHERE timestamp >= ?
        """
        params: list[Any] = [since]

        if model_id:
            query += " AND model_id = ?"
            params.append(model_id)

        row = self._conn.execute(query, params).fetchone()

        total_requests = row["total_requests"] or 0
        total_tokens_in = row["total_tokens_in"] or 0
        total_tokens_out = row["total_tokens_out"] or 0
        avg_latency = row["avg_latency_ms"] or 0.0
        success_count = row["success_count"] or 0
        failure_count = row["failure_count"] or 0

        # Calculate cost
        total_tokens = total_tokens_in + total_tokens_out
        cost = 0.0
        if model_id:
            model = self.get_model(model_id)
            if model:
                cost = (total_tokens / 1000.0) * model["cost_per_1k_tokens"]
        else:
            # Aggregate cost across all models
            cost_rows = self._conn.execute("""
                SELECT u.model_id, SUM(u.tokens_in + u.tokens_out) as total_tokens,
                       m.cost_per_1k_tokens
                FROM sylion_model_usage u
                JOIN sylion_models m ON u.model_id = m.model_id
                WHERE u.timestamp >= ?
                GROUP BY u.model_id
            """, (since,)).fetchall()
            for cr in cost_rows:
                cost += (cr["total_tokens"] / 1000.0) * cr["cost_per_1k_tokens"]

        success_rate = (success_count / total_requests * 100.0
                        if total_requests > 0 else 0.0)

        return {
            "total_requests": total_requests,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_tokens": total_tokens,
            "avg_latency_ms": round(avg_latency, 2),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": round(success_rate, 2),
            "estimated_cost": round(cost, 6),
            "days": days,
        }

    # ------------------------------------------------------------------
    # Cost reporting
    # ------------------------------------------------------------------

    def get_cost_report(self, days: int = 30) -> dict:
        """Generate cost breakdown by model and provider.

        Args:
            days: Lookback period in days.

        Returns:
            Dict with cost breakdown by model, by provider, and totals.
        """
        since = time.time() - (days * 86400)

        # Cost by model
        model_rows = self._conn.execute("""
            SELECT u.model_id, m.model_name, m.provider,
                   COUNT(*) as request_count,
                   SUM(u.tokens_in) as tokens_in,
                   SUM(u.tokens_out) as tokens_out,
                   SUM(u.tokens_in + u.tokens_out) as total_tokens,
                   AVG(u.latency_ms) as avg_latency_ms,
                   m.cost_per_1k_tokens
            FROM sylion_model_usage u
            JOIN sylion_models m ON u.model_id = m.model_id
            WHERE u.timestamp >= ?
            GROUP BY u.model_id
            ORDER BY total_tokens DESC
        """, (since,)).fetchall()

        by_model = []
        total_cost = 0.0
        total_requests = 0
        total_tokens = 0

        for r in model_rows:
            tokens = r["total_tokens"] or 0
            model_cost = (tokens / 1000.0) * r["cost_per_1k_tokens"]
            total_cost += model_cost
            total_requests += r["request_count"] or 0
            total_tokens += tokens
            by_model.append({
                "model_id": r["model_id"],
                "model_name": r["model_name"],
                "provider": r["provider"],
                "request_count": r["request_count"],
                "tokens_in": r["tokens_in"] or 0,
                "tokens_out": r["tokens_out"] or 0,
                "total_tokens": tokens,
                "avg_latency_ms": round(r["avg_latency_ms"] or 0.0, 2),
                "cost": round(model_cost, 6),
            })

        # Aggregate by provider
        by_provider: dict[str, dict] = {}
        for entry in by_model:
            prov = entry["provider"]
            if prov not in by_provider:
                by_provider[prov] = {
                    "provider": prov,
                    "request_count": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                }
            by_provider[prov]["request_count"] += entry["request_count"]
            by_provider[prov]["total_tokens"] += entry["total_tokens"]
            by_provider[prov]["cost"] += entry["cost"]

        # Round provider costs
        for prov in by_provider.values():
            prov["cost"] = round(prov["cost"], 6)

        return {
            "by_model": by_model,
            "by_provider": list(by_provider.values()),
            "total_cost": round(total_cost, 6),
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "days": days,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        """Emit event via EventBus if available."""
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="cognitive.model_router",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_router: ModelRouter | None = None
_singleton_lock = threading.Lock()


def get_model_router(db_path: str | Path | None = None,
                     event_bus: EventBus | None = None) -> ModelRouter:
    """Get or create the global ModelRouter singleton.

    Args:
        db_path: SQLite database path. Only used on first call.
        event_bus: EventBus instance. Only used on first call.

    Returns:
        The singleton ModelRouter instance.
    """
    global _router
    if _router is None:
        with _singleton_lock:
            if _router is None:
                _router = ModelRouter(db_path=db_path, event_bus=event_bus)
    return _router


def reset_model_router():
    """Reset the global singleton. Useful for testing."""
    global _router
    with _singleton_lock:
        _router = None
