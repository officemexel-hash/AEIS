# Onboarding-Checkliste — SYLION v5.9.0

10 Schritte von der Installation bis zur vollständigen Inbetriebnahme.

Haken Sie die Schritte ab, während Sie vorankommen. Der gesamte Prozess dauert ca. 20–30 Minuten.

---

## Schritt 1: Überprüfung der Systemanforderungen

Stellen Sie vor der Installation sicher, dass alle Anforderungen erfüllt sind:

- [ ] Python 3.12 oder neuer installiert und im PATH verfügbar
- [ ] Mindestens 8 GB RAM verfügbar
- [ ] Mindestens 2 GB freier Festplattenspeicher
- [ ] Betriebssystem: Linux, macOS oder Windows 10/11
- [ ] Internetzugang (benötigt für die Installation der Abhängigkeiten und die Nutzung der KI-Modelle)

Python-Version prüfen:

```bash
python --version
```

---

## Schritt 2: Download und Installation

- [ ] Repository heruntergeladen (`git clone` oder als ZIP-Archiv)
- [ ] Installationsskript ausgeführt (`./install.sh` oder `install.bat`)
- [ ] Installation ohne Fehler abgeschlossen (letzte Zeile: `SYLION installed successfully`)

Falls die Installation fehlgeschlagen ist, lesen Sie [TROUBLESHOOTING_DE.md](TROUBLESHOOTING_DE.md), Probleme 9 und 15.

---

## Schritt 3: API-Schlüssel konfigurieren

- [ ] Datei `.env` im Texteditor geöffnet
- [ ] Anthropic-API-Schlüssel eingetragen (`ANTHROPIC_API_KEY`)
- [ ] OpenAI-API-Schlüssel eingetragen (`OPENAI_API_KEY`)
- [ ] Google-API-Schlüssel eingetragen (`GOOGLE_API_KEY`)
- [ ] Datei `.env` gespeichert

Falls nicht alle Schlüssel vorhanden sind, kann SYLION auch ohne sie gestartet werden — Modelle ohne Schlüssel werden im Council deaktiviert.

---

## Schritt 4: Server zum ersten Mal starten

- [ ] Server gestartet: `python dashboard/start.py`
- [ ] Setup-Token in der Konsole sichtbar (`[SYLION] Setup token: XXXX-XXXX-XXXX-XXXX`)
- [ ] Setup-Token in die Zwischenablage kopiert oder notiert

---

## Schritt 5: Administrator-Passwort festlegen

- [ ] Seite `http://localhost:8421/setup` im Browser geöffnet
- [ ] Setup-Token in das Feld „Setup Token" eingefügt
- [ ] Administrator-Passwort festgelegt (mindestens 12 Zeichen; empfohlen: Buchstaben + Ziffern + Sonderzeichen)
- [ ] Administrator-Konto erfolgreich erstellt

---

## Schritt 6: Erste Anmeldung und Dashboard erkunden

- [ ] Anmeldung über `http://localhost:8421/login`
- [ ] Dashboard korrekt geladen
- [ ] Reiter **Pipeline** geprüft — Liste der Stages sichtbar
- [ ] Reiter **Agenten** geprüft — alle 48 Agenten werden angezeigt
- [ ] Reiter **Council** geprüft — vier Modelle sichtbar
- [ ] Reiter **Einstellungen** geprüft — Konfiguration zugänglich

---

## Schritt 7: Council überprüfen

- [ ] Reiter **Council** im Dashboard geöffnet
- [ ] Testanfrage eingegeben (z. B. „Beschreibe kurz, was SQL-Injection ist")
- [ ] „Council starten" geklickt
- [ ] Antworten aller vier Modelle im Panel erschienen
- [ ] Konsens am Ende des Panels angezeigt

Falls ein Modell nicht antwortet, überprüfen Sie den zugehörigen API-Schlüssel unter Einstellungen.

---

## Schritt 8: Erste Audit-Pipeline starten

- [ ] Reiter **Pipeline** geöffnet
- [ ] Neue Pipeline erstellt (Schaltfläche „Neue Pipeline")
- [ ] Eingabedaten angegeben (Datei oder Verzeichnis mit Quellcode)
- [ ] Pipeline gestartet
- [ ] Pipeline-Fortschritt im Panel sichtbar
- [ ] Pipeline mit Status `completed` abgeschlossen

Falls die Pipeline hängt, lesen Sie [TROUBLESHOOTING_DE.md](TROUBLESHOOTING_DE.md), Problem 15.

---

## Schritt 9: Backup konfigurieren

- [ ] Speicherort der Datenbank verstanden: `~/sylion/sylion.db`
- [ ] Befehl für manuelles Backup vorbereitet oder notiert:

```bash
cp ~/sylion/sylion.db ~/backup/sylion_$(date +%Y%m%d_%H%M%S).db
```

- [ ] (Optional) Automatischer Backup-Plan eingerichtet (cron unter Linux/macOS oder Aufgabenplanung unter Windows)

Empfehlung: Tägliches Backup in ein separates Verzeichnis oder auf ein externes Speichermedium.

---

## Schritt 10: Dokumentation lesen

- [ ] [QUICKSTART_DE.md](QUICKSTART_DE.md) gelesen — Sie wissen, wie SYLION gestartet wird
- [ ] [FAQ_DE.md](FAQ_DE.md) überflogen — Sie kennen die Antworten auf häufige Fragen
- [ ] [TROUBLESHOOTING_DE.md](TROUBLESHOOTING_DE.md) überflogen — Sie wissen, wo Sie bei Problemen Hilfe finden
- [ ] [RELEASE_NOTES_v5.9.0_DE.md](RELEASE_NOTES_v5.9.0_DE.md) gelesen — Sie kennen die Neuerungen dieser Version
- [ ] [ONBOARDING_CHECKLIST_DE.md](ONBOARDING_CHECKLIST_DE.md) vollständig abgehakt

---

## Fertig

Nach dem Abhaken aller 10 Schritte ist SYLION vollständig eingerichtet und betriebsbereit.

Bei Fragen oder Problemen: support@sylion.example
