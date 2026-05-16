# ADR-0014: TOCTOU Fix in /api/auth/setup via threading.Lock and BEGIN IMMEDIATE

**Status:** Accepted
**Date:** 2026-04-19
**Author:** security-audit-council (v5.9.1 re-audit)

## Context

Finding C-01 (P1-4) identified a time-of-check/time-of-use (TOCTOU) race condition in the `/api/auth/setup` endpoint. The setup flow was:

1. Check if any admin user exists (`SELECT COUNT(*) FROM users WHERE role='admin'`).
2. Validate the provided setup token.
3. Delete the setup token.
4. Create the admin user.

Under concurrent load (5 simultaneous POST requests with the same valid token), steps 1–4 could interleave across threads: all 5 threads see zero admins at step 1, all 5 validate the same token, and all 5 proceed to create an admin account — resulting in 5 admin accounts from a single setup token. An attacker who can race the network (e.g., LAN or localhost with scripted requests) could create rogue admin accounts.

Options considered:
- **L1** — Application-level `threading.Lock` around the entire check-and-create block (chosen, combined with L2)
- **L2** — SQLite `BEGIN IMMEDIATE` transaction to serialise at the DB level (chosen, combined with L1)
- **L3** — Unique constraint on `role='admin'` (partial fix — does not prevent token reuse)
- **L4** — Rate limiting on `/api/auth/setup` to 1 request/second

## Decision

Apply both L1 and L2 as defence in depth:

- A module-level `_SETUP_LOCK = threading.Lock()` serialises setup requests within the same process.
- The setup DB transaction uses `BEGIN IMMEDIATE` to acquire a write lock before any reads, preventing concurrent SQLite writers even from separate processes sharing the database file.

The token deletion is moved to the **first step** inside the transaction (before admin user creation), so even if the `INSERT` fails, the token is consumed and cannot be retried without operator intervention.

## Consequences

### Positive
- Eliminates the TOCTOU race under both same-process threading and multi-process deployments.
- Token is consumed atomically with the setup attempt — no double-spend possible.

### Negative
- The `threading.Lock` adds serialisation to an already-rare endpoint (`/api/auth/setup` is called at most once in the application lifecycle). In pathological multi-process deployments where the lock cannot be shared across processes, the SQLite `BEGIN IMMEDIATE` is the sole guard. This is sufficient for the single-server deployment model but would not scale to a multi-process cluster behind a load balancer.

### Neutral
- Setup is a one-shot operation. The lock contention cost is irrelevant in normal operation.

## Alternatives Considered

- **L3 (unique constraint)**: Would prevent duplicate admin accounts but does not prevent the token from being used multiple times (if admin creation fails after token deletion). Included as an additional DB constraint but not sufficient alone.
- **L4 (rate limiting)**: Slows the attack but does not eliminate it — a determined attacker with < 1 req/s could still race. Rejected as sole fix.

## References

- `dashboard/app.py` — `/api/auth/setup`, `_SETUP_LOCK`
- `dashboard/db.py` — `BEGIN IMMEDIATE` transaction pattern
- Finding C-01 in `FINDINGS_MATRIX_v591.md`
- OWASP Race Condition / TOCTOU (CWE-362)
