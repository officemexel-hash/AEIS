# PROD R6 Production Deploy Pipeline PASS1/PASS2

Date: 2026-05-18
Roadmap item: `D.1 Cloud/VPS provisioning freeze` / `PROD-P0-007 Production deploy pipeline`
Decision pack: `results/decisions/PROD-D4-PRODUCTION-DEPLOY-PIPELINE_evidence_pack.json`
Status: `FROZEN_2X` for production deploy pipeline contract, production Human Gate, canary, post-deploy verification and rollback drill

## Scope

This freeze covers:

- New `sylion.ops.production_deploy_pipeline.ProductionDeployPipeline`.
- Full recorded stage chain:
  - `build`
  - `container_scan`
  - `staging_deploy`
  - `smoke_test`
  - `canary`
  - `production_deploy`
  - `post_deploy_verification`
- Rollback drill recording with previous artifact restoration evidence.
- Failure handling:
  - critical/high container scan findings stop the pipeline;
  - smoke failures stop before canary;
  - canary failures stop before production traffic;
  - post-deploy failures trigger rollback to the previous artifact.
- Evidence Spine linkage for every stage, rollback and final deploy summary.
- Public API:
  - `POST /api/v1/production-deploy/pipeline/run`
  - `GET /api/v1/production-deploy/pipelines`
  - `GET /api/v1/production-deploy/pipeline/{run_id}`
  - `POST /api/v1/production-deploy/pipeline/{run_id}/rollback-test`
  - `POST /api/v1/production-deploy/pipeline/{run_id}/rollback`
- Production Human Gate enforcement for deploy and rollback actions.
- Deployment gate ticket scoping now includes `project_id` and `run_id`.

## Files Changed

- `src/sylion-pipeline/sylion/ops/production_deploy_pipeline.py`
- `src/sylion-pipeline/sylion/ops/__init__.py`
- `src/sylion-pipeline/sylion/api/production_deploy_routes.py`
- `src/sylion-pipeline/sylion/api/router.py`
- `src/sylion-pipeline/sylion/governance/deployment_gate.py`
- `src/sylion-pipeline/tests/test_production_deploy_pipeline.py`
- `src/sylion-pipeline/tests/test_production_deploy_routes.py`

## Verification PASS1

```text
python -m compileall -q src\sylion-pipeline\sylion\ops\production_deploy_pipeline.py src\sylion-pipeline\sylion\api\production_deploy_routes.py src\sylion-pipeline\sylion\api\router.py src\sylion-pipeline\sylion\governance\deployment_gate.py
PASS

python -m pytest src\sylion-pipeline\tests\test_deployment_orchestrator.py src\sylion-pipeline\tests\test_deploy_routes.py src\sylion-pipeline\tests\test_rollback_manager.py src\sylion-pipeline\tests\test_production_deploy_pipeline.py src\sylion-pipeline\tests\test_production_deploy_routes.py -q
190 passed, 6 warnings

run_no_mock_scan(limit=200)
PASS 449 0

git diff --check
PASS
```

## Verification PASS2

```text
python -m compileall -q src\sylion-pipeline\sylion\ops\production_deploy_pipeline.py src\sylion-pipeline\sylion\api\production_deploy_routes.py src\sylion-pipeline\sylion\api\router.py src\sylion-pipeline\sylion\governance\deployment_gate.py
PASS

python -m pytest src\sylion-pipeline\tests\test_deployment_orchestrator.py src\sylion-pipeline\tests\test_deploy_routes.py src\sylion-pipeline\tests\test_rollback_manager.py src\sylion-pipeline\tests\test_production_deploy_pipeline.py src\sylion-pipeline\tests\test_production_deploy_routes.py -q
190 passed, 6 warnings

run_no_mock_scan(limit=200)
PASS 449 0

git diff --check
PASS
```

Known warnings are historical deprecation warnings from legacy security/vault imports.

## Boundary

This freeze proves the AEIS production deploy contract inside the runtime: stage ordering, evidence, Human Gate, canary stop conditions, post-deploy verification and rollback restoration. It does not prove a live external cloud rollout because no production cloud credentials or target infrastructure were supplied in this repair step. Real provider provisioning remains covered by the separate Hetzner/deploy surfaces and future environment-specific drills.

AEIS must still remain `BLOCKED` until the remaining production roadmap blockers are frozen twice.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D4-PRODUCTION-DEPLOY-PIPELINE_evidence_pack.json
```

Expected rollback time: 20 minutes.
Data loss risk: `NONE`; the change adds append-only deploy/rollback records and can be reverted by unmounting the API route and removing the service/tests.
