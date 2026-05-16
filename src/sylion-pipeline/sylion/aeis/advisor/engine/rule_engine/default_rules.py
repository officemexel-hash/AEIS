"""Default rule definitions seeded on first run."""

from __future__ import annotations

import logging
from typing import Iterable

from sylion.aeis.advisor.engine._db import upsert_rule
from sylion.aeis.advisor.engine._models import Rule

log = logging.getLogger(__name__)


DEFAULT_RULES: list[dict] = [
    {
        "rule_id": "idea_intake_initial_guidance",
        "description": "Wystaw karte prowadzenia po przyjeciu nowego pomyslu",
        "hook_event_pattern": "aeis.idea.intake.completed",
        "precondition": {},
        "recommendation_type": "REC_TYPE_IDEA_INTAKE_GUIDANCE",
        "default_d_level": "D0",
    },
    {
        "rule_id": "council_size_outside_preference",
        "description": "Zaproponuj korekte skladu Rady, gdy propozycja odbiega od preferencji",
        "hook_event_pattern": "aeis.council.formation_requested",
        "precondition": {"field": "_match_council_preference", "op": "==", "value": False},
        "recommendation_type": "REC_TYPE_COUNCIL_FORMATION",
        "default_d_level": "D2",
    },
    {
        "rule_id": "production_deploy_blocked_no_sot",
        "description": "Zablokuj deploy produkcyjny, gdy Source of Truth nie ma akceptacji",
        "hook_event_pattern": "aeis.production.deploy_requested",
        "precondition": {"field": "payload.sot_approved", "op": "==", "value": False},
        "recommendation_type": "REC_TYPE_BLOCK_PRODUCTION_DEPLOY",
        "default_d_level": "D5",
    },
    {
        "rule_id": "budget_threshold_warning",
        "description": "Po przekroczeniu progu budzetu zaproponuj ograniczenie kosztow",
        "hook_event_pattern": "aeis.system.budget_threshold_crossed",
        "precondition": {"field": "payload.utilization_pct", "op": ">", "value": 80},
        "recommendation_type": "REC_TYPE_REDUCE_PREMIUM_USAGE",
        "default_d_level": "D2",
    },
    {
        "rule_id": "vps_scaling_to_d3",
        "description": "Dodanie lub skalowanie VPS jest D3+ i wymaga Evidence Pack",
        "hook_event_pattern": "aeis.system.vps_scaling_requested",
        "precondition": {
            "or": [
                {"field": "payload.action", "op": "==", "value": "add_env"},
                {"field": "payload.action", "op": "==", "value": "scale_up"},
                {"field": "payload.action", "op": "==", "value": "parallel_split"},
            ]
        },
        "recommendation_type": "REC_TYPE_VPS_SCALING",
        "default_d_level": "D3",
    },
    {
        "rule_id": "human_gate_batch_suggestion",
        "description": "Gdy rosnie liczba HumanGate, zaproponuj przeglad zbiorczy",
        "hook_event_pattern": "aeis.human_gate.ticket_pending",
        "precondition": {"field": "payload.pending_count_user", "op": ">=", "value": 5},
        "recommendation_type": "REC_TYPE_BATCH_HUMAN_GATE_TICKETS",
        "default_d_level": "D1",
    },
    {
        "rule_id": "human_gate_single_ticket_review",
        "description": "Pokaz pierwszy oczekujacy HumanGate zamiast czekac na kolejke",
        "hook_event_pattern": "aeis.human_gate.ticket_pending",
        "precondition": {
            "and": [
                {"field": "payload.pending_count_user", "op": ">=", "value": 1},
                {"field": "payload.pending_count_user", "op": "<", "value": 5},
            ]
        },
        "recommendation_type": "REC_TYPE_HUMAN_GATE_BATCH",
        "default_d_level": "D1",
    },
    {
        "rule_id": "subscription_break_even_detected",
        "description": "Gdy kalkulacja ROI wykryje break-even, zaproponuj plan",
        "hook_event_pattern": "aeis.advisor.subscription.roi_computed",
        "precondition": {"field": "payload.break_even_days", "op": "<=", "value": 30},
        "recommendation_type": "REC_TYPE_PURCHASE_PLAN",
        "default_d_level": "D3",
    },
    {
        "rule_id": "model_setup_first_run",
        "description": "Prowadzenie konfiguracji modeli przy pierwszym uruchomieniu",
        "hook_event_pattern": "aeis.system.model_setup_requested",
        "precondition": {"field": "payload.setup_context", "op": "==", "value": "first_run"},
        "recommendation_type": "REC_TYPE_MODEL_SETUP",
        "default_d_level": "D1",
    },
    {
        "rule_id": "api_provider_setup_added",
        "description": "Pokaz wskazowki po dodaniu klucza providera przez operatora",
        "hook_event_pattern": "aeis.system.api_provider_setup_requested",
        "precondition": {"field": "payload.action", "op": "==", "value": "add"},
        "recommendation_type": "REC_TYPE_API_PROVIDER_SETUP",
        "default_d_level": "D1",
    },
    {
        "rule_id": "budget_config_change",
        "description": "Pokaz reakcje doradcy na zmiane konfiguracji budzetu",
        "hook_event_pattern": "aeis.system.budget_config_requested",
        "precondition": {},
        "recommendation_type": "REC_TYPE_BUDGET_CONFIG",
        "default_d_level": "D2",
    },
    {
        "rule_id": "sot_model_selection_oversized",
        "description": "Zaproponuj tanszy model, gdy okno kontekstu jest nadmiarowe",
        "hook_event_pattern": "aeis.idea.sot_model_selection_requested",
        "precondition": {"field": "payload.context_tokens_estimate", "op": ">", "value": 100000},
        "recommendation_type": "REC_TYPE_SOT_MODEL_SELECTION",
        "default_d_level": "D1",
    },
    {
        "rule_id": "autonomy_policy_change_audit",
        "description": "Zmiana polityki autonomii jest twarda preferencja i zawsze D3+",
        "hook_event_pattern": "aeis.system.autonomy_policy_change_requested",
        "precondition": {},
        "recommendation_type": "REC_TYPE_AUTONOMY_POLICY",
        "default_d_level": "D3",
    },
    {
        "rule_id": "sot_drafted_quality_review",
        "description": "Zaproponuj przeglad krytyka dla dlugich szkicow SoT",
        "hook_event_pattern": "aeis.idea.sot_drafted",
        "precondition": {"field": "payload.word_count", "op": ">", "value": 1000},
        "recommendation_type": "REC_TYPE_SOT_DRAFTING",
        "default_d_level": "D1",
    },
    {
        "rule_id": "masterplan_oversized",
        "description": "Zaproponuj podzial, gdy Masterplan jest zbyt duzy",
        "hook_event_pattern": "aeis.masterplan.created",
        "precondition": {"field": "payload.total_loc_estimate", "op": ">", "value": 1000},
        "recommendation_type": "REC_TYPE_MASTERPLAN_GUIDANCE",
        "default_d_level": "D2",
    },
    {
        "rule_id": "runtime_topology_review",
        "description": "Pokaz reakcje doradcy na zmiane topologii runtime",
        "hook_event_pattern": "aeis.system.runtime_topology_change_requested",
        "precondition": {},
        "recommendation_type": "REC_TYPE_RUNTIME_TOPOLOGY",
        "default_d_level": "D2",
    },
    {
        "rule_id": "skill_selection_missing_critic",
        "description": "Ostrzez, gdy projekt produkcyjny nie ma skillu krytyka",
        "hook_event_pattern": "aeis.system.skill_selection_requested",
        "precondition": {"field": "payload.has_critic", "op": "==", "value": False},
        "recommendation_type": "REC_TYPE_SKILL_SELECTION",
        "default_d_level": "D2",
    },
    {
        "rule_id": "skill_selection_runtime_review",
        "description": "Pokaz skille runtime sugerowane przez pomysl lub analize zalacznikow",
        "hook_event_pattern": "aeis.system.skill_selection_requested",
        "precondition": {"field": "payload.suggested_skills_count", "op": ">", "value": 0},
        "recommendation_type": "REC_TYPE_SKILL_SELECTION",
        "default_d_level": "D1",
    },
    {
        "rule_id": "testing_started_review",
        "description": "Prowadzenie po starcie testow",
        "hook_event_pattern": "aeis.testing.started",
        "precondition": {},
        "recommendation_type": "REC_TYPE_TESTING_GUIDANCE",
        "default_d_level": "D0",
    },
    {
        "rule_id": "final_approval_summary",
        "description": "Karta podsumowania przy prosbie o finalna akceptacje",
        "hook_event_pattern": "aeis.final_approval.requested",
        "precondition": {},
        "recommendation_type": "REC_TYPE_FINAL_APPROVAL",
        "default_d_level": "D3",
    },
]


def seed_default_rules(rules: Iterable[dict] | None = None) -> int:
    """Insert default rules; idempotent. Returns count of rules persisted."""
    rules_iter = list(rules) if rules is not None else DEFAULT_RULES
    persisted = 0
    for r in rules_iter:
        upsert_rule(
            Rule(
                rule_id=r["rule_id"],
                description=r["description"],
                hook_event_pattern=r["hook_event_pattern"],
                precondition=r["precondition"],
                recommendation_type=r["recommendation_type"],
                default_d_level=r["default_d_level"],
                is_active=r.get("is_active", True),
                version=r.get("version", 1),
            )
        )
        persisted += 1
    log.info("seeded %d default rules", persisted)
    return persisted
