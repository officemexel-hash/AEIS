"""SYLION AEIS Advisor — Engine module.

Heart of the advisor layer:
- subscribes to 16 lifecycle hooks
- evaluates rule DSL against incoming events
- calls LLM-as-judge for rationale + alternatives
- calculates 4-component confidence with local-fallback x0.8 multiplier
- assigns D-level via 5 upgrade rules
- builds AdvisorCardEnvelope (header + body)
- triggers Evidence Pack creation when D5 or D3+ cost/subscription/funding
- emits via existing event_bus
"""

from sylion.aeis.advisor.engine.service import AdvisorEngineService, get_engine_service

__all__ = ["AdvisorEngineService", "get_engine_service"]
