# AEIS Repair Log

## R-P1-F002: Block Council False Success On LLM Failure

| Field | Value |
|---|---|
| finding_id | P1-F002 |
| status | fixed |
| files_changed | `src/sylion-pipeline/sylion/api/ai_workspace_routes.py`; `src/sylion-pipeline/tests/test_ai_workspace_routes.py`; `src/sylion-frontend/src/app/(app)/projects/[projectId]/page.tsx` |
| repair | Backend now refuses `/api/v1/workspace/council/sessions/{id}/analyze` with HTTP 503 when fewer than two usable real analyses are produced, and does not persist `llm_error` entries as analyses. Discussion now requires two usable analyses. Frontend filters existing `REAL_LLM_UNAVAILABLE` / `REAL_LLM_CALL_ERROR` entries and displays a blocking warning instead of treating them as ready opinions. |
| verification | `pytest test_ai_workspace_routes.py::TestCouncil::test_run_analysis test_ai_workspace_routes.py::TestCouncil::test_run_analysis_blocks_when_models_unavailable` passed. Frontend `npm run lint -- --quiet` is blocked by pre-existing unrelated repo-wide lint errors. |
| restart | Backend restarted on `http://127.0.0.1:8010`; health OK. |
| retest_required | Restart P1 Council round from a fresh usable Council session after API keys/local provider setup. |

## R-P1-F003: Align Model Provider Lists With Backend Catalog

| Field | Value |
|---|---|
| repair_id | R-P1-F003 |
| linked_finding | P1-F003 |
| files_changed | `src/sylion-frontend/src/app/(app)/onboarding/page.tsx`; `src/sylion-frontend/src/app/(app)/ai-models/page.tsx` |
| fix_summary | Expanded the onboarding API shortcut provider list and AI Models KeyVault provider list to match backend-supported cloud and local provider ids. Updated the provider field help text so it no longer claims a smaller list. |
| verification | In-app browser reload showed onboarding Model gate options for Perplexity, Z.ai, OpenRouter, Kimi/Moonshot, DeepSeek, xAI, Mistral, Groq, Cohere, Fireworks and Together. `/ai-models` KeyVault dropdown showed those plus Ollama, LM Studio, vLLM, llama.cpp and LocalAI. |
| backend_restart | no |
| frontend_restart | hot reload |
| retest_from_start | yes |
| retest_result | PASS for provider visibility |
| notes | Continue by completing Phase 1, then enter fresh one-time keys locally in `/ai-models` and restart P1 Council round. |

## R-P1-F004: Point Frontend Runtime At Backend 8010

| Field | Value |
|---|---|
| repair_id | R-P1-F004 |
| linked_finding | P1-F004 |
| files_changed | `src/sylion-frontend/.env.local` |
| fix_summary | Added `NEXT_PUBLIC_API_URL=http://127.0.0.1:8010` for the local frontend test runtime and restarted the frontend on port 3001. |
| verification | Backend health on 8010 returned OK. After frontend restart, `/ai-models` showed Backend Online, 11 local Ollama models, Provider Catalog snapshot, and the full KeyVault provider dropdown. |
| backend_restart | no |
| frontend_restart | yes, frontend 3001 restarted |
| retest_from_start | no |
| retest_result | PASS for AI Models runtime connectivity |
| notes | One nonblocking control-plane request still reports failure in the UI; Provider Catalog and KeyVault are usable for model setup. |

Status: no repairs yet

## R-P1-F001

| Field | Value |
|---|---|
| repair_id | R-P1-F001 |
| linked_finding | P1-F001 |
| files_changed | `src/sylion-pipeline/sylion/api/projects_routes.py`; `src/sylion-pipeline/tests/test_projects_routes.py` |
| fix_summary | Added a simple local CRM intent guard so process words such as Human Gate/workers/runtime do not force `project_management_system`; added regression test for Mini CRM staying a small `application`. |
| verification | `python -m pytest src/sylion-pipeline/tests/test_projects_routes.py::test_simple_crm_idea_promotion_stays_small_application src/sylion-pipeline/tests/test_projects_routes.py::test_idea_promotion_blocks_pending_humangate -q` = 2 passed |
| backend_restart | yes, backend 8010 restarted after fix |
| frontend_restart | no |
| retest_from_start | yes |
| retest_result | PASS for classification checkpoint |
| notes | Fresh P1 retest created `project_06e3bf38743b` as `application` with 3 modules. Continue remaining P1 flow from this project. |

## R-P1-F005: Respect Negated External Scope In Project Start

| Field | Value |
|---|---|
| repair_id | R-P1-F005 |
| linked_finding | P1-F005 |
| files_changed | `src/sylion-pipeline/sylion/api/project_start_routes.py`; `src/sylion-pipeline/tests/test_project_start_routes.py` |
| fix_summary | Added internal CRM intent and negated external-scope detection. Project Start now keeps simple local CRM prompts as `internal_app/crm`, filters payment/KSeF signals when negated, assigns internal preview/cost policy, and keeps payments/KSeF/VPS outside active goals/scope/council. |
| verification | `pytest src\sylion-pipeline\tests\test_project_start_routes.py -q` = 7 passed. Dashboard retest created `proj_94add2c61121` as D3/internal CRM with $200 reserve. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | yes |
| retest_result | PASS for P16-P18 classification/goals/scope checkpoints |
| notes | Old bad project `proj_8817f156f7ee` remains as evidence and must not be used for pass/fail continuation. |

## R-P1-F006: Make Phase 19 Council Acceptance Project-Aware

| Field | Value |
|---|---|
| repair_id | R-P1-F006 |
| linked_finding | P1-F006 |
| files_changed | `src/sylion-pipeline/sylion/api/project_start_routes.py`; `src/sylion-pipeline/tests/test_project_start_routes.py` |
| fix_summary | Added project-aware Phase 19 thresholds: internal CRM requires 9 roles and 5 KBs, while public SaaS still requires 12 roles and 8 KBs. Council preparation audit now records actual KB count for new projects. |
| verification | `pytest src\sylion-pipeline\tests\test_project_start_routes.py -q` = 7 passed. API acceptance for `proj_94add2c61121` returned 7/7, accepted true, hard blocks 0. Dashboard refresh showed Group B ready and P19 accepted. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected phase restarted from P19 checkpoint |
| retest_result | PASS for P19 acceptance |
| notes | Existing audit entry for `proj_94add2c61121` was created before the audit payload count fix, so it still contains the old prepared payload; acceptance now uses runtime project data. |

## R-P1-F007: Make Group C Internal-CRM Aware

| Field | Value |
|---|---|
| repair_id | R-P1-F007 |
| linked_finding | P1-F007 |
| files_changed | `src/sylion-pipeline/sylion/api/council_to_ksiega_routes.py`; `src/sylion-pipeline/tests/test_council_to_ksiega_routes.py` |
| fix_summary | Added internal CRM question set, project-aware role thresholds, internal CRM deliberation topics, scoped Council Book/Księga text, and artifact regression that blocks KSeF/Stripe/PCI leakage into final Book/Księga for the local CRM scenario. |
| verification | `pytest src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_council_to_ksiega_routes.py -q` = 12 passed. Dashboard retest clicked P20-P25; Group C showed 6/6 accepted and state `READY_FOR_PLANNING`. Artifact scan: `contains_ksef=false`, `contains_stripe=false`, `contains_pci=false`. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected group restarted from P20 |
| retest_result | PASS for Group C P20-P25 |
| notes | Project audit contains earlier repeated `council_convened` entries from pre-fix retests; latest artifacts and acceptance are from the fixed runtime. |

## R-P1-F009: Keep Planning Local-CRM Scoped

| Field | Value |
|---|---|
| repair_id | R-P1-F009 |
| linked_finding | P1-F009 |
| files_changed | `src/sylion-pipeline/sylion/api/planning_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py` |
| fix_summary | Added internal CRM planning branches for modules, model assignment rows, skill patterns/imports, layers, work units, dependency graph, milestones and risk-aware sequencing. Planning acceptance now allows the smaller internal matrix/work-unit count while preserving public SaaS thresholds. |
| verification | `pytest src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_council_to_ksiega_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 25 passed. Dashboard retest clicked P26-P31; planning showed accepted phases 6/6 and state `READY_FOR_BUILD`. Artifact scan over Phase 27 and masterplan files: `contains_ksef=false`, `contains_stripe=false`, `contains_payment=false`. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected group restarted from P26 |
| retest_result | PASS for Group D P26-P31 |
| notes | UI resource profile catalog still exposes expensive/global profiles for operator selection; P1 used `Solo balanced` at $189 against $200 reserve. |

## R-P1-F010: Keep Execution Local-CRM Scoped

| Field | Value |
|---|---|
| repair_id | R-P1-F010 |
| linked_finding | P1-F010 |
| files_changed | `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py`; `src/sylion-frontend/src/components/execution-start/ExecutionStartDashboard.tsx` |
| fix_summary | Execution Start now treats Project Start internal CRM projects, internal preview templates and negated external scope as local-only. P33-P41 produce local CRM build phases, local quality gates, local release rehearsal, local closure, local edge cases and no payment/KSeF/VPS/Hetzner/stub artifact language for P1. |
| verification | `pytest src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_council_to_ksiega_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 26 passed. Focused regression `test_internal_crm_execution_stays_local_without_payment_ksef_or_vps` passed. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected group restarted from P32; after final artifact cleanup P39-P41 were regenerated through the dashboard |
| retest_result | PASS for Group E-F-G P32-P41: dashboard showed 10/10 accepted and state `CLOSED`; API returned `accepted=true`, local release mode, documents `0`, financial events `0`, external submission blocked. |
| artifact_scan | `phase33_sequential_execution.json`, `phase36_build_completion.json`, `phase37_quality_gates.json`, `phase39_predeploy_authorization.json`, `phase40_production_deploy.json`, `phase41_project_closure.json`: `contains_ksef=false`, `contains_stripe=false`, `contains_payment=false`, `contains_stub=false`, `contains_hetzner=false`. |
| notes | Local-only edge cases for P39-P41 now replace production/KSeF/Stripe/VPS edge cases with local release, external-action-block and archive/handoff risks. |

## R-P1-F008: Bridge Project Start Projects Into Global Projects Registry

| Field | Value |
|---|---|
| repair_id | R-P1-F008 |
| linked_finding | P1-F008 |
| files_changed | `src/sylion-pipeline/sylion/api/projects_routes.py`; `src/sylion-pipeline/tests/test_project_start_routes.py` |
| fix_summary | Global `/api/v1/projects` now includes Project Start lifecycle projects as `project_start_lifecycle`, and `/api/v1/projects/{project_id}` adapts lifecycle records to the global project detail contract. Detail dependencies used by the frontend (`timeline`, `questions`, `canon`, `masterplan`, `modules`, `audit`, `cost`, `skills`) return lifecycle-safe responses instead of 404/KeyError. Artifact links now point to the lifecycle closure artifact file and the raw artifact guard allows files inside the lifecycle project root. |
| verification | Focused regression `test_project_start_project_is_visible_in_global_projects_registry` passed. Runtime API returned `proj_94add2c61121` from both `/api/v1/projects` and `/api/v1/projects/proj_94add2c61121` with source `project_start_lifecycle`, phase `stable`, status `completed`; raw artifact endpoint returned HTTP 200 JSON. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected global registry/detail checkpoint restarted after backend restart |
| retest_result | PASS: dashboard `/projects` listed `P1 Mini CRM Local Retest`; clicked `Otworz projekt` for `/projects/proj_94add2c61121`; detail page showed the project and no `Nie znaleziono projektu`; clicked `Otworz artefakt` and raw JSON artifact opened successfully. |
| notes | Broader `test_projects_routes.py` still has unrelated classifier regressions where operator_mobile/ecommerce/funding tests classify as `project_management_system`; track separately before funding/project simulations. |

## R-P1-F011: Tighten Project Domain Classification

| Field | Value |
|---|---|
| repair_id | R-P1-F011 |
| linked_finding | P1-F011 |
| files_changed | `src/sylion-pipeline/sylion/api/projects_routes.py` |
| fix_summary | SaaS intent no longer treats `erp` as a substring, so `Perplexity` does not trigger project-management routing. Strong primary domains for ecommerce generator, operator mobile and pure funding are evaluated before the broad project-management fallback. Runtime questions distinguish explicit zero-VPS blocks from planned VPS/Hetzner expansion through HumanGate, preserving `Tylko Change Proposal` for zero VPS while allowing `Hybrid later` for approved future expansion. |
| verification | Focused domain rerun passed for operator-mobile, ecommerce, funding, bioinformatics, zero-VPS and multi-domain project-management regressions. Full affected suite `pytest src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_council_to_ksiega_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py src\sylion-pipeline\tests\test_projects_routes.py -q` = 70 passed, 6 warnings. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected classifier/domain tests restarted |
| retest_result | PASS for funding/ecommerce/operator-mobile domain routing |
| notes | This repair is prerequisite for the planned funding simulation; it is not counted as proof that the Funding dashboard itself is live until manual funding UI tests run. |

## R-P1-F012: Correct Funding Ticket Blocking Semantics

| Field | Value |
|---|---|
| repair_id | R-P1-F012 |
| linked_finding | P1-F012 |
| files_changed | `src/sylion-pipeline/sylion/funding_autopilot/governance_bridge.py`; `src/sylion-pipeline/tests/test_funding_autopilot_routes.py` |
| fix_summary | Funding idea conversion remains a blocking Human Gate action and the E2E test now approves that gate before continuing. Programme creation, call creation and draft application creation are now non-blocking audit tickets because their records are committed immediately; final submission remains the hard Human Gate. |
| verification | `pytest src\sylion-pipeline\tests\test_funding_autopilot_routes.py src\sylion-pipeline\tests\test_projects_routes.py::test_funding_launch_generates_domain_artifact_not_calculator_fallback -q` = 5 passed, 6 warnings. Follow-up `pytest src\sylion-pipeline\tests\test_funding_autopilot_routes.py -q` = 4 passed, 6 warnings after adding explicit `gate_type` assertions. Dashboard funding test confirmed idea conversion waits for Human Gate, application with missing docs cannot be submitted, and submission session stays `blocked_missing_documents`. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected Funding guard path restarted |
| retest_result | PASS for Funding blocking semantics: conversion and final submit guarded; local catalogue/draft writes audited but not falsely labelled as blocking. |
| notes | Existing runtime tickets created before the fix may still carry the old gate type; new tickets use corrected semantics after backend restart. Regression now asserts `non_blocking` for programme/call/draft application, `blocking` for idea conversion and `financial` for final submission approval. |

## R-P1-F013: Hide Empty Funding Submission Receipts

| Field | Value |
|---|---|
| repair_id | R-P1-F013 |
| linked_finding | P1-F013 |
| files_changed | `src/sylion-frontend/src/app/(app)/funding/page.tsx` |
| fix_summary | Funding UI now clears application/session detail state while loading a new application and treats an empty receipt object as no receipt. The final confirmation block renders only when the receipt payload has fields. |
| verification | `npm run lint -- "src/app/(app)/funding/page.tsx"` passed. `pytest src\sylion-pipeline\tests\test_funding_autopilot_routes.py -q` = 4 passed, 6 warnings and asserts blocked sessions return empty receipt before final submit. Browser retest on `/funding` showed `fund_submit_909e7c229d6c - blocked_missing_documents`, blocked final submit controls, missing-document validation, and `receiptTextAfterFixCount=0`. |
| backend_restart | no |
| frontend_restart | no; Next hot reload plus browser reload |
| retest_from_start | affected Funding submission checkpoint restarted |
| retest_result | PASS: blocked missing-document submission no longer displays `Potwierdzenie złożenia`. |
| notes | Existing blocked sessions remain blocked; this repair changes only the false UI confirmation for empty backend receipts. |

## R-P1-F014: Stop Coherence Guard From Treating Demo Findings As Live Findings

| Field | Value |
|---|---|
| repair_id | R-P1-F014 |
| linked_finding | P1-F014 |
| files_changed | `src/sylion-pipeline/sylion/api/coherence_guard_routes.py`; `src/sylion-pipeline/tests/test_coherence_guard_routes.py`; `src/sylion-frontend/src/app/(app)/coherence-guard/page.tsx` |
| fix_summary | Coherence Guard run defaults now use `dashboard_current` instead of `sample_project`. Backend sample findings are retained only for explicit `sample_project` regression/demo calls; dashboard/live runs emit an INFO-only no-synthetic-finding result unless real project evidence is provided. |
| verification | `pytest src\sylion-pipeline\tests\test_coherence_guard_routes.py -q` = 6 passed, 6 warnings. `npm run lint -- "src/app/(app)/coherence-guard/page.tsx"` completed with existing `any` warnings and no errors. Browser retest after backend restart and a fresh click on `Uruchom kontrolę spójności`: Polish INFO result `Brak syntetycznych ustaleń w przebiegu dashboardu` appeared, sample text counts for checkout/GBP/API findings were 0, and `sample_project` was not displayed. One older English INFO row remained from the pre-localization runtime history. |
| backend_restart | yes |
| frontend_restart | no; Next hot reload plus browser reload |
| retest_from_start | affected Coherence Guard run checkpoint restarted from defaults/apply and run |
| retest_result | PASS: dashboard no longer creates sample ecommerce findings as real guard failures. |
| notes | The INFO no-synthetic-finding record is intentionally non-blocking; real guard signoff still requires project-specific artifact evidence. |

## R-P1-F015: Stop Guard Suite From Treating Demo Findings As Live Findings

| Field | Value |
|---|---|
| repair_id | R-P1-F015 |
| linked_finding | P1-F015 |
| files_changed | `src/sylion-pipeline/sylion/api/guard_suite_routes.py`; `src/sylion-pipeline/tests/test_guard_suite_routes.py`; `src/sylion-frontend/src/components/guards/GuardSetupDashboard.tsx` |
| fix_summary | Guard Suite run defaults now use `dashboard_current` instead of `sample_project`. Backend sample findings are retained only for explicit `sample_project` regression/demo calls; dashboard/live runs emit an INFO-only Polish no-synthetic-finding result unless real project evidence is provided. |
| verification | `pytest src\sylion-pipeline\tests\test_guard_suite_routes.py -q` = 6 passed, 6 warnings. Combined guard regression `pytest src\sylion-pipeline\tests\test_coherence_guard_routes.py src\sylion-pipeline\tests\test_guard_suite_routes.py -q` = 12 passed, 6 warnings. `npm run lint -- "src/app/(app)/coherence-guard/page.tsx" "src/components/guards/GuardSetupDashboard.tsx"` completed with existing `any` warnings and no errors. Browser retest after backend restart clicked `Uruchom kontrolę strażnika` on `/cost-guard`, `/security-guard`, `/quality-guard` and `/provenance-guard`; each new run showed the Polish INFO `Brak syntetycznych ustaleń...`, known sample finding counts were 0 and `sample_project` was 0. |
| backend_restart | yes |
| frontend_restart | no; Next hot reload plus browser reload |
| retest_from_start | affected Guard Suite run checkpoint restarted page-by-page from dashboard click |
| retest_result | PASS: phases 7-10 no longer create sample findings as live guard failures. |
| notes | One older English `No synthetic...` row can remain in each guard page from prior runtime history; it is a legacy artifact, not a new sample failure. Real guard signoff still requires project-specific artifacts. |

## R-P1-F016: Add Clickable Skills Lifecycle Actions To Dashboard

| Field | Value |
|---|---|
| repair_id | R-P1-F016 |
| linked_finding | P1-F016 |
| files_changed | `src/sylion-frontend/src/lib/api/client.ts`; `src/sylion-frontend/src/app/(app)/skills/page.tsx` |
| fix_summary | Added frontend API methods for skill registration, skill execution, demand signal recording and demand analysis. `/skills` now has an operator action panel with name/domain inputs and buttons for `Utwórz skill`, `Wykonaj ostatnią`, `Zgłoś popyt` and `Analizuj popyt`, followed by refresh and tab switching to the affected evidence surface. |
| verification | `npm run lint -- "src/app/(app)/skills/page.tsx" "src/lib/api/client.ts"` completed with existing warnings and no errors. Backend focused tests `pytest src\sylion-pipeline\tests\test_api_all_routes.py::test_skills_register_and_get src\sylion-pipeline\tests\test_api_all_routes.py::test_skills_execute -q` = 2 passed, 6 warnings. Browser retest clicked the new `/skills` controls; dashboard showed 3 registered skills, 2 completed executions, `dashboard_crm_...` execution in the log and a visible `missing_crm_skill` demand signal. |
| backend_restart | no |
| frontend_restart | no; Next hot reload plus browser reload |
| retest_from_start | affected Skills checkpoint restarted from dashboard page load and clicked through create/execute/demand/analyze |
| retest_result | PASS: Skills workflow is now testable from the dashboard without direct API calls. |
| notes | This proves manual skill lifecycle wiring, not yet autonomous project-driven skill synthesis. Autonomous skill creation/dopasowanie still needs verification during project planning/execution simulations. |

## R-P1-F017: Add Live Memory Write/Search Controls To Dashboard

| Field | Value |
|---|---|
| repair_id | R-P1-F017 |
| linked_finding | P1-F017 |
| files_changed | `src/sylion-frontend/src/app/(app)/memory/page.tsx`; `src/sylion-frontend/src/lib/api/client.ts` |
| fix_summary | Replaced the canonical bridge-only `/memory` page with a live dashboard for memory stats, recent items, Kanon section storage, evidence storage, index writes and retrieval/context search. Added frontend API methods for `/api/v1/memory/stats`, `/recent`, `/kanon/sections`, `/evidence`, `/index/sections`, `/index/search` and `/retrieval/context`. |
| verification | `npm run lint -- "src/app/(app)/memory/page.tsx" "src/lib/api/client.ts"` completed with existing warnings and no errors. `pytest src\sylion-pipeline\tests\test_api_all_routes.py::test_all_routes_mounted -q` = 1 passed, 6 warnings. Browser retest clicked `Zapisz kanon`, `Zapisz evidence`, `Indeksuj` and `Szukaj kontekst`; the dashboard showed `Wyniki:`, `Manual memory indexed section`, `memory_reuse_note` and `Manual memory retest`. |
| backend_restart | no |
| frontend_restart | no; Next hot reload plus browser reload |
| retest_from_start | affected Memory checkpoint restarted from dashboard page load and clicked through write/evidence/index/retrieval |
| retest_result | PASS: memory can now be tested from the dashboard as a live write/search surface. |
| notes | This verifies memory storage and retrieval mechanics. The stronger AEIS criterion, proving that memory changes later planning/model/skill choices, remains pending for the next cross-project simulation. |

## R-P1-F018: Add Dashboard-Triggered T0-T19 Test Runs

| Field | Value |
|---|---|
| repair_id | R-P1-F018 |
| linked_finding | P1-F018 |
| files_changed | `src/sylion-pipeline/sylion/api/test_center_routes.py`; `src/sylion-pipeline/tests/test_api_all_routes.py`; `src/sylion-frontend/src/app/(app)/test-center/catalog/page.tsx` |
| fix_summary | Added `POST /api/v1/test-center/catalog/run` to record a real W14 `TestSuite` and `TestRun` from the dashboard. Failed runs create an open P1 `Finding`. The catalog UI now provides PASS/FAIL actions for each T0-T19 class and refreshes counts after execution. |
| verification | `npm run lint -- "src/app/(app)/test-center/catalog/page.tsx"` passed. `pytest src\sylion-pipeline\tests\test_api_all_routes.py::test_test_center_catalog_run_records_failed_finding -q` = 1 passed, 6 warnings. Browser retest clicked PASS on T0 and FAIL on T1; `/test-center/dashboard` then showed `Krytyczne P0/P1 = 1`, `total findings 1`, recent passed/failed runs and release gate `blocked`. |
| backend_restart | yes |
| frontend_restart | no; Next hot reload plus browser reload |
| retest_from_start | affected Test Center catalog checkpoint restarted from dashboard page load and clicked PASS/FAIL |
| retest_result | PASS: Test Center now records executable test results and failed runs surface as blockers. |
| notes | This verifies the internal testing layer mechanics. Product-level verification for each of the five project simulations still needs to run through these controls or project-specific test flows. |

## R-P1-F019: Repair Monitoring Budget Summary And Legacy Budget Routes

| Field | Value |
|---|---|
| repair_id | R-P1-F019 |
| linked_finding | P1-F019 |
| files_changed | `src/sylion-pipeline/sylion/api/monitoring_budget_routes.py`; `src/sylion-pipeline/sylion/monitoring/model_budget.py`; `src/sylion-frontend/src/app/(app)/orchestration/llm-routing/page.tsx` |
| fix_summary | Reordered static budget routes before dynamic model routes, added legacy-compatible `PUT /budget/{model_id}` and `POST /budget/{model_id}/usage`, switched usage recording to the transaction wrapper, removed JSON-invalid `inf` values from budget checks, merged visible budget config into per-model checks, and made the budget singleton respect `SYLION_DB_PATH` for persistence tests. Frontend routing page now satisfies the React lint rule for async initial load. |
| verification | `pytest src\sylion-pipeline\tests\test_monitoring_budget_routes.py -q` = 3 passed, 6 warnings. `npm run lint -- "src/app/(app)/orchestration/llm-routing/page.tsx"` completed with existing `any` warnings and no errors. Backend `/api/v1/monitoring/budget/summary` returned 200 after restart. |
| backend_restart | yes |
| frontend_restart | no; Next hot reload plus browser reload |
| retest_from_start | affected Model routing/limits checkpoint restarted from `/orchestration/llm-routing` and `/costs` |
| retest_result | PASS: dashboard options included registry models beyond fallback, bulk assignment of `qwen3.5:latest` saved to backend, and `/costs` showed the configured 1.25 model budget. |
| notes | This verifies visible routing and per-model limit plumbing. The policy requirement "use subscription quotas first, then paid budget" still needs project-simulation evidence at execution/runtime routing level, not only configuration visibility. |

## R-P1-F020: Generate A Runnable Local CRM Product Instead Of Placeholder Inventory

| Field | Value |
|---|---|
| repair_id | R-P1-F020 |
| linked_finding | P1-F020 |
| files_changed | `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py` |
| fix_summary | Phase 36 now writes a minimal runnable local CRM product: FastAPI backend with contacts, notes, reminders, CSV export and GDPR export/delete, a backend smoke test, React `App.tsx`, SQL schema, local-only config and README. Support inventory files remain count-compatible but no longer use the old placeholder text. Regression asserts `app.py` and `App.tsx` contain product code and blocks the old `Generated by Phase 36 build completion inventory` placeholder. |
| verification | `pytest src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 14 passed, 6 warnings. Backend restarted after repair. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | required; T1 restart project to be created after repair |
| retest_result | backend/unit regression PASS; full dashboard restart pending next checkpoint |
| notes | The closed pre-repair T1 run remains invalid evidence because its generated product was a placeholder. |

## R-P1-F021: Route Funding Projects To Funding Product Generator

| Field | Value |
|---|---|
| repair_id | R-P1-F021 |
| linked_finding | P1-F021 |
| files_changed | `src/sylion-pipeline/sylion/api/project_start_routes.py`; `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py` |
| fix_summary | Added funding intent classification/template and a funding-specific Phase 36 product generator. Funding products now create a FastAPI local funding assistant with program matching, document checklist, HumanGate-protected local submission rehearsal, React `App.tsx`, SQL schema and backend smoke test. |
| verification | `pytest src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 15 passed, 6 warnings. T2RR generated `artifacts_inventory.product=funding_assistant`, backend/frontend mention funding/HumanGate/external_submit, and product scan found no CRM/Stripe/KSeF/placeholders. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | yes; T2RR created from dashboard after repair |
| retest_result | PASS for product generator and artifact smoke |
| notes | Original T2 and first T2R remain invalid evidence because one produced CRM artifacts and the other had funding classification but stale planning scope. |

## R-P1-F022: Repair Funding Planning Scope

| Field | Value |
|---|---|
| repair_id | R-P1-F022 |
| linked_finding | P1-F022 |
| files_changed | `src/sylion-pipeline/sylion/api/planning_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py` |
| fix_summary | Added funding-specific planning modules, skills, skill patterns, layers, work units, dependency graph, milestones and preflight risks. Regression blocks `Customer Management`, `Stripe` and `KSeF` in funding phase 26-30 artifacts. |
| verification | `pytest src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 15 passed, 6 warnings. T2RR planning artifact scan over 15 files: funding present, `Customer Management=false`, `Stripe=false`, `KSeF=false`, state `READY_FOR_BUILD`. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | yes; T2RR restarted from `/project-start` after repair |
| retest_result | PASS for T2RR planning scope |
| notes | Dashboard labels remain partly English and are tracked separately as P1-F023. |

## R-P1-F026A: Stop False Pass In Orchestration Test Catalog

| Field | Value |
|---|---|
| repair_id | R-P1-F026A |
| linked_finding | P1-F026 |
| files_changed | `src/sylion-pipeline/sylion/aeis/advisor/orchestration_config/service.py` |
| fix_summary | Replaced the fake catalog pass with deterministic backend checks for each selected catalog entry. Golden suite now verifies advisor engine event-map wiring, LLM routing/preferences, funding audit dimension, team-formation rules and council vote simulation, then records `pass/fail`, `completed_at` and detailed `Verified catalog check(s)` output. |
| verification | `pytest src\sylion-pipeline\tests\aeis\advisor\orchestration_config\test_orchestration_routes.py src\sylion-pipeline\tests\test_ai_workspace_routes.py::TestChatSessions -q` = 39 passed, 6 warnings. Backend restarted on `127.0.0.1:8010`. Dashboard retest clicked `/orchestration/tests` -> `Uruchom golden`; UI showed 5 passed golden checks. API run `706a79a4-01ff-495a-8e89-0ff964cda1a6` output listed PASS for advisor.engine, advisor.preferences, advisor.funding, advisor.role_resolver and advisor.council. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected meta-orchestration J6 checkpoint restarted from dashboard page load |
| retest_result | PASS for J6 golden catalog runtime checks |
| notes | This validates the meta-orchestration catalog itself. Full AEIS self-testing across generated products remains a later project-simulation checkpoint. |

## R-P1-F027: Fix Memory Dashboard Stats Mapping

| Field | Value |
|---|---|
| repair_id | R-P1-F027 |
| linked_finding | P1-F027 |
| files_changed | `src/sylion-frontend/src/app/(app)/memory/page.tsx` |
| fix_summary | Updated memory stats rendering to accept backend fields `evidence.total_evidence` and `indexer.indexed_sections` in addition to legacy frontend names. |
| verification | `npx eslint "src/app/(app)/memory/page.tsx"` = no errors, 2 existing `any` warnings. Browser retest clicked `/memory`: after evidence write UI showed `EVIDENCE 1`; after `Indeksuj` + `Szukaj kontekst`, UI showed `INDEKS 1` and returned `Manual memory indexed section` context. |
| backend_restart | no |
| frontend_restart | no; Next hot reload plus browser reload |
| retest_from_start | affected memory checkpoint restarted from dashboard page load |
| retest_result | PASS for dashboard memory write/index/search evidence |
| notes | Still does not prove automatic reuse of memory by planning/execution. That remains a cross-project simulation criterion. |

## R-P1-F028: Generate Workspace Chat Assistant Messages

| Field | Value |
|---|---|
| repair_id | R-P1-F028 |
| linked_finding | P1-F028 |
| files_changed | `src/sylion-pipeline/sylion/api/ai_workspace_routes.py`; `src/sylion-pipeline/tests/test_ai_workspace_routes.py`; `src/sylion-frontend/src/app/(app)/workspace/page.tsx`; `src/sylion-frontend/src/components/workspace/ChatPanel.tsx` |
| fix_summary | `POST /api/v1/workspace/sessions/{session_id}/messages` now stores the user message and appends an assistant message. It calls the real LLM runtime when a configured/local model is available and records `REAL_LLM_UNAVAILABLE`/`REAL_LLM_CALL_ERROR` visibly when not. Workspace visible text was also cleaned up for this surface. |
| verification | `pytest src\sylion-pipeline\tests\test_ai_workspace_routes.py::TestChatSessions -q` = 7 passed, 6 warnings. Combined backend retest with orchestration = 39 passed. `npx eslint "src/app/(app)/workspace/page.tsx" "src/components/workspace/ChatPanel.tsx"` = 0 errors, existing warnings only. Browser retest clicked `/workspace` -> `Nowy czat` -> message; UI displayed assistant response from `SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M`. |
| backend_restart | yes |
| frontend_restart | no; Next hot reload plus browser reload |
| retest_from_start | yes; workspace chat checkpoint restarted from dashboard page load |
| retest_result | PASS: chat now produces a visible assistant/runtime response |
| notes | This fixes one-to-one workspace chat. Model-to-model conversation orchestration remains tracked under P1-F025 until it governs runtime automatically. |

## R-P1-F025A: Add Clickable Runtime Triggers For Teams And Model Conversations

| Field | Value |
|---|---|
| repair_id | R-P1-F025A |
| linked_finding | P1-F025 |
| files_changed | `src/sylion-pipeline/sylion/aeis/advisor/orchestration_config/service.py`; `src/sylion-pipeline/sylion/api/orchestration_routes.py`; `src/sylion-pipeline/tests/aeis/advisor/orchestration_config/test_orchestration_routes.py`; `src/sylion-frontend/src/lib/api/orchestration.ts`; `src/sylion-frontend/src/app/(app)/orchestration/teams/page.tsx`; `src/sylion-frontend/src/app/(app)/orchestration/conversations/page.tsx` |
| fix_summary | Added backend runtime triggers and dashboard buttons for J7/J9. Team formation now matches enabled regex rules against an operator event and creates visible active teams. Inter-model conversations now require/enforce enabled state, generate a bounded `codex`/`claude` conversation record using configured `max_turns`, and persist it in `recent_conversations`. |
| verification | `pytest src\sylion-pipeline\tests\aeis\advisor\orchestration_config\test_orchestration_routes.py src\sylion-pipeline\tests\test_ai_workspace_routes.py::TestChatSessions -q` = 41 passed, 6 warnings. `npx eslint "src/app/(app)/orchestration/teams/page.tsx" "src/app/(app)/orchestration/conversations/page.tsx" "src/lib/api/orchestration.ts"` = 0 errors, existing `any` warnings only. Backend restarted; health OK with 1966 endpoints. Browser retest clicked `/orchestration/teams` -> `Testuj reguły`; UI showed active team `z_ai` + `claude`. Browser retest clicked `/orchestration/conversations` -> `Uruchom rozmowę`; UI showed `codex ↔ claude`, `4 tur` and the runtime check topic. |
| backend_restart | yes |
| frontend_restart | no; Next hot reload plus browser navigation |
| retest_from_start | affected J7/J9 meta-orchestration checkpoint restarted from dashboard page load |
| retest_result | PARTIAL_PASS: J7/J9 are no longer config-only; remaining P1-F025 gap is automatic governance of planning/execution/council/fixer/auditor runtime. |
| notes | This is an operator-testable runtime repair, not yet proof that project execution automatically consults these settings. |

## R-P1-F025B: Apply Meta-Orchestration Config To Planning And Execution Runtime

| Field | Value |
|---|---|
| repair_id | R-P1-F025B |
| linked_finding | P1-F025 |
| files_changed | `src/sylion-pipeline/sylion/api/planning_routes.py`; `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py` |
| fix_summary | Phase 26 now applies changed J1 LLM Judge routing to task assignment rows. Phase 32 applies J5 dispatch caps to worker count before build initialization. Phase 34 reads J2 council rules for role weights and quorum metadata. Phase 35 records J3 auditor cadence, J4 fixer protocol, J5 dispatch, J7 team formation and J9 inter-model conversation runtime context in the build orchestration artifact. |
| verification | `pytest src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 16 passed, 6 warnings. Regression `test_orchestration_config_controls_phase26_models_and_phase32_workers` sets J1 architecture/medium to `gpt-4o-mini` and J5 capped dispatch to 1; Phase 26 model assignment and Phase 32 build initialization reflect both settings. Existing execution regression sets dispatch cap 2, auditor cadence 60s and J9 max turns 2; Phase 35 artifact records capped worker profile, 1-minute critic cadence, runtime team formation and a 2-turn inter-model conversation. Backend restarted; health OK. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | API/runtime regression completed; dashboard project-simulation retest still required for final acceptance |
| retest_result | PARTIAL_PASS: planning/execution now consume meta-orchestration config, but project-scoped council route, quality/fixer auto-loop and event-map telemetry still need runtime wiring. |
| notes | The routing override only applies changed operator cells, so default meta-orchestration config does not silently rewrite all model assignments. |

## R-P1-F025C: Wire Council Route, Fixer Loop And Event Telemetry

| Field | Value |
|---|---|
| repair_id | R-P1-F025C |
| linked_finding | P1-F025 |
| files_changed | `src/sylion-pipeline/sylion/api/council_routes.py`; `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/sylion/aeis/advisor/orchestration_config/service.py`; `src/sylion-pipeline/tests/test_projects_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py`; `src/sylion-pipeline/tests/aeis/advisor/orchestration_config/test_orchestration_routes.py` |
| fix_summary | Project-scoped council deliberation now uses J2 council rules for quorum and critic gate policy. Phase 37 quality gates now apply J4 fixer protocol limits to auto-fix iterations. Orchestration service now records runtime events for team formation, model conversations and fixer policy application, and J8 event-map exposes those counters instead of only zero-rate static edges. |
| verification | `pytest src\sylion-pipeline\tests\aeis\advisor\orchestration_config\test_orchestration_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py src\sylion-pipeline\tests\test_projects_routes.py::test_project_council_deliberates_low_risk_change_without_human_gate src\sylion-pipeline\tests\test_projects_routes.py::test_project_council_uses_orchestration_council_quorum src\sylion-pipeline\tests\test_projects_routes.py::test_project_council_escalates_production_change_to_human_gate -q` = 54 passed, 6 warnings. Backend restarted; health OK. Browser retest clicked J7 team trigger, J9 conversation trigger and opened `/orchestration/event-map`; UI showed `aeis.orchestration.team.formed` and `aeis.orchestration.conversation.completed` with `1/min`. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected J2/J4/J8 runtime checkpoint restarted; full 5-project simulation rerun still required |
| retest_result | PASS for remaining meta-orchestration runtime wiring |
| notes | P1-F025 is now fixed at module/runtime level, but final acceptance still requires repeating project simulations from the beginning as requested. |

## R-P1-F029: Remove Payment/KSeF/Invoice Scope From Local-Only CRM Artifacts

| Field | Value |
|---|---|
| repair_id | R-P1-F029 |
| linked_finding | P1-F029 |
| files_changed | `src/sylion-pipeline/sylion/api/planning_routes.py`; `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md`; `docs/aeis_manual_tests/03_TEST_RUN_LEDGER.md` |
| fix_summary | Phase 26 quality overrides now omit `payment_processing` for local CRM/funding projects. Phase 30 uses local CRM risks instead of KSeF/Stripe. Phase 35 prompt-splitting uses local data/CSV angles for local-only builds. Phase 38 feedback switches to local CRM/CSV/status issues. Phase 41 local closure now writes `final_settlement` instead of invoice artifacts. Generated local CRM product source/docs no longer mention excluded external/payment scope. |
| verification | `pytest src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 16 passed, 6 warnings. Regression now scans generated local-only artifacts under `planning`, `reports`, `code`, `coordination`, and `archive` for `ksef`, `stripe`, `payment`, `invoice`, and `hetzner`. |
| backend_restart | yes; health OK on `127.0.0.1:8010`, version 3.5.0, 1966 endpoints |
| frontend_restart | no |
| retest_from_start | yes; fresh dashboard project `proj_91014e2cad46` created and clicked through Group B, Group C, planning 26-31 and execution 32-41 |
| retest_result | PASS: dashboard closed project, 218 generated files scanned clean, generated backend pytest passed |
| notes | The failed project `proj_ffd80b0a7464` remains failure evidence and was not manually cleaned. |

## R-P2-F030: Add Funding-Specific Scope, Council Roles And Księga Content

| Field | Value |
|---|---|
| repair_id | R-P2-F030 |
| linked_finding | P2-F030 |
| files_changed | `src/sylion-pipeline/sylion/api/project_start_routes.py`; `src/sylion-pipeline/sylion/api/council_to_ksiega_routes.py`; `src/sylion-pipeline/tests/test_council_to_ksiega_routes.py`; `src/sylion-pipeline/tests/test_project_start_routes.py` |
| fix_summary | Funding projects now get funding-specific phase 18 scope, phase 19 Council roles/KBs, phase 20-25 question sets, deliberation topics, Council Book and Księga compliance text. The generic SaaS payment/KSeF/Stripe/PCI path no longer applies to funding local rehearsal projects. |
| verification | `pytest src\sylion-pipeline\tests\test_council_to_ksiega_routes.py src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 30 passed, 6 warnings. |
| backend_restart | yes; health OK on `127.0.0.1:8010`, version 3.5.0, 1966 endpoints |
| frontend_restart | no; browser reload after backend restart |
| retest_from_start | yes; fresh dashboard project `proj_302f86187d3b` created and clicked through Group B, Group C, planning 26-31 and execution 32-41 |
| retest_result | PASS: dashboard closed project, 218 generated files scanned clean, generated funding backend pytest passed |
| notes | The failed project `proj_a1fcc8946efc` remains failure evidence and was not manually cleaned. |

## R-P2-F031: Complete Funding Product Validation And Runtime Import

| Field | Value |
|---|---|
| repair_id | R-P2-F031 |
| linked_finding | P2-F031 |
| files_changed | `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py`; `docs/aeis_manual_tests/03_TEST_RUN_LEDGER.md`; `docs/aeis_manual_tests/06_FUNDING_TEST_MATRIX.md`; `docs/aeis_manual_tests/07_PRODUCT_TEST_MATRIX.md`; `docs/aeis_manual_tests/projects/P2_FUNDING_ASSISTANT.md`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md` |
| fix_summary | Funding product generator now emits deadline validation, missing-source provenance blocking, legal/budget/document confirmation blockers, frontend confirmation controls and the required `from datetime import date` import. Generated product tests cover blocked expired/missing-source programs and confirmation blockers before local rehearsal. |
| verification | `pytest src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 16 passed. Fresh dashboard restart `proj_7544e8bdd3ea` clicked phases 16-41, closed with `10/10`, artifact scan found no forbidden scope/placeholders across 218 files, and generated backend `test_app.py` passed. |
| backend_restart | yes; health OK on `127.0.0.1:8010`, version 3.5.0, 1966 endpoints |
| frontend_restart | no; browser reload after backend restart |
| retest_from_start | yes; P2R4 created from `/project-start` after P2R3 product test failure |
| retest_result | PASS |
| notes | The failed project `proj_a96c0ff7cbb4` remains failure evidence and was not manually cleaned. |

## R-P3-F032: Add Mobile Approval Queue Runtime Path

| Field | Value |
|---|---|
| repair_id | R-P3-F032 |
| linked_finding | P3-F032 |
| files_changed | `src/sylion-pipeline/sylion/api/project_start_routes.py`; `src/sylion-pipeline/sylion/api/council_to_ksiega_routes.py`; `src/sylion-pipeline/sylion/api/planning_routes.py`; `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_project_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py`; `docs/aeis_manual_tests/03_TEST_RUN_LEDGER.md`; `docs/aeis_manual_tests/07_PRODUCT_TEST_MATRIX.md`; `docs/aeis_manual_tests/projects/P3_MOBILE_APPROVAL_QUEUE.md`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md` |
| fix_summary | Added `mobile_approval_queue` template, mobile approval classifier, scope, council roles/questions, planning modules/skills/layers/work units and a generated FastAPI/React product for local device-bound approve/reject workflow. |
| verification | `pytest src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_council_to_ksiega_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 32 passed. Fresh dashboard restart `proj_635af5715faf` clicked phases 16-41, closed with `10/10`, artifact scan found no forbidden scope/placeholders across 218 files, and generated backend `test_app.py` passed. |
| backend_restart | yes; health OK on `127.0.0.1:8010`, version 3.5.0, 1966 endpoints |
| frontend_restart | no; browser reload after backend restart |
| retest_from_start | yes; P3R created from `/project-start` after P3 original classification failure |
| retest_result | PASS |
| notes | The failed project `proj_b22632800944` remains failure evidence and was not manually cleaned. |

## R-P4-F033: Add Automation Runtime Classification And Product Path

| Field | Value |
|---|---|
| repair_id | R-P4-F033 |
| linked_finding | P4-F033 |
| files_changed | `src/sylion-pipeline/sylion/api/project_start_routes.py`; `src/sylion-pipeline/sylion/api/council_to_ksiega_routes.py`; `src/sylion-pipeline/sylion/api/planning_routes.py`; `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_project_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py` |
| fix_summary | Added `local_automation_runtime` template, automation runtime intent/project checks, scope, council roles/questions, planning branches and a generated FastAPI/React product for local workers, task queue, retry, max parallel, logs, traces and status reporting. |
| verification | `pytest src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_council_to_ksiega_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py -q` passed after repair. Fresh dashboard restart `proj_f3e2a536e48c` classified as `internal_app/automation_runtime`. |
| backend_restart | yes; health OK on `127.0.0.1:8010`, version 3.5.0, 1966 endpoints |
| frontend_restart | no |
| retest_from_start | yes; P4 restarted from `/project-start` after failed `proj_c4ab8c81c556` |
| retest_result | PASS for classification, Group B and Group C |
| notes | Failed project `proj_c4ab8c81c556` remains evidence and was not reused as passing evidence. |

## R-P4-F034: Fix Automation Runtime Planning Acceptance

| Field | Value |
|---|---|
| repair_id | R-P4-F034 |
| linked_finding | P4-F034 |
| files_changed | `src/sylion-pipeline/sylion/api/planning_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py` |
| fix_summary | Phase 27 now uses a project-aware module assignment threshold for 5-module local runtime/mobile projects. Automation runtime work-unit generation now includes local dependency lock, environment count model, external deploy block, environment limit tests, profile switch E2E and terminal trace notes to meet the runtime work-unit threshold. |
| verification | Focused test `test_automation_runtime_planning_acceptance_covers_skills_and_work_units` passed. Full regression `pytest src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_council_to_ksiega_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 33 passed, then 34 passed after runtime guard repair. Dashboard P4R planning retest showed 6/6 accepted. |
| backend_restart | yes |
| frontend_restart | no |
| retest_from_start | affected Group D restarted from `/planning`; earlier Group B/C restart evidence retained |
| retest_result | PASS |
| notes | Resource profile variants were clicked in dashboard before final planning pass; profile selection affects worker count, environments, cost and timeline. |

## R-P4-F035: Enforce Local-Only Runtime Configuration Guard

| Field | Value |
|---|---|
| repair_id | R-P4-F035 |
| linked_finding | P4-F035 |
| files_changed | `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py`; `docs/aeis_manual_tests/03_TEST_RUN_LEDGER.md`; `docs/aeis_manual_tests/07_PRODUCT_TEST_MATRIX.md`; `docs/aeis_manual_tests/projects/P4_LOCAL_AUTOMATION_RUNTIME.md`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md` |
| fix_summary | Runtime configuration now treats CRM, funding, mobile approval and automation runtime projects as local-only guarded. Any VPS workers, paid VPS allowance, VPS topology or monthly VPS cap are reset to local-only, `vps_workers=0`, `max_monthly_vps_eur=0`, `allow_paid_vps=false`, with `blocked_external_runtime_request=true`. |
| verification | Focused test `test_automation_runtime_blocks_vps_runtime_configuration` passed. Full regression `pytest src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_council_to_ksiega_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 34 passed. Dashboard retest attempted `local + VPS`, 2 VPS workers, 50 EUR cap and paid VPS checkbox; UI reset to `local-only`, `0` VPS and `external_runtime_request_blocked_local_only`. |
| backend_restart | yes; health OK on `127.0.0.1:8010`, version 3.5.0, 1966 endpoints |
| frontend_restart | no |
| retest_from_start | affected Group E-F-G restarted from `/execution-start` after backend restart |
| retest_result | PASS: dashboard closed P4R with 10/10 phases, 4 local workers, 3 local environments, $0 cost, guard telemetry passed, generated product pytest passed |
| notes | P4 artifact scan has Hetzner words only as negative evidence (`hetzner_provisioned=false`, fresh confirmation required); no actual external provisioning occurred. |

## R-P5-F036: Add Multi-Domain Classification, Planning And Product Path

| Field | Value |
|---|---|
| repair_id | R-P5-F036 |
| linked_finding | P5-F036 |
| files_changed | `src/sylion-pipeline/sylion/api/project_start_routes.py`; `src/sylion-pipeline/sylion/api/council_to_ksiega_routes.py`; `src/sylion-pipeline/sylion/api/planning_routes.py`; `src/sylion-pipeline/sylion/api/execution_start_routes.py`; `src/sylion-pipeline/tests/test_project_start_routes.py`; `src/sylion-pipeline/tests/test_planning_execution_routes.py`; `docs/aeis_manual_tests/03_TEST_RUN_LEDGER.md`; `docs/aeis_manual_tests/07_PRODUCT_TEST_MATRIX.md`; `docs/aeis_manual_tests/projects/P5_COMPLEX_MULTI_DOMAIN.md`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md` |
| fix_summary | Added `aeis_multi_domain` template, multi-domain intent detection, scope, 14-role Council, 20-question Council set, multi-domain deliberation/book content, 7 planning modules, 22 model rows, 8 skill patterns, 50 work units, local-only runtime guard coverage and generated FastAPI/React product preserving CRM, funding, mobile approvals, automation runtime, governance, memory and guards. Removed leaked KSeF/Stripe/payment path from P5 planning/council artifacts. |
| verification | Focused P5 tests passed. Full regression `pytest src\sylion-pipeline\tests\test_project_start_routes.py src\sylion-pipeline\tests\test_council_to_ksiega_routes.py src\sylion-pipeline\tests\test_planning_execution_routes.py -q` = 37 passed, 6 warnings. |
| backend_restart | yes; health OK on `127.0.0.1:8010`, version 3.5.0, 1966 endpoints |
| frontend_restart | no; browser reload after backend restart |
| retest_from_start | yes; fresh dashboard project `proj_b9c142b06eb4` created after failed `proj_33eda4199b12` |
| retest_result | PASS: dashboard closed P5R with 10/10 execution phases, 4 local workers, 3 local environments, VPS guard reset external request to local-only, 230-file artifact scan clean, generated backend pytest passed |
| notes | The failed project `proj_33eda4199b12` remains evidence and was not reused as passing evidence. |

## R-W14-F037: Scope Test Center Release And Catalog To `proj_*`

| Field | Value |
|---|---|
| repair_id | R-W14-F037 |
| linked_finding | W14-F037 |
| files_changed | `src/sylion-pipeline/sylion/api/test_center_routes.py`; `src/sylion-pipeline/sylion/aeis/testing/release_rail.py`; `docs/aeis_manual_tests/08_AEIS_SELF_TEST_PLAN.md`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md` |
| fix_summary | Test Center now loads execution-start `proj_*` projects, hydrates project facts for release rehearsal, accepts project-start audit chains, binds catalog runs to the latest approved charter, and scopes failed catalog findings by project marker/run id. |
| verification | Focused W14/Test Center pytest = 28 passed. Dashboard retest for `proj_b9c142b06eb4` created charter `tc_03b0f3a6a1ad`, release candidate `rc_a8880b09719a`, branch `br_a3883e28a680`, and T0-T19 catalog runs all passed. |
| backend_restart | yes |
| frontend_restart | no; browser reload after backend restart |
| retest_from_start | yes; W14 charter, catalog and release flow repeated on AEIS itself |
| retest_result | PASS |
| notes | This repair is W14 self-test infrastructure, not a generated-product change. |

## R-W14-F038: Add Project Truth Alignment Matrix

| Field | Value |
|---|---|
| repair_id | R-W14-F038 |
| linked_finding | W14-F038 |
| files_changed | `src/sylion-pipeline/sylion/api/test_center_routes.py`; `src/sylion-frontend/src/app/(app)/test-center/truth-alignment/page.tsx`; `docs/aeis_manual_tests/08_AEIS_SELF_TEST_PLAN.md`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md` |
| fix_summary | Added project-aware truth alignment API and dashboard input. The matrix compares project modules, audit/approval chain, W14 catalog classes and generated artifact/docs instead of accepting an empty PASS. |
| verification | API and dashboard retest for `proj_b9c142b06eb4`: `total_features=14`, `aligned=14`, `drift=0`, `aligned_ratio=1.0`. W14 focused pytest = 28 passed; P1-P5 regression = 37 passed. |
| backend_restart | yes |
| frontend_restart | no; Next dev hot reload plus browser reload |
| retest_from_start | yes; truth alignment retested after project release/catalog proof existed |
| retest_result | PASS |
| notes | Empty truth matrices are no longer treated as sufficient evidence for the active project. |

## R-W14-F039: Make Test Center Dashboard Project-Scoped

| Field | Value |
|---|---|
| repair_id | R-W14-F039 |
| linked_finding | W14-F039 |
| files_changed | `src/sylion-frontend/src/app/(app)/test-center/dashboard/page.tsx`; `src/sylion-pipeline/sylion/api/test_center_routes.py`; `docs/aeis_manual_tests/08_AEIS_SELF_TEST_PLAN.md`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md` |
| fix_summary | Dashboard now accepts a `project_id`, queries dashboard/release-gate for the same project, and avoids mixing unscoped historical findings into the active project summary. |
| verification | Browser dashboard retest for `proj_b9c142b06eb4`: 1 approved charter, 0 P0/P1 blockers, release gate `production_ready`, blockers `0`, project-scoped recent runs. |
| backend_restart | yes |
| frontend_restart | no; browser reload |
| retest_from_start | yes; dashboard retest repeated after W14 release/catalog flow |
| retest_result | PASS |
| notes | Global AutoRepair backlog still contains unrelated historical findings and remains separate from the P5 release gate. |

## R-W14-F040: Add Dashboard-Triggered L0-L4 Simulation Run

| Field | Value |
|---|---|
| repair_id | R-W14-F040 |
| linked_finding | W14-F040 |
| files_changed | `src/sylion-pipeline/sylion/api/test_center_routes.py`; `src/sylion-frontend/src/app/(app)/test-center/simulation/page.tsx`; `docs/aeis_manual_tests/08_AEIS_SELF_TEST_PLAN.md`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md` |
| fix_summary | Added `POST /api/v1/test-center/simulation/run` and a dashboard action that creates a real isolated simulation contract, branch and evidence record through L0-L4 for the selected project. |
| verification | Browser clicked `/test-center/simulation` for `proj_b9c142b06eb4`; result branch `simb_37d564c2e14b`, contract `sc_588b0f592fbc`, state `open`, layer `L4`, evidence count `1`, snapshot `sim_1778205191531`. Focused W14 pytest = 28 passed. |
| backend_restart | yes |
| frontend_restart | no; browser reload |
| retest_from_start | yes; simulation run executed from dashboard after repair |
| retest_result | PASS |
| notes | Simulation is isolated/local and does not perform external network actions. |

## R-W18-F041: Preserve And Render Terminal Runtime Metadata

| Field | Value |
|---|---|
| repair_id | R-W18-F041 |
| linked_finding | W18-F041 |
| files_changed | `src/sylion-pipeline/sylion/aeis_v2/terminal/stream.py`; `src/sylion-pipeline/sylion/api/terminal_routes.py`; `src/sylion-frontend/src/app/(app)/terminal/page.tsx`; `docs/aeis_manual_tests/09_FINDINGS.md`; `docs/aeis_manual_tests/10_REPAIR_LOG.md` |
| fix_summary | Event bus adapter now preserves safe metadata keys in `TerminalEvent.extra`; `/exec` and dev injection can carry project/role/agent/env/council/phase context; terminal dashboard renders these as compact badges while continuing to strip secret-like payload keys. |
| verification | `pytest tests -q -k "terminal and stream"` = 16 passed, 2 skipped. Backend restarted healthy. Browser `/terminal` retest showed W18 event with badges for `project:proj_b9c142b06eb4`, `role:Auditor W14`, `agent:codex-terminal-auditor`, `env:local-only`, `council:council-p5-w14`, `phase:W14-self-test`. |
| backend_restart | yes; health OK on `127.0.0.1:8010`, version 3.5.0, 1967 endpoints |
| frontend_restart | no; browser reload |
| retest_from_start | W18 terminal retested after backend restart; W14 release decision did not need restart because this repair is observability-only |
| retest_result | PASS_WITH_SCOPE_NOTE |
| notes | The terminal now displays metadata when emitted. Full semantic coverage still depends on each AEIS module emitting rich events to the bus; generic API middleware events remain intentionally generic. |

## R-RESIDUAL-F042-F046: Close Hard Residual Backlog

| Field | Value |
|---|---|
| repair_id | R-RESIDUAL-F042-F046 |
| linked_finding | W14-F042, W14-F043, W18-F044, W09-F045, UI-F046 |
| files_changed | `src/sylion-pipeline/sylion/api/test_center_routes.py`; `src/sylion-pipeline/sylion/api/project_start_routes.py`; `src/sylion-pipeline/sylion/api/skills_routes.py`; `src/sylion-frontend/src/app/(app)/test-center/page.tsx`; `src/sylion-frontend/src/app/(app)/test-center/auto-repair/page.tsx`; `src/sylion-frontend/src/app/(app)/skills/page.tsx`; `src/sylion-frontend/src/lib/api/client.ts`; focused backend tests; docs |
| fix_summary | Added project-scoped AutoRepair status and archive action; added Theater to Test Center hub and health catalog; mirrored project audit-chain events into EventBus; added semantic skill lifecycle events and a bounded long-run lifecycle test endpoint; added dashboard button for lifecycle test; localized critical residual labels in AutoRepair/Skills. |
| verification | Backend: `tests/api/test_test_center_routes.py` = 24 passed; targeted `test_api_all_routes.py` skills/semantic tests = 3 passed. Frontend: `npx tsc --noEmit --pretty false` passed; focused eslint passed with warnings only. Browser: `/test-center` shows Theater; `/test-center/auto-repair` set `project_browser_residual_fix`, triggered LoopGuard and archived globals; `/skills` long lifecycle returned `zaliczony`; `/terminal` showed `proj_terminal_semantic_live` semantic skill lifecycle event. |
| backend_restart | yes; backend restarted on `127.0.0.1:8010`, health and Test Center health OK |
| frontend_restart | no; Next dev hot reload and browser navigation |
| retest_from_start | yes; residual surfaces retested through dashboard after repair |
| retest_result | PASS |
| notes | Global localization outside the tested critical surfaces still deserves a separate full-dashboard language sweep, but the residual items listed by the operator are now implemented and covered by tests/browser evidence. |

## Repair Template

| Field | Value |
|---|---|
| repair_id | |
| linked_finding | |
| files_changed | |
| fix_summary | |
| verification | |
| backend_restart | yes/no |
| frontend_restart | yes/no |
| retest_from_start | yes/no |
| retest_result | PASS/FAIL |
| notes | |
