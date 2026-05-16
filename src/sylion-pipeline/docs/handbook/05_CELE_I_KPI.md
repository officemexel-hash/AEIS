# Cele i KPI — SYLION Pipeline v5.9.2

Ten dokument definiuje cele techniczne i biznesowe pipeline, kluczowe wskazniki wydajnosci (KPI), poziomy uslug (SLO) oraz bramki jakosci.

---

## Cele techniczne

### Bezpieczenstwo

| Cel                         | Wartosc docelowa | Stan w v5.9.2 | Metoda pomiaru                            |
|-----------------------------|------------------|---------------|-------------------------------------------|
| P0 blokerów otwartych       | 0                | 0/7 (DONE)    | Tracker P0 w SKILL_MANIFEST.md            |
| Secrets plain-text w kodzie | 0                | 0             | Skan regexowy w CI (`env_lint.py`)         |
| CSRF coverage               | 71/71            | 71/71 (DONE)  | `e2e-playwright-council` smoke tests       |
| CVE critical w zalezn.      | 0                | 0             | `pip-audit` w CI workflow                 |
| CVE high w zalezn.          | 0 na dzien deploy| 0             | `pip-audit` + Dependabot                  |
| Security headers            | Kompletne        | Kompletne     | OWASP ZAP scan / curl -I check            |
| Argon2id dla hasel          | Obowiazkowy      | Wdrozony      | Code review + test_password_hashing        |
| HSTS enforced (prod)        | max-age=31536000 | Skonfigurowany| `curl -I` na /api/health/live             |

### Jakosc kodu

| Cel                         | Wartosc docelowa | Stan w v5.9.2  |
|-----------------------------|------------------|----------------|
| Testy pytest — zielone      | >= 95%           | 150/154 = 97.4% |
| Testy pytest — FAIL         | 0                | 0/154          |
| Linter ruff — bledy         | 0                | 0              |
| Linter ruff — warningi      | 0                | 0              |
| Type hints coverage         | >= 80%           | ~85% (szacunek)|
| Funkcje > 50 linii (refactor)| < 5% modulu     | Monitorowane   |

### Architektura i infrastruktura

| Cel                         | Wartosc docelowa | Stan w v5.9.2  |
|-----------------------------|------------------|----------------|
| Workers (SQLite safety)     | WEB_CONCURRENCY=1| ENFORCED       |
| DB schema version           | v4               | v4             |
| Migracje idempotentne       | Tak              | Wdrozone (x5 test) |
| WAL mode                    | Aktywny          | PRAGMA WAL     |
| DEVICE_HARNESS_DRY_RUN default | true          | ENFORCED       |
| Rollback plan               | Przetestowany    | shadow DB test OK |

---

## Cele biznesowe

### Automatyzacja rozwoju SYLION Secure

Pipeline eliminuje recznie wykonywane czynnosci przy:

| Czynnosc                          | Czas recznie | Czas z pipeline | Oszczednosc |
|-----------------------------------|--------------|-----------------|-------------|
| Audyt bezpieczenstwa kodu         | 4-8h         | < 30 min        | 85%+        |
| Provisioning Pixel 9              | 2-3h         | < 45 min (real) | 70%+        |
| Konfiguracja Mudi + WireGuard     | 1-2h         | < 20 min        | 80%+        |
| Generowanie dokumentacji i ADR    | 1-2h         | < 10 min        | 85%+        |
| Review PR z raportem              | 30-60 min    | < 10 min        | 75%+        |

Cel ogolny: redukcja manual labor o ponad 80% przy zachowaniu jakosci audytu.

### Onboarding dewelopera

Nowy developer powinien byc w stanie:
1. Sklonowac repo i uruchomic pipeline — w < 10 minut (po `install.sh`)
2. Uruchomic pierwszy audyt codebase — w < 30 minut od startu
3. Zrozumiec wyniki rady modeli — w < 5 minut (raport HTML)

Cel: onboarding < 30 minut end-to-end.

### Redukcja kosztow LLM (FinOps)

| Metryka              | Przed tier routing | Po tier routing  | ROI      |
|----------------------|--------------------|------------------|----------|
| Koszt/mc/dev (full)  | $120-310           | $25-80           | 70-75%   |
| Koszt/mc/dev (target)| -                  | < $80            | -        |
| Odsetek lokalnych    | 0%                 | >= 60%           | -        |

---

## KPI

### Niezawodnosc pipeline

| KPI                          | Target    | Pomiar                               |
|------------------------------|-----------|--------------------------------------|
| MTTR (Mean Time to Recover)  | < 15 min  | Czas od alert -> pipeline restored    |
| HumanGate response time (p95)| < 5 min   | Czas od gate triggered -> answered   |
| Pipeline success rate        | > 95%     | Runs zakonczone sukces / wszystkie    |
| False positive rate (council)| < 10%     | FAIL reversed by operator / all FAIL  |

### Wydajnosc

| KPI                          | Target         | Pomiar                               |
|------------------------------|----------------|--------------------------------------|
| Dashboard response time (p95)| < 200 ms       | Prometheus histogram                  |
| API latency /health/live (p95)| < 50 ms       | Prometheus histogram                  |
| SQLite query time (p95)      | < 10 ms        | Custom SQLite pragma timing           |
| Audit run duration (medium)  | < 5 min        | `pipeline_runs` table `elapsed_s`     |
| Council vote collection      | < 60 s         | SSE event timestamps                  |

### Koszty

| KPI                          | Target         | Pomiar                               |
|------------------------------|----------------|--------------------------------------|
| Cost per run (average)       | < $2.00        | `cost_tracking` table avg per run    |
| Cost per run (max)           | < $5.00        | `cost_tracking` table max            |
| Daily budget utilization     | < 60% of limit | `/api/cost/budget`                    |
| Local Ollama utilization     | >= 60% of calls| `cost_tracking` / total calls         |

---

## SLO (Service Level Objectives)

### Dashboard (interfejs uzytkownika)

| SLO                    | Target  | Opis                                         |
|------------------------|---------|----------------------------------------------|
| Dostepnosc             | 99.5%   | Mierzone jako /api/health/live HTTP 200      |
| Okno niedostepnosci    | < 4h/mc | Planowane maintenance lub awaria              |
| Czas odtworzenia (RTO) | < 30 min| Czas od awarii do przywrocenia               |
| Punkt odtworzenia (RPO)| < 24h   | Maksymalny czas do poprzedniego backupu      |

### VPS Infrastructure

| SLO                    | Target  | Opis                                         |
|------------------------|---------|----------------------------------------------|
| Dostepnosc serwera     | 99.9%   | Uptime VPS (niezalezny od pipeline)          |
| WireGuard tunnel       | 99.5%   | Tunel aktywny (bez kill switch)              |

### Migracja bazy danych

| SLO                    | Target  | Opis                                         |
|------------------------|---------|----------------------------------------------|
| Zero-downtime migration| Wymagane| Migracje wykonywane bez zatrzymania serwisu  |
| Rollback time          | < 5 min | Czas od decision -> restored poprzednia DB   |

---

## Compliance

### RODO / DSGVO minimum

| Wymaganie               | Status        | Implementacja                         |
|-------------------------|---------------|---------------------------------------|
| Art. 5 — zasady przetwarzania | Spelnione | Logi bez danych osobowych             |
| Art. 17 — prawo do usuniecia | Wdrozone | `purge_soft_deleted_users` (30 dni)   |
| Art. 30 — rejestr czynnosci | Wdrozony  | `audit_log` table, retencja 90 dni    |
| Art. 32 — bezpieczenstwo  | Wdrozone    | Argon2id, HTTPS, CSRF, security headers |
| DSR SLA                  | 30 dni       | Dokumentacja w DPIA_v592.md           |

### Hardening Score

| Komponent              | Score    | Metoda oceny                         |
|------------------------|----------|--------------------------------------|
| Dashboard (OWASP)      | 9/10     | Security audit council (mega-audit)  |
| Pixel 9 (GrapheneOS)   | 9.5/10   | PIXEL_HARDENING_CHECKLIST.md         |
| WireGuard VPN          | 9/10     | wireguard-council audit              |
| Cel minimum            | >= 8/10  | Wszystkie komponenty                 |

---

## Quality Gates (bramki jakosci)

Bramki, ktore musza byc zaliczone przed kazdym deploy:

### Bramka 1 — Testy

- pytest: >= 95% PASS
- 0 testow FAIL (nie skipped)
- Regresje: brak nowych FAIL vs poprzednia wersja

### Bramka 2 — Security

- Obowiazkowa Rada 4 modeli dla zadan LARGE/CRITICAL
- 0 findings CRITICAL lub HIGH bez uzasadnienia
- pip-audit: 0 CVE critical, 0 CVE high

### Bramka 3 — Deploy Pre-Check

- Obowiazkowy Pre-Deploy Council (18 punktow)
- Wynik: GO lub GO_WITH_WARNINGS (nie NO_GO)
- Obowiazkowy Rollback Plan z przetestowanym rollback.sh

### Bramka 4 — HumanGate

- Brak oczekujacych, wygaslych lub odrzuconych HumanGate
- Kazde CRITICAL zadanie: obowiazkowe HumanGate

### Bramka 5 — Budget

- Dzienny budzet: < 80% zuzycia (nie na granicy)
- Miesieczny budzet: nie przekroczony

---

## Metryki operacyjne — zrodla danych

| Metryka                | Zrodlo danych                         | Endpoint / Plik               |
|------------------------|---------------------------------------|-------------------------------|
| Pipeline runs          | `pipeline_runs` table                 | `/api/pipeline/status/{id}`   |
| Council votes          | `event_stream` table                  | SSE `/api/pipeline/stream`    |
| HumanGate history      | `humangate_requests` table            | `/api/humangate/history`      |
| Cost tracking          | `cost_tracking` table                 | `/api/cost/budget`            |
| Health history         | `/api/health/history`                 | Grafana dashboard             |
| Audit log              | `audit_log` table                     | `/api/audit/`                 |
| Prometheus metrics     | `/metrics` endpoint                   | Grafana scrape                |
| Circuit breaker states | `/api/circuit-breakers`               | Grafana alert                 |

---

*Poprzednia sekcja: [04_PROMPTY.md](./04_PROMPTY.md)*
*Nastepna sekcja: [06_USER_MANUAL.md](./06_USER_MANUAL.md)*
