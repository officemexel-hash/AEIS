# Moduł `sylion.aeis.advisor.events`
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

Dokumentacja techniczna modułu audytu zdarzeń `aeis.advisor.*` oraz lifecycle helperów.

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura modułu](#2-architektura-modułu)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje (subscriber + helpery)](#4-funkcje-subscriber--helpery)
5. [Eventy](#5-eventy)
6. [Tabele bazy danych](#6-tabele-bazy-danych)
7. [Przykład użycia](#7-przykład-użycia)
8. [Komendy weryfikacyjne](#8-komendy-weryfikacyjne)
9. [Troubleshooting](#9-troubleshooting)
10. [Powiązania](#10-powiązania)

---

## 1. Cel modułu

`sylion.aeis.advisor.events` to **subskrybent audytu** dla całej rodziny topic-ów `aeis.advisor.*`. Moduł nie emituje własnych eventów (manifest `events_emit: []`), lecz nasłuchuje wszystkiego (`subscribe("*", ...)`) i:
1. filtruje topic po prefiksie `"aeis.advisor."`,
2. waliduje payload przez `ProtoRegistry` (callable validator lub minimalny check `isinstance(dict)`),
3. zapisuje sukces do `advisor_events.events` (partycjonowane miesięcznie, append-only) z `ON CONFLICT (event_id) DO NOTHING` (idempotencja),
4. zapisuje porażkę walidacji do `advisor_events.validation_failures` z payloadem i listą błędów.

Drugi cel modułu to lifecycle helpery (`lifecycle.publish_lifecycle_event`, `lifecycle.await_advisor_decision`) — cienka warstwa pomocnicza tworząca `SylionEvent` z deterministycznym `idempotency_key=f"{topic}:{primary_key}"`. Te helpery są używane przez engine do publikacji eventów typu `recommendation_emitted` i czekania na decyzję doradczą (proceed/block/defer_to_human_gate).

Trzeci cel to **rejestr deskryptorów proto** (`proto_registry.ProtoRegistry`) — strukturalny katalog `event_type → proto_message_type` używany przez audit subscriber do walidacji, a docelowo do dekompresji payload_proto z `advisor_events.events.payload_proto`.

---

## 2. Architektura modułu

### 2.1. Pliki źródłowe

Wszystkie ścieżki względem `src/sylion-pipeline/sylion/aeis/advisor/events/`.

| Plik | Rola |
| --- | --- |
| `audit_subscriber.py` | `AdvisorAuditSubscriber` — singleton subskrybent (`get_or_create_advisor_audit_subscriber`), `start()`, `_on_event(event)`, `_persist_event`, `_record_validation_failure`, `reset_advisor_audit_subscriber()` (do testów) |
| `proto_registry.py` | `RegistryEntry` (dataclass), `ProtoRegistry.register/list_entries/validate` |
| `lifecycle.py` | `publish_lifecycle_event(topic, payload, source_module, primary_key)` → `event_id`; `await_advisor_decision(event_id, timeout_s=5.0)` → `{"decision": "proceed"}` (placeholder) |

### 2.2. Zależności

Manifest `aeis.advisor.events.json#depends_on: []` — moduł stoi samodzielnie.

W praktyce import-time zależności:
- `sylion.aeis.advisor._db.get_pool` — wspólny pool psycopg.
- `sylion.core.event_backbone.EventBackbone` + `get_event_backbone()` — silnik publish/subscribe.
- `sylion.core.event_bus.SylionEvent` — koperta eventu.

### 2.3. Storage

Schemat: **`advisor_events`**.

| Tabela | Charakter |
| --- | --- |
| `proto_registry` | Katalog `event_type → proto_message_type` (DDL w schemacie; w runtime moduł trzyma in-memory `dict`) |
| `events` | Partycjonowana miesięcznie po `produced_at`; PK `event_id`; FK `event_type` → `proto_registry` |
| `validation_failures` | Append-only log błędów walidacji |

### 2.4. Workery / harmonogram

- **Subscriber loop**: `EventBackbone` (Kafka/Redpanda lub in-memory bus) wywołuje `_on_event` synchronicznie z dispatcher thread-em backbone'a. Subscriber jest startowany przez `get_or_create_advisor_audit_subscriber()` i wewnątrz `__init__` wywołuje `self.start()` (subskrypcja na `"*"`).
- **Partition manager**: brak własnego scheduler-a w module. Tworzenie kolejnych partycji `advisor_events.events_YYYY_MM` realizuje skrypt operacyjny lub osobny moduł historii (`advisor.history.partition_manager` dla card_actions; analogiczny mechanizm dla events realizuje admin DBA lub manualny skrypt).

---

## 3. Konfiguracja

### 3.1. Zmienne środowiskowe

| Zmienna | Opis |
| --- | --- |
| `ADVISOR_PG_DSN` | DSN dla pool-a (jeśli wspólny `_db` ją czyta) |
| `SYLION_EVENT_BUS_URL` | URL Kafki/Redpandy używanej przez `EventBackbone` |

### 3.2. Wartości domyślne

- `ProtoRegistry` startuje pusty (in-memory dict). Bez zarejestrowanego validatora payload-y walidują się jako poprawne, o ile są typu `dict`.
- `validate("*", ...)` jest fallback validator-em — jeśli zdefiniujesz `register(event_type="*", validator=fn)`, każdy nieznany topic użyje tego validatora.
- `await_advisor_decision` jest **placeholderem**: zawsze zwraca `{"decision": "proceed"}` (do czasu właściwej implementacji synchronicznej bramki przez engine).
- `_persist_event` używa `ON CONFLICT (event_id) DO NOTHING` — wielokrotna emisja tego samego `event_id` skutkuje pojedynczym wpisem.

### 3.3. Pliki konfiguracyjne

Brak. Rejestr deskryptorów ładuje się programowo przez `register(...)` (zobacz przykłady poniżej).

---

## 4. Funkcje (subscriber + helpery)

Moduł nie eksponuje gRPC. Interfejs jest pythonowy.

### 4.1. `get_or_create_advisor_audit_subscriber(*, event_backbone=None, proto_registry=None)`

Zwraca singleton `AdvisorAuditSubscriber`. Pierwsze wywołanie tworzy instancję (i automatycznie ją startuje przez `__init__ → start()`), kolejne zwracają tę samą.

**Side effects:**
- Subskrypcja `event_backbone.subscribe("*", _on_event)`.
- `_started=True` chroni przed podwójną subskrypcją.

**Reset (do testów):** `reset_advisor_audit_subscriber()` zeruje singleton.

### 4.2. `AdvisorAuditSubscriber._on_event(event: SylionEvent) -> None`

Obsługa pojedynczego eventu:
1. Filtr prefiksu `if not event.topic.startswith("aeis.advisor."): return`.
2. `is_valid, errors = self._proto_registry.validate(event.topic, event.payload)`.
3. Sukces → `_persist_event(event)` (insert do `advisor_events.events`).
4. Porażka → `_record_validation_failure(event, errors)` (log warning + insert do `validation_failures`).

### 4.3. `_persist_event(event)`

```sql
INSERT INTO advisor_events.events (
    event_id, event_type, payload_jsonb, produced_at, producer_module
) VALUES (%s, %s, %s, to_timestamp(%s), %s)
ON CONFLICT (event_id) DO NOTHING
```

Pole `payload_proto` (BYTEA) **nie jest** zapisywane przez subscriber — wypełnienie jest zarezerwowane dla high-perf publisher-a, który już posiada zserializowany proto. JSON jest źródłem prawdy w bieżącej wersji.

### 4.4. `_record_validation_failure(event, errors)`

```sql
INSERT INTO advisor_events.validation_failures (
    attempted_event_type, attempted_payload, validation_errors, producer_module
) VALUES (%s, %s, %s, %s)
```

`validation_errors` zapisywane jako `{"errors": [...]}` JSONB.

### 4.5. `ProtoRegistry.register(*, event_type, proto_message_type, validator=None, ...)`

Rejestruje wpis i opcjonalnie callable validator. Validator może zwracać:
- `True` lub `None` → poprawne,
- `False` → `["validator_rejected_payload"]`,
- `str` → traktowany jako jedyny błąd,
- `list[str]` → pusta lista = sukces, wpp. lista błędów.

### 4.6. `ProtoRegistry.validate(event_type, payload)`

Wybiera validator dla `event_type`, fallback do `"*"`, fallback do `isinstance(payload, dict)`.

### 4.7. `lifecycle.publish_lifecycle_event(topic, payload, *, source_module, primary_key) -> str`

Tworzy `SylionEvent` z:
- `event_id = uuid4()`,
- `topic`,
- `payload`,
- `source_module`,
- `timestamp = time.time()`,
- `idempotency_key = f"{topic}:{primary_key}"`.

Publikuje przez `get_event_backbone().publish(event)` i zwraca `event_id`.

### 4.8. `lifecycle.await_advisor_decision(event_id, timeout_s=5.0) -> dict[str, Any]`

Placeholder synchroniczny — zwraca `{"decision": "proceed"}`. Docelowa implementacja powinna pollować subscriber engine'a do momentu pojawienia się `recommendation_emitted` lub `deploy_blocked` z `causation_id == event_id`. Argument `timeout_s` jest obecnie nieużywany.

---

## 5. Eventy

### 5.1. Emitowane

Brak (`events_emit: []`).

### 5.2. Subskrybowane

Manifest deklaruje wildcard `aeis.advisor.*`. W kodzie subscriber subskrybuje literalnie `"*"` i filtruje prefix:

```python
self._event_backbone.subscribe("*", self._on_event)
...
if not event.topic.startswith("aeis.advisor."):
    return
```

W praktyce moduł audytuje:

| Family | Liczba topic-ów (z manifestów) |
| --- | --- |
| `aeis.advisor.preferences.*` | 7 |
| `aeis.advisor.pricing.*` | 6 |
| `aeis.advisor.actions.*` | 6 |
| `aeis.advisor.engine.*` | 14 |
| `aeis.advisor.history.*` | ~7 |
| `aeis.advisor.events.validation_failed` | 1 |

Pełna lista — patrz [30_event_taxonomy_full.md](30_event_taxonomy_full.md).

---

## 6. Tabele bazy danych

### 6.1. `advisor_events.proto_registry`

**Cel:** Katalog deskryptorów proto per `event_type`.

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `event_type` | TEXT PK | np. `aeis.advisor.engine.recommendation_emitted` |
| `proto_message_type` | TEXT NOT NULL | np. `sylion.aeis.advisor.v1.RecommendationEmittedEvent` |
| `proto_descriptor` | BYTEA NOT NULL | Zserializowany `FileDescriptorProto` lub `MessageDescriptor` |
| `proto_version` | INTEGER, default 1 | |
| `is_internal` | BOOLEAN, default true | false → outbound (HG, masterplan) |
| `is_active` | BOOLEAN, default true | |
| `created_at` | TIMESTAMPTZ | |
| `deprecated_at` | TIMESTAMPTZ | NULL = aktywne |

**Sample query:**
```sql
SELECT event_type, proto_message_type, is_internal
FROM advisor_events.proto_registry
WHERE is_active = true ORDER BY event_type;
```

### 6.2. `advisor_events.events` (PARTITION BY RANGE produced_at)

**Cel:** Główny event store, append-only, retencja **forever**.

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `event_id` | UUID PK | Z `SylionEvent.event_id` |
| `sequence_no` | BIGSERIAL | Globalny numer porządkowy |
| `event_type` | TEXT FK → `proto_registry` | |
| `payload_jsonb` | JSONB NOT NULL | Walidowany |
| `payload_proto` | BYTEA | Opcjonalny binary proto |
| `produced_at` | TIMESTAMPTZ NOT NULL | Klucz partycjonowania |
| `producer_module` | TEXT NOT NULL | np. `sylion.aeis.advisor.engine` |
| `correlation_id` | UUID | Łączy multi-event flow |
| `causation_id` | UUID | Który event spowodował ten |
| `operator_id` | UUID | NULL dla system events |
| `project_id` | UUID | |
| `trace_id` | TEXT | OpenTelemetry trace |

**Indeksy:**
- PK `event_id`,
- `idx_events_type_produced` (`event_type`, `produced_at DESC`),
- `idx_events_correlation` (`correlation_id`) WHERE NOT NULL,
- `idx_events_operator` (`operator_id`, `produced_at DESC`) WHERE NOT NULL,
- `idx_events_project` (`project_id`, `produced_at DESC`) WHERE NOT NULL.

**Partycje:** Schemat seedowo zawiera `events_2026_04`, `events_2026_05`, `events_2026_06`. Operator/Ops musi tworzyć kolejne miesiące — można zaimplementować analogicznie do `advisor.history.partition_manager`.

**Append-only:** Tabela nie ma triggera blokującego UPDATE/DELETE w schemacie 02_postgresql_schema.sql, ale subscriber wykonuje wyłącznie INSERT (idempotentne `ON CONFLICT DO NOTHING`).

**Sample queries:**

```sql
-- Wszystkie eventy z ostatniej godziny
SELECT event_type, count(*) FROM advisor_events.events
WHERE produced_at > NOW() - INTERVAL '1 hour'
GROUP BY event_type ORDER BY 2 DESC;

-- Trace pojedynczego flow
SELECT event_id, event_type, produced_at, causation_id
FROM advisor_events.events
WHERE correlation_id = '<uuid>'
ORDER BY sequence_no;

-- Aktywność operatora
SELECT date_trunc('hour', produced_at) AS hour, count(*)
FROM advisor_events.events
WHERE operator_id = '<uuid>' AND produced_at > NOW() - INTERVAL '7 days'
GROUP BY 1 ORDER BY 1;
```

### 6.3. `advisor_events.validation_failures`

**Cel:** Append-only log payloadów odrzuconych przez `ProtoRegistry`.

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `failure_id` | UUID PK | |
| `attempted_event_type` | TEXT NOT NULL | |
| `attempted_payload` | JSONB NOT NULL | |
| `validation_errors` | JSONB NOT NULL | `{"errors": [...]}` |
| `producer_module` | TEXT NOT NULL | |
| `failed_at` | TIMESTAMPTZ, default `now()` | |

**Indeksy:**
- PK `failure_id`,
- `idx_validation_failures_type` (`attempted_event_type`, `failed_at DESC`).

**Sample query:**
```sql
SELECT attempted_event_type, count(*) FROM advisor_events.validation_failures
WHERE failed_at > NOW() - INTERVAL '24 hours'
GROUP BY 1 ORDER BY 2 DESC;
```

---

## 7. Przykład użycia

### 7.1. Bootstrap subscribera (np. w `__main__` serwera)

```python
from sylion.aeis.advisor.events.audit_subscriber import (
    get_or_create_advisor_audit_subscriber,
)
from sylion.aeis.advisor.events.proto_registry import ProtoRegistry

registry = ProtoRegistry()
registry.register(
    event_type="aeis.advisor.engine.recommendation_emitted",
    proto_message_type="sylion.aeis.advisor.v1.RecommendationEmittedEvent",
    validator=lambda payload: "card_id" in payload or "card_id_required",
)

subscriber = get_or_create_advisor_audit_subscriber(proto_registry=registry)
print("audit subscriber active:", subscriber._started)
```

### 7.2. Custom validator z listą błędów

```python
from sylion.aeis.advisor.events.proto_registry import ProtoRegistry

def validate_action_routed(payload):
    errors = []
    for key in ("route_audit_id", "card_id", "action", "operator_id"):
        if key not in payload:
            errors.append(f"missing:{key}")
    return errors

registry = ProtoRegistry()
registry.register(
    event_type="aeis.advisor.actions.action_routed",
    proto_message_type="sylion.aeis.advisor.v1.ActionRoutedEvent",
    validator=validate_action_routed,
)
```

### 7.3. Lifecycle helper z poziomu enginu

```python
from sylion.aeis.advisor.events.lifecycle import (
    await_advisor_decision,
    publish_lifecycle_event,
)

event_id = publish_lifecycle_event(
    topic="aeis.advisor.engine.recommendation_emitted",
    payload={"card_id": "card-uuid", "d_level": "D2"},
    source_module="sylion.aeis.advisor.engine",
    primary_key="card-uuid",
)

decision = await_advisor_decision(event_id, timeout_s=5.0)
print(decision["decision"])  # 'proceed' until full implementation lands
```

### 7.4. Pytest reset singletona

```python
import pytest
from sylion.aeis.advisor.events.audit_subscriber import (
    get_or_create_advisor_audit_subscriber,
    reset_advisor_audit_subscriber,
)

@pytest.fixture(autouse=True)
def fresh_subscriber():
    reset_advisor_audit_subscriber()
    yield
    reset_advisor_audit_subscriber()

def test_singleton_returns_same_instance():
    a = get_or_create_advisor_audit_subscriber()
    b = get_or_create_advisor_audit_subscriber()
    assert a is b
```

---

## 8. Komendy weryfikacyjne

```bash
# 1. Liczba zapisanych eventów (per typ)
psql "$ADVISOR_PG_DSN" -c "SELECT event_type, count(*) FROM advisor_events.events GROUP BY 1 ORDER BY 2 DESC LIMIT 20;"

# 2. Validation failures w ostatnich 24h
psql "$ADVISOR_PG_DSN" -c "SELECT attempted_event_type, count(*) FROM advisor_events.validation_failures WHERE failed_at > NOW() - INTERVAL '24 hours' GROUP BY 1;"

# 3. Pytesty modułu
pytest tests/aeis/advisor/events/ -q

# 4. Sanity subscriber
python -c "from sylion.aeis.advisor.events.audit_subscriber import get_or_create_advisor_audit_subscriber; s = get_or_create_advisor_audit_subscriber(); print(s._started)"

# 5. Najnowsze partycje events
psql "$ADVISOR_PG_DSN" -c "SELECT relname FROM pg_class WHERE relname LIKE 'events_2026_%' ORDER BY relname;"
```

---

## 9. Troubleshooting

| Problem | Diagnoza | Naprawa |
| --- | --- | --- |
| Eventy nie trafiają do `advisor_events.events` | Subscriber nie wystartował (singleton nie utworzony) | Wywołaj `get_or_create_advisor_audit_subscriber()` na bootstrap |
| Każdy event ląduje w `validation_failures` | `ProtoRegistry` ma validator `"*"` zwracający `False` | Usuń wildcard validator lub popraw logikę |
| Kolizje `event_id` (duplikaty publish) | `_persist_event` ma `ON CONFLICT DO NOTHING` | Brak akcji — celowe; sprawdź producer (idempotency_key) |
| Insert do `events` failuje na FK `event_type` | Brak wpisu w `proto_registry` w PG | Insert deskryptora lub zmień FK na nullable |
| Partition out-of-range | Brak partycji `events_2026_MM` | Utwórz partycję ręcznie lub uruchom partition manager |
| `_record_validation_failure` rzuca wyjątek | Np. payload zawiera typy nieserializowalne do JSON | Wczytaj `event.payload` przez `json.dumps(default=str)` na poziomie producer-a |
| `await_advisor_decision` zawsze zwraca `proceed` | Placeholder | Zaimplementuj poll subscriber-a engine'a w lifecycle.py |
| Loga „advisor event validation failed" przy każdym evencie engine | Validator wymaga pól, których engine nie wysyła | Zaktualizuj validator do aktualnego payloadu |
| Brak indeksu `idx_events_correlation` w explain | Index partial (`WHERE correlation_id IS NOT NULL`) | Wymuszone przez `ANALYZE`; sprawdź statistics |

---

## 10. Powiązania

- [01_preferences.md](01_preferences.md), [02_pricing.md](02_pricing.md), [03_actions.md](03_actions.md), [05_engine.md](05_engine.md), [06_history.md](06_history.md) — wszyscy producent-ci `aeis.advisor.*`.
- [30_event_taxonomy_full.md](30_event_taxonomy_full.md) — pełna lista topic-ów + payload schema (źródło wpisów do `proto_registry`).
- `docs/claude_parallel/aeis_advisor/00_architecture/02_postgresql_schema.sql` — DDL `advisor_events.*` (proto_registry, events partitioned, validation_failures).
- `sylion/core/event_backbone.py` — implementacja backbone (Kafka/Redpanda + in-memory shim).
- `sylion/core/event_bus.py` — `SylionEvent` koperta.
