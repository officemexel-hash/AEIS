---
name: code-bloat-detector
description: >
  Detects code bloat in SYLION modules and files. Measures lines of code,
  cyclomatic complexity, unused exports, and code duplication. Warns above
  500 LoC per module and blocks above 1000 LoC.
---

# Code Bloat Detector

## When to Use

- Before committing new code to detect growing bloat early.
- As part of the G-EFF gate check.
- During refactoring to verify that complexity is decreasing.
- When onboarding a legacy file into the SYLION system.
- On a scheduled basis to track bloat trends across the codebase.

## Thresholds

| Metric               | Warn Threshold   | Block Threshold  |
|----------------------|------------------|------------------|
| Lines of Code (LoC)  | > 500 per module | > 1000 per module|
| Cyclomatic Complexity| > 15 per function| > 25 per function|
| Unused Exports       | > 5 per module   | > 15 per module  |
| Duplication Ratio    | > 5%             | > 15%            |
| File Count           | > 20 per module  | > 40 per module  |

## Inputs

| Name        | Type   | Required | Description                                           |
|-------------|--------|----------|-------------------------------------------------------|
| path        | string | Yes      | File or directory path to analyze                     |

## Outputs

| Name        | Type   | Description                                                        |
|-------------|--------|--------------------------------------------------------------------|
| bloat_report| object | Detailed bloat report with metrics, findings, and verdict          |

### Report Structure

```json
{
  "target": "src/sylion-pipeline/roast_engine.py",
  "timestamp": "2026-04-21T10:00:00Z",
  "summary": {
    "loc": 423,
    "effective_loc": 380,
    "cyclomatic_complexity_avg": 8.5,
    "cyclomatic_complexity_max": 22,
    "unused_exports": 3,
    "duplication_ratio_pct": 4.1,
    "file_count": 1
  },
  "findings": [
    {
      "severity": "WARN",
      "metric": "cyclomatic_complexity_max",
      "value": 22,
      "threshold": 15,
      "location": "roast_engine.py:calculate_blend_weights()",
      "message": "Function exceeds cyclomatic complexity warn threshold"
    }
  ],
  "verdict": "PASS",
  "recommendations": [
    "Extract weight calculation logic from calculate_blend_weights() into helper functions"
  ]
}
```

## Execution Steps

1. **Resolve target** -- If `path` is a file, analyze that file. If a directory, analyze all source files within recursively.
2. **Count LoC** -- Count total lines, then effective lines (excluding blank lines, comments, and docstrings). Report both.
3. **Compute complexity** -- Calculate cyclomatic complexity for each function/method. Track average and maximum.
4. **Detect unused exports** -- Parse exports (Python: public functions/classes; TypeScript: exported members). Cross-reference with imports across the codebase. Flag exports with zero consumers.
5. **Measure duplication** -- Use AST-based comparison to detect duplicated code blocks of 6+ lines. Report duplication as a percentage of total code.
6. **Evaluate thresholds** -- Compare each metric against warn and block thresholds.
7. **Generate findings** -- For each threshold breach, create a finding with severity (WARN or BLOCK), location, and specific message.
8. **Determine verdict** -- If any metric exceeds block threshold, verdict is BLOCK. If any exceeds warn threshold, verdict is WARN. Otherwise PASS.
9. **Formulate recommendations** -- For each finding, suggest a concrete remediation (extract function, delete dead code, consolidate duplicates).
10. **Write report** -- Persist to `results/bloat/{target_hash}_{timestamp}.json`.
11. **Return output** -- Emit the full bloat report.

## Safety Rules

- The detector is read-only and must never modify source files.
- A BLOCK verdict should prevent merge in CI but must not delete or alter code.
- LoC counts exclude generated files (e.g., `*.pb.ts`, `*.generated.ts`).
- Duplication detection must handle renamed variables and whitespace differences.
- Unused export detection must account for dynamic imports and reflection-based usage with a conservative flag.

## Properties

- **parallel-safe**: true -- Multiple paths can be analyzed concurrently without interference.
- **idempotent**: true -- Analyzing the same unchanged code produces the same report.
