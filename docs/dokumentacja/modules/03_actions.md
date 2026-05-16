# Moduł `sylion.aeis.advisor.actions`
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

Dokumentacja techniczna modułu rutera działań operatora na karcie AdvisorCard.

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

`sylion.aeis.advisor.actions` to synchroniczny ruter operatora — przyjmuje akcję na karcie AdvisorCard (jedną z dziewięciu typów), wybiera handler, woła zewnętrzny moduł (engine, human gate, masterplan, preferences) i zapisuje pełny audyt routingu w `advisor_actions.action_routes_audit`. Każde wywołanie kończy się dokładnie jednym wpisem do tabeli routingu i co najmniej jednym eventem (`action_routed` w razie sukcesu lub `routing_failed` w razie błędu).

Moduł nie podejmuje decyzji semantycznych — wybór konsekwencji akcji (np. czy zarejestrować preferencję jako hard change, czy utworzyć ticket Human Gate) leży po stronie modułów docelowych. Ruter jest jednak miejscem propagacji flagi `dont_learn_flag`: gdy operator zaznaczył „nie ucz się z tej karty”, ruter najpierw wywołuje pomocniczo handler `DONT_LEARN_FROM_THIS` (tag w body karty), a potem główną akcję. Dzięki temu warstwa historii widzi flagę zanim zostanie wystawiony sygnał uczący.

---

## 2. Architektura modułu

### 2.1. Pliki źródłowe

Wszystkie ścieżki względem `src/sylion-pipeline/sylion/aeis/advisor/actions/`.

| Plik | Rola |
| --- | --- |
| `service.py` | `ActionsService` — orkiestrator `HandleAction`/`RetryFailed`/`GetRoutingAudit`, mapowanie proto enum → `CardAction`, emisje eventów |
| `grpc_server.py` | `ActionsServicer` — rejestracja servicera, konwersja proto wartości (`google.protobuf.Value`) na typy Pythona |
| `_db.py` | Helpery SQL: `log_route_row`, `list_route_rows`, `update_route_status`, `get_route_for_retry`, `fetch_card_snapshot`, `append_card_tag`, `set_card_flag` |
| `_models.py` | `CardAction` enum (9 wartości), `RouteStatus` (`pending`/`success`/`failed`), dataclasses `ActionContext`, `HandlerResult`, `RouteAuditRow` |
| `audit.py` | Cienka fasada nad `_db` (`log_route`, `get_routing_audit`, `update_route_status`) |
| `retry.py` | `retry_route(route_audit_id)` — odtwarza `ActionContext` z payloadu i woła handler ponownie |
| `routing_table.py` | `_ROUTING: dict[CardAction, type[ActionHandler]]` + `get_handler(action)` |
| `handlers/base.py` | Abstrakcja `ActionHandler` (`handle(ctx) -> HandlerResult`) |
| `handlers/accept_handler.py` | `AcceptHandler` — `append_card_tag(card_id, "accepted")` |
| `handlers/reject_handler.py` | `RejectHandler` — `append_card_tag("rejected")` |
| `handlers/modify_handler.py` | `ModifyHandler` — wymaga `modified_recommendation`, ustawia `body_jsonb.modified_recommendation` |
| `handlers/remind_later_handler.py` | `RemindLaterHandler` — `append_card_tag("remind_later")` |
| `handlers/not_useful_handler.py` | `NotUsefulHandler` — `append_card_tag("not_useful")` |
| `handlers/human_gate_handler.py` | `HumanGateHandler` — pobiera snapshot karty, generuje `ticket_id` (UUID4) |
| `handlers/masterplan_handler.py` | `MasterplanHandler` — generuje `proposal_id`, payload zawiera `advisor_body` |
| `handlers/preference_handler.py` | `PreferenceHandler` — woła `PreferencesService.set_preference`, propaguje `requires_hard_confirmation` |
| `handlers/dont_learn_handler.py` | `DontLearnHandler` — `set_card_flag("dont_learn", True)` |

### 2.2. Zależności

Manifest `aeis.advisor.actions.json#depends_on`:
- `sylion.aeis.advisor.preferences` — `PreferenceHandler` woła `set_preference`,
- `sylion.aeis.advisor.engine` — `_db.fetch_card_snapshot` czyta `advisor_engine.recommendations`, `append_card_tag` / `set_card_flag` modyfikują tę samą tabelę.

Pośrednie:
- `sylion.aeis.advisor._db.get_pool` — wspólny pool psycopg.
- `sylion.core.event_bus.SylionEvent` + `get_event_bus()` — emisja eventów `aeis.advisor.actions.*`.

### 2.3. Storage

Schemat: **`advisor_actions`** (jedna tabela `action_routes_audit` — dokumentacja w sekcji 6).

Boczne efekty na innych schematach:
- `advisor_engine.recommendations.tags[]` — `append_card_tag` (immutable list of operator decisions),
- `advisor_engine.recommendations.body_jsonb` — `set_card_flag` (np. `modified_recommendation`, `dont_learn`),
- `advisor_preferences.preferences` — przez `PreferencesService.set_preference` (gdy akcja `SAVE_AS_PREFERENCE`).

### 2.4. Workery / harmonogram

Brak. Cała logika synchroniczna z punktu wywołania RPC. `RetryFailed` jest również synchroniczne — to operator (lub backend recovery script) decyduje o ponowieniu.

---

## 3. Konfiguracja

Moduł nie ma własnych zmiennych środowiskowych. Korzysta z:
- `ADVISOR_PG_DSN` (jeśli zdefiniowana, używana przez `_db.get_pool` z modułu wspólnego).
- `SYLION_EVENT_BUS_URL` lub konfiguracji Kafka/Redpanda (poprzez `get_event_bus()`).

Wartości domyślne:
- Brak retencji wpisów `action_routes_audit` — tabela jest append-only, kasowanie odbywa się wyłącznie wsadowo na poziomie operacji.
- `RouteStatus` startuje jako `success` lub `failed` (handler decyduje); `pending` jest zarezerwowane dla manualnych przepływów (rerun, partial commit).
- Soft learning trigger: każda akcja oprócz `REMIND_LATER` i `DONT_LEARN_FROM_THIS` ma `soft_learning_triggered=True`, chyba że `dont_learn_flag=true` (sprawdź pojedyncze handlery — wszystkie z wpisem `soft_learning_triggered=not ctx.dont_learn_flag`).

---

## 4. Funkcje (gRPC RPC)

Service: `sylion.aeis.advisor.actions.v1.ActionsService` (proto: `proto/actions.proto`).

### 4.1. `HandleAction(HandleActionRequest) returns (HandleActionResponse)`

Główne wejście modułu. Synchroniczne — odpowiedź zwracana po pełnym wpisie audytu i emitach.

**Wejście (`HandleActionRequest`):**
- `string card_id` — UUID karty z `advisor_engine.recommendations`,
- `CardAction action` — enum (`CARD_ACTION_ACCEPT` … `CARD_ACTION_DONT_LEARN_FROM_THIS`),
- `string operator_id` — UUID operatora,
- `string operator_note` — opcjonalna notatka,
- `string modified_recommendation` — wymagane dla `MODIFY`,
- `string preference_key`, `string preference_project_type`, `string preference_project_domain`, `Value preference_value` — wymagane (key) dla `SAVE_AS_PREFERENCE`,
- `bool dont_learn_flag` — gdy `true`, ruter najpierw woła `DontLearnHandler` jako auxiliary.

**Wyjście (`HandleActionResponse`):**
- `string action_event_id` — to samo co `route_audit_id`,
- `Timestamp recorded_at`,
- `bool soft_learning_triggered`, `bool hard_learning_pending_confirmation`,
- `string created_human_gate_ticket_id` (gdy `CONVERT_TO_HUMAN_GATE` zakończone sukcesem),
- `string created_masterplan_proposal_id` (gdy `CONVERT_TO_MASTERPLAN_CHANGE`),
- `string saved_preference_id` (gdy `SAVE_AS_PREFERENCE`),
- `string error_message`.

**Side effects per akcja:**

| Akcja | DB | Event(y) |
| --- | --- | --- |
| `accept` | `recommendations.tags += "accepted"` | `action_routed` |
| `reject` | `recommendations.tags += "rejected"` | `action_routed` |
| `modify` | `recommendations.body_jsonb.modified_recommendation = ...` | `action_routed` lub `routing_failed` (gdy brak `modified_recommendation`) |
| `remind_later` | `recommendations.tags += "remind_later"` | `action_routed` |
| `not_useful` | `recommendations.tags += "not_useful"` | `action_routed` |
| `convert_to_human_gate` | `fetch_card_snapshot`, generuje UUID ticketu | `action_routed` + `human_gate_ticket_created` |
| `convert_to_masterplan_change` | `fetch_card_snapshot`, generuje UUID propozycji | `action_routed` + `masterplan_proposal_created` |
| `save_as_preference` | `PreferencesService.set_preference` | `action_routed` + `preference_saved` |
| `dont_learn_from_this` | `recommendations.body_jsonb.dont_learn = true` | `action_routed` |

**Błędy:**
- Brak karty (`card_not_found`) — `success=false`, `error_message="card_not_found"` (Human Gate, Masterplan).
- Brak `modified_recommendation` — `error_message="modified_recommendation_required"`.
- Brak `preference_key` — `error_message="preference_key_required"`.
- Brak modułu preferencji w runtime — `error_message="preferences_module_unavailable"`.
- Każdy nie-success skutkuje statusem `failed` w `action_routes_audit` i emisją `routing_failed`.

### 4.2. `RetryFailed(RetryFailedRequest) returns (RetryFailedResponse)`

**Wejście:** `string route_audit_id`.

**Wyjście:** `bool success`, `string status` (`success`/`failed`/inny), `string error_message`.

**Algorytm (`retry.retry_route`):**
1. `get_route_for_retry(route_audit_id)` — sprawdza status.
2. Jeśli nie istnieje → `(False, "not_found", "route_audit_id_not_found")`.
3. Jeśli status nie jest `failed` → `(False, str(status), "not_in_failed_state")`.
4. Odtworzenie `ActionContext` z `payload_sent_jsonb`: `card_id`, `action`, `operator_id`, `operator_note`, `modified_recommendation`, `preference_key`, `preference_project_type` (klucz `project_type` w payloadzie), `preference_project_domain`, `preference_value`, `dont_learn_flag`.
5. Wołanie handlera, update statusu (`SUCCESS` lub ponownie `FAILED`).
6. Emisja `aeis.advisor.actions.action_retry_scheduled` przy sukcesie.

### 4.3. `GetRoutingAudit(GetRoutingAuditRequest) returns (GetRoutingAuditResponse)`

**Wejście:** `string card_id`.

**Wyjście:** `repeated RouteAuditEntry entries` (sortowane `routed_at ASC`).

`RouteAuditEntry` zawiera oryginalne `payload_sent` i `response` jako `google.protobuf.Value` (mapowanie z JSONB przez `google.protobuf.json_format.ParseDict`).

---

## 5. Eventy

### 5.1. Emitowane

Wszystkie eventy emituje `ActionsService._emit` z `source_module="sylion.aeis.advisor.actions"`. `idempotency_key = f"{topic}:{card_id}:{route_audit_id}"`.

| Topic | Trigger | Payload |
| --- | --- | --- |
| `aeis.advisor.actions.action_routed` | Sukces handlera | `route_audit_id`, `card_id`, `action`, `operator_id`, `routed_to_module` |
| `aeis.advisor.actions.routing_failed` | Wyjątek lub `success=false` | `card_id`, `action`, `error` |
| `aeis.advisor.actions.human_gate_ticket_created` | `CONVERT_TO_HUMAN_GATE` sukces | `card_id`, `ticket_id` |
| `aeis.advisor.actions.masterplan_proposal_created` | `CONVERT_TO_MASTERPLAN_CHANGE` sukces | `card_id`, `proposal_id` |
| `aeis.advisor.actions.preference_saved` | `SAVE_AS_PREFERENCE` sukces | `card_id`, `preference_key`, `operator_id` |
| `aeis.advisor.actions.action_retry_scheduled` | Sukces `RetryFailed` | `route_audit_id`, `status` |

Manifest deklaruje wszystkie 6 topic-ów (`aeis.advisor.actions.json#events_emit`).

### 5.2. Subskrybowane

Brak (`events_subscribe: []`).

---

## 6. Tabele bazy danych

### 6.1. `advisor_actions.action_routes_audit`

**Cel:** Append-only rejestr wszystkich akcji operatora wykonanych na kartach AdvisorCard.

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `route_audit_id` | UUID PK, default `gen_random_uuid()` | |
| `card_id` | UUID NOT NULL | Soft-FK do `advisor_engine.recommendations` |
| `action` | `advisor_engine.card_action` | Enum 9 wartości |
| `routed_to_module` | TEXT NOT NULL | np. `"advisor_engine"`, `"human_gate"`, `"masterplan"`, `"advisor_preferences"` |
| `routed_target_id` | UUID | ID utworzone w module docelowym (ticket / proposal / preference) |
| `payload_sent_jsonb` | JSONB NOT NULL | Dokładny payload wysłany do modułu docelowego |
| `response_jsonb` | JSONB | Odpowiedź modułu docelowego |
| `status` | TEXT NOT NULL | `success` / `failed` / `pending` |
| `error_message` | TEXT | NULL gdy success |
| `routed_at` | TIMESTAMPTZ, default `now()` | |

**Indeksy:**
- PK `route_audit_id`,
- `idx_action_routes_card` (`card_id`).

**Append-only:** Logika modułu nie wykonuje `DELETE`. `UPDATE` jest dozwolony wyłącznie w `update_route_status` (przejście `failed` → `success` po retry oraz aktualizacja `error_message`). Status `pending` zarezerwowany dla manualnych narzędzi.

**Sample queries:**

```sql
-- Audit per karta
SELECT routed_at, action, status, routed_to_module, routed_target_id, error_message
FROM advisor_actions.action_routes_audit
WHERE card_id = '12345678-1234-1234-1234-1234567890ab'
ORDER BY routed_at;

-- Top 5 modułów docelowych
SELECT routed_to_module, count(*) FROM advisor_actions.action_routes_audit
GROUP BY routed_to_module ORDER BY 2 DESC LIMIT 5;

-- Wszystkie nieudane routingi z ostatnich 24h
SELECT route_audit_id, card_id, action, error_message
FROM advisor_actions.action_routes_audit
WHERE status = 'failed' AND routed_at > NOW() - INTERVAL '24 hours';
```

---

## 7. Przykład użycia

### 7.1. SDK lokalne (Python)

```python
from types import SimpleNamespace
from sylion.aeis.advisor.actions.service import get_actions_service

service = get_actions_service()

response = service.HandleAction(SimpleNamespace(
    card_id="12345678-1234-1234-1234-1234567890ab",
    action="convert_to_human_gate",
    operator_id="op-001",
    operator_note="Need legal review",
    dont_learn_flag=False,
))
print(response.action_event_id, response.created_human_gate_ticket_id)
```

### 7.2. Klient gRPC (akcja `SAVE_AS_PREFERENCE`)

```python
import grpc
from google.protobuf import struct_pb2
from sylion.aeis.advisor._generated import actions_pb2, actions_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = actions_pb2_grpc.ActionsServiceStub(channel)

value = struct_pb2.Value(string_value="local_only")
request = actions_pb2.HandleActionRequest(
    card_id="card-uuid",
    action=actions_pb2.CARD_ACTION_SAVE_AS_PREFERENCE,
    operator_id="op-001",
    preference_key="security.deployment_mode",
    preference_project_type="external_paid_service",
    preference_value=value,
)
response = stub.HandleAction(request)
print(response.saved_preference_id, response.hard_learning_pending_confirmation)
```

### 7.3. Pytest fixture i test

```python
import pytest
from types import SimpleNamespace
from sylion.aeis.advisor.actions.service import ActionsService

class _BusFake:
    def __init__(self):
        self.events = []
    def publish(self, event):
        self.events.append(event)

@pytest.fixture
def actions_service():
    bus = _BusFake()
    return ActionsService(event_bus=bus), bus

def test_modify_requires_text(actions_service):
    service, bus = actions_service
    response = service.HandleAction(SimpleNamespace(
        card_id="card-1",
        action="modify",
        operator_id="op-1",
        modified_recommendation="",
        dont_learn_flag=False,
    ))
    assert response.error_message == "modified_recommendation_required"
    assert any(event.topic == "aeis.advisor.actions.routing_failed" for event in bus.events)
```

### 7.4. Retry niepowodzenia

```python
from types import SimpleNamespace
from sylion.aeis.advisor.actions.service import get_actions_service

service = get_actions_service()
result = service.RetryFailed(SimpleNamespace(route_audit_id="<uuid>"))
print(result.success, result.status)
```

---

## 8. Komendy weryfikacyjne

```bash
# 1. Łączna liczba zaroutowanych akcji
psql "$ADVISOR_PG_DSN" -c "SELECT count(*) FROM advisor_actions.action_routes_audit;"

# 2. Akcje na konkretnej karcie
psql "$ADVISOR_PG_DSN" -c "SELECT routed_at, action, status FROM advisor_actions.action_routes_audit WHERE card_id = '<uuid>' ORDER BY routed_at;"

# 3. Pytesty modułu (jednostkowe i smoke)
pytest tests/aeis/advisor/actions/ -q

# 4. Sanity gRPC
python -c "from sylion.aeis.advisor.actions.service import get_actions_service; print(get_actions_service().__class__.__name__)"

# 5. Konsystencja routingu vs. tags na karcie
psql "$ADVISOR_PG_DSN" -c "SELECT r.card_id, r.action, e.tags FROM advisor_actions.action_routes_audit r JOIN advisor_engine.recommendations e USING (card_id) WHERE r.action = 'accept' AND NOT ('accepted' = ANY(e.tags));"
```

---

## 9. Troubleshooting

| Problem | Diagnoza | Naprawa |
| --- | --- | --- |
| `HandleAction` zwraca `card_not_found` | Karta usunięta lub UUID literówka | Sprawdź `advisor_engine.recommendations`; reissue karty |
| `routing_failed` z `error="preferences_module_unavailable"` | `sylion.aeis.advisor.preferences` nie zainstalowane w runtime | Dodaj moduł do dependency tree, restart serwera |
| `RetryFailed` zwraca `not_in_failed_state` | Wpis już zsukcesowany lub `pending` | Wyświetl `GetRoutingAudit`, ewentualnie ręcznie zaktualizuj status |
| Brak eventu `human_gate_ticket_created` po sukcesie | `dont_learn_flag=true` blokuje? Nie — sprawdź event bus i topic filter | Pull eventów: `aeis.advisor.actions.action_routed` musi mieć `routed_to_module="human_gate"` |
| Karta ma duplikat tagu `accepted` | Wielokrotne `HandleAction(accept)` | `append_card_tag` jest idempotentne (`NOT (%s = ANY(tags))`); jeśli widzisz duplikaty, sprawdź czy nie wstawia ich inny moduł |
| `body_jsonb.modified_recommendation` przepisuje stary modify | `set_card_flag` nadpisuje pole | Oczekiwane — historia w `action_routes_audit.payload_sent_jsonb` |
| `payload_sent_jsonb` nie zawiera `operator_id` w retry | Pole zostało zapisane przez handler, nie ruter | `retry_route` czyta `payload.get("operator_id", "")`; w razie pustego pola handler ponowi ze `""`. Wzbogać payload na poziomie handlera |
| `action_retry_scheduled` nigdy nie emitowane | `retry.retry_route` zwrócił `success=False` | Tylko sukces emituje topic — sprawdź `error_message` w response |
| `save_as_preference` zwraca `requires_hard_confirmation=true` | Klucz oznaczony jako hard change w katalogu preferencji | Operator musi potwierdzić przez `Preferences.ConfirmHardChange` |

---

## 10. Powiązania

- [01_preferences.md](01_preferences.md) — `PreferenceHandler` deleguje do `set_preference`; `requires_hard_confirmation` propaguje się jako `hard_learning_pending_confirmation`.
- [05_engine.md](05_engine.md) — `_db.fetch_card_snapshot` czyta `recommendations`; `append_card_tag`/`set_card_flag` modyfikują tę samą tabelę. Karta po accept/reject przepływa do `engine.history` przez event `action_routed`.
- [06_history.md](06_history.md) — moduł historii subskrybuje `aeis.advisor.actions.action_routed` i tworzy wpis `card_actions` (partycja miesięczna) plus sygnały learning.
- [30_event_taxonomy_full.md](30_event_taxonomy_full.md) — schema payloadów wszystkich 6 emitowanych topic-ów.
- `docs/claude_parallel/aeis_advisor/00_architecture/02_postgresql_schema.sql` — DDL `advisor_actions.action_routes_audit`.
- `docs/claude_parallel/aeis_advisor/00_architecture/03_advisor_card_schema.md` — opis pola `tags[]` i `body_jsonb`.
