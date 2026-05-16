# 06. Moduł `sylion.aeis.advisor.history`
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Append-only księga akcji operatora, sygnały uczenia (soft + hard) oraz dwa
> komponenty 4-składnikowej formuły confidence engine'u
> (`history_match`, `historical_acceptance`).
> Forever-retention, partycjonowanie miesięczne, brak UPDATE / DELETE
> na partycjonowanej tabeli `card_actions` poza dwoma whitelisted-flagami.

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura](#2-architektura)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje (RPC)](#4-funkcje-rpc)
5. [Eventy](#5-eventy)
6. [Tabele DB](#6-tabele-db)
7. [Przykład użycia](#7-przykład-użycia)
8. [Komendy weryfikacyjne](#8-komendy-weryfikacyjne)
9. [Troubleshooting](#9-troubleshooting)
10. [Powiązania](#10-powiązania)

---

## 1. Cel modułu

Moduł `sylion.aeis.advisor.history` jest pamięcią długoterminową warstwy
Advisor. Przejmuje on cztery odpowiedzialności, które nie należą ani do
silnika rekomendacji (`engine`), ani do routera akcji (`actions`):

| Obszar | Odpowiedzialność |
|---|---|
| Append-only księga | Trwały zapis każdej interakcji operatora z kartą (`card_actions`) — 9 typów akcji, JSONB context, znaczniki uczenia |
| Sygnały uczenia | Agregacja akcji w `learning_signals` (5 typów), z osobnym cyklem życia dla hard-change (`pending` → `confirmed` / `rejected`) |
| Confidence components | Dostarczenie engine'owi snapshotów `history_match` (waga 0.4) i `historical_acceptance` (uśredniona waga w komponencie 0.4) — bez nich confidence spada do 0.0 |
| Soft / hard learning | Best-effort propagacja sygnałów do modułu `preferences` (soft auto-apply, hard wymaga potwierdzenia operatora) |

Moduł realizuje wymóg z kanonicznego `master_spec §4` (lifecycle 14–16:
record action → soft learning → optional hard-change request) oraz
`§9.3` (3D preference matrix + soft learning rules: próg 0.7 nad oknem 5
ostatnich akcji).

W odróżnieniu od `events`, który przechowuje audytowy log eventów busa,
`history` przechowuje **semantyczne ślady operatora** — tzn. nie każdy
zdarzenie busa jest history rowem, a każdy history row jest **odrębnym
artefaktem niezależnym od taśmy eventów**. Korelację zapewniają pola
`source_action_event_id` (link do `card_actions.action_event_id`) oraz
`source_card_id` (link do `advisor_engine.recommendations.card_id`).

Polityka retencji: **forever-retention dla `card_actions`** (partycje
miesięczne, nigdy nie kasowane bez explicit-DROP-PARTITION przez ops).
`learning_signals` nie są partycjonowane (rozmiar << 1% volumetrii akcji).

Polityka append-only: na poziomie PG wprowadzona przez funkcję
`advisor_history.block_modifications()` raisującą `RAISE EXCEPTION
'advisor_history tables are append-only'`, podpinaną do partycji przez
`partition_manager` (WP6). Wyjątkiem są dwie kolumny flagowe
(`triggered_soft_learning`, `triggered_hard_learning_request`),
aktualizowane przez whitelisted-procedurę `update_card_action_flags`
(zob. §6).

---

## 2. Architektura

### 2.1. Mapa pakietu

```
sylion/aeis/advisor/history/
├── __init__.py
├── _db.py                         # PG access layer (psycopg, dict_row)
├── _models.py                     # CardAction, LearningSignal, ConfidenceSnapshot dataclasses
├── service.py                     # AdvisorHistoryService facade + singleton
├── recorder.py                    # record_action(): insert + dispatch
├── grpc_server.py                 # gRPC stub (codegen pending)
├── partition_manager.py           # Monthly partition creator (PG-only DDL)
├── confidence_provider/
│   ├── __init__.py
│   ├── history_match.py           # Component for engine: similar past cards
│   └── historical_acceptance.py   # Component for engine: lifetime accept rate
└── learning/
    ├── __init__.py
    ├── signal_aggregator.py       # 0.7-threshold rolling window aggregator
    ├── soft_learning.py           # Best-effort apply to preferences module
    └── hard_learning.py           # request / confirm / reject hard change
```

### 2.2. Diagram przepływu

```
                    ┌────────────────────────────────────────┐
event_bus ───▶ subscribe("aeis.advisor.actions.action_routed")
event_bus ───▶ subscribe("aeis.advisor.engine.recommendation_emitted")
                    │
                    ▼
             AdvisorHistoryService._dispatch_inbound()
                    │
        ┌───────────┴────────────────────────────┐
        │                                        │
        ▼                                        ▼
record_action() ────────────────► record_card_emission()
        │                                        │
        ▼                                        ▼
recorder.record_action()        _db.insert_card_emission()
        │                       (ON CONFLICT (card_id) DO UPDATE)
        ▼
   resolve dont_learn (3 sources)
        │
        ▼
   _db.insert_card_action()  ─── PG: append-only trigger
        │
        ▼
   if dont_learn → RecordResult(skip_learning=True)
        │
        ▼
   context_from_action() → recommendation_type ?
        │
        ▼
   aggregate_signal_for_action()
        │
   ┌────┴─────────────────────────────────┐
   │                                      │
   ▼                                      ▼
preference_save (immediate)        accept/reject (window 5, threshold 0.7)
   │                                      │
   ▼                                      ▼
LearningSignal(hard_change=pending)   LearningSignal(soft)
   │                                      │
   ▼                                      ▼
request_hard_change()                apply_soft_signal()
                                         │
                                         ▼
                                preferences.set_preference()
                                (best-effort; reason on failure)
        │
        ▼
   update_card_action_flags(soft, hard)
        │
        ▼
   service._dispatch_record_events() ── emit:
        - aeis.advisor.history.action_recorded         (always)
        - aeis.advisor.history.skip_learning_recorded  (if dont_learn)
        - aeis.advisor.history.learning_signal_emitted (if signal)
        - aeis.advisor.history.hard_change_requested   (if preference_save)
        - aeis.advisor.history.soft_learning_applied   (if accept/reject auto-applied)
```

### 2.3. Singleton + thread-safety

`get_history_service()` jest klasycznym podwójnie-blokowanym singletonem
(`threading.Lock`), identycznym co do wzorca z
`sylion/governance/council_workflow.py` i `engine/service.py`.
`AdvisorHistoryService.attach_to_event_bus()` chroni `_event_bus` i
licznik `_subscribed` osobnym `_lock`. Brak per-request stanu —
serwis można dzielić między wątki.

`reset_history_service()` istnieje wyłącznie dla testów (drop
singletona). W produkcji nie wywoływane.

### 2.4. Trzy źródła `dont_learn`

`recorder.record_action()` rozstrzyga flagę `dont_learn` w deterministycznej
kolejności (zwarciowa — pierwszy True zatrzymuje resztę):

| # | Źródło | Implementacja |
|---|---|---|
| 1 | `context["dont_learn"]` (truthy) | `bool(enriched.get("dont_learn", False))` |
| 2 | Akcja `dont_learn_from_this` | `if action == "dont_learn_from_this": enriched_dont_learn = True` |
| 3 | Engine row lookup | `_engine_dont_learn(card_id)` → `engine.service.get_recommendation(card_id)` → `header["dont_learn"]` |

Po rozstrzygnięciu flaga jest dopisywana do `enriched["dont_learn"]`
(zostaje w JSONB context) plus, gdy źródłem był engine, dokładane jest
`enriched.setdefault("dont_learn_source", "engine_recommendation")`.
Każde wyjątkowe trafienie w wywołaniu engine'u (import error, missing
row, klucz niewystawiony w header) jest traktowane jako `False` —
jest to świadome **fail-open dla logowania** (zawsze zapisz, lepiej
mieć ślad niż go zgubić; flaga uczenia działa niezależnie).

### 2.5. Soft vs. hard learning

`signal_aggregator.aggregate_signal_for_action()` rozróżnia:

| Akcja | Sygnał | Próg | Auto-apply |
|---|---|---|---|
| `save_as_preference` | `preference_save` | brak (zawsze) | NIE — `hard_change_status='pending'`, czeka na `confirm_hard_change` |
| `accept` | `card_acceptance` | accept_rate >= 0.7 nad oknem 5 | TAK — `apply_soft_signal()` w pętli `_dispatch_record_events` |
| `reject` | `card_rejection` | reject_rate >= 0.7 nad oknem 5 | TAK — j.w. |
| inne (modify, remind_later, not_useful, convert_*) | brak | — | brak |

Stałe progowe są twarde w `signal_aggregator`:

```python
SOFT_LEARNING_WINDOW = 5
SOFT_LEARNING_THRESHOLD = 0.7
```

Próg 0.7 jest progiem **inkluzywnym** (`>=`). W oknie 5 akcji oznacza
to >=4 takich samych decyzji (4/5 = 0.8 dla accept lub reject).

### 2.6. Hard change lifecycle

`LearningSignal.hard_change_status` jest stringiem enumowanym
(domyślnie pusty `''`):

| Stan | Znaczenie | Przejście |
|---|---|---|
| `''` | Sygnał soft (`card_acceptance` / `card_rejection`) lub `preference_save` jeszcze nie zarejestrowany | wstaw do PG |
| `pending` | `preference_save` zarejestrowany, czeka na operatora | `request_hard_change()` |
| `confirmed` | Operator potwierdził, sygnał zaaplikowany do `preferences` (lub próba zaaplikowania zalogowana) | `confirm_hard_change()` |
| `rejected` | Operator odrzucił, sygnał nigdy nie idzie do `preferences` | `reject_hard_change()` |

Funkcje walidują operator-id — `confirm/reject_hard_change` zwracają
`False`, jeśli `signal.operator_id != operator_id` lub status ≠
`pending`. Status nie jest częścią kanonicznego schematu PG (kolumna
istnieje wyłącznie w MVP-mode; przyszła rewizja przeniesie ją do
osobnej tabeli `learning_signal_states`).

---

## 3. Konfiguracja

Moduł nie posiada własnego pliku konfiguracyjnego. Wszystkie zachowania
sterowane są:

| Mechanizm | Wartość | Lokalizacja |
|---|---|---|
| Pula PG | współdzielona z innymi modułami advisor | `sylion.aeis.advisor._db.get_pool()` |
| Próg soft-learning | 0.7 | `signal_aggregator.SOFT_LEARNING_THRESHOLD` |
| Okno soft-learning | 5 ostatnich akcji per typ | `signal_aggregator.SOFT_LEARNING_WINDOW` |
| Liczba przyszłych partycji | 3 miesiące | `partition_manager.create_next_partitions(months_ahead=3)` |
| Limit `list_actions_for_operator` | 100 | `service.list_actions_for_operator(limit=100)` |
| Singleton lock | `threading.Lock` | `service._service_lock` |

Zmienne środowiskowe wpływające pośrednio:

| Zmienna | Cel | Domyślna |
|---|---|---|
| `ADVISOR_PG_DSN` | DSN puli PG (psycopg) | host=localhost dbname=sylion user=sylion |
| `ADVISOR_PG_POOL_MIN` / `_MAX` | Rozmiar puli | 1 / 10 |

### 3.1. Inicjalizacja

```python
from sylion.aeis.advisor.history.service import register_subscribers
from sylion.core.event_bus import get_event_bus

bus = get_event_bus()
n_subs = register_subscribers(bus)
# n_subs == 3:
#   - "aeis.advisor.actions.action_routed"
#   - "aeis.advisor.engine.recommendation_emitted"
#   - subscribe_pattern("aeis.advisor.actions.*")  (gdy bus to wspiera)
```

`register_subscribers` jest idempotentna — drugie wywołanie nadpisuje
licznik (singleton lock chroni przed wyścigiem). `attach_to_event_bus`
zwraca `int` (liczba subskrypcji), tak samo jak engine.

### 3.2. Maintenance partition jobu

```python
from sylion.aeis.advisor.history.partition_manager import create_next_partitions

n = create_next_partitions(months_ahead=3)
# PG: tworzy advisor_history.card_actions_YYYY_MM dla 3 kolejnych miesięcy.
# SQLite test shim: zwraca 0 (PARTITION OF brak; warning w logu).
```

Job ten jest wywoływany przez scheduler maintenance (cron w
`scripts/start-server.ps1` lub równoważnik systemowy) raz na dobę.
Każda nowa partycja emituje
`aeis.advisor.history.partition_created` (event zadeklarowany w
manifeście; emisja z poziomu jobu — patrz §5).

---

## 4. Funkcje (RPC)

Kontrakt `proto/history.proto` (pakiet
`sylion.aeis.advisor.history.v1`) deklaruje 10 RPC. Dopóki codegen nie
zostanie uruchomiony, in-process API równoważne jest singletonowi
`AdvisorHistoryService` (`grpc_server.serve()` jest stub-em logującym
warning).

### 4.1. Tabela RPC

| RPC | Request | Response | Metoda Pythona | Side-effects |
|---|---|---|---|---|
| `RecordAction` | card_id, operator_id, action, operator_note, modified_recommendation, context | action_event_id, triggered_soft_learning, triggered_hard_learning_request, skip_learning | `record_action(...)` | INSERT do `card_actions`, UPDATE flag, INSERT do `learning_signals`, do 5 emitów |
| `GetActionsForCard` | card_id | repeated CardAction | `list_actions_for_card(card_id)` | none |
| `GetActionsForOperator` | operator_id, limit | repeated CardAction | `list_actions_for_operator(operator_id, limit=100)` | none |
| `ComputeHistoryMatch` | operator_id, recommendation_type, project_type, project_domain | similar_accepted_count, similar_rejected_count, similar_acceptance_rate | `get_history_match_snapshot(...)` | none (read-only count over context_jsonb) |
| `ComputeHistoricalAcceptanceRate` | operator_id, recommendation_type | operator_accepted_count, operator_rejected_count, operator_acceptance_rate_for_type | `get_historical_acceptance_snapshot(...)` | none |
| `GetLearningSignals` | operator_id, only_unapplied | repeated LearningSignal | `list_learning_signals(operator_id, only_unapplied=False)` | none |
| `ApplyPendingLearning` | operator_id | applied_count | `apply_pending_learning(operator_id)` | UPDATE `applied_to_preference` na zaaplikowanych, emit `soft_learning_applied` per signal |
| `ListPendingHardChangeRequests` | operator_id | repeated LearningSignal | `list_pending_hard_change_requests(operator_id)` | none |
| `ConfirmHardChange` | signal_id, operator_id | ok | `confirm_hard_change(signal_id, operator_id)` | UPDATE `hard_change_status='confirmed'`, próba `apply_soft_signal`, emit `soft_learning_applied` |
| `RejectHardChange` | signal_id, operator_id | ok | `reject_hard_change(signal_id, operator_id)` | UPDATE `hard_change_status='rejected'` |

### 4.2. RecordAction — pełny kontrakt

```protobuf
message RecordActionRequest {
  string card_id = 1;
  string operator_id = 2;
  string action = 3;            // jeden z CARD_ACTIONS
  string operator_note = 4;
  string modified_recommendation = 5;
  google.protobuf.Struct context = 6;
}

message RecordActionResponse {
  string action_event_id = 1;
  bool triggered_soft_learning = 2;
  bool triggered_hard_learning_request = 3;
  bool skip_learning = 4;
}
```

Walidacja po stronie Pythona:

| Pole | Walidacja |
|---|---|
| `card_id` | wymagane (puste → wczesny return w `_dispatch_inbound` przy emisji event-driven) |
| `operator_id` | wymagane |
| `action` | musi należeć do `CARD_ACTIONS` (9 wartości); przekroczenie — DB zwróci błąd ENUM `advisor_engine.card_action` |
| `context` | dict[str, Any]; akceptowane brakujące klucze |
| `modified_recommendation` | opcjonalne; semantycznie ważne tylko dla `action='modify'` |

Brak walidacji `action_event_id` w request — generowany przez
`_models.new_uuid()`.

### 4.3. ConfirmHardChange — semantyka best-effort

`confirm_hard_change(signal_id, operator_id)` zwraca `True` nawet jeśli
`apply_soft_signal()` nie powiodło się — wystarczy aby status zmienił
się na `confirmed`. Pole `applied_to_preference` flipuje tylko, jeśli
preferences faktycznie ustawi rekord. Operator widzi w UI „zatwierdzono",
ale audit log zachowuje ślad (warning loggera + brak emisji
`applied=true`).

```python
def confirm_hard_change(*, signal_id, operator_id) -> bool:
    signal = fetch_signal_by_id(signal_id)
    if signal is None or signal.operator_id != operator_id:
        return False
    if signal.hard_change_status != "pending":
        return False
    result = apply_soft_signal(signal)
    update_signal_hard_status(signal_id, "confirmed")
    if result.get("applied"):
        update_signal_applied(signal_id)
    else:
        log.warning(...)
    return True
```

### 4.4. ComputeHistoryMatch — model danych

Algorytm `count_similar_actions(operator_id, recommendation_type,
project_type, project_domain)`:

1. Buduje WHERE z `operator_id = %s AND context_jsonb LIKE
   '%"recommendation_type": "<type>"%'` plus opcjonalne `AND
   context_jsonb LIKE '%"project_type": "<pt>"%'` i `AND
   context_jsonb LIKE '%"project_domain": "<pd>"%'`.
2. Grupuje po `action`, sumuje liczbę występień.
3. Mapuje do `(accepted, rejected)` patrząc tylko na akcje
   `'accept'` i `'reject'` (modify / remind_later itp. nie liczą się
   jako pozytyw ani negatyw confidence).
4. `similar_acceptance_rate = accepted / (accepted + rejected)`,
   z fallback `0.0` przy braku danych.

LIKE-based query jest celowa — pozwala wspólnemu testowemu shim-owi
SQLite zachować ten sam plan zapytania. W PG indeks
`idx_card_actions_operator(operator_id, performed_at DESC)` przyspiesza
filtrację per-operator; sam fragment LIKE jest wykonywany filterstep-em
po-indeksowym.

### 4.5. ApplyPendingLearning — semantyka pętli

```python
def apply_pending_learning(self, operator_id: str) -> int:
    applied = 0
    for signal in fetch_learning_signals(operator_id, only_unapplied=True):
        if signal.hard_change_status == "pending":
            continue                 # czeka na operatora
        if signal.signal_type == "preference_save":
            continue                 # save_as_preference idzie tylko przez confirm/reject
        result = apply_soft_signal(signal)
        self._emit("aeis.advisor.history.soft_learning_applied", {...})
        if result.get("applied"):
            applied += 1
    return applied
```

Kluczowe decyzje:

| Warunek | Zachowanie |
|---|---|
| `hard_change_status == "pending"` | pomiń — operator decyduje |
| `signal_type == "preference_save"` | pomiń — taki sygnał idzie wyłącznie ścieżką confirm/reject |
| `apply_soft_signal()` → `applied=False` | emit eventu z `applied=false` i `reason`, `applied` count się nie zwiększa |

---

## 5. Eventy

Manifest `aeis.advisor.history.json` deklaruje 7 emitowanych i 2
subskrybowane eventy. Trzeci emitowany event `partition_created`
emituje `partition_manager` (zarejestrowany w manifeście; nie wystawia
go bezpośrednio `service.py`).

### 5.1. Eventy emitowane

| Topic | Trigger | Idempotency key | Payload |
|---|---|---|---|
| `aeis.advisor.history.action_recorded` | każde wywołanie `record_action` | `action_event_id` | action_event_id, card_id, operator_id, action, performed_at, triggered_soft_learning, triggered_hard_learning_request |
| `aeis.advisor.history.skip_learning_recorded` | `dont_learn` rozstrzygnięty na True | `action_event_id` | action_event_id, card_id, operator_id, reason (`"dont_learn_flag"`) |
| `aeis.advisor.history.learning_signal_emitted` | po insert do `learning_signals` (signal != None, dont_learn == False) | `signal_id` | signal_id, operator_id, signal_type, preference_key, context_project_type, context_project_domain, signal_strength, source_card_id, source_action_event_id |
| `aeis.advisor.history.hard_change_requested` | `signal_type == "preference_save"` | `signal_id` | signal_id, operator_id, preference_key, context_project_type, context_project_domain, source_card_id |
| `aeis.advisor.history.soft_learning_applied` | po `apply_soft_signal`, w pętli `_dispatch_record_events` lub w `apply_pending_learning` lub w `confirm_hard_change` | `signal_id` | signal_id, operator_id, preference_key, applied (bool), reason |
| `aeis.advisor.history.partition_created` | utworzenie nowej partycji `card_actions_YYYY_MM` | `<partition_name>` | partition_name, year, month, created_at (emit po stronie schedulera, nie service.py) |
| `aeis.advisor.history.confidence_components_calculated` | wywołanie któregokolwiek `get_*_snapshot` z eksportowanego endpointu (deklarowany w manifeście; niewystawiany bezpośrednio przez service — przyszła rewizja) | brak | (nieaktywny w bieżącej implementacji) |

Wszystkie emisje używają `service._emit(topic, payload)` budującego
`SylionEvent` z `event_id=uuid.uuid4().hex`,
`source_module="sylion.aeis.advisor.history"`,
`timestamp=time.time()`. Idempotency key wybierany z payloadu
(`action_event_id` lub `signal_id`); brak klucza → pusty string
(akceptowalne — sam `event_id` UUID gwarantuje unikalność na busie).

`_emit` jest **best-effort**: cały blok jest w `try/except Exception`
z `log.exception(...)`. Błąd busa nie wywraca recordera.

### 5.2. Eventy subskrybowane

| Topic | Handler | Co robi |
|---|---|---|
| `aeis.advisor.actions.action_routed` | `_dispatch_inbound` → `service.record_action` | Pobiera card_id / operator_id / action z payloadu, dokleja `recommendation_type`, `project_type`, `project_domain`, `preference_key` do contextu (jeśli znajdują się w payloadzie a nie w context), wywołuje `record_action` |
| `aeis.advisor.engine.recommendation_emitted` | `_dispatch_inbound` → `service.record_card_emission` | Lekka migawka karty do `card_emissions` (UPSERT po `card_id`); używana do trend analysis |

Plus opcjonalna `subscribe_pattern("aeis.advisor.actions.*", _handler)`
gdy bus to wspiera — zwiększa licznik `_subscribed` o 1 (do 3
łącznie).

Walidacja inboundu w `_dispatch_inbound`:

```python
if not card_id or not operator_id or not action:
    return       # cicho odrzuca event z brakującymi polami
```

— moduł nie alarmuje na rebroadcast czy zduplikowane eventy; idempotencja
zapewniana po stronie samej operacji DB (UNIQUE PK action_event_id w
PG; UPSERT w `card_emissions`).

### 5.3. Korelacja z eventami sąsiednich modułów

| Zewnętrzny event | Skutek w history | Następnie |
|---|---|---|
| `aeis.advisor.actions.action_routed` (z `actions`) | INSERT `card_actions`, opcjonalnie INSERT `learning_signals` | emisja `action_recorded` (+ ewentualnie 1–3 follow-up eventy) |
| `aeis.advisor.engine.recommendation_emitted` (z `engine`) | UPSERT `card_emissions` (lightweight metadata) | brak emisji history-side |
| `aeis.advisor.preferences.preference_set` (z `preferences`) | NIE wpływa — preferences sam zapisuje, history nie subskrybuje | — |

Cykl: po `confirm_hard_change` history wywołuje
`apply_soft_signal` → `preferences.set_preference` → preferences
emituje `preference_set` — **history nie reaguje na ten event**. Brak
pętli zwrotnej.

---

## 6. Tabele DB

### 6.1. `advisor_history.card_actions` — append-only, partycjonowana

```sql
CREATE TABLE advisor_history.card_actions (
  action_event_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  card_id              UUID NOT NULL,
  operator_id          UUID NOT NULL,
  action               advisor_engine.card_action NOT NULL,
  operator_note        TEXT,
  modified_recommendation TEXT,
  context_jsonb        JSONB,
  created_human_gate_ticket_id UUID,
  created_masterplan_proposal_id UUID,
  saved_preference_id  UUID,
  triggered_soft_learning BOOLEAN NOT NULL DEFAULT false,
  triggered_hard_learning_request BOOLEAN NOT NULL DEFAULT false,
  performed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (performed_at);

CREATE TABLE advisor_history.card_actions_2026_04 PARTITION OF advisor_history.card_actions
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE advisor_history.card_actions_2026_05 PARTITION OF advisor_history.card_actions
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE advisor_history.card_actions_2026_06 PARTITION OF advisor_history.card_actions
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX idx_card_actions_card     ON advisor_history.card_actions(card_id);
CREATE INDEX idx_card_actions_operator ON advisor_history.card_actions(operator_id, performed_at DESC);
CREATE INDEX idx_card_actions_action   ON advisor_history.card_actions(action);
```

#### 6.1.1. Trigger append-only

```sql
CREATE OR REPLACE FUNCTION advisor_history.block_modifications()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'advisor_history tables are append-only';
END;
$$ LANGUAGE plpgsql;
```

Wywołanie `UPDATE` lub `DELETE` na partycji z podpiętym triggerem
podnosi `RAISE EXCEPTION`. Trigger nie jest podpinany do tabeli
nadrzędnej — `partition_manager` (WP6) podpina go per-partition po
`CREATE TABLE ... PARTITION OF ...`.

#### 6.1.2. Whitelisted UPDATE: dwie kolumny flagowe

`update_card_action_flags` jest jedynym sankcjonowanym sposobem
modyfikacji `card_actions`. Zezwala na zmianę dokładnie dwóch pól:

```python
def update_card_action_flags(*, action_event_id, triggered_soft_learning=None,
                              triggered_hard_learning_request=None) -> None:
    sets = []
    if triggered_soft_learning is not None:
        sets.append("triggered_soft_learning = %s")
    if triggered_hard_learning_request is not None:
        sets.append("triggered_hard_learning_request = %s")
    # UPDATE advisor_history.card_actions SET <sets> WHERE action_event_id = %s
```

Funkcja jest wywoływana wyłącznie z `recorder.record_action` po
agregacji sygnału. **W praktyce produkcyjnej** trigger append-only
podpięty per-partition jest zwykle wykluczony dla tych dwóch kolumn
poprzez whitelisting na poziomie funkcji DB (przyszła rewizja
schematu); w MVP polegamy na konwencji „nikt poza recorderem nie pisze".

#### 6.1.3. Mapowanie kolumn → CardAction

| Kolumna | Pole `_models.CardAction` | Konwersja |
|---|---|---|
| `action_event_id` UUID | `action_event_id: str` | str(uuid) |
| `card_id` UUID | `card_id: str` | str(uuid) |
| `operator_id` UUID | `operator_id: str` | str(uuid) |
| `action` ENUM | `action: str` | walidacja przez DB ENUM |
| `operator_note` TEXT | `operator_note: str` | NULL → "" |
| `modified_recommendation` TEXT | `modified_recommendation: str` | NULL → "" |
| `context_jsonb` JSONB | `context: dict[str, Any]` | json.dumps przy INSERT, json.loads przy SELECT |
| `created_human_gate_ticket_id` UUID | `created_human_gate_ticket_id: str` | NULL → "" |
| `created_masterplan_proposal_id` UUID | `created_masterplan_proposal_id: str` | NULL → "" |
| `saved_preference_id` UUID | `saved_preference_id: str` | NULL → "" |
| `triggered_soft_learning` BOOLEAN | `triggered_soft_learning: bool` | int(bool) przy INSERT (kompatybilność z SQLite test shim) |
| `triggered_hard_learning_request` BOOLEAN | `triggered_hard_learning_request: bool` | int(bool) |
| `performed_at` TIMESTAMPTZ | `performed_at: float` | epoch seconds |

### 6.2. `advisor_history.learning_signals` — append-only by convention

```sql
CREATE TABLE advisor_history.learning_signals (
  signal_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id          UUID NOT NULL,
  signal_type          TEXT NOT NULL,
  preference_key       TEXT,
  context_project_type TEXT,
  context_project_domain TEXT,
  signal_strength      DOUBLE PRECISION NOT NULL CHECK (signal_strength >= 0.0 AND signal_strength <= 1.0),
  source_card_id       UUID,
  source_action_event_id UUID,
  applied_to_preference BOOLEAN NOT NULL DEFAULT false,
  applied_at           TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_learning_signals_operator   ON advisor_history.learning_signals(operator_id, created_at DESC);
CREATE INDEX idx_learning_signals_unapplied  ON advisor_history.learning_signals(operator_id) WHERE NOT applied_to_preference;
```

#### 6.2.1. Pole `hard_change_status` (MVP-only)

Kolumna istnieje w MVP-mode (test SQLite shim + PG poprzez Alembic
revision) i nie jest częścią kanonicznego DDL z 02_postgresql_schema.sql.
Wartości:

| Wartość | Znaczenie |
|---|---|
| `''` (empty string) | sygnał soft (`card_acceptance` / `card_rejection`) — nie podlega flow hard |
| `'pending'` | `preference_save` zarejestrowany — czeka na operatora |
| `'confirmed'` | operator potwierdził — sygnał zaaplikowany (lub próbowano zaaplikować) |
| `'rejected'` | operator odrzucił — sygnał zostaje w PG ze statusem rejected, `applied_to_preference` pozostaje false |

#### 6.2.2. Reguły CHECK i indeksy

| Reguła | Wartość |
|---|---|
| `signal_strength` BETWEEN 0.0 AND 1.0 | egzekwowane na DB-poziomie |
| `signal_type` ∈ SIGNAL_TYPES | walidowane w aplikacji (TEXT, brak ENUM po stronie DB) |
| `applied_to_preference = false` AND `applied_at IS NULL` na nowych | konwencja, brak CHECK |
| `idx_learning_signals_unapplied` | partial index — szybki query `apply_pending_learning` |

### 6.3. `advisor_history.card_emissions` — UPSERT, lightweight

Tabela dev/test (Alembic-only — **nie istnieje w kanonicznym DDL z
`02_postgresql_schema.sql`**, schemat tworzony równolegle przez
`init_history_schema` w MVP-mode lub Alembic revision).

```sql
CREATE TABLE advisor_history.card_emissions (
  card_id              UUID PRIMARY KEY,
  operator_id          UUID,
  recommendation_type  TEXT,
  project_type         TEXT,
  project_domain       TEXT,
  risk_level           TEXT,
  emitted_at           DOUBLE PRECISION NOT NULL
);
```

UPSERT jest po `card_id`:

```sql
INSERT INTO advisor_history.card_emissions (...)
VALUES (...)
ON CONFLICT (card_id) DO UPDATE SET
  operator_id = EXCLUDED.operator_id,
  recommendation_type = EXCLUDED.recommendation_type,
  project_type = EXCLUDED.project_type,
  project_domain = EXCLUDED.project_domain,
  risk_level = EXCLUDED.risk_level,
  emitted_at = EXCLUDED.emitted_at;
```

Tabela jest **wyjątkiem od reguły append-only** — celem jest snapshot
„ostatnia wersja karty wyemitowana", a nie historia emisji. History
akcji (`card_actions`) zachowuje pełen ślad operatorski.

### 6.4. Macierz źródeł zapisu

| Tabela | INSERT | UPDATE | DELETE |
|---|---|---|---|
| `card_actions` | `_db.insert_card_action` (z `record_action`) | `_db.update_card_action_flags` (whitelist 2 kolumny, z recordera) | nigdy (RAISE EXCEPTION trigger) |
| `learning_signals` | `_db.insert_learning_signal` (z `signal_aggregator`) | `_db.update_signal_applied`, `_db.update_signal_hard_status` (z `soft_learning` / `hard_learning`) | nigdy (konwencja) |
| `card_emissions` | `_db.insert_card_emission` UPSERT (z `record_card_emission`) | wbudowane w UPSERT | nigdy (konwencja) |

Każda inna ścieżka pisania (REST adapter, ad-hoc script) **musi
przechodzić przez te metody** — w przeciwnym razie obejdzie cykl
emisji eventów oraz reguły append-only.

---

## 7. Przykład użycia

### 7.1. Operator akceptuje rekomendację, próg soft-learning trafiony

```python
from sylion.aeis.advisor.history.service import get_history_service

svc = get_history_service()

# 1) Wcześniej operator zaakceptował 3 z 5 ostatnich kart typu
#    "use_postgres_for_oltp" — accept_rate = 0.6 (poniżej progu 0.7).
# 2) Operator akceptuje 4. kartę → accept_rate = 4/5 = 0.8 ≥ 0.7.

action_event_id = svc.record_action(
    card_id="6e1c4b3a-...uuid...",
    operator_id="11111111-1111-1111-1111-111111111111",
    action="accept",
    operator_note="LGTM, postgres dla OLTP standardem domu",
    context={
        "recommendation_type": "use_postgres_for_oltp",
        "project_type": "saas_b2b",
        "project_domain": "fintech",
        "preference_key": "default_db",
    },
)
# Wewnętrznie:
#  - INSERT card_actions (append-only)
#  - aggregate_signal_for_action: accept_rate = 0.8 ≥ 0.7
#    → INSERT learning_signals (signal_type='card_acceptance', strength=0.8)
#  - update_card_action_flags(triggered_soft_learning=True)
#  - apply_soft_signal: best-effort call do preferences.set_preference
#  - emit:
#      aeis.advisor.history.action_recorded             { action_event_id, ... }
#      aeis.advisor.history.learning_signal_emitted     { signal_id, ... }
#      aeis.advisor.history.soft_learning_applied       { applied=true, reason="ok" }
```

### 7.2. Operator zapisuje preferencję — hard change

```python
# Operator klika "Save as preference" na karcie.
action_event_id = svc.record_action(
    card_id="9aa1...uuid...",
    operator_id="22222222-2222-2222-2222-222222222222",
    action="save_as_preference",
    operator_note="Use Stripe Checkout for all payments",
    context={
        "recommendation_type": "use_stripe_checkout",
        "project_type": "ecommerce",
        "preference_key": "default_payment_provider",
    },
)
# Wewnętrznie:
#  - INSERT card_actions
#  - aggregate_signal_for_action: action == "save_as_preference"
#    → INSERT learning_signals (signal_type='preference_save', strength=1.0,
#                                hard_change_status='pending')
#  - request_hard_change(signal): no-op (status już 'pending')
#  - update_card_action_flags(triggered_hard_learning_request=True)
#  - emit: aeis.advisor.history.action_recorded
#         aeis.advisor.history.learning_signal_emitted
#         aeis.advisor.history.hard_change_requested

# Lista oczekujących na potwierdzenie:
pending = svc.list_pending_hard_change_requests(
    operator_id="22222222-2222-2222-2222-222222222222"
)
# pending = [
#   {
#     "signal_id": "...",
#     "signal_type": "preference_save",
#     "preference_key": "default_payment_provider",
#     "hard_change_status": "pending",
#     ...
#   },
# ]

# Operator potwierdza w UI:
ok = svc.confirm_hard_change(signal_id=pending[0]["signal_id"],
                              operator_id="22222222-2222-2222-2222-222222222222")
# ok == True
# Wewnętrznie:
#  - apply_soft_signal: preferences.set_preference(...)
#  - update_signal_hard_status(signal_id, "confirmed")
#  - update_signal_applied (jeśli preferences zwróciło applied=true)
#  - emit: aeis.advisor.history.soft_learning_applied { reason='hard_change_confirmed' }
```

### 7.3. Operator korzysta z `dont_learn`

```python
action_event_id = svc.record_action(
    card_id="ccc...uuid...",
    operator_id="33333333-3333-3333-3333-333333333333",
    action="dont_learn_from_this",
    context={
        "recommendation_type": "switch_to_kafka",
        # operator nie chce, by jednorazowy odrzut wpłynął na statystyki
    },
)
# Wewnętrznie:
#  - dont_learn ustawione: _engine_dont_learn skip (action=='dont_learn_from_this')
#  - INSERT card_actions z context["dont_learn"]=True
#  - return RecordResult(skip_learning=True, reason="dont_learn_flag")
#  - emit: aeis.advisor.history.action_recorded
#          aeis.advisor.history.skip_learning_recorded { reason="dont_learn_flag" }
#  - NO learning_signal, NO soft_learning_applied
```

### 7.4. Engine pyta history o snapshot confidence

```python
# Wnętrze engine.confidence_calculator:
hist_snap = svc.get_history_match_snapshot(
    operator_id="44444444-4444-4444-4444-444444444444",
    recommendation_type="use_postgres_for_oltp",
    project_type="saas_b2b",
    project_domain="fintech",
)
# hist_snap = {
#   "similar_accepted_count": 12,
#   "similar_rejected_count": 3,
#   "similar_acceptance_rate": 0.8,
# }

acc_snap = svc.get_historical_acceptance_snapshot(
    operator_id="44444444-4444-4444-4444-444444444444",
    recommendation_type="use_postgres_for_oltp",
)
# acc_snap = {
#   "operator_accepted_count": 47,
#   "operator_rejected_count": 9,
#   "operator_acceptance_rate_for_type": 0.839,
# }
```

Engine używa tych snapshotów w 4-składnikowej formule confidence
(zob. moduł 05) — `history_match` waga 0.4, `historical_acceptance`
uśredniona z innym składnikiem w ramach 0.4.

### 7.5. Subskrypcja event-driven (preferowana ścieżka produkcyjna)

```python
# main.py / bootstrap:
from sylion.core.event_bus import get_event_bus
from sylion.aeis.advisor.history.service import register_subscribers

bus = get_event_bus()
n = register_subscribers(bus)
# n == 3 (action_routed, recommendation_emitted, pattern actions.*)

# Następnie actions.HandleAction emituje aeis.advisor.actions.action_routed.
# History subskrybent automatycznie woła record_action — bez bezpośredniego
# wywołania REST/gRPC po stronie actions. Ten flow jest podstawowy dla
# WP6/operator-mobile, gdzie actions/HTTP-server emituje, history zapisuje.
```

### 7.6. Maintenance: tworzenie partycji

```bash
# Cron raz dziennie o 03:00 UTC:
python -c "from sylion.aeis.advisor.history.partition_manager import create_next_partitions; print(create_next_partitions(months_ahead=3))"
# Output: 0 (wszystkie 3 już istnieją) lub 1/2/3 (utworzono nowe).
# Każda nowa partycja → emisja aeis.advisor.history.partition_created
# z payloadem { partition_name, year, month, created_at }.
```

---

## 8. Komendy weryfikacyjne

### 8.1. Szybki smoke test: in-process

```bash
python - <<'PY'
import time, uuid
from sylion.aeis.advisor.history.service import get_history_service, reset_history_service

reset_history_service()
svc = get_history_service()

operator = str(uuid.uuid4())
card = str(uuid.uuid4())

aid = svc.record_action(
    card_id=card,
    operator_id=operator,
    action="accept",
    context={"recommendation_type": "use_postgres_for_oltp"},
)
print("action_event_id:", aid)
print("actions:", len(svc.list_actions_for_card(card)))
print("snapshot:", svc.get_history_match_snapshot(
    operator_id=operator, recommendation_type="use_postgres_for_oltp"))
PY
```

### 8.2. Pełen golden test suite

```bash
cd C:/Users/razor/Desktop/pipeline_glm/src/sylion-pipeline
python -m pytest tests/aeis/advisor/history/ -v
```

Zestaw goldenów (z manifestu, `minimum_required`):

| Test | Cel |
|---|---|
| `record_action_persists_row_and_emits_event` | INSERT + emit `action_recorded` |
| `dont_learn_flag_skips_learning_signal_creation` | flag z 3 źródeł skip aggregate, emit `skip_learning_recorded` |
| `soft_learning_triggers_after_threshold_accept_streak` | 4/5 accept → signal `card_acceptance`, apply soft, emit `soft_learning_applied` |
| `hard_change_request_emits_event_and_pendable_for_confirmation` | `save_as_preference` → `pending` + emit `hard_change_requested` + listing pending |
| `confidence_provider_history_match_returns_expected_shape` | shape `{similar_accepted_count, similar_rejected_count, similar_acceptance_rate}` |
| `confidence_provider_historical_acceptance_returns_expected_shape` | shape `{operator_accepted_count, operator_rejected_count, operator_acceptance_rate_for_type}` |
| `partition_manager_noop_on_sqlite_returns_zero` | SQLite shim → 0, brak crash |

### 8.3. Inspekcja DB (PG)

```bash
# Łączna liczba akcji per operator (forever-retention partycje):
psql "$ADVISOR_PG_DSN" -c "
  SELECT operator_id, action, COUNT(*) AS n
  FROM advisor_history.card_actions
  GROUP BY operator_id, action
  ORDER BY operator_id, n DESC;
"

# Partycje miesięczne na żywo:
psql "$ADVISOR_PG_DSN" -c "
  SELECT inhrelid::regclass AS partition,
         pg_get_expr(c.relpartbound, c.oid) AS bounds
  FROM pg_inherits i
  JOIN pg_class c ON c.oid = i.inhrelid
  WHERE i.inhparent = 'advisor_history.card_actions'::regclass
  ORDER BY 1;
"

# Test trigger append-only:
psql "$ADVISOR_PG_DSN" -c "
  UPDATE advisor_history.card_actions_2026_04 SET operator_note = 'tampered'
  WHERE action_event_id IN (SELECT action_event_id FROM advisor_history.card_actions_2026_04 LIMIT 1);
"
# Spodziewany błąd: 'advisor_history tables are append-only'

# Pending hard changes per operator:
psql "$ADVISOR_PG_DSN" -c "
  SELECT signal_id, preference_key, signal_strength, created_at
  FROM advisor_history.learning_signals
  WHERE hard_change_status = 'pending'
  ORDER BY created_at DESC LIMIT 20;
"

# Soft-learning candidates (only_unapplied=True):
psql "$ADVISOR_PG_DSN" -c "
  SELECT signal_id, signal_type, preference_key, signal_strength
  FROM advisor_history.learning_signals
  WHERE NOT applied_to_preference
    AND hard_change_status <> 'pending'
    AND signal_type IN ('card_acceptance', 'card_rejection')
  ORDER BY created_at DESC;
"
```

### 8.4. Weryfikacja contract-rev (manifest vs. emisja)

```bash
python - <<'PY'
import json
manifest = json.load(open("src/sylion-pipeline/sylion/contracts/manifests/aeis.advisor.history.json"))
declared = set(manifest["events_emit"])
import re
src = open("src/sylion-pipeline/sylion/aeis/advisor/history/service.py").read()
emitted = set(re.findall(r'"(aeis\.advisor\.history\.[a-z_]+)"', src))
extra_partition = {"aeis.advisor.history.partition_created"}
emitted_total = emitted | extra_partition
print("declared:", sorted(declared))
print("emitted:", sorted(emitted_total))
print("delta:", declared.symmetric_difference(emitted_total))
PY
```

`confidence_components_calculated` jest zadeklarowany w manifeście, ale
w bieżącej rewizji service.py go nie emituje — to świadoma rezerwa
dla przyszłej rewizji (telemetry o wykonaniu komponentu).

### 8.5. Check subskrypcji

```python
# tests/aeis/advisor/history/test_subscriptions.py
from sylion.core.event_bus import InMemoryEventBus
from sylion.aeis.advisor.history.service import register_subscribers, reset_history_service

reset_history_service()
bus = InMemoryEventBus()
n = register_subscribers(bus)
assert n >= 2  # action_routed + recommendation_emitted (+ 1 jeśli pattern wspierany)
assert "aeis.advisor.actions.action_routed" in bus.subscribers
assert "aeis.advisor.engine.recommendation_emitted" in bus.subscribers
```

---

## 9. Troubleshooting

### 9.1. „advisor_history tables are append-only"

| Objaw | Przyczyna | Naprawa |
|---|---|---|
| `psycopg.errors.RaiseException: advisor_history tables are append-only` przy UPDATE | Trigger `block_modifications` na partycji blokuje | Użyj `update_card_action_flags` (whitelist 2 kolumny) lub stwórz osobny INSERT (dla nowej akcji). DELETE dozwolone tylko poprzez DROP PARTITION przez ops |
| Trigger nie zadziałał (UPDATE przeszedł) | Partycja nowa, partition_manager nie podpiął triggera | Wywołaj ręcznie: `ALTER TABLE advisor_history.card_actions_YYYY_MM ADD CONSTRAINT ... TRIGGER ...` lub uruchom WP6 maintenance job |

### 9.2. Soft learning nie aplikuje

| Objaw | Przyczyna | Diagnostyka |
|---|---|---|
| `apply_soft_signal` zwraca `applied=False, reason="preferences_grpc_unreachable"` | Moduł `preferences.service` niedostępny (import error / serwis niezainicjalizowany / brak `set_preference`/`upsert_preference`) | Sprawdź log warning: `preferences module not importable` / `preferences service unavailable` / `preferences service has no set_preference / upsert_preference` |
| `apply_soft_signal` z `reason="preferences_grpc_unreachable"` + `underlying_error` | Wywołanie do preferences poszło, ale podniosło wyjątek runtime | Pole `underlying_error` zawiera `ClassName:msg`; sprawdź logi preferences |
| Pętla `apply_pending_learning` zwraca 0 mimo nieaplikowanych sygnałów | wszystkie sygnały mają `hard_change_status=='pending'` lub `signal_type=='preference_save'` | Sprawdź w PG: `SELECT signal_type, hard_change_status FROM ... WHERE applied_to_preference=false` |

### 9.3. Hard change nie znika z listy

| Objaw | Przyczyna | Naprawa |
|---|---|---|
| `confirm_hard_change` zwraca `False` | `signal.operator_id != operator_id` lub status != `pending` | Zweryfikuj operator-id wywołującego (najczęściej confused-deputy: UI dostaje signal z innego operatora), sprawdź `hard_change_status` |
| `confirm_hard_change` zwraca `True`, ale `applied_to_preference` nadal `false` | preferences nie zaaplikowało (zob. 9.2) | Sprawdź log warning: `hard change confirmed but preferences apply failed` |
| `list_pending_hard_change_requests` puste, choć operator widział kartę | Sygnał `preference_save` nie powstał (np. dont_learn=True) lub akcja nie była `save_as_preference` | Sprawdź `card_actions.context_jsonb->'dont_learn'`, sprawdź `card_actions.action` |

### 9.4. Confidence snapshot zwraca zera

| Objaw | Przyczyna | Naprawa |
|---|---|---|
| `similar_acceptance_rate == 0.0` mimo dziesiątek akcji | `recommendation_type` w query nie pasuje do tego w `context_jsonb` | Sprawdź case-sensitivity i exact match — query używa LIKE z `"recommendation_type": "<exact>"`. Brak normalizacji case |
| `operator_acceptance_rate_for_type == 0.0` mimo akcji | Brak akcji dokładnie typu `accept` lub `reject` (operator klika `modify`/`remind_later` — nie liczone) | Sprawdź `action` w `card_actions` — tylko accept/reject zaliczają się do mianownika |
| Błędne wartości po reset DB | Test zapomniał `reset_history_service()` — singleton trzyma starą referencję do bus | W setUp testu wołaj `reset_history_service()` |

### 9.5. Subskrypcje nie działają

| Objaw | Przyczyna | Naprawa |
|---|---|---|
| `_subscribed == 0` | `event_bus` nie ma metody `subscribe` | Sprawdź typ busa — InMemoryEventBus z Sylion Core zawsze ma `subscribe` |
| `record_action` nie wywoływane mimo emitów | Pattern `aeis.advisor.actions.*` nie zarejestrowany ani konkretny topic — moduł actions emituje na innym topic-u | Zweryfikuj actions: `aeis.advisor.actions.action_routed` (nie `action_recorded`!) |
| `_dispatch_inbound` cicho odrzuca | Brak `card_id` / `operator_id` / `action` w payloadzie | Zaloguj payload przed handlerem (`_handler` ma try/except — błędy są w `log.exception`); sprawdź producenta eventu |

### 9.6. Partycja nie tworzy się

| Objaw | Przyczyna | Naprawa |
|---|---|---|
| `create_next_partitions(months_ahead=3)` zwraca 0 w PG | Wszystkie 3 partycje już istnieją (CREATE TABLE IF NOT EXISTS no-op) | Normalne — sprawdź `pg_inherits` (zob. §8.3) |
| `create_next_partitions` zwraca 0 w teście | SQLite shim nie obsługuje `PARTITION OF` (warning w log, RaiseException na execute) | Oczekiwane — golden test `partition_manager_noop_on_sqlite_returns_zero` to weryfikuje |
| `Insert into card_actions` failuje z `no partition of relation found` | Brak partycji na `performed_at` (np. system działa w przyszłym miesiącu, partition_manager nie odpalony) | Wywołaj `create_next_partitions(months_ahead=3)` ręcznie; dodaj cron |

### 9.7. Diagnostyka via emisje

```bash
# Tail event log dla aeis.advisor.history.*:
psql "$ADVISOR_PG_DSN" -c "
  SELECT topic, payload->>'card_id' AS card, payload->>'reason' AS reason, ts
  FROM advisor_events.events
  WHERE topic LIKE 'aeis.advisor.history.%'
  ORDER BY ts DESC LIMIT 50;
"
```

Brak `action_recorded` przy obecnej akcji w DB → sprawdź `service._emit`
warning logger (`event emit failed for topic=...`).

---

## 10. Powiązania

### 10.1. Zależności wstępujące (depends_on)

| Moduł | Wykorzystanie | Plik |
|---|---|---|
| `sylion.aeis.advisor.engine` | `get_engine_service().get_recommendation(card_id)` w `_engine_dont_learn` (3. źródło flagi) | `recorder.py` |
| `sylion.aeis.advisor.preferences` | `get_preferences_service().set_preference()` / `upsert_preference()` w `apply_soft_signal` | `learning/soft_learning.py` |
| `sylion.aeis.advisor.actions` | subskrypcja `aeis.advisor.actions.action_routed` (oraz pattern `*`) | `service.py` |
| `sylion.aeis.advisor._db` | współdzielona pula PG (psycopg) | `_db.py`, `partition_manager.py` |
| `sylion.core.event_bus` | `SylionEvent`, `subscribe`, `subscribe_pattern`, `publish` | `service.py`, `partition_manager.py` |

### 10.2. Zależności zstępujące (kto używa history)

| Konsument | Wykorzystanie |
|---|---|
| `sylion.aeis.advisor.engine` (confidence_calculator) | `get_history_match_snapshot`, `get_historical_acceptance_snapshot` — 2 z 4 składników confidence |
| REST `/api/aeis/advisor/history/*` (operator-mobile) | wszystkie 10 RPC — listing, confirm/reject, snapshots |
| `sylion.aeis.advisor.feed` (UI Advisor Feed) | `list_actions_for_operator` przy renderowaniu „twoja historia akcji" |
| `tests/aeis/advisor/engine/` | golden testy zależą od `record_action` jako fixture'a setup |

### 10.3. Mapa eventów

```
                 ┌──────────────────────────────────┐
                 │    sylion.aeis.advisor.actions   │
                 └──────────────────────────────────┘
                                │
                                │ aeis.advisor.actions.action_routed
                                ▼
        ┌─────────────────────────────────────────────────┐
        │        sylion.aeis.advisor.history (THIS)        │
        └─────────────────────────────────────────────────┘
                                │
   ┌────────────────────────────┼─────────────────────────────────┐
   │                            │                                 │
   ▼                            ▼                                 ▼
aeis.advisor.history.action_recorded                          aeis.advisor.history.skip_learning_recorded
aeis.advisor.history.learning_signal_emitted
aeis.advisor.history.hard_change_requested
aeis.advisor.history.soft_learning_applied
aeis.advisor.history.partition_created
                                │
                                ▼
                 ┌──────────────────────────────────┐
                 │    sylion.aeis.advisor.events    │
                 │  (audit subscriber → events DB)  │
                 └──────────────────────────────────┘

                 ┌──────────────────────────────────┐
                 │    sylion.aeis.advisor.engine    │
                 └──────────────────────────────────┘
                                │
                                │ aeis.advisor.engine.recommendation_emitted
                                ▼
                 ┌──────────────────────────────────┐
                 │  history.record_card_emission()  │
                 │  UPSERT card_emissions           │
                 └──────────────────────────────────┘
```

### 10.4. Cykl życia karty + history

| Faza | Moduł | Tabela history |
|---|---|---|
| Wygenerowanie karty | engine.orchestrator | `card_emissions` (UPSERT poprzez subskrypcję `recommendation_emitted`) |
| Operator widzi kartę | UI/feed | brak (read-only z engine) |
| Operator klika akcję | actions.HandleAction | brak (actions emituje action_routed) |
| History rejestruje akcję | history.service (subskrypcja) | `card_actions` (INSERT append-only) |
| Aggregator buduje sygnał | history.signal_aggregator | `learning_signals` (INSERT) |
| Soft auto-apply | history.soft_learning → preferences | `learning_signals.applied_to_preference=true` |
| Hard request | history.hard_learning | `learning_signals.hard_change_status='pending'` |
| Operator confirm | history.confirm_hard_change | `learning_signals.hard_change_status='confirmed'`, applied_to_preference (jeśli preferences ok) |
| Engine pyta o confidence | history.confidence_provider | read-only count nad `card_actions` |

### 10.5. Powiązane dokumenty

| Dokument | Sekcja relevantna |
|---|---|
| `01_master_spec.md` | §4 (lifecycle 14–16: record action → soft learning → optional hard-change), §9.3 (3D preference matrix + soft learning rules) |
| `02_postgresql_schema.sql` | sekcja `advisor_history` (linie 465–524) |
| `03_module_manifests.md` | §9 (history manifest spec, golden tests) |
| `07_event_taxonomy.md` | §4.9 (history events, idempotency keys) |
| `08_audit_revisions.md` | Revision 2 (PG-only mode, SQLite tylko jako test fixture) |
| `30_event_taxonomy_full.md` (ten projekt) | sekcja `history.*` events |
| `31_d_ladder_complete.md` (ten projekt) | nie dotyczy bezpośrednio (D-ladder w engine) |
| `32_evidence_pack_templates.md` | nie dotyczy (evidence packs w engine) |

### 10.6. Architektoniczne decyzje

| ADR | Decyzja | Moduł history |
|---|---|---|
| ADR-2026-04-01 | Append-only audit z RAISE EXCEPTION | `card_actions` partitioned, trigger per-partition |
| ADR-2026-04-12 | 4-składnikowa formuła confidence | history dostarcza 2 z 4 składników (history_match 0.4, historical_acceptance uśredniona 0.2) |
| ADR-2026-04-15 | Hard change wymaga explicit confirm | dedykowane API `confirm/reject_hard_change` + status `pending` |
| ADR-2026-04-18 | dont_learn 3-source resolution | recorder rozstrzyga: context > action > engine row |
| ADR-2026-04-22 | Forever-retention dla card_actions | partycje miesięczne, nigdy nie kasowane bez explicit DROP PARTITION |

### 10.7. Polityki SLA

| Polityka | Wartość | Egzekucja |
|---|---|---|
| Append-only retention | forever | RAISE EXCEPTION trigger + brak DELETE w API |
| Latency record_action (P99) | < 50 ms (PG localhost) | INSERT + 1 SELECT + (opcjonalnie) INSERT learning_signal |
| Latency get_history_match (P99) | < 100 ms | indeks `idx_card_actions_operator` + filter on context_jsonb |
| Soft-learning auto-apply | best-effort, fail-open | brak SLA — `applied=false` dopuszczalne |
| Hard-change confirm timeout | brak | operator decyduje, sygnał zostaje `pending` na czas nieokreślony |
| Partition creation freshness | minimum 2 partycje wprzód | maintenance job dziennie (`months_ahead=3`) |

---

> Dokument wygenerowany na podstawie:
> `sylion/aeis/advisor/history/{__init__,_db,_models,service,recorder,grpc_server,partition_manager}.py`,
> `sylion/aeis/advisor/history/learning/{signal_aggregator,soft_learning,hard_learning}.py`,
> `sylion/aeis/advisor/history/confidence_provider/{history_match,historical_acceptance}.py`,
> `sylion/aeis/advisor/proto/history.proto`,
> `sylion/contracts/manifests/aeis.advisor.history.json`,
> `sylion/db/advisor_layer.sql` (linie 465–524).
