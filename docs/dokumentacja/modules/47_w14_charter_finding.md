# W14 CharterStore + FindingStore — wrappery cyklu życia
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Moduł: `sylion.aeis.testing.charter` + `sylion.aeis.testing.findings`
> Commit: `c8263ea4` — E7
> Plik: `src/sylion-pipeline/sylion/aeis/testing/charter.py` + `findings.py`

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura](#2-architektura)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje — CharterStore](#4-funkcje--charterstore)
5. [Funkcje — FindingStore](#5-funkcje--findingstore)
6. [Eventy](#6-eventy)
7. [Tabele bazy danych](#7-tabele-bazy-danych)
8. [Przykład użycia](#8-przykład-użycia)
9. [Weryfikacja](#9-weryfikacja)
10. [Rozwiązywanie problemów](#10-rozwiązywanie-problemów)
11. [Cross-references](#11-cross-references)

---

## 1. Cel modułu

`CharterStore` i `FindingStore` to wrappery domenowe nałożone na generyczny `OntologyStore`.
Wymuszają poprawne przejścia statusów (lifecycle enforcement) dla dwóch kluczowych obiektów W14:

- **TestCharter** — kontrakt testowy projektu (draft → proposed → approved/rejected → archived)
- **Finding** — znaleziony defekt lub problem (R0-R9 flow per kanon sekcja 11.1)

Cel: żaden kod poza tymi wrapperami nie może przejść chartera do statusu `approved` bez
wcześniejszego `proposed`, ani przejść Findingu ze stanu `REPAIRING` wprost do `CLOSED`
z pominięciem `VERIFIED`. Wymuszenie odbywa się przez `TRANSITIONS` / `_ALLOWED` dict.

---

## 2. Architektura

```
testing/
  charter.py          CharterStore + TRANSITIONS + VALID_STATUSES
  findings.py         FindingStore + _ALLOWED + TERMINAL_STATUSES
  ontology/
    objects.py        TestCharter + Finding (dataclasses)
    store.py          OntologyStore (generyczny CRUD + SQLite backend)
  tests/
    test_charter_store.py     11 testow (lifecycle valid+invalid, terminal block)
    test_findings_store.py    16 testow (severity filtering, list_critical, get_active)
```

Oba wrappery przyjmują `OntologyStore` przez konstruktor (dependency injection).
`event_bus` jest opcjonalny — gdy `None`, zdarzenia sa cicho pomijane (non-fatal).

---

## 3. Konfiguracja

Oba moduły nie wymagają osobnych zmiennych środowiskowych.
Konfiguracja pochodzi od przekazanego `OntologyStore`:

| Parametr | Zrodlo | Opis |
|----------|--------|------|
| `db_path` | `SYLION_W14_DB` lub default `sylion_aeis.db` | Sciezka do SQLite OntologyStore |
| `event_bus` | runtime | Opcjonalnie `SylionEventBus`; `None` = silent |
| `tickets` (FindingStore) | runtime | Opcjonalnie `GovernanceTickets`; `None` = bez mirroru |

---

## 4. Funkcje — CharterStore

### Cykl życia chartera

```
draft  ──►  proposed  ──►  approved  ──►  archived
  │              │
  └──►  rejected ──────────────────────►  archived
```

### Metody publiczne

| Metoda | Sygnatura | Opis |
|--------|-----------|------|
| `create` | `(charter: TestCharter) -> TestCharter` | Persystuje nowy charter; domyslny status `draft` |
| `propose` | `(charter_id: str) -> TestCharter` | Przejscie `draft -> proposed` |
| `approve` | `(charter_id, approver, hg_ticket_id?, council_session_id?) -> TestCharter` | `proposed -> approved`; zapisuje `approved_at` + referencje gate |
| `reject` | `(charter_id, reason?) -> TestCharter` | `proposed/draft -> rejected` z opcjonalnym powodem |
| `archive` | `(charter_id) -> TestCharter` | `approved/rejected -> archived` (terminal) |
| `list_for_project` | `(project_id) -> list[TestCharter]` | Wszystkie chartery projektu (limit 1000) |
| `get_active` | `(project_id) -> TestCharter \| None` | Najnowszy `approved` charter (max po `approved_at`) |

### Wymuszanie tranzycji

```python
TRANSITIONS: dict[str, set[str]] = {
    "draft":     {"proposed", "rejected"},
    "proposed":  {"approved", "rejected"},
    "approved":  {"archived"},
    "rejected":  {"archived"},
    "archived":  set(),          # terminal — brak dozwolonych przejsc
}
```

Próba niedozwolonego przejścia (np. `draft -> approved`) rzuca `ValueError`.

---

## 5. Funkcje — FindingStore

### Cykl życia findingu (R0-R9, sekcja 11.1 kanonu)

```
OPEN -> TRIAGED -> REPRODUCED -> CLASSIFIED -> REPAIR_PROPOSED
  -> {WAITING_FOR_HUMAN_GATE, REPAIRING}
  -> READY_FOR_RETEST
  -> {VERIFIED, REGRESSION_FAILED}
  -> CLOSED

Boczne gałęzie (dostępne z większości stanów):
  ESCALATED        — blokada przez Loop Governor lub przegląd ludzki
  WAIVED_BY_HUMAN  — odpuszczenie z zatwierdzeniem HG
```

### Metody publiczne

| Metoda | Sygnatura | Opis |
|--------|-----------|------|
| `create` | `(finding, mirror_to_ticket=True) -> Finding` | Tworzy finding; auto-mirroruje do governance.tickets dla D2+ |
| `transition` | `(finding_id, new_status, evidence?, actor?) -> Finding` | Przejscie z walidacja R-status + zapis `closed_at` przy CLOSED |
| `list_open` | `(severity?) -> list[Finding]` | Otwarte findingi (poza CLOSED); opcjonalnie filtr severity |
| `list_by_d_level` | `(d_level) -> list[Finding]` | Wszystkie findingi danego D-level |
| `list_critical` | `() -> list[Finding]` | Otwarte P0 i P1 (operator dashboard) |
| `get` | `(finding_id) -> Finding \| None` | Pobranie pojedynczego findingu |

### Wymuszanie tranzycji (wybrane)

```python
_ALLOWED = {
    "OPEN":           {"TRIAGED", "REPRODUCED", "CLOSED", "ESCALATED", "WAIVED_BY_HUMAN"},
    "REPAIRING":      {"READY_FOR_RETEST", "REGRESSION_FAILED", "ESCALATED"},
    "VERIFIED":       {"CLOSED"},
    "CLOSED":         set(),    # terminal
    ...
}
```

Niedozwolone przejście rzuca `ValueError` z opisem dozwolonych celów.

### Auto-mirror do tickets (D2+)

Gdy `mirror_to_ticket=True` i `finding.d_level in ("D2","D3","D4","D5")`:

```python
ticket = GovernanceTicket(
    origin="testing",
    decision_class=finding.d_level,
    priority=finding.severity,
    title=finding.title[:200],
    payload={"finding_id": finding.finding_id},
    sla_deadline=time.time() + 86400,   # 24h SLA
)
ticket_id = self._tickets.submit(ticket)
```

Jeśli `tickets=None` lub submit rzuci wyjątek — mirror cicho pominięty, finding zostaje
zapisany.

---

## 6. Eventy

### CharterStore

| Temat (topic) | Kiedy emitowany | Payload |
|---------------|----------------|---------|
| `aeis.testing.charter.created` | `create()` | `{charter_id, project_id, status}` |
| `aeis.testing.charter.proposed` | `propose()` | `{charter_id}` |
| `aeis.testing.charter.approved` | `approve()` | `{charter_id}` |
| `aeis.testing.charter.rejected` | `reject()` | `{charter_id, reason}` |
| `aeis.testing.charter.archived` | `archive()` | `{charter_id}` |

### FindingStore

| Temat (topic) | Kiedy emitowany | Payload |
|---------------|----------------|---------|
| `aeis.testing.finding.detected` | `create()` | `{finding_id, severity, d_level}` |
| `aeis.testing.finding.transitioned` | `transition()` | `{finding_id, to, actor, evidence}` |
| `aeis.testing.finding.closed` | `transition(..., "CLOSED")` | `{finding_id, actor}` |

Wszystkie zdarzenia emitowane przez `SylionEvent` z `source_module` odpowiednio
`aeis.testing.charter` lub `aeis.testing.findings`.

---

## 7. Tabele bazy danych

Oba moduły korzystają z tabel zarządzanych przez `OntologyStore` (nie tworzą własnych).
Dane persystowane jako JSON w kolumnie `payload` tabeli `w14_objects`:

```sql
-- Tabela OntologyStore (dziedziczona)
CREATE TABLE w14_objects (
    object_id   TEXT PRIMARY KEY,
    object_type TEXT NOT NULL,          -- 'TestCharter' lub 'Finding'
    payload     TEXT NOT NULL,          -- JSON serialized dataclass
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    actor       TEXT NOT NULL DEFAULT 'system'
);
CREATE INDEX idx_w14_objects_type   ON w14_objects(object_type);
CREATE INDEX idx_w14_objects_cat    ON w14_objects(object_type, created_at);
```

Pola `TestCharter` w payloadzie:

| Pole | Typ | Opis |
|------|-----|------|
| `charter_id` | str | UUID projektu |
| `project_id` | str | Powiązany projekt |
| `status` | str | Biezacy status lifecycle |
| `hg_ticket_id` | str \| None | Referencja Human Gate |
| `council_session_id` | str \| None | Referencja sesji Rady |
| `approved_at` | float \| None | Unix timestamp zatwierdzenia |

Pola `Finding` w payloadzie:

| Pole | Typ | Opis |
|------|-----|------|
| `finding_id` | str | UUID findingu |
| `title` | str | Krotki opis (max 200 znaków) |
| `description` | str | Pelny opis (max 500 w mirror) |
| `severity` | str | P0/P1/P2/P3/P4 |
| `d_level` | str | D0-D5 |
| `r_status` | str | Biezacy R-status |
| `ticket_id` | str \| None | ID mirrora w governance.tickets |
| `discovered_by` | str | Aktor który stworzył finding |
| `closed_at` | float \| None | Unix timestamp zamknięcia |

---

## 8. Przykład użycia

### Pełny cykl chartera projektu

```python
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import TestCharter
from sylion.aeis.testing.charter import CharterStore

ontology = OntologyStore(db_path="sylion_aeis.db")
store = CharterStore(ontology, event_bus=None)

# 1. Utwórz charter
charter = TestCharter(
    charter_id="ch-001",
    project_id="demo_01_mobile_field_inspector",
    status="draft",
)
store.create(charter)

# 2. Zaproponuj
store.propose("ch-001")

# 3. Zatwierdź (z referencjami gate)
store.approve("ch-001", approver="operator@sylion", hg_ticket_id="hg-42", council_session_id="cs-17")

# 4. Pobierz aktywny charter projektu
active = store.get_active("demo_01_mobile_field_inspector")
print(active.status)  # "approved"
```

### Cykl findingu z przejściami R-status

```python
from sylion.aeis.testing.ontology.objects import Finding
from sylion.aeis.testing.findings import FindingStore

fs = FindingStore(ontology, tickets=None)

# Utwórz finding
f = Finding(
    finding_id="f-001",
    title="GPS drift nie zablokowane",
    severity="P1",
    d_level="D4",
    r_status="OPEN",
    discovered_by="guardian/gps_check",
)
fs.create(f)

# Przejdź przez lifecycle
fs.transition("f-001", "TRIAGED", actor="qa_lead")
fs.transition("f-001", "REPRODUCED", evidence={"log": "drift=6km"})
fs.transition("f-001", "CLASSIFIED")
fs.transition("f-001", "REPAIR_PROPOSED")
fs.transition("f-001", "REPAIRING", actor="codex")
fs.transition("f-001", "READY_FOR_RETEST")
fs.transition("f-001", "VERIFIED")
fs.transition("f-001", "CLOSED", actor="qa_lead")

# Sprawdź listę krytycznych (P0/P1 otwarte)
critical = fs.list_critical()
print(len(critical))  # 0 — f-001 jest CLOSED
```

---

## 9. Weryfikacja

```bash
cd src/sylion-pipeline

# Testy CharterStore (11 testów)
python -m pytest tests/aeis/testing/test_charter_store.py -v

# Testy FindingStore (16 testów)
python -m pytest tests/aeis/testing/test_findings_store.py -v

# Oba razem
python -m pytest tests/aeis/testing/test_charter_store.py tests/aeis/testing/test_findings_store.py -v

# Łączny wynik (E7): 27 testów, wszystkie zielone
```

Oczekiwany wynik: `27 passed` w czasie < 0.5s.

---

## 10. Rozwiązywanie problemów

### `ValueError: invalid transition draft -> approved`

Przejście z `draft` bezpośrednio do `approved` jest zabronione. Wymagana sekwencja:
`draft -> proposed -> approved`. Sprawdź, czy `propose()` zostało wywołane wcześniej.

### `ValueError: finding not found: <id>`

`OntologyStore.get()` zwróciło `None`. Upewnij się, że:
- `Finding` był wcześniej zapisany przez `FindingStore.create()`
- `db_path` jest taki sam w OntologyStore przekazywanym do `create` i `transition`

### Auto-mirror do tickets nie działa

Sprawdź, czy `tickets` nie jest `None` w konstruktorze `FindingStore`. Gdy `tickets=None`,
mirror jest cicho pomijany. Import `GovernanceTicket` z `sylion.governance.ticket` musi
się powieść — brak modułu powoduje ciche pominięcie (warning w logu).

### Event nie emitowany

Sprawdź, czy `event_bus` jest przekazany i nie jest `None`. Błędy emisji są logowane na
poziomie `DEBUG` (`sylion.aeis.testing.charter` / `sylion.aeis.testing.findings`).

---

## 11. Cross-references

- [`46_w14_ontology.md`](./46_w14_ontology.md) — bazowe obiekty `TestCharter`, `Finding`,
  `OntologyStore`, R-status enum, Severity enum
- [`49_w14_test_center.md`](./49_w14_test_center.md) — Test Center UI używa CharterStore
  i FindingStore; sekcja Self-Audit sprawdza oba wrappery
- [`50_w14_demo_projects.md`](./50_w14_demo_projects.md) — `execute_demo` tworzy chartery
  i findingi przez te wrappery dla 6 projektów demo
- [`modules/33_council_hybrid.md`](./33_council_hybrid.md) — `approve()` przyjmuje
  `council_session_id` z sesji Rady
- [`modules/31_d_ladder_complete.md`](./31_d_ladder_complete.md) — D-level findingu
  determinuje priorytety mirroru do governance tickets
