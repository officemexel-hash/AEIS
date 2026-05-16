# Pre-W15 Module Inventory & Classification Report

**Phase:** Pre-W15 Module Inventory & Classification (1-2 weeks, before W15 G1)
**Source spec:** `docs/v2/_pdf_source/SYLION_v2_KOMPLETNY_OBRAZ_extracted.txt` §6.2 + `MIGRATION_PLAN_v1_to_v2.md`
**Inputs analyzed:** `src/sylion-pipeline/sylion/` (all 35 top-level subsystems + advisor sub-services + testing sub-areas)
**W14 reference ontology:** `src/sylion-pipeline/sylion/aeis/testing/ontology/objects.py` (25 dataclasses, 25 tables `w14_*`)

---

## 1. Top-line numbers

| Class | Count | Share | Spec target |
|------:|------:|------:|------------:|
| A — Stay unchanged | 25 | 58% | ~62% |
| B — Refactor (use OSDK) | 14 | 33% | ~31% |
| C — Deprecated | 4 | 9% | ~7% |
| **Total modules** | **43** | 100% | — |

Distribution lands inside the spec-target band (60/30/10 ± few %), confirming the §6.2 estimate was realistic. The spread is slightly tilted toward Class B because three of the largest single modules (cognitive, governance, project_mode) carry an outsized share of domain payload, and the demo apps (six of them) are all naturally W16 candidates.

**Empirical signal:** of 43 modules, 30+ have one or more `CREATE TABLE IF NOT EXISTS …` statements, but only ~14 of those tables hold first-class domain payload other layers query. The rest are either platform-runtime telemetry (cores, monitoring, efficiency, security, surface event log) or single-module internal state (autonomy phases, healing sessions, rebuild snapshots).

---

## 2. Top 10 hardest modules to refactor (highest migration risk)

Ranked by combined score: number of tables × cross-module references × LOC × downstream dependents.

### 1. `sylion/cognitive` (P0, ~973 LOC in idea_vault alone, 30+ tables, 55+ references)
The single biggest Class B target. `idea_vault.py` is referenced from 55 files; `chat_engine.py` from 15; `model_registry.py` from 19. Tables span ideas, attachments, lifecycle, chat, evaluations, models, agents, knowledge, feedback, prompts, planning. Recommendation: **first OSDK manifest after W14 lift** — Idea / IdeaAttachment / IdeaLifecycleEntry / ChatSession / Plan / Agent / KnowledgeEntry as the founding W15 manifest set. Risk: cognitive sits behind frontend Idea Vault, AI Workspace, Council — any schema change cascades to every console panel.

### 2. `sylion/governance` (P0, 1123 LOC in council_hybrid alone, 60+ tables, 70+ references)
30 modules, 60+ tables: Council Hybrid, Human Gate, Decision Gates, Policy Engine, Compliance, Conflict Resolver, Evidence Spine, Roles, Tickets, Risk Scorer, Cascade Analyzer, Change Proposal/Merger. Two storage incarnations (`evidence_packs` + `evidence_packs_v2`, `decision_gate_engine` in both `core/` and `governance/`) already signal duplication. W14 ontology cross-links to `council_session_id` and `hg_ticket_id` — these MUST be canonical W15 objects in G3. Risk: governance is the audit/approval backbone — touching it without parallel runs is unsafe; needs side-by-side validation period in G3.

### 3. `sylion/aeis/testing` (P0, 12 sub-areas, 30+ w14_* tables, defines the lift)
This IS the §6.3 lift target. 12 sub-areas (charter, findings, agent_theater, auto_repair_controller, loop_governor, merge_guard, release_rail, self_audit, simulation/, branches/, personas/, guardians/, demo_projects/, actions/, ontology/, memory.py) all import from `aeis.testing.ontology.objects` and `aeis.testing.ontology.store`. Risk: the ontology is FROZEN (E0 HG approved 2026-04-26) — manifest authoring must reproduce 25 dataclasses including hard validators (e.g. `SimulationContract.isolation.main_mutation_allowed=true ⇒ approved_d_level=D5 + council_approved=true`). Every transition table (CHARTER_TRANSITIONS, PATCH_STATUSES, REPAIR_RESULTS, LOOP_TYPES) must round-trip. Ten-step migration plan in §6.3 has rollback per step — execute it.

### 4. `sylion/project_mode` (P0, 23 tables in one store.py, 134 references)
The second-biggest single-store module. `project_projects`, `project_stages`, `project_questions`, `project_answers`, `project_decisions`, `project_canon_entries`, `project_masterplans`, `project_modules`, `project_council_members`, `project_council_votes`, `project_brain_*`. Project / Stage / Decision are first-class W15 objects. Risk: project_mode duplicates fragments of cognitive (Decision tables in both), governance (CouncilVotes in both), and aeis/advisor (CanonEntries vs Recommendations). Migration must reconcile — likely consolidate into shared W15 Project ontology with the brain/lora datasets becoming a subordinate object type.

### 5. `sylion/aeis/advisor` (P0, 13 sub-services, 50+ PG tables already, half-migrated)
ALREADY ON POSTGRESQL via `advisor_layer.sql` (9 schemas: advisor_engine, advisor_funding, advisor_history, advisor_pricing, advisor_preferences, advisor_actions, advisor_outbound, advisor_subscription, advisor_scaling, advisor_orchestration, advisor_evidence, advisor_events). Risk is LOW relative to size — the heavy lifting (SQLite→PG, schema design) is done. Refactor is mostly: replace direct SQL in service.py / _db.py with generated OSDK calls. But there are 13 sub-services and they each follow slightly different conventions (some use `_db.py` thin layer, some have inline SQL in service.py). Risk: 13 mini-migrations, easy to drop one.

### 6. `sylion/api` (P0, 103 router files, ~2300 references)
103 `*_routes.py` files — every router queries something. Most thin REST wrappers over service modules. Once W15 generates REST/gRPC/Python OSDK, ~70 of these routes become auto-gen candidates (idea_routes, projects_routes, council_routes, advisor_routes, testing_routes, governance_routes, demo_*_routes, etc.). Backbone routers (auth, health, ws, rbac_enforcement, rate_limit, app.py, router.py) stay. Risk: switching routes from hand-written to auto-generated breaks every frontend panel that hits a hand-coded URL — needs careful URL stability layer, sustained `/api/v1/*` per §6.5 backward compatibility.

### 7. `sylion/funding_autopilot` (P0, 14 tables, partial duplication of advisor_funding)
14 tables — `funding_company_profiles`, `funding_company_documents`, `funding_programmes`, `funding_calls`, `funding_ideas`, `funding_projects`, `funding_matches`, `funding_partner_candidates`, `funding_outreach_messages`, `funding_applications`, `funding_submission_sessions`, `funding_approval_events`, `funding_alerts`, `funding_audit_events`. Substantial overlap with `advisor_funding.*` (companies, grant_programs, scoring_components, scoring_history). Risk: TWO modules holding overlapping company / grant / application data — must converge in W15. Decision needed before lift: which module owns the canonical Company / GrantProgram / FundingApplication object.

### 8. `sylion/skills` (P0, 8 tables, intersects W7 extension)
7 modules: catalog, demand_analyzer, demand_signal, executor, registry, runtime, schemas. 8 tables: skills, catalog_entries, executions, runtime_executions, demand_signals, demand_reports, sylion_demand_signals, sylion_skill_demand. Note `demand_signals` + `sylion_demand_signals` are two parallel tables — typical sign of incomplete consolidation. Targeted by §8.2 W7 extension (Role Catalog, 30+ creative roles). Risk: lift must avoid breaking the demo skills_marketplace which uses these via `marketplace_skills`.

### 9. `sylion/db` (P0, classification: C — but high-priority migration)
The migration scaffolding itself (`migration.py`, `pg_migration.py`, `pg_migration_worker.py`, `advisor_layer.sql`, `migrations/0001_w14_ontology.py`). Hand-written DDL for modules/decisions/agents/skills/runs/audit_log + the W14 PG migration. Once W15 owns manifest-driven DDL, this is canonical "duplicate functionality" → delete. Risk: timing — the `0001_w14_ontology.py` migration is the bridge for §6.3 step 2 ("DDL generation + verification") and CANNOT be deleted before W15 has reproduced it via manifest. Hand-off is delicate.

### 10. `sylion/aeis` (P2 in CSV, but listed here as risk)
14 self-* modules (autonomy_controller, evolution_tracker, self_evolution, self_healing_orchestrator, integration_controller, self_limitation, self_observation, self_preservation, self_explanation, evidence_pack, adaptation_engine, explanation_engine, improvement_queue, autonomy_stages). Classified A because tables are platform-runtime, not domain. BUT — `aeis/evidence_pack.py` writes to `evidence_packs` and `evidence_items` while `governance/evidence_packs.py` writes to `evidence_packs_v2` + `evidence_artefacts_v2`. THREE evidence pack tables (this one + governance V2 + advisor_evidence) — risk: post-W15 someone will think these are unified when they aren't, leading to silent data fragmentation. Even though the module stays A, the RECONCILIATION work (which evidence pack is canonical?) is a hidden P0 task.

---

## 3. Top 5 deprecation candidates (Class C / collapse-into)

### 1. `sylion/aeis_v2` (C, P2)
Empty placeholder. Subdirs `apps/`, `deployment/`, `ontology/`, `terminal/` contain only `__pycache__`. This is the canonical v2 namespace into which W15-W18 will land. Currently zero code; becomes the home for W15 OSDK runtime. Action: keep the directory, populate with W15 G1 deliverables.

### 2. `sylion/sim` (C, P1)
`_db_shim.py` re-creates 6 advisor_engine tables in flat unschema-qualified names for sim/test fixtures. `runner.py` + `scenarios.py` + `personas.py` heavily overlap `aeis/testing/personas` + `aeis/testing/simulation/`. Two simulation engines is one too many. Action: post-W15 G3, delete `sim/_db_shim.py` (advisor PG schemas become single source); migrate `sim/runner.py` scenarios into `aeis/testing/simulation/engine.py`. ~4 files removable.

### 3. `sylion/quality` (C, P1)
6 modules / 12 tables (golden_sets, golden_set_cases, golden_set_results, baselines, regression_alerts, test_suites, test_runs, golden_runs, golden_run_results, sylion_quality_gates, sylion_quality_results, quality_gates, gate_evaluations). Every one of these has a W14 ontology counterpart (TestSuite, TestRun, RegressionRun, EvaluationSuite + GoldenSet semantics in `sylion/rebuild/golden_set_manager`). Three different golden_set tables across the codebase is a strong duplication smell. Action: post-W15 G3, gate logic stays (in `aeis/testing/release_rail.py` or new `aeis/testing/quality_gate.py`), data-layer collapses into W14 ontology. Delete or rewrite as wrapper.

### 4. `sylion/db` (C, P0)
Hand-written DDL migrations (`migration.py`, `pg_migration.py`, `0001_w14_ontology.py`). After W15 G2 (manifest compiler emits DDL), these are dead code. The pool helpers (`pool.py`, `aeis/advisor/_db.py`) stay — they're transport. The migrations themselves get archived once W15 has equivalent manifest output that round-trips.

### 5. (Tied) `sylion/grpc` + `sylion/grpc_stubs` (currently A, P2 — partial deprecation)
6 hand-written gRPC servers + auto-generated proto stubs. W15 G2 will auto-generate gRPC service+stubs from manifests for any object type. The 6 existing servers (aeis_server, cognitive_server, core_server, eventbus_server, execution_server, governance_server) compete with W15 OSDK gRPC — likely candidates for collapse post-W15 G3 if their methods can all be expressed as OSDK Action calls. Action: defer decision to W15 G3; for now mark A, plan re-evaluation.

---

## 4. Dependency hot-spots

Modules referenced from many other modules — touching their schemas cascades widely. Counted via `from sylion.X import` greps.

| Hot-spot | Inbound refs | Why it matters |
|----------|-------------:|----------------|
| `sylion/cognitive/idea_vault` | 55+ | Single most-referenced domain object (Idea). Every panel, every workflow. Schema change is a release event. |
| `sylion/governance/council_hybrid` | 70+ | Council session is referenced by W14 ReleaseDecision, every D3+ Decision Gate, every advisor card with HG. |
| `sylion/aeis/testing/ontology` | 39 files import directly | The 25 W14 dataclasses. Lift target. |
| `sylion/core/event_bus` | almost universal | Backbone — must stay rock-stable through migration. |
| `sylion/governance/human_gate` | 30+ | Every interactive decision (Idea approve, Charter approve, Release decision). |
| `sylion/governance/evidence_spine` | 25+ | Hash-chained evidence — W15 lineage piggy-backs on this. |
| `sylion/aeis/advisor/engine` | 28 | AdvisorCard pipeline. PG already, but referenced from frontend, council, projects, idea_vault. |
| `sylion/cognitive/model_registry` | 19 | Model catalog. Cross-cuts W7/W11 Adapter Bus. |

**Cross-cutting concern:** the FOUR evidence-pack incarnations (`aeis/evidence_pack`, `governance/evidence_packs` v1, `governance/evidence_packs.py` v2 with `evidence_packs_v2`, `aeis/advisor` `advisor_evidence.evidence_packs`) must be reconciled in W15 G3. This is the hidden risk that doesn't show up in module-level classification.

---

## 5. Recommended migration order (per spec §6.3 + per-module rec)

The 10-step plan in §6.3 is the global sequence. Per-module rollout:

### Phase G1 (weeks 1-4 of W15) — Foundation
- **`sylion/aeis_v2`** populated with manifest compiler MVP, schema generator, OSDK Python emitter (1 example object type — pick `Requirement` or `TestCharter` as smallest).
- No production cutovers yet. Side-by-side only.

### Phase G2 (weeks 5-8 of W15) — Core
- All 25 W14 ontology types manifested. DDL generated. OSDK emitted.
- 5 example types from cognitive picked as second wave (Idea, Project, AdvisorCard, CouncilSession, EvidencePack).
- Still side-by-side; original SQLite layers untouched.

### Phase G3 (weeks 9-12 of W15) — Migration & Cutover (CRITICAL)
Order of cutovers (most → least risky, do in this exact sequence per §6.3 step 9):

1. **`sylion/aeis/testing`** — IS the lift target. Cutover first because it owns the canonical 25 ontology types. Side-by-side validation week. Rollback path: keep SQLite ontology store as read-replica for 30 days (§6.3 step 10).
2. **`sylion/db/migrations/0001_w14_ontology.py`** — replaced by manifest-driven DDL. Move file to `sylion/db/migrations/_archived/` after W14 cutover green.
3. **`sylion/aeis/advisor`** (P0) — already PG, easy refactor. Subservice-by-subservice in dependency order: pricing → preferences → orchestration_config → role_resolver → engine → actions → events → history → funding → scaling → subscription → variants → mobile_gateway. Each gets its own one-sprint refactor.
4. **`sylion/cognitive`** (P0) — riskiest single module. Idea / IdeaAttachment / IdeaLifecycleEntry as first manifest. Then ChatSession → Plan → Agent → KnowledgeEntry. Frontend panels switch via `/api/v1/*` URL stability (§6.5). Old idea_vault.py kept as deprecated shim emitting deprecation warnings, deleted in v2.5.
5. **`sylion/governance`** (P0) — Council Session + Human Gate + Evidence Spine first (highest cross-coupling). Reconcile the four evidence-pack incarnations during this phase: pick `evidence_packs_v2` as canonical, alias others to it via OSDK. Decision Gates and Policies can wait until late G3.
6. **`sylion/funding_autopilot`** (P0) — converge with advisor_funding here. Either:
   - (a) `funding_autopilot` keeps the operator-facing logic, advisor_funding owns the data;
   - (b) merge `funding_autopilot/store.py` tables INTO `advisor_funding.*` schema, delete the SQLite store.
   Recommended: (b). Council decision needed in G2 to set direction.
7. **`sylion/project_mode`** (P0) — Project / Stage / Decision become canonical W15 objects. brain_* tables stay as separate Project sub-objects.
8. **`sylion/skills`** (P0) — collapse `demand_signals` and `sylion_demand_signals`. Lift Skill / SkillExecution / DemandSignal.
9. **`sylion/api`** — at-scale route migration. Hand-coded routes that have an exact manifest equivalent get archived; URL stability layer ensures clients don't break.

### Phase G4 (weeks 13-16 of W15) — Production-ready
- Class C deprecations executed: `sylion/sim/_db_shim.py` deleted, `sylion/quality` collapsed into `aeis/testing` (gate logic) + W15 ontology (data), `sylion/db/migration.py` archived.
- 6 demo apps (factory_automation_panel, funding_pipeline_tracker, mobile_field_inspector, operator_crm, public_project_showcase, skills_marketplace) — these stay until W16. They become Class B candidates AT W16, but are blocked here (they own own-table data; W16 G2 declares the manifest format).

### Phase POST-W15 (post-v2.0)
- **`sylion/aeis`** (self-* modules), **`sylion/autonomy`**, **`sylion/memory`**, **`sylion/surface`**, **`sylion/rebuild`** — remain Class A. No action.
- **W16 G2** — convert 6 demo apps to W16 manifests; until then they keep their SQLite stores.
- **W17 G2** — `sylion/container`, `sylion/vps`, `sylion/operator_mobile` get re-evaluated as W17 Node Registry consumers.
- **W18 charter** — `sylion/surface` extended with Operator Terminal panels; OSDK consumed read-only.

---

## 6. The risk top-10 list (combined)

A single ranked list for handing to whoever owns the W15 G3 rollout:

| Rank | Module | Class | Reason it's risky | Recommendation |
|----:|--------|:-----:|-------------------|----------------|
| 1 | `sylion/aeis/testing` | B | It's the lift target itself. Frozen ontology, 25 dataclasses, hard validators. Migration is the W14→W15 bridge. | Execute the full 10-step §6.3 plan with rollback per step. Do not start any other cutover until this is green for 1 week. |
| 2 | `sylion/governance` | B | 60+ tables, evidence-pack incarnation cluster, council/HG cross-coupling everywhere. | Reconcile the four evidence-pack incarnations FIRST in G2 (decide canonical = `evidence_packs_v2`). Then lift CouncilSession, HumanGateRequest, EvidencePack as one manifest set. Side-by-side run for 2+ weeks. |
| 3 | `sylion/cognitive` | B | 30+ tables, idea_vault referenced from 55 files, sits behind every console panel. | Ship behind a feature flag. Frontend panels migrate one-by-one to OSDK URLs. Keep idea_vault.py as deprecated shim until v2.5. |
| 4 | `sylion/project_mode` | B | 23 tables in one store, duplicates governance and advisor fragments, 134 references. | Council decision in G2: which module owns Project / Decision / CanonEntry canonically. Then merge schemas. Most likely: project_mode owns Project, governance owns Decision, advisor owns CanonEntry derivative. |
| 5 | `sylion/db` | C | Migration scaffolding becomes dead code. Timing of deletion is delicate (must not delete before W15 manifests reproduce DDL). | Archive `0001_w14_ontology.py` AFTER W14 cutover green for 1 week. Leave `pool.py` / `_db.py` (transport, not migration). |
| 6 | `sylion/funding_autopilot` | B | 14 tables that overlap `advisor_funding.*` schema. Two parallel funding stores. | Decide direction in G2 (recommended: collapse store.py INTO advisor_funding schema). Block lift of funding_autopilot until decision lands. |
| 7 | `sylion/api` | B | 103 routers, ~70 are auto-gen candidates. Frontend stability depends on URL preservation. | Strict `/api/v1/*` URL stability layer. Migrate routes 5-10 at a time. Don't auto-gen until W15 G3 green for two non-route modules. |
| 8 | `sylion/aeis/advisor` | B | 13 sub-services, 50+ PG tables, easy individually but death-by-thirteen-paper-cuts. | One sub-service per sprint in dependency order: pricing → preferences → engine → actions → ...; each has its own _db.py refactor. Don't try to do all 13 in one sprint. |
| 9 | `sylion/quality` | C | Looks like an active module but every table duplicates W14 ontology. Will silently rot if not consolidated. | Collapse into `aeis/testing` (gate logic) + W15 ontology (data) in G3-G4. Delete files; do not leave shim. |
| 10 | `sylion/sim` | C | `_db_shim.py` re-creates advisor tables with non-schema names. `runner.py` overlaps `aeis/testing/simulation`. | Delete `_db_shim.py` after advisor cutover green. Migrate scenarios to `aeis/testing/simulation/scenarios.py`. |

---

## 7. Self-check (per task constraint)

- Distribution check: 58% / 33% / 9% — within ±5% of spec target 62/31/7. PASS.
- "If 90/5/5 you're searching too shallow" — not us; 33% Class B confirms domain-payload depth was probed.
- "If 30/60/10 you're over-classifying B" — not us; downgrades from B→A applied to `sylion/aeis`, `sylion/autonomy`, `sylion/memory`, `sylion/surface`, `sylion/rebuild` after second-pass review.
- "Hidden SQL → B" check: every Class A module verified to have either zero SQLite tables OR only platform-runtime/telemetry tables that never expose data outside the module. All Class B modules have explicit cross-module imports of their store layer (verified via grep on idea_vault, council_hybrid, advisor_engine, project_mode store).

---

## 8. Files produced

- `docs/v2/migration/MODULE_INVENTORY_CLASSIFICATION.csv` — 43 rows, classification + tables + dependencies + priority.
- `docs/v2/migration/PRE_W15_inventory_report.md` — this report.

Both files form the deliverable for the §11 row "MODULE_INVENTORY_CLASSIFICATION.csv → Faza Pre-W15".
