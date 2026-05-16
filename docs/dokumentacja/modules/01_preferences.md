# Moduł: sylion.aeis.advisor.preferences
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

## Spis treści

1. [Cel modułu](#1-cel-modulu)
2. [Architektura modułu](#2-architektura-modulu)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje (gRPC RPCs)](#4-funkcje-grpc-rpcs)
5. [Eventy](#5-eventy)
6. [Database tables](#6-database-tables)
7. [Przykład użycia](#7-przyklad-uzycia)
8. [Verification](#8-verification)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## 1. Cel modułu

Moduł `sylion.aeis.advisor.preferences` jest fundamentem warstwy AEIS Advisor odpowiedzialnym za przechowywanie, rozwiązywanie i audytowanie preferencji operatora. Stanowi pojedyncze źródło prawdy dla decyzji typu "co operator wolałby otrzymać" w kartach rekomendacji oraz dla flag bezpieczeństwa w stylu `blocked_providers`, `autonomy_level`, `cost_ceilings`. Wszystkie pozostałe moduły warstwy advisor (engine, pricing, history, actions, mobile_gateway) konsultują te preferencje, aby dopasować swoje wyjścia do indywidualnego operatora.

Moduł realizuje preferencje w trójwymiarowej macierzy `(user_id × project_type × project_domain)` z kaskadą fallback (specific → type_only → domain_only → user_default → system_default), wprowadza rozróżnienie na "soft learning" (automatyczne dopasowanie po N akceptacjach z rzędu) oraz "hard change" (zmiana wymagająca jawnego kliknięcia operatora dla flag oznaczonych `is_hard_change=true`), zapewnia wieczysty append-only audyt zmian, a także udostępnia katalogi domen (14 bazowych + custom), typów projektów (8 bazowych + custom) i kluczy preferencji (16 systemowych z value_schema i defaultami).

---

## 2. Architektura modułu

### 2.1 Pliki w module

Wszystkie ścieżki względne do `src/sylion-pipeline/sylion/aeis/advisor/preferences/`.

| Plik | Rola |
|---|---|
| `__init__.py` | Eksportuje publiczne nazwy: `PreferencesService`, `get_preferences_service`, `get_preferences`, `reset_preferences_service`. |
| `_models.py` | Dataclasses i enumy używane wewnątrz modułu: `ResolutionLevel`, `PreferenceRow`, `ResolvedPreference`, `CatalogEntry`, `PreferenceKeyMetadata`, `AuditRow`, `HardChangeRequest`. |
| `_db.py` | Surowe zapytania SQL do PostgreSQL: `get_preference_row`, `list_preferences`, `upsert_preference`, `delete_preference`, `clear_preference_key_for_user`, `get_catalog_entries`, `add_custom_catalog_entry`, `get_preference_key_meta`, `get_system_default`, `insert_audit_row`, `list_audit_rows`. Używa puli `sylion.aeis.advisor._db.get_pool()`. |
| `service.py` | Synchroniczna fasada `PreferencesService` z lock'ami, integracją z `EventBackbone`, oraz publiczne API biznesowe (`get_effective`, `set_preference`, `reset_preference`, `disable_preference`, `list_preferences`, `get_audit`, `soft_learning_tick`, `request_hard_change`, `confirm_hard_change`, `get_catalog`, `add_custom_catalog_entry`, `get_blocked_providers`). |
| `resolver.py` | Logika kaskady czterech poziomów (`resolve_effective`, `get_explicit`, `find_most_specific_existing_level`). |
| `catalog.py` | Wrappery na `_db` udostępniające dataclasses katalogu: `list_catalog`, `add_custom_entry`, `get_preference_key_metadata`. |
| `learning.py` | Soft learning (zapisuje wartość na najbardziej specyficznym istniejącym poziomie) + zarządzanie pendingowymi hard-change requestami w pamięci (`_PENDING`, `request_hard_change`, `confirm_hard_change`, `count_pending_for_user`, `apply_soft_learning`, `reset_pending_requests`). |
| `audit.py` | Append-only audyt: `log_change`, `get_history`. |
| `grpc_server.py` | Servicer gRPC `PreferencesServicer` mapujący proto na metody serwisu, plus `register_preferences_service(server, service)`. |

### 2.2 Dependencies

Wewnętrzne (`sylion.*`):
- `sylion.aeis.advisor._db` — pula PostgreSQL (`get_pool`).
- `sylion.aeis.advisor._generated.preferences_pb2` / `preferences_pb2_grpc` — wygenerowane stuby gRPC.
- `sylion.core.event_backbone.get_event_backbone` — szyna zdarzeń.
- `sylion.core.event_bus.SylionEvent` — typ zdarzenia.

Zewnętrzne (PyPI):
- `psycopg` (driver PostgreSQL używany przez wspólną pulę).
- `grpcio`, `protobuf`, `google.protobuf.json_format` (Parse/MessageToDict).

Manifest (`aeis.advisor.preferences.json`) deklaruje `depends_on: []` — moduł nie ma twardych zależności od innych modułów advisora; jest fundamentem.

### 2.3 Storage

| Schema PostgreSQL | Tabele |
|---|---|
| `advisor_preferences` | `preferences`, `preferences_audit`, `project_domain_catalog`, `project_type_catalog`, `preference_key_catalog` |

Append-only enforcement na `preferences_audit` (trigger `preferences_audit_no_update` + `preferences_audit_no_delete`).

### 2.4 Workers / threads / async loops

Moduł pracuje synchronicznie. Singletony używają `threading.Lock()`:
- `service._lock` — chroni krytyczną sekcję upsert + audit + emit zdarzenia w `set_preference`/`reset_preference`/`disable_preference`.
- `learning._PENDING_LOCK` — chroni słownik pendingowych żądań hard-change w pamięci.
- `service._lock` (singleton-level) — chroni inicjalizację globalnego `_service`.

Brak osobnych wątków, brak pętli `asyncio` wewnątrz modułu. Konsumenci eventów (np. `aeis.advisor.history.learning_signal_emitted`) są obecnie obsługiwani na żądanie przez `soft_learning_tick(user_id=...)`, którą wywołuje warstwa wyższa (np. CLI lub scheduler).

---

## 3. Konfiguracja

### 3.1 Environment variables

Moduł nie czyta bezpośrednio `os.environ`. Wszystkie zmienne środowiskowe konsumuje wspólna pula `sylion.aeis.advisor._db`.

| Zmienna | Default | Opis |
|---|---|---|
| `SYLION_PG_DSN` | `postgresql://sylion:sylion@localhost:5432/sylion` | DSN bazy używanej przez pulę advisor. |
| `SYLION_PG_POOL_MIN` | `1` | Minimalna liczba połączeń w puli. |
| `SYLION_PG_POOL_MAX` | `10` | Maksymalna liczba połączeń. |

### 3.2 Config files

Moduł nie posiada własnych plików konfiguracyjnych. Inicjalne dane (14 domen, 8 typów, 16 kluczy preferencji z defaultami) są seedowane przez migrację Alembica `20260425_0002_advisor_layer.py` poprzez instrukcje `INSERT INTO ... VALUES ...` w migracji.

### 3.3 Defaults (16 systemowych preference keys)

| preference_key | Default | is_hard_change | Schema |
|---|---|---|---|
| `autonomy_level` | `"suggest"` | true | enum: manual, suggest, auto |
| `cost_sensitivity` | `"medium"` | false | enum: low, medium, high |
| `preferred_providers` | `[]` | false | array of strings |
| `runtime_strategy` | `"local_only"` | true | enum: local_only, local_plus_vps, hybrid, vps_only |
| `approval_timeout_behavior` | `"hold"` | true | enum: auto_approve, escalate, hold |
| `council_size` | `5` | false | integer 1..11 |
| `budget_thresholds` | `{}` | false | object |
| `quality_speed_cost` | `{"quality":0.4,"speed":0.3,"cost":0.3}` | false | object weights |
| `trusted_providers` | `[]` | true | array of provider IDs |
| `blocked_providers` | `[]` | true | array of provider IDs |
| `llm_judge_routing_override` | `{}` | false | object per-risk-level |
| `cost_ceilings` | `{"low":0.10,"medium":0.40,"high":1.60,"critical":6.00}` | false | object USD per call |
| `funding_advisor_enabled` | `false` | true | boolean |
| `funding_countries` | `[]` | true | array (hierarchical) |
| `funding_token_budget_monthly` | `100000` | false | integer ≥0 |
| `meta_recommendations_enabled` | `false` | true | boolean |

Pełna definicja w `02_postgresql_schema.sql` (sekcja `advisor_preferences.preference_key_catalog`).

---

## 4. Funkcje (gRPC RPCs)

Servicer: `sylion.aeis.advisor.preferences.grpc_server.PreferencesServicer`. Pakiet proto: `sylion.aeis.advisor.v1`. Plik wygenerowany: `sylion/aeis/advisor/_generated/preferences_pb2*.py`.

### 4.1 GetEffective

```proto
rpc GetEffective(GetEffectiveRequest) returns (PreferenceValue);
```

| Pole wejścia | Typ | Opis |
|---|---|---|
| `user_id` | string (UUID) | ID operatora. |
| `project_type` | string | Typ projektu (np. `production`); pusty string traktowany jako wildcard. |
| `project_domain` | string | Domena (np. `funding`); pusty string = wildcard. |
| `preference_key` | string | Klucz preferencji (np. `autonomy_level`). |

Output: `PreferenceValue` z polami: `user_id`, `project_type`, `project_domain`, `preference_key`, `value_json` (`google.protobuf.Value`), `set_by`, `created_at`, `updated_at`, `resolution_level` (enum: SPECIFIC, TYPE_ONLY, DOMAIN_ONLY, USER_DEFAULT, SYSTEM_DEFAULT).

Side effects: brak (read-only).

Errors: brak — gdy nic nie znaleziono w żadnym poziomie kaskady, zwraca wartość systemowego defaultu z `preference_key_catalog.default_value`.

### 4.2 GetExplicit

```proto
rpc GetExplicit(GetExplicitRequest) returns (PreferenceValue);
```

Identyczne wejście jak `GetEffective`. Różnica: nie wykonuje kaskady — pyta dokładnie podany `(user_id, project_type, project_domain, preference_key)`.

Errors:
- `NOT_FOUND` — z details `preference_not_found`, gdy nie ma wiersza explicit dla tego trójkąta.

### 4.3 Set

```proto
rpc Set(SetRequest) returns (SetResponse);
```

| Pole wejścia | Typ | Opis |
|---|---|---|
| `user_id` | string (UUID) | Operator. |
| `project_type` | string | Wymiar; pusty = wildcard. |
| `project_domain` | string | Wymiar; pusty = wildcard. |
| `preference_key` | string | Klucz. |
| `value_json` | `google.protobuf.Value` | Nowa wartość. |
| `set_by` | string | `user`, `soft_learning`, `system`, `wizard`. Default `user`. |
| `reason` | string | Opcjonalny powód do audytu. |

Output `SetResponse`: `success`, `requires_hard_confirmation` (true gdy klucz `is_hard_change=true`), `hard_change_request_id`, `error_message`.

Side effects:
- INSERT/UPDATE w `advisor_preferences.preferences`.
- INSERT w `advisor_preferences.preferences_audit` (`change_type='INSERT'` lub `'UPDATE'`).
- Emisja `aeis.advisor.preferences.created` lub `aeis.advisor.preferences.updated` (gdy zapis przeszedł).
- Gdy klucz to hard-change i `bypass_hard_check=false`: tworzy pendingowy request w pamięci i emituje `aeis.advisor.preferences.hard_change_requested` zamiast zapisu.

Errors: błędy bazy mapują się na `INTERNAL`. Brak walidacji `value_schema` (TODO w MVP).

### 4.4 Reset

```proto
rpc Reset(ResetRequest) returns (ResetResponse);
```

Wejście: `user_id`, `project_type`, `project_domain`, `preference_key`, `reason`.

Output: `ResetResponse(success, error_message)`.

Side effects:
- DELETE z `advisor_preferences.preferences`.
- INSERT w `preferences_audit` z `change_type='RESET'`.
- Emisja `aeis.advisor.preferences.reset`.

Errors: gdy nie ma wiersza, `success=false`, `error_message="preference_not_found"`.

### 4.5 Disable

```proto
rpc Disable(DisableRequest) returns (DisableResponse);
```

Wejście: `user_id`, `preference_key`, `reason`. Usuwa wszystkie poziomy explicit dla tego klucza i operatora.

Output: `DisableResponse(success=true, levels_cleared)`.

Side effects:
- DELETE wszystkich wierszy `(user_id, *, *, preference_key)`.
- Po jednym INSERT w `preferences_audit` (`change_type='DELETE'`) na każdy usunięty wiersz.
- Emisja `aeis.advisor.preferences.disabled`.

### 4.6 List

```proto
rpc List(ListRequest) returns (ListResponse);
```

Wejście: `user_id`, `filter_project_type`, `filter_project_domain`, `filter_preference_key`. Filtry pust = bez ograniczenia.

Output: `ListResponse{ preferences: repeated PreferenceValue }` posortowane po `(preference_key, project_type NULLS LAST, project_domain NULLS LAST)`.

Side effects: brak.

### 4.7 GetAudit

```proto
rpc GetAudit(GetAuditRequest) returns (GetAuditResponse);
```

Wejście: `user_id`, `since` (timestamp), `limit` (default 100), `filter_preference_key`.

Output: `GetAuditResponse{ entries: repeated AuditEntry }` zwracane DESC po `changed_at`.

Side effects: brak.

### 4.8 SoftLearningTick

```proto
rpc SoftLearningTick(SoftLearningTickRequest) returns (SoftLearningTickResponse);
```

Wejście: `user_id`. Pobiera `unapplied` learning_signals z `sylion.aeis.advisor.history.service`, dla każdego (poza `hard_change_status='pending'`) wywołuje `apply_soft_learning` zapisując value dedukowany z signal_type/proposed_value (mapping w `_signal_value`: `card_rejection→"high"`, `card_acceptance→"low"`, fallback `signal_strength`).

Output: `SoftLearningTickResponse(applied_count, pending_hard_confirmations, applied_preference_keys)`.

Side effects:
- INSERT/UPDATE w `preferences` (na najbardziej specyficznym istniejącym poziomie).
- INSERT w `preferences_audit` z `set_by='soft_learning'`.
- Brak emisji `created`/`updated` przy soft-learning (różne od `set_preference`).

### 4.9 RequestHardChange

```proto
rpc RequestHardChange(RequestHardChangeRequest) returns (RequestHardChangeResponse);
```

Wejście: `user_id`, `project_type`, `project_domain`, `preference_key`, `proposed_value`, `source_card_id`, `rationale`.

Output: `RequestHardChangeResponse(request_id, expires_at)`. TTL = 30 minut.

Side effects:
- Wpis w pamięci `_PENDING[request_id]`.
- Emisja `aeis.advisor.preferences.hard_change_requested`.

### 4.10 ConfirmHardChange

```proto
rpc ConfirmHardChange(ConfirmHardChangeRequest) returns (ConfirmHardChangeResponse);
```

Wejście: `request_id`, `operator_signature`, `confirmed`.

Output: `ConfirmHardChangeResponse(success, error_message, applied_value)`.

Side effects (gdy `confirmed=true`):
- Wewnętrznie wywołuje `set_preference(..., bypass_hard_check=True)`.
- INSERT/UPDATE w `preferences`, INSERT w `preferences_audit` z `reason='hard_change_confirmed:<request_id>'`.
- Emisja `aeis.advisor.preferences.hard_change_confirmed`.

Errors:
- `request_not_found` — request_id nie istnieje.
- `request_expired` — minęło TTL 30 minut.

### 4.11 GetCatalog

```proto
rpc GetCatalog(GetCatalogRequest) returns (GetCatalogResponse);
```

Wejście: `catalog_type` (enum: `CATALOG_TYPE_PROJECT_DOMAIN`, `CATALOG_TYPE_PROJECT_TYPE`, `CATALOG_TYPE_PREFERENCE_KEY`), `include_custom`.

Output: lista `CatalogEntry{entry_id, display_name, description, is_system, is_immutable, metadata_json}`. Dla `preference_key` `metadata_json` zawiera `value_schema`, `default_value`, `is_hard_change`.

### 4.12 AddCustomCatalogEntry

```proto
rpc AddCustomCatalogEntry(AddCustomCatalogEntryRequest) returns (AddCustomCatalogEntryResponse);
```

Wejście: `catalog_type`, `entry_id` (musi zaczynać się od `custom:`), `display_name`, `description`, `created_by`.

Output: `AddCustomCatalogEntryResponse(success, error_message, entry)`.

Errors:
- `invalid_catalog_entry` — gdy `entry_id` nie zaczyna się od `custom:` lub `catalog_type=preference_key` (nie wspiera dynamicznych kluczy).

Side effects (po sukcesie):
- INSERT do `project_domain_catalog` lub `project_type_catalog`.
- Emisja `aeis.advisor.preferences.catalog_extended`.

---

## 5. Eventy

### 5.1 Eventy emitowane

| Topic | Kiedy emitowany | Payload (klucze) |
|---|---|---|
| `aeis.advisor.preferences.created` | Pierwszy explicit insert w `set_preference` | `user_id`, `project_type`, `project_domain`, `preference_key` |
| `aeis.advisor.preferences.updated` | Update istniejącego wiersza | jw. |
| `aeis.advisor.preferences.reset` | Po `reset_preference` | jw. |
| `aeis.advisor.preferences.disabled` | Po `disable_preference` | `user_id`, `preference_key`, `levels_cleared` |
| `aeis.advisor.preferences.hard_change_requested` | Tworzenie pendingowego requestu | `request_id`, `user_id`, `preference_key`, `source_card_id` |
| `aeis.advisor.preferences.hard_change_confirmed` | Confirm z `confirmed=true` | `request_id`, `user_id`, `preference_key` |
| `aeis.advisor.preferences.catalog_extended` | Dodanie custom entry | `catalog_type`, `entry_id`, `created_by` |

`idempotency_key`: `f"{topic}:{payload.get('user_id', '')}:{payload.get('preference_key', '')}"` ustawiany w `service._emit`.

### 5.2 Eventy subskrybowane

| Topic | Handler | Efekt |
|---|---|---|
| `aeis.advisor.history.learning_signal_emitted` | `soft_learning_tick` (pull-based) | Aplikuje soft learning po wywołaniu RPC; brak background subscribera w MVP. |

W manifeście (`aeis.advisor.preferences.json`) jest zadeklarowany `events_subscribe: ["aeis.advisor.history.learning_signal_emitted"]`. W obecnej implementacji nie ma jeszcze aktywnej subskrypcji push — obsługa idzie przez `SoftLearningTick` RPC. Patrz `30_event_taxonomy_full.md` dla pełnej taksonomii.

---

## 6. Database tables

### 6.1 `advisor_preferences.preferences`

Cel: macierz 3D preferencji `(user_id × project_type × project_domain × preference_key)`.

| Kolumna | Typ | Opis |
|---|---|---|
| `user_id` | UUID NOT NULL | Operator. |
| `project_type` | TEXT (NULL = wildcard) | Wymiar typu projektu. |
| `project_domain` | TEXT (NULL = wildcard) | Wymiar domeny. |
| `preference_key` | TEXT NOT NULL | FK do `preference_key_catalog`. |
| `preference_value` | JSONB NOT NULL | Wartość zgodna z `value_schema`. |
| `set_by` | TEXT NOT NULL | `user` / `soft_learning` / `system` / `wizard`. |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

Primary key: `(user_id, COALESCE(project_type, ''), COALESCE(project_domain, ''), preference_key)`.

Indeksy:
- `idx_preferences_user(user_id)`
- `idx_preferences_lookup(user_id, project_type, project_domain)`
- `idx_preferences_key(preference_key)`

Append-only: nie (UPDATE i DELETE dozwolone — historia idzie do `preferences_audit`).

Sample queries:
```sql
-- Pobierz wszystkie preferencje operatora.
SELECT preference_key, project_type, project_domain, preference_value, set_by
FROM advisor_preferences.preferences
WHERE user_id = '00000000-0000-0000-0000-000000000001'
ORDER BY preference_key, project_type NULLS LAST, project_domain NULLS LAST;

-- Statystyka wykorzystania kluczy w bazie (debug).
SELECT preference_key, COUNT(*) AS rows
FROM advisor_preferences.preferences
GROUP BY preference_key
ORDER BY rows DESC;
```

### 6.2 `advisor_preferences.preferences_audit`

Cel: append-only log każdej zmiany.

| Kolumna | Typ | Opis |
|---|---|---|
| `audit_id` | UUID PK DEFAULT gen_random_uuid() | |
| `user_id` | UUID NOT NULL | |
| `project_type` | TEXT | |
| `project_domain` | TEXT | |
| `preference_key` | TEXT NOT NULL | |
| `old_value` | JSONB | NULL jeśli INSERT. |
| `new_value` | JSONB | NULL jeśli DELETE/RESET. |
| `change_type` | TEXT NOT NULL | `INSERT` / `UPDATE` / `DELETE` / `RESET`. |
| `changed_by` | TEXT NOT NULL | `set_by` z `preferences`. |
| `changed_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| `reason` | TEXT | Wolnotekstowy powód (np. `card_id` źródłowej karty). |

Indeksy:
- `idx_pref_audit_user(user_id, changed_at DESC)`
- `idx_pref_audit_key(preference_key, changed_at DESC)`

Append-only enforcement (triggery `preferences_audit_no_update`, `preferences_audit_no_delete`) wywołują `RAISE EXCEPTION 'preferences_audit is append-only'`.

Sample queries:
```sql
-- Ostatnie 50 zmian dla operatora.
SELECT changed_at, change_type, preference_key, old_value, new_value, changed_by, reason
FROM advisor_preferences.preferences_audit
WHERE user_id = '00000000-0000-0000-0000-000000000001'
ORDER BY changed_at DESC
LIMIT 50;

-- Ile soft-learningów wykonano dziś.
SELECT COUNT(*) FROM advisor_preferences.preferences_audit
WHERE changed_by = 'soft_learning' AND changed_at >= current_date;
```

### 6.3 `advisor_preferences.project_domain_catalog`

| Kolumna | Typ | Opis |
|---|---|---|
| `domain_id` | TEXT PK | Np. `funding`, `software`, `custom:devrel`. |
| `display_name` | TEXT NOT NULL | |
| `is_system` | BOOLEAN DEFAULT false | true dla 14 bazowych. |
| `is_immutable` | BOOLEAN DEFAULT false | true dla 14 bazowych. |
| `description` | TEXT | |
| `created_at` | TIMESTAMPTZ DEFAULT now() | |
| `created_by` | TEXT DEFAULT 'system' | `system` lub `user_id`. |

14 bazowych: `funding`, `software`, `audit`, `mobile`, `infrastructure`, `data_analytics`, `security`, `governance`, `research`, `marketing`, `legal`, `product_management`, `finance`, `operations`.

Custom muszą zaczynać się od `custom:` (egzekwowane przez `_db.add_custom_catalog_entry`).

### 6.4 `advisor_preferences.project_type_catalog`

Analogiczny do `project_domain_catalog` (kolumny: `type_id`, `display_name`, `is_system`, `is_immutable`, `description`, `created_at`, `created_by`).

8 bazowych: `research`, `production`, `experiment`, `poc`, `migration`, `refactor`, `integration`, `hotfix`.

### 6.5 `advisor_preferences.preference_key_catalog`

| Kolumna | Typ | Opis |
|---|---|---|
| `preference_key` | TEXT PK | Np. `autonomy_level`. |
| `display_name` | TEXT NOT NULL | |
| `description` | TEXT | |
| `value_schema` | JSONB NOT NULL | JSON schema do walidacji. |
| `default_value` | JSONB | Systemowy default. |
| `is_hard_change` | BOOLEAN DEFAULT false | true ⇒ wymagana operatora konfirmacja. |
| `created_at` | TIMESTAMPTZ DEFAULT now() | |

16 systemowych kluczy seedowanych w migracji (patrz tabela 3.3).

Sample query (jakie klucze wymagają hard-change):
```sql
SELECT preference_key, display_name, default_value
FROM advisor_preferences.preference_key_catalog
WHERE is_hard_change = true
ORDER BY preference_key;
```

---

## 7. Przykład użycia

### 7.1 Klient lokalny (singleton w procesie)

```python
from sylion.aeis.advisor.preferences import get_preferences_service

service = get_preferences_service()

# Read effective preference with fallback cascade.
resolved = service.get_effective(
    user_id="00000000-0000-0000-0000-000000000001",
    project_type="production",
    project_domain="funding",
    preference_key="cost_sensitivity",
)
print(resolved.value, resolved.resolution_level.value)

# Set a soft preference (cost_sensitivity is NOT a hard-change key).
result = service.set_preference(
    user_id="00000000-0000-0000-0000-000000000001",
    project_type=None,
    project_domain=None,
    preference_key="cost_sensitivity",
    value="high",
    set_by="user",
    reason="operator wants tight budget",
)
assert result["success"] is True
assert result["requires_hard_confirmation"] is False

# Hard change request flow (autonomy_level is a hard-change key).
hc = service.set_preference(
    user_id="00000000-0000-0000-0000-000000000001",
    project_type=None,
    project_domain=None,
    preference_key="autonomy_level",
    value="auto",
    set_by="user",
    reason="ready for full autonomy",
)
# Returns requires_hard_confirmation=True with a request_id pending operator click.
print(hc["hard_change_request_id"])

ok, request, error = service.confirm_hard_change(
    request_id=hc["hard_change_request_id"],
    operator_signature="op-sig-001",
    confirmed=True,
)
assert ok and error is None
```

### 7.2 Klient gRPC (in-process, wykorzystujący servicer)

```python
import grpc
from concurrent import futures
from sylion.aeis.advisor.preferences.grpc_server import register_preferences_service
from sylion.aeis.advisor._generated import preferences_pb2, preferences_pb2_grpc

server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
register_preferences_service(server)
server.add_insecure_port("127.0.0.1:50071")
server.start()

channel = grpc.insecure_channel("127.0.0.1:50071")
stub = preferences_pb2_grpc.PreferencesServiceStub(channel)

response = stub.GetEffective(preferences_pb2.GetEffectiveRequest(
    user_id="00000000-0000-0000-0000-000000000001",
    project_type="production",
    project_domain="funding",
    preference_key="autonomy_level",
))
print(response.resolution_level, response.value_json)

server.stop(grace=1).wait()
```

### 7.3 Test (golden style)

```python
import pytest
from sylion.aeis.advisor.preferences import get_preferences_service, reset_preferences_service

@pytest.fixture(autouse=True)
def _reset():
    reset_preferences_service()
    yield
    reset_preferences_service()


def test_resolution_falls_back_to_user_default():
    svc = get_preferences_service()
    user_id = "00000000-0000-0000-0000-000000000010"

    svc.set_preference(
        user_id=user_id,
        project_type=None,
        project_domain=None,
        preference_key="cost_sensitivity",
        value="high",
        set_by="wizard",
    )

    resolved = svc.get_effective(
        user_id=user_id,
        project_type="production",
        project_domain="audit",
        preference_key="cost_sensitivity",
    )
    assert resolved.value == "high"
    assert resolved.resolution_level.value == "user_default"
```

### 7.4 Snippet: catalog extension

```python
from sylion.aeis.advisor.preferences import get_preferences_service

svc = get_preferences_service()
entry = svc.add_custom_catalog_entry(
    catalog_type="project_domain",
    entry_id="custom:devrel",
    display_name="Developer Relations",
    description="DevRel campaigns and content",
    created_by="00000000-0000-0000-0000-000000000001",
)
assert entry is not None and entry.is_system is False
```

---

## 8. Verification

### 8.1 Smoke test SQL

```bash
psql "$SYLION_PG_DSN" -c "SELECT count(*) AS domains FROM advisor_preferences.project_domain_catalog WHERE is_system;"
# Expected: 14
psql "$SYLION_PG_DSN" -c "SELECT count(*) AS types FROM advisor_preferences.project_type_catalog WHERE is_system;"
# Expected: 8
psql "$SYLION_PG_DSN" -c "SELECT count(*) AS keys FROM advisor_preferences.preference_key_catalog;"
# Expected: 16
```

### 8.2 Append-only check

```bash
psql "$SYLION_PG_DSN" -c "UPDATE advisor_preferences.preferences_audit SET reason='hack' WHERE 1=1;"
# Expected error: ERROR: preferences_audit is append-only
psql "$SYLION_PG_DSN" -c "DELETE FROM advisor_preferences.preferences_audit WHERE 1=1;"
# Expected error: ERROR: preferences_audit is append-only
```

### 8.3 Pytest (golden tests)

```bash
cd src/sylion-pipeline
pytest tests/aeis/advisor/preferences/ -v
```

### 8.4 Round-trip RPC sanity (in-process)

```bash
python -c "
from sylion.aeis.advisor.preferences import get_preferences_service
svc = get_preferences_service()
print(svc.get_blocked_providers(user_id='00000000-0000-0000-0000-000000000001'))
"
# Expected: [] (system default for blocked_providers)
```

### 8.5 Audyt zmian dla pojedynczego klucza

```bash
psql "$SYLION_PG_DSN" <<'SQL'
SELECT changed_at, change_type, old_value, new_value, changed_by, reason
FROM advisor_preferences.preferences_audit
WHERE preference_key = 'autonomy_level'
ORDER BY changed_at DESC
LIMIT 10;
SQL
```

---

## 9. Troubleshooting

| Problem | Diagnoza | Fix |
|---|---|---|
| `Set` zwraca `requires_hard_confirmation=True` mimo że to nie jest klucz wrażliwy | Klucz nie istnieje w `preference_key_catalog` (`get_preference_key_metadata` zwraca None — defaultowo nie wymaga, ale jeśli jest oznaczony `is_hard_change=true` ręcznie) lub klucz jest zdefiniowany jako hard. | Sprawdź `SELECT is_hard_change FROM advisor_preferences.preference_key_catalog WHERE preference_key='<key>'`. Jeśli klucz nie istnieje, dodaj go w migracji. |
| `GetEffective` zwraca `SYSTEM_DEFAULT` mimo zapisanego wiersza | Niedopasowanie poziomów: ustawiona preferencja ma `project_type='production'`, a query odpytuje `project_type='research'`. Kaskada nie znajduje. | Użyj `List` z `filter_preference_key=<key>` aby zobaczyć wszystkie poziomy. Ustaw na `(NULL, NULL)` dla user_default. |
| Hard-change request `request_expired` | TTL = 30 minut wygasł. | Wyrzuć starszy request przez `confirm_hard_change(confirmed=False)` i wywołaj `RequestHardChange` ponownie. |
| `SoftLearningTick` zwraca `applied_count=0` mimo signals w history | Wszystkie signals mają `hard_change_status='pending'` (filtr). | Wykonaj `confirm_hard_change` w module `history` najpierw, lub usuń status `pending`. |
| `add_custom_catalog_entry` zwraca `None` | `entry_id` nie zaczyna się od `custom:` albo `catalog_type='preference_key'`. | Użyj prefixu `custom:` i nie wybieraj `preference_key` (custom keys nie są wspierane — są system-only). |
| `aeis.advisor.preferences.created` event nie pojawia się | `_event_bus.publish` rzucił wyjątek, które `service._emit` swallowuje. | Włącz logowanie: `logging.getLogger("sylion.core.event_bus").setLevel(logging.DEBUG)`. Sprawdź czy backbone uruchomione. |
| Walidacja JSON schema przepuszcza złe wartości | MVP nie waliduje `value_schema` przy `Set`. | Walidacja po stronie klienta lub w warstwie wyższej (TODO post-MVP). |
| `disable_preference` zwraca `levels_cleared=0` | Operator nie ma żadnego wiersza explicit dla tego klucza (wszystko leci kaskadą do system_default). | Brak akcji — to normalny stan. |
| `psycopg.OperationalError` przy każdym RPC | Pula wyczerpana lub baza niedostępna. | Sprawdź `SYLION_PG_POOL_MAX`, `SELECT pg_stat_activity` w PG. |

---

## 10. Cross-references

Powiązane moduły:
- [`02_pricing.md`](02_pricing.md) — konsumuje `get_blocked_providers` przy filtracji `list_providers`/`list_models` i `get_cost`.
- [`03_actions.md`](03_actions.md) — handler `save_as_preference` woła pośrednio `service.set_preference` (lub żąda hard-change).
- [`05_engine.md`](05_engine.md) — czyta `autonomy_level`, `cost_ceilings`, `llm_judge_routing_override` do wyboru modelu LLM oraz `is_hard_change` do U4/U5 w D-ladder.
- [`06_history.md`](06_history.md) — emituje `learning_signal_emitted`, którą konsumuje `SoftLearningTick`.

Architecture references:
- `docs/claude_parallel/aeis_advisor/00_architecture/02_postgresql_schema.sql` — sekcje `advisor_preferences.*` (linie 102-256).
- `docs/claude_parallel/aeis_advisor/00_architecture/03_module_manifests.md` — definicja kontraktu modułu.
- `docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md` — pełne payloady eventów.
- `docs/claude_parallel/aeis_advisor/00_architecture/00_master_spec.md` — kontekst kaskady i hard-change.

Manifest: `src/sylion-pipeline/sylion/contracts/manifests/aeis.advisor.preferences.json`.

Proto: `src/sylion-pipeline/sylion/aeis/advisor/proto/preferences.proto` (kompilowany do `_generated/preferences_pb2*.py`).
