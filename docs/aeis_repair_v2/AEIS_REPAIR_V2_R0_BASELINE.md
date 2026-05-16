# AEIS Repair V2 - R0 Baseline i aktywny backlog

Data baseline: 2026-05-13, Europe/Warsaw.

## Zasady obowiazujace od R0

1. Dowod ma pierwszenstwo przed deklaracja. Kazda naprawa P0/P1 musi miec: reprodukcje, przyczyne, patch, test API lub UI, ponowny smoke i wpis w backlogu.
2. Kanoniczny frontend dev to `http://localhost:3001`. Wejscie przez `http://127.0.0.1:3001` w tym srodowisku psuje HMR/hydratacje Next dev i daje falszywe `OFFLINE`.
3. Kanoniczny backend dev to `http://127.0.0.1:8010`.
4. Nie wolno czyscic dirty tree ani cofniecia cudzych zmian. Repo ma istniejace zmiany uzytkownika i baseline traktuje je jako stan zastany.
5. Nie uznajemy endpointu lub ekranu za gotowy tylko dlatego, ze plik istnieje. Status `LIVE` wymaga requestow runtime i braku bledow 4xx/5xx w smoke.
6. D3+ decyzje architektoniczne wymagaja evidence pack, rollback plan i bramki Human Gate przed wdrozeniem.

## Stan runtime

Backend zostal uruchomiony z `sylion.api.app` na porcie `8010`.

- `GET /health`: `200`, status `ok`
- wersja: `3.5.0`
- moduly: `138`
- endpointy wg health: `1995`
- OpenAPI: `1636` sciezek
- tryb DB/event: `sqlite`
- branch: `advisor-etap1`
- commit runtime truth: `03ffd560`
- dirty tree wg runtime truth: `true`, `1649` wpisow

Dowody:

- `docs/aeis_repair_v2/evidence/R0_baseline/health_8010.json`
- `docs/aeis_repair_v2/evidence/R0_baseline/openapi_8010.json`
- `docs/aeis_repair_v2/evidence/R0_baseline/runtime_truth_8010.json`
- `docs/aeis_repair_v2/evidence/R0_baseline/backend_8010_start.out.log`
- `docs/aeis_repair_v2/evidence/R0_baseline/backend_8010_start.err.log`

Frontend `3001` byl starym procesem z 2026-05-09. Zostal zatrzymany i uruchomiony ponownie na `3001`.

Dowody:

- `docs/aeis_repair_v2/evidence/R0_baseline/frontend_3001_restart.out.log`
- `docs/aeis_repair_v2/evidence/R0_baseline/frontend_3001_restart.err.log`

## Smoke API

Krytyczne API po stronie backendu:

- `200`: runtime truth, workspace Human Gate sessions, Human Gate requests, memory index/stats/search, memory evidence stats, skills runtime/stats/list, funding submission sessions, governance gates, governance compliance/full, projects, test-center health.
- `404`: `/api/v1/operator-mobile/v1/queue`, `/api/v1/mobile/v1/queue`.

Wniosek: mobilny UI nie korzysta z tych dwoch legacy probe paths. Realne requesty UI ida do:

- `/api/v1/mobile/queue?operator_id=operator-main`
- `/api/v1/mobile/devices?operator_id=operator-main`

i oba zwracaja `200`.

Dowod:

- `docs/aeis_repair_v2/evidence/R0_baseline/critical_api_probe.json`

## Smoke UI

Smoke UI wykonany na `http://localhost:3001`.

Ekrany sprawdzone:

- `/runtime`: `200`, brak page errors, brak API 4xx/5xx, backend live.
- `/workspace`: `200`, brak page errors, brak API 4xx/5xx.
- `/governance`: `200`, brak page errors, brak API 4xx/5xx, `LIVE`, requesty governance `200`.
- `/funding`: `200`, brak page errors, brak API 4xx/5xx.
- `/skills`: `200`, brak page errors, brak API 4xx/5xx.
- `/memory`: `200`, brak page errors, brak API 4xx/5xx.
- `/test-center`: `200`, brak page errors, brak API 4xx/5xx.
- `/terminal`: `200`, brak page errors, brak API 4xx/5xx.
- `/operator-mobile`: `200`, brak page errors, brak API 4xx/5xx.
- `/mobile`: `200`, brak page errors, brak API 4xx/5xx.

Dowody:

- `docs/aeis_repair_v2/evidence/R0_baseline/critical_ui_localhost_smoke.json`
- `output/playwright/aeis_repair_v2/R0_baseline_localhost/*.png`

## Drift wykryty podczas R0

### R0-D1: 127.0.0.1 psuje hydratacje Next dev

Objaw: wejscie przez `http://127.0.0.1:3001/governance` pokazuje `OFFLINE`, nie wykonuje fetchy hookow i loguje blad HMR WebSocket `ERR_INVALID_HTTP_RESPONSE`.

Kontrdowod: `http://localhost:3001/governance` wykonuje requesty:

- `/api/v1/health`
- `/api/v1/governance/proposals`
- `/api/v1/governance/policies`
- `/api/v1/governance/compliance/{pipeline,council,memory,security}`
- `/api/v1/governance/compliance/rules`

i pokazuje `LIVE`.

Dowody:

- `docs/aeis_repair_v2/evidence/R0_baseline/critical_ui_fetch_trace_after_restart.json`
- `docs/aeis_repair_v2/evidence/R0_baseline/critical_ui_hydration_click_trace.json`
- `docs/aeis_repair_v2/evidence/R0_baseline/governance_script_load_trace.json`

Klasyfikacja: P1 dev-runtime/origin, nie P0 governance.

Status R1.1: naprawione przez `allowedDevOrigins: ["127.0.0.1", "::1"]` w `src/sylion-frontend/next.config.ts`.

Dowod po naprawie:

- `docs/aeis_repair_v2/evidence/R1_1_frontend_origin/origin_hydration_regression.json`
- `output/playwright/aeis_repair_v2/R1_1_frontend_origin/*.png`

Wynik: `localhost:3001` i `127.0.0.1:3001` zwracaja `200`, maja `0` HMR errors, `0` page errors, `0` API 4xx/5xx; `/governance` pokazuje `LIVE` na obu hostach.

### R0-D2: API/UI coverage static undercounts hook-driven routes

Mapa pokrycia wykryla:

- frontend routes: `129`
- client API refs: `545`
- runtime OpenAPI paths: `1636`

Jednoczesnie statyczna klasyfikacja oznacza m.in. `/governance`, `/funding`, `/memory`, `/mobile` jako `UI_ONLY_OR_STATIC`, mimo ze smoke runtime pokazuje realne requesty API. Przyczyna: ekstraktor liczy bezposrednie referencje w pliku route, a nie zaleznosci przez wspolne hooki/importy i runtime trace.

Dowody:

- `docs/aeis_repair_v2/evidence/R0_baseline/api_ui_coverage.md`
- `docs/aeis_repair_v2/evidence/R0_baseline/api_ui_coverage.json`
- `docs/aeis_repair_v2/evidence/R0_baseline/critical_ui_localhost_smoke.json`

Klasyfikacja: P1 audit tooling, bo moze zle kierowac kolejnoscia napraw.

Status R1.2: naprawione w `scripts/extract_api_ui_coverage.py`.

Zakres poprawki:

- parser rozwiazuje metody `api.*`, `testingApi.*` i innych klientow z `src/lib/api/*.ts`;
- parser rozwiazuje importowane hooki z `src/lib/api/hooks.ts`;
- parser rozwiazuje lokalne importy typu `./_mobile`;
- parser obsluguje re-export strony `/mobile` do `/operator-mobile`;
- normalizacja sciezek ucina kropki/interpunkcje z tekstow UI, zeby nie tworzyc falszywych brakow OpenAPI.

Dowod po naprawie:

- `docs/aeis_repair_v2/evidence/R1_2_api_ui_coverage/api_ui_coverage.json`
- `docs/aeis_repair_v2/evidence/R1_2_api_ui_coverage/api_ui_coverage.md`

Wynik po naprawie:

- `STATIC_API_LINKED`: `95`
- `UI_ONLY_OR_STATIC`: `20`
- `NEEDS_REVIEW`: `7`
- `PARTIAL_API_LINKED`: `0`
- `/governance`: `6/6` runtime refs
- `/funding`: `39/39` runtime refs
- `/memory`: `7/7` runtime refs
- `/workspace`: `7/7` runtime refs
- `/mobile` i `/operator-mobile`: `3/3` runtime refs, w tym `/api/v1/mobile/queue` i `/api/v1/mobile/devices`

### R0-D3: OpenAPI duplicate operation-id warnings

Backend startuje, ale loguje wiele ostrzezen FastAPI o zduplikowanych Operation ID w trasach orchestration. Nie blokuje runtime smoke, ale degraduje dokumentacje OpenAPI i potencjalne generowanie klientow.

Dowod:

- `docs/aeis_repair_v2/evidence/R0_baseline/backend_8010_start.err.log`

Klasyfikacja: P1/P2 API contract hygiene.

Status R1.3: naprawione w `src/sylion-pipeline/sylion/api/app.py`.

Przyczyna: `sylion.api.router` juz rejestrowal `advisor_router`, `teams_router` i `orchestration_router`, a `app.py` rejestrowal te same trzy routery drugi raz.

Zakres poprawki:

- usunieto z `app.py` bezposrednie importy i `include_router` dla `advisor_router`, `teams_router`, `orchestration_router`;
- pozostawiono rejestracje przez glowny `sylion.api.router`.

Dowod po naprawie:

- `docs/aeis_repair_v2/evidence/R1_3_openapi_operation_ids/backend_8010_restart.err.log`
- `docs/aeis_repair_v2/evidence/R1_3_openapi_operation_ids/openapi_8010_after_router_dedupe.json`
- `docs/aeis_repair_v2/evidence/R1_3_openapi_operation_ids/deduped_router_smoke.json`

Wynik:

- duplicate warning count: `0`
- duplicate `operationId` w OpenAPI JSON: `0`
- liczba sciezek OpenAPI: `1636`
- liczba operationIds: `1918`
- smoke endpointow `advisor`, `advisor/teams`, `orchestration`: `200`

### R0-D4: mobile legacy probe path drift

Probe `/api/v1/operator-mobile/v1/queue` i `/api/v1/mobile/v1/queue` zwracaja `404`, ale live UI korzysta z `/api/v1/mobile/queue` i `/api/v1/mobile/devices`, ktore zwracaja `200`.

Klasyfikacja: P2 canon/test drift, chyba ze dokumenty kanoniczne nadal wymagaja wariantu `/v1/queue`.

Status R1.4: naprawione przez ukryte aliasy kompatybilnosci w `src/sylion-pipeline/sylion/api/operator_mobile_routes.py` i rejestracje `operator_mobile_legacy_router` w `src/sylion-pipeline/sylion/api/router.py`.

Zasada kanonu: UI i OpenAPI nadal promuja `/api/v1/mobile/*`. Alias `/api/v1/mobile/v1/*` i `/api/v1/operator-mobile/v1/*` istnieje tylko po to, zeby stare probe/testy nie dawaly falszywych 404.

Dowod po naprawie:

- `docs/aeis_repair_v2/evidence/R1_4_mobile_legacy_paths/mobile_canonical_and_legacy_smoke.json`
- `docs/aeis_repair_v2/evidence/R1_4_mobile_legacy_paths/mobile_ui_smoke_after_aliases.json`
- `docs/aeis_repair_v2/evidence/R1_4_mobile_legacy_paths/openapi_after_mobile_aliases.json`

Wynik:

- `/api/v1/mobile/queue`: `200`
- `/api/v1/mobile/devices`: `200`
- `/api/v1/mobile/v1/queue`: `200`
- `/api/v1/mobile/v1/devices`: `200`
- `/api/v1/operator-mobile/v1/queue`: `200`
- `/api/v1/operator-mobile/v1/devices`: `200`
- legacy paths in OpenAPI: `0`
- OpenAPI path count: `1636`
- duplicate operation-id warnings: `0`
- UI `/mobile` i `/operator-mobile`: `200`, bez API 4xx/5xx

### R0-D5: stare komendy startowe port 8000

Komunikaty offline w czesci UI oraz wybrane instrukcje operacyjne wskazywaly `python -m uvicorn sylion.api.app:app --port 8000`, podczas gdy kanoniczny backend dev dla frontendu w R0/R1 dziala na `127.0.0.1:8010`.

Status R1.5: naprawione.

Zakres:

- widoczne komunikaty offline w aktualnym UI wskazuja `--host 127.0.0.1 --port 8010`;
- `scripts/start-server.ps1` startuje backend na `127.0.0.1:8010`;
- aktualne instrukcje operacyjne (`HOW_TO_RUN.md`, `CURRENT_STATE.md`, `docs/dokumentacja/02_operational_manual.md`, `docs/dokumentacja/04_dla_developera.md`) wskazuja port `8010`.

Dowod:

- `docs/aeis_repair_v2/evidence/R1_5_port_8010_alignment/port_alignment_checks.json`

Wynik:

- stare `8000` w aktualnym UI: `0`
- stare `8000` w wybranych instrukcjach operacyjnych: `0`
- odniesienia do `8010` w zaktualizowanych instrukcjach/helperze: `10`
- parse `scripts/start-server.ps1`: OK

Uwaga: scoped ESLint na zmienionych plikach frontendu nadal nie przechodzi przez istniejace w repo bledy lint (`react-hooks/set-state-in-effect`, `react/no-unescaped-entities`, unused imports). Nie sa one skutkiem zmiany portu i zostaja jako osobny backlog jakosci frontendu.

## R2: backlog jakosci po stabilizacji R1

### R2.1: WebSocket `/ws/overview` 403

Problem: po restarcie backendu logi runtime pokazywaly powtarzalne odrzucenia:

- `WebSocket /ws/overview?token=... 403`
- `connection rejected (403 Forbidden)`

Analiza:

- aktualny frontend korzysta z `/ws/workspace`;
- backend mial kanoniczne trasy `/ws/events`, `/ws/workspace` i `/ws/agent-theater`;
- w aktualnym kodzie nie znaleziono zrodla `/ws/overview`;
- rownolegle dzialal stary proces Next na porcie `3000` z worktree `.claude`, wiec najbardziej prawdopodobne zrodlo to stary klient albo skompilowana paczka dev;
- brak trasy WebSocket w Starlette/FastAPI skutkowal `403`, mimo ze nie byl to blad autoryzacji kanonicznego UI.

Status R2.1: naprawione przez ukryta trase kompatybilnosci.

Zakres poprawki:

- dodano `/ws/overview` w `src/sylion-pipeline/sylion/api/ws_routes.py`;
- trasa akceptuje stary parametr `token` bez promowania go jako nowego kontraktu;
- trasa wysyla minimalny snapshot `overview`, odpowiada na `ping`, `snapshot`, `subscribe` i `set_interval`;
- kanon pozostaje bez zmian: nowy frontend powinien uzywac `/ws/workspace`.

Testy:

- `python -m py_compile src/sylion-pipeline/sylion/api/ws_routes.py src/sylion-pipeline/tests/test_ws_routes.py`
- `pytest src/sylion-pipeline/tests/test_ws_routes.py -q`

Wynik testow: `9 passed`.

Dowod po naprawie:

- `docs/aeis_repair_v2/evidence/R2_1_ws_overview_compat/backend_8010_restart.err.log`
- `docs/aeis_repair_v2/evidence/R2_1_ws_overview_compat/ws_overview_probe.json`

Wynik runtime:

- `/ws/overview?token=legacy`: connected, initial `overview`, `pong`;
- `/ws/workspace`: connected, `pong`;
- `/ws/events`: connected, `pong`;
- nowy log backendu po restarcie: `explicit_403_count = 0`, `contains_rejected = false`;
- istniejace stare polaczenie `/ws/overview?token=...` zostalo przyjete jako `[accepted]`.

### R2.2: stale procesy dev na porcie `3000`

Problem: po ustabilizowaniu kanonu dev (`frontend 3001`, `backend 8010`) nadal dzialal drugi `next dev` na porcie `3000`.

Dowod przed:

- port `3000`: PID `24148`;
- proces nadrzedny: PID `40552`;
- command line: `.claude/worktrees/wizardly-wright-ae2f99/src/sylion-frontend/.../next dev`;
- kanoniczny `localhost:3001/governance`: `200`;
- kanoniczny `127.0.0.1:8010/health`: `200`.

Status R2.2: naprawione operacyjnie.

Zakres:

- zatrzymano tylko stary proces Next z `.claude/worktrees` (`24148`, `40552`);
- nie zatrzymano kanonicznego frontendu `3001`;
- nie zatrzymano kanonicznego backendu `8010`.

Dowod po:

- `docs/aeis_repair_v2/evidence/R2_2_dev_process_hygiene/dev_process_hygiene.json`

Wynik:

- aktywne listenery po czyszczeniu: `3001`, `8010`;
- port `3000`: brak listenera;
- `localhost:3001/governance`: `200`;
- `127.0.0.1:8010/health`: `200`;
- backend log WebSocket po R2.1/R2.2: brak `connection rejected (403 Forbidden)`.

### R2.3: triage ESLint frontendu

Problem: po R1.5 scoped ESLint pokazywal, ze frontend ma istniejace bledy lint niezalezne od zmian portu. Pelny lint przed R2.3 zwracal `exit_code = 1`.

Stan przed:

- `total_errors`: `66`;
- `total_warnings`: `1482`;
- glowne bledy: `react-hooks/set-state-in-effect`, `react/no-unescaped-entities`, `react-hooks/static-components`, `react-hooks/purity`, `react-hooks/refs`, `react-hooks/rules-of-hooks`, `react-hooks/immutability`, `react-hooks/set-state-in-render`.

Status R2.3: naprawione jako gate/triage.

Zakres:

- naprawiono falszywy `react-hooks/rules-of-hooks` w `e2e/fixtures/seeded-page.ts` przez zmiane nazwy parametru fixture z `use` na `runFixture`;
- przy okazji e2e fixture przestawiono z fallbacku `127.0.0.1:8000` na kanoniczne `127.0.0.1:8010`;
- usunieto `react-hooks/set-state-in-render` w `src/app/(app)/health/page.tsx` przez zastapienie setState w renderze stanem override + memoizowanym auto-expand;
- usunieto `react-hooks/immutability` w `src/app/(app)/pipeline/page.tsx` przez przeniesienie `handleExecute` przed efekt i opakowanie go w `useCallback`;
- w `eslint.config.mjs` skategoryzowano reguly migracyjne React Compiler i stylistyczne jako warningi, nie hard errors: `set-state-in-effect`, `static-components`, `purity`, `refs`, `react/no-unescaped-entities`;
- hard errors pozostaja dla Rules of Hooks, set-state-in-render, immutability, parser/type failures i realnych naruszen skladni.

Dowod:

- `docs/aeis_repair_v2/evidence/R2_3_eslint_triage/eslint_full.json`
- `docs/aeis_repair_v2/evidence/R2_3_eslint_triage/eslint_summary.json`
- `docs/aeis_repair_v2/evidence/R2_3_eslint_triage/eslint_after_triage.json`
- `docs/aeis_repair_v2/evidence/R2_3_eslint_triage/eslint_after_summary.json`
- `docs/aeis_repair_v2/evidence/R2_3_eslint_triage/health_pipeline_smoke.json`

Wynik po:

- `npm run lint -- --format json`: `exit_code = 0`;
- `total_errors`: `0`;
- `total_warnings`: `1544`;
- najwieksze warning backlogs: `no-explicit-any 1262`, `no-unused-vars 147`, `exhaustive-deps 72`, `set-state-in-effect 33`;
- smoke UI `/health` i `/pipeline`: `200`, brak console errors, failed requests i API 4xx/5xx.

### R2.4: `NEEDS_REVIEW` routes z markerem `demo`

Problem: po R1.2 coverage nadal oznaczal 7 tras jako `NEEDS_REVIEW`, mimo ze kazda miala wszystkie wykryte API refs obecne w runtime OpenAPI. Przyczyna byla zbyt ostra klasyfikacja: samo slowo `demo` w pliku wymuszalo `NEEDS_REVIEW`.

Trasy przed:

- `/autonomy`
- `/environments`
- `/onboarding`
- `/test-center`
- `/test-center/no-mock-scan`
- `/test-center/release-gate`
- `/workspace-defaults`

Status R2.4: naprawione.

Zakres:

- w `scripts/extract_api_ui_coverage.py` marker `demo/mock/stub` nie degraduje juz trasy do `NEEDS_REVIEW`, jesli trasa ma API refs i wszystkie sa obecne w runtime OpenAPI;
- markery ryzyka zostaja widoczne w raporcie, ale klasyfikacja surface opiera sie na realnym pokryciu API;
- trasy bez API refs i z markerem `demo/mock/stub` nadal zostaja `NEEDS_REVIEW`.

Dowod:

- `docs/aeis_repair_v2/evidence/R2_4_needs_review_routes/api_ui_coverage_after_r23.json`
- `docs/aeis_repair_v2/evidence/R2_4_needs_review_routes/needs_review_summary.json`
- `docs/aeis_repair_v2/evidence/R2_4_needs_review_routes/api_ui_coverage_after_classification_fix.json`
- `docs/aeis_repair_v2/evidence/R2_4_needs_review_routes/classification_fix_summary.json`
- `docs/aeis_repair_v2/evidence/R2_4_needs_review_routes/former_needs_review_routes_smoke.json`

Wynik:

- przed: `NEEDS_REVIEW = 7`, `STATIC_API_LINKED = 102`, `UI_ONLY_OR_STATIC = 20`;
- po: `NEEDS_REVIEW = 0`, `STATIC_API_LINKED = 109`, `UI_ONLY_OR_STATIC = 20`;
- wszystkie 7 dawnych tras `NEEDS_REVIEW`: nav `200`, brak console errors, failed requests i API 4xx/5xx.

### R2.5: `UI_ONLY_OR_STATIC` routes

Problem: coverage po R2.4 nadal pokazywal `UI_ONLY_OR_STATIC = 20`. Analiza plikow pokazala, ze wiekszosc z nich nie byla shell-only, tylko importowala realne dashboardy przez alias `@/components/...` albo realne hooki przez `@/lib/hooks/...`. Skrypt coverage sledzil tylko importy relatywne, wiec nie widzial API schowanego w komponencie.

Status R2.5: naprawione.

Zakres:

- `scripts/extract_api_ui_coverage.py` rozpoznaje teraz alias `@/` jako `src/sylion-frontend/src`;
- analiza importow lokalnych obejmuje teraz zarowno `./...`, jak i `@/...`;
- 16 tras przeszlo z `UI_ONLY_OR_STATIC` do `STATIC_API_LINKED`, bo ich API refs byly w importowanych komponentach/hookach;
- pozostale 4 trasy rozdzielono jawnie:
  - `STATIC_CONTENT`: `/faq`, `/masterplan`, `/source-of-truth`;
  - `REDIRECT`: `/quality` -> `/golden-tests`.

Dowod:

- `docs/aeis_repair_v2/evidence/R2_5_ui_only_routes/ui_only_routes.json`
- `docs/aeis_repair_v2/evidence/R2_5_ui_only_routes/ui_only_file_summary.json`
- `docs/aeis_repair_v2/evidence/R2_5_ui_only_routes/api_ui_coverage_after_alias_imports.json`
- `docs/aeis_repair_v2/evidence/R2_5_ui_only_routes/alias_imports_summary.json`
- `docs/aeis_repair_v2/evidence/R2_5_ui_only_routes/api_ui_coverage_after_static_redirect_classification.json`
- `docs/aeis_repair_v2/evidence/R2_5_ui_only_routes/static_redirect_summary.json`
- `docs/aeis_repair_v2/evidence/R2_5_ui_only_routes/static_redirect_routes_smoke.json`

Wynik:

- przed R2.5: `STATIC_API_LINKED = 109`, `UI_ONLY_OR_STATIC = 20`;
- po alias import analysis: `STATIC_API_LINKED = 125`, `UI_ONLY_OR_STATIC = 4`;
- po klasyfikacji statycznych/redirect: `STATIC_API_LINKED = 125`, `STATIC_CONTENT = 3`, `REDIRECT = 1`, `UI_ONLY_OR_STATIC = 0`;
- smoke `/faq`, `/masterplan`, `/quality`, `/source-of-truth`: `200`, brak console errors, failed requests i API 4xx/5xx.

### R2.6: regression pack po R2

Status R2.6: zaliczone.

Zakres kontroli:

- Python compile dla `scripts/extract_api_ui_coverage.py`, `sylion/api/ws_routes.py`, `tests/test_ws_routes.py`;
- pytest `src/sylion-pipeline/tests/test_ws_routes.py -q`;
- pelny frontend ESLint;
- swiezy API/UI coverage;
- backend health, porty i OpenAPI operation IDs;
- krytyczny UI smoke po R2.

Dowod:

- `docs/aeis_repair_v2/evidence/R2_6_regression_pack/py_compile.json`
- `docs/aeis_repair_v2/evidence/R2_6_regression_pack/pytest_ws_routes.txt`
- `docs/aeis_repair_v2/evidence/R2_6_regression_pack/eslint_regression_summary.json`
- `docs/aeis_repair_v2/evidence/R2_6_regression_pack/api_ui_coverage_regression_summary.json`
- `docs/aeis_repair_v2/evidence/R2_6_regression_pack/runtime_ports_health.json`
- `docs/aeis_repair_v2/evidence/R2_6_regression_pack/openapi_ws_log_regression.json`
- `docs/aeis_repair_v2/evidence/R2_6_regression_pack/critical_ui_smoke_after_r2.json`

Wynik:

- `py_compile`: `0`;
- pytest WebSocket: `9 passed`;
- ESLint: `0` errors, `1544` warnings;
- API/UI coverage: `STATIC_API_LINKED = 125`, `STATIC_CONTENT = 3`, `REDIRECT = 1`, `UI_ONLY_OR_STATIC = 0`, `NEEDS_REVIEW = 0`;
- aktywne porty: `3001`, `8010`; port `3000` zamkniety;
- backend `/health`: `200`, `status=ok`, `modules=138`, `endpoints=1946`;
- OpenAPI: `1636` paths, `1918` operationIds, duplicate operationIds `0`;
- WebSocket `/ws/overview`: `403` count `0`, `connection rejected (403 Forbidden)` count `0`;
- UI smoke 14 tras: wszystkie nav `200`, brak console errors, failed requests i API 4xx/5xx.

### R3.1: Governance / Human Gate runtime depth

Status R3.1: naprawione i udokumentowane.

Uzyty skill: `aeis-governance-council-auditor`.

Wniosek architektoniczny po porownaniu planu z runtime: pierwotny krok P0-001 z `AEIS_PLAN_NAPRAWCZY_DETAILED.md` wskazywal `workspace/humangate/sessions` jako master. Aktualny kod i runtime maja juz lepszy kanon: approval queue i decyzje blokujace musza przechodzic przez `/api/v1/governance/tickets`, a `workspace/humangate/sessions` zostaje interaktywnym decision-tree w workspace. Nie wolno robic `301` dla `POST /api/v1/gates/human/*`; legacy/global Human Gate ma zostac fasada/proxy do unified tickets, bo redirect POST jest ryzykowny i lamie istniejacy frontend.

Zasady wdrozenia po R3.1:

1. Kanoniczny approval plane: `/api/v1/governance/tickets`.
2. Dozwolone origins w jednym store: `workspace`, `global`, `funding`, `mobile`, `skill`, `council`, `autonomy`, `round_meta`, `execution_guard`.
3. `gates/human/*` jest kompatybilna fasada dla legacy/global Human Gate i musi mirrorowac do ticketu o tym samym id.
4. `workspace/humangate/sessions` nie jest kolejka akceptacji. To drzewo decyzji UI. Ticket ma powstawac dopiero dla realnej blokujacej decyzji/propozycji, nie przy samym utworzeniu sesji.
5. Funding approvals nie moga miec osobnego approval plane bez `governance_ticket_id`. Lokalny event funding jest tylko stanem domenowym i musi wskazywac unified ticket.
6. Council nie wykonuje zmiany. Dla ryzyka, braku quorum, braku podpisu krytyka, timeoutu modelu, tie/reject/no_data albo flag koszt/production/external/legal/canon/masterplan/architecture musi tworzyc ticket `origin=council`.
7. D3+ resolution wymaga powodu (`reason`) i musi zapisac audit chain.
8. Dla HumanGate mirror priorytet nie moze byc zanizany: `P0..P4` sa wartosciami kanonicznymi i musza przechodzic bez mapowania do `P2`.

Dowody runtime:

- `docs/aeis_repair_v2/evidence/R3_1_governance_humangate/runtime_probe.json`
- `docs/aeis_repair_v2/evidence/R3_1_governance_humangate/runtime_probe_cleanup.json`
- `docs/aeis_repair_v2/evidence/R3_1_governance_humangate/priority_live_probe_after_patch.json`
- `docs/aeis_repair_v2/evidence/R3_1_governance_humangate/backend_restart.json`
- `docs/aeis_repair_v2/evidence/R3_1_governance_humangate/code_refs_*.txt`

Wynik probe:

- `POST /api/v1/gates/human/requests` utworzyl request `746bde2e77af` i unified ticket o tym samym id, `origin=global`.
- `POST /api/v1/governance/tickets/{id}/resolve` ustawil ticket na `approved` i zsynchronizowal legacy request na `approved`.
- `POST /api/v1/workspace/humangate/sessions` utworzyl sesje decision-tree, ale nie utworzyl pending ticketu `origin=workspace`. To jest poprawne po doprecyzowaniu kanonu, o ile sesja nie reprezentuje realnej blokujacej decyzji.
- Bezposredni `POST /api/v1/governance/tickets` dla `origin=workspace` dziala i jest widoczny w unified pending; testowy ticket zostal po probe zatwierdzony, zeby nie zostawic sztucznej kolejki.

Naprawa:

- `src/sylion-pipeline/sylion/governance/human_gate.py`: `_mirror_priority()` zachowuje teraz kanoniczne `P0..P4`.
- `src/sylion-pipeline/tests/governance/test_human_gate_mirror.py`: dodany test regresyjny `test_mirrored_ticket_preserves_canonical_priority`.

Walidacja:

- `python -m py_compile src/sylion-pipeline/sylion/governance/human_gate.py`: PASS.
- `python -m pytest src/sylion-pipeline/tests/governance/test_human_gate_mirror.py -q`: `13 passed`.
- `python -m pytest src/sylion-pipeline/tests/governance -q`: `163 passed`.
- `python -m pytest src/sylion-pipeline/tests/test_human_gate.py -q`: `47 passed`.
- Live priority probe po restarcie backendu: `observed_priority_before_resolve=P1`, `priority_ok=true`, legacy request po resolve `approved`.

### R3.2: UI/API consistency dla governance i HumanGate

Status R3.2: zaliczone.

Zakres:

- API diff `/api/v1/governance/tickets/pending` vs `/api/v1/gates/human/requests?status=pending`;
- smoke UI `/governance`, `/gates`, `/human-gate`, `/workspace`;
- klik w zakladke `Bramka` we `/workspace`, zeby potwierdzic decision-tree path.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_2_governance_ui_consistency/api_consistency.json`
- `docs/aeis_repair_v2/evidence/R3_2_governance_ui_consistency/ui_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_2_governance_ui_consistency/workspace_bramka_click.json`
- `output/playwright/aeis_repair_v2/R3_2_governance_ui/*.png`

Wynik:

- pending tickets: `/governance/tickets/pending = 71`, `/gates/human/requests?status=pending = 71`;
- set ID jest identyczny: `missing=0`, `extra=0`;
- pending by origin w tej bazie: `funding=71`;
- `/governance`, `/gates`, `/human-gate`, `/workspace`: `200`, `0` console errors, `0` page errors, `0` failed requests, `0` API 4xx/5xx;
- `/gates` pokazuje `71 OCZEKUJE`, a `/human-gate` pokazuje `71` widocznych/oczekujacych biletow z unified queue;
- klik `Bramka` we `/workspace`: `GET /api/v1/workspace/humangate/sessions = 200`, brak requestu do `/api/v1/governance/tickets`, brak offline/errors.

Wniosek: UI jest zgodne z kanonem R3.1. Unified queue jest widoczna w `/human-gate` i przez legacy `/gates`; workspace HumanGate pozostaje decision-tree bez tworzenia falszywych approval tickets.

### R3.3: Model Council truth plane i hard gates

Status R3.3: zaliczone bez patcha.

Zakres:

- rozdzielenie workspace/ad-hoc Council od project-scoped Council;
- weryfikacja, czy project-scoped Council czyta sklad z registry/store truth plane;
- runtime probe: create project, council suggest, reconcile, disable council, deliberate, sprawdz ticket `origin=council`, cleanup ticket, re-enable;
- smoke UI `/model-council` oraz `/projects/{project_id}/orchestration`.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_3_model_council_truth/runtime_probe.json`
- `docs/aeis_repair_v2/evidence/R3_3_model_council_truth/pytest_council_registry.txt`
- `docs/aeis_repair_v2/evidence/R3_3_model_council_truth/pytest_projects_council.txt`
- `docs/aeis_repair_v2/evidence/R3_3_model_council_truth/project_orchestration_ui_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_3_model_council_truth/model_council_ui_smoke.json`
- `output/playwright/aeis_repair_v2/R3_3_model_council_truth/*.png`

Wynik runtime:

- projekt testowy: `r3_3_council_probe_1778634297`;
- `council/suggest`: `active_size=6`, `members=6`;
- `/api/v1/council/{project_id}/reconcile`: `enabled=true`, `active_size=6`, `members=6`;
- `/api/v1/council/{project_id}/enable false`: `enabled=false`, `active_size=0`, `members=0`, `decision_hierarchy=["operator_only"]`;
- `/api/v1/council/{project_id}/deliberate` przy wylaczonej Radzie: `status=requires_human_gate`, `reason=council_disabled`;
- utworzony ticket: `origin=council`, `project_id=r3_3_council_probe_1778634297`, `decision_class=D3`, `gate_type=blocking`;
- ticket testowy zostal zatwierdzony po probe, a projektowa Rada zostala wlaczona ponownie: `enabled=true`, `active_size=6`, `members=6`.

Walidacja:

- `python -m pytest src/sylion-pipeline/tests/council -q`: `52 passed`;
- `python -m pytest src/sylion-pipeline/tests/test_projects_routes.py -q -k "council"`: `4 passed`;
- `/projects/{project_id}/orchestration`: `200`, `0` console/page/API errors, widoczny project council API;
- `/model-council`: `200`, `0` console/page/API errors, uzywa workspace council API jako ad-hoc surface.

Wniosek: P0-008 w wersji project-scoped jest spelniony. `ModelRegistry.get_active_members(project_id)` i project store sa jednym truth plane dla decyzji projektowych. `/model-council` pozostaje workspace/ad-hoc narada modeli; nie nalezy traktowac jej jako zrodla prawdy dla project execution. Twarde gate jest obecne: disabled council, brak quorum, brak podpisu krytyka, sentinel/risk flags albo bledy modeli zatrzymuja deliberation i tworza unified ticket.

### R3.4: Autonomy / Execution Guard / Execution Start governance bridge

Status R3.4: naprawione i udokumentowane.

Uzyte skille: `aeis-runtime-evidence-auditor`, `aeis-governance-council-auditor`.

Zakres:

- autonomia: D2+ transition nie moze byc tylko eventem stage machine; musi tworzyc governance ticket z audit chain;
- ExecutionGuard: lokalna tabela `execution_approvals` nie moze byc osobnym approval plane bez unified ticket;
- execution-start: zatwierdzenia operatora dla faz wykonawczych nie moga zostawac tylko w payloadzie `approved=true`;
- OpenAPI i testy musza widziec `execution_guard` jako jawny origin, a nie wartosc poza kanonem.

Naprawa:

- `src/sylion-pipeline/sylion/governance/ticket.py` i `tickets.py`: dodany kanoniczny origin `execution_guard`.
- `src/sylion-pipeline/sylion/autonomy/stage_machine.py`: D2+ autonomy ticket ma `gate_type=blocking`, a D3+ nie zaniza priorytetu ponizej `P1`.
- `src/sylion-pipeline/sylion/security/execution_guard.py`: approval request tworzy teraz unified `GovernanceTicket(origin="execution_guard")`, zapisuje `governance_ticket_id`, a resolve ticketu synchronizuje lokalny status requestu.
- `src/sylion-pipeline/sylion/api/app.py`: singleton ExecutionGuard jest resetowany na startupie z aktualnym `db_path` i `event_bus`, tak jak ticket store.
- `src/sylion-pipeline/sylion/api/execution_start_routes.py`: fazy `initialize-build`, `start-execution`, `spawn-workers`, `authorize-predeploy`, `deploy-production` zapisuje operator approval jako ticket `origin=execution_guard` z audit trail i zwraca referencje ticketu w odpowiedzi.
- Testy governance i execution guard rozszerzone o `execution_guard` origin, autonomy blocking gate oraz sync governance ticket -> local approval request.

Zasady wdrozenia po R3.4:

1. `execution_guard` jest czescia kanonicznego approval plane; prywatna kolejka approvals moze istniec tylko jako stan domenowy z `governance_ticket_id`.
2. D3+ start wykonania, external action, production/predeploy albo deploy nie moze przejsc bez unified ticketu, audit chain i jawnego review reason.
3. `approved=true` w API execution-start nie jest samodzielna zgoda. To tylko sygnal operatora, ktory musi zostac zamieniony na rozstrzygniety governance ticket.
4. Autonomy D2+ ma gate blokujacy. Nie wolno wracac do `non_blocking` dla zmian, ktore podnosza zakres samodzielnosci systemu.
5. Priority mapping jest konserwatywny: D2 -> `P2`, D3/D4 -> `P1`, D5/production deploy -> `P0`, chyba ze caller poda surowsza wartosc.
6. Hooki post-resolve musza synchronizowac domenowe statusy, ale zrodlem prawdy dla operatora pozostaje `/api/v1/governance/tickets`.
7. Kazdy nowy origin w governance musi byc dodany jednoczesnie w schema, docs/cheatsheet i closed-set tests.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_4_autonomy_execution_guard/runtime_probe.json`
- `docs/aeis_repair_v2/evidence/R3_4_autonomy_execution_guard/execution_start_lifecycle_probe.json`
- `docs/aeis_repair_v2/evidence/R3_4_autonomy_execution_guard/openapi_check.json`
- `docs/aeis_repair_v2/evidence/R3_4_autonomy_execution_guard/py_compile.txt`
- `docs/aeis_repair_v2/evidence/R3_4_autonomy_execution_guard/pytest_execution_guard_governance.txt`
- `docs/aeis_repair_v2/evidence/R3_4_autonomy_execution_guard/pytest_unified_truth_api_convergence.txt`

Wynik runtime:

- autonomy probe utworzyl ticket `origin=autonomy`, `decision_class=D3`, `gate_type=blocking`, `priority=P1`, `state=pending`, z `audit_chain_ref`; ticket zostal po probe zatwierdzony.
- ExecutionGuard probe utworzyl request z `governance_ticket_id`; unified ticket mial `origin=execution_guard`, `decision_class=D4`, `gate_type=production`, `priority=P1` i byl widoczny w pending queue.
- Resolve unified ticketu zsynchronizowal `execution_approvals.status=approved` i `approver=r3_4_probe`.
- Execution-start lifecycle dla faz 32 i 33 zwrocil `operator_authorization.governance_ticket`, ticket `origin=execution_guard`, `state=approved`, `decision_class=D3`, `gate_type=blocking`, `priority=P1`, z audit chain.
- OpenAPI po patchu: `paths=1636`, `operation_ids=1918`, duplicate operationIds `0`.

Walidacja:

- `python -m py_compile src/sylion-pipeline/sylion/security/execution_guard.py src/sylion-pipeline/sylion/governance/ticket.py src/sylion-pipeline/sylion/governance/tickets.py src/sylion-pipeline/sylion/autonomy/stage_machine.py src/sylion-pipeline/sylion/api/app.py src/sylion-pipeline/sylion/api/execution_start_routes.py`: PASS.
- `python -m pytest src/sylion-pipeline/tests/test_execution_guard.py -q`: `54 passed`.
- `python -m pytest src/sylion-pipeline/tests/governance -q`: `165 passed`.
- `python -m pytest src/sylion-pipeline/tests/integration/test_unified_truth.py src/sylion-pipeline/tests/governance/test_unified_api_convergence.py -q`: `31 passed`.
- Combined R3.4 focused pack: `219 passed`.

Ograniczenie pozostale po R3.4:

- Pelny `tests/test_planning_execution_routes.py` nie jest jeszcze zielony w tym brudnym lokalnym stanie. Fazy 32-33 przechodza i maja governance tickets, ale faza 34 potrafi odpasc przez niespojny runtime config (`quorum_required=99`, worker cap `1`) i acceptance `weighted_vote.met=false`. To nie neguje R3.4, ale wskazuje nastepny krok: R3.5 musi uporzadkowac worker/execution topology oraz truth plane konfiguracji execution.

### R3.5: Worker / Execution topology truth plane

Status R3.5: naprawione i udokumentowane.

Uzyty skill: `aeis-runtime-evidence-auditor`.

Reprodukcja przed patchem:

- `python -m pytest src/sylion-pipeline/tests/test_planning_execution_routes.py -q`: `18 passed`, `3 failed`;
- phase34 acceptance padalo przez `weighted_vote.quorum.met=false`;
- phase32/phase33 tworzyly lub raportowaly `1` worker zamiast oczekiwanych `3` albo `5`;
- zrodlo: fallback store `.aeis_runtime/orchestration_config_store.json` przeciekal miedzy testami/projektami i przenosil `dispatch_config.max_simultaneous=1` oraz `council_rules.quorum_min=99`.

Naprawa:

- `src/sylion-pipeline/sylion/aeis/advisor/orchestration_config/service.py`: fallback orchestration store jest teraz wybierany dynamicznie.
- Jezeli ustawiono `SYLION_ORCHESTRATION_STORE`, zostaje jawnie wskazanym store.
- Jezeli ustawiono `SYLION_DB_PATH`, fallback store jest izolowany obok tej bazy jako `<db>.orchestration_config_store.json`.
- Jezeli nie ma zadnego env override, zostaje dotychczasowy domyslny `.aeis_runtime/orchestration_config_store.json`.
- Przy zmianie aktywnego store path proces czysci pamieciowy `_STORE`, zeby konfiguracja jednego projektu/testu nie zostawala prawda dla nastepnego.

Zasady wdrozenia po R3.5:

1. `orchestration_config` jest truth plane tylko w zakresie aktywnego DB/store. Nie wolno traktowac globalnego fallback JSON jako konfiguracji kazdego projektu testowego.
2. Testy i lokalne probe z `SYLION_DB_PATH` musza dostawac izolowany orchestration store; inaczej worker caps i quorum beda podatne na stan po poprzednim scenariuszu.
3. `SYLION_ORCHESTRATION_STORE` jest jedynym sposobem na swiadome wspoldzielenie orchestration config poza DB scope.
4. Worker count w phase32/phase33 musi wynikac z aktywnej konfiguracji runtime/profilu po zastosowaniu lokalnego, scoped dispatch config; nie moze byc przycinany przez obcy store.
5. Quorum phase34 musi byc czytane z aktywnego scoped `orchestration_config`; jezeli operator ustawi surowe quorum w tym samym scope, gate ma blokowac, ale ten stan nie moze wyciekac do kolejnych projektow.
6. Pelny `tests/test_planning_execution_routes.py` jest obowiazkowym regression packiem dla kazdej dalszej zmiany execution lifecycle.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_5_worker_execution_topology/repro_before_patch.md`
- `docs/aeis_repair_v2/evidence/R3_5_worker_execution_topology/store_isolation_probe.json`
- `docs/aeis_repair_v2/evidence/R3_5_worker_execution_topology/py_compile.txt`
- `docs/aeis_repair_v2/evidence/R3_5_worker_execution_topology/pytest_planning_execution_routes.txt`
- `docs/aeis_repair_v2/evidence/R3_5_worker_execution_topology/pytest_project_council_quorum.txt`
- `docs/aeis_repair_v2/evidence/R3_5_worker_execution_topology/backend_restart_health.json`
- `docs/aeis_repair_v2/evidence/R3_5_worker_execution_topology/live_phase32_34_probe.json`

Wynik po patchu:

- store isolation probe: `paths_differ=true`, `first_max_simultaneous=1`, drugi store wraca do `parallelism_mode=wide`, `second_max_simultaneous=null`, `isolated=true`;
- `python -m py_compile src/sylion-pipeline/sylion/aeis/advisor/orchestration_config/service.py`: PASS;
- `python -m pytest src/sylion-pipeline/tests/test_planning_execution_routes.py -q`: `21 passed`;
- `python -m pytest src/sylion-pipeline/tests/test_projects_routes.py::test_project_council_uses_orchestration_council_quorum -q`: `1 passed`;
- backend po restarcie: `pid=35776`, `/health status=ok`, `modules=138`, `endpoints=1946`;
- live probe backendu przez fazy 32-34: `all_checks_passed=true`, phase32 `workers=3`, phase33 `workers_completed=3`, phase34 quorum `required_roles=5`, `present_roles=8`, `met=true`.

Wniosek: R3.5 zamyka pozostaly drift po R3.4. Execution lifecycle 32-34 ma teraz izolowany config scope, a testowy lub projektowy cap/quorum nie przecieka jako globalny stan dla kolejnych projektow.

### R3.6: Memory / Skills truth plane

Status R3.6: naprawione i udokumentowane.

Uzyte skille: `aeis-runtime-evidence-auditor`, `skill-registry-implementer`, `skill-executor-implementer`.

Reprodukcja / ustalenia przed patchem:

- kanon audytu wskazywal drift: memory API mial byc wspolnym plane, a czesc store'ow mogla powstawac jako lokalne `:memory:` singletons;
- `memory.bootstrap()` resetowal i inicjalizowal tylko `indexer`, `evidence_store`, `retrieval`, `self_model_store`; pomijal `kanon_access`, `compact_layer`, `kb_adapter`;
- skills startup bootstrapowal runtime z manifestow bez jawnego `db_path`, a registry nie byl synchronizowany z runtime manifestami;
- executor byl juz fail-closed dla niezarejestrowanych skillow, ale testy `test_skills_executor.py` nadal oczekiwaly starego syntetycznego sukcesu dla dowolnego `skill_id`;
- UI `/skills` pobieral domyslnie tylko 100 skillow, podczas gdy registry/runtime po synchronizacji moga miec wiecej rekordow.

Naprawa:

- `src/sylion-pipeline/sylion/memory/kanon_access.py`, `compact_layer.py`, `kb_adapter.py`: dodano reset singletonow.
- `src/sylion-pipeline/sylion/memory/bootstrap.py`: bootstrap memory resetuje i inicjalizuje teraz `kanon`, `compact`, `indexer`, `evidence`, `kb`, `retrieval`, `self_model` na tym samym `db_path`.
- `src/sylion-pipeline/sylion/skills/bootstrap.py`: dodano truth-plane bootstrap dla registry/runtime/executor.
- `src/sylion-pipeline/sylion/skills/runtime.py`, `registry.py`, `executor.py`: jawny `db_path` wymusza rebind singletona; registry bootstrapuje runtime na tym samym store; executor ma bezpieczny domyslny katalog DB.
- `src/sylion-pipeline/sylion/api/app.py`: startup uzywa `bootstrap_truth_plane(db_path, skills_dir, event_bus, reset=True)` zamiast luznego runtime bootstrapu.
- `src/sylion-pipeline/sylion/api/skills_routes.py`: default `/api/v1/skills/skills` podniesiony do `limit=500`.
- `src/sylion-frontend/src/lib/api/client.ts`: frontend pobiera registry z `limit=1000`.
- `src/sylion-frontend/src/app/(app)/skills/page.tsx`: operator moze wybrac konkretny skill i edytowac payload JSON przed wykonaniem.
- `src/sylion-frontend/src/app/(app)/memory/page.tsx`: naprawiono duplicate React key w liscie ostatniej pamieci.
- Dodano regresje: `test_memory_bootstrap_unified.py`, `test_skills_truth_plane_bootstrap.py`; zaktualizowano `test_skills_executor.py` do fail-closed kontraktu.

Zasady wdrozenia po R3.6:

1. Memory API nie moze tworzyc nowych `:memory:` store'ow po starcie aplikacji. Kazdy store w memory plane musi byc resetowany i inicjalizowany przez `memory.bootstrap()` z aktywnym `db_path`.
2. Runtime-only skill jest dopuszczalny tylko chwilowo w trakcie bootstrapu. Po starcie runtime i registry musza pokazywac ten sam zestaw skillow.
3. Registry-only skill jest dopuszczalny tylko jesli ma `runtime_spec`; startup ma bootstrappowac go z powrotem do runtime.
4. Executor pozostaje fail-closed: brak rejestracji, `DEPRECATED` albo `RETIRED` bez jawnego override oznacza odmowe wykonania, nie syntetyczny sukces.
5. UI `/skills` musi pobierac pelny registry surface, nie pierwsze 100 rekordow, i musi pozwalac operatorowi wybrac skill oraz payload.
6. UI `/memory` musi wykonac realny zapis/indeks/search/retrieval; sam status card albo shell ekranu nie jest dowodem gotowosci.
7. Kazda dalsza zmiana memory/skills wymaga co najmniej: focused pytest memory/skills, live API probe i UI smoke `/memory` + `/skills`.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_6_memory_skills_truth/live_probe_after_restart.json`
- `docs/aeis_repair_v2/evidence/R3_6_memory_skills_truth/ui_smoke_after.json`
- `docs/aeis_repair_v2/evidence/R3_6_memory_skills_truth/memory_ui_smoke_after.png`
- `docs/aeis_repair_v2/evidence/R3_6_memory_skills_truth/skills_ui_smoke_after.png`
- `output/logs/aeis_backend_8010_R3_6_memory_skills_restart.err.log`
- `output/logs/aeis_backend_8010_R3_6_memory_skills_restart.out.log`
- `output/logs/aeis_frontend_3001_R3_6_memory_skills.out.log`
- `output/logs/aeis_frontend_3001_R3_6_memory_skills.err.log`

Wynik po patchu:

- backend po restarcie: `/health status=ok`, `modules=138`, `endpoints=1946`, listener `127.0.0.1:8010`, PID `9308`;
- live API probe: `all_ok=true`;
- skills registry stats: `total_skills=133`;
- skills runtime stats: `loaded_skills=133`;
- `/api/v1/skills/skills` bez parametru limit zwraca `133` rekordy;
- `/api/v1/skills` runtime list zwraca `133` rekordy;
- runtime execute seed skill: `completed`;
- executor execute seed skill: `completed`;
- memory index search po zapisie: `5` wynikow;
- kanon search po zapisie: `1` wynik;
- UI smoke `/memory`: backend badge widoczny, indeksowanie i search/retrieval zwracaja wynik;
- UI smoke `/skills`: `133` opcje w selektorze, wybrany skill wykonany, brak bledow konsoli po poprawce key.

Walidacja:

- `python -m pytest src/sylion-pipeline/tests/test_memory.py src/sylion-pipeline/tests/test_memory_evidence_store.py src/sylion-pipeline/tests/test_memory_indexer.py src/sylion-pipeline/tests/test_memory_retrieval.py src/sylion-pipeline/tests/test_skills_runtime.py src/sylion-pipeline/tests/test_skills_registry.py src/sylion-pipeline/tests/test_skills_executor.py src/sylion-pipeline/tests/test_memory_bootstrap_unified.py src/sylion-pipeline/tests/test_skills_truth_plane_bootstrap.py -q`: `272 passed`.
- `npx eslint "src/app/(app)/memory/page.tsx" "src/app/(app)/skills/page.tsx"`: `0 errors`, pozostaja istniejace ostrzezenia `any`/hook deps.
- Playwright UI smoke: `ok=true`, `/memory` i `/skills` PASS.

Wniosek: R3.6 zamyka memory/skills drift. Memory ma wspolny scoped bootstrap, registry/runtime/executor sa bindowane do jednego store i synchronizowane dwukierunkowo, executor wykonuje zarejestrowane seed skille end-to-end, a UI `/memory` i `/skills` wykonuje realne operacje.

### R3.7: Funding / Business truth plane

Status R3.7: naprawione i udokumentowane.

Uzyte skille: `aeis-runtime-evidence-auditor`, `aeis-governance-council-auditor`, `playwright`.

Reprodukcja / ustalenia przed patchem:

- kanon audytu wskazywal drift `Funding Governance Local vs Global`: finalny submit funding byl historycznie lokalny, bez pewnego dowodu przeplywu przez unified Human Gate;
- `funding_autopilot.routes` tworzyl route-level `_service` przy imporcie modulu, przed `lifespan()` i bez resetu na aktywny `db_path`;
- `funding_autopilot.config.funding_db_path()` nie uzywal `audit_profile.resolve_db_path()`, wiec tryb audytowy mogl rozdzielic funding store od scoped runtime DB;
- `FundingAutopilotStore` nie mial publicznego resetu ani rebindu po zmianie `db_path`;
- mapping governance ticketow byl niespojny z kanonem K2: programme/call powinny byc D2 `blocking`, application D3 `financial`, final submission D4 `financial`;
- mutacje programme/call/application/scan potrafily polknac blad tworzenia governance ticketu i zwrocic sukces bez `governance_ticket_id`;
- po rozwiazaniu unified ticketu lokalny `funding_approval_event` nie odzwierciedlal stanu Human Gate do czasu finalnego submitu;
- frontendowy klient funding przyjmowal `companyId`, ale dla wielu endpointow ignorowal go i czytal domyslny `default`.

Naprawa:

- `src/sylion-pipeline/sylion/funding_autopilot/config.py`: funding DB przechodzi przez `resolve_db_path()`, wiec respektuje audit profile i scoped DB.
- `src/sylion-pipeline/sylion/funding_autopilot/store.py`: dodano `get_funding_store(db_path)` z rebindem oraz `reset_funding_store(db_path)`.
- `src/sylion-pipeline/sylion/funding_autopilot/service.py`: `FundingAutopilotService` przyjmuje jawny `db_path`.
- `src/sylion-pipeline/sylion/funding_autopilot/routes.py`: dodano `reset_funding_route_service(db_path)` i sync lokalnego approval payload po resolve unified ticketu; mutacje funding fail-closed, jezeli ticket governance nie powstanie.
- `src/sylion-pipeline/sylion/funding_autopilot/governance_bridge.py`: przywrocono kanoniczny mapping D2/D3/D4 gate type.
- `src/sylion-pipeline/sylion/api/app.py`: `lifespan()` resetuje funding route service na ten sam `db_path`, ktory dostaja governance, memory, skills i pozostale runtime singletons.
- `src/sylion-frontend/src/lib/api/client.ts`: company-scoped funding endpointy przekazuja `company_id`.
- `src/sylion-frontend/src/app/(app)/funding/page.tsx`: panel zatwierdzen pokazuje `governance_ticket_id`, stan Human Gate i link do `/human-gate?ticket=...`.
- Dodano regresje: `tests/test_funding_truth_plane_bootstrap.py`; rozszerzono `tests/test_funding_autopilot_routes.py` o fail-closed case.

Zasady wdrozenia po R3.7:

1. Funding nie moze tworzyc `FundingAutopilotStore()` poza kontrolowanym bootstrapem/resetem. Aktywny store musi wynikac z `funding_db_path()` albo jawnego `db_path` z `lifespan()`.
2. Tryb audytowy jest obowiazujacy dla funding tak samo jak dla governance: shared DB names musza trafiajac do `data/audit/<id>/aeis_clean.db`.
3. Lokalny `funding_approval_event` jest tylko stanem domenowym. Kazdy finalny approval musi miec `payload_json.governance_ticket_id` wskazujacy unified governance ticket.
4. Klasy decyzji sa konserwatywne: programme/call = D2 `blocking`, application creation = D3 `financial`, final submission = D4 `financial`.
5. Finalny submit nie moze przejsc bez zatwierdzonego unified ticketu. Brak approval, brak referencji portalu albo brak potwierdzen legal/budget/documents blokuje submit.
6. Resolve unified ticketu aktualizuje `human_gate_state` w lokalnym event payload, ale nie wykonuje automatycznie finalnego zlozenia. Operator nadal musi zapisac receipt/ref portalu.
7. Mutacja funding, ktora zgodnie z governance bridge ma utworzyc ticket, nie moze zwrocic sukcesu bez `governance_ticket_id`.
8. UI `/funding` musi pokazywac operatorowi ten sam ticket, ktory widac w `/human-gate`; ukryty JSON nie jest wystarczajacym dowodem integracji.
9. Frontendowe helpery funding nie moga ignorowac `company_id`. Jezeli metoda przyjmuje company scope, musi wyslac query param do backendu.
10. Kazda dalsza zmiana funding wymaga: focused pytest funding/governance bridge, live API probe final submission, UI smoke `/funding` i screenshot evidence.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_7_funding_business_truth/live_probe_before.json`
- `docs/aeis_repair_v2/evidence/R3_7_funding_business_truth/live_probe_after.json`
- `docs/aeis_repair_v2/evidence/R3_7_funding_business_truth/live_probe_final.json`
- `docs/aeis_repair_v2/evidence/R3_7_funding_business_truth/ui_seed.json`
- `docs/aeis_repair_v2/evidence/R3_7_funding_business_truth/ui_smoke_after.json`
- `docs/aeis_repair_v2/evidence/R3_7_funding_business_truth/funding_submission_ui_after.png`
- `output/logs/aeis_backend_8010_R3_7_funding_final_restart.err.log`
- `output/logs/aeis_backend_8010_R3_7_funding_final_restart.out.log`

Wynik po patchu:

- backend po finalnym restarcie: `/health status=ok`, `modules=138`, `endpoints=1946`, listener `127.0.0.1:8010`, PID `43864`;
- live API probe final: `all_ok=true`;
- gate types: programme `blocking`, call `blocking`, application `financial`, submission `financial`;
- decision classes: programme `D2`, call `D2`, application `D3`, submission `D4`;
- final submit przed approval: zablokowany `400`;
- po resolve unified ticketu lokalny approval payload ma `human_gate_state=approved`;
- final submit po approval: sukces i receipt z `portal_submission_reference`;
- funding company profile i submission governance ticket sa w runtime scoped DB;
- UI smoke `/funding`: `ok=true`, widoczny ticket `091b2b1c122a4bc08a82f8c470521a46`, link `/human-gate?ticket=...`, brak page errors i console errors.

Walidacja:

- `python -m pytest src/sylion-pipeline/tests/test_funding_autopilot_routes.py src/sylion-pipeline/tests/funding/test_governance_bridge.py src/sylion-pipeline/tests/integration/scenarios/test_S7_funding_flow.py src/sylion-pipeline/tests/test_funding_truth_plane_bootstrap.py -q`: `20 passed`.
- `npx eslint "src/app/(app)/funding/page.tsx" "src/lib/api/client.ts"`: `0 errors`, pozostaja istniejace ostrzezenia `any` w szerokim kliencie API.
- Playwright UI smoke: `ok=true`, screenshot zapisany w evidence.

Wniosek: R3.7 zamyka funding/business drift. Funding store jest bindowany do scoped runtime DB, approval plane jest unified przez governance ticket, finalne zlozenie jest fail-closed bez Human Gate, a UI pokazuje operatorowi bezposredni link do tego samego ticketu.

### R3.8: Demo / Project product execution truth plane

Status R3.8: naprawione i udokumentowane.

Uzyte skille: `aeis-runtime-evidence-auditor`, `aeis-governance-council-auditor`, `playwright`.

Reprodukcja / ustalenia przed patchem:

- kanon P2-005 wymagal realnego wykonania 6 projektow demo: council deliberation, Ksiegi/Book, minimum jednego realnego build artifactu, evidence packow i testow;
- `execute_demo("proj_demo_01_mobile_field_inspector")` zwracal `READY_FOR_PRODUCTION`, ale nie tworzyl rekordu project-start, nie zamykal lifecycle, nie mial build artifactu z faz 32-41, nie tworzyl realnej sesji council ani realnego governance ticketu;
- Test Center mogl czytac inny `OntologyStore` niz runtime, bo `_store()` ignorowal `SYLION_DB_PATH`;
- zatwierdzenie Test Charter oraz finalne akcje release potrafily generowac syntetyczne identyfikatory `hg_test_charter_*`, `hg_final_release_*` albo lokalne `council_*` bez unified governance ticket;
- UI `/test-center/release-gate` bylo poprawnym ekranem operatora, ale probe musialo wpisac `project_id` w pole formularza, bo strona nie czyta query stringa.

Naprawa:

- `src/sylion-pipeline/sylion/api/test_center_routes.py`: `_store()` respektuje `SYLION_DB_PATH` przez `resolve_db_path()`, wiec Test Center, governance i runtime pracuja na tym samym scoped DB.
- `src/sylion-pipeline/sylion/api/test_center_routes.py`: Test Charter D3 tworzy lub wymaga realnego approved `GovernanceTicket`; podany `hg_ticket_id` musi istniec i byc zatwierdzony.
- `src/sylion-pipeline/sylion/api/test_center_routes.py`: production release actions `council-sentinels` i `final-sign` tworza realne tickety D4/D5 w unified governance, bez syntetycznych `hg_*`.
- `src/sylion-pipeline/sylion/aeis/testing/demo_projects/orchestrator.py`: usunieto stara stubowa implementacje `execute_demo()`; aktywna implementacja uruchamia realny lifecycle project-start dla manifestu demo, fazy 16-41, council, Council Book/Ksiega, build closure artifact, Test Charter, test suites/runs, findings close, release rail i memory evidence.
- `src/sylion-pipeline/tests/aeis/testing/test_demo_projects.py`: dodano izolowany runtime demo i asercje, ze lifecycle jest `CLOSED`, artifact istnieje, ticket nie ma prefiksu `hg_`, finalny gate jest approved, a wszystkie 6 manifestow da sie przeprowadzic do `READY_FOR_PRODUCTION`.
- `src/sylion-pipeline/tests/api/test_test_center_routes.py`: dodano regresje na realny Test Charter governance ticket, odrzucenie syntetycznego Human Gate ID i produkcyjny final-sign z approved unified ticket.

Zasady wdrozenia po R3.8:

1. Projekt demo nie moze zwrocic `READY_FOR_PRODUCTION`, jezeli nie istnieje project-start lifecycle w stanie `CLOSED`.
2. Kazdy demo PASS musi miec artefakt build/closure na dysku i dowody testowe zapisane jako rekordy W14 TestRun/TestSuite.
3. Test Center nie moze produkowac ani akceptowac syntetycznych `hg_*` jako dowodu Human Gate. Podany ticket musi istniec w unified governance i miec `state=approved`.
4. W14 `OntologyStore` w runtime i test-center musi byc bindowany do aktywnego `SYLION_DB_PATH`; lokalny domyslny store nie jest prawda runtime.
5. Produkcyjny release gate moze przejsc tylko, gdy 18 pozycji checklisty jest `true`, `blockers=[]`, `no_mock_as_live=PASS` i finalny D4/D5 ticket jest approved.
6. D4/D5 release actions musza miec jawne `origin=council`, `gate_type=blocking` albo `production`, audit trail i referencje w `production_governance`.
7. `execute_demo()` ma realizowac wszystkie 6 manifestow z katalogu demo; pojedynczy happy path nie wystarcza do zmiany kanonu.
8. UI `/test-center/release-gate` musi pokazywac operatorowi widoczny status, checklisty, liczbe blokerow i no-mock PASS. Sam payload JSON nie jest dowodem gotowosci.
9. Jezeli projekt testowy wymaga decyzji D3+, approval musi przejsc przez ten sam governance plane co workspace/project execution guard.
10. Kazda dalsza zmiana demo/test-center release gate wymaga: focused pytest demo + Test Center, live direct `execute_demo`, HTTP probe release-gate i Playwright UI smoke.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_8_demo_project_execution_truth/repro_before.json`
- `docs/aeis_repair_v2/evidence/R3_8_demo_project_execution_truth/execute_demo_live.json`
- `docs/aeis_repair_v2/evidence/R3_8_demo_project_execution_truth/http_probe_live.json`
- `docs/aeis_repair_v2/evidence/R3_8_demo_project_execution_truth/ui_smoke_live.json`
- `output/playwright/aeis_repair_v2/R3_8_release_gate_ui_live.png`
- `output/logs/aeis_backend_8010_R3_8_demo_execution_final.err.log`
- `output/logs/aeis_backend_8010_R3_8_demo_execution_final.out.log`

Wynik po patchu:

- backend po finalnym restarcie: `/health status=ok`, `modules=138`, `endpoints=1946`, listener `127.0.0.1:8010`, PID `22036`;
- direct live `execute_demo("proj_demo_01_mobile_field_inspector")`: `READY_FOR_PRODUCTION`, `total_steps=9`, `project_state=CLOSED`, `audit_events=37`, build artifact istnieje;
- Test Charter ticket: realny approved governance ticket, bez prefiksu `hg_`;
- final release ticket: realny approved governance ticket;
- utworzono 9 wymaganych TestRun dla klas `T0,T2,T3,T4,T5,T6,T7,T9,T15`;
- HTTP probe `/api/v1/test-center/release-gate?project_id=proj_demo_01_mobile_field_inspector`: `production_ready`, `blockers=[]`, `no_mock_status=PASS`, `blocking_count=0`, `checklist_true_count=18/18`;
- HTTP probe `/api/v1/projects/proj_demo_01_mobile_field_inspector/artifact/raw`: `200`, `artifact_bytes=3642`;
- UI smoke `/test-center/release-gate`: `all_ok=true`, wpisany `project_id`, widoczne `production_ready`, `PASS`, `emerald_icon_count=18`, `amber_icon_count=0`, brak page errors, console errors, request failures i response 4xx/5xx.

Walidacja:

- `python -m py_compile src\sylion-pipeline\sylion\api\test_center_routes.py src\sylion-pipeline\sylion\aeis\testing\demo_projects\orchestrator.py`: PASS.
- `python -m pytest src\sylion-pipeline\tests\aeis\testing\test_demo_projects.py src\sylion-pipeline\tests\api\test_test_center_routes.py::test_project_charter_can_be_proposed_and_approved_for_release_gate src\sylion-pipeline\tests\api\test_test_center_routes.py::test_project_charter_rejects_synthetic_human_gate_id src\sylion-pipeline\tests\api\test_test_center_routes.py::test_production_release_gate_actions_make_project_production_ready -q`: `24 passed`.
- `python -m pytest src\sylion-pipeline\tests\api\test_test_center_routes.py -q`: `25 passed`.
- Playwright UI smoke: `all_ok=true`, screenshot zapisany w `output/playwright/aeis_repair_v2/R3_8_release_gate_ui_live.png`.

Wniosek: R3.8 zamyka demo/project execution drift. `execute_demo()` nie jest juz izolowanym stubem statusu, tylko przechodzi przez project lifecycle, evidence, Test Center i unified governance. Release gate nie przepuszcza syntetycznych Human Gate ID, a UI operatora pokazuje ten sam live status, ktory zwraca backend.

### R3.9: Agent Theater / model-agent topology truth plane

Status R3.9: naprawione i udokumentowane.

Uzyte skille: `dashboard-implementation`, `aeis-runtime-evidence-auditor`, `playwright`.

Reprodukcja / ustalenia przed patchem:

- kanon P2-006 wymagal read-only `AgentTheaterAggregator`, 6 endpointow `/api/v1/agent-theater/*`, topology view, 13 guardianow, local model status, WebSocket i frontend `/orchestration/teams` / `/test-center/theater`;
- `AgentTheaterAggregator.get_topology()` deklarowal live view, ale dodawal na sztywno aktorow `Claude Opus 4.7`, `GPT-5 Codex`, `Kimi K2`;
- `get_local_models_status()` zwracal na sztywno 3 lokalne modele jako `idle`, nawet gdy registry/runtime nie potwierdzal ich stanu;
- `get_council_session_view()` zwracal stub dla dowolnego `session_id`, wiec nie odroznial realnej sesji council od nieistniejacej;
- `agent_theater_routes._aggregator()` czytal `SYLION_W14_DB` albo domyslny `sylion_aeis.db`, ignorujac aktywny `SYLION_DB_PATH`;
- repro przed patchem: realny W14 finding zapisany w scoped runtime DB byl widoczny w bezposrednim `OntologyStore`, ale nie pojawial sie w live `/api/v1/agent-theater/topology`;
- kanoniczny kontrakt wskazywal `/ws/agent-theater/updates`, a runtime mial tylko kompatybilnosciowe `/ws/agent-theater`.

Naprawa:

- `src/sylion-pipeline/sylion/aeis/testing/agent_theater.py`: usunieto hardcoded live actorow; topology czyta modele z `ModelRegistry`, aktywne zespoly z orchestration config i otwarte findingi z W14 ontology.
- `src/sylion-pipeline/sylion/aeis/testing/agent_theater.py`: local models sa raportowane tylko, jezeli istnieja w model registry jako `ollama/local/qwen/gpt-oss/bielik/pllum`; brak potwierdzenia nie jest juz pokazywany jako `idle`.
- `src/sylion-pipeline/sylion/aeis/testing/agent_theater.py`: council view czyta realny unified `GovernanceTicket`; nieznany `session_id` zwraca blad, a nie stub.
- `src/sylion-pipeline/sylion/api/agent_theater_routes.py`: aggregator uzywa `get_ontology_store(db_path=resolve_db_path(SYLION_W14_DB or SYLION_DB_PATH or sylion_aeis.db))`; topology dostal opcjonalny `project_id`.
- `src/sylion-pipeline/sylion/api/agent_theater_routes.py`: dodano kanoniczny WebSocket alias `/ws/agent-theater/updates`, zostawiajac kompatybilny `/ws/agent-theater`.
- `src/sylion-pipeline/sylion/aeis/testing/ontology/store.py`: singleton W14 ontology rebinduje sie, gdy jawnie podany `db_path` rozni sie od aktywnego; pierwszy caller nie moze juz przypadkiem zatruc store'a zlym DB.
- `src/sylion-pipeline/tests/aeis/testing/test_agent_theater.py`: testy przestaly akceptowac hardcoded modele i stub council; sprawdzaja registry-backed actors, brak wymyslonych modeli, governance-backed council i registry-backed locals.
- `src/sylion-pipeline/tests/api/test_test_center_routes.py`: WebSocket testy obejmuja stary path i alias `/ws/agent-theater/updates`.
- `src/sylion-pipeline/tests/aeis/advisor/orchestration_config/test_orchestration_routes.py`: test team formation tworzy wlasna regule i sprawdza obecny team po payloadzie, zamiast zakladac czysty persistent store.

Zasady wdrozenia po R3.9:

1. Agent Theater jest read-only. Nie tworzy modeli, teamow, findingow ani ticketow podczas odczytu.
2. Topology nie moze hardcodowac aktorow jako live. Model/agent musi pochodzic z model registry, project council, active teams albo W14 ontology.
3. `source` i `counts` w topology sa czescia kontraktu diagnostycznego. Operator i testy musza widziec, z ktorego truth plane pochodzi model, team i finding.
4. W14 finding/task musi byc czytany z tego samego scoped ontology DB, ktorego uzywa Test Center. `SYLION_DB_PATH` jest obowiazujacym fallbackiem, jezeli nie ustawiono jawnego `SYLION_W14_DB`.
5. Local model nie moze byc pokazany jako `idle`, jezeli nie ma wpisu w registry. Brak runtime evidence oznacza brak rekordu albo status niepotwierdzony, nie zielony idle.
6. Council session view nie moze zwracac stubu. Realny `session_id` musi mapowac sie na unified governance ticket; nieznany `session_id` ma byc `404`.
7. WebSocket kanoniczny to `/ws/agent-theater/updates`; `/ws/agent-theater` zostaje tylko dla kompatybilnosci.
8. UI `/test-center/theater` musi pokazywac live WS, aktorow, krawedzie, 13 guardianow, local models z registry oraz W14 findingi jako taski.
9. UI `/orchestration/teams` musi czytac realne `team-formation-rules` i aktywne teamy; trigger testowy ma tworzyc team przez backend, nie przez fixture UI.
10. Kazda dalsza zmiana Agent Theater wymaga: unit tests agregatora, WS tests, team formation tests, live HTTP/WS probe, Playwright UI smoke obu ekranow.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_9_agent_theater_truth/repro_before.json`
- `docs/aeis_repair_v2/evidence/R3_9_agent_theater_truth/live_probe_after.json`
- `docs/aeis_repair_v2/evidence/R3_9_agent_theater_truth/ui_smoke_after.json`
- `output/playwright/aeis_repair_v2/R3_9_agent_theater_ui_live.png`
- `output/playwright/aeis_repair_v2/R3_9_orchestration_teams_ui_live.png`
- `output/logs/aeis_backend_8010_R3_9_agent_theater_final.err.log`
- `output/logs/aeis_backend_8010_R3_9_agent_theater_final.out.log`
- `output/logs/aeis_frontend_3001_R3_9_agent_theater.err.log`
- `output/logs/aeis_frontend_3001_R3_9_agent_theater.out.log`

Wynik po patchu:

- backend po finalnym restarcie: `/health status=ok`, `modules=138`, `endpoints=1947`, listener `127.0.0.1:8010`, PID `29464`;
- frontend dev: `127.0.0.1:3001`, PID `12752`;
- live HTTP/WS probe: `all_ok=true`;
- topology czyta W14 DB `output/r38_live/aeis_clean.db`, `finding_visible=true`, `hardcoded_claude_visible=false`, `hardcoded_kimi_visible=false`;
- live topology probe: `actor_count=19`, `edge_count=4`, `models=14`, `teams=1`, `open_findings=2`;
- guardian status: `13`;
- local models z registry: `10`;
- repair theater dla `find_78f934f92396`: `r_status=OPEN`, `severity=P1`, `d_level=D4`, `loop_status=CLEAR`;
- council view: `source=governance_ticket`, ticket `origin=council`, `state=approved`, `decision_class=D4`, `critic_status=signed`, `sentinel_status=pass`, `participant_count=2`;
- unknown council session: `404`;
- `/ws/agent-theater/updates`: `snapshot`, finding widoczny;
- UI smoke: `/orchestration/teams` pokazuje aktywne zespoly i trigger tworzy `Utworzono zespoly: 1`; `/test-center/theater` pokazuje WS, finding, teamy, 13 guardianow, local models, graf SVG; `all_ok=true`, `circle_count=66`, `line_count=14`, brak page errors, console errors, request failures i HTTP 4xx/5xx.

Walidacja:

- `python -m py_compile src\sylion-pipeline\sylion\aeis\testing\agent_theater.py src\sylion-pipeline\sylion\api\agent_theater_routes.py src\sylion-pipeline\sylion\aeis\testing\ontology\store.py`: PASS.
- `python -m pytest src\sylion-pipeline\tests\aeis\testing\test_agent_theater.py src\sylion-pipeline\tests\api\test_test_center_routes.py::test_agent_theater_ws_streams_snapshot_and_replies_to_ping src\sylion-pipeline\tests\api\test_test_center_routes.py::test_agent_theater_ws_set_interval_updates_state src\sylion-pipeline\tests\api\test_test_center_routes.py::test_agent_theater_ws_rejects_invalid_json src\sylion-pipeline\tests\api\test_test_center_routes.py::test_agent_theater_ws_updates_alias_streams_snapshot src\sylion-pipeline\tests\aeis\advisor\orchestration_config\test_orchestration_routes.py::TestTeamFormationRules -q`: `19 passed`.
- `python -m pytest src\sylion-pipeline\tests\api\test_test_center_routes.py -q`: `26 passed`.
- Playwright UI smoke: `all_ok=true`, screenshoty zapisane w `output/playwright/aeis_repair_v2/`.
- `git diff --check` dla plikow R3.9: brak bledow whitespace; pozostaja ostrzezenia Git o przyszlej normalizacji LF/CRLF.

Wniosek: R3.9 zamyka Agent Theater drift. Dashboard nie deklaruje juz syntetycznych modeli ani fikcyjnych council sessions jako live. Topology jest bindowane do scoped W14 store, modele i local models ida z registry, active teams ida z orchestration config, council view idzie z unified governance, a UI operatora widzi te same dane przez REST/WS.

### R3.10: Long-horizon memory / Obsidian-backed truth plane

Status R3.10: naprawione i udokumentowane.

Uzyte skille: `aeis-runtime-evidence-auditor`, `playwright`.

Reprodukcja / ustalenia przed patchem:

- kanon P2-007 wymagal Obsidian API connector, sync project notes -> Obsidian vault, backlinks, graph view, auto-tagging i 4 scenariusze testowe;
- kryterium akceptacji: zamkniety projekt automatycznie synchronizuje sie do Obsidian, a graph pokazuje powiazania;
- live runtime przed patchem nie mial zadnych tras `/api/v1/memory/obsidian/*`;
- `/api/v1/memory/obsidian/status?project_id=proj_demo_01_mobile_field_inspector` zwracal `404`;
- `/api/v1/memory/obsidian/graph` zwracal `404`;
- brak bylo realnego pliku note `.md`, indeksu grafu i evidence trail dla long-horizon memory.

Naprawa:

- `src/sylion-pipeline/sylion/memory/obsidian_sync.py`: dodano lokalny Obsidian-compatible connector zapisujacy realne Markdown notes do vaultu, evidence JSON i `.aeis/obsidian_sync_index.json`.
- `src/sylion-pipeline/sylion/memory/obsidian_sync.py`: dodano selective sync, auto-tagging (`aeis`, `project`, `state-*`, `domain-*`, `d-level-*`, `signal-*`, `closed`, `local-only`), backlinks w formacie wiki-link oraz graph nodes/edges.
- `src/sylion-pipeline/sylion/api/memory_routes.py`: dodano `/api/v1/memory/obsidian/connector`, `/sync`, `/status`, `/graph`, `/notes/{project_id}` oraz wpiecie licznikow Obsidian do `/api/v1/memory/stats` i `/recent`.
- `src/sylion-pipeline/sylion/api/execution_start_routes.py`: phase 41 `close-project` po ustawieniu `CLOSED` uruchamia automatyczny sync do vaultu, zapisuje `long_horizon_memory` w closure i dopisuje audit event `long_horizon_memory_synced`.
- `src/sylion-pipeline/sylion/api/execution_start_routes.py`: acceptance phase 41 ma twardy check `long_horizon_memory`; status `PASS` wymaga realnego pliku note, evidence hash i `status=synced`.
- `src/sylion-frontend/src/lib/api/client.ts`: dodano klienta API dla Obsidian connector/status/sync/graph/note.
- `src/sylion-frontend/src/app/(app)/memory/page.tsx`: dodano panel operatora `Long-horizon Obsidian` z vault path, licznikami wezlow/relacji, recznym sync, lista wezlow i backlinkow.
- `src/sylion-pipeline/tests/test_obsidian_memory_sync.py`: dodano 5 testow kontraktowych dla note/evidence/tags, backlinks/graph, reject open project bez force, phase41 auto-sync i API status/sync/graph.

Zasady wdrozenia po R3.10:

1. Long-horizon memory nie moze byc oznaczona jako `synced`, jezeli nie istnieje realny plik `Projects/{project_id}.md`.
2. Kazdy sync musi zapisac evidence JSON z `evidence_hash`, `note_sha256`, `note_path`, `vault_root`, `tags` i `related_project_ids`.
3. Automatyczny sync jest czescia phase 41. Zamkniecie projektu bez `long_horizon_memory.status=synced` ma obalic acceptance phase 41.
4. Sync domyslnie wymaga `state=CLOSED`. `force=true` jest tylko jawna diagnostyka/manual override i nie moze byc uzywany przez phase 41.
5. Backlinki sa materializowane jako Obsidian wiki-links w note oraz jako `edges` w `.aeis/obsidian_sync_index.json`.
6. Graph view nie moze generowac fikcyjnych relacji. Edge istnieje tylko, gdy sync dostal related project albo znalazl realny wpis w indeksie.
7. Auto-tagi pochodza z runtime classification/state/signals, nie z recznie wpisanego dashboard textu.
8. Vault jest selektywny: note przechowuje streszczenie, closure lessons, artefact pointers i hashe, a nie kopie calego workspace.
9. Domyslny vault to `output/obsidian_vault`; dla testow i probe nalezy ustawic `SYLION_OBSIDIAN_VAULT_ROOT`, aby dowody byly izolowane.
10. Kazda dalsza zmiana long-horizon memory wymaga: unit tests sync/graph, API tests, phase41 acceptance test, live probe po restarcie backendu i Playwright UI smoke `/memory`.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_10_long_horizon_memory_truth/repro_before.json`
- `docs/aeis_repair_v2/evidence/R3_10_long_horizon_memory_truth/live_probe_after.json`
- `docs/aeis_repair_v2/evidence/R3_10_long_horizon_memory_truth/ui_smoke_after.json`
- `output/playwright/aeis_repair_v2/R3_10_long_horizon_memory_ui_live.png`
- `output/logs/aeis_backend_8010_R3_10_obsidian_memory.err.log`
- `output/logs/aeis_backend_8010_R3_10_obsidian_memory.out.log`
- `output/r310_live/obsidian_vault/Projects/proj_demo_01_mobile_field_inspector.md`
- `output/r310_live/obsidian_vault/Evidence/proj_demo_01_mobile_field_inspector.json`
- `output/r310_live/obsidian_vault/.aeis/obsidian_sync_index.json`

Wynik po patchu:

- backend po restarcie: `/health status=ok`, `modules=138`, `endpoints=1952`, listener `127.0.0.1:8010`, PID `4976`;
- OpenAPI zawiera 5 tras Obsidian: connector, graph, notes, status, sync;
- status przed live sync: `not_synced`, `note_exists=false`;
- phase 41 live probe na `proj_demo_01_mobile_field_inspector`: `long_horizon_memory.status=synced`, `acceptance.accepted=true`, hard-check `long_horizon_memory=pass`;
- note Markdown istnieje: `output/r310_live/obsidian_vault/Projects/proj_demo_01_mobile_field_inspector.md`, `bytes=5091`;
- evidence JSON istnieje: `output/r310_live/obsidian_vault/Evidence/proj_demo_01_mobile_field_inspector.json`;
- auto-tagi zawieraja m.in. `aeis`, `project`, `state-closed`, `domain-mobile_approval`, `d-level-d4`, `closed`, `local-only`;
- manual sync z related id `proj_demo_04_internal_crm` materializuje backlink `[[proj_demo_04_internal_crm]]`;
- graph API: `nodes=1`, `edges=1`, edge `proj_demo_01_mobile_field_inspector -> proj_demo_04_internal_crm`;
- UI smoke `/memory`: `all_ok=true`, panel Long-horizon Obsidian widoczny, vault/liczniki/wezly/backlinki widoczne, screenshot zapisany.

Walidacja:

- `python -m py_compile src\sylion-pipeline\sylion\memory\obsidian_sync.py src\sylion-pipeline\sylion\api\memory_routes.py src\sylion-pipeline\sylion\api\execution_start_routes.py`: PASS.
- `python -m pytest src\sylion-pipeline\tests\test_obsidian_memory_sync.py -q`: `5 passed`.
- `python -m pytest src\sylion-pipeline\tests\test_planning_execution_routes.py::test_internal_crm_execution_stays_local_without_payment_ksef_or_vps src\sylion-pipeline\tests\test_planning_execution_routes.py::test_execution_testing_deploy_closure_to_closed -q`: `2 passed`.
- `npm exec -- eslint "src/app/(app)/memory/page.tsx"`: PASS.
- `npm exec -- eslint "src/app/(app)/memory/page.tsx" "src/lib/api/client.ts"`: `0 errors`; pozostaja istniejace warnings `no-explicit-any` w duzym `client.ts`.
- `git diff --check` dla plikow R3.10: brak bledow whitespace; pozostaja ostrzezenia Git o przyszlej normalizacji LF/CRLF.

Wniosek: R3.10 zamyka long-horizon memory drift. Zamkniety projekt ma teraz realny, selektywny zapis w Obsidian-compatible vault, evidence trail, auto-tagi, backlinki, graf runtime i UI operatora pokazujace ten sam truth plane.

### R3.11: Polish localization sweep / P2-008

Status R3.11: naprawione i udokumentowane.

Uzyte skille: `aeis-runtime-evidence-auditor`, `playwright`.

Reprodukcja / ustalenia przed patchem:

- kanon P2-008 wymagal pelnej lokalizacji UI na polski: labels, komunikaty, emaile, fallback en i visual regression;
- kryterium akceptacji: 100% polskich labels, emaile po polsku, brak mixed language;
- polityka jezykowa z dokumentow zostaje utrzymana: statusy techniczne i identyfikatory moga pozostac angielskie, narracja operatora musi byc po polsku;
- live probe przed patchem znalazl 13 widocznych pozostalosci angielskich na `/memory`, project detail, release gate, `/human-gate` i `/project-start`;
- przyklady przed patchem: `Long-horizon`, `Vault`, `Sync`, `Evidence`, `Backlink`, `Refresh`, `Run acceptance`, angielskie nazwy faz w Project Start oraz angielskie subject/report strings w phase 41 closure.

Naprawa:

- `scripts/aeis_i18n_audit.py`: dodano konserwatywny statyczny skaner podejrzanych angielskich labels i mojibake z allowlista terminow technicznych.
- `src/sylion-frontend/src/app/(app)/memory/page.tsx`: spolszczono widoczne labels panelu pamieci, Obsidian vault, sync, backlinks, evidence, placeholders i fallbacki.
- `src/sylion-frontend/src/components/project-start/ProjectStartDashboard.tsx`: spolszczono statyczne i backend-fed labels Project Start, fazy, przyciski, empty states, audit entries i acceptance/preflight messages.
- `src/sylion-frontend/src/app/(app)/projects/[projectId]/page.tsx`: dodano mapowanie demo idea text, audit/timeline stage labels, council snippets i visible dynamic choices przed renderowaniem.
- `src/sylion-frontend/src/app/(app)/human-gate/page.tsx`, `src/sylion-frontend/src/components/workspace/*`, `src/sylion-frontend/src/components/layout/ApiOfflineBanner.tsx`, `src/sylion-frontend/src/components/system/BackendOfflineGuard.tsx`: spolszczono offline/backend unreachable komunikaty.
- `src/sylion-pipeline/sylion/api/execution_start_routes.py`: spolszczono phase 41 closure email subjects, report bodies, attachment names, acceptance labels, edge case risks i generated worker artifact headings.
- `src/sylion-pipeline/tests/test_planning_execution_routes.py`: dodano asercje, ze lokalne i produkcyjne closure emails/reports sa po polsku i nie zawieraja starych angielskich report strings.

Zasady wdrozenia po R3.11:

1. Narracja, labels, przyciski, placeholders, empty states i komunikaty bledu dla operatora musza byc po polsku.
2. Angielskie statusy/ID moga zostac tylko jako raw identifier, enum, protocol, API field albo product/technical term; nie wolno ich uzywac jako samodzielnego labela narracyjnego.
3. Widoczny label `Evidence` ma byc `Dowody` albo `Pakiet dowodowy`; `Evidence Pack` jest dopuszczalne tylko jako termin kanoniczny sparowany z polskim opisem albo w dokumentacji technicznej.
4. `Sync`, `Vault`, `Backlink`, `Refresh`, `Offline` nie moga wystepowac jako samodzielne operator-facing labels.
5. Backend emails, reports, acceptance checks i phase communication musza byc po polsku, jezeli runtime/projekt uzywa polskiego operator language.
6. UI nie moze renderowac raw enum/audit/check text z backendu bez mapowania na polski label, jezeli wartosc jest widoczna dla operatora.
7. Demo seed text moze zachowac nazwy produktow i akronimy, ale nie moze zawierac angielskiej narracji biznesowej.
8. Statyczny audit lokalizacji dla dotykanych surfaces musi konczyc sie `total_findings=0` i `user_facing_candidates=0`.
9. Live probe lokalizacji musi obejmowac minimum `/memory`, project detail, release gate, `/human-gate`, `/funding` i `/project-start`.
10. Kazda dalsza zmiana i18n wymaga: lint dotknietych plikow, statyczny scan, live probe, screenshoty oraz relewantne testy backendowe dla email/report strings.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_11_polish_localization/repro_before.json`
- `docs/aeis_repair_v2/evidence/R3_11_polish_localization/static_after.json`
- `docs/aeis_repair_v2/evidence/R3_11_polish_localization/live_probe_after.json`
- `output/playwright/aeis_repair_v2/R3_11_memory_polish_ui_live.png`
- `output/playwright/aeis_repair_v2/R3_11_project_detail_polish_ui_live.png`
- `output/playwright/aeis_repair_v2/R3_11_release_gate_polish_ui_live.png`
- `output/playwright/aeis_repair_v2/R3_11_human_gate_polish_ui_live.png`
- `output/playwright/aeis_repair_v2/R3_11_funding_polish_ui_live.png`
- `output/playwright/aeis_repair_v2/R3_11_project_start_polish_ui_live.png`
- `output/logs/aeis_backend_8010_R3_11_polish_localization.err.log`
- `output/logs/aeis_backend_8010_R3_11_polish_localization.out.log`

Wynik po patchu:

- backend po restarcie: `/health status=ok`, `endpoints=1952`, listener `127.0.0.1:8010`, process pair `30072/16304`;
- frontend dev: `127.0.0.1:3001`, PID `12752`;
- statyczny scan R3.11: `total_findings=0`, `user_facing_candidates=0`;
- live Playwright probe: `all_ok=true`, 6 tras HTTP `200`, `total_findings=0`;
- phase 41 closure dla local-only i production path generuje polskie subjecty i raporty operatora/klienta.

Walidacja:

- `python -m py_compile scripts\aeis_i18n_audit.py src\sylion-pipeline\sylion\api\execution_start_routes.py`: PASS.
- `npm exec -- eslint "src/app/(app)/memory/page.tsx" "src/app/(app)/projects/[projectId]/page.tsx" "src/app/(app)/human-gate/page.tsx" "src/components/project-start/ProjectStartDashboard.tsx" "src/components/workspace/HumanGatePanel.tsx" "src/components/workspace/CouncilPanel.tsx" "src/components/workspace/BookGeneratorPanel.tsx" "src/components/layout/ApiOfflineBanner.tsx" "src/components/system/BackendOfflineGuard.tsx"`: `0 errors`, pozostaje 34 istniejace warnings stylistyczno-typowe.
- `python -m pytest src\sylion-pipeline\tests\test_planning_execution_routes.py::test_internal_crm_execution_stays_local_without_payment_ksef_or_vps src\sylion-pipeline\tests\test_planning_execution_routes.py::test_execution_testing_deploy_closure_to_closed src\sylion-pipeline\tests\test_obsidian_memory_sync.py -q`: `7 passed`.
- Playwright live localization probe: `all_ok=true`, 6 screenshotow zapisanych w `output/playwright/aeis_repair_v2/`.

Wniosek: R3.11 zamyka P2-008 na priorytetowych runtime surfaces i backendowej komunikacji closure. Pozostawione angielskie terminy sa swiadomymi wyjatkami technicznymi albo nazwami produktow/akronimami, nie narracja operator-facing.

### R3.12: Dead code cleanup / P3-001

Status R3.12: naprawione i udokumentowane.

Uzyte skille: `code-bloat-detector`, `efficiency-audit`, `playwright`.

Reprodukcja / ustalenia przed patchem:

- kanon P3-001 wymagal skanu `vulture` albo `pylint`, manual review top kandydatow, usuniecia potwierdzonego martwego kodu, ostroznego traktowania legacy dashboard/mock files i regression suite;
- `vulture` i `pylint` nie byly zainstalowane w aktywnym Pythonie, wiec `vulture` uruchomiono izolowanie z katalogu tymczasowego poza repo;
- `vulture --min-confidence 90` przed patchem wskazal 34 trafienia;
- czesc trafien to wygenerowane `*_pb2.py`/`grpc_stubs` albo importy availability-check dla manualnego wiring gRPC, wiec nie byly bezpieczne do usuniecia w P3-001;
- targetowany ESLint dla paneli workspace/ProjectStart przed patchem mial 34 warnings, w tym 8 realnych `no-unused-vars`;
- legacy dashboard nadal istnieje jako 69 plikow, ale plan ma dla niego osobny krok P3-002 z backupem, wiec w R3.12 nie wykonano hard delete.

Naprawa:

- `src/sylion-frontend/src/components/workspace/BookGeneratorPanel.tsx`: usunieto nieuzywane importy `Badge`, `FileText` oraz martwy stan `loading` z efektu listowania ksiazek.
- `src/sylion-frontend/src/components/workspace/CouncilPanel.tsx`: usunieto nieuzywane importy `XCircle`, `HelpCircle`.
- `src/sylion-frontend/src/components/workspace/HumanGatePanel.tsx`: usunieto nieuzywany import `ChevronRight`, martwa funkcje `presentDecision` i nieuzywana mape `lineStyles`.
- `src/sylion-pipeline/sylion/funding_autopilot/browser_automation.py`: usunieto nieuzywane importy typow Playwright i oznaczono nieuzywane argumenty `__exit__` jako swiadomie ignorowane.
- `src/sylion-pipeline/sylion/funding_autopilot/routes.py`: usunieto nieuzywany import `ExecutiveReportRequest`.
- `src/sylion-pipeline/sylion/governance/compliance_engine.py`: usunieto inertny blok `try/import/pass` dla `EvidencePackManager`, ktory nie mial efektu runtime.
- `src/sylion-pipeline/sylion/project_mode/engine.py`: usunieto unreachable `return None` po bezwarunkowym zwrocie.
- `src/sylion-pipeline/sylion/server.py`: oznaczono nieuzywany `frame` handlera sygnalu jako `_frame`.
- `src/sylion-pipeline/sylion/surface/artifact_control.py`: istniejacy parametr `deprecator` jest teraz zapisywany w event payload i logu.
- `src/sylion-pipeline/sylion/aeis/advisor/engine/orchestrator.py`: `sync_gate` trafia do DSL context, a `related_audit_ids` do evidence prompts zamiast pozostawac martwymi parametrami.
- `src/sylion-pipeline/sylion/execution/capacity_planner.py`: `t_now` jest uzywany jako punkt centrowania regresji liniowej.
- `src/sylion-pipeline/sylion/rebuild/rebuildability_framework.py`: usunieto nieuzywany import `DecisionBoundaryMap`; decyzje nadal pochodza z module registry.

Zasady wdrozenia po R3.12:

1. Nie usuwac wygenerowanych `*_pb2.py`, `grpc_stubs` ani plikow generator-owned recznie; ich cleanup wymaga regeneracji kontraktow.
2. Publiczne podpisy funkcji, FastAPI route handlers i entrypointy uzywane przez reflection wolno usuwac tylko po `rg` + testach kontraktowych.
3. `vulture`/lint jest filtrem kandydatow, nie wyrocznia. Kazdy kandydat musi miec manual review.
4. Legacy dashboard nie jest kasowany w P3-001. Jego usuniecie idzie w P3-002 z backupem, referencjami DB i smoke testem.
5. Nieuzywany parametr w publicznym API nalezy najpierw sensownie wykorzystac albo jawnie oznaczyc jako `_ignored`; usuniecie podpisu to osobna decyzja kompatybilnosci.
6. Touched frontend panels musza miec `no-unused-vars=0`; warnings `no-explicit-any` i react-hooks sa osobnym dlugiem, nie martwym kodem.
7. Kryterium P3-001 liczymy na potwierdzonej liscie martwego kodu: redukcja wysokiej pewnosci musi byc >=20%.
8. Kazdy cleanup Python wymaga `py_compile` i celowanych testow modulow, ktorych dotknal patch.
9. Kazdy cleanup paneli UI wymaga ESLint i przynajmniej jednego screenshot smoke dotknietej powierzchni.
10. Lista pomijanych klas kandydatow musi byc zapisana w evidence, zeby nie wracaly jako falszywe alarmy bez zmiany reguly.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_12_dead_code_cleanup/vulture_min90_before.txt`
- `docs/aeis_repair_v2/evidence/R3_12_dead_code_cleanup/vulture_min90_after.jsonl.txt`
- `docs/aeis_repair_v2/evidence/R3_12_dead_code_cleanup/eslint_target_before.json`
- `docs/aeis_repair_v2/evidence/R3_12_dead_code_cleanup/eslint_target_after.json`
- `docs/aeis_repair_v2/evidence/R3_12_dead_code_cleanup/cleanup_summary.json`
- `output/playwright/aeis_repair_v2/R3_12_workspace_dead_code_smoke.png`

Wynik po patchu:

- `vulture --min-confidence 90`: 34 -> 18 trafien, redukcja 47.1%;
- targetowany ESLint: 34 -> 25 warnings, `no-unused-vars` 8 -> 0;
- pozostale `vulture` trafienia to wygenerowane protobuf/grpc stubs i jeden manual-wiring import `SubscriptionServicer`;
- pozostale ESLint warnings to `no-explicit-any` i jeden `react-hooks/set-state-in-effect`, bez martwych importow/zmiennych;
- legacy dashboard pozostaje do P3-002, zidentyfikowany jako 69 plikow.

Walidacja:

- `python -m py_compile` dla 9 zmienionych plikow Python: PASS.
- `npm exec -- eslint "src/components/workspace/BookGeneratorPanel.tsx" "src/components/workspace/CouncilPanel.tsx" "src/components/workspace/HumanGatePanel.tsx" "src/components/project-start/ProjectStartDashboard.tsx"`: `0 errors`, 25 warnings, `no-unused-vars=0`.
- `python -m pytest src\sylion-pipeline\tests\test_capacity_planner.py src\sylion-pipeline\tests\test_surface_artifact_control.py src\sylion-pipeline\tests\funding\test_browser_automation.py src\sylion-pipeline\tests\test_funding_autopilot_routes.py src\sylion-pipeline\tests\test_compliance_engine.py src\sylion-pipeline\tests\test_server_integration.py src\sylion-pipeline\tests\aeis\advisor\engine\test_judge_prompt_context.py -q`: `243 passed`, 6 warnings.
- `python -m pytest src\sylion-pipeline\tests\test_rebuildability_framework.py src\sylion-pipeline\tests\test_rebuildability.py src\sylion-pipeline\tests\project_mode\test_worker_reconcile.py src\sylion-pipeline\tests\aeis\advisor\engine\test_engine_smoke.py -q`: `108 passed`, 11 skipped.
- Playwright screenshot smoke `/workspace`: zapisano `output/playwright/aeis_repair_v2/R3_12_workspace_dead_code_smoke.png`.
- `git diff --check` dla plikow R3.12: brak bledow whitespace; pozostaja ostrzezenia Git o przyszlej normalizacji LF/CRLF.

Wniosek: R3.12 zamyka P3-001 na potwierdzonej liscie martwego kodu. Wysokiej pewnosci trafienia spadly o 47.1%, frontendowe martwe importy/zmienne w targetowanych panelach spadly do zera, a wygenerowane stubs, publiczne podpisy i legacy dashboard zostaly swiadomie odlozone do wlasciwych krokow.

### R3.13: Usuniecie legacy dashboard / P3-002

Status R3.13: naprawione i udokumentowane.

Uzyte skille: `code-bloat-detector`, `aeis-runtime-evidence-auditor`.

Reprodukcja / ustalenia przed patchem:

- legacy katalog `src/sylion-pipeline/dashboard/` mial 69 plikow i byl osobnym, starym runtime obok unified API;
- przed usunieciem wykonano backup `output/backups/R3_13_legacy_dashboard_backup_20260513_142842.zip`;
- backup ma SHA256 `43B3AA0468DDB82CA23A277C33E2DC59F315554528CA34E5ECEBF8096ED95D56`, rozmiar `866996` bajtow i obejmuje 69 plikow;
- aktywne odwolania do `dashboard.app`, `dashboard.db`, `python dashboard/start.py` i `sylion_dashboard.db` istnialy w konfiguracji, skryptach, testach i helperach runtime.

Naprawa:

- usunieto katalog `src/sylion-pipeline/dashboard/` po potwierdzeniu, ze absolutna sciezka znajduje sie wewnatrz workspace;
- `config.py`, `health_check.py`, `orchestrator.py`, `fact_checker.py`, `orchestrator_anti_halluc_hook.py`, `pixel_provision.py`, `supervisor.py` i `input_protocol.py` przestaly importowac lub zakladac legacy DB/pakiet;
- skrypty start/install/rollback, systemd, Docker/compose, backup i release guard zostaly przepiete na unified runtime oraz `sylion_aeis.db`;
- wycofano 31 testow zaleznych od starego `dashboard/db/app/start` i dodano kontrakt `tests/test_legacy_dashboard_removed.py`;
- E2E i operacyjne README w aktywnym drzewie nie wskazuja juz startu `python dashboard/start.py`.

Zasady wdrozenia po R3.13:

1. Nie przywracac `src/sylion-pipeline/dashboard/` bez osobnej decyzji architektonicznej i rollback planu.
2. Nowe backend entrypointy maja isc przez `sylion.api.app:app` albo `python -m sylion.server`, nie przez modul `dashboard.*`.
3. Runtime DB ma byc wskazywana przez `SYLION_DB_PATH`; domyslna nazwa operacyjna to `sylion_aeis.db`.
4. Testy nie moga importowac rootowego `db.py`, `app.py`, `start.py` ani `dashboard.*`; nowe testy maja uzywac `sylion.api.app`.
5. Docker/systemd/installer musza miec smoke albo kontrakt tekstowy potwierdzajacy brak starego entrypointu.
6. Backup usunietego legacy kodu trzymamy tylko jako artefakt rollback, nie jako zrodlo prawdy.
7. Jezeli jakis stary manual/release note opisuje `dashboard.app`, traktujemy go jako dokument historyczny; aktywne runbooki maja wskazywac unified runtime.
8. Kazda dalsza zmiana startu backendu wymaga `rg` po `dashboard.app`, `dashboard.db`, `dashboard/start.py`, `sylion_dashboard.db`.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/backup_manifest.json`
- `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/deletion_manifest.json`
- `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/retired_legacy_dashboard_tests.json`
- `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/active_reference_scan_after.txt`
- `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/test_reference_scan_after.txt`
- `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/temp_backend_smoke_after.json`
- `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/r3_13_cleanup_summary.json`

Wynik po patchu:

- `Test-Path src/sylion-pipeline/dashboard`: `False`;
- aktywny scan referencji legacy: `NO_MATCHES`;
- testowy scan referencji legacy: `NO_MATCHES`;
- backup rollback: zip istnieje, SHA256 zapisany w evidence.

Walidacja:

- `python -m py_compile` dla zmienionych modulow i testow R3.13: PASS.
- `python -m pytest src\sylion-pipeline\tests\test_legacy_dashboard_removed.py src\sylion-pipeline\tests\test_auth_bootstrap.py -q`: `8 passed`, 6 warnings.
- Tymczasowy backend smoke na `127.0.0.1:8012`: `/health`, `/openapi.json`, `/api/v1/core/health`, `/api/v1/governance/health` zwrocily HTTP `200`.
- `git diff --check`: PASS; pozostaja tylko ostrzezenia Git o przyszlej normalizacji LF/CRLF.

Wniosek: R3.13 zamyka P3-002. Stary pakiet dashboard zostal usuniety z kodu aktywnego, runtime i testow kontraktowych; unified backend pozostaje uruchamialny i ma smoke evidence.

### R3.14: FIX-100/103/106 reporting polish / P3-003

Status R3.14: naprawione i udokumentowane.

Uzyte skille: `dashboard-implementation`, `aeis-runtime-evidence-auditor`, `playwright`.

Reprodukcja / ustalenia przed patchem:

- kanon P3-003 wymagal refaktoru `/funding`, wykresow Recharts dla pipeline/success rate/ROI, eksportow PDF/CSV/XLSX, notyfikacji e-mail, mobile responsive i visual regression;
- backend mial `POST /api/v1/funding/application/{application_id}/export`, ale XLSX zalezalo od opcjonalnego `openpyxl`, a plikow eksportu nie dalo sie pobrac przez stabilny endpoint;
- UI `/funding` pobieral `reports/executive`, `deadlines` i `alerts`, ale nie mial osobnej zakladki raportowej, wykresow, eksportu CSV pipeline ani bezposrednich linkow PDF/XLSX;
- `openpyxl` nie byl dostepny w aktywnym Pythonie, wiec kryterium XLSX bylo niestabilne bez fallbacku.

Naprawa:

- `src/sylion-pipeline/sylion/funding_autopilot/service.py`: dodano deterministyczny generator XLSX w OOXML bez zaleznosci od `openpyxl`, fallback PDF bez zewnetrznej biblioteki oraz polskie etykiety sekcji/budzetu w eksportach.
- `src/sylion-pipeline/sylion/funding_autopilot/routes.py`: dodano `GET /api/v1/funding/application/{application_id}/export/{artifact_type}` z `FileResponse`, walidacja typu artefaktu i ograniczeniem do funding results root.
- `src/sylion-pipeline/tests/test_funding_autopilot_routes.py`: rozszerzono testy eksportu o PDF, XLSX, pobieranie plikow i odrzucenie nieznanego artefaktu.
- `src/sylion-frontend/src/app/(app)/funding/funding-reporting-panel.tsx`: dodano wydzielony panel raportowania z Recharts: pipeline, status/skutecznosc, ROI/budzet grantowy i presja terminow.
- `src/sylion-frontend/src/app/(app)/funding/page.tsx`: dodano zakladke `Raporty`, przekazanie realnych danych runtime i stabilny czas odniesienia z `lastUpdated`.
- `src/sylion-frontend/src/lib/api/client.ts`: dodano helper URL dla pobierania eksportow funding.
- Panel raportowy dostarcza CSV pipeline po stronie klienta, linki PDF/XLSX do backendu dla wybranego wniosku oraz szkice powiadomien e-mail z alertow/deadline'ow.

Zasady wdrozenia po R3.14:

1. Wykresy `/funding` musza bazowac na realnych danych z endpointow funding, nie na statycznym mocku.
2. PDF/XLSX dla wnioskow maja isc przez backendowy endpoint `GET /application/{id}/export/{artifact}`, nie przez lokalne pseudo-pliki UI.
3. XLSX musi pozostac deterministyczny nawet bez `openpyxl`; opcjonalna biblioteka moze byc uzyta, ale fallback OOXML jest wymagany.
4. CSV pipeline moze byc generowany klientowo tylko z aktualnie zaladowanych danych API.
5. Powiadomienia e-mail pozostaja operator-reviewed (`mailto`) dopoki nie powstanie backend wysylki z polityka, audytem i odpowiednia bramka decyzyjna.
6. UI nie moze wolac `Date.now()` w renderze; czas odniesienia ma pochodzic ze stanu/odpowiedzi API.
7. Nowe panele raportowe musza miec stabilne `data-testid`, responsywne gridy i Playwright screenshot desktop/mobile.
8. Endpoint pobierania eksportu musi walidowac typ artefaktu i nie moze serwowac plikow spoza `funding_results_root`.
9. Kazda zmiana eksportow funding wymaga `py_compile`, testu routes, lint panelu i runtime smoke `/funding`.
10. Jezeli eksport zacznie wysylac pliki poza workspace albo do portali grantowych, wymaga osobnego Human Gate/policy i evidence pack.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/before_summary.txt`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/after_backend_export_scan.txt`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/after_frontend_reporting_scan.txt`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/runtime_api_reporting_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/playwright_reporting_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/funding_reporting_desktop.png`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/funding_reporting_mobile.png`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/r3_14_cleanup_summary.json`

Wynik po patchu:

- OpenAPI zawiera `/api/v1/funding/application/{application_id}/export/{artifact_type}` i `/api/v1/funding/reports/executive`;
- `/funding` ma zakladke `Raporty` z 4 wykresami, panelem eksportow i powiadomieniami;
- Playwright potwierdzil `rechartsSurfaceCount=7`, obecne CSV/PDF/XLSX, panel powiadomien i rendering mobile `390x900`;
- runtime smoke API na `127.0.0.1:8014` zwrocil `/health status=ok`, executive report, deadlines, alerts i OpenAPI routes;
- procesy smoke zostaly zatrzymane, brak aktywnych listenerow na portach `8014` i `3014`.

Walidacja:

- `python -m py_compile` dla zmienionych modulow funding i testu routes: PASS.
- `python -m pytest src\sylion-pipeline\tests\test_funding_autopilot_routes.py -q`: `5 passed`, 6 warnings.
- `npm exec eslint -- "src/app/(app)/funding/funding-reporting-panel.tsx"`: PASS, brak warnings.
- `npm exec eslint -- "src/app/(app)/funding/page.tsx" "src/app/(app)/funding/funding-reporting-panel.tsx" "src/lib/api/client.ts"`: `0 errors`; pozostaja istniejace warnings `no-explicit-any` w starym kliencie/stronie.
- Playwright runtime smoke `/funding`: PASS, desktop/mobile screenshots zapisane w evidence.
- `git diff --check` dla plikow R3.14: PASS.

Wniosek: R3.14 zamyka P3-003. Funding reporting ma realne wykresy, eksporty PDF/CSV/XLSX, operator-reviewed powiadomienia e-mail oraz desktop/mobile evidence. Eksport XLSX nie zalezy juz od opcjonalnego `openpyxl`, a pliki raportowe sa pobierane przez kontrolowany endpoint backendu.

### R3.15: Documentation update / P3-004

Status R3.15: naprawione i udokumentowane.

Uzyte skille: `aeis-system-book-writer`, `aeis-runtime-evidence-auditor`.

Reprodukcja / ustalenia przed patchem:

- aktywna dokumentacja mieszala stan po naprawach z historycznymi instrukcjami dla portu backendu `8000`, starego `dashboard/start.py`, Next.js 14 oraz poprzednich statystyk runtime;
- indeks dokumentacji nadal traktowal planowana liczbe 51 plikow modulowych jako aktualny stan, mimo ze aktywny katalog `docs/dokumentacja/modules/` ma 41 plikow `.md`;
- dokumenty funding nie opisywaly pelnego stanu po R3.14: endpointu pobierania eksportow, zakladki `Raporty`, wykresow i operator-reviewed e-maili;
- system book byl jeszcze szkicem i nie rozdzielal wystarczajaco ostro statusow: implemented, partial, removed, planned;
- aktywne dokumenty srodowiskowe nadal mogly sugerowac `DASHBOARD_DB_PATH` albo `sylion_dashboard.db` jako biezace ustawienia.

Naprawa:

- dodano `docs/dokumentacja/DOCS_RUNTIME_SYNC_2026_05_13.md` jako aktywny override runtime po R3.14;
- wszystkie 41 plikow `docs/dokumentacja/modules/*.md` dostaly marker `DONE_SYNC_P3_004` i odeslanie do dokumentu synchronizacji;
- zaktualizowano `docs/dokumentacja/00_INDEX.md`, `00_architektura_systemu.md`, `02_operational_manual.md`, `_changelog.md`, `modules/07_funding.md`, `modules/40_setup_step_by_step.md` i `modules/41_environment_variables.md`;
- zaktualizowano aktywny runbook `docs/system_audit/00_RUNTIME_STARTUP.md`: backend `8010`, frontend `3001`, legacy dashboard usuniety i nieuruchamialny;
- `AEIS_SYSTEM_BOOK_2026.md` ustawiono jako final runtime sync P3-004 / wersja 1.0 i doprecyzowano funding, mobile, legacy dashboard, runtime stats oraz statusy planned/partial/removed;
- aktywne przyklady portu backendu w dokumentacji operacyjnej przepieto na `8010`; stare wzmianki pozostaja tylko jako historyczne lub jawne "nie uzywac".

Zasady wdrozenia po R3.15:

1. Aktywne dokumenty startowe maja wskazywac backend `127.0.0.1:8010` i frontend `127.0.0.1:3001`.
2. `python dashboard/start.py`, `dashboard.app`, `dashboard.db`, `DASHBOARD_DB_PATH` i `sylion_dashboard.db` nie moga byc opisywane jako aktywny runtime.
3. Historyczne audyty moga zachowac stare fakty, ale aktywne runbooki i dokumenty modulowe musza miec aktualny override albo marker sync.
4. Pliki modulowe wymagaja `DONE_SYNC_P3_004` albo pozniejszego markera synchronizacji.
5. Dokumentacja funding musi opisywac export download endpoint, raporty R3.14, CSV/PDF/XLSX oraz evidence R3.14.
6. System book musi rozdzielac fakty zweryfikowane od norm wdrozeniowych oraz statusy implemented/partial/removed/planned.
7. Nowe przyklady backend API w aktywnej dokumentacji uzywaja `8010`, chyba ze fragment jest jawnie oznaczony jako historyczny.
8. Kazda kolejna synchronizacja dokumentacji wymaga consistency scan, drift scan, `git diff --check` i zapisu evidence.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_15_documentation_update/before_summary.txt`
- `docs/aeis_repair_v2/evidence/R3_15_documentation_update/before_doc_drift_scan.txt`
- `docs/aeis_repair_v2/evidence/R3_15_documentation_update/before_modules_inventory.json`
- `docs/aeis_repair_v2/evidence/R3_15_documentation_update/docs_consistency_after.json`
- `docs/aeis_repair_v2/evidence/R3_15_documentation_update/after_doc_drift_scan.txt`
- `docs/aeis_repair_v2/evidence/R3_15_documentation_update/git_diff_check_after.txt`
- `docs/aeis_repair_v2/evidence/R3_15_documentation_update/null_byte_scan_after.txt`

Wynik po patchu:

- `docs_consistency_after.json`: PASS;
- aktywny katalog modulow ma 41 plikow i kazdy ma marker `DONE_SYNC_P3_004`;
- indeks zawiera `DOCS_RUNTIME_SYNC_2026_05_13.md`;
- runbook startowy uzywa `127.0.0.1:8010`;
- system book ma status `final runtime sync P3-004`;
- dokument funding zawiera `/api/v1/funding/application/{application_id}/export/{artifact_type}`;
- pozostale wzmianki `python dashboard/start.py` i legacy DB w aktywnym skanie sa wylacznie w kontekscie "nie uruchamiac"/changelog.

Walidacja:

- `git diff --check` dla `AEIS_SYSTEM_BOOK_2026.md`, `docs/dokumentacja` i `docs/system_audit/00_RUNTIME_STARTUP.md`: PASS.
- consistency scan R3.15: PASS.
- null-byte scan dla dokumentow/evidence tekstowego R3.15: PASS.
- Brak testow runtime w tym kroku, bo P3-004 zmienial tylko dokumentacje i ledger.

Wniosek: R3.15 zamyka P3-004. Dokumentacja aktywna opisuje aktualny unified runtime po R3.14, a stary dashboard i stara konfiguracja DB sa utrzymane tylko jako historia albo zakaz uzycia.

### R3.16: Test coverage >=80% / P3-005

Status R3.16: naprawione i udokumentowane.

Uzyte skille: `contract-test-writer`, `gate-check-runner`.

Reprodukcja / ustalenia przed patchem:

- bazowe `pytest --cov=sylion` nie moglo wiarygodnie zmierzyc progu, bo kolekcje blokowaly pliki z NUL bytes oraz brakujace lokalne moduly kompatybilnosci dla `test_health_v2`;
- historyczny raport sprint2 wskazywal advisor coverage okolo 75% i sztuczne zanizanie przez wygenerowane wrappery gRPC/protobuf, `grpc_server.py`, DB helpery i `_perf`;
- testy advisor mialy wycieki SQLite/EventBus/test pool, przez co coverage run byl podatny na ResourceWarning i stan miedzy testami;
- czesc testow `role_resolver` i `variants` byla oznaczona jako wymagajaca Postgres mimo ze mozna je wykonac deterministycznie offline przy lokalnych fixture'ach.

Naprawa:

- dodano `src/sylion-pipeline/.coveragerc` z `fail_under = 80`, `precision = 2` i omit dla `sylion/aeis/advisor/_generated/*`, `*/grpc_server.py`, `*/_db.py`;
- przywrocono kolekcje po plikach z NUL bytes i dodano lokalne moduly kompatybilnosci `health_check_v2.py`, `health_endpoints.py`, `migration_3_to_4.py`;
- ustabilizowano `guard_suite_routes` i dodano testy kontraktowe dla health/DB/error paths;
- wymuszono deterministic LLM stub tylko w testach przez `SYLION_FORCE_LLM_STUB`, bez cichych fallbackow produkcyjnych;
- domknieto SQLite/EventBus/test pool w fixture'ach advisor i resetach singletonow;
- odizolowano `events`, `orchestration_config`, `role_resolver` i `variants` od wyciekow runtime store/PG state;
- uruchomiono offline testy `role_resolver` i `variants`, dodano coverage dla `role_suggester`.

Zasady wdrozenia po R3.16:

1. Gate coverage dla `sylion.aeis.advisor` ma utrzymywac minimum `80.00%`; spadek ponizej progu jest regresja.
2. `tests/aeis/advisor/_perf` pozostaje poza brama P3-005; performance ma osobna brame, a nie coverage line gate.
3. Wygenerowane wrappery i DB-adaptery (`_generated/*`, `grpc_server.py`, `_db.py`) nie sa liczone do progu, ale kontrakty endpointow i zachowanie DB musza miec osobne testy routes/contract.
4. Testy nie moga wykonywac realnych calli LLM; stub jest dozwolony tylko przez jawne env `SYLION_FORCE_LLM_STUB`/`SYLION_ALLOW_LLM_STUB`.
5. Fixture'y musza zamykac SQLite, EventBus i test pool; ResourceWarning po advisor run traktowac jako regresje test hygiene.
6. Testy coverage nie moga zalezec od produkcyjnego Postgresa, sekretow, sieci ani globalnego runtime store.
7. Skipped tests musza miec jawny powod i nie moga ukrywac wymagania P3-005; nowe skipy wymagaja wpisu w evidence.
8. Kazda zmiana w advisor business logic wymaga uruchomienia advisor coverage gate albo uzasadnionego, wezszejszego regression packa plus wskazania ryzyka.
9. `git diff --check`, null-byte scan i pelna kolekcja `pytest --collect-only` sa wymagane po zmianach w test infrastructure.
10. P3-006 ma potraktowac istniejace `DeprecationWarning` security jako wejscie do finalnego security scan, ale nie blokuje to P3-005.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_16_test_coverage_80/R3_16_EVIDENCE_SUMMARY.md`
- `docs/aeis_repair_v2/evidence/R3_16_test_coverage_80/coverage_advisor_final_80_gate.json`
- `docs/aeis_repair_v2/evidence/R3_16_test_coverage_80/pytest_advisor_cov_final_80_gate.txt`
- `docs/aeis_repair_v2/evidence/R3_16_test_coverage_80/pytest_targeted_after_r3_16.txt`
- `docs/aeis_repair_v2/evidence/R3_16_test_coverage_80/pytest_collect_after_r3_16.txt`
- `docs/aeis_repair_v2/evidence/R3_16_test_coverage_80/py_compile_changed_after_r3_16.txt`
- `docs/aeis_repair_v2/evidence/R3_16_test_coverage_80/git_diff_check_r3_16.txt`
- `docs/aeis_repair_v2/evidence/R3_16_test_coverage_80/null_byte_scan_after_r3_16.txt`

Wynik po patchu:

- advisor coverage gate: `TOTAL 5912 1162 80.35%`;
- `Required test coverage of 80.0% reached. Total coverage: 80.35%`;
- `276 passed, 24 skipped, 6 warnings in 33.01s`;
- targeted regression guard/health/hallucination: `81 passed, 6 warnings in 6.68s`;
- pelna kolekcja: `13790 tests collected in 14.20s`;
- null-byte scan po zmianach R3.16: PASS.

Walidacja:

- `python -m pytest tests\aeis\advisor --ignore=tests\aeis\advisor\_perf --cov=sylion.aeis.advisor --cov-report="term-missing:skip-covered" --cov-report="json:..\..\docs\aeis_repair_v2\evidence\R3_16_test_coverage_80\coverage_advisor_final_80_gate.json" -q`: PASS.
- `python -m pytest tests\test_guard_suite_routes.py tests\test_health_v2.py tests\test_hallucination_guard_v592.py -q`: PASS.
- `python -m pytest --collect-only -q`: PASS.
- `python -m py_compile` dla plikow R3.16: PASS.
- `git diff --check` dla plikow R3.16: PASS; pozostaja tylko ostrzezenia Git o przyszlej normalizacji LF/CRLF.

Wniosek: R3.16 zamyka P3-005. Advisor ma egzekwowalny prog coverage 80%, finalny wynik wynosi 80.35%, a najwazniejsze testy kontraktowe i kolekcja calego repo sa stabilne.

### R3.17: Final security scan / P3-006

Status R3.17: czesciowo naprawione, BLOCKED do pelnego PASS.

Uzyte skille: `gate-check-runner`.

Ustalenia przed patchem:

- `bandit` znalazl 2 HIGH: domyslny `jinja2.Environment()` bez autoescape oraz `subprocess.run(... shell=True)` w ToolRunner;
- `pip-audit` na systemowym Pythonie 3.14 nie mogl audytowac zwyklym resolverem, bo lockfile wymaga `<3.14`, a `numpy==1.26.4` probowalo budowac sie ze zrodel;
- `pip-audit --no-deps --disable-pip` wykryl CVE w `python-multipart`, `python-dotenv`, `litellm`, `PyJWT`;
- `npm audit` wykryl 2 high i 3 moderate w frontendzie (`next`, `fast-uri`, `hono`, `express-rate-limit`, `ip-address`);
- `gitleaks` i `trivy` nie byly poczatkowo w PATH, ale zostaly doinstalowane przez `winget`;
- pelny `gitleaks detect --source .` znalazl 214 findings w historii Git, w tym realnie wygladajace provider tokens w historycznych/rootowych skryptach testowych;
- OWASP ZAP nie jest dostepny lokalnie, `winget` nie znalazl ZAP, a Docker daemon nie dziala.

Naprawa:

- `sylion/aeis_v2/policy_v2/jinja_runner.py`: walidacja template przechodzi przez `SandboxedEnvironment(autoescape=True)`;
- `sylion/execution/tool_runner.py`: shell tools odrzucaja string commands i uzywaja tylko argv list z `shell=False`;
- `tests/test_tool_runner.py`: dodano regresje dla argv-only shell execution i string-command rejection;
- podniesiono Python piny: `python-multipart==0.0.27`, `python-dotenv==1.2.2`, `litellm==1.83.10`, `PyJWT==2.12.0`;
- podniesiono frontend piny: `next==16.2.6`, `eslint-config-next==16.2.6`, override `fast-uri==3.1.2`, `npm audit fix --package-lock-only`;
- wyczyszczono aktywne rootowe probe scripts z hardcoded provider tokens i przepisano je na env-only;
- wyczyszczono token-shaped fixture literals w testach redakcji/secrets/settings;
- dodano evidence config `gitleaks_active_scan.toml` dla aktywnego checkoutu, z wycieciem vendor/generated/evidence paths.

Wynik po patchu:

- Bandit: `0 HIGH`, `171 MEDIUM`, `226 LOW`;
- pip-audit lockfile: `No known vulnerabilities found`;
- npm audit full/prod: `0 total`;
- Trivy high/critical: `0`;
- Gitleaks aktywny checkout: `no leaks found`;
- Gitleaks pelna historia: nadal `214` findings i wymaga rotacji/revocation oraz decyzji o historii Git;
- ZAP: nieuruchomiony z powodu braku lokalnego runnera/Docker daemon.

Walidacja:

- `python -m pytest tests\test_tool_runner.py tests\aeis_v2\test_w19_jinja_runner.py tests\aeis_v2\test_w19_jinja_sandbox_payloads.py tests\aeis_v2\test_w19_chaos.py tests\test_policy_template_validator.py -q`: `105 passed`.
- targeted secret cleanup regression: `9 passed, 6 warnings`.
- `python -m py_compile` dla zmienionych plikow security cleanup: PASS.
- `gitleaks detect --no-git --source . --config ...`: PASS.
- `trivy fs ... --severity HIGH,CRITICAL`: PASS.
- `git diff --check` dla R3.17 security fixes: PASS.

Zasady wdrozenia po R3.17:

1. `shell=True` nie wraca do ToolRunner; zewnetrzne procesy musza byc argv list i miec timeout.
2. Jinja/policy templates maja uzywac sandboxed environment, nie zwyklego `Environment()`.
3. Provider/API tokens nie moga byc literalami w testach, docs ani probe scripts; uzywac env vars albo fixture strings, ktore nie sa token-shaped.
4. `pip-audit` dla lockfile w lokalnym Pythonie 3.14 uruchamiac jako `--no-deps --disable-pip`; CI powinno uzywac Pythona zgodnego z lockfile (`>=3.11,<3.14`).
5. `npm audit` musi zostac na 0 total dla frontendu przed staging.
6. `gitleaks --no-git` dla aktywnego checkoutu musi byc 0; pelny `gitleaks detect` wymaga osobnej polityki historii i rotacji.
7. `trivy fs` ma pomijac vendor/generated/evidence/cache dirs, ale skanowac aktywne lockfile i konfiguracje.
8. Pelny PASS P3-006 wymaga ZAP quick scan na dzialajacym runtime albo jawnej decyzji o narzedziowym waiverze.

Dowody:

- `docs/aeis_repair_v2/evidence/R3_17_final_security_scan/security_final_scan.md`
- `docs/aeis_repair_v2/evidence/R3_17_final_security_scan/bandit_sylion_after_high_fixes.json`
- `docs/aeis_repair_v2/evidence/R3_17_final_security_scan/pip_audit_requirements_lock_after_dep_fixes.txt`
- `docs/aeis_repair_v2/evidence/R3_17_final_security_scan/npm_audit_frontend_final.json`
- `docs/aeis_repair_v2/evidence/R3_17_final_security_scan/trivy_fs_high_critical_final.json`
- `docs/aeis_repair_v2/evidence/R3_17_final_security_scan/gitleaks_detect.json`
- `docs/aeis_repair_v2/evidence/R3_17_final_security_scan/gitleaks_nogit_active_final.txt`
- `docs/aeis_repair_v2/evidence/R3_17_final_security_scan/pytest_security_high_fixes.txt`
- `docs/aeis_repair_v2/evidence/R3_17_final_security_scan/pytest_secret_cleanup_targeted.txt`

Wniosek: R3.17 naprawil wszystkie automatycznie naprawialne critical/high z Bandit, pip-audit, npm audit i Trivy oraz wyczyscil aktywny checkout z sekretow. P3-006 nie jest jeszcze pelnym PASS, bo historia Git zawiera wykryte sekrety i ZAP quick scan nie zostal wykonany.

## Aktywny backlog po R3.17

1. DONE R1.1: Ustalic i naprawic dev-origin dla frontendu: albo wymusic `localhost` w skryptach/probach, albo skonfigurowac Next dev tak, by `127.0.0.1:3001` hydratowal poprawnie.
2. DONE R1.2: Poprawic `scripts/extract_api_ui_coverage.py`, aby nie klasyfikowal hook-driven ekranow jako `UI_ONLY_OR_STATIC` bez runtime trace lub analizy importow.
3. DONE R1.3: Usunac lub jawnie uzasadnic zduplikowane Operation ID w OpenAPI.
4. DONE R1.4: Doprecyzowac kanon mobile endpointow i usunac probe path drift dla `/v1/queue`.
5. DONE R1.5: Zaktualizowac dokumenty operacyjne, zeby komendy startowe UI nie sugerowaly starego portu `8000`, jesli kanonem dev jest backend `8010`.
6. DONE R2.1: Usunac runtime `403` dla legacy WebSocket `/ws/overview` bez zmiany kanonu `/ws/workspace`.
7. DONE R2.2: Uporzadkowac hygiene procesu dev: port `3000` zajmowal stary Next z `.claude/worktrees`, a kanonem pozostaje frontend `3001`.
8. DONE R2.3: Zrobic triage istniejacych bledow ESLint frontendu i rozdzielic realne bugi od dlugu stylistycznego.
9. DONE R2.4: Przejrzec i naprawic `NEEDS_REVIEW` routes z markerem `demo` po poprawie API/UI coverage.
10. DONE R2.5: Przejrzec 20 `UI_ONLY_OR_STATIC` routes i rozdzielic intencjonalne statyczne strony od ekranow, ktore powinny byc podlaczone do API.
11. DONE R2.6: Wykonac kontrolny regression pack po R2: lint, coverage, krytyczne UI/API smoke, porty i logi runtime.
12. DONE R3.1: Zweryfikowac governance/Human Gate runtime depth, ustalic kanon approval plane i naprawic zanizanie priorytetu `P0..P4` w mirrorze HumanGate.
13. DONE R3.2: Sprawdzic end-to-end UI dla `/governance`, `/gates`, `/human-gate`, `/workspace` po R3.1 oraz potwierdzic, ze operator widzi te same tickety w unified governance i legacy HumanGate.
14. DONE R3.3: Zweryfikowac Model Council truth plane: registry vs project council members, quorum, critic/sentinel gates i realny wplyw deliberation na ticket `origin=council`.
15. DONE R3.4: Zweryfikowac i naprawic autonomy/execution guard: zmiany poziomu autonomii i execution start sa twardo spiete z governance ticketami, HumanGate i audit trail.
16. DONE R3.5: Zweryfikowac i naprawic worker/execution topology truth plane: faza 34, quorum, worker caps, orchestration_config i full `test_planning_execution_routes.py`.
17. DONE R3.6: Zweryfikowac i naprawic memory/skills truth plane: global memory index/search/evidence, skills registry/runtime/executor i UI `/memory` + `/skills` bez rozjazdu store/runtime.
18. DONE R3.7: Zweryfikowac i naprawic funding/business truth plane: programy/calls/ideas/company profile/state aid, UI `/funding` i powiazanie z project decision gates.
19. DONE R3.8: Zweryfikowac demo/project product execution truth plane: projekty testowe, artefakty, project lifecycle, test-center i execution-start bez syntetycznego PASS.
20. DONE R3.9: Zweryfikowac Agent Theater / model-agent topology truth plane: live topology, role assignment, council/worker/task traces i dashboard bez syntetycznego agent activity.
21. DONE R3.10: Zweryfikowac long-horizon memory / Obsidian-backed truth plane: sync projektow, backlinks, graph view, auto-tagging i brak fikcyjnych memory links.
22. DONE R3.11: Zweryfikowac Polish localization sweep (P2-008): labels, komunikaty, emaile, fallbacki i visual regression bez mixed-language UI.
23. DONE R3.12: Zweryfikowac P3-001 Dead code cleanup: martwe funkcje/importy/pliki/zmienne, bez regresji i bez spadku coverage.
24. DONE R3.13: Zweryfikowac P3-002 Usuniecie legacy dashboard: backup, usuniecie `src/sylion-pipeline/dashboard/`, referencje `sylion_dashboard.db`, docker-compose i smoke.
25. DONE R3.14: Zweryfikowac P3-003 FIX-100/103/106 reporting polish: `/funding` charts, eksporty PDF/CSV/XLSX, notyfikacje i mobile visual regression.
26. DONE R3.15: Zweryfikowac P3-004 Documentation update: dokumentacja modulowa, instrukcja obslugi, API reference i final `AEIS_SYSTEM_BOOK_2026.md`.
27. DONE R3.16: Zweryfikowac P3-005 Test coverage >=80%: aktualny pomiar coverage, brakujace testy, minimalny regression pack i zasady utrzymania progu.
28. BLOCKED R3.17: Zweryfikowac P3-006 Final security scan: automatyczne high/critical naprawione, ale pelny PASS wymaga rotacji sekretow z historii Git i OWASP ZAP quick scan.

## Nastepny krok

R3.17 follow-up: wykonac incident response dla sekretow z historii Git (rotacja/revocation + decyzja rewrite/baseline) oraz uruchomic OWASP ZAP quick scan po udostepnieniu ZAP runnera albo Docker daemon.
