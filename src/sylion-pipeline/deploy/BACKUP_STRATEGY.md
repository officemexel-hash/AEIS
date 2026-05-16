# BACKUP_STRATEGY.md â€” SYLION Dashboard
**Wersja:** 1.0.0  
**Patch:** P8-BACKUP-SCRIPT  
**Projekt:** SYLION v5.9.3  
**Data:** 2026-04-19

---

## 1. Cele odtworzenia (RPO / RTO)

| Metryka | WartoĹ›Ä‡ | Uzasadnienie |
|---------|---------|--------------|
| **RPO** (Recovery Point Objective) | **24 godziny** | Backup wykonywany codziennie o 02:00 UTC. Maksymalna utrata danych = dane z 1 dnia roboczego. |
| **RTO** (Recovery Time Objective) | **15 minut** | Procedura restore: zatrzymanie serwisu (1 min) + skopiowanie backupu (1 min) + dekompresja (1 min) + uruchomienie (2 min) + weryfikacja (5 min) = ~10â€“15 min. |

---

## 2. Chroniony zasĂłb

| ZasĂłb | ĹšcieĹĽka domyĹ›lna | Typ | KrytycznoĹ›Ä‡ |
|-------|-----------------|-----|-------------|
| SYLION AEIS Runtime DB | `/var/lib/sylion/sylion_aeis.db` | SQLite 3 | **KRYTYCZNY** |

Baza zawiera: dane uĹĽytkownikĂłw, logi audytu, konfiguracjÄ™ agentĂłw, historiÄ™ pipeline'Ăłw, klucze API, rekordy rozliczeniowe.

---

## 3. Retencja

| Poziom | Ile kopii | Katalog | Harmonogram |
|--------|-----------|---------|-------------|
| **Daily** | 7 (ostatni tydzieĹ„) | `/var/backups/sylion/daily/` | Codziennie, 02:00 UTC |
| **Weekly** | 4 (ostatni miesiÄ…c) | `/var/backups/sylion/weekly/` | Co niedzielÄ™ (automatycznie z daily) |
| **Monthly** | 6 (ostatnie 6 miesiÄ™cy) | `/var/backups/sylion/monthly/` | 1. dzieĹ„ miesiÄ…ca (automatycznie z daily) |

---

## 4. Format pliku backup

```
sylion_aeis_YYYYMMDD_HHMMSS.db.gz
```

PrzykĹ‚ad: `sylion_aeis_20260419_020001.db.gz`

- Metoda backup: **SQLite Online Backup API** (`sqlite3 .backup`) â€” bezpieczna dla dziaĹ‚ajÄ…cej bazy, WAL-aware, nie blokuje zapisĂłw.
- Kompresja: **gzip -9** (~60â€“80% redukcja rozmiaru dla typowych danych SQLite).

---

## 5. Procedura RESTORE (krok po kroku)

### Wymagania wstÄ™pne
- DostÄ™p SSH do serwera
- Sudo lub uprawnienia do pliku backup i serwisu
- Zainstalowane: `gzip`, `sqlite3`

### Kroki restore

```bash
# 1. Zatrzymaj serwis (aby uniknÄ…Ä‡ konfliktĂłw zapisu)
sudo systemctl stop sylion-dashboard.service

# 2. UtwĂłrz kopiÄ™ bieĹĽÄ…cej bazy (bezpieczeĹ„stwo)
sudo cp /var/lib/sylion/sylion_aeis.db \
        /var/lib/sylion/sylion_aeis.db.pre-restore.$(date +%Y%m%d_%H%M%S)

# 3. Wybierz plik backup do przywrĂłcenia
ls -lh /var/backups/sylion/daily/
# Wybierz np.: sylion_aeis_20260419_020001.db.gz

# 4. Zdekompresuj backup do katalogu tymczasowego
BACKUP_FILE="sylion_aeis_20260419_020001.db.gz"
gunzip -c "/var/backups/sylion/daily/${BACKUP_FILE}" > /tmp/sylion_restore.db

# 5. Zweryfikuj integralnoĹ›Ä‡ przywracanej bazy
sqlite3 /tmp/sylion_restore.db "PRAGMA integrity_check;"
# Wynik musi byÄ‡: ok

# 6. SprawdĹş zawartoĹ›Ä‡ (podstawowa weryfikacja)
sqlite3 /tmp/sylion_restore.db "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM audit_log;"

# 7. PrzenieĹ› bazÄ™ na miejsce docelowe
sudo mv /tmp/sylion_restore.db /var/lib/sylion/sylion_aeis.db
sudo chown www-data:www-data /var/lib/sylion/sylion_aeis.db
sudo chmod 640 /var/lib/sylion/sylion_aeis.db

# 8. Uruchom serwis
sudo systemctl start sylion-dashboard.service

# 9. Weryfikacja â€” sprawdĹş logi i endpoint health
sudo systemctl status sylion-dashboard.service
curl -sf http://localhost:8421/api/health/live && echo "OK" || echo "FAIL"
curl -sf http://localhost:8421/api/health/ready && echo "OK" || echo "FAIL"

# 10. Zapisz zdarzenie w logu audytu
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | RESTORE | ${BACKUP_FILE} | $(whoami)" \
    >> /var/log/sylion/restore-events.log
```

---

## 6. Storage â€” lokalne + zewnÄ™trzne

### Lokalne (domyĹ›lne)

```
/var/backups/sylion/
â”śâ”€â”€ daily/      â† 7 plikĂłw (codzienne)
â”śâ”€â”€ weekly/     â† 4 pliki (tygodniowe)
â””â”€â”€ monthly/    â† 6 plikĂłw (miesiÄ™czne)
```

Wymagane miejsce (orientacyjnie przy DB 50 MB): ~50 MB Ă— (7+4+6) Ă— 0.25 (kompresja) â‰ **~190 MB**.

### ZewnÄ™trzne (manual rsync do drugiego VPS)

Backupy lokalne naleĹĽy regularnie synchronizowaÄ‡ do zewnÄ™trznego serwera:

```bash
# PrzykĹ‚adowe polecenie rsync â€” uruchom rÄ™cznie lub dodaj jako dodatkowy krok w skrypcie
rsync -avz --delete \
    /var/backups/sylion/ \
    backup-user@<BACKUP_VPS_IP>:/backup/sylion/

# Wygodne: dodaj do crontab lub osobnego systemd timer
# 0 4 * * * rsync -avz /var/backups/sylion/ backup-user@<IP>:/backup/sylion/ >> /var/log/sylion/rsync-backup.log 2>&1
```

Wymagania dla drugiego VPS:
- DostÄ™p SSH z kluczem (bez hasĹ‚a dla automatyzacji)
- Katalog `/backup/sylion/` z prawami zapisu dla backup-user
- Minimum 500 MB wolnego miejsca

---

## 7. Instalacja i konfiguracja

### Pliki do wdroĹĽenia

```bash
# Skrypt backup
sudo cp scripts/backup_db.sh /opt/sylion/scripts/backup_db.sh
sudo chmod 750 /opt/sylion/scripts/backup_db.sh
sudo chown root:www-data /opt/sylion/scripts/backup_db.sh

# Systemd units
sudo cp deploy/sylion-backup.service /etc/systemd/system/
sudo cp deploy/sylion-backup.timer   /etc/systemd/system/

# Reload i wĹ‚Ä…cz timer
sudo systemctl daemon-reload
sudo systemctl enable --now sylion-backup.timer

# SprawdĹş status
sudo systemctl status sylion-backup.timer
sudo systemctl list-timers sylion-backup.timer
```

### Opcjonalny plik konfiguracyjny (env)

UtwĂłrz `/etc/sylion/backup.env` aby nadpisaÄ‡ domyĹ›lne Ĺ›cieĹĽki:

```bash
# /etc/sylion/backup.env
SYLION_DB_PATH=/var/lib/sylion/sylion_aeis.db
SYLION_BACKUP_DIR=/var/backups/sylion
SYLION_BACKUP_KEEP_DAILY=7
SYLION_BACKUP_KEEP_WEEKLY=4
SYLION_BACKUP_KEEP_MONTHLY=6
```

### Uprawnienia do katalogu backup

```bash
sudo mkdir -p /var/backups/sylion/{daily,weekly,monthly}
sudo chown -R www-data:www-data /var/backups/sylion
sudo chmod 750 /var/backups/sylion
```

---

## 8. Monitoring

### Sprawdzenie statusu timer

```bash
# Status timera (kiedy ostatnio / kiedy nastÄ™pnie)
systemctl status sylion-backup.timer
systemctl list-timers sylion-backup.timer

# Ostatni run serwisu
systemctl status sylion-backup.service
journalctl -u sylion-backup.service --since "24 hours ago"
```

### Sprawdzenie plikĂłw backup

```bash
# Ile plikĂłw + najnowszy
ls -lht /var/backups/sylion/daily/ | head -5

# Wiek najnowszego backup (alert jeĹ›li >25h)
LATEST=$(ls -t /var/backups/sylion/daily/sylion_aeis_*.db.gz 2>/dev/null | head -1)
if [[ -n "$LATEST" ]]; then
    AGE=$(( ($(date +%s) - $(date +%s -r "$LATEST")) / 3600 ))
    echo "Wiek ostatniego backupu: ${AGE}h"
    [[ "$AGE" -gt 25 ]] && echo "ALARM: backup starszy niĹĽ 25h!"
fi
```

### Alerty (zalecane)

Dodaj do monitoringu (Prometheus/alertmanager lub cron):
- Alert jeĹ›li brak pliku backup nowszego niĹĽ 25h w `/var/backups/sylion/daily/`
- Alert jeĹ›li `systemctl is-failed sylion-backup.service` zwraca 0

---

## 9. Monthly Restore Drill (test odtwarzania)

**CzÄ™stotliwoĹ›Ä‡:** Raz w miesiÄ…cu (pierwszego roboczego dnia miesiÄ…ca).

**Cel:** Potwierdzenie ĹĽe backup faktycznie pozwala odtworzyÄ‡ dane.

### Procedura drill

```bash
# 1. Wybierz plik backup (najnowszy monthly lub dowolny daily)
BACKUP_FILE=$(ls -t /var/backups/sylion/monthly/sylion_aeis_*.db.gz 2>/dev/null | head -1)
echo "TestujÄ™: $BACKUP_FILE"

# 2. Dekompresja do Ĺ›rodowiska testowego (NIE nadpisuj produkcji!)
gunzip -c "$BACKUP_FILE" > /tmp/sylion_drill_$(date +%Y%m%d).db

# 3. Weryfikacja integralnoĹ›ci
sqlite3 /tmp/sylion_drill_$(date +%Y%m%d).db "PRAGMA integrity_check;"
# Oczekiwany wynik: ok

# 4. Weryfikacja danych â€” policz kluczowe tabele
sqlite3 /tmp/sylion_drill_$(date +%Y%m%d).db "
  SELECT 'users' AS tbl, COUNT(*) AS cnt FROM users
  UNION ALL
  SELECT 'audit_log', COUNT(*) FROM audit_log
  UNION ALL
  SELECT 'api_keys', COUNT(*) FROM api_keys;
"
# Wynik powinien byÄ‡ spĂłjny z danymi produkcji z dnia backup

# 5. Zmierz czas restore
time gunzip -c "$BACKUP_FILE" > /dev/null
# Cel RTO: <15 minut dla peĹ‚nej procedury

# 6. Zapisz wynik drill
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | DRILL | ${BACKUP_FILE} | PASS/FAIL | RTO: Xmin" \
    >> /var/log/sylion/restore-drill.log

# 7. Cleanup
rm -f /tmp/sylion_drill_$(date +%Y%m%d).db
```

### Karta wyniku drill (wypeĹ‚nij co miesiÄ…c)

| Data | Plik backup | Integrity check | Liczba users | RTO (min) | Wynik | Operator |
|------|------------|----------------|-------------|-----------|-------|---------|
| YYYY-MM-DD | sylion_aeis_....db.gz | ok | N | X | PASS/FAIL | imiÄ™ |

---

## 10. Decyzje architektoniczne

| Kwestia | Decyzja | Uzasadnienie |
|---------|---------|--------------|
| Metoda backup | `sqlite3 .backup` (Online Backup API) | Bezpieczna dla running DB, WAL-aware, bez locka na writerĂłw |
| Kompresja | gzip -9 | Brak zewnÄ™trznych zaleĹĽnoĹ›ci, ~60-80% redukcja |
| Rotacja | find + sort + head | Idempotentna, deterministyczna, brak race condition |
| Exit codes | 0/1/2/3 | UmoĹĽliwia systemd/monitoring rozrĂłĹĽnienie rodzaju bĹ‚Ä™du |
| Log format | JSON do stdout | Kompatybilny z journald, parseowalny przez logstash/grafana |
| Szyfrowanie | Brak (v1) | Backupy sÄ… lokalne; przy rsync do zewnÄ™trznego VPS uĹĽyj SSH tunelu lub gpg |
| Offsite | Manual rsync | Scope v1: automatyczny rsync w v2 (dedykowany timer) |
