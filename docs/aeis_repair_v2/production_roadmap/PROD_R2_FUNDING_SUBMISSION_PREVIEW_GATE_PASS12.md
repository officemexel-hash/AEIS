# PROD R2 Funding Submission Preview Gate PASS1/PASS2

Date: 2026-05-18
Roadmap items: `B.3 Funding external submit gate`, `Luka 5 Funding Governance Gap`
Decision pack: `results/decisions/PROD-D3-FUNDING-SUBMISSION-PREVIEW-GATE_evidence_pack.json`
Status: `FROZEN_2X` for funding submit preview hash, Human Gate binding, drift rejection and receipt audit

## Scope

This freeze covers:

- New `GET /api/v1/funding/submission/preview?session_id=...` endpoint for the exact external-submit payload.
- Deterministic SHA-256 `payload_hash` for the preview payload.
- Approval request stores `payload_hash`, full `preview_payload`, validation and finality notice.
- The D4 funding Human Gate ticket payload includes `payload_hash` and preview summary.
- Final submit recomputes the preview payload and blocks submission if anything changed after approval.
- Final receipt includes `payload_hash`, `approval_event_id`, `governance_ticket_id` and `no_rollback_after_real_submit`.
- Funding submit audit writes the same receipt payload, including the hash.
- Browser automation manifest lifecycle stage corrected from invalid `validate` to `beta`.

## Files Changed

- `src/sylion-pipeline/sylion/funding_autopilot/service.py`
- `src/sylion-pipeline/sylion/funding_autopilot/routes.py`
- `src/sylion-pipeline/sylion/funding_autopilot/governance_bridge.py`
- `src/sylion-pipeline/tests/test_funding_autopilot_routes.py`
- `src/sylion-pipeline/sylion/contracts/manifests/funding_autopilot.browser_automation.json`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\test_funding_autopilot_routes.py src\sylion-pipeline\tests\funding -q
67 passed, 6 warnings

python -m compileall -q src\sylion-pipeline\sylion\funding_autopilot
PASS
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\test_funding_autopilot_routes.py src\sylion-pipeline\tests\funding -q
67 passed, 6 warnings

git diff --check
PASS
```

## Stop-Fix-Retest Note

The first broad PASS2 attempt failed before freeze:

```text
FAILED test_contract_manifests.py
funding_autopilot.browser_automation.json lifecycle_stage was validate
```

The manifest was corrected to `beta`, then the full funding test suite was restarted and passed twice.

## Boundary

This freeze does not perform a real grant portal submission and does not add a portal-side rollback mechanism. It guarantees that AEIS cannot finalize a recorded external submit unless the exact payload seen at approval time still matches the current payload.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-FUNDING-SUBMISSION-PREVIEW-GATE_evidence_pack.json
```

Expected rollback time: 25 minutes.
Data loss risk: `NONE`.
