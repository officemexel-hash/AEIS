# PROD R1 Secure Headers PASS1/PASS2

Date: 2026-05-18
Roadmap item: `A.6 HSTS / CSP / secure headers`
Decision pack: `results/decisions/PROD-D3-SECURE-HEADERS_evidence_pack.json`
Status: `FROZEN_2X` for backend security headers middleware

## Scope

This freeze covers FastAPI response headers:

- `Strict-Transport-Security`
- `Content-Security-Policy`
- `X-Frame-Options`
- `X-Content-Type-Options`
- `Referrer-Policy`
- `Permissions-Policy`

`SecurityHeadersMiddleware` is added as the outermost FastAPI middleware so it can attach headers to normal route responses and middleware-generated denials.

## Files Changed

- `src/sylion-pipeline/sylion/api/security_headers.py`
- `src/sylion-pipeline/sylion/api/app.py`
- `src/sylion-pipeline/tests/api/test_security_headers.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\api\test_security_headers.py -q
3 passed, 6 warnings
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\api\test_security_headers.py -q
3 passed, 6 warnings
```

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-SECURE-HEADERS_evidence_pack.json
```

Expected rollback time: 10 minutes.
Data loss risk: `NONE`.
