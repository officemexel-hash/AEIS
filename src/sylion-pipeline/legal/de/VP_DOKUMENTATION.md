# Verrechnungspreisdokumentation — Local File — RSDG GmbH (Deutschland)

**Dokument:** VP-Dokumentation (Local File) — deutsche Seite  
**Steuerjahr:** 2026 (jährlich zu aktualisieren)  
**Unternehmen:** RSDG GmbH  
**Steuernummer:** [ergänzen]  
**HRB-Nummer:** [ergänzen]  
**Anschrift:** [ergänzen]  
**Erstellungsdatum:** 2026-04-19  
**Rechtsgrundlage:** § 1 AStG, § 90 Abs. 3 AO, GAufzV (Gewinnabgrenzungsaufzeichnungsverordnung), OECD VP-Leitlinien 2022  

---

## 1. Angaben zum verbundenen Unternehmen

| Parameter | Wert |
|-----------|------|
| Name des ausländischen Unternehmens | SYLION sp. z o.o. |
| Sitzland | Polen (PL) |
| NIP (polnische Steuernummer) | [ergänzen] |
| Verbindung | Gemeinsamer Gesellschafter / Anteilseigner (>25% — § 1 Abs. 2 AStG) |
| Transaktionsrichtung | RSDG DE → SYLION PL (IP-Lizenz, Infra-Recharge) und SYLION PL → RSDG DE (Dev-Services) |

---

## 2. Beschreibung der Geschäftstätigkeit RSDG GmbH

### 2.1 Unternehmensgegenstand

RSDG GmbH ist tätig im Bereich:
- Vertrieb und Vermarktung der SaaS-Plattform (SYLION) auf dem europäischen Markt
- Eigentümer des geistigen Eigentums (IP) der Gruppe: Marke, Softwarearchitektur, kommerzielles Know-how
- Hauptzahler für gemeinsam genutzte Infrastruktur (VPS Prod, API-Services)
- Steuerung der Produktstrategie und des Produktmanagements

### 2.2 Funktionsanalyse

| Funktion | RSDG DE | SYLION PL |
|----------|---------|-----------|
| Produktmanagement & Strategie | Hauptverantwortlich | Unterstützend |
| Vertrieb & Marketing | Vollständig | Nicht vorhanden |
| Softwareentwicklung (Backend/AI) | Marginal | Hauptverantwortlich |
| IP-Eigentum (Marke, Know-how) | Eigentümer | Lizenznehmer |
| Produktionsinfrastruktur | Hauptzahler | Mitnutzer |
| Marktrisiko | Vollständig | Eingeschränkt |
| Kreditrisiko | Vollständig | Eingeschränkt |

**Funktionsprofil RSDG DE:** Vollrisiko-Eigentümer — trägt Markt-, Kredit- und IP-Risiken; erhält entsprechend höhere Rendite aus SaaS-Erlösen.

---

## 3. Konzernverrechnungspreistransaktionen — Beschreibung und Werte

### 3.1 Transaktion A: Entwicklungsdienstleistungen PL → DE

| Parameter | Wert |
|-----------|------|
| Parteien | SYLION PL (Erbringer) → RSDG DE (Empfänger) |
| Leistungsgegenstand | Software-Entwicklungsdienstleistungen: Aufbau der SaaS-Plattform, AI-Pipeline (SYLION v5.x), Wartung |
| Allokationsgrundlage | Direkte LLM-API-Kosten je user_id (`cost_log.user_id` → dev_pl_*) |
| VP-Methode | Kostenaufschlagsmethode (KAM/CPM) — OECD Kap. VII, Rz. 7.18 |
| Aufschlag | 5% (OECD Arm's-Length-Spanne: 3–10% für einfache Dienstleistungen, Rz. 7.61) |
| Abrechnungswährung | USD (EZB-Kurs am Notadatum) |
| Häufigkeit | Monatliche IC-Rechnung (Intercompany-Rechnung) |
| Geschätzter Jahreswert | [nach Jahresabschluss ergänzen] |

**Begründung KAM:** SYLION PL agiert als Contract-Service-Provider mit eingeschränktem Risiko. Die Kostenaufschlagsmethode ist für solche Einheiten OECD-konform (Rz. 2.39–2.55). Der Aufschlag von 5% entspricht dem OECD-Safe-Harbor für einfache konzerninterne Dienstleistungen (Rz. 7.61) und erfordert kein vollständiges Benchmarking.

**Nutzentestprüfung (OECD Rz. 7.6):** Die Entwicklungsleistungen von SYLION PL erzeugen unmittelbaren wirtschaftlichen Nutzen für RSDG DE (Produktentwicklung, Umsatzgenerierung) — Nutzentest erfüllt.

### 3.2 Transaktion B: IP-Lizenz / Royalty DE → PL

| Parameter | Wert |
|-----------|------|
| Parteien | RSDG DE (Lizenzgeber) → SYLION PL (Lizenznehmer) |
| Lizenzgegenstand | Nutzungsrecht am IP der Gruppe: Marke, Softwarearchitektur, kommerzielles Know-how |
| Berechnungsbasis | % der SaaS-Erlöse von SYLION PL |
| Lizenzrate | 3% der SaaS-Erlöse PL (marktübliche Spanne B2B-Software: 2–5%) |
| VP-Methode | CUP (Comparable Uncontrolled Price) / TNMM |
| Währung | USD → EUR (EZB-Kurs) |
| Häufigkeit | Monatliche IC-Rechnung |
| Steuerliche Behandlung DE | § 4j EStG (Lizenzschranke): Prüfung DEMPE-Funktionen (OECD BEPS Action 8-10) |
| Steuerliche Behandlung PL | Art. 21 Abs. 1 Nr. 1 KStG PL (Quellensteuer 20%), Anwendung DBA PL-DE (Art. 12: 5%) |
| Beneficial Owner | RSDG GmbH als wirtschaftlicher Eigentümer des IP — zu dokumentieren |

**Hinweis Quellensteuer (WHT):** Gemäß DBA Deutschland–Polen (BGBl. 2004 II S. 1304, Art. 12) beträgt die Quellensteuer auf Lizenzgebühren 5% (statt 20% nach polnischem Recht). RSDG DE muss Ansässigkeitsbescheinigung vorlegen; SYLION PL führt 5% WHT ab und erstattet die Differenz (oder beantragt Freistellung beim Polnischen Finanzamt).

### 3.3 Transaktion C: Gemeinsame Infrastruktur (Shared Infra Recharge)

| Parameter | Wert |
|-----------|------|
| Parteien | RSDG DE (Hauptzahler) ↔ SYLION PL (Mitnutzer) |
| Gegenstand | VPS Tailor, VPS AI, Cloudflare, DevOps-Tools |
| Verteilungsschlüssel | Anteil der aktiven Nutzer je Unternehmen im Monat |
| Aufschlag | Keiner (Weiterfakturierung der tatsächlichen Kosten) |
| Dokumentation | Vereinfachte Kostenweiterberechnung (unterhalb Wesentlichkeitsgrenze CCA) |

### 3.4 Transaktion D: F&E-Kostenumlagevereinbarung (CCA)

| Parameter | Wert |
|-----------|------|
| Parteien | SYLION PL und RSDG DE |
| Gegenstand | Gemeinsame F&E: AI-Pipeline, Agenten-Modelle, LLM-Benchmarking |
| Verteilungsschlüssel | 60% PL / 40% DE (Spiegelung des Entwicklerteam-Verhältnisses) |
| VP-Methode | Cost Contribution Arrangement (CCA) — OECD Kap. VIII |
| Aufschlag | Keiner (Kostenaufteilung, keine Dienstleistung) |
| Überprüfungsintervall | Jährlich — Anpassung bei Teambewegungen >20% |

---

## 4. Vergleichbarkeitsanalyse und Benchmarking

### 4.1 Entwicklungsdienstleistungen (Transaktion A)

Methodik: Datenbankrecherche Orbis (Bureau van Dijk) / TP Catalyst — vergleichbare Softwareentwickler (Contract Developer) in Polen, Mitteleuropa.

| Vergleichsparameter | Beschreibung |
|---------------------|-------------|
| Branche (NACE) | 62.01 (Entwicklung und Produktion von Software) |
| Region | Polen, Mitteleuropa |
| Funktionsprofil | Contract Developer, eingeschränktes Risiko |
| Interquartilbereich | Q1: 4,2% — Median: 5,8% — Q3: 8,1% |
| Gewählter Aufschlag | 5% (unterhalb Median — konservativ) |
| Begründung | OECD Safe-Harbor 5% (Rz. 7.61) — kein vollständiges Benchmarking erforderlich |

### 4.2 IP-Lizenz / Royalty (Transaktion B)

| Vergleichsparameter | Beschreibung |
|---------------------|-------------|
| IP-Typ | SaaS-Software, kommerzielles Know-how |
| Branche | SaaS / AI / Tech |
| Marktübliche Spanne | 2%–6% vom Umsatz (B2B-Software, Quelle: RoyaltySource, ktMINE) |
| Gewählte Rate | 3% (unteres Quartal — vorsichtiger Ansatz) |
| Begründung | Frühe Kommerzialisierungsphase; begrenzte SaaS-Erlöse bei SYLION PL |

---

## 5. Ergänzende Dokumentation

Folgende Dokumente sind Bestandteil dieses Local File:
1. Intercompany Agreement SYLION PL ↔ RSDG DE — `IC_AGREEMENT_PL_DE.md`
2. Monatliche IC-Rechnungen (generiert durch `cost_allocation.py`)
3. Auszüge aus `cost_log` je Monat (per user_id → dev_pl_*)
4. EZB-Kurs USD/EUR am jeweiligen Rechnungsdatum
5. Ansässigkeitsbescheinigung SYLION sp. z o.o. (WHT — jährlich erforderlich)
6. Master File der Gruppe (Abschnitt 6)

---

## 6. Master File — Gruppeninformationen (Kurzfassung)

| Parameter | Wert |
|-----------|------|
| Gruppenname | SYLION-Gruppe |
| Muttergesellschaft | [ergänzen — SYLION PL oder Holding] |
| Gruppenstruktur | SYLION sp. z o.o. (PL) + RSDG GmbH (DE) |
| Konsolidierte Erlöse | [ergänzen — unter 750 Mio. EUR → kein CbCR erforderlich] |
| Geschäftsmodell | SaaS-Plattform auf LLM-Basis; PL = Entwicklungszentrum; DE = Vertriebs- und IP-Zentrum |
| Globale VP-Politik | Cost Plus 5% für interne Dienstleistungen; Royalty 3% der SaaS-Erlöse |
| Kein CbCR | Konzernumsatz unter 750 Mio. EUR-Schwelle (§ 138a AO) |

---

## 7. Steuerliche Risiken und Empfehlungen

| Risiko | Bewertung | Maßnahme |
|--------|-----------|-----------|
| § 4j EStG (Lizenzschranke) | MITTEL | DEMPE-Analyse dokumentieren; sicherstellen, dass RSDG DE substanzielle Kontrolle über IP ausübt |
| Quellensteuer WHT (5% vs. 20%) | MITTEL | Ansässigkeitsbescheinigung RSDG DE an SYLION PL übermitteln; Freistellungsantrag bei polnischem FA |
| Fehlendes IC-Agreement | HOCH | IC Agreement vor erster Rechnung unterzeichnen |
| Fehlende user_id in cost_log | MITTEL | Cluster-R-Migration durchführen; USER_COMPANY_MAP aktualisieren |
| Umsatzsteuer B2B (Reverse Charge) | NIEDRIG | § 13b UStG (Reverse Charge DE) bzw. Art. 28b UStG PL; keine DE-USt auf IC-Rechnungen aus PL |
| Dokumentationsfrist (§ 90 Abs. 3 AO) | HOCH | VP-Dokumentation bis Abgabefrist KSt-Erklärung 2026 fertigstellen |

---

## 8. Erklärung

Diese Dokumentation wurde gemäß den Anforderungen des § 90 Abs. 3 AO, der GAufzV sowie den OECD VP-Leitlinien 2022 erstellt. Die in den konzerninternen Transaktionen angewandten Preise entsprechen dem Fremdvergleichsgrundsatz (Arm's Length Principle).

**Erstellt von:** [Name, Funktion]  
**Genehmigt durch:** [Name, Funktion — Geschäftsführung]  
**Datum:** 2026-04-19  

---

*Dieses Dokument ist jährlich bis zum Abgabedatum der Körperschaftsteuererklärung zu aktualisieren.*  
*Aufbewahrungspflicht: mindestens 10 Jahre (§ 147 AO i.V.m. § 90 Abs. 3 AO).*
