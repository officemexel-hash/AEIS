# Projekty, fazy i tutorial operatora

## Spis tresci

1. [Cel lifecycle projektu](#cel-lifecycle-projektu)
2. [Tutorial: pierwszy projekt](#tutorial-pierwszy-projekt)
3. [Fazy 16-19 Project Start](#fazy-16-19-project-start)
4. [Fazy 20-25 Council to Ksiega](#fazy-20-25-council-to-ksiega)
5. [Fazy 26-31 Planning](#fazy-26-31-planning)
6. [Fazy 32-41 Execution](#fazy-32-41-execution)
7. [Cztery projekty probne](#cztery-projekty-probne)
8. [Scenariusze pozytywne i bledne](#scenariusze-pozytywne-i-bledne)

## Cel lifecycle projektu

Lifecycle projektu AEIS prowadzi operatora od pomyslu do zamkniecia projektu. W praktyce najwazniejszy flow to:

```text
Project Start 16-19 -> Council/Ksiega 20-25 -> Planning 26-31 -> Execution 32-41 -> Evidence/freeze
```

W retestach 2026-05-17 ten flow przeszedl przez cztery projekty probne P1-P4. Kazdy blad po drodze byl naprawiany, testowany dwukrotnie i dopiero potem zamrazany.

## Tutorial: pierwszy projekt

1. Uruchom backend i frontend.
2. Otworz `http://127.0.0.1:3002/project-start`.
3. Wypelnij nazwe, opis, domeny, budzet, deadline i poziom decyzji.
4. Kliknij preview, sprawdz klasyfikacje i hard blocks.
5. Kliknij create project.
6. Przejdz przez fazy 16-19:
   - default goals;
   - default scope;
   - council defaults;
   - approve readiness.
7. Otworz `/council-to-ksiega`.
8. Przejdz przez fazy 20-25.
9. Otworz `/planning`.
10. Przejdz przez fazy 26-31.
11. Otworz `/execution-start`.
12. Przejdz przez fazy 32-41.
13. Odswiez ekran i sprawdz:
   - projekt nadal jest wybrany;
   - stan jest `CLOSED`;
   - widac `10/10` faz wykonania;
   - konsola przegladarki nie ma bledow;
   - API potwierdza acceptance dla faz.

## Fazy 16-19 Project Start

API: `/api/v1/project-start`
UI: `/project-start`

| Faza | Nazwa operatorska | Endpoint / akcja | Co powstaje |
| --- | --- | --- | --- |
| 16 | Intake projektu | `POST /projects/preview`, `POST /projects/create` | Projekt, klasyfikacja, domena, D-level, shell lifecycle. |
| 17 | Cele i defaulty | `POST /projects/{id}/goals/defaults` | Cele, KPI, ograniczenia, acceptance goals. |
| 18 | Zakres | `POST /projects/{id}/scope/defaults` | Zakres, runtime constraints, edge cases, risk profile. |
| 19 | Gotowosc do rady | `POST /projects/{id}/council/defaults`, `POST /projects/{id}/council/approve-readiness` | Council defaults, readiness, przejscie do faz 20-25. |

Pomocne API:

- `GET /api/v1/project-start`;
- `GET /api/v1/project-start/templates`;
- `GET /api/v1/project-start/projects`;
- `GET /api/v1/project-start/active`;
- `GET /api/v1/project-start/projects/{id}`;
- `GET /api/v1/project-start/projects/{id}/phases/{phase}/acceptance`;
- `GET /api/v1/project-start/projects/{id}/edge-cases`;
- `POST /api/v1/project-start/projects/{id}/edge-cases/diagnose`.

Screenshot:

![Project Start](screenshots/01_project_start.png)

## Fazy 20-25 Council to Ksiega

API: `/api/v1/council-to-ksiega`
UI: `/council-to-ksiega`

| Faza | Nazwa | Endpoint | Wynik |
| --- | --- | --- | --- |
| 20 | Zwolanie Rady | `POST /projects/{id}/phase20/convene` | Role rady, pytania, kontekst. |
| 21 | Pierwsze werdykty | `POST /projects/{id}/phase21/initial-verdicts` | Werdykty modeli, poziomy konsensusu. |
| 22 | Rundy deliberacji | `POST /projects/{id}/phase22/deliberate` | Rundy dyskusji, sporne pytania, poprawki. |
| 23 | Konsolidacja | `POST /projects/{id}/phase23/consolidate` | Final decisions, risk register, scope guard. |
| 24 | Generowanie Ksiega Rady | `POST /projects/{id}/phase24/generate-book` | Markdown/PDF book, checksum. |
| 25 | Finalizacja Ksiegi | `POST /projects/{id}/phase25/finalize-ksiega` | Final source book i przejscie do planning. |

Screenshot:

![Council to Ksiega](screenshots/02_council_to_ksiega.png)

## Fazy 26-31 Planning

API: `/api/v1/planning`
UI: `/planning`

| Faza | Nazwa | Endpoint | Wynik |
| --- | --- | --- | --- |
| 26 | Model Selection | `POST /projects/{id}/phase26/assign-models` | Model assignment, role, fallback chains, koszt. |
| 27 | Skill Synthesis | `POST /projects/{id}/phase27/synthesize-skills` | Skills projektowe i systemowe. |
| 28 | Masterplan Synthesis | `POST /projects/{id}/phase28/generate-masterplan` | Warstwy wykonania, harmonogram, zaleznosci. |
| 29 | Test Plan Synthesis | `POST /projects/{id}/phase29/generate-test-plan` | L1-L5, human-like tests, acceptance criteria. |
| 30 | Pre-Flight Cost Preview | `POST /projects/{id}/phase30/preflight-cost` | Koszt, limity, guards. |
| 31 | Pre-Flight Dry Run | `POST /projects/{id}/phase31/dry-run` | Gotowosc do build, local-first constraints. |

Screenshot:

![Planning](screenshots/03_planning.png)

## Fazy 32-41 Execution

API: `/api/v1/execution-start`
UI: `/execution-start`

| Faza | Nazwa | Endpoint | Wynik |
| --- | --- | --- | --- |
| 32 | Inicjalizacja budowy | `POST /projects/{id}/phase32/initialize-build` | Workspace, branches, workers, environments, monitoring. |
| 33 | Sekwencyjne wykonanie | `POST /projects/{id}/phase33/start-execution` | Petla budowy, dispatch control, progress. |
| 34 | Rada w trakcie budowy | `POST /projects/{id}/phase34/reconvene-council` | Mid-build council i decision evidence. |
| 35 | Orkiestracja budowy | `POST /projects/{id}/phase35/activate-orchestration` | Koordynacja workerow, recovery, coherence. |
| 36 | Zamkniecie budowy | `POST /projects/{id}/phase36/complete-build` | Artefakty, koszt, worker decommission. |
| 37 | Bramki jakosci | `POST /projects/{id}/phase37/run-quality-gates` | L1-L5, coverage, critical findings, PASS verdict. |
| 38 | Akceptacja klienta | `POST /projects/{id}/phase38/complete-acceptance` | Staging, feedback, signoff. |
| 39 | Finalna kontrola | `POST /projects/{id}/phase39/authorize-predeploy` | Rollback, monitoring, hard gate. |
| 40 | Deploy/proba lokalna | `POST /projects/{id}/phase40/execute-production-deploy` | Canary/local rehearsal, external calls blocked. |
| 41 | Zamkniecie projektu | `POST /projects/{id}/phase41/close-project` | Raporty, archiwum, warranty, final state `CLOSED`. |

Kontrole dodatkowe:

- runtime configuration: `GET/POST /projects/{id}/runtime-configuration`;
- live workers: `GET/POST /phase32/live-spawn-workers`, `POST /phase32/stop-live-workers`;
- dispatch: `GET /phase33/dispatch-control`, `POST pause/resume/cancel`;
- W18 commands: `GET /projects/{id}/w18-commands`;
- audit truth map: `GET/POST /audit-truth-map`.

Screenshot:

![Execution Start](screenshots/04_execution_start.png)

## Cztery projekty probne

| Projekt | Trudnosc | D-level | Domena | Cel testowy | Wynik |
| --- | --- | --- | --- | --- | --- |
| P1 Mini CRM Serwisowy | Easy | D3 | crm | Najprostszy lokalny system CRM. | `CLOSED`, `10/10`, local rehearsal. |
| P2 Generator Umow i Ofert | Medium | D3 | crm | Dokumenty, oferty, workflow biznesowy. | `CLOSED`, `10/10`. |
| P3 Funding Assistant Fundacji | Hard | D4 | funding | Funding workflow bez realnego external submit. | `CLOSED`, `10/10`, local rehearsal. |
| P4 Platforma Reagowania Kryzysowego | Very hard | D5 | aeis_multi_domain | Multi-domain, governance, local-first, no external calls. | `CLOSED`, `10/10`, reload-proof. |

P4 reload-proof:

- route: `/execution-start`;
- UI: `PROJEKT ZAMKNIETY`;
- accepted phases: `10/10`;
- console errors: `0`;
- API state: `CLOSED`;
- deploy mode: `local_release_rehearsal_no_external_calls`.

## Scenariusze pozytywne i bledne

### Scenariusz pozytywny

1. Projekt tworzony jest przez UI.
2. Kazda grupa faz ma widoczny stan i acceptance.
3. Kazda akcja mutujaca wraca z backendu.
4. Po reloadzie stan pozostaje.
5. API potwierdza stan projektu.
6. Konsola przegladarki nie ma bledow.
7. Flow zostaje zapisany w evidence.

### Scenariusze bledne

| Blad | Objaw | Reakcja operatora |
| --- | --- | --- |
| `Failed to fetch` po preflight | UI kasuje projekt albo pokazuje falszywy offline. | Zatrzymac flow, sprawdzic OPTIONS/GET, naprawic retry/critical load, 2x retest. |
| Toast bez zapisu | UI pokazuje sukces, reload cofa stan. | Nie zamrazac, sprawdzic API i persisted state. |
| Brak Human Gate | D4/D5 akcja przechodzi bez decyzji. | Blokuje freeze governance. |
| Brak provenance | Memory/funding/test result nie ma zrodla. | Blokuje freeze evidence. |
| Deploy external bez zgody | Phase 40 wykonuje external call. | Krytyczny blocker, wymagany Human Gate D5. |
| Konsola ma blad JS | UI moze dzialac pozornie, ale runtime jest niespojny. | Naprawic i wykonac dwa reload-proofy. |
