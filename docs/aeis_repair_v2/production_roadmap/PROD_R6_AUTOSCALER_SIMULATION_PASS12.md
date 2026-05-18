# PROD R6 Autoscaler Simulation PASS1/PASS2

Date: 2026-05-18
Roadmap item: `D.3 Autoscaler` / `PROD-P2-002 Autoscaler simulation`
Decision pack: `results/decisions/PROD-D3-AUTOSCALER-SIMULATION_evidence_pack.json`
Status: `FROZEN_2X` for CPU, queue depth, error-rate, scale-up, scale-down and no-flapping simulation

## Scope

This freeze covers:

- New autoscaler simulation model in `sylion.worker.autoscaler`:
  - `AutoscalerSignal`
  - `AutoscalerSimulationProfile`
  - `AutoscalerSimulationRunner`
- Simulation inputs:
  - queue depth;
  - CPU percent;
  - error rate;
  - min/max workers;
  - cooldown window;
  - scale-up and scale-down thresholds.
- Simulation checks:
  - scale-up path observed;
  - scale-down path observed;
  - cooldown blocks rapid opposite action;
  - no flapping inside cooldown window;
  - worker count remains within min/max bounds.
- Evidence Spine artifact: `autoscaler_simulation`.
- Public API:
  - `POST /api/v1/workers/autoscaler/simulate`

## Files Changed

- `src/sylion-pipeline/sylion/worker/autoscaler.py`
- `src/sylion-pipeline/sylion/api/autoscaler_routes.py`
- `src/sylion-pipeline/tests/test_autoscaler_simulation.py`

## Verification PASS1

```text
python -m compileall -q src\sylion-pipeline\sylion\worker\autoscaler.py src\sylion-pipeline\sylion\api\autoscaler_routes.py
PASS

python -m pytest src\sylion-pipeline\tests\test_autoscaler_simulation.py src\sylion-pipeline\tests\test_worker_routes.py src\sylion-pipeline\tests\test_worker_fleet_lifecycle.py -q
10 passed, 6 warnings

run_no_mock_scan(limit=200)
PASS 449 0

git diff --check
PASS
```

## Verification PASS2

```text
python -m compileall -q src\sylion-pipeline\sylion\worker\autoscaler.py src\sylion-pipeline\sylion\api\autoscaler_routes.py
PASS

python -m pytest src\sylion-pipeline\tests\test_autoscaler_simulation.py src\sylion-pipeline\tests\test_worker_routes.py src\sylion-pipeline\tests\test_worker_fleet_lifecycle.py -q
10 passed, 6 warnings

run_no_mock_scan(limit=200)
PASS 449 0

git diff --check
PASS
```

Known warnings are historical deprecation warnings from legacy security/vault imports.

## Boundary

This freeze proves autoscaler decision behavior with virtual-time signals. It does not provision or remove real cloud workers; production execution remains handled by worker lifecycle and deployment infrastructure.

AEIS must still remain `BLOCKED` until remaining P2 production roadmap blockers are frozen twice.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-AUTOSCALER-SIMULATION_evidence_pack.json
```

Expected rollback time: 10 minutes.
Data loss risk: `NONE`; simulation records are evidence-only artifacts.
