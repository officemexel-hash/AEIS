# W18 Transactional Bug Ledger

Data: 2026-05-13

| ID | Severity | Status | Finding | Evidence | Exit criteria |
|---|---:|---|---|---|---|
| W18-TRX-001 | P0 | RESOLVED_2X_PASS | Brak centralnego Command Routera i ownership dla komend | `../w18_router_repair/evidence/json/w18_router_dashboard_pass12_reconstructed_2026-05-13.json`; `../execution_start_router_repair/evidence/json/execution_start_dashboard_pass12_2026-05-13T22-23-31-684Z.json`; `src/sylion-pipeline/logs/v2/command_router_audit.jsonl` | Wszystkie naprawione powierzchnie W18 tworza `CommandIntent` z targetem, ownerem, risk i audit ref |
| W18-TRX-002 | P0 | OPEN | Pause/resume nie zatrzymuja realnego agenta | `terminal_routes.py` komentarz G2 step 1; `pause_pending_task` 409 | Pause/resume/cancel maja runtime ACK od aktywnego workera/agenta |
| W18-TRX-003 | P1 | RESOLVED_2X_PASS | Trzy kanaly komend bez jednego SoT | Global `/terminal`, project W18 terminal i execution-start wpisuja `CommandIntent`/`CommandRoute`/`CommandExecution`; zob. `FULL-AUD-005` | Jeden backendowy command ledger dla global/project/dashboard actions |
| W18-TRX-004 | P1 | PARTIAL_TESTED | `implemented=yes` nie znaczy realnie wykonane | `/skip` i `/focus` sa naprawione w `tests/aeis_v2/test_terminal.py`; katalog nadal wymaga pelnej klasyfikacji capability | Katalog komend rozroznia `implemented`, `stub`, `read_only`, `mutating`, `requires_gate` |
| W18-TRX-005 | P1 | PARTIAL_2X_PASS | Brak formalnego routingu przy wielu srodowiskach | `CommandIntent` niesie `environment_id`, `agent_id`, `worker_id`, a route ma owner/phase/risk; brak jeszcze lease per aktywny runtime | Route policy + lease per environment/worker/model |
| W18-TRX-006 | P2 | RESOLVED_TESTED | Brak `/request checkpoint` z planu A7 | `tests/aeis_v2/test_terminal.py`; API probe `/api/v1/terminal/exec`; `command_route.target_action=request_checkpoint` | Checkpoint command tworzy audit event i widoczny replay marker |
| W18-TRX-007 | P1 | RESOLVED_2X_PASS | Execution-start Phase 33 nie miala kontrolowanego `/dispatch pause|resume|cancel` z ownerem i target scope | `../execution_dispatch_control/evidence/json/execution_dispatch_control_pass12_2026-05-14T09-58-40-542Z.json`; `../execution_dispatch_control/EXECUTION_DISPATCH_CONTROL_PASS12.md`; `src/sylion-pipeline/logs/v2/command_router_audit.jsonl` | Dashboard 2x wykonuje start/pause/resume/cancel; W18 route owner `execution_start.dispatch_control`; `pause/resume=D3`, `cancel=D4`; dispatch status i artifact zapisane |

## Freeze rule

Nie wolno zamrozic W18 po pojedynczym sukcesie UI. Kazdy wpis ma przejsc:

1. API test PASS.
2. Playwright dashboard test PASS.
3. Audit/replay evidence PASS.
4. Ten sam scenariusz powtorzony 2x.
5. Instrukcja obslugi i screenshot zaktualizowane.
