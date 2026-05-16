# CHANGELOG v5.8.8.1

Data wydania: 2026-04-18
Pipeline: SYLION TAILOR — local single-user developer deployment
Wszystkie zmiany w formacie [Keep a Changelog 1.1.0](https://keepachangelog.com/pl/1.1.0/).

## [5.8.8.1] — 2026-04-18

### Fixed

- **H-01 (HIGH)** — Usunięto zdublowaną definicję `compute_sha256` w `dashboard/db.py` linia 1034. Pierwsza canonical definicja z linii 34 była nadpisywana przez drugą byte-identyczną — efektu semantycznego nie było, ale code smell eliminated. W miejscu usunięcia zachowany komentarz-anchor (`# NOTE: v5.8.8.1 — DUPLICATE removed`). **Źródło finding:** kod-multi-ai-audyt (Sonnet).

- **H-02 (HIGH)** — Dodany `_db_init_lock = threading.Lock()` w `dashboard/bridge.py` z double-checked locking pattern. Poprzednia implementacja mogła wywołać `init_db()` 2× gdy dwa wątki równolegle trafiały na `_get_conn()` przy starcie (race na `_db_initialized = False`). **Źródło finding:** kod-multi-ai-audyt (Gemini).

- **H-03 (HIGH)** — Bump wersji:
  - `VERSION` file: `5.8.8` → `5.8.8.1`
  - `health_check.py` linia 3: header docstring zaktualizowany do `v5.8.8.1`
  **Źródło finding:** pre-deploy-council (Opus GO/NO-GO checklist checkpoint 13).

### Added

- **docs/adr/ADR-0001-seed-agents-guard.md** — decyzja szachisty rady 4-modelowej (16 subagentów) o utrzymaniu wariantu W1 (defense-in-depth guard) w `_seed_agents`. Warianty W2/W3/W4 odrzucone z uzasadnieniem.
- **docs/adr/ADR-0002-doc-scope-mismatch.md** — świadome udokumentowanie rozbieżności między `SYLION_v588_dokumentacja.pdf` (18 deklarowanych napraw, 16 fikcyjnych dot. nieistniejącego `sylion_deps.py`) a rzeczywistym diff v5.8.8 → v5.8.8.1.
- **CHANGELOG_v5.8.8.1.md** (ten plik) — changelog dla v5.8.8.1.

### Changed

- Nic semantycznie — wszystkie MUST-constraints C-001..C-006 preserved; brak breaking API changes; zachowany shape return `_seed_agents(conn, agents=None) -> int`; zachowane UI API keys edit path; zachowana kolejność priorytetów DB > defaults > env.

### Security

- **ACCEPTED** (user-acknowledged) — hardcoded API keys w `db.py:_DEFAULT_API_KEYS` (OpenAI, Anthropic, Google, Perplexity) pozostają bez zmian zgodnie z jawną decyzją operatora: *"to jest pipeline, moja wersja wiecznie pomiń wzgledy bezpieczenstwa"*. Kontekst: loopback-only, single-user dev pipeline, zero network exposure.
- **ACCEPTED** — brak rate-limiting na `/api/auth/login` (loopback only).
- **ACCEPTED** — setup token bez TTL (local dev).
- **ACCEPTED** — SQLite bez szyfrowania (local dev).
- **PLANNED v5.8.9** — przed network exposure: obowiązkowa rotacja kluczy + `git filter-repo` + enable rate-limit + CSRF tokens + SQLCipher.

### Verified

- 15/15 regression + concurrency tests passed (`tests/test_regressions_v588.py`, `tests/test_concurrency_v588.py`)
- 73/73 E2E API tests passed (po QA patchu `test_cost_alert_acknowledge` empty-array guard — flaga z pre-deploy QA Gemini)
- Zero CVE critical/high w `dashboard/` (pre-deploy CVE-watcher GPT); 30 CVE w litellm ACCEPTED (local-only, nie eksponowane)
- `ast.parse` syntax check OK na wszystkich zmodyfikowanych plikach

### Known Issues / Roadmap v5.8.9

- **M-01:** Migracja `_seed_agents` na Pydantic BaseModel (W2 variant) — po dodaniu `pydantic` do `requirements.txt`
- **M-02:** `PRAGMA user_version`-based migration framework (obecnie diff kolumn)
- **M-03:** `prune_audit_log()` i `prune_sessions()` — obecnie tylko `event_stream` ma 7-dniowe TTL
- **M-04:** `poetry.lock` / `requirements-lock.txt` w deploy payload
- **M-05:** `sylion_deps.py` jeśli zdecydujemy się wdrożyć architekturę z PDF
- **M-06:** `GET /api/dashboard` — konsolidacja 11× `SELECT COUNT(*)` → 3-4× `GROUP BY`
- **M-07:** Batch subprocess dep-check w `_ensure_dependencies` (12 forks → 1 fork, oszczędność ~2.2s startup)
- **M-08:** Refactor `app.py` (6437 linii, mieszane async/sync, blokujące `conn.execute` w async handlers)

### Rada i metryka walidacji

- **17 skilli zaangażowanych** (16 aktywnych + 1 N/A_JUSTIFIED dla pixel-provisioning)
- **75+ subagentów** równolegle walidujących kod, dokumenty, security, compliance, performance, testy, deployment, migrację
- **4 warianty × 4 scenariusze** szachisty na `_seed_agents` fix — zero wariantów z naruszeniem Constraint List
- **0 pętli błędów** — debug-loop-breaker aktywny, Constraint List w `SKILL_MANIFEST.md`, per-bug counter

### Pełny raport rad

`council/v588_1/FINDINGS_MATRIX.md` — konsolidacja wszystkich znalezisk, verdict per skill, mechanizmy anti-loop.

### Integrations

- **pr-reviewer-council:** REQUEST_CHANGES (Opus), po integracji H-01..H-03 = APPROVE
- **deployment-council:** GO-WITH-WARNINGS (install.bat OK, rollback 3-warstwowy OK, SQLite backup = M-08 w v5.8.9)
- **data-migration-council:** init_db idempotent OK, backup przed `_migrate_columns` zaplanowany w v5.8.9
- **pre-deploy-council:** APPROVE po naprawie VERSION mismatch (H-03) — wszystkie 4 role dają GO dla local dev deploy
