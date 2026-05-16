# Audit Chains Catalogue — SYLION AEIS v2

> Kompletna mapa wszystkich chained JSONL audit logs.
> Stan na 2026-04-28 — 17 chains across W7 / W11 / W14 / W15 / W16 / W17 / W18 / W19 / GDPR / Replay / governance.
> Format zgodny z `aeis_v2/audit_chain/chain.py` (commit `ac97e957`):
> ```json
> {"prev_hash": "<16hex>", "content": {...}, "content_hash": "<16hex>"}
> ```
> Każda linia weryfikowalna przez `sylion.aeis_v2.audit_chain.verify_chain(path)`.

---

## Master table

| # | Plik (logs/v2/) | Producent | Kind values | Konsumenci | Retention | RBAC |
|---|------------------|-----------|-------------|-----------|-----------|------|
| 1 | `gdpr_dsr.jsonl` | `DsrService` (`bc68430f`) | brak (action='access' / 'rectification' / 'erasure' / 'portability') | DPO, `metrics_v2`, `audit_chain_monitor` | 90d (per `AuditRotator`) | auditor / owner |
| 2 | `gdpr_hard_purge.jsonl` | `HardPurgeCron` (`ce336270`) | `gdpr.hard_purge.row`, `gdpr.hard_purge.run` | DPO | 90d | auditor / owner |
| 3 | `replay_fork.jsonl` | `ReplayFork.run` (`82b0af48`) | `replay_fork.run` | operator, `metrics_v2` | 30d | operator+ |
| 4 | `council_wedge.jsonl` | `evaluate_match_with_council` (`49288143`) | `council_wedge.decision` | operator, council widget | 90d | operator+ |
| 5 | `cost_ledger.jsonl` | `emit_cost_record` (`ba02aaea`) | `cost_ledger.record` | W17 PG migrator, dashboard | 365d | auditor / owner |
| 6 | `w19_evaluator.jsonl` | `emit_audit` (`e5bbd7aa`) | `w19_evaluator.render` | DPO, runbook | 90d | auditor / owner |
| 7 | `idea_lifecycle.jsonl` | `IdeaLifecycle.transition` (`aa08334c`) | `idea_lifecycle.transition` | operator, dashboard | 365d | operator+ |
| 8 | `session_lifecycle.jsonl` | `SessionLifecycle.transition` (`a4edd469`) | `session_lifecycle.transition` | operator | 90d | operator+ |
| 9 | `audit_rotation.jsonl` | `AuditRotator` (`b70954ca`) | `audit_rotation.rotate`, `.evict`, `.run_daily` | operator, DPO | 365d | auditor / owner |
| 10 | `audit_chain_alert.jsonl` | `audit_chain_monitor.py` (`1e93065b`) | `audit_chain_alert.violation`, `.run` | DPO, Slack | 365d | auditor / owner |
| 11 | `rbac_v2.jsonl` | `register_role_capabilities`, `audit_capability_check` (`fa6cebf9`) | `rbac_v2.register`, `rbac_v2.check` | security, DPO | 365d | security / owner |
| 12 | `workflow_engine.jsonl` | `WorkflowEngine.fire` (`b1684dae`) | `workflow_engine.fire` | operator | 90d | operator+ |
| 13 | `adr_signoff.jsonl` | `apply_signoff` (`b7013ad0`) | `adr_signoff.attempt` | governance, DPO | **forever** | owner |
| 14 | `g2_template_gen.jsonl` | `LlmTemplateGenerator.generate` (`7faff095`) | `g2_template_gen.attempt` | operator | 30d | operator+ |
| 15 | `federation_policy.jsonl` | `RoutingGate.check` (`146c2404`) | `federation_policy.gate_check` | operator, runbook §4 | 90d | operator+ |
| 16 | `policy_registry.jsonl` | `PgPolicyRegistry.{create,update,delete}` (`95a724b2`) | `policy_registry.create/update/delete/schema_applied` | operator, governance | 365d | owner |
| 17 | `cost_ledger_migration.jsonl` | `CostLedgerPgMigrator` (`d4088fb1`) | `cost_ledger_migration.{schema_applied,file,run}` | DPO | **forever** | auditor / owner |

---

## Per-chain reference

### 1. gdpr_dsr.jsonl — Articles 15/16/17/20

**Producent**: `DsrService.{access,rectify,erase,portability}` w `aeis_v2/gdpr_v2/dsr.py`.

**Pole content**:
- `event_id` (uuid)
- `ts` (epoch float)
- `action` (`access`/`rectification`/`erasure`/`portability`)
- `user_id`
- `actor`
- `success` (bool)
- `details` (dict: `found`, `patched_keys`, `soft_delete_ts`, `hard_purge_after_s`, …)

**Krytyczne**: PII NIE pojawia się tutaj. `user_id` jest stabilną referencją (anonimizowaną w UI dashboardu).

### 2. gdpr_hard_purge.jsonl — soft-delete purge cron

**Producent**: `HardPurgeCron.purge_expired` w `aeis_v2/gdpr_v2/hard_purge.py`.

**Pole content**:
- `kind` ∈ `{gdpr.hard_purge.row, gdpr.hard_purge.run}`
- per-row: `user_id`, `deleted_at`, `outcome` (`purged`/`skipped`/`error`/`already_gone`)
- per-run: `started_at`, `finished_at`, `candidates`, `purged`, `skipped`, `errors`

### 3. replay_fork.jsonl — replay-as-fork

**Producent**: `ReplayFork.run` w `aeis_v2/replay_v2/fork.py`.

**Pole content**:
- `kind="replay_fork.run"`
- `snapshot_id`, `original_session_id`, `decision_point`
- `replay_id`, `model_override`, `context_override`
- `divergence_score` (float [0,1])

### 4. council_wedge.jsonl — Council Hybrid decisions

**Producent**: `evaluate_match_with_council` w `aeis_v2/council_v2/wedge.py`.

**Pole content**:
- `kind="council_wedge.decision"`
- `topic`, `chosen_template_id`, `verdict`
- `weights` (dict approve/reject/conditional)
- `dissents`, `sentinel_blocks`
- `session_id` (CouncilHybrid)

### 5. cost_ledger.jsonl — W17 cost records

**Producent**: `emit_cost_record` w `aeis_v2/deployment/cost_ledger.py`.

**Pole content**:
- `kind="cost_ledger.record"`
- `ts`, `session_id`, `decision_id`, `host`, `model`
- `tokens_in`, `tokens_out`, `cost_usd`
- `metadata`

**Migrator**: `CostLedgerPgMigrator` (commit `d4088fb1`) parsuje **oba** formaty (chained + legacy raw flat).

### 6. w19_evaluator.jsonl — W19 jinja renders

**Producent**: `emit_audit` w `aeis_v2/policy_v2/jinja_runner.py`.

**Pole content**:
- `kind="w19_evaluator.render"`
- `decision_id`, `template_hash` (16-hex), `ctx_keys`
- `succeeded` (bool), `error` (str | None)
- `render_ms`

### 7. idea_lifecycle.jsonl — 11-state transitions

**Producent**: `IdeaLifecycle.transition` w `aeis_v2/lifecycle_v2/idea_lifecycle.py`.

11 stanów: `draft`, `submitted`, `under_review`, `approved`, `rejected`, `in_progress`, `blocked`, `completed`, `archived`, `soft_deleted`, `hard_deleted`.

**Pole content**: `kind="idea_lifecycle.transition"` + `event_id`, `ts`, `idea_id`, `from_state`, `to_state`, `actor`, `success`, `detail`.

### 8. session_lifecycle.jsonl — W18 4-state transitions

**Producent**: `SessionLifecycle.transition` w `aeis_v2/lifecycle_v2/session_lifecycle.py`.

4 stany: `active`, `suspended`, `replay_source`, `archived` (terminal).

### 9. audit_rotation.jsonl — meta-trail rotacji

**Producent**: `AuditRotator.{rotate_if_needed,evict_old,run_daily}` w `aeis_v2/audit_chain/rotator.py`.

**Pole content**: `kind` ∈ `{audit_rotation.rotate, .evict, .run_daily}` + `path`, `rotated_to`, `size_mb`, `forced_by_size`/`forced_by_midnight`, `deleted`, `kept`, `errors`.

### 10. audit_chain_alert.jsonl — monitor cron heartbeats

**Producent**: `scripts/v2/audit_chain_monitor.py` (commit `1e93065b`) — hourly cron.

**Pole content**: `kind` ∈ `{audit_chain_alert.run, .violation}` + per-violation `module`, `fault_count`, `first_fault_line`, `first_fault_reason` + per-run aggregate.

**Specjalne**: monitor SAM EMITUJE do tego pliku — pętla rekursji uniknięta przez nazwę-skip w `discover_chain_files`.

### 11. rbac_v2.jsonl — capability grants + checks

**Producent**: `register_role_capabilities` (operator-time grants) + `audit_capability_check` (route-time decisions) w `aeis_v2/rbac_v2/capabilities.py`.

**Pole content**: `kind` ∈ `{rbac_v2.register, rbac_v2.check}` + `role`, `capabilities`, `actor`, `merge` (grant) lub `user_id`, `user_roles`, `capability`, `granted` (check).

### 12. workflow_engine.jsonl — W15 G3 rule fires

**Producent**: `WorkflowEngine.fire` w `aeis_v2/workflow_v2/engine.py`.

**Pole content**: `kind="workflow_engine.fire"` + `event_id`, `ts`, `rule_name`, `trigger`, `matched`, `action_results` (lista per-action), `chain_depth`.

### 13. adr_signoff.jsonl — Council ADR vote attempts

**Producent**: `apply_signoff` w `aeis_v2/governance_v2/adr_signoff.py`.

**Pole content**: `kind="adr_signoff.attempt"` + `actor` (NIE `critic_signature` — secret) + `request.{adr_id, vote_count, approve_count, reject_count, conditional_count}` + `result.{status, gate_passed, new_status, ...}`.

**Krytyczne**: chain ten jest **forever-retain** (governance-trail nie podlega rotacji).

### 14. g2_template_gen.jsonl — W16 G2 LLM gen

**Producent**: `LlmTemplateGenerator.generate` w `aeis_v2/apps_v2/g2_generation.py`.

**Pole content**: `kind="g2_template_gen.attempt"` + `idea_hash` (NIE `idea_text` — może mieć PII) + `template`, `error`, `elapsed_ms`, `model`, `fallback_used`.

### 15. federation_policy.jsonl — W19 routing gate decisions

**Producent**: `RoutingGate.check` w `aeis_v2/policy_v2/routing_gate.py`.

**Pole content**: `kind="federation_policy.gate_check"` + `decision_id`, `outcome` ∈ `{allow, deny, skipped, error}`, `rendered`, `reason`, `elapsed_ms`, `rolled_out`.

**Najgęstszy chain podczas canary** — szybko rośnie. `AuditRotator` z `size_mb_threshold=100` rotuje go agresywnie.

### 16. policy_registry.jsonl — PgPolicyRegistry CRUD

**Producent**: `PgPolicyRegistry.{create_policy, update_policy, delete_policy, ensure_schema}` w `aeis_v2/policy_v2/pg_registry.py`.

**Pole content**: `kind` ∈ `{policy_registry.create, .update, .delete, .schema_applied}` + `policy_id`, `name`, `template_str` (TAK — pełen szablon dla rekonstrukcji wersji), `enabled`, `version`, `actor`.

### 17. cost_ledger_migration.jsonl — JSONL→PG migrator

**Producent**: `CostLedgerPgMigrator.{ensure_schema, migrate_file, migrate_directory}`.

**Pole content**: `kind` ∈ `{cost_ledger_migration.schema_applied, .file, .run}` + per-file: `path`, `rows_seen`, `rows_inserted`, `rows_skipped_existing`, `rows_invalid`, `elapsed_ms`, `sha256` + per-run: `started_at`, `finished_at`, `total_*`.

---

## DPO daily check

```bash
# Cron: hourly via audit_chain_monitor.py
python scripts/v2/audit_chain_monitor.py

# Manual via verify_audit_chains.py:
python scripts/v2/verify_audit_chains.py
# Expected: "17 clean / 17 total"
```

Jeśli którykolwiek raportuje fault → patrz [`dpo_recovery_runbook.md`](./dpo_recovery_runbook.md).

---

## Storage estimates (production scale)

Przy 100 routing decisions/sec + 1000 DSR/dzień + 10 Council vote/dzień:

| Chain | Rows/dzień | Bajty/dzień | Po 90d |
|-------|------------|-------------|--------|
| `federation_policy.jsonl` | ~8.6M (gdy 100% rollout) | ~2.5 GB | ~225 GB ⚠ |
| `cost_ledger.jsonl` | ~8.6M | ~3 GB | ~270 GB ⚠ |
| `w19_evaluator.jsonl` | zależne od % | scales with rollout | — |
| Pozostałe | < 100k | < 100 MB | < 9 GB |

**Konsekwencja**: `federation_policy.jsonl` + `cost_ledger.jsonl` muszą być migrowane do PG zanim canary osiągnie 100% (commit `d4088fb1` daje narzędzie dla cost_ledger; `federation_policy` PG migrator to sprint 5 backlog).
