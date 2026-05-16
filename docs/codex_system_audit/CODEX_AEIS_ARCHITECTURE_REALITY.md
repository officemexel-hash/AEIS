# CODEX AEIS ARCHITECTURE REALITY

**Status:** wersja robocza 0.3  
**Cel pliku:** opis aktualnie potwierdzonej architektury AEIS na podstawie kodu i probe runtime

## 1. Obraz ogolny

Na obecnym etapie AEIS wyglada jak system warstwowy, ale nie w pelni skonsolidowany.

Najbardziej prawdopodobny obraz:

- istnieje warstwa API agregujaca bardzo duza liczbe routerow
- istnieje osobny, rozbudowany `workspace` flow bliski kanonicznemu AEIS
- istnieja osobne subsystemy:
  - governance
  - memory
  - skills
  - project execution
  - funding
  - operator console
  - legacy dashboard
- ale miedzy nimi sa slady federacji i rozszczepienia, nie jednego jednolitego engine

## 2. Warstwy potwierdzone w kodzie i runtime

### 2.1. API Aggregation Layer

Potwierdzenie:

- `src/sylion-pipeline/sylion/api/router.py`

Wnioski:

- glowny router agreguje bardzo duza liczbe sub-routerow
- obok klasycznych rodzin `core / governance / memory / skills` montuje tez:
  - `ai_workspace_router`
  - `project_mode_router`
  - `funding_router`
  - `worker_router`
  - `vps_router`
  - `container_router`
  - `cellular_router`
  - `sdr_router`

To nie jest prosty backend. To jest szeroka warstwa integracyjna i control plane.

### 2.2. Workspace / Planning Layer

Potwierdzenie:

- `src/sylion-pipeline/sylion/api/ai_workspace_routes.py`

Funkcje potwierdzone:

- project kickoff
- budowa canon book
- budowa masterplanu
- pytania operatorskie
- wybory o:
  - canon rigor
  - learning / memory policy
  - decomposition shape
  - contract freeze
  - topology local / VPS / hybrid
  - worker composition
  - council scale
  - council mode
  - autonomy mode
  - audit escalation
- settings plane dla:
  - key vault
  - runtime LLM config
  - hierarchies
  - council members
  - books
  - Human Gate sessions

Najmocniejszy probe runtime:

- projekt `project_a81b2c935d6c`
- session `hgs_b6c8cea3c4c5`
- pełny przebieg kickoff -> pytania -> approvals -> launch
- wynik: `canonical_book`, `masterplan`, `memory_policy`, `worker_plan`, `council_plan`, `execution_plan`, `audit_plan`
- stan po launch: `queued/build`, `masterplan.status = frozen`, `worker_pool_count = 6`, `council_members_count = 5`, `hierarchy_layers_count = 29`

Wniosek:

- to jest najblizszy kanonicznemu AEIS planning plane
- to jest obecnie najmocniejszy, realnie dzialajacy spine systemu

### 2.3. Governance Layer

Potwierdzenie:

- `src/sylion-pipeline/sylion/governance/human_gate.py`
- `src/sylion-pipeline/sylion/governance/council_workflow.py`
- `src/sylion-pipeline/sylion/governance/council_hybrid.py`
- `src/sylion-pipeline/sylion/api/governance_routes.py`

Wnioski:

- istnieje klasyczny Human Gate request/review
- istnieje council voting 4/4 dla D3+
- istnieje hybrid deliberation council

Ale:

- `workspace` utrzymuje tez osobny sesyjny Human Gate
- `workspace` ma osobny council/session plane
- to oznacza rozszczepienie governance plane

### 2.4. Memory Layer

Potwierdzenie:

- `memory_routes.py`
- `evidence_store.py`
- `indexer.py`
- `retrieval.py`
- `self_model_store.py`
- `project_mode/engine.py` uzywa `EvidenceStore` i `Indexer`

Wnioski:

- memory istnieje jako globalny subsystem
- project execution tworzy tez per-project runtime DB
- memory plane nie jest jeszcze jednym wspolnym plane
- `ai_workspace_routes.py` importuje z memory tylko `book_generator`
- realne globalne indeksowanie artefaktow pojawia sie dopiero nizej, w `project_mode.engine`
- startup `src/sylion-pipeline/sylion/api/app.py` nie bootstrappuje `get_indexer()`, `get_evidence_store()` ani `get_retrieval()` z jednym trwalym `db_path`
- skutkiem jest to, ze globalny memory API jest zywy, ale startowo pusty i wyglada na leniwie, a nie centralnie, zbindowany plane
- dodatkowo `memory_routes.py` ma konflikt tras: `/evidence/{evidence_id}` cieniueje `/evidence/stats`

### 2.5. Skills Layer

Potwierdzenie:

- `skills_routes.py`
- `skills/registry.py`
- `skills/executor.py`
- `skills/demand_signal.py`
- `skills/catalog.py`
- `skills/runtime.py`

Wnioski:

- skills sa realnym subsystemem
- `workspace` mowi o `global_skill_memory` i `skill_reuse_scout`
- ale nie ma jeszcze potwierdzonego runtime call chain z `workspace` do globalnego `skills` API
- `ai_workspace_routes.py` nie importuje globalnych modulow `sylion.skills.*`; na poziomie planning routera skills sa glownie opisywane przez polityki i wybory operatora
- startup `app.py` bootstrappuje `skills_registry`, ale nie bootstrappuje `skills_runtime`
- `skills/runtime.py` wymaga `skills_dir`, aby zaladowac specyfikacje; w obecnym runtime `loaded_skills = 0`

Wniosek rozszerzony:

- skills sa dzis podzielone na co najmniej dwa planes:
  - registry / metadata plane
  - executor runtime plane
- registry zyje, ale runtime execution plane nie jest jeszcze dopiety do glownego spinu

### 2.6. Project Execution Layer

Potwierdzenie:

- `src/sylion-pipeline/sylion/project_mode/engine.py`
- `src/sylion-pipeline/sylion/project_mode/store.py`

Funkcje potwierdzone:

- tworzenie execution plan
- rejestracja workerow
- assignment modulow
- deploy bundle
- runtime DB
- validation
- writing learning outputs

Wniosek:

- execution istnieje jako osobny engine
- jest uruchamiany przez `workspace launch`
- to w `project_mode.engine`, a nie w samym `workspace`, pojawia sie realne globalne indeksowanie przez `global_indexer`
- `project_mode.store` utrwala tez `canonical_book`, `masterplan`, `memory_policy`, `worker_plan`, `council_plan`, `execution_plan`, `governance_policy`, `audit_plan`, `worker_pool`, `council_members` i `hierarchy_layers`

### 2.7. Project Registry Layer

Potwierdzenie:

- `src/sylion-pipeline/sylion/api/projects_routes.py`
- `GET /api/v1/projects` = `200`
- `GET http://127.0.0.1:3000/projects` = `200`

Wnioski:

- istnieje osobny rejestr projektow poza samym flow kickoff
- operator ma wglad w wiele projektow i ich fazy zycia
- `workspace` nie jest jedynym miejscem istnienia projektu; projekty staja sie bytem runtime

### 2.8. Worker Fleet Layer

Potwierdzenie:

- `src/sylion-pipeline/sylion/api/worker_routes.py`
- `src/sylion-pipeline/sylion/worker/registry.py`
- sekwencyjny probe `register -> list -> get -> heartbeat -> delete`

Wnioski:

- worker registry jest realnym subsystemem
- worker fleet nie jest tylko papierowym elementem architektury
- domyslna flota startuje pusta
- biblioteka topologii istnieje, ale obecnie nie ma zapisanych topologii

### 2.9. Observability Layer

Potwierdzenie:

- `src/sylion-pipeline/sylion/api/observability_routes.py`
- `src/sylion-pipeline/sylion/observability/hub.py`
- `src/sylion-pipeline/sylion/observability/log_aggregator.py`

Dowody runtime:

- log roundtrip
- metric roundtrip
- trace roundtrip
- `snapshot` zwraca `LocalLogBackend`

Wnioski:

- observability jest realnym subsystemem runtime
- to obecnie warstwa deweloperska / lokalna, nie jeszcze produkcyjna telemetryka rozproszona

### 2.10. Model Provider and Registry Layer

Potwierdzenie:

- `src/sylion-pipeline/sylion/api/ai_providers_routes.py`
- `src/sylion-pipeline/sylion/api/model_registry_routes.py`
- `src/sylion-pipeline/sylion/cognitive/model_registry.py`

Dowody runtime:

- `/api/v1/ai-providers/list` zwraca aktywnych providerow i dostepnosc kluczy
- `/api/v1/ai-providers/test/openai` wykonuje realny call
- `/api/v1/model-registry/*` pozwala na CRUD, capabilities i performance snapshots

Wnioski:

- provider plane jest zywy
- model registry jest zywy
- ale oba te planes nie skladaja sie jeszcze w jeden, twardy runtime council plane dla `workspace`

### 2.11. Autonomy Layer

Potwierdzenie:

- `src/sylion-pipeline/sylion/api/aeis_routes.py`
- `/api/v1/aeis/autonomy/stages`
- `/api/v1/aeis/autonomy/status`

Wnioski:

- istnieje kodowa warstwa autonomii z 5 etapami
- obecny runtime pozostaje na `observe`
- autonomia jest dzis bardziej osobnym subsystemem niz sterownikiem glownego flow `workspace`

### 2.12. Operator Layer

Potwierdzenie:

- Next.js routes w `src/sylion-frontend/src/app/(app)`
- legacy dashboard w `src/sylion-pipeline/dashboard`

Wnioski:

- sa co najmniej dwa operatoryczne stacki:
  - nowy surface Next.js
  - starszy legacy dashboard Python
- nowy Next.js surface byl w tej probe dostepny na `3000`
- runtime bind portu operatora nie byl stabilny miedzy probami, co wzmacnia teze o operational drift

### 2.13. Domain Layer: Funding

Potwierdzenie:

- `src/sylion-pipeline/sylion/funding_autopilot/*`
- `src/sylion-frontend/src/app/(app)/funding/page.tsx`

Wniosek:

- funding jest osobnym pionem domenowym, nie tylko dodatkiem
- funding ma wlasny store, approval events, submission sessions i audit events
- funding governance jest lokalnie mocne, ale nie jest jeszcze udowodnione jako czesc jednego globalnego Human Gate plane

### 2.14. Laboratory Extensions

Potwierdzenie:

- `cellular`
- `sdr`
- `vps`
- `container`
- `devices`

Wniosek:

- sa to swiadome rozszerzenia platformy
- musza byc opisane jako `EXTENSIONS / LABORATORY`, nie jako przypadkowy balast

### 2.15. Planned Mobile Layer

Potwierdzenie negatywne:

- brak trafien `operator_mobile`, `operator-mobile`, `follow-me`, `device binding` w `src/sylion-pipeline`
- brak trafien `operator_mobile`, `operator-mobile`, `follow-me`, `device binding` w `src/sylion-frontend/src`

Wniosek:

- operator mobile nie ma jeszcze realnej warstwy backend/frontend w `src/`
- mobile jest obecnie elementem kanonu i promptow, nie zywej architektury runtime

## 3. Najwazniejsze rozszczepienia architektoniczne

### 3.1. Human Gate split

Mamy:

- globalny `governance.human_gate`
- sesyjny `workspace humangate`

To nie jest jeden spojny approval plane.

### 3.2. Memory split

Mamy:

- globalne `/api/v1/memory/*`
- lokalne per-project `runtime.sqlite`
- leniwe singletony `indexer/evidence/retrieval`, ktore nie sa startowo zbindowane z jednym startup plane

To nie jest jeden spojny memory plane.

### 3.3. Funding governance split

Mamy:

- lokalne `approval_event` i `submission_session` w `funding_autopilot`
- oddzielny globalny `governance.human_gate`

Nie ma na razie dowodu, ze funding final approval przeplywa przez globalny AEIS gate.

### 3.4. Council semantics drift

Mamy:

- bogaty model councilu w pytaniach i configu
- ale domyslny flow potrafi go zredukowac do `active_size = 1`
- przy zachowaniu nazwy `planner_council` w hierarchy

### 3.5. Model plane split

Mamy:

- provider list i live provider tests
- model registry CRUD
- `workspace/settings/council-members`

Ale:

- nie ma jeszcze jednego, udowodnionego plane laczacego providerow, registry, role, rangi i sklad realnej rady modeli
- workspace potrafi wygenerowac `council_members`, ale nie ma jeszcze dowodu, ze sa one pobierane z jednego kanonicznego registry modeli

### 3.6. Worker topology drift

Mamy:

- `execution_plan` po wyborach operatora
- oddzielnie utrwalony `worker_pool`

Te dwa byty potrafia sie rozjechac.

## 4. Architektura realna na teraz

Najuczciwszy opis na obecnym etapie brzmi:

AEIS nie jest jednym, czystym systemem "od idei do wykonania" z jedna warstwa governance, jedna warstwa memory i jedna rada modeli.

AEIS jest obecnie:

- szerokim backendem z wieloma rodzinami API
- z najlepiej rozwinietym flow w `workspace`
- z osobnym execution engine w `project_mode`
- z osobnymi subsystemami governance, memory i skills
- z prawdziwymi domenami pionowymi jak funding
- z rownoleglymi surface'ami operatorskimi
- z rozszczepieniem kilku kluczowych warstw
- z prawdziwym spine `workspace -> project_mode`, ale bez pelnej unifikacji council/memory/skills/governance

## 5. Co dalej sprawdzic

- czy `workspace` realnie konsumuje globalny `skills` subsystem
- czy `workspace` realnie konsumuje globalny `memory` subsystem
- czy `governance_routes` i `workspace` mozna zrekonstruowac do jednego Human Gate plane
- czy `funding` mozna zrekonstruowac do jednego Human Gate plane bez utraty lokalnych rygorow submit
- czy operator console pokazuje flow `workspace`
- czy istnieje jakiekolwiek backendowe przygotowanie pod mobile approvals poza promptami
