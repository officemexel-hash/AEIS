# SYLION Pipeline v5.9.2 — Handbook

Kompletna dokumentacja dla developera, operatora, SRE i admina. Kazdy plik jest samodzielny — mozesz czytac w dowolnej kolejnosci lub podazac za linkami po kolei.

| Pole          | Wartosc                               |
|---------------|---------------------------------------|
| Wersja        | 5.9.2 (Mega-Audit Patch)              |
| Data          | 2026-04-19                            |
| Scope         | SYLION Secure (Pixel 9 + GrapheneOS + Mudi + WireGuard) |
| Jezyk         | Polski                                |
| Kontakt       | support@sylion.example                |

---

## Indeks sekcji

### [00_OVERVIEW.md](./00_OVERVIEW.md) — Przeglad systemu
Co to jest SYLION Pipeline, cel biznesowy, filozofia (Rada 4 AI, HumanGate, Skill Enforcer, Debug Loop Breaker), stack techniczny, diagram ASCII architektury, role uzytkownikow, co pipeline robi i czego nie robi.

### [01_ARCHITECTURE.md](./01_ARCHITECTURE.md) — Architektura modulow
Pelny opis kazdego modulu: Orchestrator, Supervisor, Dashboard, Council 4AI, Tier Routing, Budget Guard, Book Guardian, Fact Checker, Hallucination Guard, Pixel Provision, WireGuard Provision, Router Provision, Device Harness, Circuit Breaker, Ollama Client, Retention, Feature Flags, CSRF, Rate Limiter, i18n, Database, Rollback. Dla kazdego: wejscie/wyjscie, zmienne srodowiskowe, ADR.

### [02_SYSTEM_DECYZJI.md](./02_SYSTEM_DECYZJI.md) — System decyzyjny
Rada 4 modeli AI, konsensus (4/4, 3/4, 2/4, NO-GO), HumanGate PL (format, pola, timeout), Skill Checklist Enforcer (4 fazy), Debug Loop Breaker (4 wzorce), Constraint List (C-001..C-008), Pre-Deploy Council (18 punktow), matryca priorytetow (P0..P3), fallback matrix, diagram eskalacji.

### [03_FUNKCJE.md](./03_FUNKCJE.md) — Funkcje uzytkownika
12 grup funkcji z endpointami, rolami, opisami, przykladami curl/Python i listami bledow: autoryzacja, upload codebase, uruchamianie audytu, SSE streaming, HumanGate interakcja, diagnostyka v2, Pixel 9 provisioning, Mudi provisioning, feature flags admin, budget tracking, backup/restore, rollback.

### [04_PROMPTY.md](./04_PROMPTY.md) — Katalog promptow
10 systemowych promptow pipeline: system prompty Rady 4 modeli (Opus/Sonnet/GPT/Gemini), prompt klasyfikacji wagi zadania, code review, security audit, generowanie testow, Book Guardian check, Fact Checker, Hallucination Detection, HumanGate PL formulation, meta-prompt Orchestratora.

### [05_CELE_I_KPI.md](./05_CELE_I_KPI.md) — Cele i KPI
Cele techniczne (bezpieczenstwo, jakosc, architektura), cele biznesowe (automatyzacja, FinOps), KPI (MTTR, HumanGate response, cost/run, Ollama utilization), SLO (uptime, zero-downtime migration), compliance (RODO minimum), quality gates (5 bramek).

### [06_USER_MANUAL.md](./06_USER_MANUAL.md) — Podrecznik uzytkownika [FLAGOWY]
15+ stron instrukcji krok po kroku: pierwsze uruchomienie, konfiguracja .env, dry-run/real-run Pixel 9, Mudi + WireGuard setup, pelny audyt codebase, feature flags, diagnostyka v2, Grafana monitoring, 12 typowych bledow A-L (utrata polaczenia, zdegradowana rada, rate limit, database locked, path traversal, HumanGate expired, migracja failed, ADB not found, WRONG_MODEL, kill switch, OOM, budget exceeded), backup + restore drill, upgrade, uninstall.

### [07_TROUBLESHOOTING_FLOWCHART.md](./07_TROUBLESHOOTING_FLOWCHART.md) — Diagramy decyzyjne
ASCII diagramy: pipeline nie dziala, problemy z baza danych, problemy z modelami AI, provisioning Pixel/Mudi, HumanGate nie odpowiada, budget exceeded, WireGuard kill switch, backup/rollback. Tabela szybkiego rozwiazywania 15 objawow.

### [08_FAQ.md](./08_FAQ.md) — Najczesciej zadawane pytania
30+ pytan i odpowiedzi: uzywanie pipeline offline, czas audytu, Windows/WSL2, HumanGate po obiedzie, wymagane porty, reset hasla, przechowywanie kodu, 5ty model w radzie, TAILOR vs Secure, koszty, bezpieczenstwo kluczy, HTTPS, Hallucination Guard, prompt injection, klucz SSH do Mudi, Pixel family, reset fabryczny Pixela, kill switch vs dashboard, compliance RODO, emergency stop.

### [09_GLOSSARY.md](./09_GLOSSARY.md) — Slowniczek
Definicje slow kluczowych: ADR, ADB, Argon2id, Book Guardian, Budget Guard, Circuit Breaker, Claim Provenance, Constraint List, CSRF, Dashboard, Debug Loop Breaker, DEGRADED_COUNCIL, Device Harness, Fact Checker, Fastboot, Feature Flags, FinOps, GoBD, GrapheneOS, HumanGate, HSTS, Kill Switch, Ksiega 3.4, KSeF (NIE w scope), Loop Guard, Mudi, MTTR, Ollama, OpenWrt, Orchestrator, Phantom v3, Pixel 9 Family, Pre-Deploy Council, Rada 4 Modeli, RODO, Rollback, SemanticDedup, Skill Checklist Enforcer, SLO, Supervisor, TAILOR (NIE w scope), Tier Routing, WAL, WireGuard.

### [10_CONTRIBUTING.md](./10_CONTRIBUTING.md) — Wklad w projekt
Styl kodu (ruff, type hints, docstrings), testy (pytest, fixture in-memory DB, konwencja nazewnicza), proces ADR (kiedy i jak), PR template (checklist), CI sprawdzenia (ci.yml, security.yml, docker.yml), konwencje commitow (Conventional Commits), zglaszanie bledow security.

### [screenshots/PLACEHOLDER_INSTRUCTIONS.md](./screenshots/PLACEHOLDER_INSTRUCTIONS.md) — Instrukcje screenshotow
Lista 40 oczekiwanych screenshotow (01_login_screen.png .. 40_uninstall_warning.png) z opisem kazdego, komendami curl do reprodukcji stanu, i wskazowkami gdzie kliknac w UI. ASCII diagramy zastepujace screenshoty tam gdzie to mozliwe.

---

## Szybkie linki

| Potrzeba                                | Gdzie szukac                              |
|-----------------------------------------|-------------------------------------------|
| Pierwsze uruchomienie (5 min)           | [06_USER_MANUAL.md #1](./06_USER_MANUAL.md) |
| Pipeline nie dziala                     | [07_TROUBLESHOOTING_FLOWCHART.md](./07_TROUBLESHOOTING_FLOWCHART.md) |
| Blad X — co zrobic                      | [06_USER_MANUAL.md #10 A-L](./06_USER_MANUAL.md) |
| Provisioning Pixel 9                    | [06_USER_MANUAL.md #3-4](./06_USER_MANUAL.md) |
| WireGuard + kill switch                 | [06_USER_MANUAL.md #5](./06_USER_MANUAL.md) |
| API endpointy i przyklady               | [03_FUNKCJE.md](./03_FUNKCJE.md) |
| Architektura modulu X                   | [01_ARCHITECTURE.md](./01_ARCHITECTURE.md) |
| Jak dziala konsensus rady               | [02_SYSTEM_DECYZJI.md](./02_SYSTEM_DECYZJI.md) |
| KPI i SLO                               | [05_CELE_I_KPI.md](./05_CELE_I_KPI.md) |
| Kontrybuowanie (PR, testy, ADR)         | [10_CONTRIBUTING.md](./10_CONTRIBUTING.md) |
| Slownik pojec                           | [09_GLOSSARY.md](./09_GLOSSARY.md) |
| FAQ                                     | [08_FAQ.md](./08_FAQ.md) |

---

## Status dokumentow

| Dokument                     | Linie | Status             |
|------------------------------|-------|--------------------|
| 00_OVERVIEW.md               | ~200  | Kompletny          |
| 01_ARCHITECTURE.md           | ~950  | Kompletny          |
| 02_SYSTEM_DECYZJI.md         | ~370  | Kompletny          |
| 03_FUNKCJE.md                | ~855  | Kompletny          |
| 04_PROMPTY.md                | ~685  | Kompletny          |
| 05_CELE_I_KPI.md             | ~215  | Kompletny          |
| 06_USER_MANUAL.md            | ~1270 | Kompletny (flagowy)|
| 07_TROUBLESHOOTING_FLOWCHART.md | ~275 | Kompletny        |
| 08_FAQ.md                    | ~370  | Kompletny          |
| 09_GLOSSARY.md               | ~215  | Kompletny          |
| 10_CONTRIBUTING.md           | ~430  | Kompletny          |
| README.md                    | ten plik | Kompletny       |
| screenshots/PLACEHOLDER_INSTRUCTIONS.md | ~200 | Kompletny |

---

*Wygenerowano: 2026-04-19 — SYLION v5.9.2 Handbook*
*Scope: SYLION Secure (Pixel 9 + GrapheneOS + Mudi + WireGuard). TAILOR poza scope.*
