"""W14 Human Scenarios catalog — 50 scenarios across 10 domains.

Returns ready-to-use HumanScenario instances for common workflows.
Used by E11 demo projects and by Test Center UI for one-click runs.

The library is organized by ``domain`` so the brief's "50 scenarios per
domain" requirement is met progressively: ``scenarios_for_domain(d)``
returns at least 5 scenarios per canonical domain, and
``starter_scenarios()`` returns a curated 10-scenario seed set for
backwards compatibility with E3-E5 callers.
"""
from __future__ import annotations

from sylion.aeis.testing.ontology.objects import HumanScenario


CANONICAL_DOMAINS: tuple[str, ...] = (
    "hmep",
    "advisor",
    "compliance",
    "release",
    "exploration",
    "mobile",
    "incident",
    "funding",
    "marketplace",
    "industrial_iot",
)


def _scn(persona_id, name, domain, steps, decisions, criteria, comp_q,
         difficulty="medium"):
    # Ensure validator-compliant persona_id prefix.
    if not persona_id.startswith("persona_"):
        persona_id = f"persona_{persona_id}"
    # Sanitize: scenarios.py builds steps/decisions from caller strings
    # passed as Python literals; coerce each entry to a {key: str} dict
    # so downstream consumers never see arbitrary objects (Kimi E8 #5).
    safe_steps = [{"step": str(s)[:200]} for s in steps]
    safe_decisions = [{"d": str(d)[:200]} for d in decisions]
    safe_criteria = [str(c)[:200] for c in criteria]
    return HumanScenario(
        persona_id=persona_id,
        domain=domain,
        workflow_steps=safe_steps,
        decision_points=safe_decisions,
        success_criteria=safe_criteria,
        comprehension_check={"q": str(comp_q)[:500]},
        difficulty=difficulty,
    )


# ---------------------------------------------------------------------------
# Per-domain scenario builders (5 scenarios each = 50 total)
# ---------------------------------------------------------------------------


def _hmep_scenarios() -> list[HumanScenario]:
    return [
        _scn("operator_beginner", "First HMEP project", "hmep",
             ["intake_idea", "review_sot", "approve_charter",
              "monitor_execution", "review_release_candidate"],
             ["approve_charter_d3", "approve_release_d3"],
             ["charter_approved", "release_promoted"],
             "What is an Evidence Pack?", "easy"),
        _scn("operator_power_user", "HMEP retrospective + lessons", "hmep",
             ["pull_release_evidence", "compare_lessons", "tag_anti_patterns"],
             ["accept_lesson", "reject_lesson"],
             ["lessons_indexed", "anti_patterns_added"],
             "Why do lessons feed back into Masterplan?"),
        _scn("dev_engineer", "HMEP charter scope contract review", "hmep",
             ["review_required_test_classes", "review_release_blockers",
              "diff_against_previous_charter"],
             ["accept_charter", "request_changes"],
             ["charter_validated"],
             "What does T9 (REGRESSION) cover?"),
        _scn("qa_lead", "HMEP gate-readiness review", "hmep",
             ["read_charter", "run_dryrun_release_rail", "report_blockers"],
             ["block_or_pass"],
             ["release_rail_dryrun_complete"],
             "Which 6 production_ready items are required?", "hard"),
        _scn("auditor", "HMEP audit trail completeness", "hmep",
             ["traverse_intent_to_release", "verify_signatures",
              "verify_evidence_chain"],
             ["accept_audit", "flag_gap"],
             ["audit_chain_intact"],
             "What is a TraceCompletenessGuardian alert?", "hard"),
    ]


def _advisor_scenarios() -> list[HumanScenario]:
    return [
        _scn("operator_power_user", "Approve 5 D2 decisions in batch", "advisor",
             ["open_advisor", "filter_d2", "review_card_x5", "approve_all"],
             ["batch_approve_d2"],
             ["all_5_approved", "no_d3_in_batch"],
             "Why is D3+ batching forbidden?"),
        _scn("operator_overloaded", "12 pending decisions end of shift", "advisor",
             ["see_queue", "open_first", "context_switch", "resume_decision"],
             ["approve_or_defer_each_of_12"],
             ["no_d3_approved_without_evidence", "defers_when_uncertain"],
             "Why does cognitive overload increase risk?", "hard"),
        _scn("operator_beginner", "First advisor card review", "advisor",
             ["read_card", "click_evidence_link", "approve_or_defer"],
             ["approve_d1", "defer_d2"],
             ["correct_action_for_d_level"],
             "What does D-level mean?", "easy"),
        _scn("auditor", "Audit advisor decisions for last hour", "advisor",
             ["filter_last_hour", "verify_each_signature",
              "spot_check_evidence"],
             ["accept_audit", "raise_flag"],
             ["all_decisions_signed_within_sla"],
             "What is the SLA for D3 in advisor?", "hard"),
        _scn("admin_overconfident", "Admin overrides advisor block", "advisor",
             ["see_block", "click_override", "see_council_required"],
             ["respect_or_attempt_bypass"],
             ["bypass_attempt_logged"],
             "When is admin override allowed?", "hard"),
    ]


def _compliance_scenarios() -> list[HumanScenario]:
    return [
        _scn("auditor", "Verify audit chain for release X", "compliance",
             ["open_audit", "navigate_to_release", "verify_evidence_chain",
              "verify_council_signatures", "verify_sentinel_signoffs"],
             ["accept_evidence_complete", "flag_evidence_gap"],
             ["audit_chain_intact", "evidence_pack_validated"],
             "What does fidelity_score 1.0 mean?"),
        _scn("compliance_officer", "GDPR evidence review", "compliance",
             ["review_data_subject_rights", "verify_redaction",
              "approve_or_demand_revision"],
             ["accept_pii_redacted", "demand_re_redaction"],
             ["compliance_attestation_signed"],
             "What is PII Guardian?"),
        _scn("compliance_officer", "Quarterly retention attestation", "compliance",
             ["pull_retention_report", "verify_deletion_log",
              "attest_no_orphan_pii"],
             ["sign_or_revise"],
             ["attestation_archived"],
             "How long are evidence packs retained?", "hard"),
        _scn("security_analyst", "Threat model review", "compliance",
             ["read_threat_model", "compare_against_runtime",
              "flag_drift"],
             ["accept_or_demand_update"],
             ["threat_model_aligned_with_runtime"],
             "What does LLM Drift Guardian alert on?", "hard"),
        _scn("auditor", "Cross-project audit chain integrity", "compliance",
             ["select_3_projects", "verify_each_chain",
              "compare_signatures"],
             ["pass_all", "flag_one_for_review"],
             ["all_three_chains_validated"],
             "Why is audit_chain_intact a release blocker?", "hard"),
    ]


def _release_scenarios() -> list[HumanScenario]:
    return [
        _scn("admin_overconfident", "Attempt D5 release solo", "release",
             ["open_release_candidate", "click_promote_to_production",
              "see_council_required_block"],
             ["respect_block_or_attempt_bypass"],
             ["block_respected_or_audit_attempt_logged"],
             "Why does D5 require Council?", "hard"),
        _scn("qa_lead", "Block release on regression flake", "release",
             ["read_regression_report", "investigate_flake",
              "demand_repair_session"],
             ["block_release", "request_loopback_to_repair"],
             ["release_blocked_pending_regression"],
             "What does regression_passed mean?"),
        _scn("operator_power_user", "Promote release after charter approve",
             "release",
             ["verify_charter_approved", "verify_evidence_pack_validated",
              "click_promote_rc"],
             ["promote_or_defer_to_human_gate"],
             ["rc_promoted_with_evidence"],
             "What is the difference between RC and production_ready?"),
        _scn("incident_responder", "Emergency rollback during release", "release",
             ["see_p0_alert", "trigger_rollback",
              "verify_state_restored"],
             ["rollback_within_15min"],
             ["rollback_initiated_within_sla"],
             "What gate types apply to rollback?", "hard"),
        _scn("auditor", "Post-release attestation review", "release",
             ["pull_release_decision", "verify_signatures",
              "verify_rollback_plan_attached"],
             ["accept_or_flag"],
             ["release_decision_complete"],
             "Why is rollback_plan mandatory in ReleaseDecision?", "hard"),
    ]


def _exploration_scenarios() -> list[HumanScenario]:
    return [
        _scn("viewer_curious", "Try unauthorized action", "exploration",
             ["browse_dashboard", "click_approve_button", "see_rbac_block"],
             ["accept_block_or_complain"],
             ["rbac_block_visible", "no_action_executed"],
             "What does viewer role mean?", "easy"),
        _scn("viewer_curious", "Wander through audit ledger", "exploration",
             ["open_audit_ledger", "filter_by_actor",
              "discover_no_pii_visible"],
             ["accept_or_request_access"],
             ["pii_redaction_intact"],
             "Why does audit ledger redact PII?", "easy"),
        _scn("operator_beginner", "Learn dashboard layout", "exploration",
             ["open_each_panel", "read_tooltips", "click_help"],
             ["complete_tour", "skip_tour"],
             ["tour_completed_or_dismissed"],
             "Where do P0 alerts appear?", "easy"),
        _scn("dev_engineer", "Inspect contract registry", "exploration",
             ["open_contracts_page", "filter_by_module",
              "diff_against_previous_version"],
             ["accept_or_propose_change"],
             ["contracts_diffed"],
             "What is a ChangeProposal?"),
        _scn("data_scientist", "Sample dashboard for analytics", "exploration",
             ["open_evidence_panel", "export_metrics",
              "verify_no_pii_in_export"],
             ["accept_or_redact_more"],
             ["safe_export_validated"],
             "What does evidence_tier H2 vs H4 differ?"),
    ]


def _mobile_scenarios() -> list[HumanScenario]:
    return [
        _scn("mobile_first_operator", "Quick mobile approval during meeting",
             "mobile",
             ["receive_push", "open_card", "review_summary", "approve_d2"],
             ["approve_or_defer_to_desktop"],
             ["d2_approved_correctly", "d3_deferred_to_desktop"],
             "Why are D3+ blocked on mobile?"),
        _scn("field_inspector", "On-site evidence capture", "mobile",
             ["take_photo", "geo_tag", "attach_to_finding"],
             ["submit_or_retake"],
             ["evidence_attached_with_geo"],
             "What evidence_tier does an on-site photo earn?"),
        _scn("incident_responder", "Mobile alert triage", "mobile",
             ["read_p0_summary", "open_runbook",
              "trigger_pager_for_oncall"],
             ["page_or_self_handle"],
             ["correct_runbook_invoked"],
             "What is the mobile rollback policy?", "hard"),
        _scn("mobile_first_operator", "Lost connectivity mid-approval", "mobile",
             ["click_approve", "see_offline_indicator",
              "wait_for_reconnect"],
             ["resume_or_abandon"],
             ["no_double_submit"],
             "Why is double-submit guarded server-side?"),
        _scn("field_inspector", "Photo evidence corruption check", "mobile",
             ["upload_photo", "see_hash_mismatch_warning",
              "retake_or_explain"],
             ["accept_warning", "override_with_rationale"],
             ["evidence_hash_match"],
             "Why are artifact_hashes_present required?", "hard"),
    ]


def _incident_scenarios() -> list[HumanScenario]:
    return [
        _scn("incident_responder", "P0 production rollback", "incident",
             ["see_p0_alert", "open_release_candidate",
              "trigger_rollback", "verify_state"],
             ["rollback_within_15min"],
             ["rollback_initiated", "audit_recorded"],
             "What is the rollback SLA for P0?", "hard"),
        _scn("auditor", "Investigate Loop Governor escalation", "incident",
             ["open_loop_report", "review_attempts", "review_root_cause",
              "decide_human_action"],
             ["accept_known_issue", "change_masterplan",
              "abandon", "reassign"],
             ["decision_recorded_in_audit"],
             "What does close_loop_as_blocked do?", "hard"),
        _scn("security_analyst", "PII leak investigation", "incident",
             ["read_pii_alert", "trace_origin", "redact_in_situ",
              "open_remediation_ticket"],
             ["confirm_or_escalate"],
             ["pii_redacted_and_logged"],
             "What is the PII Guardian alert payload?", "hard"),
        _scn("incident_responder", "Council emergency convene for D5", "incident",
             ["open_emergency_session", "vote", "sign_decision"],
             ["approve_or_defer"],
             ["council_session_recorded"],
             "What is the Council emergency quorum?", "hard"),
        _scn("dev_engineer", "Loop Governor hits max attempts", "incident",
             ["read_loop_report", "diff_attempts",
              "propose_root_cause_fix"],
             ["request_human_gate", "reassign"],
             ["loop_report_closed_with_decision"],
             "What does max_auto_fix_attempts_per_finding=2 mean?", "hard"),
    ]


def _funding_scenarios() -> list[HumanScenario]:
    return [
        _scn("operator_power_user", "Funding application submission", "funding",
             ["review_grant_eligibility", "fill_application",
              "attach_evidence", "submit_to_external_gate"],
             ["accept_or_revise_application"],
             ["application_validated", "external_gate_consulted"],
             "What is required for external_action gate?"),
        _scn("external_partner", "Submit grant before deadline", "funding",
             ["review_requirements", "fill_form_quickly",
              "click_submit"],
             ["submit_or_abandon"],
             ["submission_within_deadline"],
             "Why does the system warn about expired signatures?"),
        _scn("compliance_officer", "Verify grant attestation", "funding",
             ["pull_attestation_pack", "verify_signatures",
              "approve_or_revise"],
             ["sign_attestation", "revise"],
             ["compliance_attestation_signed"],
             "What is in a grant Evidence Pack?", "hard"),
        _scn("auditor", "Post-grant audit chain", "funding",
             ["walk_audit_chain", "verify_signature_each_step"],
             ["accept_or_flag"],
             ["audit_chain_intact"],
             "Why is signature verification mandatory?"),
        _scn("external_partner", "Oversized attachment reject", "funding",
             ["upload_file", "see_size_limit_warning", "compress_or_split"],
             ["accept_or_request_exception"],
             ["upload_within_limit"],
             "Why is there an attachment size limit?", "easy"),
    ]


def _marketplace_scenarios() -> list[HumanScenario]:
    return [
        _scn("dev_engineer", "Skill upload + sandbox exec", "marketplace",
             ["upload_skill_yaml", "sandbox_run", "see_dryrun_results"],
             ["publish_or_revise"],
             ["sandbox_pass"],
             "What does the sandbox isolate?"),
        _scn("security_analyst", "Malicious skill detection", "marketplace",
             ["read_skill_manifest", "scan_dependencies",
              "block_or_quarantine"],
             ["block_publication", "quarantine"],
             ["malicious_skill_blocked"],
             "What checks does the cost_sentinel run on a skill?", "hard"),
        _scn("data_scientist", "Skill performance audit", "marketplace",
             ["pull_skill_metrics", "compare_against_baseline",
              "open_drift_report"],
             ["accept_or_request_revision"],
             ["drift_within_5pct"],
             "When does LLM Drift Guardian trigger?"),
        _scn("admin_overconfident", "Force publish without sandbox", "marketplace",
             ["click_publish", "see_sandbox_required_block"],
             ["respect_or_force"],
             ["block_respected_or_audit_logged"],
             "Why is sandbox required before publish?", "hard"),
        _scn("compliance_officer", "License attestation review", "marketplace",
             ["read_license", "verify_attribution",
              "approve_or_request_clarification"],
             ["accept_license", "request_clarification"],
             ["license_attestation_signed"],
             "What licenses are auto-rejected?"),
    ]


def _industrial_iot_scenarios() -> list[HumanScenario]:
    return [
        _scn("operator_power_user", "Industrial cabinet commissioning",
             "industrial_iot",
             ["upload_cabinet_id", "verify_emergency_stop",
              "approve_or_block"],
             ["approve_d4", "block_pending_safety"],
             ["safety_certified"],
             "Why does industrial_iot require D4+?", "hard"),
        _scn("field_inspector", "On-site safety walk-through", "industrial_iot",
             ["walk_perimeter", "verify_e_stops",
              "photograph_label_plates"],
             ["pass_walkthrough", "raise_finding"],
             ["walkthrough_signed"],
             "What does emergency_stop verification cover?"),
        _scn("security_analyst", "Industrial network audit", "industrial_iot",
             ["scan_network", "verify_segmentation",
              "report_findings"],
             ["accept_or_open_finding"],
             ["network_segmented"],
             "Why is real_device_allowed=True D5+?", "hard"),
        _scn("incident_responder", "Cabinet override during incident",
             "industrial_iot",
             ["see_alert", "trigger_safe_state",
              "log_override_with_council"],
             ["safe_state_or_full_stop"],
             ["override_logged"],
             "When is unsafe_override permitted?", "hard"),
        _scn("qa_lead", "Cabinet release readiness review", "industrial_iot",
             ["pull_test_runs", "verify_human_like_passed",
              "verify_release_rail"],
             ["pass_or_block"],
             ["release_rail_clean"],
             "What is human_like_passed?", "hard"),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_DOMAIN_BUILDERS = {
    "hmep": _hmep_scenarios,
    "advisor": _advisor_scenarios,
    "compliance": _compliance_scenarios,
    "release": _release_scenarios,
    "exploration": _exploration_scenarios,
    "mobile": _mobile_scenarios,
    "incident": _incident_scenarios,
    "funding": _funding_scenarios,
    "marketplace": _marketplace_scenarios,
    "industrial_iot": _industrial_iot_scenarios,
}


def scenarios_for_domain(domain: str) -> list[HumanScenario]:
    """Return all canonical scenarios for a domain (typically 5)."""
    builder = _DOMAIN_BUILDERS.get(domain)
    if builder is None:
        return []
    return builder()


def all_scenarios() -> list[HumanScenario]:
    """Return the full 50-scenario catalog (10 domains x 5 each)."""
    out: list[HumanScenario] = []
    for builder in _DOMAIN_BUILDERS.values():
        out.extend(builder())
    return out


def starter_scenarios() -> list[HumanScenario]:
    """Return a curated 10-scenario seed (1 per canonical domain).

    Backward-compat alias for E3-E5 callers; new code should reach for
    ``all_scenarios()`` or ``scenarios_for_domain(d)`` directly.
    """
    return [builder()[0] for builder in _DOMAIN_BUILDERS.values()]


__all__ = [
    "all_scenarios",
    "scenarios_for_domain",
    "starter_scenarios",
    "CANONICAL_DOMAINS",
]
