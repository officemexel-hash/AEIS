# CODEX AEIS Unified Repair Masterplan 2026-04-25

**Status:** draft 1.0  
**Cel:** zdefiniować jeden nadrzędny masterplan naprawczy AEIS po pełnym re-audycie, zanim system zostanie podzielony na strumienie równoległe lub prompty dla wielu modeli  
**Podstawa:**  
- [CODEX_AEIS_MASTERPLAN_NAPRAWCZY_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_MASTERPLAN_NAPRAWCZY_2026_04_25.md)
- [CODEX_AEIS_FULL_REAUDIT_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_FULL_REAUDIT_2026_04_25.md)
- [CODEX_AEIS_REPAIR_BACKLOG.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_REPAIR_BACKLOG.md)
- [CODEX_AEIS_PRODUCTION_READINESS_MAP.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_PRODUCTION_READINESS_MAP.md)
- [CODEX_AEIS_PARALLEL_MASTERPLAN_2026.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_PARALLEL_MASTERPLAN_2026.md)
- [CLAUDE_AEIS_PARALLEL_EXECUTION_PLAN.md](C:/Users/razor/Desktop/pipeline_glm/docs/claude_system_audit/parallel/CLAUDE_AEIS_PARALLEL_EXECUTION_PLAN.md)
- [CODEX_AEIS_TEST_BOOK_INTEGRATION_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_TEST_BOOK_INTEGRATION_2026_04_25.md)
- [CODEX_AEIS_FULL_FUNCTIONALITY_ROADMAP_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_FULL_FUNCTIONALITY_ROADMAP_2026_04_25.md)

## 1. Punkt wyjścia

Glowny dokument wykonawczy od tego momentu:

- [CODEX_AEIS_MASTERPLAN_NAPRAWCZY_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_MASTERPLAN_NAPRAWCZY_2026_04_25.md)

Ten dokument pozostaje planem architektonicznym i uzasadnieniem kolejnosci, ale checklista wykonawcza zyje w dokumencie powyzej.

Aktualny stan systemu po re-audycie:

`ADVANCED STAGING CANDIDATE / REQUIRES FIXES / NOT ACCEPTED AS PRODUCTION READY`

Najważniejsze fakty, które muszą sterować planem:

1. AEIS nie jest greenfieldem.
   Istnieją już żywe warstwy `workspace`, `projects`, `governance tickets`, `mobile bridge`, `funding`, `skills runtime`, `memory bootstrap`, `operator surfaces`.

2. Największy problem nie polega na braku modułów, tylko na pękniętych plane'ach prawdy.
   Najbardziej bolą:
   - `workspace Human Gate` broken route-to-service mapping
   - `workspace ideas` broken route-to-service mapping
   - `skills runtime` vs `skills registry`
   - `memory bootstrap/index` vs public memory API
   - `funding approval flow` vs unified governance tickets
   - `workspace council` vs real multi-model execution
   - `projects/workers/observability` UI vs real backend planes

3. Największy błąd wykonawczy na tym etapie to równoległe budowanie nowych subsystemów obok istniejących namespace'ów.

4. Najpierw trzeba przywrócić jeden spójny spine systemu, a dopiero potem opłaca się rozdzielać naprawy między wiele modeli.

## 2. Stan docelowy

Masterplan uznajemy za wykonany dopiero wtedy, gdy AEIS osiągnie łącznie:

1. Jeden dominujący spine:
   `workspace -> source of truth -> masterplan -> project_mode/runtime -> governance -> operator`

2. Jeden Human Gate truth plane:
   - wspólne approvale
   - wspólny audit trail
   - wspólne typy gate'ów
   - wspólna kolejka operatorska

3. Jeden council truth plane:
   - skład rady modeli
   - role modeli
   - rangi modeli
   - głosowanie
   - decyzje i log deliberacji

4. Jeden memory plane:
   - startup bootstrap
   - retrieval/search
   - evidence store
   - similarity/reuse
   - powiązanie z projektami i execution history

5. Jeden skills plane:
   - registry
   - runtime loader
   - execute path
   - przypisanie do workflow

6. Funding jako pełny obywatel wspólnego governance.

7. Operator Console i Operator Mobile jako prawdziwe, a nie tylko częściowo maskujące surface'y.

8. Potwierdzenie testami:
   - scenariusze `S1-S8`
   - testy browserowe
   - testy „jak człowiek”
   - końcowy re-audyt moduł po module

## 3. Reguły naprawy

1. Naprawiamy istniejące namespace'y.
   Nie budujemy nowego `skills`, nowego `memory`, nowego `funding`, nowego `governance` obok tego, co już żyje w repo.

2. Naprawiamy najpierw prawdę runtime, potem ergonomię UI.

3. Nie dotykamy planowania równoległego, dopóki nie zostanie zamrożony kontrakt integracyjny.

4. Nie włączamy pełnej pracy wielu modeli od pierwszej minuty.
   Najpierw musi powstać faza przygotowawcza z jedną odpowiedzialnością architektoniczną.

5. Każda faza kończy się bramką `go / no-go`.
   Bez zielonej bramki nie rozpoczyna się kolejna faza ani podział na więcej modeli.

6. Każda faza ma przypisaną podmacierz testów z Księgi Testów 500.
   Pełna księga jest obowiązkowym wejściem do Fazy 8.

## 4. Główne osie naprawy

Cały program naprawczy dzieli się logicznie na osiem osi:

1. `Runtime Spine Recovery`
2. `Workspace Recovery`
3. `Governance + Council Unification`
4. `Memory + Skills Unification`
5. `Funding Governance Convergence`
6. `Operator Surfaces Recovery`
7. `Runtime Topology + Orchestration Recovery`
8. `Proof, Hardening, Production Readiness`

Nie wszystkie te osie można naprawiać równolegle od początku.

## 5. Faza 0: Zamrożenie bazowe i kontrakt integracyjny

**Cel:** przygotować system do bezpiecznej naprawy.

**Zakres:**
- potwierdzić bieżący baseline z re-audytu
- zamrozić listę krytycznych blockerów
- ustalić shared files
- ustalić ownership map
- ustalić minimalny kontrakt integracyjny między:
  - governance
  - workspace
  - council
  - memory
  - skills
  - funding
  - mobile

**Krytyczne outputy:**
- jeden plik ownership map
- jeden plik integration contracts
- jedna lista shared files reserved-for-integrator
- jedna lista krytycznych endpointów referencyjnych do smoke probe

**Powiązane blokery:**
- przygotowanie pod wszystkie dalsze pozycje

**Bramka wyjścia:**
- wiadomo dokładnie, które pliki są wspólne
- wiadomo, które warstwy są źródłem prawdy
- wiadomo, czego nie wolno przebudowywać równolegle

**Uwagi wykonawcze:**
Ta faza powinna być robiona przez jednego lidera architektonicznego. Dzielenie pracy tutaj jest przedwczesne.

## 6. Faza 1: Runtime Spine Recovery

**Cel:** przywrócić integralność startu backendu i wyeliminować najniższy poziom driftu runtime.

**Zakres:**
- usunięcie startup dependency/register/manifest drift errors
- uporządkowanie bootstrappingu singletonów
- ustalenie, które registry i services powstają podczas startu, a które mają lazy init
- przywrócenie stabilnego mount order
- uporządkowanie health/readiness evidence

**Powiązane blokery:**
- `RB-P2-008`
- część `RB-014`
- część `RB-015`
- część `RB-007`

**Efekt oczekiwany:**
- backend startuje bez krytycznych `register error`
- health nie maskuje broken dependencies
- podstawowe plane'y systemowe mają jawny lifecycle

**Bramka wyjścia:**
- backend log po starcie nie zawiera krytycznych dependency/register drift errors
- smoke probe głównych rodzin endpointów przechodzi

**Czy wolno to dzielić?**
- nie na początku
- to nadal część krytycznego rdzenia i powinna być domknięta wąsko

## 7. Faza 2: Workspace Recovery

**Cel:** przywrócić działanie głównego wejścia operatorskiego AEIS.

**Zakres:**
- naprawa `workspace Human Gate` route/service mismatch
- naprawa `workspace ideas` route/service mismatch
- potwierdzenie `workspace sessions`
- naprawa `workspace council` tam, gdzie to jeszcze tylko shell
- potwierdzenie, że `workspace` nadal może prowadzić:
  - kickoff
  - source of truth
  - masterplan
  - launch

**Powiązane blokery:**
- `RB-P2-001`
- `RB-P2-002`
- część `RB-011`

**Efekt oczekiwany:**
- `/api/v1/workspace/humangate/sessions` nie crashuje
- `/api/v1/workspace/ideas` i `/stats` nie crashują
- workspace jest uczciwie podstawowym spine wejściowym

**Bramka wyjścia:**
- wszystkie krytyczne `workspace/*` API z probe przechodzą
- podstawowe flow workspace działa bez `500`

**Czy wolno to dzielić?**
- tylko częściowo
- backend workspace powinien mieć jednego właściciela
- UI wokół workspace można ruszać później

## 8. Faza 3: Governance + Council Unification

**Cel:** przywrócić jedną logikę decyzji człowieka i jedną logikę deliberacji modeli.

**Zakres Governance:**
- spiąć `workspace Human Gate` z głównym governance plane
- zlikwidować split między local gate/session gate/global ticket plane
- doprowadzić do jednego audit trail
- uporządkować typy gate'ów, escalation i routing

**Zakres Council:**
- uzgodnić model registry z workspace council config
- przywrócić realny, a nie shellowy council workflow
- określić role modeli, rangi, wagi głosów, log deliberacji
- zdefiniować punkt wejścia councilu do spine projektu i zmian

**Powiązane blokery:**
- `RB-001`
- `RB-004`
- `RB-011`
- `RB-012`
- `RB-013`
- część `RB-P2-007`

**Efekt oczekiwany:**
- jedna warstwa decyzji człowieka
- jedna warstwa deliberacji modeli
- workspace, projects, funding i mobile nie tworzą własnych approval universes

**Bramka wyjścia:**
- governance tickets są jedyną kanoniczną warstwą decyzji
- council nie jest tylko CRUD-em sesji, ale ma realną semantykę wykonawczą
- poziom autonomii ma realny wpływ na flow systemu

**Czy wolno to dzielić?**
- częściowo
- governance core powinien mieć jednego lidera
- model registry i council UI można wydzielić dopiero po zamrożeniu kontraktu

## 9. Faza 4: Memory + Skills Unification

**Cel:** usunąć split plane w dwóch kluczowych warstwach adaptacyjnych.

**Zakres Memory:**
- bootstrap global memory plane
- jeden startup lifecycle dla:
  - index
  - retrieval
  - evidence store
  - similarity hooks
- przywrócenie spójnego publicznego API memory

**Zakres Skills:**
- pojednanie registry i runtime
- runtime loading z prawdziwego źródła
- execute path dla skilli z registry
- telemetry dla usage i effectiveness

**Powiązane blokery:**
- `RB-P2-003`
- `RB-003`
- `RB-005`
- `RB-014`
- `RB-015`

**Efekt oczekiwany:**
- runtime skills są widoczne jako registered i executable
- memory search i evidence plane są wspólną warstwą, a nie rozłącznymi powierzchniami

**Bramka wyjścia:**
- `skills runtime` i `skills registry` pokazują ten sam truth plane
- publiczne memory endpoints działają spójnie
- spine projektu potrafi korzystać z memory i skills bez obejść

**Czy wolno to dzielić?**
- tak, ale dopiero po Faza 0-3
- to jest dobry kandydat na osobny średnio-ciężki strumień

## 10. Faza 5: Funding Governance Convergence

**Cel:** uczynić funding pełnym obywatelem AEIS, a nie subsystemem z własnym approval store.

**Zakres:**
- przepięcie funding approvals do unified governance tickets
- zachowanie istniejących żywych funding surfaces
- zachowanie browser automation, scanning, reporting i workflow grantowego
- spięcie funding z operator queue i audit trail

**Powiązane blokery:**
- `RB-P2-004`
- `RB-008`

**Efekt oczekiwany:**
- funding nie ma osobnego local approval universe
- finalne działania grantowe przechodzą przez ten sam plane co reszta AEIS

**Bramka wyjścia:**
- grant/funding actions tworzą governance tickets
- mobile/operator może obsłużyć funding approval bez specjalnego lokalnego mostu

**Czy wolno to dzielić?**
- tak, po zamrożeniu unified governance contract
- to jest dobry kandydat na lżejszy strumień

## 11. Faza 6: Operator Surfaces Recovery

**Cel:** doprowadzić UI operatorskie do zgodności z realnym backendem.

**Zakres:**
- naprawa `workers` page `500`
- naprawa `observability` page `500`
- przepi ęcie `/projects` UI na realny plane `/api/v1/projects`
- usunięcie surface drift pomiędzy UI a backendem
- uszczelnienie operator-mobile surface, żeby nie maskował błędów fallbackiem
- prawdziwy per-operator routing w mobile queue

**Powiązane blokery:**
- `RB-P2-005`
- `RB-P2-006`
- `RB-P2-007`
- `RB-006`
- `RB-007`
- `RB-009`

**Efekt oczekiwany:**
- operator widzi prawdziwy stan systemu
- UI nie wygląda „live”, gdy backend jest broken

**Bramka wyjścia:**
- wszystkie główne ekrany operatorskie renderują bez `500`
- projects pokazuje realne projekty
- workers/observability mają działające hooks
- mobile queue ma rzeczywiste routowanie, a nie globalny pending list

**Czy wolno to dzielić?**
- tak
- to jest dobry kandydat na osobny frontend/runtime strumień po stabilizacji backend contracts

## 12. Faza 7: Runtime Topology + Orchestration Recovery

**Cel:** sprawić, by wykonanie systemu odpowiadało zatwierdzonemu planowi.

**Zakres:**
- naprawa worker pool reconciliation
- dopięcie topology/runtime do execution plan
- powiązanie autonomy state z realnym spine
- weryfikacja execution continuity
- observability dla runtime topology

**Powiązane blokery:**
- `RB-002`
- część `RB-013`
- część `RB-P2-008`

**Efekt oczekiwany:**
- zatwierdzony plan i realna topologia wykonania nie rozjeżdżają się
- system nie uruchamia kosztownych workerów poza planem

**Bramka wyjścia:**
- execution plan, worker pool i runtime topology są zgodne
- smoke tests dla local/VPS topology przechodzą

**Czy wolno to dzielić?**
- ostrożnie
- to dotyka core runtime, więc lepiej utrzymać jednego właściciela technicznego

## 13. Faza 8: Proof, Hardening, Production Readiness

**Cel:** udowodnić, a nie tylko ogłosić gotowość systemu.

**Zakres:**
- pełny retest `S1-S8`
- browser walk wszystkich głównych surface'ów
- testy „jak człowiek”
- końcowy module-by-module audit
- końcowy production readiness verdict
- końcowa aktualizacja dokumentacji kanonicznej i backlogu

**Efekt oczekiwany:**
- można uczciwie powiedzieć, co jest production-ready, a co nadal nie

**Bramka końcowa:**
- brak krytycznych `500` i broken truth planes
- brak split approval plane
- brak split skills plane
- brak split memory plane
- brak krytycznych startup drift errors
- przejście testów operatorskich i browserowych

## 14. Zależności między fazami

Kolejność minimalna:

1. `Faza 0`
2. `Faza 1`
3. `Faza 2`
4. `Faza 3`
5. `Faza 4`
6. `Faza 5`
7. `Faza 6`
8. `Faza 7`
9. `Faza 8`

Dopuszczalne nakładanie po zielonych bramkach:

- `Faza 4` może częściowo iść równolegle z końcówką `Fazy 3`
- `Faza 5` może iść równolegle z `Fazą 6`, jeśli governance contract jest już zamrożony
- `Faza 6` może zacząć się po ustaleniu prawdziwych backend contracts
- `Faza 7` może częściowo zacząć się po ustabilizowaniu governance/runtime spine

Niedopuszczalne nakładanie:

- nie wolno zaczynać pełnego splitu na trzy modele przed zamknięciem `Fazy 0`
- nie wolno prowadzić funding unification przed zamrożeniem unified governance contract
- nie wolno robić finalnych testów produkcyjnych przed zakończeniem naprawy split planes

## 15. Ocena, czy w ogóle dzielić plan na wiele modeli

### Wariant A: 1 model główny + własne agenty

**Zalety:**
- najmniejsze ryzyko driftu
- najłatwiejsze pilnowanie jednego spine
- najlepsze dla faz 0-3

**Wady:**
- wolniej dla memory/skills/funding/surfaces
- większe ryzyko lokalnego przeciążenia jednego lidera

**Ocena:**
- dobry wariant dla przygotowania i dla najbardziej centralnych napraw
- zbyt wolny jako całościowy plan od początku do końca

### Wariant B: 2 modele

Podział logiczny:
- model 1: core/governance/workspace/runtime
- model 2: skills/memory/funding/mobile/operator

**Zalety:**
- prostsza koordynacja niż przy 3 modelach
- sensowny kompromis, jeśli nie chcemy pełnej orkiestracji równoległej

**Wady:**
- duży drugi strumień staje się przeładowany
- integracja nadal będzie ciężka

**Ocena:**
- realny wariant minimalny, jeśli nie chcemy Kimi

### Wariant C: 3 modele + końcowy integrator

Podział logiczny:
- `Claude Code`: najcięższy core, governance, workspace, council, runtime spine
- `Codex`: memory, skills, operator/mobile, projects/workers/observability UI binding
- `Kimi 2.6`: funding convergence, observability hygiene, lżejsze cleanupy i surface gap-fill
- `Claude Code integrator`: końcowe spięcie, testy S1-S8, browser walk, finalny audit

**Zalety:**
- najlepszy throughput po ustabilizowaniu kontraktów
- dobry balans ciężaru
- Kimi dostaje proceduralne i odcięte rzeczy

**Wady:**
- wymaga twardego ownership i shared file discipline
- bez Fazy 0 i bramek bardzo łatwo o regresję

**Ocena:**
- to jest wariant docelowo najlepszy
- ale nie od pierwszego dnia

## 16. Rekomendacja wykonawcza

Rekomenduję plan hybrydowy:

### Etap A: bez dzielenia albo z jednym liderem

Zakres:
- `Faza 0`
- `Faza 1`
- `Faza 2`
- rdzeń `Fazy 3`

To powinno być prowadzone przez jednego głównego modela/lidera architektonicznego.

### Etap B: kontrolowany split

Dopiero po zielonej bramce po `Fazie 3` rekomenduję wejście w wariant:

`3 modele wykonawcze + 1 końcowy integrator`

Bo dopiero wtedy istnieje szansa, że:
- governance contract jest zamrożony
- workspace contract jest stabilny
- council contract jest stabilny
- backend truth planes przestają się ruszać pod nogami

## 17. Zalecany docelowy podział, jeśli uruchomimy wiele modeli

### Model 1: Claude Code

**Ciężar:** najwyższy  
**Obszary:**
- `Faza 0`
- `Faza 1`
- `Faza 2`
- `Faza 3`
- rdzeń `Fazy 7`

To jest właściciel:
- spine
- governance
- council
- workspace
- runtime truth

### Model 2: Codex

**Ciężar:** średni-wysoki  
**Obszary:**
- `Faza 4`
- większa część `Fazy 6`

To jest właściciel:
- skills
- memory
- projects UI rebinding
- workers/observability UI naprawy
- operator-mobile bridge i surface fixes

### Model 3: Kimi 2.6

**Ciężar:** lżejszy  
**Obszary:**
- `Faza 5`
- lżejsze części `Fazy 6`
- observability hygiene i cleanup

To jest właściciel:
- funding governance convergence
- lżejsze operator/funding surface gaps
- porządkowanie telemetry/runtime hygiene

### Model 4: końcowy integrator

**Rola:** integracja, testy, browser walk, finalny audit

Zakres:
- `Faza 8`
- końcowe scalanie shared files
- pełny retest systemu

## 18. Szacowanie skali podziału

### Najbardziej uczciwa rekomendacja na teraz

Na obecnym stanie repo nie rekomenduję od razu dzielić planu na cztery równoległe prompty.

Najpierw:
- 1 model główny
- ewentualnie jego własne agenty pomocnicze

Po przejściu `Fazy 3`:
- 3 modele wykonawcze + 1 integrator

### Kiedy nie dzielić w ogóle

Nie warto dzielić planu, jeśli:
- nie zostanie zamrożony integration contract
- nie zostaną naprawione `workspace Human Gate` i `workspace ideas`
- governance plane nadal będzie się zmieniał
- shared files nadal będą „czyjeś i niczyje”

### Kiedy warto dzielić

Warto dzielić, gdy:
- backend startuje czysto
- workspace spine jest naprawiony
- governance/council contracts są stabilne
- ownership map jest twardo ustalona

## 19. Szacowanie kalendarzowe

### Wariant bez podziału na wiele modeli

- `Faza 0-3`: 2-4 dni robocze
- `Faza 4-8`: 4-7 dni roboczych
- razem: około `6-11 dni roboczych`

### Wariant rekomendowany: lider + późniejszy split 3+1

- `Etap A` (`Faza 0-3`): `2-3 dni`
- `Etap B` (`Faza 4-7`) w trzech strumieniach: `3-5 dni`
- `Etap C` (`Faza 8`) integrator: `2-3 dni`
- razem: około `7-10 dni roboczych`

To jest obecnie najbardziej realistyczny wariant bez sztucznego optymizmu.

## 20. Wniosek końcowy

Najpierw powinien istnieć jeden duży masterplan naprawczy, bo dziś największym ryzykiem nie jest brak pomysłów, tylko chaotyczna równoległość na niestabilnych kontraktach.

Moja rekomendacja:

1. Przyjąć ten dokument jako plan nadrzędny.
2. Nie dzielić prac od razu na wszystkie modele.
3. Najpierw zamknąć `Fazę 0-3` pod jednym liderem architektonicznym.
4. Dopiero potem wejść w kontrolowany split:
   - Claude Code
   - Codex
   - Kimi 2.6
   - końcowy integrator

To jest najbezpieczniejsza droga od obecnego AEIS do uczciwego `production ready`.
