# CODEX AEIS REPAIR BACKLOG

## Re-Audyt 2026-04-25

Pełny re-audyt po zmianach Phase 2 jest opisany w:

- [CODEX_AEIS_FULL_REAUDIT_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_FULL_REAUDIT_2026_04_25.md)

Nowe lub przerewidowane blokery krytyczne po re-audycie:

- `RB-P2-001`: workspace Human Gate route layer woła nieistniejące metody `HumanGate`
- `RB-P2-002`: workspace Idea Vault route layer woła nieistniejące albo przemianowane metody `IdeaVault`
- `RB-P2-003`: skills runtime i skills registry nadal nie są jednym plane
- `RB-P2-004`: funding approval flow nadal nie jest przepięty na unified governance tickets
- `RB-P2-005`: `workers` i `observability` fronty mają compile/runtime `500`
- `RB-P2-006`: `projects` UI jest podpięte pod zły plane danych
- `RB-P2-007`: mobile queue nie ma prawdziwego per-operator routing
- `RB-P2-008`: startup boot nadal ma dependency/register/manifest drift errors

**Status:** wersja robocza 0.2  
**Cel pliku:** backlog rozjazdow wykrytych podczas audytu. To nie jest jeszcze plan napraw kodu, tylko uporzadkowana lista problemow.

## 1. Krytyczne rozjazdy architektoniczne

### RB-001. Human Gate split brain

Opis:

- istnieje globalny `governance.human_gate`
- istnieje osobny sesyjny `workspace humangate`
- funding ma jeszcze osobny approval plane
- probe runtime projektu przeszedl przez sesje, ale nie zasilil globalnych request stats

Ryzyko:

- wiele approval planes
- wiele audit trails
- operator moze nie miec jednego miejsca prawdy decyzji

Priorytet:

`CRITICAL`

### RB-002. Worker pool reconciliation bug

Opis:

- `execution_plan` po odpowiedziach operatora moze mowic `vps_workers = 0`
- `worker_pool` nie jest przeliczany, jesli juz istnieje
- runtime po `launch` nadal nosi workerow VPS

Ryzyko:

- runtime topology nie zgadza sie z zatwierdzonym planem
- mozliwe koszty i decyzje niezgodne z Human Gate

Priorytet:

`CRITICAL`

### RB-003. Memory plane fragmentation

Opis:

- globalne `/api/v1/memory/*`
- osobne per-project `runtime.sqlite`
- brak potwierdzonego wspolnego plane dla search/retrieval/evidence

Ryzyko:

- system nie ma jednej pamieci prawdy
- operator i runtime moga widziec inny stan

Priorytet:

`HIGH`

## 2. Krytyczne rozjazdy kanoniczne

### RB-004. Council semantics drift

Opis:

- `decision_hierarchy` pozostaje `planner_council -> human_gate -> integration_gate`
- nawet gdy `council_plan.enabled = false`

Ryzyko:

- nazwy warstw nie odpowiadaja realnemu zachowaniu
- dokumentacja i runtime beda sie rozjezdzac

Priorytet:

`HIGH`

### RB-005. Skills and memory are described stronger than their proven runtime integration

Opis:

- `workspace` opisuje `global_skill_memory`, `skill_reuse_scout`, `vector_memory`, `lora_training`
- ale nie ma jeszcze potwierdzonego call chain do globalnych subsystemow skills/memory

Ryzyko:

- operator widzi kanoniczny jezyk funkcji, ktore runtime tylko czesciowo realizuje

Priorytet:

`HIGH`

## 3. Operator / surface drift

### RB-006. Dual operator stack

Opis:

- nowy surface Next.js
- stary legacy dashboard Python

Ryzyko:

- dwa zrodla operator truth
- drift dokumentacji
- drift nav i funkcji

Priorytet:

`HIGH`

### RB-007. Runtime truth drift: PID files and frontend bind

Opis:

- `.backend.pid` i `.frontend.pid` wskazuja martwe procesy
- frontend bind portu nie byl stabilny miedzy probami
- operator truth o tym "gdzie zyje UI" nie powinna opierac sie na starych pidach i notatkach

Ryzyko:

- operational docs i skrypty root moga wprowadzac w blad

Priorytet:

`MEDIUM`

## 4. Domeny strategiczne

### RB-008. Funding governance path is local, not unified

Opis:

- funding ma realny backend i frontend
- funding ma twardy lokalny approval przed final submit
- brak dowodu, ze approval fundingowy zasila globalny AEIS Human Gate

Priorytet:

`HIGH`

### RB-009. Mobile remains prompt-only

Opis:

- obecny prompt projektowy
- brak potwierdzonej app codebase

Priorytet:

`MEDIUM`

Uwagi:

- to nie jest blad typu "usunac"
- to jest strategiczna luka wzgledem kanonu

## 5. Rzeczy do utrzymania i opisania, nie do kasowania

### RB-010. Laboratory extensions need canonical placement

Zakres:

- `cellular`
- `sdr`
- `vps`
- `container`
- `devices.artifact_deployer`

Uwagi:

- zgodnie z decyzja operatora to sa swiadome rozszerzenia laboratoryjne
- backlog nie sugeruje ich usuwania
- trzeba je opisac i osadzic architektonicznie

Priorytet:

`DOCUMENT`

### RB-011. Council runtime does not yet enforce real multi-model voting

Opis:

- sesje councilu sa zywe
- ale probe nie wygenerowaly automatycznych analiz ani rund dyskusji
- konsolidacja moze zostac ustawiona bez udokumentowanego glosowania modeli

Priorytet:

`HIGH`

### RB-012. Model registry and workspace council configuration are split

Opis:

- model registry ma CRUD, capabilities i performance
- `workspace/settings/council-members` to osobny plane
- brak jednego truth plane dla skladu rady modeli

Priorytet:

`HIGH`

### RB-013. Autonomy controller is present but detached from the main runtime spine

Opis:

- autonomy stages istnieja
- runtime pozostaje na `observe`
- brak dowodu, ze `workspace` i `project_mode` steruja sie tym stanem

Priorytet:

`HIGH`

### RB-014. Memory singletons are not bootstrapped as one persistent startup plane

Opis:

- `app.py` bootstrappuje `idea_vault`, `worker_registry`, `skills_registry` i `human_gate`
- startup nie bootstrappuje `memory.indexer`, `memory.evidence_store` ani `memory.retrieval`
- manualne probe pokazuja, ze index/search i evidence write dzialaja, ale sa uruchamiane leniwie i startowo pozostaja puste

Ryzyko:

- globalna pamiec wyglada jak plane, ale nie ma jednego, jawnego startup lifecycle
- operator i runtime moga zaczynac z pustym shared-memory stanem mimo istniejacego subsystemu

Priorytet:

`HIGH`

### RB-015. Skills runtime is not bootstrapped from registry or filesystem

Opis:

- registry skills przechowuje wpisy i UI je pokazuje
- runtime stats zwracaja `loaded_skills = 0`
- execute dla `seed_skill_001` konczy sie `Unknown skill`
- `skills/runtime.py` laduje specyfikacje tylko po dostarczeniu `skills_dir`, a startup tego nie robi

Ryzyko:

- kanoniczny model skill-driven AEIS nie moze zadzialac end-to-end
- operator moze widziec skille, ktorych execution plane nie potrafi uruchomic

Priorytet:

`HIGH`

### RB-016. `/memory/evidence/stats` is shadowed by dynamic evidence route

Opis:

- `memory_routes.py` deklaruje `/evidence/{evidence_id}` przed `/evidence/stats`
- runtime `GET /api/v1/memory/evidence/stats` konczy sie `404`

Ryzyko:

- jedna z podstawowych tras diagnostycznych evidence plane jest realnie niedostepna
- diagnoza i observability pamieci sa slabsze niz sugeruje sama obecność API

Priorytet:

`MEDIUM`

### RB-017. Future masterplan must avoid greenfield duplication over existing runtime planes

Opis:

- `docs/claude_system_audit/parallel/PROMPT_02_CODEX_AGENT_B.md` traktuje `skills` i `memory` jako greenfield
- `docs/claude_system_audit/parallel/PROMPT_03_KIMI_AGENT_K.md` planuje fundingowe dopelnienia w nowych namespace'ach
- realne repo ma juz `src/sylion-pipeline/sylion/skills/*`, `memory/*`, `funding_autopilot/*`, `workspace`, `project_mode`

Ryzyko:

- drugi skills plane
- drugi memory plane
- drugi funding plane
- integracja obok realnego `workspace -> project_mode`, zamiast naprawy tego spinu

Priorytet:

`CRITICAL`

## 6. Co dalej trafi do backlogu

W kolejnych etapach dojde m.in.:

- rzeczywista interakcja browserowa na dashboardzie i funding
- klasyfikacja duplicatow governance/core/security
- API/UI coverage gaps
- production readiness gaps
- mobile backend bridge gaps
