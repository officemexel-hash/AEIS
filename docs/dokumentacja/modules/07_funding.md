# Moduł: sylion.aeis.advisor.funding
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura modułu](#2-architektura-modułu)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje (gRPC RPCs / REST endpoints)](#4-funkcje-grpc-rpcs--rest-endpoints)
5. [Eventy](#5-eventy)
6. [Database tables](#6-database-tables)
7. [Przykład użycia](#7-przykład-użycia)
8. [Verification](#8-verification)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## R3.14 runtime update - Funding Autopilot i raportowanie

Ten plik historycznie opisuje `sylion.aeis.advisor.funding`. Po R3.14 aktywny runtime funding obejmuje rowniez pakiet `sylion.funding_autopilot` oraz ekran `/funding` w operator console.

### Stan zweryfikowany

| Obszar | Stan po R3.14 |
|---|---|
| Backend routes | `/api/v1/funding/*` w unified FastAPI runtime |
| Executive report | `GET /api/v1/funding/reports/executive` |
| Deadlines/alerts | `GET /api/v1/funding/deadlines`, `GET /api/v1/funding/alerts` |
| Application export | `POST /api/v1/funding/application/{application_id}/export` generuje paczke |
| Download export | `GET /api/v1/funding/application/{application_id}/export/{artifact_type}` dla `json`, `markdown`, `csv`, `review`, `docx`, `xlsx`, `pdf`, `zip` |
| XLSX | deterministyczny fallback OOXML, nie wymaga `openpyxl` |
| UI | `/funding` -> zakladka `Raporty`, Recharts pipeline/success/ROI/deadline pressure |
| CSV | klientowy eksport `funding-report.csv` z aktualnie zaladowanych danych |
| PDF/XLSX | pobierane z backendowego `FileResponse` dla wybranego wniosku |
| E-mail | operator-reviewed szkice `mailto` z alertow i terminow; brak automatycznej wysylki bez osobnej bramki |

### Dowody

- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/runtime_api_reporting_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/playwright_reporting_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/funding_reporting_desktop.png`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/funding_reporting_mobile.png`

### Reguly utrzymania

1. Nie dokumentowac eksportu XLSX jako zaleznosci od `openpyxl`; fallback jest czescia kontraktu.
2. Nie dokumentowac automatycznej wysylki e-mail jako wdrozonej. Obecnie wdrozone sa szkice do kontroli operatora.
3. Nie uzywac starego entrypointu `dashboard/start.py`; funding dziala w unified runtime.

---

## 1. Cel modułu

Moduł `sylion.aeis.advisor.funding` jest największym z modułów warstwy AEIS Advisor i odpowiada za **doradztwo finansowe** w obszarze grantów (publicznych, regionalnych, EU, prywatnych) dla idei projektowych zgromadzonych w IdeaVault. Centralna teza modułu (kluczowy *L1 insight* z manifestu): **każdy grant ma własny scoring profile** — ta sama firma i ta sama idea wygenerują różne wyniki dla różnych grantów. Z tego powodu funding łączy w jednej granicy transakcyjnej: katalog firm, katalog grantów, katalog uniwersalnych komponentów scoringowych, profile scoringowe per grant, historię scoringów, pulę partnerów konsorcjalnych, symulator what-if oraz miesięczny budżet badawczy w tokenach.

Moduł działa jako **opt-in**: domyślnie wyłączony. Operator aktywuje go preferencją `funding_advisor_enabled`; może też ograniczyć katalog grantów do listy państw (`funding_countries`) i ustawić własny limit miesięczny tokenów (`funding_token_budget_monthly`). Wewnątrz modułu wykonują się trzy kategorie operacji: (a) zarządzanie firmami i osobami (CRUD), (b) zarządzanie katalogiem grantów wraz z load-time profilami scoringowymi, (c) wykonywanie operacji analitycznych (scoring, matching idea↔grant, symulacja what-if, sugestie konsorcjum). Wszystkie operacje analityczne emitują eventy domenowe i logują użycie tokenów do `advisor_funding.research_logs`, gdzie egzekwowany jest twardy limit budżetu.

## 2. Architektura modułu

### Pliki w module

| Plik | Rola |
|---|---|
| `__init__.py` | Eksport publicznego API modułu (singleton `get_funding_service()`). |
| `service.py` | Fasada `AdvisorFundingService` — główny punkt wejścia. Inicjalizuje schemę, deleguje do submodułów, publikuje eventy. |
| `_models.py` | Dataclassy domenowe (`Company`, `GrantProgram`, `ScoringProfile`, `IdeaContext`, `SimulationScenario`, ...) + stałe (`UNIVERSAL_COMPONENT_IDS`, `DEFAULT_COMPONENT_WEIGHTS`, `DEFAULT_HARD_FLOORS`, `RESEARCH_PURPOSES`, `SIMULATION_MODES`). |
| `_db.py` | Warstwa persystencji PG-only. Operacje CRUD na schemacie `advisor_funding.*`. Seeds uniwersalne komponenty scoringowe przy pierwszym dostępie. |
| `company_manager.py` | Funkcje wysokopoziomowe nad firmami (`create_company`, `update_company`, `attach_person`, `list_companies`). |
| `grant_catalog.py` | Rejestracja grantów + automatyczne tworzenie domyślnego scoring profile (lub z `profile_overrides` operatora). |
| `card_builder.py` | Buduje *advisor card body* + *envelope* na potrzeby modułu engine. |
| `simulator.py` | Trzy tryby symulacji what-if: `static`, `dynamic`, `auto_generated`. |
| `token_budget.py` | Egzekwowanie miesięcznego budżetu tokenów badawczych (per operator). |
| `grpc_server.py` | Stub gRPC (czeka na codegen z `proto/funding.proto`). Lokalnie używa się `get_funding_service()`. |
| `scoring/calculator.py` | Główny obliczacz scoringu — pobiera profile, aplikuje komponenty, agreguje wynik ważony. |
| `scoring/components.py` | 7 funkcji scoringowych (eligibility, thematic_alignment, capacity, competitive_position, regional_fit, consortium_readiness, timeline_fit). Każda zwraca `(score 0–100, driving_factors)`. |
| `scoring/profile_loader.py` | Resolwer profili (po `profile_id` albo aktywny dla programu). `ensure_profile()` tworzy domyślny jeśli brak. |
| `scoring/llm_scorer.py` | Warstwa LLM judge (Etap 2) — refinuje wyjaśnienia. |
| `matcher/idea_to_grants.py` | Kierunek A: dla danej idei + firmy znajdź wszystkie pasujące granty (z kompatybilnością regionalną). |
| `matcher/grants_to_ideas.py` | Kierunek B: dla danego grantu + firmy + zbioru kandydujących idei znajdź najbardziej pasujące. |
| `matcher/gap_analyzer.py` | Analiza luk — które komponenty obniżają wynik i jak je domknąć. |
| `consortium/pool.py` | CRUD nad pulą partnerów konsorcjalnych. |
| `consortium/matcher.py` | Algorytm dopasowania partnerów do (grant, company). |

### Dependencies

**Wewnętrzne:**

- `sylion.aeis.advisor.engine` — fasada do której funding wysyła envelopes (przez `card_builder.build_funding_envelope`).
- `sylion.aeis.advisor.preferences` — opt-in toggle, country filter, override profili scoringowych.
- `sylion.aeis.advisor.pricing` — wyceny modeli LLM dla research operations.
- `sylion.aeis.advisor._db` — wspólny pooler PostgreSQL.
- `sylion.core.event_bus` / `sylion.core.event_backbone` — emisja eventów.

**Zewnętrzne:**

- `psycopg` (driver PG, używany przez `psycopg.rows.dict_row`).
- `pydantic` / `dataclasses` — modele.
- Standard library: `json`, `time`, `uuid`, `os`, `copy`, `threading`, `logging`.

### Storage

| Schema | Tabele | Cel |
|---|---|---|
| `advisor_funding` | `companies`, `company_persons`, `grant_programs`, `scoring_components`, `scoring_profiles`, `scoring_history`, `consortium_pool`, `research_logs` | Pełna persystencja danych funding. Schemat tworzony przez Alembic w `sylion/db/advisor_layer.sql` (rev. `20260425_0002_advisor_layer.py`). |

Manifest deklaruje także starsze nazwy SQLite (`advisor_funding_companies`, ...) — są to tylko fixtures testowe, produkcja używa schematu PG.

### Workers / threads / async loops

Funding nie posiada własnych pętli `async` ani workerów w Etap 1.

- `service.AdvisorFundingService` używa `threading.Lock` do synchronizacji singletonu i `attach_to_event_bus`.
- `get_funding_service()` jest *thread-safe* przez `_service_lock`.
- Operacje I/O (DB) są synchroniczne; asynchroniczność dochodzi przez warstwę API/gRPC.

## 3. Konfiguracja

### Environment variables

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `SYLION_ADVISOR_FUNDING_TOKEN_BUDGET_MONTHLY` | `100000` | Miesięczny limit tokenów badawczych per operator. Dotyczy logów `advisor_funding.research_logs`. Po przekroczeniu — `TokenBudgetExceeded`. |

### Preferencje operatora (przez `aeis.advisor.preferences`)

| Klucz | Typ | Domyślna | Znaczenie |
|---|---|---|---|
| `funding_advisor_enabled` | bool | `false` | Twardy włącznik modułu. Wymuszany w `is_enabled()`. |
| `funding_countries` | list[str] | `[]` | Filtruje katalog grantów do podanych krajów. |
| `funding_token_budget_monthly` | int | (env) | Override miesięcznego budżetu (czeka na pełną integrację). |

### Defaults — uniwersalne komponenty scoringowe

| Komponent | Waga domyślna (pkt) | Hard floor | Opis |
|---|---|---|---|
| `eligibility` | 30 | 50 | Formalne kryteria (legal form, MSME, branża, lokacja, wiek). |
| `thematic_alignment` | 20 | 0 | Dopasowanie tematu idei do tematu naboru. |
| `capacity` | 15 | 0 | Doświadczenie zespołu, budżet R&D, certyfikaty. |
| `competitive_position` | 10 | 0 | Pozycja konkurencyjna względem benchmarku. |
| `regional_fit` | 10 | 0 | Zgodność lokacji z wymaganiem regionalnym. |
| `consortium_readiness` | 10 | 0 | Gotowość konsorcjalna (jeśli wymagana). |
| `timeline_fit` | 5 | 0 | Czas do deadlinu naboru. |
| **Suma** | **100** | — | — |

> Hard floor `eligibility=50` oznacza: jeśli komponent eligibility uzyska <50 pkt, total score zostaje *zaczepiony* na <50 (`profile_floor_cap=49.0`) i emitowany jest event `eligibility_floor_breached`. Karta nie jest blokowana, ale w UI sygnalizuje "blokada formalna".

### Opcjonalne profile_overrides (load-time)

```yaml
# Operator-supplied per-grant overrides; weights are renormalised to 100.
profile_overrides:
  eligibility:
    weight: 50
    hard_floor: 60
  thematic_alignment:
    weight: 30
  capacity:
    weight: 20
```

Niewymienione komponenty są pomijane — profile-loader automatycznie skaluje wagi tak, by suma wynosiła 100.

## 4. Funkcje (gRPC RPCs / REST endpoints)

W Etap 1 moduł nie udostępnia jeszcze gRPC (czeka na proto codegen w `_generated/`). Wszystkie wywołania idą przez singleton `get_funding_service()` lub adaptery REST. Poniższe sygnatury odzwierciedlają stan public API w `service.py`.

### 4.1 `is_enabled(operator_id, project_id="") -> bool`

- Wejście: `operator_id` (str), `project_id` (str, opt).
- Wyjście: `True`/`False`.
- Side effects: brak.
- Errors: brak; gdy resolver preferencji niedostępny — fallback na lokalną pamięć.

### 4.2 `set_enabled(operator_id, project_id="", enabled: bool) -> None`

- Aktualizuje preferencję operatora oraz lokalną pamięć fallback.
- Emituje: `aeis.advisor.funding.module_enabled` lub `module_disabled`.

### 4.3 `country_filter / set_country_filter`

- Czyta/zapisuje preferencję `funding_countries`.
- `set_country_filter` emituje `aeis.advisor.funding.country_filter_changed`.

### 4.4 `create_company(operator_id, **kwargs) -> Company`

- Wymagane: `legal_name`, `country`.
- Opcjonalne: `legal_form`, `region`, `pkd_codes`, `is_msme`, `employee_count`, `annual_revenue_usd`, `founding_date`, `rd_budget_history`, `innovation_certifications`, ...
- Wpisuje rekord do `advisor_funding.companies`.
- Errors: `ValueError` przy niespójnych danych (rzadko, większość pól opcjonalna).

### 4.5 `update_company(company_id, patch: dict) -> Company | None`

- Akceptuje patch z dozwolonymi kluczami: `legal_name, legal_form, registration_number, tax_id, statistical_id, country, region, size_category, employee_count, annual_revenue_usd, founding_date, is_msme, description, pkd_codes, rd_budget_history, innovation_certifications`.
- Emituje (przyszłość): `aeis.advisor.funding.company_data_updated`.

### 4.6 `attach_person(company_id, full_name, role, ...) -> CompanyPerson`

- Dołącza osobę do firmy. Pola: `ownership_pct`, `experience_years`, `qualifications`, `team_role`, `is_kp` (key personnel).

### 4.7 `list_companies(operator_id) -> list[Company]`

- Zwraca firmy danego operatora posortowane po `created_at`.

### 4.8 `load_grant_manually(operator_id, display_name, source="custom", ...) -> tuple[GrantProgram, ScoringProfile]`

- Operator-initiated. Wymusza `is_user_loaded=True` i `loaded_by=operator_id`.
- Tworzy domyślny scoring profile (lub z `profile_overrides`).
- Emituje: `aeis.advisor.funding.grant_loaded`.
- Errors: `ValueError("unknown grant source")` przy nieprawidłowym `source`.

### 4.9 `register_grant(**kwargs) -> tuple[GrantProgram, ScoringProfile]`

- System-initiated rejestracja grantu (czeka na funding_autopilot.program_scanner).
- Argumenty: `display_name, source, country, region, program_code, managing_body, description, amount_min_usd, amount_max_usd, call_open_at, call_close_at, source_url, source_documents, custom_criteria, profile, profile_overrides`.
- Walidacja: `source in GRANT_SOURCES = ("pl_national", "pl_regional", "eu", "other_country", "private", "custom")`.

### 4.10 `list_grants(country=None, region=None) -> list[GrantProgram]`

- Listuje aktywne granty z opcjonalnym filtrem.

### 4.11 `compute_scoring(operator_id, company_id, idea: IdeaContext, program_id, profile_id="", triggering_event="manual_recalc") -> ScoringHistoryEntry`

- Główne RPC scoringu. Sekwencja:
  1. Sprawdza `is_enabled`. Brak — `RuntimeError("funding_advisor_disabled")`.
  2. Pobiera Company i Grant. Brak — `ValueError`.
  3. `token_budget.check_budget_or_raise(operator_id, 1500)` — `TokenBudgetExceeded` jeśli przekroczone.
  4. `record_usage(...)` z purpose=`scoring_assessment`.
  5. `scoring_calculator.compute_score(...)` — aplikuje 7 komponentów, agreguje, sprawdza floor.
  6. Persystuje do `scoring_history`.
  7. Emituje `aeis.advisor.funding.scoring_calculated` (zawsze) i `eligibility_floor_breached` (jeśli komponent eligibility breached).
- Errors: `RuntimeError("funding_advisor_disabled")`, `ValueError("unknown company_id")`, `ValueError("unknown program_id")`, `TokenBudgetExceeded`.

### 4.12 `get_scoring_history(company_id="", idea_id="", program_id="") -> list[dict]`

- Zwraca historię scoringów (do 50 rekordów, sort `computed_at DESC`). Filtry opcjonalne.

### 4.13 `list_eligible_grants(operator_id, company_id, idea: IdeaContext, countries=None) -> list[GrantMatch]`

- Kierunek A: idea → granty.
- Defaultuje `countries` do `country_filter` operatora; dodaje `EU` jeśli brak.
- Zwraca listę dopasowanych grantów posortowaną malejąco po `total_score`.
- Pomija granty regionalne, dla których `company.region != grant.region`.

### 4.14 `list_matching_ideas(operator_id, program_id, company_id, candidate_ideas: list[IdeaContext]) -> list[IdeaMatch]`

- Kierunek B: grant → idee.
- Iteruje po kandydujących ideach, score'uje każdą i sortuje.

### 4.15 `suggest_gap_closure(operator_id, company_id, idea, program_id) -> dict`

- Wykonuje scoring (delegacja do 4.11) i analizuje luki (`gap_analyzer.analyze_gaps`).
- Zwraca: `{"scoring": ScoringHistoryEntry, "gap_analysis": dict}`.

### 4.16 `suggest_consortium(operator_id, program_id, company_id, requirements=None) -> list[ConsortiumSuggestion]`

- Sprawdza `grant.custom_criteria.requires_consortium`. Jeśli `False` — zwraca `[]`.
- Wykonuje `_db.fetch_consortium_partners` z filtrami (entity_type, country, region).
- Jeśli pula pusta dla danego typu — zwraca *placeholder suggestion* z opisem "recommend external sourcing".
- Limit: domyślnie 5 sugestii.
- Emituje: `aeis.advisor.funding.consortium_suggested` (gdy `count > 0`).

### 4.17 `simulate(operator_id, company_id, idea, program_id, mode, operator_changes=None) -> list[SimulationScenario]`

- Trzy tryby:
  - `static` — 3 predefiniowane scenariusze (założ sp. z o.o., przenieś do PL-MZ, +10% R&D).
  - `dynamic` — pojedynczy scenariusz z `operator_changes={field: new_value}`.
  - `auto` — top-3 zmiany ważone deltą scoringu, ranked greedy.
- `token_budget.check_budget_or_raise(operator_id, 200)`.
- Emituje: `aeis.advisor.funding.simulation_completed`.
- Errors: `ValueError(f"unknown simulation mode: {mode}")`.

### 4.18 `build_funding_card(operator_id, company_id, idea, program_id, suggestion_type="FUNDING_HOW_TO_QUALIFY", include_simulations=True) -> dict`

- Złożony pipeline:
  1. `is_enabled` — jeśli `False`, zwraca `{}`.
  2. `suggest_gap_closure` → scoring + gap_analysis.
  3. `consortium.matcher.suggest_partners` — jeśli `requires_consortium`.
  4. `simulate(..., mode="static")` i `simulate(..., mode="auto")` — jeśli `include_simulations=True`.
  5. `card_builder.build_funding_card_body(...)`.
  6. `card_builder.build_funding_envelope(...)`.
- Zwraca: dict z polami `envelope_version, header, funding`.
- `suggestion_type` należy do `FUNDING_SUGGESTION_TYPES`: `FUNDING_GRANT_FIT`, `FUNDING_HOW_TO_QUALIFY`, `FUNDING_FORM_COMPANY`, `FUNDING_CHANGE_LEGAL_FORM`, `FUNDING_REGIONAL_RELOCATION`, `FUNDING_FIND_CONSORTIUM`, `FUNDING_ADJUST_IDEA_FOR_GRANT`, `FUNDING_DEADLINE_WARNING`, `FUNDING_GAP_CLOSURE_PLAN`, `FUNDING_SCOPE_ADJUSTMENT`.

### 4.19 `initiate_research(operator_id, query, scope="grant_discovery", projected_tokens=2000) -> str`

- Sprawdza budżet, rejestruje placeholder usage, emituje `research_initiated`.
- Zwraca `log_id`. Faktyczne wywołanie LLM/web research realizowane przez funding_autopilot (Etap 2).
- `scope` należy do `RESEARCH_PURPOSES = ("grant_discovery", "scoring_assessment", "consortium_search", "simulation")`.

### 4.20 gRPC Servicer — `FundingServicer` (sprint3)

Plik: `sylion/aeis/advisor/funding/grpc_server.py`. Cienka warstwa RPC mapująca proto na in-process `AdvisorFundingService`.

| RPC | Opis |
|-----|------|
| `ListGrants(ListGrantsRequest{country, region})` | Woła `list_grants(country, region)`. Zwraca `ListGrantsResponse{grants[]}`. |
| `ScoreProject(ScoreProjectRequest{operator_id, company_id, program_id, profile_id, idea, triggering_event})` | Woła `compute_scoring(...)`. Zwraca `ScoreProjectResponse{scoring}`. |
| `SimulateGrant(SimulateGrantRequest{operator_id, company_id, idea, program_id, mode, operator_changes})` | Woła `simulate(...)`. Zwraca `SimulateGrantResponse{scenarios[]}`. |

Wszystkie IdeaContext pola mapowane przez `_idea_from_request` (dict fallback dla Struct protobuf). Rejestracja: `register_funding_service(server, service=None) -> bool`.

---

## 5. Eventy

### Emitted

| Topic | Kiedy | Kluczowe pola payload |
|---|---|---|
| `aeis.advisor.funding.module_enabled` | Po `set_enabled(enabled=True)` | `operator_id, project_id` |
| `aeis.advisor.funding.module_disabled` | Po `set_enabled(enabled=False)` | `operator_id, project_id` |
| `aeis.advisor.funding.country_filter_changed` | Po `set_country_filter` | `operator_id, countries` |
| `aeis.advisor.funding.grant_loaded` | Po manualnym/automatycznym registrze grantu | `program_id, display_name, source, country` |
| `aeis.advisor.funding.grant_data_refreshed` | Po refresh danych grantu (Etap 2) | `program_id, fields_changed[]` |
| `aeis.advisor.funding.scoring_calculated` | Po każdym `compute_score` | `operator_id, company_id, program_id, scoring_id, total_score` |
| `aeis.advisor.funding.eligibility_floor_breached` | Gdy `eligibility < hard_floor` | `operator_id, company_id, program_id, scoring_id` |
| `aeis.advisor.funding.consortium_suggested` | Po `suggest_consortium` z `count>0` | `operator_id, program_id, count` |
| `aeis.advisor.funding.simulation_completed` | Po `simulate` | `operator_id, program_id, mode, count` |
| `aeis.advisor.funding.token_budget_threshold_crossed` | Gdy zużycie miesięczne > X% (Etap 2) | `operator_id, used, limit, ratio` |
| `aeis.advisor.funding.research_initiated` | Po `initiate_research` | `operator_id, scope, query, log_id` |
| `aeis.advisor.funding.research_completed` | Po zakończeniu research (Etap 2) | `log_id, tokens_used, cost_usd` |
| `aeis.advisor.funding.company_data_updated` | Po update firmy (Etap 2) | `company_id, fields_changed[]` |
| `aeis.advisor.funding.scoring_history_persisted` | Po insercie do `scoring_history` (Etap 2) | `scoring_id, computed_at` |

### Subscribed

| Topic | Reakcja |
|---|---|
| `aeis.idea.intake.completed` | Wywołanie `list_eligible_grants` — wstępne mapowanie idea→granty. |
| `aeis.idea.sot_drafted` | Recompute scoringu (idea zmieniła scope). |
| `aeis.idea.masterplan_created` | Aktualizacja consortium_readiness. |
| `aeis.advisor.funding.company_data_updated` | Recompute wszystkich aktywnych scoringów dla danej firmy. |
| `aeis.advisor.preferences.updated` | Reaguje na zmianę `funding_advisor_enabled` lub `funding_countries`. |

## 6. Database tables

Wszystkie tabele należą do schematu `advisor_funding`.

### 6.1 `companies`

| Kolumna | Typ | Opis |
|---|---|---|
| `company_id` | UUID PK | Stabilne ID firmy. |
| `operator_id` | TEXT | Właściciel (operator). |
| `is_own` | INT | `1` = własna firma operatora, `0` = obca (np. partner). |
| `legal_name` | TEXT | Nazwa prawna. |
| `legal_form` | TEXT | `sp_z_o_o`, `sa`, `limited_uk`, `fundacja`, `jdg`, ... |
| `country, region` | TEXT | Kraj (ISO-2) i region (np. `PL-MZ`). |
| `pkd_codes` | JSONB | Lista kodów PKD. |
| `size_category` | TEXT | `micro`, `small`, `medium`, `large`. |
| `employee_count, annual_revenue_usd` | INT/REAL | Skala działalności. |
| `is_msme, founding_date` | INT/TEXT | MŚP flag, data zał. |
| `rd_budget_history` | JSONB | Lista `{year, budget_usd}`. |
| `innovation_certifications` | JSONB | Lista certyfikatów. |
| `created_at, updated_at` | REAL | Timestampy. |

**Indexes:** `(operator_id)`, `(country, region)`.

### 6.2 `company_persons`

| Kolumna | Typ | Opis |
|---|---|---|
| `person_id` | UUID PK | — |
| `company_id` | FK → companies | — |
| `full_name, role, team_role` | TEXT | Nazwisko + rola formalna + rola w zespole. |
| `ownership_pct` | REAL | % własności. |
| `experience_summary, experience_years` | TEXT/INT | Doświadczenie. |
| `qualifications` | JSONB | Lista kwalifikacji `[{type, value}]`. |
| `is_kp` | INT | Key personnel — wymagany dla niektórych grantów. |

### 6.3 `grant_programs`

| Kolumna | Typ | Opis |
|---|---|---|
| `program_id` | UUID PK | — |
| `program_code, display_name` | TEXT | Kod programu i nazwa wyświetlana. |
| `source` | TEXT | jeden z `GRANT_SOURCES`. |
| `country, region` | TEXT | Zasięg. |
| `managing_body` | TEXT | Instytucja zarządzająca. |
| `amount_min_usd, amount_max_usd` | REAL | Widełki dofinansowania. |
| `call_open_at, call_close_at` | REAL (epoch) | Okno naboru. |
| `source_url, source_documents` | TEXT/JSONB | Materiały źródłowe. |
| `scoring_profile_id` | UUID FK → scoring_profiles | Wskaźnik aktywnego profilu. |
| `custom_criteria` | JSONB | Kryteria niestandardowe (np. `requires_consortium`, `required_legal_forms`, `requires_msme`, `required_pkd_prefixes`, `min_company_age_years`, `required_consortium_entity_types`). |
| `is_active, is_user_loaded, loaded_by` | INT/TEXT | Flagi i autor manualnego loadu. |

### 6.4 `scoring_components`

Katalog uniwersalnych komponentów. Seedowany przy starcie modułu (`init_funding_schema`).

| Kolumna | Typ | Opis |
|---|---|---|
| `component_id` | TEXT PK | jeden z `UNIVERSAL_COMPONENT_IDS`. |
| `display_name, description` | TEXT | — |
| `measurement_dsl` | JSONB | (Etap 2) DSL pomiaru. |
| `is_system` | INT | `1` dla wbudowanych. |

### 6.5 `scoring_profiles`

| Kolumna | Typ | Opis |
|---|---|---|
| `profile_id` | UUID PK | — |
| `program_id` | FK → grant_programs | — |
| `version` | INT | Wersjonowanie. |
| `components` | JSONB | Lista `[{component_id, weight, hard_floor}]`. |
| `custom_criteria` | JSONB | Kryteria specyficzne dla profilu. |
| `total_weight` | REAL | Zwykle 100.0 po renormalizacji. |
| `is_active` | INT | Tylko jeden aktywny per `program_id`. |

### 6.6 `scoring_history`

| Kolumna | Typ | Opis |
|---|---|---|
| `scoring_id` | UUID PK | — |
| `operator_id, company_id, idea_id, program_id, scoring_profile_id` | TEXT | Klucze referencyjne. |
| `total_score` | REAL | Końcowy wynik 0–100. |
| `component_breakdown` | JSONB | Lista `ComponentScore`. |
| `eligibility_floor_breached` | INT | `1` jeśli zaczepiony floor. |
| `triggering_event` | TEXT | `manual_recalc`, `idea_change`, `company_data_updated`, ... |
| `card_id, llm_judge_audit_id` | TEXT | Powiązania. |
| `computed_at` | REAL | epoch. |

**Sample queries:**

```sql
-- Top 5 najnowszych scoringów dla firmy
SELECT scoring_id, program_id, total_score, computed_at
FROM advisor_funding.scoring_history
WHERE company_id = $1
ORDER BY computed_at DESC
LIMIT 5;

-- Granty z najwyższym scoringiem dla idei
SELECT program_id, MAX(total_score) AS best_score
FROM advisor_funding.scoring_history
WHERE idea_id = $1
GROUP BY program_id
ORDER BY best_score DESC;

-- Detekcja eligibility breach w ostatnich 24h
SELECT * FROM advisor_funding.scoring_history
WHERE eligibility_floor_breached = 1
  AND computed_at >= EXTRACT(EPOCH FROM NOW()) - 86400;
```

### 6.7 `consortium_pool`

| Kolumna | Typ | Opis |
|---|---|---|
| `partner_id` | UUID PK | — |
| `display_name, entity_type` | TEXT | Nazwa + typ (`research_institution`, `industry_partner`, `university`, ...). |
| `country, region` | TEXT | — |
| `qualifications` | JSONB | Lista qualifications. |
| `contact_info` | JSONB | Email, telefon, www. |
| `added_by, notes` | TEXT | Pochodzenie i notatki. |

### 6.8 `research_logs`

| Kolumna | Typ | Opis |
|---|---|---|
| `log_id` | UUID PK | — |
| `operator_id` | TEXT | — |
| `research_purpose` | TEXT | jeden z `RESEARCH_PURPOSES`. |
| `prompt_tokens, response_tokens` | INT | Zużycie tokenów. |
| `cost_usd` | REAL | Koszt (jeśli model płatny). |
| `model_id` | TEXT | `claude-sonnet-4-6`, `qwen2.5:72b-instruct`, `stub`, ... |
| `external_research` | INT | `1` jeśli web/API research. |
| `related_card_id` | TEXT | Opcjonalne powiązanie z kartą. |
| `performed_at` | REAL | epoch. |

**Sample:**

```sql
-- Zużycie tokenów w bieżącym miesiącu per operator
SELECT operator_id,
       SUM(prompt_tokens + response_tokens) AS total_tokens,
       SUM(cost_usd) AS total_cost
FROM advisor_funding.research_logs
WHERE performed_at >= EXTRACT(EPOCH FROM date_trunc('month', NOW()))
GROUP BY operator_id
ORDER BY total_tokens DESC;
```

## 7. Przykład użycia

### 7.1 Bootstrap operator + firma + grant + scoring (Python)

```python
from sylion.aeis.advisor.funding.service import get_funding_service
from sylion.aeis.advisor.funding._models import IdeaContext

svc = get_funding_service()

# 1. Aktywuj moduł
svc.set_enabled(operator_id="op-1", enabled=True)

# 2. Utwórz firmę
company = svc.create_company(
    operator_id="op-1",
    legal_name="Acme R&D Sp. z o.o.",
    legal_form="sp_z_o_o",
    country="PL",
    region="PL-MZ",
    pkd_codes=["72.19.Z"],
    size_category="small",
    is_msme=True,
    employee_count=12,
    annual_revenue_usd=850_000,
    founding_date="2021-03-15",
    rd_budget_history=[
        {"year": 2024, "budget_usd": 60000},
        {"year": 2025, "budget_usd": 95000},
    ],
)

# 3. Dodaj key personnel
svc.attach_person(
    company_id=company.company_id,
    full_name="Jan Kowalski",
    role="CTO",
    ownership_pct=51.0,
    experience_years=14,
    qualifications=[{"type": "phd", "value": "AI"}],
    is_kp=True,
)

# 4. Załaduj grant manualnie
grant, profile = svc.load_grant_manually(
    operator_id="op-1",
    display_name="FENG 2.21 Innowacje",
    source="pl_national",
    country="PL",
    description="Wsparcie projektów R&D w obszarze AI",
    amount_max_usd=2_500_000,
    custom_criteria={
        "requires_msme": True,
        "required_legal_forms": ["sp_z_o_o", "sa"],
        "min_company_age_years": 2,
    },
    profile_overrides={
        "eligibility": {"weight": 40, "hard_floor": 60},
        "thematic_alignment": {"weight": 30},
        "capacity": {"weight": 20},
        "timeline_fit": {"weight": 10},
    },
)

# 5. Idea
idea = IdeaContext(
    idea_id="idea-001",
    title="Adaptive AEIS for Polish SMEs",
    description="Platform for AI-driven business advisory",
    domain="artificial_intelligence",
    keywords=["AI", "advisory", "automation"],
    rd_share_pct=0.7,
    target_country="PL",
    target_region="PL-MZ",
    expected_duration_months=24,
    target_budget_usd=1_500_000,
)

# 6. Scoring
entry = svc.compute_scoring(
    operator_id="op-1",
    company_id=company.company_id,
    idea=idea,
    program_id=grant.program_id,
)
print(f"Total score: {entry.total_score:.1f}")
for c in entry.component_breakdown:
    print(f"  {c.component_id}: {c.score:.1f} (waga {c.weight_in_grant})")
```

### 7.2 Symulacja dynamiczna

```python
# What-if: dodajemy 10% R&D budget
scenarios = svc.simulate(
    operator_id="op-1",
    company_id=company.company_id,
    idea=idea,
    program_id=grant.program_id,
    mode="dynamic",
    operator_changes={"rd_budget_history": "+10%"},
)
print(f"After +10% R&D: {scenarios[0].resulting_eligibility_score:.1f}")
```

### 7.3 Auto-generated scenarios (top 3)

```python
auto = svc.simulate(
    operator_id="op-1",
    company_id=company.company_id,
    idea=idea,
    program_id=grant.program_id,
    mode="auto",
)
for s in auto:
    delta = s.resulting_eligibility_score
    print(f"{s.label} -> {delta:.1f} pkt (cost {s.cost_to_implement.amount} USD)")
```

### 7.4 Build full funding card

```python
card = svc.build_funding_card(
    operator_id="op-1",
    company_id=company.company_id,
    idea=idea,
    program_id=grant.program_id,
    suggestion_type="FUNDING_HOW_TO_QUALIFY",
    include_simulations=True,
)
print(card["envelope_version"], card["header"]["card_id"])
```

### 7.5 curl REST (przez engine REST adapter — Etap 2)

```bash
curl -X POST http://127.0.0.1:8010/advisor/funding/score \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "operator_id": "op-1",
    "company_id": "c-001",
    "program_id": "g-001",
    "idea": {"idea_id": "idea-001", "title": "...", "domain": "ai"}
  }'
```

## 8. Verification

### 8.1 Pytest — golden tests

```bash
cd src/sylion-pipeline
pytest tests/aeis/advisor/funding/ -v
```

Wymagane testy z manifestu:

- `same_company_different_grants_different_scores`
- `eligibility_floor_breach_blocks_card`
- `regional_grant_filtered_by_company_region`
- `manual_grant_load_creates_profile_with_default_weights`
- `simulation_static_returns_predefined`
- `simulation_dynamic_recomputes_with_operator_changes`
- `simulation_auto_generated_returns_top_3_score_improving`
- `separate_token_budget_enforced`
- `opt_out_skips_module_entirely`

### 8.2 PostgreSQL — kontrola schematu

```bash
psql -h localhost -U sylion -d sylion -c "\dt advisor_funding.*"
psql -h localhost -U sylion -d sylion -c "SELECT * FROM advisor_funding.scoring_components;"
```

Powinno zwrócić 7 wierszy (uniwersalne komponenty).

### 8.3 Smoke test — service startup

```python
python -c "
from sylion.aeis.advisor.funding.service import get_funding_service
svc = get_funding_service()
print('OK', svc.list_grants())
"
```

### 8.4 Token budget check

```python
from sylion.aeis.advisor.funding.token_budget import (
    monthly_budget, usage_this_month, remaining_budget,
)
print('budget:', monthly_budget())
print('used  :', usage_this_month("op-1"))
print('remain:', remaining_budget("op-1"))
```

### 8.5 Event subscription test

```python
from sylion.core.event_bus import get_event_bus
bus = get_event_bus()
events = []
bus.subscribe("aeis.advisor.funding.*", lambda e: events.append(e))
# wywołaj operacje, sprawdź events
```

## 9. Troubleshooting

| Problem | Diagnoza | Fix |
|---|---|---|
| `RuntimeError: funding_advisor_disabled` przy `compute_scoring` | Operator nie aktywował modułu lub preferencja `funding_advisor_enabled=False`. | Wywołaj `svc.set_enabled(operator_id="op-1", enabled=True)` lub w UI Operator → Funding → Aktywuj. |
| `ValueError: unknown grant source` przy `register_grant` | `source` nie znajduje się w `GRANT_SOURCES`. | Użyj jednej z: `pl_national, pl_regional, eu, other_country, private, custom`. |
| `TokenBudgetExceeded` przy scoring/simulation | Operator wyczerpał miesięczny budżet tokenów. | Zwiększ `SYLION_ADVISOR_FUNDING_TOKEN_BUDGET_MONTHLY` w env, restart procesu, lub poczekaj do nowego miesiąca. |
| Wszystkie scoringi mają eligibility=0 | Custom criteria w grancie wymagają legal_form/MSME/PKD, których firma nie posiada. | Sprawdź `grant.custom_criteria` i wzbogać dane firmy lub usuń kryteria z grantu. |
| Region filter wycina wszystkie granty | Domyślnie `_region_compatible` wymaga dokładnego dopasowania `company.region == grant.region`. | Wybierz granty bez `region` (krajowe) lub dopasuj `company.region`. |
| Symulacja `auto` zwraca puste wyniki | Wszystkie kandydaty mają delta ≤ 0 (firma już idealnie dopasowana). | Service wówczas zwraca top-3 *bez* filtra delta>0. Upewnij się, że `_STATIC_TEMPLATES` są kompatybilne z firmą. |
| `eligibility_floor_breached=True` mimo poprawnego setup | Hard floor=50 dla eligibility nie został osiągnięty. | Sprawdź `breakdown[0].driving_factors`; często chodzi o brak `legal_form`, `is_msme=False` lub niepasujące `pkd_codes`. |
| `unknown company_id` przy `compute_scoring` | Company ID literówka lub firma nie zarejestrowana. | `svc.list_companies(operator_id)` aby sprawdzić istniejące. |
| `unknown program_id` | Grant nie istnieje lub został wyłączony (`is_active=0`). | `svc.list_grants(country=...)` aby sprawdzić listę aktywnych. |
| `consortium_suggested` zwraca placeholder bez nazwy | Pula `consortium_pool` jest pusta dla danego `entity_type`. | Dodaj partnerów przez `consortium.pool.add_partner(...)`. |
| Dziwny scoring po update firmy | Cache scoringu nie został unieważniony. | Wywołaj ponownie `compute_scoring` z `triggering_event="company_data_updated"`. |

## 10. Cross-references

### Powiązane moduły

- **`sylion.aeis.advisor.engine`** — odbiorca envelope'ów funding (przez `card_builder.build_funding_envelope`).
- **`sylion.aeis.advisor.preferences`** — opt-in toggle, country filter, profile overrides.
- **`sylion.aeis.advisor.pricing`** — wycena modeli LLM dla research operations.
- **`sylion.aeis.advisor.role_resolver`** — wybór modelu dla `purpose=funding_scoring` (gemini/claude ensemble).
- **`sylion.aeis.advisor.subscription`** — kapitalizacja kosztów funding research w usage report.
- **`funding_autopilot.program_scanner`** — automatyczne wczytywanie grantów do katalogu.
- **`funding_autopilot.grant_reporter`** — raporty końcowe.
- **`funding_autopilot.governance_bridge`** — wymagane HG dla D3+ kart funding (np. wysoki koszt, zmiana legal form).

### Architecture refs

- `docs/claude_parallel/aeis_advisor/00_architecture/01_advisor_card_schema.md` — pełen schema AdvisorCardEnvelope.
- `docs/claude_parallel/aeis_advisor/00_architecture/02_postgresql_schema.sql` — kanoniczny DDL.
- `docs/claude_parallel/aeis_advisor/00_architecture/03_module_manifests.md` — manifest funding (źródło prawdy).
- `docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md` — D3+ dla funding decisions.
- `docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md` — Evidence Pack dla zmian legal form, regionalnych itd.
- `docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md` — pełna taksonomia eventów funding.
- `docs/claude_parallel/aeis_advisor/_handoff/evidence_pack_b003_loc_budget.md` — uzasadnienie LOC budget exception (3500 LOC > 1500 default).

### Wewnątrz dokumentacji

- [`docs/dokumentacja/01_modul_aeis_advisor.md`](../01_modul_aeis_advisor.md) — wysoki poziom layer Advisor.
- [`docs/dokumentacja/modules/06_pricing.md`](./06_pricing.md) — pricing estimator używany przez funding research logs.
- [`docs/dokumentacja/modules/08_role_resolver.md`](./08_role_resolver.md) — routing dla `purpose=funding_scoring`.
- [`docs/dokumentacja/modules/12_mobile_gateway.md`](./12_mobile_gateway.md) — endpoint `/funding/deadlines` w gateway.
