# Podrecznik uzytkownika — SYLION Pipeline v5.9.2

| Pole            | Wartosc                                        |
|-----------------|------------------------------------------------|
| Wersja          | 5.9.2 (Mega-Audit Patch)                       |
| Data            | 2026-04-19                                     |
| Kontakt         | support@sylion.example                         |
| Powiazane docs  | 00_OVERVIEW.md, 01_ARCHITECTURE.md, 08_FAQ.md  |

---

## Spis tresci

1. [Pierwsze uruchomienie](#1-pierwsze-uruchomienie)
2. [Setup srodowiska](#2-setup-srodowiska)
3. [Dry-run — Pixel 9 provisioning](#3-dry-run--pixel-9-provisioning)
4. [Real-run — Pixel 9 flashing](#4-real-run--pixel-9-flashing)
5. [Mudi router + WireGuard setup](#5-mudi-router--wireguard-setup)
6. [Codebase audit — pelny run](#6-codebase-audit--pelny-run)
7. [Dashboard — Feature Flags](#7-dashboard--feature-flags)
8. [Diagnostyka v2](#8-diagnostyka-v2)
9. [Monitoring i alerty](#9-monitoring-i-alerty)
10. [Typowe bledy i co z nimi robic](#10-typowe-bledy-i-co-z-nimi-robic)
11. [Backup + restore drill](#11-backup--restore-drill)
12. [Upgrade 5.9.1 do 5.9.2](#12-upgrade-591-do-592)
13. [Offboarding i Uninstall](#13-offboarding-i-uninstall)

---

## 1. Pierwsze uruchomienie

### Wymagania systemowe

| Element        | Wymaganie minimalne           | Zalecane              |
|----------------|-------------------------------|-----------------------|
| System         | Linux, macOS, Windows 10/11   | Ubuntu 22.04 LTS      |
| Python         | >= 3.11                       | 3.12.x                |
| RAM            | 8 GB                          | 16 GB (Ollama 13B+)   |
| Dysk           | 2 GB wolnego miejsca          | 10 GB (z modelami)    |
| Polaczenie     | Internet (instalacja + API)   | Stabilne broadband    |
| ADB (opcjonalne) | android-tools-adb           | Najnowszy             |
| SSH (opcjonalne) | openssh-client              | Dla provisioning Mudi |

### Krok 1 — Pobierz SYLION

```bash
git clone https://github.com/your-org/sylion-pipeline.git
cd sylion-pipeline
```

Alternatywnie rozpakuj archiwum ZIP z dystrybucji:

```bash
unzip SYLION_v592.zip
cd sylion-pipeline/
```

### Krok 2 — Uruchom instalator

```bash
# Linux / macOS
chmod +x install.sh
bash install.sh

# Windows (PowerShell jako Administrator)
.\install.bat
```

`install.sh` wykonuje automatycznie:
1. Weryfikacje wersji Pythona (wymaga >= 3.11)
2. Tworzenie wirtualnego srodowiska (`venv/`)
3. Instalacje zaleznosci (`pip install -r requirements-lock.txt`)
4. Generowanie pliku `.env` z szablonu `.env.example`
5. Inicjalizacje bazy danych SQLite w `~/sylion/sylion.db` (tryb WAL)
6. Tworzenie katalogu backupow `~/sylion/backups/`

Oczekiwany wynik na koncu instalacji:

```
[SYLION] Install complete. v5.9.2 ready.
[SYLION] Next step: edit .env with your API keys
[SYLION] Then run: python dashboard/start.py
```

### Krok 3 — Uzupelnij klucze API

Otworz `.env` w edytorze i uzupelnij przynajmniej jeden klucz:

```bash
nano .env          # Linux/macOS
notepad .env       # Windows
```

### Krok 4 — Uruchom serwer

```bash
python dashboard/start.py
```

Oczekiwany wynik:

```
[SYLION] v5.9.2 starting on http://localhost:8421
[SYLION] Setup token: XXXX-XXXX-XXXX-XXXX
[SYLION] DB: /home/user/sylion/sylion.db (WAL, v4)
[SYLION] Agents loaded: 48
[SYLION] Council: Claude Opus 4.7 | Sonnet 4.6 | GPT-5.4 | Gemini 3.1 Pro
[SYLION] Health check v2: 82 codes active
```

Skopiuj setup token — bedzie potrzebny w nastepnym kroku.

### Krok 5 — Skonfiguruj konto administratora

Otworz przegladarke i przejdz pod adres: `http://localhost:8421`

Zostaniesz przekierowany do ekranu konfiguracji. Wprowadz setup token i ustaw haslo administratora.

![Screenshot: Ekran logowania SYLION v5.9.2](screenshots/01_login_screen.png)

![Screenshot: Kreator pierwszej konfiguracji — pole setup token i haslo](screenshots/02_first_setup_wizard.png)

Po zakonczeniu setup: zaloguj sie kontem admin i sprawdz, ze dashboard sie wczytuje.

---

## 2. Setup srodowiska

### Wszystkie zmienne .env z komentarzami

Ponizej najwazniejsze zmienne — pelna lista w `.env.example`:

```ini
# === Klucze API modeli AI ===
# Potrzebujesz co najmniej jednego. Minimum: ANTHROPIC_API_KEY.
ANTHROPIC_API_KEY=sk-ant-...        # Claude Opus 4.7 + Sonnet 4.6 + Haiku
OPENAI_API_KEY=sk-...               # GPT-5.4 + o3
GOOGLE_API_KEY=AIza...              # Gemini 3.1 Pro
PERPLEXITY_API_KEY=pplx-...         # Sonar Pro (CVE search)
XAI_API_KEY=xai-...                 # Grok 3 (opcjonalne)
DEEPSEEK_API_KEY=sk-...             # DeepSeek V3 (opcjonalne)

# === Dashboard ===
DASHBOARD_PORT=8421                  # Port (domyslnie: 8421)
DASHBOARD_HOST=127.0.0.1             # Tylko localhost (produkcja: 127.0.0.1 + Caddy)
WEB_CONCURRENCY=1                    # KRYTYCZNE: nie zmieniaj (SQLite, ADR-0025)
SESSION_COOKIE_SECURE=1              # 1 = produkcja HTTPS; 0 = localhost HTTP dev
SYLION_FORWARDED_ALLOW_IPS=127.0.0.1 # IP zaufanego proxy (Caddy)

# === Pipeline ===
CONSENSUS_THRESHOLD=3                # Min. modeli do akceptacji (z 4)
MAX_COST_USD_PER_DAY=50.0            # Dzienny limit kosztow API
BUDGET_WARNING_THRESHOLD=0.80        # Ostrzezenie przy 80% limitu

# === Urzadzenia ===
DEVICE_HARNESS_DRY_RUN=true          # KRYTYCZNE: true = symulacja (bezpieczne)
DEVICE_PIXEL_SERIAL=                 # ADB serial Pixel 9 (puste = auto-detect)
DEVICE_ROUTER_HOST=192.168.8.1       # IP routera Mudi
DEVICE_ROUTER_USER=root              # Uzytkownik SSH routera
DEVICE_ROUTER_SSH_KEY=               # Sciezka do klucza SSH (wymagane do provisioning)

# === Ollama (lokalny LLM — bezplatny) ===
OLLAMA_API_BASE=http://localhost:11434   # Adres serwera Ollama

# === Fact Checker ===
FACT_CHECKER_MODEL_ID=anthropic/claude-sonnet-4-6   # Niezalezny model do weryfikacji
FACT_CHECKER_ENABLED=true

# === Logowanie ===
LOG_LEVEL=INFO                        # DEBUG/INFO/WARNING/ERROR
# SYLION_LOG_FILE=1                   # Odkomentuj: zapis do pliku
# SYLION_LOG_JSON=1                   # Odkomentuj: format JSON
```

### Wybor modeli AI — klucze

Mozesz uruchomic pipeline bez wszystkich kluczy — modele bez klucza zostana pominiete w radzie. Minimum wymagane do pelnego audytu: przynajmniej 2 modele z roznych providerow.

| Scenariusz                 | Wymagane klucze              | Tryb rady       |
|----------------------------|------------------------------|-----------------|
| Pelna rada (zalecane)      | Anthropic + OpenAI + Google  | FULL_COUNCIL    |
| Tylko Anthropic            | ANTHROPIC_API_KEY            | PARTIAL (2 mod.)|
| Bez internetu              | brak (+ Ollama uruchomiony)  | LOCAL_ONLY      |

### Dashboard UI — rotacja kluczy API

Klucze API mozna aktualizowac w Dashboard bez restartu serwera:

Przejdz do: `Ustawienia → API Keys`

![Screenshot: Widok zarzadzania kluczami API w dashboardzie](screenshots/03_api_keys_dashboard.png)

Uwaga: Rotacja UI kluczy jest zaplanowana jako funkcja F-001 w wersji v5.9.3 (constraint C-002 DEFERRED). W v5.9.2 zmiana kluczy przez UI jest dostepna, ale wymaga restartu serwera by zaktualizowac sredowisko procesu. Alternatywa: edytuj `.env` bezposrednio i zrestartuj.

---

## 3. Dry-run — Pixel 9 provisioning

Dry-run to bezpieczny tryb testowania — pipeline wykonuje wszystkie sprawdzenia i loguje komendy, ale NIE wysyla ich do urzadzenia. Domyslnie wlaczony (`DEVICE_HARNESS_DRY_RUN=true`).

### Uruchomienie dry-run

```bash
# Z linii polecen
python3 dashboard/start.py --dry-run-pixel

# Lub przez API (po zalogowaniu):
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/devices/provision-pixel \
  -d '{"dry_run": true, "steps": ["all"]}'
```

### Oczekiwany output dry-run

```
[PIXEL_PROVISION] DRY-RUN mode active. No commands sent to device.
[PIXEL_PROVISION] PRE-CHECK: Verifying environment...
[PIXEL_PROVISION]   ADB found: /usr/bin/adb (version 34.0.4)
[PIXEL_PROVISION]   adb devices...
[PIXEL_PROVISION] DRY-RUN [step: CONNECT] adb devices → [0A291FDD4003BY device]
[PIXEL_PROVISION] DRY-RUN [step: VERIFY_MODEL] Expected: Pixel 9, Found: Pixel 9 (tokay) — OK
[PIXEL_PROVISION] DRY-RUN [step: UNLOCK] fastboot oem unlock → SKIPPED (dry-run)
[PIXEL_PROVISION] DRY-RUN [step: FLASH] fastboot flash ... → SKIPPED (dry-run)
[PIXEL_PROVISION] DRY-RUN [step: LOCK] fastboot oem lock → SKIPPED (dry-run)
[PIXEL_PROVISION] PRE-CHECK complete. All steps validated. Ready for real-run.
[PIXEL_PROVISION] Elapsed: 4.2s
```

![Screenshot: Output dry-run provisioningu Pixel 9 w terminalu](screenshots/04_pixel_dry_run_output.png)

### Przyklad logu przy ADB_NOT_FOUND

```
[PIXEL_PROVISION] PRE-CHECK: Verifying environment...
[PIXEL_PROVISION] [ERROR] ADB_NOT_FOUND
[PIXEL_PROVISION]   adb binary not found in PATH.
[PIXEL_PROVISION]   Install: sudo apt install android-tools-adb (Ubuntu/Debian)
[PIXEL_PROVISION]             brew install android-platform-tools (macOS)
[PIXEL_PROVISION]             install.sh --install-adb (ten skrypt)
[PIXEL_PROVISION] Pipeline PAUSED. Fix ADB installation and retry.
```

Rozwiazanie: patrz sekcja [10H — Pixel 9 ADB not found](#h-pixel-9--adb-not-found).

### Przyklad logu przy WRONG_MODEL

```
[PIXEL_PROVISION] PRE-CHECK: Verifying device model...
[PIXEL_PROVISION] [ERROR] WRONG_MODEL
[PIXEL_PROVISION]   Expected: one of PIXEL_9_FAMILY (Pixel 9, 9 Pro, 9 Pro XL, 9a, 9 Pro Fold)
[PIXEL_PROVISION]   Detected: Pixel 7 (panther) — serial: 9A2B3C4D
[PIXEL_PROVISION]   SYLION Secure obsługuje wyłącznie Pixel 9 family (ADR-0015).
[PIXEL_PROVISION]   Podłącz właściwe urządzenie i uruchom ponownie.
[PIXEL_PROVISION] Pipeline BLOCKED. HumanGate required to override (--force flag).
```

Rozwiazanie: patrz sekcja [10I — Pixel 9 WRONG_MODEL](#i-pixel-9--wrong_model).

---

## 4. Real-run — Pixel 9 flashing

Przed uruchomieniem real-run:
- Upewnij sie, ze dry-run przeszedl bez bledow
- Podlacz Pixel 9 kablem USB do komputera
- Wlacz tryb debugowania USB w Ustawieniach Pixel 9 (Opcje programisty)
- Ustaw `DEVICE_HARNESS_DRY_RUN=false` w `.env`

### Etapy real-run z czasami

| Nr | Etap                    | Opis                                               | Czas szac.  |
|----|-------------------------|----------------------------------------------------|-------------|
| 1  | PRE-CHECK               | Weryfikacja srodowiska ADB, modelu Pixel            | < 1 min     |
| 2  | CONNECT                 | `adb devices`, autoryzacja USB                      | 1-2 min     |
| 3  | HumanGate UNLOCK        | Operator zatwierdza OEM unlock (destruktywne)       | Operator    |
| 4  | OEM UNLOCK              | `fastboot oem unlock` — reset fabryczny!            | 2-5 min     |
| 5  | REBOOT BOOTLOADER       | Restart do fastboot                                 | 1 min       |
| 6  | HumanGate FLASH         | Operator zatwierdza flash GrapheneOS                | Operator    |
| 7  | FLASH GRAPHENEOS        | Flash wszystkich partycji                           | 10-20 min   |
| 8  | HARDENING               | 16 security patchow                                 | 5-10 min    |
| 9  | DEPLOY AGENT            | Wdrozenie agenta SYLION na Pixel                    | 2-3 min     |
| 10 | HumanGate FIDO2         | Operator fizycznie podlacza klucz FIDO2             | Operator    |
| 11 | VERIFY                  | Weryfikacja GrapheneOS, patches, agenta             | 2-3 min     |

**KRYTYCZNE:** Kroki 4 i 7 sa destruktywne — powoduja utrate wszystkich danych na Pixelu. Upewnij sie, ze masz backup danych przed uruchomieniem.

### HumanGate CRITICAL — flash

Przed krokiem FLASH pojawi sie bramka decyzyjna:

```
+==============================================================+
| HUMANGATE #4                              [CRITICAL]         |
| ID: HG-2026041904-b7e3                                       |
|--------------------------------------------------------------|
| Pytanie:                                                     |
|   Gotowy do flashowania GrapheneOS na Pixel 9                |
|   (serial: 0A291FDD4003BY). Operacja jest destruktywna       |
|   i nieodwracalna — skasuje wszystkie dane na urządzeniu.    |
|--------------------------------------------------------------|
| Kontekst:                                                    |
|   Model: Pixel 9 (tokay) — PIXEL_9_FAMILY: OK               |
|   OEM unlock: DONE                                           |
|   GrapheneOS build: 2026041400 (sprawdzono SHA-256)          |
|   Backup danych: wymagany przed kontynuacją                  |
|--------------------------------------------------------------|
| Opcje:                                                       |
|   [A] Kontynuuj flash — potwierdzam backup danych           |
|   [B] Przerwij — nie flashuj                                |
|--------------------------------------------------------------|
| Plan rollbacku:                                              |
|   Uzywaj factory image Google dla Pixel 9 (dl.google.com)   |
+==============================================================+
```

![Screenshot: Postep flashing Pixel 9 w terminalu z paskiem procentow](screenshots/05_pixel_flash_progress.png)

![Screenshot: HumanGate CRITICAL modal w interfejsie dashboard — pytanie o flash](screenshots/06_humangate_critical_pixel.png)

---

## 5. Mudi router + WireGuard setup

### Wymagania wstepne

- Router GL.iNet Mudi GL-E750 z OpenWrt
- Dostep SSH (klucz lub haslo w `.env`)
- Konfiguracja serwera VPN (klucz publiczny, endpoint, IP klienta)

### Krok 1 — Skonfiguruj dane routera w .env

```ini
DEVICE_ROUTER_HOST=192.168.8.1
DEVICE_ROUTER_USER=root
DEVICE_ROUTER_SSH_KEY=/home/user/.ssh/mudi_key
```

### Krok 2 — Uruchom provisioning przez API

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/devices/provision-router \
  -d '{
    "router_host": "192.168.8.1",
    "wg_server_pubkey": "KLUCZ_PUBLICZNY_SERWERA_VPN=",
    "wg_server_endpoint": "vpn.przyklad.pl:51820",
    "wg_client_address": "10.8.0.2/24",
    "wifi_ssid": "SYLION-Pixel",
    "wifi_password": "SilneHasloWiFi123!",
    "enable_kill_switch": true,
    "enable_dns_tunnel": true,
    "dry_run": false
  }'
```

### Krok 3 — SSH na router i weryfikacja

Po ukonczeniu provisioningu sprawdz status WireGuard bezposrednio na routerze:

```bash
ssh root@192.168.8.1 "wg show"
```

Oczekiwany output:

```
interface: wg0
  public key: KLUCZ_PUBLICZNY_KLIENTA=
  private key: (hidden)
  listening port: 51820

peer: KLUCZ_PUBLICZNY_SERWERA=
  endpoint: vpn.przyklad.pl:51820
  allowed ips: 0.0.0.0/0, ::/0
  latest handshake: 14 seconds ago
  transfer: 1.23 MiB received, 456 KiB sent
  persistent keepalive: every 25 seconds
```

![Screenshot: Status WireGuard — wynik wg show z aktywnym handshake](screenshots/07_wireguard_status.png)

### Krok 4 — Weryfikacja kill switch

Kill switch jest aktywowany automatycznie po skonfigurowaniu WireGuard. Sprawdz reguly iptables:

```bash
ssh root@192.168.8.1 "iptables -L OUTPUT -n"
```

Oczekiwany output — ruch dozwolony TYLKO przez interfejs wg0:

```
Chain OUTPUT (policy DROP)
target  prot  opt  source     destination
ACCEPT  all   --   0.0.0.0/0  0.0.0.0/0  out-interface wg0
ACCEPT  all   --   0.0.0.0/0  0.0.0.0/0  out-interface lo
```

![Screenshot: Reguly iptables z aktywnym kill switch — wyjscie iptables -L OUTPUT](screenshots/08_killswitch_iptables.png)

### Krok 5 — Test DNS leak

```bash
# Na routerze lub podlaczonym urzadzeniu (przez tunel)
nslookup whoami.akamai.net
```

Odpowiedz powinna wskazywac na IP serwera VPN — nie na lokalnego ISP.

---

## 6. Codebase audit — pelny run

### Krok 1 — Upload codebase

Otworz dashboard: `http://localhost:8421` → zakadka "Pipeline" → "Upload Codebase".

![Screenshot: Formularz uploadu codebase — dwie zakladki: ZIP i Git URL](screenshots/09_upload_codebase.png)

Lub przez API (ZIP):

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -F "file=@moj-projekt.zip" \
  http://localhost:8421/api/pipeline/upload
```

Lub przez Git URL:

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/pipeline/upload-git \
  -d '{"git_url": "https://github.com/org/repo.git", "branch": "main"}'
```

### Krok 2 — Uruchom audyt

Po uploadzie kliknij "Run Audit" w UI lub przez API:

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/pipeline/run \
  -d '{"upload_id": "upl_XXXXX", "run_type": "full", "council_mode": "auto"}'
```

### Krok 3 — Monitorowanie iteracji

Dashboard SSE stream pokazuje postep w czasie rzeczywistym.

![Screenshot: Widok iteracji pipeline — pasek postepu i log iteracji 1..N](screenshots/10_run_progress_iterations.png)

Strumien SSE z linii polecen:

```bash
curl -b cookies.txt -N http://localhost:8421/api/pipeline/stream/run_XXXXX
```

Przykladowe zdarzenia SSE:

```
data: {"event":"iteration_start","iteration":1,"stage":"stage_1_prepare"}
data: {"event":"council_vote","model":"claude-opus-4-7","verdict":"PASS","confidence":0.96}
data: {"event":"council_vote","model":"claude-sonnet-4-6","verdict":"PASS","confidence":0.94}
data: {"event":"council_vote","model":"gpt-5-4","verdict":"FAIL","confidence":0.88}
data: {"event":"council_vote","model":"gemini-3-1-pro","verdict":"PASS","confidence":0.91}
data: {"event":"consensus","result":"MAJORITY_3_4","humangate_required":true}
data: {"event":"humangate_triggered","gate_id":"HG-2026041905-c2a1","priority":"HIGH"}
```

### Krok 4 — HumanGate breakpoint

Przy konsensusie 3/4 pojawia sie bramka decyzyjna.

![Screenshot: Modal HumanGate w UI — pytanie o akceptacje przy konsensusie 3/4](screenshots/11_humangate_modal.png)

Odpowiedz przez UI lub API:

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/humangate/HG-2026041905-c2a1/answer \
  -d '{"option": "A", "comment": "Zatwierdzam — finding GPT-5.4 jest niskie ryzyko"}'
```

### Krok 5 — Finalny raport i download

Po zakonczeniu audytu raport jest dostepny do pobrania.

![Screenshot: Widok finalnego raportu audytu z przyciskiem Download ZIP](screenshots/12_final_report_download.png)

```bash
curl -b cookies.txt -o raport_audyt.zip \
  http://localhost:8421/api/pipeline/download/run_XXXXX
```

ZIP zawiera:
- `report.html` — czytelny raport z findings pogrupowanymi po severity
- `findings.json` — machinereadable lista findings
- `diff.patch` — proponowane zmiany w codebase
- `audit_log.csv` — pelny log decyzji z council votes

---

## 7. Dashboard — Feature Flags

Feature flags pozwalaja wlaczac i wylaczac funkcje pipeline w czasie rzeczywistym, bez restartu serwera.

### Dostep do admin UI

Zaloguj sie jako admin, nastepnie: `Ustawienia → Feature Flags`

![Screenshot: Panel administracyjny feature flags — lista flag z toggle switchami](screenshots/13_feature_flags_admin.png)

### Toggle przez UI

Kliknij przelacznik obok nazwy flagi. Zmiana jest aktywna natychmiast i zapisana do bazy danych.

### Toggle przez API

```bash
# Wylacz Fact Checker (tymczasowo, np. do testow)
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X PATCH http://localhost:8421/api/config/flags/FACT_CHECKER_ENABLED \
  -d '{"value": false}'

# Przywroc
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X PATCH http://localhost:8421/api/config/flags/FACT_CHECKER_ENABLED \
  -d '{"value": true}'
```

### Per-user override

Admin moze nadpisac wartosc flagi dla konkretnego uzytkownika — bez zmiany globalnej wartosci.

![Screenshot: Formularz per-user override flagi — wybor uzytkownika i wartosci](screenshots/14_flag_user_override.png)

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X PATCH "http://localhost:8421/api/config/flags/BENCHMARK_ENABLED/user/42" \
  -d '{"value": false}'
```

---

## 8. Diagnostyka v2

Diagnostyka v2 oferuje 82 kody SYL-* oraz widok historyczny stanu systemu.

### Endpointy health

```bash
# Liveness — czy proces zyje
curl http://localhost:8421/api/health/live
# {"status": "ok", "version": "5.9.2"}

# Readiness — czy gotowy na ruch
curl http://localhost:8421/api/health/ready
# {"status": "ready", "db": "ok", "agents": "loaded"}

# Detailed — pelny status systemu
curl -b cookies.txt http://localhost:8421/api/health/detailed
```

### UI diagnostyki

W przegladarce: `http://localhost:8421/diagnostyka_v2.html`

![Screenshot: Dashboard diagnostyka_v2.html — zielone wskazniki wszystkich komponentow](screenshots/15_diagnostyka_v2_live.png)

![Screenshot: Szczegolowy widok health detailed — DB, modele, budget, HumanGate](screenshots/16_diagnostyka_v2_detailed.png)

### Stan DEGRADED — przyklad

Przyklad gdy dysk jest pelny (SYL-071: disk_full):

```json
{
  "status": "degraded",
  "version": "5.9.2",
  "db": {"status": "ok"},
  "disk": {"status": "warning", "free_gb": 0.2, "threshold_gb": 1.0},
  "syl_codes": [
    "SYL-001: DB ok",
    "SYL-071: DISK_LOW — free: 0.2 GB, threshold: 1.0 GB"
  ],
  "degraded_components": ["disk"]
}
```

![Screenshot: Widok diagnostyki w stanie DEGRADED — czerwony wskaznik dysku](screenshots/17_diagnostyka_degraded.png)

Rozwiazanie:
1. Zwolnij miejsce: skasuj stare workspace uploads (`~/sylion/workspace_uploads/*.zip`)
2. Uruchom retencje recznie: `POST /api/maintenance/retention-run`
3. Sprawd log audytu: `ls -lh ~/sylion/backups/` — usun stare backupy jesli potrzeba

---

## 9. Monitoring i alerty

### Grafana dashboardy (4 panele)

Grafana dostepna pod: `http://localhost:3000` (user: admin, haslo: z `.env` `GRAFANA_ADMIN_PASSWORD`)

| Dashboard                   | Tresc                                             |
|-----------------------------|---------------------------------------------------|
| SYLION Overview             | Laczny health, pipeline runs, koszt dzienny       |
| Pipeline Performance        | Czas uruchomien, iteracje, council vote times     |
| Cost Tracker                | Koszt per model, per run, trend miesieczny        |
| Device Status               | Stan Pixel 9, WireGuard tunnel, Mudi router       |

![Screenshot: Grafana Dashboard SYLION Overview — wykresy health i pipeline runs](screenshots/18_grafana_dashboard_overview.png)

![Screenshot: Grafana Cost Tracker — wykres kosztow LLM per model i per run](screenshots/19_grafana_cost_tracker.png)

### Prometheus metrics

```bash
# Wszystkie metryki eksportowane przez pipeline
curl http://localhost:8421/metrics
```

Kluczowe metryki:

| Metryka                              | Typ       | Opis                              |
|--------------------------------------|-----------|-----------------------------------|
| `sylion_pipeline_runs_total`         | Counter   | Laczna liczba uruchomien          |
| `sylion_pipeline_duration_seconds`   | Histogram | Czas trwania run                  |
| `sylion_llm_cost_usd_total`          | Counter   | Laczny koszt LLM                  |
| `sylion_circuit_breaker_state`       | Gauge     | Stan CB per provider (0=CLOSED)   |
| `sylion_humangate_pending_total`     | Gauge     | Liczba oczekujacych bramek        |
| `sylion_db_query_duration_seconds`   | Histogram | Czas zapytan DB                   |

### Alertmanager

Reguly alertow (`deploy/monitoring/alertmanager.yml`):

| Alert                    | Warunek                             | Akcja                     |
|--------------------------|-------------------------------------|---------------------------|
| PipelineFailed           | `sylion_pipeline_runs_total{status="failed"}` > 0 | Email/webhook |
| BudgetWarning            | `sylion_llm_cost_usd_total` > 80% limitu | Ostrzezenie     |
| CircuitBreakerOpen       | `sylion_circuit_breaker_state` > 0  | Alert + auto-fallback     |
| HumanGateExpired         | Gate starszy niz 30 min bez odp.   | Ostrzezenie               |
| DiskLow                  | Dysk < 1 GB wolnego                 | Alert                     |

---

## 10. Typowe bledy i co z nimi robic

### A. Utrata polaczenia z modelem AI

**Objaw:** Spinner w UI, po 30 sekundach error modal z komunikatem "Brak odpowiedzi od Anthropic API po 30s" lub "OpenAI timeout".

**Co widzi uzytkownik:**
- Spinner zamiast progresu iteracji
- Po 30s: error modal z nazwa providera i typem bledu

![Screenshot: Modal bledu — Anthropic API timeout po 30 sekundach](screenshots/20_error_anthropic_timeout.png)

**Co robi pipeline automatycznie:**
1. Circuit Breaker wykrywa 5 bledow w ciagu 60s → stan OPEN
2. Nowe requesty do tego providera → fast-fail 503 (brak oczekiwania)
3. Fallback na lokalny Ollama (jesli dostepny i tier to umozliwia)
4. Po 30 sekundach → Circuit Breaker przechodzi do HALF_OPEN (proba sondy)
5. Jesli sonda OK → powrot do CLOSED (normalnie)
6. Jesli sonda fail → OPEN ponownie

**Gdy wszystkie 4 modele fail:**

Pipeline przechodzi do stanu BLOCKED. HumanGate pojawia sie z pytaniem co robic:

![Screenshot: HumanGate BLOCKED — wszystkie modele niedostepne, opcje wait/local/abort](screenshots/21_all_models_down_humangate.png)

**Diagnoza:**

```bash
# Sprawdz status circuit breakerow
curl -b cookies.txt http://localhost:8421/api/circuit-breakers

# Sprawdz health detailed — model_status per provider
curl -b cookies.txt http://localhost:8421/api/health/detailed
```

---

### B. Skonczene kredyty w czesci modeli

Jest to scenariusz, w ktorym pipeline musi kontynuowac prace z niepelna rada — np. 3 z 4 providerow wypadlo z powodu braku kredytow lub limitow.

**Przykladowy scenariusz:**
- Anthropic Opus: `CREDITS_EXHAUSTED` (brak kredytow)
- OpenAI GPT-5.4: `RATE_LIMITED` (429)
- Google Gemini: `QUOTA_EXCEEDED`
- Aktywne: Sonnet 4.6, Claude Haiku (backup), Ollama lokalny

**Co robi pipeline:**

1. Budget Guard wykrywa `CREDITS_EXHAUSTED` per provider
2. Provider jest automatycznie usuwany z aktywnej puli rady
3. Pipeline przechodzi w tryb `DEGRADED_COUNCIL`
4. Prog konsensusu dostosowywany: zamiast 3/4 — wymagany 2/3 aktywnych modeli

![Screenshot: Widok trybu degraded council — 3 z 7 modeli aktywne](screenshots/22_degraded_council_3of7.png)

**Komunikat w UI (top bar):**

```
Dzialajace modele: 3/7 (Sonnet 4.6, Claude Haiku, Ollama). Niektore funkcje ograniczone.
```

![Screenshot: Banner ostrzezenia o czesciowo niedostepnych modelach](screenshots/23_partial_model_warning_banner.png)

**HumanGate z pytaniem o degraded mode:**

Pipeline pyta operatora czy akceptuje prace w trybie zdegradowanym:

![Screenshot: HumanGate pytajacy o zgode na prace w trybie degraded council](screenshots/24_humangate_degraded_mode_confirm.png)

**Tabela fallback matrix:**

| Aktywne modele | Tryb              | Prog konsensusu | Co sie dzieje                          |
|----------------|-------------------|-----------------|-----------------------------------------|
| 4/4            | FULL_COUNCIL      | 3/4 (75%)      | Normalnie                               |
| 3/4            | PARTIAL_COUNCIL   | 2/3 (67%)      | Ostrzezenie w UI                        |
| 2/4            | DEGRADED_COUNCIL  | 2/2 (100%)     | HumanGate o akceptacje trybu            |
| 1/4            | SINGLE_MODEL      | N/A             | HumanGate BLOCKED (ryzyko)             |
| 0/4 + Ollama   | LOCAL_ONLY        | N/A             | Tylko lokalne modele, HumanGate         |
| 0/4 + brak Ollama | BLOCKED        | N/A             | Pipeline zatrzymany                     |

**Po uzupelnieniu kredytow:**

Budget Guard wykrywa odtworzenie modelu przy nastepnym health check (co 60s). Powrot do FULL_COUNCIL automatyczny.

![Screenshot: Notyfikacja o powrocie do pelnej rady po uzupelnieniu kredytow](screenshots/25_council_recovered_notification.png)

---

### C. Rate limit na API

**Objaw:** `429 Too Many Requests` z naglowkiem `X-RateLimit-Reset: NNN`.

**Co robi pipeline:**

Exponential backoff automatyczny: 1s → 2s → 4s → 8s → max 60s przerwy miedzy probami.

![Screenshot: Log pokazujacy exponential backoff przy 429 — kolejne retry z rosnacea przerwa](screenshots/26_rate_limit_backoff_log.png)

```
[RATE_LIMIT] 429 received from OpenAI. Retry in 1s...
[RATE_LIMIT] 429 received from OpenAI. Retry in 2s...
[RATE_LIMIT] 429 received from OpenAI. Retry in 4s...
[RATE_LIMIT] X-RateLimit-Reset: 1745065200. Waiting 47s (hard reset).
```

**Jesli rate limit trwa dluzej niz 5 minut:** Circuit Breaker przechodzi do OPEN, pipeline kontynuuje z pozostalymi modelami lub Ollama.

---

### D. Database locked / corrupted

**Objaw D1 — Database locked:**

```
sqlite3.OperationalError: database is locked
```

**Przyczyna:** Dwie instancje SYLION proba zapisu jednoczesnie, lub inny program (np. DB Browser) ma otwarty plik bazy.

![Screenshot: Blad database locked w logu pipeline](screenshots/27_db_locked_error.png)

**Rozwiazanie krok po kroku:**

1. Sprawdz czy dziala wiecej niz jedna instancja SYLION:

```bash
ps aux | grep "dashboard/start.py"
# lub na Windows:
tasklist | findstr python
```

2. Jesli tak — zatrzymaj dulikat: `kill -9 PID`

3. Jesli WEB_CONCURRENCY > 1 — to P0 bloker:

```ini
# .env
WEB_CONCURRENCY=1   # KRYTYCZNE — nie zmieniaj (ADR-0025)
```

4. Wymus WAL checkpoint:

```bash
sqlite3 ~/sylion/sylion.db "PRAGMA wal_checkpoint(FULL);"
```

**Objaw D2 — Database corrupted:**

```bash
bash rollback.sh --integrity-check-only
# [FAIL] PRAGMA integrity_check returned: row X missing from index Y
```

**Rozwiazanie:**

```bash
# Lista dostepnych backupow
bash rollback.sh --list-backups

# Restore z ostatniego dobrego backupu
bash rollback.sh --from-backup=backup_20260419_060000.sqlite
```

---

### E. Upload ZIP — path traversal / mime mismatch

**Objaw E1 — Path traversal:**

```
HTTP 400: Upload rejected — path traversal detected
Offending entry: ../../../etc/passwd
```

![Screenshot: Komunikat odrzucenia uploadu — path traversal detected](screenshots/28_upload_rejected_path_traversal.png)

Pipeline odrzuca ZIP zawierajacy sciezki wychodzace poza katalog (np. `../`). Jest to funkcja bezpieczenstwa — nie blad do ominięcia. Utwórz nowe archiwum ZIP bez takich sciezek:

```bash
cd /katalog/projektu
zip -r ../projekt.zip . --exclude "*.git/*"
```

**Objaw E2 — MIME mismatch:**

```
HTTP 400: Upload rejected — MIME type mismatch
Expected: application/zip, Got: application/octet-stream
```

![Screenshot: Komunikat odrzucenia uploadu — niepoprawny MIME type](screenshots/29_upload_rejected_mime.png)

Rozwiazanie: sprawdz ze uploadujesz prawdziwy plik ZIP (nie zip zawierajacy np. .tar.gz). Uzyj `file plik.zip` aby sprawdzic typ.

---

### F. HumanGate expired (> 30 min bez odpowiedzi)

**Objaw:** Status pipeline = PAUSED. W UI: bramka z etykieta "EXPIRED — 30:00 uplynelo bez odpowiedzi".

![Screenshot: HumanGate w stanie EXPIRED — czerwony naglowek, pipeline PAUSED](screenshots/30_humangate_expired.png)

**Co zrobic:**

```bash
# Restart wygaslej bramki (nowe 30-minutowe okno)
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -X POST http://localhost:8421/api/humangate/HG-XXXXX/restart
```

Pipeline wraca do stanu WAITING i daje nowe 30 minut na odpowiedz. Wszystkie dane bramki (pytanie, opcje, rollback) pozostaja bez zmian.

---

### G. Migracja DB failed

**Objaw:**

```
MigrationError: Migration v3->v4 failed: column 'cost_model' already exists
data/migration_errors.log: ...
```

![Screenshot: Blad migracji bazy danych z automatycznym rollbackiem do poprzedniej wersji](screenshots/31_migration_failed_rollback.png)

**Co robi pipeline automatycznie:**

Pipeline wykonuje automatyczny rollback do poprzedniej wersji schematu. Baza pozostaje w stanie z przed migracji.

**Weryfikacja:**

```bash
# Sprawdz wersje schematu
sqlite3 ~/sylion/sylion.db "SELECT value FROM meta WHERE key='schema_version';"
# Powinno zwrocic: 3 (jesli rollback do v3)

# Sprawd log bledow
cat data/migration_errors.log

# Sprawdz integralnosc
bash rollback.sh --integrity-check-only
```

**Jesli rollback nie pomógl:**

```bash
bash rollback.sh --from-backup=backup_pre_migration.sqlite
```

---

### H. Pixel 9 — ADB not found

**Objaw:**

```
[PIXEL_PROVISION] [ERROR] ADB_NOT_FOUND
adb binary not found in PATH.
```

![Screenshot: Komunikat bledu ADB_NOT_FOUND z instrukcja instalacji](screenshots/32_adb_not_found.png)

**Rozwiazanie:**

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y android-tools-adb

# macOS (Homebrew)
brew install android-platform-tools

# Windows — pobierz SDK Platform Tools ze strony Google
# https://developer.android.com/tools/releases/platform-tools

# Lub przez instalator SYLION (jesli funkcja dostepna)
bash install.sh --install-adb

# Weryfikacja
adb version
# Android Debug Bridge version 34.x.x
```

---

### I. Pixel 9 — WRONG_MODEL

**Objaw:**

```
[PIXEL_PROVISION] [ERROR] WRONG_MODEL
Expected: PIXEL_9_FAMILY. Detected: Pixel 7 (panther)
Pipeline BLOCKED.
```

![Screenshot: Komunikat WRONG_MODEL — wykryto Pixel 7 zamiast Pixel 9](screenshots/33_wrong_pixel_model.png)

Pipeline NIE pozwala kontynuowac z niezgodnym modelem urzadzenia. SYLION Secure jest certyfikowane wylacznie dla rodziny Pixel 9.

**Rozwiazanie:**

1. Odlacz Pixel 7
2. Podlacz Pixel 9, 9 Pro, 9 Pro XL, 9a lub 9 Pro Fold
3. Uruchom provisioning ponownie

Jesli naprawde chcesz kontynuowac z innym modelem (nieobslugiwane, nie zalecane):

```bash
python3 dashboard/start.py --dry-run-pixel --force-model-override
```

Wymaga HumanGate CRITICAL z jawnym ostrzezeniem.

---

### J. WireGuard kill switch aktywny — brak internetu

**Objaw:** Urzadzenie podlaczone do sieci WiFi Mudi, ale brak dostepu do internetu. `ping 8.8.8.8` timeout.

**To jest zachowanie CELOWE.** Kill switch jest aktywny — jesli tunel WireGuard zerwał sie, caly ruch jest blokowany (iptables DROP dla ruchu poza wg0).

![Screenshot: Stan kill switch aktywny — terminal z ping timeout i komunikatem o blokadzie](screenshots/34_killswitch_active_no_internet.png)

**Diagnoza:**

```bash
# Na routerze Mudi
ssh root@192.168.8.1 "wg show"
# Jesli brak "latest handshake" lub handshake > 3 minuty — tunel padl

# Sprawdz logi WireGuard
ssh root@192.168.8.1 "logread | grep wireguard | tail -20"
```

**Przywracanie tunelu:**

```bash
# Restart interfejsu WG
ssh root@192.168.8.1 "wg-quick down wg0 && wg-quick up wg0"

# Jesli tunel wrocil — kill switch automatycznie przestaje blokowac ruch
```

**Swiadome wylaczenie kill switch (np. do diagnostyki):**

```bash
bash scripts/kill_switch.sh --disable
# LUB przez API:
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -X POST http://localhost:8421/api/devices/kill-switch \
  -d '{"action": "disable"}'
```

Wymaga HumanGate CONFIRMATION — pipeline pyta o potwierdzenie swiadomej decyzji.

---

### K. Ollama local — out of memory

**Objaw:**

```
[OLLAMA] OOM: model deepseek-coder:70b killed by kernel (OOM killer)
[OLLAMA] Error: signal: killed
```

![Screenshot: Blad OOM dla Ollama — log z kernel OOM killer i fallbackiem do mniejszego modelu](screenshots/35_ollama_oom.png)

**Przyczyna:** Model 70B wymaga ponad 40 GB RAM w trybie float16. Na systemach z 16 GB RAM — OOM.

**Rozwiazanie — zmiana modelu na mniejszy:**

Tier routing automatycznie probuje downgradowac do mniejszego modelu. Mozesz tez recznie zmienic konfiguracje:

```ini
# W .env lub agents.yaml — ogranicz do modeli mieszczacych sie w RAM:
# 8 GB RAM: max 8B parametrow (llama3.1:8b, qwen2.5-coder:7b)
# 16 GB RAM: max 13B (phi3.5:14b, deepseek-coder:6.7b)
# 32 GB RAM: max 30B (qwen2.5-coder:32b)
```

**Lub eskalacja do cloud:**

```bash
# Wymus Tier 2 lub Tier 3 (cloud) dla tego zadania
# (edit w .env lub przez feature flag)
OLLAMA_API_BASE=     # puste = Ollama wylaczony, pipeline uzywa cloud
```

---

### L. Cost exceeded (Budget Guard)

**Objaw:** Mieseczny budzet ($50 domyslnie) wyczerpany. Pipeline nie uruchamia nowych requestow do cloud models.

```
[BUDGET_GUARD] EXCEEDED: Daily limit $50.00 reached. LLM calls blocked.
[BUDGET_GUARD] Local Ollama still available.
```

![Screenshot: Ekran zablokowania pipeline przez Budget Guard — budzet przekroczony](screenshots/36_budget_exceeded_lock.png)

**Natychmiastowe opcje:**

1. Czekaj do nastepnego dnia (licznik dzienowy resetuje sie o 00:00 UTC)
2. Admin moze zwiekszyc limit tymczasowo:

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X PATCH http://localhost:8421/api/config/flags/MAX_COST_USD_PER_DAY \
  -d '{"value": 100.0}'
```

3. Lub admin resetuje licznik dzienny (wymaga HumanGate CONFIRMATION):

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -X POST http://localhost:8421/api/cost/reset
```

4. Kontynuuj tylko z Ollama lokalnym (bez cloud):

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/pipeline/run \
  -d '{"upload_id": "upl_XXXXX", "run_type": "full", "council_mode": "local-only"}'
```

---

## 11. Backup + restore drill

### Backup manualny

```bash
# Przez skrypt
bash scripts/backup.sh

# Przez API
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -X POST http://localhost:8421/api/backup/create
```

![Screenshot: Terminal z pomyslnym wynikiem backup.sh — nazwa pliku i rozmiar](screenshots/37_backup_success.png)

Oczekiwany wynik:

```
[BACKUP] Creating SQLite backup...
[BACKUP] WAL checkpoint: OK
[BACKUP] Copy: sylion.db → backups/backup_20260419_082100.sqlite
[BACKUP] Integrity check: OK
[BACKUP] Size: 2.1 MB
[BACKUP] Done. File: ~/sylion/backups/backup_20260419_082100.sqlite
```

### Restore drill (cwiczenie)

Zalecane cwiczenie: co miesiac przetestuj restore na kopii bazy (nie produkcji):

```bash
# 1. Zrob backup biezacy
bash scripts/backup.sh

# 2. Zatrzymaj serwer
systemctl stop sylion-dashboard

# 3. Restore (na sandbox DB)
cp ~/sylion/sylion.db ~/sylion/sylion.db.before_drill
bash rollback.sh --from-backup=backup_20260419_082100.sqlite

# 4. Uruchom i sprawdz
systemctl start sylion-dashboard
curl http://localhost:8421/api/health/ready
# {"status": "ready", ...}

# 5. Jesli OK — przywroc produkcyjna DB
systemctl stop sylion-dashboard
cp ~/sylion/sylion.db.before_drill ~/sylion/sylion.db
systemctl start sylion-dashboard
```

![Screenshot: Output restore drill — wynik rollback.sh z potwierdzeniem integralnosci](screenshots/38_restore_drill_output.png)

---

## 12. Upgrade 5.9.1 do 5.9.2

### Pre-upgrade checklist

Przed upgradeem wykonaj:
- [ ] Backup bazy: `bash scripts/backup.sh`
- [ ] Sprawdz brak oczekujacych HumanGate: `GET /api/humangate/pending`
- [ ] Sprawdz brak aktywnych runow: `GET /api/pipeline/status/active`
- [ ] Zanotuj aktualna wersje schema: `sqlite3 ~/sylion/sylion.db "SELECT value FROM meta WHERE key='schema_version';"`

### Wykonanie upgrade

```bash
# Pobierz nowa wersje
git pull origin main
# lub rozpakuj nowe archiwum ZIP

# Uruchom instalator z flaga upgrade
bash install.sh --upgrade
```

Instalator automatycznie:
1. Tworzy backup bazy przed migracja
2. Instaluje nowe zaleznosci (`pip install -r requirements-lock.txt`)
3. Uruchamia migracje bazy v3→v4
4. Restartuje serwis systemd

![Screenshot: Postep upgradu — install.sh --upgrade z paskiem instalacji zaleznosci i migracji](screenshots/39_upgrade_progress.png)

### Weryfikacja po upgrade

```bash
curl http://localhost:8421/api/health/detailed
# Sprawdz: "version": "5.9.2", "db": {"schema_version": 4}
```

### W przypadku problemu — rollback do 5.9.1

```bash
systemctl stop sylion-dashboard
bash rollback.sh --from-backup=backup_pre_upgrade_XXXXXX.sqlite
# Przywroc stary kod (git checkout v5.9.1 lub rozpakuj stare ZIP)
systemctl start sylion-dashboard
```

---

## 13. Offboarding i Uninstall

### Uninstall z zachowaniem danych

```bash
bash uninstall.sh
# Usuwa: venv/, pliki binarne, serwis systemd
# Zachowuje: ~/sylion/ (baza danych, backupy, logi)
```

### Uninstall z usuniciem wszystkich danych (--purge-data)

```bash
bash uninstall.sh --purge-data
```

**KRYTYCZNE:** `--purge-data` uruchamia HumanGate CRITICAL z pytaniem o potwierdzenie. Usuwa:
- Baze danych `~/sylion/sylion.db` i wszystkie backupy
- Workspace uploads
- Logi
- Klucze API z `.env`

![Screenshot: Modal ostrzezenia uninstall --purge-data — czerwony HumanGate z lista usuwanych danych](screenshots/40_uninstall_warning.png)

```
+==============================================================+
| HUMANGATE #UNINSTALL                      [CRITICAL]         |
| ID: HG-UNINSTALL-PURGE                                       |
|--------------------------------------------------------------|
| Pytanie:                                                     |
|   Prosisz o TRWALE usuniecie wszystkich danych SYLION.       |
|   Operacja jest nieodwracalna. Czy na pewno kontynuowac?     |
|--------------------------------------------------------------|
| Zostanie usuniete:                                           |
|   - ~/sylion/sylion.db (baza danych)                         |
|   - ~/sylion/backups/ (wszystkie backupy)                    |
|   - ~/sylion/workspace_uploads/ (pliki codebase)             |
|   - ~/sylion/logs/ (logi)                                    |
|   - .env (klucze API)                                        |
|--------------------------------------------------------------|
| Opcje:                                                       |
|   [A] Tak — usun wszystkie dane                             |
|   [B] Nie — zachowaj dane, tylko odinstaluj binarki         |
|--------------------------------------------------------------|
| Plan rollbacku: BRAK — operacja nieodwracalna                |
+==============================================================+
```

### RODO — usuniecie danych (Art. 17 DSR)

Jesli offboarding dotyczy konkretnego uzytkownika (nie calej instalacji):

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/users/{user_id}/dsr-delete \
  -d '{"reason": "user request", "purge_immediately": false}'
```

Soft-delete z 30-dniowym oknem (zgodnie z RODO Art. 17 i DSGVO §35). Twarde usuniecie nastapi automatycznie po 30 dniach przez retention scheduler.

---

*Poprzednia sekcja: [05_CELE_I_KPI.md](./05_CELE_I_KPI.md)*
*Nastepna sekcja: [07_TROUBLESHOOTING_FLOWCHART.md](./07_TROUBLESHOOTING_FLOWCHART.md)*
