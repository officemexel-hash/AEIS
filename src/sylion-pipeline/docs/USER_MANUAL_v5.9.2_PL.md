# Podręcznik użytkownika — SYLION v5.9.2

| Pole             | Wartość                                      |
|------------------|----------------------------------------------|
| **Wersja**       | 5.9.2 (*Mega-Audit Patch*)                   |
| **Data**         | 2026-04-19                                   |
| **Kontakt**      | support@sylion.example                       |
| **Dokumentacja** | docs/ · FAQ_PL.md · TROUBLESHOOTING_PL.md   |

---

## Spis treści

1. [Wprowadzenie](#1-wprowadzenie)
2. [Instalacja](#2-instalacja)
3. [Pierwsze uruchomienie](#3-pierwsze-uruchomienie)
4. [Dashboard — przegląd](#4-dashboard--przegląd)
5. [Upload projektu i uruchomienie pipeline](#5-upload-projektu-i-uruchomienie-pipeline)
6. [Diagnostyka v2 — kody SYL-*](#6-diagnostyka-v2--kody-syl-)
7. [Feature Flags](#7-feature-flags)
8. [HumanGate](#8-humangate)
9. [Rotacja kluczy API](#9-rotacja-kluczy-api)
10. [Provisioning urządzeń](#10-provisioning-urządzeń)
11. [Księga 3.4 i rebase](#11-księga-34-i-rebase)
12. [Monitoring i alerty](#12-monitoring-i-alerty)
13. [Koszty i LLM Tier Routing](#13-koszty-i-llm-tier-routing)
14. [Backup i rollback](#14-backup-i-rollback)
15. [FAQ](#15-faq)
16. [Troubleshooting](#16-troubleshooting)
17. [Incident Response](#17-incident-response)
18. [Compliance (RODO, KSeF, GoBD, DSGVO)](#18-compliance-rodo-ksef-gobd-dsgvo)
19. [Support](#19-support)

---

## 1. Wprowadzenie

### Czym jest SYLION?

SYLION to lokalny pipeline AI do audytu kodu, analizy bezpieczeństwa i wspomagania developmentu. Działa **wyłącznie na Twoim komputerze** — żadne dane nie opuszczają Twojej maszyny bez Twojej wiedzy.

**Architektura:** 48 agentów AI koordynowanych przez jeden spójny orchestrator. Cztery modele AI (Claude Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro) pracują równolegle jako „council" — każda istotna decyzja konsultowana jest przez wszystkie cztery modele jednocześnie.

**Typowe zastosowania:**
- Audyt kodu — bezpieczeństwo (OWASP Top 10), jakość, wydajność
- Automatyczne review pull requestów z raportem HTML
- Generowanie dokumentacji technicznej
- Analiza zależności, długu technicznego i CVE w lockfile
- Pipeline ML z walidacją hallucynacji przez Phantom v3

### Dla kogo?

- **Deweloperzy** — automatyczny audyt przed merge / PR
- **Architekci** — przegląd decyzji architektonicznych (ADR)
- **SRE / DevOps** — monitoring kosztów LLM, alerting, dashboardy Grafana
- **Compliance** — RODO art.30, DSGVO, GoBD, KSeF

### Wersja i wymagania

| Element | Wymaganie |
|---|---|
| Wersja SYLION | 5.9.2 |
| Python | ≥3.11 (3.12 zalecane) |
| RAM | min. 8 GB |
| Dysk | min. 2 GB wolnego miejsca |
| System | Linux, macOS, Windows 10/11 |
| Połączenie | Internet (instalacja zależności + API modeli AI) |
| argon2-cffi | ≥23.1.0 (hard requirement) |
| aiohttp | ≥3.10.11 (nowy wymóg od v5.9.2) |

---

## 2. Instalacja

### 2.1 Linux / macOS

```bash
# Pobierz SYLION (git lub archiwum ZIP)
git clone https://github.com/your-org/sylion.git
cd sylion

# Uruchom instalator
chmod +x install.sh
./install.sh
```

`install.sh` automatycznie:
1. Sprawdza wersję Pythona (min. 3.11)
2. Tworzy wirtualne środowisko Python (`venv/`)
3. Instaluje zależności (`pip install -r requirements-lock.txt`)
4. Generuje plik `.env` z szablonu `.env.example`
5. Inicjalizuje bazę danych SQLite w `~/sylion/sylion.db` (WAL mode)
6. Tworzy katalog backupów `~/sylion/backups/`

Oczekiwany wynik końcowy:
```
[SYLION] Install complete. v5.9.2 ready.
[SYLION] Next step: edit .env with your API keys, then run: python dashboard/start.py
```

### 2.2 Windows

```bat
REM Pobierz SYLION (git lub archiwum ZIP)
git clone https://github.com/your-org/sylion.git
cd sylion

REM Uruchom instalator
install.bat
```

`install.bat` wykonuje te same kroki co skrypt Linux, dostosowane do środowiska Windows:
- Używa `python` zamiast `python3`
- Ścieżki z backslash (`%USERPROFILE%\sylion\`)
- Tworzenie venv przez `python -m venv venv`
- Aktywacja: `venv\Scripts\activate`

### 2.3 Docker

```bash
# Uruchomienie pełnego stacku (SYLION + Prometheus + Grafana + Caddy)
docker compose up -d

# Tylko SYLION bez monitoringu
docker compose up -d sylion
```

`docker-compose.yml` uruchamia:
- `sylion` — kontener na porcie `8421` (wewnętrznie `127.0.0.1`)
- `caddy` — reverse proxy z TLS, port `443`
- `prometheus` — scraping metryk, port `9090`
- `grafana` — dashboardy, port `3000`

Pierwsze uruchomienie Docker: baza SQLite inicjalizowana automatycznie w volume `sylion_data`.

**Zmienne środowiskowe Docker:**
```bash
GRAFANA_ADMIN_PASSWORD=twoje_haslo   # Wymagane
SYLION_FORWARDED_ALLOW_IPS=172.17.0.1  # Dla sieci Docker
```

### 2.4 Weryfikacja instalacji

```bash
# Sprawdź wersję Pythona
python --version
# Python 3.12.x ✓

# Sprawdź zależności krytyczne
python -c "import argon2; print('argon2-cffi:', argon2.__version__)"
python -c "import aiohttp; print('aiohttp:', aiohttp.__version__)"
python -c "import fastapi; print('fastapi:', fastapi.__version__)"
```

Jeśli instalacja nie powiodła się — patrz [TROUBLESHOOTING_PL.md](./TROUBLESHOOTING_PL.md), problemy 9 i 15.

---

## 3. Pierwsze uruchomienie

### 3.1 Konfiguracja pliku `.env`

Przed uruchomieniem otwórz `.env` w edytorze i uzupełnij klucze API:

```ini
# Klucze API modeli (wymagany co najmniej jeden)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
PERPLEXITY_API_KEY=pplx-...

# Bezpieczeństwo (pozostaw domyślne lub zmień)
SESSION_COOKIE_SECURE=1         # 1 = produkcja, 0 = localhost dev
SYLION_LOGIN_MAX_ATTEMPTS=10    # max prób logowania

# Opcjonalne
SYLION_HEALTH_CHECK_V2=true     # Diagnostyka v2 (domyślnie włączona)
SYLION_FORWARDED_ALLOW_IPS=127.0.0.1  # IP zaufanego proxy
```

Możesz uruchomić SYLION bez wszystkich kluczy — modele bez klucza będą niedostępne w council, ale reszta pipeline działa.

### 3.2 Uruchomienie serwera

```bash
python dashboard/start.py
```

Oczekiwany wynik w konsoli:
```
[SYLION] v5.9.2 starting on http://localhost:8421
[SYLION] Setup token: XXXX-XXXX-XXXX-XXXX
[SYLION] DB: /home/<user>/sylion/sylion.db (WAL, v4)
[SYLION] Agents loaded: 48
[SYLION] Council: Claude Opus 4.7 | Sonnet 4.6 | GPT-5.4 | Gemini 3.1 Pro
[SYLION] Health check v2: 82 codes active
```

**Skopiuj setup token** — będzie potrzebny w następnym kroku. Token jest ważny do momentu zakończenia konfiguracji (nie wygasa przy restarcie serwera po v5.9.1).

### 3.3 Bootstrap wizard — 6 kroków

Otwórz przeglądarkę i przejdź pod adres `http://localhost:8421/setup`.

#### Krok 1: Weryfikacja tokenu

Wklej setup token z konsoli w pole „Setup Token". Kliknij „Weryfikuj".

#### Krok 2: Ustawienie hasła administratora

- Minimum 12 znaków
- Zalecane: litery + cyfry + znak specjalny
- Hasło jest hashowane przez Argon2id — nie ma możliwości odczytu

#### Krok 3: Konfiguracja kluczy API

Dashboard pozwala uzupełnić lub zmienić klucze API. Klucze przechowywane w bazie SQLite z flagą `secret=1` (nie wyświetlane w UI po zapisaniu). Szczegóły rotacji: [sekcja 9](#9-rotacja-kluczy-api).

#### Krok 4: Weryfikacja council

SYLION wysyła testowe zapytanie do każdego modelu i sprawdza odpowiedź. Modele bez klucza lub niedostępne oznaczone są jako `OFFLINE`.

#### Krok 5: Weryfikacja urządzenia (opcjonalne)

Jeśli posiadasz Pixel 9 i router Mudi, podłącz urządzenie przez USB i kliknij „Wykryj urządzenie". Szczegóły provisioning: [sekcja 10](#10-provisioning-urządzeń).

#### Krok 6: Potwierdzenie

Po zakończeniu bootstrapu kliknij „Przejdź do Dashboard". Zostaniesz przekierowany na `/login`.

---

## 4. Dashboard — przegląd

### 4.1 Nawigacja

Dashboard składa się z **14 paneli** dostępnych przez lewą nawigację boczną:

#### Przegląd
| Panel | Opis |
|---|---|
| **Dashboard** | KPI, statusy 6 guardów (kolorowe), ostatnie eventy, zdrowie systemu |
| **Monitoring** | Pipeline Stages (8 etapów), aktywne runy, urządzenia |

#### Kontrola
| Panel | Opis |
|---|---|
| **Human Gate** | Decyzje (approve/reject/defer/escalate), SSE real-time |
| **Runs Center** | Lista runów, start/retry/cancel, artefakty, szczegóły |
| **Artefakty** | Pliki z runów: SHA-256, kategorie (Raporty/Logi/Konfiguracja/Patche) |
| **Agenci** | Lista 48 agentów, akcje (start/stop/restart), status |

#### Księga
| Panel | Opis |
|---|---|
| **Baseline Center** | Baseline'y (Draft→Review→Approved→Promoted), diff, porównania |

#### Operacje
| Panel | Opis |
|---|---|
| **Urządzenia** | Pixel 9 / laptop / router Mudi, health check, deploy, benchmark |
| **Streaming** | Metryki audio/video, bitrate, latencja, anomalie |
| **Security** | Budget violations, drift events, anomalie, file verification failures |

#### Konfiguracja
| Panel | Opis |
|---|---|
| **Prompt Registry** | Prompts (Draft→Review→Active→Archived), edytor |
| **Feature Flags** | Toggle modułów, kill switch, audit_log zmian |
| **Ustawienia** | Klucze API, konfiguracja pipeline/streaming/sieci/bezpieczeństwa |
| **Użytkownicy** | RBAC, tworzenie/edycja użytkowników, role |

### 4.2 Role użytkowników (RBAC)

| Rola | Uprawnienia |
|---|---|
| `owner` | Pełny dostęp, zmiana flag krytycznych, usuwanie użytkowników |
| `architect` | Zarządzanie agentami, baseline, ADR |
| `operator` | Uruchamianie pipeline, deploy, provisioning |
| `auditor` | Tylko odczyt wszystkich danych, eksport raportów |
| `viewer` | Odczyt Dashboard i Runs Center |

### 4.3 Panel główny — wskaźniki

Na panelu głównym widoczne są:

- **6 guardów:** BudgetGuard, LoopGuard, HumanGate, FactChecker, ClaimProvenance, FileVerification — każdy w kolorze: zielony (OK) / żółty (WARN) / czerwony (ERROR/CRITICAL)
- **Ostatnie eventy** — chronologiczna lista ostatnich 20 zdarzeń pipeline
- **KPI:** liczba agentów ACTIVE, ostatni run (czas, status), zdrowie DB

---

## 5. Upload projektu i uruchomienie pipeline

### 5.1 Upload projektu

1. Kliknij **Runs Center** w nawigacji bocznej
2. Kliknij przycisk **„Nowy run"**
3. Wybierz źródło projektu:
   - **Upload ZIP** — prześlij archiwum (max 100 MB)
   - **Ścieżka lokalna** — podaj ścieżkę na serwerze SYLION
   - **Git URL** — sklonuj repozytorium (wymaga dostępu sieciowego)
4. Kliknij **„Prześlij"**

Po upload, `run_codebase_audit()` uruchamia się automatycznie (auto-run, naprawione w P0-007).

### 5.2 Auto-run vs. manual run

**Auto-run:** Domyślnie włączony. Po zakończeniu uploadu pipeline startuje natychmiast.

**Manual run:** Wyłącz auto-run w Ustawieniach (`PIPELINE_AUTO_RUN=false`) lub w panelu run przed kliknięciem Prześlij. Następnie kliknij **„Uruchom"** ręcznie z Runs Center.

### 5.3 Statusy runu

| Status | Opis |
|---|---|
| `queued` | Oczekuje na slot |
| `running` | Aktywny, subagenci pracują |
| `waiting_gate` | Zatrzymany na HumanGate |
| `completed` | Zakończony sukcesem |
| `failed` | Błąd — sprawdź logi |
| `cancelled` | Anulowany przez użytkownika |

### 5.4 Etapy pipeline (8 stages)

| Stage | Opis |
|---|---|
| 1. Pre-flight | Weryfikacja środowiska, zależności, DB |
| 2. Upload | Przyjęcie i weryfikacja plików projektu |
| 3. Baseline | Porównanie z poprzednim baseline |
| 4. Agents | Wykonanie 48 agentów |
| 5. Council | Konsultacja 4 modeli, konsensus |
| 6. Artifacts | Generowanie raportów i patchów |
| 7. Security | Audit OWASP, CVE scan |
| 8. Finalize | Zapis wyników, aktualizacja health history |

### 5.5 Artefakty runu

Po zakończeniu runu dostępne są:
- `REPORT.md` / `REPORT.html` — raport z wynikami audytu
- `FIX_MAP.md` — mapa napraw z priorytetami P0–P3
- Patche kodu (jeśli agenci wygenerowali poprawki)
- Logi każdego agenta (SHA-256 zweryfikowane)

---

## 6. Diagnostyka v2 — kody SYL-*

### 6.1 Uruchamianie diagnostyki

**Przez Dashboard:** Kliknij ikonę serduszka (♥) w prawym górnym rogu — otworzy się 16-zakładkowy panel diagnostyczny z auto-refresh co 30 sekund.

**Przez API:**
```bash
# Pełny raport zdrowia
curl -H "Authorization: Bearer TOKEN" http://localhost:8421/api/health/v2

# Raport kategorii security
curl http://localhost:8421/api/health/v2?category=security

# Historia raportów
curl http://localhost:8421/api/health/v2/history
```

### 6.2 Jak czytać raport zdrowia

Każdy wpis w raporcie ma strukturę:
```json
{
  "code": "SYL-SEC-001",
  "check": "csrf_all_endpoints",
  "severity": "ok",
  "message": "71/71 endpoints protected",
  "timestamp": "2026-04-19T12:00:00Z"
}
```

**Severity levels:**
| Poziom | Opis | Akcja |
|---|---|---|
| `ok` | Wszystko w normie | Brak |
| `warn` | Ostrzeżenie, nie krytyczne | Monitoruj |
| `error` | Błąd, wymaga uwagi | Napraw wkrótce |
| `critical` | Krytyczny, blokujący | Napraw natychmiast |
| `n/a` | Nie dotyczy tej konfiguracji | Brak |

### 6.3 Kategorie kodów SYL-*

| Prefix | Kategoria | Kody |
|---|---|---|
| `SYL-PIX-` | Pixel 9 detekcja i prowizjoning | 001–010 |
| `SYL-DB-` | SQLite, WAL, migracje | 011–020 |
| `SYL-SEC-` | Bezpieczeństwo (CSRF, rate limit, cookies) | 021–035 |
| `SYL-COST-` | FinOps, budżet LLM | 036–045 |
| `SYL-NET-` | WireGuard, Mudi, DNS | 046–055 |
| `SYL-PERF-` | Wydajność, PRAGMA, hot-paths | 056–065 |
| `SYL-COMP-` | Compliance RODO/GoBD/KSeF | 066–082 |

### 6.4 Najczęstsze alerty i ich obsługa

**SYL-PIX-001: Pixel 9 not detected**
- Sprawdź USB ADB: `adb devices` — czy urządzenie pojawia się jako `device`?
- Jeśli `unauthorized`: odblokuj ekran telefonu i zaakceptuj autoryzację ADB
- Jeśli niewidoczne: przeinstaluj sterowniki ADB (Windows) lub `udev` rules (Linux)

**SYL-DB-011: WAL file > 500 MB**
- Uruchom checkpoint: `GET /api/health/v2/checkpoint`
- Sprawdź aktywne połączenia: panel Security w Dashboard

**SYL-SEC-021: Rate limit bypass detected**
- Sprawdź konfigurację Caddy: `X-Forwarded-For` musi być przekazywany poprawnie
- Zweryfikuj `SYLION_FORWARDED_ALLOW_IPS` w `.env`

---

## 7. Feature Flags

### 7.1 Zarządzanie flagami

Feature Flags to mechanizm **runtime toggle** — włączanie/wyłączanie modułów bez deployu.

**Przez Dashboard:** Kliknij **Feature Flags** w nawigacji. Widoczna jest tabela flag z kolumnami: Key, Opis, Kategoria, Stan (ON/OFF), Krytyczna.

**Przez API:**
```bash
# Pobierz wszystkie flagi
GET /api/feature-flags

# Zmień flagę
PUT /api/feature-flags/CSRF_PROTECTION
Content-Type: application/json
{"enabled": true}

# Utwórz flagę (tylko owner)
POST /api/feature-flags

# Usuń flagę (tylko owner, niekreytyczna)
DELETE /api/feature-flags/CUSTOM_FLAG
```

### 7.2 Wbudowane flagi

| Klucz | Domyślna | Opis |
|---|---|---|
| `CSRF_PROTECTION` | `true` | Ochrona CSRF — krytyczna |
| `RATE_LIMITING` | `true` | Rate limiting logowania |
| `PIPELINE_AUTO_RUN` | `true` | Auto-run po upload |
| `HEALTH_CHECK_V2` | `true` | Diagnostyka v2 |
| `HUMAN_GATE_SSE` | `true` | SSE real-time dla HumanGate |
| `BOOK_GUARDIAN` | `true` | Ochrona Księgi 3.4 |
| `PHANTOM_V3` | `true` | Hallucination detection |
| `PIPELINE_EMERGENCY_STOP` | `false` | Kill switch — zatrzymuje wszystko |

### 7.3 Kill Switch — PIPELINE_EMERGENCY_STOP

W sytuacji incydentu (np. exploitowana zależność, niekontrolowane koszty LLM):

```bash
# Dashboard: Feature Flags → PIPELINE_EMERGENCY_STOP → Toggle ON
# lub API:
POST /api/feature-flags/kill-switch
Content-Type: application/json
{"reason": "CVE-2026-xxxxx exploited, stopping pipeline"}
```

Efekt: wszystkie aktywne runy pipeline zatrzymywane w <5 sekund. Zapis w `audit_log`. Wymaga roli `owner`.

**Flagi krytyczne** (CSRF_PROTECTION, RATE_LIMITING): zmiana wymaga roli `owner` i jest zapisywana w audit_log z powiadomieniem.

---

## 8. HumanGate

### 8.1 Kiedy pojawia się HumanGate?

HumanGate blokuje pipeline i czeka na decyzję człowieka w następujących sytuacjach:

| Trigger | GateLevel | Opis |
|---|---|---|
| Uruchomienie pełnego pipeline | CRITICAL | Wymagane zatwierdzenie startu |
| Agent wymaga gate | REVIEW | 19 z 48 agentów ma `requires_human_gate: true` |
| Wykryto hallucynacje (Phantom v3) | CRITICAL | Raport zawiera niespójności |
| Brakujące artefakty (stage 6.5) | CRITICAL | Pipeline nie może kontynuować |
| Finding CRITICAL z security audit | CRITICAL | Znalezisko wymaga decyzji |
| Nieobsługiwany błąd agenta | CRITICAL | Eskalacja |
| OEM unlock bootloadera (Pixel) | CRITICAL | Nieodwracalne — wymaga potwierdzenia |
| Wynik pętli agenta | CRITICAL | Loop guard wyzwolony |

### 8.2 Jak decydować w HumanGate?

**Przez Dashboard (zalecane):** Panel **Human Gate** pokazuje oczekujące decyzje z pełnym kontekstem:
- Opis problemu i agent/stage, który wygenerował gate
- Wyniki wszystkich 4 modeli council (jeśli dostępne)
- Opcje decyzji

**Przez CLI (legacy):**
```
[HumanGate] Action required: security_audit_critical
[HumanGate] Finding: SEC-001 CRITICAL — brak rate limiting
[HumanGate] Council consensus: 3/4 za naprawą

Decyzja?
(a) Approve — kontynuuj mimo znaleziska
(b) Reject — zatrzymaj run
(c) Defer — odrocz decyzję
(d) Escalate — eskaluj do innego użytkownika
```

### 8.3 Opcje decyzji

| Opcja | Opis |
|---|---|
| **Approve** | Pipeline kontynuuje |
| **Approve Once** | Jedno zatwierdzenie dla CRITICAL (wymaga podania powodu) |
| **Reject** | Run zatrzymany z zapisem powodu |
| **Defer** | Odroczone — gate czeka do max TTL |
| **Escalate** | Przekazanie do innego użytkownika (wymaga `role=owner`) |

### 8.4 SSE real-time

Po v5.9.2 decyzje z Dashboard UI docierają do CLI Orchestratora przez SSE + SQLite polling bridge (naprawiony defekt TF05). Orchestrator odpytuje bazę co 2 sekundy.

### 8.5 Consensus

Jeśli dostępne są wyniki 4 modeli council, HumanGate pokazuje consensus:
- **3/4 lub 4/4** — silny consensus, decyzja rekomendowana
- **2/2** — brak konsensusu — wymagana dodatkowa analiza
- Dashboard wyróżnia model z odmiennym zdaniem

---

## 9. Rotacja kluczy API

### 9.1 Przez Dashboard (UI)

1. Kliknij **Ustawienia** w nawigacji
2. Sekcja **Klucze API** — 6 providerów: Anthropic, OpenAI, Google, Perplexity, xAI, DeepSeek
3. Kliknij ikonę ołówka obok klucza do zmiany
4. Wklej nowy klucz i kliknij **„Zapisz"**
5. SYLION weryfikuje klucz test-requestem i pokazuje status: `VALID` / `INVALID`

### 9.2 Przez plik `.env`

```bash
# Zatrzymaj serwer
pkill -f "start.py" || true

# Edytuj .env
nano .env
# Zmień: ANTHROPIC_API_KEY=sk-ant-nowy_klucz

# Uruchom ponownie
python dashboard/start.py
```

Po restarcie SYLION odczyta nowy klucz z `.env` i zsynchronizuje z bazą danych.

### 9.3 Bezpieczeństwo kluczy

- Klucze przechowywane w SQLite z flagą `secret=1` — nie są wyświetlane w UI po zapisaniu
- Nigdy nie umieszczaj kluczy w kodzie ani w git — `.gitignore` wyklucza `.env`
- W środowisku produkcyjnym rozważ Vault lub AWS Secrets Manager
- Klucze widoczne w `/proc/PID/environ` — ogranicz dostęp do procesu

---

## 10. Provisioning urządzeń

### 10.1 Pixel 9 — przygotowanie

SYLION v5.9.2 wspiera pełną rodzinę Pixel 9:
`Pixel 9 | Pixel 9 Pro | Pixel 9 Pro XL | Pixel 9 Pro Fold | Pixel 9a`

**Wymagania wstępne:**
- Android Debug Bridge (ADB) zainstalowany i dostępny w PATH
- Pixel 9 podłączony przez USB
- USB Debugging włączone na urządzeniu (Opcje deweloperskie → Debugowanie USB)

**Wykrywanie urządzenia:**
```bash
# Sprawdź czy ADB widzi Pixel
adb devices
# Oczekiwany wynik: <serial>  device

# Sprawdź model
adb shell getprop ro.product.model
# Oczekiwany wynik: Pixel 9 (lub wariant)
```

Jeśli status to `unauthorized`: odblokuj ekran Pixela i zaakceptuj dialog „Zezwolić na debugowanie USB?".

### 10.2 Provisioning przez Dashboard

1. Przejdź do **Urządzenia** w nawigacji
2. Kliknij **„Wykryj urządzenia"** — SYLION odpyta ADB
3. Pixel 9 pojawi się na liście z modelem i numerem seryjnym
4. Kliknij **„Provisionuj"**

**Uwaga:** OEM unlock bootloadera jest operacją **nieodwracalną** — SYLION wyświetli HumanGate CRITICAL z ostrzeżeniem. Zatwierdzenie wymaga roli `owner`.

### 10.3 Router Mudi + WireGuard

**Wymagania:** Router GL.iNet Mudi (GL-E750) z OpenWRT, SSH dostęp.

**Konfiguracja WireGuard (nowa w v5.9.2):**

```bash
# Wygeneruj klucze WireGuard
python wg_config_generator.py --generate-keys --peer mudi

# Przeglądnij konfigurację przed wysłaniem
python wg_config_generator.py --dry-run --peer mudi

# Wyślij konfigurację na router Mudi przez SSH
python wg_config_generator.py --push --peer mudi --host 192.168.8.1
```

Co robi konfiguracja WireGuard:
1. Generuje parę kluczy (private/public) na lokalnej maszynie
2. Buduje `wg0.conf` z parametrami peer (adres, port, klucz publiczny)
3. Wysyła przez SSH na Mudi (`/etc/wireguard/wg0.conf`)
4. Weryfikuje handshake po 10 sekundach
5. Aktywuje kill switch: ruch poza `wg0` blokowany przez `iptables`

**Weryfikacja:**
```bash
# Na lokalnej maszynie
wg show

# Na routerze (przez SSH)
ssh root@192.168.8.1 "wg show"
```

---

## 11. Księga 3.4 i rebase

### 11.1 Czym jest Księga 3.4?

Księga 3.4 to specyfikacja zachowania pipeline SYLION — zestaw reguł i kontraktów, których muszą przestrzegać agenty. Book Guardian pilnuje, by Księga nie była modyfikowana bez autoryzacji.

### 11.2 Weryfikacja stanu Księgi

```bash
# Sprawdź czy Księga jest zsynchronizowana z baseline
python book_guardian.py --check

# Szczegółowy raport
python book_guardian.py --check --verbose
```

Wynik:
```
[BookGuardian] Księga 3.4: OK (0 dryft, baseline: promoted-2026-04-15)
```

### 11.3 Rebase Księgi

Jeśli wykryto drift (>5 wierszy różnicy względem promoted baseline):

```bash
# Podgląd co zrobi rebase (dry-run)
python book_guardian.py --rebase --dry-run

# Wykonaj rebase
python book_guardian.py --rebase
```

**Ważne:** Rebase wymaga zatwierdzenia przez HumanGate (`GateLevel=REVIEW`). Pipeline zostanie wstrzymany do czasu decyzji.

### 11.4 Baseline lifecycle

```
Draft → Review → Approved → Promoted
```

Tylko baseline ze statusem `Promoted` jest używany jako referencja przez Book Guardian i przy porównaniach w pipeline.

---

## 12. Monitoring i alerty

### 12.1 Prometheus

SYLION eksportuje metryki na endpoint `GET /api/metrics` (format Prometheus).

Kluczowe metryki:
| Metryka | Opis |
|---|---|
| `sylion_request_count_total` | Liczba requestów po endpoincie |
| `sylion_request_duration_seconds` | Latencja (histogram) |
| `llm_cost_usd_total` | Sumaryczny koszt LLM w USD |
| `llm_calls_total` | Liczba wywołań API modeli |
| `sylion_wal_size_mb` | Rozmiar WAL pliku SQLite |
| `sylion_disk_free_gb` | Wolne miejsce na dysku |
| `db_connections_active` | Aktywne połączenia SQLite |
| `human_gate_pending` | Liczba oczekujących HumanGate |

### 12.2 Grafana

Cztery wbudowane dashboardy (dostępne po `docker compose up -d grafana`):

| Dashboard | Zawartość |
|---|---|
| **System Overview** | Request Rate, Error Rate 4xx/5xx, Latency P50/95/99, DB, WAL, Disk |
| **LLM Cost** | Total Cost, Koszt/h, Prognoza miesiąca, Koszt per provider, Top 15 użytkowników |
| **Security** | Auth failures, CSRF violations, Rate limit hits, Budget violations |
| **Pipeline Health** | Stage durations, Agent success rates, HumanGate queue, Run history |

Dostęp: `http://localhost:3000` (login: `admin` / wartość `GRAFANA_ADMIN_PASSWORD` z `.env`)

### 12.3 AlertManager

Alerty skonfigurowane w `alertmanager.yml`:

| Alert | Warunek | Kanał |
|---|---|---|
| `SylionHighErrorRate` | Error rate >5% przez 5 min | PagerDuty |
| `SylionLLMCostSpike` | Koszt LLM >$50/h | Slack |
| `SylionWALGrowth` | WAL >500 MB | E-mail |
| `SylionDBDown` | Brak odpowiedzi SQLite | PagerDuty CRITICAL |
| `SylionDiskLow` | Wolne miejsce <1 GB | Slack WARNING |

Konfiguracja kanałów: edytuj `alertmanager.yml` i ustaw `pagerduty_url`, `slack_webhook_url`, `email_to`.

---

## 13. Koszty i LLM Tier Routing

### 13.1 Jak działają koszty?

SYLION śledzi każde wywołanie modelu AI z atrybutami: provider, model, użytkownik, koszt (USD), timestamp. Dane dostępne przez:
- Dashboard → panel **LLM Cost** (Grafana)
- `GET /api/observability/costs` — surowe dane JSON
- `GET /api/metrics` — metryki Prometheus

### 13.2 LLM Tier Routing

Tier Routing to automatyczne kierowanie zapytań do modeli o odpowiednim koszcie/jakości:

| Tier | Modele | Użycie |
|---|---|---|
| **Tier 1 (premium)** | Opus 4.7, GPT-5.4 | Council finalne, security audit, CRITICAL decisions |
| **Tier 2 (balanced)** | Sonnet 4.6, Gemini 3.1 Pro | Council robocze, review |
| **Tier 3 (economy)** | Modele lokalne (Ollama) | Pre-filtering, dokumentacja, logi |

Konfiguracja w `.env`:
```ini
LLM_TIER_ROUTING=true              # Włącz tier routing
LLM_TIER1_BUDGET_USD=50.0          # Dzienny limit Tier 1
LLM_TIER3_MODEL=ollama/llama3.2    # Model lokalny
```

Potencjalne oszczędności przy pełnej optymalizacji: ~$110–310/miesiąc (P1-015 z mega-audytu).

### 13.3 BudgetGuard

BudgetGuard zatrzymuje pipeline gdy koszt dzienny przekroczy limit:
- Konfiguracja: `BUDGET_GUARD_DAILY_USD` w `.env` (domyślnie: `10.0`)
- Alert przez HumanGate gdy 80% budżetu wykorzystane
- Hard stop przy 100% — pipeline zatrzymany do nowego dnia lub ręcznego resetu

---

## 14. Backup i rollback

### 14.1 Automatyczny backup

SYLION tworzy automatyczny backup bazy SQLite:
- **Przy każdym starcie** — `~/sylion/backups/sylion-<version>-<timestamp>.db.bak`
- **Codziennie** — scheduled backup o 02:00 (handler `lifespan` w `app.py`)
- **Przed każdą migracją DB** — WAL checkpoint + atomowy backup

Sprawdź stan backupów:
```bash
ls -lh ~/sylion/backups/
# lub przez API:
curl http://localhost:8421/api/health | jq .backup_age_hours
```

### 14.2 Ręczny backup (WAL-safe)

```bash
# Metoda 1: SQLite .backup API (zalecane, WAL-safe)
sqlite3 ~/sylion/sylion.db ".backup ~/sylion/backups/manual-$(date +%Y%m%dT%H%M%S).db"

# Metoda 2: cp (tylko gdy SYLION nie działa)
cp ~/sylion/sylion.db ~/sylion/backups/manual-$(date +%Y%m%dT%H%M%S).db
```

### 14.3 WAL Checkpoint

Jeśli WAL file rośnie powyżej 500 MB (alert SYL-DB-011):

```bash
# Przez API
curl -X POST http://localhost:8421/api/health/v2/checkpoint \
  -H "Authorization: Bearer TOKEN"

# Bezpośrednio w SQLite (gdy serwer zatrzymany)
sqlite3 ~/sylion/sylion.db "PRAGMA wal_checkpoint(FULL);"
```

### 14.4 Rollback

`rollback.sh` (327 linii) — pełna procedura rollbacku z integralnością WAL:

```bash
# Podgląd co zrobi rollback
./rollback.sh --dry-run

# Pełny rollback (zatrzymuje serwer, przywraca DB, restartuje)
./rollback.sh

# Rollback tylko kodu (zachowaj migracje DB)
git checkout v5.9.1
pip install -r requirements-lock.txt
python dashboard/start.py
```

**Staged restore:** Backup kopiowany do `sylion.db.restore.tmp`, tam uruchamiany `PRAGMA integrity_check`. Jeśli wynik != `ok` — abort BEZ dotykania produkcyjnej bazy.

Kody wyjścia: `0` = sukces · `1` = brak backupu · `2` = integrity_check failed · `3` = brak uprawnień

Pełna dokumentacja: [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md) · [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md)

---

## 15. FAQ

Pełne FAQ: [docs/FAQ_PL.md](./FAQ_PL.md)

**Najczęstsze pytania:**

**Q: Jak zmienić klucze API po instalacji?**
A: Ustawienia → Klucze API → ikona ołówka. Lub edytuj `.env` i zrestartuj. Szczegóły: [sekcja 9](#9-rotacja-kluczy-api).

**Q: Pixel 9 nie jest wykrywany — co zrobić?**
A: Sprawdź `adb devices`. Jeśli `unauthorized` — odblokuj ekran i zaakceptuj dialog USB Debugging. Pełna lista 10 root causes: [docs/FAQ_PL.md](./FAQ_PL.md).

**Q: Setup token wygasł lub zaginął.**
A: Od v5.9.1 token jest trwały — nie wygasa przy restarcie. Sprawdź logi serwera: `journalctl -u sylion -n 50 | grep "Setup token"`.

**Q: Pipeline utknął w stanie `waiting_gate`.**
A: Przejdź do Human Gate w Dashboard i podejmij decyzję. Jeśli HumanGate nie jest widoczny — sprawdź SSE (sekcja 8.4).

**Q: Jak wyłączyć moduł bez restartu?**
A: Użyj Feature Flags — [sekcja 7](#7-feature-flags).

---

## 16. Troubleshooting

Pełna lista problemów i rozwiązań: [docs/TROUBLESHOOTING_PL.md](./TROUBLESHOOTING_PL.md)

**Najczęstsze problemy:**

| Problem | Diagnoza | Rozwiązanie |
|---|---|---|
| Serwer nie startuje | `ModuleNotFoundError: dashboard` | Uruchom z katalogu projektu: `cd sylion && python dashboard/start.py` |
| HTTP 500 przy logowaniu | Błąd v5.9.1 lub starszy | Upgrade do v5.9.2 (P0-002 naprawione) |
| Pusta baza po `--seed` | Błąd v5.9.1 lub starszy | Upgrade do v5.9.2 (P0-001 naprawione) |
| argon2-cffi missing | `RuntimeError: Argon2id backend required` | `pip install argon2-cffi>=23.1.0` |
| WireGuard handshake fail | Klucze niezgodne | `python wg_config_generator.py --regenerate-keys --peer mudi` |
| WAL >1 GB | Brak checkpointa | `sqlite3 sylion.db "PRAGMA wal_checkpoint(FULL);"` |

---

## 17. Incident Response

Pełna procedura: [docs/sre/INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)

**Kluczowe komendy diagnostyczne:**

```bash
# Status serwisu
systemctl status sylion

# Logi Caddy (reverse proxy)
journalctl -u caddy -n 200

# Logi SYLION
journalctl -u sylion -n 100

# Health check
curl http://localhost:8421/api/health
# Oczekiwany: {"version":"5.9.2","db_ok":true,"backup_age_hours":<N>}

# Metryki
curl http://localhost:8421/api/metrics

# Diagnoza DB
sqlite3 ~/sylion/sylion.db "PRAGMA integrity_check; PRAGMA user_version;"

# Kontakt on-call
echo $SYLION_ONCALL_CONTACT
```

**Severity levels incident:**
- **P1 (Critical):** DB corruption, auth bypass, PII leak → HumanGate CRITICAL + PagerDuty
- **P2 (High):** Service down, WAL corruption → SRE + Slack
- **P3 (Medium):** Degraded performance, alert firing → monitoruj + email

---

## 18. Compliance (RODO, KSeF, GoBD, DSGVO)

### 18.1 RODO / DSGVO

SYLION v5.9.2 implementuje wymagania RODO art.5, 17, 30, 32 oraz DSGVO/BDSG §26, §35:

- **Rejestr czynności przetwarzania (RoPA):** [docs/RODO_COMPLIANCE.md](./RODO_COMPLIANCE.md)
- **DPIA v5.9.2:** [docs/DPIA_v592.md](./DPIA_v592.md)
- **Retencja audit_log:** 365 dni (konfiguracja: `SYLION_AUDIT_RETENTION_DAYS`)
- **Retencja sessions:** 30 dni (`SYLION_SESSION_RETENTION_DAYS`)
- **Minimum dla severity=critical:** 30 dni (nie można skrócić)
- **Prawo do usunięcia (art.17):** `DELETE /api/auth/me/data` — usuwa konto + dane, SLA 30 dni
- **Eksport danych (art.20):** `GET /api/auth/me/export` — JSON z danymi użytkownika

**Transfery do USA:** OpenAI, Anthropic, Google, Perplexity — objęte DPA art.28 + SCC Module 2 (2021). Szczegóły: `RODO_COMPLIANCE.md` sekcja 7.

### 18.2 KSeF (Polska)

SYLION v5.9.2 **nie zawiera modułu fakturowania** — KSeF nie dotyczy. Planowane: v5.11 (moduł ingestion faktur z eksportem XML FA(2)).

Szczegóły: [docs/KSEF_ERECHNUNG.md](./KSEF_ERECHNUNG.md)

### 18.3 GoBD + HGB §257 (Niemcy)

- Retencja rekordów finansowych: 10 lat (HGB §257, AO §147)
- Immutable storage dla tabel invoice: v5.11+
- Audit trail §146a AO
- Dokumentacja: [docs/GOBD_RETENTION.md](./GOBD_RETENTION.md)

### 18.4 BDSG §26 (Niemcy — dane pracownicze)

`audit_log` z `actor=username` podlega BDSG §26. Przy przetwarzaniu danych pracowniczych skonsultuj się z IOD/DSB. Dokumentacja: `RODO_COMPLIANCE.md` sekcja HIGH-05.

### 18.5 AI Act (EU 2024/1689)

SYLION jako narzędzie do audytu kodu klasyfikowany jako system AI niskiego ryzyka. Dokumentacja wymagana przez art.13 (transparentność): [docs/RODO_COMPLIANCE.md](./RODO_COMPLIANCE.md) sekcja 9.

---

## 19. Support

**Dokumentacja:**
- FAQ: [docs/FAQ_PL.md](./FAQ_PL.md)
- Troubleshooting: [docs/TROUBLESHOOTING_PL.md](./TROUBLESHOOTING_PL.md)
- Incident Response: [docs/sre/INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)
- Release Notes: [docs/RELEASE_NOTES_v5.9.2_PL.md](./RELEASE_NOTES_v5.9.2_PL.md)
- Rollback: [docs/ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md)

**Kontakt:**
- E-mail: support@sylion.example
- On-call SRE: `$SYLION_ONCALL_CONTACT` (zdefiniowany w `.env`)

---

*SYLION v5.9.2 · Podręcznik użytkownika · Data: 2026-04-19*
*Źródła: FIX_MAP_v5.9.2.md · Mega-audyt 49 subagentów · docs/council_v590/*
