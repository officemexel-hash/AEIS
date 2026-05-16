# Cookie-Richtlinie — SYLION Pipeline

**Version:** 1.0  
**Datum:** 2026-04-19  
**Produkt:** SYLION Pipeline v5.9.1  
**Verantwortlicher:** {{COMPANY_NAME_DE}}, {{ADDRESS_DE}}  
**Kontakt:** {{CONTACT_EMAIL_DE}}

> **PLATZHALTER — VOR VERTEILUNG AUSFÜLLEN:** Ersetzen Sie alle `{{…}}`-Markierungen.

---

## 1. Was sind Cookies?

Cookies (Kekse) sind kleine Textdateien, die von besuchten Webseiten und Anwendungen im Webbrowser gespeichert werden. Sie dienen der Speicherung von Sitzungsinformationen, Benutzerpräferenzen oder Sicherheitszwecken.

---

## 2. Welche Cookies verwendet SYLION Pipeline?

SYLION Pipeline verwendet **ausschließlich technisch notwendige Cookies** (*strictly necessary cookies*), die für den ordnungsgemäßen Betrieb der Anwendung unerlässlich sind. Das System verwendet **keine**:
- Analyse-Cookies (Google Analytics usw.),
- Werbe- oder Remarketing-Cookies,
- Cookies zur seitenübergreifenden Aktivitätsverfolgung (Cross-Site-Tracking),
- Drittanbieter-Cookies.

### 2.1 Vollständige Cookie-Liste SYLION Pipeline

| Cookie-Name | Typ | Zweck / Verwendung | Lebensdauer | Sicherheitsattribute | Rechtsgrundlage |
|------------|-----|-------------------|-------------|----------------------|-----------------|
| `sylion_session` | Notwendig — Sitzung | Identifizierung der angemeldeten Benutzersitzung; RBAC-Rechteverwaltung (owner/admin/member); Aufrechterhaltung des Authentifizierungszustands | **24 Stunden** ab Anmeldung | `HttpOnly` — für JavaScript nicht zugänglich; `Secure` — nur HTTPS; `SameSite=Strict` — CSRF-Schutz | Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung / Erbringung des Dienstes) — **keine Einwilligung erforderlich** |
| `_csrf_token` | Notwendig — Sicherheit | Schutz vor Cross-Site Request Forgery (CSRF)-Angriffen; Validierung der Authentizität von HTTP-Anfragen | **30 Minuten** ab Generierung (wird bei Aktivität erneuert) | `Secure` — nur HTTPS; `SameSite=Strict` | Art. 6 Abs. 1 lit. b DSGVO (Notwendigkeit zur Gewährleistung der Dienstsicherheit) — **keine Einwilligung erforderlich** |

### 2.2 Serverseitig gespeicherte Sitzungsdaten

Zusätzlich zum Cookie speichert SYLION serverseitig (in der SQLite-Datenbank) folgende Sitzungsdaten:

| Daten | Zweck | Aufbewahrung |
|-------|-------|--------------|
| Sitzungs-ID | Verknüpfung des Cookies mit dem Sitzungsdatensatz in der Datenbank | 30 Tage nach Ablauf |
| IP-Adresse | Sicherheit (Anomalieerkennung) | 30 Tage nach Ablauf |
| Anmelde-Zeitstempel | Audit-Log | 365 Tage |
| RBAC-Rolle | Zugriffskontrolle | Dauer der Sitzung |

---

## 3. Warum ist keine Einwilligung für diese Cookies erforderlich?

Die Cookies `sylion_session` und `_csrf_token` werden als **technisch notwendige Cookies** (*strictly necessary*) eingestuft, für die:
- **keine Einwilligung des Nutzers erforderlich ist** (Art. 6 Abs. 1 lit. b DSGVO; Erwägungsgrund 47 DSGVO; §25 Abs. 2 Nr. 2 TTDSG),
- ein Opt-out ohne Verlust des Zugangs zum Dienst nicht möglich ist,
- ausschließlich technische Funktionen erfüllt werden, die für den Betrieb der Anwendung unerlässlich sind.

Diese Position steht im Einklang mit den EDSA-Leitlinien 05/2020 zur Einwilligung (Rn. 40) sowie der Auslegung der deutschen Datenschutzbehörden und dem Telekommunikation-Telemedien-Datenschutz-Gesetz (TTDSG).

---

## 4. Wie lange gelten die Cookies?

| Cookie | Lebensdauer im Browser | Aufbewahrungsdauer der Sitzungsdaten auf dem Server |
|--------|------------------------|------------------------------------------------------|
| `sylion_session` | 24 Stunden (läuft nach Sitzungsende oder 24h nach Anmeldung ab) | 30 Tage nach Ablauf des Cookies |
| `_csrf_token` | 30 Minuten (wird bei Aktivität erneuert) | Wird nicht auf dem Server gespeichert |

---

## 5. Wie können Cookies verwaltet und widerrufen werden?

Da SYLION Pipeline ausschließlich **notwendige Sitzungs-Cookies** verwendet, ist die einzige Möglichkeit, diese zu löschen (und damit die Sitzung zu beenden):

### 5.1 Abmeldung über die SYLION-Oberfläche
- Klicken Sie auf die Schaltfläche „Abmelden" in der Anwendungsoberfläche,
- Das System löscht die Cookies `sylion_session` und `_csrf_token` und invalidiert die serverseitige Sitzung.

### 5.2 Manuelle Cookie-Löschung im Browser

**Google Chrome:**  
Einstellungen → Datenschutz und Sicherheit → Cookies und andere Websitedaten → `localhost` oder SYLION-Domain suchen → Löschen

**Mozilla Firefox:**  
Einstellungen → Datenschutz & Sicherheit → Cookies und Website-Daten → Daten verwalten → Löschen

**Microsoft Edge:**  
Einstellungen → Cookies und Website-Berechtigungen → Cookies und Websitedaten verwalten und löschen

**Safari:**  
Einstellungen → Datenschutz → Website-Daten verwalten → Entfernen

### 5.3 Cookie-Blockierung durch den Browser

Sie können Ihren Browser so konfigurieren, dass alle Cookies blockiert werden. Bitte beachten Sie: **Das Blockieren von Sitzungs-Cookies (`sylion_session`) macht eine Anmeldung bei SYLION Pipeline unmöglich**.

---

## 6. Cookies und die lokale SYLION-Anwendung

SYLION Pipeline ist eine Anwendung, die **lokal auf dem Gerät des Operators** läuft (localhost oder privates Netzwerk). Im Unterschied zu typischen Internetdiensten:
- werden Cookies ausschließlich von der Domain/dem Host gesetzt, auf dem SYLION läuft,
- gibt es keine externen oder Drittanbieter-Tracking-Cookies,
- werden keine Daten an externe Analyse-Server übermittelt,
- empfehlen wir in der Produktionsumgebung das Attribut `Secure` (HTTPS) und die Konfiguration `SameSite=Strict`.

---

## 7. Änderungen der Cookie-Richtlinie

Bei der Einführung neuer Cookie-Typen wird diese Richtlinie aktualisiert und den Nutzern mit einem Vorlauf von mindestens 14 Tagen mitgeteilt. Die weitere Nutzung des Dienstes nach dem Inkrafttreten der Änderungen gilt als Zustimmung.

---

## 8. Kontakt und Aufsichtsbehörde

**Kontakt:** {{CONTACT_EMAIL_DE}}

Bei Fragen oder Bedenken zur Verarbeitung von Daten in Cookies haben Sie das Recht, eine Beschwerde bei der zuständigen Aufsichtsbehörde einzureichen:

**Deutschland — BfDI:**  
Der Bundesbeauftragte für den Datenschutz und die Informationsfreiheit  
Husarenstraße 30, 53117 Bonn  
https://www.bfdi.bund.de

**Zuständige Landesbehörde:** Die Behörde des Bundeslandes, in dem der Verantwortliche seinen Sitz hat.

---

## Ausfüllanleitung für Platzhalter

| Platzhalter | Beschreibung |
|-------------|--------------|
| `{{COMPANY_NAME_DE}}` | Vollständiger Firmenname oder Name des Verantwortlichen |
| `{{ADDRESS_DE}}` | Firmenanschrift |
| `{{CONTACT_EMAIL_DE}}` | E-Mail-Adresse für DSGVO-/Cookie-Kontakt |

---

*Cookie-Richtlinie v1.0 | SYLION Pipeline v5.9.1 | 2026-04-19*  
*Cookies: ausschließlich technisch notwendige (Art. 6 Abs. 1 lit. b DSGVO; §25 Abs. 2 Nr. 2 TTDSG). Keine Analyse-, Werbe- oder Tracking-Cookies.*
