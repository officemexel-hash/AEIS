# PROD R1 Rate Limit Redis/Role PASS1/PASS2

Date: 2026-05-18
Roadmap item: `PROD-P0-004 Rate limiting globalne`
Decision pack: `results/decisions/PROD-D3-RATE-LIMIT-REDIS-ROLE_evidence_pack.json`
Status: `FROZEN_2X` for Redis-required strict runtime and per-role API budgets

## Scope

This freeze covers:

- Atomic `Cache.incr()` for rate-limit counters.
- Redis `INCR`/`EXPIRE` path for the Redis cache backend.
- Staging/production fail-fast when `SYLION_CACHE_URL` is missing, `memory`, or not `redis://` / `rediss://`.
- Startup policy requiring Redis cache for global rate limiting.
- Role-aware API tiers:
  - `owner`: 1200 rpm;
  - `security`: 900 rpm;
  - `operator`: 600 rpm;
  - `auditor`: 300 rpm;
  - `viewer`: 120 rpm.
- Existing heavy endpoints still cap at 30 rpm.
- `X-RateLimit-Tier` response header for operator/debug visibility.

## Files Changed

- `src/sylion-pipeline/sylion/api/rate_limit.py`
- `src/sylion-pipeline/sylion/infra/cache.py`
- `src/sylion-pipeline/sylion/security/startup_check.py`
- `src/sylion-pipeline/tests/api/test_rate_limit.py`
- `src/sylion-pipeline/tests/infra/test_cache.py`
- `src/sylion-pipeline/tests/security/test_startup_check.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\api\test_rate_limit.py -q
22 passed

python -m pytest src\sylion-pipeline\tests\infra\test_cache.py -q
20 passed

python -m pytest src\sylion-pipeline\tests\security\test_startup_check.py -q
35 passed
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\api\test_rate_limit.py -q
22 passed

python -m pytest src\sylion-pipeline\tests\infra\test_cache.py -q
20 passed

python -m pytest src\sylion-pipeline\tests\security\test_startup_check.py -q
35 passed

python -m pytest src\sylion-pipeline\tests\infra\test_cache_integration.py -q
8 passed
```

## Boundary

This proves code-level Redis readiness and strict configuration policy. It does
not claim a live production load test against an actual Redis cluster yet.
Remaining work:

- provision Redis in staging/production;
- run 10x expected peak load against staging;
- capture p95/p99 latency and 429 behavior under real concurrency;
- attach Redis metrics and dashboard screenshots to the final production book.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-RATE-LIMIT-REDIS-ROLE_evidence_pack.json
```

Expected rollback time: 20 minutes.
Data loss risk: `NONE`.
