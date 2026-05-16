# SYLION v5.9.0 Incident Response Runbook

> **v5.9.1 patch (2026-04-19):** Poprawiono niespójności zidentyfikowane
> przez radę pre-deploy (F-007, F-008): port 8000 → 8421, nginx → Caddy,
> `alembic_version` → `PRAGMA user_version`, `/health` → `/api/health`,
> placeholder on-call przeniesiony do zmiennej `${SYLION_ONCALL_CONTACT}`.

**Wersja:** 1.0.0  
**Data:** 2025-01-01T00:00:00Z  
**Właściciel:** SRE Team  
**Klasyfikacja:** Internal — Operations  
**Przegląd:** Co kwartał lub po każdym P0/P1  

---

> **Zasady Ogólne:**
> - Zawsze dokumentuj każdą akcję z timestampem
> - Przed każdą operacją zapisu/zmiany wykonaj backup DB
> - Post-mortem jest blameless — skupia się na systemach, nie ludziach
> - Przy P0/P1 — najpierw stabilizuj system, potem wyjaśniaj przyczyny
> - Triage = read-only diagnostyka. Nie restartuj bez diagnozy

---

**Spis Treści:**
1. [Incident Taxonomy & Severity](#1-incident-taxonomy--severity)
2. [Triage Playbook (per-incident)](#2-triage-playbook-per-incident)
3. [Mitigation & Recovery Procedures](#3-mitigation--recovery-procedures)
4. [Post-mortem Template](#4-post-mortem-template)
5. [On-call Contacts](#5-on-call-contacts)

---

## 1. Incident Taxonomy & Severity

> Autor sekcji: Claude Opus 4.7

### 1.1 Klasy Incydentów

#### HTTP Błędy (502 / 503 / 504)

| Kod | Nazwa | Opis | Typowa przyczyna |
|-----|-------|------|------------------|
| 502 | Bad Gateway | Upstream zwrócił błędną odpowiedź | Crash workera SYLION, gunicorn/uvicorn down |
| 503 | Service Unavailable | Serwis niedostępny lub przeciążony | Wyczerpany pool wątków, OOM killer aktywny |
| 504 | Gateway Timeout | Upstream nie odpowiedział w czasie | Zablokowany pipeline, wolne zapytanie DB |

**Komendy diagnostyczne:**
```bash
# Sprawdź status procesu aplikacji
systemctl status sylion.service
journalctl -u sylion.service -n 200 --no-pager

# Sprawdź logi Caddy (reverse proxy)
tail -f /var/log/caddy/error.log
grep -E "502|503|504" /var/log/caddy/access.log | tail -50

# Sprawdź czy port aplikacji odpowiada
curl -v --max-time 5 http://127.0.0.1:8421/api/health
ss -tlnp | grep 8000
```

---

#### OOM — Out of Memory

**Symptomy:** Procesy zabijane przez jądro, logi kernel `oom-kill`, aplikacja restartuje się w pętli.

```bash
# Sprawdź OOM events w dmesg
dmesg | grep -i "oom\|killed process\|out of memory" | tail -20
journalctl -k | grep -i oom | tail -20

# Stan pamięci
free -h
cat /proc/meminfo | grep -E "MemAvailable|SwapFree|Cached"
ps aux --sort=-%mem | head -20

# Docker (jeśli konteneryzacja)
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"
```

---

#### Disk Full — Zapełniony Dysk

**Symptomy:** Błędy zapisu do DB, pipeline crash z `SQLITE_FULL`, logi przestają się zapisywać.

```bash
# Ogólny stan dysków
df -h
du -sh /var/lib/sylion/* 2>/dev/null | sort -rh | head -20

# Znajdź największe pliki
find /var/log -name "*.log" -size +100M -ls 2>/dev/null

# SQLite WAL — może się rozrosnąć
ls -lah /var/lib/sylion/*.db /var/lib/sylion/*.db-wal /var/lib/sylion/*.db-shm 2>/dev/null
```

---

#### DB Corruption — Uszkodzenie Bazy Danych

**Symptomy:** `sqlite3.DatabaseError: database disk image is malformed`, błędy PRAGMA integrity_check.

```bash
# Sprawdź integralność bazy
sqlite3 /var/lib/sylion/sylion.db "PRAGMA integrity_check;"
sqlite3 /var/lib/sylion/sylion.db "PRAGMA quick_check;"
sqlite3 /var/lib/sylion/sylion.db "PRAGMA foreign_key_check;"

# Zamknij WAL i checkpoint
sqlite3 /var/lib/sylion/sylion.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

---

#### Pipeline Stuck — Zablokowany Pipeline

**Symptomy:** Zadania w kolejce nie postępują, worker nie przetwarza, logi bez aktywności >15 min.

```bash
# Sprawdź procesy pipeline
ps aux | grep -E "sylion|celery|worker|pipeline" | grep -v grep

# Wiek ostatniego przetworzonego rekordu
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT MAX(processed_at) FROM pipeline_jobs WHERE status='completed';"

# Sprawdź lock files
ls -la /var/lib/sylion/locks/ 2>/dev/null
lsof /var/lib/sylion/sylion.db 2>/dev/null
```

---

#### Auth Failure — Błąd Uwierzytelniania

**Symptomy:** 401/403 dla wszystkich żądań, tokeny wygasłe, sesje nieprawidłowe.

```bash
# Sprawdź logi auth
journalctl -u sylion.service | grep -iE "auth|token|session|403|401" | tail -50

# Sprawdź wygaśnięcie sesji w DB
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT COUNT(*) FROM sessions WHERE expires_at < datetime('now');"

# Sprawdź ważność certyfikatów
openssl x509 -in /etc/sylion/tls.crt -noout -dates 2>/dev/null

# Czas systemowy (JWT jest czasoczuły)
timedatectl status | grep -E "Local time|synchronized"
```

---

#### Migration Failed — Błąd Migracji

**Symptomy:** Aplikacja nie startuje po deploymencie, błąd `migration failed`, tabele brakujące.

```bash
# Sprawdź stan migracji
sqlite3 /var/lib/sylion/sylion.db \
  "PRAGMA user_version;"  # v5.9.1 F-007: SYLION uses PRAGMA user_version, not Alembic 2>/dev/null

# Sprawdź strukturę tabel
sqlite3 /var/lib/sylion/sylion.db ".schema"
sqlite3 /var/lib/sylion/sylion.db ".tables"

# Logi migracji
journalctl -u sylion.service | grep -iE "migrat|alembic|schema" | tail -30
```

---

### 1.2 Severity Matrix (P0–P4)

| Priorytet | Nazwa | Kryteria | SLA Reakcja | SLA Rozwiązanie | Eskalacja |
|-----------|-------|----------|-------------|-----------------|-----------|
| **P0** | Critical | Całkowita niedostępność produkcji; utrata danych; DB corruption; wszyscy użytkownicy | 5 min | 1 godz. | Natychmiastowa: CTO + Lead Dev + DevOps |
| **P1** | Major | >50% użytkowników niedostępnych; pipeline całkowicie zablokowany; auth failure | 15 min | 4 godz. | 15 min: Lead Dev + DevOps On-call |
| **P2** | Moderate | Degradacja wydajności; błędy dla <50% użytkowników; disk >90%; OOM intermittent | 30 min | 8 godz. | 30 min: DevOps On-call |
| **P3** | Minor | Błędy dla <5% użytkowników; ostrzeżenia systemowe; disk >80% | 2 godz. | 24 godz. | Standardowy ticket |
| **P4** | Informational | Niekrytyczne błędy; wnioski o ulepszenia | 8 godz. | 72 godz. | Backlog sprint |

### Matryca Decyzyjna

```
Czy produkcja jest całkowicie niedostępna?
  → TAK → P0
  → NIE ↓
Czy >50% użytkowników ma problemy LUB utrata danych w toku?
  → TAK → P1
  → NIE ↓
Czy degradacja wpływa na krytyczne funkcje (auth, pipeline, DB)?
  → TAK → P2
  → NIE ↓
Czy błąd jest powtarzalny i wpływa na małą grupę?
  → TAK → P3
  → NIE → P4
```

### 1.3 Procedura Eskalacji

```
P0/P1: Alert → PagerDuty → Slack #incidents-critical → Telekon (war room)
P2:    Alert → Slack #incidents-prod → Ticket JIRA (HIGH)
P3:    Slack #alerts-sre → Ticket JIRA (MEDIUM)
P4:    Ticket JIRA (LOW)
```

**Tworzenie incident logu (P0/P1):**
```bash
INCIDENT_ID="INC-$(date +%Y%m%d-%H%M%S)"
mkdir -p /var/log/sylion/incidents/${INCIDENT_ID}

# Snapshot systemu
{
  echo "=== SYSTEM SNAPSHOT: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  uptime; free -h; df -h; ps aux --sort=-%cpu | head -20
  journalctl -u sylion.service -n 100 --no-pager
} > /var/log/sylion/incidents/${INCIDENT_ID}/snapshot.txt

echo "Log: /var/log/sylion/incidents/${INCIDENT_ID}/"
```

| Priorytet | Brak odpowiedzi po | Eskaluj do |
|-----------|-------------------|------------|
| P0 | 10 min | CTO bezpośrednio |
| P1 | 30 min | Lead Dev + Manager |
| P2 | 2 godz. | DevOps Lead |
| P3 | 24 godz. | Team Lead |

---

## 2. Triage Playbook (per-incident)

> Autor sekcji: Claude Sonnet 4.6  
> **Zasada:** Najpierw zbierz dane, potem działaj. Komendy triage są read-only lub bezpieczne. Nie restartuj bez diagnozy.

### 2.0 Wstępny Triage (pierwsze 5 minut)

```bash
#!/bin/bash
# SYLION QUICK TRIAGE — uruchom jako pierwszy krok przy każdym incydencie
TRIAGE_FILE="/tmp/sylion-triage-$(date +%Y%m%d-%H%M%S).txt"

{
  echo "=========================================="
  echo "SYLION TRIAGE SNAPSHOT: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "=========================================="

  echo -e "\n--- SYSTEM UPTIME ---"
  uptime

  echo -e "\n--- PAMIĘĆ ---"
  free -h

  echo -e "\n--- DYSK ---"
  df -h

  echo -e "\n--- PROCESY SYLION ---"
  ps aux | grep -E "sylion|gunicorn|uvicorn|celery" | grep -v grep

  echo -e "\n--- PORTY NASŁUCHUJĄCE ---"
  ss -tlnp | grep -E "8000|8080|5432|6379|3306"

  echo -e "\n--- STATUS SERWISÓW ---"
  systemctl status sylion.service --no-pager -l 2>/dev/null || \
    docker ps --filter "name=sylion" 2>/dev/null

  echo -e "\n--- OSTATNIE 50 LOGÓW APLIKACJI ---"
  journalctl -u sylion.service -n 50 --no-pager 2>/dev/null || \
    docker logs sylion-app --tail=50 2>/dev/null

  echo -e "\n--- HEALTH CHECK ---"
  curl -s --max-time 5 http://127.0.0.1:8421/api/health 2>/dev/null || \
    echo "HEALTH ENDPOINT NIEDOSTĘPNY"

  echo -e "\n--- OSTATNIE BŁĘDY KERNELA ---"
  dmesg | tail -20

} | tee "$TRIAGE_FILE"

echo "Snapshot zapisany: $TRIAGE_FILE"
```

---

### 2.1 Triage: HTTP 502/503/504

```bash
# KROK 1: Czy aplikacja w ogóle działa?
systemctl is-active sylion.service 2>/dev/null || \
  docker inspect -f '{{.State.Status}}' sylion-app 2>/dev/null

# KROK 2: Czy port aplikacji odpowiada?
curl -v --max-time 3 http://127.0.0.1:8421/api/health
nc -zv 127.0.0.1 8000 && echo "PORT OPEN" || echo "PORT CLOSED"

# KROK 3: Błędy aplikacji (ostatnie 5 minut)
journalctl -u sylion.service --since "5 minutes ago" --no-pager | \
  grep -iE "error|exception|traceback|critical|fatal"

# KROK 4: Logi reverse proxy
tail -100 /var/log/caddy/sylion_error.log 2>/dev/null
grep -E "\"(GET|POST|PUT|DELETE).*\" (502|503|504)" \
  /var/log/caddy/sylion_access.log 2>/dev/null | tail -20

# KROK 5: Liczba aktywnych połączeń
netstat -an | grep :8000 | grep ESTABLISHED | wc -l
ss -s
```

**Drzewo Decyzyjne 502/503/504:**
```
Port 8000 odpowiada?
├── NIE → Aplikacja down → RESTART (patrz Sekcja 3.1)
│         Sprawdź: OOM killer, disk full, crash
└── TAK → Aplikacja działa, ale błąd upstream
          ├── 504 (timeout)? → Sprawdź DB / długie zapytania
          │   lsof /var/lib/sylion/sylion.db
          ├── 503? → Sprawdź pool wątków
          │   netstat -an | grep :8000 | wc -l
          └── 502? → Sprawdź crash workerów
              journalctl -u sylion -n 200 | grep -i "worker\|crash"
```

---

### 2.2 Triage: OOM (Out of Memory)

```bash
# KROK 1: Potwierdź OOM event
dmesg | grep -iE "out of memory|oom.kill|killed process" | tail -20
journalctl -k --since "1 hour ago" | grep -i oom

# KROK 2: Co zostało zabite?
dmesg | grep "Killed process" | awk '{print $5, $6, $7}' | tail -10

# KROK 3: Aktualne zużycie pamięci
free -h
cat /proc/meminfo | grep -E "MemTotal|MemAvailable|SwapTotal|SwapFree"

# KROK 4: Top konsumenci pamięci
ps aux --sort=-%mem | head -15

# KROK 5: RSS procesu aplikacji
PID=$(pgrep -f "sylion\|gunicorn\|uvicorn" | head -1)
if [ -n "$PID" ]; then
  cat /proc/$PID/status | grep -E "VmRSS|VmPeak|VmSize"
fi

# KROK 6: Docker memory
docker stats --no-stream --format \
  "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.MemLimit}}"
```

**Drzewo Decyzyjne OOM:**
```
OOM event w dmesg/journalctl?
├── NIE → Nie OOM, sprawdź inne przyczyny
└── TAK → Który proces zabity?
          ├── sylion/gunicorn → Restart (Sekcja 3.1), monitoruj RSS
          ├── brak swap → Dodaj tymczasowy swapfile:
          │   fallocate -l 2G /tmp/swapfile && chmod 600 /tmp/swapfile
          │   mkswap /tmp/swapfile && swapon /tmp/swapfile
          └── Ciągłe OOM → Uruchom prune (Sekcja 3.3) + zwiększ limit
```

---

### 2.3 Triage: Disk Full

```bash
# KROK 1: Stan dysków i inodes
df -h
df -i

# KROK 2: Gdzie jest problem?
du -sh /var/log/sylion/ /var/lib/sylion/ /tmp/ 2>/dev/null

# KROK 3: Największe pliki
find / -xdev -type f -size +100M -printf "%s\t%p\n" 2>/dev/null | \
  sort -rn | head -20

# KROK 4: SQLite WAL
find / -xdev -name "*.db-wal" -ls 2>/dev/null

# KROK 5: Błędy SQLITE_FULL w logach
journalctl -u sylion.service | grep -iE "SQLITE_FULL|disk.*full|no space" | tail -20
```

**Drzewo Decyzyjne Disk Full:**
```
Wolne miejsce < 1 GB?
├── NIE → Disk OK, szukaj gdzie indziej
└── TAK → Które partycje?
          ├── /var/log pełny → Rotuj logi (Sekcja 3.3.a)
          ├── /var/lib/sylion pełny → Prune audit_log (Sekcja 3.3.b)
          ├── WAL > 1 GB → PRAGMA wal_checkpoint(TRUNCATE) (Sekcja 3.3.c)
          └── /tmp pełny → rm -rf /tmp/sylion-* /tmp/*.tmp
```

---

### 2.4 Triage: DB Corruption

```bash
DB_PATH="/var/lib/sylion/sylion.db"

# KROK 1: Integrity check (ZAWSZE NAJPIERW)
sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | head -20

# KROK 2: Quick check
sqlite3 "$DB_PATH" "PRAGMA quick_check;" 2>&1 | head -10

# KROK 3: Foreign keys
sqlite3 "$DB_PATH" "PRAGMA foreign_key_check;" 2>&1

# KROK 4: Stan WAL
sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint;" 2>&1
ls -lah ${DB_PATH}*

# KROK 5: Statystyki stron
sqlite3 "$DB_PATH" "PRAGMA page_count; PRAGMA freelist_count;" 2>&1

# KROK 6: Czy DB jest zablokowana?
lsof "$DB_PATH" 2>/dev/null
fuser "$DB_PATH" 2>/dev/null
```

**Drzewo Decyzyjne DB Corruption:**
```
integrity_check zwraca "ok"?
├── TAK → DB sprawna, szukaj gdzie indziej
└── NIE → Jaki błąd?
          ├── "malformed" / "tree page" → Poważna korupcja
          │   → ZATRZYMAJ aplikację natychmiast
          │   → cp sylion.db sylion.db.corrupted.$(date +%s)
          │   → Przywróć z backupu M-08 (Sekcja 3.4)
          ├── "foreign key mismatch" → Niespójna referencja
          │   → PRAGMA foreign_keys=OFF;
          │   → Napraw lub usuń osierocone rekordy
          └── WAL nie daje się zcheckpointować
              → lsof i fuser, kill procesów
              → PRAGMA wal_checkpoint(RESTART)
```

---

### 2.5 Triage: Pipeline Stuck

```bash
# KROK 1: Czy worker żyje?
ps aux | grep -E "sylion.*(worker|pipeline|task)" | grep -v grep
systemctl status sylion-worker.service 2>/dev/null

# KROK 2: Ostatnia aktywność pipeline
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT id, status, created_at, updated_at,
          CAST((julianday('now') - julianday(updated_at)) * 1440 AS INT) as age_minutes
   FROM pipeline_jobs
   ORDER BY updated_at DESC
   LIMIT 10;" 2>/dev/null

# KROK 3: Zadania stuck > 30 min
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT id, job_type, status, updated_at
   FROM pipeline_jobs
   WHERE status='running'
     AND updated_at < datetime('now', '-30 minutes');" 2>/dev/null

# KROK 4: Lock files
ls -la /var/lib/sylion/locks/ 2>/dev/null
ls -la /tmp/sylion*.lock 2>/dev/null

# KROK 5: Statystyki kolejki
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT status, COUNT(*) as count
   FROM pipeline_jobs
   GROUP BY status;" 2>/dev/null
```

---

### 2.6 Triage: Auth Failure

```bash
# KROK 1: Liczba 401/403
journalctl -u sylion.service --since "30 minutes ago" | \
  grep -cE "401|403|Unauthorized|Forbidden"

# KROK 2: Problemy z tokenami
journalctl -u sylion.service --since "30 minutes ago" | \
  grep -iE "token|jwt|session|signature|expire" | tail -20

# KROK 3: Stan sesji w DB
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT COUNT(*) as total,
          SUM(CASE WHEN expires_at < datetime('now') THEN 1 ELSE 0 END) as expired,
          SUM(CASE WHEN expires_at >= datetime('now') THEN 1 ELSE 0 END) as valid
   FROM sessions;" 2>/dev/null

# KROK 4: Certyfikat TLS
echo | openssl s_client -connect localhost:443 2>/dev/null | \
  openssl x509 -noout -dates 2>/dev/null

# KROK 5: Synchronizacja czasu (JWT jest czasoczuły)
timedatectl status | grep -E "Local time|RTC time|synchronized"
date -u
```

---

### 2.7 Triage: Migration Failed

```bash
# KROK 1: Wersja schema
sqlite3 /var/lib/sylion/sylion.db \
  "PRAGMA user_version;"  # v5.9.1 F-007: SYLION uses PRAGMA user_version, not Alembic 2>/dev/null

# KROK 2: Czy schema jest kompletna?
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT name, type FROM sqlite_master
   WHERE type IN ('table','view')
   ORDER BY name;"

# KROK 3: Logi migracji
journalctl -u sylion.service | grep -iE "migrat|alembic|schema|DDL" | tail -30

# KROK 4: Czy migracja jest w toku?
sqlite3 /var/lib/sylion/sylion.db ".timeout 1000" \
  "BEGIN EXCLUSIVE; SELECT 1; ROLLBACK;" 2>&1

# KROK 5: Backup przed jakimkolwiek działaniem
cp /var/lib/sylion/sylion.db \
   /var/lib/sylion/sylion.db.pre-migration-fix.$(date +%Y%m%d%H%M%S)
echo "Backup wykonany"
```

---

## 3. Mitigation & Recovery Procedures

> Autor sekcji: GPT-5.4  
> **Zasada bezpieczeństwa:** Przed każdą operacją zapisu/restorowania wykonaj backup. Dokumentuj każdy krok w logu incydentu.

### 3.0 Przed Jakimkolwiek Działaniem

```bash
# Otwórz log incydentu
INCIDENT_ID="${INCIDENT_ID:-INC-$(date +%Y%m%d-%H%M%S)}"
INCIDENT_LOG="/var/log/sylion/incidents/${INCIDENT_ID}/actions.log"
mkdir -p "$(dirname $INCIDENT_LOG)"

log_action() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [$(whoami)] $1" | tee -a "$INCIDENT_LOG"
}

log_action "INCIDENT RECOVERY START — $INCIDENT_ID"
log_action "Operator: $(whoami)@$(hostname)"
```

---

### 3.1 Restart Procedura (Aplikacja Down: 502/503/OOM)

```bash
#!/bin/bash
# sylion-restart.sh — bezpieczny restart SYLION
set -euo pipefail

DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"
SERVICE_NAME="sylion.service"
BACKUP_DIR="/var/lib/sylion/backups"

log_action "RESTART: Rozpoczynam procedurę restartu"

# KROK 1: Backup DB przed restartem
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/sylion.db.pre-restart.$(date +%Y%m%d%H%M%S)"
log_action "RESTART: Backup DB → $BACKUP_FILE"
sqlite3 "$DB_PATH" ".backup $BACKUP_FILE" 2>/dev/null || cp "$DB_PATH" "$BACKUP_FILE"

# KROK 2: Checkpoint WAL przed restartem
log_action "RESTART: WAL checkpoint"
sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(FULL);" 2>/dev/null || true

# KROK 3: Graceful stop
log_action "RESTART: Graceful stop"
systemctl stop "$SERVICE_NAME" 2>/dev/null || docker stop sylion-app 2>/dev/null || true
sleep 3

# Weryfikacja zatrzymania
if pgrep -f "sylion\|gunicorn\|uvicorn" > /dev/null 2>&1; then
  log_action "RESTART: Procesy nadal działają, wymuszam stop"
  pkill -TERM -f "sylion\|gunicorn\|uvicorn" || true
  sleep 5
  pkill -KILL -f "sylion\|gunicorn\|uvicorn" || true
fi

# KROK 4: Start serwisu
log_action "RESTART: Starting $SERVICE_NAME"
systemctl start "$SERVICE_NAME" 2>/dev/null || docker start sylion-app 2>/dev/null

# KROK 5: Poczekaj na gotowość (max 60s)
sleep 5
MAX_WAIT=60; ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  if curl -sf --max-time 3 http://127.0.0.1:8421/api/health > /dev/null 2>&1; then
    log_action "RESTART: Aplikacja zdrowa po ${ELAPSED}s"
    echo "SUCCESS: SYLION gotowy"; break
  fi
  sleep 5; ELAPSED=$((ELAPSED + 5))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  log_action "RESTART: TIMEOUT — aplikacja nie odpowiada"
  echo "FAILURE: Sprawdź logi:"
  journalctl -u "$SERVICE_NAME" -n 50 --no-pager
  exit 1
fi
```

---

### 3.2 Rollback Procedura (po błędnym deploymencie)

```bash
#!/bin/bash
# rollback.sh — rollback SYLION do poprzedniej wersji
# Użycie: bash rollback.sh [VERSION]
# Przykład: bash rollback.sh v5.8.2
set -euo pipefail

TARGET_VERSION="${1:-}"
RELEASES_DIR="/opt/sylion/releases"
CURRENT_LINK="/opt/sylion/current"
DB_PATH="/var/lib/sylion/sylion.db"
BACKUP_DIR="/var/lib/sylion/backups"

log_action "ROLLBACK: Inicjalizacja rollback ${TARGET_VERSION:-auto}"

# KROK 1: Ustal docelową wersję
if [ -z "$TARGET_VERSION" ]; then
  PREV=$(ls -td "$RELEASES_DIR"/v*.*.* 2>/dev/null | head -2 | tail -1)
  [ -z "$PREV" ] && { echo "BŁĄD: Brak poprzedniej wersji"; exit 1; }
  TARGET_VERSION=$(basename "$PREV")
fi

ROLLBACK_PATH="$RELEASES_DIR/$TARGET_VERSION"
[ ! -d "$ROLLBACK_PATH" ] && { echo "BŁĄD: Wersja $TARGET_VERSION nie istnieje"; exit 1; }
log_action "ROLLBACK: Cel → $ROLLBACK_PATH"

# KROK 2: Backup DB
mkdir -p "$BACKUP_DIR"
DB_BACKUP="$BACKUP_DIR/sylion.db.pre-rollback.$(date +%Y%m%d%H%M%S)"
sqlite3 "$DB_PATH" ".backup $DB_BACKUP" 2>/dev/null || cp "$DB_PATH" "$DB_BACKUP"
log_action "ROLLBACK: Backup DB → $DB_BACKUP"

# KROK 3: Zatrzymaj aplikację
systemctl stop sylion.service 2>/dev/null || docker stop sylion-app 2>/dev/null

# KROK 4: Przełącz symlink
log_action "ROLLBACK: Przełączam symlink → $ROLLBACK_PATH"
ln -sfn "$ROLLBACK_PATH" "$CURRENT_LINK"

# KROK 5: Rollback schematu DB (jeśli rollback SQL istnieje)
ROLLBACK_SQL="$ROLLBACK_PATH/migrations/rollback_to_${TARGET_VERSION}.sql"
if [ -f "$ROLLBACK_SQL" ]; then
  log_action "ROLLBACK: Wykonuję rollback SQL: $ROLLBACK_SQL"
  sqlite3 "$DB_PATH" < "$ROLLBACK_SQL"
else
  log_action "ROLLBACK: Brak rollback SQL — schema bez zmian"
  echo "UWAGA: Schema DB nie cofnięta — sprawdź zgodność ręcznie"
fi

# KROK 6: Start i weryfikacja
systemctl start sylion.service 2>/dev/null || docker start sylion-app 2>/dev/null
sleep 5
if curl -sf --max-time 5 http://127.0.0.1:8421/api/health > /dev/null 2>&1; then
  log_action "ROLLBACK: SUKCES — SYLION $TARGET_VERSION działa"
  echo "ROLLBACK SUCCESS: Wersja $TARGET_VERSION aktywna"
else
  log_action "ROLLBACK: FAILURE"
  echo "ROLLBACK FAILURE: journalctl -u sylion.service -n 100"
  exit 1
fi
```

---

### 3.3 Prune — Oczyszczenie Danych

#### 3.3.a Prune Audit Log

```bash
#!/bin/bash
# manual_prune_audit_log.sh — ręczne czyszczenie audit_log
# Użycie: bash manual_prune_audit_log.sh [--dry-run] [--older-than-days 90]

DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"
OLDER_THAN_DAYS=90
DRY_RUN=0

for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=1 ;;
    --older-than-days) shift; OLDER_THAN_DAYS="$1" ;;
  esac
done

echo "PRUNE AUDIT LOG: Rekordy starsze niż ${OLDER_THAN_DAYS} dni"

COUNT=$(sqlite3 "$DB_PATH" \
  "SELECT COUNT(*) FROM audit_log
   WHERE created_at < datetime('now', '-${OLDER_THAN_DAYS} days');")
echo "Znaleziono rekordów do usunięcia: $COUNT"

[ "$DRY_RUN" = "1" ] && { echo "DRY RUN — brak zmian"; exit 0; }
[ "$COUNT" -eq 0 ] && { echo "Brak rekordów do usunięcia"; exit 0; }

# Backup
BACKUP="$DB_PATH.pre-prune.$(date +%Y%m%d%H%M%S)"
sqlite3 "$DB_PATH" ".backup $BACKUP"
echo "Backup: $BACKUP"

# Usuń w partiach po 10000
sqlite3 "$DB_PATH" << SQL
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
DELETE FROM audit_log
WHERE rowid IN (
  SELECT rowid FROM audit_log
  WHERE created_at < datetime('now', '-${OLDER_THAN_DAYS} days')
  LIMIT 10000
);
SQL

NEW_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM audit_log;")
echo "Pozostało rekordów: $NEW_COUNT"

# Odzyskaj przestrzeń
echo "Uruchamiam VACUUM..."
sqlite3 "$DB_PATH" "VACUUM;"
echo "PRUNE AUDIT LOG: zakończono"
```

#### 3.3.b Prune Sessions (wygasłe sesje)

```bash
#!/bin/bash
# manual_prune_sessions.sh — ręczne czyszczenie wygasłych sesji
DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"

COUNT=$(sqlite3 "$DB_PATH" \
  "SELECT COUNT(*) FROM sessions WHERE expires_at < datetime('now');")
echo "Wygasłych sesji: $COUNT"

if [ "$COUNT" -gt 0 ]; then
  BACKUP="$DB_PATH.pre-prune-sessions.$(date +%Y%m%d%H%M%S)"
  sqlite3 "$DB_PATH" ".backup $BACKUP"

  sqlite3 "$DB_PATH" \
    "DELETE FROM sessions WHERE expires_at < datetime('now');"

  sqlite3 "$DB_PATH" "VACUUM;"
  echo "Usunięto $COUNT wygasłych sesji"
fi
```

#### 3.3.c WAL Checkpoint (zapełniony plik WAL)

```bash
# Wymuś checkpoint WAL i skompresuj
sqlite3 /var/lib/sylion/sylion.db << 'SQL'
PRAGMA wal_checkpoint(TRUNCATE);
PRAGMA auto_vacuum=INCREMENTAL;
PRAGMA incremental_vacuum(1000);
SQL

# Sprawdź rozmiary po operacji
ls -lah /var/lib/sylion/sylion.db* 2>/dev/null
```

---

### 3.4 Odtworzenie DB z Backupu M-08

```bash
#!/bin/bash
# restore_db_m08.sh — odtworzenie DB SYLION z backupu M-08
# Użycie: bash restore_db_m08.sh [BACKUP_FILE]
# M-08 = backup comiesięczny, 8. dnia miesiąca
set -euo pipefail

DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"
BACKUP_DIR="/var/lib/sylion/backups"
BACKUP_FILE="${1:-}"

log_action "RESTORE M-08: Inicjalizacja"

# KROK 1: Znajdź backup M-08
if [ -z "$BACKUP_FILE" ]; then
  BACKUP_FILE=$(ls -t "$BACKUP_DIR"/sylion.db.m08.*.sqlite \
                   "$BACKUP_DIR"/sylion.db.*-08T* \
                   "$BACKUP_DIR"/*.db.backup 2>/dev/null | head -1)
  [ -z "$BACKUP_FILE" ] && {
    echo "BŁĄD: Brak backupu M-08 w $BACKUP_DIR"
    ls -lah "$BACKUP_DIR"/ 2>/dev/null || echo "Katalog pusty"
    exit 1
  }
fi
echo "Backup M-08: $BACKUP_FILE"

# KROK 2: Weryfikuj backup
INTEGRITY=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" 2>&1 | head -1)
[ "$INTEGRITY" != "ok" ] && {
  echo "BŁĄD: Backup uszkodzony — integrity_check: $INTEGRITY"
  exit 1
}
echo "Backup zdrowy: $INTEGRITY"

# KROK 3: Zatrzymaj aplikację
log_action "RESTORE M-08: Zatrzymuję serwis"
systemctl stop sylion.service 2>/dev/null || docker stop sylion-app 2>/dev/null || true
sleep 3

# Upewnij się że DB nie jest trzymana
lsof "$DB_PATH" 2>/dev/null | grep -q . && fuser -k "$DB_PATH" 2>/dev/null || true

# KROK 4: Archiwizuj uszkodzoną DB
CORRUPTED_SAVE="$DB_PATH.corrupted.$(date +%Y%m%d%H%M%S)"
log_action "RESTORE M-08: Archiwizuję uszkodzoną DB → $CORRUPTED_SAVE"
mv "$DB_PATH" "$CORRUPTED_SAVE"
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm" 2>/dev/null || true

# KROK 5: Odtwórz z backupu
log_action "RESTORE M-08: Kopiuję backup → $DB_PATH"
sqlite3 "$BACKUP_FILE" ".backup $DB_PATH"

# KROK 6: Weryfikuj odtworzoną DB
NEW_INTEGRITY=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | head -1)
echo "Integralność odtworzonej DB: $NEW_INTEGRITY"
[ "$NEW_INTEGRITY" != "ok" ] && {
  log_action "RESTORE M-08: FAILURE — odtworzona DB uszkodzona"
  echo "BŁĄD KRYTYCZNY: Odtworzona DB jest uszkodzona!"
  exit 1
}

TABLE_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
echo "Liczba tabel: $TABLE_COUNT"

# KROK 7: Uruchom aplikację
log_action "RESTORE M-08: Uruchamiam serwis"
systemctl start sylion.service 2>/dev/null || docker start sylion-app 2>/dev/null
sleep 8

if curl -sf --max-time 10 http://127.0.0.1:8421/api/health > /dev/null 2>&1; then
  log_action "RESTORE M-08: SUKCES"
  echo "RESTORE SUCCESS: SYLION działa z backupu M-08"
  echo "UWAGA: Dane po dacie backupu mogą być utracone — zweryfikuj z biznesem"
else
  log_action "RESTORE M-08: FAILURE"
  echo "FAILURE: journalctl -u sylion.service -n 100"
  exit 1
fi
```

---

### 3.5 Wznowienie Pipeline po Crash

```bash
#!/bin/bash
# resume_pipeline.sh — wznowienie pipeline po crash/stuck
# Użycie: bash resume_pipeline.sh [--force-reset-stuck]
DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"
FORCE_RESET="${1:-}"

log_action "PIPELINE RESUME: Inicjalizacja"

# KROK 1: Sprawdź stuck jobs
echo "=== ZADANIA STUCK > 30 MIN ==="
sqlite3 "$DB_PATH" << 'SQL'
SELECT id, job_type, status, created_at, updated_at,
       CAST((julianday('now') - julianday(updated_at)) * 60 AS INTEGER) as stuck_minutes
FROM pipeline_jobs
WHERE status = 'running'
  AND updated_at < datetime('now', '-30 minutes')
ORDER BY stuck_minutes DESC;
SQL

# KROK 2: Usuń stale lock files
echo "=== LOCK FILES ==="
find /var/lib/sylion/locks/ -name "*.lock" -mmin +60 -ls 2>/dev/null
if [ "$FORCE_RESET" = "--force-reset-stuck" ]; then
  find /var/lib/sylion/locks/ -name "*.lock" -mmin +60 -delete 2>/dev/null
  find /tmp -name "sylion*.lock" -mmin +60 -delete 2>/dev/null
  log_action "PIPELINE RESUME: Lock files wyczyszczone"
fi

# KROK 3: Reset stuck jobs → pending (tylko z --force-reset-stuck)
if [ "$FORCE_RESET" = "--force-reset-stuck" ]; then
  echo "=== RESET STUCK JOBS → pending ==="
  RESET_COUNT=$(sqlite3 "$DB_PATH" << 'SQL'
UPDATE pipeline_jobs
SET status = 'pending',
    updated_at = datetime('now'),
    retry_count = COALESCE(retry_count, 0) + 1,
    last_error = 'Reset po crash — pipeline resume'
WHERE status = 'running'
  AND updated_at < datetime('now', '-30 minutes');
SELECT changes();
SQL
  )
  log_action "PIPELINE RESUME: Reset $RESET_COUNT stuck jobs"
  echo "Reset zadań: $RESET_COUNT"
fi

# KROK 4: Restart workera
log_action "PIPELINE RESUME: Restart worker"
systemctl restart sylion-worker.service 2>/dev/null || {
  echo "UWAGA: Nie można automatycznie uruchomić workera"
  echo "Uruchom ręcznie: systemctl start sylion-worker.service"
}

# KROK 5: Monitoruj przez 5 minut
echo "=== MONITOROWANIE PIPELINE (5 min) ==="
for i in 1 2 3 4 5; do
  sleep 60
  sqlite3 "$DB_PATH" \
    "SELECT status, COUNT(*) FROM pipeline_jobs
     WHERE updated_at > datetime('now', '-2 minutes')
     GROUP BY status;" 2>/dev/null | \
    awk -v t="$(date -u +%H:%M:%S)" '{print t, $0}'
done

log_action "PIPELINE RESUME: Zakończono"
echo "Sprawdź dashboard lub: journalctl -u sylion-worker.service -f"
```

---

## 4. Post-mortem Template

> Autor sekcji: Gemini 3.1 Pro  
> **Kiedy stosować:** P0/P1 — obowiązkowo. P2 — opcjonalnie. Termin: max 5 dni roboczych od zamknięcia incydentu.  
> **Zasada:** Post-mortem jest **blameless** — skupia się na systemach i procesach, nie na osobach.

---

```markdown
# Post-mortem: [TYTUŁ INCYDENTU]

**ID Incydentu:** INC-YYYYMMDD-HHMMSS  
**Priorytet:** P0 / P1 / P2  
**Status:** OTWARTY / ZAMKNIĘTY  
**Data zdarzenia:** YYYY-MM-DDTHH:MM:SSZ  
**Data post-mortem:** YYYY-MM-DDTHH:MM:SSZ  
**Incident Commander:** [IMIĘ NAZWISKO]  
**Autorzy:** [IMIĘ NAZWISKO], [IMIĘ NAZWISKO]  
**Uczestnicy:** [LISTA]  

---

## 4.1 Executive Summary

[2-4 zdania: Co się stało, jak długo trwało, jaki był impact, jak zostało rozwiązane.]

Przykład:
> Dnia 2025-03-15 o 14:32 UTC aplikacja SYLION v5.9.0 stała się całkowicie niedostępna
> z powodu wyczerpania przestrzeni dyskowej (/var/lib/sylion). Plik WAL SQLite urósł
> do 4.7 GB po wyłączeniu automatycznego checkpointingu w v5.9.0. Incydent trwał 47 min
> i dotknął 100% użytkowników. Przywrócono działanie przez PRAGMA wal_checkpoint(TRUNCATE)
> i restart serwisu.

---

## 4.2 Timeline (ISO 8601)

| Timestamp (UTC) | Zdarzenie | Osoba | Działanie |
|-----------------|-----------|-------|-----------|
| YYYY-MM-DDTHH:MM:SSZ | ALERT WYZWOLONY | System | Automatyczny alert PagerDuty |
| YYYY-MM-DDTHH:MM:SSZ | INCIDENT OGŁOSZONY | [IC] | Incident Commander wyznaczony |
| YYYY-MM-DDTHH:MM:SSZ | TRIAGE ROZPOCZĘTY | [Name] | Uruchomiono quick-triage.sh |
| YYYY-MM-DDTHH:MM:SSZ | HIPOTEZA 1 odrzucona | [Name] | Sprawdzono OOM — negatywne |
| YYYY-MM-DDTHH:MM:SSZ | ROOT CAUSE ZIDENTYFIKOWANY | [Name] | Znaleziono: [opis] |
| YYYY-MM-DDTHH:MM:SSZ | MITIGATION ZASTOSOWANA | [Name] | Wykonano: [komenda] |
| YYYY-MM-DDTHH:MM:SSZ | WERYFIKACJA | [Name] | Health check pozytywny |
| YYYY-MM-DDTHH:MM:SSZ | INCIDENT ZAMKNIĘTY | [IC] | Ogłoszono w Slack #incidents-critical |
| YYYY-MM-DDTHH:MM:SSZ | POST-MORTEM ZAPLANOWANY | [IC] | Meeting: YYYY-MM-DD |

**Czas trwania incydentu:** HH:MM:SS  
**MTTR:** HH:MM:SS  
**MTTD:** HH:MM:SS  

---

## 4.3 Root Cause Analysis

### Bezpośrednia Przyczyna

[Jedno zdanie opisujące techniczną przyczynę.]

Przykład:
> Brak `wal_autocheckpoint` w konfiguracji SQLite spowodował nieograniczony wzrost
> pliku WAL po deploymencie v5.9.0.

### Łańcuch Przyczynowo-Skutkowy

```
1. Deploy v5.9.0 (2025-03-15T12:00Z) zmienił konfigurację SQLite
2. Parametr wal_autocheckpoint ustawiony na 0 (wyłączony)
3. Każdy zapis do DB powiększał plik WAL bez checkpointowania
4. Po ~2.5 godz. plik WAL osiągnął 4.7 GB — /var/lib zapełniony
5. SQLITE_FULL → crash aplikacji
6. Gunicorn workers restartowały się w pętli
7. Nginx zwracał 502 Bad Gateway (100% użytkowników)
```

### Diagram Przyczynowo-Skutkowy

```
Deploy v5.9.0 (wal_autocheckpoint=0)
         │
         ▼
WAL file rośnie bez ograniczeń
         │
         ▼
/var/lib = 100% (brak miejsca)
         ├──► SQLITE_FULL → crash aplikacji
         ├──► Niemożliwość zapisu logów
         └──► Niemożliwość restartu workera
                    │
                    ▼
              502 Bad Gateway (100% użytkowników)
```

---

## 4.4 Contributing Factors

| # | Czynnik | Kategoria | Wpływ |
|---|---------|-----------|-------|
| 1 | Brak alertu na rozmiar pliku WAL | Monitoring | Wysoki |
| 2 | Brak code review dla zmiany konfiguracji DB | Process | Wysoki |
| 3 | Alert disk usage przy 95% (za późno) | Alerting | Średni |
| 4 | Brak runbooka dla "disk full" | Documentation | Średni |
| 5 | Staging nie odzwierciedla wolumenu produkcji | Infrastructure | Niski |

---

## 4.5 Impact Assessment

| Metryka | Wartość |
|---------|---------|
| Czas niedostępności | HH:MM |
| Użytkownicy dotknięci | X (Y%) |
| Nieudane żądania | X,XXX |
| Utracone transakcje | X |
| Dane utracone | Tak / Nie / X rekordów |

```bash
# Zbierz dane impactu po incydencie
# Nieudane żądania:
grep -cE "\" (500|502|503|504)" /var/log/caddy/sylion_access.log 2>/dev/null

# Okno incydentu w DB:
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT MIN(created_at), MAX(created_at), COUNT(*)
   FROM audit_log
   WHERE created_at BETWEEN 'YYYY-MM-DD HH:MM:SS' AND 'YYYY-MM-DD HH:MM:SS';"
```

---

## 4.6 Remediation Tasks

| # | Działanie | Właściciel | Priorytet | Termin | Status |
|---|-----------|------------|-----------|--------|--------|
| R-01 | Alert na rozmiar WAL > 1 GB | DevOps | P0 | +3 dni | TODO |
| R-02 | Obniż próg alertu disk: 95% → 80% | DevOps | P0 | +3 dni | TODO |
| R-03 | Dodaj `wal_autocheckpoint=1000` do config SQLite | Dev | P0 | +1 dzień | TODO |
| R-04 | Napisz runbook dla disk full (ten dokument) | SRE | P1 | +5 dni | DONE |
| R-05 | Code review obowiązkowy dla zmian konfiguracji DB | Process | P1 | +7 dni | TODO |
| R-06 | Dodaj WAL size check do `/health` endpoint | Dev | P1 | +7 dni | TODO |
| R-07 | Synchronizuj wolumen danych staging = prod (anon.) | DevOps | P2 | +14 dni | TODO |
| R-08 | Automatyczny prune_audit_log jako cron (codziennie) | Dev | P2 | +14 dni | TODO |

### Szablon Ticketu JIRA

```
Tytuł: [POST-MORTEM INC-YYYYMMDD] R-XX: [Opis działania]

Incydent: INC-YYYYMMDD-HHMMSS | Priorytet: P0/P1/P2

Działanie naprawcze:
[Opis co należy zrobić]

Definition of Done:
- [ ] Implementacja
- [ ] Testy (unit/integration)
- [ ] Deploy na staging i weryfikacja
- [ ] Deploy na produkcję
- [ ] Alert lub monitoring zaktualizowany

Link do post-mortem: [URL]
```

---

## 4.7 Learning Outcomes (Wnioski)

### Co Zadziałało Dobrze

1. [Co zadziałało — bądź konkretny]
2. [Co zadziałało]
3. [Co zadziałało]

### Co Można Poprawić

1. [Co można ulepszyć]
2. [Co można ulepszyć]
3. [Co można ulepszyć]

### Analiza 5 Why

```
DLACZEGO produkcja była niedostępna?
→ Bo dysk był pełny

DLACZEGO dysk był pełny?
→ Bo plik WAL urósł do 4.7 GB

DLACZEGO WAL urósł?
→ Bo checkpointing był wyłączony po deploymencie

DLACZEGO checkpointing był wyłączony?
→ Bo zmiana konfiguracji w v5.9.0 miała błąd (wal_autocheckpoint=0)

DLACZEGO błąd trafił na produkcję?
→ Bo zmiana nie przeszła code review i brak testu sprawdzającego konfigurację
→ AKCJA: Obowiązkowy code review + test automatyczny konfiguracji SQLite
```

---

## 4.8 Metryki Post-mortem

| Metryka | Wartość |
|---------|---------|
| MTTD (wykrycie) | MM:SS |
| MTTI (identyfikacja root cause) | MM:SS |
| MTTR (recovery) | MM:SS |
| Całkowity czas incydentu | MM:SS |
| Liczba remediation tasks | X |
| Incydenty z tego root cause (ostatnie 90 dni) | X |

---

## 4.9 Podpisy i Zatwierdzenie

```
Incident Commander: _________________________ Data: ___________
Tech Lead:          _________________________ Data: ___________
SRE Lead:           _________________________ Data: ___________

Post-mortem zatwierdzony: TAK / NIE
Opublikowany w wiki/Notion: TAK / NIE  Link: _______________
```
```

---

## 5. On-call Contacts

> **Kontakt on-call:** `${SYLION_ONCALL_CONTACT}` — patrz README.md sekcja
> „Zmienne środowiskowe operacyjne”. Wartość należy ustawić PRZED deployem
> (np. `export SYLION_ONCALL_CONTACT="+48-xxx / slack: @oncall-sylion"`).

| Rola | Imię Nazwisko | Telefon | Slack | Email | Godziny |
|------|---------------|---------|-------|-------|---------|
| Incident Commander (Primario) | [NAME] | [PHONE] | @[handle] | [email] | 24/7 |
| Incident Commander (Backup) | [NAME] | [PHONE] | @[handle] | [email] | 24/7 |
| SRE On-call | [NAME] | [PHONE] | @[handle] | [email] | 24/7 |
| Lead Developer | [NAME] | [PHONE] | @[handle] | [email] | Business hours + P0/P1 |
| DevOps Lead | [NAME] | [PHONE] | @[handle] | [email] | Business hours + P0/P1 |
| CTO | [NAME] | [PHONE] | @[handle] | [email] | P0 only |
| DBA (Database) | [NAME] | [PHONE] | @[handle] | [email] | P0/P1 DB issues |
| Security | [NAME] | [PHONE] | @[handle] | [email] | Auth/Security incidents |

### Kanały Komunikacji

| Kanał | Cel | Dostęp |
|-------|-----|--------|
| `#incidents-critical` | P0/P1 real-time | Cały zespół |
| `#incidents-prod` | P2/P3 tracking | Cały zespół |
| `#alerts-sre` | Automatyczne alerty | SRE + DevOps |
| PagerDuty Schedule | Automatyczna rotacja dyżurów | Linki tu: [URL] |
| War Room (Zoom/Meet) | Telekonferencja P0/P1 | [LINK] |

### Procedura Przekazania Dyżuru (Handoff)

```bash
# Szablon wiadomości handoff (Slack)
ON_CALL_HANDOFF="
=== HANDOFF DYŻUR SRE ===
Przekazuje: [IMIĘ] → Przejmuje: [IMIĘ]
Czas: $(date -u +%Y-%m-%dT%H:%M:%SZ)

Aktywne incydenty: [LISTA LUB 'BRAK']
Otwarte tickety P0/P1: [LISTA LUB 'BRAK']
Ostatnie alerty (24h): [OPIS]
Rzeczy do obserwacji: [OPIS]

Runbook: /docs/INCIDENT_RESPONSE.md
Dashboard: [URL]
=========================
"
echo "$ON_CALL_HANDOFF"
```

---

*SYLION v5.9.0 Incident Response Runbook — wersja 1.0.0*  
*Wygenerowano: $(date -u +%Y-%m-%dT%H:%M:%SZ)*  
*Następny przegląd: po każdym P0/P1 lub co kwartał*
