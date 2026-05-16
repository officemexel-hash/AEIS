"""
SYLION Cognitive -- Model Runtime Policy.

Central enforcement point for model execution.  It connects the operator's
model registry configuration with runtime calls so budget, access level and
Human Gate policy are not dashboard-only metadata.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("sylion.cognitive.model_runtime_policy")

EXTERNAL_PROVIDERS = {"anthropic", "openai", "perplexity", "google", "zai"}
LOCAL_PROVIDERS = {"ollama", "stub", "local"}


@dataclass
class RuntimeModel:
    model_id: str
    provider: str = ""
    display_name: str = ""
    registered: bool = False
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def provider_model(self) -> str:
        return str(
            self.config.get("provider_model")
            or self.config.get("model_name")
            or self.config.get("runtime_model")
            or self.model_id
        )

    @property
    def access_level(self) -> str:
        return str(self.config.get("access_level") or "gated")

    @property
    def approval_policy(self) -> str:
        return str(self.config.get("approval_policy") or "ask_for_risky_changes")

    @property
    def fallback_model_id(self) -> str:
        return str(self.config.get("fallback_model_id") or self.config.get("fallback_model") or "")

    @property
    def is_external(self) -> bool:
        return self.provider.lower() in EXTERNAL_PROVIDERS


class ModelRuntimeBlocked(RuntimeError):
    """Raised when governance blocks a model call before provider execution."""

    def __init__(self, policy_result: dict[str, Any]):
        self.policy_result = policy_result
        super().__init__(str(policy_result.get("reason") or "model runtime blocked"))


def _parse_config(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def resolve_runtime_model(model_id: str, provider: str = "") -> RuntimeModel:
    """Resolve a runtime model from the canonical model registry.

    Missing registry entries are allowed for legacy flows, but they receive
    default gated policy and budget checks still use the requested model_id.
    """
    requested = (model_id or "").strip()
    try:
        from sylion.cognitive.model_registry import get_model_registry

        registry = get_model_registry()
        row = registry.get_model(requested) if requested else None
    except Exception as exc:  # noqa: BLE001
        log.debug("model registry unavailable for %s: %s", requested, exc)
        row = None

    if row:
        cfg = _parse_config(row.get("config_json"))
        return RuntimeModel(
            model_id=row.get("model_id") or requested,
            provider=(row.get("provider") or provider or "").lower(),
            display_name=row.get("display_name") or "",
            registered=True,
            config=cfg,
        )

    return RuntimeModel(
        model_id=requested,
        provider=(provider or "").lower(),
        display_name=requested,
        registered=False,
        config={},
    )


def estimate_cost(
    runtime_model: RuntimeModel,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> float:
    """Estimate USD cost using operator-configured pricing."""
    cfg = runtime_model.config
    prompt = max(0, int(prompt_tokens or 0))
    completion = max(0, int(completion_tokens or 0))
    total = prompt + completion

    try:
        input_per_1m = float(cfg.get("input_cost_per_1m_usd") or 0)
        output_per_1m = float(cfg.get("output_cost_per_1m_usd") or 0)
    except (TypeError, ValueError):
        input_per_1m = 0.0
        output_per_1m = 0.0

    if input_per_1m > 0 or output_per_1m > 0:
        return round((prompt / 1_000_000.0) * input_per_1m + (completion / 1_000_000.0) * output_per_1m, 8)

    try:
        cost_per_1k = float(cfg.get("cost_per_1k_tokens_usd") or cfg.get("cost_per_1k_tokens") or 0)
    except (TypeError, ValueError):
        cost_per_1k = 0.0

    if cost_per_1k <= 0:
        return 0.0
    return round((total / 1000.0) * cost_per_1k, 8)


def _create_human_gate(runtime_model: RuntimeModel, reason: str, context: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from sylion.governance.human_gate import get_human_gate

        gate = get_human_gate()
        return gate.create_request(
            gate_id="ai_model_runtime_policy",
            title=f"Model runtime approval required: {runtime_model.model_id}",
            description=reason,
            context_json={
                "model_id": runtime_model.model_id,
                "provider": runtime_model.provider,
                "display_name": runtime_model.display_name,
                "access_level": runtime_model.access_level,
                "approval_policy": runtime_model.approval_policy,
                **context,
            },
            requested_by="model_runtime_policy",
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("failed to create Human Gate ticket for model runtime policy")
        return {
            "error": "human_gate_unavailable",
            "detail": str(exc)[:300],
        }


def _blocked(
    runtime_model: RuntimeModel,
    *,
    reason: str,
    context: dict[str, Any],
    create_gate: bool,
) -> dict[str, Any]:
    ticket = _create_human_gate(runtime_model, reason, context) if create_gate else None
    return {
        "allowed": False,
        "requires_human_gate": bool(create_gate),
        "reason": reason,
        "model_id": runtime_model.model_id,
        "provider": runtime_model.provider,
        "access_level": runtime_model.access_level,
        "approval_policy": runtime_model.approval_policy,
        "human_gate_request": ticket,
    }


def preflight_model_call(
    model_id: str,
    *,
    provider: str = "",
    operation: str = "llm_call",
    action_type: str = "generation",
    risk_level: str = "medium",
    estimated_cost: float = 0.0,
    create_human_gate: bool = True,
) -> dict[str, Any]:
    """Check whether a model call may execute.

    This function is deliberately conservative.  It does not approve risky or
    external actions by inference; it either allows a clearly permitted call or
    creates a Human Gate ticket and blocks execution.
    """
    runtime_model = resolve_runtime_model(model_id, provider=provider)
    access = runtime_model.access_level
    policy = runtime_model.approval_policy
    action = (action_type or "generation").lower()
    risk = (risk_level or "medium").lower()
    context = {
        "operation": operation,
        "action_type": action,
        "risk_level": risk,
        "estimated_cost": estimated_cost,
        "registered": runtime_model.registered,
    }

    try:
        from sylion.monitoring.model_budget import get_model_budget

        budget = get_model_budget().check_budget(runtime_model.model_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("budget check failed for %s", runtime_model.model_id)
        return _blocked(
            runtime_model,
            reason=f"Budget check failed: {str(exc)[:200]}",
            context=context,
            create_gate=create_human_gate,
        )

    if budget and not budget.get("allowed", True):
        return _blocked(
            runtime_model,
            reason="Model budget exceeded; execution requires operator approval.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    if estimated_cost and estimated_cost > 25:
        return _blocked(
            runtime_model,
            reason="Single model action cost estimate exceeds 25 USD.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    if access in {"disabled", "read_only"} and action not in {"inspect", "list", "budget_check"}:
        return _blocked(
            runtime_model,
            reason=f"Model access_level={access} does not permit runtime execution.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    if access == "review_only" and action not in {"review", "validation", "connectivity_test"}:
        return _blocked(
            runtime_model,
            reason="Model is review_only and cannot execute this action type.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    if access == "no_external_actions" and runtime_model.is_external:
        return _blocked(
            runtime_model,
            reason="Model is configured for no_external_actions, but the provider is external.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    if policy == "always_human_gate":
        return _blocked(
            runtime_model,
            reason="Model approval_policy=always_human_gate requires operator approval.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    if policy == "ask_for_external_actions" and runtime_model.is_external:
        return _blocked(
            runtime_model,
            reason="External provider call requires Human Gate by model approval policy.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    if policy == "ask_for_architecture_changes" and action in {"architecture_change", "strategic_change"}:
        return _blocked(
            runtime_model,
            reason="Architecture or strategic model action requires Human Gate.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    if policy == "ask_for_code_changes" and action in {"code_change", "implementation"}:
        return _blocked(
            runtime_model,
            reason="Code-changing model action requires Human Gate.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    risky_actions = {
        "production_deploy",
        "external_upload",
        "external_submit",
        "final_publish",
        "financial",
        "legal",
        "security_change",
    }
    if policy == "ask_for_risky_changes" and (risk in {"high", "critical"} or action in risky_actions):
        return _blocked(
            runtime_model,
            reason="Risky model action requires Human Gate.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    if policy == "auto_low_risk_only" and risk not in {"low"}:
        return _blocked(
            runtime_model,
            reason="Model policy allows only low-risk autonomous actions.",
            context={**context, "budget": budget},
            create_gate=create_human_gate,
        )

    return {
        "allowed": True,
        "requires_human_gate": False,
        "reason": "",
        "model_id": runtime_model.model_id,
        "provider": runtime_model.provider,
        "provider_model": runtime_model.provider_model,
        "access_level": access,
        "approval_policy": policy,
        "registered": runtime_model.registered,
        "budget": budget,
        "runtime_model": runtime_model,
    }


def record_model_usage(
    model_id: str,
    *,
    provider: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost: float | None = None,
) -> dict[str, Any] | None:
    """Record post-call usage in the budget manager."""
    runtime_model = resolve_runtime_model(model_id, provider=provider)
    tokens = max(0, int(prompt_tokens or 0)) + max(0, int(completion_tokens or 0))
    effective_cost = estimate_cost(
        runtime_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    ) if cost is None else float(cost or 0)

    try:
        from sylion.monitoring.model_budget import get_model_budget

        return get_model_budget().record_usage(runtime_model.model_id, tokens=tokens, cost=effective_cost)
    except Exception:  # noqa: BLE001
        log.exception("failed to record model usage for %s", runtime_model.model_id)
        return None
