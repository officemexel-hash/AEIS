# SYLION v5.9.0 — Post-mortem Template
_Model: Gemini 3.1 Pro | Rola: Post-mortem Analyst_

---

## 4. Post-mortem Template

> **Cel:** Każdy incydent P0/P1 wymaga post-mortem. P2 — opcjonalnie. Zakończ post-mortem max 5 dni roboczych po zamknięciu incydentu. Post-mortem jest blameless — skupia się na systemach i procesach, nie na osobach.

---

```markdown
# Post-mortem: [TYTUŁ INCYDENTU]

**ID Incydentu:** INC-YYYYMMDD-HHMMSS  
**Priorytet:** P0 / P1 / P2  
**Status:** OTWARTY / ZAMKNIĘTY  
**Data zdarzenia:** YYYY-MM-DDTHH:MM:SSZ  
**Data post-mortem:** YYYY-MM-DDTHH:MM:SSZ  
**Incident Commander:** [IMIĘ NAZWISKO]  
**Autorzy post-mortem:** [IMIĘ NAZWISKO], [IMIĘ NAZWISKO]  
**Uczestnicy:** [LISTA]  

---

## 4.1 Executive Summary

[2-4 zdania: Co się stało, jak długo trwało, jaki był impact, jak zostało rozwiązane.]

**Przykład:**
> Dnia 2025-03-15 o 14:32 UTC aplikacja SYLION v5.9.0 stała się całkowicie niedostępna na skutek wyczerpania przestrzeni dyskowej (/var/lib/sylion). Plik WAL bazy SQLite urósł do 4.7 GB z powodu braku automatycznego checkpointing po błędnym deploymencie v5.9.0. Incydent trwał 47 minut i dotknął 100% użytkowników. Przywrócono działanie przez ręczne uruchomienie PRAGMA wal_checkpoint(TRUNCATE) i restart serwisu.

---

## 4.2 Timeline (ISO 8601)

| Timestamp (UTC) | Zdarzenie | Osoba | Działanie |
|-----------------|-----------|-------|-----------|
| YYYY-MM-DDTHH:MM:SSZ | ALERT WYZWOLONY — [opis alertu] | System | Automatyczny alert PagerDuty |
| YYYY-MM-DDTHH:MM:SSZ | INCIDENT OGŁOSZONY | [IC Name] | Incident Commander wyznaczony |
| YYYY-MM-DDTHH:MM:SSZ | TRIAGE ROZPOCZĘTY | [Name] | Uruchomiono quick-triage.sh |
| YYYY-MM-DDTHH:MM:SSZ | HIPOTEZA 1 odrzucona | [Name] | Sprawdzono OOM — negatywne |
| YYYY-MM-DDTHH:MM:SSZ | ROOT CAUSE ZIDENTYFIKOWANY | [Name] | Znaleziono: [opis] |
| YYYY-MM-DDTHH:MM:SSZ | MITIGATION ZASTOSOWANA | [Name] | Wykonano: [komenda/działanie] |
| YYYY-MM-DDTHH:MM:SSZ | WERYFIKACJA | [Name] | Health check pozytywny |
| YYYY-MM-DDTHH:MM:SSZ | INCIDENT ZAMKNIĘTY | [IC Name] | Ogłoszono w Slack |
| YYYY-MM-DDTHH:MM:SSZ | POST-MORTEM ZAPLANOWANY | [IC Name] | Meeting na YYYY-MM-DD |

**Czas trwania incydentu:** HH:MM:SS  
**MTTR (Mean Time to Recovery):** HH:MM:SS  
**MTTD (Mean Time to Detect):** HH:MM:SS  

---

## 4.3 Root Cause Analysis

### Bezpośrednia Przyczyna (Root Cause)

[Jedno zdanie opisujące techniczną przyczynę incydentu.]

**Przykład:**
> Brak `wal_autocheckpoint` w konfiguracji SQLite spowodował nieograniczony wzrost pliku WAL po deploymencie v5.9.0, który wyłączył mechanizm automatycznego checkpointingu.

### Jak Przyczyna Wywołała Incydent

```
[Opis łańcucha przyczynowo-skutkowego]

Przykład:
1. Deploy v5.9.0 (2025-03-15T12:00Z) zmienił konfigurację SQLite
2. Parametr wal_autocheckpoint ustawiony na 0 (wyłączony)
3. Każdy zapis do DB powiększał plik WAL bez checkpointowania
4. Po ~2.5 godz. plik WAL osiągnął 4.7 GB, wypełniając /var/lib
5. SQLite zwrócił SQLITE_FULL — aplikacja crashnęła z błędem 500
6. Gunicorn workers restartowały się w pętli (brak wolnego miejsca na logi)
7. Nginx zwracał 502 Bad Gateway
```

### Diagram Przyczynowo-Skutkowy

```
Deploy v5.9.0 (wal_autocheckpoint=0)
         │
         ▼
WAL file rośnie bez ograniczeń
         │
         ▼
/var/lib = 100% (brak miejsca)
         ├──► SQLITE_FULL → crash aplikacji
         ├──► Niemożliwość zapisu logów
         └──► Niemożliwość restartu workera
                    │
                    ▼
              502 Bad Gateway (100% użytkowników)
```

---

## 4.4 Contributing Factors (Czynniki Współprzyczyniające)

| # | Czynnik | Kategoria | Wpływ |
|---|---------|-----------|-------|
| 1 | Brak alertu na rozmiar pliku WAL | Monitoring | Wysoki |
| 2 | Brak code review dla zmiany konfiguracji DB | Process | Wysoki |
| 3 | Alert disk usage wyzwala się przy 95% (za późno) | Alerting | Średni |
| 4 | Brak runbooka dla "disk full" przed tym incydentem | Documentation | Średni |
| 5 | Staging nie odzwierciedla wolumenu danych produkcji | Infrastructure | Niski |

---

## 4.5 Impact Assessment

### Użytkownicy

| Metryka | Wartość |
|---------|---------|
| Czas niedostępności | HH:MM |
| Użytkownicy dotknięci | X (Y%) |
| Nieudane żądania | X,XXX |
| Utracone transakcje | X |
| Dane utracone (jeśli dotyczy) | Tak / Nie / X rekordów |

### Techniczne

```bash
# Komendy do zebrania danych impactu po incydencie
# Nieudane żądania z logów nginx:
grep -E "\" (500|502|503|504)" /var/log/nginx/sylion_access.log \
  --count 2>/dev/null

# Okno incydentu w DB (brak zapisów):
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT MIN(created_at), MAX(created_at), COUNT(*) 
   FROM audit_log 
   WHERE created_at BETWEEN 'YYYY-MM-DD HH:MM:SS' AND 'YYYY-MM-DD HH:MM:SS';"
```

---

## 4.6 Remediation Tasks (Działania Naprawcze)

| # | Działanie | Właściciel | Priorytet | Termin | Status |
|---|-----------|------------|-----------|--------|--------|
| R-01 | Dodaj alert na rozmiar WAL > 1 GB | DevOps | P0 | +3 dni | TODO |
| R-02 | Obniż próg alertu disk z 95% → 80% | DevOps | P0 | +3 dni | TODO |
| R-03 | Dodaj `wal_autocheckpoint=1000` do konfiguracji SQLite | Dev | P0 | +1 dzień | TODO |
| R-04 | Napisz runbook dla "disk full" (ten dokument) | SRE | P1 | +5 dni | DONE |
| R-05 | Code review obowiązkowy dla zmian konfiguracji DB | Process | P1 | +7 dni | TODO |
| R-06 | Dodaj WAL size check do health endpoint `/health` | Dev | P1 | +7 dni | TODO |
| R-07 | Synchronizuj wolumen danych staging = prod (anonymized) | DevOps | P2 | +14 dni | TODO |
| R-08 | Automatyczny prune_audit_log jako cron (codziennie) | Dev | P2 | +14 dni | TODO |

### Szablon ticketu JIRA

```
Tytuł: [POST-MORTEM INC-YYYYMMDD] R-XX: [Opis działania]
Opis:
  Incydent: INC-YYYYMMDD-HHMMSS
  Priorytet: P0/P1/P2
  
  Działanie naprawcze:
  [Opis co należy zrobić]
  
  Definition of Done:
  - [ ] Implementacja
  - [ ] Testy (unit/integration)
  - [ ] Deploy na staging i weryfikacja
  - [ ] Deploy na produkcję
  - [ ] Alert lub monitoring zaktualizowany
  
  Link do post-mortem: [URL]
```

---

## 4.7 Learning Outcomes (Wnioski)

### Co Zadziałało Dobrze

1. [Co zadziałało — bądź konkretny]
2. [Co zadziałało]
3. [Co zadziałało]

**Przykład:**
1. PagerDuty alert wyzwolił się automatycznie — MTTR byłby dłuższy bez alertów
2. Incident Commander wyznaczony w ciągu 3 minut od alertu
3. Procedura backup DB przed interwencją zapobiegła utracie danych

### Co Można Poprawić

1. [Co można ulepszyć]
2. [Co można ulepszyć]
3. [Co można ulepszyć]

**Przykład:**
1. Brak runbooka dla disk full wydłużył diagnostykę o ~15 minut
2. Alert disk przy 95% — za mało czasu na reakcję zanim dysk się zapełnił
3. Komunikacja z użytkownikami była opóźniona o 12 minut

### Pytania Systemowe (5 Why)

```
DLACZEGO produkcja była niedostępna?
→ Bo dysk był pełny

DLACZEGO dysk był pełny?
→ Bo plik WAL urósł do 4.7 GB

DLACZEGO WAL urósł?
→ Bo checkpointing był wyłączony po deploymencie

DLACZEGO checkpointing był wyłączony?
→ Bo zmiana konfiguracji w v5.9.0 miała błąd (wal_autocheckpoint=0)

DLACZEGO błąd w konfiguracji trafił na produkcję?
→ Bo zmiana nie była objęta code review i nie było testu który to wykrywa
→ AKCJA: Dodaj obowiązkowy code review + test sprawdzający konfigurację SQLite
```

---

## 4.8 Metryki Post-mortem

| Metryka | Wartość |
|---------|---------|
| MTTD (wykrycie) | MM:SS |
| MTTI (identyfikacja root cause) | MM:SS |
| MTTR (recovery) | MM:SS |
| Całkowity czas incydentu | MM:SS |
| Liczba R.O. (remediation tasks) | X |
| P0/P1 R.O. zakończonych w terminie | X/Y (Z%) |
| Incydenty z tego samego root cause ostatnie 90 dni | X |

---

## 4.9 Podpisy i Zatwierdzenie

```
Incident Commander: _________________________ Data: ___________
Tech Lead:          _________________________ Data: ___________
SRE Lead:           _________________________ Data: ___________

Post-mortem zatwierdzony: TAK / NIE
Opublikowany w wiki/Notion: TAK / NIE (link: _______________)
```
```
