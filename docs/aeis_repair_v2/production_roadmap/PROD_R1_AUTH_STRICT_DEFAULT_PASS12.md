# PROD R1 Auth Strict Default PASS1/PASS2

Date: 2026-05-18
Roadmap item: `PROD-P0-004 Backend RBAC / no legacy bypass`
Decision pack: `results/decisions/PROD-D3-AUTH-STRICT-DEFAULT_evidence_pack.json`
Status: `FROZEN_2X` for production-like auth default behavior

## Scope

This freeze covers the production auth-mode default:

- `SYLION_AUTH_MODE=dev` still works explicitly for local dashboard development.
- `SYLION_AUTH_MODE=strict` still blocks stale bearer fallback.
- `SYLION_AEIS_ENV=production` with unset `SYLION_AUTH_MODE` defaults to strict.
- `SYLION_AEIS_ENV=staging` with unset `SYLION_AUTH_MODE` defaults to strict.

## Files Changed

- `src/sylion-pipeline/sylion/api/app.py`
- `src/sylion-pipeline/tests/test_auth_bootstrap.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\test_auth_bootstrap.py -q
6 passed, 6 warnings
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\test_auth_bootstrap.py -q
6 passed, 6 warnings
```

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-AUTH-STRICT-DEFAULT_evidence_pack.json
```

Expected rollback time: 10 minutes.
Data loss risk: `NONE`.
