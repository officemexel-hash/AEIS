---
name: efficiency-audit
description: >
  Audits SYLION code against four efficiency dimensions: bloat, performance,
  memory, and cost. Produces a scored report with actionable recommendations.
---

# Efficiency Audit

## When to Use

- After completing a feature or module implementation.
- As part of the G-EFF gate check before stage promotion.
- During code review to quantify efficiency concerns.
- Periodically as a health check on mature modules.
- When investigating performance regressions or cost overruns.

## Dimensions

| Dimension | Metrics                                  | Thresholds                          |
|-----------|------------------------------------------|-------------------------------------|
| Bloat     | Lines of code, cyclomatic complexity     | Warn >500 LoC/module, block >1000   |
| Perf      | Latency (p50/p95/p99), throughput (rps)  | p95 < 200ms, throughput > 100 rps   |
| Memory    | Peak RSS, heap size, GC pause frequency  | RSS < 512MB, GC pause < 50ms        |
| Cost      | Tokens consumed, API calls per operation | Tokens < 2K/call, API calls < 5/op  |

## Inputs

| Name        | Type   | Required | Description                                                 |
|-------------|--------|----------|-------------------------------------------------------------|
| module_id   | string | No*      | The SYLION module identifier to audit                       |
| file_path   | string | No*      | Path to a specific file or directory to audit               |

*One of `module_id` or `file_path` must be provided. If both are given, `module_id` takes precedence.

## Outputs

| Name     | Type   | Description                                                        |
|----------|--------|--------------------------------------------------------------------|
| report   | object | Efficiency report with scores per dimension and overall grade      |

### Report Structure

```json
{
  "target": "m1_roast",
  "timestamp": "2026-04-21T10:00:00Z",
  "dimensions": {
    "bloat": {
      "score": 85,
      "grade": "B",
      "metrics": {
        "loc": 423,
        "cyclomatic_complexity": 12,
        "duplication_pct": 3.2
      },
      "findings": ["..."]
    },
    "perf": { "score": 92, "grade": "A", "metrics": {}, "findings": [] },
    "memory": { "score": 78, "grade": "C", "metrics": {}, "findings": ["..."] },
    "cost": { "score": 90, "grade": "A", "metrics": {}, "findings": [] }
  },
  "overall_score": 86,
  "overall_grade": "B",
  "recommendations": ["..."]
}
```

## Execution Steps

1. **Resolve target** -- Determine audit scope from `module_id` or `file_path`. Collect all relevant source files.
2. **Bloat analysis** -- Count lines of code (excluding blanks and comments), compute cyclomatic complexity per function, detect code duplication using AST comparison.
3. **Performance analysis** -- If benchmarks exist, run them and collect latency/throughput metrics. If not, perform static analysis for known anti-patterns (N+1 queries, sync I/O in hot paths, unnecessary re-renders).
4. **Memory analysis** -- Scan for common leak patterns: unclosed connections, event listeners without cleanup, growing caches without eviction, large object retention. Estimate heap footprint from data structures.
5. **Cost analysis** -- For modules that call LLM APIs, estimate token usage per operation. Count external API invocations. Flag operations exceeding budget thresholds.
6. **Score each dimension** -- Map metrics to a 0-100 score based on defined thresholds. Assign letter grades: A (90-100), B (80-89), C (70-79), D (60-69), F (<60).
7. **Compute overall** -- Weighted average: bloat 25%, perf 30%, memory 25%, cost 20%.
8. **Generate recommendations** -- For each dimension below grade A, produce specific, actionable recommendations with file locations.
9. **Write report** -- Persist to `results/efficiency/{target}_{timestamp}.json`.
10. **Return output** -- Emit the full report object.

## Safety Rules

- Audits are read-only; they must never modify source code or configuration.
- Running benchmarks must use a separate test environment or dataset to avoid production impact.
- Cost estimates are approximations based on static analysis and historical data; they are not billing guarantees.
- Memory analysis flags potential issues but cannot guarantee the absence of leaks without runtime profiling.
- Parallel audits on different targets are safe; parallel audits on the same target may produce slightly different perf scores due to system load.

## Properties

- **parallel-safe**: true -- Different modules can be audited concurrently.
- **idempotent**: true -- Re-auditing unchanged code produces the same bloat, memory, and cost scores. Perf scores may vary within a tolerance band.
