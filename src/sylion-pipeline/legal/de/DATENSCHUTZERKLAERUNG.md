# Datenschutzerklärung — SYLION Pipeline

**Dokumentversion:** v5.9.1  
**Datum:** 2026-04-19  
**Letzte Aktualisierung:** 2026-04-19  
**Produkt:** SYLION v5.9.1 — Lokale KI-Pipeline  
**Kontakt:** support@sylion.example

> **Hinweis:** Dieses Dokument ist die Datenschutzerklärung für Benutzer des Systems  
> (Art. 13 DSGVO — Informationspflicht). Sie ist getrennt vom Verarbeitungsverzeichnis  
> (VVT, Art. 30 DSGVO) in `docs/RODO_COMPLIANCE.md`.
>
> **PLATZHALTER — VOR VERTEILUNG AUSFÜLLEN:** Ersetzen Sie alle `{{…}}`-Markierungen durch  
> tatsächliche Daten des Verantwortlichen. Siehe Ausfüllanleitung am Ende dieses Dokuments.

---

## 1. Verantwortlicher

Verantwortlicher für die Verarbeitung Ihrer personenbezogenen Daten ist:

```
{{COMPANY_NAME_DE}}
{{ADDRESS_DE}}
{{HRB_UST_DE}}
E-Mail: {{CONTACT_EMAIL_DE}}
```

*(Alle `{{…}}`-Felder vor Verteilung ausfüllen — Art. 13 Abs. 1 lit. a DSGVO.)*

---

## 2. Was ist SYLION?

SYLION ist eine **lokale KI-Pipeline** für Code-Auditing und Analyse. Das System läuft ausschließlich auf dem Gerät des Operators (localhost). Daten, die von SYLION verarbeitet werden, werden **nicht automatisch an externe Server übermittelt**, außer Prompt-Inhalte, die an externe KI-Modelle gerichtet werden (siehe § 5).

---

## 3. Welche personenbezogenen Daten werden verarbeitet?

### 3.1 Daten der Dashboard-Operatoren (Systembenutzer)

| Datenkategorie | Beispiele | Rechtsgrundlage |
|---------------|-----------|-----------------|
| Kontodaten | Benutzername, Passwort-Hash (argon2id) | Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse — Systemsicherheit); ggf. §26 BDSG (Beschäftigungsverhältnis) |
| Sitzungsdaten | Sitzungs-ID, Anmeldezeit, Ablaufzeit, RBAC-Rolle | Art. 6 Abs. 1 lit. f DSGVO |
| Audit-Log (Ereignisprotokoll) | Benutzername, Aktionstyp, Zeitstempel, Objekt-ID | Art. 6 Abs. 1 lit. f DSGVO (Sicherheit, Missbrauchsprävention) |
| KI-Kostenprotokoll (cost_log) | user_id, KI-Modell, Token-Anzahl, Stückkosten, Zeitstempel | Art. 6 Abs. 1 lit. f DSGVO (Ressourcenverwaltung; Verteidigung finanzieller Ansprüche) |

### 3.2 An das System übermittelte Inhalte (Prompts und Dokumente)

| Datenkategorie | Beispiele | Rechtsgrundlage |
|---------------|-----------|-----------------|
| Prompt-Inhalte | Quellcode, Fragen, zur Analyse übermittelte Dokumente | Art. 6 Abs. 1 lit. f DSGVO |
| Pipeline-Ergebnisse | Berichte, Analysen der KI-Agenten | Art. 6 Abs. 1 lit. f DSGVO |

> **Wichtig:** SYLION fordert **keine personenbezogenen Daten** in Prompts. Wenn Ihre Anfragen personenbezogene Daten Dritter enthalten, sind Sie für die DSGVO-Konformität dieser Verarbeitung verantwortlich.

### 3.3 Konfigurationsdaten

| Datenkategorie | Beispiele | Rechtsgrundlage |
|---------------|-----------|-----------------|
| API-Schlüssel | Schlüssel für externe KI-Dienste (OpenAI, Anthropic, Google, Perplexity, xAI, DeepSeek) | Art. 6 Abs. 1 lit. f DSGVO (Betriebsfähigkeit des Systems) |

---

## 4. Speicherdauer

| Datentyp | Aufbewahrungsfrist | Mechanismus |
|---------|-------------------|-------------|
| Benutzerkonto | Bis zur manuellen Löschung; Soft-Delete + Hard-Purge nach 30 Tagen | DELETE /api/auth/me/data; purge_soft_deleted_users() |
| RBAC-Sitzungen | 30 Tage nach Ablauf (Standard; konfigurierbar) | Automatische tägliche Bereinigung — retention_cleaner.py |
| Audit-Log | 365 Tage (Standard; konfigurierbar) | Automatische tägliche Bereinigung — retention_cleaner.py |
| Betriebsereignisse (event_stream) | 7 Tage (fest) | Automatische tägliche Bereinigung |
| Upload-Verlauf (upload_history) | 90 Tage (Standard; konfigurierbar via UPLOAD_HISTORY_RETENTION_DAYS) | retention_cleaner.py (v5.9.1) |
| Pipeline-Ergebnisse (runs, artifacts) | Bis zur manuellen Löschung | Keine automatische Bereinigung (geplant) |
| **KI-Kostenprotokoll (cost_log)** | **90 Tage** (Art. 5 Abs. 1 lit. e DSGVO — Datensparsamkeit) | retention_cleaner.py — prune_cost_log() |
| Datenbank-Backups | 90 Tage (empfohlen) | Backup-Zeitplan — vom Operator zu konfigurieren |

**Begründung der Aufbewahrungsfristen:**
- **Audit-Log 365 Tage:** Systemsicherheit, Anomalieerkennung, Forensics (NIST SP 800-92), Geltendmachung von Ansprüchen (Art. 17 Abs. 3 lit. e DSGVO).
- **cost_log 90 Tage:** Datensparsamkeit gemäß Art. 5 Abs. 1 lit. e DSGVO; ausreichend für Abrechnungen und Verteidigung finanzieller Ansprüche.

**Hinweis zur GoBD:** Das Audit-Log ist ein technisches Protokoll, kein kaufmännisches Buch i.S.v. §257 HGB / §147 AO. Die 10-jährige GoBD-Aufbewahrungspflicht gilt nicht.

---

## 5. Übermittlung an externe KI-Anbieter (Auftragsverarbeiter)

SYLION kommuniziert mit externen KI-Modellen. Nachfolgend eine vollständige Liste der aktuellen Auftragsverarbeiter (aktiv und als optional konfiguriert):

| Anbieter | Sitz | Zweck | Übermittlungsschutzmaßnahme | Status |
|---------|------|-------|----------------------------|--------|
| OpenAI, Inc. | USA | Antwortgenerierung (GPT) | EU-US Data Privacy Framework (DPF) + Auftragsverarbeitungsvertrag (AVV) | Aktiv |
| Anthropic, PBC | USA | Antwortgenerierung (Claude) | Standardvertragsklauseln (SCC Modul 2, 2021/914) + AVV | Aktiv |
| Google LLC | USA/EU | Antwortgenerierung (Gemini) | EU-US DPF + AVV | Aktiv |
| Perplexity AI, Inc. | USA | KI-gestützte Suche | SCC Modul 2 (2021/914) + AVV | Aktiv |
| **DeepSeek AI Co., Ltd.** | **China (VRC)** | **Antwortgenerierung (DeepSeek-R1/V3)** | **KEIN Angemessenheitsbeschluss (Art. 45 DSGVO); Transfer Impact Assessment (TIA) ausstehend; SCC Modul 2 — in Verhandlung** | **Optional — in Produktionsumgebung bis Abschluss des TIA deaktiviert** |
| **xAI, Inc.** | **USA** | **Antwortgenerierung (Grok)** | **Standardvertragsklauseln (SCC Modul 2, 2021/914) + AVV — in Prüfung** | **Optional — bis AVV-Verifizierung deaktiviert** |

> **⚠ Warnung — DeepSeek (China):** Die Volksrepublik China verfügt über keinen Angemessenheitsbeschluss der Europäischen Kommission (Art. 45 DSGVO). Die Übermittlung personenbezogener Daten an DeepSeek AI Co., Ltd. erfordert geeignete Garantien (Art. 46 DSGVO), insbesondere SCC Modul 2 und ein abgeschlossenes TIA. Bis zum Abschluss des TIA und der Unterzeichnung der SCC **ist die Aktivierung von DeepSeek im Modus der Verarbeitung personenbezogener Daten untersagt**.

> **Hinweis zu Schrems II:** Jede Übermittlung in Drittländer erfordert ein Transfer Impact Assessment (TIA) gemäß EDPB-Leitlinien 05/2021. OpenAI, Google und Perplexity sind im Rahmen des EU-US DPF zertifiziert; Anthropic verwendet SCC Modul 2 als Grundlage.

> **Empfehlung:** Keine personenbezogenen Daten Dritter in Prompts einfügen.

---

## 6. Datenspeicherort

Alle SYLION-Daten werden **lokal** auf dem Gerät des Operators gespeichert:

```
Datenbank:     ~/sylion/sylion.db  (SQLite)
Backups:       ~/sylion/sylion.db.bak.*.sqlite3
Protokolle:    [konfigurierbares Verzeichnis]
```

Die Daten werden **nicht** automatisch an externe Server übertragen (außer Prompts an externe KI-APIs, siehe § 5).

---

## 7. Ihre Rechte als betroffene Person

| Recht | DSGVO / BDSG | Ausübung |
|-------|-------------|----------|
| Auskunftsrecht | Art. 15 DSGVO | E-Mail an Verantwortlichen; Antwort innerhalb 30 Tagen; Datenexport: GET /api/auth/me/export |
| Berichtigungsrecht | Art. 16 DSGVO | E-Mail an Verantwortlichen |
| Löschungsrecht | Art. 17 DSGVO; **§35 BDSG** (schriftliche Bestätigung der Löschung wird übermittelt) | E-Mail an Verantwortlichen; im System: DELETE /api/auth/me/data |
| Einschränkung der Verarbeitung | Art. 18 DSGVO | E-Mail an Verantwortlichen |
| Datenübertragbarkeit | Art. 20 DSGVO | JSON-Export über API: GET /api/auth/me/export (verfügbar seit v5.9.1) |
| Widerspruchsrecht | Art. 21 DSGVO | E-Mail an Verantwortlichen |

**Hinweis §35 BDSG:** Bei Löschungsanträgen wird eine **schriftliche Bestätigung** übermittelt. Ablehnungen werden mit Rechtsgrundlage begründet (§35 Abs. 5 BDSG).

**Kontakt DSR:** {{CONTACT_EMAIL_DE}}  
**Antwortfrist:** 30 Kalendertage (Verlängerung um 60 Tage bei komplexen Anfragen möglich — Art. 12 Abs. 3 DSGVO; Antragsteller wird vor Ablauf der 30 Tage informiert).

---

## 8. Datensicherheit

SYLION verwendet folgende Sicherheitsmaßnahmen gemäß Art. 32 DSGVO:

- **Passwort-Hashing:** argon2id-Algorithmus (NIST-konform); bcrypt als Fallback.
- **Zugangskontrolle:** RBAC mit Rollen: owner, admin, member.
- **Audit-Log:** Jede Aktion wird mit Zeitstempel und Benutzer protokolliert.
- **WAL-sichere Backups:** Sicherungen vor Datenbankmigrationen.
- **Rate Limiting:** Begrenzung von Anmeldeversuchen (FIX-01, SYLION v5.9.0).
- **Human-Gate:** KI-Entscheidungen erfordern menschliche Bestätigung (Art. 14 KI-Verordnung EU 2024/1689).
- **Sitzungs-Cookies:** HttpOnly, Secure, SameSite=Strict (siehe § 9).

**Bekannte Einschränkungen (Entwicklungsumgebung):**
- SQLite-Datenbank ist nicht verschlüsselt (Plaintext). In Produktionsumgebungen wird Verschlüsselung at-rest empfohlen (SQLCipher oder Äquivalent).
- Backups sind nicht verschlüsselt. In Produktionsumgebungen wird Backup-Verschlüsselung empfohlen.

---

## 9. Beschäftigtendatenschutz (§26 BDSG)

Sofern SYLION von Beschäftigten eines Unternehmens verwendet wird, erfolgt die Verarbeitung der Beschäftigtendaten (Benutzernamen, Audit-Log-Einträge, cost_log) auf Grundlage von §26 Abs. 1 BDSG zur Durchführung des Beschäftigungsverhältnisses und zur IT-Sicherheit.

Sofern ein **Betriebsrat** besteht, ist zu prüfen, ob ein Mitbestimmungsrecht nach §87 BetrVG (Abs. 1 Nr. 6 — technische Überwachungseinrichtungen) besteht. Eine entsprechende Betriebsvereinbarung ist vor dem Einsatz abzuschließen.

---

## 10. Cookies und Rücknahme der Einwilligung

SYLION verwendet **ausschließlich notwendige Cookies** zur Verwaltung der Benutzersitzung. Es werden keine Analyse-, Werbe- oder Tracking-Cookies verwendet.

| Cookie-Name | Typ | Zweck | Lebensdauer | Sicherheitsattribute |
|------------|-----|-------|-------------|----------------------|
| `sylion_session` | Notwendig (Sitzung) | Identifizierung der angemeldeten Sitzung; RBAC-Verwaltung | 24 Stunden | HttpOnly, Secure, SameSite=Strict |
| `_csrf_token` | Notwendig (Sicherheit) | Schutz vor Cross-Site Request Forgery (CSRF) | 30 Minuten | Secure, SameSite=Strict |

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung / Erbringung des Dienstes) — für notwendige Cookies ist keine Einwilligung erforderlich.

**Widerruf / Abmeldung:** Da es sich um für den Betrieb des Dienstes notwendige Cookies handelt, ist ihre Löschung gleichbedeutend mit einer Abmeldung:
- Abmeldung über die SYLION-Oberfläche (löscht das Sitzungs-Cookie),
- Manuelle Cookie-Löschung in den Browsereinstellungen,
- Schließen des Browsers (Sitzung läuft nach 24h unabhängig ab).

---

## 11. Aufsichtsbehörde

Sie haben das Recht, sich bei der zuständigen Datenschutz-Aufsichtsbehörde zu beschweren:

**Bundesebene (Deutschland):**  
Der Bundesbeauftragte für den Datenschutz und die Informationsfreiheit (BfDI)  
Husarenstraße 30, 53117 Bonn  
Tel.: +49 228 997799-0  
E-Mail: poststelle@bfdi.bund.de  
https://www.bfdi.bund.de

**Landesebene:** Zuständig ist die Datenschutzbehörde des Bundeslandes, in dem der Verantwortliche seinen Sitz hat.

---

## 12. Änderungen dieser Datenschutzerklärung

Bei wesentlichen Änderungen der Datenverarbeitung wird diese Datenschutzerklärung aktualisiert und das Datum „Letzte Aktualisierung" geändert. Benutzer werden über Änderungen durch die Systemoberfläche oder per E-Mail informiert. Eine regelmäßige Prüfung der Datei `PP_v591_DE.md` im Projektrepository wird empfohlen.

---

## Ausfüllanleitung für Platzhalter

> Vor Verteilung alle Markierungen durch tatsächliche Daten ersetzen. Diesen Abschnitt nach dem Ausfüllen entfernen.

| Platzhalter | Beschreibung | Beispiel |
|-------------|--------------|---------|
| `{{COMPANY_NAME_DE}}` | Vollständiger Firmenname oder Name des Verantwortlichen | RSDG GmbH |
| `{{ADDRESS_DE}}` | Firmenanschrift (Straße, PLZ, Stadt) | Musterstraße 1, 10115 Berlin |
| `{{HRB_UST_DE}}` | HRB-Nummer (GmbH) oder Steuernummer | HRB 123456 B, USt-IdNr.: DE123456789 |
| `{{CONTACT_EMAIL_DE}}` | E-Mail-Adresse für DSGVO-/DSR-Kontakt | datenschutz@rsdg.de |

---

*Datenschutzerklärung v5.9.1 | SYLION v5.9.1 | Final Draft — rechtliche Prüfung vor kommerziellem Vertrieb erforderlich.*  
*Erstellt: Legal Re-Audit Council, 2026-04-19.*  
*Ersetzt v1.0 (SYLION v5.9.0): §5 aktualisiert (DeepSeek, xAI), §10 (Cookies), §4 (cost_log Aufbewahrung), Versionierungsschema.*
