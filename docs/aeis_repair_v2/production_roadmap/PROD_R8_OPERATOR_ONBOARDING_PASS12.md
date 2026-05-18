# PROD_R8_OPERATOR_ONBOARDING_PASS12

Status: FROZEN_2X
Requirement: PROD-P2-005 Operator onboarding
Decision class: D3
Date: 2026-05-18

## Scope

This freeze proves that a new operator can complete the Phase 1 onboarding
path through real Advisor API routes and the production dashboard contract.

The probe executes the operator path end to end:

1. reset onboarding state;
2. run system check;
3. validate workspace storage;
4. save Phase 1 steps 1 through 7;
5. pass model/API/demo hard gate;
6. complete Phase 1;
7. run acceptance-test;
8. verify `has_completed=true`;
9. verify completed state marker;
10. verify frontend wizard, hook, API client and first-run banner markers.

The time budget is 15 minutes. The automated production probe completed in
less than 1 minute and verifies that no external provider is required because
the model gate accepts local models, an API shortcut, or explicit demo mode.

## Implementation

Files changed:

- `src/sylion-pipeline/sylion/aeis/testing/operator_onboarding.py`
- `src/sylion-pipeline/sylion/api/test_center_routes.py`
- `src/sylion-pipeline/tests/aeis/testing/test_operator_onboarding.py`

New Test Center endpoint:

- `GET /api/v1/test-center/operator-onboarding`

The runner mints a real operator bearer token for full-app probes so the
internal onboarding mutations pass through the RBAC middleware instead of
depending on a test-only bypass.

## Frozen Checks

| Check | Expected result |
| --- | --- |
| Reset state | 2xx |
| Phase 1 system check | 2xx |
| Storage validation | `ok=true` |
| Save steps 1-7 | all 2xx |
| Model gate | `passed=true` |
| Complete Phase 1 | 2xx, completion marker present |
| Workspace bootstrap | 15 folders created |
| Acceptance test | `accepted=true` |
| First-run completion | `has_completed=true` |
| Secret handling | API shortcut key redacted in response |
| Frontend contract | wizard, hook, API client and banner markers present |
| Duration | `< 15 minutes` |

## PASS1

Commands and results:

- `python -m compileall -q src\sylion-pipeline\sylion\aeis\testing\operator_onboarding.py src\sylion-pipeline\sylion\api\test_center_routes.py` -> PASS
- `python -m pytest src\sylion-pipeline\tests\aeis\testing\test_operator_onboarding.py -q` -> 4 passed
- Full-app probe via `OperatorOnboardingRunner(app=app).run(record_evidence=False)` -> PASS, 15 steps, 0 failed, acceptance PASS, `has_completed=True`, 15 folders, secrets redacted
- `python -m pytest src\sylion-pipeline\tests\aeis\testing\test_operator_onboarding.py src\sylion-pipeline\tests\aeis\advisor\_e2e\test_advisor_rest_routes.py src\sylion-pipeline\tests\api\test_test_center_routes.py -q` -> 49 passed
- `npx tsc --noEmit --pretty false` -> PASS
- `run_no_mock_scan(limit=500)` -> PASS, blocking_count 0
- `git diff --check` -> PASS

## PASS2

Commands and results:

- `python -m pytest src\sylion-pipeline\tests\aeis\testing\test_operator_onboarding.py src\sylion-pipeline\tests\aeis\advisor\_e2e\test_advisor_rest_routes.py src\sylion-pipeline\tests\api\test_test_center_routes.py -q` -> 49 passed
- `npx tsc --noEmit --pretty false` -> PASS
- `run_no_mock_scan(limit=500)` -> PASS, blocking_count 0
- `git diff --check` -> PASS

## Freeze Rule

Operator onboarding remains frozen only while:

- Phase 1 completion runs through backend routes, not local-only state;
- the production probe can complete under RBAC with an operator token;
- storage validation creates a safe workspace bootstrap;
- acceptance-test returns `accepted=true`;
- `has_completed=true` is visible to the first-run banner;
- API shortcut secrets are never returned raw;
- the wizard can be completed inside the 15-minute production budget;
- any new onboarding step is added to the probe and run through PASS1/PASS2.

