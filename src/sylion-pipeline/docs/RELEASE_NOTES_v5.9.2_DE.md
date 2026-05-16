# SYLION v5.9.2 — Mega-Audit-Patch (Release Notes)

| Feld              | Wert                                                         |
|-------------------|--------------------------------------------------------------|
| **Version**       | 5.9.2                                                        |
| **Codename**      | *Mega-Audit-Patch*                                           |
| **Release-Typ**   | PATCH (SemVer 5.9.1 → 5.9.2)                                |
| **Datum**         | 2026-04-19                                                   |
| **Vorgänger**     | v5.9.1 (*Hardening Patch*, 2026-04-19)                       |
| **Charakter**     | Bugfix + Sicherheit + Infrastruktur. **Keine Breaking Changes.** |
| **Quelle**        | FIX_MAP_v5.9.2.md · Mega-Audit 49 Sub-Agenten · Welle 3     |
| **Fix-Matrix**    | [FIX_MAP_v5.9.2.md](./FIX_MAP_v5.9.2.md)                    |

Format basiert auf [Keep a Changelog v1.1.0](https://keepachangelog.com/de/1.1.0/).

---

## Zusammenfassung

v5.9.2 schließt alle **7 P0-Blocker** sowie **10 P1-Findings** aus dem Mega-Audit mit 49 Sub-Agenten (4 Runden × 4 KI-Modelle). Die Version führt keine neuen APIs oder Breaking Changes ein — sie ist ein sicheres Upgrade von v5.9.1 für jede Produktionsinstallation.

---

## Sicherheit

> Dieser Abschnitt behandelt ausschließlich Findings der Klassen SEC-* oder CVE.
> Vollständige Tabelle: `reports/council_v590/security/CONSOLIDATED.md`.

### P0-003 (CRITICAL) — CSRF: fehlender Schutz an 1 von 71 Endpunkten

**Ref:** mega_audit/csrf_71_endpoints/ · ADR-0026

**Problem:** Beim CSRF-Audit wurden 71 Endpunkte gescannt. Einer davon hatte kein CSRF-Token. In einem Cross-Site-Request-Forgery-Angriff hätte eine bösartige Seite autorisierte Anfragen im Namen eines eingeloggten Nutzers senden können.

**Behebung:** Betroffener Endpunkt in `app.py` mit doppeltem Schutz versehen: `SameSite=Strict`-Cookie und `X-CSRF-Token`-Header. Regressionstests: `test_csrf_all_71_endpoints_protected`.

### SEC-001 (CRITICAL, CVSS 9.8) — Kein Rate Limiting für `/api/auth/login`

**Ref:** reports/council_v590/security/CONSOLIDATED.md · ADR-0027

**Problem:** Der Login-Endpunkt hatte keine Begrenzung der Versuche — unbegrenzte Brute-Force-Angriffe ohne IP/Username-Sperre.

**Behebung:** Progressive Sperre per IP und Username: max. 10 Versuche / 5 min, eskalierend (5 min → 30 min → 4 h). Umgebungsvariable `SYLION_LOGIN_MAX_ATTEMPTS` (Standard: 10). Integration mit Caddy `X-Forwarded-For`.

### SEC-002 (CRITICAL, CVSS 8.1) — SHA-256 als Fallback beim Passwort-Hashing

**Ref:** reports/council_v590/security/CONSOLIDATED.md

**Problem:** `_init_hash_backend` fiel bei fehlendem `argon2-cffi` still auf SHA-256 zurück (v5.9.1 hat das Standardverhalten korrigiert, verwaiste Code-Pfade verblieben).

**Behebung:** Alle verwaisten SHA-256-Pfade entfernt. Hard-Fail ohne argon2-cffi bereits ab v5.9.1; v5.9.2 beseitigt Überreste.

### SEC-004 (CRITICAL, CVSS 9.1) — SQL-Injection über `PRAGMA user_version = {version}`

**Ref:** reports/council_v590/security/CONSOLIDATED.md · `db.py:817`

**Problem:** F-String-Interpolation des Versionswerts direkt in die SQL-Anweisung.

**Behebung:** Expliziter Cast `int(version)` + `assert 0 <= version <= 999` vor der Interpolation. Jeder andere Wert löst `ValueError` aus.

### SEC-005 (CRITICAL, CVSS 8.4) — Command-Injection in `_batch_imports_ok`

**Ref:** reports/council_v590/security/CONSOLIDATED.md · `start.py:93`

**Problem:** Import-Namen wurden ohne Validierung in ein als Subprocess ausgeführtes Skript übernommen.

**Behebung:** Regex-Allowlist `^[a-zA-Z_][a-zA-Z0-9_.]*$` vor dem Aufbau des Befehls. Jeder Name außerhalb der Liste wird mit `ImportError` abgelehnt.

### SEC-006 (HIGH, CVSS 7.5) — SQL-Injection in Ollama Shadow/Insights

**Ref:** reports/council_v590/security/CONSOLIDATED.md · `app.py:5697,5814`

**Problem:** `where_sql` wurde per F-String ohne Spaltensanitierung aufgebaut.

**Behebung:** Explizite Allowlist (`OLLAMA_ALLOWED_COLUMNS`); stets parametrisiertes `col = ?` + Tuple-Params. Tests: `test_ollama_no_sqli`.

### P2-020 (MEDIUM) — CVE in `aiohttp` (transitive)

**Ref:** mega_audit/aiohttp_transitive_cve/ · Lockfile-Patch

**Problem:** `aiohttp`-Version unterhalb des Sicherheits-Patches in einer transitiven Abhängigkeit.

**Behebung:** Upgrade auf `aiohttp>=3.10.11` in `requirements-lock.txt`, hash-gepinnt.

---

## Kritische Fehler (P0)

> Alle 7 P0-Blocker mussten vor dem Release von v5.9.2 geschlossen werden.

### P0-001 (CRITICAL) — DB-Init: Leere Datenbank nach `--seed`

**Ref:** mega_audit/db_init_bug/ · ADR-0028

**Problem:** `init_db()` mit dem Flag `--seed` schrieb 0 Bytes in die Datenbank — der Seed wurde nicht angewendet. Eine Erstinstallation endete mit einer leeren Datenbank ohne Agenten und ohne Admin.

**Behebung:** Race-Condition in der `CREATE TABLE` / `INSERT`-Reihenfolge durch explizite Transaktionssteuerung behoben. `_seed_agents()` in einen separaten Block verschoben, der nach Abschluss aller DDL-Operationen ausgeführt wird. Idempotenz: Wiederholte Ausführung dupliziert den Seed nicht.

**Tests:** `test_db_init_seed_not_empty`, `test_db_init_idempotent`.

### P0-002 (CRITICAL) — Auth: HTTP 500 statt 401

**Ref:** mega_audit/auth_500_bug/ · `app.py:370`

**Problem:** Authentifizierungs-Endpunkte warfen eine nicht abgefangene Ausnahme und gaben HTTP 500 statt des korrekten 401 Unauthorized zurück.

**Behebung:** `try/except` um die Auth-Logik, mit explizitem `raise HTTPException(401)` für alle Fehlerpfade. Zusätzlich: Login-Fehler werden jetzt in `audit_log` gespeichert (SEC-016).

**Tests:** `test_auth_wrong_password_returns_401`, `test_auth_invalid_token_returns_401`.

### P0-004 (CRITICAL) — Systemd-Unit-Konflikt: `app.main` vs. `dashboard.app`

**Ref:** mega_audit/systemd_entrypoint_bug/ · ADR-0029

**Problem:** Die systemd-Unit-Datei verwies auf `app.main:app` — ein nicht existierendes Modul. Der echte Einstiegspunkt lautet `dashboard.app:app`. Jeder Start über systemd endete mit `ModuleNotFoundError`.

**Behebung:** Alle systemd-Unit-Templates (Linux, Windows Service) auf `dashboard.app:app` aktualisiert. Runbook und INCIDENT_RESPONSE.md synchronisiert. CI-Validierung: `test_systemd_unit_entry_point_valid`.

### P0-005 (CRITICAL) — Pixel 9: 10 Ursachen für Erkennungsfehler

**Ref:** mega_audit/pixel_deep/ · ADR-0030

**Problem:** Das Gerät Pixel 9 wurde aus 10 unabhängigen Gründen nicht korrekt erkannt: Hardkodiertes `EXPECTED_MODEL="Pixel 8"`, fehlende `PIXEL_9_FAMILY`-Whitelist für Varianten (Pro, Pro XL, Pro Fold, 9a), keine Behandlung des ADB-Status `"unauthorized"`, fehlendes `shell_getprop`-Mapping in `ALLOWED_ADB_COMMANDS`.

**Behebung:**
- `PIXEL_9_FAMILY = ("Pixel 9", "Pixel 9 Pro", "Pixel 9 Pro XL", "Pixel 9 Pro Fold", "Pixel 9a")`
- `DeviceHarness.validate_pixel_model()` liest `ro.product.model` via `adb shell getprop`
- Status `"unauthorized"` wird mit verständlicher Meldung und Autorisierungsanleitung behandelt
- `shell_getprop` zur Allowlist hinzugefügt, begrenzt auf `ro.product.*` und `ro.build.*`
- DB-Seed: `"pixel8"` → `"pixel9"` mit Migration für bestehende Datenbanken

**Tests:** `test_pixel9_all_variants_detected`, `test_pixel9_unauthorized_state`.

### P0-006 (CRITICAL) — Mudi WireGuard: nur Stub, keine Implementierung

**Ref:** mega_audit/wireguard_impl/ · ADR-0031

**Problem:** Das WireGuard-Modul für den Mudi-Router war ausschließlich ein Stub — Funktionen deklariert, aber nicht implementiert. Das Provisioning meldete Erfolg, ohne tatsächlich einen Tunnel zu konfigurieren.

**Behebung:** Vollständige Implementierung in `wg_config_generator.py`:
- Schlüsselerzeugung via `wg genkey | wg pubkey`
- Aufbau der `wg0.conf` mit Peer-Parametern
- SSH-Push der Konfiguration auf den Mudi-Router (OpenWRT)
- Handshake-Verifikation nach 10 Sekunden
- Kill-Switch: `PostDown`-`iptables`-Regeln blockieren Traffic außerhalb des WireGuard-Interfaces

### P0-007 (CRITICAL) — `run_codebase_audit`: Fehlende Funktion

**Ref:** mega_audit/upload_deep/ · `orchestrator.py`

**Problem:** Die Upload-Pipeline rief `run_codebase_audit()` auf — eine nicht existierende Funktion. Jeder Projekt-Upload endete mit `NameError` und ohne Audit.

**Behebung:** Implementierung von `run_codebase_audit(project_path: Path) -> AuditResult` in `orchestrator.py`. Die Funktion scannt die Projektstruktur, ruft Audit-Agenten auf und aggregiert die Ergebnisse. Sie wird nach Abschluss des Uploads automatisch ausgeführt.

---

## Neue Funktionen

### NF: Diagnostik v2 — 82 SYL-*-Codes

**Ref:** mega_audit/diagnostyka_deep/ · TF06

Neues Modul `health_check_v2.py` mit vollständiger Abdeckung von 82 Diagnose-Codes:

- **SYL-PIX-xxx** — Erkennung und Gerätestatus Pixel 9
- **SYL-DB-xxx** — SQLite-Integrität, WAL, Indizes, Migrationen
- **SYL-SEC-xxx** — Cookie-Flags, CSRF, Rate Limiting, Argon2
- **SYL-COST-xxx** — FinOps, LLM-Budget, Tier-Routing
- **SYL-NET-xxx** — WireGuard, Mudi, DNS-Leak, Kill-Switch
- **SYL-PERF-xxx** — Hot Paths, PRAGMA-Caching, Connection Pool
- **SYL-COMP-xxx** — DSGVO/RODO, GoBD, KSeF, Datenretention

Neue API-Endpunkte:
- `GET /api/health/v2` — vollständiger Gesundheitsbericht (alle 82 Codes)
- `GET /api/health/v2?category=security` — gefilterter Bericht
- `GET /api/health/v2/history` — Verlauf der Gesundheitsberichte

Frontend: 16-Tab-Diagnosepanel mit Auto-Refresh (30 s) und JSON-Export.

### NF: Feature Flags + Kill Switch

**Ref:** mega_audit/feature_flags_runtime/ · ADR-0032

Laufzeit-Toggle von Funktionen ohne Deployment:
- Tabelle `feature_flags` in SQLite (key, enabled, critical, dependencies)
- API: `GET/PUT /api/feature-flags`, `POST /api/feature-flags/kill-switch`
- Dashboard-Panel: Toggle mit audit_log für jede Änderung
- **PIPELINE_EMERGENCY_STOP** — Kill-Switch stoppt alle aktiven Runs in <5 Sekunden
- Kritische Flags erfordern die Rolle `owner`

### NF: Grafana + Prometheus Observability Stack

**Ref:** mega_audit/grafana_dashboards/

4 Grafana-Dashboards + vollständige Konfiguration:
- `1_overview.json` — Request Rate, Fehlerrate 4xx/5xx, Latenz P50/P95/P99
- `2_llm_cost.json` — Gesamtkosten, Monatsschätzung, Kosten nach Anbieter
- `3_security.json` — Sicherheitsereignisse, Auth-Fehler, CSRF-Verstöße
- `4_pipeline.json` — Pipeline-Gesundheit, Stage-Dauern, Agenten-Erfolgsraten
- AlertManager-Routing: PagerDuty / Slack / E-Mail

---

## Änderungen und Verbesserungen

### P1-011 (HIGH) — 7 Hot-Path-Optimierungen

| Hot-Path | Problem | Behebung |
|---|---|---|
| `get_conn()` PRAGMA | 2× PRAGMA pro Verbindung | Per-Process-Cache (v5.9.1) |
| `get_dashboard()` COUNT | 7 Queries → 1 UNION ALL | Single Query (v5.9.1) |
| `idx_sessions_expires_at` | Kein Index, Full-Scan | Migration 1→2 (v5.9.1) |
| Ollama Pagination | Unbegrenzte `limit`-Werte | `MAX_PAGE_SIZE = 1000` |
| `health_check` Import | `sys.path.insert` dynamisch | `importlib.util.spec_from_file_location` |
| Argon2 Concurrent Hash | Race Condition | Compare-and-Swap (v5.9.1) |
| `_periodic_prune` Timeout | Kein Timeout → Hänger | `asyncio.wait_for(timeout=300.0)` |

### P1-012 (HIGH) — Sicherer Schemamigrationspfad v3→v4

**Ref:** mega_audit/migrations_deep/

`migration_3_to_4.py` enthält:
- Shadow-DB-Test vor jeder Produktionsmigration
- Automatischer Rollback bei fehlgeschlagenem `PRAGMA integrity_check`
- Tabelle `health_history` + Indizes (neu in v3→v4)
- CLI: `python migration_3_to_4.py --dry-run`

### P1-017 (HIGH) — HumanGate: Polling-Bridge Dashboard ↔ CLI

**Ref:** mega_audit/humangate_flows/ · ADR-0033

Defekt TF05 behoben: Im Dashboard-UI getroffene Entscheidungen erreichten den CLI-Orchestrator nicht.

Lösung: SQLite-Polling-Bridge (`humangate_db_polling_bridge.py`) + SSE-Endpunkt `/api/human-gate/stream`. Der Orchestrator fragt die Datenbank alle 2 Sekunden ab; das UI sendet Entscheidungen per API → Bridge → Orchestrator wird entsperrt.

### P2-018 (MEDIUM) — Phantom v3: 4 Funktionslücken

- `log.warning` → `logger.warning` in `file_verification.py:336,344` (NameError-Fix, v5.9.1)
- Phantom v3 vollständig: Halluzinationserkennung 4 Typen, Claim Provenance, Anti-Halluc-Log
- `build_verification.py` läuft automatisch nach jedem Pipeline-Run

### P2-019 (MEDIUM) — Book Guardian: Rebase zur Laufzeit

**Ref:** mega_audit/book_guardian_runtime_check/

`book_guardian.py` erweitert um:
- `rebase()` — Vergleich der aktuellen Buchversion 3.4 mit dem Promoted-Baseline
- Automatische Drift-Erkennung (>5 Zeilen Abweichung)
- CLI: `python book_guardian.py --rebase --dry-run`

---

## Infrastruktur (CI/CD, Docker, Monitoring)

### CI: `make setup` und Automatisierung

**Ref:** mega_audit/make_setup_target/

Neue Make-Targets:
```bash
make setup    # venv + pip install + db init
make test     # pytest mit Coverage
make lint     # ruff check + ruff format --check
make deploy   # pre-deploy-council + systemd reload
```

### Docker: Vollständiges Dockerfile

**Ref:** mega_audit/dockerfile/ · Dockerfile

Multi-Stage-Build (builder + runtime), Non-Root-User `sylion` (UID 1000), Health-Check, Volume für SQLite-Daten. `docker-compose.yml` mit Services: `sylion`, `prometheus`, `grafana`, `caddy`.

### Monitoring: Prometheus-Alertregeln

Alerts: `SylionHighErrorRate` (>5% Fehlerrate), `SylionLLMCostSpike` (>$50/h), `SylionWALGrowth` (WAL >500 MB), `SylionDBDown`, `SylionDiskLow` (<1 GB).

### systemd: Korrigierter Unit-Einstiegspunkt

```ini
ExecStart=/usr/bin/python3 -m uvicorn dashboard.app:app \
  --host 127.0.0.1 --port 8421 --proxy-headers \
  --forwarded-allow-ips=127.0.0.1
```

---

## Dokumentation und Datenschutz

### P1-013 (HIGH) — Datenschutzerklärung auf v5.9.2 aktualisiert

**Ref:** docs/PRIVACY_POLICY_DE.md

Datenschutzrichtlinien verwiesen auf v5.9.0. In v5.9.2 aktualisiert: aktuelles Datum, korrekte Endpunktnamen, vollständige Liste der Datenverarbeiter.

### DSGVO/BDSG: Vollständiges VVT v5.9.2

**Ref:** mega_audit/rodo_full_audit/ · docs/RODO_COMPLIANCE.md

`RODO_COMPLIANCE.md` aktualisiert:
- Auftragsverarbeiterliste mit DPF-Verifikation und SCC (OpenAI, Anthropic, Google, Perplexity)
- DSR-Verfahren Art. 17 (Löschung) mit 30-Tage-SLA
- Mindestaufbewahrung für `audit_log` bei `severity='critical'`: 30 Tage
- Neue DSFA v5.9.2 (`docs/DPIA_v592.md`)

### GoBD + HGB §257: Aufbewahrungsfristen für DE-Umgebungen

**Ref:** mega_audit/gobd_retention/

`docs/GOBD_RETENTION.md` — neues Dokument:
- 10-jährige Aufbewahrung für Finanzdatensätze (HGB §257, AO §147)
- Immutable-Storage-Policy für Invoice-Tabellen (v5.11+)
- GoBD-konformes Audit-Trail §146a AO

---

## Bekannte Einschränkungen

| ID | Beschreibung | Ziel |
|---|---|---|
| DEFER-03 | RTP/SRTP Media Plane — Signalisierung funktioniert, Media Plane ist zukünftige Arbeit | v5.10 |
| DEFER-04 | WireGuard DNS-Leak Kill-Switch | v5.10 |
| KSeF-N/A | KSeF/E-Rechnung — kein Rechnungsmodul im Core-Pipeline | v5.11 |
| DEFER-INFO1 | BookGuardian — interaktiver Rebase-Modus | v5.10 |

---

## Migration von v5.9.1

### Voraussetzungen

| Element | Minimum | Anmerkungen |
|---|---|---|
| Python | 3.11 (3.12 empfohlen) | Unverändert gegenüber v5.9.1 |
| argon2-cffi | ≥23.1.0 | Hard Requirement |
| aiohttp | ≥3.10.11 | Neu (CVE-Patch) |

### Migrationsschritte

```bash
# 1. Datenbank-Backup
cp ~/sylion/sylion.db ~/sylion/backups/sylion.db.bak.pre-v592.$(date +%Y%m%dT%H%M%S)

# 2. Code aktualisieren
git fetch origin && git checkout v5.9.2

# 3. Abhängigkeiten aktualisieren
pip install -r requirements-lock.txt

# 4. Starten — DB-Migrationen automatisch (v2→v3→v4)
python dashboard/start.py

# 5. Verifikation
sqlite3 ~/sylion/sylion.db "PRAGMA user_version;"
# Erwartetes Ergebnis: 4
```

### Neue Umgebungsvariablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `SYLION_LOGIN_MAX_ATTEMPTS` | `10` | Max. Login-Versuche vor Sperre |
| `SYLION_FORWARDED_ALLOW_IPS` | `127.0.0.1` | Vertrauenswürdige Proxy-IPs (Caddy) |
| `SYLION_HEALTH_CHECK_V2` | `true` | Diagnostik v2 aktivieren |
| `GRAFANA_ADMIN_PASSWORD` | — | Grafana-Passwort (Pflicht bei Docker-Deploy) |

---

## Rollback

```bash
# Vorschau (Dry Run)
./rollback.sh --dry-run

# Vollständiger Rollback
./rollback.sh

# Nur Code zurücksetzen (DB-Migrationen behalten)
git checkout v5.9.1
pip install -r requirements-lock.txt
```

Exit-Codes von `rollback.sh`: `0` = Erfolg · `1` = Kein Backup · `2` = Integritätsfehler · `3` = Keine Berechtigung

Vollständige Anleitung: [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md) · [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md)

---

*SYLION v5.9.2 · Mega-Audit-Patch · Veröffentlichungsdatum: 2026-04-19*
*Quellen: FIX_MAP_v5.9.2.md · Mega-Audit 49 Sub-Agenten · reports/council_v590*
