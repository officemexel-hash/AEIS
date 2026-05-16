# Schnellstart — SYLION v5.9.1 (Deutsch)

Von der Installation bis zum ersten Login in 5 Minuten.

---

## Systemvoraussetzungen

Stellen Sie vor der Installation sicher, dass folgende Anforderungen erfüllt sind:

| Komponente  | Anforderung                        |
|-------------|------------------------------------|
| Python      | 3.11 oder neuer (3.12 empfohlen)   |
| Arbeitsspeicher | mindestens 8 GB RAM            |
| Betriebssystem | Linux, macOS oder Windows 10/11 |
| Festplatte  | 2 GB freier Speicherplatz          |
| Netzwerk    | Internetzugang (nur bei Installation und Nutzung der AI-Modelle) |

Prüfen Sie die Python-Version:

```bash
python --version
# oder
python3 --version
```

---

## Schritt 1 — Installation

### Linux / macOS

```bash
# Extract SYLION_v591.zip to your target directory
cd sylion
chmod +x install.sh
./install.sh
```

Das Skript `install.sh` führt automatisch folgende Schritte aus:

- Erstellt eine virtuelle Python-Umgebung (`venv`)
- Installiert alle Abhängigkeiten (`pip install -r requirements-lock.txt`)
- Generiert eine Standard-`.env`-Datei auf Basis von `.env.example`
- Initialisiert die SQLite-Datenbank unter `~/sylion/sylion.db`

### Windows

```bat
# Extract SYLION_v591.zip to your target directory
cd sylion
install.bat
```

`install.bat` führt dieselben Schritte aus, angepasst an die Windows-Umgebung.

---

## Schritt 2 — API-Schlüssel konfigurieren

Öffnen Sie die Datei `.env` in einem Texteditor und tragen Sie die API-Schlüssel der Modelle ein, die Sie verwenden möchten:

```ini
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

Die Schlüssel können auch zu einem späteren Zeitpunkt über das Dashboard geändert werden — siehe FAQ, Frage 1.

---

## Schritt 3 — Server starten

```bash
# Linux / macOS
python dashboard/start.py

# Windows
python dashboard/start.py
```

Nach erfolgreicher Installation erscheint folgende Ausgabe in der Konsole:

```
[SYLION] Starting server on http://localhost:8421
[SYLION] Setup token: XXXX-XXXX-XXXX-XXXX
[SYLION] Database: /home/<user>/sylion/sylion.db (WAL mode)
[SYLION] Agents loaded: 48
[SYLION] Council models: Claude Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro
```

Kopieren Sie den **Setup Token** — er wird im nächsten Schritt benötigt.

---

## Schritt 4 — Erster Login und Passwort einrichten

1. Öffnen Sie einen Browser und navigieren Sie zu:

```
http://localhost:8421/setup
```

2. Fügen Sie den kopierten Setup Token in das Feld "Setup Token" ein.

3. Geben Sie ein Administrator-Passwort ein (mindestens 12 Zeichen). Das Passwort wird mit dem Algorithmus Argon2id gehasht und niemals im Klartext gespeichert oder übertragen.

4. Klicken Sie auf "Administratorkonto erstellen".

Danach erfolgt der Login über:

```
http://localhost:8421/login
```

---

## Schritt 5 — Dashboard und erstes Council-Ausführen

Nach dem Login sehen Sie das Dashboard mit folgenden Bereichen:

- **Pipeline** — Verwaltung der Audit-Phasen (Stages)
- **Council** — Panel der vier AI-Modelle
- **Agenten** — Liste der 48 Agenten mit ihrem Status
- **Einstellungen** — API-Schlüssel, Logs, Konfiguration

### Council starten

1. Navigieren Sie zur Registerkarte **Council** im Seitenmenü.
2. Geben Sie eine Frage ein oder fügen Sie einen Code-Ausschnitt in das Textfeld ein.
3. Klicken Sie auf **"Council starten"**.

Die vier Modelle (Claude Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro) verarbeiten die Anfrage parallel. Die Ergebnisse erscheinen im rechten Panel — jedes Modell separat, mit einer Konsens-Zusammenfassung am unteren Rand.

---

## Weiterführende Dokumentation

- [FAQ_DE.md](FAQ_DE.md) — Häufig gestellte Fragen
- [TROUBLESHOOTING_DE.md](TROUBLESHOOTING_DE.md) — Häufige Probleme und Lösungen
- [RELEASE_NOTES_v5.9.0_DE.md](RELEASE_NOTES_v5.9.0_DE.md) — Neuigkeiten in dieser Version
