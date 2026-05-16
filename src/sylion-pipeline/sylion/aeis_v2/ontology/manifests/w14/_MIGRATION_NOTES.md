# W14 -> W15 Migration Notes

Phase 0 keeps W14 runtime untouched and defines declarative W15 wrappers for all 25 testing ontology objects.
The W15 primary key is generated as `id`; legacy SQLite identifiers are preserved in dedicated column `legacy_w14_id` on every object.
System columns `created_at` and `updated_at` are reserved by the compiler and should receive migrated W14 timestamps where available.

## Common Mapping Rules

- Scalar fields used in filters, joins, status transitions, or dashboards were lifted into `dedicated_columns`.
- Former `*_id` foreign keys from SQLite were mapped into `relations`; do not create parallel dedicated `*_id` columns.
- Lists, nested dicts, payloads, approval blobs, evidence maps, and long free-form structures move to `extension` JSONB.
- Source `created_at`, `approved_at`, `completed_at`, `merged_at`, `discarded_at`, `promoted_at` and similar timestamps should migrate into system audit timestamps or stay in `extension` when multiple domain timestamps must be preserved.

## Per Object

### w14_requirement
SQLite: `req_id`, `source`, `source_ref`, `criticality`, `test_required`, `description`, `created_at`.
W15: `legacy_w14_id`, `source`, `source_ref`, `criticality`, `test_required`, `description`; `created_at` -> system column.

### w14_test_charter
SQLite: `charter_id`, `project_id`, `idea_id`, versions, `status`, `hg_ticket_id`, `council_session_id`, `scope`, `required_*`, `release_blockers`, `auto_repair_policy`, `approval`, timestamps.
W15: dedicated versions/status/tickets, relations `project`, `idea`; policy arrays/maps and approval blobs -> `extension`.

### w14_test_plan
SQLite: `plan_id`, `charter_id`, `suites`, `execution_order`, `parallelization_groups`, `estimated_duration_s`, `created_at`.
W15: dedicated duration plus counts, relation `charter`; suite/order/group lists -> `extension`.

### w14_test_suite
SQLite: `suite_id`, `plan_id`, `name`, `test_class`, `case_ids`, `tags`, `enabled`.
W15: dedicated name/class/enabled/count, relation `plan`; case IDs and tags -> `extension`.

### w14_test_case
SQLite: `case_id`, `requirement_id`, `suite_id`, `persona_id`, `real_example_id`, `evaluator`, `enabled`, payloads, tags.
W15: dedicated evaluator/enabled/real example, relations `requirement`, `suite`, `persona`; payloads/tags -> `extension`.

### w14_evaluation_suite
SQLite: `suite_id`, target fields, `test_case_ids`, `evaluators`, `metrics`, `baseline_run_id`, `created_at`.
W15: dedicated target fields and counts, relation `baseline_run`; ID lists and metric/evaluator arrays -> `extension`.

### w14_test_run
SQLite: `run_id`, `suite_id`, `case_id`, `branch_id`, `charter_id`, `status`, timings, `cost_usd`, `evidence_pack_id`, `trace_id`, `result_payload`.
W15: dedicated status/duration/cost/trace/evidence, relations `suite`, `case`, `branch`, `charter`; result payload -> `extension`.

### w14_regression_run
SQLite: `regression_id`, `finding_id`, `pre_fix_run_id`, `post_fix_run_id`, `neighbor_test_run_ids`, `status`, timestamps.
W15: dedicated status, relations to `finding`, `pre_fix_run`, `post_fix_run`; neighbor run list -> `extension`.

### w14_finding
SQLite: `finding_id`, severities/statuses, `requirement_id`, `test_run_id`, `guardian_alert_id`, `title`, `description`, `discovered_by`, `ticket_id`, timestamps.
W15: dedicated severity/status/D-level/title/discovered_by/ticket, relations to linked objects; description and closure detail -> `extension`.

### w14_patch_proposal
SQLite: `proposal_id`, `finding_id`, `branch_id`, `diff_text`, `files_touched`, diff metrics, `risk_assessment`, `tests_to_run`, `status`, `proposed_by`, `created_at`.
W15: dedicated status/author/diff metrics/file count, relations `finding`, `branch`; diff text, file list, risk, tests -> `extension`.

### w14_repair_attempt
SQLite: `attempt_id`, `finding_id`, `n`, `patch_proposal_id`, `r_phase`, `result`, counts, cost/time, timestamps.
W15: dedicated attempt number, phase, result, counts, cost/time; relations `finding`, `patch_proposal`; extra loop context -> `extension`.

### w14_loop_report
SQLite: `report_id`, `finding_id`, `loop_type`, `attempts_n`, `similarity_score`, `suspected_root_cause`, `blocked_actions`, `required_decision`, `created_at`.
W15: dedicated loop type/count/score, relation `finding`; root causes, blocked actions, required decision -> `extension`.

### w14_guardian_alert
SQLite: `alert_id`, `guardian`, `severity`, `source_event_id`, `evidence_link`, `finding_id`, `reason`, `acknowledged`, `created_at`.
W15: dedicated guardian/severity/source/ack/reason, relation `finding`; evidence link -> `extension`.

### w14_simulation_contract
SQLite: `contract_id`, `simulation_id`, `branch_id`, `source_project_id`, versions, `test_charter_id`, `isolation`, `model_mode`, `persistence`, `safety`, `created_at`.
W15: dedicated simulation/project/version refs, relations `branch`, `test_charter`; safety and runtime blobs -> `extension`.

### w14_simulation_branch
SQLite: `sim_branch_id`, `parent_branch_id`, `contract_id`, `state`, `discard_reason`, `snapshot_db_path`, timestamps.
W15: dedicated state/reason/path, relations `parent_branch`, `contract`; discard timing -> `extension` or audit timestamps.

### w14_simulation_evidence
SQLite: `evidence_id`, `simulation_id`, `sim_branch_id`, `trace_id`, `layer_executed`, `screenshots_uri`, `event_log`, `branch_snapshot_hash`, `evaluator_outputs`, `created_at`.
W15: dedicated simulation/trace/layer/hash, relation `sim_branch`; screenshots, logs, evaluator outputs -> `extension`.

### w14_human_persona
SQLite: `persona_id`, `name`, `capability_level`, domain list, risk metrics, `dynamic_state`, `behavior_modifiers`, `created_at`.
W15: dedicated identity and numeric/risk traits; expertise domains and mutable state -> `extension`.

### w14_human_scenario
SQLite: `scenario_id`, `persona_id`, `domain`, workflow/decision arrays, success criteria, `comprehension_check`, `difficulty`, `created_at`.
W15: dedicated domain/difficulty/counts, relation `persona`; steps, criteria, comprehension payload -> `extension`.

### w14_human_error_injection
SQLite: `injection_id`, `error_class`, `target_action`, `timing`, `context`, expected responses, D-level fields, `created_at`.
W15: dedicated class/action/timing/context/D-levels; expected response array -> `extension`.

### w14_human_decision_trace
SQLite: `trace_id`, `persona_id`, `scenario_id`, `simulation_id`, `decisions_made`, `visible_state_snapshot`, `perception_model`, `behavior_metrics`, `created_at`.
W15: dedicated simulation ref and decision count, relations `persona`, `scenario`; decision log and models -> `extension`.

### w14_human_near_miss
SQLite: `near_miss_id`, `scenario_id`, `error_injection_id`, `blocked_successfully`, `operator_message_quality_score`, `future_risk`, `suggested_ui_improvement`, `created_at`.
W15: dedicated block/risk/score/suggestion, relations `scenario`, `error_injection`; supporting UX evidence -> `extension`.

### w14_branch
SQLite: `branch_id`, `branch_type`, `parent_branch_id`, `project_id`, versions, `state`, `created_by`, timestamps.
W15: dedicated type/state/project/version/creator, legacy parent stored as `parent_branch_ref`; branch-local metadata -> `extension`.

### w14_release_candidate
SQLite: `rc_id`, `branch_id`, `project_id`, `test_run_summary`, `unresolved_findings`, `evidence_pack_id`, `gate_status`, `blockers`, `promoted_at`.
W15: dedicated project/gate/evidence/counts, relation `branch`; test summary and blocker lists -> `extension`.

### w14_release_decision
SQLite: `decision_id`, `rc_id`, `charter_id`, `hg_ticket_id`, `council_session_id`, `outcome`, `rollback_plan`, `signatures`, `created_at`.
W15: dedicated ticket/session/outcome/signature count, relations `release_candidate`, `charter`; rollback and signatures -> `extension`.

### w14_release_readiness_report
SQLite: `report_id`, `rc_id`, checklist/blocker/warning/recommendation collections, cost/latency summaries, `evidence_tier_used`, `human_comprehension_score`, `created_at`.
W15: dedicated evidence tier, comprehension, aggregate counts, relation `release_candidate`; all report payloads -> `extension`.
