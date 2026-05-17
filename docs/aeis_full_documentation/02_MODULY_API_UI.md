# Moduly, API i UI AEIS

## Spis tresci

1. [Jak liczono moduly](#jak-liczono-moduly)
2. [Backend packages](#backend-packages)
3. [Najwieksze rodziny API](#najwieksze-rodziny-api)
4. [Kluczowe moduly logiczne](#kluczowe-moduly-logiczne)
5. [Menu operatora](#menu-operatora)
6. [Tryb techniczny](#tryb-techniczny)
7. [Mapa UI do API](#mapa-ui-do-api)
8. [Route-only ryzyko](#route-only-ryzyko)

## Jak liczono moduly

Snapshot 2026-05-17:

- backend health: `138` modulow runtime;
- OpenAPI: `1649` path templates, `1932` metody policzone po path operations;
- backend route files: `127` plikow `*_routes.py`;
- frontend route pages: `129` plikow `page.tsx`;
- menu glowne: tryb operatora + tryb techniczny + AEIS v2.

Liczba `138` z `/health` jest liczba runtime deklarowana przez aplikacje. Liczba folderow i routerow jest wieksza, bo obejmuje pomocnicze API, legacy, laboratoria, aliasy i integracje.

## Backend packages

| Package | Rola |
| --- | --- |
| `aeis`, `aeis_v2` | Rdzen AEIS, test center, terminal, W14-W19, v2 surfaces. |
| `api` | FastAPI routers, app bootstrap, middleware, route aggregation. |
| `autonomy` | Autonomia, polityki samodzielnosci, konfiguracja decyzji. |
| `cellular`, `sdr`, `devices`, `container`, `vps` | Laboratoria runtime i infrastruktury. |
| `cognitive`, `providers`, `grpc`, `grpc_stubs` | Modele, LLM runtime, providerzy, gRPC. |
| `contracts`, `core`, `db` | Kontrakty, rdzen domenowy, baza danych. |
| `demo` | Reference/demo projects. |
| `efficiency`, `quality`, `security` | Guardy i metryki jakosci, kosztu, security. |
| `execution`, `pipeline`, `worker` | Wykonanie, pipeline, worker registry, dispatch. |
| `funding_autopilot` | Modul grantowy/funding. |
| `governance` | Rada, Human Gate, D-level governance. |
| `infra`, `integration`, `observability`, `monitoring` | Integracje, runtime truth, logs, metrics, traces. |
| `memory` | Kanon, evidence, retrieval, knowledge base. |
| `operator_mobile` | Mobile approval plane. |
| `project_mode` | Projekty, lifecycle, W18/project runtime. |
| `rebuild`, `sim`, `surface` | Rebuild, symulacje, surface modules. |
| `skills` | Skills registry, catalog, runtime executor, demand signals. |

## Najwieksze rodziny API

Top OpenAPI families wedlug liczby metod:

| Prefix | Metody | Znaczenie |
| --- | ---: | --- |
| `/api/v1/governance` | 117 | Governance, Human Gate, policy, council-related APIs. |
| `/api/v1/monitoring` | 90 | Monitoring, budgets, metrics, runtime panels. |
| `/api/v1/workspace` | 73 | Workspace AI, sessions, books, project kickoff. |
| `/api/v1/security` | 62 | Security, profiles, audit, scans. |
| `/api/v1/aeis` | 56 | AEIS decomposition/core high-level APIs. |
| `/api/v1/funding` | 53 | Funding Autopilot. |
| `/api/v1/core` | 51 | Core runtime. |
| `/api/v1/reference` | 51 | Reference/demo projects. |
| `/api/v1/cognitive` | 46 | Cognitive/model runtime. |
| `/api/v1/memory` | 44 | Memory, evidence, retrieval. |
| `/api/v1/projects` | 43 | Project registry, lifecycle, details. |
| `/api/v1/skills` | 37 | Skills registry/runtime. |
| `/api/v1/execution` | 36 | Execution APIs. |
| `/api/v1/cellular` | 34 | Cellular lab. |
| `/api/v1/advisor` | 34 | Advisor cards/preferences. |
| `/api/v1/orchestration` | 32 | J-flow orchestration. |
| `/api/v1/execution-start` | 30 | Fazy 32-41. |
| `/api/v1/quality` | 29 | Quality gate APIs. |
| `/api/v1/rebuild` | 29 | Rebuild/self-repair. |
| `/api/v1/workers` | 29 | Worker registry, autoscaler. |

## Kluczowe moduly logiczne

| Modul | UI | API | Status |
| --- | --- | --- | --- |
| Bootstrap/Health | `/health`, `/runtime` | `/health`, `/api/v1/health`, `/api/v1/runtime` | `LIVE_VERIFIED` |
| Workspace AI | `/workspace` | `/api/v1/workspace` | `PARTIAL_2X_PASS` |
| Pipeline | `/pipeline` | `/api/v1/pipeline` | `PARTIAL`, build fixed |
| Project Start | `/project-start` | `/api/v1/project-start` | `2X_PASS` P1-P4 |
| Council to Ksiega | `/council-to-ksiega` | `/api/v1/council-to-ksiega` | `2X_PASS` P1-P4 |
| Planning | `/planning` | `/api/v1/planning` | `2X_PASS` P1-P4 |
| Execution Start | `/execution-start` | `/api/v1/execution-start` | `2X_PASS` P1-P4 |
| Human Gate | `/human-gate`, `/operator-mobile/queue` | `/api/v1/governance`, `/api/v1/mobile` | `PARTIAL` |
| Funding | `/funding` | `/api/v1/funding` | `PARTIAL_2X_PASS`, local rehearsal |
| Skills | `/skills` | `/api/v1/skills` | `2X_PASS` create/execute/signal |
| Memory | `/memory` | `/api/v1/memory` | `PARTIAL_ROUTE` |
| Model Council | `/model-council`, `/orchestration/council-rules` | `/api/v1/council`, `/api/v1/orchestration` | `PARTIAL` |
| Workers | `/workers` | `/api/v1/workers` | `LIVE_VERIFIED` |
| Test Center | `/test-center`, `/test-center/dashboard` | `/api/v1/test-center`, `/api/v1/testing` | `PARTIAL_2X_PASS` |
| Terminal W18 | `/terminal`, `/terminal/replay` | `/api/v1/terminal` | project W18 `2X_PASS`, global partial |
| Ontology | `/ontology` | `/api/v1/ontology` | `PARTIAL_ROUTE` |
| Apps Builder | `/apps-builder` | `/api/v1/apps` | `PARTIAL_ROUTE` |
| Federation | `/federation` | `/api/v1/federation` | `PARTIAL_ROUTE` |
| Labs | `/devices`, `/sdr`, `/cellular`, `/environments/theater` | lab prefixes | `LAB/PARTIAL` |

## Menu operatora

Sekcje i funkcje z `AppSidebar`:

| Sekcja | Zakladka | Route | Funkcja |
| --- | --- | --- | --- |
| Doradca | Centrum dowodzenia | `/advisor/cockpit` | Widok strategiczny Advisora. |
| Doradca | Doradca na zywo | `/advisor` | Karty doradcze, rekomendacje, decyzje. |
| Doradca | Monitor projektow | `/dashboard/operator-monitor` | Monitor aktywnych projektow. |
| Doradca | Pierwsze uruchomienie | `/onboarding` | Wizard startowy operatora. |
| Projekty | Projekty | `/projects` | Lista i szczegoly projektow. |
| Projekty | Start projektu | `/project-start` | Tworzenie projektu, fazy 16-19. |
| Projekty | Deliberacja i Ksiega | `/council-to-ksiega` | Fazy 20-25. |
| Projekty | Planowanie | `/planning` | Fazy 26-31. |
| Projekty | Start wykonania | `/execution-start` | Fazy 32-41. |
| Projekty | Skarbiec pomyslow | `/idea-vault` | Pomysly, attach, przejscie do projektu. |
| Finansowanie | Doradca grantow | `/funding` | Funding Autopilot. |
| Decyzje | Decyzje | `/decisions` | Decyzje systemowe i projektowe. |
| Decyzje | Rada | `/governance` | Governance/council. |
| Decyzje | Bramka czlowieka | `/human-gate` | Queue approve/reject. |
| Decyzje | Pakiety dowodowe | `/evidence` | Evidence packs. |
| Decyzje | Sciezka audytu | `/audit` | Audit trail. |
| Testowanie | Centrum testow W14 | `/test-center` | Test center. |
| Testowanie | Teatr modeli | `/test-center/theater` | Symulacje i teatr modeli. |
| Konfiguracja | Ustawienia doradcy | `/settings/advisor` | Preferencje Advisora. |
| Konfiguracja | Modele AI | `/ai-models` | Providerzy i modele. |
| Konfiguracja | Domyslny obszar pracy | `/workspace-defaults` | Defaulty projektow. |
| Konfiguracja | Guardy | `/coherence-guard`, `/cost-guard`, `/security-guard`, `/quality-guard`, `/provenance-guard` | Guard configuration. |
| Konfiguracja | Szablony | `/templates-setup` | Templates. |
| Konfiguracja | Srodowiska | `/environments` | Environment catalog. |
| Konfiguracja | Umiejetnosci | `/skills` | Skills registry/runtime. |
| Konfiguracja | Budzet modeli | `/budget` | Model budget. |
| Konfiguracja | Klucze API | `/secrets` | Secrets/API keys. |
| Orkiestracja | Trasy LLM | `/orchestration/llm-routing` | Routing modeli. |
| Orkiestracja | Reguly rady | `/orchestration/council-rules` | Council rules. |
| Orkiestracja | Audytor | `/orchestration/auditor` | Auditor agent. |
| Orkiestracja | Naprawiacze | `/orchestration/fixer` | Repair agents. |
| Orkiestracja | Rozdzial pracy | `/orchestration/dispatch` | Dispatch. |
| Orkiestracja | Katalog testow | `/orchestration/tests` | Test catalog. |
| Orkiestracja | Zespoly | `/orchestration/teams` | Agent teams. |
| Orkiestracja | Mapa eventow | `/orchestration/event-map` | Event map. |
| Orkiestracja | Rozmowy AI | `/orchestration/conversations` | AI conversations. |
| AEIS v2 | Warstwy, Ontologia, Terminal, Federation, Policy | `/architecture-layers`, `/ontology`, `/terminal`, `/federation`, `/policy` | Zaawansowane planes W7/W15/W17-W19. |
| Wsparcie | Pomoc i FAQ | `/faq` | FAQ i runbook. |

## Tryb techniczny

Tryb techniczny pokazuje dodatkowe powierzchnie dla administratora i developera:

| Grupa | Routes |
| --- | --- |
| Rdzen | `/overview`, `/pipeline`, `/workspace`, `/agents`, `/modules`, `/health`, `/contracts`, `/performance`, `/devices`, `/costs`, `/sdr`, `/cellular`, `/rebuild`, `/autonomy`, `/lifecycle`, `/book` |
| Operacje | `/anomalies`, `/sla`, `/drift`, `/risk`, `/healing`, `/capacity`, `/circuits`, `/golden-tests`, `/gates`, `/bundles`, `/evaluator`, `/integrations` |
| Bezpieczenstwo | `/auth`, `/roles`, `/notifications`, `/connectors`, `/security-scan` |

## Mapa UI do API

| UI | Glowny API prefix | Typowe akcje |
| --- | --- | --- |
| `/project-start` | `/api/v1/project-start` | preview, create, defaults, readiness, edge diagnose. |
| `/council-to-ksiega` | `/api/v1/council-to-ksiega` | convene, verdicts, deliberate, consolidate, generate book, finalize. |
| `/planning` | `/api/v1/planning` | assign models, synthesize skills, generate masterplan/test plan, cost, dry-run. |
| `/execution-start` | `/api/v1/execution-start` | runtime config, initialize, dispatch, phases 34-41, close. |
| `/funding` | `/api/v1/funding` | company profile, calls, ideas, matching, applications, submission, reports. |
| `/skills` | `/api/v1/skills` | register/create, execute, demand signal, catalog, runtime specs. |
| `/memory` | `/api/v1/memory` | kanon, evidence, index, kb, retrieval, self-model. |
| `/operator-mobile` | `/api/v1/mobile` | bind device, queue, decision, approve, reject. |
| `/orchestration/*` | `/api/v1/orchestration` | routing, council, auditor, fixer, dispatch, tests, teams. |
| `/test-center/*` | `/api/v1/test-center`, `/api/v1/testing` | suites, runs, release gate, simulation, auto-repair. |

## Route-only ryzyko

AEIS ma duzo stron, ktore renderuja jako dashboard. Produkcyjna dokumentacja traktuje route render jako osobny, slabszy dowod niz action freeze. Dla kazdej strony z akcja mutujaca wymagane jest:

- backend route 2X_PASS;
- frontend action 2X_PASS;
- blad sieci/500/403/timeout opisany i przetestowany;
- `204 No Content` obslugiwane bez falszywego JSON error;
- reload proof;
- brak bledow konsoli.

Priorytet dalszego zamykania: `/advisor`, `/planning`, `/masterplan`, `/source-of-truth`, `/ontology`, `/contracts`, `/templates-setup`, `/environments`.
