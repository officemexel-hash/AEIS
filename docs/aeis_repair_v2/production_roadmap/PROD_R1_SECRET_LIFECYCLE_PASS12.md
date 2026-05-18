# PROD R1 Secret Lifecycle PASS1/PASS2

Date: 2026-05-18
Roadmap item: `PROD-P0-003 Vault/secrets`
Decision pack: `results/decisions/PROD-D4-SECRET-LIFECYCLE_evidence_pack.json`
Status: `FROZEN_2X` for strict secret backend policy and add/validate/rotate dummy flow

## Scope

This freeze covers:

- `SecretLifecyclePolicy` with staging/production backend allow-list: `sops`, `vault`.
- Rejection of plaintext-like backends in strict environments: `env`, `file`, `memory`, `plaintext`, legacy `secret_provider`, legacy `key_vault`.
- Rotation period policy: `SYLION_SECRETS_ROTATION_DAYS <= 90`.
- `SecretLifecycleService` flow: add -> validate -> rotate -> validate.
- API routes under `/api/v1/secrets/lifecycle/*` with RBAC dependencies.
- No plaintext secret values returned from lifecycle service or route responses.
- `KeyStoreUnified.describe()` and safe lifecycle audit events.
- File-backed `KeyVault` and `KeyStoreUnified` create missing parent directories on clean installs.

## Files Changed

- `src/sylion-pipeline/sylion/security/secret_lifecycle.py`
- `src/sylion-pipeline/sylion/security/startup_check.py`
- `src/sylion-pipeline/sylion/security/key_store_unified.py`
- `src/sylion-pipeline/sylion/security/key_vault.py`
- `src/sylion-pipeline/sylion/api/secret_routes.py`
- `src/sylion-pipeline/tests/security/test_secret_lifecycle.py`
- `src/sylion-pipeline/tests/api/test_secret_lifecycle_routes.py`
- `src/sylion-pipeline/tests/security/test_startup_check.py`
- `src/sylion-pipeline/tests/security_dedup/test_key_store_unified.py`
- `src/sylion-pipeline/tests/test_key_vault.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\security\test_secret_lifecycle.py -q
6 passed

python -m pytest src\sylion-pipeline\tests\security_dedup\test_key_store_unified.py -q
16 passed

python -m pytest src\sylion-pipeline\tests\security\test_startup_check.py -q
33 passed

python -m pytest src\sylion-pipeline\tests\api\test_secret_lifecycle_routes.py -q
3 passed

python -m pytest src\sylion-pipeline\tests\aeis_v2\test_be8_backend_extensions.py::test_secrets_post_creates_entry -q
1 passed
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\security\test_secret_lifecycle.py src\sylion-pipeline\tests\api\test_secret_lifecycle_routes.py -q
9 passed

python -m pytest src\sylion-pipeline\tests\security_dedup\test_key_store_unified.py src\sylion-pipeline\tests\test_key_vault.py::TestDatabasePath -q
18 passed

python -m pytest src\sylion-pipeline\tests\security\test_startup_check.py -q
33 passed

python -m pytest src\sylion-pipeline\tests\aeis_v2\test_be8_backend_extensions.py::test_secrets_post_creates_entry -q
1 passed
```

## Stop-Fix-Retest Note

During wider smoke, `/secrets/create` exposed a clean-install fault:
file-backed `KeyVault` did not create its parent DB directory. This was fixed,
retested, and included in this freeze.

The full `tests/aeis_v2/test_be8_backend_extensions.py` still contains two
governance phase assertions outside this secret slice:

- expected `build_in_progress`, actual `build_authorization`;
- expected `execution`, actual `governance`.

Those are tracked for the next governance/Human Gate roadmap slice rather than
mixed into this secret lifecycle commit.

## Boundary

This does not claim a live external HashiCorp Vault deployment. AEIS already
has SOPS/age envelope encryption, and this slice enforces a strict backend
contract and value-safe lifecycle around the unified key store. Remaining work:

- provision the final production secret manager;
- map `vault://...` references into runtime consumers;
- run real key rotation against staging providers;
- attach final operator approval and Council vote evidence.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D4-SECRET-LIFECYCLE_evidence_pack.json
```

Expected rollback time: 25 minutes.
Data loss risk: `NONE`.
