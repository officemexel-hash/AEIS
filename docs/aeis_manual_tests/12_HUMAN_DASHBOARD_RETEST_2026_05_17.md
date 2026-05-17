# AEIS human dashboard retest - 2026-05-17

Status: ACTIVE
Runtime: backend `http://127.0.0.1:8010`, frontend `http://127.0.0.1:3002`

## Command

`HUMAN_DASHBOARD_TEST_COMMAND`

1. Click the dashboard like an operator.
2. When any error, false success, stale state, console error, network error, or missing persistence is found, stop the flow.
3. Fix the defect in code or runtime configuration.
4. Retest the same flow twice from a fresh dashboard action path: PASS 1 and PASS 2.
5. A pass requires backend effect, reload persistence, and no console/network error. A toast alone is not proof.
6. Freeze the result with project id, API proof, UI proof, and changed files.
7. Continue to the next action only after freeze.

## Four Trial Projects

| ID | Difficulty | Name | Purpose |
| --- | --- | --- | --- |
| P1 | Easy | Mini CRM Serwisowy | Customer list, tickets, statuses, technician notes, weekly report, owner/worker/client roles, 5000 PLN budget, 14-day deadline. |
| P2 | Medium | Generator Umow i Ofert | Offer and contract templates, PDF preview, approval statuses, operator/lawyer/client roles, 18000 PLN budget, 30-day deadline. |
| P3 | Hard | Funding Assistant Fundacji | NGO grant profile, call matching, application draft, exact preview, Human Gate, dummy submit receipt, CRM tracking. |
| P4 | Very hard | Platforma Reagowania Kryzysowego | Incident workflow, dispatcher roles, mobile approval, audit trail, evidence, skills, memory isolation, deploy rehearsal. |

## Freeze Log

### F-2026-05-17-001 - Project Start false fetch error after create

| Field | Value |
| --- | --- |
| Surface | `/project-start` |
| Defect | After `Utworz projekt`, the dashboard displayed `Blad startu projektu: Failed to fetch` while the project was actually created and visible. |
| Cause | Project reload treated optional edge-case loading as a critical failure and used the parallel load path immediately after create. |
| Repair | `ProjectStartDashboard.load()` now loads the critical project snapshot first and isolates edge-case loading failure from the core project state. |
| File changed | `src/sylion-frontend/src/components/project-start/ProjectStartDashboard.tsx` |
| Static verification | `npm run lint -- src/components/project-start/ProjectStartDashboard.tsx` = 0 errors, existing `any` warnings only. |
| PASS 1 | Created `P1 Mini CRM Serwisowy PASS1`, API active project `proj_c16e93dc277c`, state `READY_FOR_GOAL_DEFINITION`, edge-cases `66`, no UI false fetch error, no browser console errors. |
| PASS 2 | Created `P1 Mini CRM Serwisowy PASS2`, API active project `proj_21ad37adc2bb`, state `READY_FOR_GOAL_DEFINITION`, edge-cases `66`, no UI false fetch error, no browser console errors. |
| Frozen | Yes |

### P1 Group B freeze - Project Start phases 16-19

| Field | Value |
| --- | --- |
| Surface | `/project-start` |
| Project | `P1 Mini CRM Serwisowy PASS2` / `proj_21ad37adc2bb` |
| Operator path | Preview -> create -> apply phase 17 defaults -> apply phase 18 defaults -> apply phase 19 council defaults -> approve readiness -> reload. |
| UI proof | Dashboard shows `GRUPA B GOTOWA`, phase rows P16-P19 accepted, 0 hard blockers, no browser console errors. |
| API proof | `/api/v1/project-start/projects/proj_21ad37adc2bb` returns state `READY_FOR_COUNCIL_CONVENING`; acceptance `16=true`, `17=true`, `18=true`, `19=true`; phase 19 hard blockers `0`; audit entries `5`. |
| Reload proof | Fresh navigation to `/project-start` reloads the same active project and preserves `GRUPA B GOTOWA`. |
| Frozen | Yes |

### P1 Group C freeze - Council to Ksiegi phases 20-25

| Field | Value |
| --- | --- |
| Surface | `/council-to-ksiega` |
| Project | `P1 Mini CRM Serwisowy PASS2` / `proj_21ad37adc2bb` |
| Operator path | Convene Council -> generate initial verdicts -> run deliberation rounds -> consolidate decision -> generate Council Book -> lock Ksiegi -> reload. |
| UI proof | Dashboard shows `GRUPA C GOTOWA`, phases P20-P25 accepted, consensus `91%`, decisions `20`, hard blockers `0`, audit entries `14`, no browser console errors. |
| API proof | `/api/v1/council-to-ksiega/projects/proj_21ad37adc2bb` returns state `READY_FOR_PLANNING`; acceptance `20=true` through `25=true`; `deliberation.rounds.overall_consensus=0.91`; `deliberation.consolidation.decisions=20`; `deliberation.ksiega.locked=true`; audit entries `14`. |
| Artifact proof | Council Book path `...\\council\\council_book.md`; Ksiegi path `...\\ksiega\\ksiega_v1.md`; PDF and structured JSON artifacts present in API response with hashes. |
| Reload proof | Fresh navigation to `/council-to-ksiega` reloads the same active project and preserves `GRUPA C GOTOWA`, `gotowe do planowania`, `91%`, and artifact paths. |
| Frozen | Yes |

### F-2026-05-17-002 - Planning false fetch error after Group C

| Field | Value |
| --- | --- |
| Surface | `/planning` |
| Defect | Fresh navigation to Planning displayed `Planning error: Failed to fetch`, `Brak aktywnego projektu`, and disabled planning actions even though P1 was in `READY_FOR_PLANNING`. |
| Cause | Planning loaded the critical project snapshot and optional edge-cases concurrently; the browser could cancel the critical project GET after preflight while the API itself stayed healthy. |
| Repair | `PlanningDashboard.load()` now loads the required project snapshot before optional edge-case loading and isolates edge-case failure from active project state. |
| File changed | `src/sylion-frontend/src/components/planning/PlanningDashboard.tsx` |
| Static verification | `npm run lint -- src/components/planning/PlanningDashboard.tsx src/components/project-start/ProjectStartDashboard.tsx` = 0 errors, existing warnings only. |
| PASS 1 | Fresh `/planning` load showed `P1 Mini CRM Serwisowy PASS2`, `proj_21ad37adc2bb`, enabled actions, no `Planning error`, no browser console errors. |
| PASS 2 | Dashboard `Refresh` repeated the same state with no `Planning error`; API `/api/v1/planning` returned active project `proj_21ad37adc2bb`, state `READY_FOR_PLANNING`, 6 phases, 98 edge cases. |
| Frozen | Yes |

### F-2026-05-17-003 - False backend offline on dashboard reload

| Field | Value |
| --- | --- |
| Surfaces | `/project-start`, `/council-to-ksiega`, `/planning` |
| Defect | A fresh dashboard reload could show `BACKEND NIEDOSTEPNY` or clear the active project while backend `/health` and the flow API were healthy. |
| Cause | The dashboards treated initial health status `unknown/loading` as hard offline instead of a pending connection state. |
| Repair | The dashboards now use `backendPending` for `unknown/loading`, show `LACZENIE Z BACKENDEM`, and only clear state after a non-pending offline result. |
| Files changed | `src/sylion-frontend/src/components/project-start/ProjectStartDashboard.tsx`; `src/sylion-frontend/src/components/council-to-ksiega/CouncilToKsiegaDashboard.tsx`; `src/sylion-frontend/src/components/planning/PlanningDashboard.tsx` |
| Static verification | `npm run lint -- src/components/project-start/ProjectStartDashboard.tsx src/components/council-to-ksiega/CouncilToKsiegaDashboard.tsx src/components/planning/PlanningDashboard.tsx` = 0 errors, existing warnings only. |
| PASS 1 | Fresh `/planning` navigation waited for health, showed `BACKEND DZIALA`, `P1 Mini CRM Serwisowy PASS2`, `READY_FOR_BUILD`, `6/6`, and no browser console errors. |
| PASS 2 | Browser reload of `/planning` repeated `BACKEND DZIALA`, `P1 Mini CRM Serwisowy PASS2`, `READY_FOR_BUILD`, `6/6`, and no browser console errors. |
| Frozen | Yes |

### P1 Group D freeze - Planning phases 26-31

| Field | Value |
| --- | --- |
| Surface | `/planning` |
| Project | `P1 Mini CRM Serwisowy PASS2` / `proj_21ad37adc2bb` |
| Operator path | Assign models -> synthesize skills -> generate masterplan -> generate test plan -> approve pre-flight cost -> run dry run -> reload. |
| UI proof | Dashboard shows `PLANNING PART 1 READY`, `BACKEND DZIALA`, phases P26-P31 accepted, `6/6`, model rows `16`, skill patterns `8`, ready state `BUILD`, no browser console errors. |
| API proof | `/api/v1/planning/projects/proj_21ad37adc2bb` returns state `READY_FOR_BUILD`; acceptance `26=true` through `31=true`; model rows `16`; skill patterns `8`; work units `44`; test coverage `150`; human-like scenarios `32`; cost decision `GO`; dry-run confidence `0.88`; audit entries `20`. |
| Reload proof | Two fresh dashboard reloads preserve `P1 Mini CRM Serwisowy PASS2`, `READY_FOR_BUILD`, `PLANNING PART 1 READY`, and `6/6`. |
| Frozen | Yes |

### F-2026-05-17-004 - Execution Start false fetch error after Planning

| Field | Value |
| --- | --- |
| Surface | `/execution-start` |
| Defect | Fresh navigation to Execution Start displayed `Blad panelu wykonania: Failed to fetch` and `Brak aktywnego projektu` even though P1 was in `READY_FOR_BUILD`. |
| Cause | Execution Start loaded the critical project snapshot and optional edge/runtime/live/dispatch data in one `Promise.all`; one cancelled auxiliary request caused the whole panel to drop the project. |
| Repair | `ExecutionStartDashboard.load()` now loads the required project snapshot first and isolates optional edge/runtime/live/dispatch failures with `Promise.allSettled`. |
| File changed | `src/sylion-frontend/src/components/execution-start/ExecutionStartDashboard.tsx` |
| Static verification | `npm run lint -- src/components/execution-start/ExecutionStartDashboard.tsx` = 0 errors. |
| PASS 1 | Fresh `/execution-start` load showed `P1 Mini CRM Serwisowy PASS2`, `proj_21ad37adc2bb`, `READY_FOR_BUILD`, `API DZIALA`, no false fetch, no browser console errors. |
| PASS 2 | Browser reload repeated the same project and `READY_FOR_BUILD` state with no false fetch and no browser console errors. |
| Frozen | Yes |

### P1 Group E-F-G freeze - Execution, testing, deploy rehearsal, closure phases 32-41

| Field | Value |
| --- | --- |
| Surface | `/execution-start` |
| Project | `P1 Mini CRM Serwisowy PASS2` / `proj_21ad37adc2bb` |
| Operator path | Initialize build -> start execution -> reconvene council -> run orchestration -> complete build -> quality gates -> customer acceptance -> final check -> local deploy rehearsal -> close project -> reload twice. |
| UI proof | Dashboard shows `PROJEKT ZAMKNIETY`, `10/10`, `API DZIALA`, project `P1 Mini CRM Serwisowy PASS2`, all rows P32-P41 accepted, availability/pass metric `100%`, no browser console errors. |
| API proof | `/api/v1/execution-start/projects/proj_21ad37adc2bb` returns state `CLOSED`; acceptance `32=true` through `41=true`; workers `2`; environments `2`; quality verdict `PASS`; pass rate `99.7`; L5 human-like UI total `32`; customer signoff received; important feedback fixed `3`; minor feedback fixed `6`; deploy mode `local_release_rehearsal_no_external_calls`; uptime `100`; local-only scope verified `true`; project complete `true`; warranty `30` days; long-horizon memory `synced`; audit entries `40`. |
| Reload proof | Two fresh dashboard reloads preserve `PROJEKT ZAMKNIETY`, `10/10`, `P1 Mini CRM Serwisowy PASS2`, and no false fetch. |
| Frozen | Yes |

### P2 full trial freeze - Generator Umow i Ofert

| Field | Value |
| --- | --- |
| Project | `P2 Generator Umow i Ofert PASS1` / `proj_15b994bf5adc` |
| Difficulty | Medium |
| Operator path | Dashboard-created project -> Group B 16-19 -> Group C 20-25 -> Planning 26-31 -> Execution/Testing/Deploy/Closure 32-41 -> reload. |
| UI proof | `/execution-start` reload shows `PROJEKT ZAMKNIETY`, `10/10`, project `P2 Generator Umow i Ofert PASS1`, `API DZIALA`, and no browser console errors. |
| API proof | State `CLOSED`; D-level `D3`; domain `crm`; Planning model rows `16`; skills `8`; acceptance `32=true` through `41=true`; quality verdict `PASS`; pass rate `99.7`; deploy mode `local_release_rehearsal_no_external_calls`; project complete `true`; memory `synced`; audit entries `40`. |
| Frozen | Yes |

### P3 full trial freeze - Funding Assistant Fundacji

| Field | Value |
| --- | --- |
| Project | `P3 Funding Assistant Fundacji PASS1` / `proj_55dc5749434d` |
| Difficulty | Hard |
| Operator path | Dashboard-created funding project -> Group B 16-19 -> Group C 20-25 -> Planning 26-31 -> Execution/Testing/Deploy/Closure 32-41 -> reload. |
| UI proof | `/execution-start` reload shows `PROJEKT ZAMKNIETY`, `10/10`, project `P3 Funding Assistant Fundacji PASS1`, `API DZIALA`, and no browser console errors. |
| API proof | State `CLOSED`; D-level `D4`; domain `funding`; Planning model rows `18`; skills `8`; acceptance `32=true` through `41=true`; quality verdict `PASS`; pass rate `99.7`; deploy mode `local_release_rehearsal_no_external_calls`; project complete `true`; memory `synced`; audit entries `52`. |
| Governance note | The funding scenario remained local rehearsal only; no real external submit was executed. |
| Frozen | Yes |

### F-2026-05-17-005 - Council false fetch on D5 project

| Field | Value |
| --- | --- |
| Surface | `/council-to-ksiega` |
| Defect | P4 D5 project reached Group B, but a fresh Council load showed `Błąd przepływu Rada -> Księga: Failed to fetch`, `brak aktywnego projektu`, and disabled `Zwołaj Radę`. |
| Cause | Council loaded the critical project snapshot and optional edge-cases in one `Promise.all`; the project GET could be cancelled after preflight, leaving the panel without context. |
| Repair | `CouncilToKsiegaDashboard.load()` now loads the required project snapshot first and isolates edge-case loading failure. |
| File changed | `src/sylion-frontend/src/components/council-to-ksiega/CouncilToKsiegaDashboard.tsx` |
| Static verification | `npm run lint -- src/components/council-to-ksiega/CouncilToKsiegaDashboard.tsx` = 0 errors, existing warnings only. |
| PASS 1 | Fresh `/council-to-ksiega` load showed P4 `proj_c747b72ce3d2`, no false fetch, no browser console errors. |
| PASS 2 | Browser reload repeated P4 context, no false fetch, no browser console errors. |
| Frozen | Yes |

### F-2026-05-17-006 - GET preflight cancellation hardening

| Field | Value |
| --- | --- |
| Surface | Shared frontend API client |
| Defect | On P4 Planning the browser sent `OPTIONS /api/v1/planning/projects/proj_c747b72ce3d2` but no follow-up GET, then the UI showed `Planning error: Failed to fetch` and disabled actions. |
| Cause | Intermittent browser-side cancellation after CORS preflight surfaced as `Failed to fetch` for idempotent GET requests. |
| Repair | `request()` now retries failed GET requests once after 150 ms. Mutating methods are not retried, preventing duplicate writes. |
| File changed | `src/sylion-frontend/src/lib/api/client.ts` |
| Static verification | `npm run lint -- src/lib/api/client.ts src/components/planning/PlanningDashboard.tsx src/components/council-to-ksiega/CouncilToKsiegaDashboard.tsx` = 0 errors, existing warnings only. |
| PASS 1 | Fresh `/planning` load showed P4 `proj_c747b72ce3d2`, `READY_FOR_PLANNING`, no `Planning error`, no browser console errors. |
| PASS 2 | Browser reload repeated P4 context, no `Planning error`, no browser console errors. |
| Frozen | Yes |

### P4 full trial freeze - Platforma Reagowania Kryzysowego

| Field | Value |
| --- | --- |
| Project | `P4 Platforma Reagowania Kryzysowego PASS1` / `proj_c747b72ce3d2` |
| Difficulty | Very hard |
| Operator path | Dashboard-created D5 multi-domain project -> Group B 16-19 -> Group C 20-25 -> Planning 26-31 -> Execution/Testing/Deploy/Closure 32-41. |
| UI proof | `/execution-start` shows `PROJEKT ZAMKNIETY`, `10/10`, project `P4 Platforma Reagowania Kryzysowego PASS1`, `API DZIALA`, and no browser console errors. |
| API proof | State `CLOSED`; D-level `D5`; domain `aeis_multi_domain`; Planning model rows `22`; skills `8`; acceptance `32=true` through `41=true`; quality verdict `PASS`; pass rate `99.7`; deploy mode `local_release_rehearsal_no_external_calls`; project complete `true`; memory `synced`; audit entries `40`. |
| Governance note | D5 project remained local-first; production/external action was represented as local rehearsal with no external calls. |
| Reload proof | Fresh browser reload of `/execution-start` returned to P4, showed `PROJEKT ZAMKNIETY`, `10/10`, `API DZIALA`, and no browser console errors. |
| Frozen | Yes |

### F-2026-05-17-007 - Production build FAQ data module

| Field | Value |
| --- | --- |
| Surface | `/faq` production build |
| Defect | `npm run build` failed because `@/data/faq-entries` was imported by `/faq` but the data module was missing. |
| Repair | Added typed FAQ category labels and FAQ entries in a dedicated data module. |
| File changed | `src/sylion-frontend/src/data/faq-entries.ts` |
| Static verification | `npm run lint -- 'src/app/(app)/human-gate/page.tsx' src/data/faq-entries.ts` = 0 errors, existing warnings only. |
| PASS 1 | `npm run build` progressed past `/faq` after the module was added. |
| PASS 2 | Final `npm run build` completed successfully with 125/125 static pages generated. |
| Frozen | Yes |

### F-2026-05-17-008 - useSearchParams production Suspense hardening

| Field | Value |
| --- | --- |
| Surfaces | `/human-gate`, `/pipeline`, `/workspace` |
| Defect | `npm run build` failed on prerender because client code using `useSearchParams()` was not under a Suspense boundary. |
| Repair | Wrapped the affected client surfaces in Suspense fallbacks without changing their runtime behavior. |
| Files changed | `src/sylion-frontend/src/app/(app)/human-gate/page.tsx`; `src/sylion-frontend/src/app/(app)/pipeline/page.tsx`; `src/sylion-frontend/src/components/workspace/ChatPanel.tsx` |
| Static verification | Targeted lints for the changed files returned 0 errors; only pre-existing warnings remained in parent pages. |
| PASS 1 | `npm run build` progressed past `/human-gate` and `/pipeline` after each fix. |
| PASS 2 | Final `npm run build` completed successfully with 125/125 static pages generated. |
| Frozen | Yes |

### Final production build freeze

| Field | Value |
| --- | --- |
| Command | `npm run build` from `src/sylion-frontend` |
| Result | PASS |
| Evidence | Next.js production build compiled, TypeScript completed, and generated 125/125 static pages. |
| Human-dashboard scope | P1-P4 dashboard-created trial projects passed browser-driven flows from project creation through closure, with defects repaired, double-tested, and frozen before proceeding. |
| Frozen | Yes |
