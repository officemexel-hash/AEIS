# AEIS Findings

Status: no findings yet

## P1-F001: Mini CRM Expanded Into Project Management System

| Field | Value |
|---|---|
| finding_id | P1-F001 |
| project | P1 Mini CRM Local |
| surface | Idea promotion / project classifier |
| severity | P1 |
| type | classification/scope-drift |
| expected | A simple local CRM should remain a small local CRM/application with minimal modules, small council, and no project-management portfolio/Gantt/Hetzner scope. |
| actual | Promotion created `project_d3a336d20de7` with `project_kind=project_management_system`, 12 project-management modules, D4 Source of Truth, portfolio/Kanban/Gantt/budget/RBAC/release governance, and Hetzner language. |
| evidence | `docs/aeis_manual_tests/evidence/api/p1_project_after_promote.json`; `output/playwright/p1-mini-crm/project-after-promote.json` |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F002: Council LLM Errors Counted As Ready Analyses

| Field | Value |
|---|---|
| finding_id | P1-F002 |
| project | P1 Mini CRM Local |
| surface | Project dashboard / Council analysis |
| severity | P1 |
| type | fallback/false-success/council/guard |
| expected | If model calls fail, AEIS must block the Council flow and clearly report that there are not enough usable analyses. Discussion, variants, canon freeze, and downstream gates must not proceed from error text. |
| actual | Dashboard showed `Opinie są gotowe`, enabled the discussion step, and rendered variants while the terminal entries were `REAL_LLM_UNAVAILABLE` / `ReadTimeout`. |
| evidence | Visible in in-app browser at `http://localhost:3001/projects/project_06e3bf38743b`; screenshot state captured through Browser session after clicking `Niech modele dyskutują`. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F003: Model Provider Lists Were Inconsistent Across UI And Backend

| Field | Value |
|---|---|
| finding_id | P1-F003 |
| project | P1 Mini CRM Local / onboarding before Council retest |
| surface | Onboarding Model gate; AI Models / Providers and keys |
| severity | P1 |
| type | ui/configuration/model-routing |
| expected | Operator can select every backend-supported provider needed for the Council and router setup: OpenAI, Anthropic, Perplexity, Google, Z.ai, OpenRouter, Kimi/Moonshot, DeepSeek, xAI, Mistral, Groq, Cohere, Fireworks, Together and local runtimes where applicable. |
| actual | Onboarding exposed only OpenAI, Anthropic, Google and OpenRouter. The full AI Models KeyVault form also missed backend-supported providers including OpenRouter, Kimi/Moonshot, xAI, Cohere, Fireworks, LM Studio, vLLM and llama.cpp. |
| evidence | Visible in in-app browser at `http://localhost:3001/onboarding` and `http://localhost:3001/ai-models`; backend provider defaults in `src/sylion-pipeline/sylion/api/ai_providers_routes.py`. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F004: AI Models UI Pointed At Wrong Backend Port

| Field | Value |
|---|---|
| finding_id | P1-F004 |
| project | P1 Mini CRM Local / model setup |
| surface | AI Models control plane |
| severity | P1 |
| type | runtime/configuration/ui-api |
| expected | The frontend test runtime on `http://localhost:3001` must call the verified backend for this test run on `http://127.0.0.1:8010`. |
| actual | `/ai-models` initially showed `Backend Offline` and kept loading Provider Catalog because the frontend used the default `http://localhost:8000`, where an unrelated/stale process returned 404. Backend 8010 was healthy and returned provider catalog correctly. |
| evidence | In-app browser showed `/ai-models` offline; shell health check passed for `8010` and failed with 404 on `8000` for the same provider-catalog path. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F005: Project Start Ignored Negated Payment/KSeF/VPS Scope

| Field | Value |
|---|---|
| finding_id | P1-F005 |
| project | P1 Mini CRM Local |
| surface | Project Start / Phase 16 classifier and templates |
| severity | P1 |
| type | classification/scope-drift/cost/funding |
| expected | A prompt saying `Bez płatności, bez KSeF, bez deployu, bez VPS, bez integracji zewnętrznych` must stay `internal_app/crm`, D3, small reserve, internal preview, with payments/KSeF/VPS only out of scope. |
| actual | Fresh creation from the local CRM prompt was classified as `public_saas/crm_payments`, D4, $700 reserve, canary deployment, KSeF/PCI/Stripe/payment scope despite explicit negation. |
| evidence | Old bad project `proj_8817f156f7ee`; dashboard retest after repair created `proj_94add2c61121` as D3/internal CRM. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F006: Phase 19 Acceptance Used Public SaaS Thresholds For Internal CRM

| Field | Value |
|---|---|
| finding_id | P1-F006 |
| project | P1 Mini CRM Local Retest |
| surface | Project Start / Phase 19 Council acceptance |
| severity | P1 |
| type | guard/acceptance/council |
| expected | Internal CRM Council defaults with 9 roles and 5 relevant KBs should pass after operator readiness approval; public SaaS thresholds must not be applied to smaller local projects. |
| actual | UI and API reported `READY_FOR_COUNCIL_CONVENING` and `council_configured`, but Phase 19 still had hard blocks for `Council finalized` and `Knowledge bases loaded` because acceptance required 12 roles and 8 KBs. |
| evidence | Dashboard at `/project-start` after clicking Phase 19 defaults and `Approve readiness`; API acceptance for `proj_94add2c61121` before repair showed 5/7 with 2 hard blocks. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F007: Group C Used Public SaaS Council Assumptions For Internal CRM

| Field | Value |
|---|---|
| finding_id | P1-F007 |
| project | P1 Mini CRM Local Retest |
| surface | Council to Księga / Phases 20-25 |
| severity | P1 |
| type | council/scope-drift/artifact/guard |
| expected | Group C must continue the small internal CRM with 9 roles, local CRM questions, no active KSeF/Stripe/PCI content, and project-aware acceptance thresholds. |
| actual | Phase 20 awakened 9 roles and moved to `READY_FOR_INITIAL_VERDICTS`, but acceptance still required 12 roles. Downstream generated questions, rounds, Book and Księga text also used SaaS/payment/KSeF assumptions unless corrected. |
| evidence | Dashboard `/council-to-ksiega` after `Convene Council`; API and artifact checks for `proj_94add2c61121`; regression `test_internal_crm_group_c_uses_small_council_without_external_scope`. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F008: Project Detail Screen Uses A Different Project Registry

| Field | Value |
|---|---|
| finding_id | P1-F008 |
| project | P1 Mini CRM Local Retest |
| surface | `/projects/{project_id}` vs Project Start / Council-to-Księga |
| severity | P2 |
| type | ui-api/integration-drift |
| expected | A project created and advanced by Project Start should be discoverable in the main Projects registry/detail screen, or the dashboard should clearly route operator to the lifecycle-specific surfaces. |
| actual | `/project-start` and `/council-to-ksiega` both see `proj_94add2c61121`, but `/projects/proj_94add2c61121` displays `Nie znaleziono projektu`; `/api/v1/projects` returns an empty list. |
| evidence | In-app browser navigation to `http://localhost:3001/projects/proj_94add2c61121`; API `GET /api/v1/projects`. |
| blocker | no for P1 lifecycle continuation; yes for global dashboard consistency before final AEIS signoff |
| stop_fix_restart_required | yes before global dashboard pass |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F011: Global Project Classifier Over-Selected Project Management

| Field | Value |
|---|---|
| finding_id | P1-F011 |
| project | Global project-mode simulations |
| surface | `/api/v1/projects`, idea promotion, domain launch artifacts |
| severity | P1 |
| type | classifier/domain-routing-regression |
| expected | Funding, ecommerce generator and operator mobile simulations should keep their primary domain when governance, HumanGate, reporting or external model tokens are present. |
| actual | `test_projects_routes.py` showed operator_mobile/ecommerce/funding cases classified as `project_management_system`; funding text containing `Perplexity` falsely matched SaaS because token `erp` was detected inside `Perplexity`. |
| evidence | Broad regression initially failed 6 project-mode tests: operator mobile promotion/launch, ecommerce planning/launch, funding launch and multi-domain runtime answer. |
| blocker | yes before funding simulation and before claiming model/project routing is reliable |
| stop_fix_restart_required | yes; affected classifier tests restarted after fix |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F012: Funding Human Gate Tickets Were Marked Blocking After Committed Draft Writes

| Field | Value |
|---|---|
| finding_id | P1-F012 |
| project | Funding dashboard simulation |
| surface | `/funding`, `/human-gate`, `/api/v1/funding/*` |
| severity | P1 |
| type | governance-guard/semantic-drift |
| expected | Funding actions that are already committed as local catalogue or draft records should not appear as unresolved blocking Human Gate items; truly risky actions such as idea conversion and final submission must remain blocking. |
| actual | Manual programme/call creation and draft application creation wrote records immediately, but created pending tickets displayed in Human Gate as `blocking`/financial. This made the guard surface look like it was blocking actions it had already allowed. |
| evidence | Dashboard Funding created programme, call and application; Human Gate showed pending `Create funding programme`, `Create funding call`, and `Create grant application` tickets while the records already existed. |
| blocker | yes for Funding guard signoff |
| stop_fix_restart_required | yes; Funding guard tests restarted after fix |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F013: Funding Submission UI Displayed Empty Receipt As Saved Confirmation

| Field | Value |
|---|---|
| finding_id | P1-F013 |
| project | Funding dashboard simulation |
| surface | `/funding` -> `Złożenie i CRM` |
| severity | P1 |
| type | ui/false-success/guard |
| expected | A blocked submission session with empty `receipt: {}` must not display a final submission confirmation. |
| actual | After preparing `fund_submit_909e7c229d6c`, backend correctly returned `blocked_missing_documents` and empty receipt, but the UI showed `Potwierdzenie złożenia: zapisane`. |
| evidence | In-app browser Funding retest after P1-F012; API `GET /api/v1/funding/submission/receipt?session_id=fund_submit_909e7c229d6c` returned `{ "receipt": {} }`. |
| blocker | yes |
| stop_fix_restart_required | yes; affected Funding submission checkpoint restarted after frontend fix |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F014: Coherence Guard Dashboard Emitted Sample Findings As Real Findings

| Field | Value |
|---|---|
| finding_id | P1-F014 |
| project | Guard dashboard simulation |
| surface | `/coherence-guard`, `/api/v1/coherence-guard/run` |
| severity | P1 |
| type | guard/mock/stub/false-finding |
| expected | Guard runs from the operator dashboard must either analyze real project artifacts or state that no real project evidence was provided; they must not create sample ecommerce/checkout/currency findings as active guard failures. |
| actual | Clicking `Uruchom kontrolę spójności` sent `project_id=sample_project` and backend `_finding_samples()` created hard-coded active findings: API contract mismatch, missing checkout translation and GBP/masterplan mismatch. |
| evidence | In-app browser `/coherence-guard` after running validity/baseline/coherence/acceptance; code `sylion/api/coherence_guard_routes.py::_finding_samples`; frontend `coherence-guard/page.tsx` sent `sample_project`. |
| blocker | yes |
| stop_fix_restart_required | yes; Coherence Guard checkpoint restarted after backend/frontend fix |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F015: Guard Suite Phases 7-10 Emitted Sample Findings As Real Findings

| Field | Value |
|---|---|
| finding_id | P1-F015 |
| project | Guard dashboard simulation |
| surface | `/cost-guard`, `/security-guard`, `/quality-guard`, `/provenance-guard`, `/api/v1/guard-suite/run` |
| severity | P1 |
| type | guard/mock/stub/false-finding |
| expected | Guard Suite runs started from the operator dashboard must analyze real project artifacts or state that no project evidence was provided; they must not create sample cost/security/quality/provenance failures as live findings. |
| actual | The dashboard run path used `project_id=sample_project`, so phases 7-10 produced hard-coded sample findings such as cost budget projection, dependency CVE, checkout E2E failure and artifact provenance gap. |
| evidence | In-app browser retest of `/cost-guard`, `/security-guard`, `/quality-guard`, `/provenance-guard`; backend `sylion/api/guard_suite_routes.py::_run_findings`; frontend `GuardSetupDashboard.tsx` sent `sample_project`. |
| blocker | yes |
| stop_fix_restart_required | yes; affected Guard Suite checkpoints restarted after backend/frontend fix |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F016: Skills Dashboard Was Read-Only Despite Live Skills API

| Field | Value |
|---|---|
| finding_id | P1-F016 |
| project | Skills adaptation simulation |
| surface | `/skills`, `/api/v1/skills/*` |
| severity | P1 |
| type | skill/ui/api-gap |
| expected | Operator must be able to manually test skill lifecycle from the dashboard: create/register a skill, execute it, record a demand signal and run demand analysis. This is required to verify whether AEIS can adapt skills to project needs. |
| actual | The backend exposed live endpoints for skill registration, execution and demand signals, but `/skills` only showed read-only registry/log/demand tabs. Without API calls, the dashboard could not test the key skills workflow. |
| evidence | In-app browser `/skills` showed only `Demo Skill` and no create/execute/demand action controls. Direct API calls to `/api/v1/skills/skills`, `/api/v1/skills/executions` and `/api/v1/skills/demand/signals` succeeded and became visible after refresh. |
| blocker | yes |
| stop_fix_restart_required | yes; Skills dashboard checkpoint restarted after UI action panel was added |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F017: Memory Dashboard Was A Canonical Bridge, Not A Runtime Test Surface

| Field | Value |
|---|---|
| finding_id | P1-F017 |
| project | Memory reuse simulation |
| surface | `/memory`, `/api/v1/memory/*` |
| severity | P1 |
| type | memory/ui/api-gap |
| expected | Operator must be able to verify memory from the dashboard by storing project memory, storing evidence, indexing content and retrieving context. LIVE_VERIFIED requires proof that memory can be reused, not only described. |
| actual | `/memory` only displayed a canonical bridge and links to other panels. It explicitly stated that full memory status required proof of reuse, but exposed no clickable write/search/retrieval controls. |
| evidence | In-app browser `/memory` showed bridge text and links only. Backend `memory_routes.py` exposed live Kanon, evidence, index and retrieval endpoints that were not reachable from the dashboard surface. |
| blocker | yes |
| stop_fix_restart_required | yes; Memory dashboard checkpoint restarted after live controls were added |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F018: Test Catalog Could Not Run T0-T19 Tests From Dashboard

| Field | Value |
|---|---|
| finding_id | P1-F018 |
| project | AEIS internal testing simulation |
| surface | `/test-center/catalog`, `/api/v1/test-center/catalog` |
| severity | P1 |
| type | testing/ui/api-gap/release-gate |
| expected | Test Center catalog must allow the operator to run a T0-T19 test class and record pass/fail evidence. A failed test must create a blocking finding visible in Test Center dashboard/release status. |
| actual | The catalog displayed T0-T19 rows and the hub copy promised `uruchom teraz`, but rows had no run action and backend exposed only a read-only catalog summary. |
| evidence | In-app browser `/test-center/catalog` showed rows with counts only and no run buttons. `/test-center/dashboard` had no recent runs before manual backend/UI repair. |
| blocker | yes |
| stop_fix_restart_required | yes; Test Center catalog checkpoint restarted after run endpoint and UI actions were added |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F019: Monitoring Budget API Broke Model Limit Dashboard Checks

| Field | Value |
|---|---|
| finding_id | P1-F019 |
| project | Model routing and limits simulation |
| surface | `/orchestration/llm-routing`, `/costs`, `/api/v1/monitoring/budget/*` |
| severity | P1 |
| type | model-routing/budget/api/ui |
| expected | AEIS must expose the configured model registry in routing, allow dashboard assignment of models outside the fallback list, and let the operator verify per-model limits, spend, fallback and remaining budget without backend errors. |
| actual | The routing dashboard could only be trusted after registry refresh; the budget summary endpoint failed with HTTP 500 because `/budget/summary` was captured by `/budget/{model_id}` and returned non-JSON `inf` values. Legacy budget configure/usage URLs used by tests and frontend helpers were also incomplete. |
| evidence | Backend `/api/v1/model-registry/models` returned 14 models; `/api/v1/monitoring/budget/summary` failed with `ValueError: Out of range float values are not JSON compliant: inf`. Browser retest then verified `/orchestration/llm-routing` options included `qwen3.5:latest` and `/costs` displayed the configured `qwen3.5:latest` limit. |
| blocker | yes |
| stop_fix_restart_required | yes; Model routing/limits checkpoint restarted after API repair and backend restart |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F020: Phase 36 Marked Placeholder Files As Product Artifacts

| Field | Value |
|---|---|
| finding_id | P1-F020 |
| project | AEIS-T1 Prosty lokalny CRM 2026-05-07 |
| surface | `/execution-start`, `phase36_build_completion`, generated `code/repo` product |
| severity | P1 |
| type | product/mock/stub/false-success/testing |
| expected | Passing AEIS simulation must include testing of the product produced by the run. Generated product artifacts must be runnable or at least functionally representative of the requested app; quality gates must not pass on placeholder inventory files. |
| actual | Phase 36 created files such as `backend_001.py` and `frontend_001.tsx` containing only `# backend artifact 1` / `Generated by Phase 36 build completion inventory`, while phase 37 still reported L1-L5 PASS and project closure succeeded. |
| evidence | Browser completed T1 phases 32-41 with `10/10`; filesystem inspection of `C:\Users\razor\.sylion\projects\proj-032d6a6ddf8d-aeis-t1-prosty-lokalny-crm-2026-05-07\code\repo\backend\backend_001.py` and `frontend_001.tsx`; phase37 quality report claimed 308/309 effective tests. |
| blocker | yes |
| stop_fix_restart_required | yes; T1 simulation must be restarted after product artifact generator repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F021: Funding Simulation Generated CRM Product

| Field | Value |
|---|---|
| finding_id | P1-F021 |
| project | AEIS-T2 Lokalny asystent funding NGO 2026-05-07 |
| surface | `/project-start`, `/funding`, `/execution-start`, generated `code/repo` product |
| severity | P1 |
| type | classifier/product/scope/runtime-false-success/funding |
| expected | A funding/NGO grant assistant simulation must be classified as a funding domain and must generate a funding product with program matching, application document checks, HumanGate/final-submit protection and local-only external action blocking. |
| actual | The project completed phases 32-41, but API classification reported `project_type=internal_app`, `domain=crm`; generated `backend/app.py` was `AEIS Local CRM` with contacts/leads, while neither backend nor frontend mentioned funding. |
| evidence | Project `proj_de801eca383e`; generated root `C:\Users\razor\.sylion\projects\proj-de801eca383e-aeis-t2-lokalny-asystent-funding-ngo-2026-05-07`; product scan found zero placeholders but `backend_mentions_funding=false`, `frontend_mentions_funding=false`, `backend_mentions_crm=true`. `/funding` correctly blocked missing documents, proving the dashboard workflow existed but the final product scope drifted. |
| blocker | yes |
| stop_fix_restart_required | yes; T2 simulation must be restarted after classifier and product generator repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F022: Funding Planning Reintroduced CRM/KSeF/Stripe Scope

| Field | Value |
|---|---|
| finding_id | P1-F022 |
| project | AEIS-T2R Lokalny asystent funding NGO restart 2026-05-07 |
| surface | `/planning`, `phase26_model_assignment.json` |
| severity | P1 |
| type | planning/scope-drift/funding/skill/model-routing |
| expected | A funding-domain project must plan funding modules: grant catalog, matching, application builder, document checklist, HumanGate/final submission rehearsal, tests and funding handoff. It must not assign CRM customer modules, KSeF integration or Stripe/payment work. |
| actual | After fixing classification to `domain=funding`, phase 26 still generated `Customer Management`, `Invoicing and KSeF`, `Payments`, Stripe integration and KSeF integration assignments. |
| evidence | Project `proj_f615558b04a5`; API state after dashboard click `/planning` phase 26 showed `classification.domain=funding` but `planning.model_selection.module_assignments` contained `customer_management`, `invoicing_ksef`, `payments`, `stripe_integration`, `ksef_integration`. |
| blocker | yes |
| stop_fix_restart_required | yes; T2R planning must be restarted after funding planning repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F023: Dashboard Operator Surface Is Partly English

| Field | Value |
|---|---|
| finding_id | P1-F023 |
| project | Global AEIS dashboard audit |
| surface | `/project-start`, `/council-to-ksiega`, `/planning`, `/skills`, `/execution-start`, `/funding`, `/memory`, `/human-gate`, `/test-center`, `/orchestration/llm-routing` |
| severity | P1 |
| type | ui/localization/operator-dashboard |
| expected | Operator-facing AEIS dashboard text should be consistently Polish during Polish operator tests, with canonical technical tokens translated or explained in Polish where they are visible. |
| actual | Many primary buttons, labels, statuses and error messages remain English: `Project name`, `Create project`, `Convene Council`, `Generate Initial Verdicts`, `Generate masterplan`, `Run dry run`, `Register Skill`, `Failed to load Human Gate tickets`, `Select project`, `total findings`, `Truth Alignment`, plus mixed `Human Gate/HumanGate`. |
| evidence | Parallel localization audit by agent `Aquinas` over frontend source files: `ProjectStartDashboard.tsx`, `CouncilToKsiegaDashboard.tsx`, `PlanningDashboard.tsx`, `/skills/page.tsx`, `/funding/page.tsx`, `/memory/page.tsx`, `/human-gate/page.tsx`, `/test-center/*`, `/orchestration/llm-routing/page.tsx`. User also observed during manual dashboard work that half of the dashboard needs Polish translation. |
| blocker | yes for final operator acceptance; no for continuing current funding runtime repair |
| stop_fix_restart_required | yes; affected dashboard screens need translation retest by clicking after functional blockers are repaired |
| owner | Frontend Repair Engineer |
| status | BLOCKER_OPEN |

## P1-F024: System Surfaces Expose Incomplete Or Contradictory Runtime State

| Field | Value |
|---|---|
| finding_id | P1-F024 |
| project | Global AEIS dashboard audit |
| surface | `/ontology`, `/role-catalog`, `/policy`, `/terminal` |
| severity | P1 |
| type | dashboard/runtime/wiring/policy/ontology/terminal |
| expected | Ontology, role catalog, policy plane and terminal must be testable as live system surfaces: counts match displayed data, policy state is explicit, terminal/replay status is not falsely presented as complete, and missing wiring blocks final acceptance. |
| actual | `/ontology` displayed `0 typów` while also listing ontology type buttons; `/role-catalog` displayed `0 ról` while showing role presets/actions; `/policy` says Phase 0 read-only with no evaluator/DSL editor/redaction engine; `/terminal` shows `Replay nagrań (W18 G3) not wired`. |
| evidence | Dashboard click checkpoint on 2026-05-08 over `/ontology`, `/role-catalog`, `/policy`, `/terminal`; visible text and buttons captured in browser snapshot. User explicitly asked to include ontology, role catalog, system policies and terminal in the test scope. |
| blocker | yes for full AEIS dashboard/system acceptance; no for continuing T2RR product artifact verification |
| stop_fix_restart_required | yes; each affected system surface needs repair or accepted limitation plus retest |
| owner | System Surface Repair Engineer |
| status | BLOCKER_OPEN |

## P1-F025: Meta-Orchestration Panels Do Not Prove Runtime Governance

| Field | Value |
|---|---|
| finding_id | P1-F025 |
| project | Global AEIS meta-orchestration audit |
| surface | `/orchestration/auditor`, `/orchestration/llm-routing`, `/orchestration/dispatch`, `/orchestration/council-rules`, `/orchestration/teams`, `/orchestration/conversations`, `/orchestration/fixer`, `/orchestration/event-map` |
| severity | P1 |
| type | orchestration/config-only/runtime-governance/teams/council/models |
| expected | Meta-orchestration settings must demonstrably govern planning, execution, council decisions, work distribution, active teams, model conversations, fixer escalation and event flow in runtime. |
| actual | Before repair, dashboard wrote most meta-orchestration settings to API state, but no clicked test proved those settings control planning/execution/council runtime. `teams` showed active rules but `active_teams=[]`; `conversations` toggled enabled but `recent_conversations=[]`. After repair, `/orchestration/teams` can trigger rule matching and create an active team, `/orchestration/conversations` can trigger and log a model-to-model runtime conversation, Phase 26 applies J1 LLM routing, Phase 32 applies J5 dispatch caps to worker count, Phase 34 and project council deliberation read J2 council quorum/weights, Phase 35 records J3/J4/J5/J7/J9 runtime policy in build orchestration, Phase 37 applies J4 fixer limits, and J8 event-map displays runtime event counters. |
| evidence | Browser clicked Auditor trigger, LLM routing presets, dispatch wide/capped save, council simulation/save, fixer save, teams refresh, conversations enable/save, event-map refresh. Pre-repair API state: inter-model conversation `enabled=true`, `recent_conversations=[]`; team rules 2, active teams empty; event-map edges all `events_per_minute=0`. Post-repair browser retest clicked `/orchestration/teams` -> `Testuj reguły`, UI showed `Aktywne zespoły (1)` with `z_ai`, `claude` and operator runtime task. Browser retest clicked `/orchestration/conversations` -> `Uruchom rozmowę`, UI showed `Ostatnie konwersacje (1)`, `codex ↔ claude`, `4 tur` and the runtime check topic. Browser retest clicked `/orchestration/event-map`; UI showed `aeis.orchestration.team.formed` and `aeis.orchestration.conversation.completed` with `1/min`. Regression `test_orchestration_config_controls_phase26_models_and_phase32_workers` proves J1 routing changes Phase 26 `backend_code` model to `gpt-4o-mini` and J5 capped dispatch changes Phase 32 workers to 1. Execution regression proves Phase 35 records meta-orchestration runtime and Phase 37 applies J4 fixer policy. Council regression proves project-scoped council quorum comes from `orchestration_config`. |
| blocker | no after runtime repairs; requires full project-simulation rerun for final acceptance evidence |
| stop_fix_restart_required | yes; restart meta-orchestration checkpoint and project simulations from the beginning |
| owner | Orchestration Runtime Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## P1-F026: Orchestration Test Catalog Was A False-Pass Stub

| Field | Value |
|---|---|
| finding_id | P1-F026 |
| project | Global AEIS meta-orchestration audit |
| surface | `/orchestration/tests`, `/api/v1/orchestration/test-catalog/run-now` |
| severity | P1 |
| type | test-layer/stub/false-success |
| expected | Clicking test run must not mark tests as passed unless a real runner or verified check completed. Pending/queued work must be visible as pending/running. |
| actual | Before repair, direct API returned `status=pass` and updated selected catalog entries to `pass` immediately, with output `Executed ...`, without running pytest/CI/product checks. |
| evidence | Locke ran `tests/aeis/advisor/orchestration_config/test_orchestration_routes.py` and found contract failure: expected `running`, got `pass`. Manual API probe before backend restart also returned `status=pass`. |
| blocker | no after repair; deterministic backend checks now run from the dashboard |
| stop_fix_restart_required | yes; affected checkpoint retested after repair |
| owner | Test Layer Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F027: Memory Dashboard Displayed Incorrect Runtime Counts

| Field | Value |
|---|---|
| finding_id | P1-F027 |
| project | Global AEIS memory/meta-orchestration audit |
| surface | `/memory` |
| severity | P1 |
| type | ui/api-contract/memory/runtime-evidence |
| expected | Memory dashboard counts must reflect backend stats after dashboard writes: kanon, evidence, index and retrieval. |
| actual | After clicking `Zapisz evidence`, API returned `evidence.total_evidence=1`, but dashboard displayed `EVIDENCE 0` because frontend expected `evidence.total`. Index used a similar mismatched field. |
| evidence | Browser clicked `/memory` evidence write; `GET /api/v1/memory/stats` returned `total_evidence: 1`; UI still displayed `EVIDENCE 0`. |
| blocker | yes for memory dashboard evidence before repair |
| stop_fix_restart_required | yes; memory checkpoint restarted after frontend mapping repair |
| owner | Frontend Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F028: Workspace Chat Records User Message But Does Not Produce AI Response

| Field | Value |
|---|---|
| finding_id | P1-F028 |
| project | Global AEIS workspace/meta-orchestration audit |
| surface | `/workspace` |
| severity | P1 |
| type | workspace/chat/conversation/runtime/model-response |
| expected | In the `Czat` thinking layer, `Nowy czat` + message send should store the user message and produce either a visible assistant/model response or an explicit model/runtime error. The right-side pipeline input should be visually distinct from chat input. |
| actual | Correct chat retest posted the user message to `/api/v1/workspace/sessions/{id}/messages`, but after repeated refreshes only the user message existed; no assistant response or model error was displayed. Separately, the right-side Working input also has a `Wyślij` button and sends to `/api/v1/pipeline/ideas`, which can be mistaken for chat during split-screen testing. |
| evidence | Browser retest used `Nowy czat`, filled the chat `textarea`, pressed Enter. Backend log showed `POST /api/v1/workspace/sessions/442a613acbbe/messages -> 200`; API `GET /api/v1/workspace/sessions/442a613acbbe/messages` returned one `role=user` message only. UI did not display assistant output after waiting. Earlier split-screen click on the right-side input produced pipeline ID `9e25cb52b6fb44b4`, proving the two send surfaces are easy to confuse. |
| blocker | no after repair; chat now returns an assistant message or explicit model error |
| stop_fix_restart_required | yes; after fixing chat send wiring, restart workspace/conversation checkpoint |
| owner | Workspace Frontend/Runtime Engineer |
| status | BLOCKER_FIXED |

## P1-F009: Planning Reintroduced Payment/KSeF Scope Into Local CRM

| Field | Value |
|---|---|
| finding_id | P1-F009 |
| project | P1 Mini CRM Local Retest |
| surface | Planning / Phases 26-31 |
| severity | P1 |
| type | skill/scope-drift/masterplan/guard |
| expected | Model selection, skill synthesis, layers, work units, masterplan and dry run for P1 must stay local CRM only: contacts, notes, lead statuses, reminders, CSV, local storage, GDPR, local runbook. |
| actual | Dashboard phase 31 passed, but `Skill patterns` showed KSeF invoice generation, Stripe payment integration, and deployment/customer runbooks. Masterplan internals also contained KSeF/Stripe/payment milestones and risk sequencing. |
| evidence | In-app browser `/planning` after clicking P26-P31; regression `test_internal_crm_planning_has_no_payment_or_external_deploy_scope`; artifact scan over `phase27_skill_synthesis.json`, `masterplan_v1.md`, `masterplan_v1.json`. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F010: Execution Reintroduced KSeF/Payment Build Scope

| Field | Value |
|---|---|
| finding_id | P1-F010 |
| project | P1 Mini CRM Local Retest |
| surface | Execution Start / Phases 32-36 |
| severity | P1 |
| type | execution/scope-drift/false-success |
| expected | Execution for local CRM must build only local CRM modules and evidence: customer CRUD, notes/history, lead pipeline, reminders, CSV, local storage, GDPR, tests and local handoff. |
| actual | Dashboard accepted phases 32-36 and showed worker evidence, but sequential execution rows included `KSeF`, `Payment Integration`, and `Quality and Deploy`; this reintroduced out-of-scope external/payment work after planning had been repaired. |
| evidence | In-app browser `/execution-start` after clicking `Zainicjuj budowę`, `Start wykonania`, `Zwołaj radę`, `Uruchom orkiestrację`, `Zamknij budowę` for `proj_94add2c61121`. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED |

## P1-F029: Local CRM Product Artifacts Reintroduced Payment/KSeF/Invoice Scope After Dashboard Pass

| Field | Value |
|---|---|
| finding_id | P1-F029 |
| project | P1 Restart Mini CRM Lokalny AEIS |
| surface | Planning/Execution generated artifacts after phases 26-41 |
| severity | P1 |
| type | scope-drift/product-artifact/false-success/guard |
| expected | A local-only CRM simulation must produce only local CRM product artifacts: contacts, notes, lead statuses, reminders, CSV, GDPR export/delete, local reports and local handoff. Generated artifacts must not contain payment, KSeF, Stripe, invoice or Hetzner/VPS production scope. |
| actual | Dashboard phases closed successfully, but artifact scan found `payment_processing` in phase 26 quality overrides, KSeF/Stripe in phase 30 risks, KSEF prompt-splitting angle in phase 35, invoice/payment feedback in phase 38, final invoice fields in phase 41, and local CRM product files mentioning excluded external scope. |
| evidence | P1 dashboard run `proj_ffd80b0a7464`; artifact scan over `planning`, `reports`, and `code/repo` found forbidden terms in `phase26_model_assignment.json`, `phase30_preflight_cost.json`, `prompt_splitting_policy.json`, `phase38_acceptance_testing.json`, `phase41_project_closure.json`, generated `backend/app.py` and generated `docs/README.md`. |
| blocker | yes |
| stop_fix_restart_required | yes; P1 must restart from project creation after generator repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## P2-F030: Funding Council/Księga Reintroduced SaaS Payment Scope

| Field | Value |
|---|---|
| finding_id | P2-F030 |
| project | P2 Restart Funding NGO AEIS |
| surface | Project Start phase 18/19 and Council/Księga phases 20-25 |
| severity | P1 |
| type | scope-drift/funding/council/ksiega/false-success |
| expected | Funding project scope, Council roles, Council Book and Księga must stay on grant catalog, eligibility scoring, documents, application draft, HumanGate, local rehearsal and grant audit. |
| actual | Dashboard closed P2, but artifact scan found KSeF, Stripe, invoice and PCI content in Council Book and Księga. Root cause: funding projects fell through to the generic Polish SaaS payment scope and Council defaults. |
| evidence | Failed dashboard run `proj_a1fcc8946efc`; forbidden scan found KSeF/Stripe/invoice/PCI in `council/council_book.md` and `ksiega/ksiega_v1.md`. |
| blocker | yes |
| stop_fix_restart_required | yes; P2 restarted from project creation after repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## P2-F031: Funding Product Deadline Validation Missed Runtime Import

| Field | Value |
|---|---|
| finding_id | P2-F031 |
| project | P2 Restart3 Funding NGO AEIS |
| surface | Generated funding product after Phase 36 |
| severity | P1 |
| type | product/runtime/test/funding |
| expected | The generated funding product must pass its own backend smoke test, including deadline validation, source provenance blocking, legal/budget/document confirmations, HumanGate and local-only rehearsal. |
| actual | Dashboard P2R3 closed successfully, but generated backend pytest failed in `/match` with `NameError: name 'date' is not defined` because the product generator emitted deadline validation without importing `date`. |
| evidence | Failed dashboard run `proj_a96c0ff7cbb4`; generated backend `test_app.py` failed before P2R4. Fresh restart `proj_7544e8bdd3ea` passed artifact scan and generated backend pytest after generator repair. |
| blocker | yes |
| stop_fix_restart_required | yes; P2 restarted from project creation after repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## P3-F032: Mobile Approval Queue Classified As Payment SaaS

| Field | Value |
|---|---|
| finding_id | P3-F032 |
| project | P3 Mobile Approval Queue AEIS |
| surface | Project Start phase 16-19, downstream planning/execution generator |
| severity | P1 |
| type | classification/scope-drift/product-generator |
| expected | A local operator mobile approval queue must classify as an internal mobile approval project with local device binding, HumanGate decision guard, desktop/mobile sync and no billing/tax/VPS scope. |
| actual | First dashboard P3 run `proj_b22632800944` classified as `public_saas/crm_payments` with `$700` reserve. Without repair, downstream Council, planning and generated product would follow the payment SaaS path. |
| evidence | Browser-created failed project `proj_b22632800944`; fresh restart `proj_635af5715faf` classified as `internal_app/mobile_approval`, closed through dashboard, scanned clean and passed generated product pytest. |
| blocker | yes |
| stop_fix_restart_required | yes; P3 restarted from project creation after repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## P4-F033: Local Automation Runtime Classified As CRM

| Field | Value |
|---|---|
| finding_id | P4-F033 |
| project | P4 Local Automation Runtime AEIS |
| surface | Project Start phase 16-19, downstream planning/execution generator |
| severity | P1 |
| type | classification/scope-drift/product-generator |
| expected | A local automation runtime prompt must classify as `internal_app/automation_runtime` and create scope for workers, task queue, retry, max parallel controls, environment count, logs, traces, status reporting and guards. |
| actual | First dashboard P4 run `proj_c4ab8c81c556` classified as `internal_app/crm` with `$200` reserve. |
| evidence | Browser-created failed project `proj_c4ab8c81c556`; fresh restart `proj_f3e2a536e48c` classified as `internal_app/automation_runtime`, passed dashboard phases and product tests after repair. |
| blocker | yes |
| stop_fix_restart_required | yes; P4 restarted from project creation after repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## P4-F034: Automation Runtime Planning Acceptance Did Not Match Runtime Shape

| Field | Value |
|---|---|
| finding_id | P4-F034 |
| project | P4 Restart Local Automation Runtime AEIS |
| surface | Planning phases 27-28 |
| severity | P1 |
| type | planning/skill/masterplan/acceptance |
| expected | Runtime planning must accept the correct 5-module automation runtime shape while still requiring complete skill assignments and enough work units for guards, config, observability and local handoff. |
| actual | Dashboard P4R reached `READY_FOR_BUILD`, but UI showed P27/P28 still open: phase 27 expected six module skill assignments although runtime has five modules; phase 28 expected 41 work units but generator produced too few. |
| evidence | Browser `/planning` for `proj_f3e2a536e48c` showed P27 `Skill assignments per Ksiega module: missing` and P28 `Module-level work units: missing`; regression added `test_automation_runtime_planning_acceptance_covers_skills_and_work_units`. |
| blocker | yes |
| stop_fix_restart_required | yes; P4 planning restarted after repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## P4-F035: Local-Only Runtime Configuration Allowed External VPS Planning Path

| Field | Value |
|---|---|
| finding_id | P4-F035 |
| project | P4 Restart Local Automation Runtime AEIS |
| surface | Execution Start runtime configuration |
| severity | P1 |
| type | guard/cost/external-action/runtime |
| expected | For local-only projects, dashboard attempts to configure VPS workers, paid VPS allowance or monthly VPS budget must be blocked or reset before build initialization, with visible evidence and no external cost. |
| actual | Before repair, the execution runtime configurator accepted the external planning shape in the general code path when `max_parallel_workers` covered local+VPS workers; it did not force local-only for automation/funding/mobile/local CRM projects. |
| evidence | Browser P4R attempted `local + VPS`, 2 VPS workers, 50 EUR cap and paid VPS checkbox. After repair, UI showed `local-only`, `vps_workers=0`, cap `0`, `external_runtime_request_blocked_local_only`; regression added `test_automation_runtime_blocks_vps_runtime_configuration`. |
| blocker | yes |
| stop_fix_restart_required | yes; P4 execution restarted after repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## P5-F036: Multi-Domain Project Collapsed To Automation Runtime

| Field | Value |
|---|---|
| finding_id | P5-F036 |
| project | P5 Complex Multi Domain AEIS |
| surface | Project Start phase 16-19, Council, planning and execution generator |
| severity | P1 |
| type | classification/scope-drift/multi-domain/product-generator |
| expected | A complex AEIS multi-domain prompt must classify as `internal_app/aeis_multi_domain`, preserve CRM, funding, mobile approvals, automation runtime, governance, HumanGate, audit, memory, skills and guards, and generate a product covering those domains. |
| actual | First dashboard P5 run `proj_33eda4199b12` collapsed to `internal_app/automation_runtime` with `$500` reserve. Without repair, downstream Council, planning and product would lose the multi-domain scope. |
| evidence | Browser-created failed project `proj_33eda4199b12`; focused regression added multi-domain start/planning/execution tests. Fresh restart `proj_b9c142b06eb4` classified as `internal_app/aeis_multi_domain`, passed phases 16-41, scanned clean and passed generated backend pytest. |
| blocker | yes |
| stop_fix_restart_required | yes; P5 restarted from project creation after repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## W14-F037: Test Center Did Not Support Execution-Start Project IDs End-To-End

| Field | Value |
|---|---|
| finding_id | W14-F037 |
| project | AEIS self-test on P5 Restart `proj_b9c142b06eb4` |
| surface | `/test-center/release-gate`, `/test-center/catalog`, Test Center backend project loader |
| severity | P1 |
| type | api/ui/project-scope/release-gate/catalog |
| expected | W14 must run against the same `proj_*` project created by Project Start/Execution Start, with charter, catalog, release gate and findings scoped to that project. |
| actual | Test Center project-mode helpers assumed legacy `project_*` records and could not reliably hydrate execution-start `proj_*` projects or attach catalog runs to the approved charter. |
| evidence | W14 self-test initially could not provide release/catalog proof for `proj_b9c142b06eb4`; after repair, browser run created charter `tc_03b0f3a6a1ad`, release candidate `rc_a8880b09719a`, branch `br_a3883e28a680`, and T0-T19 catalog runs all passed for the same project. |
| blocker | yes |
| stop_fix_restart_required | yes; W14 self-test restarted from Test Center charter/catalog/release flow |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## W14-F038: Truth Alignment Returned Empty Green Status

| Field | Value |
|---|---|
| finding_id | W14-F038 |
| project | AEIS self-test on P5 Restart `proj_b9c142b06eb4` |
| surface | `/test-center/truth-alignment` |
| severity | P1 |
| type | false-success/runtime-truth/product-matrix |
| expected | Truth Alignment must compare UI, API, docs/artifacts, audit chain and generated product features for the selected project. An empty matrix must not count as proof. |
| actual | The dashboard could show a 0-feature PASS shape instead of a project-specific feature matrix, so it was possible to miss drift between the P5 generated product and AEIS runtime evidence. |
| evidence | After repair, API and dashboard show `total_features=14`, `aligned=14`, `drift=0` for `proj_b9c142b06eb4`, covering CRM, funding, mobile approvals, automation runtime, governance, HumanGate, audit, memory, skills, guards, release rehearsal, Test Center, council evidence and operator runbook. |
| blocker | yes |
| stop_fix_restart_required | yes; W14 truth-alignment retest restarted after backend/frontend repair |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## W14-F039: Test Center Dashboard Mixed Global Evidence With Project Evidence

| Field | Value |
|---|---|
| finding_id | W14-F039 |
| project | AEIS self-test on P5 Restart `proj_b9c142b06eb4` |
| surface | `/test-center/dashboard` |
| severity | P1 |
| type | ui/project-scope/false-blocker |
| expected | Dashboard summary, release gate and recent findings must be scoped to the project under test. |
| actual | The dashboard used a hardcoded project and could mix unrelated historical findings with the active W14 project, making blocker status unreliable. |
| evidence | After repair, dashboard accepts `project_id=proj_b9c142b06eb4` and shows 1 approved charter, 0 P0/P1 blockers, release gate `production_ready`, and only project-scoped recent runs. |
| blocker | yes |
| stop_fix_restart_required | yes; dashboard retest restarted for the selected P5 project |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## W14-F040: Simulation Surface Was Read-Only For L0-L4

| Field | Value |
|---|---|
| finding_id | W14-F040 |
| project | AEIS self-test on P5 Restart `proj_b9c142b06eb4` |
| surface | `/test-center/simulation` |
| severity | P1 |
| type | ui/api/simulation/test-layer |
| expected | W14 simulation must be executable from dashboard and create isolated L0-L4 evidence for the selected project. |
| actual | The simulation page exposed state but no dashboard action to run a project-specific L0-L4 simulation branch. |
| evidence | After repair, dashboard button `Uruchom L0-L4` created branch `simb_37d564c2e14b`, contract `sc_588b0f592fbc`, layer `L4`, evidence count `1`, snapshot `sim_1778205191531`. |
| blocker | yes |
| stop_fix_restart_required | yes; simulation retest restarted after adding endpoint and dashboard action |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## W18-F041: Terminal Did Not Expose Runtime Metadata As Operator Badges

| Field | Value |
|---|---|
| finding_id | W18-F041 |
| project | AEIS self-test on P5 Restart `proj_b9c142b06eb4` |
| surface | `/terminal`, W18 SSE stream, terminal event injection and `/exec` |
| severity | P1 |
| type | observability/terminal/agent-role-council-env |
| expected | Operator terminal must show actions, project, agents/workers, roles, environments, council session and phase where events carry that metadata. |
| actual | Terminal rendered generic stream lines but did not preserve/render the operational metadata needed to follow council, roles, agents and environments from the dashboard. |
| evidence | After repair and backend restart, dashboard `/terminal` showed event `W14/P5 self-test...` with badges `project:proj_b9c142b06eb4`, `role:Auditor W14`, `agent:codex-terminal-auditor`, `env:local-only`, `council:council-p5-w14`, `phase:W14-self-test`. |
| blocker | partial |
| stop_fix_restart_required | yes; W18 terminal stream retested after backend restart |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS_WITH_SCOPE_NOTE |

## W14-F042: AutoRepair Mixed Global Historical Findings With Active Project

| Field | Value |
|---|---|
| finding_id | W14-F042 |
| project | Residual backlog closure after W14 self-test |
| surface | `/test-center/auto-repair`, `/api/v1/test-center/auto-repair` |
| severity | P2 |
| type | project-scope/audit-history/auto-repair |
| expected | AutoRepair ledger must show active findings for the selected project first and preserve unrelated historical findings as archived/global evidence, not active blockers. |
| actual | Before repair, the AutoRepair status endpoint listed all open findings globally, so old LoopGuard/history findings could pollute the current project's view. |
| evidence | After repair, endpoint accepts `project_id`, returns `project_scope`, `global_hidden_count`, `archived_global_count`, and `POST /auto-repair/archive-global` archives non-project findings without deleting them. Browser retest used `project_browser_residual_fix`, triggered LoopGuard and archived global findings. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## W14-F043: Theater Page Existed But Was Missing From Test Center Hub

| Field | Value |
|---|---|
| finding_id | W14-F043 |
| project | Residual backlog closure after W14 self-test |
| surface | `/test-center`, `/test-center/theater`, `/api/v1/test-center/health` |
| severity | P2 |
| type | ui/navigation/test-center |
| expected | Test Center hub and health catalog must expose Theater so operator can test agent topology from W14 navigation. |
| actual | `/test-center/theater` existed, but the Test Center hub had no card and health endpoint omitted `theater`. |
| evidence | Added Theater card and health listing. Browser retest confirmed `/test-center/theater` loads from the hub/navigation surface and WebSocket/runtime text is present. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## W18-F044: Project And Skills Modules Did Not Consistently Emit Semantic Terminal Events

| Field | Value |
|---|---|
| finding_id | W18-F044 |
| project | Residual backlog closure after W14 self-test |
| surface | project-start/planning/execution/council audit chain, skills lifecycle, W18 terminal |
| severity | P2 |
| type | observability/event-bus/terminal |
| expected | AEIS runtime modules must emit rich semantic events with project, role, agent, environment, council/session, phase, action and status so W18 terminal can show what is happening. |
| actual | Terminal could render metadata when supplied, but several core flows only wrote audit-chain records or skill lifecycle state without a rich W18 event envelope. |
| evidence | `_append_audit()` now mirrors every project audit-chain event into `sylion.core.event_bus`; the skills lifecycle long-run endpoint emits semantic `aeis.skills.lifecycle.*` events. Browser `/terminal` live retest showed `proj_terminal_semantic_live` and skills lifecycle event lines in stream. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## W09-F045: Autonomous Skill Lifecycle Had No Dedicated Long-Run Test

| Field | Value |
|---|---|
| finding_id | W09-F045 |
| project | Residual backlog closure after W14 self-test |
| surface | `/skills`, `/api/v1/skills/lifecycle/long-run-test` |
| severity | P2 |
| type | skill/lifecycle/autonomy/test-gap |
| expected | Dashboard must be able to prove demand-signal -> skill creation -> execution -> publication lifecycle in one controlled long-running test. |
| actual | Operator could register/execute/analyze pieces separately, but there was no dedicated lifecycle proof run. |
| evidence | Added `POST /api/v1/skills/lifecycle/long-run-test` with bounded cycles and dashboard button `Dlugi test lifecycle`. Browser retest created two lifecycle skills and returned `zaliczony`; API retest for `proj_terminal_semantic_check` returned `passed=true`, final lifecycle `PUBLISHED`. |
| blocker | yes |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS |

## UI-F046: Critical Residual Dashboard Surfaces Still Had English Labels

| Field | Value |
|---|---|
| finding_id | UI-F046 |
| project | Residual backlog closure after W14 self-test |
| surface | `/test-center`, `/test-center/auto-repair`, `/skills` |
| severity | P2 |
| type | ui/localization/polish |
| expected | Critical operator surfaces under current test must not expose obvious English operational labels where Polish dashboard language is expected. |
| actual | Residual labels included `LIVE`, `OFFLINE`, `finding_id`, `sev`, `LOC`, `Draft`, `Published`, `No skills registered yet`, `Manual`, `Auto`, `High/Medium/Low`, and missing Polish flow labels for the lifecycle test. |
| evidence | Replaced critical labels in AutoRepair and Skills surfaces, added Polish/ASCII-safe lifecycle labels, and exposed Theater in hub. ESLint passed with warnings only; TypeScript passed. |
| blocker | partial |
| stop_fix_restart_required | yes |
| owner | Repair Engineer |
| status | BLOCKER_FIXED_RETEST_PASS_WITH_SCOPE_NOTE |

## Finding Template

| Field | Value |
|---|---|
| finding_id | |
| project | |
| surface | |
| severity | P0/P1/P2/P3 |
| type | mock/stub/fallback/broken/api/ui/memory/guard/funding/skill/council/humangate |
| expected | |
| actual | |
| evidence | |
| blocker | yes/no |
| stop_fix_restart_required | yes/no |
| owner | |
| status | BLOCKER_OPEN / BLOCKER_FIXED / ACCEPTED_LIMITATION |
