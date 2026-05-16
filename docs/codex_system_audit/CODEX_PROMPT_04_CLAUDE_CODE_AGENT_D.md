# CODEX PROMPT 04 - CLAUDE CODE - AGENT D

Rola: Final Integration + Human-like Audit  
Priorytet: finalny integrator  
Warunek startu: A, B i K zakonczyli swoje ownership scope i przygotowali handoff

## Cel

Masz zintegrowac wszystkie trzy strumienie bez psucia istniejacego runtime spine, a nastepnie wykonac finalny audit i testy produkcyjnej gotowosci.

## Shared files reserved for D

Tylko Ty edytujesz:

- `src/sylion-pipeline/sylion/api/app.py`
- `src/sylion-pipeline/sylion/api/router.py`
- `src/sylion-frontend/src/lib/api/client.ts`
- root start scripts
- final shared integration tests

## Zakres wykonawczy

### D1. Startup and router integration

Masz:

- wlaczyc zmiany A/B/K w jeden runtime lifecycle
- dopiac startup binding dla memory i skills
- dopiac wspolne route mounts
- dopiac mobile routes
- dopiac funding/observability rozszerzenia

### D2. Unified truth validation

Masz sprawdzic, czy po integracji:

- Human Gate jest jeden i dominujacy
- memory ma jeden startup-bound plane
- skills runtime dziala w spine
- funding wysyla decyzje do wspolnego governance
- operator console i mobile pracuja nad jedna logika decyzji

### D3. Testy S1-S8

Masz uruchomic scenariusze:

- S1 Idea Debate
- S2 Source Of Truth
- S3 Masterplan And Team Scaling
- S4 Execution With Gates
- S5 Human-Like Verification
- S6 Final Approval
- S7 Funding Flow
- S8 Operator Control Flow

### D4. Testy "jak czlowiek"

Masz przejsc browserowo kluczowe ekrany:

- workspace
- projects
- workers
- observability
- governance
- funding
- skills
- operator mobile

I potwierdzic:

- brak krytycznych bledow runtime
- sensowny flow operatora
- brak rozjazdu ekran vs API

### D5. Finalny audit modul po module

Masz zrobic finalny przeglad modulow i funkcji:

- czy importuja sie poprawnie
- czy maja testy
- czy sa zarejestrowane
- czy nie zostaly po nich duplicate planes
- czy production readiness wzrosla

## Twarde ograniczenia

- nie przepisuj od zera rzeczy, ktore A/B/K juz skonsolidowali
- nie omijaj istniejacego spine `workspace -> project_mode`
- nie zamieniaj finalnej integracji w nowy greenfield rewrite

## Deliverables

- zintegrowany runtime
- finalny raport przejsc scenariuszy S1-S8
- finalny raport human-like test
- finalny module-by-module verification note
- finalny production readiness verdict

## Done definition

- shared files sa spojne
- wszystkie mounty i startup lifecycles sa dopiete
- scenariusze S1-S8 przechodza lub maja jawne, spisane blokery
- operator flow jest browserowo zweryfikowany
- finalny audit pokazuje, ze system przeszedl z federated-dev do realnego staging candidate albo production ready
