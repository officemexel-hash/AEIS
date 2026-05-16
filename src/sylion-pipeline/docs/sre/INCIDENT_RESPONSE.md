# SYLION v5.9.2 — Incident Response Runbook

**Wersja:** 5.9.2  
**Data wydania:** 2025-01-01T00:00:00Z  
**Właściciel:** SRE Team  
**Klasyfikacja:** Internal — Operations  
**Przegląd:** Co kwartał lub po każdym P0/P1  
**Audyt:** SRE G-10 — on-call contacts compliance  

---

> **Zasady Ogólne:**
> - Zawsze dokumentuj każdą akcję z timestampem ISO 8601
> - Przed każdą operacją zapisu/zmiany wykonaj backup DB
> - Post-mortem jest blameless — skupia się na systemach, nie ludziach
> - Przy P0/P1 — najpierw stabilizuj system, potem wyjaśniaj przyczyny
> - Triage = read-only diagnostyka. Nie restartuj bez diagnozy
> - RODO/GDPR: przy incydentach INC-002 okno na zgłoszenie naruszenia to **72h** od wykrycia

---

**Spis Treści:**
1. [On-call Contacts & Escalation Tree](#1-on-call-contacts--escalation-tree)
2. [Incident Taxonomy & Severity](#2-incident-taxonomy--severity)
3. [Runbooks per Incident Type (INC-001–INC-008)](#3-runbooks-per-incident-type)
4. [Mitigation & Recovery Procedures](#4-mitigation--recovery-procedures)
5. [Legal & Regulatory Contacts](#5-legal--regulatory-contacts)
6. [Communication Channels](#6-communication-channels)
7. [On-call Handoff Procedure](#7-on-call-handoff-procedure)

---

## 1. On-call Contacts & Escalation Tree

> **INSTRUKCJA WYPEŁNIENIA:** Zastąp każdy placeholder `{{PLACEHOLDER}}` danymi rzeczywistymi.
> Szczegółowa instrukcja: `ONCALL_FILL_INSTRUCTIONS.md`

### 1.1 Primary On-Call (SRE)

| Pole | Wartość |
|------|---------|
| **Imię i Nazwisko** | `{{ONCALL_PRIMARY_NAME}}` |
| **Rola** | SRE Engineer / Incident Commander |
| **Telefon** | `{{ONCALL_PRIMARY_PHONE}}` *(format: +48XXXXXXXXX)* |
| **Email** | `{{ONCALL_PRIMARY_EMAIL}}` |
| **Signal / Telegram** | `{{ONCALL_PRIMARY_SIGNAL}}` |
| **Slack handle** | `@{{ONCALL_PRIMARY_SLACK}}` |
| **Timezone** | `{{ONCALL_PRIMARY_TZ}}` *(np. Europe/Warsaw)* |
| **Working hours** | `{{ONCALL_PRIMARY_HOURS}}` *(np. 08:00–18:00 CET, P0/P1 24/7)* |
| **PagerDuty user** | `{{ONCALL_PRIMARY_PD}}` |
| **Zastępca przy braku odpowiedzi** | Backup On-Call — patrz sekcja 1.2 |
| **SLA odbioru** | P0: 5 min, P1: 15 min |

---

### 1.2 Backup On-Call (SRE)

| Pole | Wartość |
|------|---------|
| **Imię i Nazwisko** | `{{ONCALL_BACKUP_NAME}}` |
| **Rola** | SRE Engineer (backup dyżur) |
| **Telefon** | `{{ONCALL_BACKUP_PHONE}}` |
| **Email** | `{{ONCALL_BACKUP_EMAIL}}` |
| **Signal / Telegram** | `{{ONCALL_BACKUP_SIGNAL}}` |
| **Slack handle** | `@{{ONCALL_BACKUP_SLACK}}` |
| **Timezone** | `{{ONCALL_BACKUP_TZ}}` |
| **Working hours** | `{{ONCALL_BACKUP_HOURS}}` |
| **PagerDuty user** | `{{ONCALL_BACKUP_PD}}` |
| **Aktywacja** | Gdy Primary nie potwierdził w ciągu SLA ack lub zrezygnował |

---

### 1.3 Incident Commander

| Pole | Wartość |
|------|---------|
| **Imię i Nazwisko** | `{{IC_NAME}}` |
| **Rola** | Incident Commander (IC) — koordynuje P0/P1 |
| **Telefon** | `{{IC_PHONE}}` |
| **Email** | `{{IC_EMAIL}}` |
| **Signal / Telegram** | `{{IC_SIGNAL}}` |
| **Slack handle** | `@{{IC_SLACK}}` |
| **Timezone** | `{{IC_TZ}}` |
| **Working hours** | `{{IC_HOURS}}` |
| **Backup IC** | `{{IC_BACKUP_NAME}}` / `{{IC_BACKUP_PHONE}}` |

---

### 1.4 Escalation Matrix

| Poziom | Rola | Imię | Telefon | Email | Signal/Telegram | Timezone | Working Hours | Aktywacja |
|--------|------|------|---------|-------|-----------------|----------|---------------|-----------|
| L1 | SRE Primary On-Call | `{{ONCALL_PRIMARY_NAME}}` | `{{ONCALL_PRIMARY_PHONE}}` | `{{ONCALL_PRIMARY_EMAIL}}` | `{{ONCALL_PRIMARY_SIGNAL}}` | `{{ONCALL_PRIMARY_TZ}}` | `{{ONCALL_PRIMARY_HOURS}}` | Zawsze pierwsze alerty |
| L1 | SRE Backup On-Call | `{{ONCALL_BACKUP_NAME}}` | `{{ONCALL_BACKUP_PHONE}}` | `{{ONCALL_BACKUP_EMAIL}}` | `{{ONCALL_BACKUP_SIGNAL}}` | `{{ONCALL_BACKUP_TZ}}` | `{{ONCALL_BACKUP_HOURS}}` | Brak ACK od Primary w SLA |
| L2 | Incident Commander | `{{IC_NAME}}` | `{{IC_PHONE}}` | `{{IC_EMAIL}}` | `{{IC_SIGNAL}}` | `{{IC_TZ}}` | `{{IC_HOURS}}` | P0/P1: zawsze; P2: brak rozwiązania >2h |
| L2 | Lead Developer | `{{LEAD_DEV_NAME}}` | `{{LEAD_DEV_PHONE}}` | `{{LEAD_DEV_EMAIL}}` | `{{LEAD_DEV_SIGNAL}}` | `{{LEAD_DEV_TZ}}` | `{{LEAD_DEV_HOURS}}` | P0/P1; bug aplikacyjny P2 |
| L2 | DevOps Lead | `{{DEVOPS_LEAD_NAME}}` | `{{DEVOPS_LEAD_PHONE}}` | `{{DEVOPS_LEAD_EMAIL}}` | `{{DEVOPS_LEAD_SIGNAL}}` | `{{DEVOPS_LEAD_TZ}}` | `{{DEVOPS_LEAD_HOURS}}` | P0/P1 infrastruktura |
| L2 | Mobile Team Lead | `{{MOBILE_LEAD_NAME}}` | `{{MOBILE_LEAD_PHONE}}` | `{{MOBILE_LEAD_EMAIL}}` | `{{MOBILE_LEAD_SIGNAL}}` | `{{MOBILE_LEAD_TZ}}` | `{{MOBILE_LEAD_HOURS}}` | INC-005 Pixel 9 |
| L2 | Network Team Lead | `{{NETWORK_LEAD_NAME}}` | `{{NETWORK_LEAD_PHONE}}` | `{{NETWORK_LEAD_EMAIL}}` | `{{NETWORK_LEAD_SIGNAL}}` | `{{NETWORK_LEAD_TZ}}` | `{{NETWORK_LEAD_HOURS}}` | INC-006 Mudi router |
| L2 | DBA | `{{DBA_NAME}}` | `{{DBA_PHONE}}` | `{{DBA_EMAIL}}` | `{{DBA_SIGNAL}}` | `{{DBA_TZ}}` | `{{DBA_HOURS}}` | INC-007/008 DB issues |
| L3 | CTO | `{{CTO_NAME}}` | `{{CTO_PHONE}}` | `{{CTO_EMAIL}}` | `{{CTO_SIGNAL}}` | `{{CTO_TZ}}` | `{{CTO_HOURS}}` | P0 brak postępu >30 min |
| L3 | Security Lead / Pentester | `{{SEC_NAME}}` | `{{SEC_PHONE}}` | `{{SEC_EMAIL}}` | `{{SEC_SIGNAL}}` | `{{SEC_TZ}}` | `{{SEC_HOURS}}` | INC-002/003 naruszenie/vuln |
| L4 | DPO Polska | `{{DPO_PL_NAME}}` | `{{DPO_PL_PHONE}}` | `{{DPO_PL_EMAIL}}` | `{{DPO_PL_SIGNAL}}` | Europe/Warsaw | Business hours | INC-002 RODO breach 72h |
| L4 | DPO Niemcy | `{{DPO_DE_NAME}}` | `{{DPO_DE_PHONE}}` | `{{DPO_DE_EMAIL}}` | `{{DPO_DE_SIGNAL}}` | Europe/Berlin | Business hours | INC-002 DSGVO breach 72h |
| L4 | Legal Counsel | `{{LEGAL_NAME}}` | `{{LEGAL_PHONE}}` | `{{LEGAL_EMAIL}}` | `{{LEGAL_SIGNAL}}` | `{{LEGAL_TZ}}` | `{{LEGAL_HOURS}}` | INC-002/003 |

---

### 1.5 Drzewo Eskalacji — Diagram

```
ALERT WYZWOLONY
       │
       ▼
[L1] SRE Primary On-Call
       │
       ├── ACK w SLA? → TRIAGE + MITIGATION
       │
       └── Brak ACK (P0: >5 min, P1: >15 min)
              │
              ▼
       [L1] SRE Backup On-Call
              │
              ├── ACK → TRIAGE + eskaluj do IC
              │
              └── Brak ACK (+5 min)
                     │
                     ▼
              [L2] Incident Commander
                     │
                     ├── P0 natychmiast → CTO (L3)
                     ├── Data breach → DPO + Legal (L4)
                     ├── Security vuln → Security Lead (L3)
                     ├── DB issue → DBA (L2)
                     ├── Pixel 9 → Mobile Lead (L2)
                     └── Mudi router → Network Lead (L2)
```

---

## 2. Incident Taxonomy & Severity

### 2.1 Severity Matrix (P0–P4)

| Priorytet | Nazwa | Kryteria | SLA Reakcja | SLA Rozwiązanie | Eskalacja |
|-----------|-------|----------|-------------|-----------------|-----------| 
| **P0** | Critical | Całkowita niedostępność produkcji; utrata danych; DB corruption; wszyscy użytkownicy | 5 min | 1 godz. | Natychmiastowa: IC + CTO + Lead Dev |
| **P1** | Major | >50% użytkowników niedostępnych; pipeline całkowicie zablokowany; auth failure globalna | 15 min | 4 godz. | 15 min: IC + Lead Dev + DevOps |
| **P2** | Moderate | Degradacja <50% użytkowników; disk >90%; OOM sporadyczny; fallback aktywny | 30 min | 8 godz. | 30 min: DevOps On-call |
| **P3** | Minor | Błędy <5% użytkowników; ostrzeżenia; disk >80% | 2 godz. | 24 godz. | Standardowy ticket |
| **P4** | Informational | Niekrytyczne błędy; wnioski | 8 godz. | 72 godz. | Backlog sprint |

### 2.2 Matryca Decyzyjna

```
Czy produkcja jest całkowicie niedostępna?
  → TAK → P0
  → NIE ↓
Czy >50% użytkowników ma problemy LUB dane są tracone?
  → TAK → P1
  → NIE ↓
Czy degradacja wpływa na krytyczne funkcje (auth, pipeline, DB, LLM)?
  → TAK → P2
  → NIE ↓
Czy błąd jest powtarzalny i wpływa na małą grupę?
  → TAK → P3
  → NIE → P4
```

---

## 3. Runbooks per Incident Type

### INC-001: Production Down — HTTP 5xx >50%

**Klasyfikacja:** P0  
**SLA Ack:** 5 min  
**SLA Resolve:** 1 godz.  
**Eskalacja:** Primary → Backup → IC → CTO  
**Trigger:** HTTP 5xx error rate >50% przez >3 min  

#### Krok 1 — Natychmiastowy triage (pierwsze 5 min)

```bash
# 1. Potwierdź problem
curl -sv --max-time 5 https://{{PROD_DOMAIN}}/health 2>&1 | grep -E "HTTP|< |error"

# 2. Sprawdź error rate
grep -cE '"(GET|POST|PUT|DELETE).*" (500|502|503|504)' \
  /var/log/nginx/access.log

# 3. Quick snapshot
systemctl status sylion.service --no-pager -l | tail -30
journalctl -u sylion.service -n 100 --no-pager | grep -iE "error|critical|fatal|crash"

# 4. Czy port odpowiada?
curl -sf --max-time 3 http://127.0.0.1:8000/health && echo "OK" || echo "DOWN"
```

#### Krok 2 — Klasyfikacja przyczyny

```
Port 8000 odpowiada?
├── NIE → Aplikacja down → RESTART (Sekcja 4.1)
│         Sprawdź: OOM killer, disk full, crash
└── TAK → Upstream error
          ├── 504 (timeout)? → Sprawdź DB / długie zapytania
          ├── 503? → Sprawdź pool wątków
          └── 502? → Crash workerów
```

#### Krok 3 — Mitigation

```bash
# Opcja A: Restart serwisu
bash /opt/sylion/scripts/sylion-restart.sh

# Opcja B: Jeśli OOM — tymczasowy swap
fallocate -l 2G /tmp/swapfile && chmod 600 /tmp/swapfile
mkswap /tmp/swapfile && swapon /tmp/swapfile

# Opcja C: Jeśli disk full — WAL checkpoint
sqlite3 /var/lib/sylion/sylion.db "PRAGMA wal_checkpoint(TRUNCATE);"
df -h  # Weryfikacja wolnego miejsca
```

#### Krok 4 — Weryfikacja i komunikacja

```bash
# Weryfikacja health
for i in 1 2 3; do
  sleep 10
  curl -sf --max-time 5 http://127.0.0.1:8000/health && echo "PASS $(date)" || echo "FAIL $(date)"
done

# Komunikat Slack #incidents-critical
echo "INC-001 [$(date -u +%Y-%m-%dT%H:%M:%SZ)] STATUS: [RESOLVED/IN-PROGRESS] | HTTP 5xx >50% | Przyczyna: [OPIS] | Operator: {{ONCALL_PRIMARY_NAME}}"
```

---

### INC-002: Data Breach Suspected — Podejrzenie Naruszenia Danych

**Klasyfikacja:** P0  
**SLA Ack:** 5 min  
**SLA Resolve:** 72 godz. (RODO art. 33 — zgłoszenie do organu nadzoru)  
**Eskalacja OBOWIĄZKOWA:** Primary → IC → DPO PL/DE → Legal → CERT Polska / BSI  
**Trigger:** Nieautoryzowany dostęp do danych osobowych; eksfiltracja danych; anomalia w logach dostępu  

> ⚠️ **RODO/DSGVO:** Naruszenie ochrony danych osobowych musi być zgłoszone organowi nadzorczemu **w ciągu 72 godzin** od momentu wykrycia (art. 33 RODO). Jeśli naruszenie dotyczy wysokiego ryzyka dla osób — obowiązek powiadomienia tych osób (art. 34 RODO).

#### Krok 1 — Izolacja i zabezpieczenie dowodów

```bash
# ZATRZYMAJ aplikację jeśli naruszenie jest aktywne
# NIE usuwaj logów — to dowody

INCIDENT_ID="INC-002-$(date +%Y%m%d-%H%M%S)"
mkdir -p /var/log/sylion/security/${INCIDENT_ID}

# Zrzuć logi dostępu — NIENARUSZONE
cp /var/log/nginx/access.log /var/log/sylion/security/${INCIDENT_ID}/nginx_access_$(date +%s).log
cp /var/log/nginx/error.log /var/log/sylion/security/${INCIDENT_ID}/nginx_error_$(date +%s).log
journalctl -u sylion.service --since "48 hours ago" --no-pager \
  > /var/log/sylion/security/${INCIDENT_ID}/sylion_journal.log

# Snapshot aktywnych połączeń
ss -tnp > /var/log/sylion/security/${INCIDENT_ID}/connections_$(date +%s).txt
netstat -an > /var/log/sylion/security/${INCIDENT_ID}/netstat_$(date +%s).txt

echo "Dowody zabezpieczone: /var/log/sylion/security/${INCIDENT_ID}/"
```

#### Krok 2 — Ocena zakresu naruszenia

```bash
# Sprawdź anomalie logów dostępu (masowe pobieranie danych)
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -20
# Sprawdź duże odpowiedzi (potencjalna eksfiltracja)
awk '$10 > 1000000 {print $1, $7, $10, $9}' /var/log/nginx/access.log | tail -50

# Sprawdź podejrzane IP (poza whitelist)
# Lista dozwolonych IP: {{ALLOWED_IP_WHITELIST_PATH}}
grep -v -f {{ALLOWED_IP_WHITELIST_PATH}} /var/log/nginx/access.log | \
  awk '{print $1}' | sort | uniq -c | sort -rn | head -20

# Sprawdź dostęp do wrażliwych endpointów
grep -E "/(admin|api/users|api/export|api/data)" /var/log/nginx/access.log | \
  awk '{print $1, $7, $9}' | sort | uniq -c | sort -rn
```

#### Krok 3 — Eskalacja (OBOWIĄZKOWA — wykonaj natychmiast)

**Eskalacja do wykonania w ciągu 1 godziny od wykrycia:**

1. **IC (`{{IC_NAME}}`, `{{IC_PHONE}}`)** — poinformuj natychmiast
2. **DPO Polska (`{{DPO_PL_NAME}}`, `{{DPO_PL_EMAIL}}`)** — obowiązek 72h RODO
3. **DPO Niemcy (`{{DPO_DE_NAME}}`, `{{DPO_DE_EMAIL}}`)** — jeśli dotyczy użytkowników DE
4. **Legal (`{{LEGAL_NAME}}`, `{{LEGAL_EMAIL}}`)** — ocena prawna
5. **CTO (`{{CTO_NAME}}`, `{{CTO_PHONE}}`)** — decyzja o komunikacji zewnętrznej

**Szablon wiadomości eskalacji:**
```
BEZPIECZEŃSTWO — NARUSZENIE DANYCH [POUFNE]
Data wykrycia: {{TIMESTAMP_ISO8601}}
Incydent ID: {{INCIDENT_ID}}
Zakres (wstępny): [OPIS — ilu użytkowników, jakie dane]
Status: [AKTYWNE / ZAWARTE]
Operator wykrywający: {{ONCALL_PRIMARY_NAME}}
Działania podjęte: [LISTA]
Kontakt: {{ONCALL_PRIMARY_PHONE}}
```

#### Krok 4 — Kontakty regulacyjne (patrz Sekcja 5)

- **CERT Polska:** cert@cert.pl | https://incydent.cert.pl | tel: +48 22 380 82 74
- **UODO (organ nadzoru PL):** https://uodo.gov.pl/pl/83/155 | kancelaria@uodo.gov.pl
- **BSI (Niemcy):** https://www.bsi.bund.de/meldestellen | bsi@bsi.bund.de

---

### INC-003: Security Vulnerability — Podatność Bezpieczeństwa

**Klasyfikacja:** P0/P1 (zależy od CVSS)  
**SLA Ack:** 5 min (krytyczna CVSS ≥9.0) / 15 min (wysoka CVSS 7.0–8.9)  
**Eskalacja:** Primary → IC → Security Lead/Pentester → CTO  
**Trigger:** CVE zgłoszone przez researcher; alert SAST/DAST; podejrzana aktywność  

#### Krok 1 — Ocena i embargo

```bash
# Zasada embargo: NIE publikuj szczegółów podatności publicznie
# dopóki patch nie jest wdrożony i disclosure timeline nie jest ustalony

VULN_ID="VULN-$(date +%Y%m%d-%H%M%S)"
mkdir -p /var/log/sylion/security/vulns/${VULN_ID}

# Dokumentuj podatność (POUFNE)
cat > /var/log/sylion/security/vulns/${VULN_ID}/vuln-report.txt << EOF
Vulnerability ID: ${VULN_ID}
Zgłoszono: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Zgłaszający: [INTERNAL / EXTERNAL RESEARCHER]
CVE: [jeśli znane]
CVSS Score: [0.0-10.0]
Opis: [OPIS PODATNOŚCI]
Dotknięte komponenty: [LISTA]
Proof of Concept: [TAK / NIE]
Exploitability: [AKTYWNIE EXPLOITOWANA / POC / TEORETYCZNA]
EOF
```

#### Krok 2 — Natychmiastowe mitigacje

```bash
# Jeśli podatność jest aktywnie exploitowana:
# 1. Blokada IP / WAF rule
# Dodaj regułę do nginx / firewall
iptables -I INPUT -s {{ATTACKER_IP}} -j DROP

# 2. Wyłącz podatny endpoint (tymczasowo)
# nginx: comment out location block dla endpointu
systemctl reload nginx

# 3. Rotuj klucze API i tokeny sesji jeśli skompromitowane
sqlite3 /var/lib/sylion/sylion.db \
  "UPDATE sessions SET expires_at = datetime('now') WHERE 1=1;"
```

#### Krok 3 — Disclosure Timeline

| Dzień | Działanie |
|-------|-----------|
| D+0 | Wykrycie i embargo; triage; eskalacja do Security Lead |
| D+1 | Patch opracowany i przetestowany wewnętrznie |
| D+3 | Deploy patch na produkcję |
| D+7 | Powiadomienie researcher'a (jeśli zewnętrzny) |
| D+14 | Publiczne disclosure po potwierdzeniu patcha |
| D+30 | CVE publikacja (jeśli wymagana) |

**Kontakt dla Security Lead / Pentester:**

| Pole | Wartość |
|------|---------|
| Imię i Nazwisko | `{{SEC_NAME}}` |
| Telefon | `{{SEC_PHONE}}` |
| Email (szyfrowany) | `{{SEC_EMAIL}}` |
| Signal | `{{SEC_SIGNAL}}` |
| PGP Key Fingerprint | `{{SEC_PGP_FINGERPRINT}}` |

---

### INC-004: LLM Provider Outage — Anthropic/OpenAI Down

**Klasyfikacja:** P1  
**SLA Ack:** 15 min  
**SLA Resolve:** 4 godz. (lub do przywrócenia przez provider)  
**Eskalacja:** Primary → IC → Lead Dev  
**Trigger:** API provider zwraca 5xx / timeout przez >5 min  

#### Krok 1 — Weryfikacja awarii

```bash
# Sprawdź status provider'ów
curl -sf --max-time 10 https://status.anthropic.com/ | grep -iE "operational|degraded|outage"
curl -sf --max-time 10 https://status.openai.com/ | grep -iE "operational|degraded|outage"

# Sprawdź logi błędów API
journalctl -u sylion.service --since "15 minutes ago" | \
  grep -iE "anthropic|openai|claude|gpt|llm|api.*error|rate.limit|quota" | tail -30

# Sprawdź error rate API calls
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT provider, status, COUNT(*) as cnt
   FROM llm_api_calls
   WHERE created_at > datetime('now', '-15 minutes')
   GROUP BY provider, status;" 2>/dev/null
```

#### Krok 2 — Przełączenie na Ollama Fallback

```bash
#!/bin/bash
# switch-to-ollama.sh — przełącz SYLION na lokalny Ollama fallback

log_action "LLM FALLBACK: Przełączam na Ollama"

# KROK 1: Sprawdź czy Ollama działa
if ! curl -sf --max-time 5 http://localhost:11434/api/tags > /dev/null; then
  echo "BŁĄD: Ollama nie działa na localhost:11434"
  echo "Uruchom: systemctl start ollama"
  systemctl start ollama 2>/dev/null || docker start ollama 2>/dev/null
  sleep 10
fi

# KROK 2: Sprawdź dostępne modele
curl -s http://localhost:11434/api/tags | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin)['models']]"

# KROK 3: Ustaw zmienną środowiskową / konfigurację
# Opcja A: env var
export SYLION_LLM_PROVIDER="ollama"
export SYLION_LLM_BASE_URL="http://localhost:11434"
export SYLION_LLM_MODEL="{{OLLAMA_FALLBACK_MODEL}}"  # np. llama3.2:3b, mistral:7b

# Opcja B: config file
sed -i 's/^LLM_PROVIDER=.*/LLM_PROVIDER=ollama/' /etc/sylion/sylion.env
sed -i 's/^LLM_BASE_URL=.*/LLM_BASE_URL=http:\/\/localhost:11434/' /etc/sylion/sylion.env
sed -i "s/^LLM_MODEL=.*/LLM_MODEL={{OLLAMA_FALLBACK_MODEL}}/" /etc/sylion/sylion.env

# KROK 4: Restart z nową konfiguracją
systemctl restart sylion.service

# KROK 5: Weryfikacja
sleep 10
curl -sf --max-time 10 http://127.0.0.1:8000/health && \
  echo "FALLBACK AKTYWNY: Ollama {{OLLAMA_FALLBACK_MODEL}}" || \
  echo "FALLBACK FAILED — sprawdź logi"

log_action "LLM FALLBACK: Przełączono na Ollama {{OLLAMA_FALLBACK_MODEL}}"
```

#### Krok 3 — Monitorowanie i powrót

```bash
# Monitoruj status provider'a co 15 min
while true; do
  STATUS=$(curl -sf --max-time 5 https://status.anthropic.com/ 2>/dev/null | \
    grep -c "operational" || echo "0")
  echo "$(date -u +%H:%M:%SZ) Anthropic operational components: $STATUS"
  sleep 900
done

# Powrót do primary provider — po potwierdzeniu że działa
export SYLION_LLM_PROVIDER="anthropic"  # lub openai
systemctl restart sylion.service
log_action "LLM FALLBACK: Powrót do primary provider"
```

---

### INC-005: Pixel 9 Detection Mass Failure — Błąd Wykrywania Masowego

**Klasyfikacja:** P1  
**SLA Ack:** 15 min  
**SLA Resolve:** 4 godz.  
**Eskalacja:** Primary → IC → Mobile Team Lead  
**Trigger:** Failure rate wykrywania Pixel 9 >10% przez >5 min  

#### Krok 1 — Triage

```bash
# Sprawdź failure rate dla Pixel 9
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT device_model, status, COUNT(*) as cnt
   FROM detection_jobs
   WHERE created_at > datetime('now', '-30 minutes')
     AND device_model LIKE '%Pixel 9%'
   GROUP BY device_model, status
   ORDER BY cnt DESC;" 2>/dev/null

# Sprawdź logi błędów
journalctl -u sylion.service --since "30 minutes ago" | \
  grep -iE "pixel.9|detection|camera|model.*error|inference" | tail -50

# Porównaj z innymi urządzeniami
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT device_model,
          SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failures,
          COUNT(*) as total,
          ROUND(100.0 * SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) / COUNT(*), 1) as failure_pct
   FROM detection_jobs
   WHERE created_at > datetime('now', '-1 hour')
   GROUP BY device_model
   ORDER BY failure_pct DESC
   LIMIT 20;" 2>/dev/null
```

#### Krok 2 — Kontakt Mobile Team

**Eskalacja natychmiastowa do Mobile Team Lead:**

| Pole | Wartość |
|------|---------|
| Imię | `{{MOBILE_LEAD_NAME}}` |
| Telefon | `{{MOBILE_LEAD_PHONE}}` |
| Email | `{{MOBILE_LEAD_EMAIL}}` |
| Signal | `{{MOBILE_LEAD_SIGNAL}}` |
| Slack | `@{{MOBILE_LEAD_SLACK}}` |

```bash
# Informacja do mobile team (szablon)
echo "INC-005: Pixel 9 detection failure rate: [X]%
Zaatakowane pipeline: [LISTA]
Logi: journalctl -u sylion.service --since '1 hour ago' | grep -i pixel
DB query: sqlite3 /var/lib/sylion/sylion.db [patrz wyżej]
Owner: {{MOBILE_LEAD_NAME}} {{MOBILE_LEAD_PHONE}}"
```

#### Krok 3 — Tymczasowe obejście

```bash
# Opcja A: Wyłącz Pixel 9 z kolejki do czasu naprawy
sqlite3 /var/lib/sylion/sylion.db \
  "UPDATE detection_jobs
   SET status = 'skipped', last_error = 'INC-005: Pixel 9 maintenance'
   WHERE status = 'pending'
     AND device_model LIKE '%Pixel 9%';"

# Opcja B: Skieruj Pixel 9 jobs na fallback model
# (zależy od implementacji — konsultuj z Mobile Team)

log_action "INC-005: Pixel 9 jobs tymczasowo skipped — oczekiwanie na fix od Mobile Team"
```

---

### INC-006: Mudi Router Offline — Router Sieciowy Offline

**Klasyfikacja:** P1/P2 (zależy od zasięgu)  
**SLA Ack:** 15 min  
**SLA Resolve:** 4 godz.  
**Eskalacja:** Primary → Network Team Lead  
**Trigger:** Router Mudi niedostępny; segmenty sieci izolowane; VPN tunnel down  

#### Krok 1 — Triage sieciowy

```bash
# Sprawdź dostępność routera
MUDI_IP="{{MUDI_ROUTER_IP}}"  # np. 192.168.1.1

ping -c 5 $MUDI_IP && echo "ROUTER OK" || echo "ROUTER NIEDOSTĘPNY"

# Sprawdź routing
ip route show
traceroute $MUDI_IP 2>/dev/null || tracepath $MUDI_IP

# Sprawdź czy jest backup route
ip route show | grep default

# Sprawdź interfejsy
ip addr show
ip link show

# Sprawdź DNS
nslookup {{PROD_DOMAIN}} 8.8.8.8
dig +short {{PROD_DOMAIN}}
```

#### Krok 2 — Kontakt Network Team

**Eskalacja natychmiastowa do Network Team Lead:**

| Pole | Wartość |
|------|---------|
| Imię | `{{NETWORK_LEAD_NAME}}` |
| Telefon | `{{NETWORK_LEAD_PHONE}}` |
| Email | `{{NETWORK_LEAD_EMAIL}}` |
| Signal | `{{NETWORK_LEAD_SIGNAL}}` |
| Slack | `@{{NETWORK_LEAD_SLACK}}` |

#### Krok 3 — Failover / Obejście

```bash
# Opcja A: Przełącz na backup ISP (jeśli dostępny)
# {{BACKUP_ISP_INTERFACE}} — np. eth1, wwan0
ip route replace default via {{BACKUP_GATEWAY}} dev {{BACKUP_ISP_INTERFACE}}
echo "Routing przełączony na backup ISP"

# Opcja B: Restart Mudi przez zarządzanie out-of-band
# Consult Network Team — {{NETWORK_LEAD_PHONE}}

# Opcja C: SSH tunnel przez alternatywną ścieżkę
ssh -L 8000:127.0.0.1:8000 {{BACKUP_JUMP_HOST}} &

log_action "INC-006: Mudi router offline — eskalacja do Network Team {{NETWORK_LEAD_NAME}}"
```

---

### INC-007: DB Corruption — Uszkodzenie Bazy Danych

**Klasyfikacja:** P0  
**SLA Ack:** 5 min  
**SLA Resolve:** 1 godz.  
**Eskalacja:** Primary → IC → DBA → CTO  
**Trigger:** `sqlite3.DatabaseError: database disk image is malformed`; integrity_check != ok  

#### Krok 1 — Natychmiastowa izolacja

```bash
# ZATRZYMAJ aplikację — nie dopuść do dalszych zapisów do uszkodzonej DB
systemctl stop sylion.service 2>/dev/null || docker stop sylion-app 2>/dev/null
sleep 3

# Potwierdź że DB nie jest trzymana
lsof /var/lib/sylion/sylion.db 2>/dev/null
fuser /var/lib/sylion/sylion.db 2>/dev/null

log_action "INC-007: Aplikacja zatrzymana — DB isolation"
```

#### Krok 2 — Weryfikacja uszkodzenia

```bash
DB_PATH="/var/lib/sylion/sylion.db"

echo "=== INTEGRITY CHECK ==="
sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | head -20

echo "=== QUICK CHECK ==="
sqlite3 "$DB_PATH" "PRAGMA quick_check;" 2>&1 | head -10

echo "=== FOREIGN KEY CHECK ==="
sqlite3 "$DB_PATH" "PRAGMA foreign_key_check;" 2>&1 | head -10

echo "=== WAL STATUS ==="
ls -lah ${DB_PATH}* 2>/dev/null

echo "=== PAGE COUNT ==="
sqlite3 "$DB_PATH" "PRAGMA page_count; PRAGMA freelist_count;" 2>&1
```

#### Krok 3 — Restore z Backupu (rollback.sh)

```bash
#!/bin/bash
# Wykonaj restore z backupu M-08
# Pełna dokumentacja: Sekcja 4.4

DB_PATH="/var/lib/sylion/sylion.db"
BACKUP_DIR="/var/lib/sylion/backups"

# Archiwizuj uszkodzoną DB (ZACHOWAJ — dowód)
CORRUPTED_SAVE="${DB_PATH}.corrupted.$(date +%Y%m%d%H%M%S)"
cp "$DB_PATH" "$CORRUPTED_SAVE"
log_action "INC-007: Uszkodzona DB zachowana: $CORRUPTED_SAVE"

# Znajdź najnowszy backup
BACKUP=$(ls -t "$BACKUP_DIR"/sylion.db.*.sqlite \
             "$BACKUP_DIR"/sylion.db.backup.* \
             "$BACKUP_DIR"/*.db.backup 2>/dev/null | head -1)
echo "Backup do restore: $BACKUP"

# Weryfikuj backup przed restore
INTEGRITY=$(sqlite3 "$BACKUP" "PRAGMA integrity_check;" 2>&1 | head -1)
[ "$INTEGRITY" != "ok" ] && { echo "BŁĄD: Backup uszkodzony!"; exit 1; }
echo "Backup integrity: OK"

# Restore
sqlite3 "$BACKUP" ".backup $DB_PATH"

# Weryfikuj odtworzoną DB
NEW_INTEGRITY=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | head -1)
echo "Odtworzona DB integrity: $NEW_INTEGRITY"

# Uruchom aplikację
systemctl start sylion.service

# Health check
sleep 10
curl -sf --max-time 10 http://127.0.0.1:8000/health && \
  echo "RESTORE SUCCESS" || echo "RESTORE FAILURE — sprawdź logi"

log_action "INC-007: Restore zakończony — integrity: $NEW_INTEGRITY"
```

---

### INC-008: WAL >1 GB — Zapełniony Write-Ahead Log

**Klasyfikacja:** P1  
**SLA Ack:** 15 min  
**SLA Resolve:** 4 godz.  
**Eskalacja:** Primary → DBA  
**Trigger:** Plik `sylion.db-wal` >1 GB; alarm disk usage  

#### Krok 1 — Triage WAL

```bash
DB_PATH="/var/lib/sylion/sylion.db"

# Sprawdź rozmiary plików
echo "=== ROZMIARY PLIKÓW DB ==="
ls -lah ${DB_PATH}* 2>/dev/null

# Sprawdź stan WAL
echo "=== WAL STATUS ==="
sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint;" 2>&1

# Sprawdź czy są aktywne transakcje blokujące checkpoint
echo "=== AKTYWNE POŁĄCZENIA DB ==="
lsof "$DB_PATH" 2>/dev/null
fuser "$DB_PATH" 2>/dev/null

# Sprawdź write amplification
echo "=== STATYSTYKI PAGE ==="
sqlite3 "$DB_PATH" "
  PRAGMA page_count;
  PRAGMA page_size;
  PRAGMA freelist_count;
  PRAGMA wal_autocheckpoint;
" 2>&1
```

#### Krok 2 — WAL Checkpoint i naprawa

```bash
#!/bin/bash
# wal-checkpoint.sh — wymuś checkpoint i zbadaj write amplification

DB_PATH="/var/lib/sylion/sylion.db"

log_action "INC-008: WAL checkpoint rozpoczęty"

# Backup przed operacją
BACKUP="/var/lib/sylion/backups/sylion.db.pre-wal-fix.$(date +%Y%m%d%H%M%S)"
sqlite3 "$DB_PATH" ".backup $BACKUP"
log_action "INC-008: Backup: $BACKUP"

# Wymuś checkpoint
echo "=== CHECKPOINT TRUNCATE ==="
sqlite3 "$DB_PATH" << 'SQL'
PRAGMA wal_checkpoint(TRUNCATE);
SQL

# Sprawdź wynik
ls -lah ${DB_PATH}* 2>/dev/null

# Jeśli WAL nadal duży — zidentyfikuj przyczynę write amplification
echo "=== DIAGNOZA WRITE AMPLIFICATION ==="
sqlite3 "$DB_PATH" << 'SQL'
-- Tabele z największą liczbą zmian
SELECT name, (SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name=m.name) as indexes
FROM sqlite_master m
WHERE type='table'
ORDER BY name;

-- Sprawdź auto_vacuum
PRAGMA auto_vacuum;
PRAGMA wal_autocheckpoint;
PRAGMA synchronous;
PRAGMA journal_mode;
SQL

# Włącz auto checkpoint jeśli wyłączony
sqlite3 "$DB_PATH" "PRAGMA wal_autocheckpoint=1000;"

# Wymuś VACUUM jeśli potrzebne
echo "=== INCREMENTAL VACUUM ==="
sqlite3 "$DB_PATH" << 'SQL'
PRAGMA auto_vacuum=INCREMENTAL;
PRAGMA incremental_vacuum(5000);
SQL

# Końcowy rozmiar
ls -lah ${DB_PATH}* 2>/dev/null
log_action "INC-008: WAL checkpoint zakończony"
```

#### Krok 3 — Długoterminowe zapobieganie

```bash
# Dodaj do /etc/sylion/sylion.env lub config:
# SQLITE_WAL_AUTOCHECKPOINT=1000
# SQLITE_SYNCHRONOUS=NORMAL
# SQLITE_AUTO_VACUUM=INCREMENTAL

# Cron: sprawdzanie WAL co 15 min
echo "*/15 * * * * root ls -la /var/lib/sylion/sylion.db-wal 2>/dev/null | \
  awk '\$5 > 1073741824 {print \"WAL >1GB alert: \" \$5 \" bytes\"}' | \
  mail -s 'SYLION WAL ALERT' {{ONCALL_PRIMARY_EMAIL}}" \
  >> /etc/cron.d/sylion-wal-monitor

log_action "INC-008: WAL monitor cron dodany"
```

---

## 4. Mitigation & Recovery Procedures

### 4.0 Przed Jakimkolwiek Działaniem

```bash
INCIDENT_ID="${INCIDENT_ID:-INC-$(date +%Y%m%d-%H%M%S)}"
INCIDENT_LOG="/var/log/sylion/incidents/${INCIDENT_ID}/actions.log"
mkdir -p "$(dirname $INCIDENT_LOG)"

log_action() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [$(whoami)] $1" | tee -a "$INCIDENT_LOG"
}

log_action "INCIDENT RECOVERY START — $INCIDENT_ID"
log_action "Operator: $(whoami)@$(hostname)"
```

### 4.1 Restart Procedura

```bash
#!/bin/bash
# Bezpieczny restart z backup DB i WAL checkpoint
DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"
BACKUP_DIR="/var/lib/sylion/backups"
mkdir -p "$BACKUP_DIR"

# Backup DB
BACKUP_FILE="$BACKUP_DIR/sylion.db.pre-restart.$(date +%Y%m%d%H%M%S)"
sqlite3 "$DB_PATH" ".backup $BACKUP_FILE" 2>/dev/null || cp "$DB_PATH" "$BACKUP_FILE"
log_action "Backup: $BACKUP_FILE"

# Checkpoint WAL
sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(FULL);" 2>/dev/null || true

# Stop
systemctl stop sylion.service 2>/dev/null || docker stop sylion-app 2>/dev/null || true
sleep 3
pkill -TERM -f "sylion|gunicorn|uvicorn" 2>/dev/null; sleep 5

# Start
systemctl start sylion.service 2>/dev/null || docker start sylion-app 2>/dev/null

# Health check loop
sleep 5; MAX_WAIT=60; ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  curl -sf --max-time 3 http://127.0.0.1:8000/health > /dev/null 2>&1 && \
    { log_action "RESTART SUCCESS"; echo "SUCCESS"; break; }
  sleep 5; ELAPSED=$((ELAPSED + 5))
done
[ $ELAPSED -ge $MAX_WAIT ] && { log_action "RESTART TIMEOUT"; exit 1; }
```

### 4.2 Rollback Procedura

```bash
# Rollback do poprzedniej wersji
# Użycie: bash rollback.sh [VERSION]
# Pełny skrypt: /opt/sylion/scripts/rollback.sh
TARGET="${1:-}"
RELEASES_DIR="/opt/sylion/releases"
[ -z "$TARGET" ] && TARGET=$(ls -td "$RELEASES_DIR"/v*.*.* 2>/dev/null | head -2 | tail -1 | xargs basename)
ln -sfn "$RELEASES_DIR/$TARGET" /opt/sylion/current
systemctl restart sylion.service
curl -sf http://127.0.0.1:8000/health && echo "ROLLBACK SUCCESS: $TARGET"
```

### 4.3 WAL Checkpoint (Disk Full)

```bash
sqlite3 /var/lib/sylion/sylion.db << 'SQL'
PRAGMA wal_checkpoint(TRUNCATE);
PRAGMA auto_vacuum=INCREMENTAL;
PRAGMA incremental_vacuum(1000);
SQL
ls -lah /var/lib/sylion/sylion.db* 2>/dev/null
```

### 4.4 Restore DB z Backupu M-08

```bash
# Skrypt: /opt/sylion/scripts/restore_db_m08.sh
# Pełna dokumentacja: Sekcja INC-007 / Krok 3
bash /opt/sylion/scripts/restore_db_m08.sh [BACKUP_FILE]
```

---

## 5. Legal & Regulatory Contacts

> **POUFNE** — kontakty zewnętrzne regulacyjne i prawne.

### 5.1 DPO — Data Protection Officer

#### DPO Polska

| Pole | Wartość |
|------|---------|
| **Imię i Nazwisko** | `{{DPO_PL_NAME}}` |
| **Organizacja** | `{{DPO_PL_ORG}}` |
| **Telefon** | `{{DPO_PL_PHONE}}` |
| **Email** | `{{DPO_PL_EMAIL}}` |
| **Signal / Telegram** | `{{DPO_PL_SIGNAL}}` |
| **Adres pocztowy** | `{{DPO_PL_ADDRESS}}` |
| **Timezone** | Europe/Warsaw |
| **Working hours** | `{{DPO_PL_HOURS}}` |
| **Aktywacja** | INC-002: naruszenie danych; w ciągu 1h od wykrycia |
| **Obowiązek RODO** | Art. 33: zgłoszenie do UODO w 72h; Art. 34: powiadomienie osób gdy wysokie ryzyko |

#### DPO Niemcy (DSGVO)

| Pole | Wartość |
|------|---------|
| **Imię i Nazwisko** | `{{DPO_DE_NAME}}` |
| **Organizacja** | `{{DPO_DE_ORG}}` |
| **Telefon** | `{{DPO_DE_PHONE}}` |
| **Email** | `{{DPO_DE_EMAIL}}` |
| **Signal / Telegram** | `{{DPO_DE_SIGNAL}}` |
| **Adres pocztowy** | `{{DPO_DE_ADDRESS}}` |
| **Timezone** | Europe/Berlin |
| **Working hours** | `{{DPO_DE_HOURS}}` |
| **Aktywacja** | INC-002: jeśli dotknięci użytkownicy DE; DSGVO §65a |

### 5.2 CERT Polska

| Pole | Wartość |
|------|---------|
| **Nazwa** | CERT Polska (CSIRT NASK) |
| **Email incydentów** | cert@cert.pl |
| **Portal zgłoszeń** | https://incydent.cert.pl |
| **Telefon** | +48 22 380 82 74 |
| **Godziny** | 24/7 dla incydentów krytycznych |
| **Klucz PGP** | https://www.cert.pl/en/kontakt/ |
| **Kiedy zgłaszać** | INC-002: naruszenie danych; INC-003: podatność krytyczna; ataki DDoS; ransomware |
| **Czas zgłoszenia** | Jak najszybciej; P0 w ciągu 4h |

### 5.3 BSI — Bundesamt für Sicherheit in der Informationstechnik (Niemcy)

| Pole | Wartość |
|------|---------|
| **Nazwa** | BSI (Federalny Urząd ds. Bezpieczeństwa Informacji) |
| **Email** | bsi@bsi.bund.de |
| **Portal** | https://www.bsi.bund.de/meldestellen |
| **Portal MELDUNG** | https://www.bsi.bund.de/DE/Themen/Unternehmen-und-Organisationen/Informationen-und-Empfehlungen/Meldestellen/meldestellen.html |
| **Telefon** | +49 228 99 9582-0 |
| **Godziny** | Poniedziałek–Piątek 08:00–18:00 CET |
| **Kiedy zgłaszać** | INC-002/003: jeśli firma ma siedzibę DE lub klientów DE |

### 5.4 UODO — Urząd Ochrony Danych Osobowych (Polska)

| Pole | Wartość |
|------|---------|
| **Nazwa** | UODO — Urząd Ochrony Danych Osobowych |
| **Portal zgłoszeń** | https://uodo.gov.pl/pl/83/155 |
| **Email** | kancelaria@uodo.gov.pl |
| **Formularz online** | https://www.uodo.gov.pl/pl/p/formularz-zgloszenia-naruszenia |
| **Telefon** | +48 22 531 03 00 |
| **Godziny** | 8:00–16:00 CET (pon–pt) |
| **Termin** | 72h od wykrycia naruszenia (RODO art. 33) |

### 5.5 Procedura Zgłoszenia Naruszenia (INC-002)

```
GODZINA 0:    Wykrycie potencjalnego naruszenia
GODZINA 0–1:  Izolacja + triage zakresu + eskalacja do DPO + IC + Legal
GODZINA 1–24: Analiza szczegółowa, dokumentacja zakresu naruszenia
GODZINA 24:   Konsultacja z DPO — czy art. 34 RODO wymaga notyfikacji osób
GODZINA 48:   Przygotowanie zgłoszenia do UODO / BfDI (DE)
GODZINA <72:  ZŁOŻENIE ZGŁOSZENIA do organu nadzoru [RODO art. 33]
GODZINA 72+:  Dalsze raportowanie jeśli informacje niekompletne przy zgłoszeniu
```

---

## 6. Communication Channels

| Kanał | Cel | Dostęp |
|-------|-----|--------|
| `#incidents-critical` | P0/P1 real-time koordynacja | Cały zespół |
| `#incidents-prod` | P2/P3 tracking | Cały zespół |
| `#alerts-sre` | Automatyczne alerty | SRE + DevOps |
| PagerDuty Schedule | Automatyczna rotacja dyżurów | `{{PAGERDUTY_SCHEDULE_URL}}` |
| War Room (Zoom/Meet) | Telekonferencja P0/P1 | `{{WAR_ROOM_LINK}}` |
| Status Page | Komunikacja zewnętrzna | `{{STATUS_PAGE_URL}}` |
| Slack workspace | Główny komunikator | `{{SLACK_WORKSPACE_URL}}` |

---

## 7. On-call Handoff Procedure

```bash
# Szablon wiadomości handoff — wyślij na #incidents-critical przed końcem dyżuru
ON_CALL_HANDOFF="
=== HANDOFF DYŻUR SRE ===
Przekazuje: {{ONCALL_OUTGOING_NAME}} → Przejmuje: {{ONCALL_INCOMING_NAME}}
Czas: $(date -u +%Y-%m-%dT%H:%M:%SZ)

Aktywne incydenty: [LISTA LUB 'BRAK']
Otwarte tickety P0/P1: [LISTA LUB 'BRAK']
Ostatnie alerty (24h): [OPIS]
Rzeczy do obserwacji: [OPIS]
WAL size: $(ls -lah /var/lib/sylion/sylion.db-wal 2>/dev/null | awk '{print \$5}' || echo 'brak pliku')
Disk usage: $(df -h /var/lib/sylion 2>/dev/null | tail -1 | awk '{print \$5}')

Runbook: /docs/INCIDENT_RESPONSE_v592.md
Dashboard: {{MONITORING_DASHBOARD_URL}}
PagerDuty: {{PAGERDUTY_SCHEDULE_URL}}
=========================
"
echo "$ON_CALL_HANDOFF"
```

---

## 8. Quick Reference Card

| Incydent | Klasyfikacja | SLA Ack | Pierwsze działanie | Eskalacja |
|----------|-------------|---------|-------------------|-----------|
| INC-001: HTTP 5xx >50% | P0 | 5 min | Sprawdź health + restart | Primary→IC→CTO |
| INC-002: Data breach | P0 | 5 min | Izolacja + zabezpiecz logi | Primary→IC→DPO→Legal |
| INC-003: Security vuln | P0/P1 | 5–15 min | Embargo + patch | Primary→IC→SecLead |
| INC-004: LLM outage | P1 | 15 min | Switch → Ollama | Primary→IC→LeadDev |
| INC-005: Pixel 9 failure | P1 | 15 min | Triage DB + skip stuck | Primary→IC→MobileLead |
| INC-006: Mudi router | P1/P2 | 15 min | Ping + backup route | Primary→NetworkLead |
| INC-007: DB corruption | P0 | 5 min | Stop app + restore backup | Primary→IC→DBA→CTO |
| INC-008: WAL >1 GB | P1 | 15 min | `PRAGMA wal_checkpoint(TRUNCATE)` | Primary→DBA |

---

*SYLION v5.9.2 Incident Response Runbook — wersja 5.9.2*  
*Wygenerowano: 2025-01-01T00:00:00Z*  
*Następny przegląd: po każdym P0/P1 lub co kwartał*  
*Audyt: SRE G-10*
