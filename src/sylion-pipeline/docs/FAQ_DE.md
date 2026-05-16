# FAQ — SYLION v5.9.0 (Deutsch)

20 häufig gestellte Fragen.

---

## 1. Wie ändert man API-Schlüssel?

Navigieren Sie zu **Dashboard → Einstellungen → API-Schlüssel**. Die Schlüssel können direkt im Formular bearbeitet werden — nach dem Speichern verwendet SYLION sofort die neuen Werte, ein Neustart ist nicht erforderlich. Die Schlüssel werden lokal in der Datei `.env` gespeichert und verlassen Ihren Rechner nicht.

Alternativ können Sie die Datei `.env` manuell bearbeiten:

```ini
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

Nach manueller Bearbeitung der `.env`-Datei ist ein Server-Neustart erforderlich.

---

## 2. Wie setzt man das Administrator-Passwort zurück?

SYLION speichert die Anmeldedaten in der SQLite-Datenbank. Zum Zurücksetzen des Passworts:

1. Stoppen Sie den Server (Ctrl+C in der Konsole, in der `python -m sylion serve` läuft).
2. Löschen Sie die Datenbank:

```bash
rm ~/sylion/sylion.db
```

3. Starten Sie den Server erneut. SYLION zeigt einen neuen Setup Token an.
4. Navigieren Sie zu `http://localhost:8421/setup` und setzen Sie ein neues Passwort.

**Hinweis:** Das Löschen der Datenbank entfernt die gesamte Pipeline-Historie und alle Agenten-Daten. Erstellen Sie zuvor ein Backup, falls Sie diese Daten benötigen.

---

## 3. Was sind Pipeline-Stages?

Eine Stage (Phase) ist ein einzelner Schritt im Audit-Pipeline. Jede Stage startet eine bestimmte Gruppe von Agenten und erzeugt einen Bericht. Beispiele:

- **collect** — Abrufen der Eingabedaten (Code, Konfiguration)
- **analyze** — Statische und semantische Analyse
- **review** — Bewertung durch das Council
- **report** — Erstellung des Abschlussberichts

Stages werden sequenziell ausgeführt. Sie können sie konfigurieren, überspringen oder eigene hinzufügen über den Bereich **Pipeline** im Dashboard.

---

## 4. Wie funktioniert das Human Gate?

Das Human Gate ist ein Haltepunkt im Pipeline, bei dem SYLION auf Ihre Entscheidung wartet, bevor es zur nächsten Stage übergeht. Es erscheint automatisch, wenn ein Agent feststellt, dass ein Ergebnis menschliche Überprüfung erfordert (z. B. eine Entscheidung über die Refaktorisierung eines kritischen Moduls).

Im Dashboard erscheint eine Benachrichtigung mit einer Frage und den Schaltflächen **"Genehmigen"** / **"Ablehnen"** / **"Bearbeiten und genehmigen"**. Der Pipeline wird nach Ihrer Entscheidung fortgesetzt.

Das Human Gate kann für einzelne Stages in den Pipeline-Einstellungen deaktiviert werden.

---

## 5. Werden die Daten verschlüsselt?

**At-rest (auf dem Datenträger):** Nein. Die SQLite-Datenbank (`~/sylion/sylion.db`) ist nicht verschlüsselt. SYLION ist für den lokalen Einzelbenutzerbetrieb konzipiert — die Verschlüsselung at-rest liegt in der Verantwortung des Benutzers (z. B. FileVault unter macOS, BitLocker unter Windows, LUKS unter Linux).

**In-transit (im Netzwerk):** Standardmäßig nein (HTTP). Wenn Sie SYLION hinter einem Reverse Proxy (nginx, Caddy) mit TLS-Zertifikat betreiben, ist die Kommunikation verschlüsselt (HTTPS). Eine Anleitung finden Sie in der Dokumentation unter `docs/advanced/`.

Das Benutzerpasswort wird mit dem Algorithmus Argon2id gehasht und niemals im Klartext gespeichert.

---

## 6. Was ist das Council der 4 Modelle?

Das Council ist ein Mechanismus zur parallelen Ausführung von vier AI-Modellen gleichzeitig:

- **Claude Opus 4.7** (Anthropic)
- **Claude Sonnet 4.6** (Anthropic)
- **GPT-5.4** (OpenAI)
- **Gemini 3.1 Pro** (Google)

Jede Anfrage wird gleichzeitig an alle vier Modelle gesendet. Die Ergebnisse werden gesammelt und verglichen — Konsens wird hervorgehoben, Abweichungen werden markiert. Dadurch werden "blinde Flecken" einzelner Modelle vermieden.

---

## 7. Warum blockiert der Rate Limiter meine Anmeldung?

SYLION verfügt über einen integrierten Rate Limiter für den Login-Endpunkt: **5 fehlgeschlagene Versuche innerhalb von 5 Minuten** führen zu einer IP-Sperre für **10 Minuten**.

Bei Fehler `429 Too Many Requests`:

1. Warten Sie 10 Minuten.
2. Stellen Sie sicher, dass Sie das richtige Passwort eingeben.
3. Falls Sie das Passwort vergessen haben — setzen Sie es zurück (siehe Frage 2).

Die Limits können in der `.env`-Datei angepasst werden:

```ini
RATE_LIMIT_LOGIN_ATTEMPTS=5
RATE_LIMIT_LOGIN_WINDOW_SECONDS=300
RATE_LIMIT_LOGIN_BLOCK_SECONDS=600
```

---

## 8. Wie erstellt man ein Backup der Datenbank?

**Automatisches Backup:** SYLION erstellt vor jeder Schema-Migration automatisch ein Backup der Datenbank. Die Backups befinden sich unter `~/sylion/backups/`.

**Manuelles Backup:**

```bash
cp ~/sylion/sylion.db ~/backup/sylion_$(date +%Y%m%d_%H%M%S).db
```

Es wird empfohlen, die Datei regelmäßig auf ein externes Medium oder in einen Cloud-Speicher zu kopieren.

**Backup bei aktivem WAL-Modus:** Wenn der Server läuft, sollten Sie den folgenden Befehl für ein sicheres Backup verwenden:

```bash
sqlite3 ~/sylion/sylion.db ".backup ~/backup/sylion_backup.db"
```

---

## 9. Wo befinden sich die Logs?

Standardmäßig gibt SYLION Logs auf die Standardausgabe (stdout) der Konsole aus, in der der Server läuft.

Wenn die Protokollierung in eine Datei konfiguriert wurde (in `.env`):

```ini
LOG_DIR=~/sylion/logs
LOG_LEVEL=INFO
```

Die Log-Dateien befinden sich unter `~/sylion/logs/`. Format: eine Datei pro Tag, Rotation nach 30 Tagen.

Verfügbare Log-Level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Für den Normalbetrieb ist `INFO` ausreichend.

---

## 10. Wie fügt man einen eigenen Agenten hinzu?

Ein eigener Agent ist eine Python-Datei im Verzeichnis `sylion/agents/custom/`, die das Interface `BaseAgent` implementiert:

```python
from sylion.agents.base import BaseAgent

class MyAgent(BaseAgent):
    name = "my_agent"
    description = "Was dieser Agent tut"

    async def run(self, context):
        # Ihre Logik
        return {"result": "..."}
```

Nach dem Hinzufügen der Datei starten Sie den Server neu. Der neue Agent erscheint in der Liste unter der Registerkarte **Agenten**.

---

## 11. Wie ändert man den Port von 8421 auf einen anderen?

Setzen Sie in der Datei `.env`:

```ini
PORT=9000
```

Starten Sie anschließend den Server neu. Denken Sie daran, die URLs in den Browser-Tabs zu aktualisieren.

---

## 12. Funktioniert SYLION offline?

Teilweise. Die Anwendung selbst (FastAPI-Server, SQLite-Datenbank, Weboberfläche) funktioniert offline. Das Council benötigt jedoch eine Internetverbindung, um Anfragen an Anthropic, OpenAI und Google zu senden. Ohne Internet antwortet das Council nicht.

Für den vollständig offline Betrieb können lokale Modelle (Ollama oder llama.cpp) als Ersatz konfiguriert werden — Anleitung unter `docs/advanced/LOCAL_MODELS.md`.

---

## 13. Wie aktualisiert man SYLION auf eine neuere Version?

```bash
git pull origin main
./install.sh   # oder install.bat unter Windows
python -m sylion migrate
python -m sylion serve
```

Der Befehl `migrate` aktualisiert das Datenbankschema und erstellt automatisch ein Backup vor den Änderungen.

---

## 14. Wie viele Agenten laufen gleichzeitig?

Standardmäßig führt SYLION bis zu **8 Agenten parallel** aus (8 Threads). Dies kann in `.env` geändert werden:

```ini
AGENT_CONCURRENCY=8
```

Ein Wert höher als die Anzahl der CPU-Kerne bringt in der Regel keine Vorteile und kann das System verlangsamen.

---

## 15. Was tun, wenn der Pipeline im Status "running" feststeckt?

1. Überprüfen Sie die Logs in der Konsole oder unter `~/sylion/logs/` — suchen Sie nach Fehlermeldungen.
2. Versuchen Sie, den Pipeline über die Schaltfläche **"Abbrechen"** im Dashboard → Pipeline zu stoppen.
3. Falls das Abbrechen nicht funktioniert, starten Sie den Server neu (Ctrl+C, dann `python -m sylion serve`).
4. Unvollständige Pipelines erhalten nach dem Neustart den Status `failed`.

---

## 16. Wie exportiert man einen Audit-Bericht?

Klicken Sie im Dashboard → Pipeline auf einen abgeschlossenen Pipeline, und wählen Sie dann **"Bericht exportieren"**. Verfügbare Formate:

- JSON (vollständige Daten)
- Markdown (lesbarer Text)
- HTML (mit Formatierung)

Der Bericht wird im Verzeichnis `~/sylion/reports/` gespeichert oder kann direkt über den Browser heruntergeladen werden.

---

## 17. Kann man mehrere SYLION-Instanzen gleichzeitig betreiben?

Nicht empfohlen. SQLite ist nicht für mehrere gleichzeitige schreibende Prozesse aus verschiedenen Anwendungen ausgelegt. Der WAL-Modus verbessert die Situation, aber bei mehreren Instanzen können Datenbanksperrfehler auftreten.

Wenn Sie mehrere Instanzen benötigen, erwägen Sie eine Migration zu PostgreSQL (siehe `docs/advanced/POSTGRES_MIGRATION.md`).

---

## 18. Wie deaktiviert man das Council und verwendet nur ein Modell?

Setzen Sie in `.env`:

```ini
COUNCIL_ENABLED=false
COUNCIL_DEFAULT_MODEL=claude-opus-4.7
```

Alle Anfragen werden dann ausschließlich an das gewählte Modell gesendet. Dies kann auch temporär über Dashboard → Einstellungen → Council geändert werden.

---

## 19. Woher weiß ich, dass der Server korrekt läuft?

SYLION stellt einen Health-Check-Endpunkt bereit:

```bash
curl http://localhost:8421/health
```

Antwort:

```json
{
  "status": "ok",
  "version": "5.9.0",
  "build": "2026-04-19",
  "db": "connected",
  "agents": 48
}
```

Wenn `status` nicht `"ok"` ist, überprüfen Sie die Logs.

---

## 20. Wie erreicht man den technischen Support?

SYLION ist ein Single-User-Projekt für den privaten Gebrauch. Bei Problemen:

1. Lesen Sie [TROUBLESHOOTING_DE.md](TROUBLESHOOTING_DE.md).
2. Prüfen Sie die Logs (`~/sylion/logs/` oder stdout).
3. Schauen Sie im Repository unter dem Bereich Issues auf GitHub nach.
4. Direktkontakt: robert.skorupka@icloud.com

<!-- v5.9.1 FAQ additions -->
# FAQ — SYLION v5.9.1 (Deutsch) — Ergänzungen

Diese Datei enthält **7 zusätzliche FAQ-Einträge** (Nummern 21–27) als Ergänzung zu
`FAQ_DE.md` (bisherige Fragen 1–20). Alle Einträge betreffen Lücken, die im Bericht
`audit_LATEST/18_user_manual.md` für Version v5.9.1 identifiziert wurden.

Diese Fragen sollen nach Frage 20 in `FAQ_DE.md` eingefügt werden.

---

## 21. Warum kann ich mich über HTTP nicht anmelden? [Secure-Cookie]

**Frage:** Nach dem Start von SYLION ohne HTTPS öffnet sich die Anmeldeseite. Ich gebe
das richtige Passwort ein, aber nach dem Klick auf „Anmelden" wird die Seite neu geladen
und fordert erneut die Anmeldedaten. Das Dashboard öffnet sich nicht.

**Ursache:** Ab Version v5.9.1 ist das `Secure`-Flag des Session-Cookies **standardmäßig
aktiviert** (Änderung im Rahmen der Behebung von F-015). Der Browser verwirft `Secure`-Cookies,
die über eine unverschlüsselte HTTP-Verbindung übertragen werden — die Sitzung wird nicht
gespeichert und jede Anfrage gilt als nicht angemeldet.

**Lösungen (eine auswählen):**

### Option A — SYLION hinter einem Reverse Proxy mit TLS betreiben (empfohlen für Produktion)

Konfigurieren Sie Caddy oder nginx mit TLS-Zertifikat. Beispiel-Caddyfile:

```
sylion.example.com {
    reverse_proxy 127.0.0.1:8421
}
```

Caddy bezieht automatisch ein Let's-Encrypt-Zertifikat. Ausführliche Anleitung:
`docs/RUNBOOK_DEPLOY.md §3.5`.

### Option B — Secure-Flag deaktivieren (nur für lokale Tests)

Fügen Sie in die Datei `.env` ein:

```ini
SESSION_COOKIE_SECURE=0
```

Starten Sie dann den Server neu. **Hinweis:** Verwenden Sie diese Option nicht auf einem
Server, der aus einem externen Netzwerk erreichbar ist — die Sitzung wäre abhörbar.

**Überprüfung:**

```bash
curl -c /tmp/cookies.txt -b /tmp/cookies.txt \
     -X POST http://localhost:8421/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"IhrPasswort"}'
```

Bei `{"status":"ok"}` funktioniert die Anmeldung.
Bei `{"status":"error","message":"Unauthorized"}` trotz korrektem Passwort — prüfen Sie
den Wert von `SESSION_COOKIE_SECURE` in `.env`.

---

## 22. Wie rotiert man einen API-Schlüssel über das Dashboard?

**Frage:** Einer meiner API-Schlüssel (OpenAI / Anthropic / Google) ist abgelaufen oder
wurde widerrufen. Wie aktualisiere ich ihn ohne Server-Neustart?

**Antwort:**

1. Öffnen Sie **Dashboard → Einstellungen → API-Schlüssel**
   (oder `http://localhost:8421/settings/api-keys`).
2. Finden Sie die Zeile des zu ändernden Schlüssels (z. B. `OPENAI_API_KEY`).
3. Klicken Sie auf das **Bleistift-Symbol** (Bearbeiten) neben dem entsprechenden Schlüssel.
4. Fügen Sie den neuen Schlüsselwert ein — das Feld ist aus Sicherheitsgründen maskiert.
5. Klicken Sie auf **Speichern**. SYLION verwendet den neuen Schlüssel sofort,
   ohne Server-Neustart.

**Alternative Methode über die `.env`-Datei:**

```bash
# Server stoppen
kill $(lsof -t -i :8421)

# .env bearbeiten — entsprechenden Schlüssel ändern
nano .env
# z. B. OPENAI_API_KEY=sk-proj-NeuerSchlüssel...

# Server starten
python dashboard/start.py
```

**Schlüssel nach der Änderung überprüfen:**

Navigieren Sie zu **Dashboard → Council** und klicken Sie auf „Verbindung testen" beim
Modell, dessen Schlüssel Sie geändert haben. Ein grünes Symbol bestätigt die Korrektheit.

**Sicherheitshinweis (F-001):** Version v5.9.1 enthält noch hartcodierte Schlüssel in
`dashboard/db.py:1081-1086` (Behebung in v5.9.2). Vor jedem Deployment ausführen:

```bash
grep -n "sk-" dashboard/db.py
```

Falls die Ausgabe nicht leer ist — rotieren Sie die Schlüssel und entfernen Sie die
Literale aus dem Code.

---

## 23. Wie stellt man die vorherige Version nach einem fehlgeschlagenen Update wieder her? [rollback.sh]

**Frage:** Ich habe eine neue Version von SYLION installiert, aber etwas ist schiefgelaufen
(Fehler in den Logs, Dashboard antwortet nicht). Wie kehre ich zur vorherigen Version zurück?

**Antwort:**

SYLION v5.9.1 enthält ein komplett neu geschriebenes `rollback.sh` (Behebung F-004/F-005/F-006)
mit WAL-Unterstützung und Integritätsprüfung vor dem Austausch der Datenbank.

**Schritt 1 — Vorschau (Dry Run):**

```bash
./rollback.sh --dry-run
```

Zeigt an, was wiederhergestellt würde, ohne Dateien zu verändern.

**Schritt 2 — Rollback durchführen:**

```bash
# Server stoppen
sudo systemctl stop sylion
# oder: kill $(lsof -t -i :8421)

# Letztes funktionierendes Datenbank-Backup wiederherstellen
./rollback.sh

# Server starten
sudo systemctl start sylion
```

Das Skript durchsucht Backups in folgender Reihenfolge:
1. `$HOME/sylion/backups/` (Standardspeicherort von `install.sh`)
2. `./backups/`
3. `/var/backups/sylion/`

**Exit-Codes von `rollback.sh`:**

| Code | Bedeutung |
|------|-----------|
| `0` | Erfolg — Datenbank wiederhergestellt |
| `1` | Kein Backup gefunden |
| `2` | Backup beschädigt (`PRAGMA integrity_check` fehlgeschlagen) |
| `3` | Fehlende Berechtigungen oder kein Speicherplatz |

**Falls Rollback der Datenbank nicht ausreicht** (z. B. auch Anwendungsdateien beschädigt):

```bash
# Gesamtes Anwendungsverzeichnis aus der Sicherungskopie wiederherstellen
cp -a /opt/sylion.pre-v591 /opt/sylion
sudo systemctl start sylion
```

---

## 24. Was tun, wenn das Pixel 9 von SYLION nicht erkannt wird?

**Frage:** Ich habe das Google Pixel 9 per USB angeschlossen, aber SYLION zeigt das Gerät
im Panel nicht an. Was soll ich prüfen?

**Antwort:**

Probleme bei der Erkennung des Pixel 9 betreffen drei Ebenen: Linux-System (udev),
ADB-Autorisierung und den Debug-Modus des Telefons.

### Schritt 1 — udev-Regeln prüfen (Linux)

```bash
# Prüfen ob Regeln für Google vorhanden sind
ls /etc/udev/rules.d/ | grep -i android

# Falls nicht vorhanden — Regel für Pixel 9 hinzufügen (Google Vendor-ID: 18d1)
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"' \
     | sudo tee /etc/udev/rules.d/51-android.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Trennen und wieder verbinden Sie danach das Telefon.

### Schritt 2 — ADB autorisieren

```bash
# Prüfen ob ADB das Gerät erkennt
adb devices
```

Erwartetes Ergebnis: `SERIENNUMMER    device`

Bei `unauthorized`:
1. Auf dem Telefon erscheint ein Dialog „Diesem Computer USB-Debugging erlauben?".
2. Aktivieren Sie „Immer von diesem Computer erlauben" und tippen Sie auf OK.
3. Erneut ausführen: `adb devices`.

### Schritt 3 — USB-Debugging aktivieren

Auf dem Telefon:
1. **Einstellungen → Über das Telefon → Software-Informationen**.
2. Tippen Sie 7× auf **Build-Nummer** — „Sie sind jetzt Entwickler" erscheint.
3. **Einstellungen → System → Entwickleroptionen**.
4. Aktivieren Sie **USB-Debugging**.

### Schritt 4 — USB-Verbindungstyp prüfen

Das Pixel 9 setzt standardmäßig den Modus „Nur laden". Wischen Sie die USB-Benachrichtigung
herunter und wählen Sie **Dateiübertragung (MTP)** oder **PTP**.

### Schritt 5 — Verifizierung in SYLION

Nach erfolgreicher ADB-Autorisierung:
1. Navigieren Sie zu **Dashboard → Geräte**.
2. Klicken Sie auf **Aktualisieren**. Das Pixel 9 sollte in der Liste erscheinen.

Falls das Gerät weiterhin fehlt: `cat ~/sylion/logs/device_manager.log` prüfen.

---

## 25. Mudi benötigt WireGuard — wie installiert man es auf dem GL.iNet Mudi?

**Frage:** Das SYLION-SDR-Modul erfordert eine VPN-Verbindung über WireGuard auf dem
GL.iNet Mudi-Router (GL-E750). Wie installiert man WireGuard auf diesem Gerät?

**Antwort:**

Der GL.iNet Mudi läuft auf OpenWrt. Nachfolgend die Installation und Konfiguration
von WireGuard:

### Kernel-Modul WireGuard installieren

```bash
# Per SSH mit dem Router verbinden
ssh root@192.168.8.1

# Paketindex aktualisieren
opkg update

# WireGuard installieren (Kernel-Modul + Werkzeuge)
opkg install kmod-wireguard wireguard-tools

# Prüfen ob das Modul korrekt geladen wurde
lsmod | grep wireguard
```

### Schlüssel generieren

```bash
# Auf dem Router
wg genkey | tee /etc/wireguard/private.key | wg pubkey > /etc/wireguard/public.key
chmod 600 /etc/wireguard/private.key

cat /etc/wireguard/public.key   # Öffentlichen Schlüssel in die VPN-Server-Konfiguration kopieren
```

### WireGuard-Interface konfigurieren

Datei `/etc/config/network` bearbeiten (Abschnitt für wg0):

```
config interface 'wg0'
    option proto 'wireguard'
    option private_key 'IHR_PRIVATER_SCHLÜSSEL'
    option listen_port '51820'
    list addresses '10.0.0.2/24'

config wireguard_wg0
    option public_key 'ÖFFENTLICHER_SCHLÜSSEL_DES_SERVERS'
    option endpoint_host 'vpn.example.com'
    option endpoint_port '51820'
    list allowed_ips '0.0.0.0/0'
    option persistent_keepalive '25'
```

### Starten

```bash
ifup wg0
# Status prüfen
wg show
```

### Integration mit SYLION

Nach dem Start von WireGuard SYLION so konfigurieren, dass die SDR-Route über `wg0` läuft:

```ini
# .env
SDR_VPN_INTERFACE=wg0
SDR_VPN_GATEWAY=10.0.0.1
```

Weitere Details: `sylion-pipeline/device/WIREGUARD_TODO.md` und
`sylion-pipeline/sdr/FARADAY_CAGE.md`.

---

## 26. Wie migriert man von v5.8 auf v5.9.1?

**Frage:** Ich verwende SYLION v5.8.x. Wie migriere ich sicher direkt auf v5.9.1?

**Antwort:**

Die Migration von v5.8.x auf v5.9.1 umfasst drei Datenbankschema-Migrationsschritte
(1→2→3), die automatisch ausgeführt werden. Nachfolgend die vollständige Prozedur:

### Voraussetzungen

- Python **3.11 oder neuer** (3.12 empfohlen)
- Freier Speicherplatz: min. 500 MB (DB-Backup + neue Abhängigkeiten)
- Zugang zu API-Schlüsseln (werden nach der Migration überprüft)

### Schritt 1 — Backup vor der Migration

```bash
# Datenbank sichern (kritisch!)
sqlite3 ~/sylion/sylion.db \
  ".backup '~/sylion/backups/sylion-pre-v591-$(date +%Y%m%d-%H%M%S).db.bak'"

# Gesamtes Anwendungsverzeichnis sichern
cp -a ~/sylion ~/sylion.bak-v58
```

### Schritt 2 — v5.8-Server stoppen

```bash
sudo systemctl stop sylion
# oder: kill $(lsof -t -i :8421)
```

### Schritt 3 — v5.9.1 entpacken und installieren

```bash
cd ~/
unzip SYLION_v591.zip -d /tmp/sylion-v591
rsync -a --delete /tmp/sylion-v591/sylion-pipeline/ ~/sylion/sylion-pipeline/

cd ~/sylion/sylion-pipeline
source .venv/bin/activate  # oder: python -m venv .venv && source .venv/bin/activate
pip install -r requirements-lock.txt --upgrade
```

### Schritt 4 — Schema-Migration (automatisch)

```bash
# DB-Migration wird automatisch beim ersten Start durchgeführt.
# Version vor und nach prüfen:
sqlite3 ~/sylion/sylion.db "PRAGMA user_version;"
# Erwartet: 2 (v5.9.1 Ziel-user_version)
```

### Schritt 5 — API-Schlüssel rotieren (Pflicht!)

Siehe Frage 22 (F-001 — hartcodierte Schlüssel in `dashboard/db.py`). Rotation vor
dem Start durchführen.

### Schritt 6 — Starten und verifizieren

```bash
python dashboard/start.py

# In einem anderen Terminal:
curl http://localhost:8421/api/health
# Erwartet: {"status":"ok","version":"5.9.1",...}
```

Vollständige Migrationsanleitung: `docs/MIGRATION_GUIDE.md`.

---

## 27. Welche monatlichen API-Kosten sind zu erwarten? Wie funktioniert Tier Routing?

**Frage:** Ich nutze das Council mit 19 Modellen. Wie schätze ich die monatlichen Kosten?
Was ist „Tier Routing"?

**Antwort:**

### Modelle in SYLION v5.9.1 (19 Modelle)

Das Council verwendet standardmäßig 4 Modelle parallel:

| Modell | Anbieter | Preis (ca., USD) |
|--------|----------|-----------------|
| Claude Opus 4.7 | Anthropic | ~$15 / 1M Eingabe-Token, ~$75 / 1M Ausgabe-Token |
| Claude Sonnet 4.6 | Anthropic | ~$3 / 1M Eingabe, ~$15 / 1M Ausgabe |
| GPT-5.4 | OpenAI | ~$10 / 1M Eingabe, ~$30 / 1M Ausgabe |
| Gemini 3.1 Pro | Google | ~$3,5 / 1M Eingabe, ~$10,5 / 1M Ausgabe |

*(Richtwerte — aktuelle Preise immer auf den Anbieter-Websites prüfen.)*

### Tier Routing

Tier Routing ist ein SYLION-Mechanismus, der Anfragen automatisch an das Modell
mit der passenden Leistungsstärke und den entsprechenden Kosten weiterleitet:

- **Tier 1 (günstig, schnell):** Sonnet 4.6, Gemini 3.1 Pro — für einfache Aufgaben
  (z. B. Formatierung, Zusammenfassungen).
- **Tier 2 (teuer, präzise):** Opus 4.7, GPT-5.4 — für komplexe Analysen
  (Code-Review, Security-Audit).

Konfiguration in `.env`:

```ini
COUNCIL_TIER_ROUTING=true
COUNCIL_TIER1_MODELS=claude-sonnet-4.6,gemini-3.1-pro
COUNCIL_TIER2_MODELS=claude-opus-4.7,gpt-5.4
```

### Monatliche Kosten schätzen

Bei typischer Nutzung (10 Pipelines/Tag, ~50.000 Token pro Pipeline):

- Ohne Tier Routing: ca. **$200–400/Monat** (alle 4 Modelle für jede Anfrage)
- Mit Tier Routing: ca. **$60–120/Monat** (Tier 2 nur für komplexe Aufgaben)

**Kosten überwachen:**

Navigieren Sie zu **Dashboard → FinOps → API-Verbrauch** — dort sehen Sie
tägliche und monatliche Kosten pro Modell.

Budget-Limit einrichten:

```ini
COUNCIL_MONTHLY_BUDGET_USD=100
COUNCIL_BUDGET_ACTION=warn  # oder: pause (stoppt Council nach Überschreitung)
```

---

*Ergänzungen zu FAQ_DE.md für SYLION v5.9.1 — 2026-04-19*
*Lücken identifiziert in: audit_LATEST/18_user_manual.md*
