# SYLION v5.9.0 — E2E Smoke Test Consolidated Report
## Council Run · e2e-playwright-v590

**Date:** 2025-07-14  
**Test file:** `SYLION_v590_work/sylion-pipeline/tests/test_api_smoke_v590.py`  
**Runtime:** pytest 8.3.4 + FastAPI TestClient (httpx transport)  
**Python:** 3.12.8 · Venv: `/tmp/sylion_venv`  
**Total runtime:** 1.45 s

---

## Overall Result

```
40 passed, 0 failed
```

| Model Area | Tests | Passed | Failed |
|------------|-------|--------|--------|
| Opus — Happy Path | 10 | 10 | 0 |
| Sonnet — Edge Cases | 10 | 10 | 0 |
| GPT-5.4 — Accessibility | 10 | 10 | 0 |
| Gemini — Shape Invariance | 10 | 10 | 0 |
| **TOTAL** | **40** | **40** | **0** |

---

## Endpoints Verified

| Endpoint | Method | Auth | Status |
|----------|--------|------|--------|
| `/api/health` | GET | No | ✅ 200, `{status: "ok", service: "sylion-dashboard"}` |
| `/api/version` | GET | No | ✅ 200, `api_version: "2.0.0"`, components dict |
| `/api/auth/status` | GET | No | ✅ 200, `needs_setup` / `setup_complete` flags |
| `/api/auth/setup` | POST | No (one-time) | ✅ 200 (first call); 400 (replay) |
| `/api/auth/login` | POST | No | ✅ 200 valid creds; 401 invalid; 422 missing fields |
| `/api/auth/logout` | POST | Session | ✅ 200, session deleted |
| `/api/auth/me` | GET | Session | ✅ 200 + user object when authed; unauthenticated=False when not |
| `/api/dashboard` | GET | Session | ✅ 200 + full M-06 JSON shape |

---

## M-06 Dashboard Schema — Full Invariant

```json
{
  "agents":     { "total": int, "active": int, "paused": int, "error": int },
  "human_gate": { "pending": int, "recent": list },
  "runs":       { "total": int, "active": int },
  "baselines":  { "total": int, "draft": int, "review": int },
  "prompts":    { "total": int, "active": int, "draft": int },
  "api_keys":   { "configured": int, "total": int },
  "recent_logs": list,
  "timestamp":  float
}
```

**Verdict: COMPATIBLE.** v5.9.0 M-06 optimization (15→5 DB queries) preserves byte-identical response shape vs v5.8.x.

---

## Key Findings

### Security
| Finding | Severity | Status |
|---------|----------|--------|
| No rate-limiting on `/api/auth/login` | Medium | ⚠️ Open — 5× failed logins all return 401 (no 429) |
| Setup token is one-time and deleted after use | — | ✅ Secure |
| Username/password errors are non-differentiating | — | ✅ No user enumeration |
| Session invalidation on logout works | — | ✅ Verified |
| Invalid token returns 401 (not 500) | — | ✅ Correct |

### Accessibility (Static Analysis)
| Finding | Severity | Status |
|---------|----------|--------|
| `lang=` attribute present in `index.html` | — | ✅ WCAG 3.1.1 compliant |
| `<meta name="viewport">` present | — | ✅ Mobile-ready |
| `<title>` tag present | — | ✅ WCAG 2.4.2 compliant |
| 119 inline `onclick=` handlers | Medium | ⚠️ WCAG 2.1 SC 4.1.2 concern |
| All API responses are JSON + UTF-8 | — | ✅ No encoding issues |

### Performance / Reliability
| Finding | Status |
|---------|--------|
| `/api/health` idempotent (3 calls, same shape) | ✅ |
| `/api/dashboard` responds with complete data structure | ✅ |
| Test suite completes in 1.45 s (40 tests) | ✅ |

---

## TestClient Architecture Decision

Tests use FastAPI `TestClient` (ASGI in-process transport) rather than:
- **Playwright** — requires `npm install playwright` + browser binaries (heavyweight, not available in this sandbox)
- **Live uvicorn + httpx** — would require port management and async setup

**Important caveat discovered:** FastAPI `TestClient` shares a cookie jar across requests within the same instance. Unauthenticated edge-case tests (test_14, test_16) required a separate `_no_cookie_client = TestClient(..., cookies={})` to avoid inheriting session cookies set during happy-path tests. This is a test-harness consideration only — not a bug in the application.

---

## Individual Model Reports

- [opus.md](./opus.md) — Happy path: full auth flow, 7 endpoints verified
- [sonnet.md](./sonnet.md) — Edge cases: 401/403, session expiry, replay attacks, rate-limit finding
- [gpt54.md](./gpt54.md) — Accessibility: static file structure, HTML a11y attributes, onclick audit
- [gemini.md](./gemini.md) — Shape invariance: M-06 compat, cross-endpoint schema verification

---

## Pytest Command

```bash
cd /home/user/workspace/SYLION_v590_work/sylion-pipeline
PYTHONPATH=dashboard /tmp/sylion_venv/bin/python -m pytest tests/test_api_smoke_v590.py -v --tb=short
```

Output: `40 passed in 1.45s`
