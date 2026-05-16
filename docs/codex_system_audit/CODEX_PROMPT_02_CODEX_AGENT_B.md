# CODEX PROMPT 02 - CODEX - AGENT B

Rola: Adaptive Runtime + Memory + Skills + Mobile Bridge  
Priorytet: sredni  
Ownership: tylko obszary przypisane B w `CODEX_PARALLEL_COORDINATION.md`

## Cel

Masz domknac trzy strategiczne luki:

- skills runtime
- memory startup plane
- mobile bridge

Masz to zrobic **wewnatrz realnych namespace'ow repo**, a nie przez greenfield obok nich.

## Ownership scope

- `src/sylion-pipeline/sylion/skills/*`
- `src/sylion-pipeline/sylion/memory/*`
- `src/sylion-pipeline/sylion/api/skills_routes.py`
- `src/sylion-pipeline/sylion/api/memory_routes.py`
- nowy `src/sylion-pipeline/sylion/operator_mobile/*`
- nowy `src/sylion-frontend/src/app/(app)/operator-mobile/*`
- `src/sylion-frontend/src/app/(app)/skills/*`
- `tests/skills/*`
- `tests/memory/*`
- `tests/mobile/*`

## Najwazniejsze problemy do naprawy

1. Skills registry vs runtime split
   Dzis:
   - registry zyje
   - UI zyje
   - runtime ma `loaded_skills = 0`
   - execute seed skillu zwraca `Unknown skill`

2. Memory startup binding gap
   Dzis:
   - memory API zyje
   - manualny index/search dziala
   - startup nie bootstrappuje jednego shared-memory plane
   - `/memory/evidence/stats` jest broken przez konflikt tras

3. Brak realnego bridge pod mobile
   Mobile jest planowane, ale nie ma potwierdzonego runtime backend/frontend.

## Zakres wykonawczy

### B1. Skills runtime bootstrap

Masz doprowadzic do tego, aby:

- skills runtime ladowal realne skille
- registry, runtime i operator UI przestaly byc trzema polowicznie rozlaczonymi bytami
- seed skill i kolejne registry entries daly sie realnie uruchomic

Pracujesz w istniejacym `src/sylion-pipeline/sylion/skills/*`.
Nie tworz nowego top-level `skills/`.

### B2. Skills -> spine integration

Masz przygotowac warstwe, ktora pozwoli spine A:

- korzystac z dopietego runtime skills
- wywolywac skills w kontekście workspace/project_mode

Nie edytujesz plikow A, ale zostawiasz gotowa implementacje po swojej stronie i czytelny handoff.

### B3. Memory startup unification

Masz:

- naprawic bootstrap shared memory plane
- uporzadkowac start `indexer/evidence/retrieval`
- naprawic routing collision dla `/memory/evidence/stats`
- doprowadzic do tego, aby globalne memory API nie bylo tylko leniwym, pustym singletonem po starcie

### B4. Memory -> execution evidence integration

Masz przygotowac dopiecie memory do execution spine tak, aby:

- evidence
- retrieval
- indexed sections

mogly byc sensownie konsumowane przez flow A i finalny audit D.

### B5. Operator Mobile bridge

Poniewaz nie znaleziono istniejacej realnej app codebase mobile, mozesz zbudowac:

- backendowy bridge mobile approval
- nowy operator-mobile surface
- modele danych i API pod:
  - approval queue
  - push-ready payloads
  - secure token flow
  - device binding metadata

Ale:

- nie budujesz drugiego Human Gate
- mobile ma byc frontendem do wspolnego governance plane, nie osobnym plane decyzji

## Twarde ograniczenia

- nie tworz nowego `memory/search` obok istniejacego `sylion/memory`
- nie tworz nowego `skills` obok istniejacego `sylion/skills`
- nie buduj mobile jako niezaleznego systemu odcie­tego od governance A
- nie edytuj reserved shared files D

## Handoff do D

Oddajesz:

- skills runtime dzialajacy na zywych skillach
- memory bootstrap i route fix
- mobile backend/frontend bridge w osobnym, izolowanym namespace
- testy skills/memory/mobile
- liste mountow i startup hookow, ktore D ma wlaczyc w shared files

## Done definition

- `loaded_skills > 0`
- seed skill i co najmniej jeden dodatkowy skill uruchamiaja sie poprawnie
- `/memory/evidence/stats` przestaje byc 404
- shared memory plane jest bootstrappowany na starcie
- istnieje realny operator-mobile bridge gotowy do finalnej integracji przez D
