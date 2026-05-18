# PROD R5 Production Repair Loop PASS1/PASS2

Date: 2026-05-18
Roadmap items: `E.1 Golden test suite`, `E.2 E2E dashboard suite`, `PROD-P0/P1 no false READY rule`
Decision pack: `results/decisions/PROD-D3-PRODUCTION-REPAIR-LOOP_evidence_pack.json`
Status: `FROZEN_2X` for production readiness blocking, repair-loop command and dashboard visibility

## Scope

This freeze covers:

- New `sylion.aeis.testing.production_readiness.ProductionReadinessRunner`.
- Hard command protocol: `AEIS_PRODUCTION_REPAIR_LOOP`.
- Enforced sequence:
  - stop on first error;
  - record blocker with evidence;
  - repair before next item;
  - run PASS1;
  - run PASS2 on the same scope;
  - write freeze note and evidence pack;
  - advance only after `FROZEN_2X`.
- Production readiness cannot return `PROD_READY` while any required P0/P1/P2 roadmap freeze evidence is missing.
- Test Center API:
  - `GET /api/v1/test-center/production-readiness`
  - `POST /api/v1/test-center/production-readiness/command`
- Test Center dashboard now shows:
  - production readiness status;
  - blocker count;
  - next blocker;
  - repair-loop command.

## Files Changed

- `src/sylion-pipeline/sylion/aeis/testing/production_readiness.py`
- `src/sylion-pipeline/sylion/api/test_center_routes.py`
- `src/sylion-pipeline/tests/test_production_readiness.py`
- `src/sylion-pipeline/tests/api/test_test_center_routes.py`
- `src/sylion-frontend/src/app/(app)/test-center/dashboard/page.tsx`

## Verification PASS1

```text
python -m compileall -q src\sylion-pipeline\sylion\aeis\testing\production_readiness.py src\sylion-pipeline\sylion\api\test_center_routes.py
PASS

python -m pytest src\sylion-pipeline\tests\test_production_readiness.py src\sylion-pipeline\tests\api\test_test_center_routes.py -q
31 passed, 6 warnings
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\test_production_readiness.py src\sylion-pipeline\tests\api\test_test_center_routes.py -q
31 passed, 6 warnings

npx eslint 'src/app/(app)/test-center/dashboard/page.tsx'
PASS

npx tsc --noEmit --pretty false
PASS

git diff --check
PASS
```

Known warnings are historical deprecation warnings from legacy security/vault imports.

## Boundary

This freeze does not make AEIS production-ready by itself. It prevents the system and operator dashboard from falsely claiming production readiness until the remaining production roadmap items have `FROZEN_2X` evidence. Current expected blockers include production deploy/canary/rollback, worker fleet lifecycle, load test 10x, autoscaler, global terminal policy, route-action closure and onboarding.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-PRODUCTION-REPAIR-LOOP_evidence_pack.json
```

Expected rollback time: 15 minutes.
Data loss risk: `NONE`; recorded readiness command rows are advisory audit state.
