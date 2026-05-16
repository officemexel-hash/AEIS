# ONCALL Fill Instructions — SYLION v5.9.2

**Cel dokumentu:** Instrukcja krok-po-kroku wypełnienia placeholderów w `INCIDENT_RESPONSE_v592.md`  
**Audyt:** SRE G-10  
**Właściciel:** SRE Lead / Team Manager  
**Częstotliwość aktualizacji:** Przy każdej zmianie dyżurnego; co kwartał przegląd  

---

## 1. Jak Używać Placeholderów

Wszystkie zmienne do wypełnienia mają format `{{NAZWA_ZMIENNEJ}}`.

**Wyszukiwanie wszystkich placeholderów:**
```bash
grep -oE '\{\{[A-Z0-9_]+\}\}' INCIDENT_RESPONSE_v592.md | sort -u
```

**Masowe zastępowanie (przykład dla jednej zmiennej):**
```bash
# Zastąp {{ONCALL_PRIMARY_NAME}} konkretną wartością
sed -i 's/{{ONCALL_PRIMARY_NAME}}/Jan Kowalski/g' INCIDENT_RESPONSE_v592.md
```

**Skrypt zbiorczy (utwórz plik `.env` z wartościami, uruchom skrypt):**
```bash
# Utwórz plik oncall.env z linijkami: ONCALL_PRIMARY_NAME="Jan Kowalski"
# Następnie:
source oncall.env
envsubst < INCIDENT_RESPONSE_v592.md > INCIDENT_RESPONSE_v592_filled.md
echo "Plik wypełniony: INCIDENT_RESPONSE_v592_filled.md"
```

---

## 2. Tabela Wszystkich Placeholderów

### 2.1 SRE Primary On-Call

| Placeholder | Opis | Format | Przykład |
|-------------|------|--------|---------|
| `{{ONCALL_PRIMARY_NAME}}` | Imię i Nazwisko dyżurnego | Imię Nazwisko | Jan Kowalski |
| `{{ONCALL_PRIMARY_PHONE}}` | Numer telefonu (z prefiksem kraju) | +CCXXXXXXXXX | +48501234567 |
| `{{ONCALL_PRIMARY_EMAIL}}` | Adres email służbowy | user@domain.com | jan.kowalski@sylion.io |
| `{{ONCALL_PRIMARY_SIGNAL}}` | Numer Signal lub nick Telegram | +CC... lub @nick | +48501234567 lub @jkowalski |
| `{{ONCALL_PRIMARY_SLACK}}` | Handle Slack bez @ | lowercase.name | jan.kowalski |
| `{{ONCALL_PRIMARY_TZ}}` | Strefa czasowa IANA | Region/City | Europe/Warsaw |
| `{{ONCALL_PRIMARY_HOURS}}` | Godziny pracy + on-call coverage | tekst | 08:00–18:00 CET; P0/P1 24/7 |
| `{{ONCALL_PRIMARY_PD}}` | Login PagerDuty | email lub username | jan.kowalski@sylion.io |

### 2.2 SRE Backup On-Call

| Placeholder | Opis | Format | Przykład |
|-------------|------|--------|---------|
| `{{ONCALL_BACKUP_NAME}}` | Imię i Nazwisko | Imię Nazwisko | Anna Nowak |
| `{{ONCALL_BACKUP_PHONE}}` | Telefon z prefiksem | +CCXXXXXXXXX | +48509876543 |
| `{{ONCALL_BACKUP_EMAIL}}` | Email służbowy | user@domain.com | anna.nowak@sylion.io |
| `{{ONCALL_BACKUP_SIGNAL}}` | Signal/Telegram | +CC... lub @nick | +48509876543 |
| `{{ONCALL_BACKUP_SLACK}}` | Slack handle | lowercase.name | anna.nowak |
| `{{ONCALL_BACKUP_TZ}}` | Strefa czasowa IANA | Region/City | Europe/Warsaw |
| `{{ONCALL_BACKUP_HOURS}}` | Godziny + coverage | tekst | 08:00–18:00 CET; P0/P1 24/7 |
| `{{ONCALL_BACKUP_PD}}` | PagerDuty login | email | anna.nowak@sylion.io |

### 2.3 Incident Commander

| Placeholder | Opis | Format | Przykład |
|-------------|------|--------|---------|
| `{{IC_NAME}}` | Imię i Nazwisko IC | Imię Nazwisko | Piotr Wiśniewski |
| `{{IC_PHONE}}` | Telefon IC | +CCXXXXXXXXX | +48511111222 |
| `{{IC_EMAIL}}` | Email IC | user@domain.com | p.wisniewski@sylion.io |
| `{{IC_SIGNAL}}` | Signal/Telegram IC | +CC... lub @nick | +48511111222 |
| `{{IC_SLACK}}` | Slack handle IC | lowercase | piotr.wisniewski |
| `{{IC_TZ}}` | Strefa czasowa | Region/City | Europe/Warsaw |
| `{{IC_HOURS}}` | Godziny pracy | tekst | 08:00–20:00 CET; P0 24/7 |
| `{{IC_BACKUP_NAME}}` | Zastępca IC — imię | Imię Nazwisko | Maria Zielińska |
| `{{IC_BACKUP_PHONE}}` | Zastępca IC — telefon | +CCXXXXXXXXX | +48522333444 |

### 2.4 Pozostałe Role Techniczne

| Placeholder | Opis | Format |
|-------------|------|--------|
| `{{LEAD_DEV_NAME}}` | Lead Developer — imię i nazwisko | Imię Nazwisko |
| `{{LEAD_DEV_PHONE}}` | Lead Developer — telefon | +CCXXXXXXXXX |
| `{{LEAD_DEV_EMAIL}}` | Lead Developer — email | user@domain.com |
| `{{LEAD_DEV_SIGNAL}}` | Lead Developer — Signal/Telegram | +CC... lub @nick |
| `{{LEAD_DEV_TZ}}` | Lead Developer — timezone | Region/City |
| `{{LEAD_DEV_HOURS}}` | Lead Developer — godziny | np. 09:00–18:00 CET |
| `{{DEVOPS_LEAD_NAME}}` | DevOps Lead — imię | Imię Nazwisko |
| `{{DEVOPS_LEAD_PHONE}}` | DevOps Lead — telefon | +CCXXXXXXXXX |
| `{{DEVOPS_LEAD_EMAIL}}` | DevOps Lead — email | user@domain.com |
| `{{DEVOPS_LEAD_SIGNAL}}` | DevOps Lead — Signal/Telegram | +CC... |
| `{{DEVOPS_LEAD_TZ}}` | DevOps Lead — timezone | Region/City |
| `{{DEVOPS_LEAD_HOURS}}` | DevOps Lead — godziny | tekst |
| `{{MOBILE_LEAD_NAME}}` | Mobile Team Lead — imię | Imię Nazwisko |
| `{{MOBILE_LEAD_PHONE}}` | Mobile Team Lead — telefon | +CCXXXXXXXXX |
| `{{MOBILE_LEAD_EMAIL}}` | Mobile Team Lead — email | user@domain.com |
| `{{MOBILE_LEAD_SIGNAL}}` | Mobile Lead — Signal/Telegram | +CC... lub @nick |
| `{{MOBILE_LEAD_SLACK}}` | Mobile Lead — Slack handle | lowercase |
| `{{MOBILE_LEAD_TZ}}` | Mobile Lead — timezone | Region/City |
| `{{MOBILE_LEAD_HOURS}}` | Mobile Lead — godziny | tekst |
| `{{NETWORK_LEAD_NAME}}` | Network Team Lead — imię | Imię Nazwisko |
| `{{NETWORK_LEAD_PHONE}}` | Network Lead — telefon | +CCXXXXXXXXX |
| `{{NETWORK_LEAD_EMAIL}}` | Network Lead — email | user@domain.com |
| `{{NETWORK_LEAD_SIGNAL}}` | Network Lead — Signal/Telegram | +CC... lub @nick |
| `{{NETWORK_LEAD_SLACK}}` | Network Lead — Slack handle | lowercase |
| `{{NETWORK_LEAD_TZ}}` | Network Lead — timezone | Region/City |
| `{{NETWORK_LEAD_HOURS}}` | Network Lead — godziny | tekst |
| `{{DBA_NAME}}` | DBA — imię i nazwisko | Imię Nazwisko |
| `{{DBA_PHONE}}` | DBA — telefon | +CCXXXXXXXXX |
| `{{DBA_EMAIL}}` | DBA — email | user@domain.com |
| `{{DBA_SIGNAL}}` | DBA — Signal/Telegram | +CC... lub @nick |
| `{{DBA_TZ}}` | DBA — timezone | Region/City |
| `{{DBA_HOURS}}` | DBA — godziny | tekst |
| `{{CTO_NAME}}` | CTO — imię i nazwisko | Imię Nazwisko |
| `{{CTO_PHONE}}` | CTO — telefon | +CCXXXXXXXXX |
| `{{CTO_EMAIL}}` | CTO — email | user@domain.com |
| `{{CTO_SIGNAL}}` | CTO — Signal/Telegram | +CC... lub @nick |
| `{{CTO_TZ}}` | CTO — timezone | Region/City |
| `{{CTO_HOURS}}` | CTO — godziny aktywacji | P0 only: 24/7 |
| `{{SEC_NAME}}` | Security Lead / Pentester — imię | Imię Nazwisko |
| `{{SEC_PHONE}}` | Security Lead — telefon | +CCXXXXXXXXX |
| `{{SEC_EMAIL}}` | Security Lead — email (szyfrowany) | user@domain.com |
| `{{SEC_SIGNAL}}` | Security Lead — Signal (preferowany) | +CC... |
| `{{SEC_TZ}}` | Security Lead — timezone | Region/City |
| `{{SEC_HOURS}}` | Security Lead — godziny | tekst |
| `{{SEC_PGP_FINGERPRINT}}` | PGP fingerprint Security Lead | 40-znakowy hex | ABCD EF12 3456 ... |

### 2.5 DPO i Prawne (Poufne)

| Placeholder | Opis | Format |
|-------------|------|--------|
| `{{DPO_PL_NAME}}` | DPO Polska — imię i nazwisko | Imię Nazwisko |
| `{{DPO_PL_ORG}}` | DPO Polska — organizacja | nazwa firmy/zewnętrzny |
| `{{DPO_PL_PHONE}}` | DPO PL — telefon | +48XXXXXXXXX |
| `{{DPO_PL_EMAIL}}` | DPO PL — email | dpo@domain.com |
| `{{DPO_PL_SIGNAL}}` | DPO PL — Signal/Telegram | +48... |
| `{{DPO_PL_ADDRESS}}` | DPO PL — adres pocztowy | ul. ..., kod, miasto |
| `{{DPO_PL_HOURS}}` | DPO PL — godziny | np. 09:00–17:00 CET |
| `{{DPO_DE_NAME}}` | DPO Niemcy — imię | Imię Nachname |
| `{{DPO_DE_ORG}}` | DPO DE — organizacja | nazwa |
| `{{DPO_DE_PHONE}}` | DPO DE — telefon | +49XXXXXXXXXX |
| `{{DPO_DE_EMAIL}}` | DPO DE — email | datenschutz@domain.de |
| `{{DPO_DE_SIGNAL}}` | DPO DE — Signal/Telegram | +49... |
| `{{DPO_DE_ADDRESS}}` | DPO DE — adres | Straße ..., PLZ, Stadt |
| `{{DPO_DE_HOURS}}` | DPO DE — godziny | np. 09:00–17:00 CET |
| `{{LEGAL_NAME}}` | Legal Counsel — imię | Imię Nazwisko |
| `{{LEGAL_PHONE}}` | Legal — telefon | +CCXXXXXXXXX |
| `{{LEGAL_EMAIL}}` | Legal — email | legal@domain.com |
| `{{LEGAL_SIGNAL}}` | Legal — Signal/Telegram | +CC... |
| `{{LEGAL_TZ}}` | Legal — timezone | Region/City |
| `{{LEGAL_HOURS}}` | Legal — godziny | tekst |

### 2.6 Infrastruktura i Systemy

| Placeholder | Opis | Format | Przykład |
|-------------|------|--------|---------|
| `{{PROD_DOMAIN}}` | Domena produkcyjna | FQDN | api.sylion.io |
| `{{MUDI_ROUTER_IP}}` | IP routera Mudi (sieć lokalna) | IPv4 | 192.168.1.1 |
| `{{BACKUP_GATEWAY}}` | IP bramy backup ISP | IPv4 | 10.0.1.1 |
| `{{BACKUP_ISP_INTERFACE}}` | Interfejs backup ISP | nazwa | eth1, wwan0 |
| `{{BACKUP_JUMP_HOST}}` | Host jump dla backup połączenia | user@host | admin@jump.sylion.io |
| `{{OLLAMA_FALLBACK_MODEL}}` | Model Ollama do fallbacku LLM | model:tag | llama3.2:3b |
| `{{ALLOWED_IP_WHITELIST_PATH}}` | Ścieżka do whitelist IP | absolutna | /etc/sylion/ip_whitelist.txt |
| `{{PAGERDUTY_SCHEDULE_URL}}` | URL harmonogramu PagerDuty | URL | https://sylion.pagerduty.com/schedules/XXXXX |
| `{{WAR_ROOM_LINK}}` | Link do war room Zoom/Meet | URL | https://meet.google.com/... |
| `{{STATUS_PAGE_URL}}` | URL strony statusu | URL | https://status.sylion.io |
| `{{SLACK_WORKSPACE_URL}}` | URL workspace Slack | URL | https://sylion.slack.com |
| `{{MONITORING_DASHBOARD_URL}}` | URL dashboardu monitoringu | URL | https://grafana.sylion.io/d/... |

---

## 3. Procedura Aktualizacji Dyżurów

### 3.1 Rotacja tygodniowa (co poniedziałek 09:00 CET)

1. Otwórz `INCIDENT_RESPONSE_v592.md`
2. Zaktualizuj sekcje 1.1 (Primary) i 1.2 (Backup) — zmień wartości `{{...}}`
3. Zaktualizuj PagerDuty schedule: `{{PAGERDUTY_SCHEDULE_URL}}`
4. Wyślij wiadomość na `#incidents-critical`:
   ```
   ON-CALL UPDATE: Tydzień YYYY-WXX
   Primary: [IMIĘ] | [TELEFON]
   Backup: [IMIĘ] | [TELEFON]
   ```
5. Commit do repozytorium z tagiem `oncall/YYYY-WXX`

### 3.2 Nagła zmiana dyżurnego

1. Nowy dyżurny **musi** potwierdzić odbiór przez Signal lub Slack
2. IC aktualizuje sekcję 1.5 (Escalation Tree) w dokumencie
3. PagerDuty override ustawiony przez: `{{DEVOPS_LEAD_NAME}}`
4. Powiadomienie do `#alerts-sre`

---

## 4. Checklist Wypełnienia (przed publikacją)

```
[ ] 1.1 Primary On-Call — wszystkie 8 pól wypełnione
[ ] 1.2 Backup On-Call — wszystkie 8 pól wypełnione
[ ] 1.3 Incident Commander — wszystkie 9 pól wypełnione
[ ] 1.4 Escalation Matrix — wszystkie role wypełnione (12 wierszy)
[ ] INC-001: {{PROD_DOMAIN}} wypełniony
[ ] INC-002: DPO PL/DE skontaktowani i dane potwierdzone
[ ] INC-003: {{SEC_PGP_FINGERPRINT}} zweryfikowany
[ ] INC-004: {{OLLAMA_FALLBACK_MODEL}} przetestowany
[ ] INC-005: {{MOBILE_LEAD_NAME}} i {{MOBILE_LEAD_PHONE}} potwierdzone
[ ] INC-006: {{MUDI_ROUTER_IP}} i {{BACKUP_GATEWAY}} przetestowane
[ ] INC-007: backup directory istnieje i zawiera backupy M-08
[ ] INC-008: cron WAL monitor dodany
[ ] Sekcja 5: kontakty CERT Polska i BSI zweryfikowane
[ ] Sekcja 6: {{PAGERDUTY_SCHEDULE_URL}} i {{WAR_ROOM_LINK}} działają
[ ] Grep: zero pozostałych {{...}} w finalnym pliku
```

**Weryfikacja końcowa:**
```bash
# Sprawdź czy wszystkie placeholdery zostały wypełnione
remaining=$(grep -cE '\{\{[A-Z_]+\}\}' INCIDENT_RESPONSE_v592.md 2>/dev/null || echo 0)
echo "Pozostałe placeholdery: $remaining"
[ "$remaining" -eq 0 ] && echo "GOTOWE — żadnych placeholderów" || echo "UWAGA — uzupełnij brakujące!"
```

---

## 5. Bezpieczeństwo Danych Kontaktowych

> Dokument zawiera dane osobowe (telefony, emaile) — traktuj jako **POUFNE — Internal**

- Nie przesyłaj mailem niezaszyfrowanym
- Przechowuj w repozytorium z ograniczonym dostępem (RBAC — tylko SRE team)
- Nie wklejaj do Confluence/Notion bez ACL
- Dane DPO i Legal — tylko w zaszyfrowanym magazynie (Vault, 1Password Teams)
- Regularny przegląd dostępów: co kwartał

---

*ONCALL Fill Instructions v5.9.2 — SRE G-10 Audit*
