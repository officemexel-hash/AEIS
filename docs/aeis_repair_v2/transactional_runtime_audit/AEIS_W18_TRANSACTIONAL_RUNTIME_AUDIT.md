# AEIS W18 Transactional Runtime Audit

Data audytu: 2026-05-13, 22:56 Europe/Warsaw  
Zakres: Terminal W18 jako realna warstwa komend, routingu, ownership i kontroli wielu srodowisk/agentow/modeli.  
Skills: `aeis-runtime-evidence-auditor`, `aeis-api-ui-coverage-auditor`, `aeis-governance-council-auditor`, `playwright`.

## Werdykt

W18 jest dzisiaj czesciowo dzialajaca powierzchnia obserwacji i raportow, ale nie jest jeszcze jednolitym terminalem sterujacym AEIS.

Najwazniejsze: `/terminal` ma widoczne pole komend i wykonuje bezpieczne slash-komendy, a terminal projektu ma pole rozmowy i blokuje tekstowe uruchomienie builda bez jawnej bramki. Nie ma jednak centralnego Command Routera, ktory rozstrzyga kto rzadzi komenda, do ktorego srodowiska/worker/modelu idzie polecenie, jaki ma owner, lock, decision class, Human Gate i zapis audytowy. W18 nie moze byc zamrozony jako gotowy runtime-control plane.

Status zamrozenia: **NIE ZAMRAZAC**. Najpierw naprawic P0/P1 z bug ledgera.

## Evidence

Runtime:

- Backend: `http://127.0.0.1:8010/health` zwrocil `status=ok`, `version=3.5.0`, `modules=138`, `endpoints=1953`, `db_mode=sqlite`.
- Frontend: `http://127.0.0.1:3001` zwrocil HTTP 200.

Artefakty:

- `evidence/json/w18_api_probe_20260513_225033.json`
- `evidence/json/w18_a7_command_matrix_20260513_225611.json`
- `evidence/json/w18_dashboard_dom_probe_2026-05-13_2052.json`
- `evidence/json/w18_project_terminal_open_probe_2026-05-13_2054.json`
- `evidence/json/w18_project_commands_probe_20260513_225152.json`

Screenshots:

- `evidence/screenshots/w18_terminal_before_2026-05-13_2052.png`
- `evidence/screenshots/w18_terminal_after_help_2026-05-13_2052.png`
- `evidence/screenshots/w18_terminal_replay_2026-05-13_2052.png`
- `evidence/screenshots/w18_project_terminal_open_after_command_2026-05-13_2054.png`

## Co dziala

1. `/terminal` ma input komend:
   - selector: input z placeholderem `np. /help, /sessions, /agents ...`
   - `/help` przez UI zadzialal i pokazal katalog 19 komend.
   - stream W18 pokazal eventy `W18·operator $ /help`, `W18·terminal 19 comendy dostepne`, oraz `POST /api/v1/terminal/exec -> 200`.

2. Minimalny zestaw read-only z planu A7 dziala w duzej czesci:
   - `/status`: text
   - `/report current-run`: text
   - `/report council`: table, 16 rows
   - `/report workers`: table, 3 rows
   - `/report costs`: table, 0 rows
   - `/report gates`: table, 54 rows
   - `/report tests`: table, 0 rows
   - `/report deploy`: table, 2 rows
   - `/explain last-decision`: text
   - `/show blockers`: table, 18 rows
   - `/show audit-tail`: table, 20 rows

3. `/terminal/replay` istnieje jako UI i backend slice/days API jest podlaczone.

4. Terminal projektu ma input W18:
   - `data-testid=project-w18-terminal-input`
   - polecenie `uruchom wykonanie build` zostalo zablokowane komunikatem, ze W18 nie wykonuje go automatycznie z tekstu i wymaga jawnej autoryzacji budowy oraz Human Gate.

5. Interwencyjne endpointy terminala maja lokalny wymog roli `operator`:
   - pause/resume/patch/skip/cancel uzywaja `Depends(requires_role("operator"))`.

## Findings

### W18-TRX-001 P0: Brak centralnego Command Routera i zasad ownership komend

Dowody:

- `POST /api/v1/terminal/exec` tylko parsuje `line` przez `parse_command(req.line, ctx)`.
- Context `project_id`, `agent_id`, `worker_id`, `environment_id` jest tylko kopiowany do `extra` eventu W18. Nie decyduje o routingu.
- `/run env-local-audit agent-audit echo hello` zwrocil `Nieznana komenda: /run`.
- Komenda bez slash, np. `uruchom test w env-local-audit przez agent-audit`, zwrocila blad: polecenia musza zaczynac sie od `/`.
- Projektowy terminal W18 ma osobne lokalne `if`/`else` w frontendzie i sam w komentarzu UI mowi: docelowo kazde polecenie powinno trafic do backendowego Command Bus.

Skutek:

Operator nie ma jednego miejsca, w ktorym system rozstrzyga: kto wydal komende, kto ja posiada, do ktorego srodowiska idzie, ktory agent/model ja wykonuje, jaka jest klasa decyzji i czy trzeba Human Gate.

### W18-TRX-002 P0: Interwencje W18 nie zatrzymuja realnego agenta

Dowody:

- `terminal_routes.py` ma komentarz: pause/resume w G2 step 1 tylko zmienia stan serwera i zapisuje audit trail; agent dalej emituje progress.
- `add_task` tworzy task pending.
- `pause_pending_task` zwrocil HTTP 409, bo task nie jest `running`.
- Brak dowodu runtime, ze pause/resume wysyla sygnal do aktywnego loopa agenta przez W11 adapter bus.

Skutek:

W18 wyglada jak interwencja operatorska, ale dla aktywnej pracy moze byc tylko zapisem stanu po stronie serwera. To jest krytyczne, bo operator moze myslec, ze zatrzymal prace, a wykonawca dalej dziala.

### W18-TRX-003 P1: Sa trzy rozne kanaly komend bez jednego Source of Truth

Kanaly:

1. Globalne `/terminal`: slash parser i stream/replay.
2. Projektowy W18 w `/projects/{projectId}`: lokalny frontendowy router naturalnych komend plus backend tylko dla slash-aliasow.
3. Execution Start `w18_commands`: kolejka zapisywana przez dashboardowe akcje `_append_w18_command`.

Dowody:

- `GET /api/v1/execution-start/projects/project_06e3bf38743b/w18-commands` zwrocil `count=0`.
- Ten sam projekt mial aktywny W18 terminal i wykonane lokalne polecenie tekstowe, ale nie trafilo ono do tej kolejki.
- Middleware w `app.py` mirroruje aktywnosc API do streamu W18, ale mirror API activity to nie to samo co intencja komendy z ownerem i routingiem.

Skutek:

Nie da sie wiarygodnie odpowiedziec "jaka komenda rzadzi aktualnym stanem projektu" bez sklejania UI-local history, streamu W18, replay JSONL i execution-start queue.

### W18-TRX-004 P1: Katalog komend mowi `implemented=yes`, ale czesc handlerow zwraca `not_implemented`

Dowody:

- `GET /api/v1/terminal/commands`: `count=19`, `implemented=19`.
- `POST /api/v1/terminal/exec /skip`: `kind=not_implemented`.
- `POST /api/v1/terminal/exec /focus model audit-model`: `kind=not_implemented`.

Skutek:

Dashboard pokazuje operatorowi falszywa gotowosc komend sterujacych. Szczegolnie grozne sa komendy control/intervention: `/skip`, `/retry`, `/priority`, `/focus`, `/model`, `/replay`, `/export`, jesli deklaracja "implemented" nie znaczy faktycznego wykonania.

### W18-TRX-005 P1: Brak formalnego modelu rozdzialu komend przy wielu srodowiskach

Dowody:

- W kodzie terminala wystepuja pola `environment_id`, `agent_id`, `worker_id`, ale sa metadanymi eventu.
- Nie znaleziono w W18 warstwy: route table, lease/lock per target, queue per environment, arbitration policy, broadcast policy, ani konfliktu "kto ma aktywne prawo do terminala".
- `surface.command_bus` ma `submit_intent/approve/reject` i registry handlerow, ale komentarz mowi, ze real dispatch routing w CommandBus przyjdzie pozniej.

Skutek:

W scenariuszu uzytkownika: "pracuje wiele srodowisk naraz i ktos/model/agent rozdziela komendy" system nie ma jeszcze twardej reguly. Dzisiaj komenda moze byc tylko parsowana albo obsluzona lokalnie przez konkretny ekran.

### W18-TRX-006 P2: A7 `request checkpoint` nie istnieje

Dowody:

- `/request checkpoint` zwrocil `Nieznana komenda: /request`.
- Plan A7 wymienia checkpoint jako minimalna akcje operatorska.

Skutek:

Brakuje standardowego sposobu wymuszenia checkpointu z terminala podczas pracy modeli/workerow.

## Zasady naprawy

Te reguly musza obowiazywac przed dalszym "zamrazaniem" W18:

1. Kazda komenda ma `command_id`, `route_id`, `source_surface`, `operator_id`, `project_id`, `target_kind`, `target_id`, `environment_id`, `agent_id/worker_id/model_id`, `decision_class`, `risk_level`, `owner`, `status`, `audit_ref`.
2. Kazde klikniecie UI, ktore zmienia stan, tworzy rownowazna intencje W18. Nie tylko stream API eventu.
3. Read-only komendy moga isc immediate D0/D1. Mutacje defaultowo ida TWO_PHASE. D4/D5 i produkcja/zewnetrzne akcje wymagaja Human Gate.
4. Agent/model nie moze zatwierdzic wlasnej komendy. Model moze rekomendowac trase, ale operator/Human Gate zatwierdza klasy ryzyka.
5. Komenda wykonywalna musi miec jawny target. `local`, `staging`, `vps`, `production`, `worker`, `model` nie moga byc zgadywane przy mutacji.
6. Jedno srodowisko ma jeden aktywny lease wykonawczy. Konflikt komend trafia do kolejki albo Human Gate, nie do rownoleglego wykonania.
7. W18 nie jest shell/bashem. Arbitrary shell command moze isc tylko przez osobny tool executor/sandbox, z risk policy, timeout, audit i rollback/cleanup.
8. `implemented=yes` oznacza: handler ma test API, test UI, audit entry i opis w manualu. Jezeli handler zwraca `not_implemented`, katalog musi to pokazac jako `implemented=no`.
9. Interwencje pause/resume/cancel wymagaja ACK od aktywnego wykonawcy. Zmiana samego stanu serwera nie wystarcza.
10. Freeze dopiero po 2x tym samym scenariuszu PASS: UI screenshot, API result, audit/replay zgodne, brak rozjazdu z Project/Workers UI.

## Plan naprawczy

### Faza 1: Contract i testy blokujace

1. Dodac kontrakt `CommandIntent`, `CommandRoute`, `CommandExecution`.
2. Dodac testy API dla A7 command matrix.
3. Dodac testy Playwright:
   - `/terminal` input + `/help`
   - `/terminal` report matrix
   - `/projects/{id}` W18 natural command
   - D4/D5 command blocked by Human Gate
   - command appears in unified backend audit
4. Oznaczyc W18 status jako `partial_control_plane` w runtime truth, dopoki P0 nie przejdzie.

### Faza 2: Centralny router

1. Utworzyc `sylion/aeis_v2/terminal/command_router.py`.
2. `/api/v1/terminal/exec` ma tworzyc `CommandIntent`, nie tylko wywolywac parser.
3. Project W18 terminal ma wysylac wszystkie komendy do tego samego endpointu.
4. Dashboard actions maja przechodzic przez router, a `_append_w18_command` ma byc efektem zapisu, nie osobnym kanalem.

### Faza 3: Governance i ownership

1. Podpiac `surface.command_bus` jako TWO_PHASE dla mutacji.
2. Podpiac `ToolRegistry.check_authorization` dla tool/shell/runtime actions.
3. Dodac route policy:
   - `read_status`: immediate
   - `report_*`: immediate
   - `project_state_change`: TWO_PHASE
   - `runtime_worker_action`: D3/D4 zalezne od targetu
   - `production/external`: D4/D5 Human Gate
4. Dodac lease per target: `environment_id`, `worker_id`, `agent_id`, `model_id`.

### Faza 4: Real intervention wiring

1. Pause/resume/cancel/skip maja wysylac sygnal do aktywnego runtime/adapter bus.
2. Endpoint zwraca `ack=true/false`, `ack_source`, `ack_ts`.
3. UI pokazuje "server state changed" oddzielnie od "agent acknowledged".
4. Replay zapisuje: command, approval, dispatch, ack, result.

### Faza 5: Freeze

1. Powtorzyc A7 2 razy przez dashboard.
2. Porownac W18 reporty z UI/API/audit.
3. Zaktualizowac instrukcje obslugi ze screenshotami.
4. Dopiero wtedy wpisac freeze do rejestru.

