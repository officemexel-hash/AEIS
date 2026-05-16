# CODEX AEIS FUNCTIONAL AUDIT

**Status:** wersja robocza 0.4  
**Cel pliku:** zapis statusow funkcjonalnych modulow i flow na podstawie kodu, runtime, API, UI i probe operatorskich  
**Uwaga:** to jest roboczy audyt funkcjonalny. Bedzie rozszerzany modul po module.

## 1. Pierwsze potwierdzone statusy

| Obszar | Status | Dowod | Uwagi |
|---|---|---|---|
| Bootstrap backend AEIS | LIVE_VERIFIED | `GET /health` = `200` | runtime zwraca `version=3.5.0`, `modules=119`, `endpoints=1433` |
| Frontend app bootstrap | LIVE_VERIFIED | `GET http://127.0.0.1:3000/` = `200` | w obecnej probe frontend zyje na `3000`; port runtime nie byl stabilny miedzy probami |
| Projects operator surface | LIVE_VERIFIED | `GET http://127.0.0.1:3000/projects` = `200`, `GET /api/v1/projects` = `200` | lista projektow jest realna i wielofazowa, nie stub |
| Workers operator surface | LIVE_VERIFIED | `GET http://127.0.0.1:3000/workers` = `200`, sekwencyjny CRUD/heartbeat na `/api/v1/workers/*` | surface startuje z pusta flota, ale registry dziala |
| Worker topology library | PARTIAL | `GET /api/v1/workers/topology/all` = `200` | API istnieje, ale lista topologii jest obecnie pusta |
| Observability operator surface | LIVE_VERIFIED | `GET http://127.0.0.1:3000/observability` = `200`, roundtrip metrics/logs/traces | warstwa zyje, ale backend jest lokalny i nietrwaly |
| AI provider plane | LIVE_VERIFIED | `GET /api/v1/ai-providers/list` = `200`, `POST /api/v1/ai-providers/test/openai` = `200` | realny cloud connectivity probe dziala |
| Model registry plane | LIVE_VERIFIED | sekwencyjny CRUD na `/api/v1/model-registry/*` | registry istnieje, ale jest osobny od `workspace council-members` |
| Council session runtime | PARTIAL | `POST /api/v1/workspace/council/sessions*` = `200` | sesje zyja, ale analizy i dyskusje nie uruchamiaja sie same |
| Autonomy controller plane | PARTIAL | `GET /api/v1/aeis/autonomy/stages` = `200`, `GET /api/v1/aeis/autonomy/status` = `200` | 5-etapowy model istnieje, ale runtime pozostaje na `observe` |
| Skills registry API surface | LIVE_VERIFIED | `GET /api/v1/skills/skills` = `200`, `GET /api/v1/skills/skills-registry/stats` = `200` | registry istnieje i przechowuje co najmniej 2 wpisy `DRAFT` |
| Skills runtime plane | BROKEN | `GET /api/v1/skills/runtime/stats` = `loaded_skills=0`, `POST /api/v1/skills/runtime/execute?skill_name=seed_skill_001` = failed | runtime executor istnieje, ale nie laduje skilli z registry ani z filesystem |
| Skills operator surface | PARTIAL | `GET http://127.0.0.1:3000/skills` = `200` | UI zyje; brak jeszcze dowodu, ze skills steruja glownym loop projektu |
| Memory API surface | LIVE_VERIFIED | `GET /api/v1/memory/index/stats` = `200` | globalny memory plane odpowiada, ale startup pokazuje pusty indeks |
| Memory indexing plane | PARTIAL | `POST /api/v1/memory/index/sections` = `200`, `GET /api/v1/memory/index/search` zwraca probe | indeksowanie dziala, ale nie jest startowo podpiete jako trwały globalny plane |
| Memory evidence stats route | BROKEN | `GET /api/v1/memory/evidence/stats` = `404` | route `/evidence/stats` jest cieniowany przez `/evidence/{evidence_id}` |
| Funding API surface | LIVE_VERIFIED | `GET /api/v1/funding/sources` = `200` | zywy pion domenowy z szerokim API |
| Funding operator surface | LIVE_VERIFIED | `GET http://127.0.0.1:3000/funding` = `200` | page jest data-backed, nie stub |
| Governance operator surface | LIVE_VERIFIED | `GET http://127.0.0.1:3000/governance` = `200` | UI zyje, a backend ma realne proposals, gates i policies |
| Cellular lab surface | PARTIAL | `GET http://127.0.0.1:3000/cellular` = `200`, `GET /api/v1/cellular/ran` = `200` | surface zyje, ale obecnie bez zarejestrowanych stackow |
| SDR lab surface | PARTIAL | `GET http://127.0.0.1:3000/sdr` = `200`, `GET /api/v1/sdr/devices` = `200` | surface zyje, ale bez urzadzen runtime |
| Devices lab surface | PARTIAL | `GET http://127.0.0.1:3000/devices` = `200`, `GET /api/v1/devices/discovery` = `200` | surface zyje, ale discovery/registry sa obecnie puste |
| VPS provider plane | PARTIAL | `GET /api/v1/vps/providers` = `200` | API zyje, ale brak dostawcow runtime |
| Container plane | PARTIAL | `GET /api/v1/container/stats` = `200` | manager istnieje, ale stan startowy jest pusty |
| Workspace settings surface | PARTIAL | `GET /api/v1/workspace/settings/*` = `200` | settings plane zyje, ale council members i hierarchies sa puste |
| Root PID tracking | BROKEN | `.backend.pid`, `.frontend.pid` wskazuja martwe procesy | operational drift |
| Operator Mobile | PLANOWANY / NIEZAIMPLEMENTOWANY | brak trafien `operator_mobile` / `operator-mobile` w `src/` | obecny prompt projektowy, brak potwierdzonego backendu i UI |

## 2. Zywe flow potwierdzone probe runtime

### 2.1. Workspace kickoff flow

Status:

`LIVE_VERIFIED`

Wykonane kroki:

1. `POST /api/v1/workspace/projects/kickoff`
2. `GET /api/v1/workspace/humangate/sessions/{id}/current`
3. kolejne `POST /api/v1/workspace/humangate/nodes/{id}/choose`
4. `POST /api/v1/workspace/projects/{project_id}/approve`
5. `POST /api/v1/workspace/projects/{project_id}/launch`

Potwierdzone efekty:

- projekt z `project_id`
- sesja `human_gate_session_id`
- wygenerowany `canonical_book`
- wygenerowany `masterplan`
- `questions`
- `answers`
- `decisions`
- `timeline`
- `worker_plan`
- `council_plan`
- `governance_policy`
- `memory_policy`
- `audit_plan`
- runtime assignments
- bundle deploy w `src/results/projects/project_a81b2c935d6c/`

Najwazniejszy probe kontrolny z tej rundy:

- projekt: `project_a81b2c935d6c`
- session: `hgs_b6c8cea3c4c5`
- obie sekcje approvals zatwierdzone: `book`, `operating_model`
- `launch.auto_execute = false`
- `launch.status = queued`
- status projektu po launch: `queued`
- faza projektu po launch: `build`
- `module_count = 4`
- `worker_pool_count = 6`
- `council_members_count = 5`
- `hierarchy_layers_count = 29`
- masterplan endpoint zwraca `status = frozen`
- `deployment_mode = hybrid`
- `provisioning_mode = plan_and_generate`
- `validation_profile = standard_gate`
- `autonomy_mode = L1_BOOK_LOCKED`

Wniosek:

- to jest realny flow operatorski
- nie jest to tylko statyczne API storage
- `workspace` potrafi dojsc od intake przez pytania, approvals i canon do zamrozonego, gotowego execution planu

### 2.2. Workspace Human Gate session tree

Status:

`LIVE_VERIFIED`

Dowody:

- `GET /api/v1/workspace/humangate/sessions/{id}/tree`
- `GET /api/v1/workspace/humangate/sessions/{id}/history`
- `GET /api/v1/workspace/humangate/sessions/{id}/current`

Wniosek:

- projektowy Human Gate ma drzewo, historie, fazy i wybory operatora

### 2.3. Workspace settings and council settings plane

Status:

`LIVE_VERIFIED`

Dowody runtime:

- `GET /api/v1/workspace/settings/keys` = `200`
- `GET /api/v1/workspace/settings/runtime/llm` = `200`
- `GET /api/v1/workspace/settings/hierarchies` = `200`
- `GET /api/v1/workspace/settings/council-members` = `200`
- `GET /api/v1/workspace/council/sessions` = `200`
- `GET /api/v1/workspace/books` = `200`

Wniosek:

- workspace ma realny settings plane dla modeli, kluczy, hierarchii i councilu
- nie wszystkie listy maja dane, ale nie sa to martwe endpointy

### 2.4. Workspace -> global Human Gate integration

Status:

`PARTIAL`

Dowody:

- projekt przechodzi przez `workspace/humangate/sessions/*`
- `GET /api/v1/workspace/humangate/sessions` zwraca realne sesje
- `GET /api/v1/gates/human/requests` zwraca pusty zbior
- `GET /api/v1/workspace/humangate/stats` nie pokazuje review z probe projektowej

Wniosek:

- istnieje zywy gate projektowy
- istnieje tez globalny gate request/review
- ale nie widac jeszcze, by `workspace` zasila globalny gate request/review

### 2.5. Project launch planning bundle

Status:

`LIVE_VERIFIED`

Dowody:

- `POST /api/v1/workspace/projects/{project_id}/launch`
- artefakty na dysku:
  - `src/results/projects/project_c28f57be306a/plan/canon.md`
  - `src/results/projects/project_c28f57be306a/plan/masterplan.md`
  - `src/results/projects/project_c28f57be306a/deploy/docker-compose.yml`
  - `src/results/projects/project_c28f57be306a/deploy/deploy.local.ps1`
  - `src/results/projects/project_c28f57be306a/deploy/terraform.tfvars.json`

Wniosek:

- flow nie konczy sie na dokumentach
- generuje execution bundle i assignmenty

### 2.6. Funding approval and submit path

Status:

`PARTIAL`

Dowody kodowe:

- `src/sylion-pipeline/sylion/funding_autopilot/routes.py`
- `src/sylion-pipeline/sylion/funding_autopilot/service.py`
- `src/sylion-pipeline/sylion/funding_autopilot/store.py`

Dowody runtime:

- `GET /api/v1/funding/submission/sessions` = `200`
- `GET /api/v1/funding/submission/approvals` = `200`
- `GET /api/v1/funding/alerts?company_id=default` = `200`

Potwierdzone zachowanie:

- funding ma osobne `submission_session`
- funding ma osobne `approval_event`
- `submit()` wymaga wczesniejszego `request_approval()`
- final submit wymaga:
  - approval request
  - `confirm_legal`
  - `confirm_budget`
  - `confirm_documents`
  - `portal_submission_reference`

Wniosek:

- funding ma realny, twardy gate przed finalnym submit
- ale gate jest lokalny dla modulu funding
- nie ma dowodu, ze funding zasila globalny `governance.human_gate`

### 2.7. Projects registry and lifecycle surface

Status:

`LIVE_VERIFIED`

Dowody runtime:

- `GET /api/v1/projects` = `200`
- `GET http://127.0.0.1:3000/projects` = `200`

Potwierdzone zachowanie:

- runtime zwraca `10` projektow
- statusy obejmuja:
  - `queued`
  - `completed`
  - `ready_to_launch`
  - `definition_in_progress`
  - `blocked_on_audit`
- fazy obejmuja m.in.:
  - `canon`
  - `build`
  - `governance`
  - `broadcast`

Wniosek:

- `projects` nie jest cienkim ekranem statusowym
- surface pracuje nad realnym rejestrem projektow i etapow zycia

### 2.8. Worker fleet surface

Status:

`LIVE_VERIFIED`

Dowody runtime:

- `GET /api/v1/workers` = `200`
- `GET /api/v1/workers/topology/all` = `200`
- `GET http://127.0.0.1:3000/workers` = `200`
- probe sekwencyjny:
  1. `POST /api/v1/workers`
  2. `GET /api/v1/workers`
  3. `GET /api/v1/workers/{id}`
  4. `POST /api/v1/workers/{id}/heartbeat`
  5. `DELETE /api/v1/workers/{id}`

Potwierdzone zachowanie:

- worker registry jest zywy
- heartbeat dziala
- UI startuje domyslnie z pusta flota
- biblioteka topologii istnieje, ale nie ma jeszcze zapisanych topologii

Wniosek:

- `workers` to realny operator surface
- problemem nie jest brak runtime, tylko niski poziom wypelnienia danymi startowymi

### 2.9. Observability hub

Status:

`LIVE_VERIFIED`

Dowody runtime:

- `GET /api/v1/observability/snapshot` = `200`
- `GET /api/v1/observability/logs` = `200`
- `GET /api/v1/observability/metrics` = `200`
- `GET /api/v1/observability/traces` = `200`
- `GET http://127.0.0.1:3000/observability` = `200`

Probe kontrolne:

- `POST /api/v1/observability/logs`
- `POST /api/v1/observability/metrics/codex.audit.metric`
- `POST /api/v1/observability/traces/codex-audit-trace/start`
- `POST /api/v1/observability/traces/codex-audit-trace/end`

Potwierdzone zachowanie:

- snapshot pokazuje `LocalLogBackend`
- zapis logow dziala i logi wracaja w query oraz snapshot
- zapis metryk dziala
- zapis trace dziala

Wniosek:

- observability jest realnym surface'em deweloperskim
- nie jest jeszcze produkcyjnym, trwalym backendem telemetrycznym

### 2.10. AI provider plane

Status:

`LIVE_VERIFIED`

Dowody runtime:

- `GET /api/v1/ai-providers/list` = `200`
- `POST /api/v1/ai-providers/test/openai` = `200`

Potwierdzone zachowanie:

- runtime widzi klucze dla:
  - `anthropic`
  - `openai`
  - `perplexity`
  - `google`
  - `zai`
- probe `openai / gpt-4o-mini / prompt=ping` zwrocil realna odpowiedz z latencja ok. `5655 ms`

Wniosek:

- provider plane nie jest tylko konfiguracja
- system ma realny endpoint do sprawdzania lacznosci i minimalnych calli LLM

### 2.11. Model registry plane

Status:

`LIVE_VERIFIED`

Dowody runtime:

- `GET /api/v1/model-registry/models` = `200`
- probe sekwencyjny:
  1. `POST /api/v1/model-registry/models`
  2. `POST /api/v1/model-registry/capabilities`
  3. `POST /api/v1/model-registry/performance`
  4. `GET /api/v1/model-registry/models/stats`
  5. `GET /api/v1/model-registry/models/{id}/performance`
  6. `DELETE /api/v1/model-registry/models/{id}`

Potwierdzone zachowanie:

- model registry zapisuje modele
- registry zapisuje capabilities
- registry zapisuje performance snapshots

Wniosek:

- registry modeli istnieje jako realny subsystem
- ale nie jest jeszcze tym samym plane co `workspace/settings/council-members`

### 2.12. Council session runtime

Status:

`PARTIAL`

Dowody runtime:

- `POST /api/v1/workspace/council/sessions`
- `POST /api/v1/workspace/council/sessions/{id}/analyze`
- `POST /api/v1/workspace/council/sessions/{id}/discuss`
- `POST /api/v1/workspace/council/sessions/{id}/consolidate`

Probe kontrolny:

- sesja zostala otwarta dla dwoch modeli
- `analyze` zwrocil `0` analiz
- `discuss` zwrocil `0` rund
- `consolidate` potrafil ustawic `consensus_level = 1.0` bez realnych analiz

Wniosek:

- council session plane jest zywy
- ale dzisiejszy runtime jest bardziej store/session engine niz pelna egzekucja rady modeli z glosowaniem i wagami

### 2.13. Autonomy controller

Status:

`PARTIAL`

Dowody runtime:

- `GET /api/v1/aeis/autonomy/stages` = `200`
- `GET /api/v1/aeis/autonomy/status` = `200`

Potwierdzone zachowanie:

- istnieje 5-etapowy model:
  - `observe`
  - `propose`
  - `sandbox`
  - `limited`
  - `full`
- obecny status runtime:
  - `current_stage = observe`
  - `total_actions = 0`
  - `allowed_actions = 0`
  - `denied_actions = 0`

Wniosek:

- autonomia ma juz swoj kodowy state model
- ale nie ma jeszcze dowodu, ze steruje glownym loopem `workspace -> council -> execution`

### 2.14. Laboratory and runtime extension surfaces

Status:

`PARTIAL`

Dowody runtime:

- `GET http://127.0.0.1:3000/cellular` = `200`
- `GET http://127.0.0.1:3000/sdr` = `200`
- `GET http://127.0.0.1:3000/devices` = `200`
- `GET /api/v1/cellular/ran` = `200`
- `GET /api/v1/sdr/devices` = `200`
- `GET /api/v1/devices/discovery` = `200`
- `GET /api/v1/devices/registry` = `200`
- `GET /api/v1/vps/providers` = `200`
- `GET /api/v1/container/stats` = `200`

Potwierdzone zachowanie:

- `cellular` ma zywy plane dla:
  - RAN
  - core network
  - UE
  - RF isolation
  - attack vectors
  - control plane
  - evidence writer
- `sdr` ma zywy plane dla:
  - devices
  - captures
  - analysis
  - decode
  - RF safety
- `devices` ma zywy plane dla:
  - discovery
  - registry
  - deployments
  - on-device tests
- `vps` i `container` maja API managerow runtime

Stan runtime w tej probe:

- `cellular_ran = 0`
- `sdr_devices = 0`
- `registered_devices = 0`
- `discovered_devices = 0`
- `vps_providers = 0`
- `container stats = 0` dla kontenerow, obrazow, podow i deploymentow

Wniosek:

- te moduly istnieja i sa routowane
- sa swiadomymi rozszerzeniami laboratoryjnymi / runtime
- na teraz nie bylo w nich aktywnego stanu roboczego

## 3. Potwierdzone rozjazdy funkcjonalne

### 3.1. Worker topology reconciliation

Status:

`BROKEN`

Objaw runtime:

- projekt po decyzjach operatora ma `vps_workers = 0`
- po `launch` runtime nadal rejestruje workerow VPS

Przyczyna kodowa:

- `src/sylion-pipeline/sylion/project_mode/store.py`
- `ProjectModeStore._derive_worker_pool()` nie przelicza puli, jesli `worker_pool` juz istnieje

Skutek:

- `execution_plan` i realny runtime registry moga sie rozjechac

### 3.2. Memory as shared plane

Status:

`PARTIAL`

Objaw runtime:

- globalne `/api/v1/memory/*` odpowiada
- startupowy globalny indeks jest pusty
- manualne `POST /api/v1/memory/index/sections` zapisuje sekcje i `GET /api/v1/memory/index/search?query=masterplan` zwraca trafienie
- `GET /api/v1/memory/index/stats` po probe pokazuje niezerowe `unique_terms`, `total_postings` i `indexed_sections`
- `POST /api/v1/memory/evidence` zapisuje rekord, `GET /api/v1/memory/evidence` go zwraca
- `GET /api/v1/memory/evidence/stats` konczy sie `404`
- per-project `runtime.sqlite` zawiera plan, registry i assignmenty
- ale nie ma jeszcze zapisanych `stored_evidence` ani `text_index`

Przyczyna kodowa:

- `src/sylion-pipeline/sylion/api/app.py` bootstrappuje `idea_vault`, `worker_registry`, `skills_registry` i `human_gate`
- startup nie bootstrappuje `memory.indexer`, `memory.evidence_store` ani `memory.retrieval` z jednym trwałym `db_path`
- `src/sylion-pipeline/sylion/api/memory_routes.py` deklaruje `/evidence/{evidence_id}` przed `/evidence/stats`, przez co `stats` jest parsowane jak `evidence_id`

Wniosek:

- memory istnieje i pojedyncze funkcje daja sie wykonac
- ale nie jest jeszcze potwierdzona jako wspolny, trwale zbindowany plane dla calego AEIS
- dodatkowo jedna z tras diagnostycznych jest realnie uszkodzona

### 3.3. Council semantics in default path

Status:

`DOC_DRIFT`

Objaw runtime:

- `council_plan.active_size = 1`
- `council_plan.enabled = false`
- `decision_hierarchy` nadal zaczyna sie od `planner_council`

Wniosek:

- model rady istnieje
- ale jego semantyka nie jest jeszcze konsekwentna w runtime

### 3.4. Global Human Gate vs workspace Human Gate

Status:

`PARTIAL`

Objaw runtime:

- `GET /api/v1/workspace/humangate/sessions` = `200` i zwraca realne sesje
- `GET /api/v1/gates/human/requests` = `200` i zwraca pusty zbior

Wniosek:

- workspace session gate jest zywy
- globalny human request plane tez istnieje
- ale w obecnej probe nie ma dowodu, ze workspace funnel zapisuje decyzje do globalnych requestow

### 3.5. Funding governance path is local, not unified

Status:

`DOC_DRIFT`

Objaw kodowy:

- `funding_autopilot/*` nie importuje `governance.human_gate`
- approval jest trzymany przez lokalne `approval_event` w store fundingowym

Wniosek:

- funding ma governance
- ale nie jest to jeszcze governance zunifikowane z glownym Human Gate AEIS

### 3.6. Council runtime is session-first, not vote-first

Status:

`PARTIAL`

Objaw runtime:

- sesja councilu daje sie otworzyc i skonsolidowac
- ale nie generuje samoczynnie analiz ani rund dyskusji
- `consensus_level` moze zostac ustawiony bez realnego sladu glosowania modeli

Wniosek:

- dzisiejszy council runtime nie spelnia jeszcze pelnej roli rady modeli z wagami, rangami i udokumentowanym glosowaniem

### 3.7. Model registry i `workspace council-members` to dwa rozne planes

Status:

`DOC_DRIFT`

Objaw runtime:

- `/api/v1/model-registry/*` dziala
- `/api/v1/workspace/settings/council-members` istnieje, ale jest puste
- brak dowodu, ze `workspace` pobiera sklad rady z model registry

Wniosek:

- system ma dwa byty zwiazane z modelami
- nie ma jeszcze jednego truth plane dla skladu rady modeli

### 3.8. Autonomy controller istnieje, ale pozostaje odklejony od glownych flow

Status:

`PARTIAL`

Objaw runtime:

- autonomia ma 5 etapow i endpointy
- biezacy runtime siedzi na `observe`
- brak akcji i brak dowodu, ze `workspace` lub `project_mode` odwoluje sie do tego stanu podczas probe

Wniosek:

- autonomia nie jest missing
- ale nie jest jeszcze glownym mechanizmem sterowania obecnym spine AEIS

### 3.9. Skills registry i skills runtime sa rozdzielone

Status:

`BROKEN`

Objaw runtime:

- `GET /api/v1/skills/skills-registry/stats` pokazuje 2 zarejestrowane skille
- `GET /api/v1/skills/runtime/stats` pokazuje `loaded_skills = 0`
- `GET /api/v1/skills/catalog-stats` pozostaje pusty
- `POST /api/v1/skills/runtime/execute?skill_name=seed_skill_001` zwraca blad `Unknown skill`

Przyczyna kodowa:

- `src/sylion-pipeline/sylion/skills/runtime.py` laduje specyfikacje tylko wtedy, gdy runtime dostanie `skills_dir`
- `src/sylion-pipeline/sylion/api/app.py` startuje `get_skills_registry(db_path=...)`, ale nie bootstrappuje `get_skills_runtime(db_path=..., skills_dir=...)`

Wniosek:

- registry skills jest realne
- UI skills jest realne
- ale runtime executor nie jest jeszcze zszyty ani z registry, ani z lokalnym katalogiem skilli
- to nie jest brak warstwy skills, tylko brak dopiecia runtime plane

## 4. Wazne obserwacje funkcjonalne

### 4.1. Runtime istnieje i nie jest pusty

To nie jest repo z samymi stubami. Backend, frontend i czesc flow operatorskich naprawde odpowiadaja.

### 4.2. `LIVE_VERIFIED` nie oznacza jeszcze pelnego kanonu

Przyklad:

- `skills` sa zywe
- `memory` jest zywa
- `workspace kickoff` jest zywy

Ale dalej trzeba potwierdzic, czy te warstwy wspolnie steruja calym AEIS, czy dzialaja tylko jako osobne subsystemy.

### 4.3. Funding jest blizej produktu niz mobile

Funding ma:

- backend
- store
- API
- frontend
- zywe endpointy
- lokalny approval + submission flow

Mobile ma na razie:

- prompt kanoniczny
- brak oddzielnej codebase aplikacyjnej

## 5. Najblizsze kroki funkcjonalne

- rozszerzyc probe browserowe o realne mutacje na `projects`, `skills`, `funding` i `governance`
- sprawdzic, czy `workspace launch` w trybie `auto_execute=true` rzeczywiscie zapisuje globalne evidence/index entries, a nie tylko per-project DB
- potwierdzic, czy istnieje backendowy bridge pod mobile approvals, nawet jesli brak osobnej app codebase
- rozszerzyc porownanie z audytem Claude'a o miejsca, gdzie ich masterplan zaklada greenfield mimo istniejacego runtime
- zlozyc synteze do `AEIS_SYSTEM_BOOK_2026.md`
