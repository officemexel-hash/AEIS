# PROD R6 Worker Fleet Lifecycle PASS1/PASS2

Date: 2026-05-18
Roadmap item: `D.2 Worker fleet production` / `PROD-P1-007 Worker fleet lifecycle`
Decision pack: `results/decisions/PROD-D3-WORKER-FLEET-LIFECYCLE_evidence_pack.json`
Status: `FROZEN_2X` for worker register, heartbeat, rebalance, graceful shutdown and evidence drill

## Scope

This freeze covers:

- New `sylion.worker.lifecycle.WorkerFleetLifecycle`.
- Worker lifecycle drill:
  - register external-equivalent workers;
  - record heartbeats with load data;
  - overfill one worker and rebalance to an underloaded worker;
  - gracefully drain a worker;
  - move active assignments during shutdown;
  - mark the drained worker offline;
  - register Evidence Spine artifacts for shutdown and drill summary.
- Public API:
  - `POST /api/v1/workers/fleet/lifecycle-drill`
  - `GET /api/v1/workers/fleet/lifecycle-drills`
  - `GET /api/v1/workers/fleet/lifecycle-drills/{drill_id}`
  - `POST /api/v1/workers/{worker_id}/graceful-shutdown`
- Worker registry route initialization now honors `SYLION_WORKER_DB_PATH` or `SYLION_DB_PATH`.
- Graceful shutdown has a fail-closed path: if no target worker has capacity, assignments are marked `blocked` with shutdown metadata instead of being lost.

## Files Changed

- `src/sylion-pipeline/sylion/worker/lifecycle.py`
- `src/sylion-pipeline/sylion/worker/__init__.py`
- `src/sylion-pipeline/sylion/api/worker_routes.py`
- `src/sylion-pipeline/tests/test_worker_fleet_lifecycle.py`
- `src/sylion-pipeline/tests/test_worker_routes.py`

## Verification PASS1

```text
python -m compileall -q src\sylion-pipeline\sylion\worker\lifecycle.py src\sylion-pipeline\sylion\worker\__init__.py src\sylion-pipeline\sylion\api\worker_routes.py
PASS

python -m pytest src\sylion-pipeline\tests\test_worker_routes.py src\sylion-pipeline\tests\test_worker_fleet_lifecycle.py src\sylion-pipeline\tests\project_mode\test_worker_reconcile.py src\sylion-pipeline\tests\integration\test_unified_truth.py::TestWorkerPoolReconciliation -q
22 passed, 6 warnings

run_no_mock_scan(limit=200)
PASS 449 0

git diff --check
PASS
```

## Verification PASS2

```text
python -m compileall -q src\sylion-pipeline\sylion\worker\lifecycle.py src\sylion-pipeline\sylion\worker\__init__.py src\sylion-pipeline\sylion\api\worker_routes.py
PASS

python -m pytest src\sylion-pipeline\tests\test_worker_routes.py src\sylion-pipeline\tests\test_worker_fleet_lifecycle.py src\sylion-pipeline\tests\project_mode\test_worker_reconcile.py src\sylion-pipeline\tests\integration\test_unified_truth.py::TestWorkerPoolReconciliation -q
22 passed, 6 warnings

run_no_mock_scan(limit=200)
PASS 449 0

git diff --check
PASS
```

Known warnings are historical deprecation warnings from legacy security/vault imports.

## Boundary

This freeze proves lifecycle behavior in the AEIS worker control plane and production-equivalent worker records. It does not prove SSH/systemd/Kubernetes process supervision on a live external fleet because external worker credentials and hosts were not supplied in this repair step.

AEIS must still remain `BLOCKED` until the remaining production roadmap blockers are frozen twice.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-WORKER-FLEET-LIFECYCLE_evidence_pack.json
```

Expected rollback time: 15 minutes.
Data loss risk: `NONE`; the change adds lifecycle drill records and worker assignment moves through existing registry APIs.
