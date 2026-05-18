# PROD R6 Global Terminal Policy PASS1/PASS2

Date: 2026-05-18
Roadmap item: `D.4 Disaster recovery/global ops governance` / `PROD-P2-003 Global terminal policy`
Decision pack: `results/decisions/PROD-D4-GLOBAL-TERMINAL-POLICY_evidence_pack.json`
Status: `FROZEN_2X` for global command metadata, D4+ Human Gate, batch tickets and isolated replay

## Scope

This freeze covers:

- New `sylion.aeis_v2.terminal.global_policy.GlobalTerminalPolicy`.
- Global mutating commands detected by W18 terminal routing:
  - `restart system`;
  - `rebuild system`;
  - `policy update ...`.
- Required metadata for every global mutating command:
  - `actor` or `operator_id`;
  - `environment_id`;
  - `risk_class`;
  - `rollback_hint`.
- Risk floor enforcement:
  - restart/rebuild/policy update cannot be downgraded below their default D4 floor.
- D4+ Human Gate enforcement:
  - missing approval creates canonical `governance_tickets` entries with `origin=global`;
  - multi-project global commands create one ticket per affected project;
  - approved global ticket must match action, environment and risk class before execution is accepted.
- Evidence Spine artifact per policy decision:
  - source `terminal.global_policy`;
  - artifact type `global_terminal_command`;
  - replay scope `isolated`.
- Isolated replay read-side:
  - `GET /api/v1/terminal/global/commands`;
  - `GET /api/v1/terminal/global/commands/{command_id}`;
  - `GET /api/v1/terminal/global/replay/{command_id}?environment_id=...`.

## Files Changed

- `src/sylion-pipeline/sylion/aeis_v2/terminal/global_policy.py`
- `src/sylion-pipeline/sylion/aeis_v2/terminal/command_router.py`
- `src/sylion-pipeline/sylion/api/terminal_routes.py`
- `src/sylion-pipeline/tests/aeis_v2/test_global_terminal_policy.py`

## Verification PASS1

```text
python -m compileall src\sylion-pipeline\sylion\aeis_v2\terminal\global_policy.py src\sylion-pipeline\sylion\aeis_v2\terminal\command_router.py src\sylion-pipeline\sylion\api\terminal_routes.py
PASS

python -m pytest src\sylion-pipeline\tests\aeis_v2\test_global_terminal_policy.py src\sylion-pipeline\tests\aeis_v2\test_terminal.py src\sylion-pipeline\tests\aeis_v2\test_terminal_replay.py -q
75 passed, 6 warnings

python -m pytest src\sylion-pipeline\tests\aeis_v2\test_terminal_intervention.py -q
13 passed, 6 warnings

python -m pytest src\sylion-pipeline\tests\test_surface_command_bus.py -q
40 passed

python -m pytest src\sylion-pipeline\tests\aeis_v2\test_rbac_matrix.py -q
84 passed, 47 skipped, 6 warnings

run_no_mock_scan(limit=200)
PASS 451 0

git diff --check
PASS
```

## Verification PASS2

```text
python -m compileall -q src\sylion-pipeline\sylion\aeis_v2\terminal\global_policy.py src\sylion-pipeline\sylion\aeis_v2\terminal\command_router.py src\sylion-pipeline\sylion\api\terminal_routes.py
PASS

python -m pytest src\sylion-pipeline\tests\aeis_v2\test_global_terminal_policy.py src\sylion-pipeline\tests\aeis_v2\test_terminal.py src\sylion-pipeline\tests\aeis_v2\test_terminal_replay.py src\sylion-pipeline\tests\aeis_v2\test_terminal_intervention.py src\sylion-pipeline\tests\test_surface_command_bus.py -q
128 passed, 6 warnings

run_no_mock_scan(limit=200)
PASS 451 0

git diff --check
PASS
```

Known warnings are historical deprecation warnings from legacy security/vault imports. The RBAC matrix also emits a Python finalization warning from `psycopg_pool` cleanup after the test process has already reported pass; it did not fail the test run.

## Boundary

This freeze proves the global terminal policy contract in the AEIS backend: metadata is mandatory, D4+ commands cannot bypass Human Gate, batch tickets are created per project, and replay reads only isolated command/environment records.

This does not execute real host restart, rebuild or policy mutation on live infrastructure. Those operations remain behind the deploy/DR operational runbooks and require real environment credentials.

AEIS must still remain `BLOCKED` until remaining production roadmap blockers are frozen twice.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D4-GLOBAL-TERMINAL-POLICY_evidence_pack.json
```

Expected rollback time: 15 minutes.
Data loss risk: `NONE`; the change adds terminal policy/evidence rows and governance tickets only.
