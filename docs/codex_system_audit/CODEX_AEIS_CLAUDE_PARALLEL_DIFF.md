# CODEX AEIS CLAUDE PARALLEL DIFF

**Status:** wersja robocza 0.1  
**Cel pliku:** zapisac roznice miedzy audytem i planami rownoleglymi Claude'a a ustaleniami Codexa, tak aby pozniejszy masterplan naprawczy nie nadpisal istniejacego runtime  
**Zrodla:** `docs/claude_system_audit/*`, `docs/claude_system_audit/parallel/*`, kod repo, runtime probe 2026-04-24

## 1. Wspolne punkty z Claude

W kilku osiach audyt Claude'a i audyt Codexa sa zgodne:

- AEIS nie jest production ready
- governance i Human Gate sa rozszczepione
- mobile nie ma jeszcze realnej codebase aplikacyjnej
- model council nie jest jeszcze egzekwowany jako twardy runtime voting plane
- system wymaga masterplanu pod rownolegle naprawy, a nie lokalnych hotfixow

To oznacza, ze kierunek "konsolidacja do production ready" jest poprawny.

## 2. Gdzie Codex widzi wieksza dojrzalosc niz Claude parallel

Najwieksze niedoszacowania w planach parallel Claude'a dotycza obszarow, ktore juz zyja:

### 2.1. `workspace` nie jest shellowym frontem pod nowy core

Probe kontrolny `project_a81b2c935d6c` pokazal, ze `workspace` potrafi:

- przyjac kickoff projektu
- wygenerowac `canonical_book`
- wygenerowac `masterplan`
- przeprowadzic sesje `workspace/humangate`
- zapisac approvals
- zbudowac `memory_policy`, `worker_plan`, `council_plan`, `execution_plan`, `audit_plan`
- przejsc do `launch`
- zamrozic masterplan jako execution-ready state

Wniosek:

- przyszly masterplan nie moze traktowac `workspace` jak cienkiej powloki dla nowego `core`
- to jest obecny spine, ktory trzeba domknac i zunifikowac

### 2.2. `project_mode` nie jest eksperymentalnym dodatkiem

`workspace launch` realnie uruchamia `project_mode.engine`.

`project_mode.store` utrwala m.in.:

- `canonical_book`
- `masterplan`
- `memory_policy`
- `worker_plan`
- `council_plan`
- `execution_plan`
- `governance_policy`
- `audit_plan`
- `worker_pool`
- `council_members`
- `hierarchy_layers`

Wniosek:

- plan naprawczy nie moze rekonstruowac execution layer od zera poza `project_mode`
- trzeba naprawic jego integracje i truth plane, nie budowac rownoleglego execution core obok

### 2.3. Funding jest juz rozbudowanym pionem, nie greenfieldem

W `src/sylion-pipeline/sylion/funding_autopilot` istnieja:

- store
- service
- routes
- submission sessions
- approval events
- alerts
- audit events

Runtime potwierdzil:

- `GET /api/v1/funding/sources` = `200`
- `GET /api/v1/funding/submission/sessions` = `200`
- `GET /api/v1/funding/submission/approvals` = `200`
- `GET http://127.0.0.1:3000/funding` = `200`

Wniosek:

- Claude poprawnie widzi potrzebe dopelnien, ale plan rownolegly nie powinien zakladac, ze funding trzeba zbudowac jako osobny, nowy subsystem
- brakujace elementy musza rozszerzac `funding_autopilot`, a nie tworzyc drugi pion obok

### 2.4. Skills i memory istnieja, ale sa zle zszyte

Codex potwierdzil:

- `src/sylion-pipeline/sylion/skills/*` istnieje
- `src/sylion-pipeline/sylion/api/skills_routes.py` istnieje
- `/api/v1/skills/skills` i `/skills` dzialaja
- `src/sylion-pipeline/sylion/memory/*` istnieje
- `/api/v1/memory/*` odpowiada
- manualne index/search i evidence write dzialaja

Problem nie brzmi:

- "nie ma skills"
- "nie ma memory"

Problem brzmi:

- skills runtime nie jest bootstrappowany
- memory startup binding jest niepelny
- te planes nie sa jeszcze glownymi warstwami wspolnej prawdy

Wniosek:

- plan typu "greenfield skills layer" i "greenfield memory layer" grozi duplikacja istniejących namespace'ow zamiast naprawy bootstrapu i integracji

## 3. Najbardziej ryzykowne zalozenia w Claude parallel prompts

### 3.1. Agent B traktuje skills jako greenfield

Claude parallel prompt dla Codexa mowi wprost:

- `skills/ (NEW)`
- `api/skills_routes.py`
- `Greenfield — tworzysz od zera`

To jest w napieciu z realnym repo, gdzie juz istnieja:

- `src/sylion-pipeline/sylion/skills`
- `src/sylion-pipeline/sylion/api/skills_routes.py`

Ryzyko:

- powstanie drugi skills plane
- duplikacja tras API
- konflikt nazw i odpowiedzialnosci

### 3.2. Agent B traktuje memory similarity jako nowy plane obok istniejacego memory

Claude parallel prompt zaklada:

- `memory/search/ (NEW)`
- `memory/similarity/ (NEW)`
- `api/memory_search_routes.py`

Tymczasem w repo juz istnieje:

- `src/sylion-pipeline/sylion/memory/indexer.py`
- `src/sylion-pipeline/sylion/memory/retrieval.py`
- `src/sylion-pipeline/sylion/memory/evidence_store.py`
- `src/sylion-pipeline/sylion/api/memory_routes.py`

Ryzyko:

- drugi memory plane zamiast naprawy pierwszego
- rozjazd miedzy similarity search a istniejacym evidence/index/retrieval
- jeszcze wiekszy split shared memory

### 3.3. Agent K planuje fundingowe dopelnienia jako nowe pliki poza glownym pionem

Claude parallel prompt dla Kimi proponuje:

- `funding/program_scanner.py`
- `funding/browser_automation.py`
- `funding/grant_reporting.py`
- `api/funding_scanner_routes.py`
- `api/funding_reporting_routes.py`

Samo dopelnienie funkcji jest sensowne, ale namespace jest ryzykowny, bo istnieje juz:

- `src/sylion-pipeline/sylion/funding_autopilot/*`

Ryzyko:

- drugi pion funding obok `funding_autopilot`
- dwa approval planes i dwa store'y
- utrata istniejącego submission flow

Zalecenie:

- dopelnienia fundingowe trzeba osadzac wewnatrz `funding_autopilot` albo w jego jawnie zintegrowanych submodulach

### 3.4. Agent A buduje nowy `core/*` adapter spine, a niekoniecznie naprawia obecny spine

Claude parallel plan opiera integracje na:

- `core/integration_points.py`
- `core/adapter_registry.py`
- `Null -> Real adapters`

To jest sensowna technika integracyjna, ale tylko wtedy, gdy nie obchodzi juz istniejacego spine:

- `workspace`
- `project_mode`
- `ai_workspace_routes.py`

Ryzyko:

- powstanie nowa warstwa "core", ktora bedzie obok realnego `workspace -> project_mode`
- produkcyjny truth plane nadal pozostanie w starym flow, a nowy core bedzie kolejnym bytem federacyjnym

### 3.5. Final Agent D zaklada, ze glowny problem to swap adapterow

Claude parallel final prompt skupia sie na:

- `Null -> Real adapter swap`
- merge conflict resolution
- testy i audit

Codex widzi, ze najciezsze integracje leza tez gdzie indziej:

- startup bootstrap memory
- startup bootstrap skills runtime
- unifikacja Human Gate planes
- unifikacja model registry vs workspace council-members
- truth plane `workspace` vs global governance routes

Wniosek:

- sam adapter swap nie domknie production-ready

## 4. Co z planow Claude parallel warto zachowac

Nie wszystko wymaga odrzucenia. Warto zachowac:

- zasade twardego rozdzialu ownershipu plikow przy pracy rownoleglej
- pomysl na czwarty etap finalnej integracji i testow "jak czlowiek"
- przeniesienie mobile do sredniego/duzego workstreamu
- danie Kimi lzejszych, bardziej proceduralnych prac
- podejscie append-only dla wspolnych plikow integracyjnych

## 5. Co trzeba skorygowac zanim powstanie finalny masterplan 4-promptowy

### 5.1. Zasada namespace

Nowe naprawy powinny byc planowane wewnatrz istniejacych namespace'ow:

- `src/sylion-pipeline/sylion/skills/*`
- `src/sylion-pipeline/sylion/memory/*`
- `src/sylion-pipeline/sylion/funding_autopilot/*`
- `src/sylion-pipeline/sylion/api/*`
- `src/sylion-pipeline/sylion/project_mode/*`
- `src/sylion-pipeline/sylion/api/ai_workspace_routes.py`

Zamiast budowania rownoleglych top-level katalogow typu:

- `skills/`
- `memory/search/`
- `funding/*`
- `api/skills_routes.py` poza obecnym namespace

### 5.2. Zasada spine

Masterplan musi przyjac jako realny spine:

- `workspace -> Human Gate session -> project_mode`

a nie:

- abstrakcyjny nowy `core` zbudowany obok juz istniejacego flow

### 5.3. Zasada naprawy

Dla `skills` i `memory` priorytetem nie jest greenfield, tylko:

- bootstrap
- startup binding
- runtime integration
- proof in real flow

Dla `funding` priorytetem nie jest "zrobic funding", tylko:

- dopelnic brakujace capabilities
- wpiac w wspolny Human Gate / governance
- nie zgubic istniejacych approval events i submission sessions

Dla `mobile` greenfield/merge jest dopuszczalny, bo tam kodu produkcyjnego nie znaleziono.

## 6. Wniosek praktyczny dla przyszlego masterplanu

Najuczciwsza rekomendacja Codexa brzmi:

- wykorzystac strukture 4-etapowa Claude parallel jako szkielet organizacyjny
- ale przepisac jej tresc techniczna na podstawie realnego spine AEIS
- usunac greenfieldowe zalozenia tam, gdzie kod i runtime juz istnieja
- skierowac najciezsze prace na unifikacje planes, a nie na tworzenie kolejnych subsystemow obok

Czyli:

- Claude ma dobry szkielet organizacyjny
- ale wymaga korekty technicznej przed uzyciem jako prompt execution plan
