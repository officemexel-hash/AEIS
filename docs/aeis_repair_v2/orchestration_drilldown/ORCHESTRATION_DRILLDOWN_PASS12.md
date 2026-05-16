# FLOW-019 - Orchestration J1-J9 Dashboard Drilldown

Data: 2026-05-14

## Wynik

Status: `PASS_2X`

Evidence JSON: `docs/aeis_repair_v2/orchestration_drilldown/evidence/json/orchestration_drilldown_pass12_2026-05-14T10-54-40-012Z.json`

Screenshoty: `docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/*2026-05-14T10-54-40-012Z.png`

## Zakres dashboardu

- Hub `/orchestration`.
- J1 `/orchestration/llm-routing`: klik `Zbalansowany`; API `POST /llm-judge-routing/preset/balanced`; 32 komorki routingu.
- J2 `/orchestration/council-rules`: klik `Zapisz` i `Symuluj wynik`; API `PUT /council-rules` i `POST /simulate-vote`; wynik symulacji poprawnie respektuje `quorum_min=5`.
- J3 `/orchestration/auditor`: klik `Audytuj teraz` i `Uruchom gate`; API audit trigger + Stop-Fix-Restart; decyzja `CONTINUE`, blockery `0`.
- J4 `/orchestration/fixer`: klik `Zapisz`; API `PUT /fixer-protocol`.
- J5 `/orchestration/dispatch`: klik `Zapisz`; API `PUT /dispatch-config`; tryb `capped`, limit `8`.
- J6 `/orchestration/tests`: klik `Uruchom golden`; API `POST /test-catalog/run-now`; status `pass`.
- J7 `/orchestration/teams`: klik `Testuj reguly`; UI wysyla event z aktywnej reguly `[r39-theater]`; `matched_rules=1`.
- J8 `/orchestration/event-map`: filtr `aeis.orchestration`; 2 runtime edge.
- J9 `/orchestration/conversations`: klik `Uruchom rozmowe`; status `completed`, 3 tury.

## Naprawy wykonane przed zamrozeniem

- J6: katalog golden uzywal sztywno 3 glosow rady, wiec konfiguracja operatora `quorum_min=5` powodowala falszywy `fail`. Backend generuje teraz liczbe glosow zgodna z aktualnym quorum.
- J3: Stop-Fix-Restart scan opieral source roots o `Path.cwd()`, co moglo dawac falszywie pusty skan po starcie uvicorn z `src/sylion-pipeline`. Dodano resolver root repozytorium odporny na cwd i test regresji.
- J7: przycisk `Testuj reguly` wysylal hardcoded event `[advisor][claude][engine]`, mimo ze aktywna regule stanowil wzorzec `[r39-theater]`. Panel generuje teraz probny event z pierwszej aktywnej reguly.

## Weryfikacja

- `python -m pytest src/sylion-pipeline/tests/aeis/advisor/orchestration_config/test_orchestration_routes.py -q` -> `37 passed`.
- `npm run lint -- "src/app/(app)/orchestration/teams/page.tsx"` -> `0 errors`, 3 istniejace ostrzezenia `any`.
- Finalny dashboard PASS_2X: `console_errors=0`, `page_errors=0`, `request_failures=0`, `hard_request_failures=0`, `api_failures=0`.

## Zasady zamrozenia

- Zamrozony jest tylko zakres J1-J9 opisany wyzej, wykonywany przez dashboard i potwierdzony odpowiedziami API.
- J3 Stop-Fix-Restart musi pozostac `READY/CONTINUE` przed przejsciem do kolejnego etapu.
- J6 `golden` musi respektowac aktualna konfiguracje rady; nie wolno przyjmowac testu, ktory zaklada stale quorum.
- J7 test runtime musi dobierac event do aktywnej reguly, a nie do zakodowanego na stale przykladu.
- Po zmianie dowolnego endpointu `/api/v1/orchestration/*` albo strony `/orchestration/*` trzeba powtorzyc pelny FLOW-019 2x.
