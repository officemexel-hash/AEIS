# W18 Command Router Repair - PASS1/PASS2 freeze report

Data: 2026-05-13  
Zakres: projektowy terminal W18, Human Gate, freeze canon/masterplan i autoryzacja budowy.  
Status: `2X_PASS` dla zakresu `W18 project terminal freeze/build`.

## Co zostalo naprawione

1. Terminal W18 projektu nie wykonuje juz mutujacych komend jako lokalnej logiki frontendu.
2. `/api/v1/terminal/exec` przechodzi przez centralny kontrakt:
   - `CommandIntent`
   - `CommandRoute`
   - `CommandExecution`
3. Mutujace komendy projektu maja jawnego wlasciciela i trase:
   - `zamroz ksiege` -> `project_mode.round_meta.freeze_canon`, `D3`, `TWO_PHASE`, Human Gate
   - `zamroz masterplan` -> `project_mode.round_meta.freeze_masterplan`, `D4`, `TWO_PHASE`, Human Gate
   - `autoryzuj budowe` -> `project_mode.round_meta.authorize_build`, `D4`, `TWO_PHASE`, Human Gate
4. `bramka czlowieka` w terminalu projektu odczytuje stan ticketow dla konkretnego `project_id`.
5. `/request checkpoint` zostal dodany do katalogu komend W18 i do routera jako wpis audytu.
6. Reporty W18 preferuja jawny `ctx.project_id`, zeby terminal projektu nie raportowal innego aktywnego projektu.

## Zmienione pliki

- `src/sylion-pipeline/sylion/aeis_v2/terminal/command_router.py`
- `src/sylion-pipeline/sylion/api/terminal_routes.py`
- `src/sylion-pipeline/sylion/api/projects_freeze_routes.py`
- `src/sylion-pipeline/sylion/project_mode/round_meta_hooks.py`
- `src/sylion-pipeline/sylion/aeis_v2/terminal/commands.py`
- `src/sylion-frontend/src/app/(app)/projects/[projectId]/page.tsx`
- `src/sylion-pipeline/tests/aeis_v2/test_terminal.py`
- `src/sylion-pipeline/tests/aeis_v2/test_round_meta_freeze.py`
- `src/sylion-pipeline/tests/aeis_v2/test_round_meta_post_approval.py`
- `docs/aeis_repair_v2/full_human_dashboard_audit/FULL_HUMAN_DASHBOARD_BUG_LEDGER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/BUG_LEDGER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/FREEZE_REGISTER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/AEIS_OPERATOR_MANUAL_LATEST.md`

## Testy automatyczne

Komenda:

```powershell
python -m pytest src/sylion-pipeline/tests/aeis_v2/test_terminal.py src/sylion-pipeline/tests/aeis_v2/test_round_meta_freeze.py src/sylion-pipeline/tests/aeis_v2/test_round_meta_post_approval.py -q
```

Wynik po naprawie: `86 passed, 6 warnings`.  
Ten sam zestaw zostal uruchomiony dwa razy i przeszedl dwa razy.

## Runtime evidence

- Backend health: `http://127.0.0.1:8010/health`, status OK.
- Frontend dashboard: `http://127.0.0.1:3001`.
- Audit append-only: `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`.
- Evidence JSON: `docs/aeis_repair_v2/w18_router_repair/evidence/json/w18_router_dashboard_pass12_reconstructed_2026-05-13.json`.
- Screenshots: `docs/aeis_repair_v2/w18_router_repair/evidence/screenshots/`.

## PASS1

Projekt: `project_ca111ec23cf2`.

| Komenda | Ticket | Oczekiwany skutek | Wynik |
|---|---|---|---|
| `zamroz ksiege` | `40382a65776546ac985dfe21022ee8f3` | `canon_frozen_at` po approval | PASS |
| `zamroz masterplan` | `acef8fb4486b40da8d1030c3c32d141b` | `masterplan_frozen_at` po approval | PASS |
| `autoryzuj budowe` | `6ade1fe12fe645169f9739403a241c35` | `build_authorized_at` po approval | PASS |
| `bramka czlowieka` | N/D | `pending_governance_count=0` po approval | PASS |

Stan koncowy: `status=completed`, `phase=broadcast`, `pending_governance_count=0`.

## PASS2

Projekt: `project_f3e237d2a95b`.

| Komenda | Ticket | Oczekiwany skutek | Wynik |
|---|---|---|---|
| `zamroz ksiege` | `5b354f30238942fc816f660204b42002` | `canon_frozen_at` po approval | PASS |
| `zamroz masterplan` | `f31334978b9e4898b307cfe668158c92` | `masterplan_frozen_at` po approval | PASS |
| `autoryzuj budowe` | `8b73aa796cd4454e9293af09a7dcc20b` | `build_authorized_at` po approval | PASS |
| `bramka czlowieka` | N/D | `pending_governance_count=0` po approval | PASS |

Stan koncowy: `status=completed`, `phase=broadcast`, `pending_governance_count=0`.

## Zamrozony zakres

Mozna zamrozic tylko nastepujacy zakres:

- projektowy terminal W18 dla `zamroz ksiege`;
- projektowy terminal W18 dla `zamroz masterplan`;
- projektowy terminal W18 dla `autoryzuj budowe`;
- projektowy terminal W18 dla `bramka czlowieka`;
- backendowy route contract i audit log dla powyzszych akcji.

Nie wolno jeszcze zamrazac:

- pelnego start/stop/dispatch/cancel execution;
- calego Human Gate/Model Council;
- calego AEIS.

## Otwarte po naprawie

| ID | Status | Co zostalo |
|---|---|---|
| `FULL-AUD-005` | `RESOLVED_2X_PASS` | Global/project terminal i execution-start Phase 32/33 sa w centralnym routerze; zob. `../execution_start_router_repair/EXECUTION_START_W18_ROUTER_PASS12.md`. |
| `FULL-AUD-006` | `RESOLVED_2X_PROBED` | Route smoke failures `net::ERR_ABORTED` zostaly sprawdzone 2x direct endpoint + route reprobe; brak realnego bug. |
| `FULL-AUD-007` | `RESOLVED_2X_PASS` | Execution Start Phase 32/33 ma dashboard 2x PASS, worker evidence i W18 command ledger. |

## Reguly utrzymania

- Kazda nowa komenda mutujaca musi miec `CommandIntent`, `CommandRoute`, `CommandExecution`.
- D3+ musi isc jako `TWO_PHASE` przez Human Gate.
- UI nie moze tworzyc pozornego sukcesu bez odpowiedzi backendu.
- Audit zostaje append-only; korekta to nowy wpis, nie usuwanie historii.
- Freeze wymaga dwoch pelnych przebiegow dashboardowych z JSON, screenshotami i wpisem w `FREEZE_REGISTER.md`.
