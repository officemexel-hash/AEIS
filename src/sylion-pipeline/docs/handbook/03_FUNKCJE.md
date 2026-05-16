# Funkcje uzytkownika — SYLION Pipeline v5.9.2

Ten dokument opisuje wszystkie funkcje dostepne przez dashboard API i interfejs uzytkownika. Dla kazdej funkcji podane sa: endpoint, wymagana rola, opis, parametry, przyklad i mozliwe bledy.

---

## Spis tresci

1. [Autoryzacja i sesja](#1-autoryzacja-i-sesja)
2. [Upload codebase](#2-upload-codebase)
3. [Uruchomienie audytu codebase](#3-uruchomienie-audytu-codebase)
4. [Monitorowanie uruchomienia](#4-monitorowanie-uruchomienia)
5. [HumanGate — interakcja](#5-humangate--interakcja)
6. [Diagnostyka v2](#6-diagnostyka-v2)
7. [Pixel 9 provisioning](#7-pixel-9-provisioning)
8. [Mudi router provisioning](#8-mudi-router-provisioning)
9. [Feature flags admin](#9-feature-flags-admin)
10. [Budget tracking](#10-budget-tracking)
11. [Backup i restore](#11-backup-i-restore)
12. [Rollback do poprzedniej wersji](#12-rollback-do-poprzedniej-wersji)

---

## Role dostepowe

| Rola     | Opis                                                    |
|----------|---------------------------------------------------------|
| guest    | Brak autoryzacji — dostep tylko do endpointow publicznych |
| user     | Zalogowany uzytkownik — audyty, monitoring, HumanGate  |
| operator | user + provisioning urzadzen, restart pipeline          |
| admin    | operator + zarzadzanie kontami, feature flags, backup   |

---

## 1. Autoryzacja i sesja

### 1.1 Rejestracja administratora (setup)

**Endpoint:** `POST /api/auth/setup`
**Rola:** guest (tylko podczas pierwszej konfiguracji)

Tworzy pierwsze konto administratora. Wymaga setup tokenu wyswietlonego przy starcie serwera.

**Parametry:**

```json
{
  "setup_token": "XXXX-XXXX-XXXX-XXXX",
  "username": "admin",
  "password": "silne-haslo-min-12-znakow"
}
```

**Przyklad curl:**

```bash
curl -X POST http://localhost:8421/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"setup_token":"XXXX-XXXX","username":"admin","password":"MojeHaslo123!"}'
```

**Odpowiedz:**

```json
{"status": "ok", "message": "Admin account created"}
```

**Bledy:**

| Kod | Opis                                |
|-----|-------------------------------------|
| 400 | Niepoprawne dane (np. brak hasla)   |
| 403 | Bledny setup token                  |
| 409 | Konto administratora juz istnieje   |

---

### 1.2 Logowanie

**Endpoint:** `POST /api/auth/login`
**Rola:** guest

**Parametry:**

```json
{
  "username": "admin",
  "password": "haslo"
}
```

**Przyklad curl:**

```bash
curl -c cookies.txt -X POST http://localhost:8421/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"MojeHaslo123!"}'
```

**Odpowiedz:**

```json
{
  "status": "ok",
  "username": "admin",
  "role": "admin",
  "csrf_token": "abc123..."
}
```

Sesja przechowywana w HttpOnly cookie. Token CSRF zwrocony w odpowiedzi — wymagany dla wszystkich pozniejszych mutujacych zadan.

**Bledy:**

| Kod | Opis                              |
|-----|-----------------------------------|
| 401 | Bledne haslo lub login            |
| 429 | Rate limit (5 prob / 5 min)       |
| 503 | Baza danych niedostepna (retry)   |

---

### 1.3 Wylogowanie

**Endpoint:** `POST /api/auth/logout`
**Rola:** user

```bash
curl -b cookies.txt -X POST http://localhost:8421/api/auth/logout \
  -H "X-CSRF-Token: abc123..."
```

Usuwa sesje z bazy, unieazymnia cookie i rotuje CSRF token.

---

### 1.4 CSRF token

**Endpoint:** `GET /api/auth/csrf-token`
**Rola:** user

Zwraca aktualny token CSRF dla sesji. Uzyteczny przy SPA po odswiezeniu strony.

```bash
curl -b cookies.txt http://localhost:8421/api/auth/csrf-token
# {"csrf_token": "abc123..."}
```

---

### 1.5 Status autoryzacji

**Endpoint:** `GET /api/auth/status`
**Rola:** guest

```bash
curl http://localhost:8421/api/auth/status
# {"authenticated": false, "needs_setup": true}
# lub
# {"authenticated": true, "username": "admin", "role": "admin"}
```

---

## 2. Upload codebase

**Endpoint:** `POST /api/pipeline/upload`
**Rola:** user

Uploaduje codebase do analizy. Dwie metody: ZIP lub Git URL.

### 2a. Upload ZIP

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -F "file=@myproject.zip" \
  http://localhost:8421/api/pipeline/upload
```

**Ograniczenia ZIP:**
- Maksymalny rozmiar: 100 MB (konfigurowalny)
- Dozwolone MIME: `application/zip`, `application/x-zip-compressed`
- Brak path traversal (walidacja kazdej sciezki w archiwum)
- Brak plikow .env, .git z sekretami (automatyczna redakcja)

### 2b. Upload przez Git URL

```json
{
  "git_url": "https://github.com/org/repo.git",
  "branch": "main",
  "depth": 1
}
```

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/pipeline/upload-git \
  -d '{"git_url":"https://github.com/org/repo.git","branch":"main"}'
```

**Odpowiedz:**

```json
{
  "upload_id": "upl_20260419_abc123",
  "status": "uploaded",
  "files_count": 47,
  "size_bytes": 2048576
}
```

**Bledy:**

| Kod | Opis                                          |
|-----|-----------------------------------------------|
| 400 | Zly MIME, path traversal wykryty, za duzy plik |
| 413 | Plik za duzy (> limit)                        |
| 422 | Niepoprawny Git URL lub niedostepne repo       |

---

## 3. Uruchomienie audytu codebase

**Endpoint:** `POST /api/pipeline/run`
**Rola:** user

Uruchamia pelny audyt codebase. Wymaga wczesniejszego uploadu (lub podania upload_id).

**Parametry:**

```json
{
  "upload_id": "upl_20260419_abc123",
  "run_type": "full",
  "council_mode": "auto",
  "dry_run": false
}
```

| Parametr       | Wartosci                     | Opis                                       |
|----------------|------------------------------|--------------------------------------------|
| `upload_id`    | string                       | ID z poprzedniego uploadu                  |
| `run_type`     | `full`, `modules`, `security-only` | Zakres audytu                      |
| `council_mode` | `auto`, `force`, `skip`      | auto = wg tier_routing, force = zawsze rada |
| `dry_run`      | true/false                   | true = symulacja, brak zmian w workspace   |

**Przyklad Python:**

```python
import requests

session = requests.Session()
session.post("http://localhost:8421/api/auth/login",
             json={"username": "admin", "password": "haslo"})

csrf = session.get("http://localhost:8421/api/auth/csrf-token").json()["csrf_token"]

resp = session.post(
    "http://localhost:8421/api/pipeline/run",
    headers={"X-CSRF-Token": csrf},
    json={
        "upload_id": "upl_20260419_abc123",
        "run_type": "full",
        "council_mode": "auto",
        "dry_run": False
    }
)
run = resp.json()
print("Run ID:", run["run_id"])
```

**Odpowiedz:**

```json
{
  "run_id": "run_20260419_xyz789",
  "status": "started",
  "estimated_duration_s": 180,
  "council_mode": "auto",
  "tier": "PREMIUM"
}
```

**Bledy:**

| Kod | Opis                                          |
|-----|-----------------------------------------------|
| 404 | Nie znaleziono upload_id                      |
| 409 | Inny run juz jest aktywny                     |
| 429 | Budget Guard — dzienny limit przekroczony     |

---

## 4. Monitorowanie uruchomienia

### 4.1 Status runu

**Endpoint:** `GET /api/pipeline/status/{run_id}`
**Rola:** user

```bash
curl -b cookies.txt http://localhost:8421/api/pipeline/status/run_20260419_xyz789
```

```json
{
  "run_id": "run_20260419_xyz789",
  "status": "running",
  "current_stage": "stage_2_council",
  "iteration": 3,
  "progress_pct": 42,
  "elapsed_s": 78,
  "cost_usd": 0.34,
  "humangate_pending": false
}
```

### 4.2 SSE streaming iteracji

**Endpoint:** `GET /api/pipeline/stream/{run_id}`
**Rola:** user

Server-Sent Events — strumien zdarzen w czasie rzeczywistym.

```bash
curl -b cookies.txt -N http://localhost:8421/api/pipeline/stream/run_20260419_xyz789
```

Format zdarzen SSE:

```
data: {"event":"iteration_start","iteration":1,"stage":"stage_1_prepare","ts":"2026-04-19T12:00:01Z","correlation_id":"abc123"}

data: {"event":"council_vote","model":"claude-opus-4-7","verdict":"PASS","confidence":0.97,"ts":"2026-04-19T12:00:15Z"}

data: {"event":"humangate_triggered","gate_id":"HG-2026041901-a3f2","priority":"CRITICAL","ts":"2026-04-19T12:00:32Z"}

data: {"event":"run_complete","status":"success","findings_count":7,"cost_usd":1.23,"ts":"2026-04-19T12:03:44Z"}
```

### 4.3 Wyniki runu

**Endpoint:** `GET /api/pipeline/results/{run_id}`
**Rola:** user

```bash
curl -b cookies.txt http://localhost:8421/api/pipeline/results/run_20260419_xyz789
```

Zwraca JSON z pelnym raportem: findings, consensus votes, HumanGate history, cost breakdown, diff summary.

### 4.4 Pobieranie raportu ZIP

**Endpoint:** `GET /api/pipeline/download/{run_id}`
**Rola:** user

```bash
curl -b cookies.txt -o raport.zip \
  http://localhost:8421/api/pipeline/download/run_20260419_xyz789
```

ZIP zawiera: `report.html`, `findings.json`, `diff.patch`, `audit_log.csv`.

---

## 5. HumanGate — interakcja

### 5.1 Lista oczekujacych bramek

**Endpoint:** `GET /api/humangate/pending`
**Rola:** user

```bash
curl -b cookies.txt http://localhost:8421/api/humangate/pending
```

```json
{
  "pending": [
    {
      "gate_id": "HG-2026041901-a3f2",
      "priority": "CRITICAL",
      "type": "CONFIRMATION",
      "question": "Rada 3/4 zatwierdzila migracje DB v3->v4...",
      "expires_at": "2026-04-19T14:30:00Z",
      "run_id": "run_20260419_xyz789"
    }
  ]
}
```

### 5.2 Odpowiedz na HumanGate

**Endpoint:** `POST /api/humangate/{gate_id}/answer`
**Rola:** user

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/humangate/HG-2026041901-a3f2/answer \
  -d '{"option": "A", "comment": "Zatwierdzam — shadow DB test zaliczony"}'
```

**Parametry:**

| Pole      | Opis                                                |
|-----------|-----------------------------------------------------|
| `option`  | Litera opcji z pola "Opcje" w HumanGate (A/B/C/D)  |
| `comment` | Opcjonalny komentarz operatora (max 500 znakow)     |

**Odpowiedz:**

```json
{"status": "ok", "gate_id": "HG-2026041901-a3f2", "decision": "A", "pipeline": "resumed"}
```

### 5.3 Odrzucenie / Abort

**Endpoint:** `POST /api/humangate/{gate_id}/reject`
**Rola:** user

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -X POST http://localhost:8421/api/humangate/HG-2026041901-a3f2/reject
```

Pipeline zostaje zatrzymany (NO-GO). Generowany raport z powodem.

### 5.4 Restart wygaslej bramki

**Endpoint:** `POST /api/humangate/{gate_id}/restart`
**Rola:** user

Uzywany gdy HumanGate wygasl (> 30 min bez odpowiedzi). Pipeline jest PAUSED — restart wznawia oczekiwanie z nowym licznikiem 30 minut.

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -X POST http://localhost:8421/api/humangate/HG-2026041901-a3f2/restart
```

### 5.5 Historia bramek

**Endpoint:** `GET /api/humangate/history`
**Rola:** operator

```bash
curl -b cookies.txt \
  "http://localhost:8421/api/humangate/history?limit=20&status=all"
```

---

## 6. Diagnostyka v2

### 6.1 Liveness probe

**Endpoint:** `GET /api/health/live`
**Rola:** guest

```bash
curl http://localhost:8421/api/health/live
# {"status": "ok", "version": "5.9.2"}
# HTTP 200 = alive
# HTTP 503 = aplikacja startuje lub krytyczny blad
```

### 6.2 Readiness probe

**Endpoint:** `GET /api/health/ready`
**Rola:** guest

```bash
curl http://localhost:8421/api/health/ready
# {"status": "ready", "db": "ok", "agents": "loaded"}
# HTTP 200 = gotowy do przyjmowania ruchu
# HTTP 503 = nie gotowy (np. migracja w toku)
```

### 6.3 Szczegolowy status

**Endpoint:** `GET /api/health/detailed`
**Rola:** user

```bash
curl -b cookies.txt http://localhost:8421/api/health/detailed
```

```json
{
  "status": "healthy",
  "version": "5.9.2",
  "db": {"status": "ok", "schema_version": 4, "wal_mode": true},
  "models": {
    "anthropic": {"state": "CLOSED", "last_success": "2026-04-19T12:01:00Z"},
    "openai":    {"state": "CLOSED", "last_success": "2026-04-19T12:01:05Z"},
    "google":    {"state": "OPEN",   "open_since": "2026-04-19T11:55:00Z"},
    "ollama":    {"state": "CLOSED", "models_loaded": ["llama3.1:8b"]}
  },
  "budget": {"used_usd": 12.34, "limit_usd": 50.0, "status": "NORMAL"},
  "humangate_pending": 0,
  "retention_last_run": "2026-04-19T06:00:00Z",
  "syl_codes": ["SYL-001: DB ok", "SYL-042: Ollama connected"]
}
```

**Kody SYL-*:** 82 kody diagnostyczne zdefiniowane w `dashboard/health_check_v2.py` (ADR-0029). Kazdy kod ma format `SYL-NNN: opis`.

### 6.4 Historia health checkow

**Endpoint:** `GET /api/health/history`
**Rola:** user

```bash
curl -b cookies.txt "http://localhost:8421/api/health/history?limit=24"
# Zwraca ostatnie N punktow danych (trend wykresu w UI)
```

### 6.5 Wykrywanie Pixel 9

**Endpoint:** `GET /api/devices/pixel-detect`
**Rola:** operator

```bash
curl -b cookies.txt http://localhost:8421/api/devices/pixel-detect
```

```json
{
  "connected": true,
  "serial": "0A291FDD4003BY",
  "model": "Pixel 9",
  "codename": "tokay",
  "in_family": true,
  "state": "connected",
  "grapheneos": false
}
```

---

## 7. Pixel 9 provisioning

### 7.1 Dry-run provisioning

**Endpoint:** `POST /api/devices/provision-pixel`
**Rola:** operator

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/devices/provision-pixel \
  -d '{"dry_run": true, "steps": ["unlock", "flash", "verify"]}'
```

Przy `dry_run: true` — wykonuje tylko pre-checks i walidacje, nie wysyla komend ADB.

### 7.2 Real provisioning

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/devices/provision-pixel \
  -d '{"dry_run": false, "steps": ["unlock", "flash", "hardening", "verify"]}'
```

**UWAGA:** Wymaga HumanGate CRITICAL potwierdzenia przed krokami destruktywnymi (unlock, flash). Pipeline wstrzyma sie i poczeka na decyzje operatora.

**Parametry:**

| Parametr  | Opis                                              |
|-----------|---------------------------------------------------|
| `dry_run` | true = symulacja (bezpieczne), false = prawdziwe  |
| `steps`   | Lista krokow do wykonania (lub `["all"]`)          |
| `serial`  | ADB serial urzadzenia (opcjonalne — auto-detect)  |

### 7.3 Status provisioningu

**Endpoint:** `GET /api/devices/provision-pixel/status`
**Rola:** operator

```bash
curl -b cookies.txt http://localhost:8421/api/devices/provision-pixel/status
```

Zwraca liste krokow z ich statusem (pending / running / done / failed) i czasem wykonania.

### 7.4 Weryfikacja po provisioningu

**Endpoint:** `POST /api/devices/pixel-verify`
**Rola:** operator

Sprawdza czy Pixel 9 ma zainstalowany GrapheneOS, wszystkie 16 security patchow i agenta SYLION.

---

## 8. Mudi router provisioning

### 8.1 Pelen provisioning routera

**Endpoint:** `POST /api/devices/provision-router`
**Rola:** operator

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/devices/provision-router \
  -d '{
    "router_host": "192.168.8.1",
    "router_user": "root",
    "wg_server_pubkey": "abc123pubkey==",
    "wg_server_endpoint": "vpn.example.com:51820",
    "wg_client_address": "10.8.0.2/24",
    "wifi_ssid": "SYLION-Pixel",
    "wifi_password": "silne-wifi-haslo",
    "enable_kill_switch": true,
    "enable_dns_tunnel": true,
    "dry_run": true
  }'
```

### 8.2 WireGuard status

**Endpoint:** `GET /api/devices/wireguard/status`
**Rola:** operator

Zwraca wynik `wg show` z routera (przez SSH) — aktywne polaczenia, ostatni handshake, transfer.

### 8.3 Kill switch

**Endpoint:** `POST /api/devices/kill-switch`
**Rola:** operator

```bash
# Aktywacja kill switch
curl -b cookies.txt -H "X-CSRF-Token: abc123..." \
  -X POST http://localhost:8421/api/devices/kill-switch \
  -d '{"action": "enable"}'

# Dezaktywacja (swiadoma decyzja)
curl -b cookies.txt -H "X-CSRF-Token: abc123..." \
  -X POST http://localhost:8421/api/devices/kill-switch \
  -d '{"action": "disable"}'
```

**UWAGA:** Dezaktywacja kill switch uruchamia HumanGate CONFIRMATION — pipeline pyta o potwierdzenie swiadomej decyzji wystawienia ruchu poza tunel VPN.

---

## 9. Feature flags admin

### 9.1 Lista flag

**Endpoint:** `GET /api/config/flags`
**Rola:** admin

```bash
curl -b cookies.txt http://localhost:8421/api/config/flags
```

```json
{
  "flags": [
    {"name": "BUILD_VERIFICATION_ENABLED", "value": true, "type": "bool"},
    {"name": "FACT_CHECKER_ENABLED", "value": true, "type": "bool"},
    {"name": "PIPELINE_EMERGENCY_STOP", "value": false, "type": "bool"}
  ]
}
```

### 9.2 Toggle flagi

**Endpoint:** `PATCH /api/config/flags/{name}`
**Rola:** admin

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -H "Content-Type: application/json" \
  -X PATCH http://localhost:8421/api/config/flags/FACT_CHECKER_ENABLED \
  -d '{"value": false}'
```

Zmiana jest aktywna natychmiast (bez restartu). Zapisana w bazie danych i w `audit_log`.

### 9.3 Per-user override

**Endpoint:** `PATCH /api/config/flags/{name}/user/{user_id}`
**Rola:** admin

Ustawia wartosc flagi dla konkretnego uzytkownika (nadpisuje globalna wartosc).

### 9.4 Emergency Stop

```bash
# Natychmiastowe zatrzymanie calego pipeline
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -X PATCH http://localhost:8421/api/config/flags/PIPELINE_EMERGENCY_STOP \
  -d '{"value": true}'
```

Wywoluje HumanGate CRITICAL — wymaga potwierdzenia przed aktywacja.

---

## 10. Budget tracking

### 10.1 Koszty biezacego runu

**Endpoint:** `GET /api/cost/run/{run_id}`
**Rola:** user

```bash
curl -b cookies.txt http://localhost:8421/api/cost/run/run_20260419_xyz789
```

```json
{
  "run_id": "run_20260419_xyz789",
  "total_usd": 1.23,
  "breakdown": [
    {"model": "claude-opus-4-7", "tokens_in": 12000, "tokens_out": 3000, "cost_usd": 0.67},
    {"model": "claude-sonnet-4-6", "tokens_in": 10000, "tokens_out": 2500, "cost_usd": 0.28},
    {"model": "gpt-5-4", "tokens_in": 11000, "tokens_out": 2800, "cost_usd": 0.21},
    {"model": "gemini-3-1-pro", "tokens_in": 9000, "tokens_out": 2000, "cost_usd": 0.07}
  ],
  "tier": "PREMIUM",
  "local_calls": 12,
  "cloud_calls": 8
}
```

### 10.2 Budzet dzienny

**Endpoint:** `GET /api/cost/budget`
**Rola:** user

```bash
curl -b cookies.txt http://localhost:8421/api/cost/budget
```

```json
{
  "limit_usd": 50.0,
  "used_usd": 12.34,
  "remaining_usd": 37.66,
  "status": "NORMAL",
  "warning_threshold": 0.8,
  "runs_today": 5
}
```

### 10.3 Reset budzetowy (admin)

**Endpoint:** `POST /api/cost/reset`
**Rola:** admin

Resetuje licznik kosztow dziennych. Wymaga HumanGate CONFIRMATION.

---

## 11. Backup i restore

### 11.1 Manualny backup

**Endpoint:** `POST /api/backup/create`
**Rola:** admin

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -X POST http://localhost:8421/api/backup/create
```

```json
{
  "backup_file": "backup_20260419_120000.sqlite",
  "size_bytes": 2097152,
  "integrity_check": "ok",
  "path": "/home/user/sylion/backups/backup_20260419_120000.sqlite"
}
```

Alternatywnie przez skrypt:

```bash
bash scripts/backup.sh
```

### 11.2 Lista backupow

**Endpoint:** `GET /api/backup/list`
**Rola:** admin

```bash
curl -b cookies.txt http://localhost:8421/api/backup/list
```

### 11.3 Restore

**Endpoint:** `POST /api/backup/restore`
**Rola:** admin

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: abc123..." \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8421/api/backup/restore \
  -d '{"backup_file": "backup_20260419_120000.sqlite"}'
```

**KRYTYCZNE:** Wymaga HumanGate CRITICAL. Restore nadpisuje biezaca baze danych.

Alternatywnie przez skrypt:

```bash
bash rollback.sh --from-backup=backup_20260419_120000.sqlite
```

---

## 12. Rollback do poprzedniej wersji

Rollback kodu (nie tylko bazy danych) wykonywany jest przez skrypt `rollback.sh` bezposrednio na serwerze — nie ma endpointu API dla tej operacji (bezpieczenstwo: wymagany dostep SSH).

### Kroki

1. Zatrzymaj dashboard: `systemctl stop sylion-dashboard`
2. Sprawdz dostepne backupy: `bash rollback.sh --list-backups`
3. Wykonaj rollback: `bash rollback.sh --from-backup=backup_20260419.sqlite`
4. Zweryfikuj: `bash rollback.sh --integrity-check-only`
5. Uruchom dashboard: `systemctl start sylion-dashboard`

```bash
# Pelny przebieg
systemctl stop sylion-dashboard
bash rollback.sh --from-backup=backup_20260419_120000.sqlite
systemctl start sylion-dashboard
curl http://localhost:8421/api/health/ready
```

Szczegolowa dokumentacja rollbacku: [`ROLLBACK_PLAN.md`](../ROLLBACK_PLAN.md)

---

*Poprzednia sekcja: [02_SYSTEM_DECYZJI.md](./02_SYSTEM_DECYZJI.md)*
*Nastepna sekcja: [04_PROMPTY.md](./04_PROMPTY.md)*
