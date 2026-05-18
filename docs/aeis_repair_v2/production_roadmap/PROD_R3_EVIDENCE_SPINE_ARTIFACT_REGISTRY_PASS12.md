# PROD R3 Evidence Spine Artifact Registry PASS1/PASS2

Date: 2026-05-18
Roadmap items: `C.2 Evidence spine`, `Luka 2 Memory Split`
Decision pack: `results/decisions/PROD-D3-EVIDENCE-SPINE-ARTIFACT-REGISTRY_evidence_pack.json`
Status: `FROZEN_2X` for core Evidence Spine artifact registration, checksum verification and API surface

## Scope

This freeze covers:

- `EvidenceArtifact` model with `evidence_id`, `source`, `artifact_type`, `uri`, `checksum`, `retention_policy`, metadata, size and actor.
- `evidence_artifacts` table attached to the existing core Evidence Spine database.
- `register_artifact`, `register_json_artifact`, `register_file_artifact`, `get_artifact`, `list_artifacts` and `verify_artifact` APIs.
- Every artifact registration appends `evidence.artifact.registered` to the existing SHA-256 hash chain.
- JSON artifacts are checksummed using canonical JSON.
- File artifacts are checksummed from bytes and can detect file tampering.
- Core API endpoints for artifact listing, JSON artifact registration, fetch and verify.
- Manifest update: `core.evidence_spine` now publishes `evidence.artifact.registered` and is promoted from `draft` to `beta`.

## Files Changed

- `src/sylion-pipeline/sylion/core/evidence_spine.py`
- `src/sylion-pipeline/sylion/api/core_routes.py`
- `src/sylion-pipeline/sylion/contracts/manifests/core.evidence_spine.json`
- `src/sylion-pipeline/tests/test_core_evidence_spine.py`
- `src/sylion-pipeline/tests/test_api_integration.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\test_core_evidence_spine.py src\sylion-pipeline\tests\test_evidence_spine.py src\sylion-pipeline\tests\test_memory_evidence_store.py src\sylion-pipeline\tests\test_evidence_signer_v2.py src\sylion-pipeline\tests\test_lifecycle_gates.py src\sylion-pipeline\tests\test_api_integration.py -q
319 passed, 2 xfailed, 6 xpassed, 7 warnings

python -m compileall -q src\sylion-pipeline\sylion\core\evidence_spine.py src\sylion-pipeline\sylion\api\core_routes.py
PASS

git diff --check
PASS
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\test_core_evidence_spine.py src\sylion-pipeline\tests\test_evidence_spine.py src\sylion-pipeline\tests\test_memory_evidence_store.py src\sylion-pipeline\tests\test_evidence_signer_v2.py src\sylion-pipeline\tests\test_lifecycle_gates.py src\sylion-pipeline\tests\test_api_integration.py -q
319 passed, 2 xfailed, 6 xpassed, 7 warnings
```

Known warnings are historical deprecation warnings plus one existing `PytestReturnNotNoneWarning` in `test_api_integration.py`.

## Boundary

This freeze creates the canonical artifact registry and public API. It does not yet automatically force every freeze register, bug ledger, W18 audit JSONL, screenshot pipeline and API response writer to call the registry. Those integrations remain follow-up wiring tasks under `C.2`.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-EVIDENCE-SPINE-ARTIFACT-REGISTRY_evidence_pack.json
```

Expected rollback time: 20 minutes.
Data loss risk: `NONE` for code rollback; existing artifact rows can remain inert.
