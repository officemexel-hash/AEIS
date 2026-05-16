# Fehlerbehebung — SYLION v5.9.0 (Deutsch)

15 häufige Probleme und ihre Lösungen.

---

## Problem 1: Port 8421 ist bereits belegt

**Fehlermeldung:**

```
OSError: [Errno 98] Address already in use: ('0.0.0.0', 8421)
```

**Lösung:**

Suchen Sie den Prozess, der den Port belegt, und beenden Sie ihn:

```bash
# Linux / macOS
lsof -i :8421
# Ergebnis: Die Spalte PID enthält die Prozessnummer
kill -9 <PID>

# Windows
netstat -ano | findstr :8421
taskkill /PID <PID> /F
```

Alternativ ändern Sie den Port in `.env`:

```ini
PORT=9000
```

Starten Sie den Server anschließend neu.

---

## Problem 2: Login gibt Fehler 429 zurück

**Symptom:** Die Login-Seite zeigt `429 Too Many Requests` oder `Rate limit exceeded`.

**Ursache:** Der Rate Limiter hat 5 oder mehr fehlgeschlagene Login-Versuche innerhalb von 5 Minuten erkannt.

**Lösung:**

1. Warten Sie **10 Minuten** nach dem letzten Versuch.
2. Stellen Sie sicher, dass Sie das richtige Passwort eingeben (überprüfen Sie die Feststelltaste).
3. Falls Sie das Passwort vergessen haben, setzen Sie es nach der Wartezeit zurück (siehe FAQ, Frage 2).

Für sofortige Entsperrung (z. B. beim Testen):

```bash
# Löschen Sie die Rate-Limit-Statusdatei (falls separat gespeichert)
rm ~/sylion/rate_limit_state.json
# Starten Sie dann den Server neu
```

---

## Problem 3: Datenbankmigration fehlgeschlagen

**Fehlermeldung:**

```
MigrationError: Migration to version X.X.X failed
```

**Lösung:**

1. Starten Sie den Server nicht neu, ohne zuvor den Datenbankstatus geprüft zu haben.
2. Stellen Sie das Backup wieder her (wird automatisch vor jeder Migration erstellt):

```bash
ls ~/sylion/backups/
cp ~/sylion/backups/sylion_pre_migration_XXXXXX.db ~/sylion/sylion.db
```

3. Prüfen Sie die Logs, um die Fehlerursache zu verstehen.
4. Bei wiederholten Problemen lesen Sie `docs/ROLLBACK_PLAN.md`.

---

## Problem 4: Modul argon2 fehlt

**Fehlermeldung:**

```
ModuleNotFoundError: No module named 'argon2'
```

**Lösung:**

```bash
pip install argon2-cffi
```

Falls Sie eine virtuelle Umgebung verwenden, stellen Sie sicher, dass diese aktiviert ist:

```bash
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
pip install argon2-cffi
```

---

## Problem 5: SQLite — Datenbank gesperrt

**Fehlermeldung:**

```
sqlite3.OperationalError: database is locked
```

**Ursachen und Lösungen:**

1. **Eine andere SYLION-Instanz läuft.** Suchen und beenden Sie alle Prozesse:

```bash
ps aux | grep sylion   # Linux/macOS
tasklist | findstr sylion   # Windows
```

2. **Ein anderes Programm (z. B. DB Browser for SQLite) hat die Datenbank geöffnet.** Schließen Sie es.

3. **Die WAL-Datei wurde nicht korrekt geschlossen.** Erzwingen Sie einen Checkpoint:

```bash
sqlite3 ~/sylion/sylion.db "PRAGMA wal_checkpoint(FULL);"
```

4. Wenn das Problem wiederholt auftritt, prüfen Sie die Dateiberechtigungen:

```bash
ls -la ~/sylion/sylion.db
chmod 600 ~/sylion/sylion.db
```

---

## Problem 6: API-Schlüssel abgelehnt (Fehler 401 beim Council)

**Symptom:** Das Council gibt `401 Unauthorized` oder `Invalid API key` zurück.

**Lösung:**

1. Navigieren Sie zu **Dashboard → Einstellungen → API-Schlüssel**.
2. Prüfen Sie, ob der Schlüssel korrekt kopiert wurde (keine Leerzeichen am Anfang oder Ende).
3. Verifizieren Sie den Schlüssel direkt auf der Website des Anbieters (Anthropic Console, OpenAI Platform, Google AI Studio).
4. Falls der Schlüssel abgelaufen oder widerrufen wurde — generieren Sie einen neuen.

---

## Problem 7: Seite lädt nicht (SYLION antwortet nicht auf http://localhost:8421)

**Mögliche Ursachen:**

1. Der Server läuft nicht — prüfen Sie die Konsole, starten Sie `python -m sylion serve`.
2. Sie verwenden den falschen Port — prüfen Sie den Wert `PORT` in `.env`.
3. Eine Firewall blockiert den Port — fügen Sie eine Ausnahme hinzu:

```bash
# Linux (UFW)
sudo ufw allow 8421/tcp

# macOS — prüfen Sie Systemeinstellungen → Datenschutz & Sicherheit → Firewall
```

4. Der Browser verwendet einen gecachten Fehler — versuchen Sie, die Seite im privaten Modus zu öffnen.

---

## Problem 8: Agent gibt leeres Ergebnis oder None zurück

**Symptom:** Der Pipeline schließt erfolgreich ab, aber der Bericht eines bestimmten Agenten ist leer.

**Mögliche Ursachen:**

1. Der Agent unterstützt den angegebenen Eingabe-Datentyp nicht.
2. Das AI-Modell hat eine leere Antwort zurückgegeben (z. B. bei zu langem Kontext).
3. Fehler in der Agentenlogik.

**Lösung:**

1. Prüfen Sie die Agenten-Logs in der Konsole — suchen Sie nach `[WARN]`- oder `[ERROR]`-Zeilen.
2. Reduzieren Sie die Größe der Eingabedaten (z. B. teilen Sie große Dateien in kleinere Abschnitte auf).
3. Bei einem eigenen Agenten — prüfen Sie die Implementierung der Methode `run()`.

---

## Problem 9: Installation fehlgeschlagen — pip-Fehler

**Fehlermeldung:**

```
ERROR: Could not install packages due to an OSError
```

**Lösung:**

```bash
# pip aktualisieren
python -m pip install --upgrade pip

# Installation mit --user versuchen
pip install --user -r requirements.txt

# Unter Linux möglicher Berechtigungsfehler im Verzeichnis:
chmod -R 755 venv/
```

---

## Problem 10: Council arbeitet sehr langsam

**Symptom:** Die Antwort des Councils dauert länger als 60 Sekunden.

**Mögliche Ursachen:**

1. Das Netzwerk ist langsam oder überlastet.
2. Die API-Modelle haben aktuell hohe Latenz (prüfen Sie: status.anthropic.com, status.openai.com).
3. Die Eingabedaten sind sehr umfangreich (>10.000 Token).

**Lösung:**

1. Prüfen Sie den Status der API-Anbieter.
2. Reduzieren Sie den Kontextumfang.
3. Deaktivieren Sie vorübergehend langsamere Modelle unter **Dashboard → Einstellungen → Council**.
4. Erhöhen Sie den Timeout in `.env`:

```ini
COUNCIL_TIMEOUT_SECONDS=120
```

---

## Problem 11: Kein Speicherplatz auf dem Datenträger

**Fehlermeldung:**

```
OSError: [Errno 28] No space left on device
```

**Lösung:**

1. Prüfen Sie die Festplattennutzung:

```bash
df -h ~
du -sh ~/sylion/
```

2. Alte Logs und Backups können viel Speicher belegen:

```bash
# Logs löschen, die älter als 30 Tage sind
find ~/sylion/logs/ -name "*.log" -mtime +30 -delete

# Alte Backups entfernen (die letzten 5 behalten)
ls -t ~/sylion/backups/ | tail -n +6 | xargs -I{} rm ~/sylion/backups/{}
```

---

## Problem 12: Importfehler — falsche Python-Version

**Fehlermeldung:**

```
SyntaxError: f-strings with = are only available in Python 3.8+
# oder
ImportError: cannot import name 'TypeAlias' from 'typing'
```

**Lösung:** SYLION erfordert Python **3.12 oder neuer**.

```bash
python --version   # muss 3.12.x oder neuer anzeigen
```

Falls eine ältere Version installiert ist, installieren Sie Python 3.12 von python.org oder über einen Paketmanager:

```bash
# Ubuntu / Debian
sudo apt install python3.12

# macOS (Homebrew)
brew install python@3.12

# Windows — laden Sie den Installer von python.org herunter
```

---

## Problem 13: Human Gate wird nicht angezeigt

**Symptom:** Der Pipeline durchläuft eine Stage mit Human Gate, ohne anzuhalten.

**Mögliche Ursachen:**

1. Das Human Gate ist für diese Stage in der Pipeline-Konfiguration deaktiviert.
2. Der Agent hat festgestellt, dass keine Überprüfung erforderlich ist.

**Lösung:**

1. Prüfen Sie die Pipeline-Konfiguration — Dashboard → Pipeline → bearbeiten Sie die gewünschte Stage und aktivieren Sie `require_human_gate: true`.
2. Wenn das Human Gate aktiviert ist, aber keine Benachrichtigung angezeigt wird — prüfen Sie die Logs und stellen Sie sicher, dass der Browser aktiv ist (Benachrichtigungen funktionieren über WebSocket).

---

## Problem 14: Ausgabe enthält Ersatzzeichen (?)

**Symptom:** In Berichten oder Agenten-Antworten erscheinen Fragezeichen oder Rechtecke statt Sonderzeichen.

**Ursache:** Zeichenkodierungsproblem.

**Lösung:**

Prüfen Sie die Locale-Einstellungen des Systems:

```bash
# Linux
locale
# UTF-8 setzen falls nicht vorhanden:
export LANG=de_DE.UTF-8
export LC_ALL=de_DE.UTF-8
```

Fügen Sie in `.env` hinzu:

```ini
PYTHONIOENCODING=utf-8
```

---

## Problem 15: Fehler "Permission denied" beim Ausführen von install.sh

**Fehlermeldung:**

```
bash: ./install.sh: Permission denied
```

**Lösung:**

```bash
chmod +x install.sh
./install.sh
```

Unter Windows: Klicken Sie mit der rechten Maustaste auf `install.bat` → "Als Administrator ausführen" (falls die Umgebung dies erfordert).

---

## Problem nicht gefunden?

Prüfen Sie [FAQ_DE.md](FAQ_DE.md) oder lesen Sie die Server-Logs. Kontakt: robert.skorupka@icloud.com

<!-- v5.9.1 TROUBLESHOOTING additions -->
# Fehlerbehebung — SYLION v5.9.1 (Deutsch) — Ergänzungen

Diese Datei enthält **5 zusätzliche Fehlerbehebungs-Szenarien** (Nummern 16–20)
als Ergänzung zu `TROUBLESHOOTING_DE.md` (bisherige Probleme 1–15).
Alle Szenarien sind spezifisch für Version v5.9.1.

Diese Einträge sollen nach Problem 15 in `TROUBLESHOOTING_DE.md` eingefügt werden.

---

## Problem 16: 500 Internal Server Error bei der ersten Anfrage an /api/auth/login

**Fehlermeldung:**

```
HTTP/1.1 500 Internal Server Error
{"detail":"Internal server error"}
```

Der Fehler tritt nur beim ersten Start oder nach dem Löschen der Datenbankdatei auf.
Die Server-Logs enthalten einen Eintrag wie:

```
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  ...
  sqlite3.OperationalError: no such table: users
```

**Ursache:** Race Condition bei der Datenbankinitialisierung — `init_db()` wird asynchron
aufgerufen und ist möglicherweise noch nicht abgeschlossen, wenn die erste HTTP-Anfrage
eintrifft. Die Tabelle `users` existiert zu diesem Zeitpunkt noch nicht.

Betrifft Installationen, bei denen:
- Die Datenbankdatei `~/sylion/sylion.db` nicht vorhanden ist (Neuinstallation).
- Die Datenbankdatei manuell gelöscht wurde (zum Zurücksetzen).
- Die Anwendung mit einem `DB_PATH` gestartet wird, der auf eine nicht vorhandene Datei zeigt.

**Lösung:**

### Schritt 1 — Datenbank manuell initialisieren, bevor der Server gestartet wird

```bash
cd ~/sylion/sylion-pipeline
source .venv/bin/activate

python - <<'EOF'
import sys
sys.path.insert(0, 'dashboard')
from db import init_db
init_db()
print("Datenbank erfolgreich initialisiert.")
EOF
```

### Schritt 2 — Datenbankdatei prüfen

```bash
sqlite3 ~/sylion/sylion.db ".tables"
# Erwartete Tabellen: users, sessions, pipelines, audit_log, ...
```

Falls die Tabellen sichtbar sind — Server starten:

```bash
python dashboard/start.py
```

### Schritt 3 — Verifizierung

```bash
curl -s http://localhost:8421/api/health
# Erwartet: {"status":"ok","version":"5.9.1","db":"connected",...}
```

**Langfristige Lösung:** Das Problem wird in v5.9.2 durch synchrone `init_db()`-Initialisierung
im FastAPI-Startup-Hook behoben. Bis dahin immer manuell `init_db()` ausführen, nachdem
die Datenbank gelöscht wurde.

---

## Problem 17: 403 Forbidden nach Deployment hinter Reverse Proxy (nginx / Caddy)

**Fehlermeldung:**

```
HTTP/1.1 403 Forbidden
{"detail":"Forbidden: IP not in trusted proxy list"}
```

Der Fehler tritt auf, nachdem SYLION hinter nginx oder Caddy betrieben wird. Das Dashboard
ist nicht erreichbar — jede Anfrage wird mit 403 beantwortet.

SYLION-Logs enthalten:

```
WARNING: Request from untrusted proxy 203.0.113.45 — rejected
```

**Ursache:** Ab v5.9.1 erfordert SYLION `proxy_headers=True` und prüft, ob die
Proxy-Adresse in der Liste `SYLION_FORWARDED_ALLOW_IPS` enthalten ist. Der Standardwert
ist `127.0.0.1` (nur lokaler Proxy). Die externe IP von nginx/Caddy oder eines Load
Balancers ist nicht enthalten.

**Lösung:**

### Schritt 1 — IP des Proxys zur Umgebungsvariable hinzufügen

In der Datei `.env`:

```ini
# Einzelner Proxy auf derselben Maschine:
SYLION_FORWARDED_ALLOW_IPS=127.0.0.1

# Proxy auf einem anderen Host (z. B. Load Balancer auf 10.0.0.5):
SYLION_FORWARDED_ALLOW_IPS=127.0.0.1,10.0.0.5

# Cloudflare oder CDN (CIDR-Bereich):
SYLION_FORWARDED_ALLOW_IPS=127.0.0.1,103.21.244.0/22,103.22.200.0/22
```

### Schritt 2 — Reverse-Proxy-Konfiguration prüfen

**Caddy** (empfohlen) — das Caddyfile muss Header weiterleiten:

```
sylion.example.com {
    reverse_proxy 127.0.0.1:8421 {
        header_up X-Forwarded-For {remote_host}
        header_up X-Real-IP {remote_host}
    }
}
```

**nginx** — den Abschnitt `location` prüfen:

```nginx
location / {
    proxy_pass http://127.0.0.1:8421;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Host $host;
}
```

### Schritt 3 — SYLION-Server neu starten

```bash
sudo systemctl restart sylion
```

### Schritt 4 — Rate Limiter verifizieren (Test gemäß F-002)

```bash
# 6 fehlgeschlagene Login-Versuche senden
for i in {1..6}; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://sylion.example.com/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"falschespasswort"}')
  echo "Versuch $i: HTTP $CODE"
done
# Erwartet: Versuche 1-5 → 401, Versuch 6 → 429
```

Falls Versuch 6 den Code 429 zurückgibt — der Rate Limiter funktioniert korrekt mit Proxy.

---

## Problem 18: ImportError: cannot import name 'run_codebase_audit'

**Fehlermeldung:**

```
ImportError: cannot import name 'run_codebase_audit' from 'sylion.agents.auditor'
```

oder

```
AttributeError: module 'sylion.agents.auditor' has no attribute 'run_codebase_audit'
```

Der Fehler tritt auf beim Versuch, die Code-Audit-Pipeline zu starten, oder beim Import
des Moduls `auditor` in externen Skripten.

**Ursache:** Die Funktion `run_codebase_audit` existiert in v5.9.0, aber ihre Signatur
wurde in v5.9.1 geändert und erfordert den Patch aus v5.9.2 für den vollständigen Betrieb.
Das Problem betrifft folgende Situationen:
- Ein externes Skript oder Plugin importiert `run_codebase_audit` direkt.
- Alte Pipeline-Konfigurationsdateien aus v5.8.x sind installiert.
- Dateien verschiedener Versionen werden gemischt verwendet (ZIP v5.9.0 + Dateien aus v5.9.1).

**Lösung:**

### Schritt 1 — Installierte Version prüfen

```bash
python -c "import sys; sys.path.insert(0,'dashboard'); import version; print(version.__version__)"
# oder:
curl http://localhost:8421/api/health | python -m json.tool
```

### Schritt 2 — Sicherstellen, dass alle Dateien aus v5.9.1 stammen

```bash
# Gemischte Versionen prüfen
grep -r "run_codebase_audit" sylion/ --include="*.py" -l
```

Alle Verweise sollten auf `sylion/agents/auditor.py` zeigen.

### Schritt 3 — Temporäre Umgehung (bis zum Patch in v5.9.2)

Wenn die Funktion aus einem externen Skript aufgerufen wird, den Ersatz verwenden:

```python
# Statt:
from sylion.agents.auditor import run_codebase_audit
run_codebase_audit(path="/my/code")

# Verwenden:
from sylion.agents.auditor import CodebaseAuditorAgent
agent = CodebaseAuditorAgent()
import asyncio
result = asyncio.run(agent.run({"path": "/my/code"}))
```

### Schritt 4 — Bei Pipeline-Konfigurationen aus v5.8.x

Pipeline-Konfigurationsdateien aktualisieren:

```bash
# Alte Konfigurationen suchen
grep -r "run_codebase_audit" ~/sylion/ --include="*.yaml" --include="*.json" -l

# Manuell auf die neue API umstellen oder in Dashboard löschen und neu erstellen
```

**Status:** Der vollständige Patch wird in v5.9.2 geliefert. Verfolgen Sie
`docs/FIX_MAP_v5.9.1.md` unter Position F-028 (geplant).

---

## Problem 19: dashboard/sylion_dashboard.db hat 0 Bytes

**Symptom:**

```bash
ls -la ~/sylion/
# -rw-r--r-- 1 user user    0 Apr 19 10:00 sylion_dashboard.db
```

oder in den Logs:

```
ERROR: Database file is empty (0 bytes) — possible init_db failure
sqlite3.DatabaseError: file is not a database
```

Das Dashboard lädt, aber die Pipeline-Historie, Agenten-Daten und Einstellungen sind leer.
Jeder Neustart setzt die Daten zurück.

**Ursache:** Fehler in `init_db()` — unter bestimmten Startbedingungen (z. B. fehlende
Schreibberechtigung im Verzeichnis, voller Datenträger bei der Initialisierung, unterbrochener
Prozess) wird die Datenbankdatei erstellt (touch), aber nicht korrekt mit dem SQLite-Schema
initialisiert. Ergebnis: 0-Byte-Datei statt einer korrekten Datenbank.

**Lösung:**

### Schritt 1 — Berechtigungen und freien Speicherplatz prüfen

```bash
# Verzeichnisberechtigungen prüfen
ls -la ~/sylion/
# Das Verzeichnis muss vom Server-Benutzer beschreibbar sein

# Verfügbaren Speicher prüfen
df -h ~
# Minimum: 100 MB frei
```

### Schritt 2 — 0-Byte-Datei löschen und Datenbank neu initialisieren

```bash
# Server stoppen
kill $(lsof -t -i :8421) 2>/dev/null || true

# Beschädigte Datei löschen
rm ~/sylion/sylion_dashboard.db
rm -f ~/sylion/sylion_dashboard.db-wal ~/sylion/sylion_dashboard.db-shm

# Datenbank manuell initialisieren
cd ~/sylion/sylion-pipeline
source .venv/bin/activate
python - <<'EOF'
import sys
sys.path.insert(0, 'dashboard')
from db import init_db
init_db()
print("init_db() erfolgreich abgeschlossen.")
EOF

# Dateigröße prüfen
ls -lh ~/sylion/sylion_dashboard.db
# Erwartet: mehrere Kilobytes (nicht 0 Bytes)
```

### Schritt 3 — Daten aus Backup wiederherstellen (falls vorhanden)

```bash
# Verfügbare Backups auflisten
ls -lt ~/sylion/backups/ | head -5

# Letztes Backup wiederherstellen
cp ~/sylion/backups/sylion_pre_migration_XXXXXX.db ~/sylion/sylion_dashboard.db
sqlite3 ~/sylion/sylion_dashboard.db "PRAGMA integrity_check;"
# Erwartet: ok
```

### Schritt 4 — Server starten und verifizieren

```bash
python dashboard/start.py &
sleep 3
curl http://localhost:8421/api/health
# Erwartet: {"status":"ok","db":"connected",...}
```

**Vorbeugung:** Automatisches tägliches Backup via Cron einrichten:

```bash
# Täglich um 02:00
0 2 * * * sqlite3 ~/sylion/sylion_dashboard.db ".backup '~/sylion/backups/sylion_$(date +\%Y\%m\%d).db.bak'" 2>/dev/null
```

---

## Problem 20: fstat: No such file or directory SETUP_TOKEN.txt

**Fehlermeldung:**

```
[SYLION] ERROR: Cannot read SETUP_TOKEN.txt: [Errno 2] No such file or directory: 'SETUP_TOKEN.txt'
```

oder die Seite `/setup` zeigt:

```
Setup token not found. Please check server logs or restart the server.
```

Der Fehler tritt bei der Erstinstallation oder nach einem Datenbank-Reset auf.

**Ursache:** Beim ersten Start generiert SYLION einen SETUP_TOKEN und speichert ihn in der
Datei `SETUP_TOKEN.txt` im Arbeitsverzeichnis (aktuelles Verzeichnis beim Start von
`python dashboard/start.py`). Wird der Server aus einem anderen Verzeichnis als
`sylion-pipeline/` gestartet, wird die Datei am falschen Ort erstellt und kann bei
der nächsten Anfrage nicht gefunden werden.

**Lösung:**

### Schritt 1 — Server aus dem richtigen Verzeichnis starten

```bash
# IMMER aus dem Verzeichnis sylion-pipeline/ starten
cd ~/sylion/sylion-pipeline   # oder /opt/sylion/sylion-pipeline
python dashboard/start.py
```

### Schritt 2 — Generierten Token suchen

```bash
# SETUP_TOKEN.txt an möglichen Speicherorten suchen
find ~ -name "SETUP_TOKEN.txt" 2>/dev/null
find /opt -name "SETUP_TOKEN.txt" 2>/dev/null
find /tmp -name "SETUP_TOKEN.txt" 2>/dev/null
```

Falls die Datei gefunden wird — Token auslesen:

```bash
cat /pfad/zu/SETUP_TOKEN.txt
```

### Schritt 3 — Token aus den Server-Logs auslesen

Der Token wird beim Start immer in die Logs geschrieben:

```bash
# Falls Datei-Logging aktiviert ist
grep "Setup token" ~/sylion/logs/*.log

# Oder direkt in der Konsole, in der der Server läuft
# Suchen Sie nach der Zeile: [SYLION] Setup token: XXXX-XXXX-XXXX-XXXX
```

### Schritt 4 — Token neu generieren (falls nicht abrufbar)

```bash
# Server stoppen
kill $(lsof -t -i :8421) 2>/dev/null || true

# Alten Token und Datenbank löschen (oder nur Token, falls Daten wichtig sind)
rm -f ~/sylion/sylion-pipeline/SETUP_TOKEN.txt

# Beim nächsten Start wird der Token neu generiert
cd ~/sylion/sylion-pipeline
python dashboard/start.py
# Token aus der ausgegebenen Zeile kopieren: [SYLION] Setup token: ...
```

### Schritt 5 — Setup abschließen

Öffnen Sie `http://localhost:8421/setup` im Browser, fügen Sie den Token ein und
legen Sie das Administrator-Passwort fest.

**Hinweis:** Der Token ist einmalig — nach erfolgreicher Passwortvergabe wird die Datei
`SETUP_TOKEN.txt` automatisch gelöscht. Falls die Seite `/setup` meldet „already configured"
— das Passwort wurde bereits gesetzt. Verwenden Sie `/login` oder setzen Sie das Passwort
gemäß FAQ, Frage 2 zurück.

---

## Problem nicht gefunden?

Prüfen Sie [FAQ_DE.md](FAQ_DE.md), [FAQ_DE_v591_additions.md](FAQ_DE_v591_additions.md)
oder lesen Sie die Server-Logs. Kontakt: support@sylion.example

---

*Ergänzungen zu TROUBLESHOOTING_DE.md für SYLION v5.9.1 — 2026-04-19*
*Szenarien spezifisch für v5.9.1, identifiziert in: audit_LATEST/18_user_manual.md*
