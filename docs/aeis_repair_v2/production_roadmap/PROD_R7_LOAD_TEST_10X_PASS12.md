# PROD R7 Load Test 10x Peak PASS1/PASS2

Date: 2026-05-18
Roadmap item: `E.3 Load test` / `PROD-P1-008 Load test 10x peak`
Decision pack: `results/decisions/PROD-D3-LOAD-TEST-10X_evidence_pack.json`
Status: `FROZEN_2X` for 10x peak load runner, p99, DB connection, memory growth and worker dispatch checks

## Scope

This freeze covers:

- New `sylion.quality.load_test.LoadTestRunner`.
- Configurable 10x peak profile:
  - `expected_peak_operations`
  - `peak_multiplier >= 10`
  - `target_p99_ms`
  - `max_db_connections`
  - `max_memory_growth_bytes`
  - `worker_count`
  - `dispatch_target_p99_ms`
- Runtime checks:
  - total operations = expected peak x multiplier;
  - p50/p95/p99 operation latency;
  - DB write p99;
  - DB connections opened;
  - worker dispatch p99;
  - memory growth and peak memory via `tracemalloc`;
  - fail-closed status if any threshold is breached.
- Runtime instrumentation:
  - `RuntimePerfTracker.record(...)`;
  - `MemoryFootprintTracker.snapshot(...)`;
  - Evidence Spine `load_test_10x` artifact.
- Public API:
  - `POST /api/v1/quality/load-tests/10x`
  - `GET /api/v1/quality/load-tests`
  - `GET /api/v1/quality/load-tests/{run_id}`

## Files Changed

- `src/sylion-pipeline/sylion/quality/load_test.py`
- `src/sylion-pipeline/sylion/quality/__init__.py`
- `src/sylion-pipeline/sylion/api/quality_routes.py`
- `src/sylion-pipeline/tests/test_load_test_runner.py`
- `src/sylion-pipeline/tests/test_quality_load_routes.py`

## Verification PASS1

```text
python -m compileall -q src\sylion-pipeline\sylion\quality\load_test.py src\sylion-pipeline\sylion\quality\__init__.py src\sylion-pipeline\sylion\api\quality_routes.py
PASS

python -m pytest src\sylion-pipeline\tests\test_load_test_runner.py src\sylion-pipeline\tests\test_quality_load_routes.py src\sylion-pipeline\tests\test_runtime_perf.py src\sylion-pipeline\tests\test_memory_footprint.py src\sylion-pipeline\tests\test_worker_fleet_lifecycle.py -q
47 passed, 6 warnings

run_no_mock_scan(limit=200)
PASS 449 0

git diff --check
PASS
```

## Verification PASS2

```text
python -m compileall -q src\sylion-pipeline\sylion\quality\load_test.py src\sylion-pipeline\sylion\quality\__init__.py src\sylion-pipeline\sylion\api\quality_routes.py
PASS

python -m pytest src\sylion-pipeline\tests\test_load_test_runner.py src\sylion-pipeline\tests\test_quality_load_routes.py src\sylion-pipeline\tests\test_runtime_perf.py src\sylion-pipeline\tests\test_memory_footprint.py src\sylion-pipeline\tests\test_worker_fleet_lifecycle.py -q
47 passed, 6 warnings

run_no_mock_scan(limit=200)
PASS 449 0

git diff --check
PASS
```

Known warnings are historical deprecation warnings from legacy security/vault imports.

## Boundary

This freeze proves the in-process AEIS 10x load harness and threshold enforcement. It does not replace an external distributed load test against a real production cluster. For live production release, the same runner must be executed with production-calibrated expected peak values and target infrastructure metrics.

AEIS must still remain `BLOCKED` until remaining P2 production roadmap blockers are frozen twice.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-LOAD-TEST-10X_evidence_pack.json
```

Expected rollback time: 10 minutes.
Data loss risk: `NONE`; load test records are append-only quality evidence.
