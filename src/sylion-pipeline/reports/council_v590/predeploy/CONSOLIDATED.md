# Pre-Deploy Council CONSOLIDATED — SYLION v5.9.0

**Data:** 2026-04-18  
**Council:** 4 modele AI — Opus (kod-reviewer), Sonnet (CVE-watcher), GPT-5.4 (ops-auditor), Gemini (QA-sentinel)  
**Scope:** 15 checkpointów PRE-DEPLOY dla v5.9.0  
**Baseline:** SYLION v5.8.8.1 (`SYLION_v588_unzipped/`)

---

## WERDYKT: ❌ NO-GO

**Uzasadnienie:** 5 blockerów wymagają naprawy przed deploy. 0 krytycznych CVE nowych. Infrastruktura wersjonowania i backup zaimplementowana ale zawiera błąd logiczny potwierdzony przez failing test.

---

## Macierz 15 Checkpointów

| # | Checkpoint | Status | Werdykt | Council |
|---|---|---|---|---|
| 1 | Lockfile (`requirements.in` + `requirements-lock.txt`) | ✅ PASS | Oba pliki obecne, poprawne | Opus |
| 2 | VERSION = "5.9.0" | ✅ PASS | Plik VERSION zawiera `5.9.0` | Opus |
| 3 | SYLION_VERSION w app.py = "5.9.0" | ✅ PASS | `app.py:132 SYLION_VERSION = "5.9.0"` | Opus |
| 4 | ENV secrets — no new hardcoded credentials | ⚠️ WARN | Znane `_DEFAULT_API_KEYS` z v5.8.8 (accepted). Diff v5.9.0 — 0 nowych credentials | Sonnet |
| 5 | Migracje PG — N/A; PRAGMA user_version | ✅ PASS | SQLite only. Framework `_DB_TARGET_VERSION=1`, `_run_migrations()`, `_MIGRATIONS={1:...}` zaimplementowane | Opus/GPT-5.4 |
| 6 | `_backup_db_before_migration` zaimplementowany | ❌ BLOCKER | Implementacja obecna, ale M-08 test FAIL — backup failure nie zapobiega tworzeniu 36 tabel przez `executescript` | Opus/GPT-5.4 |
| 7 | Healthcheck `/api/health` + `/api/dashboard` | ✅ PASS | Oba endpointy obecne (linie 288, 693). M-06 optimization w `/api/dashboard` | GPT-5.4 |
| 8 | Testy passed (`pytest tests/ -x`) | ❌ BLOCKER | **6 failed, 30 passed, 4 skipped** — szczegóły poniżej | Gemini |
| 9 | CHANGELOG v5.9.0 | ❌ BLOCKER | Plik `CHANGELOG_v5.9.0.md` nie istnieje | Gemini/Opus |
| 10 | ADR-003+ | ⚠️ WARN | ADR-001, ADR-002 obecne. ADR-003+ (migration framework, retention policy) brak | Gemini/Opus |
| 11 | CVE scan (bandit + deps) | ⚠️ WARN | Bandit: 0 High, 17 Medium (false positives). Deps: ~38 CVE — accepted risk, identyczne z v5.8.8.1 | Sonnet |
| 12 | Rollback Plan `docs/ROLLBACK_PLAN.md` | ❌ MISSING | Plik nie istnieje. Starszy `ROLLBACK.md` (v5.8.8) — nie jest planem dla v5.9.0 | Sonnet/GPT-5.4 |
| 13 | Performance baseline (perf-profiler-council) | ⚠️ WARN | Raport formalny brak (`council/v590/perf/` pusty). Dane w komentarzach kodu (M-07: 2.62s→0.15s, M-06: 3-5×) | GPT-5.4 |
| 14 | Security findings (security-audit-council CONSOLIDATED) | ⚠️ WARN | `council/v590/security/CONSOLIDATED.md` brak. Dostępne raporty v5.8.8.1. Nowe powierzchnie ataku w v5.9.0 nieauditowane | GPT-5.4 |
| 15 | RODO Compliance `docs/RODO_COMPLIANCE.md` | ❌ MISSING | Plik nie istnieje. M-03 implementuje retention (RODO Art.5.1.e) ale brak dokumentu compliance | Gemini |

---

## Top-5 Blockerów

### BLOCKER #1 — M-08: Atomicity failure w backup/migration flow
**Severity:** HIGH  
**Checkpoint:** 6, 8  
**Opis:** `_init_db_unlocked()` wykonuje `conn.executescript(...)` (CREATE TABLE IF NOT EXISTS dla 36+ tabel) PRZED wywołaniem `_run_migrations()`. Gdy backup w `_run_migrations` failuje, wyjątek propaguje się — ale tabele już zostały utworzone. Test `TestM08Backup::test_backup_failure_does_not_corrupt_main_db` potwierdza: "Migration created 36 new tables despite backup failure."

**Konsekwencja produkcyjna:** DB w stanie niespójnym po failed backup (tabele utworzone, user_version=0, migracje nie zastosowane). Recovery undefined.

**Fix wymagany:** Przenieść `executescript` za guard backup check, lub uczynić go częścią transakcji z rollback przy failed backup.

---

### BLOCKER #2 — Test failures: 6 failing tests (M-07, H-04, M-08)
**Severity:** HIGH  
**Checkpoint:** 8  
**Opis:**

| Test | Failure | Root Cause |
|------|---------|------------|
| `TestM08Backup::test_backup_failure_does_not_corrupt_main_db` | AssertionError: 36 nowych tabel | Atomicity bug (patrz Blocker #1) |
| `TestEnsureDependenciesM07::test_ensure_dependencies_single_fork_on_success` | AssertionError | Case mismatch `[SYLION]` vs `[sylion]` + możliwy bug w timeout path |
| `TestEnsureDependenciesM07::test_ensure_dependencies_fallback_per_package_on_failure` | AssertionError | jw. |
| `TestEnsureDependenciesM07::test_ensure_dependencies_timeout_handled` | AssertionError: brak 'timeout' w stdout | M-07 timeout path nie emituje oczekiwanego komunikatu |
| `TestSeedAgentsH04::test_seed_agents_unknown_tag_on_first_iteration_failure` | AttributeError: cursor read-only | Python 3.12 C-type immutability — test wymaga refaktoryzacji mock strategy |
| `TestSeedAgentsH04::test_seed_agents_agent_id_reset_between_iterations` | AttributeError: cursor read-only | jw. |

**Fix wymagany:** Naprawić każdy z 6 testów odpowiednią techniką:
- M-08: naprawa implementacji (Blocker #1)
- M-07: naprawa komunikatów lub expected strings + weryfikacja timeout path
- H-04: zastąpienie monkey-patchingu `conn.cursor` przez `unittest.mock.patch` na poziomie modułu

---

### BLOCKER #3 — Brak CHANGELOG_v5.9.0.md
**Severity:** MEDIUM  
**Checkpoint:** 9  
**Opis:** Plik `CHANGELOG_v5.9.0.md` nie istnieje w repozytorium. Wdrażane zmiany: M-02 (migration framework), M-03 (RODO retention), M-06 (dashboard optimization), M-07 (batch import), M-08 (WAL backup), H-04 (seed_agents fixes), nowe tabele upload_history + code_versions.

**Fix wymagany:** Utworzenie `CHANGELOG_v5.9.0.md` zgodnie z formatem keep-a-changelog 1.1.0 (patrz wzorzec `CHANGELOG_v5.8.8.1.md`).

---

### BLOCKER #4 — Brak docs/ROLLBACK_PLAN.md
**Severity:** MEDIUM  
**Checkpoint:** 12  
**Opis:** Plik `docs/ROLLBACK_PLAN.md` nie istnieje. v5.9.0 wprowadza migrację bazy danych (user_version 0→1) i nowe tabele. Brak procedury rollback stanowi ryzyko operacyjne.

**Fix wymagany:** Dokument `docs/ROLLBACK_PLAN.md` zawierający:
- Kroki przywrócenia DB z backupu (ścieżka `~/sylion/sylion.db.bak.*.sqlite3`)
- Procedura downgrade kodu v5.9.0 → v5.8.8.1
- Handling przypadku gdy backup nie istnieje (failed backup scenario — patrz Blocker #1)

---

### BLOCKER #5 — Brak docs/RODO_COMPLIANCE.md
**Severity:** MEDIUM  
**Checkpoint:** 15  
**Opis:** M-03 implementuje retencję danych (audit_log 365 dni, sessions 30 dni) jako compliance z RODO Art. 5(1)(e). Wdrożenie tej funkcji bez dokumentu compliance jest niekompletne.

**Fix wymagany:** Dokument `docs/RODO_COMPLIANCE.md` z:
- Katalogiem kategorii danych osobowych (users, sessions, audit_log, upload_history)
- Podstawami prawnymi (Art. 6(1)(f) — uzasadniony interes; tool single-user local)
- Tabelą retencji per kategoria (audit_log: 365d, sessions: 30d, users: do żądania usunięcia)
- Procedurą DSAR (local tool — uproszczona)

---

## Warningi (nie-blockery)

### WARNING W-1 — Hardcoded API keys (`_DEFAULT_API_KEYS`)
**Checkpoint:** 4, 11  
Znane, zaakceptowane przez użytkownika w v5.8.8 (HumanGate 2026-04-18). Niezmienione w v5.9.0 diff. Klucze powinny być rotowane jeśli repo zostało udostępnione zewnętrznie. **Accepted risk — local single-user.**

### WARNING W-2 — ADR-003+ brakujące
**Checkpoint:** 10  
Decyzje architektoniczne v5.9.0 (migration framework, retention policy) nieudokumentowane. Nie blokuje deploy ale obniża maintainability. **Rekomendacja: created po deploy.**

### WARNING W-3 — CVE w zależnościach (~38)
**Checkpoint:** 11  
Identyczne z v5.8.8.1. Accepted risk (local, brak ekspozycji publicznej). Rekomendacja: bump `python-multipart` 0.0.20→0.0.26 i `pytest` 8.3.4→9.0.3 w następnym release (safe bumps).

### WARNING W-4 — Brak formalnego performance baseline
**Checkpoint:** 13  
Dane są w komentarzach kodu. Brak `council/v590/perf/` raportu. **Nie blokuje** dla local single-user deployment.

### WARNING W-5 — Security audit CONSOLIDATED v5.9.0 brak
**Checkpoint:** 14  
`council/v590/security/CONSOLIDATED.md` nie istnieje. Nowe powierzchnie ataku (upload_history endpoint, code_versions) nieauditowane. **Accepted dla local single-user, ale zalecany przed scale-out.**

---

## Podsumowanie Werdyktów Rady

| Model | Rola | Werdykt |
|-------|------|---------|
| Opus | Kod-reviewer | ❌ NO-GO (3 blockery) |
| Sonnet | CVE-watcher | ❌ NO-GO (Rollback brak) / ⚠️ na CVE scope |
| GPT-5.4 | Ops-auditor | ❌ NO-GO (test failures + brak raportów) |
| Gemini | QA-sentinel | ❌ NO-GO (testy, CHANGELOG, RODO) |

**CONSENSUS: ❌ NO-GO**

---

## Ścieżka do GO

Minimalna lista napraw (ordered by priority):

1. **[CRITICAL]** Naprawa Blocker #1 — atomicity M-08: przenieść `executescript` za backup guard lub dodać cleanup przy failed backup
2. **[CRITICAL]** Naprawa testów M-07 (string matching + timeout path), H-04 (mock strategy), weryfikacja M-08 po naprawie #1
3. **[HIGH]** Utworzenie `CHANGELOG_v5.9.0.md`
4. **[HIGH]** Utworzenie `docs/ROLLBACK_PLAN.md`
5. **[HIGH]** Utworzenie `docs/RODO_COMPLIANCE.md`

Po naprawie wszystkich 5 blockerów: re-run `pytest tests/` — oczekiwane 0 failed. Re-issue pre-deploy council dla GO/NO-GO.

---

*Council generated: 2026-04-18 | SYLION Pre-Deploy Council v5.9.0*
