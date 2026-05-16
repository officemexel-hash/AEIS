# SYLION v5.9.2 — Mega-Audit Patch (Release Notes)

| Pole             | Wartość                                                     |
|------------------|-------------------------------------------------------------|
| **Wersja**       | 5.9.2                                                       |
| **Nazwa kodowa** | *Mega-Audit Patch*                                          |
| **Typ wydania**  | PATCH (SemVer 5.9.1 → 5.9.2)                               |
| **Data wydania** | 2026-04-19                                                  |
| **Poprzednia wersja** | v5.9.1 (*Hardening Patch*, 2026-04-19)                |
| **Charakter**    | Bugfix + security + infrastruktura. **Brak breaking changes.** |
| **Źródło**       | FIX_MAP_v5.9.2.md · Mega-audyt 49 subagentów · Fala 3      |
| **Mapa napraw**  | [FIX_MAP_v5.9.2.md](./FIX_MAP_v5.9.2.md)                   |

Format oparty na [Keep a Changelog v1.1.0](https://keepachangelog.com/pl/1.1.0/).

---

## TL;DR

v5.9.2 jest obowiązkową paczką naprawczą zamykającą **wszystkie 7 blokerów P0** oraz **10 znalezisk P1** wykrytych w trakcie mega-audytu 49 subagentów (4 rundy × 4 modele AI). Wersja nie wprowadza nowych API ani breaking changes — jest bezpiecznym upgrade'em z v5.9.1 dla każdej instalacji produkcyjnej.

---

## Bezpieczeństwo

> Sekcja dotyczy wyłącznie znalezisk sklasyfikowanych jako SEC-* lub CVE.
> Pełna tabela findings: `reports/council_v590/security/CONSOLIDATED.md`.

### P0-003 (CRITICAL) — CSRF: brakująca ochrona na 1 endpoincie z 71

**Ref:** mega_audit/csrf_71_endpoints/ · ADR-0026

**Problem:** Audyt CSRF przeskanował 71 endpointów i zidentyfikował jeden, który nie miał tokenu CSRF. W scenariuszu ataków cross-site request forgery złośliwa strona mogła wysyłać autoryzowane żądania w imieniu zalogowanego użytkownika.

**Naprawa:** Endpoint identyfikowany w `app.py` objęty podwójnym mechanizmem: `SameSite=Strict` cookie oraz nagłówek `X-CSRF-Token`. Testy regresyjne: `test_csrf_all_71_endpoints_protected`.

### SEC-001 (CRITICAL, CVSS 9.8) — Brak rate limiting na `/api/auth/login`

**Ref:** reports/council_v590/security/CONSOLIDATED.md · ADR-0027

**Problem:** Endpoint logowania nie miał żadnego ograniczenia liczby prób — nieograniczony brute-force bez blokady IP/username.

**Naprawa:** Progressive lockout per IP i per username: max 10 prób / 5 min, blokada eskalowana wykładniczo (5 min → 30 min → 4 h). Zmienna środowiskowa `SYLION_LOGIN_MAX_ATTEMPTS` (domyślnie: 10). Integracja z Caddy `X-Forwarded-For` (patrz FIX-002 z v5.9.1).

### SEC-002 (CRITICAL, CVSS 8.1) — SHA-256 jako fallback hashowania haseł

**Ref:** reports/council_v590/security/CONSOLIDATED.md

**Problem:** `_init_hash_backend` przy braku `argon2-cffi` cicho przełączał się na SHA-256 (v5.9.1 naprawiło domyślne zachowanie, ale martwa gałąź pozostawała w kilku ścieżkach kodowych).

**Naprawa:** Martwe gałęzie SHA-256 usunięte. Hard-fail bez argon2-cffi już w v5.9.1, v5.9.2 czyści pozostałości.

### SEC-004 (CRITICAL, CVSS 9.1) — SQL injection przez `PRAGMA user_version = {version}`

**Ref:** reports/council_v590/security/CONSOLIDATED.md · `db.py:817`

**Problem:** Interpolacja f-string wartości wersji bezpośrednio do zapytania SQL.

**Naprawa:** Explicit cast `int(version)` + `assert 0 <= version <= 999` przed interpolacją. Każda inna wartość podnosi `ValueError`.

### SEC-005 (CRITICAL, CVSS 8.4) — Command injection w `_batch_imports_ok`

**Ref:** reports/council_v590/security/CONSOLIDATED.md · `start.py:93`

**Problem:** Nazwy importów przyjmowane bez walidacji do skryptu wykonywanego jako subprocess.

**Naprawa:** Regex allowlista `^[a-zA-Z_][a-zA-Z0-9_.]*$` weryfikowana przed budowaniem komendy. Każda nazwa poza listą odrzucana z `ImportError`.

### SEC-006 (HIGH, CVSS 7.5) — SQL injection w ollama shadow/insights

**Ref:** reports/council_v590/security/CONSOLIDATED.md · `app.py:5697,5814`

**Problem:** `where_sql` budowane przez f-string bez sanityzacji wartości kolumn.

**Naprawa:** Jawna allowlista kolumn (`OLLAMA_ALLOWED_COLUMNS`); zawsze parametryzowane `col = ?` + tuple params. Testy: `test_ollama_no_sqli`.

### P2-020 (MEDIUM) — CVE w bibliotece `aiohttp` (transitive)

**Ref:** mega_audit/aiohttp_transitive_cve/ · lockfile patch

**Problem:** Wersja `aiohttp` poniżej patcha bezpieczeństwa w transitive dependency.

**Naprawa:** Upgrade do `aiohttp>=3.10.11` w `requirements-lock.txt`. Hash-pinned.

---

## Naprawy krytyczne (P0)

> Wszystkie 7 blokerów P0 musiało być zamkniętych przed wydaniem v5.9.2.

### P0-001 (CRITICAL) — DB init: baza pusta po `--seed`

**Ref:** mega_audit/db_init_bug/ · ADR-0028

**Problem:** `init_db()` wywoływana z flagą `--seed` zwracała 0 bajtów w bazie — seed nie był aplikowany. Pierwsza instalacja na czystym systemie kończyła się pustą bazą bez agentów i bez admina.

**Naprawa:** Race condition w kolejności `CREATE TABLE` vs `INSERT` naprawiona przez explicit transaction ordering. `_seed_agents()` przeniesiony do oddzielnego bloku gwarantującego wykonanie po zakończeniu DDL. Idempotencja: ponowne uruchomienie nie duplikuje seedu.

**Testy:** `test_db_init_seed_not_empty`, `test_db_init_idempotent`.

### P0-002 (CRITICAL) — Auth: HTTP 500 zamiast 401

**Ref:** mega_audit/auth_500_bug/ · `app.py:370`

**Problem:** Endpointy autentykacji rzucały nieobsługiwany wyjątek skutkujący HTTP 500 zamiast poprawnego 401 Unauthorized przy błędnych danych uwierzytelniających.

**Naprawa:** Dodany `try/except` opakowujący logikę auth z jawnym `raise HTTPException(401)` dla każdej ścieżki błędu. Dodatkowe: błędy logowania teraz zapisywane w `audit_log` (SEC-016 z raportu bezpieczeństwa).

**Testy:** `test_auth_wrong_password_returns_401`, `test_auth_invalid_token_returns_401`.

### P0-004 (CRITICAL) — Niezgodność unit systemd: `app.main` vs `dashboard.app`

**Ref:** mega_audit/systemd_entrypoint_bug/ · ADR-0029

**Problem:** Plik unit systemd wskazywał `app.main:app` — moduł nieistniejący. Prawdziwy entry point to `dashboard.app:app`. Każde uruchomienie przez systemd kończyło się `ModuleNotFoundError`.

**Naprawa:** Wszystkie szablony unit systemd (Linux, Windows Service) zaktualizowane do `dashboard.app:app`. Runbook i INCIDENT_RESPONSE.md zsynchronizowane. Walidacja w CI: `test_systemd_unit_entry_point_valid`.

### P0-005 (CRITICAL) — Pixel 9: 10 root causes detekcji

**Ref:** mega_audit/pixel_deep/ · ADR-0030

**Problem:** Urządzenie Pixel 9 nie było wykrywane poprawnie z 10 niezależnych powodów: hardkodowany `EXPECTED_MODEL="Pixel 8"`, brak `PIXEL_9_FAMILY` whitelist dla wariantów (Pro, Pro XL, Pro Fold, 9a), brak obsługi stanu `"unauthorized"` ADB, brak mapowania `shell_getprop` w `ALLOWED_ADB_COMMANDS`.

**Naprawa:**
- `PIXEL_9_FAMILY = ("Pixel 9", "Pixel 9 Pro", "Pixel 9 Pro XL", "Pixel 9 Pro Fold", "Pixel 9a")`
- `DeviceHarness.validate_pixel_model()` odczytuje `ro.product.model` przez `adb shell getprop`
- Stan `"unauthorized"` obsługiwany z czytelnym komunikatem i instrukcją autoryzacji
- `shell_getprop` dodany do allowlisty, ograniczony do namespace `ro.product.*` i `ro.build.*`
- Seed DB: `"pixel8"` → `"pixel9"` z migracją dla istniejących baz

**Testy:** `test_pixel9_all_variants_detected`, `test_pixel9_unauthorized_state`.

### P0-006 (CRITICAL) — Mudi WireGuard: stub bez implementacji

**Ref:** mega_audit/wireguard_impl/ · ADR-0031

**Problem:** Moduł WireGuard dla routera Mudi był jedynie stubem — funkcje deklarowane bez implementacji. Provisioning urządzenia kończyła się cichym sukcesem bez faktycznej konfiguracji tunelu.

**Naprawa:** Pełna implementacja `wg_config_generator.py`:
- Generowanie kluczy publicznych/prywatnych WireGuard przez `wg genkey | wg pubkey`
- Budowanie pliku konfiguracyjnego `wg0.conf` z parametrami peer
- Push konfiguracji przez SSH na router Mudi (OpenWRT)
- Weryfikacja handshake po 10 sekundach
- Kill switch: `PostDown` reguły `iptables` blokujące ruch poza interfejsem WireGuard

**ADR-0031:** Decyzja o implementacji w Pythonie (subprocess `wg`) zamiast `cryptography` lib ze względu na zero dodatkowych zależności.

### P0-007 (CRITICAL) — `run_codebase_audit` brakująca funkcja

**Ref:** mega_audit/upload_deep/ · `orchestrator.py`

**Problem:** Upload pipeline wywoływał `run_codebase_audit()` — funkcja nieistniejąca. Każdy upload projektu kończył się `NameError` i brakiem audytu.

**Naprawa:** Implementacja `run_codebase_audit(project_path: Path) -> AuditResult` w `orchestrator.py`. Funkcja: skanuje strukturę projektu, wywołuje agenty audytowe, agreguje wyniki w `AuditResult`. Podłączona do upload pipeline i uruchamiana automatycznie po zakończeniu upload (auto-run).

---

## Nowe funkcje

### NF: Diagnostyka v2 — 82 kody SYL-*

**Ref:** mega_audit/diagnostyka_deep/ · TF06

Nowy moduł `health_check_v2.py` (2 116 LOC) z pełnym pokryciem 82 kodów diagnostycznych:

- **SYL-PIX-xxx** — detekcja i stan urządzenia Pixel 9
- **SYL-DB-xxx** — integralność bazy SQLite, WAL, indeksy, migracje
- **SYL-SEC-xxx** — cookie flags, CSRF, rate limiting, argon2
- **SYL-COST-xxx** — FinOps, budżet LLM, tier routing
- **SYL-NET-xxx** — WireGuard, Mudi, DNS leak, kill switch
- **SYL-PERF-xxx** — hot paths, PRAGMA caching, connection pool
- **SYL-COMP-xxx** — RODO/DSGVO, KSeF, GoBD, retencja

Nowe endpointy API:
- `GET /api/health/v2` — pełny raport zdrowia (wszystkie 82 kody)
- `GET /api/health/v2?category=security` — raport filtrowany wg kategorii
- `GET /api/health/v2/history` — historia raportów zdrowia (SQLite `health_history`)

Frontend: 16-zakładkowy panel diagnostyczny z auto-refresh 30s i eksportem JSON.

### NF: Feature Flags + Kill Switch

**Ref:** mega_audit/feature_flags_runtime/ · ADR-0032

Mechanizm runtime toggle funkcji bez konieczności deployu:

- Tabela `feature_flags` w SQLite (key, enabled, critical, dependencies)
- API: `GET/PUT /api/feature-flags`, `POST /api/feature-flags/kill-switch`
- Dashboard panel: toggle z audit_log dla każdej zmiany
- **PIPELINE_EMERGENCY_STOP** — kill switch zatrzymuje wszystkie aktywne runy w <5 sekund
- Zmiana flagi krytycznej wymaga roli `owner`

### NF: Grafana + Prometheus Observability Stack

**Ref:** mega_audit/grafana_dashboards/

4 dashboardy Grafana + pełna konfiguracja:

- `1_overview.json` — Request Rate, Error Rate 4xx/5xx, Latency P50/P95/P99, DB Connections, WAL Size
- `2_llm_cost.json` — Total Cost, Monthly Estimate, Cost by Provider, Top 15 Users by Cost
- `3_security.json` — Security events, auth failures, CSRF violations
- `4_pipeline.json` — Pipeline health, stage durations, agent success rates
- `prometheus.yml` — scrape config + alert rules
- `alertmanager.yml` — routing PagerDuty / Slack / email

---

## Zmiany i usprawnienia

### P1-011 (HIGH) — 7 hot-path optymalizacji wydajności

**Ref:** mega_audit/perf_hot_paths/

| Hot-path | Problem | Naprawa |
|---|---|---|
| `get_conn()` PRAGMA | 2× PRAGMA per connection | Cached per-process (już v5.9.1 FIX-05) |
| `get_dashboard()` COUNT queries | 7 queries → 1 UNION ALL | Single query (v5.9.1 FIX-07) |
| `idx_sessions_expires_at` | Brak indeksu, full scan co 60s | Migracja 1→2 (v5.9.1 FIX-19) |
| Ollama insights pagination | Unbounded `limit` | `MAX_PAGE_SIZE = 1000` |
| `health_check` import | Dynamic `sys.path.insert` | Static `importlib.util.spec_from_file_location` |
| Argon2 concurrent hash | Race condition | Compare-and-swap (v5.9.1 FIX-20) |
| `_periodic_prune` timeout | Brak timeout → hang | `asyncio.wait_for(timeout=300.0)` |

### P1-012 (HIGH) — Bezpieczeństwo migracji schematu v3→v4

**Ref:** mega_audit/migrations_deep/

`migration_3_to_4.py` zawiera:
- Shadow DB test przed każdą migracją produkcyjną
- Rollback automatyczny jeśli `PRAGMA integrity_check` po migracji != `ok`
- Tabela `health_history` + indeksy (nowa w v3→v4)
- CLI: `python migration_3_to_4.py --dry-run` (podgląd bez wykonania)

### P1-017 (HIGH) — HumanGate: polling bridge dashboard ↔ CLI

**Ref:** mega_audit/humangate_flows/ · ADR-0033

Naprawiony defekt TF05: decyzje zatwierdzane w UI Dashboard nie docierały do CLI Orchestratora.

Rozwiązanie: SQLite polling bridge (`humangate_db_polling_bridge.py`) + SSE endpoint `/api/human-gate/stream`. Orchestrator odpytuje bazę co 2 sekundy; UI wysyła decyzję przez API → bridge → orchestrator odblokowany.

Gate-pointy: 19 agentów z `requires_human_gate: true`, 9 call-site'ów w orchestratorze.

### P1-009 (HIGH) — ADR 0020–0024: nagłówki i struktura

**Ref:** mega_audit/adr_0020_0024_headers/

ADR-0020 przez ADR-0024 uzupełnione o brakujące sekcje: Negative Consequences, Decision Outcome, Status. Numeracja ujednolicona do 4-cyfrowej (ADR-0001..ADR-0033).

### P2-018 (MEDIUM) — Phantom v3: 4 GAP-y funkcjonalne

**Ref:** mega_audit/phantom_deep/

- `log.warning` → `logger.warning` w `file_verification.py:336,344` (NameError fix, v5.9.1)
- Phantom v3 kompletny: hallucination detection 4 typów, claim provenance, anti-halluc log
- `build_verification.py` uruchamiany automatycznie po każdym pipeline run
- Gap: brak trybu interaktywnego (ADR-0034: odroczone do v5.10)

### P2-019 (MEDIUM) — Book Guardian: rebase w runtime

**Ref:** mega_audit/book_guardian_runtime_check/

`book_guardian.py` uzupełniony o:
- `rebase()` — porównanie bieżącej Księgi 3.4 z baseline promoted
- Automatyczne wykrywanie desynchronizacji (drift > 5 wierszy)
- CLI: `python book_guardian.py --rebase --dry-run`

---

## Infrastruktura (CI/CD, Docker, Monitoring)

### CI: `make setup` i automatyzacja środowiska

**Ref:** mega_audit/make_setup_target/

Nowy target `make setup`:
```bash
make setup      # venv + pip install + db init
make test       # pytest z coverage
make lint       # ruff check + ruff format --check
make deploy     # pre-deploy-council + systemd reload
```

Zastępuje manualne kroki opisane w starszych runbookach.

### Docker: Dockerfile kompletny

**Ref:** mega_audit/dockerfile/ · merged_v592/sylion-pipeline/Dockerfile

`Dockerfile` w oparciu o `python:3.12-slim`:
- Multi-stage build (builder + runtime)
- Non-root user `sylion` (UID 1000)
- Health check: `HEALTHCHECK CMD curl -f http://localhost:8421/api/health || exit 1`
- Volume: `/home/sylion/sylion` (dane SQLite + backupy)
- `docker-compose.yml` z serwisami: `sylion`, `prometheus`, `grafana`, `caddy`

### Monitoring: Prometheus + AlertManager

**Ref:** mega_audit/prometheus_alert_rules/ · mega_audit/grafana_dashboards/

Alert rules (plik `prometheus.yml`):
- `SylionHighErrorRate` — error rate >5% przez 5 min → PagerDuty
- `SylionLLMCostSpike` — koszt LLM >$50/h → Slack
- `SylionWALGrowth` — WAL >500 MB → email
- `SylionDBDown` — brak połączenia z SQLite → PagerDuty CRITICAL
- `SylionDiskLow` — wolne miejsce <1 GB → Slack WARNING

### systemd: poprawiony unit + entrypoint

**Ref:** P0-004 powyżej · mega_audit/systemd_entrypoint_bug/

Unit file (`deploy/sylion.service`):
```ini
[Service]
ExecStart=/usr/bin/python3 -m uvicorn dashboard.app:app \
  --host 127.0.0.1 --port 8421 --proxy-headers \
  --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=5
```

### Caddy: reverse proxy config

**Ref:** `Caddyfile` w merged_v592/

Produkcyjny `Caddyfile` z TLS, `X-Forwarded-For`, HSTS, rate limiting na poziomie proxy.

---

## Dokumentacja i prawo

### P1-013 (HIGH) — Privacy Policy zaktualizowane do v5.9.2

**Ref:** mega_audit/privacy_policy_v591/ · docs/PRIVACY_POLICY_PL.md · PRIVACY_POLICY_DE.md

Privacy Policy wskazywało v5.9.0. W v5.9.2 zaktualizowane do bieżącej wersji z poprawionymi datami, nazwami endpointów i listą procesorów danych.

### P1-014 (HIGH) — FAQ i Troubleshooting: luki pokrycia

**Ref:** mega_audit/faq_troubleshoot_v591/ · docs/FAQ_PL.md · FAQ_DE.md

Dodano 8 nowych pytań do FAQ_PL.md i FAQ_DE.md obejmujących typowe problemy:
- Pixel 9 nie wykrywany (SYL-PIX-001..010)
- WireGuard handshake fail
- DB migration rollback
- Setup token wygasł
- Feature flag kill switch

### RODO/DSGVO: pełny RoPA v5.9.2

**Ref:** mega_audit/rodo_full_audit/ · docs/RODO_COMPLIANCE.md

`RODO_COMPLIANCE.md` zaktualizowany:
- Tabela podmiotów przetwarzających z weryfikacją DPF i SCC (OpenAI, Anthropic, Google, Perplexity)
- Procedury DSR art.17 (erasure) z SLA 30 dni
- Minimalna retencja audit_log dla `severity='critical'`: 30 dni (poprzednio 1 dzień)
- Nowa: DPIA v5.9.2 (`docs/DPIA_v592.md`)

### GoBD + HGB §257: retencja dla środowisk DE

**Ref:** mega_audit/gobd_retention/

`docs/GOBD_RETENTION.md` — nowy dokument:
- 10-letnia retencja dla rekordów finansowych (HGB §257, AO §147)
- Immutable storage policy dla tabeli invoice (v5.11+)
- Audit trail zgodny z GoBD §146a AO

---

## Znane ograniczenia

| ID | Opis | Target |
|---|---|---|
| DEFER-03 | RTP/SRTP media plane — sygnalizacja OK, media plane jako future work | v5.10 |
| DEFER-04 | WireGuard kill-switch DNS leak — zaimplementowany WG, kill-switch w v5.10 | v5.10 |
| DEFER-05 | Upload nie wyzwala auto-pipeline (feature gap, nie bug) — naprawione w P0-007 | DONE |
| KSeF-N/A | KSeF/E-Rechnung — brak modułu fakturowania; poza zakresem pipeline | v5.11 |
| DEFER-INFO1 | BookGuardian — tryb interaktywny rebase | v5.10 |
| P3-x | WireGuard kill-switch z DNS leak protection | v5.10 |

---

## Migracja z v5.9.1

### Wymagania wstępne

| Element | Minimum | Uwagi |
|---|---|---|
| Python | 3.11 (3.12 zalecane) | Bez zmian względem v5.9.1 |
| argon2-cffi | ≥23.1.0 | Hard requirement |
| aiohttp | ≥3.10.11 | Nowy wymóg (CVE patch) |

### Kroki migracji

```bash
# 1. Backup bazy
cp ~/sylion/sylion.db ~/sylion/backups/sylion.db.bak.pre-v592.$(date +%Y%m%dT%H%M%S)

# 2. Zaktualizuj kod
git fetch origin && git checkout v5.9.2

# 3. Zaktualizuj zależności
pip install -r requirements-lock.txt

# 4. Uruchom — migracje DB automatyczne (v2→v3→v4)
python dashboard/start.py

# 5. Weryfikacja
sqlite3 ~/sylion/sylion.db "PRAGMA user_version;"
# Oczekiwany wynik: 4
```

### Automatyczne migracje DB

| Wersja schematu | Zmiany |
|---|---|
| v2 → v3 | Tabela `feature_flags`, `health_history` |
| v3 → v4 | Indeksy na `health_history`, kolumna `pixel_family` w `devices` |

Migracje są addytywne — brak ryzyka utraty danych. Rollback: `rollback.sh --dry-run` (podgląd), `rollback.sh` (wykonanie).

### Nowe zmienne środowiskowe

| Zmienna | Domyślna | Opis |
|---|---|---|
| `SYLION_LOGIN_MAX_ATTEMPTS` | `10` | Max prób logowania przed blokadą |
| `SYLION_FORWARDED_ALLOW_IPS` | `127.0.0.1` | Zaufane proxy IP (Caddy) |
| `SYLION_HEALTH_CHECK_V2` | `true` | Włącz Diagnostykę v2 |
| `GRAFANA_ADMIN_PASSWORD` | — | Hasło do Grafana (obowiązkowe przy Docker deploy) |

---

## Rollback

W przypadku problemów po upgrade do v5.9.2:

```bash
# Podgląd co zrobi rollback (dry-run)
./rollback.sh --dry-run

# Pełny rollback do stanu pre-v5.9.2
./rollback.sh

# Rollback tylko kodu (zachowaj nowe migracje DB)
git checkout v5.9.1
pip install -r requirements-lock.txt
```

Kody wyjścia `rollback.sh`:
- `0` = sukces
- `1` = brak backupu
- `2` = integrity_check failed
- `3` = brak uprawnień lub miejsca na dysku

Pełna procedura: [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md) · [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md)

---

*SYLION v5.9.2 · Mega-Audit Patch · Data wydania: 2026-04-19*
*Źródła: FIX_MAP_v5.9.2.md · Mega-audyt 49 subagentów · Raporty council_v590*
