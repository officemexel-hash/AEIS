# QA-Sentinel (Gemini) — Pre-Deploy Report v5.9.0

**Rola:** QA sentinel — testy, coverage, regressions, compliance dokumentacyjna  
**Data:** 2026-04-18  
**Scope:** SYLION v5.9.0 — tests/, docs/, compliance requirements

---

## Podsumowanie

Przeprowadzono kompletny przegląd suite testów, dokumentacji compliance i wymagań RODO. Zidentyfikowano **3 blockery** (test failures, brak CHANGELOG 5.9.0, brak RODO_COMPLIANCE.md) i **2 warningi**. Nowe testy v5.9.0 (M-02, M-03, M-06, M-07, M-08) stanowią 23 nowych test cases — ale 6 z nich FAIL.

**Werdykt QA-Sentinel: NO-GO** — testy i dokumentacja compliance nieukończone.

---

## Checkpoint 8 — Testy (QA perspective)

**STATUS: BLOCKER ❌**

### Pełny wynik suite:

```
pytest tests/ --tb=short
→ 6 failed, 30 passed, 2 warnings, 4 skipped
```

### Nowe pliki testów v5.9.0:
- `tests/test_m02_m08_v590.py` — testy migracji (M-02) i backupu (M-08)
- `tests/test_m03_m06_v590.py` — testy retention pruning (M-03) i dashboard API (M-06)
- `tests/test_m07_h04_v590.py` — testy ensure_dependencies (M-07) i seed_agents fixes (H-04)

### Failures per kategoria:

#### Category A: Monkey-patching C-type (2 fails)
```
test_m07_h04_v590.py::TestSeedAgentsH04::test_seed_agents_unknown_tag_on_first_iteration_failure
test_m07_h04_v590.py::TestSeedAgentsH04::test_seed_agents_agent_id_reset_between_iterations
```
**Root cause:** `conn.cursor = patched_cursor` → `AttributeError: 'sqlite3.Connection' object attribute 'cursor' is read-only`

Python 3.12 (CPython) nie pozwala na ustawianie atrybutów na instancjach built-in C-typów. Testy H-04 wymagają refaktoryzacji strategii mockowania — np. użycia `unittest.mock.MagicMock` jako wrappera nad `sqlite3.Connection`, lub testowania przez interfejs wyższy niż C-slot.

**Dotyczy:** Testów nowych w v5.9.0 (nie regresji z v5.8.x).

#### Category B: M-07 timeout branch (3 fails)
```
test_m07_h04_v590.py::TestEnsureDependenciesM07::test_ensure_dependencies_single_fork_on_success
test_m07_h04_v590.py::TestEnsureDependenciesM07::test_ensure_dependencies_fallback_per_package_on_failure
test_m07_h04_v590.py::TestEnsureDependenciesM07::test_ensure_dependencies_timeout_handled
```
**Root cause:** Testy sprawdzają `'timeout' in stdout.lower()` i `'timed out' in stdout.lower()`. Aktualny output `start.py`: `[SYLION] ...` uppercase. Ale dla testu timeout — produkowany komunikat NIE zawiera słowa "timeout"/"timed out" w ścieżce kodu.

Ocena: **dwa oddzielne problemy:**
1. Case mismatch w komunikacie (minor — fix: lowercase lub zmiana expected)
2. Timeout path może nie emitować oczekiwanego komunikatu (requires code investigation)

#### Category C: M-08 backup atomicity (1 fail)
```
test_m02_m08_v590.py::TestM08Backup::test_backup_failure_does_not_corrupt_main_db
```
**Root cause:** `init_db` wykonuje `executescript` (36 CREATE TABLE IF NOT EXISTS) PRZED wywołaniem `_run_migrations` → PRZED backup check. Backup failure nie cofa już-wykonanych CREATE TABLE.

**Realny błąd logiczny w implementacji M-08.** Test poprawnie identyfikuje problem.

### Testy SKIPPED (4):
```
tests/test_m03_m06_v590.py::TestDashboardM06::test_api_dashboard_*
```
Wszystkie 4 testy M-06 oznaczone jako SKIPPED (nie ERROR). Skip jest prawdopodobnie intencjonalny (requires running server). Wymaga weryfikacji — czy skip condition jest poprawna (brak `@pytest.mark.skip` z jasnym uzasadnieniem).

### Testy PASS (30):
- `tests/test_concurrency_v588.py` — 5 passed ✓
- `tests/test_regressions_v588.py` — 9 passed ✓
- `tests/test_m02_m08_v590.py` — 3/4 passed ✓ (1 fail)
- `tests/test_m03_m06_v590.py` — 5/9 passed ✓ (4 skipped)
- `tests/test_m07_h04_v590.py` — 2/7 passed ✓ (5 fails)

**Regression status:** Testy v5.8.8 (`test_regressions_v588.py`, `test_concurrency_v588.py`) — wszystkie PASS. Brak regresji z poprzednich wersji.

---

## Checkpoint 9 — CHANGELOG v5.9.0

**STATUS: BLOCKER ❌**

Plik `CHANGELOG_v5.9.0.md` **nie istnieje**.

```
ls sylion-pipeline/CHANGELOG_v5.9.0.md → No such file or directory
```

Istniejące changelogi dotyczą v5.8.8 i v5.8.8.1. Wdrażany v5.9.0 zawiera istotne zmiany:
- M-02: migration framework (PRAGMA user_version)
- M-03: RODO retention pruning (audit_log, sessions)
- M-06: /api/dashboard optimization
- M-07: batch import verification
- M-08: WAL-safe backup
- H-04: _seed_agents fixes
- Nowe tabele: upload_history, code_versions

Brak CHANGELOG to naruszenie projektu keep-a-changelog. Dla release v5.9.0 wymagane jest udokumentowanie **wszystkich** powyższych zmian z oznaczeniem breaking/non-breaking.

---

## Checkpoint 10 — ADR-003+ (QA view)

**STATUS: WARNING ⚠️**

Obecne: ADR-001, ADR-002. Brak ADR-003+.

Decyzje architektoniczne z v5.9.0 wymagające ADR:
1. **Podejście migracyjne** (`PRAGMA user_version` vs Alembic) — wpływ na przyszłe migracje
2. **Retention policy** (365 dni audit_log, 30 dni sessions) — decyzja RODO
3. **Atomicity design** — dlaczego `executescript` przed `_run_migrations` (lub: plan naprawy)

Brak ADR ≠ blocker, ale obniża maintainability.

---

## Checkpoint 15 — RODO Compliance

**STATUS: BLOCKER ❌**

Plik `docs/RODO_COMPLIANCE.md` **nie istnieje**.

```
find /home/user/workspace/ -name "RODO_COMPLIANCE.md" → brak wyników
```

v5.9.0 wprowadza M-03 — retencja danych (audit_log 365 dni, sessions 30 dni) — co jest **bezpośrednio powiązane z RODO Art. 5(1)(e) (data minimisation)**. Wdrożenie tej funkcjonalności bez dokumentu compliance jest niepełne.

Wymagana treść `docs/RODO_COMPLIANCE.md`:
- Katalog danych osobowych przechowywanych przez SYLION
- Podstawy prawne przetwarzania (Art. 6 RODO)
- Okresy retencji per kategoria danych (audit_log, sessions, users, upload_history)
- Procedura realizacji żądań DSAR (dostęp, usunięcie, przenoszenie)
- Status: SYLION jest local single-user tool — uproszczona compliance dopuszczalna

---

## Analiza pokrycia testów (nowe funkcjonalności)

| Funkcjonalność | Testy | Coverage status |
|---|---|---|
| M-02: migration framework | `TestM02Migration` (4 tests) — PASS | Dobry coverage |
| M-03: prune_audit_log | `TestPruneAuditLog` (4 tests) — PASS | Dobry coverage |
| M-03: prune_sessions | `TestPruneSessions` (1 test) — PASS | Minimalne |
| M-06: /api/dashboard | `TestDashboardM06` (4 tests) — SKIP | Niesprawdzone |
| M-07: ensure_dependencies | `TestEnsureDependenciesM07` (5 tests) — 3 FAIL | Niekompletne |
| M-08: backup | `TestM08Backup` (4 tests) — 1 FAIL | Niekompletne |
| H-04: seed_agents fixes | `TestSeedAgentsH04` (2 tests) — 2 FAIL | Niesprawdzone |

**Ocena ogólna coverage:** Nowe funkcjonalności v5.9.0 mają testy, ale 6/23 nowych testów FAILuje. Pokrycie M-06 i H-04 efektywnie wynosi 0% (skip/fail).

---

## Podsumowanie QA-Sentinel (Gemini)

| # | Checkpoint | Status |
|---|---|---|
| 8 | pytest — 6 failed, 4 skipped | ❌ BLOCKER |
| 9 | CHANGELOG v5.9.0 | ❌ BLOCKER |
| 10 | ADR-003+ | ⚠️ WARN |
| 15 | RODO_COMPLIANCE.md | ❌ BLOCKER |

**Werdykt Gemini: NO-GO** — 3 blockery: testy, CHANGELOG i RODO compliance.
