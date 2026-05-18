# PROD R1 DB Policy PASS1/PASS2

Date: 2026-05-18
Roadmap item: `PROD-P0-001 PostgreSQL required`
Decision pack: `results/decisions/PROD-D4-DB-POLICY_evidence_pack.json`
Status: `FROZEN_2X` for startup DB policy unit coverage

## Scope

This freeze covers the first production roadmap implementation slice:

- SQLite remains allowed for `dev` and `test`.
- `staging` and `production` require PostgreSQL.
- PostgreSQL URL must use `postgresql+asyncpg://`.
- `DATABASE_URL` is accepted as an alias for `SYLION_DB_URL`.
- FastAPI app DB mode is read dynamically after `.env` loading, not only at module import time.
- `production` refuses to boot when `SYLION_RATE_LIMIT_DISABLED=1`.
- Advisor-layer PostgreSQL table/index DDL is normalized to `IF NOT EXISTS` before migration execution.

## Files Changed

- `src/sylion-pipeline/sylion/security/startup_check.py`
- `src/sylion-pipeline/sylion/db/__init__.py`
- `src/sylion-pipeline/sylion/db/pg_migration.py`
- `src/sylion-pipeline/sylion/api/app.py`
- `src/sylion-pipeline/tests/security/test_startup_check.py`
- `src/sylion-pipeline/tests/test_pg_migration.py`
- `src/sylion-pipeline/tests/test_server_integration.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\security\test_startup_check.py -q
31 passed, 4 warnings

python -m pytest src\sylion-pipeline\tests\test_pg_migration.py -q
24 passed

python -m pytest src\sylion-pipeline\tests\test_server_integration.py -q
9 passed, 6 warnings
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\security\test_startup_check.py -q
31 passed, 4 warnings

python -m pytest src\sylion-pipeline\tests\test_pg_migration.py -q
24 passed

python -m pytest src\sylion-pipeline\tests\test_server_integration.py -q
9 passed, 6 warnings
```

## Static Checks

```text
git diff --check
PASS

python -m compileall -q src\sylion-pipeline\sylion\security\startup_check.py src\sylion-pipeline\sylion\db\__init__.py src\sylion-pipeline\sylion\db\pg_migration.py src\sylion-pipeline\sylion\api\app.py
PASS
```

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D4-DB-POLICY_evidence_pack.json
```

Expected rollback time: 15 minutes.
Data loss risk: `NONE`.

## Remaining Work

This freezes only the startup DB policy. The wider production database track still requires:

- real PostgreSQL staging environment;
- migration upgrade/downgrade drill;
- backup/restore drill;
- PgBouncer/connection monitoring;
- production-like dashboard smoke on PostgreSQL.
- enum/trigger/function idempotency audit for the expanded advisor-layer SQL.
