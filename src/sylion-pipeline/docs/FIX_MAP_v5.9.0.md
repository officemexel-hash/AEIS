# SYLION v5.9.0 — Mapa Napraw (FAZA 4)

## CRITICAL (muszą być naprawione przed release)

| ID | Źródło | Finding | Severity | Plik |
|----|--------|---------|----------|------|
| FIX-01 | security | Brak rate limiting /api/auth/login (brute-force) | CVSS 9.8 | dashboard/app.py |
| FIX-02 | pr-review #1 | M-06 COALESCE(status,'draft') regression — NULL-status rows liczone jako 'draft' | HIGH | dashboard/app.py |
| FIX-03 | pr-review #2 | _backup_db_before_migration crashes na read-only FS | HIGH | dashboard/db.py |
| FIX-04 | pr-review #3 | BEGIN EXCLUSIVE blokuje readers w WAL → zmiana na BEGIN IMMEDIATE | MEDIUM | dashboard/db.py |
| FIX-05 | pr-review #4 | PRAGMA f-string user_version — isinstance guard + :d format | MEDIUM | dashboard/db.py |
| FIX-06 | predeploy #1 | M-08 atomicity: executescript PRZED backup — tabele tworzone przed backupem | HIGH | dashboard/db.py |
| FIX-07 | security HIGH | Command injection potencjał w _batch_imports_ok | CVSS 8.4 | dashboard/start.py |
| FIX-08 | security HIGH | DoS brak max-length hasła w Argon2 | CVSS 7.5 | dashboard/app.py (lub auth) |
| FIX-09 | security HIGH | SHA-256 fallback dla haseł (usunąć/zastąpić) | CVSS 8.1 | dashboard/app.py |
| FIX-10 | security HIGH | SQL f-string WHERE w ollama endpoints | CVSS 7.5 | dashboard/app.py |
| FIX-11 | perf | Brak indeksu audit_log.ts | MEDIUM | dashboard/db.py |

## HIGH (do naprawy jeśli bez breaking changes)

| ID | Źródło | Finding | Plik |
|----|--------|---------|------|
| FIX-12 | migration LOW | _seed_admin re-runs przy users=0 — cosmetic token regen | dashboard/db.py |
| FIX-13 | audit HIGH | orchestrator.py god object (3300 linii) | ODŁÓŻ v6.0 (breaking refactor) |
| FIX-14 | audit CRITICAL | BudgetGuard + FileVerificationLayer bez testów | ODŁÓŻ (non-blocking) |

## Constraint Check (C-001..C-104)

- FIX-02 naprawa M-06 NIE zmienia JSON shape (C-308 OK)
- FIX-03/04/05/06 wszystkie w init_db — C-003 thread-safe zachowane
- FIX-07 zachowuje performance M-07 (C-307 OK)
- FIX-08/09 dotyczą auth — uważać na C-101 (15 testów muszą dalej przechodzić)
- FIX-10 w ollama — NIE dotyka _DEFAULT_API_KEYS (C-006 OK)

## Decyzja (autopilot)

FIX-01..FIX-11 → AUTO-FIX w FAZIE 4 (MEDIUM/HIGH po stronie agenta)
FIX-13/14 → odłożone do v6.0 (breaking refactor wymaga HumanGate)
