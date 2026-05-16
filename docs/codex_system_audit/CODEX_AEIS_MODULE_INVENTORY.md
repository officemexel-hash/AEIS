# CODEX AEIS MODULE INVENTORY

**Status:** wersja robocza 0.3  
**Data startu audytu Codex:** 2026-04-24  
**Zrodlo prawdy na tym etapie:** kod repo + wiring routera + struktura frontendu + runtime probe + audit Claude'a jako zrodlo wtornne  
**Snapshot roboczy:** [docs/codex_system_audit/_inventory_snapshot.json](/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/_inventory_snapshot.json)

## 1. Zasady liczenia

Ta inwentaryzacja jest celowo bardziej surowa niz audit Claude'a.

Najpierw licze:

- jednostki kodowe
- route files
- surface'y frontendu
- skills
- prompty
- addony

Dopiero potem bede je scalal do logicznych modulow AEIS.

Dlatego obecne liczby nie przecza liczbie `~119` logicznych modulow. Pokazuja raczej rzeczywista mase systemu.

## 2. Surowy snapshot Codexa

Na podstawie skanera `aeis-module-inventory-auditor` ustalilem:

| Kategoria | Liczba | Uwagi |
|---|---:|---|
| Pakiety backendowe `src/sylion-pipeline/sylion/*` | 30 | obejmuje core, governance, memory, skills, funding, lab i runtime |
| Moduly backendowe `.py` bez `__init__` | 354 | surowe jednostki kodowe |
| Pliki route API | 83 | tylko pliki `_routes.py` |
| Pliki API pomocnicze | 3 | np. `app.py`, `deploy_service.py` |
| Route pages frontendu Next.js | 56 | realne `page.tsx` pod `src/app` |
| Proto contracts | 6 | w `src/sylion-pipeline/proto` |
| Repo skills w `.agents/skills` | 27 | w tym nowe skills audytowe Codexa |
| Prompt-only aktywa w root | 2 | funding prompt, operator mobile / human gate prompt |
| Addony / pakiety zewnetrzne | 2 | `sylion_devices_addon`, `SYLION_Dashboard_V5_ClaudeCode_Package` |
| Pliki legacy dashboardu | 26 | stary surface w `src/sylion-pipeline/dashboard` |
| Entrypointy i root docs runtime | 8 | start scripts + root runtime docs |

## 3. Co juz jest pewne

### 3.1. Runtime bootstrap dziala

Probe runtime dal:

- backend `GET /health` = `200`
- health zwraca `status=ok`, `version=3.5.0`, `modules=119`, `endpoints=1433`
- frontend w obecnej probe odpowiada na porcie `3000`
- rootowe `.backend.pid` i `.frontend.pid` wskazuja martwe procesy

Wniosek:

- runtime istnieje i jest zywy
- czesc rootowych artefaktow operacyjnych jest rozjechana z rzeczywistym stanem
- bind portu frontendu nie jest jeszcze stabilnym zrodlem prawdy w dokumentacji operacyjnej

### 3.2. Backend jest szeroki i wykracza daleko poza pierwotny obraz

Potwierdzone pakiety backendowe:

- `aeis`
- `api`
- `cellular`
- `cognitive`
- `container`
- `contracts`
- `core`
- `db`
- `devices`
- `efficiency`
- `execution`
- `funding_autopilot`
- `governance`
- `grpc`
- `grpc_stubs`
- `infra`
- `integration`
- `memory`
- `monitoring`
- `observability`
- `pipeline`
- `project_mode`
- `quality`
- `rebuild`
- `sdr`
- `security`
- `skills`
- `surface`
- `vps`
- `worker`

Wniosek:

- system jest duzo szerszy niz pierwotna architektura 65 modulow
- warstwy AEIS rozrosly sie o piony funding, workspace/project_mode i lab extensions

### 3.3. Frontend jest rozbudowanym surface'em operatorskim

Skaner wykryl 56 route pages, m.in.:

- `/funding`
- `/skills`
- `/governance`
- `/gates`
- `/projects`
- `/workspace`
- `/autonomy`
- `/devices`
- `/cellular`
- `/sdr`
- `/workers`
- `/observability`
- `/decisions`
- `/contracts`
- `/modules`

Wniosek:

- operator surface jest wiekszy niz prosty dashboard
- frontend trzeba audytowac jako osobny, duzy subsystem

### 3.4. Funding nie jest prompt-only

`funding_autopilot` ma co najmniej:

- router FastAPI
- service layer
- store SQLite/Postgres
- schemy
- permissions
- frontend `/funding`

Backend i UI sa zywe:

- `GET /api/v1/funding/sources` = `200`
- `GET http://127.0.0.1:3000/funding` = `200`

Wniosek:

- Funding Autopilot jest realnym pionem domenowym

### 3.5. Mobile nadal nie ma dowodu implementacji aplikacyjnej

Potwierdzone:

- `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt`

Niepotwierdzone:

- osobny kod aplikacji mobile
- osobna codebase Android / iOS / RN / Flutter

Wniosek:

- mobile na ten moment klasyfikuje jako `PLANOWANY / NIEZAIMPLEMENTOWANY`
- przeszukanie `src/sylion-pipeline` i `src/sylion-frontend/src` nie pokazalo backendu ani UI dla `operator_mobile`

### 3.6. Istnieje rownolegly legacy dashboard

Obok Next.js istnieje stary surface w:

- `src/sylion-pipeline/dashboard`

Snapshot wykryl tam 26 plikow Python.

Wniosek:

- istnieje podwojny operator stack:
  - nowy Next.js
  - starszy legacy dashboard

### 3.7. `workspace` jest juz logicznym modulem, nie tylko zestawem endpointow

Probe runtime `workspace` utworzyl:

- projekt kickoff
- sesje Human Gate
- canon book
- masterplan
- questions / answers / decisions
- execution bundle w `src/results/projects/project_a81b2c935d6c/`
- `worker_pool_count = 6`
- `council_members_count = 5`
- `hierarchy_layers_count = 29`
- `masterplan.status = frozen`

Wniosek:

- `workspace` trzeba od tej chwili traktowac jako logiczny modul AEIS
- nie tylko jako pomocniczy plik API

### 3.8. `projects`, `workers` i `observability` tez sa logicznymi modulami runtime

Probe runtime potwierdzily:

- `GET /api/v1/projects` = `200`, `10` projektow w wielu statusach i fazach
- sekwencyjny CRUD + heartbeat dla `/api/v1/workers/*`
- roundtrip dla `/api/v1/observability/logs`, `/metrics/*`, `/traces/*`

Wniosek:

- te obszary nie powinny byc liczone tylko jako pomocnicze route families
- sa to realne logiczne moduly operatorskie i runtime

### 3.9. Repo zawiera juz dedykowane skills audytowe Codexa

W `.agents/skills` potwierdzone zostaly m.in.:

- `aeis-module-inventory-auditor`
- `aeis-runtime-evidence-auditor`
- `aeis-governance-council-auditor`
- `aeis-api-ui-coverage-auditor`
- `aeis-domain-surface-auditor`
- `aeis-canon-drift-writer`
- `aeis-cross-audit-diff-auditor`
- `aeis-system-book-writer`

Wniosek:

- warstwa skills repo jest wykorzystywana nie tylko produktowo, ale tez do samego audytu systemu
- te skills nie sa jeszcze glownym runtime plane AEIS, ale sa realnym materialem pomocniczym do dalszej pracy audytowej i dokumentacyjnej

## 4. Pierwsze rozbieznosci Codex vs Claude

### 4.1. Skills nie sa "brakiem warstwy w runtime"

Fakty:

- istnieje pakiet `sylion.skills.*`
- istnieje `skills_routes.py`
- glowny router wlacza `skills_router`
- runtime endpoint dziala
- registry stats sa zywe
- executor runtime jest obecny, ale nie laduje zadnych skilli startowo

Roboczy werdykt:

`implemented and routed, but runtime bootstrap and main-flow integration remain unproven`

### 4.2. Memory nie jest zerem

Fakty:

- istnieje `memory_routes.py`
- istnieja endpointy `kanon`, `compact`, `evidence`, `index`, `retrieval`, `self-model`
- runtime endpointy odpowiadaja

Roboczy werdykt:

`implemented and routed, but globally fragmented`

### 4.3. Multi-model council jest glebiej obecny niz wynika z samego `council_workflow`

Fakty:

- `ai_workspace_routes.py` materializuje:
  - council scale
  - council mode
  - autonomy mode
  - source of truth
  - masterplan
  - worker topology
  - learning / memory policy

Roboczy werdykt:

- Claude mogl niedoszacowac glebokosci `workspace` jako miejsca, gdzie kanon AEIS zaczyna sie materializowac

### 4.4. Funding jest dojrzalszy niz "experimental thin layer"

Fakty:

- szeroki store
- zywy backend
- zywy frontend

Roboczy werdykt:

- Claude zanizyl dojrzalosc fundingu

### 4.5. `project_mode`, `projects`, `workers` i `observability` sa zywsze, niz sugeruje cienki opis kontrolny

Fakty:

- `project_mode` stoi za realnym `launch`
- `projects` ma zywy rejestr lifecycle
- `workers` ma dzialajacy registry CRUD
- `observability` ma dzialajace logs / metrics / traces

Roboczy werdykt:

- Claude trafnie widzial federacje i brak production ready
- ale czesc runtime control-plane jest dojrzalsza niz "API-only shell"

## 5. Pierwsze logiczne moduly do wyodrebnienia

To nie jest jeszcze finalna klasyfikacja, ale juz teraz widze nastepujace logiczne byty:

- `AEIS Bootstrap Backend`
- `Workspace / Project Kickoff`
- `Human Gate Global`
- `Human Gate Session Workflow`
- `Council Workflow`
- `Council Hybrid`
- `Memory API`
- `Project Runtime Memory`
- `Skills API`
- `Funding Autopilot`
- `Operator Console Next.js`
- `Legacy Dashboard`
- `Operator Mobile (planned)`
- `Project Mode Execution`
- `Worker Registry / Assignment`
- `Lab Extensions`
  - `cellular`
  - `sdr`
  - `vps`
  - `container`
  - `devices.artifact_deployer`

## 6. Co trzeba dopiero policzyc logicznie

W kolejnej iteracji inwentaryzacji trzeba zrobic:

- scalenie jednostek kodowych do modulow logicznych
- oddzielenie `module exists` od `module is wired`
- dla kazdego logicznego modulu nadac tagi:
  - `CODE_BACKED`
  - `API_BACKED`
  - `UI_BACKED`
  - `RUNTIME_VERIFIED`
  - `PROMPT_ONLY`
  - `LEGACY`
  - `LABORATORY`
  - `PLANNED`

## 7. Nastepny krok Codexa

Nastepny etap inwentaryzacji bedzie juz logiczny, nie tylko surowo-strukturalny.

Zrobie wtedy:

- wydzielenie rzeczywistych rodzin modulowych
- osobny bilans dla:
  - `workspace / Human Gate / council`
  - `funding`
  - `memory`
  - `skills`
  - `operator surfaces`
  - `lab extensions`
