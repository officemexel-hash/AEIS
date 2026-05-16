<!-- v5.9.1 F-016: --workers 1 jest WYMAGANE — rate limiter (FIX-01) jest in-memory. Dwa workery = dwa niezależne buckety = wspólny bypass. --proxy-headers + --forwarded-allow-ips=127.0.0.1 są WYMAGANE za Caddy (F-002), inaczej rate limiter widzi tylko 127.0.0.1. Entry point to dashboard.app:app, NIE app.main:app (F-007). -->

# SYLION v5.9.0 — Runbook Wdrożeniowy

> **Model:** Opus | **Wersja dokumentu:** 1.0.0 | **Data:** 2025-07-11  
> **Aplikacja:** SYLION v5.9.0 (SQLite + FastAPI, tryb lokalny/VPS)

---

## Spis treści

1. [Wymagania wstępne (Prerequisites)](#1-wymagania-wstępne)
2. [Instalacja z archiwum ZIP — Linux](#2-instalacja-linux)
3. [Instalacja z archiwum ZIP — Windows](#3-instalacja-windows)
4. [Healthcheck po starcie](#4-healthcheck-po-starcie)
5. [Top 10 problemów i rozwiązań](#5-top-10-problemów-i-rozwiązań)
6. [Kontakty i eskalacja](#6-kontakty-i-eskalacja)

---

## 1. Wymagania wstępne

### Minimalne środowisko

| Składnik | Wymagana wersja | Weryfikacja |
|----------|----------------|-------------|
| Python | **3.12 lub wyższa** | `python --version` |   <!-- v5.9.1 F-023 -->
| pip | 23.0+ | `pip --version` |
| venv | wbudowany w Python 3.3+ | `python -m venv --help` |
| SQLite | 3.35+ (z FTS5) | `python -c "import sqlite3; print(sqlite3.sqlite_version)"` |
| cURL | dowolna | `curl --version` |
| Wolne miejsce na dysku | min. 500 MB | `df -h .` |
| RAM | min. 512 MB | — |

### Linux (Debian/Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip curl git unzip
```

### Linux (RHEL/CentOS/Fedora)

```bash
sudo dnf install -y python3.11 python3.11-devel python3-pip curl git unzip
```

### macOS (Homebrew)

```bash
brew install python@3.12 curl  # v5.9.1 F-023
```

### Windows

- Pobierz Python 3.12+ z [python.org/downloads](https://www.python.org/downloads/)
- Zaznacz **"Add Python to PATH"** podczas instalacji
- Zainstaluj [cURL dla Windows](https://curl.se/windows/) lub użyj PowerShell (wbudowany)

---

## 2. Instalacja — Linux

### 2.1. Rozpakowanie archiwum

```bash
# Przenieś archiwum ZIP do katalogu docelowego
mkdir -p /opt/sylion
cp sylion-v5.9.0.zip /opt/sylion/
cd /opt/sylion

# Rozpakuj
unzip sylion-v5.9.0.zip
cd sylion-pipeline
```

### 2.2. Nadaj uprawnienia skryptowi instalacyjnemu

```bash
chmod +x install.sh
```

### 2.3. Uruchom instalator

```bash
./install.sh
```

Instalator wykona automatycznie:
1. Walidację wersji Pythona (min. 3.12)
2. Utworzenie wirtualnego środowiska `.venv`
3. Instalację zależności z `requirements-lock.txt`
4. Inicjalizację bazy danych (`init_db`)
5. Import agentów z `agents.yaml`
6. Weryfikację healthcheck

### 2.4. Uruchomienie serwera (produkcja)

```bash
# Aktywacja środowiska
source .venv/bin/activate

# Uruchomienie aplikacji
uvicorn dashboard.app:app --host 0.0.0.0 --port 8421 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1

# Lub jako serwis systemd (zalecane na VPS):
sudo cp deploy/sylion.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sylion
sudo systemctl start sylion
sudo systemctl status sylion
```


---
<!-- PATCH 3: RUNBOOK_additions inserted here -->
# RUNBOOK_additions.md — SYLION v5.9.1
## Deployment Council Patch — Blokery B-01 / B-02 / B-03

> **Wygenerowany przez:** Deployment Council (subagent fix)  
> **Data:** 2026-04-19  
> **Cel:** Uzupełnienie `LATEST/docs/RUNBOOK_DEPLOY.md` o brakujące sekcje i poprawki  
> **Źródła:** `audit_LATEST/11_deployment.md`, `snapshot_0052/.../RUNBOOK_DEPLOY.md §3.5`

---

## Kontekst — 3 blokery twarde (z `11_deployment.md`)

| ID | Severity | Problem | Fix |
|----|----------|---------|-----|
| **B-01** | CRITICAL | `app.main:app` — paczka `app/` nie istnieje. Systemd unit nie wystartuje. | Zmieniono na `dashboard.app:app` |
| **B-02** | CRITICAL | `--workers 2` łamie in-memory rate limiter; runtime guard odrzuca start. | Zmieniono na `--workers 1` + `--proxy-headers` |
| **B-03** | CRITICAL | Brak sekcji Caddy w LATEST RUNBOOK — operator bez wzorca TLS. | Dodano §3.5 poniżej + dedykowany `Caddyfile` |

---

## §2.5 (ZASTĄPIONY) — Plik `sylion-dashboard.service` (systemd)

> **UWAGA:** Ten blok zastępuje wadliwy przykład z LATEST RUNBOOK §2.5.

```ini
# SYLION v5.9.1 — sylion-dashboard.service
# B-01 FIX: dashboard.app:app (NIE app.main:app)
# B-02 FIX: --workers 1, --proxy-headers, --forwarded-allow-ips=127.0.0.1

[Unit]
Description=SYLION v5.9.1 Dashboard (FastAPI/uvicorn)
Documentation=file:///opt/sylion/sylion-pipeline/docs/RUNBOOK_DEPLOY.md
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=exec
User=sylion
Group=sylion
WorkingDirectory=/opt/sylion/sylion-pipeline
EnvironmentFile=-/etc/sylion/secrets.env
Environment=SYLION_HOME=/var/lib/sylion
ExecStart=/opt/sylion/sylion-pipeline/.venv/bin/uvicorn \
    dashboard.app:app \
    --host 127.0.0.1 \
    --port 8421 \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips=127.0.0.1 \
    --timeout-keep-alive 30
Restart=on-failure
RestartSec=5s
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/sylion
PrivateDevices=yes
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
```

Instalacja:

```bash
sudo cp sylion-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sylion-dashboard
sudo systemctl status sylion-dashboard
```

Weryfikacja poprawności entry point (musi być `dashboard.app:app`):

```bash
systemctl cat sylion-dashboard | grep ExecStart
# Oczekiwane: dashboard.app:app --workers 1 --proxy-headers
```

---

## §3.5 (NOWY) — Caddy reverse proxy (PRODUKCJA, WYMAGANE)

> **B-03 FIX:** Ta sekcja była całkowicie nieobecna w LATEST RUNBOOK.  
> **F-002 (v5.9.1):** Rate limiter logowania (FIX-01) jest **in-memory** i widzi IP klienta
> wyłącznie przez nagłówki `X-Forwarded-For`. Uvicorn MUSI być uruchomiony z
> `--proxy-headers --forwarded-allow-ips=127.0.0.1`, a reverse proxy MUSI wstrzykiwać
> `X-Forwarded-For` i `X-Real-IP`. Bez tego rate limiter widzi tylko `127.0.0.1` dla
> wszystkich klientów — pierwszy zablokowany atakujący blokuje legitnych użytkowników.

### §3.5.1 — Instalacja Caddy

```bash
# Metoda 1: Oficjalne repozytorium Caddy (zalecane — zawsze aktualna wersja)
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

# Metoda 2: apt z repozytoriów Ubuntu/Debian (starsza wersja, wystarczy dla prod)
sudo apt install -y caddy

# Weryfikacja
caddy version
```

### §3.5.2 — Lokalizacja konfiguracji

```
/etc/caddy/Caddyfile        ← główny plik konfiguracyjny
/var/log/caddy/             ← logi dostępu (JSON format)
/var/lib/caddy/             ← certyfikaty Let's Encrypt (auto-managed)
```

### §3.5.3 — Caddyfile (produkcja)

Skopiuj gotowy plik z artefaktu `Caddyfile` (ten sam katalog co RUNBOOK_additions.md):

```bash
sudo cp Caddyfile /etc/caddy/Caddyfile
# Podmień email i hasło basicauth przed prod — patrz komentarze w pliku
```

Pełna treść `/etc/caddy/Caddyfile`:

```caddyfile
sylion.example.com {
    # Automatyczny TLS od Let's Encrypt (ACME)
    # ZMIEŃ email na swój przed deploymentem prod
    tls admin@example.com

    # Nagłówki bezpieczeństwa (OWASP baseline)
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options    "nosniff"
        X-Frame-Options           "DENY"
        Referrer-Policy           "same-origin"
        Permissions-Policy        "geolocation=(), microphone=(), camera=()"
        Content-Security-Policy   "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:"
        -Server
    }

    # Logi dostępu JSON
    log {
        output file /var/log/caddy/sylion_access.log {
            roll_size    100MiB
            roll_keep    10
            roll_keep_for 720h
        }
        format json
    }

    # Ochrona Prometheus scrape — basicauth
    # Wygeneruj hash: caddy hash-password
    handle /api/metrics {
        basicauth {
            prometheus $2a$14$Zkx19XLiW6VYouLHR5NmfOFU0z2GTNmpkT/5hnNE12P3Ui.SqVvzG
        }
        reverse_proxy 127.0.0.1:8421
    }

    # Reverse proxy do uvicorn (dashboard.app:app)
    reverse_proxy 127.0.0.1:8421 {
        # Obowiązkowe dla rate limitera (FIX-01 / B-02)
        header_up X-Real-IP         {remote_host}
        header_up X-Forwarded-For   {remote_host}
        header_up X-Forwarded-Proto {scheme}
        header_up X-Forwarded-Host  {host}

        # Backend healthcheck
        health_uri      /api/health
        health_interval 30s
        health_timeout  5s

        # Timeouts dla batch processing (PDF)
        transport http {
            dial_timeout             10s
            response_header_timeout  120s
            read_timeout             300s
            write_timeout            300s
        }
    }

    request_body { max_size 100MB }
}

www.sylion.example.com {
    redir https://sylion.example.com{uri} permanent
}
```

### §3.5.4 — Start i enable Caddy

```bash
# Walidacja konfiguracji (obowiązkowe przed restartem)
sudo caddy validate --config /etc/caddy/Caddyfile

# Włącz i uruchom jako serwis systemd
sudo systemctl enable --now caddy

# Weryfikacja statusu
sudo systemctl status caddy

# Reload po zmianach (bez restartu — zachowuje certyfikaty i połączenia)
caddy reload --config /etc/caddy/Caddyfile
# lub
sudo systemctl reload caddy
```

### §3.5.5 — Firewall (ufw) — KRYTYCZNE

> **B-03:** Port 8421 MUSI być zablokowany z zewnątrz. Jeśli jest otwarty, atakujący
> omija Caddy i bezpośrednio trafia do uvicorn — co omija rate limiter (FIX-01).

```bash
sudo ufw allow 22/tcp    # SSH — SPRAWDŹ przed enable!
sudo ufw allow 80/tcp    # HTTP (ACME challenge + redirect do HTTPS)
sudo ufw allow 443/tcp   # HTTPS (główny ruch przez Caddy)
sudo ufw deny  8421/tcp  # Blokada bezpośredniego dostępu do uvicorn z zewnątrz
sudo ufw enable
sudo ufw status verbose
```

### §3.5.6 — Weryfikacja nagłówków (KRYTYCZNE dla FIX-01 / B-02)

Z zewnątrz (z innej maszyny niż VPS):

```bash
# 1. Healthcheck przez Caddy (HTTPS)
curl -sf https://sylion.example.com/api/health

# 2. Sprawdź nagłówki bezpieczeństwa
curl -sI https://sylion.example.com | grep -E "Strict|X-Content|X-Frame|Referrer|Permissions"

# 3. Test rate limitera (6 prób logowania — 6. musi zwrócić 429)
for i in {1..6}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
       -X POST https://sylion.example.com/api/login \
       -H "Content-Type: application/x-www-form-urlencoded" \
       -d "username=test&password=bad$i"
done
# Oczekiwane: 401, 401, 401, 401, 401, 429

# Jeśli 6. nie zwraca 429 → X-Forwarded-For nie jest wstrzykiwany poprawnie
# → sprawdź sekcję header_up w Caddyfile i --proxy-headers w systemd
```

### §3.5.7 — Diagnostyka Caddy (operacyjna)

```bash
# Status i ostatnie logi
sudo systemctl status caddy
journalctl -u caddy -n 100 --no-pager | grep -E "error|502|503|504"

# Logi dostępu JSON (czytelne)
tail -50 /var/log/caddy/sylion_access.log | python3 -m json.tool 2>/dev/null \
    | grep -E "status|uri|remote_ip"

# Certyfikaty Let's Encrypt (sprawdź daty wygaśnięcia)
ls -la /var/lib/caddy/.local/share/caddy/certificates/
# lub
caddy list-certificates 2>/dev/null

# Walidacja konfiguracji po zmianach
sudo caddy validate --config /etc/caddy/Caddyfile
```

---

## §7 (NOWY) — Deployment Checklist (Pre-Deploy Council)

> **Cel:** 16-punktowa lista kontrolna do wykonania przez SRE przed każdym deploymentem
> produkcyjnym SYLION v5.9.1. Każdy punkt musi mieć status ✅ PASS zanim wydana zostanie
> zgoda na `systemctl start sylion-dashboard`.

### Pre-Deploy Checklist v5.9.1

```
Operator: _______________  Data: _______________  Wersja: v5.9.1
```

| # | Kontrola | Komenda weryfikacji | Status |
|---|---------|--------------------|----|
| **1** | Entry point to `dashboard.app:app` (NIE `app.main:app`) | `systemctl cat sylion-dashboard \| grep ExecStart` | ☐ |
| **2** | `--workers 1` w ExecStart | `systemctl cat sylion-dashboard \| grep workers` | ☐ |
| **3** | `--proxy-headers --forwarded-allow-ips=127.0.0.1` w ExecStart | `systemctl cat sylion-dashboard \| grep proxy` | ☐ |
| **4** | User=sylion, Group=sylion, WorkingDirectory=/opt/sylion/sylion-pipeline | `systemctl show sylion-dashboard \| grep -E "User\|Group\|Working"` | ☐ |
| **5** | `NoNewPrivileges=yes` w unit file | `systemctl show sylion-dashboard \| grep NoNewPriv` | ☐ |
| **6** | `PrivateTmp=yes`, `ProtectSystem=strict` | `systemctl show sylion-dashboard \| grep -E "PrivateTmp\|ProtectSys"` | ☐ |
| **7** | `ReadWritePaths=/var/lib/sylion` (katalog istnieje, właściciel sylion) | `ls -la /var/lib/sylion` | ☐ |
| **8** | Caddy: `/etc/caddy/Caddyfile` waliduje się bez błędów | `sudo caddy validate --config /etc/caddy/Caddyfile` | ☐ |
| **9** | Caddy: email w TLS nie jest `admin@example.com` | `grep tls /etc/caddy/Caddyfile` | ☐ |
| **10** | Caddy: hasło basicauth `/api/metrics` zmienione (nie domyślne `changeme`) | `grep prometheus /etc/caddy/Caddyfile` (hash różny od przykładu) | ☐ |
| **11** | Firewall: port 8421 zablokowany z zewnątrz | `sudo ufw status \| grep 8421` → musi być DENY | ☐ |
| **12** | Firewall: porty 22, 80, 443 otwarte | `sudo ufw status \| grep -E "22\|80\|443"` | ☐ |
| **13** | Backend odpowiada lokalnie przed włączeniem Caddy | `curl -sf http://127.0.0.1:8421/api/health` → `{"status":"healthy"}` | ☐ |
| **14** | HTTPS działa przez Caddy po starcie | `curl -sf https://sylion.example.com/api/health` | ☐ |
| **15** | Rate limiter działa (6. żądanie logowania = HTTP 429) | Test z §3.5.6 — 6 prób, ostatnia = 429 | ☐ |
| **16** | `journalctl -u sylion-dashboard -n 20` — brak ERROR/FATAL | `journalctl -u sylion-dashboard -n 20 --no-pager \| grep -iE "error\|fatal\|traceback"` → brak wyników | ☐ |

**Warunek GO:** Wszystkie 16 punktów = ✅ PASS.  
**Warunek NO-GO:** Jakikolwiek punkt ☐ lub ❌ = wstrzymaj deploy, eskaluj do SRE.

---

## Podsumowanie zmian (diff względem LATEST RUNBOOK_DEPLOY.md)

| Sekcja | Zmiana | Bloker |
|--------|--------|--------|
| §2.5 | `app.main:app` → `dashboard.app:app` | B-01 |
| §2.5 | `--workers 2` → `--workers 1` | B-02 |
| §2.5 | Dodano `--proxy-headers --forwarded-allow-ips=127.0.0.1` | B-02 |
| §2.5 | Dodano hardening: `Group`, `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`, `ReadWritePaths`, `CapabilityBoundingSet` | M-02 |
| §2.5 | Dodano `StartLimitBurst=5`, `StartLimitIntervalSec=60` | M-01 |
| §3.5 | Nowa sekcja — Caddy setup: instalacja, Caddyfile, start, firewall, weryfikacja, diagnostyka | B-03 |
| §7 | Nowa sekcja — Deployment Checklist 16 punktów | — |

---

*Wygenerowane przez Deployment Council fix subagent — SYLION v5.9.1*  
*Data: 2026-04-19*  
*Artefakty wyjściowe: `sylion-dashboard.service`, `Caddyfile`, `RUNBOOK_additions.md`*

---

### 2.5. Plik `sylion.service` (przykład dla systemd)

```ini
[Unit]
Description=SYLION v5.9.0 FastAPI Service
After=network.target

[Service]
Type=exec
User=sylion
WorkingDirectory=/opt/sylion/sylion-pipeline
ExecStart=/opt/sylion/sylion-pipeline/.venv/bin/uvicorn dashboard.app:app --host 127.0.0.1 --port 8421 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 3. Instalacja — Windows

### 3.1. Rozpakowanie archiwum

Kliknij prawym przyciskiem na `sylion-v5.9.0.zip` → **Wyodrębnij wszystko** do `C:\sylion\`  
lub użyj PowerShell:

```powershell
Expand-Archive -Path "sylion-v5.9.0.zip" -DestinationPath "C:\sylion\" -Force
cd C:\sylion\sylion-pipeline
```

### 3.2. Uruchomienie instalatora

Otwórz **Wiersz polecenia** (`cmd.exe`) jako Administrator:

```cmd
cd C:\sylion\sylion-pipeline
install.bat
```

### 3.3. Uruchomienie serwera

```cmd
.venv\Scripts\activate
uvicorn dashboard.app:app --host 0.0.0.0 --port 8421 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
```

Aby uruchomić jako usługę Windows, użyj [NSSM](https://nssm.cc/):

```cmd
nssm install SYLION "C:\sylion\sylion-pipeline\.venv\Scripts\uvicorn.exe" "app.main:app --host 0.0.0.0 --port 8421"
nssm start SYLION
```

---

## 3.5. Caddy reverse proxy (PRODUKCJA, WYMAGANE)

> **F-002 (v5.9.1):** Rate limiter loginów (FIX-01) jest **in-memory** i widzi IP klienta wyłącznie
> przez nagłówki `X-Forwarded-For`. Uvicorn MUSI być uruchomiony z `--proxy-headers
> --forwarded-allow-ips=127.0.0.1`, a reverse proxy MUSI wstrzykiwać `X-Forwarded-For`
> i `X-Real-IP`. Bez tego rate limiter widzi tylko `127.0.0.1` dla wszystkich klientów —
> pierwszy zablokowany atakujący blokuje legitnych użytkowników.

### 3.5.1. Instalacja Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

### 3.5.2. Caddyfile (produkcja, PROD VPS Tailor 178.104.205.119)

Ścieżka: `/etc/caddy/Caddyfile`

```caddyfile
# SYLION v5.9.1 — produkcyjna konfiguracja reverse proxy
# Założenia:
#   - uvicorn nasłuchuje lokalnie na 127.0.0.1:8421 z --proxy-headers
#     --forwarded-allow-ips=127.0.0.1
#   - domena wskazuje na VPS 178.104.205.119 (A record)
#   - Let's Encrypt TLS obsługiwane automatycznie przez Caddy

sylion.example.com {
    # Automatyczny TLS od Let's Encrypt (ACME)
    # Podmień email na swój adres dla powiadomień wygaśnięcia certa
    tls admin@example.com

    # Nagłówki bezpieczeństwa (OWASP baseline)
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options    "nosniff"
        X-Frame-Options           "DENY"
        Referrer-Policy           "strict-origin-when-cross-origin"
        Permissions-Policy        "geolocation=(), camera=(), microphone=()"
        -Server
    }

    # Logi w formacie JSON (parsowalne przez journalctl/loki)
    log {
        output file /var/log/caddy/sylion_access.log {
            roll_size 100MiB
            roll_keep 10
            roll_keep_for 720h
        }
        format json
    }

    # Reverse proxy do uvicorn (dashboard.app:app)
    reverse_proxy 127.0.0.1:8421 {
        # Obowiązkowe nagłówki dla rate limitera (FIX-01, F-002)
        header_up X-Real-IP           {remote_host}
        header_up X-Forwarded-For     {remote_host}
        header_up X-Forwarded-Proto   {scheme}
        header_up X-Forwarded-Host    {host}

        # Healthcheck backendu — Caddy sam wycofa 502 jeśli backend padnie
        health_uri    /api/health
        health_interval 10s
        health_timeout  5s

        # Timeout dla długich operacji (analiza dokumentów, batch processing)
        transport http {
            dial_timeout      10s
            response_header_timeout 120s
            read_timeout      300s
            write_timeout     300s
        }
    }

    # Ograniczenie rozmiaru request body (upload dokumentów do analizy)
    request_body {
        max_size 100MB
    }
}

# Opcjonalnie: redirect www → apex
www.sylion.example.com {
    redir https://sylion.example.com{uri} permanent
}
```

### 3.5.3. Walidacja i restart

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy
```

### 3.5.4. Weryfikacja nagłówków (KRYTYCZNE dla F-002)

Z zewnątrz (z innej maszyny):

```bash
# 1. Healthcheck przez Caddy
curl -sf https://sylion.example.com/api/health

# 2. Sprawdź czy backend widzi prawdziwe IP klienta
#    (w logach dashboard.app powinno być IP Twoje, NIE 127.0.0.1)
tail -f /var/log/sylion/app.log | grep -i "rate_limit\|login"

# 3. Test: 6 prób logowania z błędnym hasłem
for i in {1..6}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
       -X POST https://sylion.example.com/api/login \
       -H "Content-Type: application/x-www-form-urlencoded" \
       -d "username=test&password=bad$i"
done
# Oczekiwane: 401, 401, 401, 401, 401, 429  (6. request = rate limit)
```

Jeśli 6. żądanie nie zwraca 429 — konfiguracja nagłówków `X-Forwarded-For` jest
nieprawidłowa. Sprawdź sekcję `header_up` w Caddyfile i flagi `--proxy-headers
--forwarded-allow-ips=127.0.0.1` w systemd (sekcja 2.4).

### 3.5.5. Firewall (ufw)

```bash
sudo ufw allow 22/tcp       # SSH
sudo ufw allow 80/tcp       # HTTP (ACME challenge + redirect)
sudo ufw allow 443/tcp      # HTTPS
sudo ufw deny  8421/tcp     # Blokuj bezpośredni dostęp do uvicorn z zewnątrz
sudo ufw enable
sudo ufw status verbose
```

> **Ważne:** port `8421` MUSI być zablokowany z zewnątrz. Ruch wchodzi wyłącznie
> przez Caddy (443). Jeśli `8421` jest otwarty, atakujący ominie rate limiter.

---

## 4. Healthcheck po starcie

### 4.1. Szybka weryfikacja (Linux/macOS)

```bash
curl -sf http://127.0.0.1:8421/api/health && echo "OK" || echo "FAIL"
```

Oczekiwana odpowiedź:
```json
{
  "status": "healthy",
  "version": "5.9.0",
  "db": "connected",
  "agents_loaded": true
}
```

### 4.2. Weryfikacja Windows (PowerShell)

```powershell
$r = Invoke-RestMethod -Uri "http://127.0.0.1:8421/api/health"
if ($r.status -eq "healthy") { Write-Host "OK" } else { Write-Host "FAIL" }
```

### 4.3. Weryfikacja Windows (curl.exe)

```cmd
curl.exe -sf http://127.0.0.1:8421/api/health
```

### 4.4. Szczegółowy healthcheck (API)

| Endpoint | Opis |
|----------|------|
| `GET /api/health` | Ogólny status aplikacji |
| `GET /api/health/db` | Status połączenia z SQLite |
| `GET /api/agents` | Lista załadowanych agentów |
| `GET /api/version` | Wersja aplikacji |

---

## 5. Top 10 problemów i rozwiązań

---

### Problem 1: `python: command not found` / `python3: command not found`

**Objawy:** Skrypt install.sh/bat kończy się błędem przy weryfikacji Pythona.

**Rozwiązanie Linux:**
```bash
# Sprawdź czy Python 3.12 jest dostępny pod inną nazwą
which python3.11 || which python3 || which python

# Utwórz alias jeśli potrzeba
sudo ln -sf /usr/bin/python3.11 /usr/local/bin/python
```

**Rozwiązanie Windows:**  
Reinstaluj Python 3.12 zaznaczając **"Add Python to PATH"**.  
Zrestartuj cmd.exe po instalacji.

---

### Problem 2: Wersja Pythona < 3.12

**Objawy:** `Python 3.9.x detected. Minimum required: 3.12`

**Rozwiązanie:**
```bash
# Linux — instalacja Python 3.12 (Ubuntu 22.04+)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv

# Uruchom ponownie z jawnym wskazaniem interpretera
PYTHON_BIN=python3.11 ./install.sh
```

---

### Problem 3: Błąd `pip install` — brak internetu / prywatne PyPI

**Objawy:** `Could not find a version that satisfies the requirement ...`

**Rozwiązanie:**
```bash
# Opcja A: Instalacja z bundled wheels (jeśli dostępny katalog wheels/)
pip install --no-index --find-links=./wheels -r requirements-lock.txt

# Opcja B: Konfiguracja proxy korporacyjnego
pip install --proxy http://proxy.firma.pl:8080 -r requirements-lock.txt

# Opcja C: Zaufane hosty dla self-hosted PyPI
pip install --trusted-host pypi.firma.pl --index-url https://pypi.firma.pl/simple -r requirements-lock.txt
```

---

### Problem 4: Błąd `Permission denied` przy tworzeniu venv lub pisaniu do katalogu

**Objawy:** `OSError: [Errno 13] Permission denied: '.venv'`

**Rozwiązanie Linux:**
```bash
# Zmień właściciela katalogu
sudo chown -R $USER:$USER /opt/sylion
# LUB instaluj w katalogu home
mkdir -p ~/sylion && cd ~/sylion
```

**Rozwiązanie Windows:**  
Uruchom `cmd.exe` jako Administrator.

---

### Problem 5: SQLite — błąd inicjalizacji DB (`init_db` fail)

**Objawy:** `OperationalError: no such table: agents` lub `database is locked`

**Rozwiązanie:**
```bash
# Sprawdź czy baza istnieje i nie jest uszkodzona
python -c "import sqlite3; conn = sqlite3.connect('sylion.db'); print('OK')"

# Zresetuj bazę danych (UWAGA: utrata danych!)
rm -f sylion.db
python -m app.db.init_db

# Sprawdź uprawnienia do pliku
ls -la sylion.db
chmod 660 sylion.db
```

---

### Problem 6: Port 8421 jest zajęty

**Objawy:** `ERROR: [Errno 98] Address already in use`

**Rozwiązanie Linux:**
```bash
# Znajdź proces zajmujący port
ss -tlnp | grep 8421
lsof -i :8421

# Zabij proces
kill -9 $(lsof -t -i:8421)

# Lub zmień port w konfiguracji
SYLION_PORT=8422 ./install.sh
```

**Rozwiązanie Windows:**
```cmd
netstat -ano | findstr :8421
taskkill /PID <PID> /F
```

---

### Problem 7: `agents.yaml` — błąd parsowania / agenci nie ładują się

**Objawy:** `YAMLError: ...` lub `agents_loaded: false` w healthcheck

**Rozwiązanie:**
```bash
# Walidacja składni YAML
python -c "import yaml; yaml.safe_load(open('agents.yaml'))"

# Sprawdź kodowanie pliku (musi być UTF-8)
file agents.yaml
# Konwersja jeśli potrzeba
iconv -f WINDOWS-1250 -t UTF-8 agents.yaml > agents_utf8.yaml
mv agents_utf8.yaml agents.yaml

# Manualne seedowanie agentów
source .venv/bin/activate
python -m app.agents.seed --file agents.yaml --force
```

---

### Problem 8: FastAPI nie odpowiada — aplikacja zawieszona

**Objawy:** cURL zawiesza się, brak odpowiedzi z `/api/health`

**Rozwiązanie:**
```bash
# Sprawdź logi aplikacji
journalctl -u sylion -n 50 --no-pager
tail -f logs/sylion.log

# Sprawdź czy proces działa
ps aux | grep uvicorn

# Restart serwisu
sudo systemctl restart sylion

# Sprawdź zużycie zasobów
top -p $(pgrep -f uvicorn)
free -h
df -h
```

---

### Problem 9: Błąd SSL/TLS przy healthcheck (HTTPS)

**Objawy:** `SSL: CERTIFICATE_VERIFY_FAILED`

**Rozwiązanie:**
```bash
# Tymczasowo pomiń weryfikację SSL (tylko debugging!)
curl -sk https://127.0.0.1:8421/api/health

# Prawidłowe rozwiązanie — dostarcz certyfikat CA
curl --cacert /etc/ssl/certs/firma-ca.crt https://sylion.firma.pl/api/health

# Konfiguracja uvicorn z SSL
uvicorn app.main:app --ssl-keyfile=ssl/key.pem --ssl-certfile=ssl/cert.pem --port 8421
```

---

### Problem 10: `requirements-lock.txt` — konflikty wersji / hash mismatch

**Objawy:** `THESE PACKAGES DO NOT MATCH THE HASHES` lub `ResolutionImpossible`

**Rozwiązanie:**
```bash
# Sprawdź integralność pliku requirements
sha256sum requirements-lock.txt

# Wymuś reinstalację ignorując cache
pip install --no-cache-dir -r requirements-lock.txt

# Jeśli hash mismatch — pobierz paczki ponownie (środowisko deweloperskie)
pip download -r requirements-lock.txt -d ./wheels/

# Sprawdź wersję pip (musi być >= 23.0)
pip install --upgrade pip
pip --version
```

---

## 6. Kontakty i eskalacja

| Poziom | Kontakt | Zakres |
|--------|---------|--------|
| L1 | ops@firma.pl | Problemy instalacyjne, konfiguracja środowiska |
| L2 | dev@sylion.io | Błędy aplikacji, problemy z bazą danych |
| L3 | cto@sylion.io | Bezpieczeństwo, awarie krytyczne |

**Eskalacja:** Wszystkie incydenty krytyczne (aplikacja niedostępna > 15 min) raportować przez system ticketowy z priorytetem P1.

---

*Dokument wygenerowany przez Deployment Council SYLION v5.9.0 — model Opus*  
*Ostatnia aktualizacja: 2025-07-11*
