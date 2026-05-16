# AEIS Full Human Dashboard Audit - PASS 1

Data: 2026-05-13  
Tryb: testy jak czlowiek przez dashboard + runtime evidence + API/UI coverage.  
Zakres PASS 1: route smoke, projekt start, W18 globalny, W18 projektowy, Human Gate visibility, Execution Start, Skills, Test Center simulation, screenshots.

## Werdykt PASS 1

System ma szeroka, renderujaca sie powierzchnie dashboardu, ale nie jest jeszcze gotowy do freeze end-to-end. Najwiekszy problem nie jest w tym, ze ekran W18 nie istnieje. Problem jest w tym, ze W18 i inne powierzchnie operatorskie czasem komunikuja operatorowi "przekazuje do Human Gate / tworze autoryzacje", ale dowody runtime nie pokazuja spójnego biletu, route ownership ani jednego backendowego command ledgera.

Status: **AUDYT W TOKU - NIE ZAMRAZAC SYSTEMU**.

## Artefakty

Coverage:

- `API_UI_COVERAGE_MAP.md`
- `evidence/json/api_ui_coverage_runtime.json`

Route smoke:

- `evidence/json/dashboard_route_smoke_2026-05-13_2137.json`
- 41 screenshotow w `evidence/screenshots/`

Symulacje:

- `evidence/json/human_simulation_pass1_2026-05-13_2143.json`
- `evidence/json/human_project_flow_retry2_2026-05-13_2145.json`
- `evidence/json/human_project_w18_ascii_commands_2026-05-13_2146.json`

Powiazany audyt W18:

- `../transactional_runtime_audit/AEIS_W18_TRANSACTIONAL_RUNTIME_AUDIT.md`
- `../transactional_runtime_audit/W18_TRANSACTIONAL_BUG_LEDGER.md`

## Runtime baseline

- Backend: `http://127.0.0.1:8010/health`
  - `status=ok`
  - `version=3.5.0`
  - `modules=138`
  - `endpoints=1953`
  - `db_mode=sqlite`
  - `event_mode=sqlite`
- OpenAPI: `1642` runtime paths.
- Frontend: `http://127.0.0.1:3001`.
- Coverage extractor: `129` frontend routes, `570` client API refs.

## Route smoke

Wynik Playwright:

| Metryka | Wynik |
|---|---:|
| Przetestowane trasy | 125 |
| OK render | 125 |
| HTTP error | 0 |
| Navigation error | 0 |
| Application error | 0 |
| Console errors | 0 |
| Request failures | 7 |

Request failures byly glownie `net::ERR_ABORTED` przy zmianie tras albo dlugich streamach. Nie klasyfikuje ich automatycznie jako P0; wymagaja osobnego probe tylko dla tych endpointow.

## Symulacja czlowieka

### 1. Project Start

Utworzono projekt z dashboardu:

- `project_id=proj_f8d024ae5097`
- `name=TX Full Human Audit 1778708756215`
- HTTP create: `200`
- evidence: `human_project_flow_retry2_2026-05-13_2145.json`

Wniosek: tworzenie projektu przez dashboard dziala w podstawowym scenariuszu.

### 2. W18 w projekcie

Wykonane komendy przez UI terminala projektu:

- `uruchom wykonanie build`
- `/status`
- `zamroz ksiege`
- `autoryzuj budowe`
- `bramka czlowieka`

Co zobaczyl operator:

- Build z tekstu zostal zablokowany: W18 nie wykonuje builda automatycznie i wymaga jawnej autoryzacji.
- `/status` zwrocil status systemu.
- `zamroz ksiege` pokazal komunikat, ze zadanie idzie do mechanizmu AEIS i bramki czlowieka.
- `autoryzuj budowe` pokazal komunikat, ze tworzona jest autoryzacja budowy przez tor bramki czlowieka.
- `bramka czlowieka` potem pokazala, ze projekt nie ma widocznego oczekujacego biletu.

Wniosek: W18 projektowy ma realny input i czesc guardow, ale komunikaty Human Gate nie zgadzaja sie z dowodem biletu.

### 3. Human Gate

Po komendach projektu:

- Pending governance tickets total: `13`.
- Pending governance tickets dla `proj_f8d024ae5097`: `0`.
- Projekt mial `approvals={"book":true,"operating_model":true}`.
- Nie znaleziono widocznego pending ticket dla freeze/build tego projektu.

Wniosek: Human Gate istnieje jako kolejka, ale w tym flow W18 nie utworzyl widocznego biletu albo komunikat UI nie odpowiada faktycznemu stanowi.

### 4. Execution Start

Przez dashboard wykonano:

- ustawienie runtime: `local-only`, `local_workers=2`, `vps_workers=0`, `environments=1`, `max_parallel=2`, cap `0`;
- klikniecie zapisu runtime;
- klikniecie fazy 32.

Wniosek: surface Execution Start jest interaktywny, ale PASS 1 nie zamraza jeszcze tego flow, bo trzeba powiazac aktywny projekt, audit chain, worker evidence i W18 command ledger.

### 5. Skills

Przez dashboard wykonano:

- klikniecie create skill;
- klikniecie execute skill;
- widok pokazal rejestr, executions, success rate i demand signals.

Wniosek: Skills dashboard jest interaktywny. Do freeze wymagany drugi pass: porownanie UI z API, runtime executor result i audit entry.

### 6. Test Center

Przez dashboard wykonano simulation run na projekcie, gdy projekt byl dostepny w kampanii. PASS 1 potwierdza, ze powierzchnia test-center/simulation jest klikalna i podlaczona do API, ale nie zamraza pelnego W14/test-release flow.

### 7. W18 globalny A7

Przez `/terminal` wykonano:

- `/status`
- `/report workers`
- `/report gates`
- `/show blockers`
- `/request checkpoint`

Wynik:

- raporty read-only dzialaja;
- `/request checkpoint` jest nieznana komenda;
- `/report workers` nadal raportuje inny aktywny projekt (`project_06e3bf38743b`), nie projekt z biezacej symulacji.

Wniosek: globalny W18 jest dobry jako obserwacja/read-only report, ale nie jest jeszcze kanonicznym cockpit dla aktualnego flow operatora.

## Krytyczne rozjazdy

1. W18 mowi o przekazaniu freeze/build do Human Gate, ale projekt po komendach nie ma widocznego pending ticket.
2. Globalny W18 raportuje workerow dla innego projektu niz projekt tworzony w symulacji.
3. Nie ma jednej reguly: kto posiada komende, gdzie idzie komenda, jaki jest target i kto moze ja zatwierdzic.
4. `/request checkpoint` z planu A7 nie istnieje.
5. W18 ma osobne kanaly: global terminal, terminal projektu, execution-start `w18_commands`.

## Zasady dalszego audytu

1. Kazdy scenariusz testujemy przez dashboard, nie tylko API.
2. Kazdy scenariusz zapisuje: screenshot, JSON evidence, API cross-check, wynik w bug ledgerze.
3. Flow mozna zamrozic dopiero po 2x PASS na tym samym scenariuszu.
4. Jezeli UI mowi "Human Gate", musi istniec ticket albo jawny komunikat "already approved / no ticket required" z dowodem.
5. Jezeli W18 mowi "autoryzuje", musi powstac command intent, audit entry i route ownership.
6. Read-only reporty W18 musza zawsze raportowac aktualny kontekst albo jawnie wskazywac, jaki projekt raportuja.

## Kolejny pass

PASS 2 powinien objac:

1. Ponowienie Project Start na drugim projekcie.
2. W18 `zamroz ksiege`, `zamroz masterplan`, `autoryzuj budowe` z porownaniem: UI -> ticket -> project state -> audit.
3. Execution Start dla konkretnego projektu, nie tylko aktywnego projektu.
4. Test Center release-gate, no-mock-scan, simulation, catalog.
5. Skills: create -> execute -> execution record -> demand signal -> API parity.
6. Human Gate approve/reject tylko na biletach utworzonych przez testowy projekt.
7. W18 replay: czy powyzsze komendy sa odtwarzalne i zgodne z audit chain.

