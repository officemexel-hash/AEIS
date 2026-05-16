# CODEX AEIS Full Functionality Roadmap 2026-04-25

**Status:** draft 1.0  
**Cel:** rozpisać konkretny plan doprowadzenia AEIS od obecnego stanu po re-audycie do pełnej funkcjonalności systemowej, a nie tylko do punktowych napraw  
**Podstawa:**  
- [CODEX_AEIS_UNIFIED_REPAIR_MASTERPLAN_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_UNIFIED_REPAIR_MASTERPLAN_2026_04_25.md)
- [CODEX_AEIS_AUDIT500_REVIEW_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_AUDIT500_REVIEW_2026_04_25.md)
- [CODEX_AEIS_REPAIR_BACKLOG.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_REPAIR_BACKLOG.md)
- [CODEX_AEIS_TEST_BOOK_INTEGRATION_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_TEST_BOOK_INTEGRATION_2026_04_25.md)

## 1. Co rozumiem jako „pełna funkcjonalność” AEIS

AEIS uznamy za funkcjonalnie pełny dopiero wtedy, gdy jednocześnie działają:

1. `Idea -> Source of Truth -> Masterplan -> Execution`
   jako jeden spójny flow operatorski.

2. `Human Gate`
   od momentu pomysłu, przez zmianę kierunku, aż po działania finalne i zewnętrzne.

3. `Model Council`
   jako realny mechanizm ról, rang, wag głosów, critic signature, sentinels i wpływu na plan.

4. `Memory`
   jako wspólna warstwa search/evidence/similarity/reuse, a nie kilka luźnych singletonów i endpointów.

5. `Skills`
   jako wspólny plane registry/runtime/execute/usage, a nie dwa byty obok siebie.

6. `Funding`
   jako domena działająca end-to-end, ale spięta z globalnym governance.

7. `Operator Console`
   jako prawdziwe centrum dowodzenia oparte o właściwe backendowe plane’y.

8. `Operator Mobile`
   jako realna warstwa operatorska z routingiem per operator i unified governance queue.

9. `Runtime topology`
   jako zgodna z planem i zgodna z politykami autonomii oraz kosztów.

10. `Observability + Security + Recovery`
    jako realnie działające filtry stabilności, a nie tylko powierzchnie API/UI.

11. `Evidence-driven production readiness`
    poparte Księgą Testów 500, a nie samą deklaracją.

## 2. Co jest już częściowo zaawansowane i nie powinno być robione od zera

Z `.audit_500` i wcześniejszych audytów wynika, że część obszarów jest już naprawiona lub rozbudowana i należy je **wykorzystać**, a nie przepisać:

### 2.1. Idea plane

Zaawansowane elementy:
- rozszerzone lifecycle statuses
- soft delete
- archive/unarchive
- stale detection
- append-only lifecycle log
- część Human Gate handoff w samym `idea_vault`

Wniosek:
- nie projektować nowego „Idea subsystem”
- dopiąć route layer, workspace integration i operator flow

### 2.2. Council canonicalization

Zaawansowane elementy:
- `VALID_ROLES`
- `VALID_RANKS`
- weighted consensus
- critic signature
- sentinel evaluation
- consolidate-with-signatures

Wniosek:
- nie budować nowego council engine
- dopiąć council do realnego spine projektu, model registry i autonomy policy

### 2.3. Security hardening

Zaawansowane elementy:
- sporo brakujących metod w `audit_sink`, `auth_provider`, `execution_guard`, `secret_provider`, `phantom_wrapper`, `security_audit`, `security_profiles`

Wniosek:
- traktować security jako obszar już częściowo domknięty
- skupić się na integracji z resztą systemu i na końcowych testach

### 2.4. Deployment smoke fixes

Zaawansowane elementy:
- health path / dockerfile path poprawione

Wniosek:
- nie wracać do tego jako głównego problemu
- potraktować jako wstępny hardening, nie jako dowód końcowy

## 3. Co nadal blokuje pełną funkcjonalność

To są rzeczy, które nadal trzeba naprawić, nawet po uwzględnieniu `.audit_500`.

### 3.1. Core blockers

- `workspace Human Gate` nadal broken
- `workspace ideas` nadal broken
- startup bootstrap nadal niespójny
- routing truth plane nadal jest tylko częściowo stabilny

### 3.2. Governance blockers

- split Human Gate plane
- split council plane vs model registry
- autonomy detached from runtime spine

### 3.3. Adaptive blockers

- split `skills runtime` / `skills registry`
- split `memory bootstrap/index` / `public API` / `project runtime`

### 3.4. Domain blockers

- funding approvals nie są jeszcze jednym plane z governance tickets
- mobile queue nie ma prawdziwego routing per operator

### 3.5. Operator blockers

- `projects` UI jest podpięte pod zły plane
- `workers` i `observability` mają compile/runtime `500`
- operator/mobile surface potrafi maskować awarie fallbackiem

### 3.6. Runtime blockers

- worker pool reconciliation
- topology drift
- niepełny dowód realnej autonomii systemu

## 4. Roadmap wykonawczy

Poniżej rozpisuję plan w postaci konkretnych workstreamów, które razem domykają pełną funkcjonalność.

## 5. Workstream A: Stabilizacja rdzenia startowego

**Cel:** system ma startować czysto i przewidywalnie.

### Zakres

1. uporządkować startup singletonów
2. zlikwidować dependency/register drift errors
3. ustalić jawny lifecycle dla:
   - governance
   - workspace
   - council
   - memory
   - skills
   - funding
4. odróżnić prawdziwe bootstrapowane plane’y od lazy-init helperów

### Konkretne zadania

- przejrzeć `app.py` i startup registration order
- ustalić, które services są obowiązkowe do startu
- naprawić broken dependency references w manifestach i rejestracjach
- dopiąć health/readiness, żeby nie maskował uszkodzeń
- uporządkować route mount order i diagnostykę bootu

### Done

- backend log bez krytycznych startup drift errors
- `health` nie zgłasza fałszywego „ok” przy brakujących centralnych plane’ach
- bootstrap jest deterministyczny

### Testy z Księgi 500

- `SMOKE`
- `CODE`
- część `API`

## 6. Workstream B: Workspace Spine Recovery

**Cel:** workspace ma być znowu prawdziwym wejściem AEIS.

### Zakres

1. naprawa `workspace Human Gate`
2. naprawa `workspace ideas`
3. naprawa `workspace council`
4. potwierdzenie `workspace sessions`
5. zachowanie flow kickoff -> SoT -> masterplan -> launch

### Konkretne zadania

- zszyć `ai_workspace_routes.py` z realnym API `HumanGate`
- zszyć `ai_workspace_routes.py` z realnym API `IdeaVault`
- naprawić parametry i signatures route/service
- usunąć route expectations wobec nieistniejących metod
- rozdzielić shellowe endpoints od endpoints, które mają realnie wykonywać logikę

### Done

- brak `500` na krytycznych `workspace/*`
- pomysł można utworzyć, obejrzeć, policzyć statystyki i przejść przez lifecycle
- workspace Human Gate nie używa fantomowego API

### Testy z Księgi 500

- `SMOKE`
- `API`
- `IDEA`
- część `UI`

## 7. Workstream C: Unified Human Gate

**Cel:** AEIS ma mieć jedną warstwę decyzji człowieka.

### Zakres

1. zintegrować `workspace Human Gate` z `governance tickets`
2. wyeliminować approval split brain
3. ujednolicić audit trail decyzji
4. zmapować typy gate’ów do jednej warstwy

### Konkretne zadania

- ustalić jeden kanoniczny obiekt decyzji / ticketu
- przepiąć ścieżki idea approval, workspace approval, final action approval
- upewnić się, że mobile i funding nie tworzą osobnych approval światów
- dopiąć statusy, escalation, delegation i decision history

### Done

- wszystkie istotne approvale zapisują się w jednym plane
- operator ma jedną kolejkę decyzji
- audit trail decyzji jest wspólny

### Testy z Księgi 500

- `IDEA`
- `PLAN`
- `MOBILE`
- `FUND`
- `SEC`

## 8. Workstream D: Council + Model Governance

**Cel:** rada modeli ma działać naprawdę, a nie tylko istnieć.

### Zakres

1. spiąć `council_hybrid` z realnym flow projektu
2. spiąć council z model registry
3. spiąć council z autonomy policy
4. wymusić realny udział councilu w zmianach i planowaniu

### Konkretne zadania

- określić źródło prawdy dla składu rady modeli
- uzgodnić role, rangi, weights i critic requirement z workspace settings
- wpiąć council w tworzenie i zmianę masterplanu
- wpiąć sentinels w decyzje kosztowe i bezpieczeństwa
- dopiąć log deliberacji i operator surface do realnych danych

### Done

- council ma jeden truth plane
- critic signature ma realne znaczenie
- tie i sentinel reject wpływają na flow systemu
- council nie jest tylko CRUD-em sesji

### Testy z Księgi 500

- `COUNCIL`
- `PLAN`
- część `SEC`

## 9. Workstream E: Skills Plane Unification

**Cel:** skills mają być żywe end-to-end.

### Zakres

1. registry i runtime mają być jednym plane’em
2. runtime ma ładować skille z prawdziwego źródła
3. execute path ma działać dla skilli z registry
4. usage/success telemetry ma być prawdziwa

### Konkretne zadania

- ustalić jeden bootstrap registry/runtime
- naprawić source-of-truth dla loaded skills
- naprawić mapping registry entry -> executable runtime spec
- dopiąć execution errors do governance / repair / observability
- dopiąć usage metrics i success rate

### Done

- `loaded_skills` i `total_skills` są spójne lub jawnie mapowane
- seed i registry skills dają się wykonać
- plan może korzystać ze skills bez obejść

### Testy z Księgi 500

- `SKILL`
- część `PLAN`
- część `REPAIR`

## 10. Workstream F: Memory Plane Unification

**Cel:** memory ma być wspólną warstwą uczenia się systemu.

### Zakres

1. bootstrap memory w startup lifecycle
2. retrieval/search/evidence/index jako jeden plane
3. similarity i reuse wpięte w planowanie
4. trwałość po restarcie

### Konkretne zadania

- określić, co jest globalnym memory store, a co per-project cache
- naprawić publiczne memory API
- dopiąć similarity hit do source of truth/masterplan flow
- dopiąć evidence write/read do operator i repair loop

### Done

- `memory search` działa
- `memory evidence` działa
- similarity i reuse mają realny wpływ na system
- restart nie resetuje pamięci w sposób przeczący kanonowi

### Testy z Księgi 500

- `MEM`
- część `PLAN`
- część `REPAIR`
- `E2E`

## 11. Workstream G: Funding Convergence

**Cel:** funding ma działać end-to-end w ramach jednego AEIS.

### Zakres

1. zachować istniejące funding capabilities
2. przepiąć approval flow na unified governance
3. dopiąć browser automation i reporting do wspólnego audit trail

### Konkretne zadania

- przeanalizować lokalny funding approval store
- przepiąć finalne actions do governance tickets
- zachować domain-specific metadata fundingową
- upewnić się, że operator i mobile widzą funding approvals jako część jednego systemu

### Done

- funding nie ma osobnego approval universe
- final submit bez approval jest blokowany we właściwym plane
- reporting i browser actions mają wspólny evidence trail

### Testy z Księgi 500

- `FUND`
- `MOBILE`
- `SEC`
- `E2E`

## 12. Workstream H: Operator Console Recovery

**Cel:** operator ma widzieć prawdę systemu, nie błędny lub udawany obraz.

### Zakres

1. naprawa `/projects`
2. naprawa `/workers`
3. naprawa `/observability`
4. usunięcie błędnych hook imports i compile errors
5. ograniczenie fallbacków maskujących awarie

### Konkretne zadania

- przepiąć `/projects` na prawdziwy plane `/api/v1/projects`
- naprawić brakujące hook exports dla `/workers` i `/observability`
- dopiąć widoki do właściwych endpointów
- oznaczać wyraźnie fallback/offline state
- usunąć sytuacje, w których UI wygląda live mimo niesprawnego backendu

### Done

- `projects`, `workers`, `observability` renderują bez `500`
- operator widzi prawdziwe dane
- fallback nie udaje sukcesu

### Testy z Księgi 500

- `UI`
- `API`
- `OBS`
- część `SEC`

## 13. Workstream I: Operator Mobile Recovery

**Cel:** mobile ma być prawdziwą warstwą operatorską.

### Zakres

1. routing per operator
2. approval/reject -> unified governance
3. device binding, token validity, operator isolation
4. brak maskowania awarii

### Konkretne zadania

- dodać prawdziwe przypisanie ticketów do operatora albo jawny routing model
- dopiąć queue semantics do governance tickets
- przetestować device binding i token flow
- uszczelnić operator-mobile UI/web bridge

### Done

- queue nie pokazuje wszystkim wszystkiego bez rozróżnienia
- operator mobile rzeczywiście obsługuje swój scope
- mobile decyzje są widoczne w unified governance state

### Testy z Księgi 500

- `MOBILE`
- `SEC`
- `UI`

## 14. Workstream J: Runtime Topology + Execution Integrity

**Cel:** plan wykonania i realny runtime mają być zgodne.

### Zakres

1. worker pool reconciliation
2. runtime topology alignment
3. autonomy state alignment
4. execution continuity under failure

### Konkretne zadania

- dopiąć przeliczenie worker pool po zmianie execution plan
- zlikwidować niespójność local/VPS worker state
- dopiąć autonomy state do realnych decyzji runtime
- sprawdzić kosztowe i bezpieczeństwa gate’y przy zmianie topologii

### Done

- worker pool odpowiada execution planowi
- runtime nie odpala zabronionych workerów
- autonomy nie jest tylko opisem, ale wpływa na wykonanie

### Testy z Księgi 500

- `PLAN`
- `CHAOS`
- `SEC`
- `E2E`

## 15. Workstream K: Recovery, Chaos, Hardening

**Cel:** system ma nie tylko działać, ale przetrwać awarie i poprawnie się regenerować.

### Zakres

1. chaos scenarios
2. retry/recovery
3. incident + emergency gate
4. brak fake success przy degradacji

### Konkretne zadania

- uruchomić failure injection dla kluczowych plane’ów
- sprawdzić memory/funding/browser degradation
- upewnić się, że incydenty są widoczne operatorsko
- sprawdzić, czy recovery nie omija Human Gate

### Done

- awarie nie dają cichego sukcesu
- recovery ma audit trail
- emergency path działa

### Testy z Księgi 500

- `CHAOS`
- `SEC`
- `REPAIR`

## 16. Workstream L: Finalny dowód jakości

**Cel:** uczciwie udowodnić pełną funkcjonalność.

### Zakres

1. pełna matryca scenariuszy z Księgi 500
2. pełen browser walk
3. testy „jak człowiek”
4. module-by-module audit
5. końcowy verdict

### Konkretne zadania

- przejść pełną lub jawnie uzasadnioną podmacierz Księgi 500
- uruchomić S1-S8
- zbudować finalny evidence pack
- opisać remaining non-blocking issues, jeśli takie zostaną

### Done

- brak krytycznych open blockers
- evidence pack jest kompletny
- production-ready, jeśli zostanie ogłoszone, ma twardy dowód

## 17. Kolejność wykonania

### Etap 1: Core Recovery

Najpierw:
- Workstream A
- Workstream B
- Workstream C
- Workstream D

To jest etap „przywrócenia prawdy systemu”.

### Etap 2: Adaptive Recovery

Potem:
- Workstream E
- Workstream F

To jest etap „przywrócenia uczenia się i kompetencji systemu”.

### Etap 3: Domain + Operator Recovery

Potem:
- Workstream G
- Workstream H
- Workstream I

To jest etap „przywrócenia domen i sterowania operatorskiego”.

### Etap 4: Runtime Integrity

Potem:
- Workstream J
- Workstream K

To jest etap „przywrócenia niezawodności i zgodności wykonania”.

### Etap 5: Finalny dowód

Na końcu:
- Workstream L

## 18. Co wolno równoleglić, a czego nie wolno

### Nie wolno równoleglić na początku

- A z B
- B z C
- C z D

czyli:
- startup spine
- workspace
- governance
- council

To są zbyt centralne warstwy.

### Wolno równoleglić po ustabilizowaniu core

Po zakończeniu Etapu 1 można równoleglić:

- E z F
- G z H
- części I
- część J

### Najlepszy moment na podział między modele

Po zakończeniu:

- Workstream A
- Workstream B
- Workstream C
- Workstream D

czyli po przywróceniu rdzenia.

## 19. Rekomendacja wykonawcza

Jeśli pytanie brzmi: „jak doprowadzić system dalej do pełnej funkcjonalności?”,
to odpowiedź brzmi:

1. nie zaczynać od masowej równoległości,
2. najpierw przywrócić core truth planes,
3. potem wejść w adaptacyjne i domenowe workstreamy,
4. kończyć pełnym dowodem z Księgi 500.

Najbezpieczniejszy model pracy:

- najpierw jeden lider architektoniczny dla Etapu 1,
- potem rozdzielenie na:
  - core integrator,
  - adaptive executor,
  - domain/operator executor,
- na końcu integrator dowodowy i testowy.

## 20. Najbliższy praktyczny krok

Najbliższy sensowny krok po tym roadmapie to już nie „kolejna ogólna dyskusja”, tylko jedna z trzech rzeczy:

1. rozpisać dokładnie `Etap 1: Core Recovery` jako checklistę wykonawczą plik-po-pliku,
2. zaktualizować masterplan równoległy tak, aby startował dopiero po Etapie 1,
3. przygotować prompty wykonawcze dla modeli, ale dopiero dla etapów po ustabilizowaniu core.

## 21. Wniosek końcowy

Droga do pełnej funkcjonalności AEIS nie polega dziś na „dopisywaniu brakujących modułów”.

Polega na:

- zszyciu już istniejących warstw w jeden truth spine,
- doprowadzeniu governance, council, skills, memory, funding i mobile do wspólnej semantyki,
- naprawieniu operator surfaces tak, by pokazywały prawdę,
- i domknięciu tego pełnym dowodem z Księgi Testów 500.
