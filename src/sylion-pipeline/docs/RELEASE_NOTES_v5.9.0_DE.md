# Versionshinweise SYLION v5.9.0 (Deutsch)

**Erscheinungsdatum:** 2026-04-19  
**Versionstyp:** Minor Release mit Fehlerbehebungen und neuen Audit-Skills

---

## Was ist neu?

### Council der 4 Modelle — Parallelmodus

Die vier AI-Modelle (Claude Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro) arbeiten jetzt immer parallel statt sequenziell. Die Antwortzeit wurde bei gleichbleibender Analysequalität um ca. 60 % reduziert.

### Neues Agenten-Panel

Die Registerkarte **Agenten** im Dashboard zeigt jetzt:

- den Echtzeit-Status aller 48 Agenten
- den Zeitpunkt der letzten Ausführung
- Statistiken (Anzahl der Ausführungen, Durchschnittszeit, Erfolgsrate)

### Human Gate mit Inline-Bearbeitung

Beim Genehmigen einer Stage mit Human Gate können Sie das Agenten-Ergebnis jetzt direkt im Genehmigungspanel bearbeiten, anstatt es abzulehnen und neu zu starten.

### Berichtsexport als HTML

Neben den bisherigen Formaten (JSON, Markdown) gibt es jetzt den Export als HTML mit Formatierung — der Bericht ist ohne zusätzliche Nachbearbeitung teilbar.

### WAL-Modus — automatische Konfiguration

SYLION setzt den WAL-Modus beim Erstellen einer neuen Datenbank automatisch. Eine manuelle Konfiguration ist nicht erforderlich.

### Council-Kontext zwischen Sitzungen gespeichert

Der Gesprächskontext mit dem Council wird jetzt in der Datenbank gespeichert und ist nach einem Server-Neustart verfügbar. Sie können eine frühere Sitzung ohne Verlust des Verlaufs fortsetzen.

---

## Was wurde behoben? (11 Korrekturen)

1. **Fehler bei langen Prompts** — Der Pipeline blockierte bei Anfragen mit mehr als 8.000 Token. Große Eingaben werden jetzt automatisch in Abschnitte aufgeteilt.

2. **Rate Limiter blockierte lokale IP-Adresse** — Bei Tests von localhost wurde das Limit ausgelöst. Behoben — localhost und 127.0.0.1 sind vom Rate Limiter ausgenommen.

3. **Falsche Zeichenkodierung in Berichten** — Sonderzeichen (ä, ö, ü, ß usw.) erschienen beim Markdown-Export manchmal als Ersatzzeichen. Behoben — alle Berichte sind jetzt in UTF-8.

4. **Agent "security_scan" ignorierte .env-Dateien** — Der Sicherheitsscanner übergab Konfigurationsdateien. Er überprüft jetzt alle Dateien im Projekt, einschließlich versteckter Dateien.

5. **Fehler 500 nach Sitzungsablauf** — Statt einer Weiterleitung zur Login-Seite gab der Server einen internen Fehler zurück. Behoben — abgelaufene Sitzung = Weiterleitung zu /login.

6. **Council-Timeout wurde nicht berücksichtigt** — Der Wert `COUNCIL_TIMEOUT_SECONDS` aus `.env` wurde ignoriert. Er wird jetzt beim Serverstart korrekt gelesen.

7. **Doppelte Einträge in der Pipeline-Historie** — Bei einem Server-Neustart während eines laufenden Pipelines erschienen Duplikate in der Liste. Durch atomare Statusschreibungen behoben.

8. **Human Gate speicherte Entscheidungen nicht in der Datenbank** — "Genehmigen/Ablehnen"-Entscheidungen wurden nur im Arbeitsspeicher protokolliert. Nach einem Neustart ging die Historie verloren. Sie werden jetzt dauerhaft gespeichert.

9. **Importfehler unter Windows bei Pfaden mit Sonderzeichen** — Ein Projektverzeichnis mit deutschen Sonderzeichen im Namen (z. B. `Schreibtisch`) verursachte Importfehler. Durch Pfadnormalisierung behoben.

10. **Agenten-Panel aktualisierte sich nicht automatisch** — Um den aktuellen Agentenstatus zu sehen, musste die Seite manuell neu geladen werden. Jetzt funktioniert die automatische Aktualisierung alle 5 Sekunden (WebSocket).

11. **Fehler bei leerer Gemini-Antwort** — Wenn Gemini 3.1 Pro eine leere Antwort zurückgab (z. B. bei Inhaltsfilterung), warf das Council eine Exception. Solche Antworten werden jetzt sauber behandelt, mit einer Meldung im Bericht.

---

## Upgrade von v5.8.x

Das Update von v5.8.x auf v5.9.0 erfordert eine Datenbankmigration. SYLION führt diese automatisch beim ersten Start der neuen Version durch.

Vor dem Update:

```bash
# Manuelles Backup erstellen
cp ~/sylion/sylion.db ~/backup/sylion_pre_v590.db
```

Dann:

```bash
git pull origin main
./install.sh   # oder install.bat unter Windows
python -m sylion migrate
python -m sylion serve
```

Ausführlicher Migrationsleitfaden: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md).

---

## Neue Audit-Skills (18 Skills)

In dieser Version wurden 18 neue Skills für den Agenten-Audit-Satz hinzugefügt:

| Skill | Beschreibung |
|-------|--------------|
| `sql_injection_scan` | Erkennt SQL-Injection-Schwachstellen im Code |
| `secret_leak_detect` | Sucht API-Schlüssel und Passwörter im Quellcode |
| `dependency_audit` | Prüft bekannte CVEs in Abhängigkeiten (npm, pip) |
| `license_compliance` | Überprüft die Lizenzeinhaltung von Bibliotheken |
| `dead_code_finder` | Identifiziert ungenutzten Code |
| `complexity_score` | Berechnet die zyklomatische Komplexität von Funktionen |
| `test_coverage_check` | Prüft die Testabdeckung des Codes |
| `doc_completeness` | Bewertet die Vollständigkeit der Dokumentation (Docstrings, README) |
| `api_contract_lint` | Überprüft die Code-Konformität mit der OpenAPI-Definition |
| `type_hint_audit` | Prüft Vorhandensein und Korrektheit von Type Hints (Python) |
| `env_variable_check` | Erkennt hartcodierte Werte, die in .env gespeichert werden sollten |
| `async_pattern_review` | Prüft die korrekte Verwendung von async/await |
| `error_handling_audit` | Bewertet die Qualität der Exception-Behandlung |
| `logging_consistency` | Überprüft die Konsistenz der Protokollierung im Projekt |
| `migration_safety_check` | Prüft die Sicherheit von Datenbankmigrationen |
| `performance_hotspot` | Identifiziert potenzielle Performance-Engpässe |
| `accessibility_lint` | Prüft die Barrierefreiheit in Frontend-Projekten (WCAG) |
| `dockerfile_audit` | Analysiert Sicherheit und Optimierung des Dockerfiles |

Die Skills sind nach dem Update automatisch verfügbar — keine Konfiguration erforderlich.
