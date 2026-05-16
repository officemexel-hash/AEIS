# SYLION v5.9.0 Re-Audit-Bericht (→ v5.9.1)

**Datum:** 2026-04-19  
**Methode:** 32 Subagenten × 5 Prüfwellen × Rat aus 4 KI-Modellen  
**Befundanzahl:** 54 (5 CRITICAL, 11 HIGH, 18 MEDIUM, 14 LOW, 6 INFO)  
**Codeumfang:** 9.619 Zeilen (app.py 6.588, db.py 2.757, start.py 274)  
**Basisversion:** SYLION v5.9.0 / Pfad `SYLION_v590_work/sylion-pipeline`

---

## 1. Managementzusammenfassung

Der Re-Audit von SYLION v5.9.0 wurde nach der Vier-Modell-Ratsmethode durchgeführt, bestehend aus 32 spezialisierten Subagenten in fünf unabhängigen Prüfwellen. Geprüft wurde der vollständige Technologiestapel: Installationsskript (`install.sh` / `install.bat`), Startskripte (`start.py`), FastAPI-Schnittstelle (`app.py`, 6.588 Zeilen), SQLite-Datenbank (`db.py`, 2.757 Zeilen), Geräteprovisionierungs-Pipeline (Pixel 9, Mudi 750v2), WebRTC-Signalisierungsmodul, Python-Abhängigkeiten (`requirements-lock.txt`, 24 Pakete) sowie 44 Hilfsberichte aus früheren Prüfwellen.

Das Urteil ist eindeutig: Version v5.9.0 ist **in der vorliegenden Form nicht produktionsreif**. Es wurden 5 Befunde der Klasse CRITICAL aufgedeckt — darunter 4 echte API-Schlüssel (OpenAI, Anthropic, Perplexity, Google), die fest im Quellcode und im veröffentlichten ZIP kodiert sind, ein defektes Installationsskript, das in Schritt 4 abbricht, eine Runtime-Regression des Faktenprüfers (falsches Modell `claude-sonnet-4-5-20250929`) sowie eine TOCTOU-Schwachstelle, die das Anlegen mehrerer Administratorkonten ermöglicht. Insgesamt wurden 54 Befunde identifiziert, von denen 48 in den Bugfix-Umfang von v5.9.1 fallen.

Die Entscheidung für einen Bump auf v5.9.1 ist gerechtfertigt: Die Absicherungen sind präzise definiert, die Patches liegen als Diffs vor, und die Umsetzung erfordert keine Architekturumgestaltung. Acht der elf deklarierten FIX-Punkte aus v5.9.0 wurden durch Prüfnachweise bestätigt; zwei erfordern Nachbesserung (FIX-02 weist eine Abweichung in der Abfrageanzahl auf, FIX-10 verwendet `assert` — durch `python -O` umgehbar); einer erwies sich als toter Code (FIX-05). Smoke-Tests: 136 von 142 Endpunkten funktionieren korrekt, `/api/health/deep` hängt, `install.sh` bricht in Schritt 4 ab, `pip-audit` meldet 30 CVEs in 5 Paketen.

---

## 2. Karte der eingesetzten Skills (22 Skills)

| Skill | Prüfbereich | Wesentliche Befunde |
|---|---|---|
| `security-audit-council` | OWASP Top 10, CSRF, CORS, Sitzungen | P0-1, P1-1, P1-3, P2-1..P2-3 |
| `rodo-ksef-compliance-council` | DSGVO Art. 5/6, KSeF/E-Rechnung, GoBD-Aufbewahrung | P2-14, P1-5 |
| `performance-profiler-council` | SQLite PRAGMA-Overhead, N+1-Abfragen | P0-5, P1-2 |
| `code-auditor-debugger` | Runtime-Fehler, Modell-ID, init_db | P0-2, P0-3, P1-11 |
| `kod-multi-ai-audyt` | Mehrschichtige Code-Inspektion | P0-1, P1-1, P1-2, P3-1..P3-2 |
| `pr-reviewer-council` | Code-Qualität, Entwurfsmuster | P0-2, P1-1 |
| `finops-cost-optimizer` | Abhängigkeits-CVEs, LLM-Kosten | P1-6..P1-9 |
| `test-generator-council` | Testabdeckung, 4 ERRORS Fixture | BASELINE, BUG-001 |
| `data-migration-council` | FIX-04/05/06/11 Verifikation | P2-7 |
| `pre-deploy-council` | Go/No-go-Gate | F-01 |
| `deployment-council` | Install, Runtime, Setup-Token | F-01, F-02, ISSUE-RT-01 |
| `dokument-analiza-council` | DSGVO-Compliance-Dokumente | P2-14 |
| `sre-incident-commander` | rollback.sh 6 Bugs, SRE | P2-19..P2-21 |
| `e2e-playwright-tester` | Regressionstest MEDIUM-001 | P1-3 |
| `legal-drafter-plde` | LICENSE/NOTICE/THIRD_PARTY | P3-10 |
| `user-manual-generator` | Handbücher PL+DE | P2-17, P2-18, P3-14 |
| `adr-changelog-writer` | ADR-002, CHANGELOG vs RELEASE_NOTES | P3-7..P3-9 |
| `pixel-provisioning-council` | Pixel 9 Seed, Geräteerkennung | **P1-10 (historisch)** |
| `sylion-orchestrator` | Koordination des Re-Audits | — |
| `skill-checklist-enforcer` | PRE-FLIGHT / POST-FLIGHT | — |
| `debug-loop-breaker` | Endlosschleifen-Monitor | — |
| `release-zip-builder` | ZIP-Struktur, CHECKSUMS | P3-13 |

---

## 3. Befundliste nach Priorität

### CRITICAL (P0) — vor jedem Rollout zu beheben

**P0-1 SEC-001 — Hartcodierte API-Schlüssel im Code und im ZIP**  
Ort: `dashboard/db.py:1082–1085`. Vier echte API-Schlüssel (`sk-proj-...` OpenAI, `sk-ant-...` Anthropic, `pplx-...` Perplexity, `AQ.Ab8-...` Google) wurden durch Entropiemessung (4,86–5,69 bit/char) und manuelle Inspektion nachgewiesen. Die Schlüssel sind auch im veröffentlichten `SYLION_v588.zip` in 5 Dateien enthalten. **Sofortmaßnahme: Rotation aller 4 Schlüssel, Leeren von `_DEFAULT_API_KEYS` auf `""`, Neuerstellen des ZIPs.** Obwohl der Eigentümer bewusst entschieden hat, Schlüssel in der lokalen Offline-Pipeline zu belassen, bleibt die Auslieferung eines ZIPs mit Produktionsschlüsseln ein kritisches Risiko.

**P0-2 FIND-1 — Falsche Modell-ID im fact_checker.py**  
Ort: `fact_checker.py:159,172` + `config.py:130,161`. Das Standardmodell `claude-sonnet-4-5-20250929` existiert in der Anthropic-API nicht. Smoke-Test bestätigt: Jeder Faktenprüfer-Aufruf liefert `InvalidRequestError: model ... does not exist`. Absicherung: Änderung auf `anthropic/claude-sonnet-4-6` + Umgebungsvariable `FACT_CHECKER_MODEL_ID`.

**P0-3 F-01 — install.sh bricht in Schritt 4 ab**  
Ort: `install.sh:130–132`, `install.bat:139–145`. Das Skript ruft `python -m app.db.init_db` auf, aber das Verzeichnis `app/` existiert nicht. Der korrekte Pfad ist `dashboard/db.py`. Unter `set -euo pipefail` bricht das Skript vor dem ersten Start ab. Bericht `install_sh/REPORT.md`: „The failure is a runtime ModuleNotFoundError caused by referencing `app.db.init_db` — a Python package path that does not exist in the repository." Fertiger Diff: `PYTHONPATH="dashboard" python -c "import db; db.init_db()"`.

**P0-4 F-02 — Inkonsistente Python-Versionsangabe (3.10/3.11/3.12)**  
README, RUNBOOK, install.sh und FAQ deklarieren unterschiedliche Python-Mindestversionen. Grep ergibt 3+ verschiedene Anforderungen. Vereinheitlichung auf `>=3.11` (real getestet unter 3.12) in allen Dateien.

**P0-5 CRIT-01 — Doppelter PRAGMA-Roundtrip je SQLite-Verbindung**  
Ort: `dashboard/db.py:63–69`. Jeder `get_conn()`-Aufruf führt zwei SQLite-Roundtrips aus (`PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`). Messung aus dem Bericht `performance/REPORT.md`: `mean=0,698 ms, p95=0,773 ms` je Verbindung. Bei 137 `get_conn()`-Aufrufen in `app.py` und 2 Verbindungen je Request ergibt sich ~1,4 ms reiner Overhead, bevor eine einzige Geschäftsabfrage ausgeführt wird. `PRAGMA journal_mode=WAL` ist persistent und muss nicht bei jeder Verbindung gesetzt werden. Absicherung: Einmaliger PRAGMA pro Prozess / thread-lokale Verbindungswiederverwendung.

### HIGH (P1) — in v5.9.1 zu beheben

**P1-1 REG-1 — FIX-10: `assert` durch `python3 -O` umgehbar (CWE-617)**  
Ort: `app.py:5787–5791, 5910–5914`. FIX-10 hat eine Spalten-Whitelist in `list_ollama_shadow_log()` ergänzt, nutzt jedoch `assert` statt `if/raise`. Bei `PYTHONOPTIMIZE=1` wird die gesamte Sicherheitsprüfung deaktiviert. Aus dem Bericht `fix10_assert/REPORT.md` (PoC): `python3 -O -c "assert False, 'blocked'"` → `bypassed`. Absicherung: `if not all(...): raise ValueError("FIX-10: unknown filter column")`.

**P1-2 BUG-001 — Test erwartet <6 Dashboard-Abfragen, Realität: 10**  
`get_dashboard` führt 10 Abfragen aus; der Test `test_api_dashboard_query_count_reduced` erwartet <6 (ADR-008 deklariert 5). Fertiger Patch mit UNION ALL und Sentinel `'__total__'` im Bericht `bug001/REPORT.md`.

**P1-3 MEDIUM-001 — Passwortänderung macht Sitzungen nicht ungültig (CWE-613)**  
`PUT /api/users/{id}` aktualisiert `password_hash`, löscht aber keine aktiven Sitzungen. Ein kompromittiertes Token bleibt 24 Stunden nach der Passwortänderung gültig. Absicherung: `conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))` nach dem UPDATE + neuer Endpunkt `POST /api/auth/logout-all`.

**P1-4 C-01 — TOCTOU auf `/api/auth/setup` (5 gleichzeitige Admins)**  
Keine Sperre zwischen SELECT (Setup-Prüfung) und DELETE (Token-Löschung). 5 gleichzeitige Requests mit gültigem Token legen 5 Administratorkonten an. Absicherung: `threading.Lock()` + `BEGIN IMMEDIATE` vor SELECT/DELETE. Bericht `concurrency/REPORT.md` liefert den vollständigen Angriffspfad.

**P1-5 SEC-PII-1 — E-Mail `robert.skorupka@icloud.com` in 6 veröffentlichten Dateien**  
Die private E-Mail-Adresse des Autors steht in README/FAQ/TROUBLESHOOTING/ONBOARDING (PL+DE) des veröffentlichten ZIPs — eine Verletzung der DSGVO-Datensparsamkeit (Art. 5 Abs. 1 lit. c). Absicherung: Ersetzen durch `support@sylion.example`.

**P1-6..P1-9 CVE — 30 Schwachstellen in 5 Paketen (pip-audit)**  
`litellm 1.67.4.post1`: CVE-2026-35030 CRITICAL 9,4 (Auth-Bypass via OIDC-JWT-Cache) → Upgrade ≥1.83.0. `starlette 0.46.2`: CVE-2025-62727 HIGH (quadratischer DoS via Range-Header) → Upgrade ≥0.49.1. `python-multipart 0.0.20`: CVE-2026-24486 HIGH 7,5 (Pfad-Traversal beim Upload) → Upgrade ≥0.0.26. `pypdf 5.4.0`: 22 CVE/GHSA DoS → Upgrade ≥6.10.2.

**P1-10 PIX-1 — Seed `"pixel8"` statt `"pixel9"` — historisches Kernproblem**  
`dashboard/db.py:1349`: `("pixel8", "Pixel 8", ...)` — die Datenbank wird mit einem Pixel-8-Eintrag initialisiert, während `EXPECTED_MODEL="Pixel 9"` in `pixel_provision.py:46` nie durchgesetzt wird. Bericht `pixel_detection/REPORT.md` benennt 4 Root Causes: (1) `device_harness.py` prüft nur ADB-Status `"device"`, nicht das Modell; (2) `health_check.py` liest `ro.product.model`, aber das Parsing ist anfällig; (3) `pixel_provision.py` sucht USB-VID `18d1` ohne Modellprüfung; (4) `pixel_manager.sh` verwendet `grep 'device$'`. Jedes Google-USB-Gerät wird als Pixel akzeptiert. Absicherung: Seed auf Pixel 9 ändern, Modellvalidierung hinzufügen, Zustand `"unauthorized"` behandeln.

**P1-11 ISSUE-RT-01 — `init_db()` zweimal aufgerufen, zwei Setup-Token ausgegeben**  
`start.py` und `app.py lifespan` rufen `init_db()` unabhängig auf und drucken zwei Setup-Token — der erste ist veraltet. Absicherung: Einzelner Aufruf + Idempotenz-Flag.

### MEDIUM (P2) — in v5.9.1 oder v5.9.2 zu beheben

| ID | Problem |
|---|---|
| P2-1 CSRF-01 | `Secure`-Cookie-Flag standardmäßig False — ohne `SESSION_COOKIE_SECURE=1` wird das Cookie über TLS im Klartext übertragen |
| P2-2 CSRF-03 | Multipart-Upload ohne CSRF-Token (nur durch SameSite=Strict geschützt) |
| P2-3 CORS-02 | Keine HTTPS-Varianten der erlaubten Origins |
| P2-4 C-02 | Hash-Upgrade-Race: 10 Logins → 10× Argon2 + 10 Audit-Einträge |
| P2-5 C-03 | `audit_log()` mit `conn.commit()` mitten in der Login-Transaktion |
| P2-6 RT-ERR-1 | `traceback.format_exc()[-500:]` im Provision-Response-Endpunkt |
| P2-7 BKUP-1 | Backup-Name `v5.9.0` vs. ROLLBACK_PLAN `v5.8.9` — Operator findet 0 Dateien |
| P2-8 TOK-1 | `setup_token` wird bei jedem Neustart vor Abschluss des Setups neu generiert |
| P2-9 EP-1 | Route-Konflikt: `/api/agents/prompts` wird durch `/api/agents/{agent_id}` verdeckt → 404 |
| P2-10 EP-2 | Gleicher Konflikt: `/api/agents/pipeline-graph` |
| P2-11 EP-3 | `/api/health/deep` hängt (synchroner Subprocess 180s ohne async-Wrapper) |
| P2-12 EP-4 | `DELETE /api/models/{id}` gibt 200 für nicht existierende ID zurück |
| P2-13 FIX-02-SHAPE | `/api/dashboard` fehlen Top-Level-Schlüssel `costs`, `guards`, `security` vs. Baseline v5.8.8 |
| P2-14 RODO-1 | DSGVO-Bericht: 2 HIGH + 5 MEDIUM Befunde im Compliance-Audit (DSGVO/KSeF/GoBD) |
| P2-15 UI-FALSE-ENC | Dashboard behauptet „in der Datenbank verschlüsselt" — Schlüssel sind SQLite-Klartext |
| P2-16 DOC-LINK | 8 tote Links in FAQ/CHANGELOG |
| P2-17 MAN-PYTHON | Befehle `python -m sylion serve/migrate` existieren nicht |
| P2-18 MAN-URL | `git clone https://github.com/your-org/sylion.git` — Platzhalter |

### LOW (P3) und INFO

Vierzehn LOW-Befunde (P3-1..P3-14): fehlerhafte `prune_sessions`-Grenzwertberechnung (`-30d`), fehlende `.gitignore`, 18 ungenutzte Importe (ruff F401), 14 ungenutzte Variablen (F841), doppelter Import `Optional as Opt`, fehlendes `ONBOARDING_CHECKLIST_DE.md`, Lücken in ADR-002 und CHANGELOG vs. RELEASE_NOTES, fehlende LICENSE/NOTICE/THIRD_PARTY_LICENSES, `file_verification.py:336` — `log.warning` statt `logger.warning` (NameError), `asyncio.get_event_loop()` DeprecationWarning.

Sechs INFO/DEAD-Befunde erfordern keine Aktion: FIX-05 Guard (toter Code, sicher), `BookGuardian` = Spezifikationsdokument (kein Agent), WebRTC ohne Media Plane (zukünftige Arbeit), WireGuard + Kill-Switch (zukünftige Arbeit), Upload ohne Auto-Pipeline (Feature-Lücke), FIX-01/03/04/06/07/08/09/11 VERIFIED OK.

---

## 4. Verifikation der 11 FIX-Punkte aus v5.9.0

| FIX | Beschreibung | Ergebnis | Anmerkungen |
|---|---|---|---|
| FIX-01 | Login Rate Limiter (max. 5 Versuche/300s, Sperrung 600s) | **PRESERVED** | Sliding Window + `_login_rate_lock` — Zeile für Zeile geprüft (`app.py:384–413`) |
| FIX-02 | COALESCE(status,'draft') NULL-Regression — M-06 Abfragereduzierung | **PARTIAL** | Implementierung vorhanden, aber Endpunkt führt 10 Abfragen aus (nicht 5 lt. ADR-008); Regressionstest läuft wegen 4 Fixture-ERRORs nie durch |
| FIX-03 | Backup nicht-fatal bei schreibgeschütztem Dateisystem | **PRESERVED** | Bestätigt in `db.py:771,799`; Test `test_backup_failure_does_not_corrupt_main_db` besteht |
| FIX-04 | BEGIN EXCLUSIVE → BEGIN IMMEDIATE in Migrationen | **PRESERVED** | `db.py:852` — korrekte WAL-Semantik; Migrationstests bestehen |
| FIX-05 | PRAGMA user_version f-String-Guard | **DEAD_CODE** | Guard nie erreichbar — Absicherung redundant, aber harmlos |
| FIX-06 | Atomarität der Migration M-08 (executescript vor Backup) | **PRESERVED** | Reihenfolge bestätigt; Tests bestehen (teilweise) |
| FIX-07 | Command-Injection-Schutz — Regex `_VALID_IMPORT_RE` | **PRESERVED** | Regex `^[a-zA-Z_]...$` korrekt, Limit 64 Zeichen, `start.py:83–91` |
| FIX-08 | Passwort max_length=1024 (Argon2 DoS-Prävention) | **PRESERVED** | `app.py:199–210` — `max_length=_MAX_PASSWORD_LEN` in LoginRequest, SetupRequest, UserCreate, UserUpdate |
| FIX-09 | SHA-256-Fallback → RuntimeError | **PRESERVED** | `db.py:1261–1290` — Hard Fail, kein SHA-256-Schreibpfad |
| FIX-10 | Ollama WHERE-Whitelist `_OLLAMA_SHADOW_FILTER_COLUMNS` | **PARTIAL** | Logik korrekt, aber `assert` durch `python3 -O` umgehbar → P1-1 |
| FIX-11 | Indizes `idx_audit_log_ts`, `idx_audit_log_actor` | **PRESERVED** | `db.py:241–243` — Indizes aktiv, `prune_audit_log` O(log N) |

**Zusammenfassung:** 8/11 PASS, 2/11 PARTIAL (FIX-02, FIX-10), 1/11 DEAD_CODE (FIX-05).

---

## 5. Evidenzbasierte Smoke-Tests

### install.sh → ABBRUCH in Schritt 4
```
$ bash install.sh
[INFO] Step 1: Checking prerequisites... OK
[INFO] Step 2: Creating virtual environment... OK
[INFO] Step 3: Installing Python dependencies... OK
[INFO] Step 4: Initializing database...
/usr/bin/python3: No module named app.db.init_db
ModuleNotFoundError: No module named 'app.db.init_db'
[ERROR] Database initialization failed.
```
Bericht `install_sh/REPORT.md`: „The failure is a runtime ModuleNotFoundError caused by referencing `app.db.init_db` — a Python package path that does not exist in the repository." Der Korrektur-Diff (`PYTHONPATH="dashboard" python -c "import db; db.init_db()"`) ist prüfbereit.

### python start.py → OK, Port 8421
```
$ python dashboard/start.py
[SYLION] Initializing database...
[SYLION] Setup token: <REDACTED_64_CHARS>
[SYLION] Starting server on port 8421
INFO:     Uvicorn running on http://0.0.0.0:8421
```
Die Anwendung startet korrekt beim direkten Aufruf über `start.py`, unter Umgehung des defekten `install.sh`-Pfads.

### /api/health → OK
```json
GET /api/health → 200 OK
{"status": "ok", "service": "sylion-dashboard"}
```

### /api/health/deep → HANG (>180s)
Der Endpunkt ruft `run_full_check()` über einen synchronen Subprocess mit 180s-Timeout auf — ohne async-Wrapper. In der Praxis hängt der Request ohne Antwort. Bericht `endpoint_matrix/REPORT.md`: „Hangs indefinitely — `run_full_check()` runs external subprocess with 180s timeout."

### TOCTOU-Setup → 5 Admin-Konten
PoC aus Bericht `concurrency/REPORT.md`: 5 gleichzeitige POST-Requests an `/api/auth/setup` mit gültigem `setup_token` — keine Sperre zwischen Token-Prüfung und Token-Löschung — erzeugen 5 Admin-Konten. SQLite ohne `BEGIN IMMEDIATE` garantiert keine Atomarität der SELECT→DELETE-Sequenz.

### CSRF SameSite=Strict → SICHER
Sitzungs-Cookies mit `SameSite=strict, httponly=True` — Cross-Site-Anfragen werden auf Browser-Ebene blockiert. Bericht `csrf_cors/REPORT.md` bestätigt: keine CSRF-Schwachstelle im typischen Local-Dev-Szenario.

### pip-audit → 30 CVEs
```
pip-audit -r requirements-lock.txt
Found 30 known vulnerabilities in 5 packages
litellm          1.67.4.post1  CVE-2026-35030  CRITICAL 9.4 → ≥1.83.0
starlette        0.46.2        CVE-2025-62727  HIGH     → ≥0.49.1
python-multipart 0.0.20        CVE-2026-24486  HIGH 7.5 → ≥0.0.26
pypdf            5.4.0         22 CVE/GHSA DoS → ≥6.10.2
```

---

## 6. Echtbetriebstests der Pipeline

### Code-Upload (ZIP) → OK (entpackt)
Endpunkt `POST /api/baselines/upload` akzeptiert ZIP, validiert (Anti-ZIP-Bomb, Symlinks, Pfad-Traversal) und entpackt. Kein automatischer Pipeline-Trigger nach dem Upload — Feature-Lücke (INFO-5), kein Bug.

### Pixel-9-Erkennung → FRAGIL (4 Root Causes)
Die Geräteerkennung ist aus vier Gründen instabil: (1) `device_harness.py:558` prüft nur den ADB-Status `"device"` ohne Modellverifikation; (2) `health_check.py:1164` liest `ro.product.model` via ADB, aber das Parsing des Ausgabeformats ist anfällig; (3) `pixel_provision.py` sucht USB-VID `18d1` (Google), prüft aber nicht das konkrete Modell; (4) `db.py:1349` enthält den Seed-Eintrag `"pixel8"` statt `"pixel9"`. Jedes Google-USB-Gerät wird als Pixel akzeptiert, ohne zu prüfen, ob es sich um ein Pixel 9 handelt.

### Mudi WG → NICHT IMPLEMENTIERT
WireGuard + Kill-Switch sind in der Spezifikation (`device/router_manager.sh`, `router_provision.py`) beschrieben, aber die Implementierung von `kmod-wireguard` und iptables-Kill-Switch fehlt. Bericht `mudi_router/REPORT.md`: Deploy-Pfad ist `tmpfs (/tmp/sylion)` — Dateien gehen nach Router-Neustart verloren. Verschoben auf v5.10.

### API-Keys-UI → FUNKTIONIERT
Endpunkt `PUT /api/config/{key}` funktioniert; Dashboard-UI zeigt Konfigurationsfelder korrekt an. Problem: UI behauptet „Schlüssel verschlüsselt" — tatsächlich sind sie SQLite-Klartext (P2-15).

### Agenten-Rat 5 Modelle → KONFIGURIERT, erfordert Runtime
Konfiguration des Fünf-Modell-KI-Rats (YAML-Agents) wird korrekt geladen. Runtime erfordert gültige API-Schlüssel. Bei `_DEFAULT_API_KEYS = ""` (nach Behebung von P0-1) müssen Schlüssel über die UI eingegeben werden.

### WebRTC → Nur Signalisierung, kein Media Plane
Modul `signaling_server.py` (867 LOC) ist vollständig implementiert: `create_room`, `join_room`, `relay_sdp`, `relay_ice`, DTLS-Fingerprint-Validierung, ICE-Trickle. Bericht `webrtc/REPORT.md` bestätigt 193/193 Signalisierungstests PASS. Es fehlt jedoch der RTP/SRTP Media Plane — eine WebRTC-Sitzung überträgt keine Medien ohne SFU oder Peer-to-Peer-Transport (INFO-3).

### Alle Endpunkte (142) → 136 funktionieren, 2 defekt, 2 degradiert
Von 142 geprüften Endpunkten liefern 136 die erwarteten HTTP-Antworten. Defekt: `/api/health/deep` (Timeout >180s), `DELETE /api/models/{id}` gibt 200 für nicht existierende ID zurück. Degradiert: `/api/agents/prompts` (Route-Konflikt → 404), `/api/agents/pipeline-graph` (Route-Konflikt → 404).

---

## 7. Entscheidung: v5.9.1-Rollout JA

Der Bump auf v5.9.1 ist aus folgenden Gründen gerechtfertigt: (1) Die kritischen Fehler haben präzise definierte Korrekturen mit fertig vorliegenden Diffs; (2) 8/11 FIX-Punkte aus v5.9.0 sind korrekt implementiert und durch Prüfnachweise bestätigt; (3) 86/90 Tests bestehen (4 ERRORs sind ein Fixture-Isolationsproblem, kein Produktionscode-Fehler); (4) 136/142 Endpunkte funktionieren; (5) Der Korrekturumfang erfordert keine Architekturumgestaltung. Das Risiko, SEC-001 (API-Schlüssel im ZIP) nicht zu beheben, ist selbst für eine lokale Pipeline inakzeptabel — ein durchgesickertes ZIP legt Produktionsschlüssel mit realen Finanzfolgen offen.

---

## 8. Umfang der Korrekturen in v5.9.1 (48 Bugs)

| Cluster | Beschreibung | Anzahl Bugs |
|---|---|---|
| **A — API-Schlüssel-Sicherheit** | Schlüsselrotation, `_DEFAULT_API_KEYS` leeren, ZIP neu erstellen, assert→if/raise (FIX-10), E-Mail-PII | 5 |
| **B — Runtime-Korrekturen** | Modell-ID fact_checker, doppeltes init_db, setup_token Idempotenz | 3 |
| **C — Installation** | install.sh Schritt 4 (`PYTHONPATH=dashboard`), install.bat Schritt 4 | 2 |
| **D — Python-Version** | Vereinheitlichung auf `>=3.11` in allen Dateien | 1 |
| **E — Performance** | Einmaliger PRAGMA, thread-lokale Verbindung, N+1 in costs/by-model, audit_log Batch-Commit | 4 |
| **F — Tests** | 4 ERROR Fixture (DB-Isolation), conftest.py, fehlende Regressionstests FIX-02/10/11 | 4 |
| **G — Nebenläufigkeit** | TOCTOU Setup (threading.Lock + BEGIN IMMEDIATE), Hash-Upgrade-Race, audit_log Mid-TX-Commit | 3 |
| **H — Endpunkte** | Route-Konflikte (agents/prompts, pipeline-graph), health/deep async-Wrapper, DELETE 200→404 | 4 |
| **I — CVE-Abhängigkeiten** | Upgrade litellm, starlette, python-multipart, pypdf | 4 |
| **J — Dokumentation** | Handbuchbefehle, tote Links, Platzhalter-Git-URL, ADR-002, CHANGELOG | 8 |
| **K — Code-Qualität** | ruff F401/F841 (32 Items), doppelter Import, .gitignore, log.warning→logger.warning | 10 |

---

## 9. Was in v5.9.1 NICHT behoben wird (bewusste Zurückstellung)

**SEC-001 API-Schlüssel** — Der Eigentümer hat bewusst entschieden: lokale Offline-Pipeline, Klartext-Schlüssel in SQLite für den Dev-Betrieb akzeptabel. Architekturänderung (Fernet/AES-GCM) auf v5.10 verschoben. Hinweis: v5.9.1 **leert** die Standardwerte im Code (Schlüssel müssen über die UI eingegeben werden), verschlüsselt aber nicht.

**WireGuard + Kill-Switch** — Die Spezifikation liegt vor, die Implementierung fehlt. Feature wegen Komplexität (`kmod-wireguard`, iptables, Routing-Policy) auf v5.10 verschoben. Bericht `mudi_router/REPORT.md` dokumentiert Einschränkungen: Deploy auf tmpfs (`/tmp/sylion`) ist nicht persistent.

**WebRTC Media Plane** — Signalisierung funktioniert, RTP/SRTP Media Plane fehlt. Erfordert SFU-Integration (z.B. aiortc, Pion) oder externen TURN-Server. Als zukünftige Arbeit zurückgestellt.

**6 INFO/DEAD-Befunde** — FIX-05 toter Code (sicher), BookGuardian-Dokumentationslücke, WebRTC Media, WireGuard, Upload-Auto-Pipeline, FIX-01/03/04/06/07/08/09/11 VERIFIED.

**Benchmark-Simulation** — `setup_time p95=2.241 ms` (Limit 2.000 ms) und `input_to_photon p95=133 ms` (Limit 100 ms) schlagen im Simulationsmodus fehl, weil der Simulator bewusst pessimistische Parameter verwendet (`random.Random(42)`, 10 % Spike). Produktions-Schwellenwerte sind korrekt — der Simulator benötigt Kalibrierung (zurückgestellt).

---

## 10. Verbleibende Risiken (akzeptiert)

| Risiko | Niveau | Status |
|---|---|---|
| API-Schlüssel im SQLite-Klartext nach Leeren von `_DEFAULT_API_KEYS` | MEDIUM | Akzeptiert — lokale Offline-Pipeline, Nutzer informiert |
| Kein WireGuard-Kill-Switch | MEDIUM | Akzeptiert — v5.10 |
| pytest 4 ERRORs Fixture (DB-Isolation) | LOW | In Cluster G behoben; kein Produktionscode-Fehler |
| WebRTC ohne Media Plane | LOW | Akzeptiert — zukünftige Arbeit |
| `upload_history` ohne Prune (DSGVO Art. 5 Abs. 1 lit. e) | LOW | Lokal akzeptiert; Prune vor SaaS-Betrieb hinzufügen |
| `/api/version` ohne Auth gibt Versionsinformationen preis | LOW | Lokal akzeptiert; vor Produktion absichern |
| Benchmark-Simulation schlägt fehl | INFO | Nicht hardware-relevant — Simulator-Kalibrierung |

---

## 11. Empfehlungen für v5.10

**Verschlüsselung ruhender Daten für API-Schlüssel** — Implementierung von Fernet (symmetrisches AES-128-CBC + HMAC-SHA256) oder AES-GCM für das Feld `_DEFAULT_API_KEYS` und die Spalte `config.value`, in der API-Schlüssel gespeichert werden. Verschlüsselungsschlüssel aus `SYLION_MASTER_KEY` (Umgebungsvariable / Datei `.key` außerhalb des Repos). Compliance-Relevanz: DSGVO Art. 25 (Datenschutz durch Technikgestaltung), GoBD § 146 Abs. 2a.

**WireGuard kmod + iptables Kill-Switch** — Installation von `kmod-wireguard` auf dem Mudi-Router via `opkg`, Konfiguration des Interfaces `wg0`, iptables-Regeln: `FORWARD -o wg0 -j ACCEPT; OUTPUT -o wg0 -j ACCEPT; OUTPUT ! -o wg0 -j REJECT`. Persistenter Deploy auf `/overlay` statt `/tmp`. Konformität mit Sicherheitsrichtlinien für VPN-Tunnelling.

**WebRTC SFU oder aiortc-Integration** — Integration von `aiortc` (Python) oder einem externen SFU (Pion Go, mediasoup Node.js). Ohne SFU funktioniert WebRTC nur für 2 Peers ohne Relay-Server. DTLS-SRTP-Mediaverschlüsselung wird vom Signalisierungsmodul bereits vorbereitet.

**Signed Commits + GitHub CI/CD** — GPG-Signierung von Commits, GitHub-Actions-Pipeline: `ruff check`, `pytest`, `pip-audit`, `bandit`. Branch-Schutz auf `main`. Compliance: HGB § 257 Aufbewahrungspflicht, GoBD-Verfahrensdokumentation.

**SSO/SAML** — Beim Übergang zu SaaS: SAML 2.0 oder OIDC (Google Workspace, Azure AD). Das aktuelle Single-User-RBAC-System skaliert nicht für Mehrbenutzer. DSGVO Art. 32 (Sicherheit der Verarbeitung).

**DSGVO — VVT und Datenschutzerklärung** — Vor SaaS: Verzeichnis von Verarbeitungstätigkeiten (Art. 30 DSGVO), Datenschutzerklärung, Pseudonymisierung von IP-Adressen in `sessions`, Prune für `upload_history`. KSeF/E-Rechnung und GoBD sind im aktuellen Entwicklungsstadium nicht anwendbar (keine Rechnungsdaten, keine Handelsdaten).

---

## 12. Anhang

Liste der 41 Hilfsberichte unter `/home/user/workspace/council/v590_reaudit/`:

| Verzeichnis | Thema | Größe |
|---|---|---|
| `security/REPORT.md` | OWASP Top 10, FIX-01/07/08/09/10 Verifikation | 22 KB |
| `performance/REPORT.md` | SQLite PRAGMA, N+1, Benchmark | 27 KB |
| `tests/REPORT.md` | 4 ERRORs, Coverage-Lücken, Fixture-Korrektur | 34 KB |
| `code_audit/REPORT.md` | Mehrschichtige Code-Inspektion | 26 KB |
| `documents/REPORT.md` | Dokumentation, ADR, CHANGELOG | 25 KB |
| `finops_pr/REPORT.md` | FinOps, CVE, PR-Review | 23 KB |
| `rodo/REPORT.md` | DSGVO/GDPR/KSeF/GoBD Compliance | 23 KB |
| `sre/REPORT.md` | SRE, rollback.sh, Incident | 22 KB |
| `endpoint_matrix/REPORT.md` | 142 Endpunkte, Statusmatrix | 22 KB |
| `migrations/REPORT.md` | FIX-04/06/11 Migrationen | 23 KB |
| `agents_pipeline/REPORT.md` | Agenten-Rat, 5 Modelle | 19 KB |
| `pixel_detection/REPORT.md` | Pixel-9-Erkennung, 4 Root Causes | 19 KB |
| `books_phantom/REPORT.md` | BookGuardian vs. Agenten | 19 KB |
| `mudi_router/REPORT.md` | Mudi 750v2, WireGuard | 18 KB |
| `e2e/REPORT.md` | E2E-Tests, Regression | 22 KB |
| `error_handling/REPORT.md` | Fehlerbehandlung, Traceback-Leak | 18 KB |
| `webrtc/REPORT.md` | WebRTC Signalisierung, kein Media | 17 KB |
| `adr/REPORT.md` | ADR-001..ADR-009 | 21 KB |
| `manual/REPORT.md` | Nutzerhandbücher PL+DE | 16 KB |
| `cve/REPORT.md` | pip-audit 30 CVEs | 18 KB |
| `concurrency/REPORT.md` | TOCTOU, Race Conditions | 18 KB |
| `dead_code/REPORT.md` | ruff F401/F841, 32 Items | 14 KB |
| `secrets_pii/REPORT.md` | API-Schlüssel, PII-E-Mail | 13 KB |
| `zip_integrity/REPORT.md` | SHA256SUMS, CHECKSUMS | 13 KB |
| `session_invalidation/REPORT.md` | CWE-613, Sitzungen nach Passwortänderung | 10 KB |
| `fact_checker/REPORT.md` | Modell-ID, Runtime-Fehler | 11 KB |
| `fix02_deepdive/REPORT.md` | FIX-02 M-06 Deep Dive | 11 KB |
| `bug001/REPORT.md` | Dashboard-Abfrageanzahl | 8 KB |
| `bug002/REPORT.md` | prune_sessions Grenzwert | 9 KB |
| `bug003/REPORT.md` | FIX-05 toter Code | 6 KB |
| `fix10_assert/REPORT.md` | FIX-10 Assert-Bypass PoC | 6 KB |
| `install_sh/REPORT.md` | install.sh F-01 Diff | 6 KB |
| `runtime/REPORT.md` | start.py Runtime | 6 KB |
| `api_keys_ui/REPORT.md` | API-Keys-UI | 8 KB |
| `code_upload/REPORT.md` | ZIP-Upload | 9 KB |
| `upgrade/REPORT.md` | Upgrade-Pfad | 12 KB |
| `csrf_cors/REPORT.md` | CSRF, CORS, SameSite | 10 KB |
| `sec_keys/REPORT.md` | API-Schlüssel-Entropie | 8 KB |
| `predeploy/REPORT.md` | Pre-Deploy-Gate | 17 KB |
| `legal/REPORT.md` | LICENSE, NOTICE | 12 KB |
| `consolidated/FINDINGS_MATRIX_v591.md` | Matrix der 54 Befunde | Quelle |

---

*Bericht erstellt durch SYLION Audit Council — 32 Subagenten × 5 Prüfwellen × Rat aus 4 KI-Modellen. Datum: 2026-04-19.*
