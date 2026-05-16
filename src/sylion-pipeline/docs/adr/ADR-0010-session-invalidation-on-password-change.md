# ADR-0010: Session Invalidation on Password Change

**Status:** Accepted
**Date:** 2026-04-19
**Author:** security-audit-council (v5.9.1 re-audit)

## Context

Finding MEDIUM-001 (P1-3) identified that `PUT /api/users/{id}` updated the user's password hash in the `users` table but did not invalidate any existing sessions in the `sessions` table. A compromised or stolen session token therefore remained valid for up to 24 hours after the user changed their password — a classic "pass-the-cookie" attack window.

This is contrary to OWASP A07:2021 (Identification and Authentication Failures) which states that all active sessions must be terminated upon credential change.

Options considered:
- **S1** — Delete only the current session on password change (partial fix)
- **S2** — Delete all sessions for the user on password change (chosen)
- **S3** — Rotate session token in-place (keep session alive but regenerate token)
- **S4** — Add a `password_changed_at` column and validate it on every request

## Decision

On every successful password-change in `PUT /api/users/{id}`, execute:
```sql
DELETE FROM sessions WHERE user_id = ?
```
before committing the new password hash. Additionally, a new endpoint `POST /api/auth/logout-all` is added for explicit operator use, performing the same DELETE for the authenticated user.

The current request's session is also invalidated, requiring the user to re-authenticate immediately after the password change.

## Consequences

### Positive
- Eliminates the 24-hour attack window after a password change — aligns with OWASP A07:2021.
- Provides operators an explicit `logout-all` capability for incident response (e.g., suspected account compromise).

### Negative
- The user is logged out of all active browser sessions immediately after changing their password, including their current session. This may surprise users who expect to remain logged in on their primary device after a password change.

### Neutral
- No schema change is required; the `sessions` table already supports multi-row deletion by `user_id`.

## Alternatives Considered

- **S3 (token rotation)**: Keeps the user logged in on the device where the password was changed. However, this does not invalidate attacker sessions that hold the old token — rejected.
- **S4 (`password_changed_at` validation)**: More complex, requires a join on every authenticated request — deferred to v5.10 if per-device session management is desired.

## References

- `dashboard/app.py` — `PUT /api/users/{id}`, `POST /api/auth/logout-all`
- `dashboard/db.py` — `sessions` table
- OWASP A07:2021 Identification and Authentication Failures
- Finding MEDIUM-001 in `FINDINGS_MATRIX_v591.md`
