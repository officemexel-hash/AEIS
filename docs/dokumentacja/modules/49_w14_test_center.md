# W14 Test Center — UI MVP + Memory + Self-Audit
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Moduły: `sylion.aeis.testing.memory` + `sylion.aeis.testing.self_audit`
> Frontend: `src/sylion-frontend/src/app/(app)/test-center/`
> Commits: `bad4c2c0` (E9+E10) + `50773c5a` (E12-FE theater) + `cec149cb` (integration)

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura](#2-architektura)
3. [Konfiguracja](#3-konfiguracja)
4. [Frontend — struktura stron](#4-frontend--struktura-stron)
5. [TestingMemoryStore](#5-testingmemorystore)
6. [W14SelfAudit](#6-w14selfaudit)
7. [Integracja — register_testing_actions + sidebar link](#7-integracja--register_testing_actions--sidebar-link)
8. [Przykład użycia](#8-przykład-użycia)
9. [Weryfikacja](#9-weryfikacja)
10. [Rozwiązywanie problemów](#10-rozwiązywanie-problemów)
11. [Cross-references](#11-cross-references)

---

## 1. Cel modułu

Test Center to centralny hub do obserwacji i sterowania infrastrukturą testową W14.
Składa się z trzech warstw:

- **UI (E9)** — 8 stron frontend pokrywających wszystkie filary W14 (truth alignment,
  simulation, auto-repair, human lab, release gate, catalog, agent theater)
- **Memory (E10)** — `TestingMemoryStore` persystuje wnioski z testów między projektami;
  umożliwia cross-project pattern matching
- **Self-Audit (E10)** — `W14SelfAudit` uruchamia 10 dymnych sprawdzeń weryfikując, że
  infrastruktura testowa W14 jest w pełni sprawna (W14 testuje siebie)

Sidebar link (commit `cec149cb`) zapewnia dostęp z głównej nawigacji pod sekcją
"Testowanie i Release".

---

## 2. Architektura

```
Frontend:
  test-center/
    page.tsx                  hub — 8 kart sekcji
    dashboard/page.tsx        placeholder project test dashboard
    truth-alignment/page.tsx  7-layer matrix (mock data)
    simulation/page.tsx       L0-L4 backend status
    auto-repair/page.tsx      13 R-statusów + Loop Governor limits
    human-lab/page.tsx        siatka 8 person z opisami
    release-gate/page.tsx     checklist 12+6 z mock wynikami
    catalog/page.tsx          katalog T0-T19 klas testów
    theater/page.tsx          Agent Team Theater (dodany w E12)

Backend:
  testing/memory.py           TestingMemoryStore (4 tabele SQLite)
  testing/self_audit.py       W14SelfAudit (10 filarów)

Sidebar:
  components/layout/AppSidebar.tsx   sekcja "Testowanie i Release" z /test-center

Integration:
  api/app.py                  register_testing_actions() przy starcie (try/except)
```

Wszystkie strony frontend używają wzorca z `decisions/page.tsx`: hook `useHealth`,
blokada `backendLive`, komponenty `Card` i `Badge`. Dane mockowane — podłączenie do
`/api/v1/testing/*` endpointów przewidziane w E11 demo projects.

---

## 3. Konfiguracja

| Zmienna | Default | Opis |
|---------|---------|------|
| `SYLION_W14_DB` | `sylion_aeis.db` | Ścieżka do SQLite; TestingMemoryStore używa tej samej bazy gdy persystencja potrzebna |
| `SYLION_W14_MEMORY_DB` | `:memory:` | Override dla TestingMemoryStore (osobna baza lub in-memory) |

`W14SelfAudit` tworzy własny in-memory `OntologyStore` na czas sprawdzenia — nie wymaga
konfiguracji produkcyjnej bazy.

---

## 4. Frontend — struktura stron

### Hub `/test-center`

Strona główna z 8 kartami nawigacyjnymi (tytuł + ikona + opis + link):

| Karta | URL | Opis |
|-------|-----|------|
| Test Dashboard | `/test-center/dashboard` | Placeholder dla wykresu stanu testów projektu |
| Truth Alignment | `/test-center/truth-alignment` | Macierz 7-warstwowa (SoT/MasterPlan/Human/.../Council) |
| Simulation | `/test-center/simulation` | Status L0-L4 backendu |
| Auto-Repair | `/test-center/auto-repair` | 13 R-statusów + limity Loop Governor |
| Human Lab | `/test-center/human-lab` | Siatka 8 person z opisami |
| Release Gate | `/test-center/release-gate` | Checklist RC (12) + PROD (6) z wynikami mock |
| Test Catalog | `/test-center/catalog` | Katalog T0-T19 klas testów |
| Agent Theater | `/test-center/theater` | Dashboard zespołu agentów (E12) |

### `/test-center/truth-alignment`

Wyświetla 7-warstwową macierz zgodności (mock data):

```
Warstwa 1: SoT (Source of Truth)
Warstwa 2: MasterPlan
Warstwa 3: Human Gate
Warstwa 4: Charter
Warstwa 5: Findings
Warstwa 6: Release Rail
Warstwa 7: Council
```

### `/test-center/auto-repair`

Pokazuje 13 R-statusów (R0 OPEN do R9 CLOSED) + limity Loop Governor:

- Maksymalna liczba prób naprawy per finding
- Limit czasu w pętli naprawczej
- Limity linii diff i zmienianych plików
- Status Loop Governor (ACTIVE / BLOCKED)

### `/test-center/release-gate`

Checklist z 12 punktami RC i 6 punktami PROD z przykładowymi wynikami mock.
Pokazuje statusy: `satisfied` (zielony), `missing` (czerwony), `not_applicable` (szary).

### `/test-center/catalog`

Tabela klas testów T0-T19 z nazwą, opisem i przykładem zastosowania. Umożliwia
operatorowi szybkie sprawdzenie co obejmuje każda klasa przed przypisaniem projektu.

### `/test-center/theater`

Dodany przez E12 (commit `50773c5a`). Dashboard Agent Team Theater z:
- Kartą topologii (aktorzy: Claude/Codex/Kimi + otwarte findingi)
- Kartą 13 guardianów z chip HEALTH + alert_24h
- Kartą Local Models (qwen/gpt-oss obciążenie)
- Auto-refresh co 5 sekund

### Sidebar — sekcja "Testowanie i Release"

Umieszczona między sekcjami "Decyzje" a "Konfiguracja" w `AppSidebar.tsx`:

```typescript
const testingItems = [
  { title: "Test Center", url: "/test-center", icon: TestTube },
];
```

Stan `testingOpen` (accordion). Renderuje po stronie klienta (Client Component).

---

## 5. TestingMemoryStore

### Opis

`TestingMemoryStore` to persystentny magazyn wniosków z testów między projektami.
Umożliwia zadanie pytania "co się nie powiodło w podobnym projekcie?" przed startem.

### Tabele SQLite

```sql
-- Wnioski na poziomie projektu
CREATE TABLE w14_lessons (
    lesson_id    TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    release_id   TEXT NOT NULL DEFAULT '',
    pattern_type TEXT NOT NULL,           -- klasa wzorca (np. 'gps_drift', 'gdpr_delete')
    context      TEXT NOT NULL DEFAULT '{}',    -- JSON kontekst wykrycia
    detection    TEXT NOT NULL DEFAULT '{}',    -- JSON jak wykryto
    resolution   TEXT NOT NULL DEFAULT '{}',    -- JSON jak rozwiązano
    generalization TEXT NOT NULL DEFAULT '{}',  -- JSON jak uogólnić na inne projekty
    created_at   REAL NOT NULL
);

-- Przyczyny źródłowe z LoopReports
CREATE TABLE w14_root_causes (
    cause_id     TEXT PRIMARY KEY,
    finding_id   TEXT NOT NULL,
    cause_class  TEXT NOT NULL,           -- klasa przyczyny (np. 'missing_validation')
    description  TEXT NOT NULL DEFAULT '',
    confidence   REAL NOT NULL DEFAULT 0.5,
    created_at   REAL NOT NULL
);

-- Flakujące testy
CREATE TABLE w14_flaky_patterns (
    pattern_id   TEXT PRIMARY KEY,
    test_id      TEXT NOT NULL,
    fail_rate    REAL NOT NULL DEFAULT 0.0,
    fail_modes   TEXT NOT NULL DEFAULT '[]',  -- JSON lista trybów awarii
    runs_total   INTEGER NOT NULL DEFAULT 0,
    runs_failed  INTEGER NOT NULL DEFAULT 0,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);

-- Katalog anty-wzorców (system-wide)
CREATE TABLE w14_anti_patterns (
    ap_id              TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    severity           TEXT NOT NULL DEFAULT 'D3',
    detected_in_count  INTEGER NOT NULL DEFAULT 1,  -- ile projektów
    detection_rule     TEXT NOT NULL DEFAULT '',
    prevention         TEXT NOT NULL DEFAULT '',
    created_at         REAL NOT NULL
);
```

### Metody publiczne

| Metoda | Sygnatura | Opis |
|--------|-----------|------|
| `record_lesson` | `(project_id, release_id, pattern_type, context, detection, resolution, generalization)` | Zapisuje wniosek z projektu |
| `list_lessons_similar_to` | `(pattern_type, limit=20)` | Cross-project matching po `pattern_type` |
| `record_root_cause` | `(finding_id, cause_class, description, confidence)` | Zapisuje przyczynę źródłową |
| `record_flaky` | `(test_id, fail_mode)` | Rejestruje flakujący test lub aktualizuje statystyki |
| `add_anti_pattern` | `(ap_id, name, severity, detection_rule, prevention)` | Dodaje nowy anty-wzorzec |
| `increment_anti_pattern` | `(ap_id)` | Inkrementuje `detected_in_count` dla istniejącego anty-wzorca |
| `health` | `()` | Zwraca dict z liczbami wierszy per tabela |

### Thread safety

`TestingMemoryStore` używa `threading.RLock` i `check_same_thread=False`. Dla baz
plikowych włącza `PRAGMA journal_mode=WAL` (lepszа wydajność przy wielu czytnikach).

---

## 6. W14SelfAudit

### Opis

`W14SelfAudit.run_full_cycle()` uruchamia 10 dymnych sprawdzeń weryfikujących, że cała
infrastruktura testowa W14 jest w pełni sprawna. Każdy filar jest izolowany — awaria
jednego nie przerywa pozostałych.

### 10 filarów

| # | Filar | Co sprawdza |
|---|-------|-------------|
| 1 | `ontology` | CRUD per typ obiektu w OntologyStore (create/get/list/update) |
| 2 | `actions` | Rejestracja 20 handlerów W14 testing actions |
| 3 | `branches_and_simulation` | BranchManager + SimulationEngine L0-L4 lifecycle |
| 4 | `personas_and_runtime` | Ładowanie 8 person + symulacja workflow |
| 5 | `auto_repair_loop_merge` | AutoRepairController R0→R9 + LoopGovernor + MergeGuard |
| 6 | `guardians` | Rejestracja 13 guardianów + health snapshot |
| 7 | `truth_alignment` | TruthAlignmentMatrix 7-warstwa build + list_drifts |
| 8 | `charter_findings_stores` | CharterStore + FindingStore pełny lifecycle (E7) |
| 9 | `release_rail` | RC + PROD checklist evaluate + generate_report |
| 10 | `memory` | TestingMemoryStore CRUD + health |

### Format wynikowy

```python
result = W14SelfAudit().run_full_cycle()
# {
#   "status": "pass",           # "pass" gdy wszystkie 10 filarów OK
#   "total_pillars": 10,
#   "passed": 10,
#   "failed": 0,
#   "duration_s": 0.45,
#   "results": [
#     {"pillar": "ontology", "status": "pass", "details": {...}, "duration_s": 0.03, "error": null},
#     ...
#   ]
# }
```

W przypadku awarii filaru: `status: "fail"`, pole `error` zawiera traceback, `details`
zawiera częściowe wyniki z momentu awarii.

### Izolacja

Każdy filar tworzy własny in-memory `OntologyStore` (SQLite `:memory:`). Sprawdzenia
nie wpływają na produkcyjną bazę danych i nie pozostawiają trwałych danych.

---

## 7. Integracja — register_testing_actions + sidebar link

### register_testing_actions w app.py (commit `cec149cb`)

Przy starcie serwera FastAPI (po `get_human_gate()`) rejestrowane jest 20 handlerów
W14 testing actions:

```python
# app.py — fragment
try:
    from sylion.aeis.testing.ontology import OntologyStore
    from sylion.aeis.testing.actions import register_testing_actions
    ontology = OntologyStore(db_path=db_path)
    register_testing_actions(ontology, event_bus)
    log.info("W14 testing actions registered: %d handlers", handler_count)
except Exception as e:
    log.warning("W14 testing actions registration failed (non-fatal): %s", e)
```

Rejestracja jest **non-fatal** — awaria nie przerywa startu serwera. Sprawdź logi
przy poziomie WARNING jeśli akcje nie działają.

### Sidebar link (AppSidebar.tsx)

Sekcja `testingItems` dodana między "Decyzje" a "Konfiguracja":

```typescript
const testingItems = [
  { title: "Test Center", url: "/test-center", icon: TestTube },
];
// ...
const [testingOpen, setTestingOpen] = useState(false);
// <SectionHeader title="Testowanie i Release" open={testingOpen} onToggle={...} />
// <SectionItems items={testingItems} />
```

Sidebar jest Client Component — link wyrenderowany po hydratacji w przeglądarce.

---

## 8. Przykład użycia

### Uruchomienie Self-Audit

```python
from sylion.aeis.testing.self_audit import W14SelfAudit

audit = W14SelfAudit()
result = audit.run_full_cycle()

if result["status"] == "pass":
    print(f"Wszystkie {result['passed']} filary W14 OK w {result['duration_s']:.2f}s")
else:
    failed = [r for r in result["results"] if r["status"] == "fail"]
    for f in failed:
        print(f"FAIL {f['pillar']}: {f['error']}")
```

### Zapis i odczyt wniosku z projektu

```python
from sylion.aeis.testing.memory import TestingMemoryStore

mem = TestingMemoryStore(db_path="sylion_aeis.db")

# Po zakończeniu projektu mobile-field-inspector
mem.record_lesson(
    project_id="demo_01_mobile_field_inspector",
    release_id="rc-2026-04-26",
    pattern_type="gps_drift",
    context={"domain": "field_operations", "d_level": "D4"},
    detection={"guardian": "GPSCheck", "drift_km": 6.2},
    resolution={"fix": "add drift threshold validation in service layer"},
    generalization={"applies_to": ["any mobile-app with GPS input"]},
)

# Przy nowym projekcie z GPS
similar = mem.list_lessons_similar_to("gps_drift")
print(f"Znaleziono {len(similar)} podobnych przypadków z poprzednich projektów")
```

### Sprawdzenie health Memory Store

```python
health = mem.health()
# {
#   "lessons": 5,
#   "root_causes": 3,
#   "flaky_patterns": 1,
#   "anti_patterns": 2
# }
```

---

## 9. Weryfikacja

```bash
cd src/sylion-pipeline

# Testy Memory + Self-Audit (12 testów)
python -m pytest tests/aeis/testing/test_memory_and_self_audit.py -v

# Uruchom Self-Audit bezpośrednio
python -c "
from sylion.aeis.testing.self_audit import W14SelfAudit
r = W14SelfAudit().run_full_cycle()
print(r['status'], r['passed'], '/', r['total_pillars'], 'pillars')
"

# Sprawdź czy Test Center strona zwraca 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/test-center
# Oczekiwane: 200

# Sprawdź integration actions w logach backendu
grep "W14 testing actions" sylion_backend.log
# Oczekiwane: "W14 testing actions registered: 20 handlers"
```

---

## 10. Rozwiązywanie problemów

### Self-Audit filar `charter_findings_stores` odpada

Sprawdź, czy `CharterStore` i `FindingStore` są zaimportowane poprawnie.
Filar tworzy in-memory store — awaria wskazuje na błąd importu lub regresję w E7.
Uruchom `test_charter_store.py` i `test_findings_store.py` oddzielnie.

### `TestingMemoryStore` traci dane między restartami

Sprawdź czy `db_path` nie jest `:memory:` w konfiguracji produkcyjnej.
Ustaw `SYLION_W14_MEMORY_DB=sylion_w14_memory.db` (osobna baza od głównej W14).

### Sidebar link `/test-center` nie widoczny

Sidebar jest Client Component — sprawdź czy JavaScript jest włączony i czy hydratacja
nie zwróciła błędu (DevTools > Console). Upewnij się, że `testingOpen` state i
`SectionItems` są poprawnie wiring-u w `AppSidebar.tsx`.

### W14 testing actions registration failed przy starcie

Komunikat WARNING w logach. Nie blokuje serwera. Sprawdź:
1. Czy `sylion.aeis.testing.actions` jest importowalny
2. Czy `register_testing_actions` nie rzuca wyjątku przy pierwszym uruchomieniu
3. Czy `db_path` z `app.py` jest dostępny do zapisu

---

## 11. Cross-references

- [`46_w14_ontology.md`](./46_w14_ontology.md) — OntologyStore, Testing Actions (20
  handlerów, E2), Branches/Simulation L0-L4 (E3), Auto-Repair R0-R9 (E4), 13 Guardians
  + TruthAlignment (E5), Release Rail 12+6 (E6)
- [`47_w14_charter_finding.md`](./47_w14_charter_finding.md) — CharterStore i FindingStore
  testowane w filarze 8 Self-Audit
- [`48_w14_human_lab.md`](./48_w14_human_lab.md) — 8 person wyświetlanych w
  `/test-center/human-lab`
- [`51_w14_agent_team_theater.md`](./51_w14_agent_team_theater.md) — Agent Theater backend
  podłączony pod `/test-center/theater`
- [`50_w14_demo_projects.md`](./50_w14_demo_projects.md) — execute_demo wywołuje
  TestingMemoryStore.record_lesson() po każdym projekcie
- [`modules/41_environment_variables.md`](./41_environment_variables.md) — zmienne
  `SYLION_W14_DB` i `SYLION_W14_MEMORY_DB`
