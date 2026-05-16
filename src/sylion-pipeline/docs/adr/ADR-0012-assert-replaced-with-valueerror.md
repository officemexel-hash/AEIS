# ADR-0012: assert Replaced with ValueError in Ollama Whitelist

**Status:** Accepted
**Date:** 2026-04-19
**Author:** security-audit-council + pr-reviewer-council (v5.9.1 re-audit)

## Context

Finding REG-1 (P1-1) identified that the Ollama model whitelist check introduced in FIX-10 (`app.py` lines 5787–5791 and 5910–5914) used Python's `assert` statement:

```python
assert all(m in ALLOWED_OLLAMA_MODELS for m in requested_models), \
    "Unauthorized model requested"
```

Python's `assert` statements are silently removed when the interpreter is started with the `-O` (optimise) or `-OO` flag, or when the `PYTHONOPTIMIZE=1` environment variable is set. Any deployment that enables Python optimisation (common in Docker images and systemd unit files for performance) would therefore bypass the entire whitelist — the security guard would disappear at runtime without any warning.

This is classified HIGH because it turns a security control into a no-op under plausible production conditions.

Options considered:
- **A1** — Replace `assert` with explicit `if not ...: raise ValueError(...)` (chosen)
- **A2** — Replace `assert` with `if not ...: raise HTTPException(400, ...)` directly
- **A3** — Add a startup-time check that asserts are enabled (fragile, `AssertionError` at boot)
- **A4** — Lint rule to forbid `assert` in security paths only

## Decision

Replace every security-relevant `assert` in `app.py` with an explicit conditional raise:

```python
if not all(m in ALLOWED_OLLAMA_MODELS for m in requested_models):
    raise ValueError(f"Unauthorized model requested: {requested_models!r}")
```

The `ValueError` propagates up to the FastAPI exception handler which returns HTTP 400. A blanket `ruff` rule `S101` (assert-used) is enabled in `pyproject.toml` to catch future regressions.

## Consequences

### Positive
- The whitelist check is enforced regardless of the `-O` flag or `PYTHONOPTIMIZE` setting.
- `ruff S101` lint rule provides automated regression prevention in future code review.

### Negative
- Minor boilerplate increase: each `assert` becomes 2–3 lines. Approximately 6 call sites were updated in `app.py`.

### Neutral
- Behaviour is semantically identical when Python optimisation is not enabled — `ValueError` produces the same HTTP 400 response as the previous `AssertionError`.

## Alternatives Considered

- **A2 (HTTPException directly)**: Slightly cleaner for HTTP context, but would couple the whitelist logic to the HTTP layer — less testable in unit tests. The current exception handler converts `ValueError` to 400 already.
- **A4 (lint only)**: Does not fix existing instances — rejected as standalone solution.

## References

- `dashboard/app.py` — Ollama whitelist checks (lines 5787–5791, 5910–5914)
- `pyproject.toml` — ruff rule S101
- Python docs: `assert` statement and `-O` flag
- Finding REG-1 in `FINDINGS_MATRIX_v591.md`
- `council/fix10_assert/REPORT.md` — proof-of-concept bypass
