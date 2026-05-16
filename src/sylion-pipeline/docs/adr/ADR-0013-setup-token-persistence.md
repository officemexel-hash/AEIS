# ADR-0013: Setup Token Persisted Until Setup Completes

**Status:** Accepted
**Date:** 2026-04-19
**Author:** deployment-council (v5.9.1 re-audit)

## Context

Finding TOK-1 (P2-8) identified that the one-time setup token used to create the initial admin account was regenerated on every application restart if setup had not yet been completed. This created a race condition for operators:

1. Application starts → setup token T1 printed to console.
2. Operator copies T1, navigates to `/setup`, is interrupted.
3. Application restarts (e.g., systemd watchdog, crash recovery).
4. New token T2 generated — T1 is now invalid.
5. Operator submits T1 → setup fails with 403.

In environments with frequent restarts during initial deployment (e.g., troubleshooting install issues), the operator must tail the log on every restart to retrieve a fresh token — a poor and error-prone experience.

Options considered:
- **T1** — Regenerate token on every restart (status quo — rejected)
- **T2** — Persist token in the database until `setup_completed = True` (chosen)
- **T3** — Write token to a well-known file (`SETUP_TOKEN.txt`) and reuse it
- **T4** — Remove token auth from setup entirely and rely on first-connection trust

## Decision

Store the setup token in the `config` table (`key='setup_token'`) on first generation. On subsequent startups, if `setup_completed` is `False`, read the existing token from the database and print it again rather than generating a new one. Once setup completes, the token row is deleted.

Token expiry is set to 48 hours from initial generation (stored as `setup_token_expires_at`). After expiry, a new token is generated and the 48-hour window resets.

## Consequences

### Positive
- Operators can restart the application during initial deployment without losing their setup token.
- The printed token is stable across restarts — copy-paste from any earlier log entry remains valid within 48 hours.

### Negative
- The setup token is now stored in the SQLite database in plaintext. On compromised-disk scenarios this is marginally worse than an in-memory-only token. For a local development pipeline this risk is accepted.

### Neutral
- `SETUP_TOKEN.txt` (T3) is also written as a convenience file alongside the database; this file is gitignored and is purely informational.

## Alternatives Considered

- **T4 (no token)**: First-connection trust is appropriate for container environments with network isolation, not for a LAN-accessible service. Rejected.
- **T3 only (file)**: File persistence is less reliable than DB persistence (file may be on a separate tmpfs or accidentally deleted).

## References

- `dashboard/db.py` — `config` table, `setup_token`, `setup_token_expires_at`
- `dashboard/app.py` — `/api/auth/setup` endpoint
- Finding TOK-1 in `FINDINGS_MATRIX_v591.md`
