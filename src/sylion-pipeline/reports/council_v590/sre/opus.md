# SYLION v5.9.0 — Incident Taxonomy & Severity Matrix
_Model: Claude Opus 4.7 | Rola: Incident Taxonomy Commander_

---

## 1. Klasy Incydentów

### 1.1 HTTP Błędy (502 / 503 / 504)

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

# Sprawdź logi nginx/caddy (reverse proxy)
tail -f /var/log/nginx/error.log
grep -E "502|503|504" /var/log/nginx/access.log | tail -50

# Sprawdź czy port aplikacji odpowiada
curl -v --max-time 5 http://127.0.0.1:8000/health
ss -tlnp | grep 8000
```

---

### 1.2 OOM — Out of Memory

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

### 1.3 Disk Full — Zapełniony Dysk

**Symptomy:** Błędy zapisu do DB, pipeline crash z `SQLITE_FULL`, logi przestają się zapisywać.

```bash
# Ogólny stan dysków
df -h
du -sh /var/lib/sylion/* 2>/dev/null | sort -rh | head -20
du -sh /home/user/workspace/SYLION_v590_work/* | sort -rh | head -10

# Znajdź największe pliki
find /var/log -name "*.log" -size +100M -ls 2>/dev/null
find /tmp -size +50M -ls 2>/dev/null

# SQLite WAL (Write-Ahead Log) — może się rozrosnąć
ls -lah /var/lib/sylion/*.db /var/lib/sylion/*.db-wal /var/lib/sylion/*.db-shm 2>/dev/null
```

---

### 1.4 DB Corruption — Uszkodzenie Bazy Danych

**Symptomy:** `sqlite3.DatabaseError: database disk image is malformed`, błędy PRAGMA integrity_check.

```bash
# Sprawdź integralność bazy
sqlite3 /var/lib/sylion/sylion.db "PRAGMA integrity_check;"
sqlite3 /var/lib/sylion/sylion.db "PRAGMA quick_check;"
sqlite3 /var/lib/sylion/sylion.db "PRAGMA foreign_key_check;"

# Sprawdź page count i freelist
sqlite3 /var/lib/sylion/sylion.db "PRAGMA page_count; PRAGMA freelist_count;"

# Zamknij WAL i checkpoint
sqlite3 /var/lib/sylion/sylion.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

---

### 1.5 Pipeline Stuck — Zablokowany Pipeline

**Symptomy:** Zadania w kolejce nie postępują, worker nie przetwarza, logi bez aktywności >15 min.

```bash
# Sprawdź procesy pipeline
ps aux | grep -E "sylion|celery|worker|pipeline" | grep -v grep

# Sprawdź kolejkę zadań (jeśli Redis/Celery)
redis-cli LLEN sylion:queue:default 2>/dev/null
redis-cli KEYS "sylion:*" 2>/dev/null

# Sprawdź lock files
ls -la /var/lib/sylion/locks/ 2>/dev/null
lsof /var/lib/sylion/sylion.db 2>/dev/null

# Wiek ostatniego przetworzonego rekordu
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT MAX(processed_at) FROM pipeline_jobs WHERE status='completed';"
```

---

### 1.6 Auth Failure — Błąd Uwierzytelniania

**Symptomy:** 401/403 dla wszystkich żądań, tokeny wygasłe, sesje nieprawidłowe.

```bash
# Sprawdź logi auth
journalctl -u sylion.service | grep -iE "auth|token|session|403|401" | tail -50

# Sprawdź wygaśnięcie sesji w DB
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT COUNT(*) FROM sessions WHERE expires_at < datetime('now');"

# Sprawdź ważność certyfikatów/kluczy
openssl x509 -in /etc/sylion/tls.crt -noout -dates 2>/dev/null

# Sprawdź zmienne środowiskowe (SECRET_KEY, JWT_SECRET)
systemctl show sylion.service | grep -i "environment\|secret" 2>/dev/null
```

---

### 1.7 Migration Failed — Błąd Migracji

**Symptomy:** Aplikacja nie startuje po deploymencie, błąd `migration failed`, tabele brakujące.

```bash
# Sprawdź stan migracji
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT * FROM alembic_version;" 2>/dev/null || \
sqlite3 /var/lib/sylion/sylion.db \
  "SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 10;" 2>/dev/null

# Sprawdź strukturę tabel
sqlite3 /var/lib/sylion/sylion.db ".schema"
sqlite3 /var/lib/sylion/sylion.db ".tables"

# Logi migracji
journalctl -u sylion.service | grep -iE "migrat|alembic|schema" | tail -30
find /var/log/sylion/ -name "migration*.log" -exec tail -50 {} \; 2>/dev/null
```

---

## 2. Severity Matrix (P0–P4)

| Priorytet | Nazwa | Kryteria | SLA Reakcja | SLA Rozwiązanie | Eskalacja |
|-----------|-------|----------|-------------|-----------------|-----------|
| **P0** | Critical | Całkowita niedostępność produkcji; utrata danych; DB corruption; wszyscy użytkownicy dotknięci | 5 min | 1 godz. | Natychmiastowa: CTO + Lead Dev + DevOps |
| **P1** | Major | >50% użytkowników niedostępnych; pipeline całkowicie zablokowany; auth failure system-wide | 15 min | 4 godz. | 15 min: Lead Dev + DevOps On-call |
| **P2** | Moderate | Degradacja wydajności; błędy dla <50% użytkowników; disk >90%; OOM intermittent | 30 min | 8 godz. | 30 min: DevOps On-call |
| **P3** | Minor | Błędy dla <5% użytkowników; ostrzeżenia systemowe; disk >80% | 2 godz. | 24 godz. | Standardowy ticket do następnego dnia |
| **P4** | Informational | Zadania wymagające uwagi; niekrytyczne błędy; wnioski o ulepszenia | 8 godz. | 72 godz. | Backlog sprint |

### Matryca Decyzyjna — Wyznaczanie Severity

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

---

## 3. Procedura Eskalacji

### Kanały Komunikacji

```
P0/P1: Natychmiastowy alert → PagerDuty → Slack #incidents-critical → Telekon (war room)
P2:    Alert → Slack #incidents-prod → Ticket JIRA (oznaczony HIGH)
P3:    Slack #alerts-sre → Ticket JIRA (oznaczony MEDIUM)
P4:    Ticket JIRA (oznaczony LOW)
```

### Kroki Eskalacji P0

```bash
# 1. Ogłoś incident w Slack (szablon)
echo "🚨 [P0 INCIDENT] SYLION $(date -u +%Y-%m-%dT%H:%M:%SZ)
Opis: [OPIS]
Impact: [ILE UŻYTKOWNIKÓW / JAKIE DANE]
Incident Commander: [IMIĘ]
Bridge: [LINK DO WAR ROOM]
Status: INVESTIGATING"

# 2. Utwórz incident log
INCIDENT_ID="INC-$(date +%Y%m%d-%H%M%S)"
mkdir -p /var/log/sylion/incidents/${INCIDENT_ID}
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) INCIDENT OPENED" \
  > /var/log/sylion/incidents/${INCIDENT_ID}/timeline.log

# 3. Zbierz snapshot systemu
{
  echo "=== SYSTEM SNAPSHOT: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  uptime; free -h; df -h; ps aux --sort=-%cpu | head -20
  journalctl -u sylion.service -n 100 --no-pager
} > /var/log/sylion/incidents/${INCIDENT_ID}/snapshot.txt
```

### Czas Eskalacji (jeśli brak odpowiedzi)

| Priorytet | Brak odpowiedzi po | Eskaluj do |
|-----------|-------------------|------------|
| P0 | 10 min | CTO bezpośrednio |
| P1 | 30 min | Lead Dev + Manager |
| P2 | 2 godz. | DevOps Lead |
| P3 | 24 godz. | Team Lead (następny dzień) |
