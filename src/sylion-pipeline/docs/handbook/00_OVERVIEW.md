# SYLION Pipeline v5.9.2 — Przeglad

| Pole            | Wartość                                               |
|-----------------|-------------------------------------------------------|
| Wersja          | 5.9.2 (Mega-Audit Patch)                              |
| Data wydania    | 2026-04-19                                            |
| Status          | Production-ready — P0 open: 0/7                       |
| Testy           | 150 passed / 4 skipped / 0 failed                     |
| Dokumentacja    | docs/handbook/ (ten plik i pliki powiązane)           |
| Kontakt         | support@sylion.example                                |

---

## Co to jest SYLION Pipeline

SYLION Pipeline to lokalny, zautomatyzowany system wspomagający bezpieczny rozwój oprogramowania dla ekosystemu SYLION Secure (Pixel 9 + GrapheneOS + Mudi GL-E750 + WireGuard VPN).

Jeden zdaniem: pipeline koordynuje Rade 4 modeli AI, bramki decyzyjne HumanGate i zestaw narzedzi do provisioningu urzadzen — tworzac w pelni audytowalny, tamper-resistant cykl wytwarzania i utrzymania systemu SYLION Secure.

### Cel biznesowy

SYLION Secure to produkt prywatnosci dla uzytkownikow wymagajacych maksymalnej ochrony danych (liderzy biznesowi, prawnicy, osoby narazone na inwigilacje). Pipeline eliminuje reczna prace przy:

- audycie bezpieczenstwa kodu (OWASP Top 10, CVE, dependency scanning),
- provisioningu urzadzen Pixel 9 (unlock, flash GrapheneOS, hardening 16 patchów),
- konfiguracji sieci VPN (Mudi + WireGuard + kill switch + DNS tunnel),
- generowaniu dokumentacji, release notes i ADR,
- weryfikacji halucynacji AI przed zastosowaniem kazdej zmiany.

Docelowe oszczednosci: redukcja manualnej pracy o ponad 80%, onboarding nowego dewelopera ponizej 30 minut.

---

## Diagram architektury (ASCII)

```
+------------------+
|   OPERATOR / DEV |
|  (przegladarka)  |
+--------+---------+
         |
         v
+------------------+     statyczne pliki
|  DASHBOARD UI    +-----> FastAPI /static (HTML/JS)
|  (port 8421)     |
|  dashboard/app.py|<----> SQLite DB (schema v4, WAL)
+--------+---------+
         |
         | REST / SSE / WebSocket
         v
+-------------------+
|   ORCHESTRATOR    |
|  orchestrator.py  |
|  5 faз:           |
|  prepare          |
|  council          |
|  consensus        |
|  humangate        |
|  apply            |
+--------+----------+
         |
         v
+-------------------+       +-----------------------------+
|    SUPERVISOR     |       |  RADA 4 MODELI AI (Council) |
|   supervisor.py   |<----->|  Opus 4.7   (Architect)     |
|  after_iteration()|       |  Sonnet 4.6 (Code Quality)  |
|  anti_halluc_hook |       |  GPT-5.4    (Legal-lite)    |
|  DbPollingHumanGate       |  Gemini 3.1 (Cross-cutting) |
+--------+----------+       +-----------------------------+
         |
    +----+----+
    |         |
    v         v
+-------+ +-----------+
|TOOLS  | | GUARDS    |
|       | |           |
| WG    | | Book      |
| Pixel | | Guardian  |
| Code  | |           |
| base  | | Phantom   |
|       | | v3        |
|       | |           |
|       | | Fact      |
|       | | Checker   |
|       | |           |
|       | | Hallucin. |
|       | | Guard     |
+-------+ +-----------+
         |
         v
+------------------+
|  HUMANGATE PL    |
|  (bramka decyz.) |
|  SQLite polling  |
|  SSE stream      |
+------------------+
```

Legenda:
- Tools: `wireguard_provision.py`, `pixel_provision.py`, `device_harness.py`, codebase upload/audit
- Guards: `book_guardian.py`, `file_verification.py`, `fact_checker.py`, `claim_provenance.py`
- HumanGate: interaktywny punkt zatrzymania pipeline — operator akceptuje lub odrzuca propozycje

---

## Filozofia systemu

### Rada 4 modeli AI

Zadna decyzja o wadze LARGE lub CRITICAL nie jest podejmowana przez jeden model. Cztery modele AI (Claude Opus 4.7, Claude Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro) pracuja rownolegle — kazda istotna propozycja przechodzi przez konsensus. Rozbieznosci miedzy modelami sa traktowane jako sygnal ryzyka, a nie blad.

### HumanGate PL

Operator zawsze ma ostatnie slowo przy zmianach o wadze CRITICAL lub przy braku konsensusu 4/4. HumanGate to okienko decyzyjne z formatem ASCII box — pojawia sie w UI i czeka na odpowiedz maksymalnie 30 minut. Brak odpowiedzi powoduje stan PAUSED, nie automatyczne zatwierdzenie.

### Skill Checklist Enforcer

Kazdy etap pipeline sprawdza liste obowiazkowych deliverable (PRE-TASK, DURING-TASK, POST-TASK, RETROSPECTIVE). Brakujacy deliverable twardym blokiem wstrzymuje dalsza prace. Sprawdzono 68+ razy w trakcie budowy v5.9.2.

### Debug Loop Breaker

Automatyczne wykrywanie petli naprawczych (Same-Fix, Variant-Fix, Regression-Bounce, Version-Inflation). Po 3 bezskutecznych probach pipeline zatrzymuje sie i eskaluje do HumanGate zamiast kontynuowac w kolko.

---

## Stack techniczny

| Komponent              | Technologia                                   |
|------------------------|-----------------------------------------------|
| Jezyk                  | Python 3.12                                   |
| Framework API          | FastAPI + Uvicorn                             |
| Baza danych            | SQLite (schema v4, tryb WAL, migracje v1->v4) |
| Reverse proxy          | Caddy (TLS automatyczny)                      |
| Orchestracja kontener. | Docker + docker-compose (opcjonalne)          |
| Init systemu           | systemd (unit: sylion-dashboard.service)      |
| Modele AI              | Anthropic, OpenAI, Google, Ollama (lokalny)   |
| Monitoring             | Prometheus + Grafana (4 dashboardy)           |
| CI/CD                  | GitHub Actions (ci.yml, docker.yml, security.yml) |
| Linter/formatter       | ruff (Python)                                 |
| Testy                  | pytest (150 passed w finalna weryfikacji)     |
| Hashowanie hasel       | Argon2id (argon2-cffi >= 23.1.0)              |
| Komunikacja asynchron. | SSE (Server-Sent Events) + polling SQLite     |

---

## Osoby uzywajace pipeline

| Rola      | Co robi w pipeline                                                         |
|-----------|----------------------------------------------------------------------------|
| Developer | Uploaduje codebase, uruchamia audyt, odczytuje raporty, merguje propozycje |
| Operator  | Zatwierdza HumanGate, provisionuje urzadzenia Pixel 9, zarzadza kluczami  |
| SRE       | Monitoruje health v2, Grafana, alerty Alertmanager, rollback               |
| Admin     | Zarzadza feature flags, budzetem LLM, kontami, backup/restore              |

---

## Co pipeline ROBI

- Audyt bezpieczenstwa kodu (OWASP Top 10, CVE, dependency scanning)
- Provisioning Pixel 9 (OEM unlock, flash GrapheneOS, hardening)
- Konfiguracja Mudi + WireGuard (kill switch, DNS tunnel, WPA3)
- Weryfikacja anty-halucynacyjna (5 warstw: FileVerification, BuildVerification, ClaimProvenance, SemanticDedup, FactChecker)
- Generowanie dokumentacji technicznej i release notes
- Monitoring kosztow LLM i tier routing (60%+ local Ollama, $120->$40/mc)
- Interaktywne bramki decyzyjne (HumanGate) dla operacji krytycznych
- Diagnostyka v2 (82 kody SYL-*) i health check z historycznym trendem

## Czego pipeline NIE robi (non-goals)

- Fakturowanie, KSeF, JPK, e-Rechnung, ksiegowosc — to zakres SYLION TAILOR (osobny produkt, odroczone do v5.11)
- Produkcyjny VoIP / WebRTC / media plane (odroczone do v5.10)
- OpenTelemetry (Prometheus+Grafana pokrywa observability dla obecnego zakresu)
- Vault Secrets Management (SQLite secret=1 wystarczajace dla single-user lokalnej instalacji)
- Obsluga urzadzen innych niz Pixel 9 family (Pixel 9, 9 Pro, 9 Pro XL, 9a, 9 Pro Fold)

---

## Wersje

| Wersja  | Glowna zmiana                                                       |
|---------|---------------------------------------------------------------------|
| v5.9.0  | Audyt 18 umiejetnosci, 52 subagentow x4 modele, 35 findings SEC    |
| v5.9.1  | Re-audyt 32 subagentow, workers=1 constraint (SQLite), 5 CRITICAL fix |
| v5.9.2  | Mega-audit (49+ subagentow, 185 folderow), 10 P0 zamknietych, WG impl., diagnostyka v2, CSRF 71/71 |

Pelne notes: [`RELEASE_NOTES_v5.9.2_PL.md`](../RELEASE_NOTES_v5.9.2_PL.md)

---

## Szybki start (5 minut)

```bash
git clone https://github.com/your-org/sylion-pipeline.git
cd sylion-pipeline
bash install.sh
# Uzupelnij .env (przynajmniej ANTHROPIC_API_KEY)
python dashboard/start.py
# Otworz http://localhost:8421
```

Pelna instrukcja: [`06_USER_MANUAL.md`](./06_USER_MANUAL.md)

---

*Kolejna sekcja: [01_ARCHITECTURE.md](./01_ARCHITECTURE.md) — pelna architektura modulow.*
