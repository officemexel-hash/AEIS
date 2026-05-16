# Auftragsverarbeitungsvertrag (AVV)

**gemäß Art. 28 der Verordnung (EU) 2016/679 (DSGVO)**

**Version:** 1.0  
**Datum:** 2026-04-19  
**Produkt:** SYLION Pipeline v5.9.1

---

## Parteien

**Verantwortlicher (Auftraggeber):**

```
Name:       {{CLIENT_COMPANY_NAME}}
Anschrift:  {{CLIENT_ADDRESS}}
HRB/USt:    {{CLIENT_HRB_UST}}
E-Mail:     {{CLIENT_CONTACT_EMAIL}}
```

(nachfolgend „**Verantwortlicher**")

**Auftragsverarbeiter (Auftragnehmer):**

```
Name:       {{COMPANY_NAME_DE}}
Anschrift:  {{ADDRESS_DE}}
HRB/USt:    {{HRB_UST_DE}}
E-Mail:     {{CONTACT_EMAIL_DE}}
```

(nachfolgend „**Auftragsverarbeiter**")

Verantwortlicher und Auftragsverarbeiter werden nachfolgend gemeinsam als „**Parteien**" bezeichnet.

---

## Präambel

Die Parteien haben einen Hauptvertrag über die Nutzung der Software SYLION Pipeline v5.9.1 (nachfolgend „**Hauptvertrag**") geschlossen, im Rahmen dessen der Auftragsverarbeiter personenbezogene Daten verarbeiten kann, die vom Verantwortlichen übermittelt werden. Dieser Auftragsverarbeitungsvertrag (nachfolgend „**AVV**") legt die detaillierten Grundsätze der Verarbeitung personenbezogener Daten gemäß den Anforderungen des Art. 28 Abs. 3 DSGVO fest.

---

## §1. Gegenstand, Charakter und Zweck der Verarbeitung

1. Gegenstand dieses AVV ist die Beauftragung des Auftragsverarbeiters durch den Verantwortlichen mit der Verarbeitung personenbezogener Daten im Zusammenhang mit der Erbringung von SYLION-Pipeline-v5.9.1-Diensten.
2. Art der Verarbeitung: technische Verarbeitung — Authentifizierung, Sitzungsverwaltung, Audit-Protokollierung, KI-Pipeline-Orchestrierung.
3. **Zweck der Verarbeitung:** Erbringung des Dienstes gemäß dem Hauptvertrag — Code-Analyse, Dashboard-Verwaltung, Erstellung von KI-Berichten.
4. Die Verarbeitung erfolgt ausschließlich auf **dokumentierte Weisung des Verantwortlichen**, es sei denn, der Auftragsverarbeiter ist nach dem Recht der Union oder der Mitgliedstaaten zur Verarbeitung verpflichtet (in diesem Fall informiert der Auftragsverarbeiter den Verantwortlichen vor Beginn der Verarbeitung über diese Rechtspflicht, sofern dieses Recht eine solche Information nicht aus wichtigen Gründen des öffentlichen Interesses verbietet).

---

## §2. Dauer der Verarbeitung

Die Verarbeitung personenbezogener Daten erfolgt für die Dauer des Hauptvertrags. Nach dessen Ablauf oder Kündigung löscht oder gibt der Auftragsverarbeiter alle übermittelten personenbezogenen Daten an den Verantwortlichen zurück, gemäß §10 dieses AVV.

---

## §3. Art der personenbezogenen Daten

Im Rahmen dieses AVV verarbeitet der Auftragsverarbeiter folgende Kategorien personenbezogener Daten:

| Kategorie | Beispiele | Aufbewahrungsfrist |
|-----------|-----------|-------------------|
| Operatorkontodaten | Benutzername, Passwort-Hash (argon2id) | Bis zur Kontolöschung |
| Sitzungsdaten | Sitzungs-ID, IP-Adresse, Anmeldezeit, RBAC-Rolle | 30 Tage nach Ablauf |
| Audit-Log (Ereignisprotokoll) | Benutzername, Aktionstyp, Zeitstempel, Objekt-ID | 365 Tage |
| Upload-Verlauf | Benutzer-ID, Dateiname, Zeitstempel | 90 Tage |
| KI-Kostenprotokoll (cost_log) | user_id, KI-Modell, Token-Anzahl, Kosten | 90 Tage |
| Prompt-Inhalte (soweit pers. Daten enthalten) | Code, Anfragen, Dokumente | Dauer der Sitzung / Pipeline-Ausführung |

> Der Verantwortliche ist dafür verantwortlich, dass die übermittelten Daten gemäß DSGVO verarbeitet werden, insbesondere im Hinblick auf die Rechtsgrundlage der Verarbeitung.

**Besondere Kategorien personenbezogener Daten (Art. 9 DSGVO):** SYLION Pipeline ist **nicht** für die Verarbeitung besonderer Datenkategorien vorgesehen. Der Verantwortliche verpflichtet sich, solche Daten ohne vorherige Zustimmung des Auftragsverarbeiters und ohne entsprechende Rechtsgrundlage nicht in das System einzugeben.

---

## §4. Kategorien betroffener Personen

Folgende Kategorien betroffener Personen sind von der Verarbeitung betroffen:
- Systemoperatoren (Mitarbeiter oder Auftragnehmer des Verantwortlichen, die SYLION Pipeline nutzen),
- Personen, deren Daten möglicherweise in Prompt-Inhalten und zur Analyse übermittelten Dokumenten enthalten sind (soweit der Verantwortliche solche Daten übermittelt — der Verantwortliche trägt die Verantwortung dafür).

---

## §5. Pflichten des Auftragsverarbeiters

Der Auftragsverarbeiter verpflichtet sich zu:

### 5.1 Verarbeitung nur auf Weisung
Verarbeitung personenbezogener Daten ausschließlich auf dokumentierte Weisung des Verantwortlichen (einschließlich der Übermittlung von Daten in Drittländer), es sei denn, eine Rechtspflicht schreibt eine Verarbeitung vor.

### 5.2 Vertraulichkeit des Personals
Sicherstellung, dass alle zur Verarbeitung personenbezogener Daten befugten Personen einer Vertraulichkeitspflicht unterliegen oder einer angemessenen gesetzlichen Verschwiegenheitspflicht unterliegen.

### 5.3 Technische und organisatorische Maßnahmen (Art. 32 DSGVO)
Implementierung geeigneter technischer und organisatorischer Maßnahmen, insbesondere:
- Passwort-Hashing mit argon2id;
- RBAC (rollenbasierte Zugriffskontrolle);
- Audit-Log jeder Aktion mit Zeitstempel;
- Rate Limiting für Anmeldeversuche;
- Sitzungs-Cookies: HttpOnly, Secure, SameSite=Strict;
- Automatisierte Aufbewahrung und Bereinigung gemäß §3.

### 5.4 Unterauftragsverarbeiter (Art. 28 Abs. 2 und 4 DSGVO)
Einhaltung der in §6 dieses AVV beschriebenen Grundsätze.

### 5.5 Unterstützung bei der Wahrnehmung von Betroffenenrechten
Unterstützung des Verantwortlichen nach Möglichkeit bei der Erfüllung seiner Pflicht, Anfragen zur Ausübung der in Art. 15–22 DSGVO genannten Rechte der betroffenen Person zu beantworten (Auskunft, Berichtigung, Löschung, Einschränkung, Übertragbarkeit, Widerspruch).  
**Verfügbare technische Mechanismen:** GET /api/auth/me/export (Art. 15, 20), DELETE /api/auth/me/data (Art. 17).

### 5.6 Unterstützung bei Datenschutzverletzungen
Im Falle der Feststellung einer Verletzung des Schutzes personenbezogener Daten benachrichtigt der Auftragsverarbeiter den Verantwortlichen **unverzüglich, spätestens innerhalb von 24 Stunden** nach Feststellung der Verletzung, um dem Verantwortlichen die Einhaltung der 72-Stunden-Meldefrist gegenüber dem BfDI zu ermöglichen (Art. 33 DSGVO). Die Benachrichtigung enthält: Beschreibung der Art der Verletzung, Kategorien und ungefähre Anzahl der betroffenen Personen, Beschreibung der wahrscheinlichen Folgen, Beschreibung der ergriffenen oder vorgeschlagenen Abhilfemaßnahmen.

### 5.7 Unterstützung bei DSFA
Unterstützung des Verantwortlichen bei der Durchführung von Datenschutz-Folgenabschätzungen (Art. 35 DSGVO) und der vorherigen Konsultation mit der Aufsichtsbehörde (Art. 36 DSGVO).

### 5.8 Löschung oder Rückgabe der Daten
Nach Abschluss der Erbringung von Verarbeitungsleistungen löscht oder gibt der Auftragsverarbeiter nach Wahl des Verantwortlichen alle personenbezogenen Daten zurück und löscht vorhandene Kopien, sofern nicht nach dem Unionsrecht oder dem deutschen Recht eine Speicherpflicht für die personenbezogenen Daten besteht. Frist: 30 Tage nach Ablauf oder Kündigung des Hauptvertrags.

### 5.9 Nachweispflicht und Auditrecht
Dem Verantwortlichen alle erforderlichen Informationen zur Verfügung zu stellen, um die Einhaltung der in Art. 28 DSGVO niedergelegten Pflichten nachweisen zu können, sowie Audits (einschließlich Inspektionen) durch den Verantwortlichen oder einen von diesem beauftragten Prüfer zu ermöglichen.  
Bevorzugt wird zunächst: SOC 2 Type II-Bericht (falls verfügbar) oder Sicherheitsfragebogen. Ein Vor-Ort-Audit ist mit einer Vorankündigung von 30 Tagen möglich, höchstens einmal pro Jahr, auf Kosten des Verantwortlichen.

---

## §6. Unterauftragsverarbeiter

1. Der Verantwortliche erteilt eine allgemeine schriftliche Genehmigung (Art. 28 Abs. 2 DSGVO) für die Nutzung der nachfolgend aufgeführten Unterauftragsverarbeiter.
2. Der Auftragsverarbeiter informiert den Verantwortlichen über beabsichtigte Änderungen (Hinzufügung oder Ersetzung) von Unterauftragsverarbeitern mit einem Vorlauf von **14 Tagen**, um dem Verantwortlichen die Möglichkeit zu geben, Einwände zu erheben.
3. Aktuelle Liste der Unterauftragsverarbeiter:

| Unterauftragsverarbeiter | Sitz | Verarbeitungszweck | Übermittlungsschutz |
|-------------------------|------|-------------------|---------------------|
| OpenAI, Inc. | USA | Externes KI-Modell — GPT | EU-US DPF + AVV mit OpenAI |
| Anthropic, PBC | USA | Externes KI-Modell — Claude | SCC Modul 2 (2021/914) + AVV mit Anthropic |
| Google LLC | USA/EU | Externes KI-Modell — Gemini | EU-US DPF + AVV mit Google |
| Perplexity AI, Inc. | USA | KI-gestützte Suche | SCC Modul 2 (2021/914) + AVV mit Perplexity |
| xAI, Inc. | USA | Externes KI-Modell — Grok | SCC Modul 2 (2021/914) + AVV in Prüfung |
| DeepSeek AI Co., Ltd. | China | Externes KI-Modell — DeepSeek | **TIA ausstehend — bedingte Aktivierung** |

4. Der Auftragsverarbeiter stellt sicher, dass Unterauftragsverarbeitern dieselben Datenschutzpflichten auferlegt werden wie in diesem AVV festgelegt (Art. 28 Abs. 4 DSGVO).
5. Der Auftragsverarbeiter haftet gegenüber dem Verantwortlichen in vollem Umfang dafür, dass der Unterauftragsverarbeiter seine Pflichten erfüllt.

---

## §7. Drittlandübermittlungen

1. Übermittlungen von Daten an Unterauftragsverarbeiter mit Sitz außerhalb des Europäischen Wirtschaftsraums (EWR) erfolgen ausschließlich mit geeigneten Garantien (Art. 46 DSGVO):
   - Standardvertragsklauseln (SCC) Modul 2 (Beschluss 2021/914 der Kommission) — siehe Anlage SCC_Module_2.md,
   - Angemessenheitsbeschluss (EU-US DPF für qualifizierte US-Unternehmen),
   - Transfer Impact Assessment (TIA) gemäß EDPB-Leitlinien 05/2021.
2. Für DeepSeek AI Co., Ltd. (China): Die Übermittlung personenbezogener Daten ist bis zum Abschluss des TIA und der Unterzeichnung der SCC Modul 2 untersagt.

---

## §8. Pflichten des Verantwortlichen

Der Verantwortliche verpflichtet sich:
1. Dem Auftragsverarbeiter nur personenbezogene Daten zu übermitteln, die gemäß DSGVO erhoben wurden, insbesondere mit einer gültigen Rechtsgrundlage der Verarbeitung.
2. Besondere Datenkategorien (Art. 9 DSGVO) ohne vorherige Zustimmung des Auftragsverarbeiters nicht in Prompts einzugeben.
3. Den Auftragsverarbeiter unverzüglich über Änderungen im Umfang der verarbeiteten personenbezogenen Daten zu informieren.
4. Geeignete technische Ressourcen (Verschlüsselung, Zugriffskontrolle) für die Produktionsumgebung gemäß den Empfehlungen des Auftragsverarbeiters bereitzustellen.

---

## §9. Ansprechpartner und Kontaktpunkte

| Partei | AVV-Ansprechpartner | E-Mail |
|--------|---------------------|--------|
| Verantwortlicher | {{CLIENT_DPA_CONTACT}} | {{CLIENT_CONTACT_EMAIL}} |
| Auftragsverarbeiter | {{COMPANY_DPA_CONTACT}} | {{CONTACT_EMAIL_DE}} |

---

## §10. Rückgabe / Löschung der Daten nach Vertragsende

1. Innerhalb von 30 Tagen nach Ablauf oder Kündigung des Hauptvertrags:
   a) Nach Wahl des Verantwortlichen: löscht der Auftragsverarbeiter alle personenbezogenen Daten oder gibt sie im JSON/CSV-Format zurück und bestätigt die Löschung schriftlich;  
   b) Der Auftragsverarbeiter löscht Daten aus allen Backups gemäß dem regulären Zeitplan (max. 90 Tage).
2. Der Auftragsverarbeiter behält das Recht, personenbezogene Daten nur in dem Umfang und für die Dauer aufzubewahren, wie es nach dem Unionsrecht oder dem deutschen Recht erforderlich ist.

---

## §11. Anwendbares Recht und Gerichtsstand

Dieser AVV unterliegt dem Recht der Bundesrepublik Deutschland. Für alle Streitigkeiten aus diesem AVV ist der Gerichtsstand am Sitz des Auftragsverarbeiters vereinbart.

---

## §12. Schlussbestimmungen

1. Dieser AVV ist Bestandteil des Hauptvertrags.
2. Bei Widersprüchen zwischen diesem AVV und dem Hauptvertrag im Bereich des Datenschutzes hat dieser AVV Vorrang.
3. Änderungen dieses AVV bedürfen der Schriftform.

---

## Anlagen

- Anlage 1: Liste der Unterauftragsverarbeiter (vom Auftragsverarbeiter aktualisiert)
- Anlage 2: Technische und organisatorische Maßnahmen (TOM)
- Anlage 3: Standardvertragsklauseln — SCC Modul 2 (siehe: SCC_Module_2.md)

---

**Unterschriften:**

| Verantwortlicher | Auftragsverarbeiter |
|------------------|---------------------|
| {{CLIENT_COMPANY_NAME}} | {{COMPANY_NAME_DE}} |
| Ort, Datum: _________________ | Ort, Datum: _________________ |
| Unterschrift: ________________ | Unterschrift: ________________ |
| Funktion: ___________________ | Funktion: ___________________ |

---

## Ausfüllanleitung für Platzhalter

| Platzhalter | Beschreibung |
|-------------|--------------|
| `{{CLIENT_COMPANY_NAME}}` | Vollständiger Firmenname des Verantwortlichen (Kunde) |
| `{{CLIENT_ADDRESS}}` | Anschrift des Verantwortlichen |
| `{{CLIENT_HRB_UST}}` | HRB-Nummer und USt-IdNr. des Verantwortlichen |
| `{{CLIENT_CONTACT_EMAIL}}` | Datenschutz-Kontakt-E-Mail des Verantwortlichen |
| `{{CLIENT_DPA_CONTACT}}` | Name und Funktion des AVV-Ansprechpartners beim Verantwortlichen |
| `{{COMPANY_NAME_DE}}` | Vollständiger Firmenname des Auftragsverarbeiters |
| `{{ADDRESS_DE}}` | Anschrift des Auftragsverarbeiters |
| `{{HRB_UST_DE}}` | HRB-Nummer und USt-IdNr. des Auftragsverarbeiters |
| `{{CONTACT_EMAIL_DE}}` | Datenschutz-Kontakt-E-Mail des Auftragsverarbeiters |
| `{{COMPANY_DPA_CONTACT}}` | Name und Funktion des AVV-Ansprechpartners beim Auftragsverarbeiter |

---

*Auftragsverarbeitungsvertrag v1.0 | SYLION Pipeline v5.9.1 | 2026-04-19*  
*Rechtsgrundlage: Art. 28 der Verordnung (EU) 2016/679 (DSGVO).*  
*Das Dokument erfordert eine rechtliche Überprüfung durch einen Rechtsanwalt vor der Unterzeichnung.*
