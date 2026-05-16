# Changelog

All notable changes to SYLION Pipeline are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.2.0] — 2026-04-19 — "Breakthrough — 18 Skills Audit"

Release fixujący 17 bugów zidentyfikowanych w `SYLION-v600-FIX-PLAN.pdf`. Wszystkie zmiany kompatybilne wstecz (z jawnymi deprecation windows dla dwóch API).

### Added
- **B-003** Alias `GET /api/auth/setup-status` obok `/api/auth/setup_status` (snake_case→kebab-case migration).
- **B-007 / HG-001 / HG-002** Canonical dash-case dla całego namespace `/api/human-gate/*` (8 endpointów: `queue`, `approve`, `reject`, `defer-iso`, `escalate-user`, `require-manual`, `consequence-preview`, `rollback-preview`). Legacy underscore zachowany jako alias z RFC 8594 `Deprecation`, `Sunset: Wed, 31 Dec 2026 23:59:59 GMT`, `Link rel="successor-version"` i `Warning: 299` headers.
- **B-004** Plik `VERSION` w repo jako pierwsze źródło prawdy dla wersji aplikacji.
- **CONN-001** Automatyczny DNS fallback `ollama → localhost` w `ollama_client.py` przy `NXDOMAIN`, opt-out przez `SYLION_OLLAMA_DNS_FALLBACK=0`.
- **B-008** Metrics access control: `_enforce_metrics_access()` chroni `/api/metrics` i `/api/metrics/prom`. Default allowlist `127.0.0.1/::1/localhost`; remote wymaga `SYLION_METRICS_BEARER` lub session role (`owner,operator`); dev escape `SYLION_METRICS_OPEN=1`.
- **B-009** Pre-import set `LITELLM_LOCAL_MODEL_COST_MAP`, `LITELLM_DO_NOT_TRACK`, `LITELLM_TELEMETRY=False`, `NO_DOCS=True`, `LITELLM_LOG=ERROR` + post-import module patch (`litellm.telemetry=False`, `litellm.suppress_debug_info=True`).
- Nowa metryka `sylion_human_gate_legacy_calls_total` (counter) dla monitoringu ruchu na deprecated underscore namespace.
- `ULTRA_TEST_REPORT_v2.md` — raport PASS/FAIL dla wszystkich 17 bugów z odnośnikami do evidence.

### Changed
- **B-006** `DB_PATH` single source of truth: jedna ścieżka do bazy (`DASHBOARD_DB_PATH`) zamiast trzech rozbieżnych miejsc (`init_db`, `reset_db`, `app_ctx`). Opt-in legacy behaviour przez `SYLION_USE_LEGACY_DB_PATH=1`.
- **B-002** Build guard: instalacja teraz odmawia uruchomienia, gdy wykryje pre-seeded `*.db`/`*.sqlite` w źródle. Migracja schema uruchamiana w `init_db` idempotentnie.
- **B-001** JWT secret auto-generowany przez `secrets.token_urlsafe(64)` przy pierwszym starcie, zapisywany do `.env.generated` z chmod 600. Brak hardcoded fallback secret.
- **OP-001** Graceful shutdown SIGTERM: anuluje active tasks, czeka ≤10s, potem SIGKILL. Uvicorn `--timeout-graceful-shutdown 10`.
- **PIPELINE-012** `asyncio.Task.cancel()` propaguje `CancelledError` do `httpx.AsyncClient`, realnie przerywa HTTP w locie (zmierzone <100 ms).
- **STAGE1-001** Stage1 ekstrakcji teraz wymusza strict JSON (pydantic model + `response_format={"type":"json_object"}`), 6/6 regresji na edge-case payloadach PASS.
- **B-005** UI key management: przeniesione z POST `/api/keys/update` na PUT `/api/keys/{key_name}` (RESTful idempotent).
- **UI-001** Centralized `apiFetch()` helper: jednolity error handling, retry/backoff, toast na błąd.
- **UI-002** Chart.js guard: skrypt ładowany idempotentnie, nie rebinduje canvas po remount.
- **PIPELINE-001** Długie joby pipeline'u zwracają `202 Accepted` z `Location` header + `job_id`, zamiast blokować request thread.
- **DASH-RUNID-003** Zombie run cleanup: joby >30 min w stanie `RUNNING` bez heartbeat'u automatycznie przenoszone do `FAILED`.
- **PIPELINE-011** `BookGuardian._snapshot()` memoized przez klucz `(path, mtime_ns, size)`. Zmierzono 676× speedup na pliku 5 MB (1000 rehash: 5104 ms → 1000 memo hit: 7.5 ms). Opt-out `SYLION_BOOKGUARDIAN_NO_MEMOIZE=1`.
- **B-004** Version resolver: priority `env SYLION_VERSION > VERSION file > MANIFEST.json > fallback`. Wszystkie endpointy (`/api/version`, `/api/health`, OpenAPI `info.version`) reportują ten sam string.
- `MANIFEST.json` bump `6.0.0 → 6.2.0`.

### Fixed
- `init_db()` nie seeduje już domyślnych API keys — to naruszało zasadę "no secrets in code" (B-001/B-006 spillover). Operatorzy muszą jawnie dodać klucze przez `PUT /api/keys/{name}` lub `.env`.
- Duplicate Operation ID warnings w OpenAPI dla human-gate pairs — oznaczone explicit `operation_id` na dashe i suffix `_deprecated` na underscore.
- Race condition w `ollama_client.OllamaClient.__init__` przy DNS NXDOMAIN — wcześniej rzucało `NameError` przed fallback.

### Deprecated
- `/api/human_gate/*` namespace (underscore) — planowane usunięcie w SYLION v7.0.0 (sunset 2026-12-31).
- `/api/auth/setup_status` (snake_case) — pozostaje jako alias, canonical jest kebab-case.

### Security
- **B-001** Eliminacja hardcoded JWT secret fallback.
- **B-008** Default-deny dla `/api/metrics` z remote IP bez credentialsów (redukuje atak powierzchnię z internetu).
- **B-009** Wyłączenie litellm telemetry pre-import (wycieki do zewnętrznych endpointów niemożliwe bez jawnego opt-in).

### Compliance
- GoBD retention flag zachowany przy wszystkich zmianach DB path (B-002, B-006).
- Żadnych nowych PII w logach metrycznych (B-008 localhost-only bez bearer = zero PII flow).

### Migration notes
- **Breaking dla fresh installs**: init_db nie seeduje default API keys. Upgrade-in-place: bez zmian, stare klucze DB zachowane.
- **Soft-breaking dla klientów human-gate**: API nadal działa pod `/api/human_gate/*` (z deprecation headers). Migracja do `/api/human-gate/*` zalecana przed 2026-12-31.
- **Wymagany reset env**: `unset SYLION_VERSION` jeśli wcześniej było przypięte — VERSION file ma teraz priorytet.

### Known issues (pre-existing, out of v6.2.0 scope)
- `test_regressions_v588::test_bug2_sync_api_keys_to_env_applies_db_values` — FAIL (test zakładał że init_db seeduje defaults; to zachowanie celowo usunięte w B-001).
- `test_retention_cascade.py` (14 testów), `test_secure_cookies.py` (12 testów), `test_v591_regressions.py` (2 testy) — FAIL w baseline v6.0.0, niewprowadzane przez v6.2.0.
- 3 moduły `test_migrations_v591`, `test_rate_limiter_proxy`, `test_workspace_slots_security` — ImportError na brakujące moduły (`migration_patches`, `rate_limiter_patch`, `upload_quota`) w baseline.

## [6.0.0] — 2026-04-18 — baseline

Wersja bazowa przed sprintem fix-plan. Zawiera 17 zidentyfikowanych bugów obsłużonych w 6.2.0 (żadna wersja 6.1.x nie była publikowana — 6.1 zarezerwowane dla późniejszych feature'ów).

[6.2.0]: https://internal/sylion/compare/v6.0.0...v6.2.0
[6.0.0]: https://internal/sylion/releases/v6.0.0
