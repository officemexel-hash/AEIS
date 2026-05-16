# Architektura SYLION Pipeline v5.9.2

Ten dokument opisuje kazdy modul pipeline — jego role, wejscia, wyjscia, konfiguracje i powiazane ADR.

---

## Spis tresci

- [Orchestrator](#orchestrator)
- [Supervisor](#supervisor)
- [Dashboard](#dashboard)
- [Agenci i Rada 4 modeli](#agenci-i-rada-4-modeli)
- [Tier Routing](#tier-routing)
- [Budget Guard](#budget-guard)
- [Book Guardian](#book-guardian)
- [Fact Checker i Claim Provenance](#fact-checker-i-claim-provenance)
- [Hallucination Guard](#hallucination-guard)
- [Pixel Provision](#pixel-provision)
- [WireGuard Provision](#wireguard-provision)
- [Router Provision](#router-provision)
- [Device Harness](#device-harness)
- [Circuit Breaker](#circuit-breaker)
- [Ollama Client](#ollama-client)
- [Retention](#retention)
- [Feature Flags](#feature-flags)
- [Correlation ID](#correlation-id)
- [Security Headers Middleware](#security-headers-middleware)
- [CSRF Middleware](#csrf-middleware)
- [Rate Limiter](#rate-limiter)
- [i18n Middleware](#i18n-middleware)
- [Database](#database)
- [Rollback](#rollback)
- [Powiazania miedzy modulami](#powiazania-miedzy-modulami)

---

## Orchestrator

**Plik:** `../../orchestrator.py`

Orchestrator jest centralnym koordynatorem pipeline. Uruchamia 5-fazowy workflow dla kazdego zadania — od przygotowania kontekstu, przez rade modeli, po aplikowanie wynikow.

### 5 faz workflow

| Faza               | Opis                                                                         |
|--------------------|------------------------------------------------------------------------------|
| stage_1_prepare    | Wczytuje workspace, Ksiege 3.4, inicjuje AgentManager, laduje konfiguracje   |
| stage_2_council    | Uruchamia rownolegla rade 4 modeli AI z klasyfikacja wagi zadania            |
| stage_3_consensus  | Zbiera glosy, liczy konsensus, klasyfikuje wynik (4/4, 3/4, 2/4, <2)        |
| stage_4_humangate  | Przy braku pelnego konsensusu lub wadze CRITICAL — wywoluje HumanGate PL    |
| stage_5_apply      | Po zatwierdzeniu (auto lub przez operatora) aplikuje zmiany w codebase       |

### Wejscie

- Workspace path (`--workspace`)
- Ksiega 3.4 PDF (`--ksiega`)
- Konfiguracja agentow (`agents.yaml`)
- Zmienne srodowiskowe z `.env`

### Wyjscie

- Raporty JSON per iteracja w `results/`
- Diff patchow do zastosowania
- Logi pipeline z X-Correlation-Id

### Kluczowe zmienne srodowiskowe

```ini
CONSENSUS_THRESHOLD=3        # min modeli do akceptacji (domyslnie: 3)
MAX_AGENT_STEPS=50           # max krokow agenta na etap
RESULTS_DIR=./results        # katalog wynikow
MEMORY_DIR=./memory          # katalog pamieci agentow
VERIFY_COUNT=3               # ile modeli weryfikuje kazdy wynik
MIN_AGREEMENT=0.66           # minimalna zgodnosc weryfikatorow
```

### Zaleznosci

- `supervisor.py` — nadzor iteracji i HumanGate
- `agent_manager.py` — zarzadzanie zywotem agentow
- `budget_guard.py` — kontrola budzetow LLM
- `book_guardian.py` — integracja Ksiega 3.4
- `fact_checker.py`, `file_verification.py`, `claim_provenance.py` — warstwy anti-hallucination
- `tier_routing.py` — klasyfikacja kosztu zadania

### ADR

- `docs/adr/ADR-0028-run-codebase-audit-orchestrator.md` — implementacja `run_codebase_audit()`
- `docs/adr/ADR-0035-release-v5.9.2.md` — zakres zmian merge

---

## Supervisor

**Plik:** `supervisor.py` (importowany przez orchestrator)

Supervisor nadzoruje przebieg iteracji pipeline. Zapobiega petlom, egzekwuje HumanGate i uruchamia hooki po kazdej iteracji.

### Glowne komponenty

- `SupervisorAgent` — klasa nadzorujaca iteracje, przechowuje stan
- `after_iteration()` — hook wywolywany po kazdej iteracji: sprawdza deliverable, loguje postep, aktualizuje Ksiege
- `anti_halluc_hook` — hook sprawdzajacy wyniki kazdego agenta przez Hallucination Guard
- `DbPollingHumanGate` — polling SQLite co 2 sekundy w oczekiwaniu na odpowiedz operatora
- `DeterministicRunner` — uruchamia agentow w deterministycznej kolejnosci (nie rownoleglosc przy krytycznych krokach)
- `GateLevel`, `GateDecision`, `GateRequest` — modele danych dla systemu bramek

### Wejscie

- Wyniki iteracji agentow (JSON)
- Stan HumanGate z bazy danych

### Wyjscie

- Decyzja GO/NO-GO per iteracja
- Log zdarzen do tabeli `event_stream`
- Powiadomienia SSE do dashboard

### Kluczowe zmienne srodowiskowe

```ini
CB_FAILURE_THRESHOLD=5      # prog bledow Circuit Breakera
CB_RESET_TIMEOUT_S=30.0     # czas powrotu do CLOSED po OPEN
```

### ADR

- `docs/adr/ADR-0025-v591-final-verification-loop.md` — workers=1 constraint, single-process SQLite

---

## Dashboard

**Plik:** `../../dashboard/app.py`

Dashboard to aplikacja FastAPI serwujaca UI (HTML/JS/CSS) i REST API pipeline. Dziala na porcie 8421 (konfigurowalny przez `DASHBOARD_PORT`).

### Glowne cechy

- 71 endpointow REST, wszystkie chronione CSRF (pokrycie 71/71 po patchu ADR-0026)
- Autentykacja sesyjna (cookie HttpOnly, SameSite=Strict)
- SSE streaming iteracji pipeline (`/api/pipeline/stream`)
- Interfejs HumanGate (`/api/humangate/*`)
- Health check v2 (`/api/health/live`, `/api/health/ready`, `/api/health/detailed`)
- Feature flags admin UI
- Pipeline runner (`POST /api/pipeline/run`)
- Cost tracker (koszty per run, per model)
- i18n (PL/DE/EN przez naglowek `Accept-Language`)

### Struktura endpointow (grupy)

| Grupa             | Prefiks              | Liczba endpointow |
|-------------------|----------------------|-------------------|
| Auth              | `/api/auth/`         | 6                 |
| Pipeline          | `/api/pipeline/`     | 8                 |
| HumanGate         | `/api/humangate/`    | 5                 |
| Health            | `/api/health/`       | 4                 |
| Devices           | `/api/devices/`      | 7                 |
| Feature Flags     | `/api/config/flags/` | 4                 |
| Cost / Budget     | `/api/cost/`         | 3                 |
| Backup            | `/api/backup/`       | 3                 |
| Audit Log         | `/api/audit/`        | 3                 |
| i18n              | `/api/i18n/`         | 2                 |
| Circuit Breakers  | `/api/circuit-breakers/` | 1             |
| Misc (static, metrics, codebase) | rozne | 25            |

### Wejscie

- Zadania HTTP od operatora/dewelopera
- Pliki ZIP / Git URL (upload codebase)
- Odpowiedzi na HumanGate (POST z decyzja)

### Wyjscie

- JSON API responses
- SSE stream (iteracje, logi)
- Pliki statyczne (HTML dashboard)
- Raporty ZIP do pobrania

### Kluczowe zmienne srodowiskowe

```ini
DASHBOARD_PORT=8421
DASHBOARD_HOST=127.0.0.1
WEB_CONCURRENCY=1           # KRYTYCZNE: SQLite wymaga single-process (ADR-0025)
SESSION_COOKIE_SECURE=1
SYLION_INTERNAL_API_KEY=    # klucz wewn. orchestrator <-> dashboard
SYLION_HEALTH_CHECK_V2=true
```

### ADR

- `docs/adr/ADR-0026-csrf-full-coverage.md` — CSRF 71/71
- `docs/adr/ADR-0029-diagnostics-v2-syl-codes.md` — health v2
- `docs/adr/ADR-0008-dashboard-query-consolidation.md` — query optimization

---

## Agenci i Rada 4 modeli

**Pliki:** `agents.yaml`, `agents/definitions.py`, `agents/sdr_agents.py`

Agenci to wyspecjalizowane jednostki pracy, kazda odpowiedzialna za konkretny etap pipeline. Konfiguracja wszystkich agentow zyje w `agents.yaml`.

### Rada 4 modeli AI (Council)

Pipeline dziala w trybie rady — kazda decyzja o wadze LARGE lub CRITICAL jest konsultowana z czterema modelami jednoczesnie:

| Model         | Identyfikator              | Rola w radzie          | Tier           |
|---------------|----------------------------|------------------------|----------------|
| Claude Opus 4.7  | claude-opus-4-7         | Architect, RODO, security OWASP A01/A03/A07 | PREMIUM |
| Claude Sonnet 4.6 | claude-sonnet-4-6      | Code quality, implementacja, OWASP A02/A04/A06 | STANDARD |
| GPT-5.4        | gpt-5-4                  | Legal PL+DE, ROI, OWASP A03/A08/A09 | PREMIUM |
| Gemini 3.1 Pro | gemini-3-1-pro            | EU compliance, cross-border, OWASP A01/A08/A10 | STANDARD |

### Hierarchia agentow

```
Coordinator          — glowny agent; przydziela zadania, zbiera wyniki
   Ksiega Analyst    — analizuje Ksiege 3.4 (specyfikacja produktu)
   Auditors (x5)     — audyt kodu: security, quality, perf, deps, tests
   Cross Verifiers (x4) — krzyzowa weryfikacja wynikow audytu
   Merger            — scala potwierdzone zmiany
   Patch Agents (x4) — aplikuja patche w codebase
   Pixel Deployer    — provision Pixel 9
   Router Deployer   — provision Mudi/WG
   Test Agents (x4)  — generowanie i uruchamianie testow
   Red Team (x4)     — symulacja atakow (security testing)
   Blue Team (x4)    — ochrona i hardening
   SDR Agents (x3)   — monitorowanie SDR / RF (opcjonalne)
   Reporter          — generowanie raportu koncowego
   Build Agent       — weryfikacja buildu po kazdym patchu
```

### Konfiguracja `agents.yaml` (kluczowe parametry)

```yaml
global:
  consensus_threshold: 3      # N/4 modeli = ACCEPT
  default_models:
    primary: claude-sonnet    # wiekszosc zadan
    critical: claude-opus     # decyzje krytyczne
    fast: claude-haiku        # walidacja, formatowanie
    reasoning: o3             # gleboka analiza security
    search: perplexity-sonar-pro  # CVE, advisories
  verification:
    enabled: true
    min_agreement: 0.66       # minimum 2/3
    verify_count: 3           # ile modeli weryfikuje
```

### ADR

- `docs/adr/ADR-0001-seed-agents-guard.md` — inicjalizacja agentow przy starcie
- `docs/adr/ADR-0023-agent-id-reset.md` — reset ID agentow po restart

---

## Tier Routing

**Plik:** `../../tier_routing.py`

Tier Routing klasyfikuje zadania do jednego z 4 poziomow kosztowych, eliminujac zaleznosc od full-council przy kazdym zadaniu. Cel: 60%+ zapytan obsluzyc lokalnie przez Ollama, redukcja kosztow z $120 do $40/mc.

### 4 tiery

| Tier   | Nazwa    | Modele                                          | Kiedy                                      |
|--------|----------|-------------------------------------------------|--------------------------------------------|
| Tier 0 | LOCAL    | Ollama local (deepseek-coder, qwen2.5-coder)    | Triaging, smoketesty, ruff-fix, proste doc |
| Tier 1 | CHEAP    | gpt-5-4-mini, gemini-2.0-flash                  | Code review, testy, dokumentacja           |
| Tier 2 | STANDARD | claude-sonnet-4-6, gpt-5-4                      | Feature dev, refactor, bugfix              |
| Tier 3 | PREMIUM  | Full council (Opus + Sonnet + GPT-5.4 + Gemini) | Security audit, RODO, deploy NO-GO, DB migration |

### Wejscie

```python
from tier_routing import select_tier, Tier
tier = select_tier(
    task_description="fix CSRF in login endpoint",
    files_changed=["dashboard/app.py"],
    security_sensitive_flag=True
)
```

### Wyjscie

- Obiekt `Tier` (enum IntEnum: 0-3)
- Lista model_id dla danego tieru

### Logika klasyfikacji

1. Jesli `security_sensitive_flag=True` → Tier 3 (PREMIUM)
2. Jesli zadanie zawiera slowa kluczowe (deploy, migration, RODO, OWASP) → Tier 3
3. Jesli liczba zmienionych plikow > 10 → min. Tier 2
4. Jesli zadanie zawiera slowa (refactor, feature, bugfix) → Tier 2
5. Jesli zadanie zawiera slowa (test, doc, format, lint) → Tier 1
6. W pozostalych przypadkach → Tier 0 (LOCAL)

### ADR

- `docs/adr/ADR-0035-release-v5.9.2.md` — FinOps baseline i uzasadnienie tier routing

---

## Budget Guard

**Plik:** `../../budget_guard.py`

Budget Guard monitoruje koszt API LLM w czasie rzeczywistym i blokuje pipeline gdy zostanie przekroczony dzienny lub miesieczny limit.

### Mechanizm

- Sledzi zuzycie (tokeny x cena) per model, per run
- Przy progu `BUDGET_WARNING_THRESHOLD` (domyslnie 80%) wyswietla ostrzezenie w UI
- Przy przekroczeniu `MAX_COST_USD_PER_DAY` (domyslnie $50) — kill-switch: blokuje nowe requesty do modeli cloud, wymusza fallback na Ollama lokalny
- Wykrywa `CREDITS_EXHAUSTED` per provider i usuwa model z puli rady
- W trybie `DEGRADED_COUNCIL` (mniej niz 4 modele) zmienia prog konsensusu

### Wejscie

- Metryki zuzycia z `cost_tracker.py` (tokeny, cena per model)
- Konfiguracja limitu z `.env`

### Wyjscie

- Status `NORMAL` / `WARNING` / `EXCEEDED` / `DEGRADED_COUNCIL`
- Zmieniony zbior aktywnych modeli
- Zdarzenie do `audit_log` i SSE stream

### Kluczowe zmienne srodowiskowe

```ini
MAX_COST_USD_PER_DAY=50.0
BUDGET_WARNING_THRESHOLD=0.80
```

### ADR

- `docs/audits/BUDGET_GUARD_v5.9.2.md` — pelen raport audytowy

---

## Book Guardian

**Plik:** `../../book_guardian.py`

Book Guardian weryfikuje zgodnosc kodu z Ksiega 3.4 — specyfikacja produktu SYLION Secure. Wykrywa dryfty (odchylenia kodu od spec) wieksze niz 5 linii.

### Mechanizm

- Wczytuje Ksiege 3.4 PDF i indeksuje kluczowe sekcje
- Po kazdej iteracji porownuje zmiany w codebase z wymaganiami Ksiegi
- Jesli drift > 5 linii w krytycznej sekcji → blokuje stage_5_apply i wywoluje HumanGate z pytaniem o uzasadnienie
- Procedura WAL checkpoint przed kazdym porownaniem (integralnosc danych)

### Wejscie

- Ksiega 3.4 (PDF path z `--ksiega`)
- Diff zmian po iteracji agentow

### Wyjscie

- `BookGuardianResult`: PASS / DRIFT_DETECTED / CRITICAL_DRIFT
- Lista sekcji ze stwierdzonym dryftem
- Propozycja uzasadnienia lub odrzucenia

### ADR

- `docs/adr/ADR-0034-ksef-e-rechnung.md` — nie dotyczy (ten ADR dotyczy zakresu TAILOR); patrz `docs/KSIEGA_3.4.md`

---

## Fact Checker i Claim Provenance

**Pliki:** `../../fact_checker.py`, `../../claim_provenance.py`

Warstwa 5 systemu anty-halucynacyjnego. Niezalezny model LLM weryfikuje kazde twierdzenie agentow przed zastosowaniem zmiany.

### Fact Checker

- `FactCheckerAgent` — odpytuje niezalezny model (domyslnie `anthropic/claude-sonnet-4-6`)
- Sprawdza `FactCheckItem` (twierdzenie + kontekst) → `FactCheckVerdict` (PASS/FAIL/UNCERTAIN)
- Agreguje wyniki do `FactCheckReport` per run
- Przy FAIL lub UNCERTAIN → blokuje stage_5_apply

### Claim Provenance

- `ClaimProvenance` — sprawdza czy kazde twierdzenie agenta ma pokrycie w kodzie zrodlowym
- Wyszukuje slowa kluczowe w oknie kontekstu (`PROVENANCE_CONTEXT_WINDOW=10` linii)
- Przy minimalnym ratio dopasowania ponizej `PROVENANCE_MIN_MATCH_RATIO=0.3` → SUSPECT

### Kluczowe zmienne srodowiskowe

```ini
FACT_CHECKER_MODEL_ID=anthropic/claude-sonnet-4-6
FACT_CHECKER_ENABLED=true
FACT_CHECKER_MAX_ITEMS=50
FACT_CHECKER_CONTEXT_LINES=20
CLAIM_PROVENANCE_ENABLED=true
PROVENANCE_CONTEXT_WINDOW=10
PROVENANCE_MIN_MATCH_RATIO=0.3
```

### ADR

- `docs/adr/ADR-0018-fact-checker-model-id.md` — naprawa ID modelu (P0 bloker v5.9.1)
- `docs/audits/FACT_CHECKER_v5.9.2.md` — raport audytowy

---

## Hallucination Guard

**Plik:** `../../file_verification.py`

Warstwa 1 systemu anty-halucynacyjnego — sprawdza integralnosc plikow po kazdej iteracji agenta.

### Mechanizm

- `FileVerificationLayer` — oblicza SHA-256 kazdego pliku przed i po iteracji
- `HallucinationGuard` — wykrywa anomalie:
  - `SIZE_MISMATCH` — plik zmienil rozmiar o wiecej niz oczekiwano
  - `CHECKSUM_FAIL` — hash nie zgadza sie z deklaracja agenta
  - `PHANTOM_FILE` — agent twierdzil ze plik istnieje, ale go nie ma
  - `GHOST_EDIT` — agent twierdzil ze edytowal plik, ale plik sie nie zmienil
- `AgentClaim` + `ClaimAction` — model danych twierdzenia agenta
- `VerificationResult` + `Verdict` — wynik weryfikacji (PASS/FAIL/WARNING)

### Wejscie

- Lista `AgentClaim` per iteracja
- Aktualne checksums plikow z `CHECKSUMS.sha256`

### Wyjscie

- `VerificationResult` per claim
- Aggregate `Verdict` per iteracja: PASS / FAIL_HALT / WARN_CONTINUE

### ADR

- `docs/adr/ADR-0035-release-v5.9.2.md` — phantom-council wyniki, NameError fix w `file_verification.py`

---

## Pixel Provision

**Pliki:** `../../pixel_provision.py`, `../../pixel_detect.py`

Modul automatyzuje pelny provisioning Google Pixel 9 — od OEM unlock do wdrozenia agenta SYLION.

### 8 krokow provisioningu

| Krok | Nazwa                   | Opis                                                    | Destruktywne |
|------|-------------------------|---------------------------------------------------------|--------------|
| 1    | USB Passthrough         | WSL2 usbipd attach (Windows)                            | Nie          |
| 2    | ADB Verify              | `adb devices` — sprawdzenie polaczenia                  | Nie          |
| 3    | OEM Unlock              | `fastboot oem unlock` — odblokowanie bootloadera        | TAK          |
| 4    | Flash GrapheneOS        | Web installer lub lokalny obraz                         | TAK          |
| 5    | Root (opcjonalny)       | Magisk deploy (domyslnie: wyłaczony dla bezpieczenstwa) | TAK          |
| 6    | Deploy Agent            | Wdrozenie agenta SYLION + konfiguracja                  | Nie          |
| 7    | FIDO2 Enrollment        | HumanGate — operator fizycznie podlacza klucz FIDO2     | Nie          |
| 8    | Final Verification      | Weryfikacja budge GrapheneOS, agenta, security patches  | Nie          |

### 16 patchow security

Pixel 9 po flashowaniu otrzymuje 16 patchow hartowania zdefiniowanych w `pixel_provision.py`:
- Wylaczenie USB debugging w trybie produkcji
- Konfiguracja SELinux enforcing
- Wylaczenie Bluetooth odkrywalnosci
- Wymuszenie szyfrowania full-disk
- Konfiguracja DNS-over-HTTPS
- i inne (pelna lista: `docs/security/PIXEL_HARDENING_CHECKLIST.md`)

### PIXEL_9_FAMILY whitelist

```python
PIXEL_9_FAMILY = [
    "Pixel 9",
    "Pixel 9 Pro",
    "Pixel 9 Pro XL",
    "Pixel 9a",
    "Pixel 9 Pro Fold",
]
```

Urzadzenie nienalezace do tej listy blokuje pipeline (HumanGate CRITICAL z ostrzezeniem WRONG_MODEL).

### Kluczowe zmienne srodowiskowe

```ini
DEVICE_HARNESS_DRY_RUN=true   # KRYTYCZNE: domyslnie dry-run (brak destruktywnych operacji)
DEVICE_PIXEL_SERIAL=           # ADB serial (auto-detect jesli pusty)
```

### ADR

- `docs/adr/ADR-0015-pixel-9-default-device.md` — Pixel 9 jako domyslne urzadzenie
- `docs/adr/ADR-0030-pixel9-detection-root-causes.md` — 10 przyczyn bledow wykrywania
- `docs/security/PIXEL_THREAT_MODEL.md` — model zagrozen

---

## WireGuard Provision

**Pliki:** `../../wireguard_provision.py`, `../../scripts/kill_switch.sh`, `../../scripts/dns_tunnel.sh`

Modul implementuje kompletny flow WireGuard dla routera Mudi GL-E750 (OpenWrt).

### 7 krokow provisioningu WG

| Krok | Funkcja              | Opis                                                        |
|------|----------------------|-------------------------------------------------------------|
| 1    | `generate_wg_config` | Generuje wg0.conf z szablonu (klucze przez `wg genkey` na routerze) |
| 2    | `deploy_wg0_conf`    | Wgrywa wg0.conf na router przez SCP                         |
| 3    | `enable_wg_quick`    | `wg-quick up wg0` + autostart `/etc/init.d/wg-quick`        |
| 4    | `verify_tunnel`      | Weryfikuje tunel: `wg show`, ping przez tunel, IP check     |
| 5    | `enable_kill_switch` | Wgrywa kill_switch.sh i aktywuje reguly iptables            |
| 6    | `enable_dns_tunnel`  | Konfiguruje dnsmasq przez VPN DNS (brak DNS leak)           |
| 7    | `configure_wifi_ssid`| Ustawia SSID i WPA3-PSK przez uci                           |

### Bezpieczenstwo kluczy

Klucze WireGuard sa generowane na routerze (`wg genkey`) — klucz prywatny nigdy nie opuszcza urzadzenia. Skrypt pobiera tylko klucz publiczny (`wg pubkey`) do wymiany z serwerem VPN.

### Kill switch

`scripts/kill_switch.sh` konfiguruje reguly iptables blokujace caly ruch sieciowy z wyjatkiem tunelu WireGuard. Aktywuje sie automatycznie gdy interfejs WG0 traci polaczenie. Dezaktywacja wymaga swiadomej decyzji operatora:

```bash
bash scripts/kill_switch.sh --disable
```

### DNS tunnel

`scripts/dns_tunnel.sh` przekierowuje zapytania DNS przez tunel VPN, zapobiegajac DNS leak. Konfiguruje dnsmasq z adresem DNS serwera VPN.

### Kluczowe zmienne srodowiskowe

```ini
DEVICE_ROUTER_HOST=192.168.8.1
DEVICE_ROUTER_USER=root
DEVICE_ROUTER_SSH_KEY=           # sciezka do klucza SSH routera [REQUIRED]
```

### ADR

- `docs/adr/ADR-0027-wireguard-vpn-kill-switch-mudi.md` — WG implementacja od zera

---

## Router Provision

**Plik:** `router_provision.py` (importowany przez orchestrator jako `create_router_deployer`)

Router Provision sluzy do kompletnej konfiguracji routera Mudi GL-E750 z systemem OpenWrt — od bazowej sieci WiFi po WireGuard i kill switch.

### Kroki

1. Polaczenie SSH z routerem (`paramiko` lub `subprocess ssh`)
2. Aktualizacja pakietow (`opkg update`)
3. Instalacja WireGuard (`opkg install wireguard-tools`)
4. Uruchomienie `wireguard_provision.provision_wireguard()`
5. Konfiguracja WiFi (SSID + WPA3 przez `uci`)
6. Weryfikacja: ping przez tunel, test DNS leak, handshake check

### Wejscie

- `WgConfig` — konfiguracja WireGuard
- `WifiConfig` — konfiguracja WiFi
- Dane SSH routera z `.env`

### Wyjscie

- `RouterProvisionResult`: success/fail + log krokow

---

## Device Harness

**Plik:** `../../device_harness.py`

Device Harness to warstwa abstrakcji nad fizycznymi urzadzeniami. Implementuje `SafeCommandRunner` — wrapper wokol `subprocess`, ktory:
- W trybie dry-run (`DEVICE_HARNESS_DRY_RUN=true`) tylko loguje komendy, nie wykonuje ich
- W trybie real-run weryfikuje model urzadzenia przed kazda komenda destruktywna
- Wymusza HumanGate CRITICAL przed operacjami `FLASH`, `UNLOCK`, `WIPE`

### Tryby pracy

| Tryb      | Zmienna                          | Zachowanie                               |
|-----------|----------------------------------|------------------------------------------|
| Dry-run   | `DEVICE_HARNESS_DRY_RUN=true`    | Loguje komendy, nie wysyla do ADB/SSH    |
| Real-run  | `DEVICE_HARNESS_DRY_RUN=false`   | Wykonuje komendy na fizycznym urzadzeniu |

Domyslnie: `DEVICE_HARNESS_DRY_RUN=true` — wymaga swiadomej zmiany na `false` przed prawdziwym flashowaniem.

### DeviceType i DeviceState

```python
class DeviceType(Enum):
    PIXEL_9 = "pixel_9"
    MUDI_ROUTER = "mudi_router"

class DeviceState(Enum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    BOOTLOADER = "bootloader"
    RECOVERY = "recovery"
    PROVISIONED = "provisioned"
```

---

## Circuit Breaker

**Plik:** `../../circuit_breaker.py`

Circuit Breaker chroni pipeline przed kaskadowymi awariami gdy zewnetrzne API modeli AI sa niedostepne.

### Maszyna stanow

```
CLOSED --[5x fail w 60s]--> OPEN --[po 30s]--> HALF_OPEN
                                                    |
                                   sukces probe --->|---> CLOSED
                                   fail probe ----->|---> OPEN (reset timer)
```

### Zachowanie per stan

- `CLOSED` — normalna praca, zliczanie bledow
- `OPEN` — fast-fail wszystkich zapytan (503), fallback na Ollama jesli dostepny
- `HALF_OPEN` — jedna proba dozwolona (sonda)

### Konfiguracja

```ini
CB_FAILURE_THRESHOLD=5    # ile bledow do OPEN
CB_WINDOW_S=60.0          # okno czasowe liczenia bledow
CB_RESET_TIMEOUT_S=30.0   # czas w OPEN przed HALF_OPEN
```

### Endpoint

`GET /api/circuit-breakers` — status wszystkich circuit breakerow (per provider: Anthropic, OpenAI, Google, DeepSeek)

---

## Ollama Client

**Plik:** `../../ollama_client.py`

Klient dla lokalnego serwera Ollama — LLM inference bez kosztow API. Uzywany w Tier 0 (LOCAL) przez tier routing oraz jako fallback gdy circuit breaker danego providerow jest OPEN.

### Obslugiwane modele (Tier 0)

- `deepseek-coder:6.7b` — kod
- `qwen2.5-coder:14b` — kod + reasoning
- `llama3.1:8b` — ogolnego przeznaczenia
- `phi3.5:3.8b` — szybki, maly model

### Konfiguracja

```ini
OLLAMA_API_BASE=http://localhost:11434   # adres serwera Ollama
```

Serwer Ollama musi byc uruchomiony oddzielnie: `ollama serve`.

---

## Retention

**Pliki:** `../../dashboard/retention_cleaner.py`, `../../dashboard/retention_scheduler.py`

Modul odpowiada za automatyczne usuwanie danych zgodnie z polityka RODO (Art. 17) i GoBD.

### Funkcje

| Funkcja                  | Co usuwa                              | Okres retencji  |
|--------------------------|---------------------------------------|-----------------|
| `prune_event_stream`     | Stare zdarzenia pipeline              | 30 dni          |
| `prune_audit_log`        | Stare wpisy audit log                 | 90 dni          |
| `prune_sessions`         | Wygasle sesje                         | 24h po wygasnieciu |
| `prune_upload_history`   | Historia uploadow codebase            | 90 dni          |
| `prune_workspace_uploads`| Pliki ZIP z uploadow                  | 7 dni           |
| `purge_soft_deleted_users`| Konta soft-deleted (RODO Art.17)    | 30 dni po soft-delete |

### Scheduler

`retention_scheduler.run_all_v592()` uruchamiany przy starcie dashboard i co 24h. Cascade delete (klucze obce w SQLite `PRAGMA foreign_keys=ON`) zapewnia spojna usuniecie powiazanych rekordow.

### ADR

- `docs/adr/ADR-0021-rodo-retention.md` — polityka retencji, GoBD compliance

---

## Feature Flags

**Plik:** `../../dashboard/feature_flags.py` (i tabela `feature_flags` w DB)

Runtime toggle mechanizm — wlaczanie/wylaczanie funkcji bez restartu pipeline.

### Kluczowe flagi

| Flaga                      | Domyslna | Opis                                          |
|----------------------------|----------|-----------------------------------------------|
| `BUILD_VERIFICATION_ENABLED` | true   | Weryfikacja buildu przed deployem             |
| `CLAIM_PROVENANCE_ENABLED` | true     | Provenance checking                           |
| `SEMANTIC_DEDUP_ENABLED`   | true     | Semantyczna deduplikacja findingsow            |
| `FACT_CHECKER_ENABLED`     | true     | Fact checker (warstwa 5)                      |
| `PIPELINE_EMERGENCY_STOP`  | false    | Kill switch calego pipeline                   |
| `BENCHMARK_ENABLED`        | true     | Benchmark harness                             |

### Admin UI

`GET /api/config/flags` — lista flag z aktualnym stanem
`PATCH /api/config/flags/{name}` — toggle (role: admin)
`PATCH /api/config/flags/{name}/user/{user_id}` — per-user override

### ADR

- `docs/adr/ADR-0032-feature-flags-architecture.md` — SQLite tabela + REST API + kill switch

---

## Correlation ID

**Plik:** `../../dashboard/correlation_id.py`

Middleware generujacy unikalny `X-Correlation-Id` dla kazdego zadania HTTP. ID jest:
- propagowany do wszystkich logow w obramce danego zadania
- dolaczany do odpowiedzi HTTP (`X-Correlation-Id` header)
- przesylany przez SSE stream jako pole `correlation_id`
- uzywany do filtrowania logow (np. `grep X-Correlation-Id=abc123 logs/*.log`)

---

## Security Headers Middleware

**Plik:** wbudowany w `dashboard/app.py`

Middleware dodajacy naglowki bezpieczenstwa do kazdej odpowiedzi HTTP:

| Naglowek                       | Wartosc                                          |
|--------------------------------|--------------------------------------------------|
| `X-Frame-Options`              | `DENY`                                           |
| `X-Content-Type-Options`       | `nosniff`                                        |
| `X-XSS-Protection`             | `1; mode=block`                                  |
| `Content-Security-Policy`      | `default-src 'self'; script-src 'self'`          |
| `Strict-Transport-Security`    | `max-age=31536000; includeSubDomains` (HTTPS only) |
| `Referrer-Policy`              | `strict-origin-when-cross-origin`                |
| `Permissions-Policy`           | `geolocation=(), microphone=(), camera=()`       |

---

## CSRF Middleware

**Plik:** wbudowany w `dashboard/app.py` (Patch 4 — ADR-0026)

Middleware weryfikuje token CSRF dla wszystkich mutujacych zapytan (POST, PUT, PATCH, DELETE).

### Mechanizm

1. Przy logowaniu generowany jest token CSRF (UUID v4, 32 znaki)
2. Token przechowywany w bazie danych (`csrf_tokens` table) i dostarczany klientowi przez `X-CSRF-Token` header
3. Kazde mutujace zadanie musi zawierac `X-CSRF-Token` header z poprawnym tokenem
4. Token jest rotowany przy kazdym logowaniu i wylaczeniu sesji
5. Ominiety whitelist: `/api/auth/login`, `/api/auth/setup`, `/api/health/*`

### Pokrycie

71/71 mutujacych endpointow po patchu P0-003 (ADR-0026). Weryfikacja: `e2e-playwright-council` 40/40 smoke tests.

### ADR

- `docs/adr/ADR-0026-csrf-full-coverage.md`
- `docs/adr/ADR-0009-secure-cookie-default.md` — SameSite=Strict, HttpOnly

---

## Rate Limiter

**Plik:** wbudowany w `dashboard/app.py` (Patch 5)

Rate limiter chroni endpoint logowania przed atakami brute-force.

### Konfiguracja

```ini
SYLION_LOGIN_MAX_ATTEMPTS=10     # max prob logowania (domyslnie: 10)
# Opcjonalne — konfiguracja w .env:
RATE_LIMIT_LOGIN_ATTEMPTS=5
RATE_LIMIT_LOGIN_WINDOW_SECONDS=300   # 5 minut
RATE_LIMIT_LOGIN_BLOCK_SECONDS=600    # 10 minut blokady
```

### Trusted Proxy

```python
TRUSTED_PROXY_IPS: set[str]  # z .env SYLION_FORWARDED_ALLOW_IPS
```

Naglowek `X-Forwarded-For` jest akceptowany tylko z zaufanych IP proxy. Zapobiega spoofingowi IP.

### ADR

- `docs/adr/ADR-0004-rate-limiting.md`

---

## i18n Middleware

**Plik:** `../../dashboard/i18n_middleware.py`

Middleware obslugi miedzynarodowosci. Odczytuje `Accept-Language` header i serwuje tlumaczenia z plikow `static/i18n/*.json`.

### Obslugan jezyki

| Jezyk      | Kod | Plik                        |
|------------|-----|-----------------------------|
| Polski     | pl  | `static/i18n/pl.json`       |
| Niemiecki  | de  | `static/i18n/de.json`       |
| Angielski  | en  | `static/i18n/en.json`       |

Fallback: en (angielski) jesli jezyk nie jest wspierany.

---

## Database

**Plik:** `../../dashboard/db.py`

Baza danych SQLite z trybem WAL (Write-Ahead Logging) i migracjami od schematu v1 do v4.

### Schema v4 — tabele

| Tabela              | Opis                                               |
|---------------------|----------------------------------------------------|
| `users`             | Konta uzytkownikow (Argon2id hash hasel)           |
| `sessions`          | Aktywne sesje (cookie <-> user, expires)           |
| `csrf_tokens`       | Tokeny CSRF (per sesja, DB-backed)                 |
| `feature_flags`     | Feature flags z wartoscia i per-user override      |
| `pipeline_runs`     | Historia uriuchomien pipeline                      |
| `audit_log`         | Log wszystkich akcji (RODO Art.30)                 |
| `event_stream`      | Strumien zdarzen pipeline (SSE source)             |
| `humangate_requests`| Oczekujace i rozstrzygniete bramki HumanGate       |
| `api_keys`          | Klucze API modeli (encrypted at-rest: secret=1)    |
| `upload_history`    | Historia uploadow codebase                         |
| `workspace_uploads` | Metadane plikow ZIP                               |
| `cost_tracking`     | Koszty LLM per run, per model                      |

### Migracje v1 → v4

```
v1 (base) → v2 (sessions) → v3 (csrf_tokens + feature_flags) → v4 (cost_tracking + upload_history)
```

Kazda migracja jest idempotentna (wielokrotne wywolanie `init_db()` bezpieczne). Przy blakadzie downgradeu — automatyczny rollback do poprzedniej wersji schematu.

### Konfiguracja

```python
PRAGMA foreign_keys = ON    # kaskadowe usuwanie
PRAGMA journal_mode = WAL   # WAL dla lepsziej concurrency
PRAGMA synchronous = NORMAL # balans szybkosci i bezpieczenstwa
```

Uwaga: `PRAGMA` ustawiane raz przy starcie procesu (ADR-0011), nie per-connection.

### ADR

- `docs/adr/ADR-0003-migration-framework.md` — framework migracji
- `docs/adr/ADR-0011-pragma-cached-once-per-process.md` — PRAGMA optymalizacja
- `docs/adr/ADR-0033-run-migrations-v3-to-v4.md` — migracja v3→v4
- `docs/adr/ADR-0031-db-init-race-condition-fresh-install.md` — race condition fix (P0)

---

## Rollback

**Plik:** `../../rollback.sh` (394 linie)

Skrypt rollbacku bazy danych i konfiguracji. Bezpieczny dla WAL (Write-Ahead Logging).

### Glowne funkcje

```bash
bash rollback.sh                              # interaktywny rollback
bash rollback.sh --from-backup=backup.sqlite  # restore z konkretnego backupu
bash rollback.sh --integrity-check-only       # tylko sprawdzenie integralnosci
bash rollback.sh --list-backups               # lista dostepnych backupow
```

### Mechanizm bezpieczenstwa

- `flock` — wyklucza rownoczesne uruchomienie dwoch instancji skryptu (pidfile guard)
- `PRAGMA integrity_check` — weryfikacja bazy przed i po rollbacku
- `PRAGMA wal_checkpoint(FULL)` — wymusza checkpoint WAL przed backupem
- Backup automatyczny przed kazda migracja (do `~/sylion/backups/`)
- Logi bledow migracij: `data/migration_errors.log`

### ADR

- `docs/adr/ADR-0017-rollback-sh-rewrite.md` — przepisanie rollback.sh
- `docs/adr/ADR-0032-rollback-wal-integrity-pidfile-guard.md` — WAL + flock

---

## Powiazania miedzy modulami

```
.env
 |
 +-> orchestrator.py <---> supervisor.py
 |        |
 |        +-> agent_manager.py <-> agents.yaml
 |        |        |
 |        |        +-> tier_routing.py -> [Tier 0: ollama_client.py]
 |        |        |                   -> [Tier 1-3: external APIs]
 |        |        |
 |        |        +-> budget_guard.py
 |        |
 |        +-> Anti-Hallucination Stack:
 |               file_verification.py (SHA-256)
 |               build_verification.py (go/pytest)
 |               claim_provenance.py (keyword matching)
 |               semantic_dedup.py (sentence-transformers)
 |               fact_checker.py (LLM cross-check)
 |
 +-> dashboard/app.py (FastAPI, port 8421)
 |        |
 |        +-> dashboard/db.py (SQLite schema v4)
 |        +-> dashboard/correlation_id.py
 |        +-> dashboard/i18n_middleware.py
 |        +-> dashboard/cost_tracker.py
 |        +-> dashboard/retention_cleaner.py
 |        +-> circuit_breaker.py
 |        +-> feature_flags.py
 |
 +-> Device Provisioning:
          pixel_provision.py + pixel_detect.py
          wireguard_provision.py
          router_provision.py
          device_harness.py (dry-run gate)
          scripts/kill_switch.sh
          scripts/dns_tunnel.sh
```

---

*Poprzednia sekcja: [00_OVERVIEW.md](./00_OVERVIEW.md)*
*Nastepna sekcja: [02_SYSTEM_DECYZJI.md](./02_SYSTEM_DECYZJI.md)*
