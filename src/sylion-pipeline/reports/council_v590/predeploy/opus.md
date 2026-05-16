# Kod-Reviewer (Opus) — Pre-Deploy Report v5.9.0

**Rola:** Główny recenzent kodu, architektura i jakość implementacji  
**Data:** 2026-04-18  
**Scope:** SYLION v5.9.0 — diff vs v5.8.8.1 (baseline)

---

## Podsumowanie

Po dogłębnej analizie kodu v5.9.0 (diff-app.patch, diff-db.patch, diff-start.patch) oraz struktury repozytorium identyfikuję **3 blockery** i **4 warningi**. Werdykt częściowy: **NO-GO** bez naprawy blockerów M-08 i suite testów.

---

## Checkpoint 1 — Lockfile (`requirements.in` + `requirements-lock.txt`)

**STATUS: PASS ✓**

- `requirements.in` obecny: `/home/user/workspace/SYLION_v590_work/sylion-pipeline/requirements.in`
- `requirements-lock.txt` obecny i zawiera pinowane wersje z hashami generowanymi przez pip-compile
- Header lockfile: `Generated: 2026-04-11`, Python `>=3.10,<3.13`
- Wszystkie zależności z `requirements.in` mają odpowiedniki w lockfile
- `scripts/regen-lock.sh` skrypt obecny (workflow dokumentowany)

Uwaga: lockfile nie zawiera `--hash=sha256:` (format bez hash-verification). Jest to świadoma decyzja projektu — lokalny pipeline, niskie ryzyko supply-chain attack. Rekomendacja: rozważyć `--generate-hashes` w przyszłej wersji.

---

## Checkpoint 2 — VERSION file

**STATUS: PASS ✓**

```
cat VERSION → "5.9.0"
```

Plik `VERSION` zaktualizowany poprawnie do `5.9.0`.

---

## Checkpoint 3 — SYLION_VERSION w app.py

**STATUS: PASS ✓**

```python
# dashboard/app.py:132
SYLION_VERSION = "5.9.0"
```

Stała `SYLION_VERSION` ustawiona na `"5.9.0"`. Endpoint `/api/version` zwraca tę wartość. Spójne z plikiem VERSION.

---

## Checkpoint 4 — ENV secrets / hardcoded credentials

**STATUS: WARNING ⚠️ (znany, zaakceptowany)**

Zidentyfikowano w `dashboard/db.py` (`_DEFAULT_API_KEYS`):
```python
_DEFAULT_API_KEYS = {
    "OPENAI_API_KEY":      "sk-proj-JwEw64A9...",
    "ANTHROPIC_API_KEY":   "sk-ant-api03-rV-...",
    "PERPLEXITY_API_KEY":  "pplx-o2ZYm41s...",
    "GOOGLE_API_KEY":      "AQ.Ab8RN6Lio...",
}
```

**Ocena:** Jest to **znany finding**, świadomie zaakceptowany w v5.8.8 (patrz `REPORT.md`, `audit/security_v588.md` — decyzja HumanGate 2026-04-18). SYLION to lokalne narzędzie single-user bez ekspozycji sieciowej. Wartości te były obecne w v5.8.8 i nie są nowością w diff v5.9.0.

**Diff v5.9.0 nie wprowadza NOWYCH hardcoded credentials.** Żadne nowe tokeny/klucze w patchach diff-app.patch, diff-db.patch, diff-start.patch.

Nota: klucze powinny być rotowane jeśli zostały opublikowane w jakimkolwiek repo. To pozostaje poza zakresem tego audytu.

---

## Checkpoint 5 — Migracje PG / SQLite PRAGMA user_version

**STATUS: PASS ✓ (implementacja obecna)**

SQLite only — brak migracji PostgreSQL (N/A zgodnie z checklistą).

Framework migracyjny (`PRAGMA user_version`) zaimplementowany w `db.py`:
- `_DB_TARGET_VERSION = 1`
- `_run_migrations()` (linie 781–828): czyta `user_version`, aplikuje migracje rosnąco
- `_MIGRATIONS = {1: _migration_0_to_1}` — zarejestrowana migracja 0→1
- Każda migracja commituje własny `PRAGMA user_version = N`
- Downgrade refused: jeśli `user_version > target` → RuntimeError

---

## Checkpoint 6 — Backup DB (`_backup_db_before_migration`)

**STATUS: BLOCKER ❌**

Funkcja `_backup_db_before_migration()` jest zaimplementowana (linie 744–778, db.py) i używa sqlite3 Online Backup API. Jednak **test M-08 wykrywa krytyczny błąd**:

```
FAILED tests/test_m02_m08_v590.py::TestM08Backup::test_backup_failure_does_not_corrupt_main_db
AssertionError: Migration created 36 new tables despite backup failure. 
M-08 requires backup BEFORE _migrate_columns — abort on backup failure.
```

**Przyczyna:** W `_init_db_unlocked()` kolejność operacji jest:
1. `conn.executescript(...)` — tworzy WSZYSTKIE tabele (36 CREATE TABLE IF NOT EXISTS)
2. `_run_migrations(conn, db_path=DB_PATH)` — wywołuje backup, POTEM migracje

Gdy backup failuje, wyjątek z `_run_migrations` propaguje się poprawnie, ale tabele **już zostały utworzone** przez `executescript` w kroku 1. Test sprawdza że `len(new_tables) > 3` po failed backup — i to warunek jest spełniony (36 nowych tabel powstało przed próbą backupu).

**Konsekwencja:** M-08 zakłada atomowość: backup-failure → brak jakichkolwiek zmian w DB. Aktualnie niespełnione — `CREATE TABLE IF NOT EXISTS` wykonywane przed backup check.

**Wymagana naprawa:** Przenieść `executescript` za `_run_migrations` check LUB zmienić logikę tak, żeby `executescript` był częścią transakcji chronionej przez backup.

---

## Checkpoint 7 — Healthcheck endpoints

**STATUS: PASS ✓**

W `dashboard/app.py` potwierdzono:
- `GET /api/health` (linia 288) — implementacja obecna
- `GET /api/health/deep` (linia 294) — rozszerzony healthcheck
- `POST /api/health/diagnose` (linia 330) — diagnostyka
- `GET /api/dashboard` (linia 693) — endpoint dashboardu

Endpointy dostępne, implementacje nie zostały naruszone przez diff v5.9.0.

---

## Checkpoint 8 — Testy (`pytest tests/ -x`)

**STATUS: BLOCKER ❌**

Wynik: `6 failed, 30 passed, 2 warnings, 4 errors (4 skipped)`

### Failures:

**test_m02_m08_v590.py::TestM08Backup::test_backup_failure_does_not_corrupt_main_db**
- Patrz Checkpoint 6 — atomowość backup/migration

**test_m07_h04_v590.py::TestEnsureDependenciesM07 (3 testy)**
- `test_ensure_dependencies_single_fork_on_success` — FAIL
- `test_ensure_dependencies_fallback_per_package_on_failure` — FAIL  
- `test_ensure_dependencies_timeout_handled` — FAIL
- Przyczyna: test sprawdza `'timeout' in stdout.lower()` ale aktualny output zawiera `[SYLION]` zamiast `[sylion]`. Zmiana case'u w komunikatach M-07 w start.py (uppercase `[SYLION]` vs lowercase `[sylion]` oczekiwane przez test). To test-vs-implementation mismatch, ale **test NIE jest martwy** — wykrywa że M-07 nie raportuje timeout jak powinien.

**test_m07_h04_v590.py::TestSeedAgentsH04 (2 testy)**
- `test_seed_agents_unknown_tag_on_first_iteration_failure` — AttributeError
- `test_seed_agents_agent_id_reset_between_iterations` — AttributeError  
- Przyczyna: `conn.cursor = patched_cursor` → `AttributeError: 'sqlite3.Connection' object attribute 'cursor' is read-only` — Python 3.12 nie pozwala na monkey-patching atrybutów built-in C-typów. Testy wymagają poprawki techniki mockowania.

### Errors (4 skipped/error):
`tests/test_m03_m06_v590.py::TestDashboardM06` — 4 testy **SKIPPED** (nie ERROR jak raportował zbiorczo pytest przy -x). Prawdopodobnie skip z powodu brakujących fixtures/env. Nie są blockerami.

---

## Checkpoint 9 — CHANGELOG v5.9.0

**STATUS: BLOCKER ❌**

W katalogu projektu brak pliku `CHANGELOG_v5.9.0.md`. Jedyne pliki changelog to:
- `CHANGELOG_v5.8.8.md`
- `CHANGELOG_v5.8.8.1.md`

Brak dokumentacji zmian v5.9.0 (M-02, M-03, M-06, M-07, M-08, H-04). Release bez CHANGELOG jest niezgodny z konwencją projektu.

---

## Checkpoint 10 — ADR files (ADR-003+)

**STATUS: WARNING ⚠️**

Obecne ADRy:
- `docs/adr/ADR-001-seed-agents-guard.md` ✓
- `docs/adr/ADR-002-doc-scope-mismatch.md` ✓

Brakujące ADRy planowane dla v5.9.0:
- `ADR-003` — decyzja o frameworku migracyjnym PRAGMA user_version (vs Alembic/liquibase)
- `ADR-004` — decyzja o batch import verification w M-07
- `ADR-005` — RODO retention policy (M-03 audit_log + sessions)

Brak ADR-003+ to warning, nie blocker — projekt może działać bez nich, ale utrudnia onboarding nowych contributorow.

---

## Podsumowanie Kod-Reviewer (Opus)

| # | Checkpoint | Status |
|---|---|---|
| 1 | Lockfile (requirements.in + lock) | ✅ PASS |
| 2 | VERSION = 5.9.0 | ✅ PASS |
| 3 | SYLION_VERSION w app.py | ✅ PASS |
| 4 | ENV secrets — no new hardcoded creds | ⚠️ WARN (known) |
| 5 | SQLite PRAGMA user_version | ✅ PASS |
| 6 | _backup_db_before_migration | ❌ BLOCKER |
| 7 | Health endpoints /api/health + /api/dashboard | ✅ PASS |
| 8 | pytest tests/ — 6 failed | ❌ BLOCKER |
| 9 | CHANGELOG v5.9.0 | ❌ BLOCKER |
| 10 | ADR-003+ | ⚠️ WARN |

**Werdykt Opus: NO-GO** — 3 blockery wymagają naprawy przed deploy.
