"""Dataclass models for orchestration_config module."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# J1 — LLM Judge Routing Matrix
# ---------------------------------------------------------------------------

@dataclass
class LLMJudgeRoutingCell:
    recommendation_type: str
    risk_level: str           # low | medium | high | critical
    model_id: str
    enabled: bool = True
    is_default: bool = False


@dataclass
class LLMJudgeRoutingMatrix:
    cells: List[LLMJudgeRoutingCell] = field(default_factory=list)
    preset: str = "balanced"  # cost-saving | balanced | aggressive
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# J2 — Council Rules
# ---------------------------------------------------------------------------

@dataclass
class RankWeight:
    rank: int           # 1–5
    label: str
    weight: float       # 0.0–1.0


@dataclass
class SentinelRequirement:
    d_level: str        # D0–D5
    cost_required: bool
    security_required: bool


@dataclass
class CouncilRules:
    rank_weights: List[RankWeight] = field(default_factory=list)
    critic_gate_enabled: bool = True
    critic_gate_threshold: float = 0.6
    quorum_min: int = 3
    quorum_type: str = "majority"   # majority | absolute | supermajority
    sentinel_requirements: List[SentinelRequirement] = field(default_factory=list)
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# J3 — Auditor Cadence
# ---------------------------------------------------------------------------

@dataclass
class AuditorCadence:
    tick_frequency_seconds: int = 300
    enabled_dimensions: List[str] = field(default_factory=list)
    phase_boundary_cron: str = "0 */4 * * *"
    last_audit_at: Optional[str] = None
    last_10_audits: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# J4 — Fixer Protocol
# ---------------------------------------------------------------------------

@dataclass
class AgentRetryBudget:
    agent_type: str     # codex | kimi | claude | z_ai
    retry_limit: int = 2


@dataclass
class FixerProtocol:
    retry_budgets: List[AgentRetryBudget] = field(default_factory=list)
    escalation_path: List[str] = field(default_factory=list)   # ordered module names
    max_nogo_iterations: int = 3
    auto_revert_on_critical_security: bool = True
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# J5 — Multi-Agent Dispatch Config
# ---------------------------------------------------------------------------

@dataclass
class StageAllocationRule:
    stage_type: str     # architectural | production | testing | docs
    claude_ratio: float = 0.4
    codex_ratio: float = 0.3
    kimi_ratio: float = 0.3


@dataclass
class DispatchConfig:
    parallelism_mode: str = "wide"      # wide | capped
    max_simultaneous: Optional[int] = None
    stage_allocation_rules: List[StageAllocationRule] = field(default_factory=list)
    cost_ceiling_usd_per_hour: Optional[float] = None
    sub_agent_permission_by_type: Dict[str, bool] = field(default_factory=dict)
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# J6 — Test Catalog
# ---------------------------------------------------------------------------

@dataclass
class TestEntry:
    test_id: str
    name: str
    module: str
    suite: str
    test_type: str      # golden | integration | e2e | sim
    status: str = "never_run"  # pass | fail | skip | never_run
    last_run_at: Optional[str] = None
    last_run_output: Optional[str] = None


@dataclass
class TestCatalogRun:
    run_id: str
    test_id: Optional[str] = None
    suite: Optional[str] = None
    status: str = "pending"   # pending | running | pass | fail
    triggered_at: Optional[str] = None
    completed_at: Optional[str] = None
    output: Optional[str] = None


# ---------------------------------------------------------------------------
# J7 — Team Formation Rules
# ---------------------------------------------------------------------------

@dataclass
class TeamFormationRule:
    rule_id: str
    trigger_pattern: str    # regex on commit message prefix
    agent_types: List[str] = field(default_factory=list)
    lifetime: str = "ephemeral"  # ephemeral | persistent
    action: str = "spawn_audit_team"
    enabled: bool = True
    created_at: Optional[str] = None


@dataclass
class ActiveTeam:
    team_id: str
    rule_id: str
    agent_types: List[str] = field(default_factory=list)
    current_task: Optional[str] = None
    formed_at: Optional[str] = None
    lifetime: str = "ephemeral"


# ---------------------------------------------------------------------------
# J8 — Event Map
# ---------------------------------------------------------------------------

@dataclass
class EventMapNode:
    module_id: str
    events_emitted: List[str] = field(default_factory=list)
    events_subscribed: List[str] = field(default_factory=list)


@dataclass
class EventMapEdge:
    emitter: str
    topic: str
    subscriber: str
    events_per_minute: float = 0.0
    sample_payload: Optional[Dict[str, Any]] = None


@dataclass
class EventMap:
    nodes: List[EventMapNode] = field(default_factory=list)
    edges: List[EventMapEdge] = field(default_factory=list)
    generated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# J9 — Inter-Model Conversation Settings
# ---------------------------------------------------------------------------

@dataclass
class InterModelConversationSettings:
    enabled: bool = False
    max_turns: int = 4
    arbiter_model_id: Optional[str] = None
    disagreement_voting: bool = True
    recent_conversations: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: Optional[str] = None
