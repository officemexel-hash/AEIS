# Benutzerhandbuch — SYLION v5.9.2

| Feld             | Wert                                           |
|------------------|------------------------------------------------|
| **Version**      | 5.9.2 (*Mega-Audit-Patch*)                     |
| **Datum**        | 2026-04-19                                     |
| **Kontakt**      | support@sylion.example                         |
| **Dokumentation**| docs/ · FAQ_DE.md · TROUBLESHOOTING_PL.md     |

---

## Inhaltsverzeichnis

1. [Einführung](#1-einführung)
2. [Installation](#2-installation)
3. [Erster Start](#3-erster-start)
4. [Dashboard — Überblick](#4-dashboard--überblick)
5. [Projekt hochladen und Pipeline starten](#5-projekt-hochladen-und-pipeline-starten)
6. [Diagnostik v2 — SYL-*-Codes](#6-diagnostik-v2--syl--codes)
7. [Feature Flags](#7-feature-flags)
8. [HumanGate](#8-humangate)
9. [API-Schlüssel rotieren](#9-api-schlüssel-rotieren)
10. [Geräte-Provisioning](#10-geräte-provisioning)
11. [Buch 3.4 und Rebase](#11-buch-34-und-rebase)
12. [Monitoring und Alerts](#12-monitoring-und-alerts)
13. [Kosten und LLM Tier Routing](#13-kosten-und-llm-tier-routing)
14. [Backup und Rollback](#14-backup-und-rollback)
15. [FAQ](#15-faq)
16. [Troubleshooting](#16-troubleshooting)
17. [Incident Response](#17-incident-response)
18. [Compliance (DSGVO, KSeF, GoBD, RODO)](#18-compliance-dsgvo-ksef-gobd-rodo)
19. [Support](#19-support)

---

## 1. Einführung

### Was ist SYLION?

SYLION ist eine lokale KI-Pipeline für Code-Audits, Sicherheitsanalysen und Entwicklungsunterstützung. Die Anwendung läuft **ausschließlich auf Ihrem Rechner** — keine Daten verlassen Ihr System ohne Ihr Wissen.

**Architektur:** 48 KI-Agenten, koordiniert durch einen einheitlichen Orchestrator. Vier KI-Modelle (Claude Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro) arbeiten parallel als „Council" — jede wichtige Entscheidung wird von allen vier Modellen gleichzeitig beraten.

**Typische Anwendungsfälle:**
- Code-Audits — Sicherheit (OWASP Top 10), Qualität, Performance
- Automatisches Review von Pull Requests mit HTML-Bericht
- Generierung technischer Dokumentation
- Analyse von Abhängigkeiten, technischen Schulden und CVEs im Lockfile
- ML-Pipeline mit Halluzinationsvalidierung durch Phantom v3

### Für wen?

- **Entwickler** — automatischer Audit vor Merge / PR
- **Architekten** — Review von Architekturentscheidungen (ADR)
- **SRE / DevOps** — LLM-Kostenmonitoring, Alerting, Grafana-Dashboards
- **Compliance** — DSGVO Art. 30, BDSG, GoBD, KSeF

### Version und Anforderungen

| Element | Anforderung |
|---|---|
| SYLION-Version | 5.9.2 |
| Python | ≥3.11 (3.12 empfohlen) |
| RAM | min. 8 GB |
| Festplatte | min. 2 GB freier Speicherplatz |
| System | Linux, macOS, Windows 10/11 |
| Verbindung | Internet (Abhängigkeiten + KI-API) |
| argon2-cffi | ≥23.1.0 (hard requirement) |
| aiohttp | ≥3.10.11 (neu ab v5.9.2) |

---

## 2. Installation

### 2.1 Linux / macOS

```bash
# SYLION herunterladen (git oder ZIP-Archiv)
git clone https://github.com/your-org/sylion.git
cd sylion

# Installer starten
chmod +x install.sh
./install.sh
```

`install.sh` führt automatisch folgende Schritte aus:
1. Python-Version prüfen (min. 3.11)
2. Virtuelle Python-Umgebung anlegen (`venv/`)
3. Abhängigkeiten installieren (`pip install -r requirements-lock.txt`)
4. `.env`-Datei aus `.env.example` generieren
5. SQLite-Datenbank initialisieren in `~/sylion/sylion.db` (WAL-Modus)
6. Backup-Verzeichnis `~/sylion/backups/` anlegen

Erwartete Abschlussmeldung:
```
[SYLION] Install complete. v5.9.2 ready.
[SYLION] Next step: edit .env with your API keys, then run: python dashboard/start.py
```

### 2.2 Windows

```bat
REM SYLION herunterladen (git oder ZIP)
git clone https://github.com/your-org/sylion.git
cd sylion

REM Installer starten
install.bat
```

`install.bat` führt dieselben Schritte wie das Linux-Skript durch, angepasst an Windows-Pfade und -Konventionen.

### 2.3 Docker

```bash
# Vollständiger Stack (SYLION + Prometheus + Grafana + Caddy)
docker compose up -d

# Nur SYLION ohne Monitoring
docker compose up -d sylion
```

`docker-compose.yml` startet:
- `sylion` — Container auf Port `8421` (intern `127.0.0.1`)
- `caddy` — Reverse Proxy mit TLS, Port `443`
- `prometheus` — Metriken-Scraping, Port `9090`
- `grafana` — Dashboards, Port `3000`

**Umgebungsvariablen für Docker:**
```bash
GRAFANA_ADMIN_PASSWORD=ihr_passwort     # Erforderlich
SYLION_FORWARDED_ALLOW_IPS=172.17.0.1  # Für Docker-Netzwerk
```

### 2.4 Installationsverifikation

```bash
python --version                                          # Python 3.12.x ✓
python -c "import argon2; print('argon2-cffi:', argon2.__version__)"
python -c "import aiohttp; print('aiohttp:', aiohttp.__version__)"
python -c "import fastapi; print('fastapi:', fastapi.__version__)"
```

Bei Fehlern: Vollständige Fehlerliste unter [docs/TROUBLESHOOTING_PL.md](./TROUBLESHOOTING_PL.md), Probleme 9 und 15.

---

## 3. Erster Start

### 3.1 `.env`-Datei konfigurieren

Öffnen Sie `.env` im Editor und tragen Sie Ihre API-Schlüssel ein:

```ini
# API-Schlüssel (mindestens einer erforderlich)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
PERPLEXITY_API_KEY=pplx-...

# Sicherheit
SESSION_COOKIE_SECURE=1          # 1 = Produktion, 0 = Localhost-Entwicklung
SYLION_LOGIN_MAX_ATTEMPTS=10     # Max. Login-Versuche

# Optional
SYLION_HEALTH_CHECK_V2=true      # Diagnostik v2 (standardmäßig aktiv)
SYLION_FORWARDED_ALLOW_IPS=127.0.0.1  # Trusted Proxy IP
```

Sie können SYLION auch ohne alle API-Schlüssel starten — Modelle ohne Schlüssel werden im Council als `OFFLINE` markiert.

### 3.2 Server starten

```bash
python dashboard/start.py
```

Erwartete Konsolenausgabe:
```
[SYLION] v5.9.2 starting on http://localhost:8421
[SYLION] Setup token: XXXX-XXXX-XXXX-XXXX
[SYLION] DB: /home/<user>/sylion/sylion.db (WAL, v4)
[SYLION] Agents loaded: 48
[SYLION] Council: Claude Opus 4.7 | Sonnet 4.6 | GPT-5.4 | Gemini 3.1 Pro
[SYLION] Health check v2: 82 codes active
```

**Kopieren Sie den Setup-Token** — er wird im nächsten Schritt benötigt. Ab v5.9.1 bleibt der Token über Server-Neustarts hinaus erhalten.

### 3.3 Bootstrap-Wizard — 6 Schritte

Öffnen Sie Ihren Browser und navigieren Sie zu `http://localhost:8421/setup`.

#### Schritt 1: Token-Verifikation

Fügen Sie den Setup-Token aus der Konsole in das Feld „Setup Token" ein. Klicken Sie auf „Verifizieren".

#### Schritt 2: Administrator-Passwort setzen

- Mindestens 12 Zeichen
- Empfohlen: Buchstaben + Ziffern + Sonderzeichen
- Passwort wird mit Argon2id gehasht — kein Klartext-Zugriff möglich

#### Schritt 3: API-Schlüssel konfigurieren

Das Dashboard ermöglicht das Eintragen oder Ändern von API-Schlüsseln. Schlüssel werden in SQLite mit `secret=1` gespeichert (nach dem Speichern im UI nicht mehr angezeigt). Details zur Rotation: [Abschnitt 9](#9-api-schlüssel-rotieren).

#### Schritt 4: Council-Verifikation

SYLION sendet eine Testanfrage an jedes Modell. Modelle ohne Schlüssel oder nicht erreichbar werden als `OFFLINE` markiert.

#### Schritt 5: Gerät einrichten (optional)

Falls Sie ein Pixel 9 und einen Mudi-Router besitzen, verbinden Sie das Gerät per USB und klicken Sie auf „Gerät erkennen". Details: [Abschnitt 10](#10-geräte-provisioning).

#### Schritt 6: Abschluss

Klicken Sie auf „Zum Dashboard". Sie werden zum Login weitergeleitet.

---

## 4. Dashboard — Überblick

### 4.1 Navigation

Das Dashboard besteht aus **14 Panels**, zugänglich über die linke Navigationsleiste:

#### Überblick
| Panel | Beschreibung |
|---|---|
| **Dashboard** | KPIs, 6 Guard-Status (farbig), letzte Events, Systemzustand |
| **Monitoring** | Pipeline Stages (8 Stufen), aktive Runs, Geräte |

#### Steuerung
| Panel | Beschreibung |
|---|---|
| **Human Gate** | Entscheidungen (approve/reject/defer/escalate), SSE Echtzeit |
| **Runs Center** | Run-Liste, start/retry/cancel, Artefakte, Details |
| **Artefakte** | Dateien aus Runs: SHA-256, Kategorien |
| **Agenten** | Liste der 48 Agenten, Aktionen (start/stop/restart), Status |

#### Buch
| Panel | Beschreibung |
|---|---|
| **Baseline Center** | Baselines (Draft→Review→Approved→Promoted), Diff, Vergleiche |

#### Operationen
| Panel | Beschreibung |
|---|---|
| **Geräte** | Pixel 9 / Laptop / Mudi-Router, Health Check, Deploy, Benchmark |
| **Streaming** | Audio/Video-Metriken, Bitrate, Latenz, Anomalien |
| **Security** | Budget-Verstöße, Drift-Events, Anomalien |

#### Konfiguration
| Panel | Beschreibung |
|---|---|
| **Prompt Registry** | Prompts (Draft→Review→Active→Archived), Editor |
| **Feature Flags** | Modul-Toggle, Kill Switch, Audit-Log |
| **Einstellungen** | API-Schlüssel, Pipeline/Streaming/Netzwerk/Sicherheitskonfiguration |
| **Benutzer** | RBAC, Erstellen/Bearbeiten, Rollen |

### 4.2 Benutzerrollen (RBAC)

| Rolle | Berechtigungen |
|---|---|
| `owner` | Vollzugriff, kritische Flags ändern, Benutzer löschen |
| `architect` | Agenten, Baseline, ADR verwalten |
| `operator` | Pipeline starten, Deploy, Provisioning |
| `auditor` | Nur Lesen aller Daten, Berichte exportieren |
| `viewer` | Lesen von Dashboard und Runs Center |

### 4.3 Hauptpanel — Kennzahlen

- **6 Guards:** BudgetGuard, LoopGuard, HumanGate, FactChecker, ClaimProvenance, FileVerification — jeweils grün (OK) / gelb (WARN) / rot (ERROR/CRITICAL)
- **Letzte Events** — chronologische Liste der letzten 20 Pipeline-Ereignisse
- **KPIs:** Anzahl aktiver Agenten, letzter Run (Zeit, Status), DB-Gesundheit

---

## 5. Projekt hochladen und Pipeline starten

### 5.1 Projekt hochladen

1. Klicken Sie auf **Runs Center** in der Navigation
2. Klicken Sie auf **„Neuer Run"**
3. Quelle wählen:
   - **ZIP hochladen** — Archiv übertragen (max. 100 MB)
   - **Lokaler Pfad** — Pfad auf dem SYLION-Server angeben
   - **Git URL** — Repository klonen (erfordert Netzwerkzugang)
4. Klicken Sie auf **„Hochladen"**

Nach dem Upload startet `run_codebase_audit()` automatisch (Auto-Run, behoben mit P0-007).

### 5.2 Auto-Run vs. manueller Run

**Auto-Run:** Standardmäßig aktiviert. Nach abgeschlossenem Upload startet die Pipeline sofort.

**Manueller Run:** Deaktivieren Sie Auto-Run in den Einstellungen (`PIPELINE_AUTO_RUN=false`) oder im Run-Panel vor dem Hochladen. Starten Sie dann manuell über **„Run starten"** im Runs Center.

### 5.3 Run-Statuswerte

| Status | Beschreibung |
|---|---|
| `queued` | Wartet auf freien Slot |
| `running` | Aktiv, Sub-Agenten arbeiten |
| `waiting_gate` | Gestoppt bei HumanGate |
| `completed` | Erfolgreich abgeschlossen |
| `failed` | Fehler — Logs prüfen |
| `cancelled` | Vom Benutzer abgebrochen |

### 5.4 Pipeline-Stufen (8 Stages)

| Stage | Beschreibung |
|---|---|
| 1. Pre-flight | Umgebungs-, Abhängigkeits- und DB-Verifikation |
| 2. Upload | Empfang und Verifikation der Projektdateien |
| 3. Baseline | Vergleich mit vorherigem Baseline |
| 4. Agents | Ausführung der 48 Agenten |
| 5. Council | Beratung der 4 Modelle, Konsensbildung |
| 6. Artifacts | Berichte und Patches generieren |
| 7. Security | OWASP-Audit, CVE-Scan |
| 8. Finalize | Ergebnisse speichern, Health History aktualisieren |

### 5.5 Run-Artefakte

Nach Abschluss des Runs stehen bereit:
- `REPORT.md` / `REPORT.html` — Audit-Bericht
- `FIX_MAP.md` — Behebungsplan mit Prioritäten P0–P3
- Code-Patches (falls generiert)
- Agenten-Logs (SHA-256 verifiziert)

---

## 6. Diagnostik v2 — SYL-*-Codes

### 6.1 Diagnostik aufrufen

**Über Dashboard:** Klicken Sie auf das Herz-Symbol (♥) oben rechts — ein 16-Tab-Diagnosepanel mit Auto-Refresh (30 s) öffnet sich.

**Über API:**
```bash
# Vollständiger Gesundheitsbericht
curl -H "Authorization: Bearer TOKEN" http://localhost:8421/api/health/v2

# Gefiltert nach Kategorie
curl http://localhost:8421/api/health/v2?category=security

# Verlauf
curl http://localhost:8421/api/health/v2/history
```

### 6.2 Berichtsstruktur

```json
{
  "code": "SYL-SEC-001",
  "check": "csrf_all_endpoints",
  "severity": "ok",
  "message": "71/71 endpoints protected",
  "timestamp": "2026-04-19T12:00:00Z"
}
```

**Schweregrade:**
| Level | Beschreibung | Aktion |
|---|---|---|
| `ok` | Alles in Ordnung | Keine |
| `warn` | Warnung, nicht kritisch | Beobachten |
| `error` | Fehler, Handlungsbedarf | Bald beheben |
| `critical` | Kritisch, blockierend | Sofort beheben |
| `n/a` | Nicht zutreffend | Keine |

### 6.3 SYL-*-Code-Kategorien

| Präfix | Kategorie | Codes |
|---|---|---|
| `SYL-PIX-` | Pixel-9-Erkennung und Provisioning | 001–010 |
| `SYL-DB-` | SQLite, WAL, Migrationen | 011–020 |
| `SYL-SEC-` | Sicherheit (CSRF, Rate Limit, Cookies) | 021–035 |
| `SYL-COST-` | FinOps, LLM-Budget | 036–045 |
| `SYL-NET-` | WireGuard, Mudi, DNS | 046–055 |
| `SYL-PERF-` | Performance, PRAGMA-Caching | 056–065 |
| `SYL-COMP-` | Compliance DSGVO/GoBD/KSeF | 066–082 |

### 6.4 Häufige Alerts und Behebung

**SYL-PIX-001: Pixel 9 not detected**
- ADB prüfen: `adb devices` — erscheint das Gerät als `device`?
- Falls `unauthorized`: Bildschirm entsperren, USB-Debugging-Dialog akzeptieren
- Falls unsichtbar: ADB-Treiber neu installieren (Windows) oder `udev`-Regeln prüfen (Linux)

**SYL-DB-011: WAL file > 500 MB**
- Checkpoint: `GET /api/health/v2/checkpoint`
- Aktive Verbindungen prüfen: Security-Panel im Dashboard

**SYL-SEC-021: Rate limit bypass detected**
- Caddy-Konfiguration prüfen: `X-Forwarded-For` muss korrekt weitergeleitet werden
- `SYLION_FORWARDED_ALLOW_IPS` in `.env` verifizieren

---

## 7. Feature Flags

### 7.1 Flags verwalten

Feature Flags ermöglichen **Laufzeit-Toggles** — Module aktivieren/deaktivieren ohne Neustart.

**Über Dashboard:** Klicken Sie auf **Feature Flags**. Die Tabelle zeigt: Key, Beschreibung, Kategorie, Status (AN/AUS), Kritisch.

**Über API:**
```bash
# Alle Flags abrufen
GET /api/feature-flags

# Flag ändern
PUT /api/feature-flags/CSRF_PROTECTION
Content-Type: application/json
{"enabled": true}

# Flag erstellen (nur owner)
POST /api/feature-flags

# Flag löschen (nur owner, nicht-kritisch)
DELETE /api/feature-flags/CUSTOM_FLAG
```

### 7.2 Eingebaute Flags

| Key | Standard | Beschreibung |
|---|---|---|
| `CSRF_PROTECTION` | `true` | CSRF-Schutz — kritisch |
| `RATE_LIMITING` | `true` | Rate Limiting beim Login |
| `PIPELINE_AUTO_RUN` | `true` | Auto-Run nach Upload |
| `HEALTH_CHECK_V2` | `true` | Diagnostik v2 |
| `HUMAN_GATE_SSE` | `true` | SSE Echtzeit für HumanGate |
| `BOOK_GUARDIAN` | `true` | Schutz von Buch 3.4 |
| `PHANTOM_V3` | `true` | Halluzinationserkennung |
| `PIPELINE_EMERGENCY_STOP` | `false` | Kill Switch — stoppt alles |

### 7.3 Kill Switch — PIPELINE_EMERGENCY_STOP

Im Incident-Fall (z. B. ausgenutzte Schwachstelle, unkontrollierte LLM-Kosten):

```bash
# Dashboard: Feature Flags → PIPELINE_EMERGENCY_STOP → Toggle AN
# oder API:
POST /api/feature-flags/kill-switch
Content-Type: application/json
{"reason": "CVE-2026-xxxxx exploited, stopping pipeline"}
```

Wirkung: Alle aktiven Runs werden in <5 Sekunden gestoppt. Eintrag in `audit_log`. Erfordert Rolle `owner`.

---

## 8. HumanGate

### 8.1 Wann erscheint HumanGate?

HumanGate blockiert die Pipeline und wartet auf eine menschliche Entscheidung in folgenden Situationen:

| Auslöser | GateLevel | Beschreibung |
|---|---|---|
| Start der vollständigen Pipeline | CRITICAL | Genehmigung des Starts erforderlich |
| Agent erfordert Gate | REVIEW | 19 von 48 Agenten haben `requires_human_gate: true` |
| Halluzinationen erkannt (Phantom v3) | CRITICAL | Bericht enthält Inkonsistenzen |
| Fehlende Artefakte (Stage 6.5) | CRITICAL | Pipeline kann nicht fortfahren |
| CRITICAL-Finding im Security-Audit | CRITICAL | Befund erfordert Entscheidung |
| Unbehandelter Agentenfehler | CRITICAL | Eskalation |
| OEM-Bootloader-Unlock (Pixel) | CRITICAL | Nicht rückgängig zu machen |
| Agent-Schleife erkannt | CRITICAL | Loop Guard ausgelöst |

### 8.2 Entscheidungsoptionen

| Option | Beschreibung |
|---|---|
| **Approve** | Pipeline wird fortgesetzt |
| **Approve Once** | Einzelgenehmigung für CRITICAL (Begründung erforderlich) |
| **Reject** | Run wird mit erfasstem Grund gestoppt |
| **Defer** | Zurückgestellt — Gate wartet bis max. TTL |
| **Escalate** | Weiterleitung an anderen Benutzer (erfordert `owner`) |

### 8.3 Consensus-Anzeige

Falls Council-Ergebnisse aller 4 Modelle vorliegen, zeigt HumanGate den Konsens:
- **3/4 oder 4/4** — starker Konsens, Entscheidung empfohlen
- **2/2** — kein Konsens — weitere Analyse erforderlich

### 8.4 SSE Echtzeit (ab v5.9.2)

Entscheidungen aus dem Dashboard-UI erreichen den CLI-Orchestrator über SSE + SQLite-Polling-Bridge (behobener Defekt TF05). Der Orchestrator fragt die Datenbank alle 2 Sekunden ab.

---

## 9. API-Schlüssel rotieren

### 9.1 Über Dashboard (empfohlen)

1. Klicken Sie auf **Einstellungen** in der Navigation
2. Abschnitt **API-Schlüssel** — 6 Anbieter: Anthropic, OpenAI, Google, Perplexity, xAI, DeepSeek
3. Stiftsymbol neben dem zu ändernden Schlüssel anklicken
4. Neuen Schlüssel eingeben und **„Speichern"** klicken
5. SYLION verifiziert den Schlüssel per Test-Request: `VALID` / `INVALID`

### 9.2 Über `.env`-Datei

```bash
# Server stoppen
pkill -f "start.py" || true

# .env bearbeiten
nano .env
# Ändern: ANTHROPIC_API_KEY=sk-ant-neuer_schluessel

# Neu starten
python dashboard/start.py
```

### 9.3 Sicherheitshinweise

- Schlüssel werden in SQLite mit `secret=1` gespeichert — im UI nach dem Speichern nicht mehr sichtbar
- Schlüssel niemals im Code oder Git hinterlegen — `.gitignore` schließt `.env` aus
- In Produktionsumgebungen: Vault oder AWS Secrets Manager erwägen

---

## 10. Geräte-Provisioning

### 10.1 Pixel 9 — Vorbereitung

SYLION v5.9.2 unterstützt die vollständige Pixel-9-Familie:
`Pixel 9 | Pixel 9 Pro | Pixel 9 Pro XL | Pixel 9 Pro Fold | Pixel 9a`

**Voraussetzungen:**
- Android Debug Bridge (ADB) installiert und im PATH verfügbar
- Pixel 9 per USB verbunden
- USB-Debugging aktiviert (Entwickleroptionen → USB-Debugging)

**Geräteerkennung:**
```bash
adb devices
# Erwartetes Ergebnis: <serial>  device

adb shell getprop ro.product.model
# Erwartetes Ergebnis: Pixel 9 (oder Variante)
```

Bei Status `unauthorized`: Bildschirm entsperren und „USB-Debugging zulassen?" bestätigen.

### 10.2 Provisioning über Dashboard

1. **Geräte** in der Navigation öffnen
2. **„Geräte erkennen"** klicken — SYLION fragt ADB ab
3. Pixel 9 erscheint in der Liste mit Modell und Seriennummer
4. **„Provisionieren"** klicken

**Hinweis:** OEM-Bootloader-Unlock ist **unwiderruflich** — SYLION zeigt einen CRITICAL-HumanGate mit Warnung. Bestätigung erfordert Rolle `owner`.

### 10.3 Mudi-Router + WireGuard

**Voraussetzungen:** GL.iNet Mudi (GL-E750) mit OpenWRT, SSH-Zugang.

**WireGuard-Konfiguration (neu in v5.9.2):**

```bash
# Schlüsselpaar erzeugen
python wg_config_generator.py --generate-keys --peer mudi

# Konfiguration vorab ansehen (dry-run)
python wg_config_generator.py --dry-run --peer mudi

# Konfiguration per SSH auf Mudi übertragen
python wg_config_generator.py --push --peer mudi --host 192.168.8.1
```

Der Prozess:
1. Schlüsselpaar erzeugen (`wg genkey | wg pubkey`)
2. `wg0.conf` mit Peer-Parametern aufbauen
3. Konfiguration per SSH auf Mudi übertragen (`/etc/wireguard/wg0.conf`)
4. Handshake nach 10 Sekunden verifizieren
5. Kill-Switch aktivieren: `iptables`-Regeln blockieren Traffic außerhalb von `wg0`

---

## 11. Buch 3.4 und Rebase

### 11.1 Was ist Buch 3.4?

Buch 3.4 ist die Verhaltensspezifikation der SYLION-Pipeline — ein Regelwerk, das von allen Agenten eingehalten werden muss. Book Guardian überwacht, dass das Buch nicht ohne Autorisierung verändert wird.

### 11.2 Zustand prüfen

```bash
# Synchronisationsstatus prüfen
python book_guardian.py --check

# Detaillierter Bericht
python book_guardian.py --check --verbose
```

Ausgabe:
```
[BookGuardian] Buch 3.4: OK (0 Drift, Baseline: promoted-2026-04-15)
```

### 11.3 Rebase

Bei Drift (>5 Zeilen Abweichung vom Promoted-Baseline):

```bash
# Vorschau (dry-run)
python book_guardian.py --rebase --dry-run

# Rebase durchführen
python book_guardian.py --rebase
```

**Wichtig:** Rebase erfordert HumanGate-Genehmigung (`GateLevel=REVIEW`). Die Pipeline wird bis zur Entscheidung pausiert.

### 11.4 Baseline-Lebenszyklus

```
Draft → Review → Approved → Promoted
```

Nur Baselines mit Status `Promoted` werden von Book Guardian und als Pipeline-Referenz verwendet.

---

## 12. Monitoring und Alerts

### 12.1 Prometheus

SYLION exportiert Metriken unter `GET /api/metrics` (Prometheus-Format).

Wichtige Metriken:
| Metrik | Beschreibung |
|---|---|
| `sylion_request_count_total` | Anfragen pro Endpunkt |
| `sylion_request_duration_seconds` | Latenz (Histogram) |
| `llm_cost_usd_total` | LLM-Gesamtkosten in USD |
| `llm_calls_total` | Anzahl Modell-API-Aufrufe |
| `sylion_wal_size_mb` | SQLite WAL-Dateigröße |
| `sylion_disk_free_gb` | Freier Festplattenspeicher |
| `db_connections_active` | Aktive SQLite-Verbindungen |
| `human_gate_pending` | Ausstehende HumanGate-Entscheidungen |

### 12.2 Grafana

Vier eingebaute Dashboards (nach `docker compose up -d grafana`):

| Dashboard | Inhalt |
|---|---|
| **System Overview** | Request Rate, Fehlerrate 4xx/5xx, Latenz P50/95/99, DB, WAL, Disk |
| **LLM Cost** | Gesamtkosten, €/h, Monatsschätzung, Kosten nach Anbieter |
| **Security** | Auth-Fehler, CSRF-Verstöße, Rate-Limit-Treffer |
| **Pipeline Health** | Stage-Dauern, Agenten-Erfolgsraten, HumanGate-Warteschlange |

Zugang: `http://localhost:3000` (Login: `admin` / Wert von `GRAFANA_ADMIN_PASSWORD`)

### 12.3 AlertManager-Konfiguration

| Alert | Bedingung | Kanal |
|---|---|---|
| `SylionHighErrorRate` | Fehlerrate >5% für 5 min | PagerDuty |
| `SylionLLMCostSpike` | LLM-Kosten >$50/h | Slack |
| `SylionWALGrowth` | WAL >500 MB | E-Mail |
| `SylionDBDown` | Keine SQLite-Antwort | PagerDuty CRITICAL |
| `SylionDiskLow` | Freier Speicher <1 GB | Slack WARNING |

---

## 13. Kosten und LLM Tier Routing

### 13.1 Kostenverfolgung

SYLION protokolliert jeden Modellaufruf mit: Anbieter, Modell, Benutzer, Kosten (USD), Zeitstempel.

Zugang:
- Dashboard → **LLM Cost** (Grafana)
- `GET /api/observability/costs` — Rohdaten JSON
- `GET /api/metrics` — Prometheus-Metriken

### 13.2 LLM Tier Routing

Tier Routing leitet Anfragen automatisch an kostengerechte Modelle weiter:

| Tier | Modelle | Einsatz |
|---|---|---|
| **Tier 1 (Premium)** | Opus 4.7, GPT-5.4 | Finale Council-Runden, Security-Audit, CRITICAL-Entscheidungen |
| **Tier 2 (Balanced)** | Sonnet 4.6, Gemini 3.1 Pro | Reguläre Council-Arbeit, Review |
| **Tier 3 (Economy)** | Lokale Modelle (Ollama) | Vorfilterung, Dokumentation, Logs |

Konfiguration in `.env`:
```ini
LLM_TIER_ROUTING=true
LLM_TIER1_BUDGET_USD=50.0
LLM_TIER3_MODEL=ollama/llama3.2
```

Potenzielle Einsparungen bei vollständiger Optimierung: ~$110–310/Monat.

### 13.3 BudgetGuard

BudgetGuard stoppt die Pipeline, wenn das tägliche Kostenlimit überschritten wird:
- Konfiguration: `BUDGET_GUARD_DAILY_USD` in `.env` (Standard: `10.0`)
- HumanGate-Alert bei 80% des Budgets
- Hard Stop bei 100% — Pipeline gestoppt bis Folgetag oder manuelles Reset

---

## 14. Backup und Rollback

### 14.1 Automatisches Backup

SYLION erstellt automatische Backups der SQLite-Datenbank:
- **Bei jedem Start** — `~/sylion/backups/sylion-<version>-<timestamp>.db.bak`
- **Täglich** — Geplantes Backup um 02:00 Uhr
- **Vor jeder DB-Migration** — WAL-Checkpoint + atomares Backup

Backup-Status prüfen:
```bash
ls -lh ~/sylion/backups/
# oder:
curl http://localhost:8421/api/health | jq .backup_age_hours
```

### 14.2 Manuelles Backup (WAL-sicher)

```bash
# Methode 1: SQLite .backup API (empfohlen, WAL-sicher)
sqlite3 ~/sylion/sylion.db ".backup ~/sylion/backups/manual-$(date +%Y%m%dT%H%M%S).db"

# Methode 2: cp (nur wenn SYLION gestoppt)
cp ~/sylion/sylion.db ~/sylion/backups/manual-$(date +%Y%m%dT%H%M%S).db
```

### 14.3 WAL-Checkpoint

Bei WAL-Dateigröße >500 MB (Alert SYL-DB-011):

```bash
# Über API
curl -X POST http://localhost:8421/api/health/v2/checkpoint \
  -H "Authorization: Bearer TOKEN"

# Direkt in SQLite (Server gestoppt)
sqlite3 ~/sylion/sylion.db "PRAGMA wal_checkpoint(FULL);"
```

### 14.4 Rollback

`rollback.sh` (327 Zeilen) — vollständige Rollback-Prozedur mit WAL-Integritätsprüfung:

```bash
# Vorschau (dry-run)
./rollback.sh --dry-run

# Vollständiger Rollback
./rollback.sh

# Nur Code zurücksetzen (DB-Migrationen behalten)
git checkout v5.9.1
pip install -r requirements-lock.txt
python dashboard/start.py
```

**Staged Restore:** Backup wird zunächst in `sylion.db.restore.tmp` kopiert, dort `PRAGMA integrity_check` ausgeführt. Nur bei Ergebnis `ok` wird die Produktionsdatenbank ersetzt.

Exit-Codes: `0` = Erfolg · `1` = Kein Backup · `2` = Integritätsfehler · `3` = Keine Berechtigung

Vollständige Dokumentation: [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md) · [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md)

---

## 15. FAQ

Vollständiges FAQ: [docs/FAQ_DE.md](./FAQ_DE.md)

**Häufige Fragen:**

**F: Wie ändere ich API-Schlüssel nach der Installation?**
A: Einstellungen → API-Schlüssel → Stiftsymbol. Oder `.env` bearbeiten und neu starten. Details: [Abschnitt 9](#9-api-schlüssel-rotieren).

**F: Pixel 9 wird nicht erkannt — was tun?**
A: `adb devices` prüfen. Bei `unauthorized`: Bildschirm entsperren und USB-Debugging-Dialog bestätigen. Vollständige Liste der 10 Ursachen: [FAQ_DE.md](./FAQ_DE.md).

**F: Setup-Token abgelaufen oder verloren.**
A: Ab v5.9.1 ist der Token dauerhaft. Server-Logs prüfen: `journalctl -u sylion -n 50 | grep "Setup token"`.

**F: Pipeline hängt im Status `waiting_gate`.**
A: Human Gate im Dashboard öffnen und Entscheidung treffen. Falls HumanGate nicht sichtbar: SSE-Verbindung prüfen (Abschnitt 8.4).

**F: Wie deaktiviere ich ein Modul ohne Neustart?**
A: Feature Flags verwenden — [Abschnitt 7](#7-feature-flags).

---

## 16. Troubleshooting

Vollständige Liste: [docs/TROUBLESHOOTING_PL.md](./TROUBLESHOOTING_PL.md)

| Problem | Diagnose | Lösung |
|---|---|---|
| Server startet nicht | `ModuleNotFoundError: dashboard` | Aus Projektverzeichnis starten: `cd sylion && python dashboard/start.py` |
| HTTP 500 beim Login | Fehler v5.9.1 oder älter | Upgrade auf v5.9.2 (P0-002 behoben) |
| Leere DB nach `--seed` | Fehler v5.9.1 oder älter | Upgrade auf v5.9.2 (P0-001 behoben) |
| argon2-cffi fehlt | `RuntimeError: Argon2id backend required` | `pip install argon2-cffi>=23.1.0` |
| WireGuard Handshake fehlt | Schlüssel nicht übereinstimmend | `python wg_config_generator.py --regenerate-keys --peer mudi` |
| WAL >1 GB | Kein Checkpoint | `sqlite3 sylion.db "PRAGMA wal_checkpoint(FULL);"` |

---

## 17. Incident Response

Vollständige Prozedur: [docs/sre/INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)

**Wichtige Diagnose-Befehle:**

```bash
# Service-Status
systemctl status sylion

# Caddy-Logs (Reverse Proxy)
journalctl -u caddy -n 200

# SYLION-Logs
journalctl -u sylion -n 100

# Health Check
curl http://localhost:8421/api/health
# Erwartet: {"version":"5.9.2","db_ok":true,"backup_age_hours":<N>}

# Metriken
curl http://localhost:8421/api/metrics

# DB-Diagnose
sqlite3 ~/sylion/sylion.db "PRAGMA integrity_check; PRAGMA user_version;"

# On-Call-Kontakt
echo $SYLION_ONCALL_CONTACT
```

**Incident-Schweregrade:**
- **P1 (Critical):** DB-Korruption, Auth-Bypass, PII-Leak → HumanGate CRITICAL + PagerDuty
- **P2 (High):** Service down, WAL-Korruption → SRE + Slack
- **P3 (Medium):** Degradierte Performance, Alert ausgelöst → Beobachten + E-Mail

---

## 18. Compliance (DSGVO, KSeF, GoBD, RODO)

### 18.1 DSGVO / BDSG

SYLION v5.9.2 implementiert Anforderungen der DSGVO Art. 5, 17, 30, 32 sowie BDSG §26, §35:

- **Verzeichnis der Verarbeitungstätigkeiten (VVT):** [docs/RODO_COMPLIANCE.md](./RODO_COMPLIANCE.md)
- **DSFA v5.9.2:** [docs/DPIA_v592.md](./DPIA_v592.md)
- **Aufbewahrung audit_log:** 365 Tage (`SYLION_AUDIT_RETENTION_DAYS`)
- **Aufbewahrung sessions:** 30 Tage (`SYLION_SESSION_RETENTION_DAYS`)
- **Minimum für severity=critical:** 30 Tage (nicht unterschreitbar)
- **Löschrecht (Art. 17):** `DELETE /api/auth/me/data` — Konto + Daten löschen, SLA 30 Tage
- **Datenexport (Art. 20):** `GET /api/auth/me/export` — JSON mit Benutzerdaten

**Übermittlungen in die USA:** OpenAI, Anthropic, Google, Perplexity — abgedeckt durch AV-Vertrag Art. 28 + SCC Modul 2 (2021). Details: `RODO_COMPLIANCE.md` Abschnitt 7.

### 18.2 GoBD + HGB §257

**Aufbewahrungsfristen:**
- Finanzunterlagen: 10 Jahre (HGB §257, AO §147)
- Handelsbücher, Inventare, Jahresabschlüsse: 10 Jahre
- Belege, Handelsbriefe: 6 Jahre
- Technische Umsetzung (v5.11+): Immutable Storage, keine UPDATE/DELETE auf Rechnungszeilen

Dokumentation: [docs/GOBD_RETENTION.md](./GOBD_RETENTION.md)

### 18.3 BDSG §26 — Beschäftigtendaten

`audit_log` mit `actor=username` unterliegt BDSG §26. Bei Verarbeitung von Beschäftigtendaten: Betriebsrat einbinden (BetrVG §87) und DSB/IOD konsultieren. Details: `RODO_COMPLIANCE.md` Abschnitt HIGH-05.

### 18.4 KSeF — Polnisches E-Rechnungssystem

SYLION v5.9.2 **enthält kein Rechnungsmodul** — KSeF ist nicht anwendbar. Geplant: v5.11 (Rechnungs-Ingestionsmodul mit FA(2)-XML-Export).

### 18.5 E-Rechnung (XRechnung / ZUGFeRD)

Anwendbarkeit auf SYLION v5.9.2: **N/A** — SYLION verarbeitet operative Pipeline-Daten, keine Geschäftsrechnungen.

Geplant (v5.11+): ZUGFeRD-PDF-Generierung, XRechnung-XML, GoBD-konforme 10-Jahres-Aufbewahrung.

### 18.6 AI Act (EU 2024/1689)

SYLION als Code-Audit-Tool eingestuft als KI-System mit geringem Risiko. Transparenzdokumentation gem. Art. 13: [docs/RODO_COMPLIANCE.md](./RODO_COMPLIANCE.md) Abschnitt 9.

---

## 19. Support

**Dokumentation:**
- FAQ: [docs/FAQ_DE.md](./FAQ_DE.md)
- Troubleshooting: [docs/TROUBLESHOOTING_PL.md](./TROUBLESHOOTING_PL.md)
- Incident Response: [docs/sre/INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)
- Release Notes: [docs/RELEASE_NOTES_v5.9.2_DE.md](./RELEASE_NOTES_v5.9.2_DE.md)
- Rollback: [docs/ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md)

**Kontakt:**
- E-Mail: support@sylion.example
- On-Call SRE: `$SYLION_ONCALL_CONTACT` (definiert in `.env`)

---

*SYLION v5.9.2 · Benutzerhandbuch · Datum: 2026-04-19*
*Quellen: FIX_MAP_v5.9.2.md · Mega-Audit 49 Sub-Agenten · docs/council_v590/*
