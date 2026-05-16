# ADR-0018: Fact Checker Default Model ID Changed to claude-sonnet-4-6

**Status:** Accepted
**Date:** 2026-04-19
**Author:** code-auditor-debugger (v5.9.1 re-audit)

## Context

Finding FIND-1 (P0-2 — CRITICAL) identified that `fact_checker.py` (lines 159 and 172) and `config.py` (lines 130 and 161) hardcoded `claude-sonnet-4-5-20250929` as the default fact-checker model ID. Smoke testing against the Anthropic API confirmed:

```
InvalidRequestError: model 'claude-sonnet-4-5-20250929' does not exist or you do not have access to it.
```

Every fact-checking call returned `status: ERROR`, rendering SYLION's anti-hallucination layer completely non-functional. This was classified CRITICAL because it is a runtime regression that silently degrades the core pipeline output quality with no visible failure to the user (the pipeline continued to run, but fact-checking was skipped on every claim).

Root cause: the model ID used the date-specific snapshot format (`-20250929`) which was deprecated and removed from the Anthropic API between v5.9.0 development and release.

Options considered:
- **M1** — Hardcode the new model ID `anthropic/claude-sonnet-4-6` (chosen, with env override)
- **M2** — Remove the default; require explicit `FACT_CHECKER_MODEL_ID` env var
- **M3** — Add a startup probe that validates the model ID against the Anthropic models list
- **M4** — Fall back to a local Ollama model when the API model fails

## Decision

Update the default model ID to `anthropic/claude-sonnet-4-6` in both `config.py` and `fact_checker.py`. The value is overridable via the `FACT_CHECKER_MODEL_ID` environment variable, which takes precedence over the compiled default.

```python
FACT_CHECKER_MODEL_ID = os.environ.get(
    "FACT_CHECKER_MODEL_ID", "anthropic/claude-sonnet-4-6"
)
```

A startup warning is logged if `FACT_CHECKER_MODEL_ID` contains a date-specific snapshot suffix (regex `r'-\d{8}$'`) to alert operators to potential future deprecation.

## Consequences

### Positive
- Fact-checking is restored to functional status immediately after upgrade. All anti-hallucination pipeline stages return valid results.
- The env override allows operators to pin to a specific model snapshot without code changes.

### Negative
- `anthropic/claude-sonnet-4-6` is a floating alias that Anthropic may redirect to a newer model version at any time, which could introduce subtle behavioural differences in fact-checking outputs. Operators who require exact reproducibility should pin `FACT_CHECKER_MODEL_ID` to a versioned snapshot.

### Neutral
- The startup warning for date-suffixed model IDs is advisory only; it does not block startup.

## Alternatives Considered

- **M2 (no default)**: Would require every operator to set an env var before first boot — unacceptable for a pipeline that should work out-of-the-box.
- **M3 (startup probe)**: Adds an Anthropic API call at boot time, increasing startup latency and failing in offline/airgap scenarios. Deferred to v5.10.
- **M4 (local fallback)**: Ollama models are not validated against the same claim-checking prompts; fallback could silently degrade quality. Rejected.

## References

- `fact_checker.py` — lines 159, 172; `FACT_CHECKER_MODEL_ID`
- `config.py` — lines 130, 161
- Anthropic API changelog — `claude-sonnet-4-5` snapshot deprecation
- Finding FIND-1 in `FINDINGS_MATRIX_v591.md`
