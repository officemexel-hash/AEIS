# ADR-0009: Secure Cookie Flag Default True in Production

**Status:** Accepted
**Date:** 2026-04-19
**Author:** security-audit-council (v5.9.1 re-audit)

## Context

SYLION's session cookie was created with `Secure=False` as default in `app.py` (lines 484–485 and 639–640). Any deployment behind a TLS-terminating reverse proxy (nginx, Caddy, Traefik) would therefore transmit session cookies in plaintext if the operator forgot to set `SESSION_COOKIE_SECURE=1`. The finding (CSRF-01 / P2-1) was classified HIGH because the session cookie is the sole authentication token — its interception allows full account takeover without any other credential.

The `SameSite=Strict` flag was already set, which mitigates cross-site request forgery, but does not protect against network-level interception on non-TLS connections.

Options considered:
- **O1** — Keep `Secure=False` as default, rely on operator configuration (status quo — rejected)
- **O2** — Default `Secure=True`, allow override via `SESSION_COOKIE_SECURE=0` env var (chosen)
- **O3** — Detect TLS automatically from request scheme and set dynamically
- **O4** — Always `Secure=True` with no override

## Decision

Set `Secure=True` as the default for all session cookies in production. The value is read from the environment variable `SESSION_COOKIE_SECURE` (default `"1"`). Setting `SESSION_COOKIE_SECURE=0` disables the flag for local HTTP development.

```python
_SECURE_COOKIE = os.environ.get("SESSION_COOKIE_SECURE", "1") != "0"
```

All call sites in `app.py` that set `secure=` on `response.set_cookie(...)` are updated to use `_SECURE_COOKIE`.

## Consequences

### Positive
- Session cookies are protected from network interception on any TLS-terminated deployment without extra operator action.
- Aligns with OWASP Session Management Cheat Sheet (SC-1: always set `Secure` in production).

### Negative
- Local HTTP development (`http://localhost:8421`) requires explicit `SESSION_COOKIE_SECURE=0` in the environment, or the browser will refuse to send the cookie. This is a non-obvious friction point for new developers.

### Neutral
- No change to cookie lifetime, `SameSite`, or `HttpOnly` settings.

## Alternatives Considered

- **O3 (dynamic detection)**: The application cannot reliably detect TLS when behind a reverse proxy; the `X-Forwarded-Proto` header can be spoofed. Explicit env config is safer.
- **O4 (no override)**: Would break local development completely; rejected in favour of opt-out.

## References

- `dashboard/app.py` — `_SECURE_COOKIE`, `response.set_cookie()`
- OWASP Session Management Cheat Sheet — SC-1
- Finding CSRF-01 in `FINDINGS_MATRIX_v591.md`
