# CODEX AEIS PARALLEL MASTERPLAN 2026

**Status:** draft 0.1  
**Cel:** rozpisac dojscie od obecnego, sfederowanego AEIS do wersji production-ready przy pracy rownoleglej trzech modeli w tym samym katalogu oraz czwartego etapu integracyjno-audytowego  
**Podstawa:** audyt Codexa, `AEIS_SYSTEM_BOOK_2026.md`, `CODEX_AEIS_CLAUDE_PARALLEL_DIFF.md`, dokumenty `docs/claude_system_audit/parallel/*`

## 0. Relacja do masterplanu nadrzednego

Ten dokument **nie jest juz planem startowym**.

Wiazacy plan nadrzedny jest opisany w:

- [CODEX_AEIS_UNIFIED_REPAIR_MASTERPLAN_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_UNIFIED_REPAIR_MASTERPLAN_2026_04_25.md)

Ten plan rownolegly wolno uruchamiac dopiero po zielonej bramce po:

- Fazie 0
- Fazie 1
- Fazie 2
- rdzeniu Fazy 3

Czyli:

- najpierw jeden lider architektoniczny stabilizuje spine, workspace i governance contract
- dopiero potem uruchamiany jest split `Claude + Codex + Kimi + integrator`

## 1. Zasada podstawowa

Ten masterplan **nie** traktuje AEIS jak greenfield.

Naprawy maja byc planowane wedlug zasady:

- konsoliduj istniejace planes
- nie buduj rownoleglych subsystemow obok `workspace`, `project_mode`, `funding_autopilot`, `skills`, `memory`
- mobile moze byc nowym strumieniem, bo tam brak potwierdzonego runtime

## 2. Cel koncowy

System po realizacji czterech promptow ma osiagnac:

- jeden dominujacy spine `workspace -> project_mode -> runtime`
- jeden Human Gate truth plane
- jeden model council truth plane
- jeden startup-bound memory plane
- jeden dzialajacy skills runtime plane
- jeden operator truth plane
- funding wpiety do wspolnego governance
- mobilny bridge operatorski gotowy do realnych approvali
- staging/production readiness poparta testami S1-S8 i testami "jak czlowiek"

## 3. Podzial na cztery strumienie

### Prompt 1 — Claude Code — najciezsze

Zakres:

- governance core
- Human Gate unification
- council/model registry unification
- workspace/project_mode truth consolidation
- autonomy integration
- worker pool reconciliation

Dlaczego Claude:

- to sa zmiany najbardziej architektoniczne
- dotykaja spine systemu
- maja najwyzsze ryzyko regresji

### Prompt 2 — Codex — srednie

Zakres:

- skills runtime bootstrap i unifikacja registry/runtime
- memory startup binding i integracja retrieval/evidence
- wpiecie skills/memory do spine bez dublowania namespace
- backend/mobile bridge i nowy surface mobile tam, gdzie brak istniejacego kodu

Dlaczego Codex:

- to sa duze, ale dobrze odcinane bloki sredniej ciezkosci
- wymagaja duzo implementacji i integracji, ale nie powinny przebudowywac calego governance core

### Prompt 3 — Kimi 2.6 — lzejsze

Zakres:

- funding gap-fill wewnatrz `funding_autopilot`
- observability / metrics / pid truth / runtime hygiene
- legacy cleanup i lekkie surface fixes
- dokumentacja integracyjna funding + observability

Dlaczego Kimi:

- to sa zadania bardziej proceduralne
- da sie je odciac od najciezszych zmian architektonicznych
- nie powinny wymuszac masowego cross-module reasoningu

### Prompt 4 — Claude Code — integracja i finalny audit

Zakres:

- zintegrowanie shared files
- mount shared routes
- dopiecie routera i startup lifecycle
- testy S1-S8
- testy "jak czlowiek"
- modul-po-module final verification
- final production readiness verdict

## 4. Najwazniejsza korekta wzgledem planow Claude parallel

Nie wolno planowac:

- nowego `skills/` obok `src/sylion-pipeline/sylion/skills`
- nowego `memory/search` obok `src/sylion-pipeline/sylion/memory`
- nowego `funding/*` obok `src/sylion-pipeline/sylion/funding_autopilot`
- nowego abstrakcyjnego `core` obchodzacego istniejacy spine `workspace -> project_mode`

Masterplan ma pracowac na **realnych namespace'ach repo**.

## 5. Sekwencja wykonania

### Phase 0 — przygotowanie

- zamrozic baseline i zrobic tag/backup
- przyjac ownership map
- przyjac shared file rules
- przyjac integration contracts
- ustalic checklisty handoff

### Phase 1 — rownolegla praca A/B/K

Agent A, B i K pracuja w tym samym katalogu, ale na rozdzielonych obszarach.

Warunek:

- zero overlap write ownership
- shared files append-only albo reserved-for-D

### Phase 2 — handoff do D

Po zakonczeniu A/B/K:

- D integruje shared files
- D domyka mounts i startup
- D robi full regression
- D robi browser/human-like test
- D robi finalny audit i verdict

## 6. Realne workstreamy naprawcze

### Stream A — spine i governance

Naprawia:

- Human Gate split
- council semantics drift
- model registry vs workspace council-members split
- autonomy detached state
- execution_plan vs worker_pool reconciliation

### Stream B — memory, skills, mobile

Naprawia:

- skills registry/runtime split
- memory startup binding gap
- evidence stats route collision
- brak dzialajacego similarity/reuse plane w spine
- brak mobile backend/frontend bridge

### Stream K — funding, observability, cleanup

Naprawia:

- funding scanner/reporting/browser gaps
- funding -> governance bridge
- observability exporter i runtime hygiene
- pid truth i lekkie cleanupy legacy

### Stream D — integration and proof

Naprawia:

- shared mounts
- startup lifecycle integration
- end-to-end proof
- production readiness evidence

## 7. Kryteria sukcesu

Masterplan bedzie uznany za wykonany dopiero gdy:

- `workspace` i `governance` korzystaja z jednego Human Gate truth plane
- `workspace` i `project_mode` korzystaja z jednej, jawnie bootstrappowanej memory warstwy
- skills runtime laduje z registry/filesystem i dziala w spine
- funding emituje decyzje do wspolnego governance plane
- mobile ma backend bridge i operator surface
- router/startup/app sa spojne
- testy S1-S8 przechodza
- testy browserowe "jak czlowiek" przechodza
- finalny audit modulow nie pokazuje krytycznych czerwonych dziur

## 8. Dokumenty wykonawcze

Ten masterplan ma byc wykonywany razem z:

- `CODEX_PARALLEL_COORDINATION.md`
- `CODEX_PARALLEL_INTEGRATION_CONTRACTS.md`
- `CODEX_PROMPT_01_CLAUDE_CODE_AGENT_A.md`
- `CODEX_PROMPT_02_CODEX_AGENT_B.md`
- `CODEX_PROMPT_03_KIMI_AGENT_K.md`
- `CODEX_PROMPT_04_CLAUDE_CODE_AGENT_D.md`

## 9. Wniosek

Szkielet 4-etapowy z planow Claude parallel jest dobry organizacyjnie.

Musial jednak zostac skorygowany technicznie tak, aby:

- nie dublowal istniejacych namespace'ow
- nie traktowal zywego runtime jak greenfield
- wykorzystywal realny spine AEIS
- rozdzielal ownership wedlug prawdziwych punktow ciezkosci systemu
