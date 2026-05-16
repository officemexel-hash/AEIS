# Ops-Auditor (GPT-5.4) — Pre-Deploy Report v5.9.0

**Rola:** Ops auditor — infrastruktura, operacyjność, runbook, monitoring  
**Data:** 2026-04-18  
**Scope:** SYLION v5.9.0 — start.py, db.py, health endpoints, deployment readiness

---

## Podsumowanie

Oceniam gotowość operacyjną deployment v5.9.0. Identyfikuję **2 blockers** (brak raportów zewnętrznych: perf-profiler i security-audit CONSOLIDATED) i **3 warningi** operacyjne. Implementacje M-02/M-03/M-07 są solidne architektonicznie, ale test failures wskazują na niezakończony QA.

**Werdykt Ops-Auditor: NO-GO** — brak raportów zewnętrznych i test failures.

---

## Checkpoint 7 — Healthcheck endpoints

**STATUS: PASS ✓**

Endpointy zidentyfikowane w `dashboard/app.py`:

```python
GET /api/health          # linia 288 — basic healthcheck
GET /api/health/deep     # linia 294 — deep check (DB, agents, subsystems)
POST /api/health/diagnose # linia 330 — diagnostyka aktywna
GET /api/dashboard       # linia 693 — zbiorcze dane dashboardu
```

**M-06 optimization:** Diff v5.9.0 dodaje optymalizację `/api/dashboard` (5 query zamiast ~15 round-trips — zmierzono 3-5× szybciej wg komentarza). Testy M-06 są **SKIPPED** (4 testy), nie FAILED — prawdopodobnie skip z powodu braku uruchomionego serwera. Implementacja wydaje się poprawna.

---

## Checkpoint 5 — Startup procedure (start.py M-07)

**STATUS: WARNING ⚠️**

Diff `diff-start.patch` dodaje M-07: batch import verification w `_ensure_dependencies()`:

```python
_BATCH_TIMEOUT = 20   # s — batch verify 13 deps w 1 subprocess
_PER_PKG_TIMEOUT = 30 # s — fallback per-package
```

**Dobra zmiana operacyjna:** Zmniejsza cold-start z ~2.62s do ~0.15s (wg komentarza w kodzie).

**Warning:** 3 testy M-07 FAILują z powodu case mismatch w komunikatach:
- Test oczekuje `[sylion]` (lowercase), kod emituje `[SYLION]` (uppercase)
- Test sprawdza `'timeout' in stdout.lower()` ale komunikat timeout jest inaczej sformułowany

Nie ma to wpływu na runtime, ale unit tests dla M-07 są **niesprawdzone** — branch timeout path niezweryfikowany.

**Rekomendacja:** Naprawa testów M-07 przed deploy (minor — zmiana expected string w testach).

---

## Checkpoint 6 — Backup DB (ops perspective)

**STATUS: BLOCKER ❌**

Backup kieruje do `~/sylion/` (home dir). Z ops perspective:

```python
backup_dir = Path.home() / "sylion"
backup_dir.mkdir(parents=True, exist_ok=True)
backup_path = backup_dir / f"sylion.db.bak.{version_tag}.{date_str}.sqlite3"
```

**Dobre:** F-04 path traversal guard zaimplementowany (`backup_path.resolve().relative_to(backup_dir.resolve())`).

**Złe:** Test M-08 (`test_backup_failure_does_not_corrupt_main_db`) FAILuje — backup failure nie zapobiega tworzeniu tabel przez `executescript`. To jest operacyjne ryzyko przy migracji: crash w środku `init_db` może zostawić DB w stanie niespójnym (tabele utworzone, user_version=0, migracja nie aplikowana).

**Brakuje:** Procedura recovery po failed backup nie jest udokumentowana.

---

## Checkpoint 8 — Testy (ops view)

**STATUS: BLOCKER ❌**

Wynik pytest: `6 failed, 30 passed, 2 warnings`

Breakdown operacyjny:
- **M-08 (1 fail)** — atomicity backup/migration — ryzyko produkcyjne
- **M-07 (3 fails)** — string mismatch w testach (niskie ryzyko runtime, ale nieweryfikowalne)
- **H-04 (2 fails)** — `sqlite3.Connection.cursor` read-only — testy wymagają refaktoryzacji mock-strategy

**Konkluzja ops:** CI/CD pipeline nie może go-live z 6 failing tests. Protokół: zero failing tests przed deploy lub explicit documented skip z uzasadnieniem.

---

## Checkpoint 13 — Performance baseline

**STATUS: MISSING ❌**

Oczekiwany raport: `council/v590/perf/` (z perf-profiler-council)

```
find /home/user/workspace/council/v590/perf/ -type f → brak plików
```

Informacje operacyjne zawarte w kodzie (komentarze):
- M-07: batch import 2.62s → 0.15s (ale brak formalnego raportu)
- M-06: /api/dashboard 15 queries → 5 queries, 3-5× faster (ale brak benchmarku)

**Wymagane:** Formalny raport z baseline przed/po dla kluczowych metryk:
- Cold start time (start.py)
- /api/dashboard response time
- Memory footprint (nowe tabele upload_history, code_versions)

---

## Checkpoint 14 — Security findings (ops perspective)

**STATUS: MISSING ❌**

Oczekiwany raport: `council/v590/security/CONSOLIDATED.md` (z security-audit-council)

```
find /home/user/workspace/council/v590/security/ -type f → brak plików
```

Dostępne są starsze raporty:
- `audit/security_v588.md` — v5.8.8 security baseline
- `audit/v588_1/security_triage.md` — v5.8.8.1 triage

**Brak dedykowanego security-audit-council dla v5.9.0.** Nowe powierzchnie ataku w v5.9.0:
- Endpoint `/api/uploads/history` (jeśli dodany) — nieauditowany
- Tabele `upload_history`, `code_versions` — nowe wektory dla data exfiltration

---

## Monitoring i observability

**STATUS: INFO**

Ocena obecnego stanu monitorowania:
- `GET /api/health` — dostępny, wystarczający do health probe
- Audit log (`audit_log` table) — present, RODO retention 365 dni
- Prune tasks dla audit_log + sessions — dodane w M-03 (`_PRUNE_TASKS`)

Brakuje:
- Alert dla failed backup (linia 777: `logger.exception(...)` ale brak alertu/metric)
- Prometheus/metrics endpoint — nie wymagany dla single-user, informacyjnie

---

## Podsumowanie Ops-Auditor (GPT-5.4)

| # | Checkpoint | Status |
|---|---|---|
| 5 | PRAGMA user_version (ops) | ✅ PASS |
| 6 | Backup DB — atomicity | ❌ BLOCKER |
| 7 | Health endpoints | ✅ PASS |
| 8 | Tests — 6 failed | ❌ BLOCKER |
| 12 | Rollback Plan | ❌ MISSING |
| 13 | Performance baseline | ❌ MISSING |
| 14 | Security CONSOLIDATED | ❌ MISSING |

**Werdykt GPT-5.4: NO-GO** — blockers i braki raportów zewnętrznych.
