# SYLION v5.9.0 — Mitigation & Recovery Procedures
_Model: GPT-5.4 | Rola: Recovery Architect_

---

## 3. Mitigation & Recovery Procedures

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
log_action "System: $(uname -a)"
log_action "Operator: $(whoami)@$(hostname)"
```

---

### 3.1 Restart Procedura (Aplikacja Down: 502/503/OOM)

```bash
#!/bin/bash
# sylion-restart.sh — bezpieczny restart SYLION
# Użycie: bash sylion-restart.sh [--force]

set -euo pipefail

DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"
SERVICE_NAME="sylion.service"
BACKUP_DIR="/var/lib/sylion/backups"

log_action "RESTART: Rozpoczynam procedurę restartu"

# KROK 1: Backup DB przed restartem
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/sylion.db.pre-restart.$(date +%Y%m%d%H%M%S)"
log_action "RESTART: Backup DB → $BACKUP_FILE"
sqlite3 "$DB_PATH" ".backup $BACKUP_FILE" 2>/dev/null || \
  cp "$DB_PATH" "$BACKUP_FILE"
echo "Backup: $BACKUP_FILE"

# KROK 2: Checkpoint WAL przed restartem
log_action "RESTART: WAL checkpoint"
sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(FULL);" 2>/dev/null || true

# KROK 3: Graceful stop
log_action "RESTART: Graceful stop"
systemctl stop "$SERVICE_NAME" 2>/dev/null || {
  docker stop sylion-app 2>/dev/null || true
}
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
systemctl start "$SERVICE_NAME" 2>/dev/null || \
  docker start sylion-app 2>/dev/null

# KROK 5: Poczekaj na gotowość
sleep 5
MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  if curl -sf --max-time 3 http://127.0.0.1:8000/health > /dev/null 2>&1; then
    log_action "RESTART: Aplikacja zdrowa po ${ELAPSED}s"
    echo "SUCCESS: SYLION gotowy"
    break
  fi
  sleep 5
  ELAPSED=$((ELAPSED + 5))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  log_action "RESTART: TIMEOUT — aplikacja nie odpowiada po ${MAX_WAIT}s"
  echo "FAILURE: Aplikacja nie odpowiada — sprawdź logi"
  journalctl -u "$SERVICE_NAME" -n 50 --no-pager
  exit 1
fi

log_action "RESTART: Zakończono pomyślnie"
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
DEPLOY_DIR="/opt/sylion"
RELEASES_DIR="/opt/sylion/releases"
CURRENT_LINK="/opt/sylion/current"
DB_PATH="/var/lib/sylion/sylion.db"
BACKUP_DIR="/var/lib/sylion/backups"

log_action "ROLLBACK: Inicjalizacja rollback ${TARGET_VERSION:-auto}"

# KROK 1: Ustal docelową wersję
if [ -z "$TARGET_VERSION" ]; then
  # Poprzednia wersja (symlink lub katalog)
  PREV=$(ls -td "$RELEASES_DIR"/v*.*.* 2>/dev/null | head -2 | tail -1)
  if [ -z "$PREV" ]; then
    echo "BŁĄD: Brak poprzedniej wersji do rollbacku"
    exit 1
  fi
  TARGET_VERSION=$(basename "$PREV")
fi

ROLLBACK_PATH="$RELEASES_DIR/$TARGET_VERSION"
if [ ! -d "$ROLLBACK_PATH" ]; then
  echo "BŁĄD: Wersja $TARGET_VERSION nie istnieje w $RELEASES_DIR"
  ls "$RELEASES_DIR/" 2>/dev/null
  exit 1
fi

log_action "ROLLBACK: Cel → $ROLLBACK_PATH"

# KROK 2: Backup bieżącego stanu DB
mkdir -p "$BACKUP_DIR"
DB_BACKUP="$BACKUP_DIR/sylion.db.pre-rollback.$(date +%Y%m%d%H%M%S)"
log_action "ROLLBACK: Backup DB → $DB_BACKUP"
sqlite3 "$DB_PATH" ".backup $DB_BACKUP" 2>/dev/null || cp "$DB_PATH" "$DB_BACKUP"

# KROK 3: Zatrzymaj aplikację
log_action "ROLLBACK: Zatrzymuję serwis"
systemctl stop sylion.service 2>/dev/null || docker stop sylion-app 2>/dev/null

# KROK 4: Przełącz symlink na poprzednią wersję
log_action "ROLLBACK: Przełączam symlink $CURRENT_LINK → $ROLLBACK_PATH"
ln -sfn "$ROLLBACK_PATH" "$CURRENT_LINK"

# KROK 5: Rollback schematu DB (jeśli migracje są odwracalne)
log_action "ROLLBACK: Sprawdzam konieczność rollback migracji DB"
CURRENT_SCHEMA=$(sqlite3 "$DB_PATH" "SELECT version_num FROM alembic_version;" 2>/dev/null || echo "unknown")
log_action "ROLLBACK: Aktualna wersja schema: $CURRENT_SCHEMA"

# Jeśli rollback.sql istnieje dla wersji
ROLLBACK_SQL="$ROLLBACK_PATH/migrations/rollback_to_${TARGET_VERSION}.sql"
if [ -f "$ROLLBACK_SQL" ]; then
  log_action "ROLLBACK: Wykonuję rollback SQL: $ROLLBACK_SQL"
  sqlite3 "$DB_PATH" < "$ROLLBACK_SQL"
else
  log_action "ROLLBACK: Brak rollback SQL — schema pozostaje bez zmian"
  echo "UWAGA: Schema DB nie została cofnięta — sprawdź zgodność ręcznie"
fi

# KROK 6: Start z poprzednią wersją
log_action "ROLLBACK: Uruchamiam poprzednią wersję"
systemctl start sylion.service 2>/dev/null || docker start sylion-app 2>/dev/null

sleep 5
if curl -sf --max-time 5 http://127.0.0.1:8000/health > /dev/null 2>&1; then
  log_action "ROLLBACK: SUKCES — SYLION $TARGET_VERSION działa"
  echo "ROLLBACK SUCCESS: Wersja $TARGET_VERSION aktywna"
else
  log_action "ROLLBACK: FAILURE — aplikacja nie odpowiada"
  echo "ROLLBACK FAILURE: Sprawdź logi: journalctl -u sylion.service -n 100"
  exit 1
fi
```

---

### 3.3 Prune — Oczyszczenie Danych (disk full / wydajność)

#### 3.3.a Prune Audit Log

```bash
#!/bin/bash
# manual_prune_audit_log.sh — ręczne czyszczenie audit_log
# Użycie: bash manual_prune_audit_log.sh [--dry-run] [--older-than-days 90]

DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"
OLDER_THAN_DAYS="${OLDER_THAN_DAYS:-90}"
DRY_RUN="${DRY_RUN:-0}"

for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=1 ;;
    --older-than-days) shift; OLDER_THAN_DAYS="$1" ;;
  esac
done

echo "PRUNE AUDIT LOG: Rekordy starsze niż ${OLDER_THAN_DAYS} dni"

# Ile rekordów do usunięcia?
COUNT=$(sqlite3 "$DB_PATH" \
  "SELECT COUNT(*) FROM audit_log 
   WHERE created_at < datetime('now', '-${OLDER_THAN_DAYS} days');")

echo "Znaleziono rekordów: $COUNT"

if [ "$DRY_RUN" = "1" ]; then
  echo "DRY RUN — brak zmian"
  exit 0
fi

if [ "$COUNT" -eq 0 ]; then
  echo "Brak rekordów do usunięcia"
  exit 0
fi

# Backup przed prunem
BACKUP="$DB_PATH.pre-prune.$(date +%Y%m%d%H%M%S)"
sqlite3 "$DB_PATH" ".backup $BACKUP"
echo "Backup: $BACKUP"

# Usuń w partiach po 10000 (unikaj długich transakcji)
log_action "PRUNE: Usuwanie ${COUNT} rekordów audit_log"
sqlite3 "$DB_PATH" << 'SQL'
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

-- Usuń stare rekordy
DELETE FROM audit_log 
WHERE rowid IN (
  SELECT rowid FROM audit_log 
  WHERE created_at < datetime('now', '-90 days')
  LIMIT 10000
);
SQL

# Sprawdź wynik
NEW_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM audit_log;")
echo "Pozostało rekordów audit_log: $NEW_COUNT"

# Odzyskaj przestrzeń
echo "Uruchamiam VACUUM..."
sqlite3 "$DB_PATH" "VACUUM;"
echo "VACUUM zakończony"

log_action "PRUNE AUDIT LOG: zakończono — usunięto $COUNT rekordów"
```

#### 3.3.b Prune Sessions

```bash
#!/bin/bash
# manual_prune_sessions.sh — ręczne czyszczenie wygasłych sesji

DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"

echo "PRUNE SESSIONS: Wygasłe sesje"

COUNT=$(sqlite3 "$DB_PATH" \
  "SELECT COUNT(*) FROM sessions WHERE expires_at < datetime('now');")
echo "Wygasłych sesji: $COUNT"

if [ "$COUNT" -gt 0 ]; then
  BACKUP="$DB_PATH.pre-prune-sessions.$(date +%Y%m%d%H%M%S)"
  sqlite3 "$DB_PATH" ".backup $BACKUP"
  
  sqlite3 "$DB_PATH" \
    "DELETE FROM sessions WHERE expires_at < datetime('now');"
  
  DELETED=$?
  echo "Usunięto sesje (status: $DELETED)"
  sqlite3 "$DB_PATH" "VACUUM;"
  log_action "PRUNE SESSIONS: Usunięto $COUNT wygasłych sesji"
fi
```

#### 3.3.c WAL Checkpoint

```bash
# Wymuś checkpoint WAL i skompresuj
sqlite3 /var/lib/sylion/sylion.db << 'SQL'
PRAGMA wal_checkpoint(TRUNCATE);
PRAGMA auto_vacuum=INCREMENTAL;
PRAGMA incremental_vacuum(1000);
SQL

# Sprawdź rozmiary po
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

log_action "RESTORE M-08: Inicjalizacja przywracania DB"

# KROK 1: Znajdź backup M-08 jeśli nie podany
if [ -z "$BACKUP_FILE" ]; then
  # Szukaj pliku z "m08" lub backupu z 8. dnia miesiąca
  BACKUP_FILE=$(ls -t "$BACKUP_DIR"/sylion.db.m08.*.sqlite \
                   "$BACKUP_DIR"/sylion.db.*-08T* \
                   "$BACKUP_DIR"/*.db.backup 2>/dev/null | head -1)
  
  if [ -z "$BACKUP_FILE" ]; then
    echo "BŁĄD: Nie znaleziono backupu M-08 w $BACKUP_DIR"
    echo "Dostępne backupy:"
    ls -lah "$BACKUP_DIR"/ 2>/dev/null || echo "Katalog backupów pusty"
    exit 1
  fi
fi

echo "Backup M-08 do odtworzenia: $BACKUP_FILE"

# KROK 2: Weryfikuj backup
echo "Weryfikacja backupu..."
INTEGRITY=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" 2>&1 | head -1)
if [ "$INTEGRITY" != "ok" ]; then
  echo "BŁĄD: Backup uszkodzony — integrity_check: $INTEGRITY"
  echo "Sprawdź inne backupy w: $BACKUP_DIR"
  ls -lah "$BACKUP_DIR"/*.sqlite "$BACKUP_DIR"/*.db 2>/dev/null | head -20
  exit 1
fi
echo "Backup zdrowy: $INTEGRITY"

# KROK 3: Zatrzymaj aplikację
log_action "RESTORE M-08: Zatrzymuję serwis"
systemctl stop sylion.service 2>/dev/null || \
  docker stop sylion-app 2>/dev/null || true

# Upewnij się że nikt nie trzyma DB
sleep 3
if lsof "$DB_PATH" 2>/dev/null | grep -q .; then
  echo "UWAGA: DB jest nadal otwarta — zamykam procesy"
  fuser -k "$DB_PATH" 2>/dev/null || true
  sleep 2
fi

# KROK 4: Zachowaj bieżącą (uszkodzoną) DB
CORRUPTED_SAVE="$DB_PATH.corrupted.$(date +%Y%m%d%H%M%S)"
log_action "RESTORE M-08: Archiwizuję uszkodzoną DB → $CORRUPTED_SAVE"
mv "$DB_PATH" "$CORRUPTED_SAVE" 2>/dev/null || cp "$DB_PATH" "$CORRUPTED_SAVE"
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm" 2>/dev/null || true

# KROK 5: Odtwórz z backupu
log_action "RESTORE M-08: Kopiuję backup → $DB_PATH"
sqlite3 "$BACKUP_FILE" ".backup $DB_PATH"
# Alternatywnie: cp "$BACKUP_FILE" "$DB_PATH"

# KROK 6: Weryfikuj odtworzoną DB
NEW_INTEGRITY=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | head -1)
echo "Integralność odtworzonej DB: $NEW_INTEGRITY"

if [ "$NEW_INTEGRITY" != "ok" ]; then
  echo "BŁĄD KRYTYCZNY: Odtworzona DB jest uszkodzona!"
  log_action "RESTORE M-08: FAILURE — odtworzona DB uszkodzona"
  exit 1
fi

# KROK 7: Sprawdź dane
TABLE_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
echo "Liczba tabel w odtworzonej DB: $TABLE_COUNT"

# KROK 8: Uruchom aplikację
log_action "RESTORE M-08: Uruchamiam serwis"
systemctl start sylion.service 2>/dev/null || \
  docker start sylion-app 2>/dev/null

sleep 8
if curl -sf --max-time 10 http://127.0.0.1:8000/health > /dev/null 2>&1; then
  log_action "RESTORE M-08: SUKCES"
  echo "RESTORE SUCCESS: SYLION działa z backupu M-08"
  echo "UWAGA: Dane od $(sqlite3 "$BACKUP_FILE" "SELECT MAX(created_at) FROM audit_log;" 2>/dev/null) mogą być utracone"
else
  log_action "RESTORE M-08: FAILURE — serwis nie odpowiada"
  echo "FAILURE: Sprawdź logi: journalctl -u sylion.service -n 100"
  exit 1
fi
```

---

### 3.5 Wznowienie Pipeline po Crash

```bash
#!/bin/bash
# resume_pipeline.sh — wznowienie pipeline SYLION po crash/stuck
# Użycie: bash resume_pipeline.sh [--force-reset-stuck]

DB_PATH="${SYLION_DB:-/var/lib/sylion/sylion.db}"
FORCE_RESET="${1:-}"

log_action "PIPELINE RESUME: Inicjalizacja"

# KROK 1: Sprawdź stuck jobs
echo "=== ZADANIA PIPELINE W STATUSIE 'running' > 30 min ==="
sqlite3 "$DB_PATH" << 'SQL'
SELECT id, job_type, status, created_at, updated_at,
       CAST((julianday('now') - julianday(updated_at)) * 60 AS INTEGER) as stuck_minutes
FROM pipeline_jobs 
WHERE status = 'running' 
  AND updated_at < datetime('now', '-30 minutes')
ORDER BY stuck_minutes DESC;
SQL

# KROK 2: Usuń stale lock files
echo "=== CZYSZCZENIE LOCK FILES ==="
find /var/lib/sylion/locks/ -name "*.lock" -mmin +60 -ls 2>/dev/null
if [ "$FORCE_RESET" = "--force-reset-stuck" ]; then
  find /var/lib/sylion/locks/ -name "*.lock" -mmin +60 -delete 2>/dev/null
  find /tmp -name "sylion*.lock" -mmin +60 -delete 2>/dev/null
  log_action "PIPELINE RESUME: Usunięto stale lock files"
  echo "Lock files wyczyszczone"
fi

# KROK 3: Reset stuck jobs do 'pending' (z --force-reset-stuck)
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
  log_action "PIPELINE RESUME: Reset $RESET_COUNT stuck jobs → pending"
  echo "Reset zadań: $RESET_COUNT"
fi

# KROK 4: Restart workera pipeline
log_action "PIPELINE RESUME: Restart worker"
systemctl restart sylion-worker.service 2>/dev/null || {
  # Fallback: znajdź i uruchom worker ręcznie
  WORKER_CMD=$(systemctl show sylion-worker.service -p ExecStart 2>/dev/null | \
    sed 's/ExecStart=//')
  if [ -n "$WORKER_CMD" ]; then
    eval "$WORKER_CMD" &
    log_action "PIPELINE RESUME: Worker uruchomiony ręcznie"
  else
    echo "UWAGA: Nie można automatycznie uruchomić workera"
    echo "Uruchom ręcznie: sylion worker start (lub odpowiedni komend)"
  fi
}

# KROK 5: Monitoruj wznowienie przez 5 minut
echo "=== MONITOROWANIE PIPELINE (5 min) ==="
for i in 1 2 3 4 5; do
  sleep 60
  STATUS=$(sqlite3 "$DB_PATH" \
    "SELECT status, COUNT(*) FROM pipeline_jobs 
     WHERE updated_at > datetime('now', '-2 minutes')
     GROUP BY status;" 2>/dev/null)
  echo "$(date -u +%H:%M:%S) — Aktywność: $STATUS"
done

log_action "PIPELINE RESUME: Zakończono procedurę wznowienia"
echo "PIPELINE RESUME: Sprawdź dashboard lub logi workera"
```
