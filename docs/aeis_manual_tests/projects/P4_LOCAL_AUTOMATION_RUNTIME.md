# P4 Local Automation Runtime

Status: restart pass after Stop-Fix-Restart repairs

## Goal

Create a local automation runtime with workers, task queue, retry, max parallel, logs, traces, and status reporting.

## Complexity Profile

- Complexity: high
- Resource profiles to compare: `cheap_slow`, `balanced`, `fast_expensive`
- Expected scope: workers, runtime config, observability, guards, Test Center

## Required AEIS Checks

1. Idea creation and runtime domain classification.
2. Module, worker, environment, and skill proposals.
3. Resource profile comparison.
4. Max parallel change.
5. Environment count change.
6. Planned VPS value may be tested and reset, without deploy.
7. Local worker start/stop if available.
8. Observability logs/metrics/traces.
9. Guard tests.
10. Product artifact test.
11. Test Center execution.

## Product Test

The generated local runtime artifact must show tasks, statuses, retry behavior or validation, and runtime/log evidence.

## Run Log

| Run | Project ID | Result | Evidence |
|---|---|---|---|
| T4 | `proj_c4ab8c81c556` | FAIL | Classified as `internal_app/crm` with `$200` reserve instead of `automation_runtime`. Stop-Fix-Restart triggered P4-F033. |
| T4R | `proj_f3e2a536e48c` | PASS | Dashboard clicked `/project-start`, `/council-to-ksiega`, `/planning`, `/execution-start`; project closed with execution 10/10. |

## Restart Evidence

- Classification: PASS, `internal_app/automation_runtime`, D4, resource reserve `$500`.
- Council/Księga: PASS, 6/6 phases, 91% consensus, 0 blockers.
- Resource profiles: PASS, dashboard switches worker count/cost/time from 1 worker `$150`/8.5 weeks through burst/max profiles to Burst Mode 60 worker option; final selected profile `Solo balanced`.
- Skills: PASS, 8 patterns; project skills created for local worker registry, task queue/retry, environment count, logs/traces/status; existing skills assigned for max parallel guard and Test Center checks.
- Planning: PASS after P4-F034 repair; P26-P31 show 6/6 accepted, 19 model rows, 8 layers, 150/150 AC coverage, dry-run confidence 88%.
- Runtime config guard: PASS after P4-F035 repair; attempted `local + VPS`, 2 VPS workers, 50 EUR cap and paid VPS checkbox were reset to `local-only`, `vps_workers=0`, cap `0`, `external_runtime_request_blocked_local_only`.
- Execution: PASS, P32-P41 show 10/10 accepted, 4 local workers, 3 local environments, 100% completion, cost `$0`.
- Guards: PASS, coherence/cost/provenance/quality/security all passed in execution dashboard.
- Product artifact scan: PASS, 230 files; no KSeF/Stripe/payment/invoice scope. `hetzner` occurrences are blocking evidence only: `hetzner_provisioned=false` and fresh confirmation required.
- Generated product test: PASS, backend `test_app.py` = `1 passed`.
