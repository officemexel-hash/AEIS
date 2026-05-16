# AEIS Self-Test Plan

Status: executed 2026-05-08 for `proj_b9c142b06eb4`

## Purpose

After manual tests, AEIS must generate and execute its own test plan against AEIS and its generated products.

## Required Self-Test Flow

1. Create Source of Truth for the test scope.
2. Create Masterplan for the test execution.
3. Human Gate approves scope.
4. Council reviews the plan.
5. AEIS Test Center executes tests.
6. Guards block release on failures.
7. AEIS generates its own report.
8. Manual report and AEIS report are compared.

## AEIS Test Center Surfaces

| Surface | Required Check | Status |
|---|---|---|
| `/test-center` | Entry renders and links to test tools | PASS |
| `/test-center/catalog` | Test catalog loads real tests | PASS - T0-T19 clicked PASS for `proj_b9c142b06eb4`; all project-scoped runs are attached to approved charter `tc_03b0f3a6a1ad`. |
| `/test-center/dashboard` | Results dashboard shows project-linked results | PASS - fixed project filter; dashboard shows 1 approved charter, 0 P0/P1, release gate `production_ready`, blockers 0. |
| `/test-center/simulation` | Can run or represent simulation tests | PASS - fixed executable dashboard action; created L0-L4 branch `simb_37d564c2e14b` with one evidence record. |
| `/test-center/release-gate` | Blocks release on failed tests | PASS - created/approved Test Charter, then completed rehearsal, rollback, Council D4/D5 + sentinels and final sign; status `production_ready`. |
| `/test-center/auto-repair` | Does not fake repair success | PASS/PARTIAL - LoopGuard creates real findings, repair attempts, LoopReport and HumanGate escalation. Global page still shows historical unrelated open findings, so project filtering remains backlog. |
| `/test-center/no-mock-scan` | Detects mock/stub/fallback markers | PASS - 445 files scanned, 3 allowed non-blocking mentions, 0 blockers. |
| `/test-center/truth-alignment` | Checks product against Source of Truth | PASS - fixed project-scoped matrix; 14/14 aligned, 0 drift for `proj_b9c142b06eb4`. |
| `/test-center/human-lab` | Supports human verification evidence | PASS - 15/15 canonical personas and 50/50 scenarios render from backend. |

## Comparison Criteria

| Area | Manual Report | AEIS Self-Test Report | Match Status |
|---|---|---|---|
| Core flow | P1-P5 manual simulations completed | Release Gate `production_ready`; W14 catalog T0-T19 PASS | MATCH |
| Products | 5 generated products tested; P5 product multi-domain verified | T14 real-example PASS and truth-alignment 14/14 | MATCH |
| Funding | P2/P5 funding domain tested manually | Truth feature `funding_assistant` aligned | MATCH |
| Guards | External/VPS/no-mock/release gates manually checked | No-mock PASS, release gate PASS, simulation L4 guarded | MATCH |
| Skills | P5 skill auto-synthesis verified manually | Truth feature `skill_auto-synthesis` aligned | MATCH |
| Memory | P5 memory reuse evidence verified manually | Truth feature `memory_reuse_evidence` aligned | MATCH |
| Test Center | Manual W14 dashboard clicks executed | Catalog/dashboard/simulation/release/truth/no-mock/human-lab live | MATCH |
| Open blockers | Terminal observability is partial; global auto-repair history is noisy | Not release-blocking for P5; tracked as follow-up | PARTIAL |

## Repairs Made During W14 Self-Test

- `test_center_routes.py`: project-start `proj_*` projects now hydrate Release Gate facts from AEIS audit chain, artifact path and approvals.
- `test_center_routes.py`: `catalog/run` now attaches project-scoped runs to the approved Test Charter when present.
- `test_center_routes.py`: truth alignment now supports `project_id` and builds a real 7-layer matrix from project evidence and W14 runs.
- `test_center_routes.py`: simulation now has a dashboard-triggered L0-L4 run endpoint.
- Test Center frontend: dashboard, truth-alignment and simulation gained project-aware controls.
- Terminal stream/UI: event `extra` metadata now preserves safe project/role/agent/environment/council/phase fields and renders them as badges.
