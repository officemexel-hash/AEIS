"""SYLION Offensive — Swarm AI (Strategic + Tactical)"""
from .strategic_ai import StrategicAI, CampaignGoal
from .tactical_agents import TacticalAgent, ReconAgent, CredentialAgent, CloudAgent, WebAgent, ADAgent

__all__ = [
    "StrategicAI", "CampaignGoal",
    "TacticalAgent", "ReconAgent", "CredentialAgent", "CloudAgent", "WebAgent", "ADAgent",
]
