# AEIS Dashboard Inventory

Status: not started

## Static Snapshot 2026-05-07 Start

Evidence files:

- `docs/aeis_manual_tests/evidence/api/frontend_routes_static_start.txt`
- `docs/aeis_manual_tests/evidence/api/frontend_risk_routes_static_start.txt`
- `docs/aeis_manual_tests/evidence/api/api_ui_coverage_static_start.md`

Initial counts:

| Metric | Count |
|---|---:|
| Frontend `page.tsx` routes | 127 |
| Frontend routes with static mock/stub/demo/fallback risk markers | 27 |
| Frontend routes with `mock/stub/demo` markers | 10 |

Initial highest-risk routes:

| Route | Reason To Verify Carefully |
|---|---|
| `/autonomy` | Static marker scan hit. Must prove autonomy is operative, not demo-only. |
| `/coherence-guard` | Static marker scan hit. Guard must block real inconsistency. |
| `/environments` | Static marker scan hit. Must prove config changes are persisted/audited. |
| `/onboarding` | Static marker scan hit. Must verify no demo-only onboarding. |
| `/test-center` | Static marker scan hit. Must prove Test Center runs real checks. |
| `/test-center/no-mock-scan` | Static marker scan hit. Must prove it detects mocks/stubs. |
| `/test-center/release-gate` | Static marker scan hit. Must prove release blocking is real. |
| `/workspace-defaults` | Static marker scan hit. Must prove defaults affect generated plans. |

Inventory Agent caveat: raw substring scanning can produce false positives. `test-center` routes naturally contain mock/stub terms because they are scanner surfaces. Runtime manual tests must decide whether each marker is expected evidence UI or a real fake-functionality risk.

## Browser Smoke 2026-05-07 Start

Evidence:

- `output/playwright/aeis-manual-start/route_smoke_results.json`
- `output/playwright/aeis-manual-start/*.png`

Routes checked:

| Route | HTTP | Console Issues | Screenshot |
|---|---:|---:|---|
| `/` | 200 | 0 | `output/playwright/aeis-manual-start/root.png` |
| `/idea-vault` | 200 | 0 | `output/playwright/aeis-manual-start/idea-vault.png` |
| `/human-gate` | 200 | 0 | `output/playwright/aeis-manual-start/human-gate.png` |
| `/projects` | 200 | 0 | `output/playwright/aeis-manual-start/projects.png` |
| `/workspace` | 200 | 1 | `output/playwright/aeis-manual-start/workspace.png` |
| `/source-of-truth` | 200 | 0 | `output/playwright/aeis-manual-start/source-of-truth.png` |
| `/model-council` | 200 | 0 | `output/playwright/aeis-manual-start/model-council.png` |
| `/masterplan` | 200 | 0 | `output/playwright/aeis-manual-start/masterplan.png` |
| `/funding` | 200 | 0 | `output/playwright/aeis-manual-start/funding.png` |
| `/operator-mobile` | 200 | 0 | `output/playwright/aeis-manual-start/operator-mobile.png` |
| `/skills` | 200 | 0 | `output/playwright/aeis-manual-start/skills.png` |
| `/test-center` | 200 | 0 | `output/playwright/aeis-manual-start/test-center.png` |
| `/dashboard/operator-monitor` | 200 | 0 | `output/playwright/aeis-manual-start/dashboard__operator-monitor.png` |

Workspace warning to verify during P1/P4: browser console reported `WebSocket connection to ws://127.0.0.1:8010/ws/workspace failed`.

## Purpose

Inventory every Dashboard surface before project simulations begin.

## Inventory Columns

| Route | UI File | Purpose | Main Actions | Forms | API Refs | Backend Module | Mock/Stub Risk | Runtime Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|

## Required Coverage

- All routes under `src/sylion-frontend/src/app/(app)`.
- Buttons, forms, modals, dropdowns, toggles, tabs.
- Empty, loading, error, success states.
- Mock, stub, fallback, demo markers.
- Screens with mutation actions.
- Screens that claim release, deployment, submit, approval, or external action.
