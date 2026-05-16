# 46. W14 Testing Ontology — 25 obiektow, 12 enums, Store, REST
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja modulu `sylion.aeis.testing.ontology` (W14 Etap E1).
> Spec bazowa: `docs/w14_workplan/ontology_spec.yaml` (FROZEN 2026-04-26, HG-approved).
> Implementacja: commit `c960ed6`.

## Spis tresci

1. [Cel modulu](#1-cel-modulu)
2. [Architektura](#2-architektura)
3. [Enumy (12)](#3-enumy-12)
4. [Obiekty ontologii (25)](#4-obiekty-ontologii-25)
5. [OntologyStore — CRUD i relacje](#5-ontologystore--crud-i-relacje)
6. [REST API](#6-rest-api)
7. [Schemat bazy danych](#7-schemat-bazy-danych)
8. [Weryfikacja](#8-weryfikacja)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)
11. [W14 Testing Actions — 20 handlerow (E2)](#11-w14-testing-actions--20-handlerow-e2)

---

## 1. Cel modulu

Modul `sylion.aeis.testing` dostarcza **kanoniczny model ontologiczny dla W14** (Testing/Simulation/Repair/Release Governance). Jest jedynym zrodlem prawdy dla struktur danych uzywanych przez wszystkich agentow i komponentow w procesach testowania, symulacji i zarzadzania wydaniami AEIS.

Etap E1 (sprint3, commit `c960ed6`) dostarcza:
- 25 dataclass-ow (obiekty ontologii) z walidatorami
- 12 enumeracji (`str` subclasses) z metodami `.values()` i `.has_value()`
- `OntologyStore` — SQLite-backed CRUD z relacjami i historia
- REST API (`/api/v1/testing/`) — 15 endpointow
- Migracje DB: `db/migrations/0001_w14_ontology.py`
- 3 pliki testow golden set

---

## 2. Architektura

```
sylion/aeis/testing/
├── __init__.py
└── ontology/
    ├── __init__.py
    ├── objects.py          — 25 dataclasses + OBJECT_TABLE_MAP + PRIMARY_KEY_MAP
    ├── enums.py            — 12 enumeracji
    ├── store.py            — OntologyStore (SQLite, thread-safe, EventBus)
    └── _validators/
        ├── __init__.py
        ├── enums.py        — require_enum_value, require_enum_subset
        ├── identifiers.py  — require_prefix (format: prefix_hex12)
        ├── numeric.py      — require_positive, require_in_range
        └── semantic.py     — require_branch_not_main

sylion/api/testing_routes.py  — FastAPI router (/api/v1/testing/)
sylion/db/migrations/0001_w14_ontology.py — DDL (25 tabel + 2 aux)

tests/aeis/testing/ontology/
├── fixtures.py
├── test_adversarial.py
├── test_objects.py
└── test_store.py
```

---

## 3. Enumy (12)

Wszystkie enumy dziedzicza z `_SylionEnum(str, Enum)` — mozliwe persystowanie jako TEXT w SQLite.

| Enum | Wartosci (kluczowe) | Opis |
|------|---------------------|------|
| `DLevel` | D0, D1, D2, D3, D4, D5 | Poziom decyzji D-ladder |
| `RStatus` | R0..R9 + stany oczekiwania/eskalacji | Cykl naprawy finding |
| `TestClass` | unit, integration, e2e, performance, security, ... | Klasa testu |
| `ReleaseStatus` | draft, rc, approved, rejected, shipped, rolled_back | Status kandydata wydania |
| `Severity` | info, low, medium, high, critical | Waga findigu/alertu |
| `GateType` | entry, exit, emergency | Typ bramki jakosci |
| `HumanErrorClass` | commission, omission, timing, sequence, ... | Klasa bledu ludzkiego |
| `EvidenceTier` | L0, L1, L2, L3, L4 | Poziom fidelity dowodow symulacji |
| `BranchType` | feature, bugfix, hotfix, release, experiment | Typ branchy git |
| `BranchState` | open, merged, abandoned | Stan branchy |
| `PersonaCapability` | expert, novice, distracted, multitasking, ... | Zdolnosc persony HG |
| `GuardianClass` | correctness, security, performance, coverage, ... | Klasa Guardian |

---

## 4. Obiekty ontologii (25)

### 4.1. Core Testing (8)

| Klasa | ID prefix | Tabela SQLite | Opis |
|-------|-----------|---------------|------|
| `Requirement` | `req_` | `w14_requirements` | Wymaganie (zrodlo, priorytet, typ) |
| `TestCharter` | `chrt_` | `w14_test_charters` | Misja sesji testowej (stan: draft→proposed→approved→archived) |
| `TestPlan` | `plan_` | `w14_test_plans` | Plan testow (zakres, harmonogram) |
| `TestSuite` | `suite_` | `w14_test_suites` | Zbior TestCase |
| `TestCase` | `tc_` | `w14_test_cases` | Pojedynczy przypadek testowy (klasa, krooki, oczekiwania) |
| `EvaluationSuite` | `evsuite_` | `w14_evaluation_suites` | Suite ewaluacyjna dla LLM |
| `TestRun` | `run_` | `w14_test_runs` | Wykonanie TestSuite (wyniki per case) |
| `RegressionRun` | `regrun_` | `w14_regression_runs` | Porownanie z baselineiem |

### 4.2. Findings & Repair (5)

| Klasa | ID prefix | Tabela | Opis |
|-------|-----------|--------|------|
| `Finding` | `find_` | `w14_findings` | Defekt / obserwacja (severity, guardian_class) |
| `PatchProposal` | `patch_` | `w14_patch_proposals` | Propozycja naprawy (diff, target, DLevel) |
| `RepairAttempt` | `reptmt_` | `w14_repair_attempts` | Proba naprawy (status R0-R9) |
| `LoopReport` | `lrep_` | `w14_loop_reports` | Raport cyklu Loop Governor |
| `GuardianAlert` | `galert_` | `w14_guardian_alerts` | Alert od Guardian (klasa, severity, payload) |

### 4.3. Simulation (8)

| Klasa | ID prefix | Tabela | Opis |
|-------|-----------|--------|------|
| `SimulationContract` | `simctr_` | `w14_simulation_contracts` | Kontrakt symulacji (scope, fidelity EvidenceTier) |
| `SimulationBranch` | `simbr_` | `w14_simulation_branches` | Branch symulacyjny (L0-L4) |
| `SimulationEvidence` | `simev_` | `w14_simulation_evidence` | Dowody z symulacji |
| `HumanPersona` | `hpers_` | `w14_human_personas` | Persona operatora (capabilities, error_rate) |
| `HumanScenario` | `hscen_` | `w14_human_scenarios` | Scenariusz HG (kroki, oczekiwania) |
| `HumanErrorInjection` | `herrinj_` | `w14_human_error_injections` | Injekcja bledu ludzkiego (klasa, lokalizacja) |
| `HumanDecisionTrace` | `hdtrace_` | `w14_human_decision_traces` | Slad decyzji HG |
| `HumanNearMiss` | `hnear_` | `w14_human_near_misses` | Zdarzenie near-miss |

### 4.4. Branches & Release (4)

| Klasa | ID prefix | Tabela | Opis |
|-------|-----------|--------|------|
| `Branch` | `br_` | `w14_branches` | Branch git (type, state, commit range) |
| `ReleaseCandidate` | `rc_` | `w14_release_candidates` | RC (wersja, status, DLevel) |
| `ReleaseDecision` | `rdec_` | `w14_release_decisions` | Decyzja release (approve/reject, sygnatury) |
| `ReleaseReadinessReport` | `rrep_` | `w14_release_readiness_reports` | Raport gotowosci (gate checks, guardian alerts) |

### 4.5. Konwencja ID

Wszystkie ID: `<prefix>_<uuid4-hex-12>`. Np.: `find_a1b2c3d4e5f6`. Walidacja: `require_prefix(value, "find_")` z `_validators/identifiers.py`.

---

## 5. OntologyStore — CRUD i relacje

### 5.1. Inicjalizacja

```python
from sylion.aeis.testing.ontology.store import OntologyStore

store = OntologyStore(db_path=":memory:")  # lub sciezka do pliku
store.initialize()  # uruchamia migracje DDL
```

### 5.2. Operacje CRUD (interfejs Contract C1)

| Metoda | Opis |
|--------|------|
| `create(obj)` | Insertuje obiekt do tabeli per kind; emituje `aeis.testing.ontology.created` |
| `get(kind, obj_id)` | Pobiera po ID; zwraca None jesli brak |
| `list(kind, **filters)` | Lista z opcjonalnymi filtrami (status, severity, ...) |
| `update(kind, obj_id, patch)` | Czesciowy update (merge); emituje `aeis.testing.ontology.updated` |
| `delete(kind, obj_id)` | Soft-delete (ustawia `deleted_at`); emituje `aeis.testing.ontology.deleted` |
| `link(src_id, dst_id, relation_type)` | Tworzy relacje w `w14_testing_relations` |
| `get_related(src_id, relation_type?)` | Zwraca powiazane obiekty |
| `history(obj_id)` | Audit log per obiekt z `w14_testing_history` (append-only) |

### 5.3. Thread-safety i storage

- `threading.RLock` chroni wszystkie operacje DB.
- SQLite z `check_same_thread=False` i WAL mode dla sciezek plikowych.
- Opcjonalny `event_bus: EventBus` dla emitowania mutacji.

### 5.4. Specjalne przejscia

- `charter_approve(charter_id)` — zmienia status `TestCharter` z `proposed` → `approved`.
- `finding_waive(finding_id, reason)` — wycofuje Finding (status `waived`).

---

## 6. REST API

Prefix: `/api/v1/testing/`

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/health` | GET | Status sklepu + liczba obiektow per kind |
| `/objects` | GET | Lista dostepnych kind-ow |
| `/{kind}` | POST | Tworzy obiekt danego kind |
| `/{kind}/{obj_id}` | GET | Pobiera obiekt |
| `/{kind}` | GET | Lista obiektow (z filtrami query params) |
| `/{kind}/{obj_id}` | PUT | Aktualizuje obiekt |
| `/{kind}/{obj_id}` | DELETE | Soft-delete |
| `/{kind}/{obj_id}/history` | GET | Audit log per obiekt |
| `/relations` | POST | Tworzy relacje (link) |
| `/relations/{src_id}` | GET | Pobiera powiazane obiekty |
| `/charters/{id}/approve` | POST | Przejscie: proposed → approved |
| `/findings/{id}/waive` | POST | Wycofanie Finding |

Parametr `{kind}` odpowiada kluczom `OBJECT_TABLE_MAP` (np. `requirements`, `test_charters`, `findings`).

---

## 7. Schemat bazy danych

Migracja: `src/sylion-pipeline/sylion/db/migrations/0001_w14_ontology.py`

```sql
-- 25 tabel per obiekt (schemat jednolity):
CREATE TABLE w14_<kind> (
    obj_id      TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    data        TEXT NOT NULL,  -- JSON (caly dataclass)
    created_at  REAL,
    updated_at  REAL,
    deleted_at  REAL
);

-- Relacje (N:M)
CREATE TABLE w14_testing_relations (
    rel_id          TEXT PRIMARY KEY,
    src_id          TEXT NOT NULL,
    dst_id          TEXT NOT NULL,
    relation_type   TEXT NOT NULL,
    created_at      REAL
);

-- Historia mutacji (append-only audit log)
CREATE TABLE w14_testing_history (
    hist_id     TEXT PRIMARY KEY,
    obj_id      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    verb        TEXT NOT NULL,  -- created / updated / deleted
    delta_json  TEXT,
    actor_id    TEXT,
    created_at  REAL
);
```

---

## 8. Weryfikacja

```bash
# Uruchom testy golden set
cd src/sylion-pipeline
python -m pytest tests/aeis/testing/ontology/ -v

# Sprawdz endpoint zdrowia
curl http://127.0.0.1:8010/api/v1/testing/health

# Stworz Requirement
curl -X POST http://127.0.0.1:8010/api/v1/testing/requirements \
  -H "Content-Type: application/json" \
  -d '{"title":"API coverage > 90%","priority":"high","source":"qa_team"}'

# Lista Finding-ow
curl http://127.0.0.1:8010/api/v1/testing/findings
```

---

## 9. Troubleshooting

| Problem | Mozliwa przyczyna | Rozwiazanie |
|---------|-------------------|-------------|
| `IntegrityError: UNIQUE constraint failed` | Duplikat obj_id | ID generowane auto — nie przekazuj recznych ID bez prefixu |
| `ValidationError: unknown enum value` | Status/severity poza spec | Sprawdz `.values()` odpowiedniego enumy |
| `branch not_main required` | Branch `main` uzyty jako target | Wymaganie spec: branche musza byc inne niz `main` |
| Historia pusta | `store.history(obj_id)` przed `initialize()` | Wywolaj `store.initialize()` przy starcie |
| Relacje nie zwracaja wynikow | `src_id` nie istnieje lub zly typ relacji | Sprawdz `link(src_id, dst_id, "relation_type")` |

---

## 10. Cross-references

- `docs/w14_workplan/ontology_spec.yaml` — spec FROZEN (zrodlo prawdy)
- `docs/w14_workplan/W14_INTEGRATION_CONTRACTS.md` — Contract C1 (Store CRUD)
- `docs/w14_workplan/W14_PROGRESS_LEDGER.md` — ledger postepow E0→E1
- [`05_engine.md`](05_engine.md) — engine moze emitowac `Finding` przez Guardian
- [`25_evidence_pack_viewer.md`](25_evidence_pack_viewer.md) — `SimulationEvidence` i `EvidenceTier` powiazane z Evidence Pack
- [`31_d_ladder_complete.md`](31_d_ladder_complete.md) — `DLevel` enum uzywany w `PatchProposal` i `ReleaseCandidate`
- [`27_audit_viewer.md`](27_audit_viewer.md) — `w14_testing_history` widoczne w Audit Viewer

---

## 11. W14 Testing Actions — 20 handlerow (E2)

> Etap E2 (sprint4, commit `4c0bfd37`). Spec: `docs/w14_workplan/actions_spec.yaml` (FROZEN 2026-04-26).
> Implementacja: pakiet `sylion.aeis.testing.actions`, 63 testy w `tests/aeis/testing/actions/`.

### 11.1 Architektura pakietu

```
sylion/aeis/testing/actions/
├── __init__.py          — register_testing_actions(), ALL_HANDLER_CLASSES
├── base.py              — TestingActionHandler (klasa bazowa)
├── charter_actions.py   — 4 handlery (charter group)
├── finding_actions.py   — 3 handlery (finding group)
├── repair_actions.py    — 4 handlery (repair group)
├── persona_actions.py   — 6 handlerow (persona/simulation group)
└── release_actions.py   — 3 handlery (release group)

tests/aeis/testing/actions/
├── test_charter_actions.py   — 12 testow
├── test_finding_actions.py   — 9 testow
├── test_persona_actions.py   — 12 testow
├── test_register.py          — 8 testow
├── test_release_actions.py   — 11 testow
└── test_repair_actions.py    — 11 testow
```

### 11.2 Klasa bazowa TestingActionHandler

Kazdy handler to podklasa `TestingActionHandler` z nastepujacymi atrybutami klasowymi:

| Atrybut | Typ | Opis |
|---------|-----|------|
| `target_action` | `str` | Unikatowa nazwa akcji (klucz w CommandBus) |
| `d_level` | `DLevel` | Poziom decyzyjny (D0–D5); determinuje governance flow |
| `phase` | `"TWO_PHASE" \| "IMMEDIATE"` | TWO_PHASE: submit → review → resolve; IMMEDIATE: auto-resolve (D0/D1) |
| `mirror_to_ticket` | `bool` | Jesli True: tworzy `GovernanceTicket` przy execute |
| `gate_type` | `GateType \| None` | Typ bramki dla mirrorowanego ticketu |

Metody publiczne:
- `validate(payload: dict) -> None` — zgłasza `ValueError` przy blednym payloadzie
- `execute(payload: dict, intent_id: str) -> dict` — wykonuje akcje, zwraca wynik

Metody pomocnicze (dziedziczone przez podklasy):
- `_require_keys(payload, *keys)` — brakujace pola → ValueError
- `_require_prefix(payload, key, prefix)` — format ID (np. `find_`, `proj_`)
- `_require_not_main(payload, key)` — hard guard: `branch_id != "main"`
- `_require_in_range(payload, key, lo, hi)` — walidacja zakresu numerycznego
- `_emit(event_type, payload)` — EventBus (best-effort, nie blokuje)
- `_mirror_ticket(...)` — tworzy `GovernanceTicket` z SLA per D-level

SLA per D-level (via `PRIORITY_BY_DLEVEL` i `SLA_SECONDS`):

| D-level | Priorytet | SLA |
|---------|-----------|-----|
| D0 | P4 | 1 tydzien |
| D1 | P3 | 1 dzien |
| D2 | P2 | 4 godziny |
| D3 | P1 | 1 godzina |
| D4, D5 | P0 | 15 minut |

### 11.3 Tabela wszystkich 20 akcji

| target_action | Grupa | DLevel | Phase | mirror_to_ticket |
|---------------|-------|--------|-------|-----------------|
| `propose_test_charter` | charter | D2 | TWO_PHASE | tak |
| `approve_test_charter` | charter | D3 | TWO_PHASE | tak |
| `create_eval_suite` | charter | D1 | IMMEDIATE | nie |
| `run_eval_suite` | charter | D1 | IMMEDIATE | nie |
| `mark_finding_reproduced` | finding | D1 | IMMEDIATE | nie |
| `waive_finding` | finding | D3 | TWO_PHASE | tak |
| `disable_test` | finding | D2 | TWO_PHASE | tak |
| `propose_patch` | repair | D2 | TWO_PHASE | tak |
| `approve_patch` | repair | D3 | TWO_PHASE | tak |
| `apply_patch_to_branch` | repair | D2 | TWO_PHASE | tak |
| `run_regression` | repair | D1 | IMMEDIATE | nie |
| `register_persona` | persona | D1 | IMMEDIATE | nie |
| `register_human_scenario` | persona | D1 | IMMEDIATE | nie |
| `simulate_human_workflow` | persona | D2 | TWO_PHASE | nie |
| `simulate_human_decision` | persona | D2 | TWO_PHASE | nie |
| `inject_human_error` | persona | D3 | TWO_PHASE | tak |
| `record_comprehension_finding` | persona | D1 | IMMEDIATE | nie |
| `promote_release_candidate` | release | D3 | TWO_PHASE | tak |
| `rollback_release` | release | D4 | TWO_PHASE | tak |
| `close_loop_as_blocked` | release | D2 | TWO_PHASE | tak |

### 11.4 Kluczowe invarianty walidacji

- `propose_patch`, `apply_patch_to_branch`: `branch_id` nie moze byc `"main"` (hard guard `_require_not_main`).
- `promote_release_candidate`: blokuje release, gdy istnieja nierozwiazane findingi P0/P1 (status inny niz `VERIFIED`, `WAIVED_BY_HUMAN`, `CLOSED`).
- `waive_finding`: `expiry_at` musi byc co najmniej 24h w przyszlosci (zakaz permanentnych waiverow).
- `approve_test_charter`: wymagany `hg_ticket_id` (HG review przed zatwierdzeniem D3).

### 11.5 Rejestracja w aplikacji

```python
from sylion.aeis.testing.actions import register_testing_actions

handlers = register_testing_actions(
    bus=command_bus,          # opcjonalny; jesli podany, wstrzykuje bus._testing_handlers
    ontology=ontology_store,
    tickets=ticket_store,
    event_bus=event_bus,
)
# handlers: dict[target_action -> TestingActionHandler]
```

`register_testing_actions` instancjonuje wszystkie 20 klas (bez duplikatow `target_action`) i opcjonalnie rejestruje je na `CommandBus` poprzez atrybut `_testing_handlers`.
Handlersy sa uzywalne standalone (bez CommandBus) do testow jednostkowych.

### 11.6 Eventy emitowane

Format: `aeis.testing.<domena>.<zdarzenie>`.

| Event | Emitowany przez |
|-------|----------------|
| `aeis.testing.charter.proposed` | `propose_test_charter` |
| `aeis.testing.charter.approved` | `approve_test_charter` |
| `aeis.testing.finding.transitioned` | `mark_finding_reproduced` |
| `aeis.testing.finding.waived` | `waive_finding` |
| `aeis.testing.repair.patch_proposed` | `propose_patch` |
| `aeis.testing.repair.patch_approved` | `approve_patch` |
| `aeis.testing.repair.patch_applied` | `apply_patch_to_branch` |
| `aeis.testing.release.rc_promoted` | `promote_release_candidate` |
| `aeis.testing.release.rolled_back` | `rollback_release` |
| `aeis.testing.release.loop_blocked` | `close_loop_as_blocked` |
| `aeis.testing.human.persona_registered` | `register_persona` |

### 11.7 Weryfikacja

```bash
cd src/sylion-pipeline

# Wszystkie 63 testy akcji
python -m pytest tests/aeis/testing/actions/ -v

# Smoke: 20 handlerow zarejestrowanych
python -m pytest tests/aeis/testing/actions/test_register.py -v

# Konkretna grupa
python -m pytest tests/aeis/testing/actions/test_charter_actions.py -v
```

---

## 12. W14 Branches + Simulation L0-L4 (E3) [commit 7db93cdb]

> Etap E3 (commit `7db93cdb`). 54 nowe testy. Cumulative: 257/257 PASS.
> Pakiet: `sylion.aeis.testing.{branches, simulation, personas}`.

### 12.1 Architektura plikow

```
sylion/aeis/testing/
├── branches/
│   ├── __init__.py
│   └── manager.py          — BranchManager: 4 typy brancy, create/merge/discard
├── simulation/
│   ├── __init__.py
│   ├── contract.py         — L0: SimulationContract z twardymi limitami bezpieczenstwa
│   ├── sandbox.py          — L1: TransactionalSandbox z izolowanym OntologyStore + EventBus
│   └── engine.py           — SimulationEngine: start/run_layer/collect_evidence/discard
└── personas/
    ├── __init__.py
    ├── registry.py         — PersonaRegistry: CRUD + autoload 4 starters z JSON
    ├── runtime.py          — PersonaRuntime: simulate_workflow/decision/inject_error
    ├── _starter/*.json     — 4 persony poczatkowe
    └── _errors/*.json      — 7 klas bledow ludzkich

tests/aeis/testing/
├── branches/test_manager.py    — 13 testow
├── simulation/test_engine.py   — 19 testow
├── personas/test_registry.py   — 11 testow
└── personas/test_runtime.py    — 11 testow
```

### 12.2 BranchManager (branches/manager.py)

Zarzadza branchami symulacyjnymi. 4 typy brancy (z `BranchType` enum z E1):

| Typ | Przeznaczenie |
|-----|--------------|
| `simulation` | Izolowana symulacja — nie trafia do produkcji |
| `repair` | Auto-naprawa findingu (zarzadzany przez AutoRepairController w E4) |
| `test` | Branche testowe |
| `release` | Kandydaci wydania |

Glowne metody:

| Metoda | Opis |
|--------|------|
| `create(branch_id, branch_type, description)` | Tworzy Branch w OntologyStore, status=open |
| `merge(branch_id, context)` | Sprawdza MergeGuard (stub w E3, pelny w E4), zmienia status=merged |
| `discard(branch_id, reason)` | Zmienia status=abandoned; zapis powodu |
| `list_changes(branch_id)` | Zwraca liste zmian w branchu (symulacja: lista z EventBus) |

MergeGuard w E3 to stub (zawsze pozwala na merge) — pelna implementacja z 8 reguly w E4.

### 12.3 Simulation Contract (simulation/contract.py) — warstwa L0

`build_contract(scope, fidelity)` tworzy `SimulationContract` i natychmiast weryfikuje twardy zakres bezpieczenstwa (REJECTS):

| Odrzucona operacja | Powod |
|-------------------|-------|
| `main_mutation` | Zakaz mutacji brancha `main` |
| `external_network` | Symulacja nie moze wychodzic na internet |
| `real_device` | Zakaz uzywania prawdziwych urzadzen w symulacji |

Twardie limity (`HardBounds`):

| Limit | Wartosc |
|-------|---------|
| `max_runtime_seconds` | 3600 (1h) |
| `max_cost_usd` | 10.0 |
| `max_actions` | 1000 |

Naruszenie limitu → `SimulationContract` z `rejected=True` i `rejection_reason`.

### 12.4 TransactionalSandbox (simulation/sandbox.py) — warstwa L1

Izolowane srodowisko wykonawcze symulacji:

- Prywatny `OntologyStore` (`:memory:` SQLite) — zmiany nie trafiaja do glownego store.
- Buforowany `EventBus` — eventy zbierane in-memory, nie emitowane globalnie.
- Deterministyczny stub LLM (zwraca przewidywalne odpowiedzi bez wywolywania API).
- `sandbox.discard()` — automatyczne czyszczenie wszystkich zmian (auto-discard przy `.discard()`).

### 12.5 SimulationEngine (simulation/engine.py)

Orchestrator warstw symulacji L0-L4:

```
L0 → build_contract (weryfikacja bezpieczenstwa)
L1 → TransactionalSandbox (izolacja)
L2 → PersonaRuntime.simulate_workflow (symulacja workflow z persona)
L3 → PersonaRuntime.simulate_decision (symulacja decyzji HG)
L4 → PersonaRuntime.inject_error (injekcja bledu ludzkiego)
```

Glowne metody:

| Metoda | Opis |
|--------|------|
| `start(contract)` | Inicjuje sandbox; sprawdza limity |
| `run_layer(layer, payload)` | Dyspatchuje do odpowiedniego handlera L1-L4 |
| `collect_evidence()` | Zbiera `SimulationEvidence` z sandbox EventBus |
| `discard()` | Niszczy sandbox i wszystkie zmiany |

Enforcement limitow: po kazdym `run_layer` sprawdza `max_actions`, `max_cost_usd`, `max_runtime_seconds`. Przekroczenie → auto-discard + `SimulationContract.rejected=True`.

**Znany bug E3 (naprawiony):** `OntologyStore.list` stosowal `LIMIT` przed filtrem in-memory → `get_by_name(limit=1)` mogl przegapic match. Obejscie: `limit=1000` dla zapytan filtrowanych. TODO E4: refaktoryzacja `store.list` z filterami w SQL.

### 12.6 PersonaRegistry (personas/registry.py)

CRUD rejestr person HG. Autoload 4 startowych person z `_starter/*.json` przy inicjalizacji.

**4 persony startowe:**

| Plik | Persona | Opis |
|------|---------|------|
| `01_operator_beginner.json` | Poczatkujacy operator | Niska znajomosc systemu, wysoki error_rate, wolny |
| `02_operator_power_user.json` | Zaawansowany operator | Wysoka znajomosc, niski error_rate, szybki |
| `03_auditor.json` | Audytor | Skupia sie na dokumentacji i dochodach, sredni error_rate |
| `04_operator_overloaded.json` | Przeciazony operator | Wysoki fatigue, wysoki error_rate, wiele zadan rownoczesnie |

Metody CRUD: `create`, `get`, `list`, `update`, `delete`. Dodatkowa metoda `update_dynamic_state(persona_id, state)` / `reset_dynamic_state(persona_id)` do modyfikacji stanu person w trakcie symulacji.

### 12.7 PersonaRuntime (personas/runtime.py)

Silnik wykonywania scenariuszy dla person HG.

| Metoda | Warstwa | Opis |
|--------|---------|------|
| `simulate_workflow(persona, scenario)` | L2 | Symuluje caly workflow przez persona; zwraca comprehension_score |
| `simulate_decision(persona, decision_context)` | L3 | Symuluje pojedyncza decyzje HG (approve/reject/delay) |
| `inject_error(persona, error_class, location)` | L4 | Injectuje blad ludzki do scenariusza |

**Comprehension scoring:** wynik = `base_comprehension * (1 - fatigue_factor) * (1 - difficulty_factor)`. Respektuje `persona.behavior_modifiers.fatigue` i scenario `difficulty`.

**Latency:** uzywana z `persona.behavior_modifiers` — przecia/zony operator dziala wolniej niz power_user.

### 12.8 7 klas bledow ludzkich (_errors/*.json)

| Plik | Blad | Opis |
|------|------|------|
| `01_approve_without_evidence.json` | approve_no_evidence | Zatwierdzenie bez Evidence Pack |
| `02_upload_without_backup.json` | upload_no_backup | Upload danych bez backup |
| `03_stale_data_action.json` | stale_data | Akcja na nieaktualnych danych |
| `04_mock_as_live.json` | mock_as_live | Uzywanie mock jako danych produkcyjnych |
| `05_wrong_project_context.json` | wrong_project | Akcja w zlym kontekscie projektu |
| `06_double_submit_multitab.json` | multitab_double_submit | Podwojne zatwierdzenie przez multitab |
| `07_admin_approve_d5_without_council.json` | admin_d5_no_council | Admin zatwierdza D5 bez Rady |

### 12.9 Weryfikacja

```bash
cd src/sylion-pipeline
python -m pytest tests/aeis/testing/branches/ tests/aeis/testing/simulation/ tests/aeis/testing/personas/ -v
# 54 testy: 13 branches + 19 simulation + 11 registry + 11 runtime
```

---

## 13. W14 Auto-Repair R0-R9 + Loop Governor + Merge Guard (E4) [commit 787426d1]

> Etap E4 (commit `787426d1`). 37 nowych testow. Cumulative: 294/294 PASS.
> Pakiet: `sylion.aeis.testing.{loop_governor, merge_guard, auto_repair_controller}`.

### 13.1 Architektura plikow

```
sylion/aeis/testing/
├── loop_governor.py           — LoopGovernor: 8 limitow, LoopReport
├── merge_guard.py             — MergeGuard: 8 regul odrzucenia
└── auto_repair_controller.py  — AutoRepairController: R0-R9 state machine

tests/aeis/testing/
├── test_loop_governor.py      — 12 testow
├── test_merge_guard.py        — 12 testow
└── test_auto_repair_controller.py — 13 testow
```

### 13.2 LoopGovernor (loop_governor.py)

Straznik petli naprawy. Zapobiega nieskonczonym petlom auto-repair.

**8 limitow (spec sec 12.1):**

| Limit | Wartosc | Opis |
|-------|---------|------|
| `max_auto_fix_attempts_per_finding` | 2 | Max prob automatycznej naprawy per finding |
| `max_total_no_go_iterations` | 3 | Max iteracji bez postepow |
| `max_files_touched_no_hg` | 5 | Max plikow zmienionych bez Human Gate |
| `max_diff_size_no_hg` | 300 | Max linii diff bez Human Gate |
| `max_time_in_repair_loop_s` | 1800 (30 min) | Max czas w petli naprawy |
| `max_new_p0_p1_introduced` | 0 | Zakaz wprowadzania nowych krytycznych findinkow |
| `max_parallel_repair_agents_per_finding` | 1 | Jeden agent naprawczy na finding |

Glowne metody:

| Metoda | Opis |
|--------|------|
| `check(finding, payload) -> {allowed, reason, loop_report_id}` | Sprawdza wszystkie 8 limitow; zwraca `allowed=False` przy naruszeniu |
| `generate_loop_report(finding) -> LoopReport` | Tworzy `LoopReport` w OntologyStore z `loop_type` i `reason` |

**6 kanoniczych typow LoopReport (`loop_type`):**

`max_attempts_reached`, `no_go_limit_reached`, `files_limit_exceeded`, `diff_too_large`, `time_limit_exceeded`, `new_critical_introduced`.

`LIMIT_TO_LOOP_TYPE` mapuje nazwy wewnetrzne na te wartosci enum.

### 13.3 MergeGuard (merge_guard.py)

Straznik mergowania brancy. Sprawdza 8 regul strukturalnych przed dopuszczeniem merge.

**8 regul odrzucenia:**

| Regula | Kluczowa weryfikacja |
|--------|---------------------|
| `mandatory_test_deleted` | Usuniecie testu bez Council+HG |
| `assertion_weakened_without_hg` | Oslabienie asercji testowej bez Human Gate |
| `mock_added_to_pass_live_test` | Dodanie mocka zeby przejsc test produkcyjny |
| `sot_changed_without_proposal` | Zmiana Source of Truth bez Propozycji (D3+) |
| `masterplan_changed_without_proposal` | Zmiana Masterplan bez Propozycji |
| `new_p0_p1_introduced` | Nowe findingi krytyczne w diff |
| `evidence_missing` | Brak dowodow dla D3+ akcji |
| `loop_governor_status_not_clear` | LoopGovernor nie wydal zielonego swiatla |

Glowne metody:

```python
check_branch(branch_id, context) -> {allowed: bool, violations: list[str]}
```

Heurystyki: analiza diff, detekcja usuniecia testow, detekcja mockow.

### 13.4 AutoRepairController (auto_repair_controller.py)

Orchestrator cyklu naprawy R0-R9.

**10 stanow naprawy (R0-R9):**

| Stan | Nazwa | Opis |
|------|-------|------|
| R0 | OPEN | Finding otwarty, brak naprawy |
| R1 | TRIAGED | Finding przypisany do agenta |
| R2 | ANALYSING | Agent analizuje przyczyne |
| R3 | REPAIR_PROPOSED | Propozycja naprawy (PatchProposal) gotowa |
| R4 | REPAIRING | Agent aplikuje patch |
| R5 | REGRESSION | Testy regresji po naprawie |
| R6 | REVIEW | Przeglad przez agenta/auditora |
| R7 | HG_REQUIRED | Wymagany Human Gate (przekroczono limity LoopGovernor lub MergeGuard) |
| R8 | VERIFIED | Naprawa zweryfikowana |
| R9 | MERGE_READY | Gotowy do merge (MergeGuard OK) |

**Glowne metody:**

| Metoda | Opis |
|--------|------|
| `start_repair(finding_id) -> RepairSession` | Tworzy `RepairSession`, przechodzi do R1 |
| `step(session_id, target_phase, payload) -> dict` | Przesuwa session do target_phase; waliduje przejscie |
| `request_merge(session_id, ctx) -> dict` | Wywoluje MergeGuard dla brancha sesji; R9 → allowed/rejected |

**Integracja z LoopGovernor i MergeGuard:**

- Przy `step` do R3 (`REPAIR_PROPOSED`) i R4 (`REPAIRING`): `LoopGovernor.check()` — jesli `allowed=False` → automatyczne przejscie do R7 (HG_REQUIRED).
- Przy `request_merge` (R9): `MergeGuard.check_branch()` — jesli `allowed=False` → merge odrzucony, violations zwracane do callera.

**Persystencja:** kazda proba naprawy tworzy `RepairAttempt` w OntologyStore (append-only). Pozwala na audit history dla kazdego finding.

### 13.5 Weryfikacja

```bash
cd src/sylion-pipeline
python -m pytest tests/aeis/testing/test_loop_governor.py tests/aeis/testing/test_merge_guard.py tests/aeis/testing/test_auto_repair_controller.py -v
# 37 testow: 12 + 12 + 13
```

---

## 14. W14 13 Guardianow + Truth Alignment Matrix (E5) [commit a612756f]

> Etap E5 (commit `a612756f`). 39 nowych testow. Cumulative: 333/333 PASS.
> Pakiet: `sylion.aeis.testing.guardians` + `sylion.aeis.testing.truth_alignment`.

### 14.1 Architektura plikow

```
sylion/aeis/testing/
├── guardians/
│   ├── __init__.py          — register_all_guardians(ontology, event_bus)
│   ├── base.py              — GuardianBase: alert/status/event helpers, RGY health
│   └── implementations.py  — 13 guardianow w jednym pliku (~50 LOC kazdy)
└── truth_alignment.py       — TruthAlignmentMatrix + FeatureSnapshot (7 warstw)

tests/aeis/testing/
├── test_guardians.py        — 29 testow
└── test_truth_alignment.py  — 10 testow
```

### 14.2 GuardianBase (guardians/base.py)

Klasa bazowa dla wszystkich Guardianow.

| Metoda | Opis |
|--------|------|
| `alert(message, severity, payload)` | Tworzy `GuardianAlert` w OntologyStore |
| `status(color)` | Zwraca status RGY (Red/Yellow/Green) |
| `emit(event_type, payload)` | Emituje event przez EventBus (best-effort) |

**System statusow RGY:**

| Kolor | Znaczenie |
|-------|-----------|
| Green | Guardian OK — brak naruszenia |
| Yellow | Ostrzezenie — potencjalne naruszenie |
| Red | Blokada — naruszenie wykryte, akcja wymagana |

### 14.3 13 Guardianow (implementations.py)

| Nr | Guardian | Klasa | Co sprawdza |
|----|----------|-------|-------------|
| 1 | `SoTGuardian` | correctness | Feature poza Source of Truth (SoT) |
| 2 | `MasterplanGuardian` | correctness | Modul nie w Masterplan |
| 3 | `TestIntegrityGuardian` | coverage | Usuniecie/dezaktywacja testu bez Council+HG |
| 4 | `MockFallbackGuardian` | correctness | D3+ akcja na mock/demo/fallback/cache_stale danych |
| 5 | `EvidenceGuardian` | correctness | PASS bez `run_id`/`trace_id` (brak dowodow) |
| 6 | `GateGuardian` | correctness | D3+ akcja bez HG ticket |
| 7 | `CouncilGuardian` | correctness | D4/D5 bez sesji Rady |
| 8 | `ReleaseGuardian` | correctness | Release z nierozwiazanymi findingami |
| 9 | `LoopGuardian` | correctness | Potwierdza ze LoopGovernor blokuje |
| 10 | `LLMDriftGuardian` | performance | Roznica modeli A→B > 5% (drift) |
| 11 | `CostSentinel` | performance | 10x spike kosztow LUB przekroczenie budzetu |
| 12 | `PIIGuardian` | security | Wzorce email/telefon/PESEL/karta kredytowa w payload |
| 13 | `TraceCompletenessGuardian` | correctness | D3+ bez `trace_id` |

Guardiany 10-13 sa NOWE w E5 (pozostale 8 to core z spec sec 13).

**Rejestracja:**

```python
from sylion.aeis.testing.guardians import register_all_guardians

guardians = register_all_guardians(ontology_store, event_bus)
# guardians: list[GuardianBase] — 13 instancji
```

**Interfejs sprawdzania:**

```python
result = guardian.check(context: dict) -> {status: "red"|"yellow"|"green", message: str, payload: dict}
```

Guardiany ktore wykryja naruszenie wywoluja `self.alert(...)` tworzac `GuardianAlert` w OntologyStore.

### 14.4 Truth Alignment Matrix (truth_alignment.py)

Macierz wyrownania prawdy miedzy warstwami systemu.

**7 warstw (LAYERS):**

| Warstwa | Opis |
|---------|------|
| `sot` | Source of Truth (spec, manifest) |
| `masterplan` | Masterplan modulu |
| `runtime` | Dzialajacy kod produkcyjny |
| `api` | Definicje API (proto, OpenAPI) |
| `ui` | Interface uzytkownika |
| `test` | Pokrycie testami |
| `docs` | Dokumentacja |

**Klasy:**

```python
@dataclass
class FeatureSnapshot:
    feature_name: str
    sot: bool = False
    masterplan: bool = False
    runtime: bool = False
    api: bool = False
    ui: bool = False
    test: bool = False
    docs: bool = False

class TruthAlignmentMatrix:
    def build_for_feature(feature_name, **layer_flags) -> FeatureSnapshot
    def list_drifts() -> list[dict]    # wszystkie dryfy z reguly
    def list_aligned() -> list[dict]   # wszystkie wyrownane features
    def health_summary() -> dict       # {"total", "drifts", "aligned", "drift_rate"}
```

**Reguly detekcji dryfu:**

| Regula | Opis |
|--------|------|
| `runtime_without_sot_authorization` | Kod dziala bez autoryzacji w SoT |
| `sot_without_runtime_implementation` | Feature w SoT bez implementacji runtime |
| `docs_without_runtime` | Dokumentacja istnieje ale brak implementacji |
| `ui_shows_mock_despite_live_runtime` | UI pokazuje mock mimo ze runtime jest live |
| Per-layer present mismatch | Warstwa X istnieje bez sot lub runtime |

### 14.5 Weryfikacja

```bash
cd src/sylion-pipeline
python -m pytest tests/aeis/testing/test_guardians.py tests/aeis/testing/test_truth_alignment.py -v
# 39 testow: 29 guardians + 10 truth_alignment
```

---

## 15. W14 Release Rail: 12+6 checklist + 10 ReleaseStatus (E6) [commit 306ef4bb]

> Etap E6 (commit `306ef4bb`). 19 nowych testow. Cumulative: 352/352 PASS.
> Plik: `sylion.aeis.testing.release_rail`.

### 15.1 Architektura plikow

```
sylion/aeis/testing/
└── release_rail.py           — ReleaseRail, EvaluationContext, ReleaseReadinessReport

tests/aeis/testing/
└── test_release_rail.py      — 19 testow
```

### 15.2 ReleaseRail (release_rail.py)

Ostatni straznik przed wydaniem. Ocenia gotowosci RC i produkcji.

**Glowne metody:**

| Metoda | Opis |
|--------|------|
| `evaluate(ctx: EvaluationContext) -> dict` | Ewaluuje RC_CHECKLIST i PROD_CHECKLIST; zwraca `{status, checklist_results, blockers, rc_pass, prod_pass}` |
| `generate_report(ctx) -> ReleaseReadinessReport` | Tworzy i persystuje `ReleaseReadinessReport` w OntologyStore |

### 15.3 RC_CHECKLIST (12 punktow, spec sec 17.2)

| # | Klucz | Opis |
|---|-------|------|
| 1 | `sot_approved` | SoT zatwierdzone dla wersji |
| 2 | `masterplan_approved` | Masterplan zatwierdzone |
| 3 | `test_charter_approved` | Test Charter zatwierdzony (D3+) |
| 4 | `all_mandatory_tests_passed` | Wszystkie obowiazkowe testy przeszly |
| 5 | `every_pass_has_evidence` | Kazdy PASS ma `run_id`/`trace_id` |
| 6 | `no_p0_p1_findings` | Brak nierozwiazanych findinkow P0/P1 |
| 7 | `d3_findings_decided` | Wszystkie D3+ findinki maja decyzje |
| 8 | `regression_passed` | Testy regresji przeszly |
| 9 | `human_like_passed` | Symulacja HG przeszla (L3/L4) |
| 10 | `audit_chain_intact` | Lancuch audytu kompletny |
| 11 | `no_mock_as_live` | Brak mock danych jako live |
| 12 | `artifact_hashes_present` | Skroty artefaktow obecne |

### 15.4 PROD_CHECKLIST (6 dodatkowych punktow, spec sec 17.3)

| # | Klucz | Opis |
|---|-------|------|
| 1 | `release_rehearsal_passed` | Probna publikacja przeszla |
| 2 | `rollback_tested_within_7d` | Rollback testowany w ciagu 7 dni |
| 3 | `final_approval_signed` | Ostateczna zgoda podpisana |
| 4 | `council_completed_d4_d5` | Rada zakonczyla sesje D4/D5 |
| 5 | `sentinels_pass` | Wszystkie Sentinele (CostSentinel, PIIGuardian) OK |
| 6 | `operator_signed_final_gate` | Operator podpisal finalny gate |

### 15.5 Logika statusow (10 stanow ReleaseStatus)

Rozszerzony enum `ReleaseStatus` z E1 (draft/rc/approved/rejected/shipped/rolled_back) plus stany posrednie:

| Status | Warunek |
|--------|---------|
| `READY_FOR_PRODUCTION` | `prod_pass=True` (wszystkie 18 punktow OK) |
| `READY_FOR_RELEASE_CANDIDATE` | `rc_pass=True` (12 RC OK) ale PROD niespelniony |
| `BLOCKED_BY_GOVERNANCE` | Punkty governance broken (sot/masterplan/council/d3_decisions) |
| `BLOCKED_BY_FINDINGS` | Inne punkty broken (p0/p1, testy, audit, hashes) |

Determination algorithm:

```python
if prod_pass:
    status = "READY_FOR_PRODUCTION"
elif rc_pass:
    status = "READY_FOR_RELEASE_CANDIDATE"
elif any(b in GOVERNANCE_KEYS for b in blockers):
    status = "BLOCKED_BY_GOVERNANCE"
else:
    status = "BLOCKED_BY_FINDINGS"
```

### 15.6 EvaluationContext

```python
@dataclass
class EvaluationContext:
    rc_id: str                          # ID ReleaseCandidate
    version: str                        # np. "1.4.2"
    hints: dict = field(default_factory=dict)  # overrides per klucz checklist
    # Klucze hints: identyczne z kluczami RC_CHECKLIST + PROD_CHECKLIST
    # Jesli hint[key]=True → pozycja uznana za zaliczona (bypass query do ontology)
```

### 15.7 Rekomendacje

`generate_report` automatycznie tworzy `recommendations` na podstawie listy `blockers`:

- Kazdy blocker mapuje sie na komunikat po angielsku wyjasnajacy co zrobic.
- `comprehension_score` = `1.0` jesli `hints.get("human_like_passed")` else `0.0`.

### 15.8 Weryfikacja

```bash
cd src/sylion-pipeline
python -m pytest tests/aeis/testing/test_release_rail.py -v
# 19 testow: RC+PROD checklist stale, evaluate path, generate_report,
#            recommendations, comprehension score, status determination
```

---

## 16. Cross-references do modułów E7-E12 (sync v6)

Poniższe moduły rozszerzają ontologię W14 zdefiniowaną w tym dokumencie.
Każdy plik zawiera pełną dokumentację 10-sekcyjną.

| Moduł | Plik | Zakres |
|-------|------|--------|
| CharterStore + FindingStore | [`47_w14_charter_finding.md`](./47_w14_charter_finding.md) | E7 — wrappery lifecycle `TestCharter` i `Finding`; TRANSITIONS/R-status enforcement; auto-mirror do governance tickets D2+; 27 testów |
| Human Lab — 8 person | [`48_w14_human_lab.md`](./48_w14_human_lab.md) | E8 — 4 nowe persony (05-08); 10 scenariuszy startowych pokrywających wszystkie 8 person; `starter_scenarios()`; 14 testów |
| Test Center UI + Memory + Self-Audit | [`49_w14_test_center.md`](./49_w14_test_center.md) | E9+E10 — 8 stron frontend `/test-center/*`; `TestingMemoryStore` (4 tabele); `W14SelfAudit` 10 filarów; sidebar link; 12 testów |
| 6 Demo Projects | [`50_w14_demo_projects.md`](./50_w14_demo_projects.md) | E11 — 6 manifestów YAML; `DemoProjectOrchestrator`; `execute_demo` 6-krokowy lifecycle; 51 REST endpoints; 6 stron FE; 151 testów |
| Agent Team Theater | [`51_w14_agent_team_theater.md`](./51_w14_agent_team_theater.md) | E12 — `AgentTheaterAggregator` read-only; 6 REST endpoints; `/test-center/theater` dashboard; 9 testów |

Oba obiekty `TestCharter` i `Finding` (sekcje 2.1 i 2.2 tego dokumentu) są używane
przez `CharterStore` i `FindingStore` z modułu E7. `ReleaseCandidate` i
`ReleaseReadinessReport` (sekcja 15) są używane przez `execute_demo` z E11.
