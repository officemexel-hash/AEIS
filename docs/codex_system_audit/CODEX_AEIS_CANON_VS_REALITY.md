# CODEX AEIS CANON VS REALITY

**Status:** wersja robocza 0.3  
**Cel pliku:** zapis rozjazdow miedzy kanonem AEIS a stanem faktycznym repo i runtime  
**Zasada dowodowa:** kod > runtime > API > UI > testy > dokumentacja > audit innego modelu

## 1. Wniosek startowy

Na tym etapie system wyglada na mniej "niezaimplementowany", niz wynika z najostrzejszych tez audytu Claude'a, ale jednoczesnie bardziej rozlaczony end-to-end, niz sugerowalaby sama liczba modulow.

Najlepszy opis stanu na teraz brzmi:

- w repo istnieje duzo cegiel odpowiadajacych kanonowi
- kilka z tych cegiel ma zywy runtime
- ale glowny przeplyw AEIS jest federacyjny i nie wszedzie korzysta z jednej wspolnej warstwy governance, memory i execution

## 2. Pierwsze korekty wobec audytu Claude'a

### 2.1. Skills nie sa `MISSING`

Dowody kodowe:

- `src/sylion-pipeline/sylion/skills/catalog.py`
- `src/sylion-pipeline/sylion/skills/demand_signal.py`
- `src/sylion-pipeline/sylion/skills/executor.py`
- `src/sylion-pipeline/sylion/skills/registry.py`
- `src/sylion-pipeline/sylion/skills/runtime.py`
- `src/sylion-pipeline/sylion/api/skills_routes.py`
- `src/sylion-pipeline/sylion/api/router.py` zawiera `skills_router`

Dowody runtime:

- `GET /api/v1/skills/skills` = `200`
- `GET /api/v1/skills/skills-registry/stats` = `200`
- `GET /api/v1/skills/runtime/stats` = `loaded_skills = 0`
- `POST /api/v1/skills/runtime/execute?skill_name=seed_skill_001` = failed
- `GET http://127.0.0.1:3000/skills` = `200`

Wniosek:

- warstwa skills istnieje jako kod
- warstwa skills istnieje jako API
- warstwa skills istnieje jako surface operatorski
- registry skills jest zywe
- runtime executor istnieje, ale nie jest bootstrappowany ani z filesystem, ani z registry
- nie ma jeszcze dowodu, ze skills sa glownym rdzeniem source-of-truth/masterplan/execution loop
- `workspace` opisuje reuse skills i memory w planie, ale sam planning router nie importuje globalnych modulow `sylion.skills.*`

Roboczy status:

`IMPLEMENTED / ROUTED / RUNTIME_BOOTSTRAP_MISSING`

### 2.2. Memory nie jest zerem, ale nie jest tez jednym wspolnym plane

Dowody kodowe:

- `src/sylion-pipeline/sylion/memory/retrieval.py`
- `src/sylion-pipeline/sylion/memory/indexer.py`
- `src/sylion-pipeline/sylion/memory/evidence_store.py`
- `src/sylion-pipeline/sylion/memory/self_model_store.py`
- `src/sylion-pipeline/sylion/api/memory_routes.py`
- `src/sylion-pipeline/sylion/api/router.py` zawiera `memory_router`

Dowody runtime:

- `GET /api/v1/memory/index/stats` = `200`
- `POST /api/v1/memory/index/sections` = `200`
- `GET /api/v1/memory/index/search?query=masterplan` zwraca probe
- `GET /api/v1/memory/self-model` = `200`
- `GET /api/v1/memory/evidence-store` = `200`
- `GET /api/v1/memory/evidence/stats` = `404`

Ale jednoczesnie:

- startupowy globalny indeks jest pusty
- pamiec da sie zasilić recznie przez API, ale startup nie spina jej jako stalego plane
- execution engine uzywa osobnego `runtime.sqlite` per projekt

Wniosek:

- memory jako subsystem istnieje
- memory jako wspolny plane dla calego AEIS nie jest jeszcze potwierdzony
- dodatkowo jedna z tras diagnostycznych jest realnie uszkodzona przez konflikt routingowy
- `workspace` opisuje memory glownie jako polityke i konfiguracje
- realne globalne indeksowanie pojawia sie dopiero w `project_mode.engine`

Roboczy status:

`MEMORY SUBSYSTEM PRESENT / STARTUP_BINDING_MISSING / PROJECT INTEGRATION UNPROVEN`

### 2.3. Council i autonomia sa glebiej obecne niz sugeruje Claude

Dowody kodowe:

- `src/sylion-pipeline/sylion/governance/council_hybrid.py`
- `src/sylion-pipeline/sylion/governance/council_workflow.py`
- `src/sylion-pipeline/sylion/api/governance_routes.py`
- `src/sylion-pipeline/sylion/api/ai_workspace_routes.py`

W `ai_workspace_routes.py` sa realne elementy bliskie kanonowi AEIS:

- council scale
- council mode
- autonomy mode
- source of truth / canon book
- masterplan
- local / VPS / hybrid
- worker topology
- memory policy
- LoRA / learning policy
- Human Gate sessions

Dowod runtime:

- `GET /api/v1/workspace/settings/council-members` = `200`
- `GET /api/v1/workspace/settings/runtime/llm` = `200`
- `GET /api/v1/workspace/settings/hierarchies` = `200`
- `POST /api/v1/workspace/projects/kickoff` zwraca `council_plan`, `governance_policy`, `canonical_book`, `masterplan`
- dry-run projektu `project_a81b2c935d6c` po approvals i `launch(auto_execute=false)` zostawia `masterplan.status = frozen`, `worker_pool_count = 6`, `council_members_count = 5`, `hierarchy_layers_count = 29`

Wniosek:

- model council + autonomia + canon istnieje nie tylko w izolowanych plikach governance
- jest juz materializowany w surface `workspace`
- `workspace` jest dzis najmocniejszym, zywo zweryfikowanym spine AEIS

Roboczy status:

`IMPLEMENTED_IN_WORKSPACE_SURFACE`

### 2.4. Funding jest dojrzalszy niz "thin experimental stub"

Dowody kodowe:

- `src/sylion-pipeline/sylion/funding_autopilot/routes.py`
- `src/sylion-pipeline/sylion/funding_autopilot/service.py`
- `src/sylion-pipeline/sylion/funding_autopilot/store.py`
- `src/sylion-frontend/src/app/(app)/funding/page.tsx`

Store fundingowy obejmuje m.in.:

- company profiles
- company documents
- programmes
- calls
- ideas
- projects
- matches
- partners
- outreach
- applications
- submission sessions
- approval events
- alerts
- audit events

Dowody runtime:

- `GET /api/v1/funding/sources` = `200`
- `GET /api/v1/funding/submission/sessions` = `200`
- `GET /api/v1/funding/submission/approvals` = `200`
- `GET http://127.0.0.1:3000/funding` = `200`

Wniosek:

- funding jest realnym pionem domenowym
- ma realny approval + submit path
- ale approval jest lokalny dla subsystemu funding, nie globalny dla calego AEIS

Roboczy status:

`CODE-BACKED + API-BACKED + UI-BACKED + LOCAL_GOVERNANCE`

### 2.5. Mobile nadal nie ma dowodu wdrozenia aplikacyjnego

Potwierdzone:

- istnieje `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt`

Niepotwierdzone:

- osobny projekt mobile
- kod Android / iOS / React Native / Flutter
- osobny mobile operator app runtime

Roboczy status:

`PROMPT_ONLY / PLANOWANY / NIEZAIMPLEMENTOWANY`

### 2.6. Project registry jest zywy, a nie tylko skutkiem ubocznym `workspace`

Dowody runtime:

- `GET /api/v1/projects` = `200`
- `GET http://127.0.0.1:3000/projects` = `200`
- zwracane sa projekty w fazach `canon`, `build`, `governance`, `broadcast`

Wniosek:

- projekty sa dzis samodzielnym bytem operatorskim AEIS
- `workspace` nie jest jedynym miejscem, gdzie zyje lifecycle projektu

Roboczy status:

`LIVE_PROJECT_REGISTRY`

### 2.7. Worker fleet nie jest missing, tylko defaultowo pusta

Dowody runtime:

- `GET /api/v1/workers` = `200`
- sekwencyjny `POST -> list -> get -> heartbeat -> delete` zakonczyl sie sukcesem
- `GET http://127.0.0.1:3000/workers` = `200`

Wniosek:

- worker fleet jest realnym subsystemem
- nie mamy dowodu na produkcyjna flotę rozproszona
- mamy dowod na zywy registry plane

Roboczy status:

`IMPLEMENTED / DEV_RUNTIME_VERIFIED`

### 2.8. Observability nie jest zerem, ale pozostaje lokalnym dev-plane

Dowody runtime:

- log roundtrip
- metric roundtrip
- trace roundtrip
- `snapshot` pokazuje `LocalLogBackend`

Wniosek:

- observability nie jest missing
- nie jest tez produkcyjnym, trwalym telemetry plane

Roboczy status:

`IMPLEMENTED / DEV_ONLY_BACKEND`

### 2.9. Provider plane jest zywy, ale jeszcze nie jest rada modeli

Dowody runtime:

- `GET /api/v1/ai-providers/list` = `200`
- `POST /api/v1/ai-providers/test/openai` = `200`

Wniosek:

- system potrafi wykryc providerow i przetestowac realny call
- to jeszcze nie oznacza, ze provider plane zasila council, rangi i glosowanie

Roboczy status:

`LIVE_CONNECTIVITY / COUNCIL_INTEGRATION_UNPROVEN`

### 2.10. Model registry istnieje, ale nie jest jeszcze kanoniczna rada modeli

Dowody runtime:

- CRUD modeli dziala
- capabilities dzialaja
- performance snapshots dzialaja
- `workspace/settings/council-members` pozostaje osobnym, pustym plane

Wniosek:

- registry modeli nie jest missing
- ale nie jest jeszcze tym, czym w Twoim modelu ma byc rada modeli z rolami, rangami i odpowiedzialnoscia za moduly masterplanu

### 2.11. Claude moze niedoszacowywac kosztu "naprawy", jesli traktuje `workspace` i funding jak greenfield

Z audytu Codexa wynika, ze dwa obszary sa bardziej dojrzale niz sugeruja najostrzejsze interpretacje:

- `workspace` realnie generuje canon, masterplan, worker plan, council plan i frozen execution state
- `funding` ma juz lokalny approval plane, submission sessions i operator surface

Wniosek:

- przyszly masterplan nie moze zaczynac od przepisania tych obszarow od zera
- trzeba je konsolidowac, a nie rekonstruowac jak puste moduły

Roboczy status:

`MODEL_REGISTRY_PRESENT / COUNCIL_GOVERNANCE_SPLIT`

### 2.11. Council runtime jest zbyt lekki wobec kanonu

Dowody runtime:

- sesje councilu daja sie otworzyc
- `analyze` i `discuss` nie uruchomily realnych analiz w probe
- `consolidate` ustawilo wynik bez realnego sladu glosowania

Wniosek:

- council runtime jest obecny
- ale jest to bardziej engine sesyjny niz pelna rada modeli z wagami, rangami i glosowaniem wymuszanym przed zmianami

Roboczy status:

`SESSION_ENGINE_PRESENT / FULL_COUNCIL_RUNTIME_NOT_PROVEN`

### 2.12. Autonomy stages istnieja, ale nie steruja jeszcze glownym spine

Dowody runtime:

- `/api/v1/aeis/autonomy/stages` = 5 etapow
- `/api/v1/aeis/autonomy/status` = `observe`, `0` akcji

Wniosek:

- autonomia nie jest missing
- ale glowny spine `workspace -> launch -> project_mode` nie pokazal jeszcze, ze ten kontroler naprawde steruje decyzjami runtime

Roboczy status:

`AUTONOMY_ENGINE_PRESENT / MAIN_FLOW_BINDING_UNPROVEN`

## 3. Najwazniejsze ustalenia po probe runtime `workspace`

### 3.1. `workspace` ma zywy flow: canon -> masterplan -> approvals -> launch

Wykonany probe runtime przeszedl przez:

- `POST /api/v1/workspace/projects/kickoff`
- kolejne wybory `humangate/nodes/{id}/choose`
- approvals `book` i `operating_model`
- `POST /api/v1/workspace/projects/{project_id}/launch`

Potwierdzone artefakty:

- `human_gate_session_id`
- `canonical_book`
- `masterplan`
- `memory_policy`
- `worker_plan`
- `council_plan`
- `governance_policy`
- `timeline`
- runtime assignments
- bundle deploy i plan w `src/results/projects/project_c28f57be306a/`

Wniosek:

- `workspace` nie jest stubem
- to jest jak dotad najmocniejszy dowod istnienia kanonicznego flow AEIS

### 3.2. Human Gate jest realny, ale rozszczepiony

`ai_workspace_routes.py` zawiera dwa rozne mechanizmy:

1. globalny request/review gate:
- `/humangate/requests`
- `/humangate/requests/{id}/review`
- `/humangate/stats`

2. sesyjny gate projektowy:
- `/humangate/sessions`
- `/humangate/nodes/{id}/choose`
- `/humangate/sessions/{id}/tree`

Probe runtime pokazal:

- projekt przeszedl przez sesje `hgs_*`
- `GET /api/v1/workspace/humangate/sessions` zwraca realne sesje
- `GET /api/v1/gates/human/requests` zwraca pusty zbior

Wniosek:

- Human Gate nie jest brakujacy
- ale nie jest tez jedna wspolna warstwa AEIS
- mamy co najmniej dwa rownolegle modele approval

Roboczy status:

`HUMAN_GATE_SPLIT_BRAIN`

### 3.3. Council istnieje, ale domyslna sciezka potrafi go logicznie wylaczyc

Kickoff projektu startowal z:

- `council_plan.suggested_size = 3`
- wyborami `1 / 3 / 5 / 7`
- pytaniami o `council_scale`, `council_mode`, `autonomy_mode`

Po przejsciu domyslnych wyborow projekt skonczyl z:

- `council_plan.active_size = 1`
- `council_plan.enabled = false`
- ale `decision_hierarchy` dalej zaczyna sie od `planner_council`

Wniosek:

- semantyka rady modeli jest obecna
- ale nie jest jeszcze konsekwentnie egzekwowana
- nazwa councilu zostaje w hierarchy nawet po logicznym wylaczeniu councilu

Roboczy status:

`PARTIAL + DECISION_MODEL_DRIFT`

### 3.4. Memory jest pofragmentowana miedzy globalne API i runtime projektu

Execution engine uzywa:

- `EvidenceStore`
- `Indexer`

ale zapisuje stan do per-project `runtime.sqlite`.

Probe `src/results/projects/project_c28f57be306a/runtime.sqlite` pokazal:

- `execution_plans = 1`
- `plan_steps = 8`
- `plan_dependencies = 7`
- `worker_registry = 6`
- `worker_assignments = 4`
- `stored_evidence = 0`
- `text_index = 0`

Wniosek:

- memory jest obecna jako technologia
- ale globalne `/api/v1/memory/*` i lokalne runtime DB projektu nie sa jeszcze jednym wspolnym plane

Roboczy status:

`MEMORY_PRESENT_BUT_FRAGMENTED`

### 3.5. Funding ma twardy gate, ale nie jest on globalny

Dowod kodowy:

- `funding_autopilot/service.py::request_approval()`
- `funding_autopilot/service.py::submit()`
- brak importow `governance.human_gate` wewnatrz `funding_autopilot/*`

Dowod runtime:

- `submission/sessions` i `submission/approvals` maja realne dane
- `gates/human/requests` pozostaje puste

Wniosek:

- finalny funding submit nie jest "bez bramki"
- ale bramka lezy lokalnie wewnatrz subsystemu funding
- to jest rozjazd wzgledem docelowego modelu jednego Human Gate plane

### 3.6. Worker topology ma realny bug rekonsyliacji

Po odpowiedziach operatora projekt mial:

- `deployment_mode = local_docker`
- `vps_workers = 0`

Po `launch` runtime nadal zarejestrowal workerow VPS.

Kod wskazuje przyczyne:

- `ProjectModeStore._derive_worker_pool()` zwraca istniejacy `worker_pool`, jesli ten juz istnieje
- kickoff startuje z domyslnym `hybrid`
- pozniejsze zmiany `execution_plan` nie wymuszaja odbudowy puli workerow

Skutek:

- canon, config i runtime moga mowic o roznych topologiach wykonania

Roboczy status:

`BROKEN_RECONCILIATION_BETWEEN_EXECUTION_PLAN_AND_WORKER_POOL`

## 4. Najwazniejsze napiecie architektoniczne

Na dzis glowny problem nie brzmi:

- "nic nie istnieje"

tylko:

- "istnieje duzo kanonicznych subsystemow, ale sa rozdzielone na rownolegle powierzchnie i nie zawsze korzystaja ze wspolnego plane governance, memory i execution"

To dotyczy w szczegolnosci:

- `workspace` vs globalny `governance.human_gate`
- funding-local approvals vs globalny Human Gate
- globalne `memory API` vs per-project `runtime.sqlite`
- deklarowanego `planner_council` vs realnego `active_size = 1`
- `execution_plan` vs utrwalony `worker_pool`

## 5. Gdzie Claude byl trafny, a gdzie za ostry

### Claude byl trafny w tym, ze:

- runtime nie dowodzi jeszcze jednego wspolnego memory plane
- governance jest pofragmentowane
- mobile nadal nie ma wdrozenia
- system nadal nie jest production ready mimo obecnosci wielu zywych surfaces

### Claude byl za ostry w tym, ze:

- skills nie sa `MISSING`
- funding nie jest cienkim stubem
- `workspace` nie jest tylko shellowym API
- operator surface nie jest pusty; problemem jest split i niespojnosc, nie absolutny brak

## 6. Hipotezy do dalszego sprawdzenia

- czy `funding` finalnie spina sie z globalnym Human Gate
- czy `workspace` uruchamia realne globalne skills reuse
- czy `workspace` uruchamia realne globalne memory retrieval
- czy operator console ma jeden dominujacy truth plane
- czy istnieje backendowy zalazek mobile approval bridge
