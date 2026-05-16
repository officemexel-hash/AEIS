# RACI Matrix — SYLION v5.9.2 Incident Response

**Wersja:** 5.9.2  
**Audyt:** SRE G-10  
**Klucz:** R=Responsible (wykonuje), A=Accountable (odpowiada), C=Consulted (konsultowany), I=Informed (informowany)

---

## Legenda Ról

| Skrót | Rola | Placeholder |
|-------|------|-------------|
| **PRI** | SRE Primary On-Call | `{{ONCALL_PRIMARY_NAME}}` |
| **BCK** | SRE Backup On-Call | `{{ONCALL_BACKUP_NAME}}` |
| **IC** | Incident Commander | `{{IC_NAME}}` |
| **LDEV** | Lead Developer | `{{LEAD_DEV_NAME}}` |
| **DOPS** | DevOps Lead | `{{DEVOPS_LEAD_NAME}}` |
| **MOB** | Mobile Team Lead | `{{MOBILE_LEAD_NAME}}` |
| **NET** | Network Team Lead | `{{NETWORK_LEAD_NAME}}` |
| **DBA** | Database Administrator | `{{DBA_NAME}}` |
| **CTO** | Chief Technology Officer | `{{CTO_NAME}}` |
| **SEC** | Security Lead / Pentester | `{{SEC_NAME}}` |
| **DPO** | Data Protection Officer (PL/DE) | `{{DPO_PL_NAME}}` / `{{DPO_DE_NAME}}` |
| **LEG** | Legal Counsel | `{{LEGAL_NAME}}` |

---

## INC-001: Production Down (HTTP 5xx >50%)

| Aktywność | PRI | BCK | IC | LDEV | DOPS | CTO | DBA |
|-----------|-----|-----|----|------|------|-----|-----|
| Odbiór alertu PagerDuty | **R** | C | I | I | I | — | — |
| ACK incydentu (SLA: 5 min) | **A** | R | I | — | — | — | — |
| Uruchomienie quick-triage | **R** | C | I | — | — | — | — |
| Ogłoszenie P0 w Slack | R | — | **A** | I | I | I | — |
| Izolacja przyczyny (502/503/OOM) | **R** | C | I | C | C | — | — |
| Decyzja o restarcie | R | — | **A** | C | C | — | — |
| Wykonanie restartu | **R** | — | — | — | C | — | — |
| Rollback deploymentu | R | — | **A** | R | R | I | — |
| Weryfikacja health-check | **R** | — | I | — | — | — | — |
| Komunikat o przywróceniu | R | — | **A** | I | I | I | — |
| Eskalacja do CTO (P0 >30 min) | — | — | **A** | — | — | R | — |
| Post-mortem (P0/P1 obowiązkowo) | R | — | **A** | R | R | I | — |

---

## INC-002: Data Breach Suspected (Naruszenie Danych)

| Aktywność | PRI | BCK | IC | SEC | DPO | LEG | CTO | DOPS |
|-----------|-----|-----|----|-----|-----|-----|-----|------|
| Wykrycie i odbiór alertu | **R** | C | I | — | — | — | — | — |
| ACK (SLA: 5 min) | **A** | R | I | — | — | — | — | — |
| Izolacja systemu (stop traffic) | **R** | — | **A** | C | — | — | — | C |
| Zabezpieczenie logów (dowody) | **R** | — | A | C | I | — | — | — |
| Ocena zakresu naruszenia | R | — | A | **R** | C | — | — | — |
| Eskalacja do IC (natychmiast) | **R** | — | A | — | — | — | — | — |
| Powiadomienie DPO (≤1h) | — | — | **A** | — | R | — | — | — |
| Powiadomienie Legal (≤1h) | — | — | **A** | — | C | R | — | — |
| Powiadomienie CTO | — | — | **A** | — | — | — | R | — |
| Zgłoszenie UODO/BfDI (≤72h) | — | — | C | — | **A** | R | I | — |
| Zgłoszenie CERT Polska | — | — | C | **R** | C | — | I | — |
| Zgłoszenie BSI (użytkownicy DE) | — | — | C | R | **A** | R | I | — |
| Powiadomienie użytkowników (art. 34) | — | — | C | — | **A** | R | A | — |
| Patch / fix bezpieczeństwa | — | — | I | R | — | — | — | **A** |
| Post-mortem | R | — | **A** | R | I | I | I | R |

**Uwaga RODO Art. 33:** DPO jest **Accountable** za złożenie zgłoszenia do organu nadzoru w 72h.

---

## INC-003: Security Vulnerability (Podatność)

| Aktywność | PRI | BCK | IC | SEC | LDEV | DOPS | CTO | LEG |
|-----------|-----|-----|----|-----|------|------|-----|-----|
| Odbiór zgłoszenia (wewnętrzne/zewnętrzne) | **R** | C | I | — | — | — | — | — |
| Ocena CVSS Score | R | — | — | **R** | C | — | — | — |
| Decyzja o klasyfikacji P0/P1 | — | — | **A** | R | C | C | — | — |
| Ogłoszenie embargo (NIE publikuj) | — | — | **A** | R | R | R | I | — |
| Blokada podatnego endpointu (WAF/firewall) | R | — | I | C | — | **R** | — | — |
| Opracowanie patcha | — | — | I | C | **R** | — | — | — |
| Code review patcha | — | — | I | R | **A** | — | — | — |
| Deploy patch staging | — | — | I | C | R | **R** | — | — |
| Deploy patch produkcja | — | — | **A** | C | R | R | I | — |
| Ustalenie disclosure timeline | — | — | C | **R** | — | — | A | C |
| Powiadomienie researcher'a (D+7) | — | — | C | **A** | — | — | — | C |
| Publiczne disclosure (D+14) | — | — | C | R | — | — | **A** | R |
| CVE publikacja | — | — | I | **R** | — | — | I | C |
| Post-mortem | R | — | **A** | R | R | R | I | — |

---

## INC-004: LLM Provider Outage (Anthropic/OpenAI Down)

| Aktywność | PRI | BCK | IC | LDEV | DOPS | CTO |
|-----------|-----|-----|----|------|------|-----|
| Wykrycie alertu API errors | **R** | C | I | — | — | — |
| Potwierdzenie awarii provider'a | **R** | — | I | C | — | — |
| Sprawdzenie status page provider'a | **R** | — | I | — | — | — |
| Decyzja o przełączeniu na Ollama | — | — | **A** | R | C | I |
| Uruchomienie switch-to-ollama.sh | **R** | — | I | C | — | — |
| Weryfikacja fallback działa | **R** | — | I | C | — | — |
| Komunikat w Slack | R | — | **A** | I | I | I |
| Monitorowanie powrotu primary | **R** | — | I | — | — | — |
| Przełączenie z powrotem na primary | R | — | **A** | R | — | I |
| Post-mortem (jeśli P1) | R | — | **A** | R | — | I |

---

## INC-005: Pixel 9 Detection Mass Failure

| Aktywność | PRI | BCK | IC | MOB | LDEV | DOPS |
|-----------|-----|-----|----|-----|------|------|
| Wykrycie alertu failure rate | **R** | C | I | I | — | — |
| Triage DB — sprawdzenie failure stats | **R** | — | I | C | — | — |
| Eskalacja do Mobile Lead | **R** | — | **A** | R | — | — |
| Tymczasowe skip Pixel 9 jobs | R | — | A | **R** | C | — |
| Analiza przyczyny (model/firmware) | — | — | I | **R** | R | — |
| Fix i deploy | — | — | I | R | **R** | R |
| Weryfikacja po fix | **R** | — | I | R | — | — |
| Przywrócenie Pixel 9 do kolejki | R | — | **A** | R | — | — |
| Post-mortem | R | — | **A** | R | R | — |

---

## INC-006: Mudi Router Offline

| Aktywność | PRI | BCK | IC | NET | DOPS | CTO |
|-----------|-----|-----|----|-----|------|-----|
| Wykrycie alertu sieciowego | **R** | C | I | — | I | — |
| Potwierdzenie awarii (ping/traceroute) | **R** | — | I | C | — | — |
| Eskalacja do Network Lead | **R** | — | **A** | R | — | — |
| Ocena zasięgu (P1 vs P2) | — | — | **A** | R | C | I |
| Aktywacja backup ISP/route | R | — | I | **R** | R | — |
| Diagnoza i naprawa routera | — | — | I | **A** | — | — |
| Weryfikacja łączności | **R** | — | I | R | — | — |
| Komunikat statusu | R | — | **A** | I | I | I |
| Post-mortem (jeśli P1) | R | — | **A** | R | R | I |

---

## INC-007: DB Corruption (Uszkodzenie Bazy)

| Aktywność | PRI | BCK | IC | DBA | LDEV | DOPS | CTO |
|-----------|-----|-----|----|-----|------|------|-----|
| Wykrycie błędu integrity | **R** | C | I | — | — | — | — |
| Natychmiastowe zatrzymanie aplikacji | **R** | — | **A** | C | — | — | — |
| Uruchomienie integrity_check | **R** | — | I | **R** | — | — | — |
| Eskalacja do IC i DBA | **R** | — | R | **A** | — | — | — |
| Powiadomienie CTO | — | — | **A** | — | — | — | R |
| Selekcja backupu M-08 | — | — | I | **R** | C | — | — |
| Weryfikacja backupu (integrity) | — | — | I | **R** | — | — | — |
| Wykonanie restore_db_m08.sh | R | — | I | **A** | — | — | — |
| Weryfikacja odtworzonej DB | **R** | — | I | R | R | — | — |
| Restart aplikacji po restore | **R** | — | A | C | — | — | — |
| Health check i weryfikacja end-to-end | **R** | — | A | C | R | — | — |
| Analiza zakresu utraty danych | — | — | A | **R** | R | — | I |
| Komunikat biznesowy o stracie danych | — | — | **A** | I | I | — | R |
| Post-mortem (P0 obowiązkowo) | R | — | **A** | R | R | R | I |

---

## INC-008: WAL >1 GB (Write-Ahead Log Overflow)

| Aktywność | PRI | BCK | IC | DBA | DOPS | LDEV |
|-----------|-----|-----|----|-----|------|------|
| Wykrycie alertu WAL size | **R** | C | I | I | — | — |
| Potwierdzenie rozmiaru WAL | **R** | — | I | C | — | — |
| Sprawdzenie blokujących transakcji | **R** | — | I | **R** | — | — |
| Eskalacja do DBA | **R** | — | **A** | R | — | — |
| Backup przed operacją | **R** | — | I | **A** | — | — |
| Wykonanie wal_checkpoint(TRUNCATE) | R | — | I | **A** | — | — |
| Weryfikacja rozmiaru po checkpoint | **R** | — | I | R | — | — |
| Konfiguracja wal_autocheckpoint | — | — | I | **R** | — | R |
| Dodanie cron monitoringu WAL | — | — | I | C | **R** | — |
| Post-mortem (jeśli P1) | R | — | **A** | R | R | R |

---

## RACI — Procedury Crosscutting

### Post-mortem Process

| Aktywność | IC | PRI | LDEV | DOPS | DBA | SEC | CTO |
|-----------|----|----|------|------|-----|-----|-----|
| Uruchomienie post-mortem (≤5 dni) | **A** | R | I | I | I | I | I |
| Uzupełnienie sekcji Timeline | **A** | R | C | C | C | C | — |
| RCA i 5 Whys | R | R | **A** | C | C | C | — |
| Action items — przypisanie | **A** | — | R | R | R | R | I |
| Review i zatwierdzenie | R | — | C | C | — | — | **A** |
| Publikacja w wiki/Notion | **A** | R | — | — | — | — | I |
| Follow-up action items | **A** | — | R | R | R | R | I |

### On-call Handoff

| Aktywność | PRI (outgoing) | BCK (incoming) | IC |
|-----------|---------------|----------------|-----|
| Przygotowanie raportu handoff | **A** | I | I |
| Briefing nowego dyżurnego | **R** | C | — |
| Przekazanie aktywnych incydentów | **A** | R | I |
| Aktualizacja PagerDuty schedule | R | — | **A** |

---

*RACI Matrix v5.9.2 — SRE G-10 Audit*  
*Aktualizuj po każdej zmianie struktury zespołu lub po P0/P1 post-mortem*
