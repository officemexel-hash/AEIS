# CODEX PROMPT 03 - KIMI 2.6 - AGENT K

Rola: Funding + Observability + Runtime Hygiene  
Priorytet: lzejszy  
Ownership: tylko obszary przypisane K w `CODEX_PARALLEL_COORDINATION.md`

## Cel

Masz domknac izolowane, proceduralne strumienie, ktore nie wymagaja przebudowy glównego governance spine, ale sa potrzebne do production readiness:

- funding gap-fill
- observability i metrics
- runtime hygiene / cleanup

## Ownership scope

- `src/sylion-pipeline/sylion/funding_autopilot/*`
- `src/sylion-pipeline/sylion/api/funding*`
- `src/sylion-pipeline/sylion/observability/*`
- `src/sylion-pipeline/sylion/monitoring/*`
- `src/sylion-frontend/src/app/(app)/funding/*`
- `src/sylion-frontend/src/app/(app)/observability/*`
- `src/sylion-pipeline/dashboard/*` tylko legacy bridge / cleanup / oznaczenia
- `tests/funding/*`
- `tests/observability/*`

## Najwazniejsze problemy do naprawy

1. Funding jest dojrzaly, ale brakuje czesci capabilities
2. Funding ma lokalny approval plane i musi byc gotowy do wpiecia w unified governance
3. Observability zyje, ale jest lokalne i za slabe na production readiness
4. Runtime truth ma hygiene problemy, np. stare PID files i niejednoznaczne operacyjne wskazniki

## Zakres wykonawczy

### K1. Funding gap-fill wewnatrz `funding_autopilot`

Masz dopelnic brakujace capabilities **w istniejacym namespace `funding_autopilot`**, nie w nowym top-level `funding/`.

Obszary:

- scanner programow
- browser-driven helpers
- reporting / post-award flow
- contract/manifest helper dla call requirements

### K2. Funding -> governance bridge preparation

Nie zmieniasz governance A, ale przygotowujesz po swojej stronie:

- eventy
- payloady
- hook points

tak, aby D mogl finalnie spiac funding z unified Human Gate plane.

### K3. Observability / metrics strengthening

Masz:

- dopelnic metrics/exporter
- wzmocnic route hygiene i gotowosc operatorska
- przygotowac powierzchnie do finalnej oceny readiness przez D

### K4. Runtime hygiene i legacy cleanup

Masz uporzadkowac rzeczy izolowane i niskiego ryzyka, np.:

- pid truth / start-script hygiene
- legacy dashboard oznaczenia / bridge
- lekkie cleanupy surface'ow funding/observability

## Twarde ograniczenia

- nie buduj drugiego funding domain obok `funding_autopilot`
- nie wchodz w governance/workspace/project_mode A
- nie wchodz w skills/memory/mobile B
- nie edytuj reserved shared files D

## Handoff do D

Oddajesz:

- dopelniony funding domain
- gotowe funding hooks do unified governance
- metrics/observability improvements
- runtime hygiene notes
- testy funding/observability

## Done definition

- funding zachowuje istniejacy lokalny flow i rozszerza capabilities, zamiast byc przebudowany od zera
- observability ma silniejszy eksport i lepsza gotowosc operatorska
- runtime hygiene jest lepsza i bardziej jednoznaczna
- nic z tego nie tworzy rownoleglego subsystemu obok istniejacych namespace'ow
