# PROD R1 RBAC/Auth Contract PASS1/PASS2

Date: 2026-05-18
Roadmap item: `PROD-P0-005 Backend RBAC enforcement`
Decision pack: `results/decisions/PROD-D3-RBAC-AUTH-CONTRACT_evidence_pack.json`
Status: `FROZEN_2X` for strict RBAC middleware/auth contract regression

## Scope

This freeze covers:

- RBAC enforcement tests run in strict auth mode, not dev auto-user mode.
- Anonymous mutating requests return `401`.
- Wrong-role mutating requests return `403`.
- Owner token reaches operator and security routes.
- AuthProvider supports the keyword provider contract:
  - `provider_id=...`
  - `credentials_json=...`
- RBAC coverage and `requires_role()` unit behavior remain green.

## Files Changed

- `src/sylion-pipeline/sylion/security/auth_provider.py`
- `src/sylion-pipeline/tests/security/conftest.py`
- `src/sylion-pipeline/tests/test_auth_provider.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\security\test_rbac_middleware_enforcement.py -q
10 passed

python -m pytest src\sylion-pipeline\tests\security\test_rbac.py -q
10 passed

python -m pytest src\sylion-pipeline\tests\security\test_rbac_coverage.py -q
4 passed

python -m pytest src\sylion-pipeline\tests\test_auth_provider.py -q
59 passed
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\security\test_rbac_middleware_enforcement.py src\sylion-pipeline\tests\security\test_rbac.py src\sylion-pipeline\tests\security\test_rbac_coverage.py -q
24 passed

python -m pytest src\sylion-pipeline\tests\test_auth_provider.py -q
59 passed
```

## Stop-Fix-Retest Note

Earlier RBAC smoke failed because:

- auth fixtures called `AuthProvider.authenticate(provider_id=..., credentials_json=...)`, while the implementation only accepted positional arguments;
- enforcement tests ran under dev auth mode, which injected a dev user and turned anonymous mutation into `403` instead of `401`.

Both failures were fixed, retested twice, and frozen here.

## Boundary

This does not yet prove that every mutating route has an explicit
`Depends(requires_role(...))`; it proves global backend enforcement and coverage
policy. Remaining work:

- add explicit route-level dependencies for highest-risk mutation endpoints;
- persist authorization decisions into the central audit/evidence spine;
- run dashboard E2E with real owner/operator/security/auditor users.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-RBAC-AUTH-CONTRACT_evidence_pack.json
```

Expected rollback time: 15 minutes.
Data loss risk: `NONE`.
