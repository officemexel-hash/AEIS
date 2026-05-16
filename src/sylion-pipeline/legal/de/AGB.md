# Allgemeine Geschäftsbedingungen — SYLION Pipeline

**Produkt:** SYLION Pipeline v5.9.1  
**Dokumentversion:** 1.0  
**Datum:** 2026-04-19  
**Anbieter:** {{COMPANY_NAME_DE}} (nachfolgend „Anbieter")  
**Anschrift:** {{ADDRESS_DE}} | **HRB/USt:** {{HRB_UST_DE}}  
**Kontakt:** {{CONTACT_EMAIL_DE}}

> **PLATZHALTER — VOR VERTEILUNG AUSFÜLLEN:** Ersetzen Sie alle `{{…}}`-Markierungen durch  
> tatsächliche Daten. Diese AGB gelten ausschließlich für B2B-Verhältnisse (zwischen Unternehmern i.S.v. §14 BGB).  
> Vor Verteilung ist eine rechtliche Überprüfung durch einen Rechtsanwalt erforderlich.

---

## §1. Geltungsbereich und allgemeine Bestimmungen

1. Diese Allgemeinen Geschäftsbedingungen (nachfolgend „AGB") regeln die Bedingungen für die Nutzung der Software SYLION Pipeline (nachfolgend „Dienst") durch Unternehmer (nachfolgend „Kunde").
2. Diese AGB gelten ausschließlich für B2B-Verhältnisse — zwischen Unternehmern i.S.v. §14 BGB. Diese AGB gelten **nicht für Verbraucher** i.S.v. §13 BGB.
3. Ein Vertrag kommt durch schriftliche (oder elektronische mit qualifizierter elektronischer Signatur) Annahme des Angebots des Anbieters oder durch die erste Aktivierung des Lizenz- oder API-Schlüssels durch den Kunden zustande.
4. Abweichende Einkaufsbedingungen oder sonstige Geschäftsbedingungen des Kunden sind unwirksam, es sei denn, der Anbieter hat ihnen ausdrücklich schriftlich zugestimmt.
5. Gegenüber Unternehmern i.S.d. §14 BGB ist §305c BGB (überraschende Klauseln) und §307 BGB (unangemessene Benachteiligung) im durch das B2B-Recht zulässigen Umfang abbedungen.

---

## §2. Beschreibung des Dienstes und Lizenzumfang

1. SYLION Pipeline ist eine **lokale KI-Software** für Code-Auditing und Analyse, die auf der Infrastruktur des Kunden betrieben wird (On-Premise oder Private Cloud).
2. Der Dienst wird unter den Bedingungen der MIT-Lizenz (Datei `LICENSE.md`) mit den Einschränkungen dieser AGB bereitgestellt.
3. Die Lizenz umfasst:
   - Installation und Betrieb des Dienstes auf der Infrastruktur des Kunden;
   - Nutzung der Benutzeroberfläche (Dashboard) und der SYLION-API;
   - Zugang zur technischen Dokumentation.
4. Die Lizenz umfasst **nicht**:
   - Modifikation des Quellcodes zwecks Vertrieb als eigenständiges Produkt;
   - Unterlizenzierung ohne schriftliche Zustimmung des Anbieters;
   - Zugang zu externen KI-Modellen (OpenAI, Anthropic, Google, Perplexity, xAI, DeepSeek) — der Kunde schließt mit diesen Anbietern separate Verträge auf eigene Kosten und eigenes Risiko.
5. Der Anbieter behält sich das Recht vor, den Dienst zu aktualisieren. Aktualisierungen, die die Funktionalität wesentlich verändern, erfordern eine vorherige Benachrichtigung des Kunden mit einem Vorlauf von 14 Tagen.

---

## §3. Kein SLA — Leistung „as-is"

1. **Der Dienst wird im vorhandenen Zustand ("as-is") bereitgestellt**, ohne Garantie für ununterbrochenen Betrieb, Fehlerfreiheit, Eignung für einen bestimmten Zweck oder das Erzielen bestimmter Ergebnisse.
2. Der Anbieter **garantiert nicht** (sofern nicht in einem separaten SLA-Vertrag schriftlich vereinbart):
   - eine bestimmte Verfügbarkeit des Dienstes (kein SLA);
   - Antwortzeiten der APIs externer KI-Anbieter;
   - Betriebskontinuität bei Updates.
3. SYLION ist ein **Entwicklerwerkzeug** — alle durch KI verarbeiteten Daten erfordern eine menschliche Überprüfung. Geschäftliche, rechtliche oder finanzielle Entscheidungen, die ausschließlich auf KI-Ergebnissen basieren, erfolgen auf Risiko des Kunden.
4. Die lokale SQLite-Umgebung (Dev) ist nicht verschlüsselt — die Produktionskonfiguration liegt in der Verantwortung des Kunden.

---

## §4. Vergütung und Zahlungsbedingungen

1. Die Vergütung des Anbieters wird in einem separaten Auftrag oder einem kommerziellen Angebot festgelegt.
2. Rechnungen werden gemäß dem im Auftrag angegebenen Zahlungsplan ausgestellt.
3. Zahlungsziel: 14 Tage ab Rechnungsdatum, sofern im Auftrag nichts anderes vereinbart ist.
4. Bei Zahlungsverzug werden Verzugszinsen in Höhe von 9 Prozentpunkten über dem Basiszinssatz (§288 Abs. 2 BGB) berechnet.
5. Der Anbieter behält sich das Recht vor, den Zugang zum Dienst bei Zahlungsverzug von mehr als 30 Tagen nach erfolgloser Mahnung zu sperren.
6. Alle Preise verstehen sich als Nettopreise und sind zzgl. der gesetzlichen Mehrwertsteuer.
7. Der Anbieter ist berechtigt, eine Pauschale für Verzugsschäden gemäß §288 Abs. 5 BGB (40 EUR) geltend zu machen.

---

## §5. Haftungsbeschränkung

1. **Die Gesamthaftung des Anbieters** gegenüber dem Kunden aus und im Zusammenhang mit diesem Vertrag ist auf die Nettovergütung begrenzt, die der Kunde in den letzten **12 Monaten** vor dem haftungsbegründenden Ereignis gezahlt hat.
2. Der Anbieter haftet **nicht** für:
   a) mittelbare Schäden, Folgeschäden, entgangenen Gewinn, Datenverlust, Reputationsschäden;  
   b) Betriebsunterbrechungen aufgrund von Ausfällen der Infrastruktur des Kunden, externer KI-Anbieter oder höherer Gewalt;  
   c) KI-Analyseergebnisse — der Kunde trägt die alleinige Verantwortung für auf deren Grundlage getroffene Entscheidungen;  
   d) DSGVO-Verstöße, die daraus resultieren, dass der Kunde entgegen den Empfehlungen des Anbieters personenbezogene Daten in Prompts eingegeben hat.
3. Die vorstehenden Haftungsbeschränkungen gelten nicht bei:
   a) Schäden durch Vorsatz oder grobe Fahrlässigkeit des Anbieters;  
   b) Verletzungen von Leben, Körper oder Gesundheit;  
   c) Verletzung wesentlicher Vertragspflichten (Kardinalpflichten) — in diesem Fall ist die Haftung auf den typischen, vorhersehbaren Schaden begrenzt;  
   d) Ansprüchen nach dem Produkthaftungsgesetz (ProdHaftG).
4. Der Kunde ist verpflichtet, zumutbare Maßnahmen zur Schadensminimierung zu ergreifen (§254 BGB).

---

## §6. Datenschutz und Auftragsverarbeitung

1. Soweit der Kunde im Rahmen der Nutzung des Dienstes die Verarbeitung personenbezogener Daten an den Anbieter überträgt, schließen die Parteien einen separaten **Auftragsverarbeitungsvertrag (AVV)** gemäß Art. 28 DSGVO ab — Muster: Anlage 1 oder separates AVV-Dokument (AVV_DE.md).
2. Der Anbieter verarbeitet Operatordaten (Kontodaten, Sitzungsdaten, Audit-Log) als Verantwortlicher im in der Datenschutzerklärung (PP_v591_DE.md) beschriebenen Umfang.
3. Der Kunde nimmt zur Kenntnis, dass Prompt-Inhalte, die an externe KI-Modelle (OpenAI, Anthropic, Google, Perplexity, xAI, DeepSeek) gesendet werden, den Datenschutzrichtlinien dieser Anbieter unterliegen.

---

## §7. Unterauftragsverarbeitung (Unterauftragnehmer)

1. Der Anbieter informiert den Kunden über die Nutzung folgender externer KI-Modelle als potenzielle Datenempfänger:

| KI-Anbieter | Sitz | Schutzmaßnahme |
|------------|------|----------------|
| OpenAI, Inc. | USA | EU-US DPF + AVV |
| Anthropic, PBC | USA | SCC Modul 2 + AVV |
| Google LLC | USA/EU | EU-US DPF + AVV |
| Perplexity AI, Inc. | USA | SCC Modul 2 + AVV |
| xAI, Inc. | USA | SCC Modul 2 + AVV (in Prüfung) |
| DeepSeek AI Co., Ltd. | China | TIA ausstehend — bedingte Aktivierung |

2. Der Kunde hat das Recht, innerhalb von 14 Tagen nach Mitteilung Widerspruch gegen die Nutzung eines bestimmten Unterauftragsverarbeiters einzulegen. Bei begründetem Widerspruch wird der Anbieter eine alternative Lösung anbieten oder dem Kunden die kostenlose Kündigung des Vertrags ermöglichen.

---

## §8. Geistiges Eigentum

1. Die Software SYLION Pipeline ist Eigentum des Anbieters und wird unter den Bedingungen der MIT-Lizenz bereitgestellt.
2. Der Kunde behält alle Rechte an den in den Dienst eingegebenen Inhalten (Quellcode, Dokumente, Prompts).
3. Berichte, Analysen und vom Dienst generierte Ergebnisse sind Eigentum des Kunden.
4. Der Anbieter erhebt keine Ansprüche auf geistiges Eigentum in Bezug auf Kundendaten.
5. Der Kunde ist nicht berechtigt, Marken des Anbieters ohne dessen vorherige schriftliche Zustimmung zu verwenden.

---

## §9. Vertraulichkeit

1. Die Parteien verpflichten sich, alle vertraulichen Informationen der jeweils anderen Partei, die im Zusammenhang mit der Durchführung dieses Vertrags erlangt wurden, geheim zu halten.
2. Die Vertraulichkeitsverpflichtung gilt für einen Zeitraum von **5 Jahren** ab Offenbarung der Information oder ab dem Tag der Vertragsauflösung, je nachdem, welcher Zeitpunkt später liegt.
3. Detaillierte B2B-Vertraulichkeitsbedingungen regelt ein separater NDA (Muster: NDA_DE.md).

---

## §10. Vertragslaufzeit und Kündigung

1. **Kündigung durch den Kunden:** Der Kunde kann den Vertrag mit einer **Kündigungsfrist von 30 Tagen** zum Monatsende kündigen, sofern im Auftrag nichts anderes vereinbart ist.
2. **Außerordentliche Kündigung durch den Anbieter** — Der Anbieter kann den Vertrag fristlos kündigen bei:
   a) Zahlungsverzug von mehr als 30 Tagen nach erfolgloser Mahnung;  
   b) schwerem Verstoß des Kunden gegen diese AGB;  
   c) Eröffnung eines Insolvenz- oder Restrukturierungsverfahrens über das Vermögen des Kunden.
3. **Folgen der Kündigung:**  
   a) Der Kunde ist verpflichtet, die Nutzung des Dienstes einzustellen und alle Installationen zu entfernen;  
   b) Der Anbieter löscht oder gibt Kundendaten innerhalb von 30 Tagen nach Vertragsauflösung zurück;  
   c) Der Kunde ist verpflichtet, alle ausstehenden Zahlungen zu begleichen.
4. Die Klauseln zur Haftungsbeschränkung (§5), Vertraulichkeit (§9), anwendbarem Recht (§11) und Gerichtsstand (§12) bleiben nach Vertragsauflösung in Kraft.

---

## §11. Anwendbares Recht

Diese AGB unterliegen dem Recht der Bundesrepublik Deutschland, insbesondere:
- dem Bürgerlichen Gesetzbuch (BGB),
- dem Gesetz gegen den unlauteren Wettbewerb (UWG),
- dem Bundesdatenschutzgesetz (BDSG),
- der Verordnung (EU) 2016/679 (DSGVO).

Das UN-Kaufrecht (CISG) findet keine Anwendung.

---

## §12. Gerichtsstand

1. Für alle Streitigkeiten aus und im Zusammenhang mit diesen AGB ist der Gerichtsstand am Sitz des Anbieters vereinbart (§38 Abs. 1 ZPO — ausschließlicher Gerichtsstand für Kaufleute).
2. Die Parteien streben eine gütliche Beilegung von Streitigkeiten vor einer gerichtlichen Auseinandersetzung an. Zu diesem Zweck einigen sich die Parteien auf eine 30-tägige Verhandlungsfrist.

---

## §13. Änderungen der AGB

1. Der Anbieter behält sich das Recht vor, diese AGB mit einer Ankündigungsfrist von 30 Tagen zu ändern.
2. Der Kunde, der den Änderungen nicht zustimmt, kann den Vertrag vor dem Inkrafttreten der Änderungen kostenfrei kündigen.
3. Die weitere Nutzung des Dienstes nach dem Inkrafttreten der Änderungen gilt als Zustimmung.

---

## §14. Schlussbestimmungen

1. Sollte eine Bestimmung dieser AGB unwirksam oder undurchführbar sein, bleiben die übrigen Bestimmungen wirksam.
2. Änderungen und Ergänzungen dieser AGB bedürfen der Schriftform.
3. Diese AGB bilden die gesamte Vereinbarung der Parteien hinsichtlich der Nutzung des Dienstes und ersetzen alle früheren Absprachen.
4. Es gilt §305 ff. BGB, soweit nicht ausdrücklich abbedungen.

---

## Ausfüllanleitung für Platzhalter

| Platzhalter | Beschreibung | Beispiel |
|-------------|--------------|---------|
| `{{COMPANY_NAME_DE}}` | Vollständiger Firmenname des Anbieters | RSDG GmbH |
| `{{ADDRESS_DE}}` | Firmenanschrift des Anbieters | Musterstraße 1, 10115 Berlin |
| `{{HRB_UST_DE}}` | HRB-Nummer und USt-IdNr. des Anbieters | HRB 123456 B, USt-IdNr.: DE123456789 |
| `{{CONTACT_EMAIL_DE}}` | Kontakt-E-Mail-Adresse | kontakt@rsdg.de |

---

*Allgemeine Geschäftsbedingungen v1.0 | SYLION Pipeline v5.9.1 | RSDG GmbH | 2026-04-19*  
*Gilt ausschließlich für B2B-Verhältnisse. Das Dokument erfordert eine rechtliche Überprüfung durch einen Rechtsanwalt vor dem kommerziellen Vertrieb.*
