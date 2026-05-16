# Post-mortem Template — SYLION v5.9.2

**Szablon wersja:** 5.9.2  
**Kiedy stosować:** P0/P1 — obowiązkowo w ciągu 5 dni roboczych. P2 — opcjonalnie.  
**Zasada:** Post-mortem jest **blameless** — skupia się na systemach i procesach, nie na osobach.  
**Plik:** Zapisz jako `POSTMORTEM_INC-YYYYMMDD-HHMMSS.md` w `/var/log/sylion/incidents/`

---

# Post-mortem: [TYTUŁ INCYDENTU]

**ID Incydentu:** `INC-YYYYMMDD-HHMMSS`  
**Typ incydentu:** `INC-00X: [OPIS]` *(np. INC-001: Production Down)*  
**Priorytet:** P0 / P1 / P2  
**Status:** OTWARTY / ZAMKNIĘTY  
**Data zdarzenia:** `YYYY-MM-DDTHH:MM:SSZ`  
**Data zamknięcia:** `YYYY-MM-DDTHH:MM:SSZ`  
**Data post-mortem:** `YYYY-MM-DDTHH:MM:SSZ`  
**Incident Commander:** `{{IC_NAME}}`  
**SRE On-call (Primary):** `{{ONCALL_PRIMARY_NAME}}`  
**SRE On-call (Backup, jeśli aktywowany):** `{{ONCALL_BACKUP_NAME}}`  
**Autorzy tego dokumentu:** [Imię Nazwisko], [Imię Nazwisko]  
**Uczestnicy war-room:** [LISTA]  

---

## Sekcja 1 — Executive Summary

> 2–4 zdania: Co się stało, jak długo trwało, jaki był impact, jak zostało rozwiązane.

[WYPEŁNIJ]

**Przykład:**
> Dnia 2025-03-15 o 14:32 UTC aplikacja SYLION v5.9.1 stała się całkowicie niedostępna
> z powodu przepełnienia pliku WAL SQLite (/var/lib/sylion). Plik WAL osiągnął 1.3 GB
> po wyłączeniu automatycznego checkpointingu. Incydent trwał 47 minut
> i dotknął 100% użytkowników. Przywrócono przez `PRAGMA wal_checkpoint(TRUNCATE)` + restart.

---

## Sekcja 2 — Timeline (ISO 8601)

> Wszystkie czasy w UTC. Każde zdarzenie osobny wiersz.

| Timestamp (UTC) | Zdarzenie | Osoba | Działanie |
|-----------------|-----------|-------|-----------|
| `YYYY-MM-DDTHH:MM:SSZ` | **ALERT WYZWOLONY** | System/PagerDuty | Automatyczny alert; trigger: [OPIS] |
| `YYYY-MM-DDTHH:MM:SSZ` | **ACK** | `{{ONCALL_PRIMARY_NAME}}` | Primary potwierdził incydent |
| `YYYY-MM-DDTHH:MM:SSZ` | **INCIDENT OGŁOSZONY** | `{{IC_NAME}}` | IC wyznaczony; war-room otwarto |
| `YYYY-MM-DDTHH:MM:SSZ` | **TRIAGE ROZPOCZĘTY** | [Imię] | Uruchomiono quick-triage; snapshot systemu |
| `YYYY-MM-DDTHH:MM:SSZ` | **HIPOTEZA 1 sprawdzona** | [Imię] | [Co sprawdzono — wynik] |
| `YYYY-MM-DDTHH:MM:SSZ` | **HIPOTEZA 2 sprawdzona** | [Imię] | [Co sprawdzono — wynik] |
| `YYYY-MM-DDTHH:MM:SSZ` | **ROOT CAUSE ZIDENTYFIKOWANY** | [Imię] | Przyczyna: [KRÓTKI OPIS] |
| `YYYY-MM-DDTHH:MM:SSZ` | **MITIGATION ZASTOSOWANA** | [Imię] | Wykonano: [KOMENDA/DZIAŁANIE] |
| `YYYY-MM-DDTHH:MM:SSZ` | **WERYFIKACJA** | [Imię] | Health check: [pozytywny/negatywny] |
| `YYYY-MM-DDTHH:MM:SSZ` | **INCIDENT ZAMKNIĘTY** | `{{IC_NAME}}` | Ogłoszono w Slack #incidents-critical |
| `YYYY-MM-DDTHH:MM:SSZ` | **POST-MORTEM ZAPLANOWANY** | `{{IC_NAME}}` | Meeting: `YYYY-MM-DD HH:MM UTC` |

**Czas od pierwszego alertu do zamknięcia (TTCL):** `HH:MM:SS`  
**MTTD (Mean Time to Detect):** `HH:MM:SS`  
**MTTI (Mean Time to Identify root cause):** `HH:MM:SS`  
**MTTR (Mean Time to Recover):** `HH:MM:SS`  

---

## Sekcja 3 — Root Cause Analysis

### 3.1 Bezpośrednia Przyczyna

> Jedno zdanie opisujące techniczną przyczynę.

[WYPEŁNIJ]

### 3.2 Łańcuch Przyczynowo-Skutkowy

```
1. [Co się wydarzyło jako pierwsze — zdarzenie inicjujące]
2. [Konsekwencja 1]
3. [Konsekwencja 2]
4. [Bezpośrednia przyczyna awarii]
5. [Efekt dla użytkowników]
```

### 3.3 Diagram Przyczynowo-Skutkowy

```
[Zdarzenie inicjujące]
         │
         ▼
[Konsekwencja techniczna]
         │
         ├──► [Efekt boczny A]
         ├──► [Efekt boczny B]
         └──► [Główna awaria]
                    │
                    ▼
              [Impact dla użytkowników]
```

### 3.4 Analiza 5 Why

```
DLACZEGO [PROBLEM KOŃCOWY]?
→ Bo [przyczyna 1]

DLACZEGO [przyczyna 1]?
→ Bo [przyczyna 2]

DLACZEGO [przyczyna 2]?
→ Bo [przyczyna 3]

DLACZEGO [przyczyna 3]?
→ Bo [przyczyna 4]

DLACZEGO [przyczyna 4]?
→ Bo [przyczyna 5 — ROOT CAUSE]
→ AKCJA NAPRAWCZA: [Co zrobimy żeby to nie wróciło]
```

---

## Sekcja 4 — Contributing Factors (Czynniki Sprzyjające)

| # | Czynnik | Kategoria | Wpływ |
|---|---------|-----------|-------|
| CF-1 | [OPIS] | Monitoring | Wysoki / Średni / Niski |
| CF-2 | [OPIS] | Process | Wysoki / Średni / Niski |
| CF-3 | [OPIS] | Alerting | Wysoki / Średni / Niski |
| CF-4 | [OPIS] | Documentation | Wysoki / Średni / Niski |
| CF-5 | [OPIS] | Infrastructure | Wysoki / Średni / Niski |

---

## Sekcja 5 — Impact Assessment

| Metryka | Wartość |
|---------|---------|
| Czas niedostępności (downtime) | `HH:MM` |
| Użytkownicy dotknięci | `X (Y%)` |
| Nieudane żądania HTTP | `X,XXX` |
| Utracone / rollback transakcje | `X` |
| Dane utracone | `Tak / Nie / X rekordów` |
| SLA breached | `Tak / Nie` |
| Naruszenie RODO | `Tak / Nie` |

```bash
# Zbierz dane impactu po incydencie
# Nieudane żądania:
grep -cE '"(GET|POST|PUT|DELETE).*" (500|502|503|504)' /var/log/nginx/access.log

# Okno incydentu w DB:
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT MIN(created_at), MAX(created_at), COUNT(*)
   FROM audit_log
   WHERE created_at BETWEEN 'YYYY-MM-DD HH:MM:SS' AND 'YYYY-MM-DD HH:MM:SS';"
```

---

## Sekcja 6 — Action Items (Remediation Tasks)

| ID | Działanie | Właściciel | Priorytet | Termin | Status |
|----|-----------|------------|-----------|--------|--------|
| R-01 | [OPIS DZIAŁANIA] | [Imię] | P0/P1/P2 | `YYYY-MM-DD` | TODO / IN-PROGRESS / DONE |
| R-02 | [OPIS DZIAŁANIA] | [Imię] | P0/P1/P2 | `YYYY-MM-DD` | TODO |
| R-03 | [OPIS DZIAŁANIA] | [Imię] | P0/P1/P2 | `YYYY-MM-DD` | TODO |
| R-04 | [OPIS DZIAŁANIA] | [Imię] | P0/P1/P2 | `YYYY-MM-DD` | TODO |
| R-05 | [OPIS DZIAŁANIA] | [Imię] | P0/P1/P2 | `YYYY-MM-DD` | TODO |

### Szablon Ticketu JIRA

```
Tytuł: [POST-MORTEM INC-YYYYMMDD] R-XX: [Opis działania]

Incydent: INC-YYYYMMDD-HHMMSS | Priorytet: P0/P1/P2

Działanie naprawcze:
[Opis co należy zrobić]

Definition of Done:
- [ ] Implementacja
- [ ] Testy (unit/integration)
- [ ] Deploy na staging i weryfikacja
- [ ] Deploy na produkcję
- [ ] Alert lub monitoring zaktualizowany
- [ ] Dokumentacja zaktualizowana

Link do post-mortem: [URL]
```

---

## Sekcja 7 — Learning Outcomes

### 7.1 Co Zadziałało Dobrze

1. [Bądź konkretny — np. "Runbook INC-007 był aktualny i umożliwił szybkie działanie"]
2. [Co zadziałało]
3. [Co zadziałało]

### 7.2 Co Można Poprawić

1. [Konkretnie — np. "Alert na WAL >1GB nie istniał; dodano R-01"]
2. [Co można ulepszyć]
3. [Co można ulepszyć]

### 7.3 Wnioski Systemowe

> Co to incydent mówi nam o naszych systemach, procesach lub narzędziach?

[WYPEŁNIJ]

---

## Sekcja 8 — Metryki Post-mortem

| Metryka | Wartość |
|---------|---------|
| MTTD (Mean Time to Detect) | `MM:SS` |
| MTTI (Mean Time to Identify) | `MM:SS` |
| MTTR (Mean Time to Recover) | `MM:SS` |
| Całkowity czas incydentu | `HH:MM:SS` |
| Liczba action items | `X` |
| Incydenty z tego samego root cause (90 dni) | `X` |
| Czas do pierwszego ACK | `MM:SS` (SLA: P0=5min, P1=15min) |
| SLA dotrzymane | `Tak / Nie` |

---

## Sekcja 9 — Podpisy i Zatwierdzenie

```
Incident Commander:   _________________________ Data: ___________
SRE Lead / Primary:   _________________________ Data: ___________
Tech Lead:            _________________________ Data: ___________
```

Post-mortem zatwierdzony: `TAK / NIE`  
Opublikowany w wiki/Notion: `TAK / NIE`  Link: `[URL]`  
Wersja runbooka zaktualizowana: `TAK / NIE`  

---

*SYLION Post-mortem Template v5.9.2 — SRE G-10 Audit*  
*Plik: POSTMORTEM_INC-YYYYMMDD-HHMMSS.md*
