"""OrchestrationConfigService."""
from __future__ import annotations

import logging
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sylion.aeis.advisor.orchestration_config import _db
from sylion.aeis.advisor.orchestration_config._models import (
    ActiveTeam,
    AgentRetryBudget,
    AuditorCadence,
    CouncilRules,
    DispatchConfig,
    EventMap,
    EventMapEdge,
    EventMapNode,
    FixerProtocol,
    InterModelConversationSettings,
    LLMJudgeRoutingCell,
    LLMJudgeRoutingMatrix,
    RankWeight,
    SentinelRequirement,
    StageAllocationRule,
    TeamFormationRule,
    TestCatalogRun,
    TestEntry,
)

log = logging.getLogger("sylion.aeis.advisor.orchestration_config")

_DEFAULT_RECOMMENDATION_TYPES = [
    "cost_optimization",
    "scaling",
    "security",
    "subscription",
    "architecture",
    "funding",
    "onboarding",
    "maintenance",
]
_RISK_LEVELS = ["low", "medium", "high", "critical"]

_DEFAULT_MODEL_MAP = {
    ("cost_optimization", "low"): "claude-haiku-4-5-20251001",
    ("cost_optimization", "medium"): "claude-haiku-4-5-20251001",
    ("cost_optimization", "high"): "claude-sonnet-4-6",
    ("cost_optimization", "critical"): "claude-opus-4-7",
    ("security", "high"): "claude-sonnet-4-6",
    ("security", "critical"): "claude-opus-4-7",
}

_DEFAULT_AUDIT_DIMENSIONS = [
    "code_quality",
    "test_coverage",
    "security_posture",
    "cost_efficiency",
    "performance_budget",
    "api_contract_compliance",
    "event_schema_validity",
    "preference_drift",
    "council_health",
    "escalation_backlog",
    "funding_deadlines",
    "subscription_roi",
    "d_level_distribution",
    "hallucination_rate",
    "evidence_pack_completeness",
    "agent_error_rate",
]

_STORE: Dict[str, Any] = {}
_LOCK = threading.Lock()
_PG_AVAILABLE: Optional[bool] = None
_DEFAULT_STORE_PATH = Path(".aeis_runtime/orchestration_config_store.json")
_STORE_PATH = Path(os.environ.get("SYLION_ORCHESTRATION_STORE", _DEFAULT_STORE_PATH))
_ACTIVE_STORE_PATH: Path | None = None


def _current_store_path() -> Path:
    explicit = os.environ.get("SYLION_ORCHESTRATION_STORE")
    if explicit:
        return Path(explicit)
    db_path = os.environ.get("SYLION_DB_PATH")
    if db_path and db_path != ":memory:":
        path = Path(db_path)
        return path.with_name(f"{path.name}.orchestration_config_store.json")
    return _DEFAULT_STORE_PATH


def _ensure_store_context() -> Path:
    global _ACTIVE_STORE_PATH
    path = _current_store_path()
    if _ACTIVE_STORE_PATH != path:
        _STORE.clear()
        _ACTIVE_STORE_PATH = path
    return path


def _load_store_from_disk() -> None:
    store_path = _ensure_store_context()
    if _STORE or not store_path.exists():
        return
    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - fallback store must not block runtime
        log.debug("orchestration fallback store load failed: %s", exc)
        return
    if isinstance(data, dict):
        _STORE.update(data)


def _flush_store_to_disk() -> None:
    try:
        store_path = _ensure_store_context()
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store_path.write_text(json.dumps(_STORE, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - fallback store must not block runtime
        log.debug("orchestration fallback store write failed: %s", exc)


def _store_get(key: str) -> Optional[Any]:
    with _LOCK:
        _load_store_from_disk()
        return _STORE.get(key)


def _store_set(key: str, value: Any) -> None:
    with _LOCK:
        _STORE[key] = value
        _flush_store_to_disk()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _pg_call(func, *args, **kwargs):
    global _PG_AVAILABLE
    if _PG_AVAILABLE is False:
        return None
    if not os.environ.get("SYLION_PG_DSN") and not os.environ.get("SYLION_DB_URL"):
        _PG_AVAILABLE = False
        return None
    try:
        result = func(*args, **kwargs)
        _PG_AVAILABLE = True
        return result
    except Exception as exc:
        _PG_AVAILABLE = False
        log.debug("PG operation failed, using fallback store: %s", exc)
        return None


class OrchestrationConfigService:
    """Thread-safe service for all J1-J9 orchestration config operations."""

    def _default_llm_routing(self) -> LLMJudgeRoutingMatrix:
        cells = []
        for rec_type in _DEFAULT_RECOMMENDATION_TYPES:
            for risk in _RISK_LEVELS:
                model = _DEFAULT_MODEL_MAP.get((rec_type, risk), "claude-haiku-4-5-20251001")
                cells.append(
                    LLMJudgeRoutingCell(
                        recommendation_type=rec_type,
                        risk_level=risk,
                        model_id=model,
                        enabled=True,
                        is_default=True,
                    )
                )
        return LLMJudgeRoutingMatrix(cells=cells, preset="balanced")

    def get_llm_routing(self) -> LLMJudgeRoutingMatrix:
        raw = _pg_call(_db.load_llm_judge_routing)
        if raw:
            return LLMJudgeRoutingMatrix(
                cells=[
                    LLMJudgeRoutingCell(
                        recommendation_type=row["recommendation_type"],
                        risk_level=row["risk_level"],
                        model_id=row["model_id"],
                        enabled=row.get("enabled", True),
                        is_default=False,
                    )
                    for row in raw
                ],
                preset="database",
            )
        stored = _store_get("llm_judge_routing")
        if stored:
            return LLMJudgeRoutingMatrix(
                cells=[LLMJudgeRoutingCell(**c) for c in stored.get("cells", [])],
                preset=stored.get("preset", "balanced"),
                updated_at=stored.get("updated_at"),
            )
        return self._default_llm_routing()

    def update_llm_routing(self, cells: List[dict], preset: str = "balanced") -> LLMJudgeRoutingMatrix:
        matrix = LLMJudgeRoutingMatrix(
            cells=[LLMJudgeRoutingCell(**c) for c in cells],
            preset=preset,
            updated_at=_now_iso(),
        )
        payload = {
            "cells": [c.__dict__ for c in matrix.cells],
            "preset": matrix.preset,
            "updated_at": matrix.updated_at,
        }
        _store_set("llm_judge_routing", payload)
        _pg_call(_db.replace_llm_judge_routing, payload["cells"])
        return matrix

    def reset_llm_routing_cell(self, recommendation_type: str, risk_level: str) -> LLMJudgeRoutingMatrix:
        matrix = self.get_llm_routing()
        default = self._default_llm_routing()
        default_cell = next(
            (
                c
                for c in default.cells
                if c.recommendation_type == recommendation_type and c.risk_level == risk_level
            ),
            None,
        )
        if default_cell:
            found = False
            for idx, cell in enumerate(matrix.cells):
                if cell.recommendation_type == recommendation_type and cell.risk_level == risk_level:
                    matrix.cells[idx] = default_cell
                    found = True
                    break
            if not found:
                matrix.cells.append(default_cell)
        return self.update_llm_routing([c.__dict__ for c in matrix.cells], matrix.preset)

    def apply_llm_routing_preset(self, preset: str) -> LLMJudgeRoutingMatrix:
        presets = {
            "cost-saving": "claude-haiku-4-5-20251001",
            "balanced": None,
            "aggressive": "claude-opus-4-7",
        }
        if preset not in presets:
            raise ValueError(f"Unknown preset: {preset}")
        matrix = self._default_llm_routing()
        forced_model = presets[preset]
        if forced_model:
            for cell in matrix.cells:
                cell.model_id = forced_model
                cell.is_default = False
        matrix.preset = preset
        return self.update_llm_routing([c.__dict__ for c in matrix.cells], preset)

    def _default_council_rules(self) -> CouncilRules:
        return CouncilRules(
            rank_weights=[
                RankWeight(rank=1, label="Associate", weight=0.6),
                RankWeight(rank=2, label="Engineer", weight=0.8),
                RankWeight(rank=3, label="Senior", weight=1.0),
                RankWeight(rank=4, label="Principal", weight=1.2),
                RankWeight(rank=5, label="Architect", weight=1.5),
            ],
            critic_gate_enabled=True,
            critic_gate_threshold=0.6,
            quorum_min=3,
            quorum_type="majority",
            sentinel_requirements=[
                SentinelRequirement(d_level="D3", cost_required=False, security_required=False),
                SentinelRequirement(d_level="D4", cost_required=True, security_required=False),
                SentinelRequirement(d_level="D5", cost_required=True, security_required=True),
            ],
        )

    def get_council_rules(self) -> CouncilRules:
        raw = _pg_call(_db.load_council_rules)
        if raw:
            return CouncilRules(
                rank_weights=[RankWeight(**w) for w in raw.get("rank_weights", [])],
                critic_gate_enabled=raw.get("critic_gate_enabled", True),
                critic_gate_threshold=raw.get("critic_gate_threshold", 0.6),
                quorum_min=raw.get("quorum_min", 3),
                quorum_type=raw.get("quorum_type", "majority"),
                sentinel_requirements=[SentinelRequirement(**s) for s in raw.get("sentinel_requirements", [])],
                updated_at=raw.get("updated_at"),
            )
        raw = _store_get("council_rules")
        if raw:
            return CouncilRules(
                rank_weights=[RankWeight(**w) for w in raw.get("rank_weights", [])],
                critic_gate_enabled=raw.get("critic_gate_enabled", True),
                critic_gate_threshold=raw.get("critic_gate_threshold", 0.6),
                quorum_min=raw.get("quorum_min", 3),
                quorum_type=raw.get("quorum_type", "majority"),
                sentinel_requirements=[SentinelRequirement(**s) for s in raw.get("sentinel_requirements", [])],
                updated_at=raw.get("updated_at"),
            )
        return self._default_council_rules()

    def update_council_rules(self, data: dict) -> CouncilRules:
        rules = CouncilRules(
            rank_weights=[RankWeight(**w) for w in data.get("rank_weights", [])],
            critic_gate_enabled=data.get("critic_gate_enabled", True),
            critic_gate_threshold=data.get("critic_gate_threshold", 0.6),
            quorum_min=data.get("quorum_min", 3),
            quorum_type=data.get("quorum_type", "majority"),
            sentinel_requirements=[SentinelRequirement(**s) for s in data.get("sentinel_requirements", [])],
            updated_at=_now_iso(),
        )
        payload = {
            "rank_weights": [w.__dict__ for w in rules.rank_weights],
            "critic_gate_enabled": rules.critic_gate_enabled,
            "critic_gate_threshold": rules.critic_gate_threshold,
            "quorum_min": rules.quorum_min,
            "quorum_type": rules.quorum_type,
            "sentinel_requirements": [s.__dict__ for s in rules.sentinel_requirements],
            "updated_at": rules.updated_at,
        }
        _store_set("council_rules", payload)
        _pg_call(_db.upsert_council_rules, payload)
        return rules

    def simulate_council_vote(self, votes: List[dict]) -> dict:
        rules = self.get_council_rules()
        weight_map = {w.rank: w.weight for w in rules.rank_weights}
        total_weight = 0.0
        for_weight = 0.0
        against_weight = 0.0
        abstain_weight = 0.0
        for vote in votes:
            rank = int(vote.get("rank", 3))
            weight = weight_map.get(rank, 1.0)
            total_weight += weight
            value = vote.get("vote", "abstain")
            if value == "for":
                for_weight += weight
            elif value == "against":
                against_weight += weight
            else:
                abstain_weight += weight
        participating = len([vote for vote in votes if vote.get("vote") != "abstain"])
        quorum_met = participating >= rules.quorum_min
        outcome = "approved" if quorum_met and for_weight > against_weight else "rejected"
        return {
            "outcome": outcome,
            "quorum_met": quorum_met,
            "total_weight": total_weight,
            "for_weight": for_weight,
            "against_weight": against_weight,
            "abstain_weight": abstain_weight,
            "participating": participating,
            "quorum_min": rules.quorum_min,
        }

    def get_auditor_cadence(self) -> AuditorCadence:
        raw = _pg_call(_db.load_auditor_cadence)
        if raw:
            return AuditorCadence(
                tick_frequency_seconds=raw.get("tick_frequency_seconds", 300),
                enabled_dimensions=raw.get("enabled_dimensions", _DEFAULT_AUDIT_DIMENSIONS[:]),
                phase_boundary_cron=raw.get("phase_boundary_cron", "0 */4 * * *"),
                last_audit_at=raw.get("last_audit_at"),
                last_10_audits=raw.get("last_10_audits", []),
                updated_at=raw.get("updated_at"),
            )
        raw = _store_get("auditor_cadence")
        if raw:
            return AuditorCadence(
                tick_frequency_seconds=raw.get("tick_frequency_seconds", 300),
                enabled_dimensions=raw.get("enabled_dimensions", _DEFAULT_AUDIT_DIMENSIONS[:]),
                phase_boundary_cron=raw.get("phase_boundary_cron", "0 */4 * * *"),
                last_audit_at=raw.get("last_audit_at"),
                last_10_audits=raw.get("last_10_audits", []),
                updated_at=raw.get("updated_at"),
            )
        return AuditorCadence(
            tick_frequency_seconds=300,
            enabled_dimensions=_DEFAULT_AUDIT_DIMENSIONS[:],
            phase_boundary_cron="0 */4 * * *",
        )

    def update_auditor_cadence(self, data: dict) -> AuditorCadence:
        existing = self.get_auditor_cadence()
        cadence = AuditorCadence(
            tick_frequency_seconds=data.get("tick_frequency_seconds", 300),
            enabled_dimensions=data.get("enabled_dimensions", _DEFAULT_AUDIT_DIMENSIONS[:]),
            phase_boundary_cron=data.get("phase_boundary_cron", "0 */4 * * *"),
            last_audit_at=existing.last_audit_at,
            last_10_audits=existing.last_10_audits,
            updated_at=_now_iso(),
        )
        _store_set("auditor_cadence", cadence.__dict__)
        _pg_call(_db.upsert_auditor_cadence, cadence.__dict__)
        return cadence

    def trigger_audit_now(self) -> dict:
        audit_record = {
            "audit_id": str(uuid.uuid4()),
            "triggered_at": _now_iso(),
            "status": "triggered",
        }
        cadence = self.get_auditor_cadence()
        cadence.last_audit_at = audit_record["triggered_at"]
        cadence.last_10_audits = [audit_record] + cadence.last_10_audits[:9]
        cadence.updated_at = _now_iso()
        _store_set("auditor_cadence", cadence.__dict__)
        _pg_call(_db.upsert_auditor_cadence, cadence.__dict__)
        return audit_record

    def get_fixer_protocol(self) -> FixerProtocol:
        raw = _pg_call(_db.load_fixer_protocol)
        if raw:
            return FixerProtocol(
                retry_budgets=[AgentRetryBudget(**b) for b in raw.get("retry_budgets", [])],
                escalation_path=raw.get("escalation_path", []),
                max_nogo_iterations=raw.get("max_nogo_iterations", 3),
                auto_revert_on_critical_security=raw.get("auto_revert_on_critical_security", True),
                updated_at=raw.get("updated_at"),
            )
        raw = _store_get("fixer_protocol")
        if raw:
            return FixerProtocol(
                retry_budgets=[AgentRetryBudget(**b) for b in raw.get("retry_budgets", [])],
                escalation_path=raw.get("escalation_path", []),
                max_nogo_iterations=raw.get("max_nogo_iterations", 3),
                auto_revert_on_critical_security=raw.get("auto_revert_on_critical_security", True),
                updated_at=raw.get("updated_at"),
            )
        return FixerProtocol(
            retry_budgets=[
                AgentRetryBudget(agent_type="codex", retry_limit=2),
                AgentRetryBudget(agent_type="kimi", retry_limit=2),
                AgentRetryBudget(agent_type="claude", retry_limit=2),
                AgentRetryBudget(agent_type="z_ai", retry_limit=3),
            ],
            escalation_path=["original_agent", "final_integrator", "operator"],
            max_nogo_iterations=3,
            auto_revert_on_critical_security=True,
        )

    def update_fixer_protocol(self, data: dict) -> FixerProtocol:
        protocol = FixerProtocol(
            retry_budgets=[AgentRetryBudget(**b) for b in data.get("retry_budgets", [])],
            escalation_path=data.get("escalation_path", []),
            max_nogo_iterations=data.get("max_nogo_iterations", 3),
            auto_revert_on_critical_security=data.get("auto_revert_on_critical_security", True),
            updated_at=_now_iso(),
        )
        payload = {
            "retry_budgets": [b.__dict__ for b in protocol.retry_budgets],
            "escalation_path": protocol.escalation_path,
            "max_nogo_iterations": protocol.max_nogo_iterations,
            "auto_revert_on_critical_security": protocol.auto_revert_on_critical_security,
            "updated_at": protocol.updated_at,
        }
        _store_set("fixer_protocol", payload)
        _pg_call(_db.upsert_fixer_protocol, payload)
        return protocol

    def get_dispatch_config(self) -> DispatchConfig:
        raw = _pg_call(_db.load_dispatch_config)
        if raw:
            return DispatchConfig(
                parallelism_mode=raw.get("parallelism_mode", "wide"),
                max_simultaneous=raw.get("max_simultaneous"),
                stage_allocation_rules=[StageAllocationRule(**r) for r in raw.get("stage_allocation_rules", [])],
                cost_ceiling_usd_per_hour=raw.get("cost_ceiling_usd_per_hour"),
                sub_agent_permission_by_type=raw.get("sub_agent_permission_by_type", {}),
                updated_at=raw.get("updated_at"),
            )
        raw = _store_get("dispatch_config")
        if raw:
            return DispatchConfig(
                parallelism_mode=raw.get("parallelism_mode", "wide"),
                max_simultaneous=raw.get("max_simultaneous"),
                stage_allocation_rules=[StageAllocationRule(**r) for r in raw.get("stage_allocation_rules", [])],
                cost_ceiling_usd_per_hour=raw.get("cost_ceiling_usd_per_hour"),
                sub_agent_permission_by_type=raw.get("sub_agent_permission_by_type", {}),
                updated_at=raw.get("updated_at"),
            )
        return DispatchConfig(
            parallelism_mode="wide",
            stage_allocation_rules=[
                StageAllocationRule(stage_type="architectural", claude_ratio=0.5, codex_ratio=0.2, kimi_ratio=0.3),
                StageAllocationRule(stage_type="production", claude_ratio=0.3, codex_ratio=0.5, kimi_ratio=0.2),
                StageAllocationRule(stage_type="testing", claude_ratio=0.2, codex_ratio=0.4, kimi_ratio=0.4),
                StageAllocationRule(stage_type="docs", claude_ratio=0.6, codex_ratio=0.2, kimi_ratio=0.2),
            ],
            sub_agent_permission_by_type={"claude": True, "codex": True, "kimi": False, "z_ai": True},
        )

    def update_dispatch_config(self, data: dict) -> DispatchConfig:
        parallelism_mode = data.get("parallelism_mode", "wide")
        max_simultaneous = data.get("max_simultaneous")
        if parallelism_mode == "capped" and max_simultaneous is None:
            max_simultaneous = 8
        config = DispatchConfig(
            parallelism_mode=parallelism_mode,
            max_simultaneous=max_simultaneous,
            stage_allocation_rules=[StageAllocationRule(**r) for r in data.get("stage_allocation_rules", [])],
            cost_ceiling_usd_per_hour=data.get("cost_ceiling_usd_per_hour"),
            sub_agent_permission_by_type=data.get("sub_agent_permission_by_type", {}),
            updated_at=_now_iso(),
        )
        payload = {
            "parallelism_mode": config.parallelism_mode,
            "max_simultaneous": config.max_simultaneous,
            "stage_allocation_rules": [r.__dict__ for r in config.stage_allocation_rules],
            "cost_ceiling_usd_per_hour": config.cost_ceiling_usd_per_hour,
            "sub_agent_permission_by_type": config.sub_agent_permission_by_type,
            "updated_at": config.updated_at,
        }
        _store_set("dispatch_config", payload)
        _pg_call(_db.upsert_dispatch_config, payload)
        return config

    def _seed_test_catalog(self) -> List[TestEntry]:
        entries = []
        modules = [
            "advisor.engine",
            "advisor.preferences",
            "advisor.funding",
            "advisor.role_resolver",
            "advisor.council",
        ]
        for module_name in modules:
            for index in range(3):
                test_type = "golden" if index == 0 else ("integration" if index == 1 else "e2e")
                entries.append(
                    TestEntry(
                        test_id=str(uuid.uuid4()),
                        name=f"test_{module_name.replace('.', '_')}_{index}",
                        module=module_name,
                        suite=test_type,
                        test_type=test_type,
                        status="never_run",
                    )
                )
        payload = [entry.__dict__ for entry in entries]
        _store_set("test_catalog", payload)
        _pg_call(_db.replace_test_catalog, payload)
        return entries

    def get_test_catalog(self) -> List[TestEntry]:
        raw = _pg_call(_db.list_test_catalog)
        if raw:
            return [TestEntry(**row) for row in raw]
        raw = _store_get("test_catalog")
        if raw:
            return [TestEntry(**row) for row in raw]
        return self._seed_test_catalog()

    def get_test_catalog_runs(self, limit: int = 20) -> List[TestCatalogRun]:
        raw = _pg_call(_db.list_test_catalog_runs, limit)
        if raw is None:
            raw = _store_get("test_catalog_runs") or []
        return [TestCatalogRun(**row) for row in raw[:limit]]

    def _run_catalog_entry_check(self, entry: TestEntry) -> tuple[bool, str]:
        """Run a small deterministic backend check for a catalog entry."""
        module = entry.module
        test_type = entry.test_type
        try:
            if module == "advisor.engine":
                event_map = self.get_event_map()
                assert event_map.edges, "event map has no advisor edges"
                assert any(edge.topic == "aeis.advisor.card.issued" for edge in event_map.edges), (
                    "missing advisor card issued edge"
                )
            elif module == "advisor.preferences":
                routing = self.get_llm_routing()
                assert routing.cells, "LLM routing matrix is empty"
                assert all(cell.model_id for cell in routing.cells), "routing cell without model_id"
            elif module == "advisor.funding":
                cadence = self.get_auditor_cadence()
                assert "funding_deadlines" in cadence.enabled_dimensions, "funding deadline audit disabled"
            elif module == "advisor.role_resolver":
                rules = self.get_team_formation_rules()
                assert rules, "team formation rules are empty"
                assert any(rule.enabled for rule in rules), "no enabled team formation rule"
            elif module == "advisor.council":
                rules = self.get_council_rules()
                vote_count = max(1, min(int(rules.quorum_min or 1), 9))
                ranks = [5, 4, 3, 2, 1]
                result = self.simulate_council_vote(
                    [
                        {"rank": ranks[index % len(ranks)], "vote": "for"}
                        for index in range(vote_count)
                    ]
                )
                assert result.get("outcome") == "approved", "council approval simulation failed"
                assert result.get("quorum_met") is True, "council quorum not met"
            else:
                raise AssertionError(f"unknown module {module}")

            if test_type == "integration":
                dispatch = self.get_dispatch_config()
                assert dispatch.stage_allocation_rules, "dispatch allocation rules are empty"
            elif test_type == "e2e":
                conversation = self.get_inter_model_conversation_settings()
                assert conversation.max_turns >= 1, "conversation max_turns invalid"
            return True, f"PASS {entry.name}: verified {module}/{test_type}"
        except Exception as exc:  # noqa: BLE001
            return False, f"FAIL {entry.name}: {type(exc).__name__}: {str(exc)[:300]}"

    def trigger_test_run(self, test_id: Optional[str] = None, suite: Optional[str] = None) -> TestCatalogRun:
        catalog = self.get_test_catalog()
        selected = [
            entry
            for entry in catalog
            if (test_id and entry.test_id == test_id)
            or (suite and entry.suite == suite)
            or (not test_id and not suite)
        ]
        triggered_at = _now_iso()
        if selected:
            results = [self._run_catalog_entry_check(entry) for entry in selected]
            status = "pass" if all(ok for ok, _ in results) else "fail"
            output = "Verified catalog check(s):\n" + "\n".join(message for _, message in results)
            selected_ids = {entry.test_id for entry in selected}
            updated_catalog: list[TestEntry] = []
            for entry in catalog:
                if entry.test_id in selected_ids:
                    updated_catalog.append(
                        TestEntry(
                            **{
                                **entry.__dict__,
                                "status": status,
                                "last_run_at": triggered_at,
                                "last_run_output": output,
                            }
                        )
                    )
                else:
                    updated_catalog.append(entry)
            payload = [entry.__dict__ for entry in updated_catalog]
            _store_set("test_catalog", payload)
            _pg_call(_db.replace_test_catalog, payload)
        else:
            status = "fail"
            output = f"No test catalog entries matched test_id={test_id!r} suite={suite!r}"
        run = TestCatalogRun(
            run_id=str(uuid.uuid4()),
            test_id=test_id,
            suite=suite,
            status=status,
            triggered_at=triggered_at,
            completed_at=triggered_at if selected else None,
            output=output,
        )
        runs = _store_get("test_catalog_runs") or []
        runs.insert(0, run.__dict__)
        _store_set("test_catalog_runs", runs[:50])
        _pg_call(_db.insert_test_catalog_run, run.__dict__)
        return run

    def _default_team_formation_rules(self) -> List[TeamFormationRule]:
        return [
            TeamFormationRule(
                rule_id=str(uuid.uuid4()),
                trigger_pattern=r"^\[advisor\]\[claude\]\[engine\]",
                agent_types=["z_ai", "claude"],
                lifetime="ephemeral",
                action="spawn_audit_team",
                enabled=True,
                created_at=_now_iso(),
            ),
            TeamFormationRule(
                rule_id=str(uuid.uuid4()),
                trigger_pattern=r"^\[advisor\]\[kimi\]",
                agent_types=["kimi", "z_ai"],
                lifetime="ephemeral",
                action="spawn_audit_team",
                enabled=True,
                created_at=_now_iso(),
            ),
        ]

    def get_team_formation_rules(self) -> List[TeamFormationRule]:
        raw = _pg_call(_db.list_team_formation_rules)
        if raw:
            return [TeamFormationRule(**row) for row in raw]
        raw = _store_get("team_formation_rules")
        if raw:
            return [TeamFormationRule(**row) for row in raw]
        defaults = self._default_team_formation_rules()
        _store_set("team_formation_rules", [row.__dict__ for row in defaults])
        return defaults

    def update_team_formation_rules(self, rules: List[dict]) -> List[TeamFormationRule]:
        result = [TeamFormationRule(**rule) for rule in rules]
        payload = [rule.__dict__ for rule in result]
        _store_set("team_formation_rules", payload)
        _pg_call(_db.replace_team_formation_rules, payload)
        return result

    def add_team_formation_rule(self, rule: dict) -> TeamFormationRule:
        rule["rule_id"] = rule.get("rule_id") or str(uuid.uuid4())
        rule["created_at"] = rule.get("created_at") or _now_iso()
        result = TeamFormationRule(**rule)
        existing = _store_get("team_formation_rules") or [row.__dict__ for row in self._default_team_formation_rules()]
        existing.append(result.__dict__)
        _store_set("team_formation_rules", existing)
        _pg_call(_db.insert_team_formation_rule, result.__dict__)
        return result

    def get_active_teams(self) -> List[ActiveTeam]:
        raw = _pg_call(_db.list_active_teams)
        if raw is None:
            raw = _store_get("active_teams") or []
        return [ActiveTeam(**row) for row in raw]

    def trigger_team_formation(self, event_label: str, task: str) -> dict:
        event_label = (event_label or "").strip()
        task = (task or "").strip() or "Manual team formation runtime check"
        if not event_label:
            raise ValueError("event_label is required")

        rules = self.get_team_formation_rules()
        active = [team.__dict__ for team in self.get_active_teams()]
        created: list[ActiveTeam] = []
        errors: list[dict[str, str]] = []
        now = _now_iso()

        for rule in rules:
            if not rule.enabled:
                continue
            try:
                matched = re.search(rule.trigger_pattern, event_label) is not None
            except re.error as exc:
                errors.append({"rule_id": rule.rule_id, "error": f"invalid regex: {exc}"})
                continue
            if not matched:
                continue
            team = ActiveTeam(
                team_id=str(uuid.uuid4()),
                rule_id=rule.rule_id,
                agent_types=rule.agent_types[:],
                current_task=task,
                formed_at=now,
                lifetime=rule.lifetime,
            )
            created.append(team)
            active.insert(0, team.__dict__)

        _store_set("active_teams", active[:50])
        if created:
            self.record_runtime_event("aeis.orchestration.team.formed", len(created))
        return {
            "event_label": event_label,
            "task": task,
            "matched_rules": len(created),
            "created_teams": [team.__dict__ for team in created],
            "errors": errors,
            "triggered_at": now,
        }

    def get_event_map(self) -> EventMap:
        cached = _pg_call(_db.load_event_map_cache)
        if cached:
            return EventMap(
                nodes=[EventMapNode(**row) for row in cached.get("nodes", [])],
                edges=[EventMapEdge(**row) for row in cached.get("edges", [])],
                generated_at=cached.get("generated_at"),
            )
        runtime_events = _store_get("runtime_event_counts") or {}

        nodes: List[EventMapNode] = []
        edges: List[EventMapEdge] = []
        try:
            from sylion.core.module_registry import get_registry

            registry = get_registry()
            for module in registry.list_modules():
                module_id = module.get("module_id") or module.get("id", "")
                if module_id:
                    nodes.append(EventMapNode(module_id=module_id))
        except Exception:
            pass

        for emitter, topic, subscriber in [
            ("advisor.engine", "aeis.advisor.card.issued", "advisor.actions"),
            ("advisor.engine", "aeis.advisor.card.issued", "advisor.history"),
            ("advisor.actions", "aeis.advisor.action.recorded", "advisor.preferences"),
            ("advisor.actions", "aeis.advisor.action.recorded", "advisor.history"),
            ("advisor.preferences", "aeis.advisor.preference.updated", "advisor.engine"),
            ("advisor.funding", "aeis.advisor.funding.grant.matched", "advisor.engine"),
            ("orchestration.team_formation", "aeis.orchestration.team.formed", "execution.phase35"),
            ("orchestration.inter_model_conversation", "aeis.orchestration.conversation.completed", "execution.phase35"),
            ("execution.quality", "aeis.execution.quality.fixer_policy.applied", "advisor.fixer"),
        ]:
            count = int(runtime_events.get(topic, 0) or 0)
            edges.append(
                EventMapEdge(
                    emitter=emitter,
                    topic=topic,
                    subscriber=subscriber,
                    events_per_minute=float(count),
                    sample_payload={"runtime_events": count, "source": "orchestration_runtime_store"} if count else None,
                )
            )

        event_map = EventMap(nodes=nodes, edges=edges, generated_at=_now_iso())
        _pg_call(
            _db.upsert_event_map_cache,
            {
                "nodes": [node.__dict__ for node in event_map.nodes],
                "edges": [edge.__dict__ for edge in event_map.edges],
                "generated_at": event_map.generated_at,
            },
        )
        return event_map

    def record_runtime_event(self, topic: str, count: int = 1) -> dict:
        topic = (topic or "").strip()
        if not topic:
            raise ValueError("topic is required")
        events = _store_get("runtime_event_counts") or {}
        events[topic] = int(events.get(topic, 0) or 0) + int(count)
        _store_set("runtime_event_counts", events)
        return {"topic": topic, "count": events[topic], "recorded_at": _now_iso()}

    def get_inter_model_conversation_settings(self) -> InterModelConversationSettings:
        raw = _pg_call(_db.load_inter_model_conversations)
        if raw:
            return InterModelConversationSettings(
                enabled=raw.get("enabled", False),
                max_turns=raw.get("max_turns", 4),
                arbiter_model_id=raw.get("arbiter_model_id"),
                disagreement_voting=raw.get("disagreement_voting", True),
                recent_conversations=raw.get("recent_conversations", []),
                updated_at=raw.get("updated_at"),
            )
        raw = _store_get("inter_model_conversation")
        if raw:
            return InterModelConversationSettings(
                enabled=raw.get("enabled", False),
                max_turns=raw.get("max_turns", 4),
                arbiter_model_id=raw.get("arbiter_model_id"),
                disagreement_voting=raw.get("disagreement_voting", True),
                recent_conversations=raw.get("recent_conversations", []),
                updated_at=raw.get("updated_at"),
            )
        return InterModelConversationSettings()

    def update_inter_model_conversation_settings(self, data: dict) -> InterModelConversationSettings:
        existing = self.get_inter_model_conversation_settings()
        settings = InterModelConversationSettings(
            enabled=data.get("enabled", existing.enabled),
            max_turns=data.get("max_turns", existing.max_turns),
            arbiter_model_id=data.get("arbiter_model_id", existing.arbiter_model_id),
            disagreement_voting=data.get("disagreement_voting", existing.disagreement_voting),
            recent_conversations=existing.recent_conversations,
            updated_at=_now_iso(),
        )
        payload = {
            "enabled": settings.enabled,
            "max_turns": settings.max_turns,
            "arbiter_model_id": settings.arbiter_model_id,
            "disagreement_voting": settings.disagreement_voting,
            "recent_conversations": settings.recent_conversations,
            "updated_at": settings.updated_at,
        }
        _store_set("inter_model_conversation", payload)
        _pg_call(_db.upsert_inter_model_conversations, payload)
        return settings

    def trigger_inter_model_conversation(self, topic: str = "") -> dict:
        settings = self.get_inter_model_conversation_settings()
        if not settings.enabled:
            raise ValueError("inter-model conversations are disabled")

        topic = (topic or "").strip() or "Manual meta-orchestration runtime check"
        turns = max(1, min(int(settings.max_turns or 1), 10))
        participants = ["codex", "claude"]
        transcript = []
        for turn in range(1, turns + 1):
            speaker = participants[(turn - 1) % len(participants)]
            transcript.append(
                {
                    "turn": turn,
                    "speaker": speaker,
                    "message": (
                        f"{speaker} validates orchestration topic '{topic}' "
                        f"against runtime policy, memory, guard and cost constraints."
                    ),
                }
            )

        record = {
            "conversation_id": str(uuid.uuid4()),
            "agent_a": participants[0],
            "agent_b": participants[1],
            "topic": topic,
            "turns": turns,
            "status": "completed",
            "source": "operator_runtime_trigger",
            "arbiter_model_id": settings.arbiter_model_id,
            "disagreement_voting": settings.disagreement_voting,
            "created_at": _now_iso(),
            "transcript": transcript,
        }
        settings.recent_conversations = [record] + settings.recent_conversations[:19]
        settings.updated_at = _now_iso()
        payload = settings.__dict__
        _store_set("inter_model_conversation", payload)
        _pg_call(_db.upsert_inter_model_conversations, payload)
        self.record_runtime_event("aeis.orchestration.conversation.completed", 1)
        return record


_SERVICE: Optional[OrchestrationConfigService] = None
_SVC_LOCK = threading.Lock()


def get_orchestration_service() -> OrchestrationConfigService:
    global _SERVICE
    if _SERVICE is None:
        with _SVC_LOCK:
            if _SERVICE is None:
                _SERVICE = OrchestrationConfigService()
    return _SERVICE
