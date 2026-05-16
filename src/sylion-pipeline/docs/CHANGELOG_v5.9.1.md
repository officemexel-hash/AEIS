# Changelog v5.9.1 — 2026-04-19

All notable changes follow [Keep a Changelog v1.1.0](https://keepachangelog.com/en/1.1.0/).

## [5.9.1] — 2026-04-19 — Re-audit Release

### Added

- `POST /api/auth/logout-all` endpoint for invalidating all sessions (MEDIUM-001)
- Regression tests: `test_v591_regressions.py` covering all MUST-FIX findings
- Periodic daily backup in app lifespan (`startup` event handler)
- pidfile + port-check guards in `start.py` to prevent double-start
- Extended `/api/health` with `db_ok`, `backup_age_hours`, `disk_free_gb` fields
- `LICENSE.md` (MIT), `NOTICE`, `THIRD_PARTY_LICENSES.md`
- `PRIVACY_POLICY_PL.md`, `PRIVACY_POLICY_DE.md`
- `ONBOARDING_CHECKLIST_DE.md` (German translation)
- `.gitignore` (excludes `__pycache__`, `*.pyc`, `app.db`, `SETUP_TOKEN.txt`)
- 12 new ADRs (ADR-0009 through ADR-0019 + ADR-0025 final verification loop) — see `docs/adr/`
- `PIXEL_9_FAMILY` whitelist (Pixel 9, 9 Pro, 9 Pro XL, 9 Pro Fold, 9a) and `DeviceHarness.validate_pixel_model()` reading `ro.product.model` via `adb shell getprop` — part of PIX-1 enforcement
- `shell_getprop` added to `ALLOWED_ADB_COMMANDS` allowlist, restricted to `ro.product.*` / `ro.build.*` namespaces

### Changed

- Default fact_checker model: `claude-sonnet-4-5-20250929` → `anthropic/claude-sonnet-4-6`
  (env override: `FACT_CHECKER_MODEL_ID`)
- PRAGMA `journal_mode=WAL` and `foreign_keys=ON`: cached once per process (was per-connection)
- DB seed device: `"pixel8"` → `"pixel9"` with migration for upgraded databases
- Python minimum version harmonized: `>=3.11` (3.12 tested) across all documentation
- Cookie `Secure` flag default: `True` in production (was `False`); override via `SESSION_COOKIE_SECURE=0`
- CSRF protection: `SameSite=Strict` confirmed + `X-CSRF-Token` added to upload endpoint
- `rollback.sh` rewritten using SQLite `.backup` API (WAL-safe, atomic, 6 bugs fixed)
- Backup filename version label: dynamic `${CURRENT_VERSION}` (was hardcoded `v5.9.0`)
- Route order: `/api/agents/prompts` and `/api/agents/pipeline-graph` moved before `{agent_id}` catch-all

### Fixed

- **SEC-PII-1** — Removed personal email `robert.skorupka@icloud.com` from all docs (HIGH)
- **REG-1** — Replaced `assert` with `ValueError` in Ollama whitelist (`app.py:5787–5791, 5910–5914`) — guard was bypassed by `python -O` (HIGH)
- **BUG-001** — `get_dashboard` now issues 5 COUNT queries (was 7); regression test passes (HIGH)
- **MEDIUM-001** — Password change now invalidates all existing sessions via `DELETE FROM sessions WHERE user_id=?` (HIGH)
- **C-01** — TOCTOU race in `/api/auth/setup` fixed: `threading.Lock` + `BEGIN IMMEDIATE` (HIGH)
- **PIX-1** — Pixel 9 not detected: replaced hardcoded `"pixel8"` seed, enforced `EXPECTED_MODEL`, added `"unauthorized"` ADB state handling (HIGH — primary historical issue)
- **ISSUE-RT-01** — Double `init_db()` + double `setup_token` on startup eliminated (MEDIUM)
- **FIND-1** — `fact_checker` default model ID caused runtime `InvalidRequestError` on every call (CRITICAL)
- **F-01** — `install.sh` / `install.bat` step 4 `app.db.init_db` module path corrected to `PYTHONPATH=dashboard python -c "import db; db.init_db()"` (CRITICAL)
- **F-02** — Python version documentation inconsistency (`3.10` / `3.11` / `3.12`) unified to `>=3.11` (CRITICAL doc)
- **CRIT-01** — 2× PRAGMA overhead per connection (~91 ms/request) eliminated by per-process caching (CRITICAL perf)
- **CVE-1..4** — litellm, starlette, fastapi, python-multipart, pypdf upgraded to patched versions (all HIGH/CRITICAL)
- **C-02** — Hash upgrade race (10 concurrent logins → 10 Argon2 calls) fixed with compare-and-swap (MEDIUM)
- **C-03** — `audit_log` `conn.commit()` in-transaction corrected (MEDIUM)
- **EP-1, EP-2** — Route shadowing: `/api/agents/prompts` and `/api/agents/pipeline-graph` moved before `{agent_id}` catch-all (MEDIUM)
- **EP-3** — `/api/health/deep` hang fixed with async wrapper + timeout guard (MEDIUM)
- **EP-4** — `DELETE /api/models/{id}` now returns 404 for missing ID (was silent 200) (MEDIUM)
- **FIX-02-SHAPE** — `/api/dashboard` response now includes top-level `costs`, `guards`, `security` keys (MEDIUM)
- **RT-ERR-1** — `traceback.format_exc()` removed from `/api/devices/provision` response; logged locally only (MEDIUM)
- **Phantom v3** — `NameError: log.warning` vs `logger.warning` in `file_verification.py:336,344` path traversal path (LOW)
- **asyncio deprecation** — `asyncio.get_event_loop()` replaced with `asyncio.get_running_loop()` (LOW)
- **Ruff cleanup** — 18 unused imports (`F401`) + 14 unused vars (`F841`) + 1 duplicate import removed (LOW)
- **Dead doc links** — 8 broken links in FAQ and CHANGELOG fixed (LOW)
- **ADR numbering** — 3-digit → 4-digit (`ADR-001` → `ADR-0001`) in all filenames and internal references (LOW)
- **rollback.sh** — 6 bugs fixed: WAL checkpoint, atomic copy, exclusive lock, hardcoded version, integrity check, `set -e` (HIGH ops)

### Deprecated

- (none)

### Removed

- `assert`-based input validation in Ollama model whitelist checks (replaced with explicit `ValueError`)

### Security

- CVE upgrades: litellm ≥1.83.0 (CVE-2026-35030 CRITICAL 9.4), starlette ≥0.49.1 (CVE-2025-62727 HIGH), python-multipart ≥0.0.26 (CVE-2026-24486 HIGH), pypdf ≥6.10.2 (22 GHSA advisories)
- No hardcoded PII in documentation (SEC-PII-1 resolved)
- Cookie `Secure` default `True` — prevents session cookie plaintext transmission on TLS deployments
- `X-CSRF-Token` header required on multipart upload endpoint (`/api/baselines/upload`)
- Setup endpoint TOCTOU race eliminated (C-01)

---

## [5.9.1] — 2026-04-19 — Final verification loop (ADR-0025)

### Verified (post-cluster re-audit)

Po 22 klastrach fixowych (A–V, ~200+ subagentów) uruchomiono ręczną pętlę weryfikacyjną, która ujawniła desynchronizację raportów subagentów vs realnego stanu plików:

- **install.sh banner** `v5.9.0` → `v5.9.1` (2 miejsca, linia 3 i 196)
- **`DEVICE_PIXEL_SERIAL` setting label** `"Pixel 8 serial (ADB)"` → `"Pixel 9 serial (ADB)"` (db.py:1185)
- **MANIFEST.json** `"version": "5.9.0"` → `"5.9.1"`, `baseline_from: "5.9.0"`, `release_type: "minor-patch"`
- **PIXEL_9_FAMILY tuple** + **validate_pixel_model()** metoda w DeviceHarness — realizuje wcześniej tylko-enumowaną walidację (WRONG_MODEL, UNKNOWN_MODEL state handling)
- **shell_getprop allowlist entry** + mapowanie w `_build_adb_command` ograniczone do `ro.product.*`/`ro.build.*`
- **release_root/sylion-pipeline/ resync** — był stary snapshot v5.9.0, teraz `cp -a` z głównego drzewa v5.9.1 (211 → 311 plików bez `__pycache__`, `*.pyc`, `*.db*`, `SETUP_TOKEN.txt`)

### Runtime UAT (post-verification)

- pytest: **150 passed, 4 skipped, 0 failed** (7.40s)
- uvicorn start OK (port 8821, HOME=/tmp/uat_runtime2)
- `/api/health` → 200, `version:5.9.1`, `db_ok:true`
- `/api/metrics` → 200 (Prometheus format)
- `/api/observability/costs`, `/api/auth/me/export`, `/api/settings/api-keys` → 401 (auth required, nie 404)
- `POST /api/auth/logout-all` → 405 na GET (route poprawnie zarejestrowane jako POST-only)
- `DELETE /api/auth/me/data` → 422 (wymaga body z password confirmation)

---

## Related

- [ADR-0009 through ADR-0019](./adr/) + [ADR-0025](./adr/ADR-0025-v591-final-verification-loop.md)
- [REAUDIT_v590_REPORT.md](./REAUDIT_v590_REPORT.md)
- [FINDINGS_MATRIX_v591.md](./FINDINGS_MATRIX_v591.md)
