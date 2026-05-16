# CODEX AEIS MASTERPLAN NAPRAWCZY 2026-04-25

**Status:** draft 1.0  
**Rola dokumentu:** nadrzedny dokument wykonawczy do doprowadzenia AEIS od stanu po re-audycie do pelnej funkcjonalnosci i uczciwego `production ready`  
**Ten dokument ma pierwszenstwo nad rozproszonymi notatkami planistycznymi.**  

## 0. Jak uzywac tego dokumentu

To jest jeden glowny dokument operacyjny. Ma sluzyc jako:

- plan naprawczy,
- roadmapa techniczna,
- lista checkpointow `go / no-go`,
- checklista wykonawcza,
- checklista walidacyjna,
- punkt odniesienia do podzialu pracy miedzy modele dopiero wtedy, gdy rdzen systemu bedzie ustabilizowany.

Zasada pracy:

1. Nie przeskakujemy checkpointow.
2. Nie odpalamy szerokiej rownoleglosci przed checkpointem `CP4`.
3. Nie oglaszamy `production ready` bez przejscia przez checkpoint `CP12`.
4. Dowod wygrywa z interpretacja:
   `kod -> runtime -> API -> UI -> testy -> dokumentacja -> audit`.

## 1. Zrodla prawdy

Ten dokument opiera sie na:

- [CODEX_AEIS_FULL_REAUDIT_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_FULL_REAUDIT_2026_04_25.md)
- [CODEX_AEIS_AUDIT500_REVIEW_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_AUDIT500_REVIEW_2026_04_25.md)
- [CODEX_AEIS_TEST_BOOK_INTEGRATION_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_TEST_BOOK_INTEGRATION_2026_04_25.md)
- [CODEX_AEIS_REPAIR_BACKLOG.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_REPAIR_BACKLOG.md)
- [CODEX_AEIS_UNIFIED_REPAIR_MASTERPLAN_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_UNIFIED_REPAIR_MASTERPLAN_2026_04_25.md)
- [CODEX_AEIS_FULL_FUNCTIONALITY_ROADMAP_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_FULL_FUNCTIONALITY_ROADMAP_2026_04_25.md)
- [AEIS_KSIEGA_TESTOW_500_SCENARIUSZY.pdf](C:/Users/razor/Downloads/AEIS_KSIEGA_TESTOW_500_SCENARIUSZY.pdf)

## 2. Stan wyjsciowy

Aktualny uczciwy status systemu:

`ADVANCED STAGING CANDIDATE / REQUIRES FIXES / NOT ACCEPTED AS PRODUCTION READY`

Najwazniejsze fakty:

- AEIS nie jest greenfieldem.
- Zyja juz warstwy `workspace`, `projects`, `governance tickets`, `mobile bridge`, `funding`, `idea_vault`, `council_hybrid`, `skills`, `memory`, `operator surfaces`.
- Najwiekszym problemem nie jest brak modulow, tylko pekniete planes prawdy i niespojna integracja runtime.
- `.audit_500` potwierdza realny hardening w wielu miejscach, ale nie uniewaznia glownych blockerow rdzenia.

## 3. Co juz jest zaawansowane i ma byc wykorzystane

Punkty ponizej traktujemy jako rzeczy **istniejace i warte wykorzystania**, nie do przepisywania od zera.

### 3.1. Idea plane

- [x] rozszerzone lifecycle statuses w `idea_vault`
- [x] soft delete
- [x] archive / unarchive
- [x] stale detection
- [x] append-only lifecycle log
- [x] czesciowy Human Gate handoff na poziomie samego `idea_vault`

### 3.2. Council plane

- [x] `VALID_ROLES`
- [x] `VALID_RANKS`
- [x] weighted consensus
- [x] critic signature
- [x] sentinel evaluation
- [x] consolidate-with-signatures

### 3.3. Security hardening

- [x] poprawki `audit_sink`
- [x] poprawki `auth_provider`
- [x] poprawki `execution_guard`
- [x] poprawki `secret_provider`
- [x] poprawki `phantom_wrapper`
- [x] poprawki `security_audit`
- [x] poprawki `security_profiles`

### 3.4. Smoke / deploy hardening

- [x] poprawiony `healthcheck` path
- [x] poprawiony `Dockerfile` path w compose

## 4. Co nadal blokuje pelna funkcjonalnosc

### 4.1. Blockery rdzenia

- [ ] `workspace Human Gate` route / service mismatch
- [ ] `workspace ideas` route / service mismatch
- [ ] startup dependency / register / manifest drift
- [ ] health bootstrap semantics nadal za slabe

### 4.2. Blockery governance

- [ ] Human Gate split brain
- [ ] council split z model registry
- [ ] autonomia oderwana od runtime spine

### 4.3. Blockery warstw adaptacyjnych

- [ ] `skills runtime` vs `skills registry`
- [ ] `memory bootstrap/index` vs `memory API` vs project runtime

### 4.4. Blockery domenowe

- [ ] funding approvals nie sa jeszcze unified governance tickets
- [ ] mobile queue nie ma prawdziwego routing per operator

### 4.5. Blockery operatora

- [ ] `/projects` podpięte pod zly data plane
- [ ] `/workers` ma compile/runtime `500`
- [ ] `/observability` ma compile/runtime `500`
- [ ] operator-mobile surface potrafi maskowac awarie fallbackiem

### 4.6. Blockery runtime

- [ ] worker pool reconciliation
- [ ] topology drift
- [ ] brak pelnego dowodu execution integrity

## 5. Stan docelowy

AEIS uznajemy za funkcjonalnie pelny dopiero wtedy, gdy wszystkie punkty ponizej sa odhaczone.

### 5.1. Core spine

- [ ] `Idea -> Source of Truth -> Masterplan -> Execution` dziala jako jeden spojny flow
- [ ] `workspace` jest prawdziwym spine wejsciowym AEIS
- [ ] `project_mode` i runtime sa podlaczone do tego samego planu i governance

### 5.2. Human Gate

- [ ] istnieje jeden approval plane
- [ ] istnieje jeden audit trail decyzji
- [ ] istnieje jedna kolejka operatorska
- [ ] funding, mobile, workspace i final actions korzystaja z tego samego truth plane

### 5.3. Council

- [ ] sklad rady modeli ma jeden truth plane
- [ ] role, rangi i wagi glosow sa realnie egzekwowane
- [ ] critic signature ma realny skutek
- [ ] sentinel blocks maja realny skutek
- [ ] council wplywa na plan i zmiany planu

### 5.4. Skills

- [ ] registry i runtime to jeden plane albo jawnie zmapowany jeden plane logiczny
- [ ] execute dziala dla rzeczywistych skilli
- [ ] usage i success rate sa prawdziwe

### 5.5. Memory

- [ ] istnieje startup-bound memory plane
- [ ] search / retrieval / evidence / similarity dzialaja jako jedna warstwa
- [ ] memory ma realny wplyw na plan

### 5.6. Funding

- [ ] funding dziala end-to-end
- [ ] finalne funding approvals sa unified governance tickets
- [ ] browser / reporting / submit maja wspolny evidence trail

### 5.7. Operator

- [ ] `projects` pokazuje realne dane z `/api/v1/projects`
- [ ] `workers` dziala bez `500`
- [ ] `observability` dziala bez `500`
- [ ] fallback nie udaje sukcesu
- [ ] operator rozumie status, ryzyko i nastepny krok

### 5.8. Mobile

- [ ] queue ma routing per operator
- [ ] approval / reject aktualizuje unified governance state
- [ ] device binding i token flow sa prawdziwe

### 5.9. Runtime

- [ ] execution plan = runtime topology
- [ ] worker pool = zatwierdzony plan
- [ ] autonomia ma realny wplyw na wykonanie

### 5.10. Dowod jakosci

- [ ] przejscie `S1-S8`
- [ ] przejscie wymaganej macierzy z Ksiegi Testow 500
- [ ] browser walk i testy "jak czlowiek"
- [ ] koncowy module-by-module audit

## 6. Reguly bezwzgledne

- [ ] Nie budowac nowych subsystemow obok `workspace`, `governance`, `skills`, `memory`, `funding`.
- [ ] Nie naprawiac przez ukryty mock, fallback, usuniecie testu ani drugi namespace.
- [ ] Nie oglaszac sukcesu, jesli runtime probe temu przeczy.
- [ ] Nie zaczynac szerokiej pracy wielu modeli przed checkpointem `CP4`.
- [ ] Kazda faza musi miec evidence pack.
- [ ] Kazdy wazniejszy fix przechodzi przez `R0-R9` z Ksiegi 500.

## 7. Checkpointy glówne

To sa glówne checkpointy programu naprawczego.

- [ ] `CP0` Kontrakt integracyjny i ownership freeze
- [ ] `CP1` Clean boot i stabilny startup spine
- [ ] `CP2` Workspace truth restored
- [ ] `CP3` Unified Human Gate
- [ ] `CP4` Council + autonomy semantics real
- [ ] `CP5` Skills unified
- [ ] `CP6` Memory unified
- [ ] `CP7` Funding governance convergence
- [ ] `CP8` Operator Console truth restored
- [ ] `CP9` Operator Mobile truth restored
- [ ] `CP10` Runtime topology integrity proven
- [ ] `CP11` Security / observability / chaos hardening closed
- [ ] `CP12` Production readiness proven by evidence

## 8. Faza 0 - Contract Freeze i przygotowanie programu

**Cel:** zablokowac chaos i ustalic jedno zrodlo sterowania naprawa.

### Wyjscie z fazy

- [ ] wiadomo, ktore pliki sa shared
- [ ] wiadomo, kto jest wlascicielem core
- [ ] wiadomo, czego nie wolno ruszac rownolegle
- [ ] wiadomo, ktore endpointy sa smoke reference set

### Checklista

- [ ] potwierdzic aktualny baseline re-audytu
- [ ] potwierdzic aktualny baseline `.audit_500`
- [ ] ustalic `ownership map`
- [ ] ustalic `integration contracts`
- [ ] ustalic `reserved shared files`
- [ ] ustalic `smoke probe set`
- [ ] ustalic `evidence pack template`
- [ ] ustalic `go/no-go rules`

### Evidence

- [ ] jeden plik ownership
- [ ] jeden plik contracts
- [ ] jedna checklista smoke

### Testy z Ksiegi 500

- [ ] zasada prawdy `kod -> runtime -> API -> UI -> testy -> dokumentacja`
- [ ] `C1-C10`
- [ ] `A0-A5`
- [ ] `R0-R9`

## 9. Faza 1 - Runtime Spine Recovery

**Checkpoint:** `CP1`

**Cel:** przywrocic czysty, przewidywalny start backendu i jawny lifecycle centralnych plane'ow.

### Kluczowe cele techniczne

- [ ] usunac startup dependency/register drift errors
- [ ] uporzadkowac bootstrap order
- [ ] rozdzielic real bootstrap od lazy-init
- [ ] upewnic sie, ze health nie maskuje broken dependencies

### Lista napraw

- [ ] przejrzec `app.py` i startup registration order
- [ ] zidentyfikowac wszystkie krytyczne `register error` z logu
- [ ] naprawic `core.event_bus` registration drift
- [ ] naprawic `governance.tickets` dependency order
- [ ] naprawic `funding_autopilot.store` dependency order
- [ ] naprawic `core.decision_gate_engine` dependency/order drift
- [ ] naprawic bledne manifest stage values typu `beta` tam, gdzie lamia parser
- [ ] jawnie bootstrapowac centralne singletony
- [ ] ustalic, czy `memory` i `skills` startuja twardo czy lazy, i opisac to w kodzie
- [ ] sprawdzic, czy `modules` w health odzwierciedlaja realny bootstrap

### Warunki wyjscia

- [ ] backend log bez krytycznych startup errors
- [ ] `/health` jest uczciwy
- [ ] smoke probe glownych rodzin endpointow nie pokazuje nowych regressions

### Testy z Ksiegi 500

- [ ] `SMOKE`
- [ ] `CODE`
- [ ] fragment `API`

## 10. Faza 2 - Workspace Spine Recovery

**Checkpoint:** `CP2`

**Cel:** przywrocic workspace jako prawdziwe wejscie operatorskie AEIS.

### Kluczowe cele techniczne

- [ ] naprawic `workspace Human Gate`
- [ ] naprawic `workspace ideas`
- [ ] potwierdzic `workspace sessions`
- [ ] potwierdzic `workspace council`

### Lista napraw

- [ ] przeanalizowac `ai_workspace_routes.py`
- [ ] usunac wywolania nieistniejacych metod `HumanGate`
- [ ] zdecydowac, czy:
  - [ ] route layer ma byc przepiety na realny governance service
  - [ ] czy `HumanGate` ma dostac session facade
- [ ] usunac wywolania nieistniejacych metod `IdeaVault`
- [ ] uzgodnic `list_ideas` signature z route params
- [ ] uzgodnic `stats` API dla ideas
- [ ] upewnic sie, ze workspace idea flow nie obchodzi glownego idea plane
- [ ] potwierdzic brak `500` na:
  - [ ] `/api/v1/workspace/humangate/sessions`
  - [ ] `/api/v1/workspace/ideas`
  - [ ] `/api/v1/workspace/ideas/stats`
  - [ ] tworzeniu workspace idea
  - [ ] odczycie workspace sessions

### Warunki wyjscia

- [ ] wszystkie krytyczne `workspace/*` probe'y przechodza
- [ ] workspace moze uczciwie obsluzyc pomysl, sesje i podstawowe flow

### Testy z Ksiegi 500

- [ ] `SMOKE`
- [ ] `API`
- [ ] `IDEA`
- [ ] fragment `UI`

## 11. Faza 3 - Unified Human Gate

**Checkpoint:** `CP3`

**Cel:** zrobic z Human Gate jedyny plane decyzji czlowieka.

### Kluczowe cele techniczne

- [ ] zlikwidowac split workspace / governance / funding / mobile
- [ ] zrobic jeden truth plane decyzji
- [ ] zrobic jeden audit trail decyzji
- [ ] zrobic jedna operator queue semantics

### Lista napraw

- [ ] zdefiniowac jeden kanoniczny ticket / request model
- [ ] zmapowac workspace approvals na governance tickets
- [ ] zmapowac idea approvals na governance tickets albo jawny wspolny service
- [ ] zmapowac final action gates na ten sam plane
- [ ] zmapowac mobile decision flow na ten sam plane
- [ ] zmapowac funding approval flow na ten sam plane albo przygotowac ten hook do Fazy 7
- [ ] ustalic typy gate'ow:
  - [ ] blocking
  - [ ] non-blocking
  - [ ] batch
  - [ ] emergency
  - [ ] financial
  - [ ] legal
  - [ ] production
  - [ ] security
  - [ ] external
  - [ ] final
- [ ] upewnic sie, ze operator ma jedna kolejke decyzji

### Warunki wyjscia

- [ ] nie istnieje drugi approval universe dla core flow
- [ ] wszystkie wazne decyzje ida do wspolnego audit trail
- [ ] workspace i governance nie zyja osobno

### Testy z Ksiegi 500

- [ ] `IDEA`
- [ ] `PLAN`
- [ ] `MOBILE`
- [ ] `FUND`
- [ ] fragment `SEC`

## 12. Faza 4 - Council i autonomia

**Checkpoint:** `CP4`

**Cel:** dopiac council do realnego spine projektu i realnej autonomii systemu.

### Kluczowe cele techniczne

- [ ] jeden truth plane dla skladu rady modeli
- [ ] realne znaczenie critic signature
- [ ] realne znaczenie weights i sentinels
- [ ] realny zwiazek councilu z planem i zmianami
- [ ] autonomia ma wplyw na flow

### Lista napraw

- [ ] uzgodnic `workspace council settings` z `model registry`
- [ ] ustalic, skad bierze sie sklad rady modeli
- [ ] dopiac role i rangi do model registry albo odwrotnie
- [ ] podlaczyc council do source-of-truth i masterplan changes
- [ ] podlaczyc council do change proposals
- [ ] podlaczyc sentinels do kosztow i security gates
- [ ] okreslic tie semantics i eskalacje do Human Gate
- [ ] podlaczyc autonomie do runtime spine
- [ ] upewnic sie, ze `observe` nie jest jedynym realnym stanem autonomii

### Warunki wyjscia

- [ ] council nie jest tylko CRUD-em sesji
- [ ] council ma realny skutek wykonawczy
- [ ] autonomia wpływa na zachowanie systemu

### Testy z Ksiegi 500

- [ ] `COUNCIL`
- [ ] `PLAN`
- [ ] fragment `SEC`

## 13. Faza 5 - Skills Plane Unification

**Checkpoint:** `CP5`

**Cel:** sprawic, by skille byly zywe end-to-end.

### Kluczowe cele techniczne

- [ ] registry i runtime nie sa osobnymi swiatami
- [ ] seed i registry skills sa wykonalne
- [ ] usage / success telemetry jest prawdziwa

### Lista napraw

- [ ] zdefiniowac jedno zrodlo prawdy dla skill manifests
- [ ] zdefiniowac bootstrap runtime loader
- [ ] dopiac registry entry -> runtime executable mapping
- [ ] naprawic `execute` dla seed skill i registry skill
- [ ] zapewnic telemetry:
  - [ ] total executions
  - [ ] loaded skills
  - [ ] usage history
  - [ ] success rate
- [ ] upewnic sie, ze operator surface `/skills` pokazuje prawde runtime, nie tylko storage

### Warunki wyjscia

- [ ] `loaded_skills` zgadza sie z runtime logic
- [ ] `total_skills` jest spójne logicznie z runtime
- [ ] execute przechodzi dla testowych skilli

### Testy z Ksiegi 500

- [ ] `SKILL`
- [ ] fragment `PLAN`
- [ ] fragment `REPAIR`

## 14. Faza 6 - Memory Plane Unification

**Checkpoint:** `CP6`

**Cel:** sprawic, by memory byla jedna warstwa uczenia sie systemu.

### Kluczowe cele techniczne

- [ ] startup-bound memory plane
- [ ] retrieval / search / evidence / similarity jako jedna semantyka
- [ ] brak split global memory vs project memory bez jawnego modelu

### Lista napraw

- [ ] okreslic kanoniczny memory store
- [ ] okreslic relacje global vs per-project
- [ ] naprawic publiczne API:
  - [ ] search
  - [ ] evidence stats
  - [ ] evidence store access
  - [ ] self-model jesli ma byc publiczny
- [ ] uniknac shadowingu tras typu `/evidence/stats`
- [ ] dopiac similarity do planowania
- [ ] dopiac evidence do repair loop
- [ ] potwierdzic trwałość po restarcie

### Warunki wyjscia

- [ ] memory search dziala
- [ ] evidence stats dziala
- [ ] similarity ma realny wplyw na plan
- [ ] restart nie niszczy wspolnej pamieci wbrew kanonowi

### Testy z Ksiegi 500

- [ ] `MEM`
- [ ] fragment `PLAN`
- [ ] fragment `REPAIR`
- [ ] fragment `E2E`

## 15. Faza 7 - Funding Governance Convergence

**Checkpoint:** `CP7`

**Cel:** zrobic z fundingu pelnego obywatela AEIS.

### Kluczowe cele techniczne

- [ ] funding nie ma swojego osobnego approval universe
- [ ] submit, reporting i browser automation wchodza do wspolnego governance plane
- [ ] domain metadata pozostaje zachowana

### Lista napraw

- [ ] przeanalizowac lokalny funding approval store
- [ ] przepiac funding final actions do governance tickets
- [ ] dopiac `governance_bridge` do realnych call sites
- [ ] upewnic sie, ze scanning / drafting / browser / reporting sa widoczne w audit trail
- [ ] upewnic sie, ze mobile/operator widzi funding approvals jako czesc jednego systemu

### Warunki wyjscia

- [ ] funding final submit bez approval jest blokowany we wspolnym plane
- [ ] funding approval jest widoczny w governance queue
- [ ] funding nie robi lokalnego "truth plane"

### Testy z Ksiegi 500

- [ ] `FUND`
- [ ] `MOBILE`
- [ ] `SEC`
- [ ] fragment `E2E`

## 16. Faza 8 - Operator Console Recovery

**Checkpoint:** `CP8`

**Cel:** sprawic, by operator widzial prawde systemu.

### Kluczowe cele techniczne

- [ ] `/projects` pokazuje realny project plane
- [ ] `/workers` dziala
- [ ] `/observability` dziala
- [ ] fallback nie udaje sukcesu

### Lista napraw

- [ ] przepiac `/projects` na `/api/v1/projects`
- [ ] usunac zaleznosc od falszywego `plans/workflows/jobs` jako glownego plane
- [ ] naprawic brakujace hook exports dla `/workers`
- [ ] naprawic brakujace hook exports dla `/observability`
- [ ] dopiac UI do realnych backend endpoints
- [ ] oznaczac offline/fallback w sposob uczciwy i jawny
- [ ] sprawdzic wszystkie glowne operator pages:
  - [ ] overview
  - [ ] workspace
  - [ ] projects
  - [ ] governance
  - [ ] funding
  - [ ] skills
  - [ ] operator-mobile
  - [ ] workers
  - [ ] observability

### Warunki wyjscia

- [ ] brak `500` na glownych ekranach operatora
- [ ] operator widzi prawdziwe dane
- [ ] fallback jest jawny i nie myli z live

### Testy z Ksiegi 500

- [ ] `UI`
- [ ] `API`
- [ ] `OBS`
- [ ] fragment `SEC`

## 17. Faza 9 - Operator Mobile Recovery

**Checkpoint:** `CP9`

**Cel:** sprawic, by mobile byl prawdziwa warstwa operatorska.

### Kluczowe cele techniczne

- [ ] routing per operator
- [ ] unified governance state updates
- [ ] real device binding and token semantics

### Lista napraw

- [ ] okreslic model przypisania ticketow do operatora
- [ ] dodac prawdziwy per-operator routing
- [ ] upewnic sie, ze `decision -> governance ticket state`
- [ ] sprawdzic binding urzadzenia
- [ ] sprawdzic token / HMAC / auth flow
- [ ] uszczelnic mobile UI przed falszywym live fallback

### Warunki wyjscia

- [ ] mobile queue nie pokazuje po prostu wszystkich pending
- [ ] operator mobile zarzadza swoim sciem ticketow
- [ ] decyzje z mobile sa widoczne w unified governance trail

### Testy z Ksiegi 500

- [ ] `MOBILE`
- [ ] `SEC`
- [ ] `UI`

## 18. Faza 10 - Runtime Topology + Execution Integrity

**Checkpoint:** `CP10`

**Cel:** dopiac zatwierdzony plan do rzeczywistego runtime.

### Kluczowe cele techniczne

- [ ] worker pool = execution plan
- [ ] topology nie dryfuje po starcie
- [ ] autonomia ma realne znaczenie wykonawcze

### Lista napraw

- [ ] naprawic worker pool reconciliation
- [ ] dopiac execution plan do realnego runtime topology state
- [ ] naprawic przypadek `vps_workers = 0` a runtime nadal nosi workerow
- [ ] dopiac autonomy state do rzeczywistego wykonania
- [ ] dopiac koszty i governance do zmian topologii

### Warunki wyjscia

- [ ] runtime topology nie przeczy zatwierdzonemu planowi
- [ ] worker pool jest zgodny z execution planem
- [ ] autonomia i governance steruja runtime

### Testy z Ksiegi 500

- [ ] `PLAN`
- [ ] `CHAOS`
- [ ] fragment `SEC`
- [ ] fragment `E2E`

## 19. Faza 11 - Security / Observability / Chaos Hardening

**Checkpoint:** `CP11`

**Cel:** domknac stabilnosc, odpornosc i uczciwa obserwowalnosc systemu.

### Kluczowe cele techniczne

- [ ] brak cichego sukcesu przy degradacji
- [ ] recovery ma audit trail
- [ ] observability jest realna
- [ ] security plane jest zintegrowany z reszta, nie tylko "zalatany"

### Lista napraw

- [ ] utrzymac i zweryfikowac security hardening z `.audit_500`
- [ ] dopiac metrics i traces do operator truth
- [ ] zweryfikowac `/metrics`
- [ ] zweryfikowac incident / emergency paths
- [ ] uruchomic chaos scenarios dla:
  - [ ] memory
  - [ ] funding
  - [ ] browser
  - [ ] execution workers
  - [ ] governance interruption

### Warunki wyjscia

- [ ] awaria nie daje fake success
- [ ] emergency path dziala
- [ ] observability pokazuje prawde o systemie

### Testy z Ksiegi 500

- [ ] `SEC`
- [ ] `CHAOS`
- [ ] `REPAIR`

## 20. Faza 12 - Finalny dowod production readiness

**Checkpoint:** `CP12`

**Cel:** udowodnic, a nie zadeklarowac, ze AEIS jest gotowy.

### Kluczowe cele techniczne

- [ ] przejsc `S1-S8`
- [ ] przejsc wymagana macierz z Ksiegi 500
- [ ] przejsc browser walk i testy "jak czlowiek"
- [ ] przejsc koncowy audit modul po module

### Lista napraw i dowodow

- [ ] uruchomic finalny smoke
- [ ] uruchomic finalny code sweep
- [ ] uruchomic finalne API probes
- [ ] uruchomic finalny UI walk
- [ ] uruchomic finalne `IDEA`
- [ ] uruchomic finalne `COUNCIL`
- [ ] uruchomic finalne `PLAN`
- [ ] uruchomic finalne `SKILL`
- [ ] uruchomic finalne `MEM`
- [ ] uruchomic finalne `MOBILE`
- [ ] uruchomic finalne `FUND`
- [ ] uruchomic finalne `SEC`
- [ ] uruchomic finalne `CHAOS`
- [ ] uruchomic finalne `REPAIR`
- [ ] uruchomic finalne `E2E`
- [ ] zbudowac evidence pack
- [ ] zbudowac finalny report gotowosci

### Warunki wyjscia

- [ ] brak krytycznych open blockers
- [ ] brak split truth plane dla core
- [ ] brak `500` na krytycznych flow
- [ ] operator i mobile widza ten sam stan
- [ ] funding jest unified
- [ ] skills i memory sa unified
- [ ] runtime topology jest zgodna z planem
- [ ] istnieje twardy dowod produkcyjnej gotowosci

## 21. Mapa zaleznosci

### Tego nie wolno przeskoczyc

- [ ] `CP0` przed wszystkim
- [ ] `CP1` przed `CP2`
- [ ] `CP2` przed `CP3`
- [ ] `CP3` przed `CP4`
- [ ] `CP4` przed pelna rownolegloscia

### Tego nie wolno robic za wczesnie

- [ ] nie dzielic core na wiele modeli przed `CP4`
- [ ] nie robic funding convergence przed ustabilizowaniem unified governance
- [ ] nie robic mobile routing finalnie przed ustaleniem operator ticket semantics
- [ ] nie oglaszac gotowosci skills/memory bez swiezego runtime proof

### Co wolno zrownoleglac po `CP4`

- [ ] `Skills`
- [ ] `Memory`
- [ ] `Funding`
- [ ] `Operator Console`
- [ ] `Operator Mobile`
- [ ] czesc `Runtime topology`

## 22. Macierz testow z Ksiegi 500 na checkpointy

### `CP1`

- [ ] `SMOKE`
- [ ] `CODE`
- [ ] wybrane `API`

### `CP2`

- [ ] `SMOKE`
- [ ] `API`
- [ ] `IDEA`
- [ ] wybrane `UI`

### `CP3`

- [ ] `IDEA`
- [ ] `PLAN`
- [ ] `MOBILE`
- [ ] `FUND`

### `CP4`

- [ ] `COUNCIL`
- [ ] `PLAN`
- [ ] wybrane `SEC`

### `CP5`

- [ ] `SKILL`

### `CP6`

- [ ] `MEM`

### `CP7`

- [ ] `FUND`
- [ ] `SEC`

### `CP8`

- [ ] `UI`
- [ ] `OBS`

### `CP9`

- [ ] `MOBILE`
- [ ] `SEC`

### `CP10`

- [ ] `PLAN`
- [ ] `CHAOS`

### `CP11`

- [ ] `SEC`
- [ ] `CHAOS`
- [ ] `REPAIR`

### `CP12`

- [ ] pelna albo jawnie uzasadniona podmacierz 500 scenariuszy
- [ ] `S1-S8`
- [ ] browser walk
- [ ] testy "jak czlowiek"

## 23. Definicja Done dla calego programu

Program jest zakonczony dopiero gdy:

- [ ] `CP0-CP12` sa odhaczone
- [ ] wszystkie krytyczne truth planes sa pojednane
- [ ] operator ma jedna prawde systemu
- [ ] mobile ma jedna prawde systemu
- [ ] funding ma jedna prawde governance
- [ ] memory i skills sa zintegrowane z runtime
- [ ] runtime topology nie dryfuje
- [ ] produkcyjna gotowosc ma evidence pack

## 24. Punkt, w ktorym wolno dzielic prace na wiele modeli

Do checkpointu `CP4` rekomendacja jest jedna:

- [ ] jeden lider architektoniczny
- [ ] ewentualnie jego wlasne agenty pomocnicze

Po checkpointcie `CP4` mozna uruchomic:

- [ ] model core / governance
- [ ] model adaptive / skills / memory
- [ ] model domain / funding / operator surfaces
- [ ] integrator koncowy

## 25. Najblizszy praktyczny krok

Ten dokument jest gotowy jako nadrzedny masterplan.

Najblizszy sensowny krok wykonawczy:

- [ ] rozpisac `Faza 0-4` plik-po-pliku i endpoint-po-endpoincie
- [ ] zamrozic ownership map
- [ ] zamrozic integration contracts
- [ ] dopiero potem przejsc do promtow dla modeli

## 26. Wniosek koncowy

Droga do pelnej funkcjonalnosci AEIS nie polega juz na "wymyslaniu architektury".

Polega na:

- [ ] zszyciu istniejacych warstw w jeden truth spine
- [ ] doprowadzeniu governance, council, skills, memory, funding i mobile do wspolnej semantyki
- [ ] naprawieniu operator surfaces tak, by pokazywaly prawde
- [ ] i domknieciu tego dowodem z Ksiegi Testow 500

Ten dokument ma byc od teraz glowna checklista prowadzenia systemu do pelnej funkcjonalnosci.
