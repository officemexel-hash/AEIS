---
name: gate-check-runner
description: >
  Runs entry and exit gates for SYLION module lifecycle stages. Each gate
  enforces a checklist of quality, security, and performance criteria that
  must pass before a module can transition to the next stage.
---

# Gate Check Runner

## When to Use

- Before promoting a module from one lifecycle stage to the next (e.g., DEV -> STAGING).
- During CI/CD pipeline execution at stage boundaries.
- When onboarding a new module into the SYLION system.
- On-demand verification that an existing module still meets gate criteria.

## Supported Gates

| Gate    | Name             | Focus Area                                          |
|---------|------------------|-----------------------------------------------------|
| G-ARCH  | Architecture     | Module boundaries, dependency direction, no cycles  |
| G-TEST  | Testing          | Unit coverage >= 80%, integration tests pass        |
| G-SEC   | Security         | No hardcoded secrets, input validation, auth checks |
| G-EFF   | Efficiency       | Meets bloat and performance budgets                 |
| G-PERF  | Performance      | Latency within SLA, throughput targets met          |
| G-MEM   | Memory           | No leaks, heap within limits, GC pressure acceptable|
| G-COST  | Cost             | Token usage, API call count within budget           |
| G-READY | Release Ready    | All other gates pass, docs updated, changelog ready |

## Inputs

| Name         | Type   | Required | Description                                           |
|--------------|--------|----------|-------------------------------------------------------|
| module_id    | string | Yes      | The SYLION module identifier (e.g., `m1_roast`)       |
| gate_type    | string | Yes      | One of: G-ARCH, G-TEST, G-SEC, G-EFF, G-PERF, G-MEM, G-COST, G-READY |
| target_stage | string | Yes      | The lifecycle stage being transitioned to             |

## Outputs

| Name        | Type   | Description                                                  |
|-------------|--------|--------------------------------------------------------------|
| gate_result | string | "PASS" or "FAIL"                                             |
| checklist   | list   | Checklist items with pass/fail status and details per item   |

## Execution Steps

1. **Validate inputs** -- Confirm `module_id` exists in the module registry, `gate_type` is a known gate, `target_stage` is a valid lifecycle stage.
2. **Load gate definition** -- Retrieve the checklist criteria for the specified `gate_type`.
3. **Run checks** -- Execute each checklist item against the module's current state:
   - G-ARCH: Scan imports, verify dependency direction, check for circular references.
   - G-TEST: Run test suite, collect coverage report, verify threshold.
   - G-SEC: Scan for secrets, check input sanitization, verify auth middleware.
   - G-EFF: Measure LoC, cyclomatic complexity, compare against budgets.
   - G-PERF: Run benchmarks, measure latency and throughput.
   - G-MEM: Profile memory usage, check for leak patterns.
   - G-COST: Analyze token usage logs, count API invocations.
   - G-READY: Aggregate results from all other gates.
4. **Compile checklist** -- For each item, record `{"item": "...", "status": "PASS|FAIL", "detail": "..."}`.
5. **Determine result** -- If any mandatory checklist item fails, result is FAIL. All items must pass for PASS.
6. **Write report** -- Persist the gate result to `results/gates/{module_id}_{gate_type}.json`.
7. **Return output** -- Emit `gate_result` and `checklist`.

## Safety Rules

- A module must never skip a required gate for its target stage.
- G-READY requires all other gates to have passed within the current release cycle.
- Gate results are immutable once written; re-running creates a new timestamped entry.
- FAIL results must include actionable remediation steps in the checklist details.
- Parallel gate runs on the same module are allowed but write to separate result files.

## Properties

- **parallel-safe**: true -- Multiple gates can run concurrently on different modules.
- **idempotent**: true -- Re-running the same gate with unchanged code produces the same result.
