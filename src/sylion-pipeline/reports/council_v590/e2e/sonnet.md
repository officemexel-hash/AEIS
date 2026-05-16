# Sonnet — Edge Cases E2E Report
## SYLION v5.9.0 Smoke Tests · Model Area: Edge Cases / Security / Auth Failures

**Date:** 2025-07-14  
**File:** `tests/test_api_smoke_v590.py` · `TestSonnetEdgeCases`  
**Tests:** 10  **Passed:** 10  **Failed:** 0

---

## Test Summary

| # | Test ID | Description | Result | HTTP Status |
|---|---------|-------------|--------|-------------|
| 11 | `test_11_setup_rejects_second_call` | POST /api/auth/setup (after setup complete) → 400 | ✅ PASS | 400 |
| 12 | `test_12_login_wrong_password` | POST /api/auth/login wrong password → 401 | ✅ PASS | 401 |
| 13 | `test_13_login_nonexistent_user` | POST /api/auth/login unknown user → 401 | ✅ PASS | 401 |
| 14 | `test_14_dashboard_without_auth` | GET /api/dashboard (no token, no cookie) → 401/403 | ✅ PASS | 401 |
| 15 | `test_15_dashboard_with_invalid_token` | GET /api/dashboard (garbage token) → 401/403 | ✅ PASS | 401 |
| 16 | `test_16_auth_me_without_token` | GET /api/auth/me (no auth) → authenticated=False | ✅ PASS | 200 |
| 17 | `test_17_five_failed_logins` | 5 consecutive bad-password attempts → each 401 (or 429) | ✅ PASS | 401×5 |
| 18 | `test_18_setup_with_empty_token` | POST /api/auth/setup empty token → 400/403/422 | ✅ PASS | 400 |
| 19 | `test_19_login_missing_fields` | POST /api/auth/login missing password → 422 | ✅ PASS | 422 |
| 20 | `test_20_logout_clears_session` | Logout then dashboard with old token → 401/403 | ✅ PASS | 401 |

---

## Security Observations

### Auth Behavior
- **Non-existent users and wrong passwords return identical 401** — no user-enumeration information leakage (correct).
- **Setup endpoint rejects replay after first use** (400) and rejects empty tokens (400). One-time-token pattern is correctly enforced.
- **5 consecutive failed logins** all returned `401` — no rate-limiting (429) is currently implemented. This is a **security gap**: brute-force protection is not present in v5.9.0.

### Session Management
- **Logout correctly invalidates the session token.** Subsequent requests with the old token return 401.
- **TestClient cookie isolation required:** The FastAPI `TestClient` shares a cookie jar across test instances, so unauthenticated tests (14, 16) require a dedicated `_no_cookie_client` instance with `cookies={}` to prevent cookie bleed-over from the happy-path setup. This is a test-harness consideration, not a bug.
- **`/api/auth/me` returns `{"authenticated": False}` (not a 401/403)** when no session exists — this is valid behavior but differs from `/api/dashboard` which returns 401. Consumers should handle both patterns.

### Rate Limit Gap (Finding)
```
FINDING: No HTTP 429 responses observed across 5 consecutive failed login attempts.
/api/auth/login does not implement rate-limiting in v5.9.0.
Recommendation: Add per-IP or per-username exponential backoff or lockout.
```

---

## Covered Endpoints (Edge Cases)

| Endpoint | Method | Edge Tested | Status |
|----------|--------|-------------|--------|
| `/api/auth/setup` | POST | Replay, empty token | ✅ Secure |
| `/api/auth/login` | POST | Wrong password, missing field, 5× fail | ✅ Correct (no rate-limit) |
| `/api/auth/logout` | POST | Session invalidation | ✅ Working |
| `/api/dashboard` | GET | No auth, invalid token | ✅ Returns 401 |
| `/api/auth/me` | GET | No auth | ✅ Returns unauthenticated |
