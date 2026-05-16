# AEIS Test Run Ledger

Status: running

## Global Run Checklist

| Checkpoint | Name | Status | Evidence | Notes |
|---:|---|---|---|---|
| 1 | Documentation structure created | DONE | this folder | Baseline created before execution |
| 2 | Roles and agents confirmed | PENDING | | |
| 3 | Stop-Fix-Restart confirmed | DONE | `00_TEST_PLAN.md` | No exceptions |
| 4 | Dashboard inventory complete | IN_PROGRESS | `01_DASHBOARD_INVENTORY.md` | Static snapshot and core browser smoke captured; full route inventory still pending |
| 5 | UI/API/module map complete | IN_PROGRESS | `02_API_UI_MODULE_MAP.md` | Static + runtime snapshot captured on backend 8010/frontend 3001; detailed route validation pending |
| 5.1 | API key entry pause and provider budget policy confirmed | PENDING | `00_TEST_PLAN.md` | Operator enters disposable keys only when requested |
| 6 | P1 simulation complete | RESTART2_PASS | `docs/aeis_manual_tests/projects/P1_MINI_CRM.md` | Fresh dashboard restart `proj_91014e2cad46` passed 32-41, product artifact scan clean, generated backend pytest passed |
| 7 | P2 simulation complete | RESTART4_PASS | `docs/aeis_manual_tests/projects/P2_FUNDING_ASSISTANT.md`; `06_FUNDING_TEST_MATRIX.md`; `07_PRODUCT_TEST_MATRIX.md` | Fresh dashboard restart `proj_7544e8bdd3ea` passed 16-41, artifact scan clean, generated funding backend pytest passed with deadline/source/legal/budget/document blockers |
| 8 | P3 simulation complete | RESTART_PASS | `docs/aeis_manual_tests/projects/P3_MOBILE_APPROVAL_QUEUE.md`; `07_PRODUCT_TEST_MATRIX.md` | Fresh dashboard restart `proj_635af5715faf` passed 16-41, artifact scan clean, generated mobile approval backend pytest passed |
| 9 | P4 simulation complete | RESTART_PASS | `docs/aeis_manual_tests/projects/P4_LOCAL_AUTOMATION_RUNTIME.md`; `07_PRODUCT_TEST_MATRIX.md` | Fresh dashboard restart `proj_f3e2a536e48c` passed 16-41, resource profile variants tested, VPS runtime guard reset external request to local-only, artifact scan acceptable, generated runtime backend pytest passed |
| 10 | P5 simulation complete | RESTART_PASS | `docs/aeis_manual_tests/projects/P5_COMPLEX_MULTI_DOMAIN.md`; `07_PRODUCT_TEST_MATRIX.md` | Fresh dashboard restart `proj_b9c142b06eb4` passed 16-41, profile variants tested, VPS guard reset external request to local-only, artifact scan clean, generated multi-domain backend pytest passed |
| 11 | Product test matrix complete | DONE_FOR_P1_P5 | `07_PRODUCT_TEST_MATRIX.md` | Generated products for all five simulations passed local backend smoke tests and artifact scans |
| 12 | Guards matrix complete | DONE_FOR_P5_W14 | `05_GUARDS_TEST_MATRIX.md`; `/test-center/release-gate`; generated product `/guards` | P5 local-only, external-action, HumanGate, audit, release, no-mock and catalog guards passed; AutoRepair global backlog remains separate |
| 13 | Funding matrix complete | DONE_FOR_P2_P5 | `06_FUNDING_TEST_MATRIX.md`; P2 generated product; P5 truth matrix | P2 funding product passed deadline/source/legal/budget/document blockers; P5 multi-domain preserves funding assistant and external submit block |
| 14 | AEIS self-test complete | RESTART_PASS | `08_AEIS_SELF_TEST_PLAN.md`; Test Center IDs below | W14 self-test repeated on AEIS itself after repairs: charter, catalog T0-T19, no-mock scan, simulation L0-L4, truth alignment and release gate passed |
| 15 | Final report complete | UPDATED_AFTER_RESIDUAL_REPAIR | `11_FINAL_REPORT.md` | Final decision updated after hard residual backlog closure |
| 16 | Hard residual backlog repair | RETEST_PASS | `09_FINDINGS.md`; `10_REPAIR_LOG.md`; browser evidence | Closed AutoRepair project archive, Theater hub coverage, semantic terminal events, skills long lifecycle test and critical Polish-label gaps |

## Current Meta-Orchestration Checkpoint

| Field | Value |
|---|---|
| checkpoint_id | META-J-2026-05-08 |
| status | META_RUNTIME_REPAIRED_P1_P2_RESTART_PASS |
| dashboard_paths_clicked | `/orchestration/auditor`, `/orchestration/llm-routing`, `/orchestration/dispatch`, `/orchestration/council-rules`, `/orchestration/fixer`, `/orchestration/tests`, `/orchestration/teams`, `/orchestration/event-map`, `/orchestration/conversations`, `/memory`, `/workspace`, `/apps-builder/wizard` |
| pass_evidence | API health OK on `127.0.0.1:8010`; J6 golden catalog now runs deterministic backend checks and dashboard shows 5 passed checks; `/memory` writes evidence, indexes a section and retrieves context; `/workspace` chat returns a visible assistant response from local Ollama model; `/orchestration/teams` creates a visible active `z_ai` + `claude` team from a clicked runtime trigger; `/orchestration/conversations` records a clicked `codex ↔ claude` 4-turn runtime conversation; `/orchestration/event-map` shows runtime counters for team formation and conversation events; Phase 26 consumes changed J1 model routing; Phase 32 consumes J5 dispatch cap; Phase 34 and project council consume J2 council policy; Phase 35 records J3/J4/J5/J7/J9 runtime policy; Phase 37 consumes J4 fixer protocol. |
| blockers | P1-F025, P1-F029, P2-F030, P2-F031, P3-F032, P4-F033, P4-F034, P4-F035 and P5-F036 fixed with fresh dashboard restarts. P1-F023 localization and P1-F024 system surfaces remain globally open. |
| repairs_done | R-P1-F026A, R-P1-F027, R-P1-F028, R-P1-F025A, R-P1-F025B, R-P1-F025C, R-P1-F029, R-P2-F030, R-P2-F031, R-P3-F032, R-P4-F033, R-P4-F034, R-P4-F035, R-P5-F036 |
| next_required_action | Continue broad full-dashboard Polish sweep and long-horizon memory/learning productization; hard residual items from final backlog are repaired and retested. |

## Residual Backlog Closure Event

| Field | Value |
|---|---|
| test_id | RESIDUAL-CLOSURE-2026-05-08 |
| project_id | `project_browser_residual_fix`; `proj_dashboard_skill_lifecycle`; `proj_terminal_semantic_live` |
| start_time | 2026-05-08 after W14 final residual backlog |
| operator_action | Dashboard clicked `/test-center`, `/test-center/theater`, `/test-center/auto-repair`, `/skills`, `/terminal`; backend restarted on `127.0.0.1:8010`. |
| expected_result | Close the explicit backlog: Polish critical labels, project-scoped AutoRepair/archive, Theater navigation, semantic terminal events, dedicated long-running skills lifecycle test. |
| actual_result | PASS after repairs F042-F046. |
| ui_evidence | Theater card present in Test Center; AutoRepair accepts project input, triggers LoopGuard, shows archive counters and archives global findings; Skills dashboard runs `Dlugi test lifecycle` and shows `zaliczony`; Terminal shows `proj_terminal_semantic_live` skills lifecycle event. |
| api_evidence | `/api/v1/test-center/health` includes `theater`; `/api/v1/skills/lifecycle/long-run-test` returned `passed=true`; AutoRepair status returns project/global archive counters. |
| log_evidence | `tests/api/test_test_center_routes.py` 24 passed; targeted `test_api_all_routes.py` 3 passed; `npx tsc --noEmit --pretty false` passed; focused eslint 0 errors. |
| status | RETEST_PASS |
| mock_stub_detected | no new mock/stub; residual gaps were wiring/scope/navigation/test-coverage issues |
| fix_required | yes; R-RESIDUAL-F042-F046 |
| restart_required | yes |
| retest_from_start | yes; each residual surface was retested from dashboard entry after backend restart |

## W14 AEIS Self-Test Event

| Field | Value |
|---|---|
| test_id | W14-AEIS-SELF-P5-2026-05-08 |
| project_id | `proj_b9c142b06eb4` |
| start_time | 2026-05-08, after P5 generated product pass |
| operator_action | Dashboard clicked through `/test-center/release-gate`, `/test-center/catalog`, `/test-center/no-mock-scan`, `/test-center/truth-alignment`, `/test-center/dashboard`, `/test-center/simulation`, `/test-center/human-lab`, `/test-center/auto-repair`, and `/terminal`. |
| expected_result | AEIS uses its own W14 layer to prove the P5 generated product and AEIS runtime: project-scoped charter, catalog T0-T19, release candidate, no-mock scan, truth matrix, L0-L4 simulation, guards, HumanGate, council/release decision and terminal observability. |
| actual_result | PASS after Stop-Fix-Restart repairs W14-F037 through W18-F041. |
| ui_evidence | Release gate `production_ready`; dashboard 1 approved charter and 0 P0/P1 blockers; catalog T0-T19 all 100%; truth alignment 14/14 aligned, 0 drift; simulation branch visible; terminal badges visible. |
| api_evidence | Charter `tc_03b0f3a6a1ad`; RC `rc_a8880b09719a`; release branch `br_a3883e28a680`; simulation branch `simb_37d564c2e14b`; simulation contract `sc_588b0f592fbc`; no-mock scan 445 files, 3 allowed non-blocking mentions, 0 blockers. |
| log_evidence | Backend health after restart: version 3.5.0, 1967 endpoints; terminal stream replay recorded W18 verification event. |
| artifact_path | `C:\Users\razor\.sylion\projects\proj-b9c142b06eb4-p5-restart-multi-domain-aeis` |
| memory_evidence | Truth matrix includes `memory_reuse_evidence`; P5 product preserves memory/governance/audit modules. |
| status | RETEST_PASS |
| mock_stub_detected | yes; W14 false-success/empty truth and read-only simulation were detected as test-layer gaps, then repaired |
| fix_required | yes; R-W14-F037, R-W14-F038, R-W14-F039, R-W14-F040, R-W18-F041 |
| restart_required | yes |
| retest_from_start | yes; W14 self-test was repeated from charter/catalog/release/simulation after repairs |

## Test Event Template

| Field | Value |
|---|---|
| test_id | |
| project_id | |
| start_time | |
| operator_action | |
| expected_result | |
| actual_result | |
| ui_evidence | |
| api_evidence | |
| log_evidence | |
| artifact_path | |
| memory_evidence | |
| status | PASS / FAIL / BLOCKER / RETEST_PASS |
| mock_stub_detected | yes/no |
| fix_required | yes/no |
| restart_required | yes/no |
| retest_from_start | yes/no |
