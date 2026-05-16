# Slowniczek — SYLION Pipeline v5.9.2

Terminy techniczne i produktowe uzywane w dokumentacji pipeline. Termy sa posortowane alfabetycznie.

---

## A

**ADR (Architecture Decision Record)**
Dokument opisujacy decyzje architektoniczna: kontekst, podjeta decyzje, konsekwencje i uzasadnienie. Pipeline SYLION generuje ADR automatycznie dla wazniejszych zmian. Archiwum ADR: `docs/adr/ADR-0001` do `ADR-0035` (v5.9.2).

**ADB (Android Debug Bridge)**
Narzedzie linii polecen do komunikacji z urzadzeniami Android. Pipeline uzywa ADB do provisioningu Pixel 9 (weryfikacja modelu, flash, deploy agenta). Wymagane: `android-tools-adb` w PATH.

**Agents (Agenci)**
Wyspecjalizowane jednostki pracy AI w pipeline. Kazdy agent ma konkretna role (Coordinator, Auditor, Merger, Pixel Deployer itp.). Konfiguracja: `agents.yaml`. Lacznie 48 agentow aktywnych w v5.9.2.

**Argon2id**
Algorytm hashowania hasel — standard bezpieczenstwa 2026. Uzywany w SYLION do wszystkich hasel uzytkownikow. Zastepuje MD5, SHA1, bcrypt (przestarzale). Wymaga `argon2-cffi >= 23.1.0`.

---

## B

**Book Guardian**
Modul (`book_guardian.py`) weryfikujacy zgodnosc zmian kodu z Ksiega 3.4 — specyfikacja produktu SYLION Secure. Wykrywa dryft (odchylenie kodu od spec) wiekszy niz 5 linii w krytycznych sekcjach.

**Budget Guard**
Modul (`budget_guard.py`) monitorujacy koszty API modeli LLM. Wyzwala ostrzezenia przy 80% limitu i blokuje pipeline przy przekroczeniu limitu dziennego. Wspiera tryb DEGRADED_COUNCIL gdy czesc modeli traci dostep.

---

## C

**Circuit Breaker**
Wzorzec odpornosci (`circuit_breaker.py`) — chroni pipeline przed kaskadowymi awariami. Trzy stany: CLOSED (normalna praca), OPEN (fast-fail), HALF_OPEN (sonda). Per-provider dla Anthropic, OpenAI, Google, DeepSeek.

**Claim Provenance**
Modul (`claim_provenance.py`) — warstwa 3 systemu anty-halucynacyjnego. Weryfikuje ze kazde twierdzenie agenta AI ma pokrycie w kodzie zrodlowym (keyword matching w oknie 10 linii kontekstu).

**Constraint List**
Lista decyzji architektonicznych podjeta podczas sesji. Format: `C-NNN: STATUS Tresc — data`. Zapobiega ponownemu otwieraniu tych samych debat. Przykladowe: C-001 (workers=1), C-002 (UI key rotation DEFERRED), C-003 (Pixel 9 family only).

**CSRF (Cross-Site Request Forgery)**
Atak polegajacy na wykonaniu nieautoryzowanych dzialan w imieniu zalogowanego uzytkownika. Pipeline SYLION chroni 71/71 mutujacych endpointow przez token CSRF (X-CSRF-Token header, DB-backed, SameSite=Strict cookie). Patrz: ADR-0026.

---

## D

**Dashboard**
Interfejs webowy SYLION (`dashboard/app.py`, port 8421). Serwuje UI HTML i API REST/SSE dla pipeline. 71 endpointow, RBAC (role: guest/user/operator/admin).

**Debug Loop Breaker**
Mechanizm wykrywania i przerywania petli naprawczych. Cztery wzorce: Same-Fix, Variant-Fix, Regression-Bounce, Version-Inflation. Po 3 bezskutecznych probach — eskalacja do HumanGate.

**DEGRADED_COUNCIL**
Tryb pracy rady AI gdy mniej niz 4 modele sa aktywne. Prog konsensusu jest dostosowywany automatycznie (np. 2/3 zamiast 3/4). Wymaga HumanGate jesli aktywne mniej niz 3 modele.

**Device Harness**
Modul (`device_harness.py`) abstrahujacy dostep do fizycznych urzadzen (Pixel 9, Mudi). W trybie `DEVICE_HARNESS_DRY_RUN=true` (domyslny) — tylko loguje komendy bez ich wykonania.

**DPIA (Data Protection Impact Assessment)**
Ocena skutkow dla ochrony danych (RODO Art. 35). Dokument analizujacy ryzyko przetwarzania danych osobowych. Plik: `docs/DPIA_v591.md`.

---

## F

**Fact Checker**
Modul (`fact_checker.py`) — warstwa 5 anty-halucynacyjna. Niezalezny model LLM (domyslnie: claude-sonnet-4-6) weryfikuje kazde twierdzenie agentow przed zastosowaniem zmiany. Naprawiony w v5.9.2: ADR-0018.

**Fastboot**
Narzedzie Google do flashowania partycji Androida przez USB w trybie bootloadera. Pipeline uzywa fastboot podczas flash GrapheneOS na Pixel 9.

**Feature Flags**
Mechanizm runtime toggle — wlaczanie/wylaczanie funkcji bez restartu serwera. Przechowywane w tabeli `feature_flags` SQLite. Admin UI i API (`/api/config/flags`). Wazna flaga: `PIPELINE_EMERGENCY_STOP`.

**FinOps**
Praktyki optymalizacji kosztow infrastruktury chmurowej. W SYLION: Tier Routing redukuje koszty LLM API z $120-310/mc do $25-80/mc przez priorytetyzowanie lokalnego Ollama (60%+ zapytan).

---

## G

**GoBD**
Grundsätze zur ordnungsmäßigen Führung und Aufbewahrung von Büchern, Aufzeichnungen und Unterlagen in elektronischer Form. Niemieckie wymogi dot. retencji dokumentow ksiegowych. Istotne dla SYLION TAILOR (poza scope tego pipeline — patrz nizel).

**GrapheneOS**
Zhardenowany system Android z otwartym kodem zrodlowym, dedykowany urządzeniom Google Pixel. Oferuje rozszerzone uprawnienia, prywatnosc sieci, sandboxing aplikacji. SYLION Secure bazuje na GrapheneOS dla Pixel 9.

---

## H

**Hallucination Guard**
Warstwa 1 systemu anty-halucynacyjnego (`file_verification.py`). Wykrywa anomalie: SIZE_MISMATCH, CHECKSUM_FAIL, PHANTOM_FILE (plik nieistniejacy), GHOST_EDIT (brak zmiany pomimo twierdzenia agenta).

**HumanGate**
Interaktywna bramka decyzyjna pipeline. Punkt wstrzymania gdzie operator podejmuje decyzje o kontynuowaniu, modyfikacji lub odrzuceniu propozycji AI. Format ASCII box, timeout 30 minut, odpowiedz przez UI lub API. HumanGate PL = wersja po polsku.

**HSTS (HTTP Strict Transport Security)**
Naglowek HTTP wymuszajacy HTTPS dla kolejnych polaczen. Konfiguracja: `max-age=31536000; includeSubDomains`. Aktywny w SYLION w trybie produkcyjnym (Caddy + TLS).

---

## K

**Kill Switch**
Mechanizm blokowania calego ruchu sieciowego gdy tunel WireGuard straci polaczenie (`scripts/kill_switch.sh`). Reguly iptables: OUTPUT DROP poza interfejsem wg0. Aktywacja automatyczna, dezaktywacja wymaga swiadomej decyzji (HumanGate).

**Ksiega 3.4**
Specyfikacja produktu SYLION Secure — dokumentuje wymagania funkcjonalne i bezpieczenstwa dla ekosystemu Pixel 9 + GrapheneOS + Mudi + WireGuard. Book Guardian weryfikuje zgodnosc kodu z Ksiega.

**KSeF**
Krajowy System e-Faktur — polski system wymiany faktur elektronicznych. NIE dotyczy SYLION Pipeline / SYLION Secure. KSeF jest zakresem produktu SYLION TAILOR (odroczone do v5.11). Jesli szukasz KSeF — ten pipeline nie jest odpowiednim miejscem.

---

## L

**Loop Guard**
Komponent (`loop_guard.py`) implementujacy logike Debug Loop Breakera. Sledzi historie prob naprawy i wykrywa wzorce petli: Same-Fix, Variant-Fix, Regression-Bounce, Version-Inflation.

---

## M

**Mudi**
Router GL.iNet Mudi GL-E750 z systemem OpenWrt. Uzywany w SYLION Secure jako prywatny hotspot z WireGuard VPN i kill switch. Provisioning: `wireguard_provision.py` + SSH + uci.

**MTTR (Mean Time to Recover)**
Sredni czas do przywrocenia systemu po awarii. KPI: MTTR < 15 minut dla SYLION Pipeline.

---

## O

**Ollama**
Platforma do uruchamiania modeli LLM lokalnie na CPU/GPU bez kosztow API. Uzywany przez SYLION jako Tier 0 (LOCAL) i fallback gdy cloud providers sa niedostepni. Modele: llama3.1:8b, deepseek-coder:6.7b, qwen2.5-coder:14b.

**OpenWrt**
Otwarty system operacyjny dla routerow oparty na Linuxie. System na routerze Mudi GL-E750. Umozliwia konfiguracje WireGuard, WiFi i kill switch przez SSH i uci.

**Orchestrator**
Centralny koordynator pipeline (`orchestrator.py`). Uruchamia 5-fazowy workflow: prepare → council → consensus → humangate → apply. Zarzadza zywotem agentow i deleguje zadania przez AgentManager.

---

## P

**Phantom v3**
System wykrywania halucynacji AI (warstwa 1-4) — oryginalnie nazwany od `phantom-council`. Obejmuje: FileVerificationLayer, BuildVerification, ClaimProvenance, SemanticDedup. Warstwa 5 to Fact Checker.

**PIXEL_9_FAMILY**
Lista wspieranych modeli urzadzen: Pixel 9, Pixel 9 Pro, Pixel 9 Pro XL, Pixel 9a, Pixel 9 Pro Fold. Urzadzenia poza lista sa odrzucane przez pipeline (blad WRONG_MODEL). ADR-0015.

**Pre-Deploy Council**
18-punktowa kontrola wykonywana przez rade 4 modeli przed kazda operacja deploy w produkcji. Wynik: GO / GO_WITH_WARNINGS / NO_GO.

---

## R

**Rada 4 Modeli AI (Council)**
Cztery modele AI analizujace to samo zadanie jednoczesnie: Claude Opus 4.7 (Architect), Claude Sonnet 4.6 (Code Quality), GPT-5.4 (Legal-lite), Gemini 3.1 Pro (Cross-cutting). Decyzje konsensusu: 4/4, 3/4, 2/4, <2/4.

**RODO**
Rozporzadzenie Ogolne o Ochronie Danych — polska implementacja unijnego GDPR. SYLION Pipeline implementuje minimum RODO: logi bez danych osobowych, retencja, DSR, rejestr czynnosci.

**Retention Cleaner**
Modul (`dashboard/retention_cleaner.py`) usuwajacy stare dane zgodnie z polityka RODO i GoBD. Uruchamiany co 24h przez retention_scheduler.

**Rollback**
Przywrocenie poprzedniego stanu systemu po nieudanej zmianie. Pipeline SYLION: `rollback.sh` (394 linie, WAL-safe, flock). Automatyczny rollback bazy przy nieudanej migracji.

---

## S

**SemanticDedup**
Modul (`semantic_dedup.py`) — warstwa 4 anty-halucynacyjna. Usuwa semantyczne duplikaty findingsow (jesli dwa findings maja cosine similarity > 0.75 — tylko jeden jest zachowany).

**Skill Checklist Enforcer**
Mechanizm wymuszajacy kompletnosc deliverable na kazdym etapie pipeline (PRE-TASK, DURING-TASK, POST-TASK, RETROSPECTIVE). Brakujacy deliverable = twardy blok etapu.

**SLO (Service Level Objective)**
Cel poziomu uslugi — liczbowy target dla metryki. SYLION: uptime 99.5% dashboard, 99.9% VPS, zero-downtime migration.

**Supervisor**
Modul (`supervisor.py`) nadzorujacy iteracje pipeline. Implementuje after_iteration() hook, anti_halluc_hook, DbPollingHumanGate. Egzekwuje HumanGate i zapobiega petlom.

---

## T

**TAILOR (SYLION TAILOR)**
Osobny produkt firmy SYLION — system zarzadzania dla zakladow krawieckich. Zawiera: KSeF, JPK, e-Rechnung, faktury, GoBD. NIE jest czescia SYLION Pipeline ani SYLION Secure. Scope v5.11+. Pliki TAILOR zostaly zarchiwizowane w `docs/archived/tailor_deferred/`.

**Tier Routing**
Modul (`tier_routing.py`) klasyfikujacy zadania do 4 poziomow kosztowych: Tier 0 (LOCAL/Ollama), Tier 1 (CHEAP/mini), Tier 2 (STANDARD), Tier 3 (PREMIUM/full council). Redukcja kosztow LLM o 70-75%.

---

## W

**WAL (Write-Ahead Logging)**
Tryb dziennika SQLite zapewniajacy lepsza wspolbieznosc odczytow. SYLION: `PRAGMA journal_mode = WAL`. Wymaga WAL-safe procedur backup (checkpoint przed kopiowaniem).

**WireGuard**
Nowoczesny, lekki protokol VPN. Uzywany w SYLION Secure jako szyfrowany tunel miedzy Pixelem 9 / Mudi a serwerem VPN. Konfiguracja: `wireguard_provision.py`, klucze generowane na routerze.

---

*Poprzednia sekcja: [08_FAQ.md](./08_FAQ.md)*
*Nastepna sekcja: [10_CONTRIBUTING.md](./10_CONTRIBUTING.md)*
