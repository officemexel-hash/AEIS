# PROD_R7_ROUTE_ACTION_CLOSURE_PASS12

Status: FROZEN_2X
Requirement: PROD-P2-004 Route-action closure
Decision class: D3
Date: 2026-05-18

## Scope

This freeze closes the production roadmap gap where priority dashboard pages
could render while their save/submit/execute actions were not proven against
live backend routes. The new closure contract covers:

- backend FastAPI route existence;
- frontend route surface file existence;
- frontend action/client marker existence;
- shared empty-body and non-2xx response handling;
- explicit 204, 403, 500, network-error and timeout behavior.

The contract is not a replacement for browser click-through E2E. It is the
production guard that prevents route-only or client-path drift from being
marked as production ready.

## Implementation

Files changed:

- `src/sylion-pipeline/sylion/aeis/testing/route_action_closure.py`
- `src/sylion-pipeline/sylion/api/test_center_routes.py`
- `src/sylion-pipeline/tests/aeis/testing/test_route_action_closure.py`
- `src/sylion-frontend/src/lib/api/client.ts`

The frontend contracts client was repaired from non-proxied paths:

- `/contracts`
- `/contracts/{id}`
- `/contracts/bindings`

to live proxied API paths:

- `/api/v1/contracts`
- `/api/v1/contracts/{id}`
- `/api/v1/contracts/bindings`

New Test Center endpoint:

- `GET /api/v1/test-center/route-action-closure`

## Frozen Action Manifest

| Action | Surface | Method | Backend path |
| --- | --- | --- | --- |
| `advisor.card.action` | `/advisor` | POST | `/api/v1/advisor/cards/{card_id}/actions` |
| `planning.phase28.masterplan` | `/planning` | POST | `/api/v1/planning/projects/{project_id}/phase28/generate-masterplan` |
| `source_of_truth.freeze_canon` | `/source-of-truth` | POST | `/api/v1/projects/{project_id}/canon/freeze` |
| `masterplan.freeze` | `/masterplan` | POST | `/api/v1/projects/{project_id}/masterplan/freeze` |
| `ontology.reload` | `/ontology` | POST | `/api/v1/ontology/reload` |
| `contracts.list.active` | `/contracts` | GET | `/api/v1/contracts` |
| `contracts.register` | `/contracts` | POST | `/api/v1/contracts` |
| `templates_setup.defaults.apply` | `/templates-setup` | POST | `/api/v1/templates-setup/{phase_id}/defaults/apply` |
| `environments.create` | `/environments` | POST | `/api/v1/environment-catalog/environments` |

## PASS1

Commands and results:

- `python -m compileall -q src\sylion-pipeline\sylion\aeis\testing\route_action_closure.py src\sylion-pipeline\sylion\api\test_center_routes.py` -> PASS
- `python -m pytest src\sylion-pipeline\tests\aeis\testing\test_route_action_closure.py -q` -> 5 passed
- `python -m pytest src\sylion-pipeline\tests\api\test_test_center_routes.py::test_production_readiness_endpoint_blocks_false_ready_claims src\sylion-pipeline\tests\api\test_test_center_routes.py::test_health_lists_all_endpoints -q` -> 2 passed
- `python -m pytest src\sylion-pipeline\tests\aeis\testing\test_route_action_closure.py src\sylion-pipeline\tests\api\test_test_center_routes.py -q` -> 33 passed
- `npm run lint -- src/lib/api/client.ts` -> 0 errors, existing warnings only
- `npx tsc --noEmit --pretty false` -> PASS
- `run_no_mock_scan(limit=500)` -> PASS, blocking_count 0
- `git diff --check` -> PASS

## PASS2

Commands and results:

- `python -m pytest src\sylion-pipeline\tests\aeis\testing\test_route_action_closure.py src\sylion-pipeline\tests\api\test_test_center_routes.py -q` -> 33 passed
- `npx tsc --noEmit --pretty false` -> PASS
- `run_no_mock_scan(limit=500)` -> PASS, blocking_count 0
- `git diff --check` -> PASS

## Freeze Rule

Route-action closure remains frozen only while:

- every manifest action has a backend route in the FastAPI app;
- every action has a frontend/client marker in tracked source;
- shared frontend clients continue to treat 204 or empty response bodies as
  successful no-content responses;
- 403, 500, network failures and timeouts are surfaced as operator-visible
  errors instead of false-success toasts;
- any new mutating priority dashboard action is added to the manifest and
  tested with PASS1/PASS2 before release.

