"""
SYLION Cognitive -- LLM Adapter

Unified LLM API adapter supporting Anthropic, OpenAI, Ollama, and an
explicit deterministic test provider. Records call metadata including token counts, cost, and latency
for tracking and audit.

Thread-safe. SQLite-backed. Emits events on LLM calls.

Configuration via environment variables:
  SYLION_LLM_PROVIDER  — "anthropic" | "openai" | "ollama" | "stub" (default: "stub")
  SYLION_LLM_API_KEY   — API key for anthropic/openai
  SYLION_LLM_MODEL     — model name (default: provider-specific)
  SYLION_LLM_BASE_URL  — custom base URL (Ollama default: http://localhost:11434)
  SYLION_LLM_MAX_TOKENS — max completion tokens (default: 4096)
  SYLION_LLM_COST_PER_1K — cost per 1k tokens (default: 0.0)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus
from sylion.cognitive.model_runtime_policy import (
    estimate_cost,
    preflight_model_call,
    record_model_usage,
    resolve_runtime_model,
)

log = logging.getLogger("sylion.cognitive.llm_adapter")


class LLMCallUnavailableError(RuntimeError):
    """Raised when a live LLM call is required but unavailable."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LLMCall:
    """A single LLM call record."""
    call_id: str = ""
    model_id: str = ""
    prompt_hash: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    latency_ms: int = 0
    status: str = "pending"
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.call_id:
            self.call_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# LLM Adapter
# ---------------------------------------------------------------------------

class LLMAdapter:
    """Unified LLM API adapter with live providers and gated deterministic tests.

    Thread-safe. SQLite-backed. Emits events on LLM calls.
    """

    def __init__(self, model_router: Any = None,
                 event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
        self._model_router = model_router
        self._event_bus = event_bus
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
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_calls (
                call_id            TEXT PRIMARY KEY,
                model_id           TEXT NOT NULL DEFAULT '',
                prompt_hash        TEXT NOT NULL DEFAULT '',
                prompt_tokens      INTEGER NOT NULL DEFAULT 0,
                completion_tokens  INTEGER NOT NULL DEFAULT 0,
                cost               REAL NOT NULL DEFAULT 0.0,
                latency_ms         INTEGER NOT NULL DEFAULT 0,
                status             TEXT NOT NULL DEFAULT 'pending',
                timestamp          REAL NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_model ON llm_calls(model_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_status ON llm_calls(status)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_ts ON llm_calls(timestamp)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Provider helpers
    # ------------------------------------------------------------------

    def _get_provider(self) -> str:
        """Return the configured LLM provider name."""
        return os.environ.get("SYLION_LLM_PROVIDER", "stub").lower()

    def _allow_stub(self) -> bool:
        """Allow deterministic test calls only when explicitly enabled."""
        return os.environ.get("SYLION_ALLOW_LLM_STUB") == "1"

    def _select_default_model_id(self) -> str:
        """Pick a live model from the registry for legacy callers."""
        try:
            from sylion.cognitive.model_registry import get_model_registry

            rows = get_model_registry().list_models()
        except Exception:  # noqa: BLE001
            log.exception("model registry unavailable while selecting default LLM")
            return ""

        provider_rank = {
            "ollama": 0,
            "local": 1,
            "openai": 2,
            "anthropic": 3,
            "zai": 4,
            "perplexity": 5,
            "google": 6,
        }
        candidates = [
            row for row in rows
            if str(row.get("provider") or "").lower() not in {"", "stub"}
        ]
        candidates.sort(key=lambda row: (
            provider_rank.get(str(row.get("provider") or "").lower(), 99),
            str(row.get("display_name") or row.get("model_id") or ""),
        ))
        return str(candidates[0].get("model_id") or "") if candidates else ""

    def _get_model(self, provider: str) -> str:
        """Return the model name, falling back to provider defaults."""
        env_model = os.environ.get("SYLION_LLM_MODEL")
        if env_model:
            return env_model
        defaults = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
            "ollama": "llama3",
            "stub": "stub",
        }
        return defaults.get(provider, "stub")

    def _get_max_tokens(self) -> int:
        """Return the configured max completion tokens."""
        try:
            return int(os.environ.get("SYLION_LLM_MAX_TOKENS", "4096"))
        except (ValueError, TypeError):
            return 4096

    def _get_cost_per_1k(self) -> float:
        """Return the configured cost per 1k tokens."""
        try:
            return float(os.environ.get("SYLION_LLM_COST_PER_1K", "0.0"))
        except (ValueError, TypeError):
            return 0.0

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text length."""
        return max(1, len(text) // 4)

    def _calculate_cost(self, total_tokens: int) -> float:
        """Calculate cost from token count and cost-per-1k rate."""
        return (total_tokens / 1000.0) * self._get_cost_per_1k()

    def _resolve_key(self, provider: str) -> str:
        """Resolve provider key from KeyVault first, then env."""
        env_keys = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "perplexity": "PERPLEXITY_API_KEY",
            "google": "GOOGLE_API_KEY",
            "zai": "ZAI_API_KEY",
        }
        try:
            from sylion.security.key_vault import get_key_vault

            vault = get_key_vault()
            keys = vault.list_keys(provider=provider)
            active = [k for k in keys if k.get("is_active")]
            if active:
                val = vault.get_decrypted_key(active[0]["key_id"]) or ""
                if val:
                    return val
        except Exception:
            pass

        generic = os.environ.get("SYLION_LLM_API_KEY", "")
        return os.environ.get(env_keys.get(provider, ""), "") or generic

    def _make_stub_response(self, start_time: float) -> dict:
        """Build the deterministic test response dict."""
        latency = int((time.time() - start_time) * 1000)
        return {
            "text": "stub",
            "tokens": 0,
            "cost": 0.0,
            "latency_ms": latency,
        }

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    def _call_anthropic(self, messages: list[dict], model: str,
                        max_tokens: int, api_key: str = "",
                        base_url: str | None = None,
                        cost_per_1k: float | None = None) -> dict:
        """Call Anthropic Messages API. Imports anthropic lazily."""
        import anthropic  # noqa: lazy import

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = anthropic.Anthropic(**client_kwargs)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        response = client.messages.create(**kwargs)

        text = response.content[0].text if response.content else ""
        prompt_tokens = response.usage.input_tokens if response.usage else 0
        completion_tokens = response.usage.output_tokens if response.usage else 0
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens == 0:
            total_tokens = self._estimate_tokens(text)
        cost = (total_tokens / 1000.0) * cost_per_1k if cost_per_1k is not None else self._calculate_cost(total_tokens)

        return {
            "text": text,
            "tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
        }

    def _call_openai(self, messages: list[dict], model: str,
                     max_tokens: int, api_key: str = "",
                     base_url: str | None = None,
                     cost_per_1k: float | None = None) -> dict:
        """Call OpenAI Chat Completions API. Imports openai lazily."""
        from openai import OpenAI  # noqa: lazy import

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        response = client.chat.completions.create(**kwargs)

        text = response.choices[0].message.content if response.choices else ""
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens == 0:
            total_tokens = self._estimate_tokens(text)
        cost = (total_tokens / 1000.0) * cost_per_1k if cost_per_1k is not None else self._calculate_cost(total_tokens)

        return {
            "text": text,
            "tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
        }

    def _call_ollama(self, messages: list[dict], model: str,
                     max_tokens: int, base_url: str | None = None,
                     cost_per_1k: float | None = None) -> dict:
        """Call local Ollama API using httpx. No extra package beyond httpx."""
        import httpx  # noqa: lazy import

        base_url = base_url or os.environ.get("SYLION_LLM_BASE_URL", "http://localhost:11434")
        url = f"{base_url.rstrip('/')}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens == 0:
            total_tokens = self._estimate_tokens(text)
        cost = (total_tokens / 1000.0) * cost_per_1k if cost_per_1k is not None else self._calculate_cost(total_tokens)

        return {
            "text": text,
            "tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
        }

    # ------------------------------------------------------------------
    # Core call dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, messages: list[dict], model_id: str,
                  max_tokens: int) -> tuple[dict, str, dict]:
        """Dispatch to the configured provider. Returns (result_dict, status).

        result_dict keys: text, tokens, cost.
        status: "completed" on success, "fallback" on provider error.
        """
        if not (model_id or "").strip() and self._get_provider() == "stub" and not self._allow_stub():
            model_id = self._select_default_model_id()

        runtime_model = resolve_runtime_model(model_id)
        effective_max = min(max_tokens, self._get_max_tokens())
        cfg = runtime_model.config
        try:
            cost_per_1k = float(cfg.get("cost_per_1k_tokens_usd") or cfg.get("cost_per_1k_tokens") or 0)
        except (TypeError, ValueError):
            cost_per_1k = 0.0
        cost_hint = cost_per_1k if cost_per_1k > 0 else None
        base_url = cfg.get("base_url") or os.environ.get("SYLION_LLM_BASE_URL", None)

        try:
            from sylion.cognitive.llm_runtime import (
                infer_provider_for_model,
                provider_available,
                provider_candidates,
                resolve_model,
            )

            inferred_provider = infer_provider_for_model(model_id)
            requested_provider = runtime_model.provider or inferred_provider or self._get_provider()
            candidates = provider_candidates(provider=requested_provider, model=model_id, role="domain_specialist")
        except Exception:  # noqa: BLE001
            requested_provider = runtime_model.provider or self._get_provider()
            candidates = [requested_provider]

            def provider_available(provider: str) -> bool:  # type: ignore[no-redef]
                return provider == "stub" or provider == "ollama" or bool(self._resolve_key(provider))

            def resolve_model(provider: str, requested_model: str = "") -> str:  # type: ignore[no-redef]
                return requested_model if requested_model and provider == requested_provider else self._get_model(provider)

        attempts: list[str] = []
        first_error: Exception | None = None
        for provider in candidates:
            provider = str(provider or "").lower()
            if provider == "stub":
                if self._allow_stub():
                    return {}, "stub", {"provider": provider, "provider_model": "stub", "registered": runtime_model.registered, "attempts": attempts}
                attempts.append("stub:disabled")
                continue
            if not provider_available(provider):
                attempts.append(f"{provider}:not_configured")
                continue
            model = runtime_model.provider_model if runtime_model.registered and provider == requested_provider else resolve_model(provider, model_id)
            api_key = self._resolve_key(provider)
            meta = {
                "provider": provider,
                "provider_model": model,
                "registered": runtime_model.registered,
                "requested_provider": requested_provider,
                "requested_model_id": model_id,
                "attempts": attempts,
            }
            try:
                if provider == "anthropic":
                    result = self._call_anthropic(messages, model, effective_max, api_key=api_key, base_url=base_url, cost_per_1k=cost_hint)
                elif provider == "openai":
                    result = self._call_openai(messages, model, effective_max, api_key=api_key, base_url=base_url, cost_per_1k=cost_hint)
                elif provider == "perplexity":
                    result = self._call_openai(messages, model, effective_max, api_key=api_key, base_url=base_url or "https://api.perplexity.ai", cost_per_1k=cost_hint)
                elif provider == "zai":
                    result = self._call_openai(messages, model, effective_max, api_key=api_key, base_url=base_url or "https://api.z.ai/api/paas/v4", cost_per_1k=cost_hint)
                elif provider == "ollama":
                    result = self._call_ollama(messages, model, effective_max, base_url=base_url, cost_per_1k=cost_hint)
                else:
                    attempts.append(f"{provider}:unsupported")
                    continue
                meta["attempts"] = attempts + [f"{provider}:completed"]
                return result, "completed", meta
            except Exception as exc:  # noqa: BLE001
                first_error = first_error or exc
                attempts.append(f"{provider}:{type(exc).__name__}:{str(exc)[:120]}")
                continue

        if self._allow_stub():
            log.warning("All LLM providers failed, using deterministic test response: %s", "; ".join(attempts))
            return {}, "fallback", {
                "provider": requested_provider,
                "provider_model": model_id or self._get_model(requested_provider),
                "registered": runtime_model.registered,
                "attempts": attempts,
            }
        if first_error is not None:
            raise first_error
        raise RuntimeError("No configured LLM provider available: " + "; ".join(attempts))

    def _execute_call(self, messages: list[dict], model_id: str,
                      max_tokens: int = 1000) -> dict:
        """Shared logic for call() and call_messages().

        Dispatches to provider, records to SQLite, emits event.
        Returns the standard response dict.
        """
        start_time = time.time()

        # Build prompt_hash from serialized messages for audit trail
        prompt_text = messages[-1].get("content", "") if messages else ""
        prompt_hash = hashlib.sha256(
            json.dumps(messages, default=str).encode("utf-8")
        ).hexdigest()

        runtime_model = resolve_runtime_model(model_id)
        preflight_provider = runtime_model.provider or self._get_provider()
        policy = preflight_model_call(
            model_id,
            provider=preflight_provider,
            operation="llm_adapter.call",
            action_type="generation",
            risk_level="medium",
        )

        if not policy.get("allowed"):
            latency = int((time.time() - start_time) * 1000)
            llm_call = LLMCall(
                model_id=model_id,
                prompt_hash=prompt_hash,
                prompt_tokens=0,
                completion_tokens=0,
                cost=0.0,
                latency_ms=latency,
                status="blocked",
            )
            with self._lock:
                self._conn.execute("""
                    INSERT INTO llm_calls
                    (call_id, model_id, prompt_hash, prompt_tokens,
                     completion_tokens, cost, latency_ms, status, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    llm_call.call_id, llm_call.model_id, llm_call.prompt_hash,
                    llm_call.prompt_tokens, llm_call.completion_tokens,
                    llm_call.cost, llm_call.latency_ms, llm_call.status,
                    llm_call.timestamp,
                ))
                self._conn.commit()
            self._emit("llm.call_blocked", {
                "call_id": llm_call.call_id,
                "model_id": model_id,
                "reason": policy.get("reason"),
                "human_gate_request": policy.get("human_gate_request"),
            })
            return {
                "call_id": llm_call.call_id,
                "text": "",
                "tokens": 0,
                "cost": 0.0,
                "latency_ms": latency,
                "status": "blocked",
                "blocked": True,
                "policy": {k: v for k, v in policy.items() if k != "runtime_model"},
            }

        # Dispatch to provider
        result, status, dispatch_meta = self._dispatch(messages, model_id, max_tokens)

        if status in ("stub", "fallback"):
            stub = self._make_stub_response(start_time)
            text = stub["text"]
            total_tokens = 0
            cost = 0.0
            latency = stub["latency_ms"]
        else:
            text = result["text"]
            total_tokens = result["tokens"]
            cost = result["cost"]
            latency = int((time.time() - start_time) * 1000)

        prompt_tokens = int(result.get("prompt_tokens") or 0) if result else 0
        completion_tokens = int(result.get("completion_tokens") or total_tokens or 0) if result else 0
        estimated = estimate_cost(
            resolve_runtime_model(model_id, provider=dispatch_meta.get("provider", "")),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        if estimated > 0:
            cost = estimated
        budget_usage = record_model_usage(
            model_id,
            provider=dispatch_meta.get("provider", ""),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )

        llm_call = LLMCall(
            model_id=model_id,
            prompt_hash=prompt_hash,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            latency_ms=latency,
            status=status,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO llm_calls
                (call_id, model_id, prompt_hash, prompt_tokens,
                 completion_tokens, cost, latency_ms, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                llm_call.call_id, llm_call.model_id, llm_call.prompt_hash,
                llm_call.prompt_tokens, llm_call.completion_tokens,
                llm_call.cost, llm_call.latency_ms, llm_call.status,
                llm_call.timestamp,
            ))
            self._conn.commit()

        self._emit("llm.call_completed", {
            "call_id": llm_call.call_id,
            "model_id": model_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
            "latency_ms": latency,
            "provider": dispatch_meta.get("provider"),
            "provider_model": dispatch_meta.get("provider_model"),
        })
        log.info("LLM call %s to %s: %dms [%s]", llm_call.call_id[:12],
                 model_id, latency, status)

        return {
            "call_id": llm_call.call_id,
            "text": text,
            "tokens": total_tokens,
            "cost": cost,
            "latency_ms": latency,
            "status": status,
            "provider": dispatch_meta.get("provider"),
            "provider_model": dispatch_meta.get("provider_model"),
            "budget_usage": budget_usage,
            "policy": {
                "access_level": policy.get("access_level"),
                "approval_policy": policy.get("approval_policy"),
                "registered": policy.get("registered"),
            },
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(self, model_id: str, prompt: str,
             max_tokens: int = 1000) -> dict:
        """Execute an LLM call with a single prompt string.

        Wraps the prompt into a single user message and dispatches to the
        configured provider. Deterministic test fallback is only used when explicitly enabled.
        """
        messages = [{"role": "user", "content": prompt}]
        return self._execute_call(messages, model_id, max_tokens)

    def call_messages(self, model_id: str,
                      messages: list[dict],
                      max_tokens: int = 1000) -> dict:
        """Execute an LLM call with a multi-turn message list.

        Args:
            model_id: Identifier for the model to use.
            messages: List of message dicts, e.g.
                [{"role": "user", "content": "..."},
                 {"role": "assistant", "content": "..."},
                 {"role": "user", "content": "..."}]
            max_tokens: Maximum completion tokens.

        Returns:
            Same dict format as call():
            {"call_id", "text", "tokens", "cost", "latency_ms"}
        """
        return self._execute_call(messages, model_id, max_tokens)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_call(self, call_id: str) -> dict | None:
        """Retrieve a single LLM call record by ID."""
        row = self._conn.execute(
            "SELECT * FROM llm_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_calls(self, model_id: str | None = None,
                   limit: int = 100) -> list[dict]:
        """List LLM call records, optionally filtered by model."""
        if model_id:
            rows = self._conn.execute(
                "SELECT * FROM llm_calls WHERE model_id = ? ORDER BY timestamp DESC LIMIT ?",
                (model_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM llm_calls ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_usage_stats(self) -> dict:
        """Aggregate LLM usage statistics: total tokens, cost, calls."""
        row = self._conn.execute("""
            SELECT COUNT(*) as total_calls,
                   COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                   COALESCE(SUM(cost), 0) as total_cost
            FROM llm_calls
        """).fetchone()

        by_model_rows = self._conn.execute("""
            SELECT model_id, COUNT(*) as cnt,
                   COALESCE(SUM(cost), 0) as model_cost
            FROM llm_calls
            GROUP BY model_id
        """).fetchall()
        by_model = {}
        for r in by_model_rows:
            by_model[r["model_id"]] = {
                "calls": r["cnt"],
                "cost": r["model_cost"],
            }

        return {
            "total_calls": row["total_calls"],
            "total_prompt_tokens": row["total_prompt_tokens"],
            "total_completion_tokens": row["total_completion_tokens"],
            "total_cost": round(row["total_cost"], 6),
            "by_model": by_model,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.llm_adapter",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_adapter: LLMAdapter | None = None


def get_llm_adapter(model_router: Any = None,
                    event_bus: EventBus | None = None,
                    db_path: str | Path | None = None) -> LLMAdapter:
    global _adapter
    if _adapter is None:
        _adapter = LLMAdapter(model_router, event_bus, db_path)
    return _adapter
