# AEIS SYSTEM BOOK 2026

Status dokumentu: rozszerzona księga systemu po audycie runtime i freeze FLOW-001..FLOW-022
Data aktualizacji: 2026-05-14
Język: polski
Autor wersji: Codex audit synthesis
Zakres: opis warstwa po warstwie, etap po etapie, faza po fazie, moduł po module, z osobnym rozwinięciem funding, operator console, W18, Human Gate, Model Council, memory, skills, mobile, audit i runtime.

## 0. Jak Czytać Tę Księgę

Ta księga nie jest opisem życzeniowym. Przyjmuje stan systemu według kolejności dowodów:

1. kod,
2. runtime,
3. API,
4. dashboard UI,
5. testy i symulacje operatorskie,
6. dokumentacja.

Jeżeli dokumentacja obiecuje więcej niż runtime, opis mówi to wprost. Jeżeli funkcja ma UI, ale nie ma pełnego testu działania, ma status `PARTIAL`, `UI_ONLY` albo `ROUTE_2X`. Jeżeli zakres przeszedł dwa przebiegi przez dashboard i ma JSON/screenshoty, ma status `2X_PASS`.

### Statusy

| Status | Znaczenie |
|---|---|
| `LIVE_VERIFIED` | Kod istnieje i runtime/API/UI potwierdzają działanie. |
| `2X_PASS` | Flow przeszedł dwa pełne przebiegi dashboardowe albo dwa zgodne reprobe. |
| `PARTIAL` | Funkcja istnieje, ale nie jest domknięta end-to-end. |
| `PARTIAL_2X_PASS` | Fragment funkcji ma dwa przebiegi, ale nie cały obszar. |
| `ROUTE_2X` | Strona renderuje 2x bez błędów, ale akcje nie są jeszcze pełnym freeze. |
| `API_ONLY` | API działa bez pełnego UI albo bez przepływu operatora. |
| `UI_ONLY` | UI istnieje, ale brak potwierdzonego backendu/akcji. |
| `LEGACY` | Historyczny lub pomocniczy element, nie source of truth. |
| `PLANNED` | Zaplanowane, bez wystarczającego runtime. |
| `BROKEN` | Kod istnieje, ale test/runtime przeczy oczekiwanemu działaniu. |

### Główne Dowody

- `docs/aeis_repair_v2/dashboard_e2e_freeze/FREEZE_REGISTER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/BUG_LEDGER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/RUN_LOG.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/AEIS_OPERATOR_MANUAL_LATEST.md`
- `docs/aeis_repair_v2/full_human_dashboard_audit/FULL_HUMAN_DASHBOARD_BUG_LEDGER.md`
- `docs/codex_system_audit/CODEX_AEIS_MODULE_INVENTORY.md`
- `docs/codex_system_audit/CODEX_AEIS_ARCHITECTURE_REALITY.md`
- `docs/codex_system_audit/CODEX_AEIS_FUNCTIONAL_AUDIT.md`
- `docs/codex_system_audit/CODEX_AEIS_CANON_VS_REALITY.md`
- `docs/codex_system_audit/CODEX_AEIS_PRODUCTION_READINESS_MAP.md`
- `docs/codex_system_audit/CODEX_AEIS_REPAIR_BACKLOG.md`

Aktualny runtime dev:

| Element | Wartość |
|---|---|
| Backend | `http://127.0.0.1:8010` |
| Frontend | `http://127.0.0.1:3001` |
| Backend health | `status=ok`, `version=3.5.0`, `modules=138`, `endpoints=1957` |
| OpenAPI | `3.1.0`, około `1646` ścieżek path templates |
| DB mode | `sqlite` |
| Event mode | `sqlite` |

## 1. Czym Jest AEIS

AEIS jest lokalno-federacyjnym systemem operacyjnym do prowadzenia projektów przez człowieka, modele, agentów, workerów, governance i evidence. System nie jest już tylko koncepcją. Ma realny backend FastAPI, realny dashboard Next.js, realne API, rejestry projektów, workerów, skills, funding, W18 command router, Human Gate, monitoring, test center i wiele laboratoriów runtime.

Najuczciwszy stan systemu:

`SYSTEM FEDERATED / DEV-STAGING CAPABLE / NOT PRODUCTION READY`

AEIS potrafi dziś:

- uruchomić backend i frontend lokalnie;
- pokazać dashboard operatora i dashboard techniczny;
- przyjąć pomysł w `/workspace`;
- uruchomić pipeline z 5 krokami i pokazać wyniki w `Pipeline`, `Kod`, `Wynik`;
- utworzyć projekt przez `/project-start`;
- przeprowadzić fazy 16-19 project start;
- pokazać projekt na `/projects`, wejść w detail i lifecycle;
- wykonać W18 project freeze/build dla księgi, masterplanu i autoryzacji budowy;
- przeprowadzić execution-start Phase 32/33;
- uruchomić i zatrzymać lokalnych smoke workerów;
- sterować dispatch Phase 33: start, pauza, wznowienie, anulowanie;
- przeprowadzić Phase 34-41 do zamknięcia projektu;
- rejestrować workerów, heartbeat, rebalance, filtr per projekt i delete;
- wykonać orchestration J1-J9: LLM routing, council rules, auditor, fixer, dispatch, golden tests, teams, event map, conversations;
- utworzyć, wykonać i zapisać demand signal dla skills;
- renderować funding z profilem firmy, naborami, pomysłami, matchingiem, wnioskami, submission i raportami;
- pokazać mobile operator queue;
- pokazać audit/evidence/replay/health/runtime surfaces;
- przechowywać dowody freeze jako JSON i screenshoty.

AEIS nie jest jeszcze produkcyjnie domknięty, bo:

- Human Gate istnieje w kilku planes;
- memory istnieje, ale nie jest jednym globalnym lifecycle plane;
- skills registry i skills runtime nadal są częściowo rozdzielone;
- Model Council działa w wielu miejscach, ale nie jest jeszcze jednym egzekwowalnym kanonem głosowania dla całego systemu;
- mobile operator jest częściowy;
- funding ma silny moduł, ale część akcji formalnych jest nadal `PARTIAL`;
- wiele route pages ma tylko route-level proof, bez pełnych action tests.

## 2. Mapa Warstw AEIS W1-W19

Warstwy W1-W19 są operacyjną mapą systemu. Nie są tym samym co katalog folderów. Opisują odpowiedzialność runtime i miejsce w pracy operatora.

| Warstwa | Nazwa | Funkcja | Główne powierzchnie | Status |
|---|---|---|---|---|
| W1 | Kanon i konstytucja systemu | Zasady, polityki, granice autonomii, prawda systemowa. | `/policy`, `/book`, dokumenty canon | `PARTIAL` |
| W2 | Bootstrap, instalacja i workspace | Start backend/frontend, lokalny workspace, zdrowie runtime. | `/health`, `/runtime`, scripts start | `2X_PASS` dla startup |
| W3 | Tożsamość, uprawnienia i profil operatora | Profil operatora, tryb operator/technical, lokalny auth bridge. | `/settings/profile`, `/auth`, `/roles` | `PARTIAL_ROUTE` |
| W4 | Katalog providerów i modeli | Modele AI, klucze, routing, budżety. | `/ai-models`, `/budget`, `/secrets`, `/orchestration/llm-routing` | `PARTIAL`, J1 `2X_PASS` |
| W5 | Runtime, środowisko i infrastruktura | Local-first runtime, kontenery, środowiska, deploy. | `/environments`, `/environments/theater`, `/deploy`, `/runtime` | `PARTIAL_ROUTE` |
| W6 | Defaulty, autonomia i polityki systemowe | Defaulty workspace, budżety, autonomia, testy, dziedziczenie. | `/workspace-defaults`, `/autonomy`, `/policy` | `/workspace-defaults 2X_PASS` |
| W7 | Guards, Human Gate i governance | Bramy człowieka, decyzje, D-levels, policy enforcement. | `/human-gate`, `/governance`, `/gates`, `/guards` | Human Gate partial, wybrane flow `2X_PASS` |
| W8 | Pamięć systemu | Index/search/evidence, uczenie z projektów. | `/memory`, API memory | `PARTIAL_ROUTE_2X` |
| W9 | Kompetencje systemu | Skills registry, execution, demand signal. | `/skills` | `2X_PASS` dla create/execute/signal |
| W10 | Intake i rozumienie projektu | Przyjęcie pomysłu, klasyfikacja, preview, projekt. | `/project-start`, `/idea-vault`, `/workspace` | project-start i pipeline `2X_PASS` |
| W11 | Rada modeli | Kworum, role, symulacja, rozmowy modeli. | `/model-council`, `/orchestration/council-rules`, `/orchestration/conversations` | J2/J9 `2X_PASS`, całość `PARTIAL` |
| W12 | Source of Truth i Księga | Freeze księgi, canon, masterplan, truth artifacts. | `/source-of-truth`, `/council-to-ksiega`, W18 | W18 freeze/build `2X_PASS` |
| W13 | Advisor, Masterplan, koordynacja | Rekomendacje, planowanie, dispatch agentów. | `/advisor`, `/advisor/cockpit`, `/planning`, `/orchestration/dispatch` | `PARTIAL`, J5 `2X_PASS` |
| W14 | Quality Gates, testy i weryfikacja | Test center, golden tests, guardy jakości, symulacje człowieka. | `/test-center`, `/golden-tests`, `/orchestration/tests` | J6 `2X_PASS`, reszta partial |
| W15 | Ontologia, kontrakty i model domenowy | Typy domenowe, kontrakty, role i obiekty systemowe. | `/ontology`, `/contracts`, `/role-catalog` | `PARTIAL_ROUTE` |
| W16 | Wykonanie workerów, artefakty i build | Workers, execution-start, build phases, artifact production. | `/workers`, `/execution-start`, `/apps-builder` | workers/execution `2X_PASS` w wybranych scopes |
| W17 | Integracje, funding i urządzenia | Funding, deploy, federation, devices, lab, external actions. | `/funding`, `/devices`, `/sdr`, `/cellular`, `/federation` | funding partial, lab partial |
| W18 | Konsola operatora i terminal W18 | Terminal, command ownership, routing komend, audit. | `/terminal`, project W18, `/terminal/replay` | project W18 `2X_PASS`, global terminal partial |
| W19 | Audyt, zamknięcie i ewolucja | Evidence, audit, replay, freeze register, uczenie. | `/audit`, `/evidence`, `/terminal/replay` | `PARTIAL_ROUTE_2X` |

## 3. Realne Warstwy Techniczne

### 3.1. Backend API Aggregation

Backend FastAPI w `src/sylion-pipeline/sylion/api` agreguje ponad 80 plików route. Jest centralnym control plane dla workspace, projects, funding, governance, skills, memory, workers, orchestration, W18, mobile, lab i observability.

Najważniejsze rodziny API:

- `ai_workspace_routes.py` - workspace, sessions, council sessions, settings, books, Human Gate, ideas, attachments;
- `pipeline_routes.py` - pipeline ideas/runs/steps/execute/cancel;
- `project_start_routes.py` - preview/create/fazy 16-19;
- `projects_routes.py` i `projects_freeze_routes.py` - registry, detail, freeze artifacts;
- `execution_start_routes.py` - Phase 32-41, dispatch control, worker actions;
- `worker_routes.py` - registry, heartbeat, topology, rebalance;
- `orchestration_routes.py` - J1-J9 i konfiguracje rady/dispatch/tests;
- `terminal_routes.py` - W18 `/api/v1/terminal/exec`;
- `funding_autopilot/routes.py` - pełny funding domain;
- `skills_routes.py` - skills registry, runtime, demand signal;
- `memory_routes.py` - memory index, search, evidence;
- `governance_routes.py`, `gates_routes.py`, `council_routes.py` - governance and decision surfaces;
- `operator_mobile_routes.py` - mobile queue/device surfaces;
- `observability_routes.py`, `metrics_routes.py`, `health_routes.py`, `runtime_truth_routes.py` - runtime truth.

### 3.2. Frontend Operator Console

Frontend Next.js w `src/sylion-frontend/src/app/(app)` jest realnym dashboardem operatora. Ma tryb operatora i tryb techniczny.

Stałe elementy shell:

- `AppSidebar` - menu operator/technical;
- `TopCommandBar` - pasek komend, tryb, status;
- `BackendOfflineGuard` - wykrywanie braku backendu;
- `AuthFetchBridge` - lokalne powiązanie auth/fetch;
- `FirstRunBanner` - informacja o onboarding;
- `AdvisorBubble` - boczny doradca.

### 3.3. Storage i Source of Truth

Aktualnie runtime używa SQLite:

- główne DB dev;
- event mode SQLite;
- per-project runtime DB w wybranych flow;
- logi W18 i evidence JSON w repo.

Source of truth jest jeszcze federacyjny. Nie ma jednego finalnego store dla całego AEIS. Dla zamrożonych flow prawda jest kombinacją:

- backend state;
- API responses;
- project artifacts;
- W18 audit ledger;
- freeze register;
- screenshot/evidence JSON.

### 3.4. Runtime Topology

Topologia runtime obejmuje:

- backend API `8010`;
- frontend `3001`;
- workers registry;
- orchestration config;
- dispatch state;
- project lifecycle state;
- funding store;
- logs/evidence.

Nie należy mylić laboratoryjnych routes `devices/sdr/cellular/vps/container` z produkcyjnym deployem. Są częścią warstwy eksperymentalnej W17.

## 4. Etapy Pracy AEIS Od Startu Do Zamrożenia

| Etap | Co robi operator | Co robi AEIS | Status |
|---|---|---|---|
| 1. Start runtime | Uruchamia backend/frontend. | `/health`, OpenAPI, route shell. | `2X_PASS` |
| 2. Konfiguracja domyślna | Wchodzi w `/workspace-defaults`. | Smart defaults, budżety, autonomia, mobile, testy, acceptance. | `2X_PASS` |
| 3. Intake pomysłu | Wpisuje pomysł w `/workspace` albo `/project-start`. | Tworzy run/projekt, klasyfikuje, ustawia kontekst. | `2X_PASS` dla obu ścieżek |
| 4. Pipeline | Klik `Wyślij`, wybór runu, `Wykonaj`. | Tworzy 5 kroków, wykonuje model/guard, pokazuje wynik. | `2X_PASS` |
| 5. Project Start | Preview/create projektu. | Fazy 16-19, defaults, edge diagnosis. | `2X_PASS` |
| 6. Project Detail | Otwiera `/projects/{id}`. | Pokazuje W18, stan, `/status`, lifecycle. | `2X_PASS` |
| 7. W18 Freeze/Build | `zamroz ksiege`, `zamroz masterplan`, `autoryzuj budowe`. | Tworzy Human Gate tickets, zapisuje route/audit. | `2X_PASS` |
| 8. Execution Start | Uruchamia fazy wykonania. | Phase 32/33, live smoke workers, dispatch. | `2X_PASS` w scopes FLOW-014..017 |
| 9. Phase 34-41 | Klik fazy 34-41. | Council, orchestration, quality gates, acceptance, predeploy, closure. | `2X_PASS` |
| 10. Workers | Rejestruje workera, heartbeat, rebalance, delete. | Aktualizuje registry/topology. | `2X_PASS` |
| 11. Orchestration | J1-J9. | Routing, council, auditor, fixer, tests, teams, event map, conversations. | `2X_PASS` |
| 12. Funding | Profil, nabory, pomysły, matching, wnioski, submission, raporty. | Funding domain, local approval/submission guard. | `PARTIAL_2X_PASS` |
| 13. Audit i freeze | Sprawdza evidence. | Freeze register, bug ledger, screenshots, JSON. | `2X_PASS` dla zamrożonych flow |

## 5. Fazy I Punkty Kontrolne

### 5.1. Fazy 16-19: Project Start

Fazy 16-19 są wejściem projektu do formalnego lifecycle.

| Faza | Funkcja | Akcje operatora | Wynik |
|---|---|---|---|
| 16 | Intake/analiza projektu | Preview/create, opis, budżet, termin. | Acceptance `8/8`, hard blocks `0` w FLOW-020. |
| 17 | Cele i defaulty | `Zastosuj domyślne fazy 17`. | Acceptance `7/7`. |
| 18 | Zakres wykonania | `Zastosuj domyślne fazy 18`. | Acceptance `8/8`. |
| 19 | Rada/gotowość | `Zastosuj domyślne fazy 19`, `Zatwierdź gotowość`. | Acceptance `7/7`. |

Freeze: `docs/aeis_repair_v2/project_start_lifecycle/PROJECT_START_LIFECYCLE_PASS12.md`.

### 5.2. W18 Project Freeze/Build

W18 to terminal/operator cockpit dla komend. Po naprawie mutujące komendy projektu idą przez centralny kontrakt:

- `CommandIntent`;
- `CommandRoute`;
- `CommandExecution`;
- W18 audit log.

| Komenda | Owner | Decision | Route | Gate |
|---|---|---|---|---|
| `zamroz ksiege` | `project_mode.round_meta.freeze_canon` | `D3` | `TWO_PHASE` | Human Gate |
| `zamroz masterplan` | `project_mode.round_meta.freeze_masterplan` | `D4` | `TWO_PHASE` | Human Gate |
| `autoryzuj budowe` | `project_mode.round_meta.authorize_build` | `D4` | `TWO_PHASE` | Human Gate |
| `bramka czlowieka` | project ticket reader | read | immediate | nie dotyczy |

Freeze: `docs/aeis_repair_v2/w18_router_repair/W18_COMMAND_ROUTER_REPAIR_PASS12.md`.

### 5.3. Phase 32-33

Phase 32/33 przygotowuje wykonanie i worker evidence. Scope freeze:

- runtime config;
- initialize build;
- start execution;
- worker evidence `live_verified_local`;
- W18 command ledger.

Dispatch Phase 33:

| Akcja | Stan po kliknięciu | Decision | Owner |
|---|---|---|---|
| `Start wykonania` | `running` | runtime action | execution-start |
| `Pauza` | `paused` | `D3` | `execution_start.dispatch_control` |
| `Wznow` | `running` | `D3` | `execution_start.dispatch_control` |
| `Anuluj` | `cancelled` | `D4` | `execution_start.dispatch_control` |

Freeze: `docs/aeis_repair_v2/execution_dispatch_control/EXECUTION_DISPATCH_CONTROL_PASS12.md`.

### 5.4. Phase 34-41

| Faza | Przycisk | Target action | Decision | Wynik freeze |
|---|---|---|---|---|
| 34 | `Zwolaj rade` | `reconvene_mid_build_council` | `D4` | accepted |
| 35 | `Uruchom orkiestracje` | `activate_orchestration` | `D3` | accepted |
| 36 | `Zamknij budowe` | `complete_build` | `D3` | accepted |
| 37 | `Bramki jakosci` | `run_quality_gates` | `D3` | accepted |
| 38 | `Akceptacja klienta` | `complete_acceptance_testing` | `D4` | accepted |
| 39 | `Zatwierdz kontrole` | `authorize_predeploy` | `D4` | ticket present |
| 40 | `Wdrozenie / proba` | `execute_production_deploy` | `D5` | ticket present |
| 41 | `Zamknij projekt` | `close_project` | `D4` | final state `CLOSED` |

Freeze: `docs/aeis_repair_v2/execution_phases_34_41/EXECUTION_PHASES_34_41_PASS12.md`.

## 6. Operator Console: Menu, Zakładki I Status

### 6.1. Tryb Operatora

| Sekcja | Route | Funkcja | Status |
|---|---|---|---|
| Doradca | `/advisor/cockpit` | Centrum dowodzenia Advisora. | `PARTIAL_ROUTE` |
| Doradca | `/advisor` | Karty doradcze i rekomendacje. | `PARTIAL_ROUTE` |
| Doradca | `/dashboard/operator-monitor` | Monitor projektów/runtime. | `2X_PASS` route |
| Doradca | `/onboarding` | Pierwsze uruchomienie. | `PARTIAL_ROUTE` |
| Projekty | `/projects` | Lista projektów, wejście w detail. | `2X_PASS` w FLOW-020 |
| Projekty | `/project-start` | Intake i fazy 16-19. | `2X_PASS` |
| Projekty | `/council-to-ksiega` | Deliberacja i Księga. | `PARTIAL_ROUTE` |
| Projekty | `/planning` | Masterplan i plan wykonania. | `PARTIAL_ROUTE` |
| Projekty | `/execution-start` | Execution phases, dispatch, workers. | `2X_PASS` w FLOW-014..017 |
| Projekty | `/idea-vault` | Pomysły i załączniki. | `PARTIAL_ROUTE` |
| Funding | `/funding` | Doradca grantów. | `PARTIAL_2X_PASS` |
| Decyzje | `/decisions` | Decyzje systemowe. | `PARTIAL_ROUTE` |
| Decyzje | `/governance` | Rada/governance. | `PARTIAL_2X_PASS` |
| Decyzje | `/human-gate` | Approve/reject ticketów. | `PARTIAL_2X_PASS` |
| Decyzje | `/evidence` | Pakiety dowodowe. | `PARTIAL_ROUTE_2X` |
| Decyzje | `/audit` | Ścieżka audytu. | `PARTIAL_ROUTE_2X` |
| Testy | `/test-center` | Centrum testów W14. | `PARTIAL_ROUTE` |
| Konfiguracja | `/settings/advisor` | Preferencje Advisora. | `PARTIAL_ROUTE` |
| Konfiguracja | `/ai-models` | Modele i providerzy. | `PARTIAL_ROUTE` |
| Konfiguracja | `/workspace-defaults` | Pełny kreator defaultów. | `2X_PASS` |
| Konfiguracja | `/coherence-guard` | Strażnik spójności. | `PARTIAL_ROUTE` |
| Konfiguracja | `/cost-guard` | Strażnik kosztów. | `PARTIAL_ROUTE` |
| Konfiguracja | `/security-guard` | Strażnik bezpieczeństwa. | `PARTIAL_ROUTE` |
| Konfiguracja | `/quality-guard` | Strażnik jakości. | `PARTIAL_ROUTE` |
| Konfiguracja | `/provenance-guard` | Strażnik pochodzenia. | `PARTIAL_ROUTE` |
| Konfiguracja | `/templates-setup` | Szablony. | `PARTIAL_ROUTE` |
| Konfiguracja | `/environments` | Środowiska. | `PARTIAL_ROUTE` |
| Konfiguracja | `/skills` | Umiejętności. | `2X_PASS` dla create/execute/signal |
| Konfiguracja | `/budget` | Budżet modeli. | `PARTIAL_ROUTE` |
| Konfiguracja | `/secrets` | Klucze API/secrets. | `PARTIAL_2X_PASS` readonly |

### 6.2. Tryb Techniczny

| Route | Funkcja | Status |
|---|---|---|
| `/overview` | Przegląd systemu. | `2X_PASS` route |
| `/pipeline` | Linia wykonania. | `PARTIAL_ROUTE` |
| `/workspace` | Obszar pracy AI: Thinking/Working layers i pipeline. | tabs + pipeline `2X_PASS` |
| `/agents` | Rejestr agentów. | `ROUTE_2X` |
| `/modules` | Moduły. | `ROUTE_2X` |
| `/health` | Zdrowie backendu. | `2X_PASS` |
| `/contracts` | Kontrakty. | `ROUTE_2X` |
| `/performance` | Wydajność. | `ROUTE_2X` |
| `/devices` | Urządzenia/lab. | `PARTIAL_ROUTE` |
| `/costs` | Koszty. | `ROUTE_2X` |
| `/sdr` | Laboratorium SDR. | `PARTIAL_ROUTE` |
| `/cellular` | Laboratorium sieci komórkowej. | `PARTIAL_ROUTE` |
| `/rebuild` | Odbudowa. | `ROUTE_2X` |
| `/autonomy` | Autonomia. | `PARTIAL_ROUTE` |
| `/lifecycle` | Cykl życia. | `ROUTE_2X` |
| `/book` | Księga systemu w UI. | `ROUTE_2X` |
| `/anomalies` | Anomalie. | `2X_PROBED` po false-positive route abort |
| `/sla` | SLA. | `ROUTE_2X` |
| `/drift` | Dryf konfiguracji. | `ROUTE_2X` |
| `/risk` | Ryzyko. | `ROUTE_2X` |
| `/healing` | Samonaprawa. | `ROUTE_2X` |
| `/capacity` | Pojemność. | `ROUTE_2X` |
| `/circuits` | Bezpieczniki. | `ROUTE_2X` |
| `/golden-tests` | Testy złote. | `ROUTE_2X` |
| `/gates` | Bramki. | `PARTIAL_2X_PASS` route/gate surfaces |
| `/bundles` | Pakiety. | `ROUTE_2X` |
| `/evaluator` | Ewaluator. | `ROUTE_2X` |
| `/integrations` | Integracje. | `ROUTE_2X` |
| `/auth` | Uwierzytelnianie. | `ROUTE_2X` |
| `/roles` | Role. | `ROUTE_2X` |
| `/notifications` | Powiadomienia. | `ROUTE_2X` |
| `/connectors` | Konektory. | `ROUTE_2X` |
| `/security-scan` | Skan bezpieczeństwa. | `ROUTE_2X` |

### 6.3. AEIS V2, Orchestration I Test Center

| Route | Funkcja | Status |
|---|---|---|
| `/v2/admin` | Przegląd administracyjny. | `ROUTE_2X` |
| `/architecture-layers` | Warstwy W1-W19. | `LIVE_VERIFIED` route/API |
| `/ontology` | Ontologia W15. | `PARTIAL_ROUTE` |
| `/apps-builder` | Kreator aplikacji W16. | `PARTIAL_ROUTE` |
| `/apps-builder/wizard` | Wizard aplikacji. | `PARTIAL_ROUTE` |
| `/terminal` | Globalny terminal W18. | `PARTIAL`; project W18 frozen |
| `/terminal/replay` | Replay terminala. | `PARTIAL_ROUTE_2X` |
| `/role-catalog` | Katalog ról W7. | `PARTIAL_ROUTE` |
| `/federation` | Federacja W17. | `PARTIAL_ROUTE` |
| `/policy` | Polityki W19. | `PARTIAL_ROUTE` |
| `/orchestration` | Hub J1-J9. | `2X_PASS` |
| `/orchestration/llm-routing` | J1 routing LLM. | `2X_PASS` |
| `/orchestration/council-rules` | J2 reguły rady. | `2X_PASS` |
| `/orchestration/auditor` | J3 audytor/gate. | `2X_PASS` |
| `/orchestration/fixer` | J4 fixer protocol. | `2X_PASS` |
| `/orchestration/dispatch` | J5 dispatch config. | `2X_PASS` |
| `/orchestration/tests` | J6 golden test catalog. | `2X_PASS` |
| `/orchestration/teams` | J7 team formation. | `2X_PASS` |
| `/orchestration/event-map` | J8 event map. | `2X_PASS` |
| `/orchestration/conversations` | J9 rozmowy AI. | `2X_PASS` |
| `/test-center/theater` | Teatr modeli. | `PARTIAL_ROUTE` |
| `/test-center/auto-repair` | Auto-repair. | `PARTIAL_ROUTE` |
| `/test-center/simulation` | Symulacje. | `2X_PROBED` route |
| `/test-center/human-lab` | Human lab. | `2X_PROBED` route |
| `/test-center/no-mock-scan` | No-mock scan. | `PARTIAL_ROUTE` |
| `/test-center/release-gate` | Release gate. | `PARTIAL_ROUTE` |
| `/test-center/truth-alignment` | Truth alignment. | `PARTIAL_ROUTE` |

## 7. Moduły Backendowe I Ich Funkcje

| Pakiet | Funkcja | Status |
|---|---|---|
| `api` | FastAPI routers, OpenAPI, aggregation. | `LIVE_VERIFIED` |
| `aeis`, `aeis_v2` | Core AEIS v2, terminal, advisor, deployment, ontology. | `PARTIAL/LIVE` zależnie od submodułu |
| `autonomy` | Stage machine i autonomy state. | `PARTIAL` |
| `cellular` | Laboratorium sieci komórkowej. | `PARTIAL_ROUTE` |
| `cognitive` | LLM adaptery, code agent, chat, planner, idea vault. | `LIVE/PARTIAL` |
| `container` | Rejestr/plan kontenerów. | `PARTIAL` |
| `contracts` | Manifesty i kontrakty. | `PARTIAL_ROUTE` |
| `core` | Event bus, lifecycle gates, pipeline controller. | `LIVE_VERIFIED` dla pipeline/freeze scopes |
| `db` | SQLite/Postgres helpers. | `DEV_READY` |
| `demo` | Demo projects. | `PARTIAL_ROUTE` |
| `devices` | Device lab i artifact deployer. | `PARTIAL` |
| `efficiency` | Audyty efektywności. | `PARTIAL` |
| `execution` | Tool runner, workflow engine, capacity planner. | `2X_PASS` w execution-start scopes |
| `funding_autopilot` | Funding domain. | `PARTIAL_2X_PASS` |
| `governance` | Human Gate, policies, council, tickets. | `PARTIAL_2X_PASS` |
| `grpc`, `grpc_stubs` | gRPC contracts/stubs. | `PARTIAL` |
| `infra` | Deployment/topology templates. | `PARTIAL` |
| `integration` | Integration orchestration/connectors. | `PARTIAL_ROUTE` |
| `logs` | Runtime logs. | `LIVE` |
| `memory` | Index, retrieval, evidence. | `PARTIAL_ROUTE_2X` |
| `monitoring` | Model budget and monitoring. | `PARTIAL_ROUTE` |
| `observability` | Logs, metrics, traces. | `PARTIAL_ROUTE_2X` |
| `offensive` | Security/offensive lab. | `PARTIAL` |
| `operator_mobile` | Mobile operator gateway. | `PARTIAL` |
| `pipeline` | Pipeline domain helpers. | `/workspace` pipeline `2X_PASS` |
| `project_mode` | Project execution spine, round meta, store. | `2X_PASS` in project/W18/execution scopes |
| `providers` | Provider integrations. | `PARTIAL` |
| `quality` | Quality gates. | `PARTIAL`, Phase 37 `2X_PASS` |
| `rebuild` | Rebuildability. | `PARTIAL_ROUTE` |
| `sdr` | SDR lab. | `PARTIAL_ROUTE` |
| `security` | SOPS, vault, guards, cloud connectors. | `PARTIAL_ROUTE` |
| `sim` | Simulations. | `PARTIAL_ROUTE` |
| `skills` | Registry/runtime/executor/demand. | `/skills` create/execute/signal `2X_PASS` |
| `surface` | Dashboard V5 surface modules. | `PARTIAL` |
| `vps` | VPS provider plane. | `PARTIAL` |
| `worker` | Worker primitives. | `/workers` `2X_PASS` |

## 8. Workspace, Project Start I Pipeline

### 8.1. `/workspace`

Zakładki i warstwy:

- Thinking/Working tabs z wcześniejszego freeze route/tabs;
- `Pipeline` - lista runów, input pomysłu, status runu, wykonanie/anulowanie;
- `Kod` - wynik kroków pipeline;
- `Wynik` - log wykonania i statusy kroków.

Pipeline full flow:

1. operator wpisuje pomysł;
2. klik `Wyślij`;
3. API `POST /api/v1/pipeline/ideas` tworzy run `pending`;
4. operator wybiera run;
5. klik `Wykonaj`;
6. API `POST /api/v1/pipeline/runs/{run_id}/execute`;
7. system polluje `GET /api/v1/pipeline/runs/{run_id}`;
8. system pobiera `GET /api/v1/pipeline/runs/{run_id}/steps`;
9. status musi dojść do `complete`;
10. `quality_gate` musi być `passed`;
11. `Kod` i `Wynik` muszą pokazać realne dane.

Kroki pipeline:

- `artifact_contract`;
- `product_design`;
- `implementation_artifact`;
- `acceptance_tests`;
- `final_quality_report`.

Status freeze: `2X_PASS` w FLOW-022.

### 8.2. `/project-start`

Funkcje:

- formularz nazwy/opisu/kontekstu/terminu/budżetu;
- preview analizy;
- create project;
- fazy 16-19;
- edge diagnosis;
- przejście do `/projects`;
- detail W18 `/status`;
- lifecycle chart.

Status freeze: `2X_PASS` w FLOW-020.

### 8.3. `/workspace-defaults`

Cele testowane:

- `apps_internal`;
- `public_products`;
- `cybersecurity`;
- `research`.

Kroki kreatora:

1. Welcome;
2. Default budgets i estimate;
3. Autonomy preset;
4. Notifications + mobile;
5. Cleanup periods;
6. UI customization;
7. Shortcuts + navigation;
8. Approval + escalation;
9. Testing + council.

Możliwości konfiguracji:

- smart defaults per goal;
- budget ceilings;
- autonomy mapping;
- mobile pairing demo;
- notification matrix;
- cleanup periods;
- UI preset `Power User`;
- custom shortcut;
- approval/escalation visibility;
- test strategy;
- edge-case diagnosis;
- inheritance preview;
- acceptance run.

Status freeze: `2X_PASS` w FLOW-021.

## 9. Execution, Workers I Runtime

### 9.1. `/execution-start`

Zakresy zamrożone:

- W18 route evidence Phase 32/33;
- live smoke workers start/stop;
- dispatch start/pause/resume/cancel;
- Phase 34-41.

Nie zamrożono:

- produkcyjnego Docker/VPS deploy;
- pełnej floty workerów w środowiskach zewnętrznych;
- pełnego cloud provisioning.

### 9.2. `/workers`

Funkcje:

- wyświetlenie seeded topology;
- register worker;
- heartbeat;
- rebalance;
- widok per project;
- delete worker;
- obsługa `204 No Content` bez fałszywego błędu UI.

API:

- `GET /api/v1/workers`;
- `POST /api/v1/workers`;
- `POST /api/v1/workers/{worker_id}/heartbeat`;
- `DELETE /api/v1/workers/{worker_id}`;
- `GET /api/v1/workers/topology/all`;
- `POST /api/v1/workers/assignments/rebalance`.

Status freeze: `2X_PASS` w FLOW-018.

### 9.3. Dispatch Control

Reguły:

- owner: `execution_start.dispatch_control`;
- target: aktywny projekt, worker pool, local environment;
- `pause` i `resume`: `D3`, `TWO_PHASE`;
- `cancel`: `D4`, `TWO_PHASE`;
- po cancel nie wolno dalej pauzować/wznawiać/anulować;
- każda akcja zapisuje event, artifact, audit i W18 route.

## 10. Orchestration I Model Council

J1-J9 to realny drilldown orchestration:

| J | Route | Funkcja | Status |
|---|---|---|---|
| J1 | `/orchestration/llm-routing` | Presety i macierz routingu modeli. | `2X_PASS` |
| J2 | `/orchestration/council-rules` | Quorum, wagi, symulacja głosowania. | `2X_PASS` |
| J3 | `/orchestration/auditor` | Audit trigger + Stop-Fix-Restart gate. | `2X_PASS` |
| J4 | `/orchestration/fixer` | Fixer protocol. | `2X_PASS` |
| J5 | `/orchestration/dispatch` | Dispatch config, tryb `capped`, limity. | `2X_PASS` |
| J6 | `/orchestration/tests` | Golden catalog run. | `2X_PASS` |
| J7 | `/orchestration/teams` | Runtime team formation. | `2X_PASS` |
| J8 | `/orchestration/event-map` | Runtime event graph/filter. | `2X_PASS` |
| J9 | `/orchestration/conversations` | Inter-model conversation. | `2X_PASS` |

Model Council nadal ma status całościowy `PARTIAL`, bo:

- J2/J9 działają w scope orchestration;
- workspace/project/funding nie mają jeszcze jednego globalnego council plane;
- model registry, provider catalog i workspace council settings nadal są osobnymi planes.

## 11. Governance I Human Gate

Human Gate istnieje w kilku ścieżkach:

1. globalne `/human-gate`;
2. governance tickets;
3. project W18 tickets;
4. workspace Human Gate sessions;
5. funding approval events.

Co działa:

- approve/reject kontrolowanych ticketów;
- project W18 freeze/build przez Human Gate;
- dispatch D3/D4 route evidence;
- Phase 39/40 governance ticket IDs;
- funding submission approval plane lokalnie.

Co nie jest jeszcze jednolite:

- jeden globalny plane Human Gate dla workspace, project, funding, deploy i mobile;
- pełna matryca D0-D5 egzekwowana przez wszystkie moduły.

## 12. Funding - Pełny Opis Modułu

Funding jest jednym z najbardziej rozbudowanych modułów domenowych AEIS. Nie jest prompt-only. Ma backend, UI, API, raporty, local submission gate i szeroki model danych.

Status całości: `PARTIAL_2X_PASS`.

Route UI: `/funding`
Backend prefix: `/api/v1/funding`
Health: `/api/v1/funding/health`, `status=ok`, `module=funding`, `version=3.5.0`

### 12.1. Dashboard Funding - Zakładki

| Zakładka | Wartość internal | Funkcja | Status |
|---|---|---|---|
| Firma | `company` | Profil firmy, dokumenty, readiness, pomoc publiczna, registry sync. | route/tabs verified |
| Nabory | `calls` | Źródła, programy, nabory, skan źródeł, search. | route/tabs verified |
| Pomysły | `ideas` | Generowanie pomysłów fundingowych i konwersja do projektu. | partial |
| Dopasowanie | `matching` | Matching projektu do naborów, scoring, konsorcjum, partnerzy, outreach. | partial |
| Wnioski | `applications` | Tworzenie, review i export application package. | partial |
| Złożenie i CRM | `submission` | Prepare/fill/save draft/request approval/submit/receipt. | partial, guarded |
| Raporty | `reporting` | Pipeline, ROI, budżet, deadline pressure, chart reports, export URLs. | chart `2X_PASS` |

### 12.2. Metryki Widoczne W Funding

- `Gotowość` - readiness score profilu i brakujące pola;
- `Nabory` - liczba calls i wygenerowanych pomysłów;
- `Wnioski` - liczba applications i submission sessions;
- `Alerty` - alerts i deadlines.

### 12.3. Profil Firmy

Konfiguracja:

- KRS/CEIDG/NIP;
- forma prawna;
- kraj, region, miasto;
- status MŚP;
- liczba pracowników;
- roczny przychód;
- EBITDA;
- rynki eksportowe;
- technologie;
- produkty;
- usługi;
- kompetencje zespołu;
- cele strategiczne;
- reprezentant i e-mail;
- dokumenty: typ, nazwa pliku, storage path;
- state aid;
- readiness.

Akcje:

- `registry-sync` - synchronizacja profilu z rejestrem;
- `save-profile` - zapis profilu;
- `add-document` - dodanie dokumentu.

API:

- `GET/PUT /company-profile`;
- `GET /company-profile/readiness`;
- `GET/POST /company-profile/documents`;
- `GET /company-profile/state-aid`;
- `GET/POST /company-profile/registry-sync`.

### 12.4. Nabory I Źródła

Funkcje:

- lista źródeł;
- lista programów;
- tworzenie programu;
- tworzenie naboru;
- search calls;
- scored calls;
- trigger scan.

Pola programu:

- nazwa;
- instytucja;
- kraj;
- typ finansowania;
- opis.

Pola naboru:

- programme_id;
- tytuł;
- kod;
- portal URL;
- data zamknięcia;
- min/max budget;
- grant intensity;
- TRL min/max;
- beneficjenci;
- tematy;
- wymagane dokumenty;
- wymagane typy partnerów.

API:

- `GET /sources`;
- `GET/POST /programmes`;
- `GET/POST /calls`;
- `POST /calls/search`;
- `GET /calls/scored`;
- `GET /calls/{call_id}`;
- `POST /scan/trigger`;
- `GET /scan/status/{job_id}`.

### 12.5. Pomysły Fundingowe

Funkcje:

- generowanie pomysłów fundingowych dla firmy;
- lista pomysłów;
- szczegół pomysłu;
- konwersja pomysłu do projektu AEIS.

API:

- `GET /ideas`;
- `POST /ideas/generate`;
- `GET /ideas/{idea_id}`;
- `POST /ideas/{idea_id}/convert-to-project`.

Status: UI istnieje, flow pełnej konwersji jest jeszcze poza freeze 2x dla funding. W raporcie produkcyjnym traktować jako `PARTIAL`.

### 12.6. Matching, Scoring I Konsorcjum

Funkcje:

- `run matching`;
- pobranie wyników matching;
- eligibility check;
- scoring;
- analiza konsorcjum;
- search partnerów;
- shortlist partnerów;
- outreach generate.

API:

- `POST /matching/run`;
- `GET /matching/results/{project_id}`;
- `POST /eligibility/check`;
- `POST /scoring/run`;
- `GET /scoring/{project_id}`;
- `POST /consortium/analyze`;
- `POST /consortium/partners/search`;
- `POST /consortium/partners/shortlist`;
- `POST /consortium/outreach/generate`.

Konfiguracja partnera:

- nazwa;
- typ partnera;
- kraj;
- expertise;
- grant track record;
- e-mail kontaktowy.

### 12.7. Wnioski

Funkcje:

- create application;
- get application;
- get documents;
- review modes: formal, financial, technical, market;
- export application.

API:

- `POST /application/create`;
- `GET /application/{application_id}`;
- `GET /application/{application_id}/documents`;
- `POST /application/{application_id}/review`;
- `POST /application/{application_id}/export`;
- `GET /application/{application_id}/export/{artifact_type}`.

### 12.8. Submission I CRM

Funkcje:

- prepare submission;
- fill submission;
- save draft;
- request approval;
- submit application;
- receipt;
- submission sessions;
- approvals;
- CRM applications;
- deadlines;
- alerts.

API:

- `POST /submission/prepare`;
- `POST /submission/fill`;
- `POST /submission/save-draft`;
- `POST /submission/request-approval`;
- `POST /submission/submit`;
- `GET /submission/receipt`;
- `GET /submission/sessions`;
- `GET /submission/approvals`;
- `GET /crm/applications`;
- `GET /deadlines`;
- `GET /alerts`.

Reguły bezpieczeństwa:

- external submission nie może przejść bez approval;
- deadline/source/legal/budget/document blockers mają blokować;
- local rehearsal jest dozwolony;
- real submission jest akcją formalną i wymaga Human Gate/governance.

### 12.9. Raporty Funding

Funkcje raportowe:

- executive report;
- chart pipeline;
- skuteczność;
- ROI/budżet;
- presja terminów;
- export application;
- PDF/XLSX/CSV przez backend URL;
- szkic e-mail.

API:

- `GET /reports/executive`;
- export routes application artifacts.

Status: chart render i tabs reports `2X_PASS`; profile save, idea conversion, exports, email draft i full application/submission nadal `PARTIAL`.

## 13. Memory

Memory ma kod i API:

- index sections;
- search;
- evidence write;
- stats;
- retrieval;
- self model store.

Status:

- `/memory` route: `PARTIAL_ROUTE_2X`;
- manualne API index/search/evidence: potwierdzone w starszym audycie;
- pełny runtime lifecycle memory plane: `NOT_READY/PARTIAL`.

Ograniczenia:

- pamięć globalna i per-project runtime DB są nadal częściowo rozdzielone;
- nie każdy flow zapisuje lessons learned do jednego kanonu;
- route evidence stats historycznie miało problem cieniowania.

## 14. Skills

Skills ma:

- registry;
- lifecycle;
- executor;
- runtime;
- demand signal;
- UI `/skills`.

Zamrożony scope:

- create skill;
- execute `seed.echo`;
- demand signal;
- status execution `completed`;
- UI nie pokazuje fałszywego sukcesu przy backend failure.

Status: `/skills` create/execute/signal `2X_PASS`.
Nie jest jeszcze zamrożone: pełne zasilanie głównego project pipeline przez skills runtime.

## 15. Operator Mobile

Mobile surface:

- `/operator-mobile`;
- `/operator-mobile/queue`;
- `/operator-mobile/queue/{ticketId}`;
- `/operator-mobile/devices`;
- backend operator mobile routes;
- mobile gateway w advisor.

Zamrożony scope:

- mobile viewport navigation do queue;
- live pending tickets visible;
- console/API errors `0`.

Nie zamrożono:

- approve/reject z mobile;
- device binding;
- push notifications;
- natywnej aplikacji Android/iOS.

Status: `PARTIAL_2X_PASS` dla queue navigation, `PLANNED/PARTIAL` dla pełnej aplikacji mobilnej.

## 16. Security, Secrets I Konfiguracja

Powierzchnie:

- `/settings`;
- `/settings/profile`;
- `/settings/advisor`;
- `/secrets`;
- `/auth`;
- `/roles`;
- `/security-guard`;
- `/security-scan`;
- SOPS/vault/security routes.

Status:

- settings/secrets readonly `PARTIAL_2X_PASS`;
- key add/validate/rotate intentionally pending;
- frontend RBAC traktować jako UX, nie security boundary;
- backend enforcement wymagany dla produkcji.

Konfiguracje:

- provider keys;
- advisor settings;
- profile operatora;
- model budgets;
- secrets vault;
- security guard policies.

## 17. Audit, Evidence I Freeze

AEIS ma aktywną kulturę evidence:

- `FREEZE_REGISTER.md` - co jest zamrożone;
- `BUG_LEDGER.md` - każdy bug z root cause, fix, retest 1, retest 2;
- `RUN_LOG.md` - przebieg kampanii;
- screenshoty per flow;
- JSON evidence per flow;
- W18 command audit jsonl;
- manual operatorski.

Zasada freeze:

1. błąd wykryty dashboardem/API;
2. zapis w bug ledgerze;
3. fix;
4. retest 1;
5. retest 2;
6. brak console/API errors;
7. manual i freeze register zaktualizowane;
8. dopiero wtedy `2X_PASS`.

## 18. Katalog FLOW-001..FLOW-022

| Flow | Obszar | Status |
|---|---|---|
| FLOW-001 | Runtime startup | `2X_PASS` |
| FLOW-002 | Dashboard shell | `2X_PASS` |
| FLOW-003 | Workspace/project lifecycle umbrella | `2X_PASS` przez FLOW-020/021/022 |
| FLOW-004 | Governance/Human Gate | `PARTIAL_2X_PASS` |
| FLOW-005 | Execution umbrella | `2X_PASS` przez FLOW-014..019 |
| FLOW-006 | Memory | `PARTIAL_ROUTE_2X` |
| FLOW-007 | Skills | `2X_PASS` |
| FLOW-008 | Funding | `PARTIAL_2X_PASS` |
| FLOW-009 | Audit/replay/evidence | `PARTIAL_ROUTE_2X` |
| FLOW-010 | Mobile/operator | `PARTIAL_2X_PASS` |
| FLOW-011 | Settings/keys/secrets | `PARTIAL_2X_PASS` |
| FLOW-012 | Observability/readiness | `PARTIAL_ROUTE_2X` |
| FLOW-013 | W18 project terminal freeze/build | `2X_PASS` |
| FLOW-014 | Execution-start W18 router Phase 32-33 | `2X_PASS` |
| FLOW-015 | Live worker smoke start/stop | `2X_PASS` |
| FLOW-016 | Execution phases 34-41 | `2X_PASS` |
| FLOW-017 | Dispatch control | `2X_PASS` |
| FLOW-018 | Workers registry/topology | `2X_PASS` |
| FLOW-019 | Orchestration J1-J9 | `2X_PASS` |
| FLOW-020 | Project Start lifecycle | `2X_PASS` |
| FLOW-021 | Workspace Defaults full wizard | `2X_PASS` |
| FLOW-022 | Workspace Pipeline full | `2X_PASS` |

## 19. Co AEIS Może Wykonać Dzisiaj

AEIS może wykonać:

- lokalny start systemu;
- route smoke i dashboard probe;
- projektowy intake;
- workspace pipeline;
- project lifecycle 16-19;
- W18 freeze księgi/masterplanu/build;
- execution preparation;
- live smoke workers;
- dispatch control;
- Phase 34-41 closeout;
- worker registry lifecycle;
- orchestration J1-J9;
- skills create/execute/signal;
- funding reports/tabs i dużą część funding backendu;
- mobile queue navigation;
- evidence collection and freeze.

AEIS nie powinien jeszcze bez dodatkowej kontroli wykonywać:

- realnego production deployu;
- zewnętrznego funding submit bez Human Gate;
- operacji na sekretach poza kontrolowanym dummy flow;
- pełnego autonomous execution bez operatora;
- cloud/VPS provisioning jako production action;
- mobile approval jako zamrożony flow, dopóki nie przejdzie 2x.

## 20. Production Readiness

| Obszar | Status produkcyjny | Dlaczego |
|---|---|---|
| Backend startup | `STAGING_CANDIDATE` | Health i API działają. |
| Frontend dashboard | `STAGING_CANDIDATE` | Shell i wiele route/action flows ma evidence. |
| Workspace/project spine | `STAGING_CANDIDATE` | FLOW-020/021/022 `2X_PASS`. |
| Execution local | `DEV/STAGING` | Phase/action scopes frozen, brak production deploy freeze. |
| W18 router | `STAGING_CANDIDATE` dla project freeze/build | Central route contract działa. |
| Human Gate | `DEV_READY` | Działa, ale split planes. |
| Model Council | `DEV_READY/PARTIAL` | J-flow działa, globalny council plane niepełny. |
| Funding | `STAGING_CANDIDATE` dla reports/backend, `PARTIAL` dla full submit | Duży domain, ale submission/governance wymaga dalszego freeze. |
| Memory | `NOT_READY/PARTIAL` | API istnieje, globalny lifecycle niepełny. |
| Skills | `DEV_READY` | UI/registry/execution scope frozen, pełny runtime reuse nie. |
| Mobile | `PARTIAL` | Queue działa, full approve/device binding nie. |
| Lab modules | `DEV_READY/PARTIAL` | Świadome rozszerzenia, nie core production. |
| Security/secrets | `PARTIAL` | Readonly checked, key lifecycle pending. |

## 21. Najważniejsze Drifty I Ryzyka

1. Human Gate split brain: workspace, global governance, funding i W18 nie są jeszcze jednym plane.
2. Memory split: global memory, evidence i per-project DB nie są jeszcze jednym source of truth.
3. Skills split: registry/executor istnieją, ale nie karmią jeszcze całego project loop.
4. Model plane split: provider registry, model registry, council settings i orchestration routing są osobne.
5. Funding governance: moduł jest realny, ale external submission wymaga mocniejszej globalnej integracji z Human Gate.
6. Mobile: queue działa, pełne mobile approval/device binding jest pending.
7. Route-only surfaces: wiele stron renderuje, ale akcje nie mają jeszcze 2x freeze.
8. Production deploy: Phase 40 ma rehearsal/probe, ale nie pełny production cloud rollout freeze.

## 22. Reguły Utrzymania Systemu

- Nie cofać zamrożonych flow bez powtórzenia testów 2x.
- Każda nowa mutująca komenda W18 musi mieć `CommandIntent`, `CommandRoute`, `CommandExecution`.
- Każda decyzja D3+ musi mieć Human Gate albo jawny evidence pack.
- UI nie może raportować sukcesu, jeśli backend zwraca failed/error.
- `204 No Content` musi być obsługiwane bez fałszywego JSON error.
- Funding external submit wymaga gate i dowodu.
- `localhost/127.0.0.1` są dozwolone jako lokalne URL runtime; realne placeholder endpointy `example.com` dalej blokują artifact.
- Freeze nie oznacza zamrożenia całego systemu, tylko konkretnego scope w registerze.

## 23. Plan Dalszego Rozwoju Dokumentacji

Następne rozszerzenia tej księgi powinny powstać jako osobne rozdziały po kolejnych freeze:

1. pełny funding end-to-end: profile save, idea conversion, application, export, submission approval, blocked real submit;
2. memory write/search/evidence przez dashboard;
3. mobile approve/reject i device binding;
4. secrets dummy add/validate/rotate;
5. global terminal command arbitration poza projektem;
6. production deploy rehearsal z rollbackiem;
7. apps-builder wizard i demo app lifecycle;
8. test center full W14 human simulation.

## 24. Aneks: Pełny Katalog Route Pages

Ten katalog pochodzi z `src/sylion-frontend/src/app/(app)/**/page.tsx`. Status `opisane` oznacza, że route jest uwzględnione w tej księdze, ale nie każdy route ma pełny action freeze.

### 24.1. Advisor, Cockpit I Operator

| Route | Rola | Status |
|---|---|---|
| `/advisor` | Doradca na żywo, karty rekomendacji. | `PARTIAL_ROUTE` |
| `/advisor/[cardId]` | Detail karty Advisora. | `PARTIAL_ROUTE` |
| `/advisor/cockpit` | Kokpit Advisora. | `PARTIAL_ROUTE` |
| `/dashboard/operator-monitor` | Monitor operatora/projektów. | `2X_PASS` route |
| `/overview` | Główny przegląd techniczny. | `2X_PASS` route |
| `/onboarding` | Pierwsze uruchomienie. | `PARTIAL_ROUTE` |
| `/auth` | Lokalna powierzchnia auth. | `ROUTE_2X` |
| `/settings` | Ustawienia ogólne. | `PARTIAL_2X_PASS` tabs |
| `/settings/profile` | Profil operatora. | `PARTIAL_2X_PASS` route |
| `/settings/advisor` | Ustawienia Advisora. | `PARTIAL_ROUTE` |
| `/faq` | Pomoc i FAQ. | `ROUTE_2X` |
| `/v2/admin` | Przegląd administracyjny v2. | `ROUTE_2X` |

### 24.2. Workspace, Projekty I Planowanie

| Route | Rola | Status |
|---|---|---|
| `/workspace` | Obszar pracy AI i pipeline. | tabs + pipeline `2X_PASS` |
| `/workspace-defaults` | Domyślne ustawienia workspace. | `2X_PASS` |
| `/project-start` | Start projektu i fazy 16-19. | `2X_PASS` |
| `/projects` | Lista projektów. | `2X_PASS` w FLOW-020 |
| `/projects/[projectId]` | Detail projektu, W18, status. | `2X_PASS` w FLOW-020/013 |
| `/projects/[projectId]/lifecycle` | Lifecycle chart projektu. | `2X_PASS` |
| `/projects/[projectId]/orchestration` | Orkiestracja konkretnego projektu. | `PARTIAL_ROUTE` |
| `/idea-vault` | Skarbiec pomysłów. | `PARTIAL_ROUTE` |
| `/idea-vault/[id]` | Detail pomysłu i przejście do workspace. | `PARTIAL_ROUTE` |
| `/planning` | Planowanie/Masterplan. | `PARTIAL_ROUTE` |
| `/masterplan` | Masterplan i prawda projektu. | `PARTIAL_ROUTE` |
| `/source-of-truth` | Source of Truth. | `PARTIAL_ROUTE` |
| `/council-to-ksiega` | Deliberacja i Księga. | `PARTIAL_ROUTE` |
| `/book` | Księga systemu w UI. | `ROUTE_2X` |
| `/lifecycle` | Ogólny lifecycle. | `ROUTE_2X` |
| `/pipeline` | Linia wykonania techniczna. | `PARTIAL_ROUTE` |

### 24.3. Execution, Runtime I Workery

| Route | Rola | Status |
|---|---|---|
| `/execution-start` | Fazy wykonania, dispatch, worker controls. | `2X_PASS` scopes |
| `/workers` | Worker registry, heartbeat, topology, delete. | `2X_PASS` |
| `/agents` | Agenci. | `ROUTE_2X` |
| `/modules` | Moduły. | `ROUTE_2X` |
| `/runtime` | Runtime overview. | `PARTIAL_ROUTE_2X` |
| `/health` | Health dashboard. | `2X_PASS` |
| `/observability` | Logs/metrics/traces. | `PARTIAL_ROUTE_2X` |
| `/environments` | Środowiska. | `PARTIAL_ROUTE` |
| `/environments/theater` | Teatr środowisk. | `PARTIAL_ROUTE` |
| `/deploy` | Deploy/rollback. | `PARTIAL_ROUTE` |
| `/builds` | Build data. | `ROUTE_2X` |
| `/build-state` | Stan buildów. | `ROUTE_2X` |
| `/bundles` | Pakiety. | `ROUTE_2X` |
| `/capacity` | Pojemność. | `ROUTE_2X` |
| `/autoscaler` | Autoscaler. | `PARTIAL_ROUTE` |
| `/performance` | Wydajność. | `ROUTE_2X` |
| `/sla` | SLA. | `ROUTE_2X` |
| `/circuits` | Circuit breakers. | `ROUTE_2X` |
| `/healing` | Samonaprawa. | `ROUTE_2X` |
| `/rebuild` | Odbudowa. | `ROUTE_2X` |

### 24.4. Governance, Human Gate, Guards I Audit

| Route | Rola | Status |
|---|---|---|
| `/governance` | Governance/Rada. | `PARTIAL_2X_PASS` |
| `/human-gate` | Bramka człowieka. | `PARTIAL_2X_PASS` |
| `/model-council` | Model Council. | `PARTIAL_ROUTE` |
| `/decisions` | Decyzje. | `PARTIAL_ROUTE` |
| `/gates` | Bramki. | `PARTIAL_ROUTE_2X` |
| `/guards` | Panel strażników. | `PARTIAL_ROUTE` |
| `/coherence-guard` | Coherence Guard. | `PARTIAL_ROUTE` |
| `/cost-guard` | Cost Guard. | `PARTIAL_ROUTE` |
| `/security-guard` | Security Guard. | `PARTIAL_ROUTE` |
| `/quality-guard` | Quality Guard. | `PARTIAL_ROUTE` |
| `/provenance-guard` | Provenance Guard. | `PARTIAL_ROUTE` |
| `/policy` | Polityki. | `PARTIAL_ROUTE` |
| `/audit` | Audit viewer. | `PARTIAL_ROUTE_2X` |
| `/audit-trail` | Ścieżka audytu. | `ROUTE_2X` |
| `/evidence` | Evidence packages. | `PARTIAL_ROUTE_2X` |
| `/evidence-spine` | Evidence spine. | `ROUTE_2X` |
| `/terminal` | Globalny terminal W18. | `PARTIAL` |
| `/terminal/replay` | Terminal replay. | `PARTIAL_ROUTE_2X` |

### 24.5. Orchestration, Council I Test Center

| Route | Rola | Status |
|---|---|---|
| `/orchestration` | Hub orchestration J1-J9. | `2X_PASS` |
| `/orchestration/llm-routing` | J1 LLM routing. | `2X_PASS` |
| `/orchestration/council-rules` | J2 council rules. | `2X_PASS` |
| `/orchestration/auditor` | J3 auditor/gate. | `2X_PASS` |
| `/orchestration/fixer` | J4 fixer. | `2X_PASS` |
| `/orchestration/dispatch` | J5 dispatch. | `2X_PASS` |
| `/orchestration/tests` | J6 golden tests. | `2X_PASS` |
| `/orchestration/teams` | J7 teams. | `2X_PASS` |
| `/orchestration/event-map` | J8 event map. | `2X_PASS` |
| `/orchestration/conversations` | J9 conversations. | `2X_PASS` |
| `/test-center` | Centrum testów. | `PARTIAL_ROUTE` |
| `/test-center/dashboard` | Dashboard test center. | `PARTIAL_ROUTE` |
| `/test-center/catalog` | Katalog testów. | `PARTIAL_ROUTE` |
| `/test-center/theater` | Teatr modeli. | `PARTIAL_ROUTE` |
| `/test-center/auto-repair` | Auto-repair. | `PARTIAL_ROUTE` |
| `/test-center/human-lab` | Human lab. | `2X_PROBED` |
| `/test-center/no-mock-scan` | No-mock scan. | `PARTIAL_ROUTE` |
| `/test-center/release-gate` | Release gate. | `PARTIAL_ROUTE` |
| `/test-center/simulation` | Simulation. | `2X_PROBED` |
| `/test-center/truth-alignment` | Truth alignment. | `PARTIAL_ROUTE` |
| `/golden-tests` | Golden tests. | `ROUTE_2X` |
| `/evaluator` | Ewaluator. | `ROUTE_2X` |

### 24.6. Funding, Integracje, Mobile I Lab

| Route | Rola | Status |
|---|---|---|
| `/funding` | Doradca grantów i funding workflow. | `PARTIAL_2X_PASS` |
| `/operator-mobile` | Mobile operator home. | `PARTIAL_2X_PASS` |
| `/operator-mobile/queue` | Mobile ticket queue. | `PARTIAL_2X_PASS` |
| `/operator-mobile/queue/[ticketId]` | Detail ticketu mobile. | `PARTIAL_ROUTE` |
| `/operator-mobile/devices` | Mobile devices. | `PARTIAL_ROUTE` |
| `/mobile` | Mobile surface. | `PARTIAL_ROUTE` |
| `/devices` | Devices lab. | `PARTIAL_ROUTE` |
| `/sdr` | SDR lab. | `PARTIAL_ROUTE` |
| `/cellular` | Cellular lab. | `PARTIAL_ROUTE` |
| `/federation` | Federation. | `PARTIAL_ROUTE` |
| `/integrations` | Integrations. | `ROUTE_2X` |
| `/connectors` | Connectors. | `ROUTE_2X` |
| `/notifications` | Notifications. | `ROUTE_2X` |
| `/apps-builder` | Apps Builder. | `PARTIAL_ROUTE` |
| `/apps-builder/[appId]` | Detail aplikacji. | `PARTIAL_ROUTE` |
| `/apps-builder/wizard` | Wizard Apps Builder. | `PARTIAL_ROUTE` |

### 24.7. Security, Modele, Budżet I Wiedza

| Route | Rola | Status |
|---|---|---|
| `/ai-models` | Modele AI i providerzy. | `PARTIAL_ROUTE` |
| `/budget` | Budżet modeli. | `PARTIAL_ROUTE` |
| `/costs` | Koszty. | `ROUTE_2X` |
| `/secrets` | Sekrety/klucze API. | `PARTIAL_2X_PASS` readonly |
| `/security-scan` | Skan bezpieczeństwa. | `ROUTE_2X` |
| `/auth` | Auth. | `ROUTE_2X` |
| `/roles` | Role. | `ROUTE_2X` |
| `/role-catalog` | Katalog ról W7. | `PARTIAL_ROUTE` |
| `/contracts` | Kontrakty. | `ROUTE_2X` |
| `/ontology` | Ontologia. | `PARTIAL_ROUTE` |
| `/architecture-layers` | Warstwy AEIS W1-W19. | `LIVE_VERIFIED` |
| `/memory` | Memory UI. | `PARTIAL_ROUTE_2X` |
| `/skills` | Skills UI. | `2X_PASS` for selected actions |
| `/templates-setup` | Szablony. | `PARTIAL_ROUTE` |
| `/quality` | Quality. | `ROUTE_2X` |
| `/risk` | Risk. | `ROUTE_2X` |
| `/drift` | Drift. | `ROUTE_2X` |
| `/anomalies` | Anomalies. | `2X_PROBED` |

### 24.8. Demo I Pomocnicze Powierzchnie

| Route | Rola | Status |
|---|---|---|
| `/demo/crm` | Demo CRM. | `ROUTE_EXISTS` |
| `/demo/factory` | Demo factory. | `ROUTE_EXISTS` |
| `/demo/funding` | Demo funding. | `ROUTE_EXISTS` |
| `/demo/marketplace` | Demo marketplace. | `ROUTE_EXISTS` |
| `/demo/mobile-inspector` | Demo mobile inspector. | `ROUTE_EXISTS` |
| `/demo/portal` | Demo portal. | `ROUTE_EXISTS` |
| `/apps-builder` | Builder apps, także do demo. | `PARTIAL_ROUTE` |

## 25. Aneks: API Route Families

Backend ma bardzo szeroki katalog API. Najważniejsze rodziny route:

| Rodzina | Przykładowy plik | Rola |
|---|---|---|
| Workspace | `ai_workspace_routes.py`, `workspace_defaults_routes.py`, `workspace_ws_routes.py` | workspace, defaults, sessions, council, Human Gate, ideas. |
| Pipeline | `pipeline_routes.py` | pipeline ideas, runs, execute, steps, cancel. |
| Projects | `project_start_routes.py`, `projects_routes.py`, `projects_freeze_routes.py` | intake, create, detail, lifecycle, freeze. |
| Execution | `execution_start_routes.py`, `execution_routes.py`, `execution_guard_routes.py` | phases, dispatch, execution runtime, guards. |
| Workers | `worker_routes.py`, `worker_monitor_routes.py`, `autoscaler_routes.py` | worker registry, monitor, autoscaler. |
| Orchestration | `orchestration_routes.py`, `teams_routes.py`, `agent_theater_routes.py` | J1-J9, teams, conversations, theater. |
| W18/Terminal | `terminal_routes.py`, `replay_routes.py` | command routing, terminal exec, replay. |
| Governance | `governance_routes.py`, `gates_routes.py`, `council_routes.py`, `council_signoff_routes.py` | tickets, approvals, policies, council. |
| Funding | `funding_autopilot/routes.py` | company, calls, ideas, matching, applications, submission, reports. |
| Memory | `memory_routes.py`, `knowledge_routes.py` | memory index, search, evidence. |
| Skills | `skills_routes.py` | registry, runtime, execution, demand signal. |
| Models | `ai_providers_routes.py`, `provider_catalog_routes.py`, `model_registry_routes.py`, `model_budget_routes.py` | provider catalog, keys, model registry, budgets. |
| Security | `auth_routes.py`, `secret_routes.py`, `vault_routes.py`, `security_routes.py`, `security_profiles_routes.py`, `security_audit_routes.py` | auth, vault, profiles, scans. |
| Observability | `observability_routes.py`, `metrics_routes.py`, `monitoring_routes.py`, `health_routes.py`, `runtime_truth_routes.py` | health, metrics, logs, traces, runtime truth. |
| Audit/Evidence | `audit_routes.py`, `audit_query_routes.py`, `audit_sink_routes.py`, `evidence_timeline_routes.py` | audit event write/query/replay. |
| Apps/Demo | `apps_routes.py`, `demo_*_routes.py` | apps builder and demo surfaces. |
| Lab | `device_routes.py`, `sdr_routes.py`, `cellular_routes.py`, `container_routes.py`, `vps_routes.py` | devices, SDR, cellular, containers, VPS. |
| Quality/Test | `quality_routes.py`, `quality_gate_routes.py`, `test_center_routes.py`, `testing_routes.py`, `golden_set_routes.py`, `regression_routes.py` | quality gates, test center, golden/regression tests. |
| Policy/Config | `policy_routes.py`, `autonomy_routes.py`, `autonomy_configuration_routes.py`, `templates_setup_routes.py` | policies, autonomy, templates. |

## 26. Podsumowanie

AEIS jest już dużym systemem operacyjnym, nie szkicem. Jego najmocniejszy rzeczywisty spine to:

`workspace/project-start -> project -> W18 -> execution-start -> workers/orchestration -> evidence/freeze`

Funding jest realnym, rozbudowanym pionem domenowym i wymaga traktowania jako pełny moduł biznesowy, nie dodatek. Największym zadaniem architektonicznym nie jest budowanie od zera, tylko konsolidacja istniejących planes: Human Gate, memory, skills, model council, funding governance i mobile.

Ta księga jest punktem odniesienia dla dalszych napraw: wszystko, co ma status `2X_PASS`, powinno być chronione regresjami; wszystko, co ma `PARTIAL`, wymaga osobnego pełnego testu przez dashboard i freeze po dwóch czystych przebiegach.

## 27. Instrukcja Operatorska: Przykładowe Scenariusze I Screeny Z Pracy

Ta sekcja jest praktyczną instrukcją obsługi na podstawie realnych przebiegów dashboardu. Nie zastępuje rejestru freeze, tylko pokazuje operatorowi, jak ma wyglądać poprawna praca: gdzie wejść, co kliknąć, co powinno się zmienić po kliknięciu, kiedy zapisać błąd i kiedy wolno zamrozić funkcję.

Zasada prowadzenia testu:

1. Operator otwiera wskazaną trasę dashboardu.
2. Wykonuje kroki dokładnie w podanej kolejności.
3. Po każdym kliknięciu sprawdza widok, request/API albo zapis evidence.
4. Jeżeli wynik różni się od instrukcji, wpisuje błąd do bug ledger i nie zamraża funkcji.
5. Ten sam scenariusz trzeba wykonać dwa razy.
6. Dopiero dwa czyste przebiegi dają status `2X_PASS`.

### 27.1. Scenariusz: Workspace Pipeline Od Pomysłu Do Wyniku

Status: `2X_PASS` dla `/workspace` submit/execute oraz zakładek `Pipeline`, `Kod`, `Wynik`.

Cel operatora: wysłać pomysł do pipeline, uruchomić run, poczekać na `complete`, sprawdzić kroki, kod i wynik.

Trasa UI: `/workspace`

Powiązane API:

- `POST /api/v1/pipeline/ideas`
- `POST /api/v1/pipeline/runs/{run_id}/execute`
- `GET /api/v1/pipeline/runs/{run_id}`
- `GET /api/v1/pipeline/runs/{run_id}/steps`

Kroki:

| Krok | Akcja operatora | Co powinno się stać po kliknięciu | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz `/workspace`. | Dashboard ładuje workspace bez stuck loading i bez czerwonego błędu. | Widoczny formularz pomysłu i obszar pipeline. |
| 2 | Wpisz unikalny pomysł w polu wysyłki. | Tekst zostaje w polu, przycisk wysyłki jest dostępny. | Formularz nie czyści się przed wysłaniem. |
| 3 | Kliknij `Wyślij`. | Powstaje nowy run ze statusem `pending`. | API tworzy run, a UI pokazuje go na liście. |
| 4 | Wybierz nowy run. | Panel szczegółów pokazuje wybrany run. | ID runu zgadza się z odpowiedzią backendu. |
| 5 | Kliknij `Wykonaj`. | Backend uruchamia run, status przechodzi przez wykonanie do `complete`. | `quality_gate=passed`, brak `failed`, brak pustych kroków. |
| 6 | Otwórz zakładkę `Kod`. | Zakładka pokazuje rzeczywisty `step.result`, nie placeholder. | Dane pochodzą z wyniku kroku. |
| 7 | Otwórz zakładkę `Wynik`. | Zakładka pokazuje log i wynik wykonania. | Output nie jest pusty i odpowiada statusowi kroku. |

Screen 1 - workspace po załadowaniu:

![Workspace loaded](docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_01_workspace_loaded_2026-05-14T12-39-30-039Z.png)

Screen 2 - wpisany pomysł przed wysłaniem:

![Workspace idea filled](docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_02_idea_filled_2026-05-14T12-39-30-039Z.png)

Screen 3 - kliknięcie wykonania runu:

![Workspace execute clicked](docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_04_execute_clicked_2026-05-14T12-39-30-039Z.png)

Screen 4 - run zakończony statusem complete:

![Workspace run complete](docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_05_run_complete_selected_2026-05-14T12-39-30-039Z.png)

Screen 5 - zakładka Kod:

![Workspace code tab](docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_06_code_tab_2026-05-14T12-39-30-039Z.png)

Screen 6 - zakładka Wynik:

![Workspace output tab](docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_07_output_tab_2026-05-14T12-39-30-039Z.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| Run nie pojawia się po kliknięciu `Wyślij`. | Brak nowego runu albo API error. | Zapisuje błąd, screenshot formularza i odpowiedź API. |
| Run kończy się `failed` albo `cancelled`. | Status nie przechodzi do `complete`. | Nie zamraża flow, zapisuje run ID i log kroku. |
| Zakładka `Kod` pokazuje placeholder. | Brak rzeczywistego `step.result`. | Oznacza regresję `DASH-E2E-018`. |
| Zakładka `Wynik` jest pusta. | Brak outputu mimo `complete`. | Oznacza regresję `DASH-E2E-019` albo błąd mapowania outputu. |

Warunek zamrożenia: dwa przebiegi muszą zakończyć się `complete`, `quality_gate=passed`, `issueCount=0`, `hardEventCount=0`, `apiErrorCount=0`.

### 27.2. Scenariusz: Workspace Defaults I Konfiguracja Startowa Projektu

Status: `2X_PASS` dla wybranych profili i zapisu ustawień workspace defaults.

Cel operatora: ustawić domyślne parametry pracy projektu, zapisać je i potwierdzić, że dziedziczą się do kolejnych flow.

Trasa UI: `/workspace-defaults`

Kroki:

| Krok | Akcja operatora | Co powinno się stać | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz `/workspace-defaults`. | Widoczny jest profil lub wizard domyślnych ustawień. | Brak stuck loading. |
| 2 | Ustaw sekcję welcome/intake. | Formularz zapisuje dane profilu startowego. | Zapis potwierdzony w UI/API. |
| 3 | Ustaw budżet i estymację. | System pokazuje limity lub estymaty kosztów. | Brak utraty danych po przejściu dalej. |
| 4 | Ustaw autonomię. | Poziom autonomii jest zapisany jawnie. | Decyzje wyższego ryzyka nadal wymagają bramki. |
| 5 | Ustaw mobile/notifications. | Powiadomienia i tryb operatora są widoczne w konfiguracji. | Zapis pozostaje po odświeżeniu. |
| 6 | Zapisz acceptance. | Konfiguracja jest gotowa jako default dla nowego projektu. | Drugi przebieg daje ten sam wynik. |

Screen 1 - workspace defaults po załadowaniu:

![Workspace defaults loaded](docs/aeis_repair_v2/workspace_defaults_full/evidence/screenshots/pass2_apps_internal_00_loaded_2026-05-14T11-58-27-462Z.png)

Screen 2 - zapis budżetu:

![Workspace defaults budget](docs/aeis_repair_v2/workspace_defaults_full/evidence/screenshots/pass2_apps_internal_02_budget_estimate_saved_2026-05-14T11-58-27-462Z.png)

Screen 3 - zapis autonomii:

![Workspace defaults autonomy](docs/aeis_repair_v2/workspace_defaults_full/evidence/screenshots/pass2_apps_internal_03_autonomy_saved_2026-05-14T11-58-27-462Z.png)

Screen 4 - akceptacja konfiguracji:

![Workspace defaults acceptance](docs/aeis_repair_v2/workspace_defaults_full/evidence/screenshots/pass2_apps_internal_10_acceptance_2026-05-14T11-58-27-462Z.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| Zapis znika po odświeżeniu. | Formularz wraca do starych wartości. | Zapisuje before/after i response API. |
| Autonomia pozwala ominąć Human Gate. | Ryzykowna akcja idzie bez zatwierdzenia. | Blokuje freeze, tworzy błąd governance. |
| Profil nie dziedziczy się do projektu. | Project start ma inne limity niż defaults. | Zapisuje projekt ID i porównanie konfiguracji. |

Warunek zamrożenia: zapis musi przetrwać odświeżenie, drugi przebieg i użycie w downstream project start.

### 27.3. Scenariusz: Human Gate - Zatwierdzanie I Odrzucanie Decyzji

Status: `PARTIAL_2X_PASS` dla kontrolowanych akcji approve/reject, pełne governance nadal wymaga rozszerzenia na wszystkie typy decyzji.

Cel operatora: sprawdzić, że decyzje wymagające człowieka są widoczne, można je zatwierdzić albo odrzucić, a wynik wraca do projektu/runtime.

Trasa UI: `/human-gate`

Kroki:

| Krok | Akcja operatora | Co powinno się stać | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz `/human-gate`. | Widać kolejkę decyzji, priorytet, źródło i status. | Brak pustej strony bez informacji. |
| 2 | Wybierz decyzję testową. | UI pokazuje szczegóły decyzji. | Operator wie, czego dotyczy decyzja. |
| 3 | Kliknij approve. | Status zmienia się na zatwierdzony. | Backend zapisuje decyzję. |
| 4 | W drugim scenariuszu kliknij reject. | Status zmienia się na odrzucony. | Projekt/runtime nie kontynuuje odrzuconej ścieżki. |

Screen 1 - Human Gate desktop:

![Human Gate desktop](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/human-gate_desktop_pass2_after_d004.png)

Screen 2 - approve po kliknięciu:

![Human Gate approve after](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/human_gate_pass2_approve_after.png)

Screen 3 - reject po kliknięciu:

![Human Gate reject after](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/human_gate_pass2_reject_after.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| Przycisk działa w UI, ale backend nie zmienia statusu. | Po odświeżeniu decyzja wraca. | Zapisuje response API i screenshot po reload. |
| Decyzja nie ma kontekstu. | Operator nie widzi projektu, ryzyka ani powodu bramki. | Zgłasza błąd usability/governance. |
| Odrzucona decyzja dalej uruchamia execution. | Runtime ignoruje Human Gate. | To blocker freeze governance. |

Warunek zamrożenia: decyzja musi zmienić stan w UI, API, projekcie i audit trail.

### 27.4. Scenariusz: W18 Terminal Router, Freeze I Authorize Build

Status: `2X_PASS` dla W18 freeze/build routing w przetestowanym zakresie.

Cel operatora: nie wpisywać surowych komend w przypadkowe środowisko, tylko używać routera W18, który przypisuje intencję do projektu, bramki, modelu i akcji wykonawczej.

Trasy UI:

- `/terminal`
- `/terminal/replay`
- `/projects/[projectId]`
- `/human-gate`

Kroki:

| Krok | Akcja operatora | Co powinno się stać | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz projekt z aktywnym W18. | Widoczny jest status komend i freeze. | Projekt ma jednoznaczny kontekst. |
| 2 | Uruchom freeze canon/masterplan. | System tworzy decyzję lub stan freeze dla projektu. | Operacja nie trafia do losowego terminala. |
| 3 | Przejdź do Human Gate, jeżeli wymagana. | Widać decyzję dotyczącą build/freeze. | Operator zna powód zatwierdzenia. |
| 4 | Kliknij authorize build. | Build zostaje autoryzowany dla właściwego projektu. | Status projektu i W18 są spójne. |
| 5 | Otwórz replay. | Da się odtworzyć ślad komendy i decyzji. | Evidence pozwala sprawdzić, kto/co wywołało akcję. |

Screen 1 - W18 authorize build:

![W18 authorize build](docs/aeis_repair_v2/w18_router_repair/evidence/screenshots/pass2_authorize_build_project_f3e237d2a95b_2026-05-13T22-03-46-999Z.png)

Screen 2 - Human Gate status projektu:

![W18 human gate status](docs/aeis_repair_v2/w18_router_repair/evidence/screenshots/pass2_human_gate_status_project_f3e237d2a95b_2026-05-13T22-03-46-999Z.png)

Screen 3 - terminal/replay jako powierzchnia kontroli:

![Terminal replay](docs/aeis_repair_v2/transactional_runtime_audit/evidence/screenshots/w18_terminal_replay_2026-05-13_2052.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| UI sugeruje terminal, ale nie ma pola komendy. | Operator nie ma jak wpisać ani wysłać intencji. | Zgłasza brak funkcji terminal input/routing. |
| Komenda nie ma właściciela. | Nie wiadomo, czy rządzi nią człowiek, agent, model czy projekt. | Zgłasza błąd governance W18. |
| Komenda trafia do złego środowiska. | Efekt pojawia się w innym projekcie/runtime. | Blokuje freeze, zapisuje ID obu środowisk. |

Reguła docelowa: każda komenda musi mieć `actor`, `project_id`, `environment_id`, `command_intent`, `risk_class`, `approval_policy`, `dispatch_target`, `audit_event_id` i `rollback_hint`.

### 27.5. Scenariusz: Execution Start, Fazy 32-41 I Dispatch Control

Status: `PARTIAL_2X_PASS` dla przetestowanych fragmentów start/stop, faz 32-41 i dispatch control.

Cel operatora: uruchomić execution dla projektu, przejść przez fazy, sprawdzić dispatch i móc bezpiecznie zatrzymać albo anulować.

Trasa UI: `/execution-start`

Kroki:

| Krok | Akcja operatora | Co powinno się stać | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz `/execution-start`. | UI pokazuje projekt, runtime i dostępne fazy. | Brak niejawnego startu bez operatora. |
| 2 | Zainicjuj Phase 32. | Projekt przechodzi w fazę startową. | Status zapisany w backendzie. |
| 3 | Uruchom Phase 33. | Runtime pokazuje rozpoczęcie pracy. | Event execution jest widoczny. |
| 4 | Przejdź przez fazy 34-41. | Każda faza pokazuje osobny status. | Brak pomijania etapów. |
| 5 | Sprawdź dispatch. | Widać cel dispatch, status i możliwość kontroli. | Dispatch nie jest anonimowy. |
| 6 | Użyj cancel/stop w scenariuszu kontrolnym. | System zatrzymuje proces bez utraty audit trail. | Po reload stan nadal jest poprawny. |

Screen 1 - Phase 32 initialized:

![Execution phase 32](docs/aeis_repair_v2/execution_start_router_repair/evidence/screenshots/pass2_project_97bfd7670d3d_2026-05-13T22-23-31-684Z_phase32_initialized.png)

Screen 2 - Phase 33 started:

![Execution phase 33](docs/aeis_repair_v2/execution_start_router_repair/evidence/screenshots/pass2_project_97bfd7670d3d_2026-05-13T22-23-31-684Z_phase33_started.png)

Screen 3 - faza 41:

![Execution phase 41](docs/aeis_repair_v2/execution_phases_34_41/evidence/screenshots/execution_34_41_2026-05-14T09-40-35-269Z_pass2_phase41.png)

Screen 4 - dispatch:

![Orchestration dispatch](docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j5_dispatch_2026-05-14T10-54-40-012Z.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| Faza przeskakuje bez eventu. | UI pokazuje kolejny etap, ale audit nie ma śladu. | Zgłasza błąd evidence/runtime. |
| Cancel nie zatrzymuje pracy. | Po kliknięciu proces nadal działa. | Zapisuje worker/run ID i screenshot po reload. |
| Dispatch nie pokazuje celu. | Nie wiadomo, który agent/worker/model pracuje. | Zgłasza błąd command ownership. |

Warunek zamrożenia: fazy muszą mieć kolejność, widoczny status, ślad API/evidence i kontrolę przerwania.

### 27.6. Scenariusz: Skills - Utworzenie, Wykonanie I Demand Signal

Status: `2X_PASS` dla create/execute/signal w przetestowanym zakresie.

Cel operatora: stworzyć skill, uruchomić go kontrolnie i sprawdzić, że demand signal zapisuje zapotrzebowanie.

Trasa UI: `/skills`

Kroki:

| Krok | Akcja operatora | Co powinno się stać | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz `/skills`. | Widać rejestr skills i formularze/akcje. | Brak stuck loading. |
| 2 | Utwórz testowy skill. | Skill pojawia się w rejestrze. | Backend zwraca ID i status. |
| 3 | Kliknij execute. | Execution zwraca wynik kontrolny. | UI pokazuje rezultat, nie tylko toast. |
| 4 | Wyślij demand signal. | System zapisuje sygnał zapotrzebowania. | Signal jest widoczny po odświeżeniu/API. |

Screen 1 - skills po utworzeniu:

![Skills create](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/skills_full_pass2_create_after.png)

Screen 2 - skills po wykonaniu:

![Skills execute](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/skills_full_pass2_execute_after.png)

Screen 3 - skills demand signal:

![Skills signal](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/skills_full_pass2_signal_after.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| Skill tworzy się tylko w UI. | Po reload znika. | Zapisuje błąd rejestru. |
| Execute nie zwraca wyniku. | Brak stdout/result/error. | Zapisuje request i timeout. |
| Demand signal nie zapisuje się. | Nie ma sygnału po odświeżeniu. | Zapisuje payload i response API. |

Warunek zamrożenia: create, execute i signal muszą przejść dwa razy, z widocznym stanem po reload.

### 27.7. Scenariusz: Memory - Wyszukiwanie I Dowód Wiedzy

Status: `PARTIAL_ROUTE_2X` dla tras memory, pełny zapis/search/evidence wymaga osobnego freeze.

Cel operatora: sprawdzić, czy memory pokazuje wiedzę systemu i czy wynik można powiązać z evidence.

Trasa UI: `/memory`

Kroki:

| Krok | Akcja operatora | Co powinno się stać | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz `/memory`. | UI pokazuje stan memory albo kontrolowany empty state. | Brak błędu renderowania. |
| 2 | Wyszukaj hasło związane z projektem. | Wyniki pojawiają się z kontekstem. | Wynik ma źródło lub evidence path. |
| 3 | Otwórz szczegół wyniku. | Widać dane, źródło i powiązania. | Nie ma anonimowej wiedzy bez provenance. |

Screen - memory UI:

![Memory UI](docs/aeis_repair_v2/evidence/R3_6_memory_skills_truth/memory_ui_smoke_after.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| Wynik nie ma źródła. | Memory pokazuje tekst bez provenance. | Oznacza błąd evidence policy. |
| Search zwraca dane innego projektu. | Kontekst się miesza. | Blokuje freeze memory. |
| Pusty wynik nie jest wyjaśniony. | Operator nie wie, czy to brak danych czy błąd. | Zgłasza błąd UX/runtime. |

Warunek zamrożenia: wynik musi mieć źródło, kontekst projektu i powtarzalność w drugim przebiegu.

### 27.8. Scenariusz: Funding - Od Profilu Firmy Do Wniosku I Raportu

Status: `PARTIAL_2X_PASS` dla zakładek i raportów; pełny zapis/eksport/submission wymaga osobnych przebiegów biznesowych.

Cel operatora: sprawdzić, że moduł funding prowadzi firmę przez profil, nabory, pomysły, matching, wniosek, submission i reporting.

Trasa UI: `/funding`

Zakładki:

- `Firma`
- `Nabory`
- `Pomysły`
- `Dopasowanie`
- `Wnioski`
- `Submission`
- `Raporty`

Kroki:

| Krok | Akcja operatora | Co powinno się stać | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz `/funding`. | Widoczny dashboard funding i zakładki. | Brak stuck loading. |
| 2 | Uzupełnij lub sprawdź profil firmy. | Dane firmy są widoczne w module. | Profil zapisuje się i wraca po reload. |
| 3 | Otwórz `Nabory`. | Widać listę programów/naborów. | Dane mają źródło lub kontrolowany empty state. |
| 4 | Otwórz `Pomysły`. | Można generować lub przeglądać pomysły grantowe. | Pomysł da się powiązać z profilem firmy. |
| 5 | Otwórz `Dopasowanie`. | System pokazuje scoring/matching. | Score ma wyjaśnienie. |
| 6 | Otwórz `Wnioski`. | Widać aplikacje i stan przygotowania. | Statusy są spójne. |
| 7 | Otwórz `Submission`. | UI pokazuje etap wysyłki/CRM/receipt. | Operator wie, co zostanie wysłane. |
| 8 | Otwórz `Raporty`. | Widać raportowanie, wykresy lub podsumowania. | Wykresy renderują się po resize/reload. |

Screen 1 - Funding dashboard:

![Funding dashboard](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/funding_desktop_pass2_after_d004.png)

Screen 2 - zakładka Dopasowanie:

![Funding matching](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/funding_full_pass2_tab_dopasowanie.png)

Screen 3 - zakładka Wnioski:

![Funding applications](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/funding_full_pass2_tab_wnioski.png)

Screen 4 - submission:

![Funding submission](docs/aeis_repair_v2/evidence/R3_7_funding_business_truth/funding_submission_ui_after.png)

Screen 5 - raporty:

![Funding reports](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/funding_full_pass2_tab_raporty.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| Nabory bez źródła. | Programy są pokazane bez daty/źródła. | Oznacza błąd provenance funding. |
| Matching bez wyjaśnienia. | Jest score, ale nie wiadomo dlaczego. | Zgłasza brak explainability. |
| Submission nie mówi, co wysyła. | Operator może kliknąć wysyłkę bez podglądu. | Blokuje freeze submission. |
| Raport nie renderuje wykresu. | Puste miejsce albo błąd chart. | Cofnięcie do naprawy UI. |

Warunek zamrożenia: każdy etap funding musi mieć zapis, powrót po reload, źródło danych i dowód screenshot/API.

### 27.9. Scenariusz: Operator Mobile - Kolejka Decyzji

Status: `PARTIAL_2X_PASS` dla nawigacji i queue view.

Cel operatora: sprawdzić, czy operator może przejrzeć kolejkę decyzji na mniejszym ekranie i czy układ nie zakrywa akcji.

Trasy UI:

- `/operator-mobile`
- `/operator-mobile/queue`
- `/operator-mobile/devices`

Kroki:

| Krok | Akcja operatora | Co powinno się stać | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz `/operator-mobile` w mobile viewport. | Dashboard mieści się na ekranie. | Brak poziomego overflow. |
| 2 | Przejdź do queue. | Widać listę decyzji/zadań. | Elementy są klikalne. |
| 3 | Otwórz szczegół zadania. | Widać kontekst i możliwe akcje. | Nie ma przycisków poza viewportem. |
| 4 | Sprawdź devices. | Urządzenia/operatorzy są pokazani albo jest kontrolowany empty state. | Brak niejawnego powiązania urządzenia. |

Screen 1 - operator mobile home:

![Operator mobile home](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/operator_mobile_pass2_home_mobile.png)

Screen 2 - operator mobile queue:

![Operator mobile queue](docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/screenshots/operator_mobile_pass2_queue_mobile.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| Akcja approve/reject poza ekranem. | Nie da się kliknąć bez zoomu. | Zgłasza błąd responsive UX. |
| Queue nie odświeża się po decyzji. | Decyzja zostaje na liście. | Zapisuje screenshot before/after i API. |
| Brak identyfikacji urządzenia. | Nie wiadomo, kto podjął decyzję. | Zgłasza błąd audit/operator identity. |

Warunek zamrożenia: mobile queue musi przejść dwa razy w mobile viewport, z widocznym kontekstem i akcją.

### 27.10. Scenariusz: Orchestration I Model Council Drilldown

Status: `PARTIAL_2X_PASS` dla wybranych powierzchni orchestration drilldown.

Cel operatora: sprawdzić, jak system rozdziela pracę między role, zespoły, audytora, dispatch i modele.

Trasy UI:

- `/orchestration`
- `/orchestration/teams`
- `/orchestration/llm-routing`
- `/orchestration/dispatch`
- `/model-council`

Kroki:

| Krok | Akcja operatora | Co powinno się stać | Warunek PASS |
|---|---|---|---|
| 1 | Otwórz `/orchestration`. | Widać główny stan orchestration. | Brak martwej strony. |
| 2 | Sprawdź teams/roles. | Role są jawne i powiązane z pracą. | Nie ma anonimowego wykonawcy. |
| 3 | Otwórz llm routing. | Widać reguły przypisania modeli. | Model nie jest wybierany niejawnie. |
| 4 | Otwórz dispatch. | Widać, dokąd trafia praca. | Cel dispatch jest audytowalny. |
| 5 | Otwórz Model Council. | Widać role rady albo kontrolowany stan braku sesji. | Decyzje D3+ wymagają evidence pack. |

Screen 1 - orchestration dispatch:

![Orchestration dispatch detail](docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j5_dispatch_2026-05-14T10-54-40-012Z.png)

Screen 2 - auditor gate:

![Orchestration auditor gate](docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j3_auditor_gate_2026-05-14T10-54-40-012Z.png)

Scenariusze błędne:

| Błąd | Objaw | Co robi operator |
|---|---|---|
| Brak roli wykonawcy. | Nie wiadomo, kto pracuje nad zadaniem. | Zgłasza błąd ownership. |
| Routing modeli jest ukryty. | Nie wiadomo, który model i dlaczego. | Zgłasza błąd model governance. |
| Dispatch bez rollbacku. | Nie ma sposobu przerwania. | Blokuje freeze dla tej ścieżki. |

Warunek zamrożenia: rola, model, dispatch target, audit event i rollback muszą być jawne.

### 27.11. Wzór Karty Instrukcji Dla Każdej Następnej Funkcji

Każda nowa funkcja lub zakładka dodawana do tej książki powinna mieć poniższą kartę:

```text
### [Nazwa funkcji]

Status:
Trasa UI:
Powiązane API:
Powiązane moduły:
Evidence path:
Screenshoty:

Cel operatora:

Kroki:
1. Otwórz...
2. Kliknij...
3. Sprawdź...
4. Zapisz evidence...

Co operator widzi po kliknięciu:

Co system robi po kliknięciu:

Scenariusz pozytywny:

Scenariusze błędne:

Warunek 2X_PASS:

Warunek zamrożenia:

Rollback / bezpieczne przerwanie:
```

Nie wolno wpisywać `2X_PASS`, jeżeli brakuje screenshotu, odpowiedzi API/logu albo drugiego przebiegu. Nie wolno zamrażać funkcji na podstawie samego istnienia pliku, routingu frontendowego albo mocka.
