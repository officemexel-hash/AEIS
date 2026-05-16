# SYLION v5.9.0 — Triage Playbook (per-incident)
_Model: Claude Sonnet 4.6 | Rola: Triage Diagnostician_

---

## 2. Triage Playbook

> **Zasada:** Najpierw zbierz dane, potem działaj. Każda komenda triage jest read-only lub bezpieczna. Nie restartuj bez diagnozy.

### 2.0 Wstępny Triage (pierwsze 5 minut)

```bash
#!/bin/bash
# SYLION QUICK TRIAGE — uruchom jako pierwszy krok przy każdym incydencie
# Zapisuje snapshot do /tmp/sylion-triage-$(date +%Y%m%d-%H%M%S).txt

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
  curl -s --max-time 5 http://127.0.0.1:8000/health 2>/dev/null || echo "HEALTH ENDPOINT NIEDOSTĘPNY"

  echo -e "\n--- OSTATNIE BŁĘDY KERNELA ---"
  dmesg | tail -20

} | tee "$TRIAGE_FILE"

echo ""
echo "Snapshot zapisany: $TRIAGE_FILE"
```

---

### 2.1 Triage: HTTP 502/503/504

**Cel:** Ustalić czy problem jest w procesie aplikacji, proxym, czy bazie danych.

```bash
# KROK 1: Czy aplikacja w ogóle działa?
systemctl is-active sylion.service 2>/dev/null || \
  docker inspect -f '{{.State.Status}}' sylion-app 2>/dev/null

# KROK 2: Czy port aplikacji odpowiada?
curl -v --max-time 3 http://127.0.0.1:8000/health
nc -zv 127.0.0.1 8000 && echo "PORT OPEN" || echo "PORT CLOSED"

# KROK 3: Sprawdź logi błędów aplikacji (ostatnie 5 minut)
journalctl -u sylion.service --since "5 minutes ago" --no-pager | \
  grep -iE "error|exception|traceback|critical|fatal"

# KROK 4: Sprawdź logi reverse proxy
tail -100 /var/log/nginx/sylion_error.log 2>/dev/null
grep -E "\"(GET|POST|PUT|DELETE).*\" (502|503|504)" \
  /var/log/nginx/sylion_access.log 2>/dev/null | tail -20

# KROK 5: Sprawdź workers/threads
# Gunicorn
ps aux | grep gunicorn | grep -v grep | wc -l
# Uvicorn
ps aux | grep uvicorn | grep -v grep

# KROK 6: Sprawdź połączenia sieciowe
netstat -an | grep :8000 | grep ESTABLISHED | wc -l
ss -s  # podsumowanie socketów
```

**Drzewo Decyzyjne 502/503/504:**
```
Port 8000 odpowiada?
├── NIE → Aplikacja down → RESTART (patrz Sekcja 3.1)
│         Sprawdź: OOM killer, disk full, crash
└── TAK → Aplikacja działa, ale błąd upstream
          ├── 504 (timeout)? → Sprawdź DB / pipeline (długie zapytania)
          │   sqlite3 sylion.db "SELECT * FROM sqlite_stat1;"
          │   lsof /var/lib/sylion/sylion.db
          ├── 503? → Sprawdź pool wątków, worker slots
          │   netstat -an | grep :8000 | wc -l
          └── 502? → Sprawdź crash workerów, logi wyjątków
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
cat /proc/meminfo | grep -E "MemTotal|MemAvailable|SwapTotal|SwapFree|Cached|Buffers"

# KROK 4: Top konsumenci pamięci
ps aux --sort=-%mem | head -15

# KROK 5: Sprawdź memory leaks w Sylion
# RSS (Resident Set Size) procesu aplikacji
PID=$(pgrep -f "sylion\|gunicorn\|uvicorn" | head -1)
if [ -n "$PID" ]; then
  cat /proc/$PID/status | grep -E "VmRSS|VmPeak|VmSize"
  pmap -x $PID | tail -5
fi

# KROK 6: Docker memory (jeśli kontener)
docker stats --no-stream --format \
  "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.MemLimit}}"
```

**Drzewo Decyzyjne OOM:**
```
OOM event w dmesg/journalctl?
├── NIE → Nie OOM, sprawdź inne przyczyny niedostępności
└── TAK → Który proces zabity?
          ├── sylion/gunicorn → Restart aplikacji (Sekcja 3.1)
          │   Następnie: monitoruj RSS co 60s przez 15 min
          ├── brak swap → Dodaj swapfile tymczasowy
          │   fallocate -l 2G /tmp/swapfile && chmod 600 /tmp/swapfile
          │   mkswap /tmp/swapfile && swapon /tmp/swapfile
          └── Ciągłe OOM → Uruchom prune (Sekcja 3.3) + zwiększ limit
```

---

### 2.3 Triage: Disk Full

```bash
# KROK 1: Stan dysków
df -h
df -i  # inodes (może być pełne przy małych plikach)

# KROK 2: Gdzie jest problem?
du -sh /var/log/sylion/ 2>/dev/null
du -sh /var/lib/sylion/ 2>/dev/null
du -sh /tmp/ 2>/dev/null
du -sh /home/user/workspace/ 2>/dev/null

# KROK 3: Największe pliki
find / -xdev -type f -size +100M -printf "%s\t%p\n" 2>/dev/null | \
  sort -rn | head -20

# KROK 4: Logi rotacji
ls -lah /var/log/sylion/*.log* 2>/dev/null
ls -lah /var/log/nginx/*.log* 2>/dev/null

# KROK 5: SQLite WAL — może być ogromny
find / -xdev -name "*.db-wal" -ls 2>/dev/null

# KROK 6: Czy SQLite dostaje błąd FULL?
journalctl -u sylion.service | grep -iE "SQLITE_FULL|disk.*full|no space" | tail -20
```

**Drzewo Decyzyjne Disk Full:**
```
Wolne miejsce < 1GB?
├── NIE → Disk OK, szukaj gdzie indziej
└── TAK → Które partycje?
          ├── /var/log pełny → Rotuj logi (Sekcja 3.3.a)
          ├── /var/lib/sylion pełny → Uruchom prune_audit_log (Sekcja 3.3.b)
          ├── WAL file > 1GB → PRAGMA wal_checkpoint(TRUNCATE) (Sekcja 3.3.c)
          └── /tmp pełny → Wyczyść /tmp: rm -rf /tmp/sylion-* /tmp/*.tmp
```

---

### 2.4 Triage: DB Corruption

```bash
# KROK 1: Sprawdź integralność (ZAWSZE NAJPIERW TEN KROK)
DB_PATH="/var/lib/sylion/sylion.db"
# Lub jeśli w workspace:
DB_PATH=$(find /home/user/workspace -name "*.db" | head -1)

sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | head -20

# KROK 2: Quick check (szybszy, mniej dokładny)
sqlite3 "$DB_PATH" "PRAGMA quick_check;" 2>&1 | head -10

# KROK 3: Foreign keys
sqlite3 "$DB_PATH" "PRAGMA foreign_key_check;" 2>&1

# KROK 4: Stan WAL
sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint;" 2>&1
ls -lah ${DB_PATH}*

# KROK 5: Ile stron uszkodzonych?
sqlite3 "$DB_PATH" "PRAGMA page_count;" 2>&1
sqlite3 "$DB_PATH" "PRAGMA freelist_count;" 2>&1

# KROK 6: Sprawdź czy DB jest zablokowana
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
          │   → Zrób backup bieżącego stanu: cp sylion.db sylion.db.corrupted.$(date +%s)
          │   → Przywróć z backupu M-08 (Sekcja 3.4)
          ├── "foreign key mismatch" → Niespójna referencja
          │   → sqlite3 sylion.db "PRAGMA foreign_keys=OFF;"
          │   → Napraw referencje lub usuń osierocone rekordy
          └── WAL nie daje się zcheckpointować → Zamknij wszystkie połączenia
              → lsof i fuser, kill procesów → PRAGMA wal_checkpoint(RESTART)
```

---

### 2.5 Triage: Pipeline Stuck

```bash
# KROK 1: Czy worker żyje?
ps aux | grep -E "sylion.*(worker|pipeline|task)" | grep -v grep
systemctl status sylion-worker.service 2>/dev/null

# KROK 2: Ostatnia aktywność pipeline w DB
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT id, status, created_at, updated_at, 
          CAST((julianday('now') - julianday(updated_at)) * 1440 AS INT) as age_minutes
   FROM pipeline_jobs 
   ORDER BY updated_at DESC 
   LIMIT 10;" 2>/dev/null

# KROK 3: Zadania w statusie 'running' od dawna (>30 min)
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT id, job_type, status, updated_at 
   FROM pipeline_jobs 
   WHERE status='running' 
     AND updated_at < datetime('now', '-30 minutes');" 2>/dev/null

# KROK 4: Lock files
ls -la /var/lib/sylion/locks/ 2>/dev/null
ls -la /tmp/sylion*.lock 2>/dev/null

# KROK 5: Czy kolejka rośnie?
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT status, COUNT(*) as count 
   FROM pipeline_jobs 
   GROUP BY status;" 2>/dev/null

# KROK 6: Logi workera
journalctl -u sylion-worker.service -n 100 --no-pager 2>/dev/null
```

---

### 2.6 Triage: Auth Failure

```bash
# KROK 1: Sprawdź HTTP 401/403 w logach
journalctl -u sylion.service --since "30 minutes ago" | \
  grep -cE "401|403|Unauthorized|Forbidden"

# KROK 2: Czy problem z tokenami?
journalctl -u sylion.service --since "30 minutes ago" | \
  grep -iE "token|jwt|session|signature|expire" | tail -20

# KROK 3: Stan sesji w DB
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT COUNT(*) as total,
          SUM(CASE WHEN expires_at < datetime('now') THEN 1 ELSE 0 END) as expired,
          SUM(CASE WHEN expires_at >= datetime('now') THEN 1 ELSE 0 END) as valid
   FROM sessions;" 2>/dev/null

# KROK 4: Klucze środowiskowe
systemctl show sylion.service | grep -i "Environment" 2>/dev/null
# Sprawdź czy SECRET_KEY ustawiony (bez pokazywania wartości)
env | grep -E "SECRET|JWT|API_KEY" | sed 's/=.*/=***HIDDEN***/'

# KROK 5: Czy certyfikat TLS wygasł?
echo | openssl s_client -connect localhost:443 2>/dev/null | \
  openssl x509 -noout -dates 2>/dev/null

# KROK 6: Czas systemowy (JWT jest czasoczuły)
timedatectl status | grep -E "Local time|RTC time|synchronized"
date -u
```

---

### 2.7 Triage: Migration Failed

```bash
# KROK 1: Sprawdź wersję schema
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT * FROM alembic_version;" 2>/dev/null || \
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT * FROM schema_migrations ORDER BY id DESC LIMIT 5;" 2>/dev/null

# KROK 2: Sprawdź tabele — czy schema jest kompletna?
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT name, type FROM sqlite_master 
   WHERE type IN ('table','view') 
   ORDER BY name;"

# KROK 3: Logi migracji
journalctl -u sylion.service | grep -iE "migrat|alembic|schema|DDL" | tail -30

# KROK 4: Czy migracja jest w toku (transaction open)?
sqlite3 /var/lib/sylion/sylion.db ".timeout 1000" \
  "BEGIN EXCLUSIVE; SELECT 1; ROLLBACK;" 2>&1

# KROK 5: Backup przed jakimikolwiek działaniami
cp /var/lib/sylion/sylion.db \
   /var/lib/sylion/sylion.db.pre-migration-fix.$(date +%Y%m%d%H%M%S)
echo "Backup wykonany: $?"

# KROK 6: Sprawdź dostępność narzędzia migracji
which alembic 2>/dev/null && alembic current 2>/dev/null
which sylion 2>/dev/null && sylion db status 2>/dev/null
```
