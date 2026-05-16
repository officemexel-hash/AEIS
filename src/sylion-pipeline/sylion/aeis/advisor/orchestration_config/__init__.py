"""SYLION AEIS — orchestration_config module.

Meta-orchestration controls for the multi-agent system: LLM routing, Council rules,
auditor cadence, fixer protocol, dispatch config, test catalog, team formation,
event map, and inter-model conversations.
"""
from sylion.aeis.advisor.orchestration_config.service import get_orchestration_service

__all__ = ["get_orchestration_service"]
