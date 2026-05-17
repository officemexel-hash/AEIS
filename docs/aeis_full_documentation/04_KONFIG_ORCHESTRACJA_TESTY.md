# Konfiguracja, orkiestracja i testy AEIS

## Spis tresci

1. [Konfiguracja systemu](#konfiguracja-systemu)
2. [Model Control i Council](#model-control-i-council)
3. [Orchestration J1-J9](#orchestration-j1-j9)
4. [Skills runtime](#skills-runtime)
5. [Memory i evidence](#memory-i-evidence)
6. [Test Center i golden tests](#test-center-i-golden-tests)
7. [Zasady testow jak czlowiek](#zasady-testow-jak-czlowiek)
8. [Runbook naprawy bledu](#runbook-naprawy-bledu)

## Konfiguracja systemu

Najwazniejsze powierzchnie konfiguracji:

| Powierzchnia | Route | Co konfiguruje |
| --- | --- | --- |
| Workspace defaults | `/workspace-defaults` | Defaulty projektu, autonomia, budzet, testy, acceptance. |
| AI Models | `/ai-models` | Providerzy, modele, klucze, testy providerow. |
| Budget | `/budget` | Limity kosztow modeli i runtime. |
| Secrets | `/secrets` | Klucze API i sekrety. Docelowo vault, nie plaintext. |
| Environments | `/environments` | Srodowiska lokalne, staging, theater, runtime constraints. |
| Templates | `/templates-setup` | Szablony projektow, dokumentow, pipeline. |
| Guards | `/coherence-guard`, `/cost-guard`, `/security-guard`, `/quality-guard`, `/provenance-guard` | Guard policies i thresholds. |
| Autonomy | `/autonomy` | Poziomy autonomii i blokady decyzji. |
| Policy | `/policy` | Globalne policy W19. |

W praktyce operator powinien zaczac od:

1. `/onboarding` - pierwszy wizard;
2. `/settings/advisor` - preferencje doradcy;
3. `/workspace-defaults` - defaulty projektow;
4. `/ai-models` i `/budget` - modele i koszt;
5. `/secrets` - klucze;
6. `/guards` albo konkretne guard pages;
7. `/project-start` - pierwszy projekt.

## Model Control i Council

AEIS ma kilka powierzchni modelowych:

- `/ai-models` - konfiguracja providerow i modeli;
- `/model-council` - widok rady modeli;
- `/orchestration/llm-routing` - routing modeli do zadan;
- `/orchestration/council-rules` - reguly rady;
- `/orchestration/conversations` - rozmowy i glosy modeli;
- `/budget` - koszt i limity.

Docelowa regola:

```text
Kazdy model uzyty w systemie musi istniec w ModelRegistry.
Council settings musza wskazywac ModelRegistry.model_id.
Routing musi przejsc przez BudgetEnforcer.
Key rotation musi propagowac sie do wszystkich planes.
```

Stan runtime:

- routing i council dzialaja w wybranych flow;
- planning phase 26 generuje model assignment;
- P4 wygenerowal `22` model rows;
- globalny jeden `ModelControlPlane` nadal jest celem architektonicznym, nie w pelni zamknietym faktem.

Screenshot:

![Model Council](screenshots/11_model_council.png)

## Orchestration J1-J9

Orchestration dzieli prace modeli i agentow na konkretne planes:

| J | Powierzchnia | Funkcja |
| --- | --- | --- |
| J1 | `/orchestration/llm-routing` | Wybor modeli, fallback, routing. |
| J2 | `/orchestration/council-rules` | Quorum, role, reguly rady. |
| J3 | `/orchestration/auditor` | Audytor i gate checks. |
| J4 | `/orchestration/fixer` | Naprawiacze i auto-repair. |
| J5 | `/orchestration/dispatch` | Rozdzial pracy, target worker/model. |
| J6 | `/orchestration/tests` | Katalog testow i golden tests. |
| J7 | `/orchestration/teams` | Zespoly agentow. |
| J8 | `/orchestration/event-map` | Event map i telemetry. |
| J9 | `/orchestration/conversations` | Rozmowy AI, decyzje, trace. |

W execution phase 33 dispatch control ma osobne operacje:

- `GET /api/v1/execution-start/projects/{id}/phase33/dispatch-control`;
- `POST /pause-dispatch`;
- `POST /resume-dispatch`;
- `POST /cancel-dispatch`.

Screenshot:

![Orchestration](screenshots/08_orchestration.png)

## Skills runtime

API skills ma kilka warstw:

| Warstwa | Endpointy | Znaczenie |
| --- | --- | --- |
| Health/list | `GET /api/v1/skills/health`, `GET /api/v1/skills` | Stan i lista. |
| Legacy register | `POST /api/v1/skills/register` | Rejestracja zgodna z poprzednim API. |
| Demand | `POST /demand/signals`, `GET /demand/signals`, `POST /demand/analyze` | Sygaly zapotrzebowania. |
| Executions | `POST /executions`, `GET /executions` | Uruchomienia skills. |
| Registry | `POST /skills`, `GET /skills`, `POST /skills/{id}/publish/deprecate/retire` | Lifecycle skill. |
| Catalog | `POST /catalog`, `GET /catalog`, `GET /catalog/recommend` | Katalog i rekomendacje. |
| Runtime | `GET /runtime/specs`, `POST /runtime/execute`, `GET /runtime/stats` | Runtime executor. |

Stan:

- create/execute/demand signal byly testowane jako `2X_PASS`;
- integracja z pipeline W10 i execution W16 jest nadal czesciowo rozdzielona;
- docelowo `SkillIntegrationLayer` powinien laczyc pipeline step, dispatch i demand signals.

Screenshot:

![Skills](screenshots/12_skills.png)

## Memory i evidence

API memory obejmuje:

| Obszar | Endpointy | Funkcja |
| --- | --- | --- |
| Obsidian connector | `/obsidian/connector`, `/obsidian/sync`, `/obsidian/status`, `/obsidian/graph` | Sync notatek i grafu. |
| Kanon | `/kanon/load`, `/kanon/sections`, `/kanon/search`, `/kanon/full-text` | Kanoniczna dokumentacja i wyszukiwanie. |
| Compact | `/compact`, `/compact/record`, `/compact/fidelity`, `/compact/stats` | Kompakcja i fidelity. |
| Evidence | `/evidence`, `/evidence/stats`, `/evidence-store`, `/evidence/{id}` | Dowody i store. |
| Index | `/index/sections`, `/index/search`, `/index/stats` | Indeks i search. |
| KB | `/kb/sources`, `/kb/query`, `/kb/stats` | Knowledge base sources. |
| Retrieval | `/retrieval`, `/retrieval/context` | Retrieval context. |
| Self-model | `/self-model/*` | Model wiedzy o systemie. |
| Stats/recent | `/stats`, `/recent` | Podsumowanie memory. |

Regola docelowa:

```text
Kazdy wynik memory search ma project_id, provenance, evidence_id i permission context.
Per-project DB moze byc read view, ale nie primary write source.
```

Stan:

- UI `/memory` renderuje i ma screenshot;
- API memory jest szerokie;
- globalny jeden write plane pozostaje luka architektoniczna.

Screenshot:

![Memory](screenshots/13_memory.png)

## Test Center i golden tests

Glowna powierzchnia:

- `/test-center`;
- `/test-center/dashboard`;
- `/test-center/catalog`;
- `/test-center/human-lab`;
- `/test-center/no-mock-scan`;
- `/test-center/release-gate`;
- `/test-center/simulation`;
- `/test-center/theater`;
- `/test-center/truth-alignment`;
- `/golden-tests`.

Testy w AEIS dziela sie na:

| Poziom | Co obejmuje |
| --- | --- |
| L1 | Unit tests i izolowane funkcje. |
| L2 | Integracje API/service. |
| L3 | E2E dashboard/API. |
| L4 | Performance/load. |
| L5 | Human-like UI scenarios, klikane przez operatora lub automaty browser. |

Screenshot:

![Test Center](screenshots/06_test_center.png)

## Zasady testow jak czlowiek

Kazdy test dashboardu powinien udowodnic:

- co operator widzi;
- co operator klika;
- jakie dane wpisuje;
- jaka odpowiedz backendu powstaje;
- czy stan trwa po reloadzie;
- czy po drugim przebiegu wynik jest taki sam;
- czy konsola przegladarki jest bez bledow.

Minimalny protokol:

```text
1. Otworz ekran.
2. Sprawdz health/API status.
3. Wpisz dane jak czlowiek.
4. Kliknij jedna akcje.
5. Sprawdz UI po akcji.
6. Sprawdz API lub stan projektu.
7. Odswiez ekran.
8. Powtorz pass.
9. Zapisz screenshot, project_id, endpointy i wynik.
```

## Runbook naprawy bledu

```text
ERROR -> STOP FLOW
  -> opisz blad
  -> znajdz przyczyne w UI/API/logach
  -> napraw minimalnie
  -> uruchom lint/build/test adekwatny do zmiany
  -> wykonaj PASS 1
  -> wykonaj PASS 2
  -> zapisz evidence
  -> oznacz frozen
  -> przejdz dalej
```

Nie wolno:

- zamrazac po samym toascie;
- zamrazac po samym `200`;
- automatycznie retry'owac mutujacych `POST` bez idempotency key;
- wykonywac realnego external submit/deploy bez Human Gate;
- mieszac danych projektow w memory/search;
- ignorowac bledow konsoli.
