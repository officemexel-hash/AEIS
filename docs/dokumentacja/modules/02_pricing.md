# Moduł `sylion.aeis.advisor.pricing`
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

Dokumentacja techniczna modułu cenowego warstwy doradczej AEIS (Etap 1).

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura modułu](#2-architektura-modułu)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje (gRPC RPC)](#4-funkcje-grpc-rpc)
5. [Eventy](#5-eventy)
6. [Tabele bazy danych](#6-tabele-bazy-danych)
7. [Przykład użycia](#7-przykład-użycia)
8. [Komendy weryfikacyjne](#8-komendy-weryfikacyjne)
9. [Troubleshooting](#9-troubleshooting)
10. [Powiązania](#10-powiązania)

---

## 1. Cel modułu

`sylion.aeis.advisor.pricing` jest jedynym kanałem cenowym warstwy doradczej. Moduł zarządza katalogiem providerów (Anthropic, OpenAI, Google, xAI, Z.AI, Moonshot, Ollama lokalnie, manual_table) i ich modeli, utrzymuje aktywną tabelę cen `pricing_tables` z atrybutem `is_assumption`, prowadzi append-only historię odświeżeń `pricing_history` i wystawia spójne estymacje kosztu z trzema źródłami: `assumption`, `profile`, `measured`. Każda estymacja wracająca do silnika doradczego zawiera flagę `is_assumption`, dzięki której karta AdvisorCard odpowiednio oznacza poziom pewności kosztu.

Moduł nie podejmuje decyzji biznesowych — odpowiada wyłącznie za fakty cenowe. Integruje się jednak z `sylion.aeis.advisor.preferences` przez `get_blocked_providers()`: provider zablokowany przez operatora znika z list `ListProviders`/`ListModels`, a `GetCost` natychmiast zwraca `assumption` z notatką `"Provider blocked by operator preferences"` zamiast wykonywać kalkulację. Dzięki temu blokady budżetowo-bezpieczeństwowe propagują się przez cały pipeline doradczy (rule_engine → estimator → karta), nie wymuszając duplikacji logiki w wyższych warstwach.

---

## 2. Architektura modułu

### 2.1. Pliki źródłowe

Wszystkie ścieżki podane są względem `src/sylion-pipeline/sylion/aeis/advisor/pricing/`.

| Plik | Rola |
| --- | --- |
| `service.py` | Klasa `PricingService` — fasada SDK lokalnego (8 metod publicznych) |
| `grpc_server.py` | `PricingServicer` mapujący 8 RPC na metody serwisu |
| `_db.py` | Czyste helpery SQL (psycopg connection pool przez `sylion.aeis.advisor._db.get_pool`) |
| `_models.py` | Dataclasses domenowe: `Source` (Enum), `Provider`, `Model`, `PricingTable`, `CostEstimate`, `PricingSnapshot` |
| `catalog.py` | Inicjalizacja katalogu, dynamiczna rejestracja adapterów, manual_table |
| `estimator.py` | Algorytm wyliczania kosztu per call (input + output + cache, kwantyzacja `0.000001`) |
| `refresher.py` | Orkiestracja `refresh_provider_pricing(provider_id)`, lista eventów wynikowych |
| `adapters/base.py` | `ProviderPricingAdapter` (abstract) + `FetchedPricing` |
| `adapters/anthropic_adapter.py` | Adapter Anthropic (live/assumption fallback) |
| `adapters/openai_adapter.py` | Adapter OpenAI |
| `adapters/google_adapter.py` | Adapter Google (Gemini) |
| `adapters/xai_adapter.py` | Adapter xAI |
| `adapters/zai_adapter.py` | Adapter Z.AI |
| `adapters/moonshot_adapter.py` | Adapter Moonshot |
| `adapters/ollama_adapter.py` | Adapter Ollama (lokalny, `is_local=true`) |
| `adapters/manual_table_adapter.py` | Adapter wczytujący tabelę z pliku JSON/YAML |
| `seed_data/default_providers.json` | Seed dla `initialize_catalog` (4 providery: anthropic, openai, google, ollama_local) |

### 2.2. Zależności wewnętrzne

- `sylion.aeis.advisor._db` — wspólny pool psycopg (PG produkcja + SQLite shim w testach).
- `sylion.aeis.advisor.preferences.service.get_preferences` — best-effort import dla blokad providerów (tryb `try/except` — moduł działa nawet bez preferencji).
- `sylion.core.event_backbone.get_event_backbone` — emisja eventów `aeis.advisor.pricing.*`.
- `sylion.core.event_bus.SylionEvent` — koperta eventu z `idempotency_key`.

### 2.3. Storage (PostgreSQL)

Schemat: **`advisor_pricing`**.

| Tabela | Charakter |
| --- | --- |
| `providers` | Katalog providerów (PK: `provider_id`) |
| `provider_models` | Modele per provider (PK: `model_id`, FK → providers) |
| `pricing_tables` | Cennik per model w czasie (PK: `pricing_id` UUID, `effective_until=NULL` = aktywne) |
| `pricing_history` | Append-only log każdej próby pobrania cennika (PK: `history_id` UUID) |

Sekwencja zmian: insert do `pricing_tables` z `effective_from=NOW()` zamyka poprzedni rekord (`UPDATE ... SET effective_until=NOW() WHERE effective_until IS NULL`) — implementuje to `_db.insert_pricing_table`. Każdy taki insert (oraz każda nieudana próba) zapisuje wpis w `pricing_history` zawierający źródło (`assumption`/`profile`/`measured`), `raw_response` (JSONB) lub `error_message`.

### 2.4. Workery / harmonogram

Moduł nie ma własnego workera. Refresh wywołuje:
- ręczna komenda operatora przez `RefreshPricing` (gRPC),
- skrypt CLI `python -m sylion.aeis.advisor.pricing.refresh_all` (jeśli dostępny w środowisku).

Inicjalizacja katalogu (`PricingService.initialize`) jest idempotentna (`upsert_provider`, `upsert_model` z `ON CONFLICT ... DO UPDATE`) i dopuszczalna przy każdym restarcie procesu.

---

## 3. Konfiguracja

### 3.1. Zmienne środowiskowe (klucze API)

Adaptery sięgają po klucze przez `initialize_pricing_catalog(api_keys=...)` lub bezpośrednio przez `os.environ`. Klucze nie są wymagane — adapter bez klucza zwraca `is_available()=False` i wszystkie ceny lądują jako `assumption`.

| Zmienna | Provider | Konsekwencja braku |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | anthropic | adapter assumption-only |
| `OPENAI_API_KEY` | openai | adapter assumption-only |
| `GOOGLE_API_KEY` lub `GEMINI_API_KEY` | google | adapter assumption-only |
| `XAI_API_KEY` | xai | adapter assumption-only |
| `ZAI_API_KEY` | zai | adapter assumption-only |
| `MOONSHOT_API_KEY` | moonshot | adapter assumption-only |
| `OLLAMA_BASE_URL` (default `http://localhost:11434`) | ollama_local | adapter zwraca measured zero-cost (lokalny) |

### 3.2. Pliki konfiguracyjne

| Plik | Opis |
| --- | --- |
| `seed_data/default_providers.json` | Lista 4 providerów seedowanych przy `initialize_catalog` |
| `manual_table_adapter` table_path | Ścieżka do JSON/YAML z manualną tabelą cen (zarządzana przez `register_manual_table`) |

### 3.3. Wartości domyślne

- `is_assumption=true` dla każdej ceny pochodzącej z providera, gdy `fetch_live_pricing` zwraca `None` lub adapter jest niedostępny.
- `cache_hit_tokens_usd_per_million` jest opcjonalne; brak danych traktujemy jak 0 USD/mln.
- `pricing_history` przechowuje wszystkie próby — także z `error_message` (to jedyna append-only ścieżka modułu).
- `effective_from` używa zegara aplikacji (`datetime.now(timezone.utc)`).
- Kwantyzacja kosztu: `Decimal("0.000001")`, `ROUND_HALF_UP` (estimator).

---

## 4. Funkcje (gRPC RPC)

Service: `sylion.aeis.advisor.pricing.v1.PricingService` (proto: `proto/pricing.proto`).

### 4.1. `GetCost(GetCostRequest) returns (CostEstimate)`

Zwraca estymację kosztu dla pojedynczego wywołania modelu.

**Wejście (`GetCostRequest`):**
- `string model_id` — wymagane, identyfikator modelu z `provider_models.model_id`,
- `int64 input_tokens` — tokeny wejściowe,
- `int64 output_tokens` — tokeny wyjściowe,
- `int64 cache_hit_tokens` — tokeny z cache (opcjonalne).

**Wyjście (`CostEstimate`):**
- `total_cost_usd`, `input_cost_usd`, `output_cost_usd`, `cache_cost_usd` (wszystkie jako `string` z `Decimal`),
- `source` (`SOURCE_ASSUMPTION` / `SOURCE_PROFILE` / `SOURCE_MEASURED`),
- `is_assumption`, `assumption_note`,
- `pricing_effective_from` (Timestamp),
- `pricing_id` (UUID, pusty gdy brak rekordu w `pricing_tables`).

**Side effects:**
- Emisja `aeis.advisor.pricing.assumption_used` gdy provider zablokowany przez preferencje **lub** estymacja jest oznaczona jako assumption (np. brak rekordu w `pricing_tables`).
- Brak modyfikacji bazy danych.

**Błędy:**
- Brak provider/model: zwracana estymacja `assumption` z `provider_id="unknown"`, `pricing_id=""`, kwoty zerowe.
- Provider zablokowany: estymacja zerowa z `assumption_note="Provider blocked by operator preferences"`.

### 4.2. `RefreshPricing(RefreshPricingRequest) returns (RefreshPricingResponse)`

Pobiera cennik dla wszystkich modeli wskazanego providera.

**Wejście:**
- `string provider_id` — wymagane,
- `bool force` — obecnie nie używane (parametr zarezerwowany).

**Wyjście:**
- `int32 refreshed_count`, `int32 failed_count`,
- `bool used_live` (true jeśli przynajmniej jeden model dostał `live_metadata_fetched`),
- `bool assumption_fallback` (true gdy wszystkie modele wpadły w assumption).

**Side effects:**
- Insert do `pricing_tables` (z zamknięciem poprzedniego aktywnego wiersza).
- Insert do `pricing_history` per próba — także w razie błędu.
- Emisja eventów: `aeis.advisor.pricing.refreshed`, `live_metadata_fetched`, `profile_updated`, `assumption_used`, `provider_unavailable`, `adapter_failed` (deduplikowane w obrębie wywołania).

**Błędy:**
- Brak adaptera dla `provider_id`: zwraca `refreshed_count=0`, `failed_count=0`, emit `provider_unavailable`.
- Adapter `is_available()=False`: każdy model dostaje wpis history `assumption`+`error="adapter_not_available"`.

### 4.3. `ListProviders(ListProvidersRequest) returns (ListProvidersResponse)`

**Wejście:**
- `bool active_only` — gdy true, zwraca wyłącznie providerów z `is_active=true`.

**Wyjście:**
- `repeated Provider providers` (`provider_id`, `display_name`, `is_local`, `is_active`, `metadata_url`).

**Side effects:**
- Wymusza `initialize()` (idempotentne seedowanie).
- Lista jest filtrowana przez `_get_blocked_providers()` (preferencje operatora).

### 4.4. `ListModels(ListModelsRequest) returns (ListModelsResponse)`

**Wejście:**
- `string provider_id` — opcjonalny filtr,
- `bool include_deprecated` — gdy false, ukrywa `is_deprecated=true`.

**Wyjście:**
- `repeated Model models` z polem `sample_cost_per_1k` (`CostEstimate` dla 1000 in + 1000 out).

**Side effects:**
- `initialize()`, filtrowanie po blokadach providerów.
- Każdy element wymaga jednego `get_cost()` w celu wyliczenia próbki — to widzi licznik kosztu API.

### 4.5. `RegisterAdapter(RegisterAdapterRequest) returns (RegisterAdapterResponse)`

**Wejście:**
- `string provider_id`, `string display_name`,
- `bool is_local`,
- `string metadata_url`,
- `string adapter_class_path` — pełna ścieżka modułu i klasy, np. `sylion.aeis.advisor.pricing.adapters.openai_adapter.OpenAIAdapter`.

**Wyjście:**
- `bool success`, `string error_message`.

**Side effects:**
- `import_module` + walidacja `isinstance(adapter, ProviderPricingAdapter)`.
- Upsert do `advisor_pricing.providers`.
- Rejestracja adaptera w globalnym registry (`adapters.register_adapter`).

**Błędy:**
- Brak modułu / klasy: `success=false`, `error_message=str(exc)`.
- Niewłaściwy typ: `success=false`, `error_message="adapter_class_path did not resolve to ProviderPricingAdapter"`.
- Brak segmentu modułu w ścieżce: `error_message="adapter_class_path must include module and class"`.

### 4.6. `GetPricingHistory(GetPricingHistoryRequest) returns (GetPricingHistoryResponse)`

**Wejście:**
- `string model_id`,
- `Timestamp since` — opcjonalny dolny próg `fetched_at`,
- `int32 limit` (default 50, gdy `0`).

**Wyjście:**
- `repeated PricingSnapshot snapshots`: `history_id`, `model_id`, `fetched_at`, `source`, `is_assumption`, `error_message`.

**Side effects:** brak (read-only).

### 4.7. `GetProvider(GetProviderRequest) returns (Provider)`

**Wejście:** `string provider_id`.

**Wyjście:** pełny `Provider` lub status `NOT_FOUND` (`grpc.StatusCode.NOT_FOUND`, detail `"Provider {id} not found"`).

### 4.8. `GetModel(GetModelRequest) returns (Model)`

**Wejście:** `string model_id`.

**Wyjście:** `Model` lub `NOT_FOUND`. Modele należące do zablokowanych providerów są traktowane jako `NOT_FOUND` (filtr w `PricingService.get_model`).

---

## 5. Eventy

### 5.1. Emitowane

Wszystkie eventy emituje `PricingService._emit` z `source_module="sylion.aeis.advisor.pricing"`. Klucz idempotencji: `f"{topic}:{provider_id_or_model_id_or_global}"`.

| Topic | Trigger | Payload (kluczowe pola) |
| --- | --- | --- |
| `aeis.advisor.pricing.refreshed` | Koniec `RefreshPricing` (sukces/porażka) | `provider_id` |
| `aeis.advisor.pricing.assumption_used` | Brak danych live, blokada providera, brak rekordu cennika | `provider_id`, `model_id`, `note`/`reason` |
| `aeis.advisor.pricing.provider_unavailable` | Adapter niezarejestrowany lub `is_available()=False` | `provider_id` |
| `aeis.advisor.pricing.adapter_failed` | Wyjątek w `fetch_live_pricing` | `provider_id` |
| `aeis.advisor.pricing.live_metadata_fetched` | `source="measured"` (adapter lokalny) | `provider_id` |
| `aeis.advisor.pricing.profile_updated` | `source="profile"` (publiczny cennik providera) | `provider_id` |

Manifest deklaruje 6 powyższych topic-ów (`aeis.advisor.pricing.json#events_emit`).

### 5.2. Subskrybowane

Brak. Manifest: `events_subscribe: []`. Pricing jest fasadą domain-only, refresh trafia do niej tylko explicit RPC.

---

## 6. Tabele bazy danych

Wszystkie definicje pochodzą z `docs/claude_parallel/aeis_advisor/00_architecture/02_postgresql_schema.sql` (sekcja `SCHEMA: advisor_pricing`).

### 6.1. `advisor_pricing.providers`

**Cel:** Katalog providerów modeli LLM.

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `provider_id` | TEXT PK | np. `anthropic`, `openai`, `ollama_local` |
| `display_name` | TEXT NOT NULL | Nazwa wyświetlana w UI |
| `is_local` | BOOLEAN, default false | true dla Ollama / on-prem |
| `is_active` | BOOLEAN, default true | Soft-disable bez usuwania rekordu |
| `metadata_url` | TEXT | URL cennika lub endpoint live API |
| `metadata_auth` | JSONB | Konfiguracja autoryzacji (szyfrowana w warstwie aplikacji) |
| `created_at`, `updated_at` | TIMESTAMPTZ | Audyt rekordu |

**Indeksy:** PK na `provider_id`.

**Append-only:** Tabela nie jest append-only — `upsert_provider` używa `ON CONFLICT DO UPDATE`. Audyt zmian providerów tracony jest na rzecz `pricing_history` per model.

**Sample query:**
```sql
SELECT provider_id, display_name, is_local
FROM advisor_pricing.providers
WHERE is_active
ORDER BY provider_id;
```

### 6.2. `advisor_pricing.provider_models`

**Cel:** Modele dostępne u providera.

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `model_id` | TEXT PK | np. `claude-sonnet-4-6`, `gpt-5` |
| `provider_id` | TEXT FK → `providers` | |
| `display_name` | TEXT NOT NULL | |
| `context_window` | INTEGER | tokeny |
| `is_local` | BOOLEAN | |
| `capabilities` | JSONB, default `'[]'` | `["code","long_context","vision"]` |
| `is_default_judge` | BOOLEAN | rola LLM-as-judge |
| `is_default_local` | BOOLEAN | preferowany fallback lokalny |
| `is_deprecated` | BOOLEAN | nie pokazuj domyślnie |
| `created_at` | TIMESTAMPTZ | |

**Indeksy:**
- PK `model_id`,
- `idx_provider_models_provider` na `provider_id`.

**Sample query:**
```sql
SELECT model_id, provider_id, context_window
FROM advisor_pricing.provider_models
WHERE is_default_judge = true AND is_deprecated = false;
```

### 6.3. `advisor_pricing.pricing_tables`

**Cel:** Aktywny cennik per model (`effective_until IS NULL`) plus historia kompletnych okresów.

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `pricing_id` | UUID PK, default `gen_random_uuid()` | |
| `model_id` | TEXT FK → `provider_models` | |
| `input_tokens_usd_per_million` | NUMERIC(20,8) | nullable gdy assumption-only |
| `output_tokens_usd_per_million` | NUMERIC(20,8) | |
| `cache_hit_tokens_usd_per_million` | NUMERIC(20,8) | |
| `source` | `advisor_engine.impact_confidence` | enum: `assumption` / `profile` / `measured` |
| `source_url` | TEXT | URL strony cennika |
| `is_assumption` | BOOLEAN, default false | |
| `assumption_note` | TEXT | |
| `effective_from` | TIMESTAMPTZ, default `now()` | |
| `effective_until` | TIMESTAMPTZ | NULL = aktywne |
| `created_at` | TIMESTAMPTZ | |

**Indeksy:**
- PK `pricing_id`,
- `idx_pricing_model_active` (`model_id`) WHERE `effective_until IS NULL`.

**Append-only?** Tabela jest semi-append-only: nowy rekord zamyka poprzedni (`UPDATE effective_until=NOW()`); nie kasujemy historycznych wierszy.

**Sample query (aktualny cennik dla modelu):**
```sql
SELECT pricing_id, source, input_tokens_usd_per_million, output_tokens_usd_per_million, is_assumption
FROM advisor_pricing.pricing_tables
WHERE model_id = 'claude-sonnet-4-6' AND effective_until IS NULL;
```

### 6.4. `advisor_pricing.pricing_history`

**Cel:** Append-only log każdej próby pobrania cennika (sukces lub błąd).

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `history_id` | UUID PK | |
| `model_id` | TEXT NOT NULL | |
| `fetched_at` | TIMESTAMPTZ, default `now()` | |
| `source` | `advisor_engine.impact_confidence` | enum |
| `raw_response` | JSONB | surowa odpowiedź adaptera |
| `resolved_pricing_id` | UUID FK → `pricing_tables` | NULL gdy nie zakończyło się insertem |
| `is_assumption` | BOOLEAN | |
| `error_message` | TEXT | NULL = sukces |

**Indeksy:**
- PK `history_id`,
- `idx_pricing_history_model` (`model_id`, `fetched_at DESC`).

**Append-only:** Tak. Brak triggerów w schemacie advisor_pricing — jedynym wykonywaczem zapisu jest `_db.insert_pricing_history`. Nie istnieją ścieżki `UPDATE`/`DELETE` w kodzie modułu.

**Sample query:**
```sql
SELECT fetched_at, source, is_assumption, error_message
FROM advisor_pricing.pricing_history
WHERE model_id = 'gpt-5'
ORDER BY fetched_at DESC
LIMIT 20;
```

---

## 7. Przykład użycia

### 7.1. SDK lokalne (Python)

```python
from decimal import Decimal
from sylion.aeis.advisor.pricing.service import PricingService

pricing = PricingService()
pricing.initialize()

estimate = pricing.get_cost("claude-sonnet-4-6", input_tokens=2000, output_tokens=800)
print(estimate.source.value, estimate.total_cost_usd, estimate.is_assumption)

# Refresh from a real provider
result = pricing.refresh_pricing("anthropic")
assert result["used_live"] or result["assumption_fallback"]

# List models a Council member can pick from
models = pricing.list_models(provider_id="anthropic", include_deprecated=False)
for model in models:
    sample = pricing.get_cost(model.model_id, 1000, 1000, 0)
    print(model.model_id, sample.total_cost_usd, sample.source.value)
```

### 7.2. Klient gRPC

```python
import grpc
from sylion.aeis.advisor._generated import pricing_pb2, pricing_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = pricing_pb2_grpc.PricingServiceStub(channel)

cost = stub.GetCost(pricing_pb2.GetCostRequest(
    model_id="gpt-5",
    input_tokens=1500,
    output_tokens=600,
    cache_hit_tokens=0,
))
print(cost.total_cost_usd, cost.is_assumption, cost.source)
```

### 7.3. Pytest fixture

```python
import pytest
from sylion.aeis.advisor.pricing.service import PricingService

@pytest.fixture
def pricing_service():
    service = PricingService(event_bus=None)
    service.initialize()
    return service

def test_assumption_when_unknown_model(pricing_service):
    estimate = pricing_service.get_cost("unknown-model", 100, 100)
    assert estimate.is_assumption is True
    assert estimate.total_cost_usd.is_zero()
```

### 7.4. Rejestracja manualnej tabeli cen

```python
from sylion.aeis.advisor.pricing.catalog import register_manual_table

ok, err = register_manual_table(
    provider_id="local_proxy",
    display_name="Internal Proxy",
    metadata_url="http://intranet/pricing",
    table_path="/var/sylion/pricing/local_proxy.json",
)
assert ok, err
```

---

## 8. Komendy weryfikacyjne

```bash
# 1. Liczność katalogu providerów / modeli
psql "$ADVISOR_PG_DSN" -c "SELECT count(*) FROM advisor_pricing.providers;"
psql "$ADVISOR_PG_DSN" -c "SELECT count(*) FROM advisor_pricing.provider_models;"

# 2. Aktualny cennik z assumption
psql "$ADVISOR_PG_DSN" -c "SELECT model_id, source, is_assumption FROM advisor_pricing.pricing_tables WHERE effective_until IS NULL;"

# 3. Append-only check (powinno zwrócić tylko inserty)
psql "$ADVISOR_PG_DSN" -c "SELECT count(*) FROM advisor_pricing.pricing_history;"

# 4. Pytesty modułu
pytest tests/aeis/advisor/pricing/ -q

# 5. Sanity gRPC
python -c "from sylion.aeis.advisor.pricing.service import PricingService; s = PricingService(); s.initialize(); print(len(s.list_providers()))"
```

---

## 9. Troubleshooting

| Problem | Diagnoza | Naprawa |
| --- | --- | --- |
| `GetCost` zwraca zawsze `assumption=true` | Brak rekordu w `pricing_tables` lub provider zablokowany | Uruchom `RefreshPricing(provider_id)`, sprawdź `aeis.advisor.preferences.get_blocked_providers` |
| `RefreshPricing` zwraca `provider_unavailable` | Brak adaptera dla providera | Wywołaj `RegisterAdapter` lub seeduj `seed_data/default_providers.json` |
| `adapter_failed` event przy każdym refresh | Klucz API nieobecny lub niepoprawny | Ustaw `*_API_KEY`, `pricing_history.error_message` zawiera szczegóły |
| `ListModels` ukrywa znany model | Provider zablokowany przez preferencje lub `is_deprecated=true` | Włącz `include_deprecated=true` lub odblokuj providera w preferencjach |
| `GetCost` zwraca `provider_id="unknown"` | Brak modelu w `provider_models` | `_db.upsert_model(...)` lub re-init katalogu |
| `RefreshPricing` zostawia poprzedni rekord aktywny | Wyjątek przed insertem zamykającym | Sprawdź `pricing_history.error_message`; rerun gdy adapter wróci |
| `Decimal` w kosztach traci precyzję | Klient czyta `string` jako `float` | Parsuj `total_cost_usd` przez `Decimal(str_value)` |
| Manifest ostrzega o brakującym kluczu | `events_emit` w manifeście vs. faktyczny topic | Patrz tabela 5.1 — wszystkie 6 emitowanych topics jest pokrytych |
| `pricing_id` pusty w `CostEstimate` | Estymacja jako assumption bez wpisu w `pricing_tables` | Oczekiwane — assumption nie tworzy rekordu pricing |

---

## 10. Powiązania

## 4.9 `effective_cost_estimate(operator_id, model_id, input_tokens, output_tokens, cache_hit_tokens=0) -> (CostEstimate, bool)` [sprint4]

> Dodana w sprint4 (commit `d6eb4d15`). Rozszerza `estimate_cost` o priorytetowe sprawdzenie aktywnej subskrypcji.

**Sygnatura:** `estimator.effective_cost_estimate(operator_id, model_id, input_tokens, output_tokens, cache_hit_tokens=0) -> tuple[CostEstimate, bool]`

**Logika (subscription-first):**

```python
quota = get_quota_status(operator_id, model_id)  # z quota_tracker
if quota and quota.has_quota:
    return (CostEstimate(total_cost_usd=Decimal("0"), source=Source.SUBSCRIPTION, ...), True)
else:
    return (estimate_cost(model_id, input_tokens, output_tokens, cache_hit_tokens), False)
```

**Wyjscie:** krotka `(CostEstimate, used_subscription: bool)`.
- `used_subscription=True` → koszt jest $0, `source=Source.SUBSCRIPTION`, `pricing_id=f"sub:{subscription_id}"`, `assumption_note` zawiera `remaining_tokens` i `remaining_usd`.
- `used_subscription=False` → standardowe wyjscie `estimate_cost` (PAYG z katalogiem cenowym).

**Nowe pole `Source.SUBSCRIPTION`** (enum `_models.py`):

| Source | Znaczenie |
|--------|-----------|
| `Source.ASSUMPTION` | Cena szacunkowa (brak danych live) |
| `Source.PROFILE` | Publiczny cennik providera |
| `Source.MEASURED` | Adapter live (Ollama localny) |
| `Source.SUBSCRIPTION` | Wywolanie pokryte aktywna subskrypcja — koszt $0 |

**Side effects:** brak (quota decremented przez `subscription.consume_quota` po faktycznym call, nie przy estymacji).

**Errors:** brak — jesli `quota_tracker` nie dostepny (import error), funkcja ciche-falluje na standardowy `estimate_cost`.

**Crossref:** `modules/10_subscription.md §10.5` — opis Quota Tracker + tabele `active_subscriptions`/`quota_usage`.

---

## 10. Powiązania

- [01_preferences.md](01_preferences.md) — `get_blocked_providers` propaguje blokady do `list_providers`/`list_models`/`get_cost`.
- [05_engine.md](05_engine.md) — silnik doradczy konsumuje `CostEstimate` w komponencie `confidence/components/pricing_quality` oraz w `card_builder/decision_card` (sekcja Money/Impact).
- [07_funding.md](07_funding.md) — moduł fundingu używa `pricing` do prognoz wydatków per provider.
- [30_event_taxonomy_full.md](30_event_taxonomy_full.md) — pełna lista eventów z payload schema.
- `docs/claude_parallel/aeis_advisor/00_architecture/02_postgresql_schema.sql` — DDL `advisor_pricing.*`.
- `docs/claude_parallel/aeis_advisor/00_architecture/03_advisor_card_schema.md` — pole `cost_breakdown` na karcie referencjonuje `pricing_id`.
