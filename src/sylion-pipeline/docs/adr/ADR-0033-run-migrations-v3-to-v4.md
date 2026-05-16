# ADR-0033: run_migrations_v3_to_v4 (csrf_tokens + health_history)

**Status:** PROPOSED  
**Data:** 2026-04-20  
**Wersja:** 5.9.2  
**Autor:** SYLION AI Council / mega_audit/migrations_deep  

---

## Kontekst

Zmiany wprowadzone w v5.9.2 (ADR-0026..0032) wymagają nowych tabel i kolumn w bazie SQLite. Obecny schemat bazy to v3 (PRAGMA user_version = 3, ustanowiony w ADR-0003). Framework migracji (ADR-0003) wymaga dedykowanej funkcji `run_migrations_v3_to_v4()` dla każdego skoku wersji schematu.

Wymagane zmiany schematu dla v5.9.2:

**Nowe tabele:**

1. `csrf_tokens` (ADR-0026):
   ```sql
   CREATE TABLE IF NOT EXISTS csrf_tokens (
       token      TEXT PRIMARY KEY,
       session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
       created_at INTEGER NOT NULL,
       expires_at INTEGER NOT NULL
   );
   CREATE INDEX IF NOT EXISTS idx_csrf_tokens_session ON csrf_tokens(session_id);
   ```

2. `health_history` (mega_audit/diagnostyka_deep — metryki SRE):
   ```sql
   CREATE TABLE IF NOT EXISTS health_history (
       id         INTEGER PRIMARY KEY AUTOINCREMENT,
       ts         INTEGER NOT NULL,
       syl_code   TEXT,
       endpoint   TEXT,
       status_code INTEGER,
       latency_ms  REAL
   );
   CREATE INDEX IF NOT EXISTS idx_health_history_ts ON health_history(ts);
   ```

3. `pipeline_runs` (ADR-0028):
   ```sql
   CREATE TABLE IF NOT EXISTS pipeline_runs (
       run_id      TEXT PRIMARY KEY,
       status      TEXT NOT NULL DEFAULT 'queued',
       started_at  INTEGER,
       finished_at INTEGER,
       artifact_path TEXT,
       error_syl_code TEXT
   );
   ```

**Nowe kolumny w istniejących tabelach:**

4. `agents.last_health_check` (INTEGER) — timestamp ostatniego health check przez agent monitor
5. `audit_log.syl_code` (TEXT NULL) — kod diagnostyczny (ADR-0029) dla wpisów błędów

Zgodnie z ADR-0003: migracje muszą być addytywne (tylko ADD, nie DROP/RENAME), idempotentne (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN ... DEFAULT NULL`) i transakcyjne (jeden `BEGIN IMMEDIATE` / `COMMIT`).

Rozważane warianty:
- **M1** — Ręczne skrypty SQL w `scripts/migrate_v3_to_v4.sql` (brak integracji z frameworkiem)
- **M2** — `run_migrations_v3_to_v4()` w `dashboard/db.py` zgodna z ADR-0003 (wybrana)
- **M3** — Alembic (SQLAlchemy migration tool) — wymaga SQLAlchemy jako zależności
- **M4** — Flyway (Java) — niekompatybilne ze środowiskiem Python/SQLite

## Decyzja

Wdrożenie **M2**: funkcja `run_migrations_v3_to_v4()` w `dashboard/db.py`:

```python
def run_migrations_v3_to_v4(conn: sqlite3.Connection) -> None:
    """Addytywna migracja schematu v3 → v4 (SYLION v5.9.2)."""
    with conn:  # BEGIN IMMEDIATE / COMMIT lub ROLLBACK
        _create_csrf_tokens(conn)
        _create_health_history(conn)
        _create_pipeline_runs(conn)
        _add_agents_last_health_check(conn)
        _add_audit_log_syl_code(conn)
        conn.execute("PRAGMA user_version = 4")
```

Wywoływana przez `init_db()` po sprawdzeniu `PRAGMA user_version` (gdy == 3). Po migracji: `user_version = 4`.

## Konsekwencje

### Pozytywne
- Spójna z ADR-0003 strategia migracji — jeden punkt zarządzania schematem
- Transakcyjność: błąd w połowie migracji → automatyczny ROLLBACK → baza pozostaje w v3
- Idempotentność: wielokrotne wywołanie `run_migrations_v3_to_v4()` nie psuje danych
- Automatyczna migracja przy pierwszym starcie v5.9.2 — zero ręcznych kroków dla użytkowników

### Negatywne
- `ALTER TABLE agents ADD COLUMN last_health_check` — SQLite nie wspiera `ALTER COLUMN` (tylko ADD) — brak możliwości zmiany typu w przyszłości bez DROP/CREATE
- 5 zmian schematu w jednej migracji zwiększa ryzyko konfliktu z równoległymi zmianami (dev branches)

### Neutralne
- Rollback schematu z v4 → v3 niemożliwy (SQLite brak `ALTER TABLE DROP COLUMN` < 3.35) — dokumentowane w `MIGRATION_GUIDE.md`
- Testy migracji: `tests/test_migrations.py::test_v3_to_v4` + `test_v3_to_v4_idempotent`

## Alternatywy odrzucone

- **Alembic (M3)**: wymaga SQLAlchemy — naruszenie zasady minimal-dependencies SYLION — odrzucone
- **Flyway (M4)**: Java runtime — niekompatybilne z Python-only stack — odrzucone

## Referencje

- ADR-0003 (migration-framework) — framework migracji SYLION
- ADR-0026 (csrf-full-coverage) — tabela `csrf_tokens`
- ADR-0028 (run-codebase-audit-orchestrator) — tabela `pipeline_runs`
- ADR-0029 (diagnostics-v2-syl-codes) — kolumna `audit_log.syl_code`
- ADR-0031 (db-init-race-condition) — `init_db()` + `lifespan`
- `dashboard/db.py` — `run_migrations_v3_to_v4()`, `init_db()`
- `tests/test_migrations.py` — testy migracji v3→v4
- `docs/MIGRATION_GUIDE.md` — instrukcja dla użytkowników upgradujących v5.9.1 → v5.9.2
