# Datenschutzerklärung — SYLION Pipeline

**Version:** 1.0 (Entwurf — rechtliche Überprüfung vor Vertrieb erforderlich)  
**Datum:** 2026-04-19  
**Produkt:** SYLION v5.9.0 — Lokale KI-Pipeline  
**Kontakt:** support@sylion.example

> **Hinweis:** Dieses Dokument ist die Datenschutzerklärung für Benutzer des Systems  
> (Art. 13 DSGVO — Informationspflicht). Sie ist getrennt vom Verarbeitungsverzeichnis  
> (VVT, Art. 30 DSGVO) in `docs/RODO_COMPLIANCE.md`.

---

## 1. Verantwortlicher

Verantwortlicher für die Verarbeitung Ihrer personenbezogenen Daten ist:

```
[VOLLSTÄNDIGER NAME / FIRMENNAME]
[ANSCHRIFT]
[HRB/Steuernummer oder entsprechend]
E-Mail: support@sylion.example
```

*(Vor Vertrieb ausfüllen.)*

---

## 2. Was ist SYLION?

SYLION ist eine **lokale KI-Pipeline** für Code-Auditing und Analyse. Das System läuft ausschließlich auf Ihrem Gerät (localhost). Daten, die von SYLION verarbeitet werden, werden **nicht automatisch an externe Server übermittelt**, außer Prompt-Inhalte, die an externe KI-Modelle gerichtet werden (siehe Abschnitt 5).

---

## 3. Welche personenbezogenen Daten werden verarbeitet?

### 3.1 Daten der Dashboard-Operatoren (Benutzer des Systems)

| Datenkategorie | Beispiele | Rechtsgrundlage |
|---------------|-----------|-----------------|
| Kontodaten | Benutzername, Passwort-Hash (argon2id) | Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse — Systemsicherheit); ggf. §26 BDSG (Beschäftigungsverhältnis) |
| Sitzungsdaten | Sitzungs-ID, Anmeldezeit, Ablaufzeit, RBAC-Rolle | Art. 6 Abs. 1 lit. f DSGVO |
| Audit-Log (Ereignisprotokoll) | Benutzername, Aktionstyp, Zeitstempel, Objekt-ID | Art. 6 Abs. 1 lit. f DSGVO (Sicherheit, Missbrauchsprävention) |

### 3.2 An das System übermittelte Inhalte (Prompts und Dokumente)

| Datenkategorie | Beispiele | Rechtsgrundlage |
|---------------|-----------|-----------------|
| Prompt-Inhalte | Quellcode, Fragen, zur Analyse übermittelte Dokumente | Art. 6 Abs. 1 lit. f DSGVO |
| Pipeline-Ergebnisse | Berichte, Analysen der KI-Agenten | Art. 6 Abs. 1 lit. f DSGVO |

> **Wichtig:** SYLION fordert **keine personenbezogenen Daten** in Prompts. Wenn Ihre Anfragen personenbezogene Daten Dritter enthalten, sind Sie für die DSGVO-Konformität dieser Verarbeitung verantwortlich.

### 3.3 Konfigurationsdaten

| Datenkategorie | Beispiele | Rechtsgrundlage |
|---------------|-----------|-----------------|
| API-Schlüssel | Schlüssel für externe KI-Dienste (OpenAI, Anthropic, Google, Perplexity) | Art. 6 Abs. 1 lit. f DSGVO (Betriebsfähigkeit des Systems) |

---

## 4. Speicherdauer

| Datentyp | Aufbewahrungsfrist | Mechanismus |
|---------|-------------------|-------------|
| Benutzerkonto | Bis zur manuellen Löschung durch Administrator | DELETE /api/users/{id} |
| RBAC-Sitzungen | 30 Tage nach Ablauf (Standard; konfigurierbar) | Automatische tägliche Bereinigung |
| Audit-Log | 365 Tage (Standard; konfigurierbar) | Automatische tägliche Bereinigung |
| Betriebsereignisse (event_stream) | 7 Tage (fest) | Automatische tägliche Bereinigung |
| Pipeline-Ergebnisse (runs, artifacts) | Bis zur manuellen Löschung | Keine automatische Bereinigung |
| Datenbank-Backups | [Bitte ausfüllen — empfohlen: 90 Tage] | [Bitte ausfüllen] |

**Begründung der 365-Tage-Aufbewahrung für Audit-Log:** Systemsicherheit, Anomalieerkennung, Forensics (NIST SP 800-92), Geltendmachung von Ansprüchen (Art. 17 Abs. 3 lit. e DSGVO).

**Hinweis zur GoBD:** Das Audit-Log ist ein technisches Protokoll, kein kaufmännisches Buch i.S.v. §257 HGB / §147 AO. Die 10-jährige GoBD-Aufbewahrungspflicht gilt nicht.

---

## 5. Übermittlung an externe KI-Anbieter

SYLION kommuniziert mit externen KI-Modellen:

| Anbieter | Land | Zweck | Schutzmaßnahme |
|---------|------|-------|----------------|
| OpenAI | USA | Antwortgenerierung (GPT) | EU-US Data Privacy Framework (DPF) + Auftragsverarbeitungsvertrag (AVV) |
| Anthropic | USA | Antwortgenerierung (Claude) | Standardvertragsklauseln (SCC Modul 2, 2021) + AVV |
| Google AI | USA/EU | Antwortgenerierung (Gemini) | EU-US DPF + AVV |
| Perplexity | USA | KI-gestützte Suche | SCC Modul 2 + AVV |

> **Hinweis zu Schrems II:** Jede Übermittlung in Drittländer erfordert ein Transfer Impact Assessment (TIA) gemäß EDPB-Leitlinien 05/2021.

> **Empfehlung:** Keine personenbezogenen Daten Dritter in Prompts einfügen.

---

## 6. Datenspeicherort

Alle SYLION-Daten werden **lokal** auf Ihrem Gerät gespeichert:

```
Datenbank:     ~/sylion/sylion.db  (SQLite)
Backups:       ~/sylion/sylion.db.bak.*.sqlite3
Protokolle:    [konfigurierbar]
```

Die Daten werden **nicht** automatisch an externe Server übertragen (außer Prompts an externe KI-APIs, siehe Abschnitt 5).

---

## 7. Ihre Rechte als betroffene Person

| Recht | DSGVO / BDSG | Ausübung |
|-------|-------------|----------|
| Auskunftsrecht | Art. 15 DSGVO | E-Mail an Verantwortlichen; Antwort innerhalb 30 Tagen |
| Berichtigungsrecht | Art. 16 DSGVO | E-Mail an Verantwortlichen |
| Löschungsrecht | Art. 17 DSGVO; **§35 BDSG** (schriftliche Bestätigung) | E-Mail an Verantwortlichen; im System: DELETE /api/users/{id} |
| Einschränkung der Verarbeitung | Art. 18 DSGVO | E-Mail an Verantwortlichen |
| Datenübertragbarkeit | Art. 20 DSGVO | JSON-Export über API (in Vorbereitung) |
| Widerspruchsrecht | Art. 21 DSGVO | E-Mail an Verantwortlichen |

**Hinweis §35 BDSG:** Bei Löschungsanträgen wird eine **schriftliche Bestätigung** übermittelt. Ablehnungen werden mit Rechtsgrundlage begründet (§35 Abs. 5 BDSG).

**Kontakt DSR:** support@sylion.example  
**Antwortfrist:** 30 Kalendertage (Verlängerung um 60 Tage bei komplexen Anfragen möglich, mit Mitteilung an den Antragsteller).

---

## 8. Datensicherheit

SYLION verwendet folgende Sicherheitsmaßnahmen gemäß Art. 32 DSGVO:

- **Passwort-Hashing:** argon2id-Algorithmus (NIST-konform); bcrypt als Fallback.
- **Zugangskontrolle:** RBAC mit Rollen: owner, admin, member.
- **Audit-Log:** Jede Aktion wird mit Zeitstempel und Benutzer protokolliert.
- **WAL-sichere Backups:** Sicherungen vor Datenbankmigrationen.
- **Rate Limiting:** Begrenzung von Anmeldeversuchen (FIX-01, SYLION v5.9.0).
- **Human-Gate:** KI-Entscheidungen erfordern menschliche Bestätigung (Art. 14 KI-Verordnung).

**Bekannte Einschränkungen (Entwicklungsumgebung):**
- SQLite-Datenbank ist nicht verschlüsselt (Plaintext). In Produktionsumgebungen wird Verschlüsselung at-rest empfohlen.
- Backups sind nicht verschlüsselt. In Produktionsumgebungen wird Backup-Verschlüsselung empfohlen.

---

## 9. Beschäftigtendatenschutz (§26 BDSG)

Sofern SYLION von Beschäftigten eines Unternehmens verwendet wird, erfolgt die Verarbeitung der Beschäftigtendaten (Benutzernamen, Audit-Log-Einträge) auf Grundlage von §26 Abs. 1 BDSG zur Durchführung des Beschäftigungsverhältnisses und zur IT-Sicherheit.

Sofern ein **Betriebsrat** besteht, ist zu prüfen, ob ein Mitbestimmungsrecht nach §87 BetrVG (Abs. 1 Nr. 6 — technische Überwachungseinrichtungen) besteht.

---

## 10. Aufsichtsbehörde

Sie haben das Recht, sich bei der zuständigen Datenschutz-Aufsichtsbehörde zu beschweren:

**Bundesebene (Deutschland):**
Der Bundesbeauftragte für den Datenschutz und die Informationsfreiheit (BfDI)  
Husarenstraße 30, 53117 Bonn  
Tel.: +49 228 997799-0  
E-Mail: poststelle@bfdi.bund.de  
https://www.bfdi.bund.de

**Landesebene:** Zuständig ist die Datenschutzbehörde des Bundeslandes, in dem der Verantwortliche seinen Sitz hat.

---

## 11. Änderungen dieser Datenschutzerklärung

Bei wesentlichen Änderungen der Datenverarbeitung wird diese Datenschutzerklärung aktualisiert. Empfohlen wird eine regelmäßige Prüfung der Datei `PRIVACY_POLICY_DE.md` im Projektrepository.

---

*Datenschutzerklärung v1.0 | SYLION v5.9.0 | Entwurf — rechtliche Prüfung vor kommerziellem Vertrieb erforderlich.*  
*Erstellt: Legal Re-Audit Council, 2026-04-19.*
