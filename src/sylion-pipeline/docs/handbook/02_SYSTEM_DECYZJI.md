# System Decyzyjny SYLION Pipeline v5.9.2

Ten dokument opisuje wszystkie mechanizmy decyzyjne pipeline — kto, kiedy i jak podejmuje decyzje o zastosowaniu zmian, eskalacji i blokowaniu.

---

## Spis tresci

- [Rada 4 modeli AI (Council)](#rada-4-modeli-ai-council)
- [System konsensusu](#system-konsensusu)
- [HumanGate PL](#humangate-pl)
- [Skill Checklist Enforcer](#skill-checklist-enforcer)
- [Debug Loop Breaker](#debug-loop-breaker)
- [Constraint List — decyzje sesji](#constraint-list--decyzje-sesji)
- [Pre-Deploy Council](#pre-deploy-council)
- [Matryca priorytetow](#matryca-priorytetow)
- [Fallback Matrix — modele zdegradowane](#fallback-matrix--modele-zdegradowane)
- [Escalation Flow](#escalation-flow)

---

## Rada 4 modeli AI (Council)

Rada 4 modeli to mechanizm rownolegly — cztery modele AI analizuja to samo zadanie jednoczesnie i oddaja niezalezne glosy. Zadne zadanie o wadze LARGE lub CRITICAL nie jest przetwarzane przez pojedynczy model.

### Kiedy aktywowana

Rada jest aktywowana automatycznie gdy spelnione jest co najmniej jedno z ponizszych kryteriow:

| Kryterium                          | Przyklad                                          |
|------------------------------------|---------------------------------------------------|
| Waga zadania: LARGE                | Zmiana wiecej niz 10 plikow                       |
| Waga zadania: CRITICAL             | Migracja DB, deploy, RODO, security audit          |
| Plik oznaczony jako security-sensitive | `dashboard/app.py`, `db.py`, `rollback.sh`    |
| Rozbieznosc modeli w poprzedniej iteracji | Jeden model PASS, inny FAIL              |
| Zadanie zawiera slowa kluczowe     | "unlock", "flash", "wipe", "deploy", "secret"     |
| Flaga security_sensitive_flag=True | Ustawiona recznie lub przez tier_routing           |

### Role modeli w radzie

| Model             | Rola w radzie               | Specjalizacja OWASP                    |
|-------------------|-----------------------------|----------------------------------------|
| Claude Opus 4.7   | Architect                   | A01 (Broken Access), A03 (Injection), A07 (Auth) |
| Claude Sonnet 4.6 | Code Quality                | A02 (Crypto), A04 (SSRF), A06 (Config) |
| GPT-5.4           | Legal-lite / Pragmatic ROI  | A03 (Injection), A08 (Integrity), A09 (Logging) |
| Gemini 3.1 Pro    | Cross-cutting / EU Compliance | A01 (Access), A08 (Integrity), A10 (SSRF) |

---

## System konsensusu

Po zebraniu glosow od wszystkich 4 modeli pipeline klasyfikuje wynik i podejmuje automatyczna lub eskalowana decyzje.

### Tabela konsensusu

| Wynik glosowania | Klasyfikacja       | Akcja pipeline                                               |
|------------------|--------------------|--------------------------------------------------------------|
| 4/4 PASS         | FULL_CONSENSUS     | Auto-apply (dla zadan non-security). Logowane do audit_log   |
| 4/4 PASS         | FULL_CONSENSUS_SEC | HumanGate CONFIRMATION dla zadan security-sensitive          |
| 3/4 PASS         | MAJORITY           | HumanGate — operator widzi rozbieznosc i model ktory odrzucil |
| 2/4 PASS         | SPLIT              | HumanGate ESCALATION — obowiazkowa odpowiedz operatora       |
| 1/4 lub 0/4 PASS | NO_GO              | Zadanie odrzucone. Raport rozbieznosci. Brak aplikowania zmian |

### Szczegoly glosowania

Kazdy model zwraca:
- `verdict`: PASS / FAIL / UNCERTAIN
- `confidence`: 0.0–1.0
- `findings`: lista szczegolowych uwag
- `blocking_issues`: lista blokujacych problemow (jesli FAIL)

Przy UNCERTAIN — model jest traktowany jako FAIL przy obliczaniu konsensusu, ale jego findings sa dolaczane do raportu.

### Waga zadania (klasyfikacja przed rada)

| Waga     | Kryteria                                                                  | Domyslny tier |
|----------|---------------------------------------------------------------------------|---------------|
| MICRO    | 1 plik, < 5 linii, brak implikacji security                               | Tier 0 (LOCAL) |
| SMALL    | 1-3 pliki, < 20 linii, brak security                                      | Tier 1 (CHEAP) |
| MEDIUM   | 3-10 plikow, srednia zlozonosc                                            | Tier 2 (STANDARD) |
| LARGE    | > 10 plikow lub duza zlozonosc lub wplyw na architekture                  | Tier 3 (PREMIUM) + Council |
| CRITICAL | Deploy, migracja DB, provisioning urzadzenia, RODO, secrets               | Tier 3 (PREMIUM) + Council + HumanGate |

---

## HumanGate PL

HumanGate to interaktywna bramka decyzyjna — punkt wstrzymania pipeline, w ktorym operator podejmuje decyzje. Pipeline NIE kontynuuje bez odpowiedzi.

### Format ASCII box (przyklad HumanGate)

```
+==============================================================+
| HUMANGATE #7                              [CRITICAL]         |
| ID: HG-2026041914-a3f2                                       |
|--------------------------------------------------------------|
| Pytanie:                                                     |
|   Rada 3/4 zatwierdzila migracje schematu DB v3->v4.         |
|   GPT-5.4 zglasza ryzyko: brak testu rollback na shadow DB.  |
|   Czy kontynuowac migracje?                                  |
|--------------------------------------------------------------|
| Kontekst:                                                    |
|   Plik: dashboard/db.py (migration_3_to_4)                   |
|   Shadow DB test: PASS (x5 idempotency, 10 threads)          |
|   GPT-5.4 finding: "rollback path not covered in CI"         |
|   Alternatywa: --integrity-check-only przed migracją         |
|--------------------------------------------------------------|
| Opcje:                                                       |
|   [A] Zatwierdz — kontynuuj migracje                         |
|   [B] Odrzuc — wstrzymaj, nie aplikuj                        |
|   [C] Zatwierdz z warunkiem — dodaj test rollback do CI      |
|--------------------------------------------------------------|
| Plan rollbacku:                                              |
|   bash rollback.sh --from-backup=backup_pre_migration.sqlite |
|--------------------------------------------------------------|
| Wygasa:  2026-04-19 14:30:00 UTC (za 30 min)                 |
+==============================================================+
```

### Pola HumanGate

| Pole         | Opis                                                                    |
|--------------|-------------------------------------------------------------------------|
| ID           | Unikalny identyfikator (format: HG-YYYYMMDDNN-xxxx)                     |
| Priority     | CRITICAL / HIGH / MEDIUM / LOW                                          |
| Type         | CONFIRMATION / ESCALATION / INFORMATION / BLOCKED                       |
| Pytanie      | Jasno sformulowane pytanie do operatora (max 3 zdania)                  |
| Kontekst     | Kluczowe informacje: plik, wyniki rady, finding blokujacy               |
| Opcje        | Min. 2, max. 4 opcje z literami [A]/[B]/[C]/[D]                        |
| Rollback     | Konkretna komenda lub krok do cofniecia zmiany                          |
| Expires      | Czas wygasniecia (domyslnie: 30 minut od wygenerowania)                 |

### Kiedy HumanGate jest wymagany

HumanGate jest bezwzglednie wymagany (nie mozna wylaczyc) przy:
- Wadze zadania CRITICAL (provisioning, deploy, migracja DB)
- Konsensusie 3/4 lub nizszym
- Wykryciu BLOCKING_ISSUE przez jakikolwiek model
- Operacjach destruktywnych (unlock, flash, wipe, purge)
- Przekroczeniu progu budzetowego (`BUDGET_WARNING_THRESHOLD`)
- Trybie DEGRADED_COUNCIL (mniej niz 3 aktywne modele)

### Timeout i EXPIRED

- Domyslny timeout: 30 minut
- Po wygasnieciu: status -> EXPIRED, pipeline -> PAUSED (nie ABORTED)
- Operator moze wznowic: `POST /api/humangate/{id}/restart`
- Brak odpowiedzi NIE jest traktowany jako zatwierdzenie

---

## Skill Checklist Enforcer

Skill Checklist Enforcer (SKE) wymusza kompletnosc deliverable na kazdym etapie. W v5.9.2 byl wywolany 68+ razy.

### 4 fazy SKE

#### PRE-TASK (przed rozpoczeciem etapu)

Sprawdza czy warunki wstepne sa spelnione:
- Czy poprzedni etap zakonczyl sie sukcesem?
- Czy wszystkie wymagane zmienne srodowiskowe sa ustawione?
- Czy workspace nie jest w stanie bledu?
- Czy HumanGate z poprzedniego etapu zostal odpowiedziany?

#### DURING-TASK (w trakcie etapu)

Monitoruje postep:
- Czy agenci zglosili postep w ostatnich N minutach?
- Czy Debug Loop Breaker nie wykryl petli?
- Czy budget nie zostal przekroczony?

#### POST-TASK (po zakonczeniu etapu)

Weryfikuje deliverable:

| Deliverable               | Czy wymagany       |
|---------------------------|--------------------|
| TOC wygenerowany          | Tak (dla doc etapow) |
| Indeks terminow obecny    | Tak (dla doc etapow) |
| Screenshot placeholdery   | Tak                |
| Readability Score > 60    | Tak (dla doc PL)   |
| Testy pytest PASS         | Tak (dla code etapow) |
| HumanGate odpowiedziany   | Tak (jesli byl wywolany) |
| ADR wygenerowane          | Tak (dla arch. decyzji) |

Brakujacy deliverable = twardy blok (pipeline nie przechodzi do nastepnego etapu).

#### RETROSPECTIVE (po calym pipeline)

Agregacja wynikow:
- Ile etapow zakonczylo sie sukcesem?
- Ile HumanGate zostalo odpowiedzianych vs wygaslych?
- Jakie deliverable sa brakujace w calosci?
- Cost per run?

---

## Debug Loop Breaker

Debug Loop Breaker (DLB) wykrywa i przerywa petli naprawcze — sytuacje gdy pipeline wielokrotnie proby naprawienia tego samego problemu bez efektu.

### 4 wzorce petli

| Wzorzec          | Definicja                                                                    |
|------------------|------------------------------------------------------------------------------|
| Same-Fix         | Identyczna propozycja naprawy pojawia sie 3 lub wiecej razy bez zmiany       |
| Variant-Fix      | Semantycznie podobne propozycje (> 0.85 similarity) 3+ razy                  |
| Regression-Bounce | Zmiana A naprawia problem, zmiana B cofа A, zmiana C naprawia ponownie — petla |
| Version-Inflation | Numer wersji rosnie bez istotnych zmian tresci (padding wersji)             |

### Akcja po wykryciu petli

1. Po 3 probach tego samego wzorca: pipeline zatrzymuje sie
2. Generowany jest raport DLB z historyczna lista prob
3. Wywolywany HumanGate z pytaniem: kontynuowac z innym podejsciem / abortowac / eskalowac do czlowieka
4. Operator moze wyspecyfikowac nowe ograniczenia (dodane do Constraint List)

### Konfiguracja

```yaml
# agents.yaml
loop_guard:
  max_same_fix: 3
  similarity_threshold: 0.85
  enabled: true
```

### ADR

- `docs/audits/LOOP_GUARD_v5.9.2.md` — raport audytowy loop guard
- `docs/adr/ADR-0025-v591-final-verification-loop.md`

---

## Constraint List — decyzje sesji

Constraint List to lista decyzji architektonicznych podjeta podczas sesji. Kazda decyzja ma ID i zapobiega ponownemu otwieraniu tego samego tematu.

### Format decyzji

```
C-NNN: [STATUS] Tresc decyzji — data — autor
```

### Przykladowe decyzje z sesji v5.9.2

| ID    | Status   | Tresc                                                                    |
|-------|----------|--------------------------------------------------------------------------|
| C-001 | ACCEPTED | workers=1 (SQLite single-process) — nie zmieniamy bez migracji na Postgres |
| C-002 | DEFERRED | F-001 (key rotation UI) — odroczone do v5.9.3 — dashboard/app.py L.812   |
| C-003 | ACCEPTED | Pixel 9 family jako jedyne wspierane urzadzenie (whitelist)               |
| C-004 | ACCEPTED | CSRF 71/71 — brak wyjtakow dla endpointow mutujacych                     |
| C-005 | ACCEPTED | Merge LATEST + SNAPSHOT jako baza dla v5.9.2                              |
| C-006 | ACCEPTED | DEVICE_HARNESS_DRY_RUN=true jako domyslny (bezpieczenstwo)               |
| C-007 | DEFERRED | WebRTC media plane — scope v5.10                                          |
| C-008 | REJECTED | Vault Secrets — SQLite secret=1 wystarczajace dla single-user deploy      |

---

## Pre-Deploy Council

Pre-Deploy Council to 18-punktowa kontrola przeprowadzana przez rade 4 modeli przed kazdym deployem w srodowisku produkcyjnym.

### 18 punktow kontrolnych

| Nr | Punkt                           | Kryteria sukcesu                                        |
|----|--------------------------------|---------------------------------------------------------|
| 1  | P0 blokers                     | 0 otwartych P0 blokujacych                             |
| 2  | Testy pytest                   | >= 95% PASS, 0 blokujacych FAIL                        |
| 3  | Linter (ruff)                  | 0 bledow, 0 warningow                                  |
| 4  | CSRF coverage                  | 71/71 mutujacych endpointow chronionych                |
| 5  | Secrets plain-text             | 0 sekretow w kodzie (skan regexowy)                    |
| 6  | CVE critical                   | 0 znanych CVE critical w zaleznoscia (pip-audit)       |
| 7  | DB integrity                   | PRAGMA integrity_check = ok                            |
| 8  | DB migrations                  | Wszystkie migracje idempotentne i przetestowane        |
| 9  | Rollback plan                  | rollback.sh przetestowany na shadow DB                 |
| 10 | DEVICE_HARNESS_DRY_RUN         | Swiadoma decyzja o trybie (true/false)                 |
| 11 | Health check v2                | /api/health/ready = 200 OK                             |
| 12 | Security headers               | HSTS, CSP, X-Frame-Options obecne                      |
| 13 | Rate limiter                   | Skonfigurowany i przetestowany                         |
| 14 | Retention policy               | Scheduler uruchomiony, retencja zgodna z RODO          |
| 15 | HumanGate pending              | Brak oczekujacych bramek                               |
| 16 | Budget guard                   | Budzet nie przekroczony, nie na granicy                |
| 17 | Backup                         | Swiezy backup bazy (max. 24h wiek)                     |
| 18 | ADR kompletne                  | Wszystkie decyzje architektoniczne udokumentowane      |

### Wynik Pre-Deploy Council

| Wynik              | Opis                                               | Akcja                        |
|--------------------|----------------------------------------------------|------------------------------|
| GO                 | Wszystkie 18 punktow zaliczone                     | Deploy moze ruszyc           |
| GO_WITH_WARNINGS   | 1-2 punkty z ostrzezeniami (nie blokerami)         | Deploy po swiadomej akceptacji |
| NO_GO              | Dowolny punkt blokujacy nie zaliczony              | Deploy zatrzymany, naprawa wymagana |

---

## Matryca priorytetow

Pipeline stosuje jednolita matryca priorytetow dla wszystkich zadan:

| Priorytet | Nazwa            | Czas odpowiedzi | Przyklady                                          |
|-----------|------------------|------------------|----------------------------------------------------|
| P0        | Bloker           | Natychmiast      | Crash, brak autoryzacji, data loss, security breach |
| P1 SEC    | Security         | < 24h            | CVE critical, OWASP finding HIGH+                  |
| P1 PERF   | Performance      | < 24h            | Latency > SLO, OOM, DB locks                       |
| P2 UX     | User experience  | < 1 tydzien      | Bledy UI, misleading messages, slow feedback        |
| P3        | Nice-to-have     | Backlog          | Refaktoryzacja kosmetyczna, dodatkowe testy, docs   |

W v5.9.2 zamknieto: 7/7 P0, 10/10 P1.

---

## Fallback Matrix — modele zdegradowane

Gdy czesc modeli AI jest niedostepna (brak kredytow, rate limit, API down), pipeline przechodzi w tryb DEGRADED_COUNCIL.

| Aktywne modele | Tryb              | Konsensus threshold | Akcja                                       |
|----------------|-------------------|-----------------------|---------------------------------------------|
| 4/4            | FULL_COUNCIL      | 3/4 (75%)            | Normalne dzialanie                          |
| 3/4            | PARTIAL_COUNCIL   | 2/3 (66%)            | Ostrzezenie w UI, logi                     |
| 2/4            | DEGRADED_COUNCIL  | 2/2 (100%)           | HumanGate o akceptacji trybu zdegradowanego |
| 1/4            | SINGLE_MODEL      | HumanGate wymagany   | Operator decyduje: wait / local-only / abort |
| 0/4 + Ollama   | LOCAL_ONLY        | N/A — lokalny model  | HumanGate BLOCKED — tylko Ollama local     |
| 0/4 + brak Ollama | BLOCKED        | N/A                  | Pipeline zatrzymany. HumanGate BLOCKED      |

### Powrot do FULL_COUNCIL

Budget Guard sprawdza dostepnosc modeli przy kazdym health check (co 60s). Gdy provider odpowiada poprawnie i ma dostepne kredyty — model wraca do puli automatycznie. Operator otrzymuje notyfikacje w UI.

---

## Escalation Flow

Diagram decyzyjny eskalacji problemu w pipeline:

```
Problem wykryty przez agenta
         |
         v
   Waga problemu?
   /              \
 LOW/MEDIUM      LARGE/CRITICAL
   |                    |
   v                    v
Auto-fix          Rada 4 modeli
(Tier 0-2)              |
                  Konsensus?
                  /         \
               4/4           <4/4
                |               |
           Non-security?    HumanGate
           /       \             |
         tak       nie     Operator odpowiada?
          |         |       /          \
     Auto-apply  HumanGate tak          nie (> 30min)
                CONFIRM      |               |
                         Zatwierdzone?   EXPIRED
                          /       \         |
                        tak       nie   Pipeline PAUSED
                         |         |        |
                     Apply     NO-GO    Restart mozliwy
                              (raport)
```

---

*Poprzednia sekcja: [01_ARCHITECTURE.md](./01_ARCHITECTURE.md)*
*Nastepna sekcja: [03_FUNKCJE.md](./03_FUNKCJE.md)*
