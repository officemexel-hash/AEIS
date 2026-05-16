# Execution-start W18 Router - PASS1/PASS2 freeze report

Data: 2026-05-13  
Zakres: `/execution-start` Phase 32/33, runtime configuration, W18 route ledger, worker evidence.  
Status: `2X_PASS` dla zakresu `execution-start W18 router / Phase 32-33`.

## Co zostalo naprawione

1. `execution.w18_commands` pozostaje lista UI, ale kazdy nowy wpis dostaje centralny kontrakt:
   - `command_intent`
   - `command_route`
   - `command_execution`
2. Execution-start zapisuje te same akcje do `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`.
3. `record_terminal_evidence(...)` pozwala trasom dashboardowym dopisac route evidence bez ponownego wykonywania domenowej akcji.
4. Phase 33 dopisuje teraz jawny W18 command entry dla startu wykonania.
5. Phase 33 zwraca i zapisuje worker evidence `live_verified_local`: worker logs, diff artifacts i test result JSON.

## Zmienione pliki

- `src/sylion-pipeline/sylion/aeis_v2/terminal/command_router.py`
- `src/sylion-pipeline/sylion/api/execution_start_routes.py`
- `src/sylion-pipeline/tests/test_planning_execution_routes.py`
- `docs/aeis_repair_v2/full_human_dashboard_audit/FULL_HUMAN_DASHBOARD_BUG_LEDGER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/BUG_LEDGER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/FREEZE_REGISTER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/AEIS_OPERATOR_MANUAL_LATEST.md`

## Testy automatyczne

Komenda:

```powershell
python -m pytest src/sylion-pipeline/tests/aeis_v2/test_terminal.py src/sylion-pipeline/tests/test_planning_execution_routes.py -q
```

Wynik po naprawie: `76 passed, 6 warnings`.  
Ten sam zestaw przeszedl ponownie po runtime dashboard PASS1/PASS2.

Frontend lint:

```powershell
npm run lint -- "src/components/execution-start/ExecutionStartDashboard.tsx" "src/app/(app)/projects/[projectId]/page.tsx"
```

Wynik: PASS.

## Runtime evidence

- Backend po restarcie: PID `40272`, `http://127.0.0.1:8010/health` OK.
- Frontend dashboard: `http://127.0.0.1:3001`.
- Evidence JSON: `docs/aeis_repair_v2/execution_start_router_repair/evidence/json/execution_start_dashboard_pass12_2026-05-13T22-23-31-684Z.json`.
- Screenshots: `docs/aeis_repair_v2/execution_start_router_repair/evidence/screenshots/`.
- Audit append-only: `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`.

## PASS1

Projekt: `project_941d83cdd5d9`.

| Dashboard action | W18 route action | Wynik |
|---|---|---|
| `Zapisz runtime` | `runtime_configuration` | PASS |
| `Zainicjuj budowe` | `initialize_build` | PASS |
| `Start wykonania` | `start_sequential_execution` | PASS |

Worker evidence:

- `status=live_verified_local`
- `run_id=wr_1778711023104`
- `workers_completed=2`
- `artifacts_written=10`
- `diffs_written=2`
- `logs_written=2`
- `tests_passed=2`
- `external_actions=false`
- `vps_used=false`

Browser evidence: `console=0`, `requestFailures=0`.

## PASS2

Projekt: `project_97bfd7670d3d`.

| Dashboard action | W18 route action | Wynik |
|---|---|---|
| `Zapisz runtime` | `runtime_configuration` | PASS |
| `Zainicjuj budowe` | `initialize_build` | PASS |
| `Start wykonania` | `start_sequential_execution` | PASS |

Worker evidence:

- `status=live_verified_local`
- `run_id=wr_1778711035018`
- `workers_completed=2`
- `artifacts_written=10`
- `diffs_written=2`
- `logs_written=2`
- `tests_passed=2`
- `external_actions=false`
- `vps_used=false`

Browser evidence: `console=0`, `requestFailures=0`.

## Zamrozony zakres

Mozna zamrozic:

- runtime configuration route evidence dla `/execution-start`;
- Phase 32 initialize-build route evidence;
- Phase 33 start-execution route evidence;
- centralny `command_router_audit.jsonl` dla powyzszych akcji;
- worker evidence generowane przez Phase 33.
- live smoke worker start/stop UI jest zamrozone osobno w `../execution_live_workers/EXECUTION_LIVE_WORKERS_PASS12.md`.

Nie wolno jeszcze zamrazac:

- calego execution dashboardu;
- dispatch/cancel;
- faz 34-41 jako pelnego E2E;
- produkcyjnego deploy.

## Reguly utrzymania

- `execution.w18_commands` nie moze byc jedynym ledgerem dla akcji operatorskich.
- Kazdy nowy wpis W18 musi miec `command_route.owner`, `target_action`, `phase`, `requires_human_gate`.
- D3+ w execution-start musi miec governance ticket ID albo jawnie opisany powod braku ticketu.
- Worker evidence po `Start wykonania` musi zawierac logs, diffs i test result JSON.
- Freeze wymaga dwoch przebiegow przez dashboard oraz zgodnego wpisu w `FREEZE_REGISTER.md`.
