# PROD R2 Mobile Device Audit PASS1/PASS2

Date: 2026-05-18
Roadmap items: `B.4 Mobile approve/reject`, `Luka 9 Mobile Device Identity i Audit`
Decision pack: `results/decisions/PROD-D3-MOBILE-DEVICE-AUDIT_evidence_pack.json`
Status: `FROZEN_2X` for mobile device-bound D3-D5 decisions and mobile audit trail

## Scope

This freeze covers:

- D3-D5 mobile `approved` / `rejected` decisions require `device_id`.
- `device_id` must be actively bound to the reviewer/operator.
- Successful mobile decisions write `operator_mobile.ticket.decision` to the audit trail.
- Audit metadata includes `ticket_id`, `decision`, `reason`, `device_id`, platform, device label, auth method, geo payload, decision class and project id.
- `operator_mobile` is now an accepted audit source.
- Mobile queue/detail frontend sends the first active bound device id with approvals/rejections.
- The shared frontend API client includes `device_id` and `auth_method` in mobile approve/reject payloads.

## Files Changed

- `src/sylion-pipeline/sylion/api/operator_mobile_routes.py`
- `src/sylion-pipeline/sylion/security/audit_trail_aggregator.py`
- `src/sylion-pipeline/tests/operator_mobile/test_routes.py`
- `src/sylion-frontend/src/app/(app)/operator-mobile/_mobile.ts`
- `src/sylion-frontend/src/app/(app)/operator-mobile/queue/page.tsx`
- `src/sylion-frontend/src/app/(app)/operator-mobile/queue/[ticketId]/page.tsx`
- `src/sylion-frontend/src/lib/api/client.ts`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\operator_mobile src\sylion-pipeline\tests\test_audit_trail_aggregator.py src\sylion-pipeline\tests\security_dedup\test_audit_aggregator.py src\sylion-pipeline\tests\integration\scenarios\test_S8_operator_mobile.py -q
93 passed, 4 warnings

npx tsc --noEmit
PASS

npx eslint "src/app/(app)/operator-mobile/_mobile.ts" "src/app/(app)/operator-mobile/queue/page.tsx" "src/app/(app)/operator-mobile/queue/[ticketId]/page.tsx" --max-warnings=0
PASS

npx eslint "src/lib/api/client.ts" --quiet
PASS
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\operator_mobile src\sylion-pipeline\tests\test_audit_trail_aggregator.py src\sylion-pipeline\tests\security_dedup\test_audit_aggregator.py src\sylion-pipeline\tests\integration\scenarios\test_S8_operator_mobile.py -q
93 passed, 4 warnings

npx tsc --noEmit
PASS

npx eslint "src/app/(app)/operator-mobile/_mobile.ts" "src/app/(app)/operator-mobile/queue/page.tsx" "src/app/(app)/operator-mobile/queue/[ticketId]/page.tsx" --max-warnings=0
PASS

npx eslint "src/lib/api/client.ts" --quiet
PASS
```

Additional checks:

```text
python -m compileall -q src\sylion-pipeline\sylion\api\operator_mobile_routes.py src\sylion-pipeline\sylion\security\audit_trail_aggregator.py
PASS

git diff --check
PASS
```

## Stop-Fix-Retest Note

Global frontend lint was also run:

```text
npm run lint -- --max-warnings=0
FAILED: 1531 existing warnings, 0 errors
```

The failure is not from this mobile slice. The changed operator-mobile files pass with `--max-warnings=0`; `client.ts` has no lint errors under `--quiet` but already contains broad historical `any` warnings.

## Boundary

This freeze does not yet add a real Firebase/APNs provider, QR-code binding, TOTP, biometric verification, offline queue sync or device geofence policy. It closes the backend/frontend identity and audit gap for online mobile decisions.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-MOBILE-DEVICE-AUDIT_evidence_pack.json
```

Expected rollback time: 20 minutes.
Data loss risk: `NONE`.
