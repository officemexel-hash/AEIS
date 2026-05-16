# SYLION AEIS v2 — modules index

> Stan na 2026-04-28 (sprint 2 day 4 → sprint 4 day 1).
> 40 atomic ``[v2 cron]`` commits w jeden dzień. Ten plik jest mapą.

---

## Spis treści

1. [Sprint 2 — fundament](#sprint-2--fundament)
2. [Sprint 3 — production hardening](#sprint-3--production-hardening)
3. [Sprint 4 — W19 production layer](#sprint-4--w19-production-layer)
4. [Audit chain catalogue](./operations/audit_chains_catalogue.md)
5. [Production runbooks](#production-runbooks)
6. [REST API surface](#rest-api-surface)
7. [Operator user manual](./AEIS_OPERATOR_USER_MANUAL.md)
8. [Audit and human simulation plan](./AEIS_AUDIT_AND_HUMAN_SIMULATION_PLAN.md)

---

## Sprint 2 — fundament

| # | Commit | Moduł | Co dostarcza | Testy |
|---|--------|-------|--------------|-------|
| 1 | `49288143` | `aeis_v2/council_v2/wedge.py` | W16 G1 step 3: 9-role Council Hybrid wedge + REST `POST /api/v1/apps/match-idea-g1-with-council` | 18/18 |
| 2 | `47b54c03` | `aeis_v2/embeddings/cache.py` + `pg_schema.sql` | SqliteEmbeddingCache + pgvector schema | 22/22 |
| 3 | `4936a463` | `aeis_v2/apps_v2/__init__.py` (wired) | CachingEmbeddingProvider w G1 cascade — idea-text caching | 14/14 |
| 4 | `bc68430f` | `aeis_v2/gdpr_v2/dsr.py` + `api/gdpr_routes.py` | GDPR Articles 15/16/17/20 + 5 REST endpoints | 28/28 |
| 5 | `82b0af48` | `aeis_v2/replay_v2/{fork,divergence}.py` | Replay-as-fork PoC + divergence_score | 31/31 |
| 6 | `ac97e957` | `aeis_v2/audit_chain/chain.py` | **AuditChainIntegrity** — tamper-evident JSONL z hash chain | 24/24 |
| 7 | `ce336270` | `aeis_v2/gdpr_v2/hard_purge.py` | HardPurgeCron 30d grace window | 17/17 |
| 8 | `d656bd0b` | (3 modules migration) | gdpr_dsr + replay_fork + council_wedge → chained format | +3 |
| 9 | `f8ad2e41` | `api/metrics_v2_routes.py` | Prometheus exposition `/api/v1/metrics/v2` | 17/17 |
| 10 | `8b6f3f63` | `scripts/v2/verify_audit_chains.py` | DPO CLI dla integrity check | 8/8 |
| 11 | `71415137` | `api/health_v2_routes.py` | k8s liveness/readiness `/api/v1/health/v2` | 15/15 |

**Sprint 2 razem: 11 commits, ~197 testów, ~5500 LoC.**

---

## Sprint 3 — production hardening

| # | Commit | Moduł | Co dostarcza | Testy |
|---|--------|-------|--------------|-------|
| 12 | `a8836cb2` | `aeis_v2/audit_chain/chain.py` | Last-hash side-cache O(n)→O(1) appends | +4 |
| 13 | `b70954ca` | `aeis_v2/audit_chain/rotator.py` | AuditRotator midnight + size + 90d retention | 26/26 |
| 14 | `b7013ad0` | `aeis_v2/governance_v2/adr_signoff.py` + `api/council_signoff_routes.py` | **Council ADR sign-off endpoint** — flips PROPOSED→ACCEPTED | 25/25 |
| 15 | `e5bbd7aa` | `aeis_v2/policy_v2/jinja_runner.py` (refactor) | W19 jinja real timeout via daemon thread + chained audit | +5 |
| 16 | `7faff095` | `aeis_v2/apps_v2/g2_generation.py` | **W16 G2 LlmTemplateGenerator** (Ollama) + W19 token blocklist | 28/28 |
| 17 | `e486f65b` | `api/replay_routes.py` + `replay_v2/replay_storage_lru.py` | Replay W18 REST endpoints + LRU storage | 13/13 |
| 18 | `dffaa4fc` | `docs/v2/operations/dpo_recovery_runbook.md` | DPO 10-step procedure + smoke test | 7/7 |
| 19 | `6fe98c6c` | `aeis_v2/gdpr_v2/pg_store.py` | PgUserDataStore (psycopg) | 18/18 |
| 20 | `d70f4154` | `aeis_v2/embeddings/pg_cache.py` | PgEmbeddingCache (psycopg) | 13/13 |
| 21 | `d4088fb1` | `aeis_v2/deployment/cost_ledger_pg_migrator.py` | W17 cost_ledger JSONL→PG migrator (idempotent) | 20/20 |
| 22 | `9c44c93d` | `scripts/v2/migrate_cost_ledger_to_pg.py` | CLI wrapper for migrator (--dry-run / --apply) | 9/9 |
| 23 | `607a018e` | `aeis_v2/council_v2/adapters.py` | **OllamaRoleAdapter** — 9 ról, real-model votes | 26/26 |
| 24 | `aa08334c` | `aeis_v2/lifecycle_v2/idea_lifecycle.py` | IdeaLifecycle 11-state machine | 26/26 |
| 25 | `1e93065b` | `scripts/v2/audit_chain_monitor.py` | hourly cron + Slack alerts | 17/17 |
| 26 | `d163e87c` | `tests/aeis_v2/test_v2_full_smoke_e2e.py` | 10-step E2E smoke 7 modules | 2/2 |
| 27 | `b1684dae` | `aeis_v2/workflow_v2/engine.py` | W15 G3 WorkflowEngine | 44/44 |
| 28 | `fa6cebf9` | `aeis_v2/rbac_v2/capabilities.py` | W7 capability extension (3 nowe role) | 25/25 |
| 29 | `a4edd469` | `aeis_v2/lifecycle_v2/session_lifecycle.py` | W18 SessionLifecycle 4-state | 23/23 |
| 30 | `ba02aaea` | `aeis_v2/deployment/cost_ledger.py` (migration) | cost_ledger emit → chained format | +2 |
| 31 | `a6d9b1a4` | `aeis_v2/adapter_bus_v2/metrics.py` | W11 Prometheus metrics + /metrics/v2 wiring | 16/16 |

**Sprint 3 razem: 20 commits, ~370 testów, ~8000 LoC.**

---

## Sprint 4 — W19 production layer

| # | Commit | Moduł | Co dostarcza | Testy |
|---|--------|-------|--------------|-------|
| 32 | `ef2e720f` | `aeis_v2/policy_v2/staged_rollout.py` | StagedRolloutGate canary 0/1/5/25/50/100% | 21/21 |
| 33 | `e883ebcf` | `scripts/v2/run_w19_adr003_council_vote.py` | Council vote dispatcher (parallel 9 ról + apply_signoff) | 11/11 |
| 34 | `146c2404` | `aeis_v2/policy_v2/routing_gate.py` | **RoutingGate** — 3-gate composition production hook | 16/16 |
| 35 | `2d8a7556` | `tests/aeis_v2/test_w19_chaos.py` | Chaos test suite (10 attack vectors) | 11/11 |
| 36 | `95a724b2` | `aeis_v2/policy_v2/pg_registry.py` | **PgPolicyRegistry** — operator-stored templates | 19/19 |
| 37 | `0899913a` | `docs/v2/operations/w19_production_runbook.md` | 11-section runbook + smoke test | 10/10 |
| 38 | `45478f26` | `aeis_v2/policy_v2/metrics.py` | W19 Prometheus metrics + auto-instrumentation | 15/15 |
| 39 | `9307524e` | `aeis_v2/deployment/federation.py` (wired) | **federation route() wire-in** — operator hooks | 10/10 |
| 40 | `d0f02c05` | `sylion-frontend/.../AdminOverview.tsx` + `/v2/admin/page.tsx` | Frontend operator dashboard | TS clean |

**Sprint 4 razem: 9 commits, ~133 testy, ~3500 LoC.**

---

## Production runbooks

| Plik | Zakres | Sekcje |
|------|--------|--------|
| [`operations/w19_production_runbook.md`](./operations/w19_production_runbook.md) | W19 jinja evaluator rollout | Pre-deploy, ADR-003 sign-off, canary dial 0→100, observability, rollback, incident, DPO, split-brain, jinja2 CVE, version migration, UI walkthrough, exit criteria |
| [`operations/dpo_recovery_runbook.md`](./operations/dpo_recovery_runbook.md) | Audit chain violations | Pre-flight, 10-step procedure, decision tree A/B/C, rollback triggers, stakeholder contacts, post-mortem template |
| [`operations/audit_chains_catalogue.md`](./operations/audit_chains_catalogue.md) | Wszystkie chained JSONL files | Per-module: path, kind values, retention, who reads |

---

## REST API surface (sprint 2-4)

Wszystkie endpointy w `/api/v1/`. **RBAC** = role wymagana per `requires_role(...)`.

| Path | Method | RBAC | Co robi |
|------|--------|------|---------|
| `apps/match-idea-g1-with-council` | POST | operator+ | W16 G1 cascade step 3 — Council vote |
| `gdpr/dsr/access/{user_id}` | GET | operator/owner/auditor | GDPR Article 15 |
| `gdpr/dsr/rectification/{user_id}` | POST | operator/owner | GDPR Article 16 |
| `gdpr/dsr/erasure/{user_id}` | DELETE | owner | GDPR Article 17 |
| `gdpr/dsr/portability/{user_id}` | GET | operator/owner/auditor | GDPR Article 20 |
| `gdpr/dsr/audit/recent` | GET | auditor/owner | DPO ledger view |
| `terminal/sessions/{sid}/snapshot` | POST | operator/owner | replay-as-fork capture |
| `replay/run` | POST | operator/owner | run replay against snapshot |
| `replay/list` | GET | operator/owner/auditor | tail replay_fork.jsonl |
| `council/sign-off-adr/{adr_id}` | POST | owner | flip ADR PROPOSED→ACCEPTED |
| `metrics/v2` | GET | auditor/owner | Prometheus exposition (W11 + W19 + audit + GDPR + Council + replay + cache) |
| `health/v2` | GET | none (k8s probe) | services + audit_chains presence |

---

## Audit chain modules (15)

Wszystkie w `src/sylion-pipeline/sylion/logs/v2/*.jsonl`, hash-chained format od commit `ac97e957`. Patrz [`audit_chains_catalogue.md`](./operations/audit_chains_catalogue.md) po pełną tabelę.

1. `gdpr_dsr.jsonl` — DSR actions
2. `gdpr_hard_purge.jsonl` — soft-delete purges
3. `replay_fork.jsonl` — replay runs
4. `council_wedge.jsonl` — Council Hybrid decisions
5. `cost_ledger.jsonl` — W17 cost records
6. `w19_evaluator.jsonl` — W19 jinja renders
7. `idea_lifecycle.jsonl` — 11-state transitions
8. `session_lifecycle.jsonl` — 4-state transitions
9. `audit_rotation.jsonl` — rotator runs
10. `audit_chain_alert.jsonl` — monitor cron heartbeats + alerts
11. `rbac_v2.jsonl` — capability grants + checks
12. `workflow_engine.jsonl` — rule fires
13. `adr_signoff.jsonl` — Council ADR sign-off attempts
14. `g2_template_gen.jsonl` — W16 G2 LLM generation attempts
15. `federation_policy.jsonl` — W19 routing gate decisions
16. `policy_registry.jsonl` — PgPolicyRegistry CRUD
17. `cost_ledger_migration.jsonl` — JSONL→PG migrator runs

---

## Quick start (operator workflow)

```bash
# 1. Run all v2 tests:
cd src/sylion-pipeline
pytest tests/aeis_v2/ -q
# Expected: ~700+ passed (40 commits dziś)

# 2. Verify all chained audit logs:
python ../../scripts/v2/verify_audit_chains.py
# Expected: "N clean / N total"

# 3. (sprint 4) Vote ADR-003 → ACCEPTED:
python ../../scripts/v2/run_w19_adr003_council_vote.py --apply

# 4. (sprint 4) Open operator dashboard:
cd ../sylion-frontend && npm run dev
# → http://localhost:3000/v2/admin
```
